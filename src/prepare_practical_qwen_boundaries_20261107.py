"""Freeze one source-grounded boundary experiment before any new inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261107-model-generation-recovery'
base=B/'practical-qwen-native17-r5';C=B/'practical-qwen-author-boundaries-r6';src=Path(__file__).parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not C.exists();proof=read(base/'author-boundary-preparation.json')
assert proof['state']=='PASS_BOUNDED_WAV_AUTHOR_BOUNDARY_MATH_ONLY_NO_ASR_QUALITY_RESULT' and proof['portSourceSha256']==sha(src/'practical_qwen_audio_boundaries_20261107.py')
assert read(base/'ordinary-stage-review.json')['rawChronologicalCerNative17']==0.05765765765765766
C.mkdir();(C/'full').mkdir()
for file in ['native-protocol.json','model-ready.json','hip-inventory.json','pilot-extra-audio-only.json']:shutil.copyfile(base/file,C/file)
shutil.copyfile(base/'author-boundaries-audio-only.json',C/'audio-only.json');shutil.copyfile(C/'audio-only.json',C/'full/audio-only.json');shutil.copyfile(base/'full/scoring-only.json',C/'full/scoring-only.json')
atomic_json(C/'seed-manifest.json',{'files':{},'reason':'Same checkpoint but audio-root spans differ. Do not reuse fixed-root generated outputs as new-boundary recognition.'})
P=read(base/'protocol.json')
P.update(declaredAt=datetime.now().astimezone().isoformat(timespec='seconds'),baseControl=str(C),baseProtocolSha256=sha(C/'native-protocol.json'),
  workerSourceSha256=sha(src/'practical_qwen_boundaries_worker_20261107.py'),baseWorkerSourceSha256=None,
  boundarySourceSha256=sha(src/'practical_qwen_audio_boundaries_20261107.py'),
  boundaryPolicy='Exact author low-energy rule, same local30s budget; search±5s/minimum100ms absolute-amplitude window; source-required short-tail padding only. No VAD trimming.',
  sourceAuthorAsrDefaultTargetSeconds=1200,localTargetSeconds=30.,searchExpandSeconds=5.,energyWindowMilliseconds=100.,
  normalControlRawFile=str(base/'pilot/nodes/ordinary-bounded-root.json'),
  modelParametersChanged=False,changedParameterScope='Only root boundaries and documented short-tail padding; weights, greedy/BF16/eager/Chinese/no prompt/token budget/recovery/CPU5%/private2GiB unchanged.',
  pilotCases='One unchanged actual30s must match native1.7B recorded IDs/text; longest real audio-only selected root must retain all input mel frames (no30s truncation); exact-zero-only pipeline guard reused. No accuracy claim before same full meeting scoring.')
atomic_json(C/'protocol.json',P)
atomic_json(C/'boundary-math-proof.json',proof)
atomic_json(C/'comparison-rule.json',{'declaredAt':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'FROZEN_BEFORE_AUTHOR_BOUNDARY_NEURAL_INFERENCE',
  'baselineControl':str(base),'ordinaryMeeting':'S_R004S03C01','baselineStrictCer':0.05765765765765766,'requiredCerExclusiveMax':.05,
  'rule':'Accuracy-first: only if complete ordinary strict CER<5% continue the same full complex meeting. Otherwise retain the actual gain/regression and stop complex inference; no threshold/window sweep or per-meeting policy choosing. All other quality/sale gates remain open.',
  'whyDifferent':'Author uses low-energy cuts, while the controlled0.6B/1.7B comparisons used fixed30s cuts. This tests one specific input-boundary hypothesis, not another checkpoint/training/repetition penalty. The author1200s default is not attempted under this machine budget.',
  'referenceOrAsrTextUsedToSelectSpans':False,'qualityQualified':False})
atomic_json(C/'prepared.json',{'state':'FROZEN_AUTHOR_BOUNDARY_COMPARISON_PREPARED_NO_NEW_INFERENCE',
  'at':datetime.now().astimezone().isoformat(timespec='seconds'),'modelId':'Qwen/Qwen3-ASR-1.7B-hf','nativeProtocolSha256':sha(C/'native-protocol.json'),
  'protocolSha256':sha(C/'protocol.json'),'weightsReusedWithoutRedownload':True,'fullSpanCounts':{r['meeting']:len(r['spans']) for r in read(C/'audio-only.json')},
  'fullNative17ComplexStillSeparateOngoingComparison':True,'inferenceStarted':False,'qualityQualified':False})
print(json.dumps({'state':'PREPARED_ONLY_NO_NEW_NEURAL_WORK','control':str(C),'ordinaryTarget':.05}))
