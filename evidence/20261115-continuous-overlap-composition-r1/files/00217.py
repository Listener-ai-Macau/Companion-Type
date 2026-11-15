"""Prepare the already specified natural-word gate only after source gate passes."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
T=D/'supervised-blind-separation-r1';OLD=D/'blind-separation-composition-r1'
C=T/'natural-composition-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert read(T/'source-decision.json')['state']=='PASS_SOURCE_GATE_NATURAL_WORD_EVALUATION_REQUIRED'
assert not C.exists();C.mkdir()
train=read(T/'protocol.json');trained=Path(train['trainRun'])/'latest-checkpoint.json'
assert read(Path(train['trainRun'])/'state.json')['state']=='COMPLETE_ONE_FIXED_BLIND_SEPARATOR_TRAINING_PASS'
final=read(trained);assert final['optimizerUpdates']==80
worker=S/'supervised_separator_natural_worker_20261115.py'
text=(S/'blind_separation_worker_20261115.py').read_text(encoding='utf-8')
old='            save(weightProof=weight_proof)'
new="""            from blind_separator_supervision_20261115 import apply_full_checkpoint
            model.to('cuda:0')
            trained_proof=apply_full_checkpoint(model,read(protocol['trainedCheckpoint']),torch)
            model.to('cpu')
            save(weightProof=weight_proof,trainedFullCheckpointReload=trained_proof,
                 trainingUpdatesBeforeValidation=80)
"""
assert text.count(old)==1;text=text.replace(old,new)
old='                    folder=a.run/\'streams\'/case[\'id\'];folder.mkdir(parents=True,exist_ok=False)'
new="""                    raw_sum=out.sum(0).astype(np.float64)
                    e=float(np.mean(raw_sum**2))
                    gain=float(np.sqrt(np.mean(samples.astype(np.float64)**2)/e)) if e>0 else 1.
                    out=(out*gain).astype(np.float32)
                    folder=a.run/'streams'/case['id'];folder.mkdir(parents=True,exist_ok=False)
"""
assert text.count(old)==1;text=text.replace(old,new)
text=text.replace('stitching=trace,allFramesPreserved=True,perStreamGainApplied=False,',
    'stitching=trace,allFramesPreserved=True,perStreamGainApplied=False,sharedOutputUnitGain=gain,')
assert not worker.exists();compile(text,str(worker),'exec');worker.write_text(text,encoding='utf-8')
runner=S/'run_supervised_separator_natural_20261115.py'
text=(S/'run_blind_separation_composition_20261115.py').read_text(encoding='utf-8')
assert 'blind_separation_worker_20261115.py' in text
text=text.replace('blind_separation_worker_20261115.py',worker.name)
assert not runner.exists();compile(text,str(runner),'exec');runner.write_text(text,encoding='utf-8')
for name in ['audio-only.json','source-binding.json','model-binding.json']:
    shutil.copyfile(OLD/name,C/name)
protocol=read(OLD/'protocol.json');root=Path(train['trainRun']).parent/'natural-composition-r1'
protocol.update(state='FROZEN_FIXED_FINAL_SOURCE_ADAPTED_SEPARATOR_NATURAL_WORD_GATE',
    at=datetime.now().astimezone().isoformat(),trainedCheckpoint=str(trained),
    trainedCheckpointSha256=sha(trained),sourceDecision=str(T/'source-decision.json'),
    sourceDecisionSha256=sha(T/'source-decision.json'),
    controlRun=str(root/'control-r1'),separationRun=str(root/'separate-r1'),asrRun=str(root/'asr-r1'),
    newTraining=False,trainingUpdatesBeforeValidation=80,
    separation='Same original core/CSS2s/1.5s; fixed final80 source-adapted full weights only. Same shared mixture/output-sum RMS restoration applied after complete waveform stitching; both raw-float streams retained, no per-stream amplification, clipping, identity/reference/word gate or tuning.',
    productDefaultChanged=False)
write(C/'protocol.json',protocol)
binding=read(OLD/'worker-binding.json');helpers=binding['helpers']
helpers.pop(str(OLD/'model-binding.json'),None);helpers.pop(str(OLD/'source-binding.json'),None)
for path in [C/'model-binding.json',C/'source-binding.json',trained,T/'source-decision.json',S/'blind_separator_supervision_20261115.py',S/'companion_tse_checkpoint_streamed_20261108.py',S/'moss_streamed_weights_20261104.py']:
    helpers[str(path)]=sha(path)
for item in final['modelShards']:helpers[item['file']]=item['sha256']
write(C/'worker-binding.json',dict(workerSha256=sha(worker),runnerSha256=sha(runner),
    protocolSha256=sha(C/'protocol.json'),helpers=helpers))
prefix=read(OLD/'asr-execution.json')
write(C/'asr-execution.json',dict(run=protocol['asrRun'],
    nativePrefixControl=prefix['nativePrefixControl'],nativePrefixControlSha256=prefix['nativePrefixControlSha256']))
route=read(OLD/'routed-composition-protocol.json')
route.update(at=datetime.now().astimezone().isoformat(),
    stage='Identical already frozen original whole-audio detector predictions and route decisions, copied before natural validation for fixed final80 source-adapted separator. No new routing selection.',
    originalAlwaysOnProtocolSha256=sha(C/'protocol.json'),trainingUpdatesBeforeValidation=80)
write(C/'routed-composition-protocol.json',route)
# Keep the original all-word scorer unchanged; only its directory differs.
router=Path('work/score_routed_blind_separation_20261115.py').read_text(encoding='utf-8')
old="C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/blind-separation-composition-r1'"
assert old in router
router=router.replace(old,'C=Path('+repr(str(C))+')')
target=Path('work/score_supervised_separator_natural_router_20261115.py');assert not target.exists()
target.write_text(router,encoding='utf-8')
print(json.dumps(dict(control=str(C),runRoot=str(root),worker=str(worker),routedCases=sum(r['useBothSeparatedStreams'] for r in route['cases']))))
