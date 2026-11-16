"""Candidate CPU decoder launcher. Existing GPU package/default remains untouched."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,subprocess,time,psutil
from companion_local_pcm_session_20261114 import PcmSession,exclusive_file
from practical_io_20261107 import atomic_json,stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
from run_moss_overnight_20261115 import PowerLease
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--follow-seconds',type=float,default=0);a=p.parse_args()
 B=read(a.control/'binding.json');worker=Path(__file__).with_name('companion_local_moss_cpu_worker_20261116.py')
 assert sha(worker)==B['workerSha256'] and sha(__file__)==B['runnerSha256'];assert 0<=a.follow_seconds<=10800
 assert not a.run.exists();a.run.mkdir(parents=True);session=PcmSession(a.session);session.reconcile()
 pressure=SystemRamPressure();child=owned=None;state={'state':'PREPARING_CPU_PCM_DECODER','startedAt':datetime.now().astimezone().isoformat(),
  'privatePeakBytes':0,'familyWorkingSetPeakBytes':0,'systemAvailableMinBytes':psutil.virtual_memory().available,'localOnly':True,
  'sourceUploaded':False,'qualityQualified':False,'productDefaultChanged':False,'automaticRetries':0}
 def save():atomic_json(a.run/'run.json',state)
 save()
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),exclusive_file(session.root/'inference.lock'),PowerLease():
  try:
   assert not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
   with (a.run/'worker.log').open('xb') as log:
    child=subprocess.Popen([B['workerPython'],str(worker),'--session',str(session.root),'--control',str(a.control),'--run',str(a.run),'--follow-seconds',str(a.follow_seconds)],
     stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    owned=psutil.Process(child.pid);state.update(state='RUNNING_CPU_PCM_DECODER',pid=child.pid,pidCreatedAt=owned.create_time());save();last=0.
    while child.poll() is None:
     if pressure.low() or (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):
      (a.run/'stop.request').write_text('Actual low RAM/owned stop/deadline.\n',encoding='utf-8')
      try:child.wait(timeout=8)
      except subprocess.TimeoutExpired:stop_owned_family(child,owned)
      raise InterruptedError('Confirmed PCM, accepted results and partials retained')
     try:
      mem=[p.memory_info() for p in [owned]+owned.children(recursive=True)];private=sum(x.private for x in mem)
      state['privatePeakBytes']=max(state['privatePeakBytes'],private);state['familyWorkingSetPeakBytes']=max(state['familyWorkingSetPeakBytes'],sum(x.rss for x in mem))
      state['systemAvailableMinBytes']=min(state['systemAvailableMinBytes'],psutil.virtual_memory().available)
      if private>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Original family2GiB guard')
     except psutil.Error:pass
     if time.monotonic()-last>15:save();last=time.monotonic()
     time.sleep(.5)
   state.update(workerExitCode=child.returncode,workerState=read(a.run/'worker-state.json')['state']);assert child.returncode==0
   state['state']='CPU_PCM_ATTEMPT_COMPLETE_REVIEW_PENDING'
  except BaseException as error:state.update(state='INCOMPLETE_CPU_PCM_ATTEMPT_RETAINED',error=repr(error));raise
  finally:
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
