"""Fresh third-meeting local-overlap inference, frozen recipe and bounded CPU."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,subprocess,sys,time,ctypes,shutil
import psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';ROOT=R/'docs/handoffs/20261108-competitive-sale-standard/two-lane-validation-20261109';C=ROOT/'automatic-cross-meeting-r2/independent-overlap-candidate-r1/third-meeting-r1';repair='--repair-output' in sys.argv;resume='--resume' in sys.argv or repair;C.mkdir(exist_ok=resume);sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import stop_owned_family
# The model worker owns one resource job. A nested controller CPU cap can
# multiply the restriction; the mostly-idle controller only monitors it.
pressure=SystemRamPressure()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
base=R/'docs/handoffs/20261107-model-generation-recovery/bounded-speaker-full-r1';P=read(base/'protocol.json');P['boundedCacheRoot']='E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/third-meeting-overlap-r1';write(C/'protocol.json',P);case=read(ROOT/'ordinary-full-r1/audio-only.json')[0];write(C/'audio-only.json',[case]);worker=M/'src/bounded_speaker_20261107.py';old=read(base/'results/L_R003S01C02/segment-state.json');assert old['sourceSha256']==sha(worker),'Reuse only unchanged verified segmentation worker'
execution=C
if repair:
 assert read(C/'run.json')['state']=='FAILED_SEGMENTATION'
 cache=Path(P['boundedCacheRoot'])/case['meeting'];saved=read(cache/'segment.json');assert saved['state']=='COMPLETE_SEGMENTATION_CACHE' and saved['done']==saved['total']
 shutil.copyfile(C/'run.json',C/'run-full-neural-output-path-failed.json')
 buf=ctypes.create_unicode_buffer(4096);fn=ctypes.windll.kernel32.GetShortPathNameW;fn.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint];fn.restype=ctypes.c_uint;assert fn(str(C),buf,4096)>0;execution=Path(buf.value);assert os.path.samefile(C,execution) and len(str(execution))<120
write(C/('selection-protocol-shortpath-replay.json' if repair else 'selection-protocol-worker-only-limit.json' if resume else 'selection-protocol.json'),{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'purpose':'Fresh unchangedCPU localoverlap detection on already prepared36m35s fullthirddevelopmentmeeting. Samepowersetargmax/countaggregation as twoexposedfullrecordings. No model/threshold/gapfilter changes, diarizationembedding, ASR, training or downloads.','audioOnlySha256':sha(C/'audio-only.json'),'sameUnchangedWorkerSha256':sha(worker),'referenceNotPassedToWorker':True,'sourcePreviouslyUsedForTseValidation':True,'finalHeldout':False,'previousSameWorkerFullInferenceSeconds':old['wholeWorkerSeconds'],'earlyNativeProofReusedFromExistingFullControl':str(base),'modelPrivateLimitBytes':2*1024**3,'modelCpuPercent':5,'controllerNoNestedCpuJob':True,'resumeSameBoundNeuralCache':resume,'executionControlAlias':str(execution),'repairOnlyCompletedNeuralCache':repair,'stopOnWindowsLowMemory':True,'timeoutSeconds':300,'saleQualified':False})
state={'state':'STARTED','newNeuralItems':0,'startedAt':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')};write(C/'run.json',state);child=None;root=None;started=time.perf_counter();peak=0
try:
 if pressure.low():raise RuntimeError('ActualWindowsLOWRAM; stop before launching')
 with (C/('segment-shortpath-replay.log' if repair else 'segment-worker-only-limit.log' if resume else 'segment.log')).open('xb') as log:
  child=subprocess.Popen([sys.executable,str(worker),'--control',str(execution),'--index','0','--stage','segment'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);root=psutil.Process(child.pid);root.cpu_affinity([12,13]);state['activePid']=child.pid;write(C/'run.json',state)
  while child.poll() is None:
   if pressure.low() or time.perf_counter()-started>300:
    low=pressure.low();stop_owned_family(child,root);state['state']='STOPPED_WINDOWS_LOW_MEMORY' if low else 'STOPPED_TIMEOUT';break
   try:peak=max(peak,root.memory_info().private)
   except psutil.Error:pass
   time.sleep(1)
 receipt=C/'results'/case['meeting']/'segment-state.json';result=read(receipt) if receipt.exists() else {};state.update(exitCode=child.returncode,newNeuralItems=result.get('newNeuralItems',0),workerState=result.get('state'),workerPrivatePeakBytes=result.get('limits',{}).get('jobPeakPrivateCommitBytes'))
 if child.returncode==0 and result.get('state')=='COMPLETE_SEGMENTATION_CACHE':
  state['state']='COMPLETE_FRESH_THIRD_MEETING_SEGMENTATION'
  if repair:
   assert result['newNeuralItems']==0 and result['reusedCachedPrefix']==saved['total'],'Output-path repair must not repeat completed inference'
   state.update(completionFromVerifiedCacheOnly=True,completedFreshNeuralCacheFrames=saved['total'],priorFullNeuralAttempt=read(C/'run-full-neural-output-path-failed.json'))
 elif state['state']=='STARTED':state['state']='FAILED_SEGMENTATION'
except BaseException as exc:
 state.update(state='FAILED',failureType=type(exc).__name__);raise
finally:
 if child is not None and child.poll() is None:stop_owned_family(child,root)
 state.pop('activePid',None);state.update(wallSeconds=time.perf_counter()-started,polledPrivatePeakBytes=peak,resourcePolicy='Modelworker single5percent job/2GiB privatecap; controller monitors Windows actualLOWRAM without nestedCPUcap',finishedAt=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),saleQualified=False);write(C/'run.json',state);print(json.dumps(state,ensure_ascii=False),flush=True)
