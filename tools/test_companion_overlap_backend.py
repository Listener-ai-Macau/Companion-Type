"""Routing/provenance checks; synthetic PCM, no model inference or device."""
from pathlib import Path
import tempfile
import subprocess
import sys
import json
import shutil
import wave
from companion_overlap_backend import review_result,model_turn,fresh_stages

with tempfile.TemporaryDirectory() as folder:
    root=Path(folder)
    for name in ['original','left','right']:
        with wave.open(str(root/(name+'.wav')),'wb') as w:
            w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(bytes(32000))
    source=root/'original.wav';before=source.read_bytes()
    separation={'files':[str(root/'left.wav'),str(root/'right.wav')],'inferenceSeconds':10}
    speech={'speechSeconds':[.8,.6],'stageWallSeconds':.02}
    transcription={'texts':['甲的发言','乙的回应','原混音文字'],'stageWallSeconds':2}
    result=review_result(source,5000,16000,separation,speech,transcription)
    assert result['status']=='separated_candidates_need_review'
    assert result['reviewRequired'] and all(x['speakerId'] is None and x['role'] is None for x in result['lanes'])
    assert result['source']['startMs']==0 and result['source']['endMs']==1000
    assert result['source']['callerProvidedOriginOffsetMs']==5000
    assert not result['source']['originRecordingBindingVerified'], 'caller offset cannot become verified source timing'
    assert '甲的发言' in result['minutesInput']['text'] and '乙的回应' in result['minutesInput']['text']
    result=review_result(source,0,16000,separation,{'speechSeconds':[.8,0]},transcription)
    assert result['status']=='original_retained_no_reliable_second_voice'
    assert result['minutesInput']['text']=='原混音文字'
    assert not any(x['includeAsCandidate'] for x in result['lanes']), 'phantom lane must not enter minutes'
    try:review_result(source,-1,16000,separation,speech,transcription)
    except ValueError:pass
    else:raise AssertionError('negative source offset accepted')
    try:review_result(source,0,16001,separation,speech,transcription)
    except ValueError:pass
    else:raise AssertionError('wrong lane length accepted')
    assert source.read_bytes()==before,'original audio changed'
    with model_turn(root):
        check=subprocess.run([sys.executable,'-c',
            'from companion_overlap_backend import model_turn; from pathlib import Path; import sys\n'
            'try:\n with model_turn(Path(sys.argv[1])): pass\n'
            'except RuntimeError: sys.exit(0)\nelse: sys.exit(1)',str(root)],cwd=Path(__file__).parent)
        assert check.returncode==0,'second process acquired the same model turn'
    with model_turn(root):pass
    components=root/'components';components.mkdir()
    (components/'prepare.json').write_text(json.dumps({'sourceRevision':'fake-test-only','modelExpectedSha256':'fake','files':{}}))
    (root/'silero_vad.onnx').write_bytes(b'fake-test-only')
    (root/'firered-aed-download-state.json').write_text(json.dumps({'modelFiles':{'fake':'fake-test-only'}}))
    calls=[];fail_speech=[True]
    def fake_worker(stage,request):
        calls.append(stage)
        if stage=='separate':
            paths=[]
            for i,name in enumerate(['left','right']):
                path=Path(request['directory'])/f'lane-{i}.wav';shutil.copyfile(root/(name+'.wav'),path);paths.append(str(path))
            return {'files':paths,'inferenceSeconds':10}
        if stage=='speech':
            if fail_speech[0]:fail_speech[0]=False;raise RuntimeError('simulated interruption after completed separation')
            return {'speechSeconds':[.8,.6]}
        return {'texts':['甲','乙','原混音']}
    work=root/'partial-work'
    try:fresh_stages(source,components,work,stage_runner=fake_worker)
    except RuntimeError:pass
    else:raise AssertionError('expected simulated interruption')
    stages=fresh_stages(source,components,work,stage_runner=fake_worker)
    assert calls==['separate','speech','speech','transcribe'],'completed separation was repeated after interruption'
    assert stages[0]['reusedCheckpoint'] and not stages[1]['reusedCheckpoint']
    damaged=Path(stages[0]['files'][0]);data=bytearray(damaged.read_bytes());data[-1]^=1;damaged.write_bytes(data)
    repaired=fresh_stages(source,components,work,stage_runner=fake_worker)
    assert calls.count('separate')==2,'changed derived audio was silently reused'
    assert calls.count('speech')==2 and calls.count('transcribe')==1,'unaffected, same-content stages were unnecessarily repeated'
    assert list(work.glob('separate-rejected-*.json')),'failed artifact evidence was lost'
    data=bytearray(source.read_bytes());data[-1]^=1;source.write_bytes(data)
    try:fresh_stages(source,components,work,stage_runner=fake_worker)
    except ValueError:pass
    else:raise AssertionError('different recording reused another source checkpoint')
print('Two candidates, absent second voice fallback, unknown identities, source offsets and unchanged audio passed.')
print('Interrupted-stage resume, derived-audio integrity, unaffected-stage reuse and source isolation passed; no model inference.')
