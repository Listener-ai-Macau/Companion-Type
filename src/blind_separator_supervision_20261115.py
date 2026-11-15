"""Fixed blind PIT source-aggregated SDR and bounded full checkpoints.

Loss: SA-SDR equation9 with the paper's30dB soft maximum, equations2/9.
https://arxiv.org/html/2110.15581v2
No all-zero target is used; digital silence has the verified zero bypass.
"""
from pathlib import Path
from types import SimpleNamespace
import json,math
from companion_community1_adapter_20261115 import sha
from companion_tse_checkpoint_streamed_20261108 import write_archive
from moss_streamed_weights_20261104 import load_streamed_weights
from companion_local_pcm_session_20261114 import atomic_json

def restore_common_units(torch,estimate,mixture):
    input_energy=mixture.square().mean()
    output_energy=estimate.sum(0).square().mean()
    # Exact cancellation/zero has no identifiable common scale. Identity
    # scale here keeps loss gradients finite rather than inventing a voice.
    if float(output_energy.detach())==0:return estimate
    return estimate*(input_energy/output_energy).sqrt()

def pit_source_aggregated_sdr(torch,estimate,target):
    assert estimate.shape==target.shape and target.shape[0]==2
    energy=target.square().sum();assert float(energy.detach())>0
    direct=(estimate-target).square().sum();swapped=(estimate.flip(0)-target).square().sum()
    swap=bool(swapped.detach()<direct.detach());error=swapped if swap else direct
    # Source aggregation handles a truly inactive one of two targets. The
    # fixed1e-3 is the paper's30dB soft maximum, not a fitted silence gate.
    return 10*torch.log10(error/energy+.001),swap,error/energy

def loss_controls(torch):
    x=torch.linspace(-.2,.2,4096,device='cuda:0');target=torch.stack([x,torch.zeros_like(x)])
    perfect=pit_source_aggregated_sdr(torch,target,target)[0]
    duplicate=pit_source_aggregated_sdr(torch,torch.stack([x/2,x/2]),target)[0]
    zero=pit_source_aggregated_sdr(torch,torch.zeros_like(target),target)[0]
    assert float(perfect)<float(duplicate)<float(zero)
    assert abs(float(perfect)+30)<1e-4
    train=torch.zeros_like(target,requires_grad=True);loss,_,_=pit_source_aggregated_sdr(torch,train,target);loss.backward()
    assert torch.isfinite(train.grad).all() and bool((train.grad!=0).any())
    reverse=pit_source_aggregated_sdr(torch,target.flip(0),target)[0]
    assert torch.equal(reverse,perfect)
    return dict(perfectDb=float(perfect),duplicatedSoloDb=float(duplicate),zeroOutputOnSpeechDb=float(zero),
                swappedOutputsSameLoss=True,zeroOutputHasFiniteNonzeroGradient=True,
                silenceShortcutNotRewarded=True,allSilentReferenceExcluded=True,fixedSoftMaximumDb=30)

def load_trainable_core(protocol,torch):
    from accelerate import init_empty_weights
    from models.mossformer2_ss.mossformer2 import MossFormer2_SS_16K
    import inspect
    assert Path(inspect.getfile(MossFormer2_SS_16K)).resolve().is_relative_to(Path(protocol['sourceRoot']).resolve())
    args=SimpleNamespace(encoder_embedding_dim=512,mossformer_sequence_dim=512,num_mossformer_layer=24,encoder_kernel_size=16,num_spks=2)
    payload=torch.load(protocol['checkpoint'],map_location='cpu',weights_only=True,mmap=True)
    values=payload['model'];del payload
    with init_empty_weights(include_buffers=False):model=MossFormer2_SS_16K(args).model
    original_trainability={n:p.requires_grad for n,p in model.named_parameters()}
    assert set(model.state_dict())==set(values)
    model.load_state_dict(values,strict=True,assign=True)
    assert all(torch.equal(v,values[n]) for n,v in model.state_dict().items())
    model.to('cuda:0').eval()
    for n,p in model.named_parameters():p.requires_grad_(original_trainability[n])
    return model,dict(parameters=sum(p.numel() for p in model.parameters()),
                      trainableParameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
                      originalTrainabilityPreserved=True,allOriginalCheckpointTensorsExact=True,
                      originalNonlearnedRotaryFrequenciesNotUnfrozen=True)

