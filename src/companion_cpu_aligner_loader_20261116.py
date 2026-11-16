"""Exact native timestamp classifier with immutable CPU mmap weights."""
from pathlib import Path
import hashlib,json,math,mmap,struct,time

def load_cpu_aligner(root,*,torch,expected_sha256):
    from accelerate import init_empty_weights
    from transformers import AutoConfig,AutoModelForTokenClassification
    root=Path(root);source=root/'model.safetensors';tick=time.perf_counter()
    with source.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected_sha256
    config=AutoConfig.from_pretrained(root,local_files_only=True)
    assert config.model_type=='qwen3_asr' and config.architectures==['Qwen3ASRForTokenClassification']
    with init_empty_weights(include_buffers=False):model=AutoModelForTokenClassification.from_config(config,dtype=torch.bfloat16,attn_implementation='eager')
    assert all(p.is_meta for p in model.parameters());buffers={k:v.detach().cpu().clone() for k,v in model.named_buffers()}
    assert all(not v.is_meta for v in buffers.values())
    stream=source.open('rb');size=struct.unpack('<Q',stream.read(8))[0];assert 0<size<16*1024**2
    header=json.loads(stream.read(size));offset=8+size;mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ);weights={};total=0
    for name,row in header.items():
        if name=='__metadata__':continue
        assert row['dtype']=='BF16';start,end=row['data_offsets'];count=math.prod(row['shape'])
        assert end-start==count*2 and offset+end<=source.stat().st_size
        weights[name]=torch.frombuffer(mapping,dtype=torch.bfloat16,count=count,offset=offset+start).reshape(row['shape']);total+=end-start
    result=model.load_state_dict(weights,strict=True,assign=True)
    assert not result.missing_keys and not result.unexpected_keys and hasattr(model,'score') and not hasattr(model,'lm_head')
    model=model.to('cpu').eval().requires_grad_(False)
    for name,value in model.named_parameters():assert value.device.type=='cpu' and value.dtype==torch.bfloat16 and value.data_ptr()==weights[name].data_ptr()
    for name,value in model.named_buffers():assert torch.equal(value.detach().cpu(),buffers[name])
    model._readonly_weight_mapping_owners=(stream,mapping)
    return model,{'state':'EXACT_NATIVE_CPU_ALIGNER_READONLY_BF16_ALL_KEYS_ASSIGNED','weightSha256':expected_sha256,'tensorCount':len(weights),'tensorBytes':total,
        'noPrivateWholeStateDictCopy':True,'noWholeModelToEmpty':True,'computedBuffersPreserved':list(buffers),'gpuUsed':False,'quantization':False,'weightsChanged':False,'seconds':time.perf_counter()-tick}
