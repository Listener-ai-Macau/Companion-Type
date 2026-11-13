from pathlib import Path
from datetime import datetime
import copy,hashlib,json,os,shutil,subprocess,sys,time,wave,array,math
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/concentrated20261113/chinese-real-short');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/notebook-foundation20261113/real-chinese019f118-r2');O.mkdir(exist_ok=False)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,2*1024**3)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();capture=json.loads((C/'capture/result.json').read_bytes());assert capture['ownHandlesClosed'] and capture['release']['result']=='TURN_RELEASED'
rows=json.loads((C/'capture/short/library/sessions.json').read_bytes());assert len(rows)==1;row=copy.deepcopy(rows[0]);assert row['id']=='v1-real-installed-1794533232243'and row['audioStored']and not row['captureIncomplete'] and not row.get('transcriptText')
original=Path(row['audioPath']);original_sha=sha(original);shutil.copytree(original.parent,O/'recordings');wav=O/'recordings'/original.name;assert sha(wav)==original_sha
def relocate(value):
 if isinstance(value,dict):return {k:relocate(v) for k,v in value.items()}
 if isinstance(value,list):return [relocate(v) for v in value]
 if isinstance(value,str)and value.startswith(str(original.parent)):
  return str(O/'recordings'/Path(value).relative_to(original.parent))
 return value
row=relocate(row)
with wave.open(str(wav),'rb')as audio:
 assert audio.getnchannels()==1 and audio.getsampwidth()==2 and audio.getframerate()==16000
 seconds=audio.getnframes()/audio.getframerate();samples=array.array('h',audio.readframes(audio.getnframes()))
assert abs(seconds-285.52)<.05
energies=[]
for start in range(0,len(samples),16000):
 part=samples[start:start+16000];energies.append(math.sqrt(sum(x*x for x in part)/len(part)))
ordered=sorted(energies);rms=math.sqrt(sum(x*x for x in samples)/len(samples));peak=max(abs(x)for x in samples)
audio_info=dict(path=str(wav),originalPath=str(original),sha256=original_sha,seconds=seconds,sampleRate=16000,channels=1,rms=rms,rmsDbfs=20*math.log10(max(rms,1)/32768),peak=peak,peakDbfs=20*math.log10(max(peak,1)/32768),clippedSamples=sum(abs(x)>=32760 for x in samples),oneSecondRmsQuantiles={str(q):ordered[round((len(ordered)-1)*q)] for q in [.1,.5,.9,.99]},oneSecondRms=energies)
row['audioPath']=str(wav);row['processingPolicy']='manual';(O/'sessions.json').write_text(json.dumps([row],ensure_ascii=False),encoding='utf-8')
exe=Path('C:/Program Files/Companion Type/companion-type.exe');proof=json.loads((R/'docs/handoffs/20261112-product-closure/windows118/windows-verification.json').read_bytes());assert sha(exe)==proof['embeddedExeSha256']
env={k:v for k,v in os.environ.items()if not k.startswith(('COMPANION_TYPE_TRANSCRIPT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_MINUTES_COMMAND'))};env.update(COMPANION_TYPE_STATE_PATH=str(O/'sessions.json'),COMPANION_TYPE_RECORDING_DIR=str(O/'recordings'),COMPANION_TYPE_DISABLE_AUTO_RECOVERY='1',COMPANION_TYPE_DISABLE_AUTO_RECONNECT='1',COMPANION_TYPE_BLE_NATIVE_DISABLED='1');env.pop('PSModulePath',None);env.pop('COMPANION_TYPE_PRODUCT_SETTINGS_PATH',None)
result=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ACTUAL_019F_THROUGH_INSTALLED118_LOCAL_ASR_RUNNING',sessionId=row['id'],recordingKey=row.get('deviceRecordingKey'),audio=audio_info,sourceCaptureReceipt=str(C/'capture/result.json'),version='0.1.118',appSourceCommit=proof['sourceCommit'],syntheticAudio=False,physicalPublicHumanMeeting=True,private019eRead=False,originalRecordingChanged=False,newRecordingStarted=False,boardAccess=False,transcriptInjected=False,referenceTextFed=False,cloudAudioUpload=False,minutesNotYetRequested=True)
def save():(O/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save();request=O/'local-asr-request.json';request.write_text(json.dumps(dict(sessionId=row['id'])),encoding='utf-8');started=time.monotonic()
try:
 with(O/'local-asr.log').open('wb')as log:run=subprocess.run([str(exe),'--meeting-transcribe-request',str(request),str(O/'transcribed.json')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
 result['localAsrExitCode']=run.returncode;result['localAsrSeconds']=round(time.monotonic()-started,3);assert run.returncode==0
 response=json.loads((O/'transcribed.json').read_bytes());assert response['deviceAccess']is False and response['transcriptionRequested']and response['operationError']is None
 saved=next(r for r in response['snapshot']['host']['sessions']if r['id']==row['id']);assert saved['transcriptFinal']and saved['transcriptText'].strip();assert response['settings']['asrProvider']=='local-paraformer'
 assert sha(original)==original_sha==sha(wav)
 result.update(state='ACTUAL_PHYSICAL_PUBLIC019F_LOCAL_ASR_COMPLETED_TEXT_REVIEW_BEFORE_MINUTES',actualLocalAsrCompleted=True,transcriptCharacters=len(saved['transcriptText']),asrProvider='local-paraformer',transcriptForLocalReview=str(O/'transcribed.json'),originalAudioUnchanged=True)
except BaseException as error:result.update(state='ACTUAL019F_ASR_NEEDS_ATTENTION',error=str(error));raise
finally:result['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');save();print(json.dumps({k:v for k,v in result.items()if k!='audio'},ensure_ascii=False),flush=True)
