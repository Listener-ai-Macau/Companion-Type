"""Verify a lightweight CPU frontend against the saved official tensors."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import os
import sys
import wave

os.environ['OPENBLAS_NUM_THREADS'] = '1'
PROJECT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
sys.path.insert(0, str(PROJECT / 'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits

limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024**2)
import numpy as np
from reference_parakeet_cpu_frontend_20261118 import extract

OUT = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117/preprocessing-contract-20261118')
contract = json.loads((OUT / 'feature-inputs-r2/completed.json').read_text(encoding='utf-8'))
rows = []
for case in contract['cases']:
    path = Path(case['audio'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == case['audioSha256']
    with wave.open(str(path), 'rb') as f:
        assert (f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()) == (1, 2, 16000, case['frames'])
        actual, length = extract(f.readframes(f.getnframes()))
    baseline = next(x for x in case['features'] if x['mode'] == 'published_hf_frontend')
    original = Path(baseline['file'])
    assert hashlib.sha256(original.read_bytes()).hexdigest() == baseline['sha256']
    expected = np.load(original, allow_pickle=False)
    assert length == baseline['length'] and actual.shape == expected.shape and not actual[length:].any()
    error = np.abs(actual - expected)
    rows.append(dict(id=case['id'], validFrames=length, maxAbsFeatureError=float(error.max()), meanAbsFeatureError=float(error.mean())))

result = dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
              state='LIGHTWEIGHT_CPU_REFERENCE_FEATURE_PARITY_MEASURED', cases=rows,
              numpyVersion=np.__version__, modelWeightsLoaded=False, torchImported='torch' in sys.modules,
              inferenceCalls=0, trainingUpdates=0, limits=limits.query(),
              maxAbsFeatureError=max(r['maxAbsFeatureError'] for r in rows),
              meanOfMeanAbsFeatureErrors=sum(r['meanAbsFeatureError'] for r in rows) / len(rows))
assert len(rows) == 12 and not result['torchImported']
with (OUT / 'portable-frontend-parity-r1.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))
