from pathlib import Path
from datetime import datetime
import json,os,sys,hashlib,subprocess,time,wave,numpy as np
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/notebook-foundation20261113/real-chinese019f118-r3');V=O/'volume-reference';L=V/'capture-normalized-r1/short/library'
out=V/'comparison-analysis-r2';out.mkdir(exist_ok=False)
capture=json.loads((L.parent.parent/'result.json').read_bytes());assert capture['ownHandlesClosed']and capture['release']['result']=='TURN_RELEASED'
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,2*1024**3)
def sha(p):
 p=Path(p)
 if not str(p).startswith('\\\\?\\'):p=Path('\\\\?\\'+str(p.resolve()))
 with p.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
raw=(L/'sessions.json').read_bytes();rows=json.loads(raw);assert len(rows)==1 and rows[0]['deviceRecordingKey']['sessionId']=='00000000000001a0'and not rows[0]['transcriptText'];(out/'session-before.json').write_bytes(raw)
originals={p.name:sha(p)for p in (L/'recordings').iterdir()if p.suffix in ['.wav','.opus']}
exe=Path('C:/Program Files/Companion Type/companion-type.exe');proof=json.loads((R/'docs/handoffs/20261112-product-closure/windows118/windows-verification.json').read_bytes());assert sha(exe)==proof['embeddedExeSha256']
env={k:v for k,v in os.environ.items()if not k.startswith(('COMPANION_TYPE_TRANSCRIPT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_MINUTES_COMMAND'))};env.update(COMPANION_TYPE_STATE_PATH=str(L/'sessions.json'),COMPANION_TYPE_RECORDING_DIR=str(L/'recordings'),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1');env.pop('PSModulePath',None);env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
request=out/'request.json';request.write_text(json.dumps(dict(sessionId=rows[0]['id'])),encoding='utf8');started=time.monotonic()
with(out/'asr.log').open('xb')as log:run=subprocess.run([str(exe),'--meeting-transcribe-request',str(request),str(out/'transcribed.json')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
assert run.returncode==0
response=json.loads((out/'transcribed.json').read_bytes());assert response['operationError']is None and response['deviceAccess']is False
saved=next(row for row in response['snapshot']['host']['sessions']if row['id']==rows[0]['id']);assert saved['transcriptFinal'];(out/'actual-transcript.txt').write_text(saved['transcriptText'],encoding='utf8')
def samples(p):
 with wave.open(str(p),'rb')as w:assert w.getframerate()==16000 and w.getnchannels()==1 and w.getsampwidth()==2;return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float64)
def info(v):
 rms=np.sqrt(np.mean(v*v));return dict(rms=float(rms),rmsDbfs=float(20*np.log10(max(rms,1)/32768)),peak=float(np.max(np.abs(v))),clippedSamples=int(np.sum(np.abs(v)>=32760)))
def envelope(v):return np.sqrt(np.mean(v[:len(v)//800*800].reshape(-1,800)**2,axis=1))
baseline=json.loads((O/'result.json').read_bytes());oldrows=json.loads((Path(baseline['statePath'])).read_bytes());old=samples(Path(oldrows[0]['audioPath']));new=samples(Path(saved['audioPath']));source=samples(V/'public-human-meeting-playback-normalized.wav')[:110*16000]
def align(v,near):
 a=envelope(v);b=envelope(source);best=(-2,0)
 for shift in range(max(0,round((near-2)*20)),round((near+2)*20)+1):
  n=min(len(a)-shift,len(b));score=float(np.corrcoef(a[shift:shift+n],b[:n])[0,1]);best=max(best,(score,shift))
 return dict(envelopeCorrelation=best[0],sourceOffsetSeconds=best[1]/20,matchingPublic110Seconds=info(v[best[1]*800:best[1]*800+len(source)]))
a=align(old,28.45);b=align(new,.5)
for name,digest in originals.items():assert sha(L/'recordings'/name)==digest
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ACTUAL_NORMALIZED_SPEAKER_TO_MIC_COMPARISON_LOCAL_ASR_COMPLETED_REVIEW_PENDING',version='0.1.118',sessionId=saved['id'],recordingKey=saved['deviceRecordingKey'],captureResult=str(L.parent.parent/'result.json'),asrSeconds=round(time.monotonic()-started,3),asrProvider=response['settings']['asrProvider'],transcriptCharacters=len(saved['transcriptText']),baseline019f=a,normalized01a0=b,matchingCapturedRmsIncreaseDb=b['matchingPublic110Seconds']['rmsDbfs']-a['matchingPublic110Seconds']['rmsDbfs'],originalAudioFiles=originals,originalAudioUnchanged=True,referenceTextFed=False,cloudRequested=False,private019eRead=False,deviceAccessByAsr=False,ownerAudibilityAccepted=False,modelGeneralQualityQualified=False)
(out/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False),flush=True)
