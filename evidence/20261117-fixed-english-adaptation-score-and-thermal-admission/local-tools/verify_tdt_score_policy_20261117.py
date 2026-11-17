"""Original-gate boundary examples; hypothetical counts, not ASR quality."""
from pathlib import Path
from datetime import datetime
import json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from score_tdt_adaptation_20261117 import summarize_pair
from meeting_acoustic_contract_20261116 import read,sha
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
gate=read(J/'language-specific-adaptation-r1/prepared-r1/scoring-control.json')['admissionGate']
def rows(first,second):return [
    {'meeting':'hypothetical-source-A','referenceWords':290,'baselineErrors':52,'candidateErrors':first,'priorMossErrors':51},
    {'meeting':'hypothetical-source-B','referenceWords':419,'baselineErrors':71,'candidateErrors':second,'priorMossErrors':73}]
assert summarize_pair(rows(41,57),gate)['advanceToCompleteSources']
assert not summarize_pair(rows(42,57),gate)['advanceToCompleteSources']
assert not summarize_pair(rows(53,45),gate)['advanceToCompleteSources']
assert not summarize_pair(rows(52,71),gate)['advanceToCompleteSources']
assert summarize_pair(rows(15,20),gate)['englishFivePercentFloorPassedOnThisExposedSubset']
assert not summarize_pair(rows(16,20),gate)['englishFivePercentFloorPassedOnThisExposedSubset']
assert summarize_pair(rows(6,8),gate)['englishTwoPercentTargetPassedOnThisExposedSubset']
assert not summarize_pair(rows(7,8),gate)['englishTwoPercentTargetPassedOnThisExposedSubset']
assert 'torch' not in sys.modules
out=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/score-policy-proof-r1')
out.mkdir(parents=True,exist_ok=False)
report={'state':'PASS_HYPOTHETICAL_PAIRED_GATE_BOUNDARIES_NOT_MODEL_ACCURACY',
    'at':datetime.now().astimezone().isoformat(),'proofs':['20percent paired improvement uses exact integer boundary98of123',
    '99of123 rejected although original fixed99 gate alone would pass',
    'one source regression rejected despite aggregate98','unchanged123 rejected',
    '35of709 passes strict5percent;36 fails','14of709 passes2percent;15 fails'],
    'sourceSha256':sha(S/'score_tdt_adaptation_20261117.py'),'actualModelOutputsScored':False,
    'torchImported':False,'newNeuralCalls':0,'parameterUpdates':0,'qualityQualified':False,'limits':limits.query()}
atomic_json(out/'result.json',report);print(json.dumps(report))
