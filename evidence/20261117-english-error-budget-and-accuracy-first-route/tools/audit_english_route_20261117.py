"""Audit already-exposed English evidence without inference or changed scoring."""
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib, json, math, sys, wave

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
S = R / 'model-research/src'
J = R / 'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E = Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
sys.path.insert(0, str(S))
from score_sequential_meetings_20261115 import measure, tokens

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

control = read(J / 'english-transducer-r1/scoring-control.json')
for item in control['files']:
    assert sha(item['file']) == item['sha256'], item['file']
tdt_path = J / 'english-transducer-r1/score.json'
tdt = read(tdt_path)
ids = {c['id'] for c in tdt['cases']}
assert len(ids) == 12 and all(c.startswith(('ES2003b-', 'EN2001a-')) for c in ids)
refs = {c['id']: c for c in read(control['references']) if c['id'] in ids}
assert len(refs) == 12 and all(c['role'] == 'validation' and c['language'] == 'English' for c in refs.values())
audio = {c['id']: c for c in read(J / 'english-transducer-r1/audio-only.json')}
state_path = E / 'english-transducer-r1/run-r1/completed.json'
state = read(state_path)
weights_proof_path = state_path.parent / 'weight-roundtrip.json'
weights = read(weights_proof_path)
protocol = read(control['protocol'])
assert weights['fileSha256'] == weights['deviceRoundtripSha256'] == protocol['weights']['sha256']
assert len(state['completed']) == 12 and state['trainingUpdates'] == 0

scores = {'Parakeet': {c['id']: c['errors'] for c in tdt['cases']}}
moss_path = Path(control['mossBaseline'])
moss = {c['id']: c for c in read(moss_path)['cases'] if c['id'] in ids}
scores['MOSS'] = {k: v['raw']['errors'] for k, v in moss.items()}
qwen_path = Path(control['qwenBaseline'])
qwen = {c['id']: c for c in read(qwen_path)['cases'] if c['id'] in ids}
scores['Qwen'] = {k: v['errors'] for k, v in qwen.items()}
whisper_path = E / 'english-full-base-r1/cpu-execution-r3/score.json'
whisper = read(whisper_path)
scores['Whisper_large_v3_F16'] = {c['id']: c['errors'] for c in whisper['cases']}
assert all(set(v) == ids for v in scores.values())

fillers = {'uh', 'um', 'hmm', 'mm', 'hm', 'ah', 'er', 'erm', 'mhm'}
aggregate = Counter()
rows = []
for entry in state['completed']:
    assert sha(entry['file']) == entry['sha256']
    out = read(entry['file'])
    c = refs[out['id']]
    a = audio[out['id']]
    assert out['audioSha256'] == a['audioSha256'] == sha(a['audio'])
    assert out['binding'] == state['binding']
    assert out['featureFrames'] == a['frames'] // 160
    assert out['allInputFramesPreserved'] and out['naturalTermination'] and out['encoderExhausted']
    assert not out['referenceUsed'] and not out['wordsPostEdited']
    with wave.open(a['audio'], 'rb') as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, a['frames'])
        pcm_digest = hashlib.sha256(w.readframes(w.getnframes())).hexdigest()
    assert pcm_digest == c['pcmSha256']
    result = measure(c['rawReferenceText'], out['text'], 'English')
    old = next(v for v in tdt['cases'] if v['id'] == c['id'])
    for key in ('errors', 'substitutions', 'deletions', 'insertions'):
        assert result[key] == old[key]
        aggregate[key] += result[key]
    rt = tokens(c['rawReferenceText'], 'English')
    aggregate['referenceWords'] += len(rt)
    positions = [op['referenceIndex'] for op in result['editOperations'] if op['operation'] == 'delete']
    deleted_fillers = sum(rt[pos] in fillers for pos in positions)
    aggregate['explicitFillerDeletions'] += deleted_fillers
    aggregate['allExplicitReferenceFillers'] += sum(t in fillers for t in rt)
    row = {
        'id': c['id'], 'meeting': c['meeting'], 'referenceWords': len(rt),
        'errors': result['errors'], 'substitutions': result['substitutions'],
        'deletions': result['deletions'], 'insertions': result['insertions'],
        'explicitFillerDeletions': deleted_fillers,
        'deletedReferencePositions': positions,
        'allNativeInputFramesAndEncoderFramesProcessed': True,
        'continuousOriginalSourceInterval': c['sourceEndFrame'] - c['sourceStartFrame'] == c['frames'],
        'nonoverlapByExistingPublicReference': not c['overlapPresentByReference'],
        'originalAudioSeconds': c['audioSeconds'],
        'bestWholeClipErrorsWithReferenceOracle': min(v[c['id']] for v in scores.values()),
    }
    rows.append(row)

