"""Compare exact real-query forward and backward before memory-only correction."""
from pathlib import Path
from datetime import datetime
import argparse, json, os, time, traceback
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read, sha, load_models, load_pair
from companion_tse_training_20261108 import make_spatial_extractor, waveform_supervision
from companion_tse_activation_memory_20261108 import checkpoint_residual_rnns
parser=argparse.ArgumentParser(); parser.add_argument('--control',required=True); parser.add_argument('--protocol',required=True); parser.add_argument('--run-id',required=True); args=parser.parse_args()
C=Path(args.control); P=read(args.protocol); out=C/args.run_id; out.mkdir(exist_ok=False)
assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']: assert sha(row['file'])==row['sha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3); tick=time.perf_counter()
state={'state':'PROVING_ACTIVATION_RECOMPUTATION','pid':os.getpid(),'startedAt':datetime.now().astimezone().isoformat(),'newWeightUpdates':0,'qualityQualified':False,'checks':{}}
def save(): atomic_json(out/'state.json',{**state,'limits':limits.query()},progress=True)
save()
try:
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(P['seed']);assert torch.version.hip and torch.cuda.device_count()==1;assert 'RX 6800 XT' in torch.cuda.get_device_name(0)
    base,_,_=load_models(P,out,torch=torch,with_teacher=False);model=make_spatial_extractor(base,torch=torch).to('cuda:0').train()
    rows=read(P['dataManifest']);example=next(x for x in rows if x['id']==P['probeCases'][0]);assert example['role']=='train'
    pair,profile,peak=load_pair(example,torch=torch,device='cuda:0'); pair.requires_grad_();rng=torch.cuda.get_rng_state()
    torch.cuda.reset_peak_memory_stats();output=model(pair,profile)[0];fidelity,_=waveform_supervision(output,pair[0],example,torch=torch);loss=output.square().mean()+fidelity;loss.backward();torch.cuda.synchronize()
    expected_output=output.detach().cpu();expected_input=pair.grad.detach().cpu();expected_grads={n:p.grad.detach().cpu() for n,p in model.named_parameters() if p.grad is not None};original_peak=torch.cuda.max_memory_allocated();assert len(expected_grads)==562
    del output,fidelity,loss;model.zero_grad(set_to_none=True);pair.grad=None;torch.cuda.empty_cache();torch.cuda.set_rng_state(rng)
    modules=checkpoint_residual_rnns(base,torch=torch);torch.cuda.reset_peak_memory_stats();output=model(pair,profile)[0];fidelity,_=waveform_supervision(output,pair[0],example,torch=torch);loss=output.square().mean()+fidelity;loss.backward();torch.cuda.synchronize()
    def compare(actual,expected):
        value=actual.detach().cpu();error=float((value-expected).abs().max());assert torch.allclose(value,expected,atol=P['gradientAbsoluteTolerance'],rtol=P['gradientRelativeTolerance']),str(error);return error
    assert torch.equal(output.detach().cpu(),expected_output)
    input_error=compare(pair.grad,expected_input);errors=[]
    for name,p in model.named_parameters():
        if p.requires_grad:assert p.grad is not None and name in expected_grads;errors.append(compare(p.grad,expected_grads[name]))
        else:assert p.grad is None
    assert len(errors)==len(expected_grads)
    memory_peak=torch.cuda.max_memory_allocated();assert memory_peak<original_peak
    state['checks']={'case':example['id'],'seconds':example['audioSeconds'],'outputBitIdentical':True,'inputGradientMaximumAbsoluteError':input_error,'parameterGradientMaximumAbsoluteError':max(errors),'parameterGroupsCompared':len(errors),'originalPeakGpuAllocatedBytes':original_peak,'recomputedPeakGpuAllocatedBytes':memory_peak,'recomputedResidualRnnModules':modules,'allFrozenParametersWithoutGrad':True,'newWeightUpdates':0}
    state.update(state='PASS_ACTIVATION_RECOMPUTATION_OUTPUT_AND_GRADIENT_PARITY')
except BaseException as error:state.update(state='ACTIVATION_RECOMPUTATION_PROOF_FAILED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps(state),flush=True)
