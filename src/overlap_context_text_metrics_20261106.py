"""Attribute whole-meeting cpCER edits without trimming ambiguous sentences.

An overlap-context utterance is a COMPLETE reference utterance intersecting
another speaker. Its full text is retained; this is not a pure overlap-word
CER or verified word alignment. Global anonymous assignment/edit alignment is
unchanged, and unmatched hypothesis streams remain counted separately.
"""
from bisect import bisect_right
from collections import Counter, defaultdict
from full_meeting_transcript_metrics_20261103 import group_transcripts, normalize, speaker_cer, Levenshtein


def reference_overlap_intervals(rows):
    events = defaultdict(list)
    for row in rows:
        if normalize(row['text']):
            events[row['start']].append((str(row['speaker']), 1))
            events[row['end']].append((str(row['speaker']), -1))
    active = Counter()
    points = sorted(events)
    intervals = []
    for index, start in enumerate(points[:-1]):
        for person, change in events[start]:
            active[person] += change
            if active[person] == 0:
                del active[person]
        end = points[index + 1]
        if len(active) >= 2 and end > start:
            if intervals and intervals[-1][1] == start:
                intervals[-1] = (intervals[-1][0], end)
            else:
                intervals.append((start, end))
    return intervals


def attributed_text_metrics(reference, hypothesis, audio_seconds, *, short_seconds=2.):
    # Same validation, normalization, chronological ordering and full-stream
    # anonymous assignment as the existing primary cpCER.
    ref_text = group_transcripts(reference, audio_seconds)
    hyp_text = group_transcripts(hypothesis, audio_seconds)
    primary = speaker_cer(reference, hypothesis, audio_seconds)
    intervals = reference_overlap_intervals(reference)
    ends = [end for _, end in intervals]
    flags = defaultdict(list)
    utterances = Counter()
    for row in sorted(reference, key=lambda r: (r['start'], r['end'])):
        text = normalize(row['text'])
        if not text:
            continue
        index = bisect_right(ends, row['start'])
        context = bool(index < len(intervals) and intervals[index][0] < row['end'])
        short = row['end'] - row['start'] <= short_seconds
        flag = (context, short)
        flags[str(row['speaker'])].extend([flag] * len(text))
        utterances['overlapContext' if context else 'singleSpeakerOnly'] += 1
        if short:
            utterances['short'] += 1
    groups = {
        'overlapContextUtterances': {'referenceCharacters': sum(context for rows in flags.values() for context, _ in rows), 'referenceUtterances': utterances['overlapContext'], 'edits': Counter()},
        'singleSpeakerOnlyUtterances': {'referenceCharacters': sum(not context for rows in flags.values() for context, _ in rows), 'referenceUtterances': utterances['singleSpeakerOnly'], 'edits': Counter()},
        'shortUtterances': {'referenceCharacters': sum(short for rows in flags.values() for _, short in rows), 'referenceUtterances': utterances['short'], 'edits': Counter()},
    }
    unassigned = Counter()
    people = []
    for pair in primary['anonymousAssignmentForEvaluationOnly']:
        name, predicted = pair['referenceSpeaker'], pair['hypothesisSpeaker']
        truth = ref_text.get(name, '')
        output = hyp_text.get(predicted, '')
        operations = Levenshtein.editops(truth, output)
        if name is None:
            for op in operations:
                assert op.tag == 'insert'
                unassigned[op.tag] += 1
            continue
        assert len(flags[name]) == len(truth)
        counts = Counter()
        for op in operations:
            # An insertion at a reference boundary is assigned to the next
            # reference character, or the last at end-of-stream. This fixed
            # convention is disclosed; it cannot establish true word timing.
            context, short = flags[name][min(op.src_pos, len(truth) - 1)]
            groups['overlapContextUtterances' if context else 'singleSpeakerOnlyUtterances']['edits'][op.tag] += 1
            if short:
                groups['shortUtterances']['edits'][op.tag] += 1
            counts[op.tag] += 1
        people.append({'referenceSpeaker': name, 'anonymousHypothesisSpeaker': predicted, 'referenceCharacters': len(truth), 'edits': dict(counts), 'totalEdits': sum(counts.values()), 'characterErrorRate': sum(counts.values()) / len(truth)})
    for group in groups.values():
        group['edits'] = dict(group['edits'])
        group['totalEdits'] = sum(group['edits'].values())
        group['characterErrorRate'] = group['totalEdits'] / group['referenceCharacters'] if group['referenceCharacters'] else None
    assigned = sum(groups[key]['totalEdits'] for key in ['overlapContextUtterances', 'singleSpeakerOnlyUtterances'])
    assert assigned + sum(unassigned.values()) == primary['totalEdits']
    assert sum(groups[key]['referenceCharacters'] for key in ['overlapContextUtterances', 'singleSpeakerOnlyUtterances']) == primary['referenceCharacters']
    return {
        'metric': 'FULL_MEETING_CPCER_EDIT_ATTRIBUTION_TO_COMPLETE_REFERENCE_UTTERANCES',
        'primaryCpCer': primary,
        **groups,
        'unassignedExtraStreamEdits': dict(unassigned),
        'unassignedExtraStreamTotalEdits': sum(unassigned.values()),
        'perReferenceSpeaker': people,
        'referenceOverlapSeconds': sum(end - start for start, end in intervals),
        'shortUtteranceMaximumSeconds': short_seconds,
        'allPrimaryEditsAccountedFor': True,
        'referenceUsedForScoringOnly': True,
        'pureOverlapWordsMeasured': False,
        'limitations': [
            'Overlap-context category retains full utterances, including their nonoverlapping parts; never label it pure overlap-word CER.',
            'Anonymous speaker assignment and edit operations come from the original complete cpCER streams; no reference-activity filtering of model words, oracle count, sentence clipping or local reassignment.',
            'Insertion at a reference boundary uses the following character, or final character at stream end. Levenshtein ties are deterministic library alignment, not proven word timing.',
            'Unmatched hypothesis streams remain explicit insertion errors; they are not silently allocated to an easier category or discarded.',
            'Short utterances overlap the other two categories and are not a third disjoint partition. No short reference yields null, not zero error.',
            'Reference speakers are anonymous evaluation labels, not confirmed real identities or meeting roles.'
        ]
    }
