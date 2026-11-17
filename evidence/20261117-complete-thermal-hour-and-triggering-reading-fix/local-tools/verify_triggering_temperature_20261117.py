"""Preserve actual triggering readings in exceptions; metadata-only regression."""
from pathlib import Path
from datetime import datetime
import json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=128*1024**2)
from model_thermal_guard_20261117 import evaluate_temperature,CpuThermalLimit
from meeting_acoustic_contract_20261116 import read,sha
from durable_model_state_20261117 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
policy=read(J/'language-specific-adaptation-r1/prepared-r2/protocol.json')['thermal'];now=datetime.now().astimezone()
observed=[]
for value,starting in [(95,False),(95.5,False),(85.01,True)]:
    snapshot={'latest':{'At':now.isoformat(),'CpuSensors':[{'Hardware':'AMD Ryzen 7 7840HS',
        'Identifier':policy['sensorIdentifier'],'Celsius':value}]}}
    try:evaluate_temperature(snapshot,policy,now=now,starting=starting)
    except CpuThermalLimit as error:
        assert error.observation['celsius']==value and error.observation['sampleAt']==now.isoformat()
        assert error.observation['celsius']!=92
        observed.append({'starting':starting,'triggeringValue':error.observation['celsius'],'error':str(error)})
    else:raise AssertionError('Expected task-temperature stop')
for name in ['model_thermal_guard_20261117.py','silero_presence_worker_20261117.py',
    'tdt_domain_adaptation_20261116.py','run_owned_tdt_adaptation_20261117.py']:
    compile((S/name).read_bytes(),str(S/name),'exec')
assert 'torch' not in sys.modules
out=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/trigger-temperature-proof-r1')
out.mkdir(parents=True,exist_ok=False)
report={'state':'PASS_TEMPERATURE_LIMIT_EXCEPTION_CARRIES_TRIGGERING_READING',
    'at':now.isoformat(),'cases':observed,'sourceSha256':sha(S/'model_thermal_guard_20261117.py'),
    'originalFailedVadStateModified':False,'taskThresholdsChanged':False,'hardwareTemperatureChanged':False,
    'newNeuralCalls':0,'parameterUpdates':0,'torchImported':False,'limits':limits.query()}
atomic_json(out/'result.json',report);print(json.dumps(report))
