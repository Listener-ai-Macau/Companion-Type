from pathlib import Path
from datetime import datetime
import hashlib
import json
import subprocess
import sys

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/combination-study-r1'
ALIGN = CONTROL / 'alignment'
sys.path.insert(0, str(SRC))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits = WorkerLimits(cpu_percent=5, memory_bytes=512*1024**2)
from companion_local_speaker_document_20261114 import join_aligned_recording
from companion_exclusive_journal_20261114 import exclusive_journal
from practical_nemotron_worker_20261107 import probability_segments
import numpy as np

read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


assert not (CONTROL / 'result.json').exists()
assert read(ALIGN / 'run.json')['state'] == 'COMPLETE_NORMAL_TURN_ALIGNMENT_JOIN_PENDING'
full = read(ALIGN / 'full-state.json')
pilot = read(ALIGN / 'pilot-state.json')
assert full['state'] == 'COMPLETE_NATIVE_ALIGNMENT_FULL_NOT_TIME_QUALIFIED'
assert full['binding']['protocolSha256'] == sha(ALIGN / 'protocol.json')
assert full['binding']['planSha256'] == sha(ALIGN / 'audio-text-only.json')
policy = read(ALIGN / 'join-policy.json')
assert policy['originalStudyProtocolSha256'] == sha(CONTROL / 'protocol.json')
assert all(sha(SRC/n) == v for n, v in policy['sourceModuleSha256'].items())
assert sha(policy['speakerJournal']) == policy['speakerJournalSha256']
assert sha(policy['producerFile']) == policy['producerSha256']
assert sha(policy['nativeProtocolFile']) == policy['nativeProtocolSha256']
journal = read(policy['speakerJournal'])
producer = read(policy['producerFile'])
native_protocol = read(policy['nativeProtocolFile'])
base, = read(CONTROL / 'audio-only.json')
probability_dir = Path(native_protocol['probabilityCacheRoot']) / base['meeting']
manifest = read(probability_dir / 'probabilities.json')
assert manifest['audioSha256'] == journal['audioSha256'] == base['audioSha256']
assert manifest['modelSha256'] == native_protocol['modelSha256']
assert manifest['protocolSha256'] == policy['nativeProtocolSha256']
data = np.load(probability_dir / 'probabilities.npy', mmap_mode='r', allow_pickle=False)
frames, cadence = manifest['committedFrames'], producer['nativeSecondsPerFrame']
assert list(data.shape) == manifest['shape'] and data.dtype == np.float32
assert hashlib.sha256(memoryview(data[:frames]).cast('B')).hexdigest() == manifest['committedPrefixSha256']
assert probability_segments(data, frames, cadence, base['audioSeconds'], .5) == journal['segments']
exclusive, receipt = exclusive_journal(data, frames=frames, seconds_per_frame=cadence, source_journal=journal)
write(CONTROL / 'exclusive-journal.json', exclusive)
write(CONTROL / 'exclusive-derivation.json', {**receipt, 'originalMultiVoiceJournalReproducedExactly': True,
                                            'originalJournalSha256': policy['speakerJournalSha256'],
                                            'posteriorManifestSha256': sha(probability_dir / 'probabilities.json')})

