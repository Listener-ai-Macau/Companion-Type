"""Serialize complete ASR scoring and fixed classifier controls; no neural retries."""
from pathlib import Path
from datetime import datetime
import json,subprocess,sys,time,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');CLEAN='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
target=B/'cpu-forced-alignment-control-r1/queue.json';assert not target.exists()
state={'state':'WAITING_EXISTING_WHOLE_ASR_FAMILY_TO_CLOSE','startedAt':datetime.now().astimezone().isoformat(),'automaticNeuralRetries':0,'requiredStableMemorySeconds':60,'qualityQualified':False};pressure=SystemRamPressure()
def save():atomic_json(target,state)
save()
try:
 while True:
  if datetime.now().astimezone()>=datetime.fromisoformat('2026-11-16T15:40:00+08:00'):raise TimeoutError('Absolute neural deadline reached while queued')
  prior=read(E/'qwen-cpu-chinese-whole-run-r2/run.json')
  if prior.get('finishedAt'):
   assert prior['state']=='COMPLETE_QWEN_CPU_PORT_CLIPS_SCORING_PENDING','Do not advance a failed or low-memory interrupted preceding family';break
  time.sleep(2)
 assert not (B/'qwen-cpu-chinese-characterization-r2/whole-score.json').exists()
 subprocess.run([CLEAN,str(S/'score_qwen_cpu_chinese_whole_20261116.py'),'--control',str(B/'qwen-cpu-chinese-characterization-r2'),'--run',str(E/'qwen-cpu-chinese-whole-run-r2')],check=True)
 state['state']='WAITING_ORIGINAL_MEMORY_RECOVERY_STABLE_60_SECONDS';save();stable=None
 while True:
  if datetime.now().astimezone()>=datetime.fromisoformat('2026-11-16T15:40:00+08:00'):raise TimeoutError('Absolute neural deadline reached during resource recovery')
  healthy=not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
  stable=time.monotonic() if healthy and stable is None else (stable if healthy else None)
  if stable is not None and time.monotonic()-stable>=60:break
  time.sleep(1)
 state['state']='RUNNING_FIXED_CPU_CLASSIFIER_STANDARD_VERSUS_MMAP_AND_BILINGUAL_CONTROLS';state['availableBytesAtLaunch']=psutil.virtual_memory().available;save()
 subprocess.run([CLEAN,str(S/'run_cpu_forced_alignment_20261116.py'),'--control',str(B/'cpu-forced-alignment-control-r1'),'--run',str(E/'cpu-forced-alignment-control-r1')],check=True)
 state['state']='COMPLETE_FIXED_CPU_CLASSIFIER_CONTROLS_REVIEW_PENDING'
except BaseException as error:state.update(state='INCOMPLETE_QUEUE_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
finally:pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
print(json.dumps(state,ensure_ascii=False))
