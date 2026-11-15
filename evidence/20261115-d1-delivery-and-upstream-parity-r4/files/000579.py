"""Prove feature parity, derivatives, causal-label alignment and zero-impact adapters."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read,sha,load_models,load_pair,tensor_hash
from companion_tse_training_20261108 import differentiable_fbank,make_spatial_extractor,target_text,teacher_batch,teacher_loss,waveform_supervision
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();C=Path(args.control);P=read(args.protocol);out=C/args.run_id;out.mkdir(exist_ok=False)
assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();state={'state':'PREPARING_DIFFERENTIABLE_TSE_PROOF','pid':os.getpid(),'startedAt':datetime.now().astimezone().isoformat(),'newWeightUpdates':0,'protocolSha256':sha(args.protocol),'checks':{},'qualityQualified':False}
def save():state['limits']=limits.query();atomic_json(out/'state.json',state,progress=True)
save()
try:
    import numpy as np
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(P['seed']);assert torch.version.hip and torch.cuda.device_count()==1;gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030');torch.cuda.set_device(0)
    state.update(state='LOADING_ONE_EXTRACTOR_AND_FROZEN_TEACHER',gpu=gpu.name);save();base,teacher,processor=load_models(P,out,torch=torch)
    rows=read(P['dataManifest']);selected=[next(x for x in rows if x['id']==identity) for identity in P['probeCases']];assert all(x['role']=='train' for x in selected)
    # The frontend's native function detaches to NumPy. Compare its values to
    # the connected implementation, including short/non-hop-aligned inputs.
    parity=[]
    for length in [8000,32123,60000]:
        rng=np.random.default_rng(P['seed']+length);audio=rng.normal(0,.03,length).astype(np.float32);official=processor.feature_extractor(audio,sampling_rate=16000,padding=True,return_attention_mask=True,device='cuda:0');wave=torch.tensor(audio,device='cuda:0',requires_grad=True);features,mask=differentiable_fbank(wave,processor.feature_extractor,torch=torch)
        expected=official['input_features'].to('cuda:0');error=float((features-expected).abs().max());assert error<=P['featureMaximumAbsoluteError'];assert torch.equal(features.to(torch.bfloat16),expected.to(torch.bfloat16)) and torch.equal(mask.cpu(),official['attention_mask']);g=torch.autograd.grad(features.square().mean(),wave)[0];assert torch.isfinite(g).all() and float(g.abs().sum())>0
        parity.append({'samples':length,'maximumAbsoluteError':error,'sameBf16Values':True,'sameAttentionMask':True,'gradientAbsoluteSum':float(g.abs().sum())})
    state['checks']['featureForwardParity']=parity;state.update(state='CHECKING_FEATURE_DIRECTIONAL_DERIVATIVES');save()
    generator=torch.Generator().manual_seed(P['seed']);wave=(torch.randn(9001,generator=generator,dtype=torch.float64)*.03).requires_grad_();features,_=differentiable_fbank(wave,processor.feature_extractor,torch=torch);weights=torch.sin(torch.arange(features.numel(),dtype=torch.float64)).reshape(features.shape);objective=(features*weights).mean();gradient=torch.autograd.grad(objective,wave)[0];directions=[]
    for _ in range(3):
        direction=torch.randn(wave.shape,generator=generator,dtype=torch.float64);direction/=direction.norm();eps=P['finiteDifferenceEpsilon']
        with torch.no_grad():plus=(differentiable_fbank(wave+eps*direction,processor.feature_extractor,torch=torch)[0]*weights).mean();minus=(differentiable_fbank(wave-eps*direction,processor.feature_extractor,torch=torch)[0]*weights).mean()
        numeric=float((plus-minus)/(2*eps));analytic=float((gradient*direction).sum());error=abs(numeric-analytic);assert error<=P['finiteDifferenceAbsoluteTolerance']+P['finiteDifferenceRelativeTolerance']*abs(numeric)
        directions.append({'numeric':numeric,'analytic':analytic,'absoluteError':error})
    state['checks']['independentDirectionalFiniteDifferences']=directions;save()
    example=selected[0];pair,profile,peak=load_pair(example,torch=torch,device='cuda:0');base.eval()
    with torch.no_grad():original=base(pair[:,0],profile)[0]
    extractor=make_spatial_extractor(base,torch=torch).to('cuda:0').eval()
    with torch.no_grad():adapted=extractor(pair,profile);mono=extractor(pair[:,:1],profile)
    assert torch.equal(original,adapted) and torch.equal(original,mono);state['checks']['zeroSpatialAdapters']={'pairedOutputExactlyOriginal':True,'monoFallbackExactlyOriginal':True,'newSpatialParameters':sum(p.numel() for p in extractor.spatial.parameters()),'trainableActualSeparationParameters':sum(p.numel() for p in extractor.parameters() if p.requires_grad)};save()
    # Verify causal teacher forcing against the official native labels/loss.
    wave=original[0].detach()*peak;batch=teacher_batch(wave,target_text(example),processor,torch=torch)
    with torch.no_grad():
        native=teacher(input_ids=batch['input_ids'],attention_mask=batch['attention_mask'],input_features=batch['input_features'].to(teacher.dtype),input_features_mask=batch['input_features_mask'],labels=batch['labels'],use_cache=False).loss;selected_loss=teacher_loss(teacher,batch,torch=torch)
    assert torch.allclose(native,selected_loss,atol=P['teacherLossAbsoluteTolerance'],rtol=1e-5);state['checks']['teacherForcingLabels']={'officialNativeLoss':float(native),'selectedTargetOnlyLoss':float(selected_loss),'prefixLabelsIgnored':bool((batch['labels'][:,:batch['prefix_length']]==-100).all()),'targetTokens':batch['target_ids'].numel(),'correctOneTokenCausalShift':True};save()
    versions={name:p._version for name,p in teacher.named_parameters()};speaker_before=tensor_hash(list(base.spk_model.named_parameters())+list(base.spk_model.named_buffers()));gradients=[];extractor.train()
    for example in selected:
        extractor.zero_grad(set_to_none=True);pair,profile,peak=load_pair(example,torch=torch,device='cuda:0');output=extractor(pair,profile)[0];output.retain_grad();batch=teacher_batch(output*peak,target_text(example),processor,torch=torch);ce=teacher_loss(teacher,batch,torch=torch);fidelity,scope=waveform_supervision(output,pair[0],example,torch=torch);loss=ce+fidelity;assert torch.isfinite(loss)
        loss.backward();parameters=[(n,p) for n,p in extractor.named_parameters() if p.requires_grad];active=[(n,float(p.grad.detach().float().norm())) for n,p in parameters if p.grad is not None];assert active and all(np.isfinite(v) for n,v in active);assert any(n.startswith('spatial.') and v>0 for n,v in active);assert output.grad is not None and torch.isfinite(output.grad).all() and float(output.grad.abs().sum())>0
        assert not any(p.grad is not None for p in teacher.parameters()) and not any(p.grad is not None for p in base.spk_model.parameters());assert all(p._version==versions[name] for name,p in teacher.named_parameters());assert tensor_hash(list(base.spk_model.named_parameters())+list(base.spk_model.named_buffers()))==speaker_before
        gradients.append({'id':example['id'],'category':example['category'],'teacherCe':float(ce),'waveformLoss':float(fidelity),'waveformScope':scope,'waveformGradientAbsoluteSum':float(output.grad.abs().sum()),'separationParameterGroupsWithGradient':len(active),'spatialGradientNormSum':sum(v for n,v in active if n.startswith('spatial.')),'teacherAndSpeakerEncoderFrozen':True});state['checks']['gradientCases']=gradients;state['state']='PROVING_GRADIENTS_WITHOUT_WEIGHT_UPDATES';save();del output,loss,ce,fidelity,batch,pair,profile
    extractor.zero_grad(set_to_none=True);state.update(state='PASS_TRAINING_GRAPH_PARITY_LABELS_GRADIENTS_AND_FROZEN_TEACHER',newWeightUpdates=0,gradientCases=len(gradients),trainingQualityQualified=False)
except BaseException as error:state.update(state='GRADIENT_PROOF_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps(state),flush=True)
