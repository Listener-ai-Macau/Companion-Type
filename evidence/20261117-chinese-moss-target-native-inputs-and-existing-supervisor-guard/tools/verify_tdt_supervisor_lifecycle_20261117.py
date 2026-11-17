"""Real subprocess lifecycle faults only; no neural runtime or hardware calls."""
from pathlib import Path
from datetime import datetime,timedelta
import argparse,json,subprocess,sys,time
import psutil
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from meeting_acoustic_contract_20261116 import sha
from durable_model_state_20261117 import atomic_json

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--expect-orphan',action='store_true');a=p.parse_args()
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
a.output.mkdir(parents=True,exist_ok=False)
source=S/'run_owned_tdt_adaptation_20261117.py'
(a.output/'supervisor-at-test.py').write_bytes(source.read_bytes())
worker=a.output/'nonneural-worker.py'
worker.write_text('''from pathlib import Path
from datetime import datetime
import argparse,json,os,time
import psutil
p=argparse.ArgumentParser();p.add_argument('--protocol');p.add_argument('--phase');p.add_argument('--run');a=p.parse_args()
P=json.loads(Path(a.protocol).read_text());r=Path(a.run);out=r/a.phase;out.mkdir(parents=True,exist_ok=True)
s={'pid':os.getpid()+(1 if P['fixture']=='identity' else 0),'phase':a.phase,
 'state':'NONNEURAL_LIFECYCLE_FIXTURE','parameterUpdates':0,'candidateOptimizerUpdates':0,
 'completedTrainingExamples':0,'observedAt':datetime.now().astimezone().isoformat(),
 'currentOperationBudgetSeconds':180}
(out/'state.json').write_text(json.dumps(s))
(r/'fixture-child-identity.json').write_text(json.dumps({'pid':os.getpid(),'createdAt':psutil.Process().create_time(),'command':psutil.Process().cmdline()}))
if P['fixture']=='normal':
 time.sleep(.7);(out/'completed.json').write_text(json.dumps(s))
else:time.sleep(25)
''',encoding='utf-8')
wrapper=a.output/'supervisor-fixture-wrapper.py'
wrapper.write_text('''import sys,json
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
''',encoding='utf-8')
scenarios=['identity'] if a.expect_orphan else ['identity','write','thermal','normal']
results=[]
for scenario in scenarios:
    out=a.output/scenario;out.mkdir();run=out/'run'
    protocol=out/'protocol.json'
    atomic_json(protocol,{'gpuExecutionEnabled':True,'stopAt':(datetime.now().astimezone()+timedelta(minutes=1)).isoformat(),
        'files':[{'file':str(worker.resolve()),'sha256':sha(worker)}],
        'runtime':{'python':sys.executable},'thermal':{'fixtureOnly':True},'fixture':scenario})
    cmd=[sys.executable,str(wrapper),str(S),scenario,str(worker.resolve()),str(protocol.resolve()),str(run.resolve())]
    test=subprocess.run(cmd,capture_output=True,text=True,timeout=12,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'supervisor-output.log').write_text(test.stdout+test.stderr,encoding='utf-8')
    started=run/'supervisor-baseline/started.json';child_record=run/'fixture-spawn-identity.json'
    if started.exists():identity=json.loads(started.read_text())
    else:
        until=time.monotonic()+3
        while not child_record.exists() and time.monotonic()<until:time.sleep(.05)
        assert child_record.exists(),'Fixture child identity unavailable'
        identity=json.loads(child_record.read_text())
    alive=False
    try:
        owned=psutil.Process(identity['pid'])
        alive=abs(owned.create_time()-identity['createdAt'])<.01 and owned.is_running()
    except psutil.NoSuchProcess:pass
    cleaned_by_harness=False
    if alive:
        assert a.expect_orphan,'Fixed supervisor left the real fixture child alive'
        assert abs(owned.create_time()-identity['createdAt'])<.01 and owned.cmdline()==identity['command']
        owned.kill();owned.wait(timeout=5);cleaned_by_harness=True
    else:assert not a.expect_orphan,'Original defect was not reproduced'
    if scenario=='normal':assert test.returncode==0
    else:assert test.returncode!=0
    assert 'torch' not in sys.modules
    results.append({'scenario':scenario,'supervisorExitCode':test.returncode,
        'childPid':identity['pid'],'childCreatedAt':identity['createdAt'],
        'aliveAfterSupervisorExit':alive,'testHarnessStoppedOnlyItsVerifiedOrphan':cleaned_by_harness,
        'supervisorCleanupReceipt':str(run/'supervisor-baseline/exception-cleanup.json')
            if (run/'supervisor-baseline/exception-cleanup.json').exists() else None})
result={'state':'REPRODUCED_SUPERVISOR_IDENTITY_EXCEPTION_LEAVES_OWNED_CHILD_ALIVE' if a.expect_orphan
        else 'PASS_REAL_NONNEURAL_SUPERVISOR_EXCEPTION_THERMAL_AND_NORMAL_LIFECYCLES',
    'at':datetime.now().astimezone().isoformat(),'supervisorSha256':sha(source),'cases':results,
    'hardwareTemperatureGuardMockedForLifecycleOnly':True,'noRealGpuProtocolAdmitted':True,
    'neuralCalls':0,'parameterUpdates':0,'torchImported':False,'cpuOrIntegratedGpuTraining':False,
    'actualGpuCleanupCompatibilityProven':False,'limits':limits.query()}
atomic_json(a.output/'result.json',result);print(json.dumps(result))
