"""Shared verified native model packaging, preserving the published encoder space."""
from pathlib import Path
import ast,hashlib,importlib.util,json,math,sys,types

BASE=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def tensor_state_sha(model):
    h=hashlib.sha256()
    for key,value in model.state_dict().items():
        value=value.detach().cpu().contiguous();h.update(key.encode()+b'\0'+str(value.dtype).encode()+b'\0');h.update(value.numpy().tobytes())
    return h.hexdigest()

def load_native_pair(torch):
    ready=read(BASE/'model-ready.json');protocol=read(BASE/'protocol.json')
    assert sha(BASE/'model-ready.json')==protocol['modelReadySha256']
    for file in ready['files']:assert sha(file['file'])==file['sha256']
    front=read(ready['audioFrontendSource'])
    for file in front['files']:assert sha(file['file'])==file['sha256']
    assert sha(BASE/'gpu-feature-numeric-proof.json')==protocol['gpuFeatureProofSha256'] and read(BASE/'gpu-feature-numeric-proof.json')['state']=='PASS_NATIVE_GPU_KALDI_FEATURES_INDEPENDENT_NUMPY_REFERENCE'
    assert torch.version.hip and torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0);torch.cuda.set_device(0)
    sys.path.insert(0,front['pythonPath']);msroot=Path(ready['modelscopeRoot'])
    for name in ['modelscope','modelscope.models','modelscope.models.audio','modelscope.models.audio.sv']:
        module=types.ModuleType(name);module.__path__=[str(msroot/Path(*name.split('.')))];sys.modules[name]=module
        if '.' in name:parent,short=name.rsplit('.',1);setattr(sys.modules[parent],short,module)
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);parent,short=name.rsplit('.',1);setattr(sys.modules[parent],short,module);return module
    folder=msroot/'modelscope/models/audio/sv';pool=load('modelscope.models.audio.sv.pooling_layers',folder/'pooling_layers.py');fusion=load('modelscope.models.audio.sv.fusion',folder/'fusion.py')
    classes=[n for n in ast.parse((folder/'ERes2NetV2.py').read_text(encoding='utf8')).body if isinstance(n,ast.ClassDef) and n.name in ['ReLU','BasicBlockERes2NetV2','BasicBlockERes2NetV2AFF','ERes2NetV2']]
    nativehash=hashlib.sha256(ast.dump(ast.Module(body=classes,type_ignores=[]),include_attributes=False).encode()).hexdigest();assert nativehash==protocol['nativeEncoderClassAstSha256']
    module=types.ModuleType('modelscope.models.audio.sv.ERes2NetV2');module.__dict__.update(torch=torch,nn=torch.nn,F=torch.nn.functional,math=math,pooling_layers=pool,AFF=fusion.AFF)
    exec(compile(ast.Module(body=classes,type_ignores=[]),str(folder/'ERes2NetV2.py'),'exec'),module.__dict__);sys.modules[module.__name__]=module;setattr(sys.modules['modelscope.models.audio.sv'],'ERes2NetV2',module)
    receipts=[];original=torch.nn.Module.load_state_dict
    def strict_load(model,weights,strict=True,assign=False):
        result=original(model,weights,strict=True,assign=assign);assert not result.missing_keys and not result.unexpected_keys
        for key,value in model.state_dict().items():assert torch.equal(value,weights[key].to(device=value.device,dtype=value.dtype)),key
        receipts.append({'class':type(model).__name__,'tensors':len(model.state_dict()),'stateSha256':tensor_state_sha(model),'allKeysAndValuesRequired':True});return result
    torch.nn.Module.load_state_dict=strict_load
    try:
        sys.path.insert(0,ready['sourceRoot']);import nomo_pvad
        native_feature=nomo_pvad._eres2netv2_fbank
        def feature_gpu(wav,sample_rate=16000):return native_feature(wav.to('cuda:0'),sample_rate)
        nomo_pvad._eres2netv2_fbank=feature_gpu
        pair=nomo_pvad.NomoPVAD(ready['weight'],ready['enrollmentDirectory'],device='cuda:0');pair._ensure_eres()
    finally:torch.nn.Module.load_state_dict=original
    assert tensor_state_sha(pair.model)==next(r['stateSha256'] for r in receipts if r['class']=='NomoPVADNet')
    assert tensor_state_sha(pair._eres)==[r['stateSha256'] for r in receipts if r['class']=='ERes2NetV2'][-1]
    for parameter in pair._eres.parameters():parameter.requires_grad_(False)
    pair._eres.eval()
    return pair,{'baseProtocolSha256':sha(BASE/'protocol.json'),'modelReadySha256':sha(BASE/'model-ready.json'),'nativeEncoderClassAstSha256':nativehash,'strictLoads':receipts,'gpuWeightsMatchNativeCpuLoad':True,'sameUnmodifiedAuthorFeaturesOnVerifiedGpu':True,'unrelatedSdkRegistryNotExecuted':True}
