"""Sample-conserving research route plan from predicted speaker activity.

Never substitutes target audio into ordinary audio or calls uncertain silence.
Candidate extraction retains the raw source; promotion requires content checks.
"""
from collections import Counter, defaultdict
import math

def plan_routes(segments, *, source_frames, sample_rate):
    if not isinstance(source_frames, int) or source_frames <= 0:
        raise ValueError('positive complete source frame count required')
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError('positive sample rate required')
    events = defaultdict(Counter)
    events[0]; events[source_frames]
    for row in segments:
        start, end, person = row['start'], row['end'], row['speaker']
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)):
            raise ValueError('finite activity bounds required')
        if start < 0 or end <= start or end > source_frames / sample_rate + 1e-6:
            raise ValueError('activity outside original audio or empty')
        if isinstance(person, bool) or not isinstance(person, (str, int)) or str(person) == '':
            raise ValueError('explicit anonymous person required')
        first, last = round(start * sample_rate), round(end * sample_rate)
        if first == last:
            continue  # Subsample activity has no represented source frame.
        key = str(person)
        events[first][key] += 1
        events[last][key] -= 1
    active = Counter()
    rows = []
    edges = sorted(events)
    for first, last in zip(edges, edges[1:]):
        active.update(events[first])
        assert all(value >= 0 for value in active.values())
        people = sorted(person for person, value in active.items() if value > 0)
        route = 'raw_asr_unattributed' if not people else 'raw_asr' if len(people) == 1 else 'candidate_target_extraction'
        if rows and rows[-1]['route'] == route and rows[-1]['predictedPeople'] == people:
            rows[-1]['endSample'] = last
        else:
            rows.append({'startSample': first, 'endSample': last, 'route': route,
                         'predictedPeople': people, 'retainRawSource': True,
                         'candidateCanReplaceRawByDefault': False})
    active.update(events[source_frames])
    assert all(value == 0 for value in active.values())
    assert rows[0]['startSample'] == 0 and rows[-1]['endSample'] == source_frames
    assert all(a['endSample'] == b['startSample'] for a, b in zip(rows, rows[1:]))
    assert sum(row['endSample'] - row['startSample'] for row in rows) == source_frames
    return rows
