"""One local C++ joint architecture; bounded private RAM/CPU, no retry or fallback."""
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
 src=Path(__file__).resolve().parent;worker=src/'cpp_joint_meeting_worker_20261115.py';B=read(a.control/'cpp-binding.json')
 assert sha(worker)==B['workerSha256'] and sha(__file__)==B['runnerSha256']
 state={'state':'PREPARING_CPP_JOINT_ARCHITECTURE','startedAt':datetime.now().astimezone().isoformat(),
  'phases':[],'privatePeakBytes':0,'qualityQualified':False,'automaticRetries':0,'noCpuFallback':True}
 def save():atomic_json(a.run/'run.json',state)
 pressure=SystemRamPressure();child=owned=None;began=time.monotonic();save()
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),PowerLease():
  try:
   for phase,expected in [('inventory','PASS_PINNED_CPP_ABI_AND_LIVE_6800XT_VULKAN_NO_MODEL'),
    ('full','COMPLETE_CPP_JOINT_FOUR_WHOLE_MEETING_OUTPUTS_SCORING_PENDING')]:
    assert not pressure.low(),'Actual Windows low-memory notification'
    command=[sys.executable,str(worker),'--phase',phase,'--control',str(a.control),'--run',str(a.run)]
    env={k:v for k,v in os.environ.items() if k not in ['PYTHONPATH','TRANSCRIBE_LIBRARY','TRANSCRIBE_BACKEND','TRANSCRIBE_NATIVE_PROVIDER']}
    tick=time.monotonic();peak=0
    with (a.run/(phase+'-worker.log')).open('xb') as log:
     child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
     owned=psutil.Process(child.pid);state.update(state='RUNNING_CPP_JOINT_'+phase.upper(),pid=child.pid,pidCreatedAt=owned.create_time());save()
     while child.poll() is None:
      if pressure.low() or (a.run/'stop.request').exists() or time.monotonic()-tick>14400:
       stop_owned_family(child,owned);raise InterruptedError('Owned native inference stopped; original audio/raw outputs preserved')
      try:
       memory=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));peak=max(peak,memory)
       state['privatePeakBytes']=max(state['privatePeakBytes'],memory)
       if memory>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Owned C++ model family reached2GiB')
      except psutil.Error:pass
      time.sleep(.5)
    state['phases'].append({'phase':phase,'exitCode':child.returncode,'privatePeakBytes':peak,'seconds':time.monotonic()-tick});save()
    assert child.returncode==0 and read(a.run/(phase+'-state.json'))['state']==expected,'Native phase failed; inspect once before changed continuation'
   state.update(state='COMPLETE_CPP_JOINT_WHOLE_MEETING_RUN_SCORING_PENDING')
  except BaseException as error:state.update(state='INCOMPLETE_CPP_JOINT_FAILURE_RETAINED',error=repr(error));raise
  finally:
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   pressure.close();state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.monotonic()-began);save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
