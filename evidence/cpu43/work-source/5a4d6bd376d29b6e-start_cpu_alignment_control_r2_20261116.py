from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,time,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
failed=read(E/'cpu-forced-alignment-control-r1/worker-state.json');assert failed['newNeuralCalls']==0 and not failed['modelLoaded'] and 'transformers' in failed['error']
C=B/'cpu-forced-alignment-control-r2';assert not C.exists();C.mkdir();binding=read(B/'cpu-forced-alignment-control-r1/binding.json')
runtime=read(B/'cpu-forced-alignment-r2/runtime-installation.json');binding['workerPython']=runtime['source']['basePython']
binding['correctedBeforeAnyModelNeuralCall']={'previousRun':str(E/'cpu-forced-alignment-control-r1/worker-state.json'),'sha256':sha(E/'cpu-forced-alignment-control-r1/worker-state.json'),
 'rootCause':'The prior preparation incorrectly inherited the CPP scoring Python, which lacks Transformers; select the pinned processor dependency environment with the isolated official CPU Torch overlay. No model/math/limits change.'}
binding['noFullExpansionOfRejectedQwenCpuAsr']=True
atomic_json(C/'binding.json',binding);state={'state':'WAITING_ORIGINAL_MEMORY_RECOVERY_STABLE_60_SECONDS','startedAt':datetime.now().astimezone().isoformat(),'automaticNeuralRetries':0,'qualityQualified':False};pressure=SystemRamPressure()
def save():atomic_json(C/'queue.json',state)
save();stable=None
try:
 while True:
  assert datetime.now().astimezone()<datetime.fromisoformat(binding['neuralDeadline'])
  healthy=not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
  stable=time.monotonic() if healthy and stable is None else (stable if healthy else None)
  if stable is not None and time.monotonic()-stable>=60:break
  time.sleep(1)
 state.update(state='RUNNING_CORRECTED_RUNTIME_CONTROL_NO_MODEL_RETRY',availableBytesAtLaunch=psutil.virtual_memory().available);save()
 subprocess.run(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(S/'run_cpu_forced_alignment_20261116.py'),'--control',str(C),'--run',str(E/'cpu-forced-alignment-control-r2')],check=True)
 state['state']='COMPLETE_FIXED_CPU_CLASSIFIER_CONTROLS_REVIEW_PENDING'
except BaseException as error:state.update(state='INCOMPLETE_CONTROL_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
finally:pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
print(json.dumps(state,ensure_ascii=False))
