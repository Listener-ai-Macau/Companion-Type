from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path('C:/Users/Billy/Desktop/Denzic/Companion')
SRC = ROOT / 'model-research/src'
BASE = ROOT / 'docs/handoffs/20261107-model-generation-recovery'
CONTROL = ROOT / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/normal-turn-r6-alignment-r1'
sys.path.insert(0, str(SRC))
from companion_local_speaker_document_20261114 import join_aligned_recording
from moss_windows_resource_limits_20261104 import WorkerLimits
limits = WorkerLimits(cpu_percent=5, memory_bytes=512*1024**2)
read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
now = lambda: datetime.now().astimezone().isoformat(timespec='seconds')


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


run = read(CONTROL / 'run.json')
state = read(CONTROL / 'full-state.json')
assert run['state'] == 'COMPLETE_NORMAL_TURN_ALIGNMENT_JOIN_PENDING' and run['finishedAt']
assert state['state'] == 'COMPLETE_NATIVE_ALIGNMENT_FULL_NOT_TIME_QUALIFIED' and state['finishedAt']
assert state['binding']['protocolSha256'] == sha(CONTROL / 'protocol.json')
assert state['binding']['planSha256'] == sha(CONTROL / 'audio-text-only.json')
policy = read(CONTROL / 'join-policy.json')
assert sha(SRC / 'practical_transcript_20261107.py') == policy['helperSourceSha256']
assert policy['uncertaintyMarginSeconds'] == .06
assert read(CONTROL / 'existing-full-join-regression.json')['moduleSha256'] == sha(SRC / 'companion_local_speaker_document_20261114.py')
case, = read(CONTROL / 'audio-text-only.json')
source = read(case['sourceDocument'])
assert sha(case['sourceDocument']) == case['sourceDocumentSha256']
journal_record = policy['speakerJournal']
assert sha(journal_record['file']) == journal_record['sha256']
assert sha(journal_record['producerFile']) == journal_record['producerSha256']
payloads = []
for leaf in case['leaves']:
    packet = read(CONTROL / 'aligned' / case['meeting'] / (leaf['id']+'.json'))
    assert packet['binding'] == {**state['binding'], 'sourceNodeSha256': leaf['nodeSha256'], 'meeting': case['meeting']}
    assert sha(leaf['nodeFile']) == leaf['nodeSha256']
    payload = packet['payload']
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(canonical).hexdigest() == packet['payloadSha256']
    payloads.append(payload)
journal = read(journal_record['file'])
document, trace = join_aligned_recording(source, case['leaves'], payloads, journal,
                                        audio_seconds=case['audioSeconds'], audio_sha256=case['audioSha256'])
out = CONTROL / 'transcripts' / case['meeting']
assert not out.exists()
out.mkdir(parents=True)
write(out / 'model-output.json', document)
attribution = {**trace, 'meeting': case['meeting'], 'audioSha256': case['audioSha256'],
               'audioSeconds': case['audioSeconds'], 'allOriginalAudioSamplesCoveredOnce': True,
               'allTextPreservedThroughAttribution': True, 'rawWindowText': source['text'],
               'sourceDocumentSha256': case['sourceDocumentSha256'], 'speakerJournalSha256': journal_record['sha256'],
               'scope': 'Fixed existing predicted onset+/-60ms; unknown boundaries remain unknown. No source text edits or real identity inference.'}
write(out / 'attribution-review.json', attribution)
write(out / 'completed-state.json', {'state': 'COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED', 'finishedAt': now(),
                                      'audioSha256': case['audioSha256'], 'speakerJournalPending': False,
                                      'modelOutputSha256': sha(out / 'model-output.json'),
                                      'attributionReviewSha256': sha(out / 'attribution-review.json'), 'qualityQualified': False})
