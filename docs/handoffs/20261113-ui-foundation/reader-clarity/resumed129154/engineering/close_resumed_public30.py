"""Finish the one resumed, newly captured public meeting on ordinary126.

The punctuation comparison, minutes, and native reader use one retained library.
No device connection, automatic Owner prompt, or old recording is opened here.
"""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, json, os, subprocess, sys, time

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'companion-device-closure055'
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
C=O/'public-level-control-full30-fixed20261113'
P=C/'closure'
parser=argparse.ArgumentParser()
parser.add_argument('phase',choices=['retranscribe','minutes','reader'])
parser.add_argument('--version',type=int,choices=[126,127],default=127)
args=parser.parse_args();phase=args.phase;version=args.version
scope=C/'content-scope.json'
if scope.exists():
    assert json.loads(scope.read_bytes()).get('publicOnly') is True, 'This mixed-room capture is retained local-only; no further ASR, cloud minutes, or public-demo use.'
control=json.loads((C/'result.json').read_bytes())
assert control['state']=='BOTH_PUBLIC_LEVEL_CONTROLS_CAPTURED_ASR_COMPARISON_PENDING'
evaluation=json.loads((C/'evaluation/result.json').read_bytes())
assert evaluation['state']=='RESUMED_PUBLIC_LEVEL_AND_SOURCE_ASR_COMPARISON_COMPLETE'
assert len(control['comparisons'])==1
step=control['comparisons'][0]
capture_path=Path(step['captureOutput'])/'result.json'
capture=json.loads(capture_path.read_bytes())
assert capture['ownHandlesClosed'] and capture['release']['result']=='TURN_RELEASED'
key=step['captureObserved']['recordingKey']
assert key['sessionId']=='00000000000001a7'
L=Path(step['captureOutput'])/'short/library'
rows=json.loads((L/'sessions.json').read_bytes())
assert len(rows)==1 and rows[0]['deviceRecordingKey']==key and rows[0]['transcriptFinal']
session_id=rows[0]['id']
assert any(s.get('sessionId')==session_id and s.get('recordingKey')==key
           and s.get('state')=='NATIVE_ORIGINAL_SAVED' for s in capture['stages'])
proof_path=R/'docs/handoffs/20261112-product-closure'/('windows'+str(version))/'windows-verification.json'
proof=json.loads(proof_path.read_bytes())
if version==127:
    # The capture used126. This candidate changes only reading presentation;
    # verify the unchanged native ASR/minutes and protocol implementation.
    subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','diff','--exit-code',
        'cbfcb4b81b40dffdf0ee7220c46e696c068c713f',proof['sourceCommit'],'--',
        'apps/windows/src-tauri/src','third_party/denzic-platform'],
        cwd=Path(proof['frozenSourceRoot']),check=True,stdout=subprocess.DEVNULL)
exe=Path('C:/Program Files/Companion Type/companion-type.exe')

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

assert sha(exe)==proof['embeddedExeSha256']
assert sha(exe.with_name('companion_type_lib.dll'))==proof['dllSha256']
originals={f.name:sha(f) for f in (L/'recordings').iterdir()
           if f.is_file() and f.suffix in ['.wav','.opus']}
assert originals
P.mkdir(exist_ok=True)

