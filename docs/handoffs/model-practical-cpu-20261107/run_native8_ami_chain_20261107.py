"""One already-declared cross-corpus full meeting; score exited output and protect it."""
from pathlib import Path
from datetime import datetime
import json,subprocess,sys,traceback
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';B=R/'docs/handoffs/20261107-model-generation-recovery';C=B/'native8-ami-r1'
sys.path.insert(0,str(M/'src'))
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));state={'state':'PREPARING_SINGLE_AMI_FROZEN_MODEL_VALIDATION','startedAt':datetime.now().astimezone().isoformat(timespec='seconds'),'automaticRetries':0,'asrAndProductQualification':False};target=C/'chain-state.json';assert not target.exists();atomic_json(target,state)
try:
    assert read(C/'input-preparation.json')['state']=='RESTORED_ONE_COMPLETE_AMI_VALIDATION_NO_INFERENCE'
    assert read(B/'native8-command-r1/cancel-resume-proof.json')['state']=='PASS_ACTUAL_NATIVE_CANCEL_DRAFT_RETAINED_RAW_ASR_REUSED_AND_VOICE_REPLAY'
    with (C/'speaker-controller.log').open('xb') as log:code=subprocess.run([sys.executable,str(M/'src/run_practical_nemotron_20261107.py'),'--control',str(C),'--score','--native-control-proof',str(B/'native8-f16-smoke-r1/native-control-proof.json')],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS).returncode
    run=read(C/'native-run.json');state.update(controllerExitCode=code,run=run,state='COMPLETE_ONE_AMI_DIARIZATION_REVIEW_REQUIRED' if code==0 and run['state']=='COMPLETE_NATIVE8_BATCH_REVIEW_REQUIRED' else 'INCOMPLETE_AMI_NO_AUTOMATIC_RETRY')
except BaseException as error:state.update(state='AMI_CHAIN_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc())
finally:
    state['finishedAt']=datetime.now().astimezone().isoformat(timespec='seconds');atomic_json(target,state)
    with (C/'preservation.log').open('xb') as log:state['preservationExitCode']=subprocess.run([sys.executable,str(Path(__file__).with_name('preserve_practical_progress_20261107.py')),'--phase','finished' if state['state']=='COMPLETE_ONE_AMI_DIARIZATION_REVIEW_REQUIRED' else 'failed'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.IDLE_PRIORITY_CLASS).returncode
    atomic_json(target,state);print(json.dumps({'state':state['state'],'preservationExitCode':state['preservationExitCode']}),flush=True)
