"""Reject silent/attenuated shortcut objectives and prove full longest-pair gradients."""
from pathlib import Path
from datetime import datetime
import argparse,json,os,time,traceback
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_tse_model_io_20261108 import read,sha,load_models,tensor_hash
from companion_tse_training_20261108 import make_spatial_extractor
from companion_tse_activation_memory_20261108 import checkpoint_residual_rnns
from companion_tse_source_runtime_20261108 import unit_inputs,unit_objective
from companion_tse_source_objective_20261108 import positive_loss,consistency_loss,absence_loss
parser=argparse.ArgumentParser();parser.add_argument('--control',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--run-id',required=True);args=parser.parse_args();C=Path(args.control);P=read(args.protocol);out=C/args.run_id;out.mkdir(exist_ok=False);assert sha(__file__)==P['workerSha256']
for row in P['sourceFiles']:assert sha(row['file'])==row['sha256']
limits=WorkerLimits(cpu_percent=10,memory_bytes=2*1024**3);tick=time.perf_counter();state={'state':'PROVING_SOURCE_PRESERVATION_OBJECTIVE','pid':os.getpid(),'newWeightUpdates':0,'checks':{},'qualityQualified':False};save=lambda:atomic_json(out/'state.json',{**state,'limits':limits.query()},progress=True);save()
try:
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(P['seed']);assert torch.version.hip and torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0)
    units=read(C/'training-units.json');profiles={x['id']:x for x in read(C/'profiles.json')};example=max([x for x in units if x['kind']=='known_additive_mixture'],key=lambda x:x['mixture']['audioSeconds']);pair,enrollments,targets,peak=unit_inputs(example,profiles,torch=torch);values=[]
    for target,other in [(targets[0],targets[1]),(targets[1],targets[0])]:
        perfect=float(positive_loss(target,target,torch=torch));half=float(positive_loss(target*.5,target,torch=torch));silent=torch.zeros_like(target,requires_grad=True);silence=positive_loss(silent,target,torch=torch);gradient=torch.autograd.grad(silence,silent)[0];wrong=float(positive_loss(other,target,torch=torch));directional=float((gradient*target).sum());assert perfect==0 and half>perfect and float(silence)>half and wrong>perfect and directional<0 and torch.isfinite(gradient).all();values.append({'perfectSourceLoss':perfect,'halfVolumeLoss':half,'silentOutputLoss':float(silence),'wrongSpeakerLoss':wrong,'silentOutputGradientTowardTargetDirectionalDerivative':directional})
    assert float(consistency_loss(targets[0],targets[1],pair[0,0],torch=torch))<1e-6;assert float(absence_loss(torch.zeros_like(targets[0]),pair[0,0],torch=torch))==0
    state['checks']['antiSilenceAndAttenuation']=values;state.update(state='LOADING_ORIGINAL_COMPLETE_BACKBONE_FOR_LONGEST_PAIR');save();base,_,_=load_models(P,out,torch=torch,with_teacher=False);checkpoint_residual_rnns(base,torch=torch);model=make_spatial_extractor(base,torch=torch).cuda().train();speaker_hash=tensor_hash(list(base.spk_model.named_parameters())+list(base.spk_model.named_buffers()));torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();state['state']='PROVING_COMPLETE_LONGEST_PAIRED_FORWARD_BACKWARD';save();estimates=[model(pair,profile)[0] for profile in enrollments];loss=unit_objective(example,estimates,targets,pair,torch=torch);assert torch.isfinite(loss);loss.backward();parameters=[(n,p) for n,p in model.named_parameters() if p.requires_grad];assert len(parameters)==562 and all(p.grad is not None and torch.isfinite(p.grad).all() for n,p in parameters);spatial=sum(float(p.grad.norm()) for n,p in parameters if n.startswith('spatial.'));assert spatial>0 and not any(p.grad is not None for p in base.spk_model.parameters());assert tensor_hash(list(base.spk_model.named_parameters())+list(base.spk_model.named_buffers()))==speaker_hash
    state['checks']['longestPairedGraph']={'id':example['id'],'audioSeconds':example['mixture']['audioSeconds'],'twoTargetGraphsInOneLoss':True,'parameterGroupsWithFiniteGradient':len(parameters),'spatialGradientNormSum':spatial,'loss':float(loss),'gpuPeakAllocatedBytes':torch.cuda.max_memory_allocated(),'gpuPeakReservedBytes':torch.cuda.max_memory_reserved(),'speakerEncoderFrozen':True,'recognizerLoaded':False};state.update(state='PASS_SOURCE_OBJECTIVE_ANTI_COLLAPSE_AND_LONGEST_PAIRED_GRADIENTS')
except BaseException as error:state.update(state='SOURCE_SUPERVISION_PROOF_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.perf_counter()-tick,limits=limits.query());atomic_json(out/'state.json',state);print(json.dumps(state),flush=True)
