from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,time,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');C=B/'cpu-retained-baseline-alignment-r1'
PY='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (C/'run.json').exists();state={'state':'WAITING_ORIGINAL_MEMORY_STABILITY_BEFORE_BASELINE_FIRST_LEAF','startedAt':datetime.now().astimezone().isoformat(),'sourceAsrBackend':'protected previous GPU result, no ASR rerun','newAsrNeuralCalls':0,'newSpeakerNeuralCalls':0,'qualityQualified':False};pressure=SystemRamPressure()
def save():atomic_json(C/'run.json',state)
def stable_memory():
 tick=None
 while True:
  assert datetime.now().astimezone()<datetime.fromisoformat('2026-11-16T15:40:00+08:00')
  healthy=not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
  tick=time.monotonic() if healthy and tick is None else (tick if healthy else None)
  if tick is not None and time.monotonic()-tick>=60:return
  time.sleep(1)
def execute(control,run):subprocess.run([PY,str(S/'run_cpu_forced_alignment_20261116.py'),'--control',str(control),'--run',str(run)],check=True)
save()
try:
 stable_memory();state['state']='RUNNING_RETAINED_NATIVE_BASELINE_FIRST_LEAF_CPU_CLASSIFIER';save();pilot=E/'cpu-retained-baseline-alignment-pilot-r1';execute(C/'pilot',pilot)
 result=read(pilot/'worker-state.json');assert len(result['completed'])==1;item=result['completed'][0];assert sha(item['file'])==item['sha256'];packet=read(item['file'])
 assert packet['payload']['allOriginalCharactersPreserved'] and any(x['positiveAndInOriginalLeafBounds'] for x in packet['payload']['units'])
 binding=read(C/'pilot/binding.json');binding['cases']=read(C/'frozen-audio-recognized-text-only.json')['cases'];binding['reuseCompleted']=result['completed'];binding['reuseBinding']={'file':str(C/'pilot/binding.json'),'sha256':sha(C/'pilot/binding.json')}
 atomic_json(C/'binding.json',binding);state['state']='WAITING_ORIGINAL_MEMORY_STABILITY_BEFORE_UNCHANGED_FULL_CLASSIFIER';save();stable_memory()
 full=E/'cpu-retained-baseline-alignment-full-r1';state['state']='RUNNING_RETAINED_NATIVE_BASELINE_COMPLETE_CPU_CLASSIFIER';save();execute(C,full)
 subprocess.run([PY,str(S/'compose_cpu_qwen_alignment_20261116.py'),'--control',str(C),'--run',str(full)],check=True)
 subprocess.run([PY,str(S/'score_cpu_qwen_alignment_20261116.py'),'--control',str(C),'--run',str(full)],check=True)
 checker=Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe');document=full/'composed/S_R004S03C01-model-output.json'
 check=subprocess.run([str(checker),str(document),str(round(2327.119*1000))],capture_output=True,text=True)
 atomic_json(C/'product-contract.json',{'exitCode':check.returncode,'stdout':check.stdout,'stderr':check.stderr,'checkerSha256':sha(checker),'documentSha256':sha(document),'installedNativeUiTested':False})
 state.update(state='COMPLETE_RETAINED_NATIVE_ASR_CPU_ALIGNMENT_VOICES_FULL_RECORDING_CHARACTERIZATION_NOT_QUALIFIED',sharedRustDocumentContractPassed=check.returncode==0)
except BaseException as error:state.update(state='INCOMPLETE_BASELINE_COMPONENT_PORT_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
finally:pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
print(json.dumps(state,ensure_ascii=False))
