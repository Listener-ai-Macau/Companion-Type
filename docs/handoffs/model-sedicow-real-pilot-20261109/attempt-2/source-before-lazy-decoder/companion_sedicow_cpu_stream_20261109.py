"""Exact F32 CPU layer streaming for one bounded diagnostic, never training.

Keep the repeatedly used decoder resident, load an encoder block only for its
forward call, then release it. The author's CTC-only modules stay on meta only
when generation.ctc_weight == 0 and labels are absent. Hooks fail if they are
unexpectedly called. No weights, dimensions, features or audio are changed.
"""
from pathlib import Path
import hashlib,json,math,struct,time


class CpuCheckpoint:
    def __init__(self,path,*,expected_sha256,torch,stop=lambda:False):
        self.path=Path(path);self.torch=torch;self.stop=stop
        self.stream=self.path.open('rb',buffering=0)
        self.loaded_tensor_calls=0;self.loaded_tensor_bytes=0;self.tensor_hashes={}
        prefix=self.stream.read(8);length=struct.unpack('<Q',prefix)[0]
        assert 0<length<100*1024**2
        raw=self.stream.read(length);assert len(raw)==length
        self.header=json.loads(raw);self.header.pop('__metadata__',None)
        self.data_start=8+length;digest=hashlib.sha256(prefix+raw);offset=0
        for key,row in sorted(self.header.items(),key=lambda kv:kv[1]['data_offsets'][0]):
            a,b=row['data_offsets'];assert row['dtype']=='F32' and a==offset and b-a==math.prod(row['shape'])*4
            own=hashlib.sha256();remaining=b-a
            while remaining:
                if stop():raise RuntimeError('ActualWindowsLOWRAM while verifying source')
                block=self.stream.read(min(remaining,1024**2));assert block
                digest.update(block);own.update(block);remaining-=len(block)
            self.tensor_hashes[key]=own.hexdigest();offset=b
        assert self.stream.tell()==self.path.stat().st_size
        assert digest.hexdigest()==expected_sha256,'Checkpoint bytes differ'
        self.sha256=digest.hexdigest();self.source_stat=self.path.stat()

    def tensor(self,key):
        if self.stop():raise RuntimeError('ActualWindowsLOWRAM before loading tensor')
        row=self.header[key];value=self.torch.empty(row['shape'],dtype=self.torch.float32,device='cpu')
        view=memoryview(value.detach().numpy()).cast('B')
        self.stream.seek(self.data_start+row['data_offsets'][0])
        assert self.stream.readinto(view)==len(view)
        assert hashlib.sha256(view).hexdigest()==self.tensor_hashes[key],'Tensor changed after source validation'
        self.loaded_tensor_calls+=1;self.loaded_tensor_bytes+=len(view)
        return value

    def receipt(self):
        return {'checkpointSha256':self.sha256,'tensorCalls':self.loaded_tensor_calls,'tensorBytesLoaded':self.loaded_tensor_bytes,'wholeCpuStateDictCreated':False,'mmapUsed':False,'dtypeConversion':False,'everyLoadedTensorHashVerified':True}


def stream_model(source_root,weight_file,*,torch,expected_sha256,attention='eager',config_override=None,stop=lambda:False,progress=lambda row:None):
    from companion_sedicow_checkpoint_20261109 import author_classes
    Config,Model=author_classes(source_root)
    cfg=json.loads((Path(source_root)/'config.json').read_text())
    if config_override:cfg.update(config_override)
    config=Config(**cfg);config._attn_implementation=attention
    with torch.device('meta'):model=Model(config)
    model.eval().requires_grad_(False)
    checkpoint=CpuCheckpoint(weight_file,expected_sha256=expected_sha256,torch=torch,stop=stop)
    expected=model.state_dict(keep_vars=True);groups={}
    for key,value in expected.items():groups.setdefault(id(value),[]).append(key)
    aliases={}
    for names in groups.values():
        present=[name for name in names if name in checkpoint.header];assert present,('Missing weight',names)
        for name in names:
            if name not in checkpoint.header:aliases[name]=present[0]
    assert set(checkpoint.header).issubset(expected)
    assert all(list(value.shape)==checkpoint.header[aliases.get(key,key)]['shape'] for key,value in expected.items())
    block_names=['model.encoder.layers.'+str(i) for i in range(config.encoder_layers)]+['model.encoder.ca_enrolls.'+str(i) for i in range(config.scb_layers)]
    ctc_only=['model.encoder.lm_head','model.encoder.subsample_conv1','model.encoder.subsample_conv2','model.encoder.additional_self_attention_layer']
    is_below=lambda key,paths:any(key==p or key.startswith(p+'.') for p in paths)
    resident={key:checkpoint.tensor(key) for key in checkpoint.header if not is_below(key,block_names+ctc_only)}
    for key,origin in aliases.items():
        if origin in resident:resident[key]=resident[origin]
    missing,unexpected=model.load_state_dict(resident,strict=False,assign=True)
    assert not unexpected and all(is_below(key,block_names+ctc_only) for key in missing)
    model.tie_weights();del resident
    model._cpu_stream_trace=[]
    def attach(name):
        module=model.get_submodule(name);keys=[key for key in checkpoint.header if key.startswith(name+'.')]
        assert keys
        def before(mod,args):
            tick=time.perf_counter();weights={key[len(name)+1:]:checkpoint.tensor(key) for key in keys};mod.load_state_dict(weights,strict=True,assign=True)
            model._cpu_stream_trace.append({'module':name,'loadSeconds':time.perf_counter()-tick,'state':'LOADED'});progress(model._cpu_stream_trace[-1])
        def after(mod,args,output):
            mod.to_empty(device='meta');model._cpu_stream_trace[-1]['state']='RELEASED';progress(model._cpu_stream_trace[-1]);return output
        module.register_forward_pre_hook(before);module.register_forward_hook(after)
    for name in block_names:attach(name)
    def unused_guard(module,args):raise RuntimeError('CTC-only module unexpectedly requested; diagnostic streaming contract forbids it')
    for name in ctc_only:model.get_submodule(name).register_forward_pre_hook(unused_guard)
    return model,checkpoint
