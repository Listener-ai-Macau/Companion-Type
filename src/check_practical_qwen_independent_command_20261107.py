"""Real public60s independent input, cancellation, resume and cache-only recovery.

Run only after the full neural comparison exits. This owns an isolated public
fixture task; no user recording, device, UI or private-task publisher is used.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,subprocess,sys,time,wave
from practical_io_20261107 import atomic_json,stop_owned_family
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-native17-r5'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for process in psutil.process_iter(['cmdline']):
    try:assert not any(Path(arg).name in ['practical_qwen_checkpoint_worker_20261107.py','run_practical_qwen_checkpoint_20261107.py','practical_qwen_bounded_worker_20261107.py','moss_night_gpu_worker_20261104.py'] for arg in process.info['cmdline'] or []),'Wait for the existing model before this real command control'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
assert not (C/'independent-command-proof.json').exists()
assets=Path('E:/CodexData/Companion/.model-cache/qwen-native17-asr-20261107/independent-public60-control');assets.mkdir(exist_ok=False)
case=read(C/'audio-only.json')[0];assert sha(case['audio'])==case['audioSha256']
audio=assets/'public-original-first60s.wav'
with wave.open(case['audio'],'rb') as source:
    params=source.getparams();pcm=source.readframes(960000)
with wave.open(str(audio),'wb') as output:output.setparams(params);output.writeframes(pcm)
assert len(pcm)==1920000
root=assets/'task';cli=Path(__file__).with_name('companion_native_asr_20261107.py')
command=[sys.executable,str(cli),'--audio',str(audio),'--model-pack',str(C/'model-pack.json'),'--work-dir',str(root)]
events=[]
def run(label,*,resume=False,cancel_after_first=False):
    outlog=C/(label+'-stdout.json');errlog=C/(label+'-stderr.log');started=time.perf_counter();cancelled=False;child=None;owned=None
    try:
        with outlog.open('xb') as stdout,errlog.open('xb') as stderr:
            child=subprocess.Popen(command+(['--resume'] if resume else []),stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid)
            while child.poll() is None:
                if time.perf_counter()-started>600:raise RuntimeError('Public independent command control timed out; preserve this attempt')
                if cancel_after_first and not cancelled and (root/'task.json').exists():
                    task=read(root/'task.json');state=root/'control/full/transcripts'/task['meeting']/'state.json'
                    if state.exists():
                        progress=read(state)
                        if 0<progress.get('completedWindows',0)<progress.get('totalWindows',0):
                            stop=root/'stop.request';assert stop.resolve().parent==root.resolve() and not stop.exists();stop.write_text('Actual public cancellation after one committed root\n');cancelled=True
                time.sleep(.2)
        row={'label':label,'exitCode':child.returncode,'wholeControllerFamilySeconds':time.perf_counter()-started,'cancelRequestedAfterFirstCommittedRoot':cancelled}
        events.append(row);return row
    finally:
        if child is not None and child.poll() is None:stop_owned_family(child,owned)
first=run('independent-real-start-cancel',cancel_after_first=True)
assert first['cancelRequestedAfterFirstCommittedRoot'] and first['exitCode']!=0
task=read(root/'task.json');out=root/'control/full/transcripts'/task['meeting'];node0=out/'nodes/000000-root.json'
assert task['state']=='INCOMPLETE_RETAINED_RESUMABLE' and (out/'text-draft.json').exists() and read(out/'text-draft.json')['isFinal'] is False
first_node_sha=sha(node0);stop=root/'stop.request';assert stop.resolve().parent==root.resolve();stop.unlink()
resumed=run('independent-real-resume',resume=True);assert resumed['exitCode']==0
task=read(root/'task.json');complete=read(out/'completed-state.json');assert complete['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
assert complete['reusedNodeFiles']>=1 and complete['newNeuralCalls']>0 and sha(node0)==first_node_sha
assert task['originalAudioUnchanged'] and complete['completedWindows']==2 and complete['allAudioSamplesCoveredOnce']
for index in [0,1]:
    actual=read(out/'nodes'/('%06d-root.json'%index))['raw']
    reference_execution=read(C/'full/transcripts/S_R004S03C01/nodes'/('%06d-root.json'%index))['raw']
    assert actual['generatedIds']==reference_execution['generatedIds'] and actual['text']==reference_execution['text'],'Independent entry changed native generation on identical public audio'
output=out/'model-output.json';output_sha=sha(output);doc=read(output)
assert json.loads((C/'independent-real-resume-stdout.json').read_text())==doc
rust=R/'companion-device-closure055/packages/meeting-transcript/src/lib.rs';assert sha(rust)=='f8f5b87017ebf10616b93d36520bab388f7e63033187bc289dfa1034b3af1684'
checker='E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe'
checked=subprocess.run([checker,str(output),'60000'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW);assert checked.returncode==0,checked.stderr
cache=run('independent-complete-cache-reopen',resume=True);cached=read(out/'state.json')
assert cache['exitCode']==0 and cached['newNeuralCalls']==0 and not cached['modelLoaded'] and sha(output)==output_sha
missing=out/'nodes/000001-root.json';held=missing.with_suffix('.json.held')
assert missing.resolve().is_relative_to(root.resolve()) and held.resolve().is_relative_to(root.resolve()) and not held.exists();held_sha=sha(missing);missing.rename(held)
for label in ['independent-missing-node-refusal','independent-missing-node-refusal-again']:
    row=run(label,resume=True);failed=read(out/'state.json')
    assert row['exitCode']!=0 and failed['completedCacheOnly'] and failed['newNeuralCalls']==0 and not failed['modelLoaded']
    assert sha(output)==output_sha and sha(held)==held_sha
assert held.resolve().is_relative_to(root.resolve()) and missing.resolve().is_relative_to(root.resolve()) and not missing.exists();held.rename(missing)
restored=run('independent-restored-node-cache-reopen',resume=True);restored_state=read(out/'state.json')
assert restored['exitCode']==0 and restored_state['newNeuralCalls']==0 and not restored_state['modelLoaded'] and sha(output)==output_sha
assert 'error' not in read(root/'task.json') and any(r.get('error') for r in read(root/'task.json')['attempts']),'Successful recovery must clear the current error and retain failed-attempt evidence'
proof={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_INDEPENDENT_NATIVE_INPUT_CANCEL_RESUME_CACHE_AND_SHARED_DOCUMENT',
  'audioSeconds':60.,'publicOriginalSourceAudioSha256':case['audioSha256'],'publicInputSha256':sha(audio),
  'cliSourceSha256':sha(cli),'modelPackSha256':sha(C/'model-pack.json'),'outputSha256':output_sha,
  'actualCancellationAfterCommittedFirstRoot':True,'firstRootRawBytesReusedUnchanged':True,'independentNativeIdsAndTextMatchResearchOnSameAudio':True,
  'actualSharedRustProductDocumentPassed':True,'completeCacheZeroModelExactOutput':True,'missingCommittedNodeRefusedTwiceZeroModel':True,
  'restoredOriginalNodeReopensZeroModel':True,'originalAudioUnchanged':sha(audio)==read(root/'task.json')['binding']['audioSha256'],
  'knownOwnedWorkerAttempts':read(root/'task.json')['attempts'],'controlEvents':events,
  'privateAudioUploaded':False,'privateTaskPublished':False,'publicFixtureOnly':True,'installedAppOrPhoneCardPassed':False,'qualityQualified':False}
atomic_json(C/'independent-command-proof.json',proof)
print(json.dumps({'state':proof['state'],'events':events,'qualityQualified':False}))
