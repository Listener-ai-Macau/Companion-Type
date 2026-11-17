"""Finish this one owned epoch with validation and the original paired scorer.

No retries, checkpoint selection, deployment or new model trials. Training is
already running; a failed/incomplete phase never advances to evaluation.
"""
from pathlib import Path
from datetime import datetime
import json,subprocess,sys,time,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from meeting_acoustic_worker_20261116 import own_limits
from durable_model_state_20261117 import atomic_json
from meeting_acoustic_contract_20261116 import sha
limits=own_limits(25)
run=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/gpu-owned-evening20261117-r2')
directory=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/language-specific-adaptation-r1/prepared-gpu-evening20261117-r2'
protocol=directory/'protocol.json';control=directory/'scoring-control-verified.json'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
P=read(protocol);identity=read(run/'supervisor-train/started.json')
out=run/'finish-evaluation-r1';out.mkdir(exist_ok=False)
state=dict(state='FOLLOWING_ONE_FIXED_TRAINING_PHASE',pid=psutil.Process().pid,createdAt=psutil.Process().create_time(),
 protocol=str(protocol),protocolSha256=sha(protocol),scoringControl=str(control),scoringControlSha256=sha(control),
 trainLauncherPid=identity['pid'],trainLauncherCreatedAt=identity['createdAt'],automaticRetry=False,qualityQualified=False,saleQualified=False)
def save(**values):
 state.update(values,at=datetime.now().astimezone().isoformat(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
try:
 save();missing_since=None
 while not (run/'supervisor-train/completed.json').exists():
  assert datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Frozen execution window ended'
  alive=psutil.pid_exists(identity['pid']) and abs(psutil.Process(identity['pid']).create_time()-identity['createdAt'])<.01
  if not alive:
   missing_since=missing_since or time.monotonic()
   assert time.monotonic()-missing_since<5,'Training launcher ended without supervisor completion'
  time.sleep(1)
 result=read(run/'supervisor-train/completed.json')
 assert result['state']=='OWNED_TDT_PHASE_COMPLETE' and result['exitCode']==0,'Training did not complete cleanly'
 final=read(run/'training-completed.json')
 assert final['completedTrainingExamples']==1828 and final['candidateOptimizerUpdates']==457,'One fixed epoch incomplete'
 assert datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'No evaluation outside the frozen window'
 command=[P['runtime']['python'],str(S/'run_owned_tdt_adaptation_20261117.py'),'--worker',str(S/'tdt_domain_adaptation_20261116.py'),
  '--protocol',str(protocol),'--phase','validate','--run',str(run)]
 save(state='VALIDATING_EXACT_FINAL457_UPDATE_CHECKPOINT',command=command)
 with (out/'validate-supervisor.log').open('w',encoding='utf-8') as log:
  code=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 assert code==0,'Validation failed; retain without retry'
 result=read(run/'supervisor-validate/completed.json')
 assert result['state']=='OWNED_TDT_PHASE_COMPLETE' and result['exitCode']==0
 output=run/'paired-score.json'
 command=['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',
  str(S/'score_tdt_adaptation_20261117.py'),'--control',str(control),'--run',str(run),'--output',str(output)]
 save(state='INDEPENDENTLY_SCORING_ORIGINAL12_AND709_WORDS',command=command)
 with (out/'score.log').open('w',encoding='utf-8') as log:
  code=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 assert code==0,'Independent scoring failed; retain inputs and no changed retry'
 score=read(output)
 save(state='COMPLETE_FIXED_EPOCH_AND_ORIGINAL_PAIRED_EVALUATION',scoreFile=str(output),
  baselineErrors=score['baselineErrors'],candidateErrors=score['candidateErrors'],candidateWer=score['candidateWer'],
  advanceToCompleteSources=score['advanceToCompleteSources'])
 atomic_json(out/'completed.json',state);print(json.dumps({k:state[k] for k in ['state','baselineErrors','candidateErrors','candidateWer','advanceToCompleteSources']}),flush=True)
except BaseException as error:
 save(state='STOPPED_FIXED_EPOCH_FOLLOWUP_WITHOUT_AUTOMATIC_RETRY',error=repr(error))
 atomic_json(out/'completed.json',state);raise
