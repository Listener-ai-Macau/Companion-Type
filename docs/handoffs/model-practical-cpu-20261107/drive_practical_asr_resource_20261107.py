"""Finish one concrete full-meeting trial with progress-checked RAM continuations.

No native/model-error retries. A continuation must add a durable raw window;
otherwise this driver stops. Existing strict model/CPU/RAM limits stay intact.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,psutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');src=R/'model-research/src';sys.path.insert(0,str(src))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import atomic_json,stop_owned_family
base=R/'docs/handoffs/20261107-model-generation-recovery';C=base/'practical-qwen-signal-r3';full=C/'full'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['ordinary','complex'],default='ordinary');args=parser.parse_args()
target=C/('resource-followthrough-complex.json' if args.stage=='complex' else 'resource-followthrough.json');assert not target.exists()
rule=read(C/'execution-stop-rule.json');baseline=rule['baselineStrictCer'];quality=full/'transcripts/S_R004S03C01/quality-review.json'
if args.stage=='complex':
    assert read(full/'transcripts/S_R004S03C01/completed-state.json')['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
    assert read(quality)['chronologicalTextDiagnostic']['cer']<baseline
    assert len(list((full/'transcripts/L_R003S01C02/windows').glob('*.raw.json')))>0,'Complex stage must already have real durable progress; no blind retry of failed loading'
state={'state':'FOLLOWING_ONE_FROZEN_NATIVE_TRIAL','startedAt':now(),'pid':__import__('os').getpid(),'modelFailureRetries':0,'lowMemoryContinuations':0,'futilityStopRequested':False,'limitsChanged':False,'sourceSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'events':[]}
pressure=SystemRamPressure();child=None;process=None;launched_floor=None;last_wait=None
def save():atomic_json(target,state)
def progress():
    return sum(len(list((out/'windows').glob('*.raw.json'))) for out in (full/'transcripts').iterdir() if out.is_dir())
save()
try:
    while True:
        run=read(full/'run.json')
        if quality.exists():
            score=read(quality)['chronologicalTextDiagnostic']['cer'];state['ordinaryStrictCer']=score
            if score>=baseline and not state['futilityStopRequested']:
                stop=full/'stop.request'
                if not stop.exists():stop.write_text('Predeclared ordinary no-improvement stop '+now()+'\n',encoding='utf8')
                state.update(futilityStopRequested=True,futilityStopAt=now());save()
        if not run.get('finishedAt'):
            parent=psutil.Process(run['pid']);assert any(Path(arg).name=='run_practical_qwen_full_20261107.py' for arg in parent.cmdline()),'Controller PID identity differs'
            state.update(state='FOLLOWING_RUNNING_NATIVE_TRIAL',durableWindows=progress());save();time.sleep(1);continue
        if child is not None and child.poll() is None:
            time.sleep(.2);continue
        if run['state']!='STOPPED_ACTUAL_WINDOWS_LOW_RAM' or state['futilityStopRequested']:
            state.update(state='CONCRETE_NATIVE_TRIAL_TERMINAL_REVIEW_REQUIRED',controllerState=run['state'],durableWindows=progress());break
        current=progress()
        if launched_floor is not None and current<=launched_floor:
            state.update(state='STOPPED_RAM_CONTINUATION_WITHOUT_DURABLE_PROGRESS',controllerState=run['state'],durableWindows=current);break
        last=json.loads((full/'resources.jsonl').read_text().splitlines()[-1]);peak=run['results'][-1]['sampledPrivatePeakBytes'];available=psutil.virtual_memory().available;low=pressure.low()
        eligible=not low and available>last['availableBytes']+peak
        if not eligible:
            state.update(state='WAITING_ACTUAL_SYSTEM_MEMORY_RECOVERY',durableWindows=current,resourceObservation={'availableBytes':available,'actualWindowsLowRam':low,'lastAvailableBytes':last['availableBytes'],'releasedOwnPrivatePeakUpperBound':peak});save();time.sleep(2);continue
        launched_floor=current
        count=state['lowMemoryContinuations']+1;prefix='complex-resource-continuation' if args.stage=='complex' else 'resource-continuation';log=full/(prefix+'-%02d.log'%count)
        command=[sys.executable,str(src/'run_practical_qwen_full_20261107.py'),'--parent',str(C),'--resume-after-low-ram']
        with log.open('xb') as stream:child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        process=psutil.Process(child.pid);state['lowMemoryContinuations']=count;state['events'].append({'at':now(),'state':'CONTINUE_AFTER_OBSERVED_RAM_RECOVERY','durableWindowsBefore':current,'availableBytes':available,'actualWindowsLowRam':False,'controllerPid':child.pid});save()
        # Wait for this new controller to publish its identity or refuse before
        # launch. Never repeatedly invoke a preflight under the same refusal.
        while child.poll() is None:
            active=read(full/'run.json')
            if active.get('pid')==child.pid:break
            time.sleep(.1)
        if child.poll() is not None and read(full/'run.json').get('pid')!=child.pid:
            state.update(state='DEFERRED_CONTROLLER_PREFLIGHT_WITHOUT_NEURAL_RETRY',controllerState=read(full/'run.json')['state']);break
        time.sleep(1)
finally:
    # Normal completion never leaves our launched controller running. On an
    # exception stop only this verified Popen family, not another chat/app.
    if child is not None and child.poll() is None:stop_owned_family(child,process)
    pressure.close();state.update(finishedAt=now());save();print(json.dumps(state),flush=True)
