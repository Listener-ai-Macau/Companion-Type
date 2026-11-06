"""Supplement exited complete-meeting scoring; never open a live reference."""
import os
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse, hashlib, json, psutil
from moss_windows_resource_limits_20261104 import WorkerLimits

parser = argparse.ArgumentParser()
parser.add_argument('--control-root', required=True)
parser.add_argument('--meeting', required=True)
args = parser.parse_args()
limits = WorkerLimits(cpu_percent=5, memory_bytes=512 * 1024**2)
psutil.Process().cpu_affinity([10])
read = lambda p: json.loads(Path(p).read_text(encoding='utf8'))
control = Path(args.control_root)
run = read(control / 'full-L-owner-resume.json')
assert run['state'] == 'COMPLETE_GPU_INFERENCE_SCORING_REQUIRED' and not run.get('activePid')
result = next(r for r in run['results'] if r['meeting'] == args.meeting)
assert result['exitCode'] == 0
folder = Path(result['receipt']).parent
state = read(result['receipt'])
assert state['state'] == 'COMPLETE_JOINT_CANDIDATE_UNQUALIFIED' and state['eosCompleted'] and not state['invalidNativeTimeRows']
case = next(c for c in read(control / 'frozen-scoring-only.json') if c['meeting'] == args.meeting)
assert case['audioSha256'] == state['audioSha256'] and case['audioSeconds'] == state['audioSeconds']
assert hashlib.sha256((folder / 'model-output.json').read_bytes()).hexdigest() == state['modelOutputSha256']
assert hashlib.sha256(Path(case['reference']).read_bytes()).hexdigest() == case['referenceSha256']
from reference_textgrid_20261104 import read_reference_intervals, PARSER_ID
from overlap_context_text_metrics_20261106 import attributed_text_metrics
from full_meeting_transcript_metrics_20261103 import normalize
references = [row for row in read_reference_intervals(case['reference']) if normalize(row['text'])]
hypothesis = read(folder / 'raw-parsed-segments.json')
score = attributed_text_metrics(references, hypothesis, case['audioSeconds'])
if (folder / 'full-speaker-cer.json').exists():
    original = read(folder / 'full-speaker-cer.json')
    assert score['primaryCpCer'] == original, 'Supplement must preserve exact original primary cpCER'
score.update(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'), meeting=args.meeting, audioSeconds=case['audioSeconds'], audioSha256=case['audioSha256'], referenceSha256=case['referenceSha256'], referenceParser=PARSER_ID, resourceLimits=limits.query(), productQualified=False)
target = folder / 'overlap-context-text-review.json'
assert not target.exists(), 'Preserve previous scoring result'
target.write_text(json.dumps(score, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({key: value for key, value in score.items() if key not in ['primaryCpCer', 'perReferenceSpeaker']}, ensure_ascii=False), flush=True)
