"""One CPU model family with actual low-RAM protection and Owner's deadline."""
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
 assert not a.run.exists();a.run.mkdir(parents=True)
 B=read(a.control/'binding.json');S=Path(__file__).resolve().parent;worker=S/'cpu_window_joint_worker_20261116.py'
 assert sha(worker)==B['workerSha256'] and sha(__file__)==B['runnerSha256']
 assert psutil.disk_usage('E:/').free>50*1024**3
 pressure=SystemRamPressure();child=owned=None
 state={'state':'STARTING_CPU_WINDOW_COHORT','startedAt':datetime.now().astimezone().isoformat(),'privatePeakBytes':0,
  'qualityQualified':False,'wholeMeetingAcceptance':False,'automaticRetries':0,'neuralDeadline':B['neuralDeadline'],'reportDeadline':B['reportDeadline']}
 def save():atomic_json(a.run/'run.json',state)
 save()
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),PowerLease():
  try:
   assert not pressure.low()
   with (a.run/'worker.log').open('xb') as log:
    child=subprocess.Popen([B['workerPython'],str(worker),'--control',str(a.control),'--run',str(a.run)],
     stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    owned=psutil.Process(child.pid);state.update(state='RUNNING_CPU_WINDOW_COHORT',pid=child.pid,pidCreatedAt=owned.create_time());save();last=0.
    while child.poll() is None:
     if pressure.low() or (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):
      (a.run/'stop.request').write_text('Actual Windows low RAM, owned stop or Owner deadline.\n',encoding='utf-8')
      try:child.wait(timeout=8)
      except subprocess.TimeoutExpired:stop_owned_family(child,owned)
      raise InterruptedError('Preserve complete cases and original inputs')
     try:
      memory=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));state['privatePeakBytes']=max(state['privatePeakBytes'],memory)
      if memory>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Original2GiB private guard reached')
     except psutil.Error:pass
     if time.monotonic()-last>15:save();last=time.monotonic()
     time.sleep(.5)
   result=read(a.run/'inference-state.json');state['workerExitCode']=child.returncode
   assert child.returncode==0 and result['state']=='COMPLETE_CPU_WINDOW_COHORT_COMPOSITION_AND_SCORING_PENDING'
   state.update(state='COMPLETE_CPU_WINDOW_COHORT_COMPOSITION_AND_SCORING_PENDING',completedCases=len(result['completed']))
  except BaseException as error:state.update(state='INCOMPLETE_CPU_WINDOW_COHORT_RETAINED',error=repr(error));raise
  finally:
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