def verify_originals():
    for name,digest in originals.items():assert sha(L/'recordings'/name)==digest

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def native_review(folder,spec,local_model=False):
    folder.mkdir(exist_ok=False)
    save(folder/'spec.json',spec)
    source=S/'tools/qa/core_acceptance20261109/windows_meeting.py'
    runner=source
    if local_model:
        # The existing model+UI ceiling is2GiB; text-only UI keeps1536MiB.
        text=source.read_text(encoding='utf8')
        needle='else 1536)*1024**2'
        assert text.count(needle)==1
        bounded=folder/'bounded-helper.py'
        bounded.write_text(text.replace(needle,'else 2048)*1024**2'),encoding='utf8')
        runner=folder/'execute-helper.py'
        runner.write_text('from pathlib import Path\np='+repr(str(source))+
            '\nexec(compile(Path('+repr(str(bounded))+').read_text(encoding="utf8"),p,"exec"),'+
            '{"__name__":"__main__","__file__":p})\n',encoding='utf8')
    env={**os.environ,'COMPANION_ACCEPTANCE_PROJECT_ROOT':str(folder/'product'),
         'COMPANION_ACCEPTANCE_CACHE':str(folder/'private'),
         'COMPANION_ACCEPTANCE_VERIFICATION':str(proof_path),
         'COMPANION_ACCEPTANCE_FROZEN_NATIVE':proof['nativeRoot'],
         'COMPANION_ACCEPTANCE_OWNER_PREFLIGHT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1',
         'COMPANION_ACCEPTANCE_REAL_PUBLIC_SPEC':str(folder/'spec.json'),
         'NO_PROXY':'127.0.0.1,localhost,::1','no_proxy':'127.0.0.1,localhost,::1',
         'PYTHONPATH':str(source.parent)}
    before=sha(spec['statePath'])
    with (folder/'runner.log').open('xb') as log:
        run=subprocess.run([sys.executable,str(runner),'--stage','product-background'],
            cwd=S,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
    assert sha(spec['statePath'])==before
    verify_originals()
    assert run.returncode==0,(folder/'runner.log').read_text(errors='replace')[-2500:]
    cases=list((folder/'product/docs/handoffs/20261109-core-acceptance').iterdir())
    assert len(cases)==1
    path=cases[0]/'result.json'
    detail=json.loads(path.read_bytes())
    assert detail['processRestart']['previousAppExited']
    return path,detail

def spec_for(state):
    return dict(statePath=str(state),stateSha256=sha(state),recordingDir=str(L/'recordings'),
        captureReceipt=str(capture_path),originalAudioFiles=originals,sessionId=session_id,
        recordingKey=key,audioDurationMs=step['durationMs'])

if phase=='retranscribe':
    sys.path.insert(0,str(R/'model-research/src'))
    from moss_windows_resource_limits_20261104 import SystemRamPressure
    assert not SystemRamPressure().low(),'System low-memory guard: no model/UI launched.'
    model=Path(os.environ['APPDATA'])/'Companion Type/models/local-asr'
    assert sha(model/'ct-transformer-punctuation-zh-en-2024/model.onnx')=='e93593a6dbd69a07f8734ef269dbe861a379755f8d1c8354719432116f2c44bd'
    spec=spec_for(L/'sessions.json')
    spec.update(retranscriptionOnly=True,localModelRoot=str(model))
    evidence,detail=native_review(P/'retranscription',spec,True)
    assert detail['ui']['localAsrCompleted'] and detail['ui']['recognizerWordsUnchanged']
    state=Path(detail['privateRoot'])/'state/sessions.json'
    row=json.loads(state.read_bytes())[0]
    text=row['transcriptReview']['text']
    assert ''.join(c for c in text if c.isalnum())==''.join(c for c in row['transcriptText'] if c.isalnum())
    (P/'hypothesis.txt').write_text(text,encoding='utf8')
    save(P/'active-public-library.json',dict(statePath=str(state),recordingDir=str(L/'recordings'),
        sessionId=session_id,recordingKey=key,nativeUiEvidence=str(evidence),
        transcriptSha256=hashlib.sha256(text.encode()).hexdigest(),transcriptCharacters=len(text),
        rawTranscriptRetained=True,sourceStateUnchanged=True,originalAudioFiles=originals))
    print(json.dumps(dict(state=f'ACTUAL{version}_NEW_PUBLIC30_COMPARE_ADOPT_REOPEN_PASSED',
        characters=len(text),evidence=str(evidence))))
elif phase=='minutes':
    active=json.loads((P/'active-public-library.json').read_bytes())
    state=Path(active['statePath'])
    before=json.loads(state.read_bytes())
    row=before[0]
    text=row['transcriptReview']['text']
    digest=hashlib.sha256(text.encode()).hexdigest()
    assert digest==active['transcriptSha256']
    reviewed=json.loads((P/'text-reviewed-before-cloud.json').read_bytes())
    assert reviewed['allTextRead'] and reviewed['publicOnly'] and reviewed['transcriptSha256']==digest
    sys.path.insert(0,str(R/'model-research/src'))
    from moss_windows_resource_limits_20261104 import WorkerLimits
    limits=WorkerLimits(10,512*1024**2)
    env={k:v for k,v in os.environ.items() if not k.startswith((
        'COMPANION_TYPE_TRANSCRIPT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_MINUTES_COMMAND'))}
    env.update(COMPANION_TYPE_STATE_PATH=str(state),COMPANION_TYPE_RECORDING_DIR=active['recordingDir'],
        COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',
        COMPANION_TYPE_BLE_NATIVE_DISABLED='1')
    env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
    report=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),
        state=f'RUNNING_ACTUAL{version}_NEW_PUBLIC30_MINUTES_EXPORT_REOPEN',
        sessionId=session_id,recordingKey=key,sourceCommit=proof['sourceCommit'],
        steps=[],cloudTextOnly=True,cloudAudioUpload=False,privateOldAudioOr01a3Read=False)
    output=P/'minutes-result.json'
    assert not output.exists()
    def request(name,flag,data,destination,timeout=900):
        request_file=P/(name+'-request.json')
        assert not request_file.exists()
        save(request_file,data)
        started=time.monotonic()
        with (P/(name+'.log')).open('xb') as log:
            run=subprocess.run([str(exe),flag,str(request_file),str(destination)],env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW)
        report['steps'].append(dict(name=name,exitCode=run.returncode,
            seconds=round(time.monotonic()-started,3)))
        save(output,report)
        assert run.returncode==0,(P/(name+'.log')).read_text(errors='replace')[-1500:]
    try:
        request('standard-minutes','--meeting-minutes-request',dict(action='meetingGenerateMinutes',
            sessionId=session_id,meetingMode='offlineStore',minutesTemplate=dict(id='meeting')),P/'minutes.json')
        row=json.loads((P/'minutes.json').read_bytes())
        minutes=row['minutesByMode']['offlineStore']
        assert minutes['source']=='llm_deepseek' and minutes['quality']=='final'
        assert minutes['status']=='minutesReady' and minutes.get('processing',{}).get('complete') is not False
        assert row['transcriptText']==before[0]['transcriptText'] and row['transcriptReview']==before[0]['transcriptReview']
        (P/'actual-minutes.md').write_text(minutes['markdown'],encoding='utf8')
        request('readable-export','--meeting-export-request',dict(sessionId=session_id,
            meetingMode='offlineStore',format='txt',contentSections=dict(minutes=True,
            transcript=True,highlights=False,timeline=False,noteIds=[])),P/'公开中文会议30分钟-本轮实卡结果.txt')
        exported=(P/'公开中文会议30分钟-本轮实卡结果.txt').read_text(encoding='utf8')
        assert '超市' in exported and 'Generated:' not in exported and 'Minutes engine:' not in exported
        saved=json.loads(state.read_bytes())
        request('process-reopen','--local-recording-snapshot',{},P/'reopened.json')
        assert saved==json.loads((P/'reopened.json').read_bytes())['snapshot']['host']['sessions']
        verify_originals()
        report.update(state=f'ACTUAL{version}_NEW_PUBLIC30_MINUTES_EXPORT_REOPEN_DONE_CONTENT_REVIEW_PENDING',
            allOriginalAudioFilesUnchanged=True,rawAndAdoptedTranscriptsRetained=True,
            allPublicRowsRetainedAfterNewProcess=True,minutesCharacters=len(minutes['markdown']),
            ownerExperienceAccepted=False,asrAccuracyQualified=False,saleQualified=False)
    except BaseException as error:
        report.update(state=f'ACTUAL{version}_NEW_PUBLIC30_CLOSURE_NEEDS_ATTENTION_RETAINED',error=repr(error))
        raise
    finally:
        report['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds')
        save(output,report)
        print(json.dumps(report,ensure_ascii=False),flush=True)
else:
    active=json.loads((P/'active-public-library.json').read_bytes())
    spec=spec_for(Path(active['statePath']))
    spec.update(expectFoldedOverview=True,expectedMinutesTerms=['会议概览'],
        expectedTranscriptTerms=['超市'],expectedExportTerms=['超市','设备录音'])
    evidence,detail=native_review(P/'reader',spec)
    assert detail['ui']['actualDefaultOverviewAndFoldedCompleteDetailChecked']
    save(P/'reader-result.json',dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),
        state=f'ACTUAL{version}_NEW_PUBLIC30_NATIVE_READING_THEMES_REPLAY_EXPORT_REOPEN_PASSED',
        evidence=str(evidence),sourcePublicStateAndOriginalsUnchanged=True,
        newAsrOrCloudRequestedByUi=False,ownerExperienceAccepted=False,
        recognitionAndSemanticQualityQualified=False))
    print(json.dumps(dict(state='NATIVE_READER_CLOSURE_PASSED',evidence=str(evidence))))
