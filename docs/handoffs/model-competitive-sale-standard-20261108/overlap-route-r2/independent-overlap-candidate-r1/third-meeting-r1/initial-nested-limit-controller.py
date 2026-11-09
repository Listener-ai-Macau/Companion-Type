"""Fresh third-meeting local-overlap inference, frozen recipe and bounded CPU."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,subprocess,sys,time
import psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';ROOT=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109';C=ROOT/'automatic-cross-meeting-r2/independent-overlap-candidate-r1/third-meeting-r1';C.mkdir(exist_ok=False);sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import stop_owned_family
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2);pressure=SystemRamPressure()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
base=R/'docs/handoffs/20261107-model-generation-recovery/bounded-speaker-full-r1';P=read(base/'protocol.json');P['boundedCacheRoot']='E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/third-meeting-overlap-r1';write(C/'protocol.json',P);case=read(ROOT/'ordinary-full-r1/audio-only.json')[0];write(C/'audio-only.json',[case]);worker=M/'src/bounded_speaker_20261107.py';old=read(base/'results/L_R003S01C02/segment-state.json');assert old['sourceSha256']==sha(worker),'Reuse only unchanged verified segmentation worker'
write(C/'selection-protocol.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'purpose':'Fresh unchangedCPU localoverlap detection on already prepared36m35s fullthirddevelopmentmeeting. Samepowersetargmax/countaggregation as twoexposedfullrecordings. No model/threshold/gapfilter changes, diarizationembedding, ASR, training or downloads.','audioOnlySha256':sha(C/'audio-only.json'),'sameUnchangedWorkerSha256':sha(worker),'referenceNotPassedToWorker':True,'sourcePreviouslyUsedForTseValidation':True,'finalHeldout':False,'previousSameWorkerFullInferenceSeconds':old['wholeWorkerSeconds'],'earlyNativeProofReusedFromExistingFullControl':str(base),'parentFamilyPrivateLimitBytes':512*1024**2,'cpuPercent':5,'stopOnWindowsLowMemory':True,'timeoutSeconds':300,'saleQualified':False})
state={'state':'STARTED','newNeuralItems':0,'startedAt':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')};write(C/'run.json',state);child=None;root=None;started=time.perf_counter();peak=0
try:
 if pressure.low():raise RuntimeError('ActualWindowsLOWRAM; stop before launching')
 with (C/'segment.log').open('xb') as log:
  child=subprocess.Popen([sys.executable,str(worker),'--control',str(C),'--index','0','--stage','segment'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);root=psutil.Process(child.pid);root.cpu_affinity([12,13]);state['activePid']=child.pid;write(C/'run.json',state)
  while child.poll() is None:
   if pressure.low() or time.perf_counter()-started>300:
    low=pressure.low();stop_owned_family(child,root);state['state']='STOPPED_WINDOWS_LOW_MEMORY' if low else 'STOPPED_TIMEOUT';break
   try:peak=max(peak,root.memory_info().private)
   except psutil.Error:pass
   time.sleep(1)
 receipt=C/'results'/case['meeting']/'segment-state.json';result=read(receipt) if receipt.exists() else {};state.update(exitCode=child.returncode,newNeuralItems=result.get('newNeuralItems',0),workerState=result.get('state'),workerPrivatePeakBytes=result.get('limits',{}).get('jobPeakPrivateCommitBytes'))
 if child.returncode==0 and result.get('state')=='COMPLETE_SEGMENTATION_CACHE':state['state']='COMPLETE_FRESH_THIRD_MEETING_SEGMENTATION'
 elif state['state']=='STARTED':state['state']='FAILED_SEGMENTATION'
except BaseException as exc:
 state.update(state='FAILED',failureType=type(exc).__name__);raise
finally:
 if child is not None and child.poll() is None:stop_owned_family(child,root)
 state.pop('activePid',None);state.update(wallSeconds=time.perf_counter()-started,polledPrivatePeakBytes=peak,limits=limits.query(),finishedAt=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),saleQualified=False);write(C/'run.json',state);print(json.dumps(state,ensure_ascii=False),flush=True)
