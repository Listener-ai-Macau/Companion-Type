from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
CACHE = Path('E:/CodexData/Companion/.model-cache/ordinary-combination-study-20261114')
OLD = ROOT / 'docs/handoffs/20261107-model-generation-recovery/practical-alignment-r1'
sys.path.insert(0, str(SRC))
from practical_qwen_bounded_decode_20261107 import accepted
from moss_windows_resource_limits_20261104 import WorkerLimits
limits = WorkerLimits(cpu_percent=5, memory_bytes=512*1024**2)
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


alignment = CONTROL / 'alignment'
assert not alignment.exists()
qwen_task = CACHE / 'qwen/tasks/ordinary-qwen'
task = read(qwen_task / 'task.json')
assert task['state'] == 'COMPLETE_LOCAL_NATIVE_ASR_CANDIDATE_NOT_QUALITY_QUALIFIED'
assert read(CONTROL / 'paraformer/run.json')['state'] == 'COMPLETE_PARAFORMER_COMPARATOR'
assert sha(task['output']) == task['outputSha256']
base_case, = read(CONTROL / 'audio-only.json')
scoring_case, = read(CONTROL / 'scoring-only.json')
spans = read(CONTROL / 'audio-only-spans.json')
native = CONTROL / 'native8'
assert read(native / 'native-run.json')['state'] == 'COMPLETE_NATIVE8_BATCH_REVIEW_REQUIRED'
speaker_dir = native / 'results' / base_case['meeting']
producer = read(speaker_dir / 'completed-state.json')
assert producer['allOriginalAudioSamplesSubmitted'] and producer['oneContinuousSpeakerState']
assert producer['audioSha256'] == base_case['audioSha256']

alignment.mkdir()
for name in ['model-source.json', 'preparation.json', 'tiny-loader-proof.json']:
    shutil.copy2(OLD / name, alignment / name)
    assert sha(OLD / name) == sha(alignment / name)
plan, references = [], []
receipts = []
for arm in ['qwen', 'paraformer']:
    if arm == 'qwen':
        source = qwen_task / 'control/full/transcripts' / task['meeting']
        terminal = read(source / 'completed-state.json')
        assert terminal['state'] == 'COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
        assert terminal['allAudioSamplesCoveredOnce'] and terminal['allAsrTextPreserved']
        assert sha(source / 'model-output.json') == terminal['modelOutputSha256']
        assert terminal['totalWindows'] == len(spans)
        leaves = []
        for span in spans:
            index = span['index']
            root = read(source / 'windows' / ('%06d.raw.json' % index))['raw']
            assert root['startSample'] == span['startSample'] and root['endSample'] == span['endSample'], 'Both arms must use identical frozen root spans'
            for entry in root['acceptedLeaves']:
                identity = '%06d-%s' % (index, entry['nodeKey'])
                node_file = source / 'nodes' / (identity+'.json')
                node = read(node_file)
                raw = node['raw']
                assert node['binding'] == terminal['binding'] and accepted(raw)
                canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
                assert hashlib.sha256(canonical).hexdigest() == node['rawSha256']
                leaves.append({'id': identity, 'nodeFile': str(node_file), 'nodeSha256': sha(node_file),
                               'text': raw['text'], 'startSample': raw['startSample'], 'endSample': raw['endSample']})
    else:
        source = CONTROL / 'paraformer'
        terminal = read(source / 'worker-state.json')
        assert terminal['state'] == 'COMPLETE_PARAFORMER_MATCHED_SPANS_UNSCORED'
        assert terminal['allOriginalAudioSamplesCoveredOnce'] and terminal['allAsrTextPreserved']
        assert sha(source / 'model-output.json') == terminal['modelOutputSha256']
        leaves = []
        for span in spans:
            node_file = source / 'nodes' / ('%06d.json' % span['index'])
            packet = read(node_file)
            raw = packet['raw']
            canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            assert hashlib.sha256(canonical).hexdigest() == packet['rawSha256']
            assert packet['binding'] == terminal['binding']
            assert all(raw[key] == span[key] for key in span)
            leaves.append({'id': '%06d' % span['index'], 'nodeFile': str(node_file), 'nodeSha256': sha(node_file),
                           'text': raw['text'], 'startSample': raw['startSample'], 'endSample': raw['endSample']})
    document = read(source / 'model-output.json')
    assert document['text'] == '\n'.join(l['text'] for l in leaves)
    assert leaves[0]['startSample'] == 0 and leaves[-1]['endSample'] == round(base_case['audioSeconds']*16000)
    assert all(a['endSample'] == b['startSample'] for a, b in zip(leaves, leaves[1:]))
    name = arm+'-'+base_case['meeting']
    plan.append({**base_case, 'meeting': name, 'sourceDocument': str(source / 'model-output.json'),
                 'sourceDocumentSha256': sha(source / 'model-output.json'), 'leaves': leaves})
    references.append({**scoring_case, 'meeting': name})
    receipts.append({'arm': arm, 'originalDocumentSha256': sha(source / 'model-output.json'),
                     'acceptedLeaves': len(leaves), 'frozenRootSpans': len(spans),
                     'sameOriginalRootSpansAsOtherArm': True, 'allOriginalSamplesCoveredOnce': True,
                     'originalSourceTextPreserved': True})
write(alignment / 'audio-text-only.json', plan)
write(alignment / 'scoring-only.json', references)
protocol = read(OLD / 'protocol.json')
protocol.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),
                workerSourceSha256=sha(SRC / 'practical_alignment_session_worker_20261114.py'),
                inputPlanSha256=sha(alignment / 'audio-text-only.json'),
                inputSelection='Two complete frozen ASR arms on identical original audio and root spans. No reference text, person labels or true person count.',
                pilotRule='Reuse unchanged exact-logit loader control, then first actual new leaf must execute with preserved characters and valid onset units.',
                fullRule='Align both complete ASR arms unchanged, then apply the same frozen exclusive journal and onset60ms fusion. No threshold or model selection by output.')
assert all(sha(SRC / n) == v for n, v in protocol['helperSources'].items())
assert all(sha(n) == v for n, v in protocol['runtimeSources'].items())
write(alignment / 'protocol.json', protocol)
write(alignment / 'join-policy.json', {
    'state': 'FROZEN_TWO_ARMS_SAME_EXISTING_FUSION_BEFORE_ALIGNMENT',
    'originalStudyProtocolSha256': sha(CONTROL / 'protocol.json'),
    'speakerJournal': str(speaker_dir / 'speaker-journal.json'),
    'speakerJournalSha256': sha(speaker_dir / 'speaker-journal.json'),
    'producerFile': str(speaker_dir / 'completed-state.json'),
    'producerSha256': sha(speaker_dir / 'completed-state.json'),
    'nativeProtocolFile': str(native / 'protocol.json'), 'nativeProtocolSha256': sha(native / 'protocol.json'),
    'sourceModuleSha256': {n: sha(SRC/n) for n in ['companion_local_speaker_document_20261114.py',
                                               'companion_exclusive_journal_20261114.py', 'practical_transcript_20261107.py']},
    'uncertaintyMarginSeconds': .06, 'newWeightUpdates': 0,
    'perWordBestOutputSelection': False, 'realCardTested': False, 'qualityQualified': False})
write(alignment / 'input-checks.json', {'state': 'PASS_BOTH_COMPLETE_FROZEN_RAW_ASR_INPUTS',
                                       'arms': receipts, 'limits': limits.query()})
print(json.dumps({'state': 'READY_SHARED_ALIGNMENT_BOTH_ARMS', 'arms': receipts}, ensure_ascii=False))
