"""Bounded local loading for one extractor learner plus its frozen ASR teacher."""
from pathlib import Path
import hashlib,importlib.util,json,sys,wave
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load_pair(example,*,torch,device):
    import numpy as np
    assert sha(example['audio'])==example['audioSha256'] and sha(example['profileAudio'])==example['profileAudioSha256']
    with wave.open(example['audio'],'rb') as f:
        assert f.getnchannels()==2 and f.getsampwidth()==2 and f.getframerate()==16000;pair=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,2).T.copy().astype(np.float32)/32768
    with wave.open(example['profileAudio'],'rb') as f:
        assert f.getnchannels()==1 and f.getframerate()==16000;profile=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').copy().astype(np.float32)/32768
    peak=float(np.max(np.abs(pair[0])));profile_peak=float(np.max(np.abs(profile)));assert peak>0 and profile_peak>0
    return torch.from_numpy(pair/peak).unsqueeze(0).to(device),torch.from_numpy(profile/profile_peak).unsqueeze(0).to(device),peak
def load_models(P,out,*,torch,with_teacher=True):
    from practical_io_20261107 import atomic_json
    ready=read(P['extractorReady']);assert sha(P['extractorReady'])==P['extractorReadySha256']
    for x in ready['files']:assert sha(x['file'])==x['sha256']
    front=read(P['audioFrontend']);assert sha(P['audioFrontend'])==P['audioFrontendSha256']
    for x in front['files']:assert sha(x['file'])==x['sha256']
    sys.path.insert(0,front['pythonPath']);source=Path(ready['sourceRoot'])/'inference.py';spec=importlib.util.spec_from_file_location('pinned_trainable_author',source);author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author);assert Path(author.torchaudio.__file__).resolve().is_relative_to(Path(front['pythonPath']).resolve())
    checkpoint=torch.load(ready['weight'],map_location='cpu',weights_only=True,mmap=True);weights=checkpoint.get('model',checkpoint.get('state_dict',checkpoint));prefix=all(k.startswith('module.') for k in weights)
    if prefix:weights={k.removeprefix('module.'):v for k,v in weights.items()}
    base=author.build_model(torch.device('cuda:0'));result=base.load_state_dict(weights,strict=True);assert not result.missing_keys and not result.unexpected_keys
    actual=base.state_dict();assert set(actual)==set(weights);left=hashlib.sha256();right=hashlib.sha256()
    for name in sorted(weights):
        a=weights[name].detach().contiguous().cpu().numpy().tobytes();b=actual[name].detach().contiguous().cpu().numpy().tobytes();assert a==b;left.update(name.encode()+a);right.update(name.encode()+b)
    atomic_json(out/'extractor-load-proof.json',{'state':'PASS_EXACT_COMPLETE_AUTHOR_WEIGHTS_GPU_ROUNDTRIP','tensors':len(weights),'sourceSha256':left.hexdigest(),'deviceSha256':right.hexdigest(),'strictLoad':True,'originalSourceUnmodified':True});del checkpoint,weights,actual,a,b
    teacher=processor=None
    if with_teacher:
        N=read(P['asrProtocol']);assert sha(P['asrProtocol'])==P['asrProtocolSha256']
        for x in N['files']:assert sha(x['file'])==x['sha256']
        from transformers import AutoProcessor
        from practical_qwen_streamed_loader_20261107 import load_model
        processor=AutoProcessor.from_pretrained(N['modelRoot'],local_files_only=True);weight=next(x for x in N['files'] if Path(x['file']).name=='model.safetensors');teacher,proof=load_model(N['modelRoot'],torch=torch,device='cuda:0',expected_sha256=weight['sha256'])
        teacher.requires_grad_(False);teacher.eval();assert not any(p.requires_grad for p in teacher.parameters());atomic_json(out/'frozen-asr-load-proof.json',proof)
    return base,teacher,processor
def tensor_hash(named_tensors):
    h=hashlib.sha256()
    for name,value in named_tensors:
        h.update(name.encode());h.update(value.detach().contiguous().view(-1).view(__import__('torch').uint8).cpu().numpy().tobytes())
    return h.hexdigest()
