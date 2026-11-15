"""Independent source-waveform gate; never supplies labels to inference."""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, json
import numpy as np
from moss_windows_resource_limits_20261104 import WorkerLimits

read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def measure(estimate, target, mixture):
    estimate = np.asarray(estimate, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    assert estimate.shape == target.shape and target.shape[0] == 2
    assert np.isfinite(estimate).all() and np.isfinite(target).all()
    source_energy = (target * target).sum(axis=1)
    total = float(source_energy.sum()); assert total > 0
    direct = float(((estimate - target) ** 2).sum())
    flipped = float(((estimate[::-1] - target) ** 2).sum())
    swap = flipped < direct
    aligned = estimate[::-1] if swap else estimate
    error = min(direct, flipped)
    active = int((source_energy > 0).sum()); assert active in (1, 2)
    inactive = float((aligned[source_energy == 0] ** 2).sum()) if active == 1 else None
    return dict(errorEnergy=error, targetEnergy=total, errorRatio=error / total,
                softMaximumLossDb=float(10 * np.log10(error / total + .001)),
                swapped=swap, actualActiveSources=active,
                inactiveToMixtureEnergy=inactive / float((mixture.astype(np.float64) ** 2).sum()) if inactive is not None else None)

def aggregate(rows):
    inactive = [r['inactiveToMixtureEnergy'] for r in rows if r['inactiveToMixtureEnergy'] is not None]
    return dict(examples=len(rows), meanErrorRatio=float(np.mean([r['errorRatio'] for r in rows])),
                aggregatedErrorRatio=sum(r['errorEnergy'] for r in rows) / sum(r['targetEnergy'] for r in rows),
                meanSoftMaximumLossDb=float(np.mean([r['softMaximumLossDb'] for r in rows])),
                meanInactiveToMixtureEnergy=float(np.mean(inactive)) if inactive else None)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--control', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--phase', choices=['baseline', 'candidate'], required=True)
    a = p.parse_args()
    limits = WorkerLimits(cpu_percent=5, memory_bytes=2 * 1024 ** 3)
    # Analytic controls include a silent output, duplication, and permutation.
    x = np.linspace(-.2, .2, 4096)
    target = np.stack([x, np.zeros_like(x)])
    assert measure(target, target, x)['errorRatio'] == 0
    assert measure(target[::-1], target, x)['errorRatio'] == 0
    assert measure(np.zeros_like(target), target, x)['errorRatio'] == 1
    assert abs(measure(np.stack([x/2, x/2]), target, x)['errorRatio'] - .5) < 1e-12
    protocol = read(a.control / 'protocol.json')
    assert sha(a.control / 'validation-examples.json') == protocol['validationTargetsSha256']
    state = read(a.run / 'state.json')
    assert state['state'] == 'COMPLETE_FROZEN_SYNTHETIC_SOURCE_PREDICTIONS_SCORE_PENDING'
    assert state['validationReferenceRead'] is False
    assert state['protocolSha256'] == sha(a.control / 'protocol.json')
    predictions = {r['id']: r for r in state['results']}
    targets = read(a.control / 'validation-examples.json')
    assert set(predictions) == {r['id'] for r in targets} and len(targets) == 84
    rows = []
    for row in targets:
        pred = predictions[row['id']]
        assert sha(pred['file']) == pred['sha256'] and sha(row['file']) == row['sha256']
        source = np.load(row['file'], allow_pickle=False)
        estimate = np.load(pred['file'], allow_pickle=False)
        assert source.shape == (3, 32000) and estimate.shape == (2, 32000)
        assert np.array_equal(source[0], source[1:].sum(axis=0))
        rows.append(dict(id=row['id'], meeting=row['meeting'], unit=row['unit'],
                         inputKind=row['kind'], predictionSha256=pred['sha256'],
                         targetFileSha256=row['sha256'], **measure(estimate, source[1:], source[0])))
    groups = {'all': aggregate(rows)}
    for meeting in sorted({r['meeting'] for r in rows}):
        groups['meeting:' + meeting] = aggregate([r for r in rows if r['meeting'] == meeting])
    for count in (1, 2):
        groups['active:' + str(count)] = aggregate([r for r in rows if r['actualActiveSources'] == count])
    result = dict(state='COMPLETE_INDEPENDENT_SYNTHETIC_SOURCE_SCORE', phase=a.phase,
                  at=datetime.now().astimezone().isoformat(), protocolSha256=sha(a.control / 'protocol.json'),
                  scorerSha256=sha(__file__), run=str(a.run), groups=groups, rows=rows,
                  diagnosticOnly=True, naturalMeetingQualified=False, qualityQualified=False)
    output = a.control / (a.phase + '-source-score.json'); assert not output.exists()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if a.phase == 'candidate':
        baseline = read(a.control / 'baseline-source-score.json')
        assert baseline['protocolSha256'] == result['protocolSha256']
        assert baseline['scorerSha256'] == result['scorerSha256']
        before = baseline['groups']; assert set(before) == set(groups)
        checks = {'overallImproves': groups['all']['meanErrorRatio'] < before['all']['meanErrorRatio']}
        for key in groups:
            if key != 'all': checks['noRegression:' + key] = groups[key]['meanErrorRatio'] <= before[key]['meanErrorRatio']
        for key in ('active:1', 'active:2'):
            checks['beatsAllZero:' + key] = groups[key]['meanErrorRatio'] < 1
        checks['inactiveOutputDoesNotRegress'] = groups['active:1']['meanInactiveToMixtureEnergy'] <= before['active:1']['meanInactiveToMixtureEnergy']
        passed = all(checks.values())
        decision = dict(state='PASS_SOURCE_GATE_NATURAL_WORD_EVALUATION_REQUIRED' if passed else 'REJECT_FINAL_FIXED_SEPARATOR_SOURCE_ADAPTATION',
                        checks=checks, baseline=before, candidate=groups,
                        selectedCheckpoint='fixed final update80 only', scorerSha256=sha(__file__),
                        syntheticSourcesAreNotNaturalIsolatedOverlap=True,
                        noHyperparameterVariantsAuthorizedByThisGate=True,
                        qualityQualified=False, d2Complete=False, productDefaultChanged=False)
        (a.control / 'source-decision.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(decision, ensure_ascii=False))
    else: print(json.dumps(dict(state=result['state'], groups=groups), ensure_ascii=False))

if __name__ == '__main__': main()
