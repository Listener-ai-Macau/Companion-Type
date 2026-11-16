"""Bound stateless classifier lifetime; reuse accepted61 leaves, compute remaining18."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,time,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
old=B/'cpu-retained-baseline-alignment-r1';C=B/'cpu-retained-baseline-alignment-r2';run=E/'cpu-retained-baseline-alignment-full-r2';PY='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
failed=read(E/'cpu-retained-baseline-alignment-full-r1/run.json');previous=read(E/'cpu-retained-baseline-alignment-full-r1/worker-state.json')
assert '2GiB' in failed['error'] and len(previous['completed'])==61 and previous['activeCase']=='000061-root'
binding=read(old/'binding.json');assert sha(S/'cpu_forced_alignment_worker_20261116.py')==binding['workerSha256']
for item in previous['completed']:assert sha(item['file'])==item['sha256']
accepted={x['id'] for x in previous['completed']};pending=[x for x in binding['cases'] if x['id'] not in accepted];assert len(pending)==18
assert not C.exists() and not run.exists();C.mkdir();run.mkdir()
for name in ['composition-binding.json','whole-scoring-only.json']:(C/name).write_bytes((old/name).read_bytes())
score=read(old/'scoring-binding.json');score['files']={str(C/Path(k).name) if Path(k).parent==old else k:v for k,v in score['files'].items()};atomic_json(C/'scoring-binding.json',score)
atomic_json(C/'binding.json',binding)
batches=[]
for offset in range(0,len(pending),16):
 control=C/('batch-'+str(len(batches)));control.mkdir();part=dict(binding,cases=pending[offset:offset+16],reuseCompleted=[]);part.pop('reuseBinding',None);atomic_json(control/'binding.json',part)
 batches.append({'control':str(control),'run':str(E/('cpu-alignment-recovery-batch-'+str(len(batches)))),'cases':[x['id'] for x in part['cases']]})
atomic_json(C/'process-lifetime-policy.json',{'state':'FIXED_STATELESS_CPU_CLASSIFIER_MAX16_LEAVES_PER_OWNED_PROCESS_BEFORE_RECOVERY','at':datetime.now().astimezone().isoformat(),
 'reason':'A long-lived CPU classifier completed61 retained leaves but private commit accumulated across varied shapes, then the unchanged2GiB family guard stopped it. Exact allocator/primitive-cache mechanism not yet proven. A bounded process lifetime releases its private allocations deterministically.',
 'unchangedWorkerSha256':binding['workerSha256'],'failedRun':failed,'acceptedLeavesReused':61,'newLeaves':18,'batches':batches,'maximumLeavesPerProcess':16,
 'newModelOrPresetSearch':False,'noSourceAudioRecut':True,'speakerModelRemainsOneContinuousOriginalSourceState':True,'qualityQualified':False})
pressure=SystemRamPressure();state={'state':'WAITING_ORIGINAL_MEMORY_RECOVERY_STABLE60','startedAt':datetime.now().astimezone().isoformat(),'reusedLeaves':61,'completedRecoveryBatches':[],'qualityQualified':False}
def save():atomic_json(C/'run.json',state)
save();stable=None
try:
 while True:
  assert datetime.now().astimezone()<datetime.fromisoformat(binding['neuralDeadline']);healthy=not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
  stable=time.monotonic() if healthy and stable is None else (stable if healthy else None)
  if stable is not None and time.monotonic()-stable>=60:break
  time.sleep(1)
 completed=list(previous['completed'])
 for batch in batches:
  state.update(state='RECOVERING_ONLY_UNCOMMITTED_LEAVES_IN_BOUNDED_STATELESS_CPU_PROCESS',activeBatch=batch);save()
  subprocess.run([PY,str(S/'run_cpu_forced_alignment_20261116.py'),'--control',batch['control'],'--run',batch['run']],check=True)
  record=read(Path(batch['run'])/'worker-state.json');assert [x['id'] for x in record['completed']]==batch['cases'];completed.extend(record['completed']);state['completedRecoveryBatches'].append({'batch':batch,'execution':read(Path(batch['run'])/'run.json')});save()
 assert len(completed)==len(binding['cases'])==79 and {x['id'] for x in completed}=={x['id'] for x in binding['cases']}
 completed=sorted(completed,key=lambda x:next(i for i,c in enumerate(binding['cases']) if c['id']==x['id']))
 atomic_json(run/'worker-state.json',{'state':'COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED','completed':completed,
  'producerKind':'Exact immutable stateless leaf assembly from prior accepted results and two bounded recovery processes; not one long-lived worker.',
  'sourceAsrInferenceBackend':binding['sourceAsrInferenceBackend'],'newAsrNeuralCalls':0,'newSpeakerNeuralCalls':0,'reusedLeaves':61,'recoveryNewAlignmentCalls':18,
  'priorIncompleteRun':str(E/'cpu-retained-baseline-alignment-full-r1'),'recoveryBatches':state['completedRecoveryBatches'],'qualityQualified':False})
 subprocess.run([PY,str(S/'compose_cpu_qwen_alignment_20261116.py'),'--control',str(C),'--run',str(run)],check=True)
 subprocess.run([PY,str(S/'score_cpu_qwen_alignment_20261116.py'),'--control',str(C),'--run',str(run)],check=True)
 checker=Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe');doc=run/'composed/S_R004S03C01-model-output.json'
 checked=subprocess.run([str(checker),str(doc),str(round(2327.119*1000))],capture_output=True,text=True)
 atomic_json(C/'product-contract.json',{'exitCode':checked.returncode,'stdout':checked.stdout,'stderr':checked.stderr,'checkerSha256':sha(checker),'documentSha256':sha(doc),'installedNativeUiTested':False})
 state.update(state='COMPLETE_RETAINED_NATIVE_ASR_CPU_ALIGNMENT_VOICES_FULL_RECORDING_CHARACTERIZATION_NOT_QUALIFIED',sharedRustDocumentContractPassed=checked.returncode==0);state.pop('activeBatch',None)
except BaseException as error:state.update(state='INCOMPLETE_BOUNDED_PROCESS_RECOVERY_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
finally:pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save();atomic_json(run/'run.json',state)
print(json.dumps(state,ensure_ascii=False))
