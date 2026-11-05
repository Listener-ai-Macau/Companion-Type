"""Exercise the real supervisor's RAM paths with sleeping test workers only."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,shutil,subprocess,sys,time
from moss_windows_resource_limits_20261104 import SystemRamPressure

root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
test=root/'system-ram-guard-control-r10';test.mkdir(exist_ok=False)
for name in ['run_night_moss_gpu_20261104.py','moss_windows_resource_limits_20261104.py']:
    shutil.copy2(Path(__file__).parent/name,test/name)
(test/'moss_night_gpu_worker_20261104.py').write_text('import time\ntime.sleep(60)\n',encoding='utf8')
(test/'inputs.json').write_text(json.dumps([{'meeting':'sleeping-ram-guard-check'}]),encoding='utf8')
(test/'protocol.json').write_text(json.dumps({'runtime':{'python':sys.executable,'affinity':[10,14]}}),encoding='utf8')
checks=[]
for mode,expected in [('before','DEFERRED_WINDOWS_LOW_SYSTEM_RAM_NO_WORKER_STARTED'),('during','STOPPED_DURING_WORKER_WINDOWS_LOW_SYSTEM_RAM')]:
    # Fake only the OS notification provider in this isolated test process.
    # Production has no bypass switch and reads the actual Windows event.
    code='''import runpy,sys
import moss_windows_resource_limits_20261104 as limits
class Signal:
 def __init__(self):self.calls=0
 def low(self):
  self.calls+=1
  return MODE=='before' or self.calls>=2
 def close(self):pass
limits.SystemRamPressure=Signal
sys.argv=['run_night_moss_gpu_20261104.py','--control-root',ROOT,'--inputs',ROOT+'/inputs.json','--protocol',ROOT+'/protocol.json','--run-name',MODE]
runpy.run_path('run_night_moss_gpu_20261104.py',run_name='__main__')
'''.replace('MODE',repr(mode)).replace('ROOT',repr(str(test).replace('\\','/')))
    begin=time.perf_counter()
    result=subprocess.run([sys.executable,'-c',code],cwd=test,capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
    state=json.loads((test/(mode+'.json')).read_text(encoding='utf8'))
    assert result.returncode==0 and state['state']==expected,(result.stderr,state)
    assert 'activePid' not in state
    if mode=='before':assert not state['results']
    checks.append({'mode':mode,'state':state['state'],'seconds':time.perf_counter()-begin,'modelImported':False})
sensor=SystemRamPressure()
try:actual=sensor.low()
finally:sensor.close()
report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 'state':'PASS_OS_RAM_NOTIFICATION_SUPERVISOR_CONTROL','checks':checks,'actualWindowsLowMemorySignal':actual,
 'realSystemExhaustionInduced':False,'gpuWorkLaunched':False,'otherApplicationsChanged':False}
target=root/'system-ram-notification-check-r10.json';assert not target.exists();target.write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report))
