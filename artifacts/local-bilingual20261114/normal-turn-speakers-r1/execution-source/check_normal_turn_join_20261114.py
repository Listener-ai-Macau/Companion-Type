from pathlib import Path
import copy
import hashlib
import json
import sys

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
sys.path.insert(0, str(SRC))
from companion_local_speaker_document_20261114 import join_aligned_recording
from moss_windows_resource_limits_20261104 import WorkerLimits
limits = WorkerLimits(cpu_percent=5, memory_bytes=256*1024**2)
OLD = ROOT / 'docs/handoffs/20261107-model-generation-recovery/practical-alignment-r1'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/normal-turn-r6-alignment-r1'
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
case = next(c for c in read(OLD / 'audio-text-only.json') if c['meeting'] == 'S_R004S03C01')
original = read(case['sourceDocument'])
payloads = [read(OLD / 'aligned/S_R004S03C01' / (leaf['id']+'.json'))['payload'] for leaf in case['leaves']]
policy = read(OLD / 'onset-attribution-policy.json')
journal = read(policy['speakerJournals']['S_R004S03C01']['file'])
document, trace = join_aligned_recording(original, case['leaves'], payloads, journal,
                                        audio_seconds=case['audioSeconds'], audio_sha256=case['audioSha256'])
old_document = read(OLD / 'derived-onset/transcripts/S_R004S03C01/model-output.json')
expected = [(r['text'], r['speaker'], r['startMs'], r['endMs']) for r in old_document['utterances']]
actual = [(r['text'], r['speaker'], r['startMs'], r['endMs']) for r in trace['tokenEstimates']]
assert actual == expected, 'New reusable join changed the established actual full-meeting unit decisions'
assert document['text'] == original['text'] == ''.join(r['text'] for r in document['utterances'])
by_speaker = lambda rows: {str(s): ''.join(r['text'] for r in rows if r['speaker'] == s).replace('\n', '')
                           for s in {r['speaker'] for r in rows}}
assert by_speaker(document['utterances']) == by_speaker(old_document['utterances'])

def rejected(leaves, aligned, predicted):
    try:
        join_aligned_recording(original, leaves, aligned, predicted,
                               audio_seconds=case['audioSeconds'], audio_sha256=case['audioSha256'])
    except ValueError:
        return
    raise AssertionError('Invalid recording/payload binding was accepted')

wrong_recording = {**journal, 'audioSha256': '0'*64}
rejected(case['leaves'], payloads, wrong_recording)
wrong_payload = copy.deepcopy(payloads)
wrong_payload[0]['originalText'] += ' invented'
rejected(case['leaves'], wrong_payload, journal)
wrong_leaves = copy.deepcopy(case['leaves'])
wrong_leaves[1]['startSample'] += 1
rejected(wrong_leaves, payloads, journal)
result = {'state': 'PASS_EXISTING_FULL_NORMAL_TURN_JOIN_EXACT_REGRESSION_AND_RECORDING_CONSERVATION',
          'meeting': case['meeting'], 'sourceDocumentSha256': case['sourceDocumentSha256'],
          'existingActualUnitsCompared': len(actual), 'sameTextSpeakerAndDisplayTimesEveryUnit': True,
          'samePerSpeakerTextAfterParagraphPacking': True, 'allSourceCharactersIncludingNewlinesPreserved': True,
          'wrongRecordingRejected': True, 'changedAlignmentTextRejected': True, 'sourceSampleGapRejected': True,
          'paragraphs': len(document['utterances']), 'newNeuralCalls': 0, 'qualityQualified': False,
          'moduleSha256': hashlib.sha256((SRC / 'companion_local_speaker_document_20261114.py').read_bytes()).hexdigest(),
          'limits': limits.query()}
target = CONTROL / 'existing-full-join-regression.json'
assert not target.exists()
target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
