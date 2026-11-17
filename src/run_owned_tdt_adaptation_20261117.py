"""One explicit TDT phase, truthful update counts and no automatic retry."""
from pathlib import Path
from datetime import datetime
import argparse,json,subprocess,sys,time
import psutil
from meeting_acoustic_contract_20261116 import read,require,sha
from meeting_acoustic_worker_20261116 import own_limits
from durable_model_state_20261117 import atomic_json,read_snapshot
from model_thermal_guard_20261117 import ThermalGuard

def bind_owned_worker(launcher,command,pid):
    """Bind a real worker behind Windows' venv redirector, within our own tree."""
    worker=psutil.Process(pid)
    require(worker.create_time()>=launcher.create_time()-.01,'Worker predates owned launcher')
    if pid!=launcher.pid:
        require(any(parent.pid==launcher.pid and abs(parent.create_time()-launcher.create_time())<.01
            for parent in worker.parents()),'Reported worker is outside owned launcher tree')
    actual=worker.cmdline()
    require(actual[1:]==command[1:],'Owned worker script/arguments differ')
    allowed={str(Path(command[0]).resolve()).casefold(),str(Path(sys._base_executable).resolve()).casefold()}
    require(str(Path(actual[0]).resolve()).casefold() in allowed,'Unexpected Python executable behind launcher')
    return {'pid':worker.pid,'createdAt':worker.create_time(),'command':actual,'launcherPid':launcher.pid}

def observed_updates(state):
    if not state:return {'parameterUpdatesThisProcess':None,'candidateOptimizerUpdates':None,
        'preflightParameterUpdates':None,'completedTrainingExamples':None,'countsUnknown':True}
    return {'parameterUpdatesThisProcess':state['parameterUpdates'],
        'candidateOptimizerUpdates':state['candidateOptimizerUpdates'],
        'preflightParameterUpdates':state.get('preflightParameterUpdates',state['parameterUpdates'] if state['phase']=='preflight' else 0),
        'completedTrainingExamples':state['completedTrainingExamples'],'countsUnknown':False,
        'observedWorkerState':state['state'],'observedAt':state['observedAt']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',type=Path,required=True)
    p.add_argument('--protocol',type=Path,required=True);p.add_argument('--phase',required=True)
    p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    limits=own_limits(25);P=read(a.protocol)
    require(a.phase in ('baseline','preflight','train','validate') or
        (a.phase.startswith('resume-') and a.phase[7:].isdigit()),'Unknown TDT phase')
    require(P.get('gpuExecutionEnabled') is True,'Frozen GPU preparation is not enabled')
    require(datetime.now().astimezone()<datetime.fromisoformat(P['stopAt']),'Frozen execution window expired')
    require(any(Path(x['file']).resolve()==a.worker.resolve() and x['sha256']==sha(a.worker) for x in P['files']),
        'Worker not frozen in protocol')
    thermal=ThermalGuard(P['thermal']);initial_temperature=thermal.check(starting=True)
    run=a.run.resolve();run.mkdir(parents=True,exist_ok=True)
    owner=run/('supervisor-'+a.phase);owner.mkdir(exist_ok=False)
    command=[P['runtime']['python'],str(a.worker.resolve()),'--protocol',str(a.protocol.resolve()),
        '--phase',a.phase,'--run',str(run)]
    last=None;selection=None;reason=None;read_error=None;thermal_stop=None;worker_identity=None
    with (owner/'stdout.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        owned=psutil.Process(proc.pid);created=owned.create_time();began=time.monotonic()
        atomic_json(owner/'started.json',{'pid':proc.pid,'createdAt':created,
            'at':datetime.now().astimezone().isoformat(),'command':command,
            'protocolSha256':sha(a.protocol),'workerSha256':sha(a.worker),'noAutomaticRetry':True,
            'initialCpuTemperature':initial_temperature})
        while proc.poll() is None:
            time.sleep(.5);path=run/a.phase/'state.json'
            try:
                current,selection=read_snapshot(path)
                require(current['phase']==a.phase,'Worker phase mismatch')
                if worker_identity is None:
                    worker_identity=bind_owned_worker(owned,command,current['pid'])
                    atomic_json(owner/'worker-identity.json',worker_identity)
                require(current['pid']==worker_identity['pid'],'Bound worker PID changed')
                current_worker=psutil.Process(worker_identity['pid'])
                require(abs(current_worker.create_time()-worker_identity['createdAt'])<.01,'Bound worker creation identity changed')
                last=current;read_error=None
            except (OSError,ValueError) as error:read_error=repr(error)
            except psutil.NoSuchProcess as error:read_error=repr(error)
            except RuntimeError as error:reason='Owned worker identity verification failed: '+repr(error);read_error=repr(error)
            if last:
                age=time.time()-datetime.fromisoformat(last['observedAt']).timestamp()
                if age>last.get('currentOperationBudgetSeconds',180)+3:reason='Owned worker exceeded its progress budget'
            elif time.monotonic()-began>180:reason='No valid startup state within180s'
            if datetime.now().astimezone()>=datetime.fromisoformat(P['stopAt']):reason='Frozen execution cutoff'
            try:thermal.check()
            except (OSError,KeyError,RuntimeError,ValueError) as error:
                reason='Owned thermal guard: '+repr(error);thermal_stop=getattr(error,'observation',None)
            if reason:
                require(abs(owned.create_time()-created)<.01 and owned.cmdline()==command,'Owned PID identity changed')
                for child in reversed(owned.children(recursive=True)):
                    try:child.kill()
                    except psutil.NoSuchProcess:pass
                try:owned.kill()
                except psutil.NoSuchProcess:pass
                break
        code=proc.wait(timeout=15)
    final=run/a.phase/'completed.json'
    if final.exists():
        current=read(final)
        require(worker_identity is not None and current['pid']==worker_identity['pid'] and current['phase']==a.phase,'Final worker identity differs')
        last=current
    else:
        try:last,selection=read_snapshot(run/a.phase/'state.json')
        except (OSError,ValueError) as error:read_error=repr(error)
    complete=code==0 and final.exists()
    result={'state':'OWNED_TDT_PHASE_COMPLETE' if complete else 'OWNED_TDT_PHASE_FAILED_NO_RETRY',
        'at':datetime.now().astimezone().isoformat(),'exitCode':code,'watchdogReason':reason,
        'pid':proc.pid,'createdAt':created,'workerIdentity':worker_identity,'phase':a.phase,'stateSelection':selection,'stateReadError':read_error,
        'triggeringCpuTemperature':thermal_stop,
        **observed_updates(last),'countsAreLastPersistedObservationNotUnloggedCrashInstant':True,
        'limits':limits.query(),'cannotGuaranteeGpuDriverRecovery':True,'noAutomaticRetry':True}
    atomic_json(owner/'completed.json',result);print(json.dumps(result));sys.exit(0 if complete else 1)

if __name__=='__main__':main()
