"""One owned neural family through controls and full meetings, with fixed deadline."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,subprocess,sys,time
import psutil
from companion_local_pcm_session_20261114 import atomic_json,exclusive_file
from companion_windows_power_request_20261115 import PowerLease
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 assert a.control.is_absolute() and a.run.is_absolute() and not a.run.exists();a.run.mkdir(parents=True)
 src=Path(__file__).resolve().parent;B=read(a.control/'overnight-binding.json');worker=src/'moss_overnight_worker_20261115.py'
 assert sha(worker)==B['workerSha256'] and sha(__file__)==B['runnerSha256']
 deadline=datetime.fromisoformat(B['neuralDeadline'])
 state={'state':'PREPARING_FIXED_OVERNIGHT_ARCHITECTURE_RUN','startedAt':datetime.now().astimezone().isoformat(),
  'neuralDeadline':B['neuralDeadline'],'reportDeadline':B['reportDeadline'],'phases':[],
  'privatePeakBytes':0,'qualityQualified':False,'newWeightTraining':False,'automaticRetries':0}
 def save():atomic_json(a.run/'run.json',state)
 pressure=SystemRamPressure();child=owned=None;started=time.monotonic();save()
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),PowerLease():
  try:
   assert not pressure.low() and datetime.now().astimezone()<deadline
   inventory=a.run/'inventory'
   with (a.run/'inventory.log').open('xb') as log:
    code=subprocess.call([sys.executable,str(src/'run_practical_qwen_native_20261107.py'),'--phase','inventory','--control',str(inventory)],
     stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   value=read(inventory/'hip-inventory.json');assert code==0 and value['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
   gpu=value['selected'];assert gpu['name']=='AMD Radeon RX 6800 XT' and gpu['architecture']=='gfx1030'
   env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
   env.update(HIP_VISIBLE_DEVICES=str(gpu['ordinal']),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
   for phase,expected in [('control','PASS_NATIVE_CPU_AND_PUBLISHED_GPU_CAUSAL_PREFILL'),
    ('full','COMPLETE_FOUR_ORIGINAL_MEETING_JOINT_OUTPUTS_SCORING_PENDING')]:
    if (datetime.now().astimezone()-datetime.fromisoformat(value['finishedAt'])).total_seconds()>=1800:
     with (a.run/'inventory-refresh.log').open('xb') as log:
      fresh=a.run/'inventory-refresh';code=subprocess.call([sys.executable,str(src/'run_practical_qwen_native_20261107.py'),
       '--phase','inventory','--control',str(fresh)],stdout=log,stderr=subprocess.STDOUT,
       creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
     value=read(fresh/'hip-inventory.json');assert code==0 and value['selected']==gpu;inventory=fresh
    assert not pressure.low() and datetime.now().astimezone()<deadline
    command=[B['gpuPython'],str(worker),'--phase',phase,'--control',str(a.control),'--inventory',str(inventory/'hip-inventory.json'),'--run',str(a.run)]
    tick=time.monotonic();peak=0;last_save=0.
    with (a.run/(phase+'-worker.log')).open('xb') as log:
     child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
     owned=psutil.Process(child.pid);state.update(state='RUNNING_'+phase.upper(),pid=child.pid,pidCreatedAt=owned.create_time());save()
     while child.poll() is None:
      if pressure.low() or (a.run/'stop.request').exists() or datetime.now().astimezone()>=deadline:
       (a.run/'stop.request').write_text('Frozen deadline or actual Windows low RAM or owner stop.\n',encoding='utf-8')
       try:child.wait(timeout=8)
       except subprocess.TimeoutExpired:stop_owned_family(child,owned)
       raise InterruptedError('Stopped owned inference at resource/deadline boundary; no automatic retry')
      try:
       memory=sum(x.memory_info().private for x in [owned]+owned.children(recursive=True));peak=max(peak,memory)
       state['privatePeakBytes']=max(state['privatePeakBytes'],memory)
       if memory>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Owned family reached2GiB; no limit increase')
      except psutil.Error:pass
      if time.monotonic()-last_save>15:save();last_save=time.monotonic()
      time.sleep(.5)
    state['phases'].append({'phase':phase,'exitCode':child.returncode,'seconds':time.monotonic()-tick,'privatePeakBytes':peak});save()
    assert child.returncode==0 and read(a.run/(phase+'-state.json'))['state']==expected,'Inspect new evidence before any changed continuation'
   state.update(state='COMPLETE_OVERNIGHT_FOUR_MEETING_INFERENCE_SCORING_PENDING')
  except BaseException as error:state.update(state='OVERNIGHT_RUN_INCOMPLETE_FAILURE_RETAINED',error=repr(error));raise
  finally:
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   pressure.close();state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.monotonic()-started);save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
