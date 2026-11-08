"""Derive a separately pinned training worker after recomputation parity passes."""
from pathlib import Path
from datetime import datetime
import hashlib,json
from practical_io_20261107 import atomic_json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261108-tse-supervised-adaptation';E=Path('E:/CodexData/Companion/.model-cache/tse-supervised-adaptation-20261108')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=C/'training-protocol-r1.json';P=read(old);assert all(sha(x['file'])==x['sha256'] for x in P['sourceFiles'])
proof=C/'activation-proof-r1/state.json';G=read(proof);assert G['state']=='PASS_ACTIVATION_RECOMPUTATION_OUTPUT_AND_GRADIENT_PARITY' and G['newWeightUpdates']==0
source=(S/'tse_supervised_train_worker_20261108.py').read_text(encoding='utf8')
source=source.replace('from companion_tse_checkpoint_20261108 import save_checkpoint,restore_checkpoint','from companion_tse_checkpoint_20261108 import save_checkpoint,restore_checkpoint\nfrom companion_tse_activation_memory_20261108 import checkpoint_residual_rnns')
oldline="base,teacher,processor=load_models(P,out,torch=torch);model=make_spatial_extractor(base,torch=torch).to('cuda:0');rows=read(P['dataManifest']);"
replacement="""base,teacher,processor=load_models(P,out,torch=torch)
    def memory_point(label):
        import psutil
        torch.cuda.synchronize()
        row={'at':datetime.now().astimezone().isoformat(),'phase':label,'gpuAllocatedBytes':torch.cuda.memory_allocated(),'gpuReservedBytes':torch.cuda.memory_reserved(),'gpuFreeAndTotalBytes':list(torch.cuda.mem_get_info()),'systemAvailableBytes':psutil.virtual_memory().available}
        with (out/'preflight-memory.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row)+'\\n')
        state.update(state=label,lastMemoryPoint=row);save()
    def observe_rnn(name,edge):
        if state.get('recordRnnMemory',False):memory_point('PREFLIGHT_RNN_'+name+'_'+edge)
    modules=checkpoint_residual_rnns(base,torch=torch,observer=observe_rnn);model=make_spatial_extractor(base,torch=torch).to('cuda:0');memory_point('EXACT_MODELS_READY_WITH_RECOMPUTATION');rows=read(P['dataManifest']);"""
assert oldline in source;source=source.replace(oldline,replacement)
oldpre="example=max(train,key=lambda x:x['audioSeconds']);model.train();pair,profile,peak=load_pair(example,torch=torch,device='cuda:0');estimate=model(pair,profile)[0];loss,ce,fidelity,scope=losses(example,estimate,pair,peak);loss.backward();assert torch.isfinite(loss);model.zero_grad(set_to_none=True);"
newpre="""example=max(train,key=lambda x:x['audioSeconds']);state['preflightId']=example['id'];state['recordRnnMemory']=True;model.train();torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();pair,profile,peak=load_pair(example,torch=torch,device='cuda:0');memory_point('PREFLIGHT_FULL_LONGEST_EXTRACTOR_FORWARD');estimate=model(pair,profile)[0];memory_point('PREFLIGHT_FULL_LONGEST_TEACHER_LOSS');loss,ce,fidelity,scope=losses(example,estimate,pair,peak);memory_point('PREFLIGHT_FULL_LONGEST_BACKWARD');loss.backward();assert torch.isfinite(loss);model.zero_grad(set_to_none=True);memory_point('PREFLIGHT_FULL_LONGEST_BACKWARD_COMPLETE');state['recordRnnMemory']=False;"""
assert oldpre in source;source=source.replace(oldpre,newpre)
needle="del pair,profile,estimate,loss,ce,fidelity\n        before=validation_pass('baseline')"
assert needle in source;source=source.replace(needle,"del pair,profile,estimate,loss,ce,fidelity;torch.cuda.empty_cache()\n        before=validation_pass('baseline')")
worker=S/'tse_supervised_memory_train_worker_20261108.py';assert not worker.exists();worker.write_text(source,encoding='utf8',newline='\n')
extra=[S/'companion_tse_activation_memory_20261108.py',worker,proof,C/'activation-memory-proof-protocol-r1.json']
updated={**P,'at':datetime.now().astimezone().isoformat(),'workerSha256':sha(worker),'sourceFiles':[*P['sourceFiles'],*[{'file':str(p),'sha256':sha(p)} for p in extra]],'activationRecomputationProof':str(proof),'activationRecomputationProofSha256':sha(proof),'supersedesZeroUpdateMemoryProtocol':{'file':str(old),'sha256':sha(old)},'checkpointRoot':str(E/'checkpoints-r2'),'audioRoot':str(E/'validation-audio-r2'),'memoryCorrection':'Only residual-RNN intermediate activations are recomputed during backward. Complete pinned weights, all data/labels, one-pass order, optimizer and learning rates remain identical. Phase/GPU/physical-RAM telemetry added. Output and all 562 trainable parameter gradient groups compared before this trial.'}
for key in ['seed','trainingOrder','validationOrder','learningRate','weightDecay','gradientClipNorm','epochs','loss','qualityDecision','lossComparisonTolerance']:assert updated[key]==P[key]
target=C/'training-protocol-r2.json';assert not target.exists();atomic_json(target,updated)
print(json.dumps({'state':'FROZEN_SAME_TRIAL_MEMORY_CORRECTION','protocol':str(target),'worker':str(worker),'newWeightUpdates':0}),flush=True)
