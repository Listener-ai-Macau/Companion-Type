"""Correct a proven train/inference operation-order mismatch, without tuning."""
from pathlib import Path
from datetime import datetime
import json,hashlib,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
T=D/'supervised-blind-separation-r1';OLD=T/'natural-composition-r1';C=T/'natural-window-unit-alignment-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert read(OLD/'routed-decision.json')['state']=='REJECT_FIXED_ROUTED_THREE_MODEL_COMPOSITION'
assert not C.exists();C.mkdir()
worker=S/'window_aligned_separator_worker_20261115.py'
text=(S/'supervised_separator_natural_worker_20261115.py').read_text(encoding='utf-8')
needle='                return np.stack([v.detach().cpu().numpy()[0] for v in out]).astype(np.float32,copy=False)'
replacement="""                from blind_separator_supervision_20261115 import restore_common_units
                estimate=torch.stack([v[0] for v in out])
                normalized=restore_common_units(torch,estimate,x[0])
                return normalized.detach().cpu().numpy().astype(np.float32,copy=False)"""
assert text.count(needle)==1;text=text.replace(needle,replacement)
needle="""                    raw_sum=out.sum(0).astype(np.float64)
                    e=float(np.mean(raw_sum**2))
                    gain=float(np.sqrt(np.mean(samples.astype(np.float64)**2)/e)) if e>0 else 1.
                    out=(out*gain).astype(np.float32)
"""
assert text.count(needle)==1;text=text.replace(needle,'                    gain=None # Common scale is restored inside each forward, exactly as training.\n')
needle="                np.save(a.run/'cpu-control.npy',cpu,allow_pickle=False)"
replacement="""                source_control=protocol['sourceValidationNumericalControl']
                assert sha(source_control['input'])==source_control['inputSha256']
                assert sha(source_control['prediction'])==source_control['predictionSha256']
                known=np.load(source_control['input'],allow_pickle=False)
                expected=np.load(source_control['prediction'],allow_pickle=False)
                observed=forward(known)
                difference=float(np.max(np.abs(observed-expected)))
                assert difference<=1e-6,'Window forward differs from frozen source-validation graph'
                atomic_json(a.run/'source-forward-equivalence.json',dict(
                    state='PASS_TRAINING_VALIDATION_AND_NATURAL_SINGLE_WINDOW_FORWARD_EQUIVALENCE',
                    maximumDifference=difference,sourcePredictionSha256=source_control['predictionSha256'],
                    fixedTolerance=1e-6,referenceTargetsOrTextRead=False))
                np.save(a.run/'cpu-control.npy',cpu,allow_pickle=False)"""
assert text.count(needle)==1;text=text.replace(needle,replacement)
assert not worker.exists();compile(text,str(worker),'exec');worker.write_text(text,encoding='utf-8')
runner=S/'run_window_aligned_separator_20261115.py'
text=(S/'run_supervised_separator_natural_20261115.py').read_text(encoding='utf-8')
assert 'supervised_separator_natural_worker_20261115.py' in text
text=text.replace('supervised_separator_natural_worker_20261115.py',worker.name)
assert not runner.exists();compile(text,str(runner),'exec');runner.write_text(text,encoding='utf-8')
for name in ['audio-only.json','source-binding.json','model-binding.json']:shutil.copyfile(OLD/name,C/name)
protocol=read(OLD/'protocol.json')
candidate=Path(read(T/'candidate-execution.json')['run'])
first=read(T/'validation-audio-only.json')[0]
pred=next(r for r in read(candidate/'state.json')['results'] if r['id']==first['id'])
root=candidate.parent/'natural-window-unit-alignment-r1'
protocol.update(state='FROZEN_SINGLE_TRAIN_INFERENCE_UNIT_ORDER_CORRECTION_BEFORE_FORWARD',
    at=datetime.now().astimezone().isoformat(),controlRun=str(root/'control-r1'),
    separationRun=str(root/'separate-r1'),asrRun=str(root/'asr-r1'),
    sourceValidationNumericalControl=dict(input=first['file'],inputSha256=first['sha256'],
        prediction=pred['file'],predictionSha256=pred['sha256']),
    separation='Same final80 weights, original core and CSS2s/1.5s. Apply the EXACT training/source-validation restore_common_units(torch,raw_two_outputs,input_window) inside every forward BEFORE permutation/OLA. Remove previous whole-clip post-stitch calibration. No per-stream normalization, clipping, gating or model/threshold/lr/window variant.',
    correctnessRepair=dict(trainingOrder='window core -> same common-scale function -> source loss/validation output',
        failedNaturalOrder='window core -> raw-scale permutation/OLA -> whole-clip common scale',
        repairedNaturalOrder='window core -> identical common-scale function -> permutation/OLA',
        previousFailure=str(OLD/'routed-decision.json'),previousFailureSha256=sha(OLD/'routed-decision.json'),
        selectionOrQualityCriteriaChanged=False,weightsChanged=False),
    stop='One operation-order correctness repair only. Preserve the previous failure and exact same natural word/whole-meeting/person gates. If still failing, no additional parameter/model/window/gain/gating variants. No final holdout.')
write(C/'protocol.json',protocol)
binding=read(OLD/'worker-binding.json');binding.update(workerSha256=sha(worker),runnerSha256=sha(runner),protocolSha256=sha(C/'protocol.json'))
for path in [C/'model-binding.json',C/'source-binding.json',Path(first['file']),Path(pred['file'])]:binding['helpers'][str(path)]=sha(path)
write(C/'worker-binding.json',binding)
execution=read(OLD/'asr-execution.json');execution['run']=protocol['asrRun'];write(C/'asr-execution.json',execution)
route=read(OLD/'routed-composition-protocol.json');route.update(at=protocol['at'],
    originalAlwaysOnProtocolSha256=sha(C/'protocol.json'),
    stage='Identical originalNemotron route decisions and original ASR baseline; only trained forward-unit operation order repaired. No new route selection or thresholds.')
write(C/'routed-composition-protocol.json',route)
router=Path('work/score_supervised_separator_natural_router_20261115.py').read_text(encoding='utf-8')
needle='C=Path('+repr(str(OLD))+')';assert needle in router
router=router.replace(needle,'C=Path('+repr(str(C))+')')
Path('work/score_window_aligned_separator_router_20261115.py').write_text(router,encoding='utf-8')
write(T/'window-unit-repair.json',dict(state=protocol['state'],control=str(C),runRoot=str(root),
    at=protocol['at'],trainingWorkerSha256=sha(S/'blind_separator_training_worker_20261115.py'),
    failedNaturalWorkerSha256=sha(S/'supervised_separator_natural_worker_20261115.py'),
    repairedWorkerSha256=sha(worker),inferenceHelperUnchanged=True,weightsChanged=False,
    previousFailureRetained=True,neuralCalls=0,qualityQualified=False))
print(json.dumps(dict(control=str(C),runRoot=str(root))))
