"""Exited output diagnosis under the same full-meeting evaluation mapping."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import re
import sys

os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
sys.path.insert(0, str(SRC))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits = WorkerLimits(cpu_percent=5, memory_bytes=1024**3)
from reference_textgrid_20261104 import read_reference_intervals
from pyannote.core import Annotation, Segment, Timeline
from pyannote.metrics.identification import IdentificationErrorRate

read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
case, = read(CONTROL / 'scoring-only.json')
out = CONTROL / 'native8/results' / case['meeting']
target = out / 'failure-diagnosis.json'
assert not target.exists()
review = read(out / 'review.json')
assert hashlib.sha256(Path(case['reference']).read_bytes()).hexdigest() == case['referenceSha256']
assert read(CONTROL / 'native8/native-run.json')['state'] == 'COMPLETE_NATIVE8_BATCH_REVIEW_REQUIRED'
mapping = {v['matchedAnonymousGroup']: person for person, v in review['perReferenceSpeakerForEvaluationOnly'].items()}
reference = Annotation(uri=case['meeting'])
for i, row in enumerate(read_reference_intervals(case['reference'])):
    if re.sub(r'<[^>]*>', '', row['text']).strip():
        reference[Segment(row['start'], row['end']), row['speaker']+':'+str(i)] = row['speaker']
reference = reference.support().crop(Segment(0, case['audioSeconds']))
hypothesis = Annotation(uri=case['meeting'])
for i, line in enumerate((out / 'predicted.rttm').read_text(encoding='utf-8').splitlines()):
    fields = line.split()
    lo, duration = float(fields[3]), float(fields[4])
    hypothesis[Segment(lo, lo+duration), str(i)] = mapping.get(fields[7], 'UNMATCHED:'+fields[7])
hypothesis = hypothesis.support().crop(Segment(0, case['audioSeconds']))
metric = IdentificationErrorRate(collar=0., skip_overlap=False)
whole = metric(reference, hypothesis, uem=Timeline([Segment(0, case['audioSeconds'])]), detailed=True)
for key in ['correct', 'confusion', 'missed detection', 'false alarm', 'total']:
    assert abs(whole[key] - review['components'][key]) < 1e-4
blocks = []
start = 0.
while start < case['audioSeconds']:
    end = min(start+300, case['audioSeconds'])
    counts = metric(reference, hypothesis, uem=Timeline([Segment(start, end)]), detailed=True)
    blocks.append({'startSeconds': start, 'endSeconds': end, 'components': counts})
    start = end
for key in ['correct', 'confusion', 'missed detection', 'false alarm', 'total']:
    assert abs(sum(b['components'][key] for b in blocks)-whole[key]) < 1e-4

# Reference-solo intervals only, paired with every simultaneous hypothesis label.
# Matrix cells can sum beyond solo duration when the model emits multiple voices.
events = {0.: {'r': [], 'h': []}, case['audioSeconds']: {'r': [], 'h': []}}
for kind, annotation in [('r', reference), ('h', hypothesis)]:
    for person in annotation.labels():
        for span in annotation.label_timeline(person).support():
            events.setdefault(span.start, {'r': [], 'h': []})[kind].append((person, 1))
            events.setdefault(span.end, {'r': [], 'h': []})[kind].append((person, -1))
active = {'r': {}, 'h': {}}
matrix, solo = {}, {}
previous = 0.
for point, changes in sorted(events.items()):
    refs = [p for p, n in active['r'].items() if n]
    hyps = [p for p, n in active['h'].items() if n]
    if point > previous and len(refs) == 1:
        person = refs[0]
        duration = point-previous
        solo[person] = solo.get(person, 0)+duration
        cells = matrix.setdefault(person, {})
        for hyp in hyps or ['__no_predicted_speech__']:
            cells[hyp] = cells.get(hyp, 0)+duration
    for kind in ['r', 'h']:
        for person, delta in changes[kind]:
            active[kind][person] = active[kind].get(person, 0)+delta
    previous = point

result = {'at': datetime.now().astimezone().isoformat(timespec='seconds'),
          'state': 'COMPLETE_EXITED_JOURNAL_ROOT_DIAGNOSIS_NO_NEW_INFERENCE',
          'meeting': case['meeting'], 'fixedFullMeetingMappingForEvaluationOnly': mapping,
          'wholeComponentsReproduced': True, 'componentsByFiveMinuteBlocks': blocks,
          'referenceSoloSeconds': solo, 'referenceSoloHypothesisSeconds': matrix,
          'matrixCanDoubleCountSimultaneousHypothesisLabels': True,
          'shortSpanResult': review['shortReferenceSpans'],
          'newNeuralCalls': 0, 'thresholdOrMappingRetuned': False, 'truthReturnedToInference': False,
          'qualityQualified': False, 'limits': limits.query()}
target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'matrix': matrix, 'solo': solo, 'shortSpans': result['shortSpanResult']}, ensure_ascii=False))
