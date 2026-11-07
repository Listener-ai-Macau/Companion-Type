"""One requested complete comparison batch, one model at a time, then retain."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,subprocess,sys,traceback
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';sys.path.insert(0,str(M/'src'))
from practical_io_20261107 import atomic_json
p=argparse.ArgumentParser();p.add_argument('--control',required=True);a=p.parse_args();C=Path(a.control)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
target=C/'chain-state.json';assert not target.exists() and not (C/'run.json').exists()
state={'state':'STARTING','startedAt':now(),'pid':os.getpid(),'automaticRetries':0,'modelsConcurrent':1,'phoneOrBoardIo':False,'computerUse':False}
def save():atomic_json(target,state)
save()
try:
    for stage,module,receipt,expected in [('diarization','run_practical_cpu_20261107.py','run.json','TWO_COMPLETE_CPU_MEETINGS_SCORED_REVIEW_REQUIRED'),('transcript','run_practical_transcript_20261107.py','transcript-run.json','TWO_COMPLETE_CPU_TRANSCRIPTS_SCORED_REVIEW_REQUIRED')]:
        state.update(state='RUNNING_'+stage.upper());save()
        with (C/('chain-'+stage+'.log')).open('xb') as log:
            child=subprocess.Popen([sys.executable,str(M/'src'/module),'--control',str(C)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            state.update(activeControllerPid=child.pid);save();code=child.wait()
        outcome=read(C/receipt);state[stage]={'controllerExitCode':code,'result':outcome};state.pop('activeControllerPid',None);save()
        if code or outcome['state']!=expected:state['state']='INCOMPLETE_EVIDENCE_RETAINED_NO_AUTOMATIC_RETRY';save();break
    else:state['state']='TWO_WHOLE_MEETINGS_SCORED_QUALITY_REVIEW_REQUIRED';save()
except BaseException as error:
    state.update(state='CHAIN_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());save()
finally:
    # This final phase does not start/retry any model. Preserve the real outcome.
    state['modelPhasesFinishedAt']=now();save()
    with (C/'chain-preserve.log').open('xb') as log:
        code=subprocess.run([sys.executable,str(Path(__file__).with_name('preserve_practical_cpu_20261107.py')),'--control',str(C),'--phase','finished'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS).returncode
    state.update(finalizationState='REMOTE_PROTECTED' if code==0 else 'PRESERVATION_FAILED_RETAINED',preserveExitCode=code,finishedAt=now());save();print(json.dumps(state,ensure_ascii=False),flush=True)
