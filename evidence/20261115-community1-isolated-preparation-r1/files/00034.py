"""Fixed local Community1 control; public feature probe requires no weights."""
from pathlib import Path
from datetime import datetime
from functools import partial
from types import SimpleNamespace
import argparse,hashlib,json,os,random,sys,time
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYANNOTE_METRICS_ENABLED='0',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_local_pcm_session_20261114 import atomic_json
from companion_community1_adapter_20261115 import sha,pin_rocm_blas,read_pcm_tensor,export_output
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))

def main():
 p=argparse.ArgumentParser()
 for name in ['control','inventory','run']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--phase',choices=['features','full'],required=True);a=p.parse_args()
 limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 protocol=read(a.control/'protocol.json');binding=read(a.control/'worker-binding.json')
 assert sha(__file__)==binding['workerSha256'] and sha(a.control/'protocol.json')==binding['protocolSha256']
 for path,digest in binding['helpers'].items():assert sha(path)==digest
 runtime=read(protocol['runtimeManifest']);assert sha(protocol['runtimeManifest'])==protocol['runtimeManifestSha256']
 for item in runtime['files']:assert sha(item['file'])==item['sha256']
 sys.path[:0]=protocol['additionalSites']
 os.environ.update(HF_HOME=str(a.run/'offline-hf-cache'),MPLCONFIGDIR=str(a.run/'matplotlib-cache'))
 state={'state':'STARTING_FIXED_LOCAL_COMMUNITY1_CONTROL','startedAt':datetime.now().astimezone().isoformat(),
  'protocolSha256':binding['protocolSha256'],'workerSha256':sha(__file__),'runtimeManifestSha256':protocol['runtimeManifestSha256'],
  'phase':a.phase,'newNeuralCalls':0,'parameterUpdates':0,'referenceRead':False,'qualityQualified':False}
 began=time.perf_counter()
 def save(**values):
  state.update(values,limits=limits.query(),observedAt=datetime.now().astimezone().isoformat())
  atomic_json(a.run/'state.json',state)
 save()
 try:
  inventory=read(a.inventory);assert inventory['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
  assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()<1800
  import torch,numpy as np
  assert torch.__version__=='2.11.0+rocm10.0.0' and torch.cuda.device_count()==1
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
  blas=pin_rocm_blas(protocol['rocmBlasLibrary'],protocol['rocmBlasLibrarySha256'])
  torch.cuda.set_device(0);gpu=torch.cuda.get_device_properties(0)
  assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
  save(gpu=gpu.name,blas=blas)
  if a.phase=='features':
   from torchaudio.compliance import kaldi
   from pyannote.audio.models.embedding.wespeaker import BaseWeSpeakerResNet
   # The real upstream feature method is called unbound. No backbone, random
   # network or model checkpoint is created. Dither is the upstream default0.
   obj=SimpleNamespace(hparams=SimpleNamespace(fbank_centering_span=None),
    _fbank=partial(kaldi.fbank,num_mel_bins=80,frame_length=25.,round_to_power_of_two=True,
     frame_shift=10.,snip_edges=True,dither=0.,sample_frequency=16000,window_type='hamming',use_energy=False))
   rng=np.random.default_rng(20261115);t=np.arange(16000,dtype=np.float32)/16000
   pcm=np.rint(np.clip(.2*np.sin(2*np.pi*311*t)+.1*np.sin(2*np.pi*1099*t)+.01*rng.normal(size=t.size),-1,1)*32767).astype('<i2')
   waveform=torch.from_numpy(pcm.astype(np.float32)/32768).reshape(1,1,-1)
   with torch.inference_mode():
    cpu=BaseWeSpeakerResNet.compute_fbank(obj,waveform)
    gpu_features=BaseWeSpeakerResNet.compute_fbank(obj,waveform.to('cuda:0')).cpu()
   torch.cuda.synchronize();difference=(cpu-gpu_features).abs()
   maximum=float(difference.max());mean=float(difference.mean())
   assert cpu.shape==gpu_features.shape==(1,98,80) and torch.isfinite(gpu_features).all()
   assert maximum<=.003 and mean<=.0001,'Fixed FP32 CPU/GPU feature control failed; retain failure, no silent tolerance change'
   save(state='PASS_UPSTREAM_WESPEAKER_CPU_GPU_FEATURE_NUMERICAL_CONTROL_NO_MODEL',
    featureShape=list(cpu.shape),maximumAbsoluteDifference=maximum,meanAbsoluteDifference=mean,
    predefinedMaximumAbsoluteTolerance=.003,predefinedMeanAbsoluteTolerance=.0001,
    noModelInstantiated=True,noWeightsLoaded=True,upstreamFeatureMethodUnchanged=True)
  else:
   feature_proof=read(protocol['featureProof'])
   assert feature_proof['state']=='PASS_UPSTREAM_WESPEAKER_CPU_GPU_FEATURE_NUMERICAL_CONTROL_NO_MODEL'
   assert feature_proof['protocolSha256']==binding['protocolSha256'] and feature_proof['workerSha256']==sha(__file__)
   model_binding=read(a.control/'model-binding.json')
   assert model_binding['featureProofSha256']==sha(protocol['featureProof'])
   assert model_binding['repository']=='pyannote/speaker-diarization-community-1'
   assert model_binding['ownerAccessConditionsAccepted'] is True and len(model_binding['revision'])==40
   model_root=Path(model_binding['modelRoot']).resolve();assert model_root==Path(protocol['modelRoot']).resolve() and model_root.is_dir()
   for item in model_binding['files']:
    path=(model_root/item['relativePath']).resolve();assert path.is_relative_to(model_root)
    assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
   case=read(a.control/'audio-only.json');waveform,pcm_binding=read_pcm_tensor(case,torch)
   from pyannote.audio import Pipeline
   from pyannote.audio.telemetry.metrics import is_metrics_enabled
   assert not is_metrics_enabled()
   random.seed(20261115);np.random.seed(20261115);torch.manual_seed(20261115)
   save(state='LOADING_PINNED_LOCAL_OFFICIAL_COMMUNITY1',modelBindingSha256=sha(a.control/'model-binding.json'),pcm=pcm_binding)
   pipeline=Pipeline.from_pretrained(model_root,token=False,cache_dir=a.run/'offline-hf-cache')
   assert pipeline is not None;pipeline.to(torch.device('cuda:0'))
   def hook(step,artifact,**kwargs):
    if (a.run/'stop.request').exists():raise InterruptedError('Owned stop; raw source and model retained')
    save(state='RUNNING_WHOLE_FIXED_COMMUNITY1',step=step,completed=kwargs.get('completed'),total=kwargs.get('total'))
   with torch.inference_mode():output=pipeline({'waveform':waveform,'sample_rate':16000,'uri':case['meeting']},hook=hook)
   torch.cuda.synchronize()
   result=export_output(output,a.run/'output',case=case,binding={
    'protocolSha256':binding['protocolSha256'],'modelBindingSha256':sha(a.control/'model-binding.json'),
    'runtimeManifestSha256':protocol['runtimeManifestSha256'],'workerSha256':sha(__file__),'pcm':pcm_binding})
   assert sha(case['audio'])==case['audioSha256']
   save(state='COMPLETE_WHOLE_COMMUNITY1_ORIGINAL_SCORE_PENDING',pipelineApplications=1,
    newNeuralCalls=None,neuralCallsCountExplanation='One upstream whole-pipeline application; internal NN batches recorded by hook, not counted as one neural batch.',
    output=result,sourceWavUnchanged=True,numSpeakersHintUsed=False,asrRunOrChanged=False)
 except BaseException as error:
  save(state='INCOMPLETE_COMMUNITY1_CONTROL_RAW_RETAINED_NO_AUTO_RETRY',error=repr(error));raise
 finally:save(seconds=time.perf_counter()-began,finishedAt=datetime.now().astimezone().isoformat())
 print(json.dumps(state,ensure_ascii=False))

if __name__=='__main__':main()