checker = Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe')
scorer_python = 'E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
plan = read(ALIGN / 'audio-text-only.json')
results = []
for case in plan:
    assert sha(case['sourceDocument']) == case['sourceDocumentSha256']
    source = read(case['sourceDocument'])
    payloads = []
    for leaf in case['leaves']:
        assert sha(leaf['nodeFile']) == leaf['nodeSha256']
        packet = read(ALIGN / 'aligned' / case['meeting'] / (leaf['id']+'.json'))
        assert packet['binding'] == {**full['binding'], 'sourceNodeSha256': leaf['nodeSha256'], 'meeting': case['meeting']}
        canonical = json.dumps(packet['payload'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        assert hashlib.sha256(canonical).hexdigest() == packet['payloadSha256']
        payloads.append(packet['payload'])
    views = {}
    for name, attribution_journal in [('conservative-control', None), ('exclusive-frozen', exclusive)]:
        document, trace = join_aligned_recording(source, case['leaves'], payloads, journal,
                                                 audio_seconds=case['audioSeconds'], audio_sha256=case['audioSha256'],
                                                 attribution_journal=attribution_journal)
        assert document['text'] == source['text'] == ''.join(row['text'] for row in document['utterances'])
        destination = CONTROL / name
        if not (destination / 'scoring-only.json').exists():
            write(destination / 'scoring-only.json', read(ALIGN / 'scoring-only.json'))
        out = destination / 'transcripts' / case['meeting']
        assert not out.exists()
        write(out / 'model-output.json', document)
        write(out / 'attribution-review.json', {
            **trace, 'meeting': case['meeting'], 'audioSha256': case['audioSha256'],
            'audioSeconds': case['audioSeconds'], 'allOriginalAudioSamplesCoveredOnce': True,
            'allTextPreservedThroughAttribution': True, 'rawWindowText': source['text'],
            'sourceDocumentSha256': case['sourceDocumentSha256'],
            'speakerJournalSha256': policy['speakerJournalSha256'],
            'independentForcedAlignmentOnsetsNotNativeAsrTokenTimes': True})
        write(out / 'completed-state.json', {
            'state': 'COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED', 'finishedAt': now(),
            'audioSha256': case['audioSha256'], 'speakerJournalPending': False,
            'modelOutputSha256': sha(out / 'model-output.json'),
            'attributionReviewSha256': sha(out / 'attribution-review.json'), 'qualityQualified': False})
        checked = subprocess.run([str(checker), str(out / 'model-output.json'), str(round(case['audioSeconds']*1000))],
                                 capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        write(out / 'product-contract.json', {'exitCode': checked.returncode, 'stdout': checked.stdout,
                                             'stderr': checked.stderr, 'existingCheckerSha256': sha(checker),
                                             'newBuildPerformed': False, 'installedProductTested': False})
        assert checked.returncode == 0, checked.stderr
        with (out / 'scoring.log').open('xb') as log:
            scored = subprocess.run([scorer_python, str(SRC / 'score_practical_transcript_20261107.py'),
                                     '--control', str(destination), '--meeting', case['meeting']],
                                    stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        assert scored.returncode == 0
        quality = read(out / 'quality-review.json')
        views[name] = {'rawCer': quality['chronologicalTextDiagnostic'],
                       'cpCer': quality['anonymousStreamCpCerDiagnostic'],
                       'unknownForcedUnmatched': quality['confirmedAttributionCerDiagnostic'],
                       'unknown': quality['unconfirmedSpeakerText'],
                       'paragraphs': len(document['utterances']),
                       'perUnitDecisions': len(trace['tokenEstimates']),
                       'sourceCharactersPreserved': True, 'productContractAccepted': True,
                       'outputFile': str(out / 'model-output.json'), 'outputSha256': sha(out / 'model-output.json')}
    assert views['conservative-control']['rawCer'] == views['exclusive-frozen']['rawCer']
    results.append({'arm': case['meeting'].split('-')[0], 'meeting': case['meeting'],
                    'referenceCharacters': quality['referenceCharacters'],
                    'recognizedCharacters': quality['hypothesisCharacters'],
                    'newAlignmentCalls': sum(p['neuralInferencePerformed'] for p in payloads),
                    'pureAlignmentSeconds': sum(p['inferenceSeconds'] for p in payloads), 'views': views})

speaker_quality = read(CONTROL / 'native8/results' / base['meeting'] / 'review.json')
regions = read(CONTROL / 'native8/results' / base['meeting'] / 'overlap-breakdown.json')
result = {'at': now(), 'state': 'COMPLETE_TWO_FROZEN_COMBINATIONS_QUALITY_NOT_QUALIFIED',
          'protocolSha256': sha(CONTROL / 'protocol.json'), 'audio': base,
          'arms': results, 'sharedRawSpeakerQuality': speaker_quality, 'sharedRawSpeakerRegions': regions,
          'sharedDiarizationAttempt': read(CONTROL / 'native8/native-run.json'),
          'sharedAlignmentAttempt': read(ALIGN / 'run.json'),
          'qwenAttempt': read(Path('E:/CodexData/Companion/.model-cache/ordinary-combination-study-20261114/qwen/tasks/ordinary-qwen/task.json')),
          'paraformerAttempt': read(CONTROL / 'paraformer/run.json'),
          'newAlignmentCalls': full['newNeuralCalls']+pilot['newNeuralCalls'],
          'newWeightUpdates': 0, 'allOriginalSamplesAndSourceCharactersPreserved': True,
          'sameSharedDiarizationAlignmentFusion': True, 'bothArmsSameFrozenRootSpans': True,
          'dataScope': 'Newly used complete Train-split development meeting; not pretraining-independent, final holdout or real card.',
          'rawChronologicalOverlapOrderIsAmbiguous': True, 'wordTimeTruthMeasured': False,
          'englishFullMeetingQualified': False, 'overlappedSecondVoiceRecovered': False,
          'installedWindowsAndroidOrCardTested': False, 'qualityQualified': False, 'saleQualified': False,
          'limits': limits.query()}
write(CONTROL / 'result.json', result)
print(json.dumps({'state': result['state'], 'arms': results,
                  'sharedDer': speaker_quality['components']['diarization error rate']}, ensure_ascii=False))
