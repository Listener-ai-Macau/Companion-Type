"""Inspect frozen stage-A errors without changing inference or scoring.

Reference labels are used only in this offline diagnostic. Inspection classes,
edit locations and missed-turn counts are associations, not verified causes.
"""
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
sys.path.insert(0, str(SRC))
from score_sequential_meetings_20261115 import tokens, measure
from rapidfuzz.distance import Levenshtein
from moss_windows_resource_limits_20261104 import WorkerLimits

D = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J = D / 'joint-architecture-r1'
C = D / 'sequential-meeting-stageA-r2'
OUT = J / 'meeting-domain-data-r1/stagea-error-priorities20261116.json'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


HESITATIONS = {
    'English': {'uh', 'um', 'uhm', 'umm', 'erm', 'er', 'hmm', 'hm', 'ah'},
    'Chinese': {'嗯', '呃'},
}


def inspection_class(op, ref, hyp, atoms, language):
    left = ref[op.src_pos] if op.tag != 'insert' else ''
    right = hyp[op.dest_pos] if op.tag != 'delete' else ''
    if left in HESITATIONS[language] or right in HESITATIONS[language]:
        return 'hesitation_token_involved'
    if language == 'Chinese' and (left == '儿' or right == '儿'):
        return 'er_character_involved'
    if language == 'English' and op.tag != 'insert':
        if '_' in atoms[op.src_pos]['sourceText']:
            return 'reference_spelled_acronym'
        if len(left) == 1 and left.isalpha() and left not in {'a', 'i'}:
            return 'reference_isolated_letter'
    return 'other_lexical'


def inspect(case, baseline):
    language = case['language']
    ref = tokens(case['rawReferenceText'], language)
    hyp = tokens(baseline['hypothesis'], language)
    atoms, turns = [], []
    for event in case['referenceEvents']:
        assert event['end'] >= event['start']
        event_tokens = tokens(event['text'], language)
        if not event_tokens:
            continue
        if not turns or turns[-1]['speaker'] != event['speaker']:
            turns.append({'speaker': event['speaker'], 'start': event['start'],
                          'end': event['end'], 'indices': [], 'tokens': []})
        turn = turns[-1]
        turn['end'] = max(turn['end'], event['end'])
        for token in event_tokens:
            turn['indices'].append(len(atoms))
            turn['tokens'].append(token)
            atoms.append({'token': token, 'turn': len(turns)-1,
                          'speaker': event['speaker'], 'start': event['start'],
                          'end': event['end'], 'sourceText': event['text']})
    assert [a['token'] for a in atoms] == ref
    fresh = measure(case['rawReferenceText'], baseline['hypothesis'], language)
    for key in ['errors', 'referenceUnits', 'hypothesisUnits',
                'substitutions', 'deletions', 'insertions']:
        assert fresh[key] == baseline[key], (case['id'], key)
    ops = Levenshtein.editops(ref, hyp)
    counts = Counter(op.tag for op in ops)
    classes = Counter(inspection_class(op, ref, hyp, atoms, language) for op in ops)
    deleted = {op.src_pos for op in ops if op.tag == 'delete'}
    substituted = {op.src_pos for op in ops if op.tag == 'replace'}
    edge = {i for i in range(len(ref)) if i < 3 or i >= len(ref)-3}
    short = [t for t in turns if t['end']-t['start'] <= 2]
    short_indices = {i for t in short for i in t['indices']}
    missed = [t for t in short if t['indices'] and set(t['indices']) <= deleted]
    start = case['sourceStartFrame']/16000
    end = case['sourceEndFrame']/16000
    time_edge = set()
    if language == 'English':
        assert all(e.get('annotationElement') == 'w' for e in case['referenceEvents']
                   if tokens(e['text'], language))
        time_edge = {i for i,a in enumerate(atoms)
                     if a['start'] < start+1 or a['end'] > end-1}
    speaker_rows = []
    for speaker in sorted({a['speaker'] for a in atoms}):
        indices = {i for i,a in enumerate(atoms) if a['speaker'] == speaker}
        speaker_rows.append({'speaker': speaker, 'referenceUnits': len(indices),
                             'deletedReferenceUnits': len(indices & deleted),
                             'substitutedReferenceUnits': len(indices & substituted)})
    return {
        'id': case['id'], 'meeting': case['meeting'], 'language': language,
        'role': case['role'], 'referenceUnits': len(ref), 'errors': len(ops),
        'errorRate': len(ops)/len(ref), 'counts': dict(counts),
        'inspectionClasses': dict(classes), 'turns': len(turns),
        'shortTurns': len(short), 'shortTurnReferenceUnits': len(short_indices),
        'shortTurnDeletedReferenceUnits': len(short_indices & deleted),
        'fullyDeletedShortTurns': len(missed),
        'fullyDeletedShortTurnExamples': [
            {k: v for k,v in t.items() if k != 'indices'} for t in missed],
        'edgeThreeReferenceUnits': len(edge),
        'deletedEdgeThreeReferenceUnits': len(edge & deleted),
        'englishOneSecondEdgeReferenceUnits': len(time_edge),
        'deletedEnglishOneSecondEdgeReferenceUnits': len(time_edge & deleted),
        'referenceSpeakerDeletionInspection': speaker_rows,
        'largestDeletionRuns': deletion_runs(ref, hyp, ops),
    }


