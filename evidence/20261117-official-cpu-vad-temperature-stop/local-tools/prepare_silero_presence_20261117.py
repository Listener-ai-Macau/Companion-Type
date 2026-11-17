"""One default dedicated VAD comparison motivated by remaining speech misses."""
from pathlib import Path
from datetime import datetime
import ast,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
from meeting_acoustic_contract_20261116 import read,sha,require
from durable_model_state_20261117 import atomic_json
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
out=J/'context-activity-r1/silero-presence-r1';out.mkdir(exist_ok=False)
asset=Path('E:/CodexData/Companion/.model-cache/silero-vad-official20261117')
receipt=read(asset/'asset-receipt.json')
for item in receipt['files']:require(sha(item['file'])==item['sha256'],'Official VAD asset changed')
require('MIT License' in (asset/'LICENSE').read_text(encoding='utf-8'),'Published license missing')
tree=ast.parse((asset/'utils_vad.py').read_text(encoding='utf-8'))
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='get_speech_timestamps')
defaults=dict(zip([a.arg for a in function.args.args][-len(function.args.defaults):],
    [ast.unparse(n) for n in function.args.defaults]))
require(defaults['threshold']=='0.5' and defaults['min_speech_duration_ms']=='250'
    and defaults['min_silence_duration_ms']=='100' and defaults['speech_pad_ms']=='30','Upstream default recipe changed')
adapt=read(J/'language-specific-adaptation-r1/prepared-r1/protocol.json')
old=read(J/'context-activity-r1/quantized30-presence-r1/protocol.json')
paths=[S/n for n in ['silero_presence_worker_20261117.py','compose_vad_presence_20261117.py',
    'fixed_presence_identity_core_20261117.py','compose_presence_identity_20261116.py',
    'score_joint_whole_meetings_20261115.py','meeting_acoustic_contract_20261116.py',
    'meeting_acoustic_worker_20261116.py','companion_local_pcm_session_20261114.py',
    'moss_windows_resource_limits_20261104.py','durable_model_state_20261117.py','model_thermal_guard_20261117.py']]
paths += [Path(old['audioOnly']),Path(old['predictedBindings']),asset/'asset-receipt.json']
paths += [Path(item['file']) for item in receipt['files']]
protocol={'state':'FROZEN_ONE_DEFAULT_CPU_SILERO_PRESENCE_PLUS_RETAINED_IDENTITY',
    'at':datetime.now().astimezone().isoformat(),'cpuInferenceOnly':True,'cpuPercent':5,'threads':1,
    'privateMemoryBytes':2*1024**3,'minimumAvailableBytes':3414499000,
    'stopAt':'2026-11-17T09:24:00+08:00','thermal':adapt['thermal'],'neuralLock':adapt['neuralLock'],
    'python':adapt['runtime']['python'],'torch':adapt['runtime']['torch'],
    'weights':str(asset/'silero_vad.jit'),'upstreamUtils':str(asset/'utils_vad.py'),
    'upstreamRepository':receipt['repository'],'upstreamCommit':receipt['commit'],
    'audioOnly':old['audioOnly'],'predictedBindings':old['predictedBindings'],'meetings':['ES2003b','EN2002a'],
    'upstreamDefaults':defaults,'defaultParametersUnchanged':True,
    'temperaturePolicy':'RAM stable60s and CPU<=85C immediately before load; CPU5percent single-thread detector, stop at95C or stale sensor. No GPU or CPU/iGPU training.',
    'decisionBasis':'Cached Q8 presence lowers full DER on both English sources but leaves104.24s missing in single-speaker portions of EN2002a. A dedicated speech detector is the appropriate distinct component to test, with fixed original identity fusion and original full-source gates.',
    'admissionGate':'Each complete original English source must reduce DER by>=20percent, have valid times/no unknown identity. Original full10percent DER and all raw-word/fact gates remain. Reject if not passed; no threshold/padding/model grid.',
    'newWeightTraining':False,'qualityQualified':False,'saleQualified':False,
    'files':[{'file':str(p),'sha256':sha(p)} for p in paths]}
atomic_json(out/'protocol.json',protocol)
prior=read(J/'context-activity-r1/quantized30-presence-r1/scoring-control.json')
control={'predictionProtocol':str(out/'protocol.json'),'wholeReferences':prior['wholeReferences'],
    'files':[{'file':str(p),'sha256':sha(p)} for p in [out/'protocol.json',S/'score_context_activity_20261116.py',
        S/'score_joint_whole_meetings_20261115.py',Path(prior['wholeReferences'])]]}
atomic_json(out/'scoring-control.json',control)
for name in ['silero_presence_worker_20261117.py','compose_vad_presence_20261117.py']:
    compile((S/name).read_bytes(),str(S/name),'exec')
atomic_json(out/'preparation.json',{'state':'OFFICIAL_DEFAULT_VAD_READY_CPU_INFERENCE_NOT_TRAINING',
    'at':datetime.now().astimezone().isoformat(),'protocolSha256':sha(out/'protocol.json'),
    'officialAssets':receipt,'defaults':defaults,'torchImported':'torch' in sys.modules,
    'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'limits':limits.query()})
print(json.dumps({'protocol':str(out/'protocol.json'),'defaultThreshold':defaults['threshold'],'cpuPercent':5,'newNeuralCalls':0}))
