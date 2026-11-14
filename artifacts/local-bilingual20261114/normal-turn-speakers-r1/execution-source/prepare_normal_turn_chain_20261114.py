from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
BASE = ROOT / 'docs/handoffs/20261107-model-generation-recovery'
OLD = BASE / 'practical-alignment-r1'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/normal-turn-r6-alignment-r1'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


old_worker = SRC / 'practical_alignment_worker_20261107.py'
assert sha(old_worker) == '30ee26053270ebf229c74cd391e2f712b94e00571b03751d456fa07ad4107978'
worker = SRC / 'practical_alignment_session_worker_20261114.py'
assert not worker.exists() and not CONTROL.exists()
old_text = old_worker.read_text(encoding='utf-8')
old_parser = "parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['pilot','full'],required=True);parser.add_argument('--resume',action='store_true');args=parser.parse_args()"
new_parser = old_parser.replace(";args=parser.parse_args()", ";parser.add_argument('--control',type=Path,required=True);args=parser.parse_args()")
old_control = "C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-alignment-r1')"
assert old_text.count(old_parser) == old_text.count(old_control) == 1
new_text = old_text.replace(old_parser, new_parser).replace(old_control, 'C=args.control.resolve()')
assert new_text.replace(new_parser, old_parser).replace('C=args.control.resolve()', old_control) == old_text
worker.write_text(new_text, encoding='utf-8')
CONTROL.mkdir(parents=True)
for name in ['model-source.json', 'preparation.json', 'tiny-loader-proof.json']:
    shutil.copy2(OLD / name, CONTROL / name)
    assert sha(OLD / name) == sha(CONTROL / name)

sys.path.insert(0, str(SRC))
from practical_qwen_bounded_decode_20261107 import accepted
asr = BASE / 'practical-qwen-author-boundaries-r6'
case = next(c for c in read(asr / 'audio-only.json') if c['meeting'] == 'S_R004S03C01')
assert not any('reference' in key.lower() for key in case)
source = asr / 'full/transcripts' / case['meeting']
terminal = read(source / 'completed-state.json')
assert terminal['state'] == 'COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
assert terminal['allAudioSamplesCoveredOnce'] and terminal['allAsrTextPreserved']
assert sha(source / 'model-output.json') == terminal['modelOutputSha256']
assert sha(case['audio']) == case['audioSha256']
leaves, texts = [], []
for index in range(terminal['totalWindows']):
    packet = read(source / 'windows' / ('%06d.raw.json' % index))
    raw = packet['raw']
    texts.append(raw['text'])
    for entry in raw['acceptedLeaves']:
        identity = '%06d-%s' % (index, entry['nodeKey'])
        node_file = source / 'nodes' / (identity + '.json')
        node = read(node_file)
        node_raw = node['raw']
        assert node['binding'] == terminal['binding'] and accepted(node_raw)
        canonical = json.dumps(node_raw, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        assert hashlib.sha256(canonical).hexdigest() == node['rawSha256']
        leaves.append({'id': identity, 'nodeFile': str(node_file), 'nodeSha256': sha(node_file),
                       'text': node_raw['text'], 'startSample': node_raw['startSample'], 'endSample': node_raw['endSample']})
document = read(source / 'model-output.json')
assert document['text'] == '\n'.join(texts) == '\n'.join(l['text'] for l in leaves)
assert leaves[0]['startSample'] == 0 and leaves[-1]['endSample'] == terminal['completedSample']
assert all(a['endSample'] == b['startSample'] for a, b in zip(leaves, leaves[1:]))
plan = [{**case, 'sourceDocument': str(source / 'model-output.json'),
         'sourceDocumentSha256': sha(source / 'model-output.json'), 'leaves': leaves}]
write(CONTROL / 'audio-text-only.json', plan)
protocol = read(OLD / 'protocol.json')
protocol.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),
                workerSourceSha256=sha(worker), inputPlanSha256=sha(CONTROL / 'audio-text-only.json'),
                inputSelection='Owner-prioritized existing full single-mic non-overlap meeting. Existing R6 author-boundary raw text only; no new ASR or speaker inference.',
                pilotRule='Reuse unchanged loader exact-logit proof; first actual changed R6 leaf must preserve all text and emit in-bound onset units.',
                fullRule='After actual first-leaf pilot, align this one full normal-turn meeting. Fixed existing onset60ms join; no reference input or policy search.')
assert all(sha(SRC / n) == digest for n, digest in protocol['helperSources'].items())
assert all(sha(n) == digest for n, digest in protocol['runtimeSources'].items())
write(CONTROL / 'protocol.json', protocol)
journal_dir = BASE / 'native8-f16-full-r1/results/S_R004S03C01'
policy = read(OLD / 'onset-attribution-policy.json')
record = policy['speakerJournals']['S_R004S03C01']
assert sha(record['file']) == record['sha256'] and sha(record['producerFile']) == record['producerSha256']
assert read(record['file'])['audioSha256'] == case['audioSha256']
write(CONTROL / 'join-policy.json', {
    'state': 'FIXED_BEFORE_NEW_ALIGNMENT_INFERENCE', 'uncertaintyMarginSeconds': .06,
    'method': 'Existing onset_attribution; finite onset in original leaf, stable single predicted anonymous speaker throughout onset +/-60ms. Otherwise unknown.',
    'speakerJournal': record, 'helperSourceSha256': sha(SRC / 'practical_transcript_20261107.py'),
    'speakerSourceSha256': sha(journal_dir / 'review.json'), 'newSpeakerInference': False,
    'oldR5IntegratedCpCer': 531/8325, 'oldR5ChronologicalCer': 480/8325,
    'r6ChronologicalCer': 461/8325, 'ordinarySpeakerDer': .03855615562340746,
    'differentInputReason': 'Previous alignment used older R5 text with fixed30s boundaries. R6 changed recognized text and audio boundaries; do not attach stale R5 times to it.',
    'trueWordTimeAccuracyMeasured': False, 'qualityQualified': False})
write(CONTROL / 'worker-port-proof.json', {
    'at': protocol['at'], 'oldWorker': str(old_worker), 'oldWorkerSha256': sha(old_worker),
    'newWorker': str(worker), 'newWorkerSha256': sha(worker),
    'change': 'Only explicit --control path and its argument parser; reverting those two textual replacements exactly reproduces prior source.',
    'modelMathOrLoadingChanged': False, 'existingLoaderProofReused': True,
    'actualChangedInputPilotStillRequired': True})
# Scoring inputs live outside the worker plan and are only read after exit.
write(CONTROL / 'scoring-only.json', [c for c in read(asr / 'full/scoring-only.json') if c['meeting'] == case['meeting']])
print(json.dumps({'state': protocol['state'], 'control': str(CONTROL), 'leaves': len(leaves),
                  'textCharacters': len(document['text']), 'newAsrCalls': 0, 'newSpeakerCalls': 0,
                  'workerSha256': sha(worker)}, ensure_ascii=False))
