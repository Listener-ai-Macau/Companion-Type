from pathlib import Path
from datetime import datetime
import hashlib
import json
import subprocess
import sys

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
BASE = ROOT / 'docs/handoffs/20261107-model-generation-recovery'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/normal-turn-r6-alignment-r1'
OUT = CONTROL / 'exclusive-r2'
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


policy = read(CONTROL / 'exclusive-reconciliation-policy.json')
assert policy['state'] == 'FROZEN_BEFORE_EXCLUSIVE_RECONCILIATION_OUTPUT_OR_SCORE'
assert not OUT.exists()
OUT.mkdir()
tiny = np.asarray([[.8, .1], [.9, .6], [.7, .7], [.5, .1], [.1, .1]], dtype=np.float32)
test, receipt = exclusive_journal(tiny, frames=5, seconds_per_frame=.01,
                                   source_journal={'audioSha256': 'test-only', 'audioSeconds': .05, 'segments': []})
assert test['segments'] == [{'start': 0., 'end': .02, 'speaker': 0}, {'start': .03, 'end': .04, 'speaker': 0}]
assert receipt['speechFramesUnassignedDueToExactPosteriorTie'] == 1
assert receipt['rawSpeechFrames'] == 4 and receipt['exclusiveSpeechFrames'] == 3
write(OUT / 'posterior-semantics-control.json', {'state': 'PASS_UNIQUE_POSTERIOR_TIE_SILENCE_AND_NATIVE_HALF_VALUE_CARRY', **receipt})

ordinary, = read(CONTROL / 'audio-text-only.json')
old = BASE / 'practical-alignment-r1'
complex_case = next(c for c in read(old / 'audio-text-only.json') if c['meeting'] == 'L_R003S01C02')
plans = [(ordinary, CONTROL, CONTROL / 'transcripts/S_R004S03C01',
          read(CONTROL / 'join-policy.json')['speakerJournal']),
         (complex_case, old, old / 'derived-onset/transcripts/L_R003S01C02',
          read(old / 'onset-attribution-policy.json')['speakerJournals']['L_R003S01C02'])]
