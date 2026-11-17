"""One actual fixed-order training example on CPU; cost proof, no optimizer."""
from pathlib import Path
from datetime import datetime
import ctypes,gc,hashlib,json,math,os,random,struct,sys,time,traceback,wave
os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate,SystemRamPressure
from durable_model_state_20261117 import atomic_json
from companion_local_pcm_session_20261114 import exclusive_file
import psutil
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
plan=read(J/'language-specific-adaptation-r1/expanded-data-r3/english-data-plan.json')
assert sha(plan['trainingManifest'])==plan['trainingManifestSha256']
rows=[json.loads(s) for s in Path(plan['trainingManifest']).read_text(encoding='utf-8').splitlines() if s]
assert len(rows)==1828
order=list(range(len(rows)));random.Random(20261116).shuffle(order);row=rows[order[0]]
run=E/'language-specific-adaptation-r1/real-cpu-backward-r1';run.mkdir(exist_ok=False)
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);rate=CpuRate(5,2500)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
pressure=SystemRamPressure();tick=time.monotonic();last=0
state={'at':datetime.now().astimezone().isoformat(),'state':'PREPARING_ONE_REAL_CPU_BACKWARD',
 'pid':os.getpid(),'exampleId':row['id'],'trainingOrderIndex':0,'exampleFrames':row['frames'],
 'targetTokens':len(row['targetIds']),'parameterUpdates':0,'cpuPercentMaximum':25,
 'trainingManifestSha256':plan['trainingManifestSha256'],'referenceLabelsRead':False,
 'validationAudioOrTextRead':False,'qualityQualified':False,'gpuInitialized':False,'newModelForwards':0,
 'sourceSha256':sha(__file__),'lossSourceSha256':sha(S/'tdt_selected_loss_20261116.py')}
def save(**values):
 state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
 atomic_json(run/'state.json',state,progress=True)
def stop(*args,**kwargs):
 global last
 assert not pressure.low() and psutil.virtual_memory().available>=3414499000,'Original realRAM floor'
 assert time.monotonic()-tick<600,'Single-example CPU cost proof10min cutoff'
 assert not(run/'stop.request').exists(),'Owned stop request'
 if time.monotonic()-last>3:save();last=time.monotonic()