checker = Path('E:/CodexData/Companion/.build-cache/practical-model-contract-20261107/x86_64-pc-windows-msvc/debug/companion-model-output-contract-check.exe')
checked = subprocess.run([str(checker), str(out / 'model-output.json'), str(round(case['audioSeconds']*1000))],
                         capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
write(out / 'product-contract.json', {'at': now(), 'exitCode': checked.returncode, 'stdout': checked.stdout,
                                      'stderr': checked.stderr, 'existingBinarySha256': sha(checker),
                                      'newBuildPerformed': False, 'installedProductTested': False})
assert checked.returncode == 0, checked.stderr
scorer_python = 'E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
with (out / 'scoring.log').open('xb') as log:
    scored = subprocess.run([scorer_python, str(SRC / 'score_practical_transcript_20261107.py'),
                             '--control', str(CONTROL), '--meeting', case['meeting']],
                            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
assert scored.returncode == 0
quality = read(out / 'quality-review.json')
prior = read(Path(case['sourceDocument']).parent / 'quality-review.json')
assert quality['chronologicalTextDiagnostic'] == prior['chronologicalTextDiagnostic']
assert quality['referenceCharacters'] == 8325
assert document['text'] == source['text'] == ''.join(r['text'] for r in document['utterances'])
speaker_dir = BASE / 'native8-f16-full-r1/results' / case['meeting']
speaker_quality = read(speaker_dir / 'review.json')
assert sha(speaker_dir / 'review.json') == policy['speakerSourceSha256']
assert sha(speaker_dir / 'predicted.rttm') == speaker_quality['rttmSha256']
speaker_regions = read(speaker_dir / 'overlap-breakdown.json')
assert speaker_regions['regions']['twoOrMore']['audioRegionSeconds'] == 0
result = {'at': now(), 'state': 'COMPLETE_SINGLE_MIC_NORMAL_TURN_TEXT_AND_SPEAKER_CHAIN_QUALITY_STILL_OPEN',
          'meeting': case['meeting'], 'seconds': case['audioSeconds'], 'referenceSpeakers': 5,
          'referenceOverlappingSeconds': 0, 'inputChannels': 1,
          'sourceAudioSha256': case['audioSha256'], 'sourceDocumentSha256': case['sourceDocumentSha256'],
          'outputDocumentSha256': sha(out / 'model-output.json'),
          'rawChronological': quality['chronologicalTextDiagnostic'],
          'speakerActivityDerReused': speaker_quality['components']['diarization error rate'],
          'speakerActivityComponentsReused': speaker_quality['components'],
          'integratedCpCer': quality['anonymousStreamCpCerDiagnostic'],
          'unknownForcedUnmatched': quality['confirmedAttributionCerDiagnostic'],
          'unknownText': quality['unconfirmedSpeakerText'],
          'existingR5IntegratedCpCer': policy['oldR5IntegratedCpCer'],
          'existingR5RawCer': policy['oldR5ChronologicalCer'],
          'asrAndBoundaryChangeNotIsolatedByThisComparison': True,
          'moduleSha256': sha(SRC / 'companion_local_speaker_document_20261114.py'),
          'paragraphs': len(document['utterances']), 'alignedUnits': len(trace['tokenEstimates']),
          'knownAnonymousSpeakers': sorted({r['speaker'] for r in document['utterances'] if r['speaker'] is not None}),
          'sourceTextAndPunctuationAndNewlinesUnchanged': True,
          'newAsrCalls': 0, 'newSpeakerCalls': 0,
          'newAlignmentCalls': state['newNeuralCalls'] + read(CONTROL / 'pilot-state.json')['newNeuralCalls'],
          'pureNewAlignmentSeconds': sum(p['inferenceSeconds'] for p in payloads),
          'ownedAlignmentAttempts': run['results'],
          'wordTimeGroundTruthMeasured': False, 'realNamesVerified': False, 'installedWindowsAndroidOrCardTested': False,
          'qualityQualified': False, 'saleQualified': False,
          'next': 'Keep the proven five-speaker ordinary journal. Diagnose remaining source ASR errors and integration seams independently; do not expand overlap training or guess uncertain identities.',
          'limits': limits.query()}
write(CONTROL / 'result.json', result)
print(json.dumps({k: result[k] for k in ['state', 'rawChronological', 'speakerActivityDerReused', 'integratedCpCer',
                                        'unknownText', 'paragraphs', 'newAlignmentCalls', 'pureNewAlignmentSeconds']}, ensure_ascii=False))
