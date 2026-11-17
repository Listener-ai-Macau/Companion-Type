"""Exercise hot/stale/wrong-sensor policy using metadata; no model execution."""
from pathlib import Path
from datetime import datetime,timedelta
import copy,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from model_thermal_guard_20261117 import evaluate_temperature,ThermalGuard
from meeting_acoustic_contract_20261116 import read,sha
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
P=read(J/'language-specific-adaptation-r1/prepared-r1/protocol.json');policy=P['thermal']
out=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/thermal-policy-proof-r1')
out.mkdir(parents=True,exist_ok=False);now=datetime.now().astimezone()
snapshot={'latest':{'At':now.isoformat(),'CpuSensors':[{'Identifier':policy['sensorIdentifier'],
    'Hardware':'AMD Ryzen 7 7840HS','Celsius':85}]}}
assert evaluate_temperature(snapshot,policy,now=now,starting=True)['celsius']==85
checks=[]
def reject(label,value,*,starting=False):
    try:evaluate_temperature(value,policy,now=now,starting=starting)
    except (RuntimeError,ValueError,KeyError):checks.append(label);return
    raise AssertionError('Invalid thermal state accepted: '+label)
for value in [85.01,94.99]:
    item=copy.deepcopy(snapshot);item['latest']['CpuSensors'][0]['Celsius']=value
    assert evaluate_temperature(item,policy,now=now)['celsius']==value
    reject('warm-runtime-allowed-but-start-rejected-'+str(value),item,starting=True)
for value in [95,100,130,None,float('nan')]:
    item=copy.deepcopy(snapshot);item['latest']['CpuSensors'][0]['Celsius']=value
    reject('stop-or-invalid-'+str(value),item)
for offset,label in [(-15.01,'stale'),(3,'future')]:
    item=copy.deepcopy(snapshot);item['latest']['At']=(now+timedelta(seconds=offset)).isoformat();reject(label,item)
item=copy.deepcopy(snapshot);item['latest']['CpuSensors'][0]['Identifier']='ACPI/TZ01';reject('unidentified-acpi-cannot-substitute-for-cpu',item)
item=copy.deepcopy(snapshot);item['latest']['CpuSensors']*=2;reject('duplicate-sensor',item)
live=ThermalGuard(policy).check()
assert 'torch' not in sys.modules
report={'state':'PASS_IDENTIFIED_CPU_THERMAL_POLICY_FAULT_CASES_AND_LIVE_LOGGER_BINDING',
    'at':datetime.now().astimezone().isoformat(),'rejectedMetadataFaults':checks,'liveReading':live,
    'sourceSha256':sha(S/'model_thermal_guard_20261117.py'),'newNeuralCalls':0,'parameterUpdates':0,
    'hardwareTemperatureChangedByTest':False,'physicalGpuAbortExecuted':False,'overheatCauseProven':False,
    'torchImported':False,'limits':limits.query()}
atomic_json(out/'result.json',report);print(json.dumps(report))
