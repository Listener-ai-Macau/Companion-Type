from pathlib import Path
from datetime import datetime
import json,os,sys,hashlib,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/concentrated20261113/chinese-real-short/capture');L=C/'short/library';O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/notebook-foundation20261113/real-chinese019f118-r3');O.mkdir(exist_ok=False)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,2*1024**3);capture=json.loads((C/'result.json').read_bytes());assert capture['ownHandlesClosed']and capture['release']['result']=='TURN_RELEASED'
raw=(L/'sessions.json').read_bytes();rows=json.loads(raw);assert len(rows)==1 and rows[0]['id']=='v1-real-installed-1794533232243'and not rows[0]['transcriptText'];(O/'original-session-before.json').write_bytes(raw)
def sha(p):
 with Path(p).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
recordings=L/'recordings';before={x.name:sha(x)for x in recordings.iterdir()if x.suffix in ['.wav','.opus']};assert len(before)==4
exe=Path('C:/Program Files/Companion Type/companion-type.exe');proof=json.loads((R/'docs/handoffs/20261112-product-closure/windows118/windows-verification.json').read_bytes());assert sha(exe)==proof['embeddedExeSha256']
env={k:v for k,v in os.environ.items()if not k.startswith(('COMPANION_TYPE_TRANSCRIPT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_MINUTES_COMMAND'))};env.update(COMPANION_TYPE_STATE_PATH=str(L/'sessions.json'),COMPANION_TYPE_RECORDING_DIR=str(recordings),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1');env.pop('PSModulePath',None);env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
result=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='PROCESSING_AUTHORIZED_NEW_PUBLIC019F_IN_ITS_ORIGINAL_DURABLE_LIBRARY',version='0.1.118',sessionId=rows[0]['id'],onlyFreshPublicRecording=True,private019eRead=False,localAsrRequested=True,cloudAudioUpload=False,referenceTextFed=False,transcriptInjected=False,deviceAccess=False,statePath=str(L/'sessions.json'),recordingDir=str(recordings),priorIsolatedCopyFailuresRetained=True,sourceFilesBefore=before)
request=O/'request.json';request.write_text(json.dumps(dict(sessionId=rows[0]['id'])),encoding='utf-8');start=time.monotonic()
try:
 with(O/'asr.log').open('wb')as log:run=subprocess.run([str(exe),'--meeting-transcribe-request',str(request),str(O/'transcribed.json')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
 result.update(exitCode=run.returncode,seconds=round(time.monotonic()-start,3));assert run.returncode==0
 response=json.loads((O/'transcribed.json').read_bytes());assert response['deviceAccess']is False and response['operationError']is None;saved=next(x for x in response['snapshot']['host']['sessions']if x['id']==rows[0]['id']);assert saved['transcriptFinal']and saved['transcriptText'].strip()
 result.update(state='ACTUAL_PHYSICAL_PUBLIC019F_ORIGINAL_LIBRARY_LOCAL_ASR_COMPLETED_TEXT_REVIEW_PENDING',localAsrCompleted=True,transcriptCharacters=len(saved['transcriptText']),asrProvider=response['settings']['asrProvider'])
except BaseException as error:result.update(state='ACTUAL019F_ORIGINAL_LIBRARY_ASR_FAILED_PRESERVED',error=repr(error));raise
finally:
 after={x.name:sha(x)for x in recordings.iterdir()if x.name in before};assert after==before;result.update(finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),allFourOriginalAudioFilesUnchanged=True);(O/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
