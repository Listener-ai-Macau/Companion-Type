"""Audit low-level feature differences on the original fixed waveform cohort."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json

import numpy as np

ROOT = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
OUT = ROOT / 'preprocessing-contract-20261118'
prepared = json.loads((OUT / 'feature-inputs-r2/completed.json').read_text(encoding='utf-8'))
assert prepared['state'] == 'COMPLETE_CPU_FRONTEND_INPUTS_NO_MODEL_INFERENCE'
rows = []
for case in prepared['cases']:
    arrays = {}
    for entry in case['features']:
        path = Path(entry['file'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        arrays[entry['mode']] = np.load(path, allow_pickle=False)[:entry['length']]
    old = arrays['installed_frontend']
    reference = arrays['published_hf_frontend']
    original = json.loads((ROOT / 'selected-cpu-segmentation-r1' / ('whole_case--' + case['id'] + '.json')).read_text(encoding='utf-8'))
    assert original['audioSha256'] == case['audioSha256'] and original['frames'] == case['frames']
    count = min(len(old), len(reference))
    rows.append({
        'id': case['id'], 'priorWholeCaseOutputEmpty': not original['text'].strip(),
        'validFeatureFrames': count, 'energyFractionBelowCurrentFloor': case['energyFractionBelowCurrentFloor'],
        'logGuardOnlyMeanAbsDifference': case['logGuardOnlyMeanAbsDifference'],
        'sameIndexFeatureMeanAbsDifference': float(np.abs(old[:count] - reference[:count]).mean()),
        'reconstructedOldFeatureAbsMaximum': float(np.abs(old).max()),
        'referenceFeatureAbsMaximum': float(np.abs(reference).max()),
    })
assert len(rows) == 12
result = {
    'at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
    'state': 'VERIFIED_NUMERICAL_FRONTEND_DIFFERENCE_CAUSAL_DECODING_COMPARISON_PENDING',
    'legacyFrontendReconstructedFromPinnedSource': True,
    'legacyFrontendBitEquivalentToLiveRuntimeProven': False,
    'independentInMemorySourceFeaturesMeasured': True,
    'legacyLibrary': 'kaldi-native-fbank v1.22.3, declared by sherpa-onnx v1.13.4',
    'originalResearchFrontend': 'Pinned NVIDIA Parakeet v3 processor, Transformers 5.22.1',
    'provedDifferences': ['Mel log floor uses log(max(E, float32_epsilon)) versus log(E + 2^-24).',
                          'Frame/window geometry and variance estimation also differ between the two paths.'],
    'cases': rows,
    'belowFloorRange': [min(r['energyFractionBelowCurrentFloor'] for r in rows), max(r['energyFractionBelowCurrentFloor'] for r in rows)],
    'priorEmptyWholeCaseOutputs': sum(r['priorWholeCaseOutputEmpty'] for r in rows),
    'newNeuralCalls': 0, 'trainingUpdates': 0, 'qualityQualified': False,
}
with (OUT / 'numerical-frontend-audit.json').open('x', encoding='utf-8') as output:
    json.dump(result, output, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))
