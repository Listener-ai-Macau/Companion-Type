"""Run the already selected default detector after the explicit owner policy change."""
from pathlib import Path
from datetime import datetime,timedelta
import copy,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from meeting_acoustic_contract_20261116 import read,sha,require
from durable_model_state_20261117 import atomic_json
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
old=J/'context-activity-r1/silero-fixed-thread-day-r3/protocol.json'
P=copy.deepcopy(read(old));C=J/'context-activity-r1/silero-owner-observe-r4';C.mkdir()
run=E/'context-activity-r1/silero-owner-observe-r4/run-default';require(not run.exists(),'Keep earlier attempt')
prior_sources={r['file'] for r in P['thermal']['loggerSources']}
P['thermal']=copy.deepcopy(read(J/'igpu-native8-r3/protocol.json')['thermal'])
paths=[Path(r['file']) for r in P['files'] if r['file'] not in prior_sources]
paths.extend(Path(r['file']) for r in P['thermal']['loggerSources'])
P['files']=[{'file':str(p),'sha256':sha(p)} for p in dict.fromkeys(paths)]
at=datetime.now().astimezone()
P.update(at=at.isoformat(),state='FROZEN_DEFAULT_SILERO_OWNER_CPU_TEMPERATURE_OBSERVATION_ONLY',
    stopAt=(at+timedelta(minutes=10)).isoformat(),previousClosedProtocol=str(old),previousClosedProtocolSha256=sha(old),
    temperaturePolicy='Owner removed taskCPU85/95 cutoffs. Read-only temperature telemetry; originalRAM60s/CPU5percent/1thread/2GiB/time limit retained.',
    decisionBasis='Existing default Silero candidate has no completed whole-source quality result; prior attempts stopped on task temperature policy. Owner explicitly removed that policy. Published weights/defaults, exact two full sources, fixed fusion and20percent-per-source admission unchanged; no training or parameter search.')
for key in ['weights','upstreamDefaults','meetings','admissionGate','cpuBlas','privateMemoryBytes','minimumAvailableBytes','cpuPercent','threads']:
    require(P[key]==read(old)[key],'Do not alter the fixed detector experiment')
atomic_json(C/'protocol.json',P)
score=read(old.with_name('scoring-control.json'));score['predictionProtocol']=str(C/'protocol.json')
for i,item in enumerate(score['files']):
    if item['file']==str(old):score['files'][i]={'file':str(C/'protocol.json'),'sha256':sha(C/'protocol.json')}
    else:require(sha(item['file'])==item['sha256'],'Original scoring reference/code changed')
atomic_json(C/'scoring-control.json',score)
report={'at':at.isoformat(),'control':str(C),'run':str(run),'protocolSha256':sha(C/'protocol.json'),
    'defaultParametersAndFrozenQualityGatesUnchanged':True,'cpuTemperatureMode':'observe-only',
    'cpuInferenceOnly':True,'cpuOrIntegratedGpuTraining':False,'timeboxMinutes':10}
atomic_json(C/'preparation.json',report);print(json.dumps(report,ensure_ascii=False))
