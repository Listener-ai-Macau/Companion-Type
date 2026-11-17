"""Recover omitted training words without pre-merging whole speaker turns.

The existing training clips are immutable barriers. Only additional natural
nonoverlap speech is selected, using the existing2-30s /3s-gap /100ms-pad
policy. No model, scoring references, waveform processing or token edits.
"""
import math
from collections import Counter
from score_sequential_meetings_20261115 import tokens


def omitted_nonoverlap_windows(rows, retained, source_frames, sample_rate=16000):
    seconds = source_frames / sample_rate
    covered = {i for example in retained for event in example['events'] for i in event['sourceIndices']}
    barriers = [(r['startFrame'], r['endFrame']) for r in retained]
    items = []
    stats = Counter()
    for start, end in barriers:
        items.append({'start': start / sample_rate, 'end': end / sample_rate,
                      'events': [], 'blocked': {'retained_training_audio'}})
    for index, original in enumerate(rows):
        start, end = original['start'], original['end']
        assert 0 <= start <= end <= seconds + .1
        tagged = '<' in original['text'] and '>' in original['text']
        invalid = end > seconds or start == end
        if tagged or invalid:
            stats['taggedOrInvalidSourceEvents'] += 1
            if end > start and start < seconds:
                items.append({'start': start, 'end': min(end, seconds), 'events': [],
                              'blocked': {'unclear_or_invalid_annotation'}})
            continue
        if not tokens(original['text'], 'English'):
            stats['nonlexicalSourceEvents'] += 1
            continue
        if index in covered:
            stats['retainedOriginalWordEvents'] += 1
            continue
        event = dict(original, sourceIndices=[index])
        items.append({'start': start, 'end': end, 'events': [event], 'blocked': set()})
    # Detect overlap on the original word intervals before any turn grouping.
    # Earlier code merged entire same-person turns first, so a brief overlap
    # or a >30s turn could discard many otherwise usable nonoverlap words.
    clusters = []
    for item in sorted(items, key=lambda r: (r['start'], r['end'])):
        if clusters and item['start'] < clusters[-1]['end'] - 1e-9:
            cluster = clusters[-1]
            cluster['end'] = max(cluster['end'], item['end'])
            cluster['events'].extend(item['events']);cluster['blocked'].update(item['blocked'])
        else:
            clusters.append({'start': item['start'], 'end': item['end'],
                             'events': list(item['events']), 'blocked': set(item['blocked'])})
    result, group = [], []

    def floor_frame(time):
        return math.floor(round(time * sample_rate, 6))

    def ceil_frame(time):
        return math.ceil(round(time * sample_rate, 6))

    def flush():
        if not group:
            return
        start, end = group[0][1]['start'], group[-1][1]['end']
        events = [r for _, cluster in group for r in cluster['events']]
        if not 2 <= end - start <= 30:
            stats['wordsInGroupsOutsideExisting2To30sPolicy'] += len(events)
            group.clear();return
        first, last = group[0][0], group[-1][0]
        before = clusters[first-1]['end'] if first else 0.
        after = clusters[last+1]['start'] if last+1 < len(clusters) else seconds
        pad = min(.1, max(0., (30 - (end-start))/2))
        left, right = max(start-pad, (before+start)/2), min(end+pad, (end+after)/2, seconds)
        left_frame = max(0, floor_frame(left));right_frame = min(source_frames, ceil_frame(right))
        assert left_frame < right_frame
        if right_frame-left_frame > 30*sample_rate:
            stats['wordsInRoundedGroupsExceeding30s'] += len(events)
            group.clear();return
        assert not result or left_frame >= result[-1]['endFrame'], 'Supplement windows duplicate source frames'
        assert all(right_frame <= a or left_frame >= b for a, b in barriers), 'Supplement overlaps retained training PCM'
        assert len({r['speaker'] for _, c in group for r in c['events']}) >= 1
        assert all(len({r['speaker'] for r in c['events']}) == 1 for _, c in group)
        result.append({'startFrame': left_frame, 'endFrame': right_frame, 'events': events,
                       'text': ' '.join(r['text'] for r in events)})
        group.clear()

    for index, cluster in enumerate(clusters):
        people = {r['speaker'] for r in cluster['events']}
        if cluster['blocked'] or len(people) > 1 or cluster['end']-cluster['start'] > 30:
            flush()
            reason = ('barrier' if cluster['blocked'] else 'true_word_overlap'
                      if len(people) > 1 else 'single_annotation_interval_exceeds30s')
            stats['omittedWordEventsInside_' + reason] += len(cluster['events'])
            continue
        if not cluster['events']:
            continue
        if group and (cluster['end']-group[0][1]['start'] > 30
                      or cluster['start']-group[-1][1]['end'] > 3):
            flush()
        group.append((index, cluster))
    flush()
    selected = [i for r in result for e in r['events'] for i in e['sourceIndices']]
    assert len(selected) == len(set(selected)) and not set(selected) & covered
    stats.update(supplementExamples=len(result), supplementOriginalWordEvents=len(selected))
    return result, dict(stats)


def regression_examples():
    # A continuous36s speaker turn must be split at words, not discarded whole.
    rows = [{'start': i*1.8, 'end': i*1.8+1.7, 'speaker': 'A', 'text': 'word', 'index': i}
            for i in range(20)]
    windows, _ = omitted_nonoverlap_windows(rows, [], 38*16000)
    assert len(windows) == 2 and sum(len(w['events']) for w in windows) == 20
    # A short real interruption must not erase preceding/following speech.
    rows = [{'start': i*.5, 'end': i*.5+.4, 'speaker': 'A', 'text': 'word', 'index': i}
            for i in range(30)]
    rows.append({'start': 7.2, 'end': 7.3, 'speaker': 'B', 'text': 'yes', 'index': 30})
    rows.sort(key=lambda r: (r['start'], r['end'], r['speaker']))
    windows, _ = omitted_nonoverlap_windows(rows, [], 16*16000)
    selected = [e for w in windows for e in w['events']]
    assert len(selected) == 29 and all(not (e['start'] < 7.3 and e['end'] > 7.2) for e in selected)
    # Preserved training audio is a hard barrier, even when words touch it.
    retained = [{'startFrame': 0, 'endFrame': 5*16000,
                 'events': [{'sourceIndices': list(range(10))}]}]
    windows, _ = omitted_nonoverlap_windows(rows, retained, 16*16000)
    assert windows and all(w['startFrame'] >= 5*16000 for w in windows)
    return {'longTurnWordBoundarySplit': True, 'briefOverlapDoesNotEraseWholeTurn': True,
            'retainedTrainingFramesProtected': True, 'newNeuralCalls': 0}
