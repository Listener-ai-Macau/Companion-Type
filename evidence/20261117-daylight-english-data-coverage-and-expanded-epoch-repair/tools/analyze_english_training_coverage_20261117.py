"""Compare retained TDT errors with training coverage using frozen text/word metadata only."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import re
import sys

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
S = R / 'model-research/src';sys.path.insert(0, str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from score_sequential_meetings_20261115 import tokens
from rapidfuzz.distance import Levenshtein

D = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
DATA = E / 'meeting-domain-data-r1'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def band(word, counts):
    n = counts[word]
    return 'not_in_training_text' if n == 0 else 'training_frequency1_to4' if n < 5 else 'training_frequency_at_least5'


def main():
    limits = WorkerLimits(cpu_percent=5, memory_bytes=256 * 1024 ** 2)
    plan_file = J / 'language-specific-adaptation-r1/english-data-plan.json'
    plan = read(plan_file)
    assert sha(plan['trainingManifest']) == plan['trainingManifestSha256']
    manifest = [json.loads(line) for line in Path(plan['trainingManifest']).read_text(encoding='utf-8').splitlines() if line]
    provenance_file = DATA / 'acoustic-nonoverlap-r2/example-provenance.json'
    assert sha(provenance_file) == plan['sourceProvenanceSha256']
    provenance = {r['id']: r for r in read(provenance_file) if r['language'] == 'English'}
    assert len(manifest) == len(provenance) == 475
    counts = Counter(w for row in manifest for w in tokens(row['text'], 'English'))
    for row in manifest:
        assert tokens(row['text'], 'English') == tokens(row['originalTrainingText'], 'English')
        assert row['id'] in provenance
    all_refs = read(D / 'sequential-meeting-stageA-r2/scoring-only.json')
    scored_file = J / 'english-transducer-r1/score.json'
    scored = read(scored_file)
    by_id = {r['id']: r for r in all_refs}
    frequency_totals, error_frequency, insertion_frequency = Counter(), Counter(), Counter()
    operation_counts = Counter();short = Counter();cases = []
    for score in scored['cases']:
        ref = by_id[score['id']]
        assert ref['language'] == 'English' and ref['role'] == 'validation'
        pred = read(E / 'english-transducer-r1/run-r1/results' / (score['id'] + '.json'))
        assert pred['referenceUsed'] is False and pred['wordsPostEdited'] is False
        ref_words = tokens(ref['rawReferenceText'], 'English');hyp = tokens(pred['text'], 'English')
        ops = Levenshtein.editops(ref_words, hyp)
        assert len(ops) == score['errors']
        operation_counts.update(op.tag for op in ops)
        frequency_totals.update(band(w, counts) for w in ref_words)
        errors = {op.src_pos for op in ops if op.tag != 'insert'}
        error_frequency.update(band(ref_words[i], counts) for i in errors)
        insertion_frequency.update(band(hyp[op.dest_pos], counts) for op in ops if op.tag == 'insert')
        atoms, turns = [], []
        for event in ref['referenceEvents']:
            words = tokens(event['text'], 'English')
            if not words:
                continue
            if not turns or turns[-1]['speaker'] != event['speaker']:
                turns.append({'speaker': event['speaker'], 'start': event['start'], 'end': event['end'], 'indices': []})
            turns[-1]['end'] = max(turns[-1]['end'], event['end'])
            for word in words:
                turns[-1]['indices'].append(len(atoms));atoms.append(word)
        assert atoms == ref_words
        deleted = {op.src_pos for op in ops if op.tag == 'delete'}
        short_turns = [t for t in turns if t['end'] - t['start'] <= 2]
        indices = {i for t in short_turns for i in t['indices']}
        short.update(turns=len(short_turns), words=len(indices), deletedWords=len(indices & deleted),
                     referenceSideErrors=len(indices & errors),
                     fullyDeletedTurns=sum(set(t['indices']) <= deleted for t in short_turns))
        cases.append({'id': score['id'], 'errors': len(ops), 'referenceWords': len(ref_words),
                      'referenceSideErrorsOnKnownFrequentTrainingWords': sum(counts[ref_words[i]] >= 5 for i in errors)})
    assert sum(operation_counts.values()) == 123 and sum(frequency_totals.values()) == 709

    meetings = []
    for meeting in plan['meetings']:
        original_file = DATA / 'acoustic-nonoverlap' / meeting / 'original-reference-events.json'
        raw = read(original_file)
        assert raw['modified'] is False and raw['trainingOnly'] is True
        rows = raw['events'];selected = set()
        audio_seconds = read(DATA / meeting / 'receipt.json')['audioSeconds']
        for row in provenance.values():
            if row['meeting'] == meeting:
                for event in row['events']:
                    selected.update(event['sourceIndices'])
        usable = []
        for i, event in enumerate(rows):
            if (tokens(event['text'], 'English') and not ('<' in event['text'] and '>' in event['text'])
                    and 0 <= event['start'] < event['end'] <= audio_seconds):
                usable.append((i, event))
        active = [];overlapped = set()
        for i, event in usable:
            active = [(j, e) for j, e in active if e['end'] > event['start'] + 1e-9]
            others = [j for j, e in active if e['speaker'] != event['speaker']]
            if others:
                overlapped.add(i);overlapped.update(others)
            active.append((i, event))
        nonoverlap = {i for i, _ in usable if i not in overlapped}
        # Reconstruct the old pre-merge for a causal data-selection diagnosis.
        merged = []
        for i, event in usable:
            if merged and event['speaker'] == merged[-1]['speaker'] and event['start'] - merged[-1]['end'] <= .5:
                merged[-1]['end'] = max(merged[-1]['end'], event['end']);merged[-1]['indices'].append(i)
            else:
                merged.append({'speaker': event['speaker'], 'start': event['start'],
                               'end': event['end'], 'indices': [i]})
        long_turn_indices = {i for turn in merged if turn['end'] - turn['start'] > 30 for i in turn['indices']}
        missing = nonoverlap - selected
        word_count = lambda indices: sum(len(tokens(rows[i]['text'], 'English')) for i in indices)
        duration = lambda indices: sum(rows[i]['end'] - rows[i]['start'] for i in indices)
        meetings.append({'meeting': meeting, 'originalReferenceEvents': len(rows),
            'usableLexicalEvents': len(usable), 'nonoverlapLexicalEvents': len(nonoverlap),
            'oldTrainingSelectedEvents': len(selected),
            'oldSelectedOverlappingEvents': len(selected & overlapped),
            'nonoverlapWords': word_count(nonoverlap), 'oldSelectedNonoverlapWords': word_count(selected & nonoverlap),
            'unselectedNonoverlapWords': word_count(missing),
            'unselectedNonoverlapAnnotatedWordSeconds': duration(missing),
            'oldPremergedTurnsLongerThan30s': sum(t['end'] - t['start'] > 30 for t in merged),
            'unselectedNonoverlapWordsInsideOldLongTurns': word_count(missing & long_turn_indices),
            'originalReferenceSha256': sha(original_file)})
    totals = {k: sum(r[k] for r in meetings) for k in meetings[0]
              if k not in ['meeting', 'originalReferenceSha256']}
    assert totals['oldSelectedOverlappingEvents'] == 0
    report = {'state': 'ENGLISH_TDT_ERRORS_AND_TRAINING_NONOVERLAP_COVERAGE_AUDITED_NO_MODEL_EXECUTION',
        'at': datetime.now().astimezone().isoformat(),
        'fixedOriginalScore': {'errors': 123, 'referenceWords': 709, 'operationCounts': dict(operation_counts)},
        'trainingLexicalWordCount': sum(counts.values()), 'trainingDistinctWordTypes': len(counts),
        'validationWordFrequencyInTraining': dict(frequency_totals),
        'referenceSideErrorFrequencyInTraining': dict(error_frequency),
        'insertionWordFrequencyInTraining': dict(insertion_frequency),
        'shortTurnDiagnosticSamePriorTwoSecondDefinition': dict(short),
        'trainingCoverageByMeeting': meetings, 'trainingCoverageTotals': totals, 'cases': cases,
        'scope': 'Frozen exposed12-clip TDT output diagnosis plus existing10 English training sources. Frequency is training-text coverage, not tokenizerOOV, acoustic learnability or a validation-derived training word list.',
        'method': 'Existing strict English scorer tokens and a singleLevenshtein alignment; no words, reference, metric or gate edits. Complete original training word metadata used to count nonoverlap words omitted by old selected clips. Old same-person0.5s pre-merge reconstructed for >30s exclusion diagnosis.',
        'inputs': {str(p): sha(p) for p in [plan_file, scored_file, provenance_file,
                                          D / 'sequential-meeting-stageA-r2/scoring-only.json']},
        'newNeuralCalls': 0, 'parameterUpdates': 0, 'audioDecoded': False,
        'trainingManifestOrValidationChanged': False, 'finalHoldoutOpened': False,
        'qualityQualified': False, 'saleQualified': False, 'limits': limits.query()}
    target = J / 'meeting-domain-data-r1/english-training-coverage-20261117.json'
    assert not target.exists()
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['state', 'trainingLexicalWordCount',
        'validationWordFrequencyInTraining', 'referenceSideErrorFrequencyInTraining',
        'shortTurnDiagnosticSamePriorTwoSecondDefinition', 'trainingCoverageTotals']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
