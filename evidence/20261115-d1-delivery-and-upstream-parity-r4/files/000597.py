"""CPU-only feature equivalence; no GPU initialization or speech model."""
from pathlib import Path
from datetime import datetime
import ctypes, hashlib, importlib.util, json, os, sys, tarfile, wave

os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                  HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
R=Path('E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1')
out=R/'bounded-frontend-control-r1';out.mkdir()
state={'state':'PREPARING_CPU_ONLY_FRAME_EQUIVALENCE','newNeuralCalls':0,'gpuInitialized':False}
def save(**values):
 state.update(values,at=datetime.now().astimezone().isoformat(),limits=limits.query())
 (out/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
save()
import torch,numpy as np,yaml
torch.set_num_threads(1);torch.set_num_interop_threads(1)
library=Path(sys.prefix)/'Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll'
lib=ctypes.CDLL(str(library));lib.openblas_set_num_threads(1)
spec=importlib.util.spec_from_file_location('pinned_converter',R/'source/convert_nemotron3_diarization_to_hf.py')
up=importlib.util.module_from_spec(spec);spec.loader.exec_module(up)
with tarfile.open('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107/Nemotron-3-Diarization.nemo') as archive:
 config=yaml.safe_load(archive.extractfile('model_config.yaml').read())
extractor=up.build_feature_extractor(config)
processor=up.Nemotron3DiarizationProcessor(feature_extractor=extractor,subsampling_factor=8)
audio=Path('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107/public61-from-S.wav')
with wave.open(str(audio),'rb') as wav:
 samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
expected=processor(samples,sampling_rate=16000,return_tensors='pt')
from bounded_nemotron_frontend_20261115 import install_bounded_frontend
install_bounded_frontend(extractor)
actual=processor(samples,sampling_rate=16000,return_tensors='pt')
assert torch.equal(actual['attention_mask'],expected['attention_mask'])
delta=(actual['input_features']-expected['input_features']).abs()
assert torch.equal(actual['input_features'],expected['input_features']),float(delta.max())
# Non-hop-aligned true tails, frame-boundary impulses and both global edges.
checks=[]
for size in [960057,960160,960511]:
 source=np.zeros(size,dtype=np.float32)
 source[[0,479999,480000,480001,size-1]]=[.3,-.25,.75,-.5,.4]
 bounded=processor(source,sampling_rate=16000,return_tensors='pt')
 saved=extractor._torch_extract_fbank_features
 extractor._torch_extract_fbank_features=type(extractor)._torch_extract_fbank_features.__get__(extractor)
 full=processor(source,sampling_rate=16000,return_tensors='pt')
 extractor._torch_extract_fbank_features=saved
 assert all(torch.equal(bounded[k],full[k]) for k in full),size
 checks.append({'samples':size,'exactFeaturesAndMask':True})
save(state='PASS_BIT_EXACT_FULL_VERSUS_BOUNDED_UPSTREAM_CPU_FRONTEND',
 shape=list(actual['input_features'].shape),maxAbsoluteDifference=float(delta.max()),
 original61FeatureSha256=hashlib.sha256(expected['input_features'].contiguous().numpy().tobytes()).hexdigest(),
 globalEdgesAndNonAlignedTails=checks,framesPerBlock=3000,
 helperSha256=hashlib.sha256((S/'bounded_nemotron_frontend_20261115.py').read_bytes()).hexdigest())
print(json.dumps(state))
