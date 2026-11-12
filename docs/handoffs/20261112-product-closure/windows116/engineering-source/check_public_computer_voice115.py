from pathlib import Path
from datetime import datetime
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
import wave

root=Path('C:/Users/Billy/Desktop/Denzic/Companion')
out=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/public-computer-voice115-r3')
out.mkdir(exist_ok=False)
sys.path.insert(0,str(root/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,2*1024**3)
exe=Path('C:/Program Files/Companion Type/companion-type.exe')
proof=json.loads((root/'docs/handoffs/20261112-product-closure/windows115/windows-verification.json').read_bytes())
assert hashlib.sha256(exe.read_bytes()).hexdigest()==proof['embeddedExeSha256']
env={key:value for key,value in os.environ.items() if not key.startswith(('COMPANION_TYPE_TRANSCRIPT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_MINUTES_COMMAND'))}
env.update(COMPANION_TYPE_STATE_PATH=str(out/'sessions.json'),COMPANION_TYPE_RECORDING_DIR=str(out/'recordings'),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1')
env.pop('PSModulePath',None)
env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
result=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='RUNNING_PUBLIC_COMPUTER_VOICE_THROUGH_INSTALLED115',version='0.1.115',appSourceCommit=proof['sourceCommit'],syntheticAudio=True,privateAudioRead=False,deviceAccess=False,microphoneCapture=False,asrSidecarUsed=False,transcriptInjected=False,cloudAudioUpload=False,steps=[])
def write():
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def command(name,arguments,timeout=600):
    start=time.monotonic()
    with (out/(name+'.log')).open('wb') as log:
        run=subprocess.run(arguments,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
    result['steps'].append(dict(name=name,exitCode=run.returncode,seconds=round(time.monotonic()-start,3)))
    write()
    assert run.returncode==0, name+' failed; preserved log '+str(out/(name+'.log'))
def request(name,flag,data,destination):
    source=out/(name+'-request.json')
    source.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
    command(name,[str(exe),flag,str(source),str(destination)])
try:
    write()
    wav=out.parent/'public-computer-voice115-r2/computer-public-example.wav'
    assert hashlib.sha256(wav.read_bytes()).hexdigest()=='d1e07b18f5863f9dcb933bc0d59085f3fe083ec7de67b56a98eff408548d5d5b'
    with wave.open(str(wav),'rb') as audio:
        assert audio.getframerate()==16000 and audio.getnchannels()==1 and audio.getsampwidth()==2
        seconds=audio.getnframes()/16000
    result['audio']=dict(bytes=wav.stat().st_size,sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),seconds=seconds,rate=16000,channels=1)
    # Controlled public local-audio fixture, explicitly not the GUI file importer or physical capture.
    source=root/'docs/handoffs/20261112-product-closure/windows115/runtime-result.json'
    runtime=json.loads(source.read_bytes())
    plan=json.loads((Path(runtime['nativeUiEvidence']).parent/'plan.json').read_bytes())
    rows=json.loads(Path(plan['statePath']).read_bytes())
    row=copy.deepcopy(next(item for item in rows if item['id']==plan['sessionId']))
    row.update(id='public-computer-voice115',title='电脑合成公开示例 · 演示安排',status='captured',source='importedAudio',startedAt=datetime.now().astimezone().isoformat(),durationMs=round(seconds*1000),audioStored=True,audioPath=str(wav),audioBytes=wav.stat().st_size,transcriptText='',transcriptFinal=False,transcriptSegments=0,utterances=[],chunks=[],minutes=None,minutesByMode={'offlineStore':None,'onlineLive':None,'history':[]},pendingReason='needs_transcription',processingPolicy='manual',meetingNotes=[],noteRevision=0,bookmarks=[],captureIncomplete=False,recovery={},transcriptReview=None,deviceRecordingId=None,deviceRecordingKey=None,sourceDeviceId=None,deviceTotalLength=None,deviceSha256=None,recorderControl=None,recorderControlUncertain=False)
    row['recovery']={'intent':'none','requestedMeetingMode':'','stage':'idle','attemptCount':0,'maxAttempts':3,'retryStage':'','captureReviewConfirmed':False}
    row['retention'].update(audioCached=True,transcriptCached=False,minutesCached=False)
    (out/'sessions.json').write_text(json.dumps([row],ensure_ascii=False),encoding='utf8')
    request('actual-local-asr','--meeting-transcribe-request',{'sessionId':row['id']},out/'transcribed.json')
    response=json.loads((out/'transcribed.json').read_bytes())
    assert response['deviceAccess'] is False and response['transcriptionRequested'] is True and response['operationError'] is None
    settings=response['settings']
    assert settings['asrProvider']=='local-paraformer' and settings['localAsrAvailable'] is True
    saved=next(item for item in response['snapshot']['host']['sessions'] if item['id']==row['id'])
    assert saved['transcriptFinal'] is True and saved['transcriptText'].strip()
    result.update(actualLocalAsrCompleted=True,transcriptCharacters=len(saved['transcriptText']),asrProvider='local-paraformer')
    request('actual-configured-minutes','--meeting-minutes-request',{'action':'meetingGenerateMinutes','sessionId':row['id']},out/'minutes.json')
    minutes_row=json.loads((out/'minutes.json').read_bytes())
    minutes=minutes_row.get('minutesByMode',{}).get('offlineStore') or minutes_row.get('minutes')
    assert minutes and minutes.get('markdown','').strip()
    result.update(minutesSource=minutes.get('source'),minutesQuality=minutes.get('quality'),actualConfiguredMinutesCompleted=True)
    request('save-result','--meeting-export-request',{'sessionId':row['id'],'meetingMode':'offlineStore','format':'markdown'},out/'computer-public-result.md')
    assert (out/'computer-public-result.md').stat().st_size>0
    before=json.loads((out/'sessions.json').read_bytes())
    request('read-after-process-restart','--local-recording-snapshot',{},out/'reopened.json')
    after=json.loads((out/'reopened.json').read_bytes())['snapshot']['host']['sessions']
    assert before==after
    assert hashlib.sha256(wav.read_bytes()).hexdigest()==result['audio']['sha256']
    result.update(state='ACTUAL_INSTALLED115_COMPUTER_VOICE_LOCAL_ASR_CONFIGURED_MINUTES_EXPORT_AND_REOPEN_COMPLETED',savedStateUnchangedAcrossProcesses=True,originalSyntheticWavUnchanged=True,guiAudioImportQualified=False,modelGeneralAccuracyQualified=False,physicalRecordingQualified=False,longRecordingQualified=False,saleQualified=False)
except BaseException as error:
    result.update(state='PUBLIC_COMPUTER_VOICE_CHECK_NEEDS_ATTENTION',error=str(error))
    raise
finally:
    result['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds')
    write()
    print(json.dumps(result,ensure_ascii=False),flush=True)
