"""Metadata-only regressions for old119/new457 update counts and final checkpoint binding."""
from pathlib import Path
from datetime import datetime
import json
import sys

R = Path('C:/Users/Billy/Desktop/Denzic/Companion');S = R / 'model-research/src'
sys.path.insert(0, str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from meeting_acoustic_contract_20261116 import read, sha
from durable_model_state_20261117 import atomic_json
from tdt_adaptation_contract_20261117 import (valid_resume_position, require_final_checkpoint,
    checkpoint_identity, training_scope, checkpoint_due)
from tdt_domain_adaptation_20261116 import inspect

limits = WorkerLimits(cpu_percent=5, memory_bytes=256*1024**2)
J = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
out = E / 'language-specific-adaptation-r1/expanded-epoch-contract-r3'
out.mkdir(exist_ok=False)
P = read(J / 'language-specific-adaptation-r1/prepared-r3/protocol.json');plan = inspect(P)
assert training_scope(P) == (1828, 457, 32, True)
assert plan['independentIntegrityPassed'] and plan['examples'] == 1828
for update in range(1, 458):
    assert valid_resume_position(update*4, update, examples=1828) == (update*4, update)
for completed in list(range(4, 475, 4)) + [475]:
    assert valid_resume_position(completed, (completed+3)//4) == (completed, (completed+3)//4)
rejections = []


def rejected(name, f):
    try:
        f()
    except (RuntimeError, ValueError, KeyError):
        rejections.append(name);return
    raise AssertionError('Invalid case accepted: ' + name)


for completed, updates in [(0,0), (1,1), (1827,457), (1828,456), (1832,458), (True,1), (475,119)]:
    rejected('expanded-resume-' + str(completed), lambda: valid_resume_position(completed, updates, examples=1828))
receipt = {'file': 'metadata-fixture.safetensors', 'sha256': 'fixed-payload',
    'receiptFile': 'metadata-fixture.json', 'receiptSha256': 'fixed-receipt',
    'completedExamples': 1828, 'optimizerUpdates': 457, 'orderSha256': 'fixed-order',
    'frozenDigest': 'fixed-factory', 'preflightOnly': False}
final = {'finalCheckpoint': checkpoint_identity(receipt)}
assert require_final_checkpoint(receipt, final, examples=1828) == final['finalCheckpoint']
rejected('old119-checkpoint-cannot-qualify-expanded457-epoch', lambda: require_final_checkpoint(
    {**receipt, 'completedExamples': 475, 'optimizerUpdates': 119}, final, examples=1828))
rejected('earlier-expanded-optimizer-boundary-not-final', lambda: require_final_checkpoint(
    {**receipt, 'completedExamples': 476, 'optimizerUpdates': 119}, final, examples=1828))
rejected('preflight-payload-never-final-candidate', lambda: require_final_checkpoint(
    {**receipt, 'preflightOnly': True}, final, examples=1828))
rejected('different-final-payload-binding', lambda: require_final_checkpoint(
    {**receipt, 'sha256': 'different'}, final, examples=1828))
rejected('protocol-data-count-mismatch', lambda: training_scope({**P,
    'training': {**P['training'], 'examples': 475}}))
schedule = [u for u in range(1, 458) if checkpoint_due(u, 457, every=32, first=True)]
assert schedule == [1] + list(range(32, 449, 32)) + [457]
assert P['checkpointStoragePlan']['checkpointUpdates'] == schedule and len(schedule) == 16
assert P['checkpointBudgetBytes'] == 32*1024**3
assert P['checkpointStoragePlan']['candidateCheckpointBytesUpperBound'] < P['checkpointBudgetBytes']
sources = ['english_nonoverlap_training_windows_20261117.py', 'tdt_adaptation_contract_20261117.py',
           'tdt_domain_adaptation_20261116.py', 'score_tdt_adaptation_20261117.py']
for name in sources:
    compile((S/name).read_bytes(), str(S/name), 'exec')
assert 'torch' not in sys.modules
report = {'state': 'PASS_EXPANDED1828_FIXED457_EPOCH_RECOVERY_COUNTS_FINAL_BINDING_AND_STORAGE_PLAN',
    'at': datetime.now().astimezone().isoformat(), 'old119ResumeBoundariesChecked': 119,
    'expanded457ResumeBoundariesChecked': 457, 'rejectedFaultCases': rejections,
    'checkpointUpdates': schedule, 'checkpointStorage': P['checkpointStoragePlan'],
    'originalAcceptanceGatesChanged': False, 'actualGpuPreflightPassed': False,
    'actualGpuTensorCheckpointRoundtripExecuted': False, 'cpuModelTraining': False,
    'torchImported': False, 'newNeuralCalls': 0, 'parameterUpdates': 0,
    'sourceSha256': {n: sha(S/n) for n in sources}, 'limits': limits.query()}
atomic_json(out / 'result.json', report)
print(json.dumps({k: report[k] for k in ['state', 'old119ResumeBoundariesChecked',
    'expanded457ResumeBoundariesChecked', 'checkpointUpdates']}))
