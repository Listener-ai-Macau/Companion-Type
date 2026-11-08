"""Complete bounded-size trainable weights plus resumable optimizer state."""
from pathlib import Path
import hashlib,json,os,uuid
from practical_io_20261107 import atomic_json
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save_checkpoint(model,optimizer,*,torch,root,step,protocol_sha,parameter_names):
    from safetensors.torch import save_file,load_file
    folder=Path(root)/('step-%04d'%step);folder.mkdir(parents=True,exist_ok=True);receipt=folder/'checkpoint.json'
    if receipt.exists():raise RuntimeError('Never overwrite a previously completed training checkpoint')
    # Only21.5M actual separation/spatial parameters (~86MiB), not the frozen
    # 4GB recognizer or frozen speaker encoder. No full-model CPU copy.
    values={n:p.detach().cpu().contiguous() for n,p in model.named_parameters() if p.requires_grad};assert list(values)==parameter_names
    weights=folder/('trainable-'+uuid.uuid4().hex+'.safetensors');save_file(values,str(weights));assert weights.stat().st_size<100*1024**2
    restored=load_file(str(weights),device='cpu');assert set(restored)==set(values)
    for n in values:assert torch.equal(values[n],restored[n]),'Checkpoint changed trained values'
    weight_hash=sha(weights);del restored,values
    opt=folder/('optimizer-'+uuid.uuid4().hex+'.pt');part=opt.with_suffix('.part')
    torch.save({'optimizer':optimizer.state_dict(),'torchCpuRng':torch.get_rng_state(),'torchCudaRng':torch.cuda.get_rng_state_all(),'completedSteps':step},part)
    with part.open('r+b') as f:os.fsync(f.fileno())
    os.replace(part,opt);record={'state':'COMPLETE_EXACT_TRAINING_CHECKPOINT','completedSteps':step,'protocolSha256':protocol_sha,'trainableWeights':str(weights),'trainableWeightsSha256':weight_hash,'optimizerState':str(opt),'optimizerStateSha256':sha(opt),'parameterNames':parameter_names,'frozenBaseRequired':True,'savedTeacherWeights':False,'allSavedWeightTensorsExactlyVerified':True};atomic_json(receipt,record);return record
def restore_checkpoint(model,optimizer,record,*,torch,protocol_sha,parameter_names):
    from safetensors.torch import load_file
    assert record['protocolSha256']==protocol_sha and record['parameterNames']==parameter_names
    assert sha(record['trainableWeights'])==record['trainableWeightsSha256'] and sha(record['optimizerState'])==record['optimizerStateSha256']
    values=load_file(record['trainableWeights'],device='cpu');parameters=dict(model.named_parameters());assert set(values)==set(parameter_names)
    with torch.no_grad():
        for name,value in values.items():parameters[name].copy_(value.to(parameters[name].device));assert torch.equal(parameters[name].detach().cpu(),value)
    del values;state=torch.load(record['optimizerState'],map_location='cpu',weights_only=True,mmap=True);assert state['completedSteps']==record['completedSteps'];optimizer.load_state_dict(state['optimizer']);torch.set_rng_state(state['torchCpuRng'].cpu());torch.cuda.set_rng_state_all([x.cpu() for x in state['torchCudaRng']]);return state['completedSteps']
def apply_trainable_weights(model,file,digest,*,torch):
    from safetensors.torch import load_file
    assert sha(file)==digest;values=load_file(file,device='cpu');expected={n for n,p in model.named_parameters() if p.requires_grad};assert set(values)==expected;parameters=dict(model.named_parameters())
    with torch.no_grad():
        for name,value in values.items():parameters[name].copy_(value.to(parameters[name].device));assert torch.equal(parameters[name].detach().cpu(),value)
    return {'state':'PASS_RELOADED_TRAINED_PARAMETERS_EXACTLY','tensorCount':len(values),'weightsSha256':digest}