def deletion_runs(ref, hyp, ops):
    runs = []
    for op in ops:
        if op.tag != 'delete':
            continue
        if runs and op.src_pos == runs[-1]['lastReferenceIndex']+1:
            row = runs[-1]
        else:
            row = {'firstReferenceIndex': op.src_pos, 'tokens': []}
            runs.append(row)
        row['lastReferenceIndex'] = op.src_pos
        row['tokens'].append(ref[op.src_pos])
        row['hypothesisContext'] = hyp[max(0,op.dest_pos-3):op.dest_pos+4]
    return sorted(runs, key=lambda r: -len(r['tokens']))[:3]


def aggregate(rows, speaker_cases):
    def total(key):
        return sum(r[key] for r in rows)
    counts, classes = Counter(), Counter()
    for row in rows:
        counts.update(row['counts'])
        classes.update(row['inspectionClasses'])
    raw_der = {key: sum(speaker_cases[r['id']]['rawDER'][key] for r in rows)
               for key in ['referenceSpeakerSeconds', 'missSeconds',
                           'falseAlarmSeconds', 'confusionSeconds', 'errorSeconds']}
    raw_der['DER'] = raw_der['errorSeconds']/raw_der['referenceSpeakerSeconds']
    raw_der['missFractionOfDiarizationError'] = raw_der['missSeconds']/raw_der['errorSeconds']
    result = {
        'language': rows[0]['language'], 'role': rows[0]['role'],
        'cases': len(rows), 'referenceUnits': total('referenceUnits'),
        'errors': total('errors'), 'errorRate': total('errors')/total('referenceUnits'),
        'counts': dict(counts), 'inspectionClasses': dict(classes),
        'hesitationInvolvedFractionOfEdits': classes['hesitation_token_involved']/total('errors'),
        'rawDiarizationReusedUnchanged': raw_der,
    }
    for key in ['turns', 'shortTurns', 'shortTurnReferenceUnits',
                'shortTurnDeletedReferenceUnits', 'fullyDeletedShortTurns',
                'edgeThreeReferenceUnits', 'deletedEdgeThreeReferenceUnits',
                'englishOneSecondEdgeReferenceUnits',
                'deletedEnglishOneSecondEdgeReferenceUnits']:
        result[key] = total(key)
    return result


