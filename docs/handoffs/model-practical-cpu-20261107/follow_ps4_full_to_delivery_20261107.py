"""One-shot owned-run follow-through: score only complete output and protect it."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,psutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-full-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
def save(value):
    file=C/'followthrough.json';temp=file.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,file)
target=C/'followthrough.json';assert not target.exists()
run=read(C/'run-r2.json');owner=psutil.Process(run['pid']);identity=owner.create_time()
assert any(Path(a).name=='run_practical_ps4_full_20261107.py' for a in owner.cmdline())
scorer=R/'model-research/src/finish_practical_ps4_full_20261107.py';publisher=Path(__file__).with_name('preserve_practical_progress_20261107.py')
score_hash=sha(scorer);publisher_hash=sha(publisher)
state={'at':now(),'state':'FOLLOWING_OWNED_FULL_COMPLEX_TRIAL','ownedControllerPid':owner.pid,'ownedControllerCreateTime':identity,
    'scorerSourceSha256':score_hash,'publisherSourceSha256':publisher_hash,'modelFailureRetries':0,'qualityQualified':False}
save(state)
while True:
    current=read(C/'run-r2.json')
    if current.get('finishedAt') and not current.get('activePid'):break
    if not owner.is_running() or owner.create_time()!=identity:
        state.update(state='CONTROLLER_NOT_RUNNING_WITHOUT_TERMINAL_RECEIPT',at=now());save(state);print(json.dumps(state),flush=True);raise SystemExit(1)
    time.sleep(10)
assert not owner.is_running() or owner.create_time()!=identity,'Wait for actual controller exit before postprocessing'
state.update(neuralRunState=current['state'],neuralRunFinishedAt=current['finishedAt'])
assert sha(scorer)==score_hash and sha(publisher)==publisher_hash,'Source changed; retain model output and require explicit assessment restart'
if current['state']=='COMPLETE_TARGET_SEPARATION_AND_ASR_REVIEW_REQUIRED':
    with (C/'followthrough-scoring.log').open('xb') as log:
        result=subprocess.run(['E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe',str(scorer)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    state['scoringExitCode']=result.returncode
    if result.returncode:
        state.update(state='FULL_MODEL_OUTPUT_RETAINED_POSTHOC_REPAIR_REQUIRED',at=now());save(state);print(json.dumps(state),flush=True);raise SystemExit(result.returncode)
    phase='finished'
else:phase='running'
with (C/'followthrough-publish.log').open('xb') as log:
    result=subprocess.run([sys.executable,str(publisher),'--phase',phase],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
state.update(publishExitCode=result.returncode,at=now(),state='COMPLETE_SCORED_AND_REMOTE_PROTECTED' if phase=='finished' and result.returncode==0 else 'RUN_TERMINAL_UNQUALIFIED_CHECKPOINT_PROTECTED' if result.returncode==0 else 'PUBLISH_NEEDS_REPAIR_MODEL_OUTPUT_RETAINED')
save(state);print(json.dumps(state),flush=True)
