"""Score a terminal CPU frontend comparison on the existing 709-word screen."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse
import hashlib
import json
import sys

PROJECT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
sys.path.insert(0, str(PROJECT / 'model-research/src'))
from durable_model_state_20261117 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from score_sequential_meetings_20261115 import measure

parser = argparse.ArgumentParser()
parser.add_argument('run', type=Path)
parser.add_argument('protocol', type=Path)
args = parser.parse_args()
limits = WorkerLimits(cpu_percent=5, memory_bytes=256 * 1024**2)

def read(path):
    return Path(path).read_bytes()

protocol_bytes = read(args.protocol)
protocol = json.loads(protocol_bytes)
protocol_hash = hashlib.sha256(protocol_bytes).hexdigest()
terminal = json.loads(read(args.run / 'completed.json'))
ref_path = protocol.get('originalReferences')
if not ref_path:
    selected = args.protocol.parent.parent / 'selected-cpu-segmentation-protocol-r1.json'
    ref_path = json.loads(read(selected))['originalReferences']
references = {
    case['id']: case for case in json.loads(read(ref_path))
    if case['role'] == 'validation' and case['language'] == 'English'
}
case_ids = {case['id'] for case in protocol['cases']}
assert set(references) == case_ids and len(case_ids) == 12
bundles = defaultdict(dict)
manifest = [(item, protocol_hash) for item in terminal['completed']]
baseline = None
if 'baselineReceipt' in protocol:
    receipt = read(protocol['baselineReceipt'])
    assert hashlib.sha256(receipt).hexdigest() == protocol['baselineReceiptSha256']
    baseline = json.loads(receipt)
    manifest += [(item, protocol['baselineProtocolSha256']) for item in baseline['completed']]
for item, expected_protocol_hash in manifest:
    raw = read(item['file'])
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
    packet = json.loads(raw)
    reference = references[packet['id']]
    assert packet['protocolSha256'] == expected_protocol_hash
    assert packet['audioSha256'] == reference['wavSha256']
    assert packet['inputFrames'] == reference['frames']
    assert not packet['wordsPostEdited'] and not packet['referenceUsed']
    assert packet['id'] not in bundles[packet['mode']]
    bundles[packet['mode']][packet['id']] = {
        'id': packet['id'], 'meeting': reference['meeting'],
        'emptyOutput': not packet['text'].strip(),
        'seconds': packet['seconds'], 'audioSeconds': packet['inputFrames'] / 16000,
        'originalSherpaOutputMatches': packet['oldOutputMatch'],
        **measure(reference['rawReferenceText'], packet['text'], 'English'),
    }

def summarize(rows):
    words = sum(row['referenceUnits'] for row in rows)
    errors = sum(row['errors'] for row in rows)
    audio = sum(row['audioSeconds'] for row in rows)
    seconds = sum(row['seconds'] for row in rows)
    return {
        'cases': len(rows), 'referenceWords': words, 'errors': errors,
        'wer': errors / words, 'seconds': seconds, 'rtf': seconds / audio,
        'emptyOutputs': sum(row['emptyOutput'] for row in rows),
        **{name: sum(row[name] for row in rows) for name in ['deletions', 'substitutions', 'insertions']},
    }

summaries = {}
for mode, packets in bundles.items():
    if set(packets) != case_ids:
        continue
    rows = list(packets.values())
    summary = summarize(rows)
    assert summary['referenceWords'] == 709
    meetings = {row['meeting'] for row in rows}
    summary['meetings'] = {
        name: summarize([row for row in rows if row['meeting'] == name])
        for name in sorted(meetings)
    }
    summary['rows'] = rows
    summaries[mode] = summary

result = {
    'at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
    'state': 'SCORED_EXISTING_SCREEN_CPU_FRONTEND_CONTROL',
    'executionState': terminal['state'], 'protocolSha256': protocol_hash,
    'originalSherpaExactOutputMatches': (baseline or terminal).get('baselineExactOutputMatches'),
    'reconstructedOldFrontendInSameDirectOnnxExecutor': baseline is not None,
    'originalReferenceDenominatorUnchanged': True, 'summaryByMode': summaries,
    'privatePeakBytes': terminal['limits']['jobPeakPrivateCommitBytes'],
    'newNeuralCallsByScorer': 0, 'trainingUpdates': 0,
    'qualityQualified': False, 'saleQualified': False, 'installedClientBinaryTest': False,
}
output = args.run / 'score.json'
assert not output.exists()
atomic_json(output, result)
print(json.dumps({**result, 'summaryByMode': {
    key: {k: v for k, v in item.items() if k != 'rows'} for key, item in summaries.items()
}}, ensure_ascii=False))
