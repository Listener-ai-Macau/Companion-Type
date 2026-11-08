"""Bounded standard safetensors archives for weights, AdamW state and RNG."""
from pathlib import Path
import hashlib,json,math,os,struct,uuid
from practical_io_20261107 import atomic_json
from moss_streamed_weights_20261104 import load_streamed_weights
CHUNK=1024**2
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def metadata(values,torch):
    types={torch.float32:'F32',torch.bfloat16:'BF16',torch.float16:'F16',torch.float64:'F64',torch.int64:'I64',torch.int32:'I32',torch.uint8:'U8',torch.bool:'BOOL'};result={};offset=0
    for name,value in sorted(values.items()):
        assert value.is_contiguous();size=value.numel()*value.element_size();result[name]={'dtype':types[value.dtype],'shape':list(value.shape),'data_offsets':[offset,offset+size]};offset+=size
    return result
def verify_archive(path,values,*,torch):
    expected=metadata(values,torch);scratch=bytearray(CHUNK);returned=bytearray(CHUNK);destination=torch.frombuffer(returned,dtype=torch.uint8)
    with Path(path).open('rb',buffering=0) as f:
        length=struct.unpack('<Q',f.read(8))[0];assert 0<length<1024**2;header=json.loads(f.read(length));assert set(header)==set(expected)
        ordered=sorted(header.items(),key=lambda x:x[1]['data_offsets'][0]);offset=0
        for name,meta in ordered:
            assert meta['dtype']==expected[name]['dtype'] and meta['shape']==expected[name]['shape'];start,end=meta['data_offsets'];assert start==offset and end-start==values[name].numel()*values[name].element_size();flat=values[name].detach().reshape(-1).view(torch.uint8)
            for at in range(0,end-start,CHUNK):
                take=min(CHUNK,end-start-at);view=memoryview(scratch)[:take];assert f.readinto(view)==take;destination[:take].copy_(flat[at:at+take],non_blocking=False);assert memoryview(returned)[:take]==view,'Checkpoint tensor bytes differ'
            offset=end
        assert f.tell()==Path(path).stat().st_size
    return {'state':'PASS_ALL_ARCHIVE_TENSOR_BYTES_MATCH_DEVICE','tensorCount':len(values),'maximumCpuScratchBytes':2*CHUNK,'fileSha256':sha(path)}
def write_archive(path,values,*,torch):
    path=Path(path);assert not path.exists();header=json.dumps(metadata(values,torch),separators=(',',':')).encode();header+=b' '*((-len(header))%8);buffer=bytearray(CHUNK);cpu=torch.frombuffer(buffer,dtype=torch.uint8)
    with path.open('xb',buffering=0) as f:
        f.write(struct.pack('<Q',len(header)));f.write(header)
        for name,value in sorted(values.items()):
            flat=value.detach().reshape(-1).view(torch.uint8)
            for at in range(0,flat.numel(),CHUNK):
                take=min(CHUNK,flat.numel()-at);cpu[:take].copy_(flat[at:at+take],non_blocking=False);assert f.write(memoryview(buffer)[:take])==take
        os.fsync(f.fileno())
    return verify_archive(path,values,torch=torch)
def save_checkpoint(model,optimizer,*,torch,root,step,protocol_sha,parameter_names):
    folder=Path(root)/('step-%04d'%step);folder.mkdir(parents=True,exist_ok=True);receipt=folder/'checkpoint.json';assert not receipt.exists()
    values={n:p.detach() for n,p in model.named_parameters() if p.requires_grad};assert list(values)==parameter_names;weights=folder/('trainable-'+uuid.uuid4().hex+'.safetensors');proof=write_archive(weights,values,torch=torch);assert weights.stat().st_size<100*1024**2
    state=optimizer.state_dict();opt_values={};schema={}
    for index,fields in state['state'].items():
        schema[str(index)]={}
        for key,value in fields.items():
            assert isinstance(value,torch.Tensor);name='optimizer.'+str(index)+'.'+key;opt_values[name]=value.detach();schema[str(index)][key]={'tensor':name,'originalDeviceType':value.device.type}
    opt_values['rng.cpu']=torch.get_rng_state()
    for i,value in enumerate(torch.cuda.get_rng_state_all()):opt_values['rng.cuda.'+str(i)]=value
    opt=folder/('optimizer-'+uuid.uuid4().hex+'.safetensors');opt_proof=write_archive(opt,opt_values,torch=torch)
    record={'state':'COMPLETE_EXACT_TRAINING_CHECKPOINT','completedSteps':step,'protocolSha256':protocol_sha,'trainableWeights':str(weights),'trainableWeightsSha256':proof['fileSha256'],'optimizerState':str(opt),'optimizerStateSha256':opt_proof['fileSha256'],'optimizerStateFormat':'bounded-safetensors-v1','optimizerStateSchema':schema,'optimizerParamGroups':state['param_groups'],'cudaRngCount':torch.cuda.device_count(),'parameterNames':parameter_names,'frozenBaseRequired':True,'savedTeacherWeights':False,'allSavedWeightTensorsExactlyVerified':True,'allOptimizerAndRngTensorBytesExactlyVerified':True,'maximumCpuScratchBytes':2*CHUNK};atomic_json(receipt,record);return record
def apply_trainable_weights(model,file,digest,*,torch):
    assert sha(file)==digest;values,proof=load_streamed_weights(file,torch=torch,device='cuda:0',expected_sha256=digest,chunk_bytes=CHUNK);parameters=dict(model.named_parameters());expected={n for n,p in parameters.items() if p.requires_grad};assert set(values)==expected
    with torch.no_grad():
        for name,value in values.items():parameters[name].copy_(value);assert torch.equal(parameters[name],value)
    return {'state':'PASS_RELOADED_TRAINED_PARAMETERS_EXACTLY','tensorCount':len(values),'weightsSha256':digest,'streamed':proof}
def restore_checkpoint(model,optimizer,record,*,torch,protocol_sha,parameter_names):
    assert record['protocolSha256']==protocol_sha and record['parameterNames']==parameter_names;apply_trainable_weights(model,record['trainableWeights'],record['trainableWeightsSha256'],torch=torch);assert sha(record['optimizerState'])==record['optimizerStateSha256']
    if record.get('optimizerStateFormat')=='bounded-safetensors-v1':
        values,_=load_streamed_weights(record['optimizerState'],torch=torch,device='cuda:0',expected_sha256=record['optimizerStateSha256'],chunk_bytes=CHUNK);state={}
        for index,fields in record['optimizerStateSchema'].items():state[int(index)]={key:values[meta['tensor']].cpu() if meta['originalDeviceType']=='cpu' else values[meta['tensor']] for key,meta in fields.items()}
        groups=record['optimizerParamGroups']
        for group in groups:
            if 'betas' in group:group['betas']=tuple(group['betas'])
        optimizer.load_state_dict({'state':state,'param_groups':groups});torch.set_rng_state(values['rng.cpu'].cpu());torch.cuda.set_rng_state_all([values['rng.cuda.'+str(i)].cpu() for i in range(record['cudaRngCount'])])
    else:
        # Only the verified original zero-step checkpoint can be adopted.
        assert record['completedSteps']==0 and record.get('adoptedFromZeroStepProtocolSha256');state=torch.load(record['optimizerState'],map_location='cpu',weights_only=True,mmap=True);assert state['completedSteps']==0 and not state['optimizer']['state'];optimizer.load_state_dict(state['optimizer']);torch.set_rng_state(state['torchCpuRng'].cpu());torch.cuda.set_rng_state_all([x.cpu() for x in state['torchCudaRng']])
    return record['completedSteps']
