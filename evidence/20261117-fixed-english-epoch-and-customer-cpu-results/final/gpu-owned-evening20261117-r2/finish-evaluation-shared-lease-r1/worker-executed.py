"""One explicit zero-inference lock-admission recovery, then original evaluation.

Wait for the identified other job; do not signal, kill or alter it. Preserve the
failed admission directories. No training, neural retry, new model or promotion.
"""
from pathlib import Path
from datetime import datetime
import json,os,psutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from meeting_acoustic_worker_20261116 import own_limits
from durable_model_state_20261117 import atomic_json
from companion_local_pcm_session_20261114 import exclusive_file
from meeting_acoustic_contract_20261116 import sha
limits=own_limits(25)
T=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/gpu-owned-evening20261117-r2')
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/language-specific-adaptation-r1/prepared-gpu-evening20261117-r2'
PFILE=D/'protocol.json';CONTROL=D/'scoring-control-verified.json'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
P=read(PFILE);out=T/'finish-evaluation-shared-lease-r1';out.mkdir(exist_ok=False)
state=dict(state='WAITING_IDENTIFIED_SHARED_MODEL_JOB',pid=os.getpid(),createdAt=psutil.Process().create_time(),
 otherPid=4668,otherCreatedAt=1794923433.4203124,protocolSha256=sha(PFILE),
 noAutomaticModelRetry=True,qualityQualified=False,saleQualified=False)
def save(**v):
 state.update(v,at=datetime.now().astimezone().isoformat(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
def call(command,label):
 save(state=label,command=command)
 with (out/(label+'.log')).open('w',encoding='utf-8') as log:
  code=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 assert code==0,(label,code)
try:
 save()
 while psutil.pid_exists(state['otherPid']):
  try:
   if abs(psutil.Process(state['otherPid']).create_time()-state['otherCreatedAt'])>=.01:break
  except psutil.NoSuchProcess:break
  assert datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Frozen window ended while other job owns shared resources'
  time.sleep(1)
 assert datetime.now().astimezone()<datetime.fromisoformat(P['stopAt'])
 with exclusive_file(Path(P['neuralLock'])):pass
 failure=read(T/'supervisor-validate/completed.json')
 assert failure['exitCode']==1 and failure['workerIdentity'] is None
 assert not (T/'validate/state.json').exists() and not list((T/'validate/results').iterdir())
 assert 'SessionConflict' in (T/'supervisor-validate/stdout.log').read_text(encoding='utf-8')
 assert read(T/'training-completed.json')['candidateOptimizerUpdates']==457
 preserved=[]
 for name in ['validate','supervisor-validate']:
  source=(T/name).resolve();target=(T/(name+'-lock-admission-failed-r1')).resolve()
  assert source.parent==T.resolve() and target.parent==T.resolve() and not target.exists()
  source.rename(target);preserved.append(str(target))
 save(state='SHARED_RESOURCE_RELEASE_CONFIRMED_ADMISSION_FAILURE_PRESERVED',preservedDirectories=preserved,
  failedAdmissionNewNeuralCalls=0,failedAdmissionParameterUpdates=0)
 atomic_json(out/'admission-recovery.json',state)
 call([P['runtime']['python'],str(S/'run_owned_tdt_adaptation_20261117.py'),'--worker',str(S/'tdt_domain_adaptation_20261116.py'),
  '--protocol',str(PFILE),'--phase','validate','--run',str(T)],'VALIDATING_EXACT_FINAL457_CHECKPOINT')
 call(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(S/'score_tdt_adaptation_20261117.py'),
  '--control',str(CONTROL),'--run',str(T),'--output',str(T/'paired-score.json')],'SCORING_ORIGINAL12_AND709_WORDS')
 score=read(T/'paired-score.json');save(baselineErrors=score['baselineErrors'],candidateErrors=score['candidateErrors'],
  candidateWer=score['candidateWer'],advanceToCompleteSources=score['advanceToCompleteSources'])
 worker=Path(__file__).with_name('probe_customer_cpu_bilingual_20261117.py')
 call([sys.executable,str(worker),'--execute'],'CPU_EXISTING_BILINGUAL_MODEL_PROBE')
 call([sys.executable,str(worker),'--score'],'SCORING_EXISTING_CPU_BILINGUAL_PROBE')
 save(state='COMPLETE_FINAL_ENGLISH_CHECKPOINT_AND_CPU_BILINGUAL_PROBE')
 atomic_json(out/'completed.json',state);print(json.dumps(state,ensure_ascii=False))
except BaseException as error:
 save(state='STOPPED_SHARED_LEASE_FOLLOWUP_WITHOUT_MODEL_RETRY',error=repr(error));atomic_json(out/'completed.json',state);raise
