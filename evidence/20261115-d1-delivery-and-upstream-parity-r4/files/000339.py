"""One predeclared activity hypothesis, including rejection before full runs."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json
from practical_io_20261107 import atomic_json
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (C/'protocol.json').exists();ready=read(C/'model-ready.json');source=ast.parse((Path(ready['modelscopeRoot'])/'modelscope/models/audio/sv/ERes2NetV2.py').read_text(encoding='utf8'))
classes=[n for n in source.body if isinstance(n,ast.ClassDef) and n.name in ['ReLU','BasicBlockERes2NetV2','BasicBlockERes2NetV2AFF','ERes2NetV2']]
P={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ONE_TARGET_ACTIVITY_HYPOTHESIS_FROZEN_BEFORE_INFERENCE',
    'hypothesis':'A learned target-conditioned presence model on original mixture may distinguish target absence that post-extraction native cosine top1 failed to detect. It is not assumed to solve separation distortion or ASR hallucination.',
    'candidate':'tuya/nomo-pvad release-1.1 cb828468d183424fd574984f00b3ffbcce0be9bc, matching native ModelScope ERes2NetV2 enrollment; FP32/eval, author offline probs_on/score_utterance path.',
    'workerSourceSha256':sha(Path(__file__).with_name('practical_target_activity_worker_20261107.py')),
    'audioOnlySha256':sha(C/'audio-only.json'),'enrollmentPlanSha256':sha(C/'automatic-enrollments.json'),'modelReadySha256':sha(C/'model-ready.json'),
    'nativeEncoderClassAstSha256':hashlib.sha256(ast.dump(ast.Module(body=classes,type_ignores=[]),include_attributes=False).encode()).hexdigest(),
    'featureRule':'Author native Kaldi80d fbank,25ms/10ms,dither0,time-mean subtraction on each full30s clip. Original normalized PCM, no peak normalization/no denoising/no reference. No graph/export/quantization change.',
    'timingRule':'Author160ms output grid; chunk i is [i*2560,min((i+1)*2560,input_samples)) at16kHz. Fbank frame count (N-400)//160+1; output ceil(frames/16). Final padding clipped, never adds real audio. Coarse predicted activity, not verified word time or streaming latency.',
    'decisionThreshold':.7,'thresholdSource':'Pinned author CLI/default high-false-acceptance-prevention operating point, frozen once; no threshold/window sweep.',
    'pilot':'First frozen clip and all6 automatic L targets, plus all15 disjoint automatic profile vectors. Technical strict-key/value/native GPU byte and160ms count/finite-probability checks only; do not tune to pilot quality.',
    'short':'All13 frozen real30s clips from3development meetings/2corpora,67 target queries including absent targets, reusing identical pilot outputs. One changed component: target activity. Original ASR/separation and all words unchanged.',
    'shortRejectionCriteria':{'everyMeetingPositive3sWindowRecallMin':.95,'everyMeetingAbsent3sWindowFalseAcceptanceMax':.05,
        'windowRule':'3s windows/1.5s-hop. Any lexical reference target speech makes positive; prediction positive iff any frozen0.7 output interval intersects the window. Same predicate on existing baseline activity. Correlated diagnostics, not CER/DER acceptance.',
        'ordinaryPositiveWindowRecallMustNotDecreaseFromBaseline':True,'shortReferenceTurnEventRecallMustNotDecreaseWithinEachMeeting':True,
        'aggregateWrongActivitySecondsMustImproveFromBaseline':True,'allConditionsMustHoldBeforeFullExpansion':True,
        'scope':'Quick engineering falsification only.95/5 does not imply final wordCER<5%; native time-grid/corpus short-span conventions disclosed.'},
    'ifPass':'Only then freeze complete-development-meeting activity validation and integration strategy; no unreviewed transcript filtering. Original full word/person<5%, ordinary nonregression and final unseen/summary/card gates remain.',
    'ifFail':'Stop this candidate before full activity/ASR/separation runs. No backup without different causal evidence; no cutoff/window sweep. Reassess domain/enrollment/training supervision or architecture using observed failure strata.',
    'referencesPassedToWorker':False,'asrOrSeparationRerunAllowed':False,'finalHoldoutOpened':False,'qualityQualified':False}
atomic_json(C/'protocol.json',P);print(json.dumps({'state':P['state'],'workerSha256':P['workerSourceSha256'],'queries':67,'threshold':P['decisionThreshold']},ensure_ascii=False))