def main():
    limits = WorkerLimits(cpu_percent=5, memory_bytes=1024**3)
    binding = read(J/'stagea-cpu-composition-r2/scoring-binding.json')
    for name, key in [('audio-only.json', 'audioManifestSha256'),
                      ('scoring-only.json', 'scoringManifestSha256'),
                      ('raw-text-baseline.json', 'rawBaselineSha256'),
                      ('speaker-baseline.json', 'speakerBaselineSha256')]:
        assert sha(C/name) == binding[key]
    cases = read(C/'scoring-only.json')
    baseline = {r['id']: r for r in read(C/'raw-text-baseline.json')['cases']}
    speakers = {r['id']: r for r in read(C/'speaker-baseline.json')['cases']}
    assert len(cases) == len(baseline) == len(speakers) == 32
    assert all(not c['overlapPresentByReference'] for c in cases)
    assert not any('L_R003S03C02' in c['meeting'] for c in cases)
    rows = [inspect(c, baseline[c['id']]) for c in cases]
    by_group = defaultdict(list)
    for row in rows:
        by_group[(row['language'], row['role'])].append(row)
    groups = [aggregate(items, speakers) for items in by_group.values()]
    ordinary_file = J/'cpu-retained-baseline-join-r4/full-score.json'
    ordinary = read(ordinary_file)['meetings'][0]
    assert ordinary['rawText']['errors'] == 461
    contract_file = D/'asr-input-contract-audit-r1/conclusion.json'
    contract = read(contract_file)
    assert contract['actualOfficialExactBlocks'] == {'ES2003b': 71, 'EN2002a': 72}
    assert contract['productTextPreservation']['exactTextEqual']
    inputs = [C/n for n in ['audio-only.json', 'scoring-only.json',
                            'raw-text-baseline.json', 'speaker-baseline.json']]
    inputs += [ordinary_file, contract_file, SRC/'score_sequential_meetings_20261115.py']
    report = {
        'at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'state': 'FROZEN_STAGE_A_ERROR_INVENTORY_COMPLETE_NO_NEW_INFERENCE',
        'ownerTarget': {'targetErrorRate': .02, 'floorOriginalErrorRateStrictlyBelow': .05,
                        'chineseUnit': 'character', 'englishUnit': 'word',
                        'rawAndSpeakerAttributedTextReportedSeparately': True,
                        'originalEveryPersonDerAndFactsGatesRetained': True},
        'inputs': [{'file': str(p), 'sha256': sha(p)} for p in inputs],
        'diagnosticSourceSha256': sha(__file__),
        'previouslyVerifiedOutputContract': {
            'officialExactEnglishBlocks': contract['actualOfficialExactBlocks'],
            'productMergePreservedText': True, 'newDecoderReplayPerformed': False},
        'groups': groups,
        'ordinaryChineseWholeMeetingReused': {
            'meeting': ordinary['meeting'], 'rawText': ordinary['rawText'],
            'personText': ordinary['personTextFixedOriginalActivityIdentity'],
            'rawDER': ordinary['originalReferenceRawContinuousSpeakerDER'],
            'newFullMeetingInference': False},
        'cases': rows,
        'method': {
            'shortTurn': 'Consecutive reference events from one speaker in the selected clip, duration from first start to last end<=2 seconds; no inferred word times.',
            'fullyDeletedTurn': 'Every lexical reference unit of this turn is deleted in the unchanged raw-text Levenshtein alignment; diagnostic association, not verified acoustic cause.',
            'lexicalEdge': 'First/last3 reference units per clip, fixed before aggregation; not an acoustic boundary test.',
            'englishTimeEdge': 'Reference word annotations within first/last1 second of the selected clip; deletions only. No Chinese word-time interpolation.',
            'inspectionClasses': 'Mutually exclusive token-shape tags; no class is removed, corrected, or treated as harmless in acceptance.',
            'diarization': 'Sum already scored raw multi-voice zero-collar errors, not exclusive attribution view and not newly rescored predictions.',
        },
        'diagnosticRepair': 'First attempt stopped before writing output: the assertion incorrectly required empty AMI vocalsound/disfmarker events to be word events. Empty lexical events are now skipped when building lexical turns; all nonempty events still require actual word annotations. Frozen reference tokens and all S/D/I counts are asserted unchanged.',
        'limitations': [
            'Preselected exposed32 short clips; train diagnostics and validation stay separate. No blind or complete-meeting generalization.',
            'Alignment placement can be ambiguous for repeated words; edit categories and edge associations do not establish causes.',
            'No audio listening or new neural inference; no claim that reference spellings are acoustically adjudicated.',
            'Existing whole Chinese score is reused; this inventory does not improve any recognition score.',
        ],
        'newNeuralCalls': 0, 'newWeightUpdates': 0,
        'originalScoringOrOutputsChanged': False, 'finalHoldoutOpened': False,
        'qualityQualified': False, 'saleQualified': False, 'limits': limits.query(),
    }
    OUT.parent.mkdir(exist_ok=True)
    if OUT.exists():
        previous = read(OUT)
        assert previous['inputs'] == report['inputs']
        assert previous['diagnosticSourceSha256'] == report['diagnosticSourceSha256']
        assert previous['groups'] == report['groups']
        print(json.dumps({'reused': str(OUT), 'groups': previous['groups']}, ensure_ascii=False))
        return
    with OUT.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'file': str(OUT), 'groups': groups, 'newNeuralCalls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