try:
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
  save();started=time.monotonic()
  while time.monotonic()-started<60:stop();time.sleep(1)
  import torch,numpy as np
  from companion_community1_adapter_20261115 import pin_rocm_blas
  P=read(J/'english-transducer-r1/protocol.json')
  state['blas']=pin_rocm_blas(P['blas']['file'],P['blas']['sha256'])
  torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.set_grad_enabled(True)
  torch.random.default_generator.manual_seed(20261116)
  assert not torch.cuda.is_initialized()
  from transformers import AutoConfig,AutoProcessor
  from english_transducer_worker_20261116 import make_empty
  from tdt_selected_loss_20261116 import blocked_joint_loss
  root=Path(P['modelRoot']);weights=root/'model.safetensors';before=sha(weights)
  assert before==plan['publishedWeightsSha256']
  with weights.open('rb') as f:
   hsize=struct.unpack('<Q',f.read(8))[0];header=json.loads(f.read(hsize))
  # OS copy-on-write mapping: no modification can write the published file.
  raw=torch.from_file(str(weights),shared=False,size=weights.stat().st_size,dtype=torch.uint8)
  tensors={};types={'F32':torch.float32,'I64':torch.int64}
  for name,item in header.items():
   if name=='__metadata__':continue
   a,b=item['data_offsets'];tensors[name]=raw[8+hsize+a:8+hsize+b].view(types[item['dtype']]).reshape(item['shape'])
  config=AutoConfig.from_pretrained(root,local_files_only=True,trust_remote_code=False)
  config._attn_implementation='eager';config.encoder_config._attn_implementation='eager'
  save(state='MAPPING_EXACT_PUBLISHED_FP32_MODEL_ON_CPU')
  model=make_empty(config,torch);model.load_state_dict(tensors,strict=True,assign=True);del tensors
  model.eval().requires_grad_(False);named=dict(model.named_parameters());names=plan['trainableParameterNames']
  assert sum(named[n].numel() for n in names)==118886022
  assert all(p.device.type=='cpu' and p.dtype==torch.float32 and not p.is_meta for p in model.parameters())
  for name in names:named[name].requires_grad_(True)
  for layer in model.encoder.layers[20:]:layer.train()
  model.encoder_projector.train();model.decoder.train();model.joint.train()
  assert not model.encoder.training and all(not m.training for m in model.encoder.layers[:20])
  hooks=[layer.register_forward_hook(stop) for layer in model.encoder.layers]
  def grad_ready(g):stop();return g
  hooks+=[named[n].register_hook(grad_ready) for n in names]
  processor=AutoProcessor.from_pretrained(root,local_files_only=True,trust_remote_code=False)
  assert sha(row['audio'])==row['audioSha256']
  with wave.open(row['audio'],'rb') as f:
   assert (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes())==(1,2,16000,row['frames'])
   pcm=f.readframes(f.getnframes())
  samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
  request=processor(audio=samples,sampling_rate=16000,return_tensors='pt',audio_kwargs={'truncation':False,'device':'cpu'})
  assert int(request['attention_mask'].sum())==row['frames']//160
  labels=torch.tensor([row['targetIds']],dtype=torch.long)
  decoder_ids=torch.cat([torch.full((1,1),config.blank_token_id,dtype=torch.long),labels],dim=1)
  save(state='FORWARD_ONE_ORIGINAL_TRAINING_EXAMPLE_CPU',modelMappedCopyOnWrite=True,trainableParameters=118886022)
  began=time.perf_counter();state['newModelForwards']+=1
  encoded=model.get_audio_features(**request);decoded=model.decoder(decoder_ids)
  loss=blocked_joint_loss(model.joint,encoded.pooler_output,decoded,labels,encoded.attention_mask.sum(-1),
   vocab_size=config.vocab_size,blank_token_id=config.blank_token_id,durations=config.durations,
   torch=torch,chunk_frames=16,heartbeat=stop,checkpoint_joint=True)
  assert torch.isfinite(loss);value=float(loss.detach());forward=time.perf_counter()-began
  save(state='BACKWARD_ONE_ORIGINAL_TRAINING_EXAMPLE_CPU',loss=value,forwardSeconds=forward)
  began=time.perf_counter();loss.backward();backward=time.perf_counter()-began
  assert all(named[n].grad is not None and torch.isfinite(named[n].grad).all() for n in names)
  assert all(p.grad is None for n,p in named.items() if n not in names)
  norm=math.sqrt(sum(float(torch.linalg.vector_norm(named[n].grad))**2 for n in names))
  assert math.isfinite(norm) and norm>0 and not torch.cuda.is_initialized()
  for hook in hooks:hook.remove()
  after=sha(weights);assert after==before
  save(state='PASS_REAL_CPU_FP32_ONE_EXAMPLE_FORWARD_BACKWARD_NO_OPTIMIZER',
   backwardSeconds=backward,gradientNorm=norm,all119MSelectedGradientsFinite=True,
   originalPublishedWeightFileUnchanged=True,publishedWeightsSha256=after,
   optimizerStepExecuted=False,optimizerSteadyStorageProven=False,largestShapeProven=False,
   wholeEpochFeasibleOrBeneficialProven=False,gpuInitialized=False)
except BaseException as error:
 state.update(state='STOPPED_REAL_CPU_BACKWARD_PARTIAL_RETAINED',error=repr(error),traceback=traceback.format_exc())
finally:
 pressure.close();save(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.monotonic()-tick)
 atomic_json(run/'result.json',state)
 print(json.dumps(state,ensure_ascii=False),flush=True)
