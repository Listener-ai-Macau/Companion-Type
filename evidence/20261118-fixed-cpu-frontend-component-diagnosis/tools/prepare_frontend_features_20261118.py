"""Same public PCM: reproduce installed NeMo frontend and pinned HF frontend.

CPU feature extraction only. No network, model weights, neural inference or
reference text. Saved arrays remain local inputs, not source-control evidence.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,sys,threading,time,wave
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from meeting_acoustic_worker_20261116 import own_limits
from durable_model_state_20261117 import atomic_json
from moss_windows_resource_limits_20261104 import SystemRamPressure
limits=own_limits(25)
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
O=C/'preprocessing-contract-20261118';out=O/'feature-inputs-r2';out.mkdir(exist_ok=False)
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
P=read(C/'selected-cpu-segmentation-protocol-r1.json');prepared=read(O/'preparation.json')
sys.path.insert(0,prepared['isolatedModuleRoot'])
pressure=SystemRamPressure();done=threading.Event();start=time.monotonic()
state=dict(state='EXTRACTING_TWO_FROZEN_FRONTENDS_FROM_ORIGINAL_PCM',pid=os.getpid(),cases=[],newNeuralCalls=0,newTrainingUpdates=0,referenceRead=False)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(**v):
 state.update(v,at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
def watch():
 import psutil
 while not done.wait(.5):
  if pressure.low() or psutil.virtual_memory().available<P['minimumAvailableBytes'] or time.monotonic()-start>300:
   save(state='STOPPED_CPU_FEATURE_RESOURCE_OR300S_BOUNDARY');atomic_json(out/'completed.json',state);os._exit(76)
try:
 save();threading.Thread(target=watch,daemon=True).start()
 import torch
 from companion_community1_adapter_20261115 import pin_rocm_blas
 blas=Path(sys.executable).parent.parent/'Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll'
 state['blasThreadPin']=pin_rocm_blas(blas,'88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0')
 save(state='PINNED_EXISTING_ROCM_OPENBLAS_ONE_THREAD')
 import numpy as np,transformers,kaldi_native_fbank as knf
 from transformers import AutoProcessor
 assert torch.__version__=='2.11.0+rocm10.0.0' and transformers.__version__=='5.22.1'
 torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
 modelroot=Path('E:/CodexData/Companion/.model-cache/english-transducer-official20261116')
 processor=AutoProcessor.from_pretrained(str(modelroot),local_files_only=True,trust_remote_code=False)
 assert processor.feature_extractor.feature_size==128 and not torch.cuda.is_initialized()
 opts=knf.FbankOptions();opts.frame_opts.dither=0;opts.frame_opts.snip_edges=False;opts.frame_opts.remove_dc_offset=False
 opts.mel_opts.num_bins=128;opts.mel_opts.low_freq=0;opts.mel_opts.high_freq=-400;opts.mel_opts.is_librosa=True
 opts.use_log_fbank=False
 state['fbankOptions']=opts.as_dict();state['hfConfig']=processor.feature_extractor.to_dict()
 state['pinnedFrontendSource']=dict(file=str(Path(transformers.__file__).parent/'models/parakeet/feature_extraction_parakeet.py'))
 state['pinnedFrontendSource']['sha256']=sha(state['pinnedFrontendSource']['file'])
 for case in P['cases']:
  assert sha(case['audio'])==case['audioSha256']
  with wave.open(case['audio'],'rb') as w:
   assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,case['frames']);raw=w.readframes(case['frames'])
  assert hashlib.sha256(raw).hexdigest()==case['pcmSha256']
  samples=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768
  fb=knf.OnlineFbank(opts);fb.accept_waveform(16000,samples.tolist());fb.input_finished()
  linear=np.stack([fb.get_frame(i) for i in range(fb.num_frames_ready)]).astype(np.float32)
  logged=np.log(np.maximum(linear,np.finfo(np.float32).eps));mean=logged.mean(axis=0,dtype=np.float32)
  variance=np.maximum((logged*logged).mean(axis=0,dtype=np.float32)-mean*mean,0)
  baseline=np.ascontiguousarray((logged-mean)/(np.sqrt(variance)+np.float32(1e-5)))
  request=processor(audio=samples,sampling_rate=16000,return_tensors='np',audio_kwargs={'truncation':False,'device':'cpu'})
  corrected=np.ascontiguousarray(request['input_features'][0],dtype=np.float32);n=int(request['attention_mask'][0].sum())
  assert n==case['frames']//160 and np.isfinite(corrected).all() and not torch.cuda.is_initialized()
  entries=[]
  for mode,value,length in [('installed_frontend',baseline,len(baseline)),('published_hf_frontend',corrected,n)]:
   file=out/(mode+'--'+case['id']+'.npy');np.save(file,value,allow_pickle=False)
   entries.append(dict(mode=mode,file=str(file),sha256=sha(file),shape=list(value.shape),length=length))
  state['cases'].append(dict(id=case['id'],audio=case['audio'],audioSha256=case['audioSha256'],frames=case['frames'],
   energyFractionBelowCurrentFloor=float((linear<=np.finfo(np.float32).eps).mean()),
   logGuardOnlyMeanAbsDifference=float(np.abs(logged-np.log(linear+np.float32(2**-24))).mean()),
   channelsWithZeroClippedVariance=int((variance==0).sum()),features=entries))
  save(activeCase=case['id'])
 save(state='COMPLETE_CPU_FRONTEND_INPUTS_NO_MODEL_INFERENCE',torchGpuInitialized=False,seconds=time.monotonic()-start)
 atomic_json(out/'completed.json',state);print(json.dumps(dict(state=state['state'],cases=len(state['cases']),newNeuralCalls=0,seconds=state['seconds']),ensure_ascii=False))
except BaseException as error:
 save(state='FAILED_CPU_FEATURE_PREPARATION_RETAINED',error=repr(error));atomic_json(out/'completed.json',state);raise
finally:done.set();pressure.close()
