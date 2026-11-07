"""One owner-requested full continuation, then preserve its actual terminal result."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,subprocess,sys,traceback
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';H=R/'docs/handoffs/20261105-model-resume';C=R/'docs/handoffs/20261107-model-generation-recovery'
work=Path(__file__).resolve().parent;target=C/'disjoint-full-launch-and-preserve.json';assert not target.exists(),'One attempt; retain earlier result'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
proof=C/'generation-resume-control-staged-r3-result.json'
assert read(proof)['state']=='PASS_FRESH_AND_RESUMED_ALL173_IDS_IDENTICAL_EXECUTION_ONLY' and read(proof)['disjointStages']
report=H/'full-L-retired-acoustic-20261106-r24/generation-recovery-bound-20261107/adoption-result.json'
control=H/'full-L-disjoint-recovery-20261107-r25';assert not control.exists()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
state={'startedAt':now(),'state':'PREPARING','fullControl':str(control),'pid':os.getpid(),'automaticRetries':0,'phoneOrBoardIo':False,'computerUse':False}
def save():
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,target)
save()
try:
    cmd=[sys.executable,str(M/'src/resume_full_moss_and_score_20261106.py'),'--control-name',control.name,'--output-suffix=-20261107-r25','--prepared-inputs','E:/CodexData/Companion/.model-cache/moss-prepared-full-L-20261106-r21/packet/manifest.json','--prepared-inputs-sha256','dc2bd9195972c2cd8c6828838b6c12daf08d8d42afefd1173e432dbd2c5ab432','--retire-acoustic-after-encoding','--generation-recovery-report',str(report),'--generation-recovery-report-sha256',hashlib.sha256(report.read_bytes()).hexdigest(),'--generation-execution-proof',str(proof),'--disjoint-stages']
    with (C/'disjoint-full-wrapper.log').open('xb') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        state.update(state='RUNNING_ONE_COMPLETE_MEETING_CONTINUATION',wrapperPid=child.pid);save()
        state['wrapperExitCode']=child.wait()
    state.update(state='PRESERVING_ACTUAL_TERMINAL_RESULT',batch=read(control/'batch-state.json'));state.pop('wrapperPid',None);save()
    with (C/'disjoint-full-preserve.log').open('xb') as log:
        done=subprocess.run([sys.executable,str(work/'preserve_disjoint_stages_20261107.py'),'--phase','full','--full-control',str(control)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    state.update(state='TERMINAL_RESULT_REMOTE_PROTECTED' if done.returncode==0 else 'TERMINAL_PRESERVATION_FAILED_RETAINED',preserveExitCode=done.returncode)
except BaseException as error:
    state.update(state='LAUNCH_OR_PRESERVATION_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state['finishedAt']=now();save();print(json.dumps(state,ensure_ascii=False),flush=True)
