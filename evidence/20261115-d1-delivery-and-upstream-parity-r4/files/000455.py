"""Native GPU Kaldi frontend vs independent NumPy reference, zero neural calls."""
from pathlib import Path
import json,sys,wave,hashlib,time
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1');read=lambda p:json.loads(Path(p).read_text());limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
assert not (C/'gpu-feature-numeric-proof.json').exists();state={'state':'PREPARING_GPU_FEATURE_NUMERIC_CONTROL','newNeuralCalls':0,'featureMaxAbsoluteTolerance':.005,'featureRmseTolerance':.001};atomic_json(C/'gpu-feature-numeric-proof.json',state)
import numpy as np
import torch
torch.set_num_threads(1);torch.set_num_interop_threads(1);assert torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0)
front=read(C.parent/'practical-conditioned-ps4-full-r1/audio-frontend-source.json');sys.path.insert(0,front['pythonPath']);sys.path.insert(0,read(C/'model-ready.json')['sourceRoot']);import nomo_pvad
def pcm(file):
    with wave.open(file,'rb') as f:return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(np.float32)/32768
def reference(audio):
    x=np.asarray(audio,dtype=np.float64)*32768.;count=(len(x)-400)//160+1
    frames=np.lib.stride_tricks.as_strided(x,shape=(count,400),strides=(x.strides[0]*160,x.strides[0])).copy();frames-=frames.mean(axis=1,keepdims=True)
    previous=np.concatenate([frames[:,:1],frames[:,:-1]],axis=1);frames-=.97*previous;frames*=np.hanning(400)**.85
    spectrum=np.abs(np.fft.rfft(frames,n=512,axis=1))**2
    mel=lambda value:1127.*np.log1p(value/700.)
    edges=np.linspace(mel(20.),mel(8000.),82);frequencies=mel(np.arange(257)*16000./512)
    banks=np.maximum(0.,np.minimum((frequencies[None,:]-edges[:-2,None])/(edges[1:-1,None]-edges[:-2,None]),(edges[2:,None]-frequencies[None,:])/(edges[2:,None]-edges[1:-1,None])))
    banks[:,-1]=0.;energies=np.einsum('ij,kj->ik',spectrum,banks,optimize=False);features=np.log(np.maximum(energies,np.finfo(np.float32).eps));features-=features.mean(axis=0,keepdims=True);return features
anchors=read(C/'automatic-enrollments.json');cases=read(C/'audio-only.json');inputs=[('real-enrollment',pcm(anchors[0]['audio'])),('real30s-mixture',pcm(cases[0]['audio'])),('exact-zero',np.zeros(16000,dtype=np.float32)),('nonzero-1lsb',np.tile(np.array([-1,1],dtype=np.float32)/32768,8000))]
rows=[];tick=time.perf_counter()
for name,audio in inputs:
    gpu=nomo_pvad._eres2netv2_fbank(torch.from_numpy(audio).to('cuda:0')).cpu().numpy();truth=reference(audio);assert gpu.shape==truth.shape
    error=np.asarray(gpu,dtype=np.float64)-truth;row={'case':name,'shape':list(gpu.shape),'maxAbsoluteError':float(np.max(np.abs(error))),'rmse':float(np.sqrt(np.mean(error**2))),'allFinite':bool(np.isfinite(gpu).all())};rows.append(row)
    state.update(state='CHECKING_GPU_NUMERIC_FEATURES',results=rows,limits=limits.query());atomic_json(C/'gpu-feature-numeric-proof.json',state)
    assert row['allFinite'] and row['maxAbsoluteError']<=.005 and row['rmse']<=.001,row
state.update(state='PASS_NATIVE_GPU_KALDI_FEATURES_INDEPENDENT_NUMPY_REFERENCE',wholeProbeSeconds=time.perf_counter()-tick,sourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),nativeAuthorFunctionUnmodified=True,onlyFeatureInputDeviceChanges=True,limits=limits.query());atomic_json(C/'gpu-feature-numeric-proof.json',state);print(json.dumps(state),flush=True)
