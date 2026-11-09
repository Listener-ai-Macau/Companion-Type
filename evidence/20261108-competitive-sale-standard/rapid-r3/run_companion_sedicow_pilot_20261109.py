"""Bounded dedicated-GPU pilot; no CPU/iGPU fallback and no persistent task."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,subprocess,sys,time
import psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--control',default=str(R/'docs/handoffs/20261109-sedicow-r1'));parser.add_argument('--all-targets',action='store_true');a=parser.parse_args();C=Path(a.control);P=read(C/'gpu-protocol.json');phase='all-targets' if a.all_targets else 'pilot';path=C/(phase+'-controller.json');logpath=C/(phase+'.log');child=None;root=None;start=time.perf_counter();pressure=SystemRamPressure();state={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'PREFLIGHT','newNeuralCalls':0,'privatePeakBytes':0,'controllerHasCpuRateJob':False,'saleQualified':False}
 def save():state['wallSeconds']=time.perf_counter()-start;path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 try:
  assert sha(__file__)==P['controllerSha256'],'Controller changed after protocol freeze'
  # pnputil is read-only and needs no Torch import or CUDA runtime allocation.
  check=subprocess.run(['pnputil','/enum-devices','/class','Display','/connected','/deviceids'],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
  output=check.stdout.decode('utf8',errors='replace');state['connectedDisplayQuery']=output;state['displayQueryReturnCode']=check.returncode
  if check.returncode or 'DEV_73BF' not in output.upper():state['state']='DEFERRED_NO_CONNECTED_6800XT_NO_MODEL_IMPORTED';save();return
  if pressure.low():state['state']='DEFERRED_ACTUAL_WINDOWS_LOWRAM_NO_MODEL_IMPORTED';save();return
  assert read(C/'checkpoint-probe.json')['state']=='PASS_EXACT_TINY_LOAD_GENERATION_AND_FULL_META_HEADER','Checkpoint plumbing must pass first'
  if a.all_targets:
   review=read(C/'pilot-acceptance.json');assert review.get('pilotContentUseful') is True and review.get('referencePassedToInference') is False,'Review pilot content before expanding targets'
  worker=M/'src/companion_sedicow_gpu_worker_20261109.py';assert sha(worker)==P['workerSha256'];assert not (C/phase).exists() and not logpath.exists(),'Never overwrite previous neural evidence'
  args=[P['amdPython'],str(worker),'--control',str(C)]
  if a.all_targets:args.append('--all-targets')
  with logpath.open('xb') as log:
   child=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);root=psutil.Process(child.pid);state.update(state='RUNNING',pid=child.pid);save();progress=start;last_count=0
   while child.poll() is None:
    low=pressure.low();now=time.perf_counter();worker_path=C/phase/'state.json'
    if worker_path.exists():
     try:current=read(worker_path);count=current.get('newNeuralCalls',0)
     except (ValueError,OSError):count=last_count
     if count!=last_count:last_count=count;progress=now
    timeout=now-progress>P['maximumSecondsWithoutCompletedTarget'] or now-start>P['maximumRunSeconds']
    if low or timeout:stop_owned_family(child,root);state['state']='STOPPED_ACTUAL_WINDOWS_LOWRAM' if low else 'STOPPED_BOUNDED_TIME';break
    try:
     private=root.memory_info().private;state['privatePeakBytes']=max(state['privatePeakBytes'],private)
     if private>P['maximumPrivateBytes']:stop_owned_family(child,root);state['state']='STOPPED_PRIVATE_MEMORY_BUDGET';break
    except psutil.Error:pass
    time.sleep(1)
  worker_state=read(C/phase/'state.json') if (C/phase/'state.json').exists() else {};state.update(exitCode=child.returncode,workerState=worker_state.get('state'),newNeuralCalls=worker_state.get('newNeuralCalls',0))
  if state['state']=='RUNNING':state['state']='COMPLETE_UNQUALIFIED_TARGET_ASR' if child.returncode==0 and worker_state.get('state')=='COMPLETE_TARGET_ASR_PILOT_NOT_QUALIFIED' else 'FAILED'
 except BaseException as exc:state.update(state='FAILED_CONTROLLER',failureType=type(exc).__name__,reason=str(exc));raise
 finally:
  if child is not None and child.poll() is None:stop_owned_family(child,root)
  save();print(json.dumps(state,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
