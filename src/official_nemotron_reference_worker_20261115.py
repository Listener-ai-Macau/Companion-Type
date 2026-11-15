"""Same original Nemotron checkpoint through the upstream Transformers model.

No new checkpoint, training, label-conditioned inference or default change.
The pinned upstream converter supplies only strict key/config/frontend mapping.
"""
from pathlib import Path
from datetime import datetime
import argparse,ctypes,hashlib,importlib.util,json,os,shutil,tarfile,time,traceback,wave
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--run',type=Path,required=True)
 a=p.parse_args();read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
 P=read(a.control/'protocol.json');case=read(a.control/'audio-only.json')[a.index]
 assert not any('reference' in k.lower() for k in case)
 out=a.run/'result';out.mkdir();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 now=lambda:datetime.now().astimezone().isoformat(timespec='seconds');began=time.monotonic()
 state={'state':'PREPARING_SAME_CHECKPOINT_UPSTREAM_REFERENCE','startedAt':now(),'pid':os.getpid(),'case':case,
  'completedChunks':0,'newNeuralCalls':0,'referenceRead':False,'trainingUpdates':0,'qualityQualified':False}
 def save(**values):
  state.update(values,observedAt=now(),limits=limits.query());atomic_json(out/'state.json',state)
 try:
  assert sha(__file__)==P['workerSha256'] and sha(P['checkpoint'])==P['checkpointSha256']
  assert sha(P['converter'])==P['converterSha256'] and sha(case['audio'])==case['audioSha256']
  inventory=read(a.run/'inventory/hip-inventory.json');assert inventory['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
  assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()<1800
  save()
  import torch,numpy as np,transformers,yaml
  assert transformers.__version__=='5.22.1' and torch.version.hip and torch.cuda.device_count()==1
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  # This ROCm-specific pool ignores the common BLAS environment setting and
  # starts at16, even while NumPy/SciPy each use1. Keep the existing one-thread
  # policy in this worker only, before GPU/frontend initialization.
  library=Path(P['rocmBlasLibrary']);assert sha(library)==P['rocmBlasLibrarySha256']
  blas=ctypes.CDLL(str(library));get=blas.openblas_get_num_threads;get.argtypes=[];get.restype=ctypes.c_int
  set_threads=blas.openblas_set_num_threads;set_threads.argtypes=[ctypes.c_int];set_threads.restype=None
  before=get();set_threads(1);assert get()==1
  save(runtimeBlasThreadsBefore=before,runtimeBlasThreadsAfter=get())
  torch.cuda.set_device(0);assert get()==1
  props=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in props.name and props.gcnArchName.startswith('gfx1030')
  module_spec=importlib.util.spec_from_file_location('pinned_upstream_converter',P['converter']);up=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(up)
  # Only the two known regular members are extracted into this owned run.
  with tarfile.open(P['checkpoint']) as archive:
   members=archive.getmembers();assert {m.name for m in members}=={'model_config.yaml','model_weights.ckpt'} and all(m.isfile() for m in members)
   config=yaml.safe_load(archive.extractfile('model_config.yaml').read())
   checkpoint=a.run/'model_weights.ckpt'
   with archive.extractfile('model_weights.ckpt') as source,checkpoint.open('xb') as target:shutil.copyfileobj(source,target,1024*1024)
  old=torch.load(checkpoint,map_location='cpu',weights_only=True,mmap=True)
  original_fb=old['preprocessor.featurizer.fb'].detach().float().squeeze(0).clone()
  original_window_dtype=old['preprocessor.featurizer.window'].dtype
  original_window=old['preprocessor.featurizer.window'].detach().float().clone()
  assert tuple(original_fb.shape)==(128,257)
  assert torch.equal(original_window,torch.hann_window(400,periodic=False).to(original_window_dtype).float()), 'Original frontend window formula differs after checkpoint dtype roundtrip'
  hf_config=up.build_config(config);assert hf_config.chunk_length==340 and hf_config.chunk_right_context==40 and hf_config.fifo_length==40 and hf_config.speaker_cache_update_period==300
  hf_config._attn_implementation='eager'
  # Avoid allocating a second random400MiB CPU backbone before loading the
  # original tensors. Leave nonpersistent RoPE buffers on CPU, materialized.
  # The original strict mapping and inference FP32 values remain identical.
  from accelerate import init_empty_weights
  with init_empty_weights(include_buffers=False):
   model=up.Nemotron3DiarizationForAudioFrameClassification(hf_config).eval()
  mapped=up.convert_state_dict(old);model.load_state_dict(mapped,strict=True,assign=True)
  actual=model.state_dict();assert actual.keys()==mapped.keys()
  assert all(torch.equal(actual[k].to(value.dtype),value) for k,value in mapped.items()),'Strict original tensor roundtrip changed'
  atomic_json(out/'model-binding.json',{'originalCheckpoint':P['checkpoint'],'originalSha256':P['checkpointSha256'],
   'converterSha256':P['converterSha256'],'mappedTensors':len(mapped),'originalTensors':len(old),
   'allMappedTensorBytesRoundtripExact':True,'onlyDroppedKeys':[k for k in old if any(up.re.match(pattern,k) for pattern in up.KEYS_TO_DROP)],
   'config':hf_config.to_dict(),'newWeightsDownloaded':False,'referenceRead':False})
  del mapped,actual,old
  assert not any(parameter.is_meta for parameter in model.parameters())
  assert not any(buffer.is_meta for buffer in model.buffers())
  save(state='MOVING_ORIGINAL_REFERENCE_TENSORS_TO_GPU')
  model=model.to(device='cuda:0',dtype=torch.float32)
  save(state='BUILDING_UPSTREAM_FRONTEND',modelLoaded=True)
  assert get()==1
  extractor=up.build_feature_extractor(config)
  # Full-length STFT intermediates exceed this worker's2GiB Job. Split only
  # the already-preemphasized waveform, with global zero-padding and exact
  # hop-aligned frames. CPU control proved every feature and mask bit equal
  # on the original61s input and non-aligned edge/impulse cases.
  from bounded_nemotron_frontend_20261115 import install_bounded_frontend
  helper=Path(__file__).with_name('bounded_nemotron_frontend_20261115.py')
  assert sha(helper)==P['boundedFrontendSha256']
  install_bounded_frontend(extractor)
  atomic_json(out/'frontend-constants.json',{'source':'Unmodified upstream converter/feature extractor, regenerated FP32 mel filters',
   'melShape':list(original_fb.shape),'melSha256':hashlib.sha256(original_fb.numpy().tobytes()).hexdigest(),
   'upstreamMelSha256':hashlib.sha256(extractor.mel_filters.numpy().tobytes()).hexdigest(),
   'upstreamVersusOriginalMelMaxAbsoluteDifference':float((extractor.mel_filters-original_fb).abs().max()),
   'checkpointWindowDtype':str(original_window_dtype),
   'hannWindowMatchesUpstreamFormulaAfterCheckpointDtypeRoundtrip':True,
   'upstreamAndNativeWindowRecomputedInFloat32':True,'upstreamPerBlockFeatureFormulaUnmodified':True,
   'boundedAllocationOnly':True,'boundedFrontendSha256':sha(helper),'framesPerBlock':3000})
  processor=up.Nemotron3DiarizationProcessor(feature_extractor=extractor,subsampling_factor=8)
  with wave.open(case['audio'],'rb') as source:
   assert (source.getnchannels(),source.getsampwidth(),source.getframerate())==(1,2,16000)
   samples=np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype(np.float32)/32768
  assert abs(len(samples)/16000-case['audioSeconds'])<1/16000
  inputs=processor(samples,sampling_rate=16000,return_tensors='pt')
  assert inputs['input_features'].ndim==3 and inputs['input_features'].shape[-1]==128
  assert inputs['input_features'].shape[1]>=len(samples)//160
  feature=inputs['input_features'];atomic_json(out/'feature-binding.json',{'shape':list(feature.shape),'dtype':str(feature.dtype),
   'sha256':hashlib.sha256(feature.contiguous().numpy().tobytes()).hexdigest(),'allSourceFramesRepresented':True})
  if a.index==0:np.save(out/'short-features.npy',feature.numpy(),allow_pickle=False)
  inputs=inputs.to('cuda:0',dtype=torch.float32)
  def progress(module,args,output):
   if (a.run/'stop.request').exists():raise InterruptedError('Owned stop during upstream chunk inference')
   state['completedChunks']+=1;state['newNeuralCalls']+=1;save(state='RUNNING_UPSTREAM_REFERENCE_SAME_CHECKPOINT')
  hook=model.model.register_forward_hook(progress)
  save(state='RUNNING_UPSTREAM_REFERENCE_SAME_CHECKPOINT',gpu=props.name,modelLoaded=True,inferenceStarted=True)
  torch.cuda.synchronize();tick=time.perf_counter()
  with torch.inference_mode():value=model(**inputs).logits.sigmoid()
  torch.cuda.synchronize();elapsed=time.perf_counter()-tick
  main_chunks=state['completedChunks']
  probability=value[0].float().cpu().numpy();assert probability.ndim==2 and probability.shape[1]==8 and np.isfinite(probability).all()
  np.save(out/'probabilities.npy',probability,allow_pickle=False)
  # One pre-declared61s differential control holds the original BF16-quantized
  # mel bank equal to C++. It diagnoses frontend-vs-core drift, never selects
  # a candidate by reference scores. Full runs always use upstream FP32.
  diagnostic_seconds=0.
  if a.index==0:
   extractor.mel_filters=original_fb
   alternative=processor(samples,sampling_rate=16000,return_tensors='pt').to('cuda:0',dtype=torch.float32)
   torch.cuda.synchronize();at=time.perf_counter()
   with torch.inference_mode():alternative_value=model(**alternative).logits.sigmoid()[0].float().cpu().numpy()
   torch.cuda.synchronize();diagnostic_seconds=time.perf_counter()-at
   np.save(out/'same-original-bank-probabilities.npy',alternative_value,allow_pickle=False)
  hook.remove()
  from practical_nemotron_worker_20261107 import probability_segments
  rows=probability_segments(probability,len(probability),.01,case['audioSeconds'],.5)
  atomic_json(out/'speaker-journal.json',{'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
   'segments':rows,'outputSpeakers':8,'secondsPerFrame':.01,'anonymousOnly':True,'qualityQualified':False})
  atomic_json(out/'probabilities.json',{'audioSha256':case['audioSha256'],'frames':len(probability),'shape':list(probability.shape),
   'sha256':sha(out/'probabilities.npy'),'originalCheckpointSha256':P['checkpointSha256'],'sourceWorkerSha256':sha(__file__),
   'precision':'FP32 upstream model from original BF16/FP16 tensor values, exact strict roundtrip',
   'noSpeakerCacheResetBetweenChunks':True,'upstreamDefaultOfflineGeometry':True,'frameThreshold':.5})
  save(state='COMPLETE_UPSTREAM_REFERENCE_COMPARISON_PENDING',newNeuralCalls=state['completedChunks'],wholeForwardCalls=2 if a.index==0 else 1,neuralChunkCalls=state['completedChunks'],
       mainNeuralChunkCalls=main_chunks,diagnosticForwardSeconds=diagnostic_seconds,runtimeBlasThreadsAfterInference=get(),
       inferenceSeconds=elapsed,frames=len(probability),segments=len(rows))
 except BaseException as error:save(state='FAILED_UPSTREAM_REFERENCE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
 finally:state.update(finishedAt=now(),seconds=time.monotonic()-began,limits=limits.query());atomic_json(out/'state.json',state)
 print(json.dumps({k:state.get(k) for k in ['state','seconds','frames','completedChunks','error']},ensure_ascii=False))

if __name__=='__main__':main()
