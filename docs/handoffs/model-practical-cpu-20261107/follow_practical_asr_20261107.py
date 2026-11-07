"""Follow this existing concrete run, with a pre-score futility stop; no inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');base=R/'docs/handoffs/20261107-model-generation-recovery';C=base/'practical-qwen-signal-r3';full=C/'full'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
quality=full/'transcripts/S_R004S03C01/quality-review.json';rule=C/'execution-stop-rule.json';assert not quality.exists() and not rule.exists()
baseline=next(r for r in read(base/'practical-verbatim-r1/review.json')['results'] if r['meeting']=='S_R004S03C01')['rawCerAfter']
value={'declaredAt':now(),'state':'DECLARED_BEFORE_FIRST_COMPLETE_NEW_MEETING_SCORE','ordinaryMeeting':'S_R004S03C01','baselineStrictCer':baseline,'futilityRule':'If full ordinary raw CER is not lower than the existing6.95495% baseline, reject this pipeline as a default improvement and stop further complex inference. Do not hide the failed ordinary score or mark unrun complex/identity/facts/holdout qualified.','neuralProtocolChanged':False,'originallyPlannedMeetings':['S_R004S03C01','L_R003S01C02'],'fullNewQualityScoreAvailableAtDeclaration':False,'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
rule.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
state={'state':'FOLLOWING_EXISTING_FULL_NATIVE_RUN','startedAt':now(),'parentControllerPid':read(full/'run.json')['pid'],'futilityStopRequested':False,'newInferenceLaunchedByFollower':False}
target=C/'followthrough.json'
def save():target.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
save()
while True:
    run=read(full/'run.json')
    if quality.exists():
        score=read(quality)['chronologicalTextDiagnostic']['cer'];state['ordinaryStrictCer']=score
        if score>=baseline and not state['futilityStopRequested']:
            stop=full/'stop.request'
            assert not stop.exists()
            stop.write_text('Predeclared ordinary full-meeting no-improvement stop '+now()+'\n',encoding='utf8')
            state.update(futilityStopRequested=True,stopReason='Full ordinary CER not better than retained baseline',stopRequestedAt=now());save()
    if run.get('finishedAt'):
        state.update(state='EXISTING_CONTROLLER_TERMINAL_REVIEW_REQUIRED',controllerState=run['state'],finishedAt=now());save();break
    try:
        p=psutil.Process(state['parentControllerPid']);assert any(Path(arg).name=='run_practical_qwen_full_20261107.py' for arg in p.cmdline()),'Saved controller identity changed'
    except psutil.NoSuchProcess:
        state.update(state='CONTROLLER_NOT_LIVE_NO_FALSE_COMPLETION',finishedAt=now());save();break
    time.sleep(1.)
print(json.dumps(state),flush=True)