references = read(CONTROL / 'scoring-only.json') + [c for c in read(old / 'derived-onset/scoring-only.json') if c['meeting'] == 'L_R003S01C02']
write(OUT / 'scoring-only.json', references)
native = BASE / 'native8-f16-full-r1'
native_protocol = read(native / 'protocol.json')
scorer_python = 'E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
checker = Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe')
assert checker.exists()
results = []
for case, aligned_control, previous_out, record in plans:
    name = case['meeting']
    assert sha(case['sourceDocument']) == case['sourceDocumentSha256']
    assert sha(record['file']) == record['sha256'] and sha(record['producerFile']) == record['producerSha256']
    raw_journal = read(record['file'])
    producer = read(record['producerFile'])
    cadence = producer['nativeSecondsPerFrame']
    assert abs(cadence - .01) < 1e-8
    probability_dir = Path(native_protocol['probabilityCacheRoot']) / name
    manifest = read(probability_dir / 'probabilities.json')
    assert manifest['audioSha256'] == case['audioSha256'] == raw_journal['audioSha256']
    assert manifest['modelSha256'] == native_protocol['modelSha256']
    assert manifest['protocolSha256'] == sha(native / 'protocol.json')
    data = np.load(probability_dir / 'probabilities.npy', mmap_mode='r', allow_pickle=False)
    frames = manifest['committedFrames']
    assert list(data.shape) == manifest['shape'] and data.dtype == np.float32
    assert hashlib.sha256(memoryview(data[:frames]).cast('B')).hexdigest() == manifest['committedPrefixSha256']
    reproduced = probability_segments(data, frames, cadence, case['audioSeconds'], .5)
    assert reproduced == raw_journal['segments'], 'Posterior cache no longer reproduces the preserved multi-voice journal'
    exclusive, derive = exclusive_journal(data, frames=frames, seconds_per_frame=cadence, source_journal=raw_journal)
    write(OUT / 'journals' / (name + '-exclusive.json'), exclusive)
    write(OUT / 'journals' / (name + '-derivation.json'), {
        **derive, 'posteriorManifestSha256': sha(probability_dir / 'probabilities.json'),
        'posteriorCommittedPrefixSha256': manifest['committedPrefixSha256'],
        'originalJournalReproducedExactly': True, 'originalJournalSha256': record['sha256']})
    payloads = []
    binding = read(aligned_control / 'full-state.json')['binding']
    for leaf in case['leaves']:
        packet = read(aligned_control / 'aligned' / name / (leaf['id']+'.json'))
        assert packet['binding'] == {**binding, 'sourceNodeSha256': leaf['nodeSha256'], 'meeting': name}
        canonical = json.dumps(packet['payload'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        assert hashlib.sha256(canonical).hexdigest() == packet['payloadSha256']
        payloads.append(packet['payload'])
    source = read(case['sourceDocument'])
    baseline_doc, baseline_trace = join_aligned_recording(source, case['leaves'], payloads, raw_journal,
                                                         audio_seconds=case['audioSeconds'], audio_sha256=case['audioSha256'])
    baseline_saved = read(previous_out / 'attribution-review.json')['tokenEstimates']
    actual = [(r['text'], r['speaker'], r['estimatedOnsetSeconds']) for r in baseline_trace['tokenEstimates']]
    expected = [(r['text'], r['speaker'], r['estimatedOnsetSeconds']) for r in baseline_saved]
    assert actual == expected, 'Default join changed existing full-meeting onset decisions'
    document, trace = join_aligned_recording(source, case['leaves'], payloads, raw_journal,
                                             audio_seconds=case['audioSeconds'], audio_sha256=case['audioSha256'],
                                             attribution_journal=exclusive)
    assert document['text'] == source['text'] == ''.join(r['text'] for r in document['utterances'])
    assert trace['nativeToConsecutiveDisplaySpeakerIds'] == baseline_trace['nativeToConsecutiveDisplaySpeakerIds']
    if name == 'S_R004S03C01':
        wrong = {**exclusive, 'audioSha256': '0'*64}
        try:
            join_aligned_recording(source, case['leaves'], payloads, raw_journal, audio_seconds=case['audioSeconds'],
                                   audio_sha256=case['audioSha256'], attribution_journal=wrong)
        except ValueError:
            pass
        else:
            raise AssertionError('Exclusive journal from another recording was accepted')
    out = OUT / 'transcripts' / name
    write(out / 'model-output.json', document)
    write(out / 'attribution-review.json', {
        **trace, 'meeting': name, 'audioSha256': case['audioSha256'], 'audioSeconds': case['audioSeconds'],
        'rawWindowText': source['text'], 'allOriginalAudioSamplesCoveredOnce': True,
        'allTextPreservedThroughAttribution': True, 'speakerJournalSha256': record['sha256'],
        'sourceDocumentSha256': case['sourceDocumentSha256'],
        'exclusiveJournalSha256': sha(OUT / 'journals' / (name+'-exclusive.json'))})
    write(out / 'completed-state.json', {'state': 'COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED',
                                        'finishedAt': now(), 'audioSha256': case['audioSha256'], 'speakerJournalPending': False,
                                        'modelOutputSha256': sha(out / 'model-output.json'),
                                        'attributionReviewSha256': sha(out / 'attribution-review.json'), 'qualityQualified': False})
    check = subprocess.run([str(checker), str(out / 'model-output.json'), str(round(case['audioSeconds']*1000))],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    write(out / 'product-contract.json', {'exitCode': check.returncode, 'stdout': check.stdout, 'stderr': check.stderr,
                                         'checkerSha256': sha(checker), 'newBuildPerformed': False})
    assert check.returncode == 0, check.stderr
    with (out / 'scoring.log').open('xb') as log:
        scored = subprocess.run([scorer_python, str(SRC / 'score_practical_transcript_20261107.py'),
                                 '--control', str(OUT), '--meeting', name], stdout=log, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    assert scored.returncode == 0
    quality = read(out / 'quality-review.json')
    prior = read(previous_out / 'quality-review.json')
    assert quality['chronologicalTextDiagnostic'] == prior['chronologicalTextDiagnostic']
    changes = [{'sourceLeaf': a['sourceLeaf'], 'text': a['text'], 'estimatedOnsetSeconds': a['estimatedOnsetSeconds'],
                'beforeSpeaker': b['speaker'], 'afterSpeaker': a['speaker'],
                'originalCandidates': a['rawMultiVoiceCandidates'], 'originalOverlap': a['rawMultiVoiceOverlapNearOnset']}
               for a, b in zip(trace['tokenEstimates'], baseline_trace['tokenEstimates']) if a['speaker'] != b['speaker']]
    results.append({'meeting': name, 'sourceDocumentSha256': case['sourceDocumentSha256'],
                    'audioSeconds': case['audioSeconds'], 'strictRawCerUnchanged': quality['chronologicalTextDiagnostic']['cer'],
                    'beforeCpCer': prior['anonymousStreamCpCerDiagnostic'], 'afterCpCer': quality['anonymousStreamCpCerDiagnostic'],
                    'beforeUnknown': prior['unconfirmedSpeakerText'], 'afterUnknown': quality['unconfirmedSpeakerText'],
                    'unknownForcedUnmatched': quality['confirmedAttributionCerDiagnostic'],
                    'changedUnitLabels': changes, 'allOriginalCharactersPreserved': True,
                    'defaultJoinFullUnitDecisionsUnchanged': True, 'nativeAnonymousIdentityMappingUnchanged': True,
                    'rawOverlapEvidencePreserved': True, 'posteriorDerivation': derive})
ordinary_result, complex_result = results
better = ordinary_result['afterCpCer']['totalEdits'] < ordinary_result['beforeCpCer']['totalEdits']
result = {'at': now(), 'state': 'OPTIONAL_EXCLUSIVE_ATTRIBUTION_RETAINED_EXPERIMENTAL' if better else 'EXCLUSIVE_ATTRIBUTION_NO_GAIN_RETAIN_FAILURE_STOP',
          'policySha256': sha(CONTROL / 'exclusive-reconciliation-policy.json'),
          'moduleSha256': sha(SRC / 'companion_exclusive_journal_20261114.py'),
          'joinModuleSha256': sha(SRC / 'companion_local_speaker_document_20261114.py'),
          'results': results, 'newNeuralCalls': 0, 'originalWordsOrNativeProbabilitiesEdited': False,
          'originalMultiVoiceDerUnchanged': True, 'nativeModelOrThresholdChanged': False,
          'ordinaryFullResultImproved': better, 'referenceUsedOnlyForPosthocScoring': True,
          'exposedDevelopmentNotHoldout': True, 'overlappingWordsRecovered': False,
          'productDefaultChanged': False, 'qualityQualified': False, 'saleQualified': False,
          'limits': limits.query()}
write(OUT / 'result.json', result)
print(json.dumps({'state': result['state'], 'results': [
    {'meeting': r['meeting'], 'beforeCpCer': r['beforeCpCer']['characterErrorRate'],
     'afterCpCer': r['afterCpCer']['characterErrorRate'], 'beforeEdits': r['beforeCpCer']['totalEdits'],
     'afterEdits': r['afterCpCer']['totalEdits'], 'beforeUnknown': r['beforeUnknown']['characters'],
     'afterUnknown': r['afterUnknown']['characters'], 'changedUnits': len(r['changedUnitLabels'])} for r in results]}, ensure_ascii=False))
