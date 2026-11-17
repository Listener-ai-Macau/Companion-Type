"""Freeze one ten-minute fixed default VAD test with the corrected CPU BLAS binding."""
from pathlib import Path
from datetime import datetime,timedelta
import copy,json,shutil,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from meeting_acoustic_contract_20261116 import read,sha
from durable_model_state_20261117 import atomic_json
from model_thermal_guard_20261117 import ThermalGuard,CpuThermalLimit
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
old=J/'context-activity-r1/silero-presence-day-r2/protocol.json';P=copy.deepcopy(read(old))
C=J/'context-activity-r1/silero-fixed-thread-day-r3';C.mkdir()
monitor=E/'system-restart-20261116-2315/daytime-vad-thread-fixed-thermal-r8'
assert (monitor/'started.json').exists() and not(monitor/'completed.json').exists()
prior_log_sources={r['file'] for r in P['thermal']['loggerSources']}
for name in ['monitor_thermal_20261117.py','read_laptop_thermal_stream_20261117.ps1']:
    shutil.copyfile(Path('work')/name,monitor/name)
P['thermal']['run']=str(monitor)
P['thermal']['loggerSources']=[{'file':str(monitor/name),'sha256':sha(monitor/name)}
    for name in ['monitor_thermal_20261117.py','read_laptop_thermal_stream_20261117.ps1']]
P['cpuBlas']=read(J/'english-transducer-r1/protocol.json')['blas']
files=[Path(r['file']) for r in P['files'] if r['file'] not in prior_log_sources]
files += [Path(P['cpuBlas']['file']),S/'companion_community1_adapter_20261115.py']
files += [Path(r['file']) for r in P['thermal']['loggerSources']]
P['files']=[{'file':str(p),'sha256':sha(p)} for p in dict.fromkeys(files)]
at=datetime.now().astimezone()
P.update(state='FROZEN_ONE_DEFAULT_CPU_VAD_TEST_EXPLICIT_SINGLE_BLAS_THREAD',at=at.isoformat(),
    stopAt=(at+timedelta(minutes=10)).isoformat(),previousClosedProtocol=str(old),previousClosedProtocolSha256=sha(old),
    decisionBasis='One primary speech detector and unchanged default parameters/fusion. Existing real CPU profile omitted the explicitROCmCPU_BLAS thread export; now bind exactDLL1thread. Fresh observation follows lower-than85C reading. Original60sRAM admission/85Cload/95Cstop remain. At most10min; preserve failure and do not restart/grid.',
    originalOvernightGpuWindowExtended=False,newWeightTraining=False)
for field in ['upstreamDefaults','weights','meetings','admissionGate','privateMemoryBytes','minimumAvailableBytes','cpuPercent','threads']:
    assert P[field]==read(old)[field]
atomic_json(C/'protocol.json',P)
score=read(old.with_name('scoring-control.json'));score['predictionProtocol']=str(C/'protocol.json')
score['files'][0]={'file':str(C/'protocol.json'),'sha256':sha(C/'protocol.json')};atomic_json(C/'scoring-control.json',score)
try:observation=ThermalGuard(P['thermal']).check(starting=True);ready=True
except CpuThermalLimit as error:observation=error.observation;ready=False
report={'at':at.isoformat(),'state':'FIXED_THREAD_CPU_VAD_PREPARED_ORIGINAL_LOAD_GATE_CHECKED',
    'protocol':str(C/'protocol.json'),'protocolSha256':sha(C/'protocol.json'),
    'scoringControl':str(C/'scoring-control.json'),'run':str(E/'context-activity-r1/silero-fixed-thread-day-r3/run-default'),
    'readyForOriginal60SecondWorkerAdmission':ready,'currentCpuObservation':observation,
    'cpuBlas':P['cpuBlas'],'fixedDetectorWeightsThresholdsAndAssociationUnchanged':True,
    'timeboxMinutes':10,'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'preparation.json',report);print(json.dumps(report,ensure_ascii=False))
