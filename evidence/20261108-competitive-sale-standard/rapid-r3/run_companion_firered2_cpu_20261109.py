"""Monitor only this task's model child; avoid nested CPU rate jobs."""
from pathlib import Path
import hashlib,json,os,sys,subprocess,time
import psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=Path(sys.argv[sys.argv.index('--control')+1]) if '--control' in sys.argv else R/'docs/handoffs/20261109-firered2-cpu-r1';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
phase=sys.argv[1];meeting=sys.argv[2] if len(sys.argv)>2 and not sys.argv[2].startswith('--') else None;assert phase in ['probe','full'];out=C/('probe' if phase=='probe' else 'full-'+meeting);assert not out.exists();pressure=SystemRamPressure();args=[sys.executable,str(M/'src/companion_firered2_cpu_worker_20261109.py'),'--control',str(C),'--phase',phase]
if meeting:args+=['--meeting',meeting]
child=None;root=None;start=time.perf_counter();state={'state':'RUNNING','phase':phase,'meeting':meeting,'privatePeakBytes':0};path=C/('probe-controller.json' if phase=='probe' else 'full-'+meeting+'-controller.json')
def save():path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
try:
 assert not pressure.low(),'ActualWindowsLOWRAM beforelaunch'
 with (C/('probe.log' if phase=='probe' else 'full-'+meeting+'.log')).open('xb') as log:
  child=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);root=psutil.Process(child.pid);state['activePid']=child.pid;save()
  while child.poll() is None:
   low=pressure.low()
   if low or time.perf_counter()-start>(180 if phase=='probe' else 1800):stop_owned_family(child,root);state['state']='STOPPED_LOW_MEMORY' if low else 'STOPPED_BOUNDED_TIME';break
   try:
    private=root.memory_info().private;state['privatePeakBytes']=max(state['privatePeakBytes'],private)
    if private>2*1024**3:stop_owned_family(child,root);state['state']='STOPPED_PRIVATE_MEMORY_BUDGET';break
   except psutil.Error:pass
   time.sleep(1)
 state['exitCode']=child.returncode;worker=json.loads((out/'state.json').read_text()) if (out/'state.json').exists() else {};state['workerState']=worker.get('state');state['newNeuralCalls']=worker.get('newNeuralCalls',0);state['state']='COMPLETE' if child.returncode==0 and worker.get('state')=='COMPLETE_FROZEN_FIRERED2_CPU_UNQUALIFIED' else 'FAILED' if state['state']=='RUNNING' else state['state']
finally:
 if child is not None and child.poll() is None:stop_owned_family(child,root)
 state.pop('activePid',None);state['wallSeconds']=time.perf_counter()-start;save();print(json.dumps(state,ensure_ascii=False),flush=True)
