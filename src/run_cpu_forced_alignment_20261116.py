"""Run one owned native CPU classifier family under existing resource guards."""
from pathlib import Path
from datetime import datetime
import argparse,json,hashlib,subprocess,time,psutil
from moss_windows_resource_limits_20261104 import SystemRamPressure
from companion_local_pcm_session_20261114 import exclusive_file
from run_moss_overnight_20261115 import PowerLease
from practical_io_20261107 import atomic_json,stop_owned_family
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 B=read(a.control/'binding.json');worker=Path(__file__).with_name('cpu_forced_alignment_worker_20261116.py')
 assert 0<len(B['cases'])<=16,'Use the bounded stateless coordinator for a longer recording; never retain one classifier process across more than16 leaves'
 assert sha(worker)==B['workerSha256'] and sha(__file__)==B['runnerSha256']
 pressure=SystemRamPressure();child=owned=None
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),PowerLease():
  assert not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3),'Original memory start gate unmet'
  assert datetime.now().astimezone()<datetime.fromisoformat(B['neuralDeadline'])
  assert not a.run.exists();a.run.mkdir(parents=True)
  state={'state':'STARTING_NATIVE_CPU_ALIGNMENT','startedAt':datetime.now().astimezone().isoformat(),'privatePeakBytes':0,'familyWorkingSetPeakBytes':0,
   'systemAvailableMinBytes':psutil.virtual_memory().available,'qualityQualified':False,'automaticRetries':0,'neuralDeadline':B['neuralDeadline']}
  def save():atomic_json(a.run/'run.json',state)
  save()
  try:
   with (a.run/'worker.log').open('xb') as log:
    child=subprocess.Popen([B['workerPython'],str(worker),'--control',str(a.control),'--run',str(a.run)],stdout=log,stderr=subprocess.STDOUT,
     creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    owned=psutil.Process(child.pid);state.update(state='RUNNING_NATIVE_CPU_ALIGNMENT',pid=child.pid,pidCreatedAt=owned.create_time());save();last=0.
    while child.poll() is None:
     low=pressure.low();available=psutil.virtual_memory().available
     if low or (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):
      state['stopReason']='actual_windows_low_memory' if low else ('owned_stop_request' if (a.run/'stop.request').exists() else 'neural_deadline')
      state['availableBytesAtStop']=available;save();(a.run/'stop.request').write_text(state['stopReason']+'\n',encoding='utf-8')
      try:child.wait(timeout=8)
      except subprocess.TimeoutExpired:stop_owned_family(child,owned)
      raise InterruptedError('Owned guard; immutable text and completed outputs retained')
     try:
      mem=[x.memory_info() for x in [owned]+owned.children(recursive=True)];private=sum(x.private for x in mem)
      state['privatePeakBytes']=max(state['privatePeakBytes'],private);state['familyWorkingSetPeakBytes']=max(state['familyWorkingSetPeakBytes'],sum(x.rss for x in mem))
      state['systemAvailableMinBytes']=min(state['systemAvailableMinBytes'],available)
      if private>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Original2GiB family private guard')
     except psutil.Error:pass
     if time.monotonic()-last>15:save();last=time.monotonic()
     time.sleep(.5)
   result=read(a.run/'worker-state.json');state['workerExitCode']=child.returncode
   assert child.returncode==0 and result['state']=='COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED' and len(result['completed'])==len(B['cases'])
   state.update(state='COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED',completedInputs=len(result['completed']))
  except BaseException as error:state.update(state='INCOMPLETE_CPU_ALIGNMENT_RETAINED',error=repr(error));raise
  finally:
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