assert aggregate['referenceWords'] == 709 and aggregate['errors'] == 123
n = aggregate['referenceWords']
oracle = sum(row['bestWholeClipErrorsWithReferenceOracle'] for row in rows)
oracle_pm = sum(min(scores[m][case] for m in ('Parakeet', 'MOSS')) for case in ids)
floor = math.floor(.05 * n)
target = math.floor(.02 * n)
plan_path = J / 'language-specific-adaptation-r1/expanded-data-r3/english-data-plan.json'
plan = read(plan_path)
assert plan['examples'] == 1828 and plan['parameterUpdates'] == 0
evidence_files = [tdt_path, moss_path, qwen_path, whisper_path, state_path,
                  weights_proof_path, Path(control['references']),
                  S / 'score_sequential_meetings_20261115.py', plan_path]
report = {
    'at': datetime.now().astimezone().isoformat(timespec='seconds'),
    'state': 'ENGLISH_ROUTE_REASSESSMENT_FROM_FIXED_EXISTING_OUTPUTS_NO_NEW_MODEL_RUN',
    'ownerQuotes': [
        '怎么感觉英文的这个差这么远？是不是因为模型搞错了？是不是感觉很难降到5%以下？你这个看一下怎么搞吧。',
        '你看一下是不是需要那个。哦，需要那个。走一条新的路线什么的，感觉一直微磨应该磨不出来这个东西。',
    ],
    'scope': '12 already-exposed development/validation clips from 2 English meetings, 709 unchanged words. No blind or final-holdout result.',
    'originalScores': {k: {'errors': sum(v.values()), 'referenceWords': n, 'WER': sum(v.values()) / n} for k, v in scores.items()},
    'parakeetErrorBudget': {
        **dict(aggregate), 'WER': 123 / n,
        'maximumErrorsAtFivePercent': floor, 'maximumErrorsAtTwoPercent': target,
        'errorsToRemoveForFivePercent': 123 - floor,
        'relativeErrorReductionNeededForFivePercent': (123 - floor) / 123,
        'relativeErrorReductionNeededForTwoPercent': (123 - target) / 123,
        'optimisticErrorsIfEveryDeletionWereCorrectedWithNoNewErrors': 123 - aggregate['deletions'],
        'optimisticWerIfEveryDeletionWereCorrectedWithNoNewErrors': (123 - aggregate['deletions']) / n,
        'optimisticErrorsIfEveryExplicitFillerDeletionWereCorrected': 123 - aggregate['explicitFillerDeletions'],
        'warning': 'Counterfactual arithmetic only; not measured improvement, a clean-verbatim score, or a promised recoverable error count.',
    },
    'wholeClipOracleSelection': {
        'MossOrParakeetErrors': oracle_pm, 'MossOrParakeetWer': oracle_pm / n,
        'fourExistingModelsErrors': oracle, 'fourExistingModelsWer': oracle / n,
        'fivePercentPassed': oracle <= floor,
        'notDeployable': True, 'usesKnownReferencesToChooseBestWholeClip': True,
        'conclusionScope': 'Tests switching among the complete existing clip outputs only. Not a word/phrase fusion oracle and not a lower bound on all ensemble architectures.',
    },
    'implementationEvidence': {
        'exactPublishedF32DeviceRoundtripAlreadyVerified': True,
        'allTwelveFeatureLengthsAndEncoderExhaustionVerified': True,
        'originalWavAndPcmHashesVerified': True,
        'doesNotProve': 'Independent full-model NeMo-vs-Transformers equivalence or absence of every possible generation bug. Encoder exhaustion does not prove that every spoken word was recognized.',
        'referencePolicy': 'Existing punctuation/case-insensitive lexical scorer still counts fillers, partial words, initials and repetitions. Original scores and gates unchanged.',
        'crossLanguageCaveat': 'Chinese CER vs English WER and different recordings cannot be read as a direct language-capability comparison.',
    },
    'publishedContextNotOurBenchmark': [
        {'source': 'https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3',
         'officialModelCardTable': {'AMI_WER': 11.31, 'LibriSpeech_test_clean_WER': 1.93},
         'caveat': 'Different corpus protocol/normalization and clips from this product cohort; not a reproduction or an expected score on our distant microphone.'},
        {'source': 'https://huggingface.co/ibm-granite/granite-speech-4.1-2b-nar',
         'officialAdditionalResults': {'AMI_IHM_WER': 7.91, 'AMI_SDM_WER': 19.59},
         'caveat': 'Same published model under headset vs single distant microphone; publisher results, not a universal limit. Requires flash_attention_2 in its documented reference path; do not initiate an AMD port.'},
        {'source': 'https://huggingface.co/nvidia/multitalker-parakeet-streaming-0.6b-v1',
         'officialMultitalkerCpWer': {'AMI_IHM': 21.26, 'AMI_SDM': 37.44},
         'caveat': 'Includes overlap and speaker attribution; cpWER is not our ordinary raw WER. Adding diarization-conditioned ASR does not itself guarantee 5 percent.'},
    ],
    'adaptationEvidence': {
        'examples': plan['examples'], 'audioHours': plan['audioSeconds'] / 3600,
        'trainableParameters': plan['trainableParameters'], 'completedAsrOptimizerUpdates': 0,
        'assessment': 'No complete English ASR adaptation result exists. This is an execution gap, not a negative trained-model result. Four hours/one epoch has not been shown sufficient for a 71.5 percent relative error reduction.',
    },
    'decision': {
        'changeExecutionRoute': True,
        'retainValidatedComponentsAndOriginalQualityFloor': True,
        'pauseNext119MFileMappedCpuBackwardExperiment': True,
        'whyPause': 'Another CPU optimizer-memory workaround primarily proves executability, while no evidence links that four-hour recipe to the required quality jump.',
        'mainline': 'Accuracy-first English offline final transcription, distinct from the existing provisional incremental transcript. Prove one substantially stronger acoustically grounded base on unchanged far-field data before domain training, distillation, quantization or deployment tuning.',
        'oneNextAccuracyReference': {
            'repository': 'ibm-granite/granite-speech-4.1-2b',
            'reason': 'Official dual-head CTC acoustic encoder plus speech-conditioned language decoder, commercial Apache2.0 distribution, documented native Transformers and llama.cpp paths. The NAR card explicitly recommends this AR sibling when accuracy is primary. Not selected by parameter size or generic mean score.',
            'status': 'REFERENCE_CANDIDATE_ONLY_NOT_DOWNLOADED_OR_EXECUTED',
            'publicNumbersDoNotProveOurAccuracy': True,
            'feasibilityBeforeWeights': 'Pin revision/config and inspect the existing upstream native path and remaining realRAM/private budget. If unavailable, record that dependency without a custom engine port or a fallback model grid.',
            'newStricterIntermediateGate': {'maxErrors': 70, 'referenceWords': 709, 'eachMeetingNoWorseThanBestExistingBase': True,
                'addsToOriginal99ErrorAdmissionGate': True, 'isSaleOrFivePercentQualification': False},
        },
        'ifReferenceHasSubstantialGain': 'Keep one base, perform one predeclared meeting-domain adaptation with speaker/meeting-disjoint training and unchanged multi-meeting/person/facts/final tests. Retain the current incremental stream and validate offline-final integration only after accuracy admission.',
        'ifNoSubstantialGain': 'Close this accuracy reference; do not continue decoder/precision/size grids. The product-wide 5 percent floor remains unmet and requires a specific remaining acoustic/data/recording hypothesis, not a new promised overnight success.',
        'overlapPriority': 'After ordinary nonoverlapping ASR is strong. Preserve the working diarizer; defer separation and overlapping-speaker expansion.',
        'cpuAndIntegratedGpuTrainingAllowedButNotPrerequisite': True,
        'newResourceOrCloudPermissionRequested': False,
    },
    'cases': rows,
    'sources': [{'file': str(p), 'sha256': sha(p)} for p in evidence_files],
    'scorerChanged': False, 'oldResultsOverwritten': False,
    'newNeuralCalls': 0, 'newTrainingUpdates': 0,
    'finalHoldoutOpened': False, 'qualityQualified': False, 'saleQualified': False,
}
dest = J / 'english-route-audit-20261117.json'
assert not dest.exists(), 'Retain completed audit; do not overwrite'
dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: report[k] for k in ('state', 'originalScores', 'parakeetErrorBudget', 'wholeClipOracleSelection')}, ensure_ascii=False, indent=2))
