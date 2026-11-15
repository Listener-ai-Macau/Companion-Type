"""Score completed frozen native tasks after inference; never load a model.

Headset identities are known file assignments, not predicted diarization.
Full far-field chronological CER is a distinct diagnostic from source CER.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import ast
import hashlib
import json
import re
import sys
import unicodedata

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting'
TASKS = Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/fixed-native-r2-runs')
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals, PARSER_ID
from rapidfuzz.distance import Levenshtein

read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))

def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    assert not output.exists(), 'Preserve previous scores; choose a new receipt'
    limits = WorkerLimits(cpu_percent=5, memory_bytes=192*1024**2)
    normalizer = ROOT / 'model-research/src/full_meeting_transcript_metrics_20261103.py'
    assert sha(normalizer) == '45859723659b91b7ae0750331dc86eba216c631d27d35ebc4979a3663eae971e'
    module = ast.parse(normalizer.read_text(encoding='utf-8'))
    scope = {'re': re, 'unicodedata': unicodedata}
    exec(compile(ast.Module(body=[n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'normalize'], type_ignores=[]), 'frozen-normalizer', 'exec'), scope)
    normalize = scope['normalize']
    inputs = read(CONTROL / 'fixed-asr-audio-only.json')
    references = read(CONTROL / 'fixed-asr-scoring-only.json')
    own = {}
    all_rows = []
    for source in references['sourceReferences']:
        assert sha(source['reference']) == source['referenceSha256']
        rows = [r for r in read_reference_intervals(source['reference']) if normalize(r['text'])]
        assert rows and len({r['speaker'] for r in rows}) == 1
        own[source['id']] = rows
        all_rows.extend(rows)
    assert len(all_rows) == 604
    runtime_pack = TASKS.parent / 'fixed-native-runtime-r2/model-pack.json'
    pack = read(runtime_pack)
    protocol = read(Path(pack['sourceControl']) / 'native-protocol.json')
    assert protocol['modelId'] == 'Qwen/Qwen3-ASR-1.7B-hf'
    product = read(CONTROL / 'product-five-source-ci/score.json')
    product_by_id = {r['id']: r for r in product['results']}
    results = []
    pending = []
    examples = {}
    for case in inputs:
        task_path = TASKS / case['id'] / 'task.json'
        task = read(task_path) if task_path.exists() else {}
        if task.get('state') != 'COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED':
            pending.append(case['id'])
            continue
        assert task['binding'] == {'audioSha256': case['audioSha256'], 'audioSeconds': case['audioSeconds'], 'modelPackSha256': sha(runtime_pack)}
        assert sha(case['audio']) == case['audioSha256']
        assert sha(task['output']) == task['outputSha256']
        document = read(task['output'])
        assert document['isFinal'] is True
        terminal = read(Path(task['output']).parent / 'completed-state.json')
        assert terminal['allAudioSamplesCoveredOnce'] and terminal['allAsrTextPreserved']
        assert terminal['modelOutputSha256'] == task['outputSha256']
        rows = own.get(case['id'], all_rows)
        assert max(r['end'] for r in rows) <= case['audioSeconds']
        reference = normalize(''.join(r['text'] for r in sorted(rows, key=lambda r: (r['start'], r['end']))))
        hypothesis = normalize(document['text'])
        edits = Levenshtein.editops(reference, hypothesis)
        counts = {kind: sum(op.tag == kind for op in edits) for kind in ['replace', 'delete', 'insert']}
        baseline = product_by_id[case['id']]
        assert baseline['audioSha256'] == case['audioSha256'] and baseline['referenceCharacters'] == len(reference)
        results.append({'id': case['id'], 'metric': 'known-headset-source-CER' if case['id'] in own else 'raw-mixed-chronological-CER',
                        'referenceCharacters': len(reference), 'hypothesisCharacters': len(hypothesis), 'edits': counts,
                        'totalEdits': len(edits), 'cer': len(edits)/len(reference), 'strictBelowFivePercent': len(edits)/len(reference) < .05,
                        'audioSha256': case['audioSha256'], 'outputSha256': task['outputSha256'], 'taskReceiptSha256': sha(task_path),
                        'accumulatedKnownOwnedProcessSeconds': task['accumulatedKnownOwnedProcessSeconds'],
                        'attemptsWithUnknownDuration': task['attemptsWithUnknownDuration'],
                        'includesRetainedFailedAttemptTime': len(task['attempts']) > 1,
                        'modelLoadedSeconds': terminal.get('modelLoadSeconds'),
                        'sameInputProductParaformer': {'cer': baseline['cer'], 'edits': baseline['edits']},
                        'knownSourceIdentityNotAutomaticDiarization': case['id'] in own})
        examples[case['id']] = [{'op': op.tag, 'referenceIndex': op.src_pos, 'hypothesisIndex': op.dest_pos,
                                 'referenceContext': reference[max(0, op.src_pos-12):op.src_pos+13],
                                 'hypothesisContext': hypothesis[max(0, op.dest_pos-12):op.dest_pos+13]} for op in list(edits)[:40]]
    assert args.allow_partial or not pending, 'Some fixed inputs are incomplete; no complete aggregate score'
    assert results, 'No complete output exists; do not score drafts'
    near = [r for r in results if r['id'] in own]
    complete = not pending
    aggregate = None
    if len(near) == 4:
        aggregate = {'metric': 'known-headset-source-aggregate-CER-not-diarization',
                     'referenceCharacters': sum(r['referenceCharacters'] for r in near),
                     'edits': {k: sum(r['edits'][k] for r in near) for k in ['replace', 'delete', 'insert']},
                     'totalEdits': sum(r['totalEdits'] for r in near)}
        aggregate['cer'] = aggregate['totalEdits']/aggregate['referenceCharacters']
    record = {'at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
              'state': 'COMPLETE_FIXED_NATIVE_PAIRED_DIAGNOSTIC' if complete else 'PARTIAL_COMPLETED_TASKS_ONLY_NOT_BATCH_SCORE',
              'modelId': protocol['modelId'], 'modelRevision': protocol['revision'], 'runtimePackSha256': sha(runtime_pack),
              'audioManifestSha256': sha(CONTROL / 'fixed-asr-audio-only.json'),
              'referenceManifestSha256': sha(CONTROL / 'fixed-asr-scoring-only.json'),
              'referenceParser': PARSER_ID, 'normalizerSourceSha256': sha(normalizer),
              'meeting': 'R8001_M8004', 'commonSecondsPerInput': 1551.82, 'sourceUtterances': 604,
              'results': results, 'pending': pending, 'nearAggregate': aggregate, 'editExamples': examples,
              'neuralInferencePerformedByScorer': False, 'referencesUsedOnlyAfterCompletedInference': True,
              'pureOverlapWordCerMeasured': False, 'wordTimingMeasured': False,
              'limitations': ['Headsets include real crosstalk; inserted other-speaker words are not automatically hallucinations.',
                              'Far chronological CER has overlap ordering ambiguity and cannot be directly compared with source-associated aggregate CER.',
                              'This exposed Eval diagnostic is shorter than the30minute qualification minimum and is not automatic diarization or a final holdout.',
                              'Dynamic background inference timing is not controlled end-to-end product latency.'],
              'qualityQualified': False, 'saleQualified': False, 'limits': limits.query()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: record[k] for k in ['state', 'results', 'pending', 'nearAggregate']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
