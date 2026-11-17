"""Compare tensor values between the two official serializations, no network/NN."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
import hashlib,json,os,sys,tarfile,time
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from companion_local_pcm_session_20261114 import exclusive_file
from durable_model_state_20261117 import atomic_json
import psutil
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure()
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/native8-reference-fidelity-r1')
P=json.loads((E/'protocol.json').read_text(encoding='utf-8'));target=E/'official-weight-value-comparison.json';assert not target.exists()
tick=time.monotonic()
def stop():
    assert not pressure.low() and psutil.virtual_memory().available>=P['minimumAvailableBytes']
    assert time.monotonic()-tick<300
def key(t):
    stop();t=t.detach().to(dtype=torch.float32).contiguous()
    return (tuple(t.shape),hashlib.sha256(memoryview(t.numpy()).cast('B')).hexdigest())
try:
    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
        stop();import torch
        from safetensors import safe_open
        from companion_community1_adapter_20261115 import pin_rocm_blas
        pin=pin_rocm_blas(P['cpuBlas']['file'],P['cpuBlas']['sha256'])
        torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
        cache=Path(P['modelRoot']);original=cache.parent/'Nemotron-3-Diarization.nemo'
        with tarfile.open(original) as archive:
            member=next(m for m in archive if m.name.endswith('model_weights.ckpt'))
            with archive.extractfile(member) as f:state=torch.load(f,map_location='cpu',weights_only=True)
        if 'state_dict' in state:state=state['state_dict']
        prior=defaultdict(list)
        for name,tensor in state.items():
            if isinstance(tensor,torch.Tensor):prior[key(tensor)].append(name)
        matched=[];unmatched=[];dtypes=Counter();total=0
        with safe_open(cache/'model.safetensors',framework='pt',device='cpu') as weights:
            for name in weights.keys():
                tensor=weights.get_tensor(name);dtypes[str(tensor.dtype)]+=1;total+=tensor.numel();signature=key(tensor)
                names=prior.get(signature)
                row={'hf':name,'shape':list(tensor.shape),'elements':tensor.numel()}
                if names:row['nemo']=names.pop();matched.append(row)
                else:unmatched.append(row)
        matched_elements=sum(r['elements'] for r in matched)
        result={'at':datetime.now().astimezone().isoformat(),'state':'OFFICIAL_SERIALIZATION_TENSOR_VALUES_COMPARED_NO_NEURAL_CALLS',
            'originalArchive':str(original),'hfRoot':str(cache),'hfFileSha256':P['files']['model.safetensors']['sha256'],
            'hfDtypes':dict(dtypes),'hfTensors':len(matched)+len(unmatched),'hfElements':total,
            'matchedExactFloat32TensorValues':len(matched),'matchedElements':matched_elements,
            'matchedElementFraction':matched_elements/total,'allHfTensorValuesMatchNemo':not unmatched,
            'comparison':'Per-tensor exact shape andSHA256 of original values widened toFP32. Tensor names can differ; each source tensor is used at most once. No numeric tolerance, transposition or truncation.',
            'matched':matched,'unmatchedHf':unmatched,
            'remainingNemoNames':[name for names in prior.values() for name in names],
            'newNeuralCalls':0,'parameterUpdates':0,'gpuInitialized':torch.cuda.is_initialized(),
            'limits':limits.query(),'cpuBlasThreadPin':pin,'seconds':time.monotonic()-tick}
        assert not result['gpuInitialized']
        atomic_json(target,result)
        print(json.dumps({k:result[k] for k in ['state','hfTensors','matchedExactFloat32TensorValues','matchedElementFraction','allHfTensorValuesMatchNemo','unmatchedHf','remainingNemoNames','seconds']},ensure_ascii=False))
finally:pressure.close()
