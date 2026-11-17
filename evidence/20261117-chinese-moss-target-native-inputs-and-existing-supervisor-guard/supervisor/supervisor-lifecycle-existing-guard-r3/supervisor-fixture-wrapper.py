import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import run_owned_tdt_adaptation_20261117 as m
fixture,worker,protocol,run=sys.argv[2:]
original_popen=m.subprocess.Popen
def record_spawn(*args,**kwargs):
 proc=original_popen(*args,**kwargs)
 child=m.psutil.Process(proc.pid)
 (Path(run)/'fixture-spawn-identity.json').write_text(json.dumps({'pid':proc.pid,'createdAt':child.create_time(),'command':child.cmdline()}))
 return proc
m.subprocess.Popen=record_spawn
class NonHardwareGuard:
 def __init__(self,*args):pass
 def check(self,starting=False):
  if fixture=='thermal' and not starting:raise RuntimeError('NONHARDWARE_FIXTURE_THERMAL_STOP')
  return {'fixture':True,'actualTemperatureRead':False}
m.ThermalGuard=NonHardwareGuard
if fixture=='write':
 original=m.atomic_json
 def fail_start(path,value,**kwargs):
  if Path(path).name=='started.json':raise OSError('NONNEURAL_FIXTURE_START_RECORD_FAILURE')
  return original(path,value,**kwargs)
 m.atomic_json=fail_start
sys.argv=[str(Path(m.__file__)),'--worker',worker,'--protocol',protocol,'--phase','baseline','--run',run]
m.main()
