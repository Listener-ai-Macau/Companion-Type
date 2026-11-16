"""One fixed memory-control test against a retained real native output, not ASR tuning."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
base=B/'qwen-cpu-chinese-characterization-r1';oldrun=E/'qwen-cpu-chinese-whole-run-r1';old=read(oldrun/'run.json');previous=read(oldrun/'inference-state.json')
assert old['stopReason']=='actual_windows_low_memory' and len(previous['completed'])==1
item=previous['completed'][0];packet=read(item['file']);assert packet['naturalEos'] and sha(item['file'])==item['sha256']
C=B/'qwen-cpu-working-set-r1/neural-control';assert not C.exists();C.mkdir()
probe=read(C.parent/'probe.json');assert probe['state']=='PASS_EXACT_READONLY_MODEL_BYTES_WITH_ENFORCED_175GIB_WORKING_SET_NO_NEURAL_CALLS'
worker=S/'qwen_cpu_workingset_worker_20261116.py';text=(S/'qwen_cpu_chinese_whole_worker_20261116.py').read_text(encoding='utf-8')
text=text.replace('from practical_io_20261107 import atomic_json','from practical_io_20261107 import atomic_json\nfrom companion_windows_working_set_20261116 import WorkingSetCeiling')
marker="assert limits.query()['cpuRate']==2500 and limits.query()['jobPrivateCommitLimitBytes']==2*1024**3"
assert text.count(marker)==1;text=text.replace(marker,marker+"\n ws=WorkingSetCeiling(B['maximumWorkingSetBytes'])")
marker="lock=threading.RLock();watch_stop=threading.Event()";assert text.count(marker)==1;text=text.replace(marker,"state['workingSetControl']=ws.query()\n "+marker)
condition="if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):session.cancel();return"
assert text.count(condition)==1;text=text.replace(condition,"if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']) or (B.get('caseTimeBudgetSeconds') and time.perf_counter()-tick>B['caseTimeBudgetSeconds']):session.cancel();return")
assert not worker.exists();worker.write_text(text,encoding='utf-8');compile(text,str(worker),'exec')
runner=S/'run_qwen_cpu_workingset_20261116.py';text=(S/'run_qwen_cpu_chinese_whole_20261116.py').read_text(encoding='utf-8').replace('qwen_cpu_chinese_whole_worker_20261116.py',worker.name)
assert not runner.exists();runner.write_text(text,encoding='utf-8');compile(text,str(runner),'exec')
binding=read(base/'binding.json');binding.update(workerSha256=sha(worker),runnerSha256=sha(runner),cases=[binding['cases'][0]],resumeCompleted=[],
 maximumWorkingSetBytes=1879048192,caseTimeBudgetSeconds=packet['seconds']*2,
 resourceControl={'expectedRawFile':item['file'],'expectedRawSha256':item['sha256'],'originalSeconds':packet['seconds'],
 'keepRule':'Same rawDecoded/hypothesis/naturalEOS, original25%/4/2GiB+lowRAM guards, observed family RSS<=1.75GiB+64MiB, compute no slower than2x original. Otherwise reject this memory setting; no ceiling grid.'})
binding['helpers'][str(S/'companion_windows_working_set_20261116.py')]=sha(S/'companion_windows_working_set_20261116.py')
atomic_json(C/'binding.json',binding);atomic_json(C/'protocol.json',binding['resourceControl'])
pressure=SystemRamPressure();stable=None;started=time.monotonic();observations=[]
try:
 while time.monotonic()-started<300:
  available=psutil.virtual_memory().available;low=pressure.low();observations.append({'at':datetime.now().astimezone().isoformat(),'availableBytes':available,'actualWindowsLowMemory':low})
  if not low and available>=int(3.18*1024**3):
   if stable is None:stable=time.monotonic()
   if time.monotonic()-stable>=60:break
  else:stable=None
  time.sleep(5)
 else:raise RuntimeError('Original stable recovery gate not met; no neural control start')
finally:pressure.close();atomic_json(C/'recovery-observation.json',{'observations':observations,'newNeuralCalls':0,'stableRecoveryReached':stable is not None and time.monotonic()-stable>=60})
print(json.dumps({'control':str(C),'run':str(E/'qwen-cpu-working-set-control-r1'),'caseComputeBudgetSeconds':binding['caseTimeBudgetSeconds'],'originalRamGateRecovered':True}))
