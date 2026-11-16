"""CPU candidate stage guards, scoped to the owned family and task deadline."""
from pathlib import Path
from datetime import datetime
import subprocess,time,psutil
from companion_local_pcm_session_20261114 import atomic_json
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family

def run_cpu_stage(root,state,name,command,*,timeout,deadline,env=None):
    deadline=datetime.fromisoformat(deadline)
    remaining=(deadline-datetime.now().astimezone()).total_seconds()
    if remaining<=0:raise TimeoutError('Task neural deadline reached before stage start')
    timeout=min(timeout,remaining)
    state.update(state='RUNNING_'+name.upper(),activeStage=name);atomic_json(root/'job.json',state)
    logs=root/'logs';logs.mkdir(exist_ok=True);log_path=logs/(name+'-'+str(time.time_ns())+'.log')
    child=owned=None;pressure=SystemRamPressure();tick=time.perf_counter();peak=0;self_process=psutil.Process()
    try:
        assert not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3),'Original memory start gate unmet'
        with log_path.open('xb') as log:
            child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            owned=psutil.Process(child.pid);state.update(activePid=child.pid,activePidCreatedAt=owned.create_time());atomic_json(root/'job.json',state)
            while child.poll() is None:
                if pressure.low() or (root/'stop.request').exists() or time.perf_counter()-tick>timeout:
                    stop_owned_family(child,owned);raise InterruptedError('CPU stage resource/owned/deadline guard; durable source retained')
                try:
                    private=self_process.memory_info().private+sum(p.memory_info().private for p in [owned]+owned.children(recursive=True))
                    peak=max(peak,private)
                    if private>2*1024**3:
                        stop_owned_family(child,owned);raise MemoryError('Original2GiB owned CPU stage family guard')
                except psutil.Error:pass
                time.sleep(.25)
        if child.returncode:raise RuntimeError('Local '+name+' stage did not complete; retained stage log: '+str(log_path))
    finally:
        if child is not None and child.poll() is None:stop_owned_family(child,owned)
        pressure.close();state.pop('activePid',None);state.pop('activePidCreatedAt',None)
        state.setdefault('attempts',[]).append({'stage':name,'exitCode':child.returncode if child else None,'seconds':time.perf_counter()-tick,
            'privatePeakBytes':peak,'log':str(log_path),'taskNeuralDeadline':deadline.isoformat(),'originalRamStartGateBytes':int(3.18*1024**3)})
        atomic_json(root/'job.json',state)