def checkpoint(model,optimizer,torch,folder,*,updates,examples,protocol_sha,order):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    groups=[];current={};size=0
    for name,value in sorted(model.state_dict().items()):
        value=value.detach();n=value.numel()*value.element_size()
        assert n<=24*1024**2
        if current and size+n>24*1024**2:groups.append(current);current={};size=0
        current[name]=value;size+=n
    if current:groups.append(current)
    shards=[]
    for index,values in enumerate(groups):
        target=folder/('model-'+str(index).zfill(2)+'.safetensors');proof=write_archive(target,values,torch=torch)
        shards.append(dict(file=str(target),sha256=proof['fileSha256'],keys=list(values),bytes=target.stat().st_size))
    opt=optimizer.state_dict();values={};schema={}
    for index,fields in opt['state'].items():
        schema[str(index)]={}
        for key,value in fields.items():
            assert isinstance(value,torch.Tensor);name='optimizer.'+str(index)+'.'+key;values[name]=value.detach()
            schema[str(index)][key]=dict(tensor=name,device=value.device.type)
    values['rng.cpu']=torch.get_rng_state()
    for i,value in enumerate(torch.cuda.get_rng_state_all()):values['rng.cuda.'+str(i)]=value
    optimizer_file=folder/'optimizer-rng.safetensors';proof=write_archive(optimizer_file,values,torch=torch)
    result=dict(state='COMPLETE_BYTE_VERIFIED_BLIND_SEPARATOR_FULL_CHECKPOINT',optimizerUpdates=updates,
        completedExamples=examples,protocolSha256=protocol_sha,modelShards=shards,
        optimizerFile=str(optimizer_file),optimizerSha256=proof['fileSha256'],optimizerSchema=schema,
        paramGroups=opt['param_groups'],order=order,maximumConcurrentArchiveScratchBytes=3*1024**2,
        allSavedTensorBytesVerified=True,selectedByValidation=False)
    atomic_json(folder/'checkpoint.json',result);return result

def apply_full_checkpoint(model,record,torch):
    expected=set(model.state_dict());loaded=set();live=model.state_dict()
    with torch.no_grad():
        for shard in record['modelShards']:
            assert sha(shard['file'])==shard['sha256']
            values,proof=load_streamed_weights(shard['file'],torch=torch,device='cuda:0',expected_sha256=shard['sha256'],chunk_bytes=1024**2)
            assert set(values)==set(shard['keys']) and not loaded&set(values)
            for name,value in values.items():live[name].copy_(value);assert torch.equal(live[name],value)
            loaded.update(values);del values
    assert loaded==expected
    return dict(state='PASS_FULL_SHARDED_SEPARATOR_CHECKPOINT_RELOADED_EXACT',tensors=len(loaded),shards=len(record['modelShards']))

def restore_optimizer(model,optimizer,record,torch,protocol_sha):
    assert record['protocolSha256']==protocol_sha
    apply_full_checkpoint(model,record,torch)
    values,_=load_streamed_weights(record['optimizerFile'],torch=torch,device='cuda:0',expected_sha256=record['optimizerSha256'],chunk_bytes=1024**2)
    state={}
    for index,fields in record['optimizerSchema'].items():
        state[int(index)]={key:values[meta['tensor']].cpu() if meta['device']=='cpu' else values[meta['tensor']] for key,meta in fields.items()}
    groups=record['paramGroups']
    for group in groups:group['betas']=tuple(group['betas'])
    optimizer.load_state_dict(dict(state=state,param_groups=groups));torch.set_rng_state(values['rng.cpu'].cpu())
    torch.cuda.set_rng_state_all([values['rng.cuda.'+str(i)].cpu() for i in range(torch.cuda.device_count())])
    return record['completedExamples']
