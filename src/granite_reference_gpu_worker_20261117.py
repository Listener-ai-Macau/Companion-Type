"""Same fixed native Granite reference on RX6800XT, using prepared native inputs.

The validated bounded streamed loader transfers original BF16 bytes once. There
is no CPU audio frontend or per-token host weight offload in this worker.
"""
from pathlib import Path
from datetime import datetime
import argparse,gc,json,os,sys,threading,time,traceback
os.environ.update(OMP_NUM_THREADS='4',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
import psutil
from meeting_acoustic_contract_20261116 import read,sha,require,select_gpu
from meeting_acoustic_worker_20261116 import own_limits,present_discrete_gpu
from moss_windows_resource_limits_20261104 import SystemRamPressure
from companion_local_pcm_session_20261114 import exclusive_file
from durable_model_state_20261117 import atomic_json

ap=argparse.ArgumentParser();ap.add_argument('--protocol',type=Path,required=True)
mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--inspect',action='store_true');mode.add_argument('--execute',action='store_true')
a=ap.parse_args();P=read(a.protocol);limits=own_limits(5 if a.inspect else 25)
require(sha(__file__)==P['workerSha256'],'Frozen GPU worker changed')
for item in P['files']:require(sha(item['file'])==item['sha256'],'Frozen source/asset changed: '+item['file'])
require(P['computeDevice']=='rx6800xt' and len(P['cases'])==12,'One fixed original reference only')
prepared=read(P['preparedNativeInputs']);inputs_by_id={v['id']:v for v in prepared['cases']}
require(prepared['state']=='PASS_ALL12_NATIVE_PROCESSOR_GEOMETRY_AND_PINNED_TEMPLATE' and not prepared['referenceUsed'],'Native frontend receipt required')
for c in P['cases']:
 require(set(c)=={'id','audio','audioSha256','pcmSha256','frames'} and c['id'].startswith(('ES2003b-','EN2001a-')),'Unexpected input or label')
 v=inputs_by_id[c['id']]
 require(sha(c['audio'])==c['audioSha256'] and v['audioSha256']==c['audioSha256'] and v['pcmSha256']==c['pcmSha256'] and v['frames']==c['frames'],'Original input changed')
 require(sha(v['file'])==v['sha256'],'Prepared original native inputs changed')
if a.inspect:
 print(json.dumps({'state':'PASS_FIXED_GPU_REFERENCE_SOURCE_ASSET_AND_PREPARED_INPUT_INSPECTION',
  'cases':12,'torchImported':'torch' in sys.modules,'newNeuralCalls':0,'trainingUpdates':0,
  'gpuExecutionVerified':False,'limits':limits.query()}));sys.exit(0)

# Presence is checked before torch import, model allocation or creating a run.
present=present_discrete_gpu()
out=Path(P['run']);out.mkdir(exist_ok=False)
pressure=SystemRamPressure();closing=threading.Event();mutex=threading.RLock();start=time.monotonic()
state=dict(state='PREPARING_NATIVE_GPU_GRANITE_REFERENCE',startedAt=datetime.now().astimezone().isoformat(),
 pid=os.getpid(),createdAt=psutil.Process().create_time(),completed=[],newNeuralCalls=0,
 attemptedOriginalCases=0,newTrainingUpdates=0,referenceRead=False,qualityQualified=False,saleQualified=False,
 protocolSha256=sha(a.protocol),presentDevices=present)
def save(**values):
 with mutex:
  state.update(values,observedAt=datetime.now().astimezone().isoformat(),elapsedSeconds=time.monotonic()-start,limits=limits.query())
  atomic_json(out/'state.json',state,progress=True)
def reason():
 if (out/'stop.request').exists():return 'Owned stop request'
 if time.monotonic()-start>P['maximumSeconds']:return 'Frozen run deadline'
 if pressure.low() or psutil.virtual_memory().available<P['minimumAvailableBytes']:return 'Original low-memory protection'
 return None
def check():
 why=reason()
 if why:raise InterruptedError(why)
def watch():
 while not closing.wait(.5):
  why=reason()
  if why:
   atomic_json(out/'stop-observed.json',{'reason':why,'state':state,'limits':limits.query()});os._exit(76)
  if int(time.monotonic()-start)%5==0:save()
try:
 with exclusive_file(Path(P['neuralLock'])):
  save();check();threading.Thread(target=watch,daemon=True).start()
  import torch,transformers
  require(torch.__version__==P['gpuRuntime']['torch'] and torch.version.hip and transformers.__version__==P['gpuRuntime']['transformers'],'Frozen GPU runtime changed')
  torch.set_num_threads(4);torch.set_num_interop_threads(1)
  inventory=[{'index':i,'name':torch.cuda.get_device_properties(i).name,
   'architecture':getattr(torch.cuda.get_device_properties(i),'gcnArchName','')} for i in range(torch.cuda.device_count())]
  chosen=select_gpu(inventory);device=torch.device('cuda:'+str(chosen['index']));torch.cuda.set_device(device)
  from companion_community1_adapter_20261115 import pin_rocm_blas
  pin_rocm_blas(P['blas']['file'],P['blas']['sha256'])
  free,total=torch.cuda.mem_get_info(device)
  require(free>=P['checkpointTensorBytes']+2*1024**3,'Original model plus2GiB device workspace does not fit')
  save(state='CHECKING_NATIVE_GPU_TRANSFER_CONTROL',device=chosen,gpuFreeAtAdmission=free,gpuTotalBytes=total)
  from accelerate import init_empty_weights
  from transformers import AutoConfig,AutoTokenizer,GraniteSpeechForConditionalGeneration,StoppingCriteria,StoppingCriteriaList
  from transformers.conversion_mapping import get_checkpoint_conversion_mapping
  from transformers.core_model_loading import WeightRenaming,rename_source_key
  from moss_streamed_weights_20261104 import load_streamed_weights
  from safetensors.torch import save_file,load_file
  torch.manual_seed(20261117)
  tiny=torch.nn.Sequential(torch.nn.Linear(8,16),torch.nn.GELU(),torch.nn.Linear(16,8)).to(device=device,dtype=torch.bfloat16).eval().requires_grad_(False)
  file=out/'tiny-transfer.safetensors';save_file({k:v.cpu().contiguous() for k,v in tiny.state_dict().items()},str(file))
  values,control=load_streamed_weights(file,torch=torch,device=device,expected_sha256=sha(file),chunk_bytes=4096)
  with init_empty_weights():other=torch.nn.Sequential(torch.nn.Linear(8,16),torch.nn.GELU(),torch.nn.Linear(16,8))
  other.load_state_dict(values,strict=True,assign=True);other.eval().requires_grad_(False)
  x=torch.randn((2,8),device=device,dtype=torch.bfloat16)
  with torch.inference_mode():left=tiny(x);right=other(x)
  require(torch.equal(left,right),'Tiny native GPU transfer changed BF16 output')
  atomic_json(out/'native-gpu-transfer-control.json',{'state':'PASS_BIT_IDENTICAL_GPU_BF16_STANDARD_AND_STREAMED_WEIGHTS','transfer':control,'maxAbsDifference':float((left-right).abs().max())})
  del tiny,other,values,x,left,right;gc.collect();torch.cuda.empty_cache();check()
  config=AutoConfig.from_pretrained(P['modelRoot'],local_files_only=True,trust_remote_code=False)
  require(config.model_type=='granite_speech' and not config.has_lora_adapter,'Original architecture changed')
  config._attn_implementation='eager';config.text_config._attn_implementation='eager'
  previous=torch.get_default_dtype()
  try:
   torch.set_default_dtype(torch.bfloat16)
   with init_empty_weights(include_buffers=False):model=GraniteSpeechForConditionalGeneration(config)
  finally:torch.set_default_dtype(previous)
  model.eval().requires_grad_(False);meta=model.state_dict()
  transforms=get_checkpoint_conversion_mapping('granite_speech')
  require(len(transforms)==4 and all(isinstance(t,WeightRenaming) for t in transforms),'Official pure key mappings changed')
  index=read(Path(P['modelRoot'])/'model.safetensors.index.json');values={};receipts=[]
  for name in sorted(set(index['weight_map'].values())):
   check();save(state='STREAMING_ORIGINAL_BF16_TO_GPU_ONCE',activeShard=name)
   raw,receipt=load_streamed_weights(Path(P['modelRoot'])/name,torch=torch,device=device,expected_sha256=P['shardSha256'][name],chunk_bytes=8*1024**2)
   for key,value in raw.items():
    target,converter=rename_source_key(key,transforms,[])
    require(converter is None and target not in values and target in meta and meta[target].shape==value.shape,'Native key/shape mismatch')
    values[target]=value
   receipts.append(receipt);del raw
  require(set(values)==set(meta),'Native state is incomplete')
  model.load_state_dict(values,strict=True,assign=True);model.to(device).eval().requires_grad_(False)
  require(all(not p.is_meta and p.device==device and p.dtype==torch.bfloat16 for p in model.parameters()),'Published parameter/device contract changed')
  atomic_json(out/'native-gpu-weight-roundtrip.json',{'state':'PASS_ALL_ORIGINAL_TENSOR_BYTES_AND_NATIVE_KEYS','tensors':len(values),'shards':receipts})
  del values,meta;gc.collect();torch.cuda.empty_cache()
  tokenizer=AutoTokenizer.from_pretrained(P['modelRoot'],local_files_only=True,trust_remote_code=False)
  for c in P['cases']:
   check();v=inputs_by_id[c['id']];inputs={k:t.to(device) for k,t in load_file(v['file']).items()}
   torch.cuda.synchronize(device);tick=time.perf_counter()
   state['attemptedOriginalCases']+=1;save(state='DECODING_ONE_NATIVE_GRANITE_ENGLISH_REFERENCE',activeCase=c['id'],featureShape=list(inputs['input_features'].shape))
   class Stop(StoppingCriteria):
    def __call__(self,input_ids,scores,**kwargs):
     check()
     if time.perf_counter()-tick>P['maximumCaseSeconds']:raise InterruptedError('Frozen per-case deadline')
     return False
   with torch.inference_mode():output=model.generate(**inputs,do_sample=False,num_beams=1,max_new_tokens=P['maxNewTokens'],use_cache=True,disable_compile=True,stopping_criteria=StoppingCriteriaList([Stop()]))
   torch.cuda.synchronize(device);ids=output[0,inputs['input_ids'].shape[-1]:].cpu().tolist()
   eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos or []
   text=tokenizer.decode(ids,skip_special_tokens=True);natural=bool(ids and ids[-1] in eos)
   packet=dict(id=c['id'],text=text,generatedIds=ids,naturalTermination=natural,seconds=time.perf_counter()-tick,
    audioSha256=c['audioSha256'],pcmSha256=c['pcmSha256'],frames=c['frames'],protocolSha256=sha(a.protocol),
    referenceUsed=False,wordsPostEdited=False,trainingUpdates=0,actualDevice=str(device),actualDtype='published bfloat16',
    cpuFrontendPerformedInGpuWorker=False,weightTransfersDuringGeneration=False,qualityQualified=False)
   file=out/(c['id']+'.json');atomic_json(file,packet);state['newNeuralCalls']+=1
   require(natural and text.strip(),'Incomplete native output; retain without changed retry')
   state['completed'].append({'id':c['id'],'file':str(file),'sha256':sha(file)})
   save(gpuPeakAllocatedBytes=torch.cuda.max_memory_allocated(device));del inputs,output;gc.collect();torch.cuda.empty_cache()
  save(state='COMPLETE_NATIVE_GRANITE_12_CLIPS_PENDING_INDEPENDENT_SCORE',activeCase=None,gpuInitialized=True)
  atomic_json(out/'completed.json',state)
except BaseException as error:
 save(state='FAILED_NATIVE_GPU_GRANITE_REFERENCE_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error),traceback=traceback.format_exc())
 atomic_json(out/'completed.json',state);raise
finally:closing.set();pressure.close()
