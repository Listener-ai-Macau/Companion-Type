"""No-neural exact model-byte scan under a scoped physical working-set ceiling."""
from pathlib import Path
from datetime import datetime
import ctypes,hashlib,json,mmap,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate,SystemRamPressure
from companion_windows_working_set_20261116 import WorkingSetCeiling
from practical_io_20261107 import atomic_json
import psutil
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';C=B/'qwen-cpu-working-set-r1';assert not C.exists();C.mkdir()
source=json.loads((B/'qwen-cpu-port-r1/model-ready.json').read_text(encoding='utf-8'))
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
control=WorkingSetCeiling(int(1.75*1024**3));pressure=SystemRamPressure();process=psutil.Process();tick=time.monotonic()
state={'state':'PROBING_READONLY_MMAP_WORKING_SET_NO_NEURAL_MODEL','startedAt':datetime.now().astimezone().isoformat(),'workingSetControl':control.query(),
 'peakWorkingSetBytes':0,'peakPrivateBytes':0,'systemAvailableMinBytes':psutil.virtual_memory().available,'bytesScanned':0,'newNeuralCalls':0,'modelLoaded':False}
try:
 with Path(source['file']).open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as mapped:
  h=hashlib.sha256()
  for start in range(0,len(mapped),1024**2):
   if pressure.low():raise InterruptedError('Actual Windows low-memory notification, no neural model started')
   view=memoryview(mapped)[start:start+1024**2];h.update(view);state['bytesScanned']+=len(view);view.release()
   memory=process.memory_info();state['peakWorkingSetBytes']=max(state['peakWorkingSetBytes'],memory.rss);state['peakPrivateBytes']=max(state['peakPrivateBytes'],memory.private)
   state['systemAvailableMinBytes']=min(state['systemAvailableMinBytes'],psutil.virtual_memory().available)
  assert h.hexdigest()==source['sha256'] and state['peakWorkingSetBytes']<=control.maximum+64*1024**2
 state.update(state='PASS_EXACT_READONLY_MODEL_BYTES_WITH_ENFORCED_175GIB_WORKING_SET_NO_NEURAL_CALLS',modelSha256=h.hexdigest())
except BaseException as error:state.update(state='INCOMPLETE_NONNEURAL_WORKING_SET_PROBE',error=repr(error));raise
finally:pressure.close();state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.monotonic()-tick,limits=limits.query());atomic_json(C/'probe.json',state)
print(json.dumps(state,ensure_ascii=False))
