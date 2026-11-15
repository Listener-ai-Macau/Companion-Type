"""One fixed joint candidate, bounded causal prefill, deadline-aware full meetings."""
from pathlib import Path
from datetime import datetime
import argparse,faulthandler,gc,hashlib,json,os,time,wave
faulthandler.enable()
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['allocation-control','control','full'],required=True)
 for key in ['control','run','inventory']:p.add_argument('--'+key,type=Path,required=True)
 a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 B=read(a.control/'overnight-binding.json');assert sha(__file__)==B['workerSha256']
 for file,digest in B['helpers'].items():assert sha(file)==digest,file
 C=Path(B['modelControl']);assert sha(C/'full-audio-only.json')==B['wholeManifestSha256']
 deadline=datetime.fromisoformat(B['neuralDeadline'])
 state={'state':'STARTING_'+a.phase.upper(),'startedAt':datetime.now().astimezone().isoformat(),
  'completed':[],'referenceRead':False,'speakerCountHintUsed':False,'newWeightTraining':False,
  'qualityQualified':False,'automaticRetries':0,'deadline':B['neuralDeadline']}
 def save():state['limits']=limits.query();atomic_json(a.run/(a.phase+'-state.json'),state,progress=True)
 def check_stop():
  if (a.run/'stop.request').exists() or datetime.now().astimezone()>=deadline:
   raise InterruptedError('Owned stop or frozen overnight deadline; keep partial output and completed meetings')
 started=time.perf_counter();last_progress=[0.];save()
 try:
  import torch,numpy as np
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  assert torch.version.hip and torch.cuda.device_count()==1
  gpu=torch.cuda.get_device_properties(0);assert gpu.name=='AMD Radeon RX 6800 XT' and gpu.gcnArchName.startswith('gfx1030')
  inventory=read(a.inventory);assert inventory['selected']['name']==gpu.name and inventory['selected']['architecture']=='gfx1030'
  assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()<1800
  from companion_community1_adapter_20261115 import pin_rocm_blas
  state['blas']=pin_rocm_blas(Path(B['blas']),B['blasSha256']);save()
  if a.phase=='allocation-control':
   import psutil
   free,total=torch.cuda.mem_get_info();assert free>B['allocationProbeBytes']+2*1024**3
   tensors=[];rows=[];process=psutil.Process()
   for n in range(B['allocationProbeBytes']//(512*1024**2)):
    check_stop();tensors.append(torch.zeros((512*1024**2,),device='cuda:0',dtype=torch.uint8));torch.cuda.synchronize()
    row={'allocatedBytes':(n+1)*512*1024**2,'privateBytes':process.memory_info().private,
     'gpuAllocatedBytes':torch.cuda.memory_allocated(),'gpuReservedBytes':torch.cuda.memory_reserved()}
    rows.append(row);atomic_json(a.run/'allocation-control.json',{'rows':rows,'modelLoaded':False,'qualityQualified':False})
    assert row['privateBytes']<int(1.8*1024**3),'Stop device allocation feasibility probe before original2GiB boundary'
   state.update(state='PASS_FIXED_GPU_ALLOCATION_UNDER_EXISTING_PRIVATE_BUDGET',deviceAllocationBytes=B['allocationProbeBytes'])
   return
  from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
  from moss_native_architecture_20261115 import load_public_native
  from moss_native_full_execution_20261115 import prepare_wave,install_native_bounded
  from moss_causal_prefill_20261115 import tiny_cpu_control,install_causal_prefill,fixed_native_cache
  if a.phase=='control':
   atomic_json(a.run/'tiny-causal-control.json',tiny_cpu_control(torch=torch));gc.collect()
  else:assert read(a.run/'control-state.json')['state']=='PASS_NATIVE_CPU_AND_PUBLISHED_GPU_CAUSAL_PREFILL'
  P=read(C/'preparation.json')
  for asset in P['files']:assert sha(asset['file'])==asset['sha256']
  processor=AutoProcessor.from_pretrained(P['nativeModelRoot'],local_files_only=True,trust_remote_code=False)
  model,weight_proof=load_public_native(C,P['nativeModelRoot'],torch=torch,device='cuda:0')
  atomic_json(a.run/(a.phase+'-weight-roundtrip.json'),weight_proof)
  def acoustic(done,total):
   check_stop();state.update(state='ENCODING_ORIGINAL_AUDIO',encoderDone=done,encoderTotal=total);save()
  def attention(stats):
   check_stop()
   if time.monotonic()-last_progress[0]>15:
    state['executionStats']=dict(stats);save();last_progress[0]=time.monotonic()
  execution=install_native_bounded(model,torch=torch,encoder_progress=acoustic,attention_progress=attention)
  import psutil
  process=psutil.Process();probes=[];probe_count=[0]
  def memory_probe(label):
   if label.startswith('first-layer/') and probe_count[0]>=250:return
   probe_count[0]+=1
   row={'at':datetime.now().astimezone().isoformat(),'label':label,
    'privateBytes':process.memory_info().private,'gpuAllocatedBytes':torch.cuda.memory_allocated(),
    'gpuReservedBytes':torch.cuda.memory_reserved()}
   with (a.run/(a.phase+'-allocation-trace.jsonl')).open('a',encoding='utf-8') as out:
    out.write(json.dumps(row)+'\n');out.flush()
  def register_probe(name,module):
   probes.append(module.register_forward_pre_hook(lambda module,args:memory_probe(name+'-before')))
   probes.append(module.register_forward_hook(lambda module,args,result:memory_probe(name+'-after')))
  # One first-layer traversal identifies the last actual operator if a native
  # failure interrupts Python. This is not an additional model experiment.
  for name,module in model.model.language_model.layers[0].named_modules():
   if name in ['', 'self_attn','self_attn.q_proj','self_attn.k_proj','self_attn.v_proj',
    'self_attn.o_proj','mlp','mlp.gate_proj','mlp.up_proj','mlp.down_proj']:
    register_probe('first-layer/'+name,module)
  def prefill(done,total,stats):
   check_stop();state.update(state='PREFILL_FULL_CAUSAL_CACHE_IN_BOUNDED_TOKEN_BLOCKS',prefillDone=done,prefillTotal=total)
   if done==total or time.monotonic()-last_progress[0]>10:
    state.update(prefillStats=dict(stats),executionStats=dict(execution));save();last_progress[0]=time.monotonic()
  if a.phase=='control':
   assert sha(B['controlAudio'])==B['controlAudioSha256']
   inputs,receipt=prepare_wave(processor,B['controlAudio'],a.run/'control-input',torch=torch)
   atomic_json(a.run/'control-input.json',receipt);inputs=inputs.to('cuda:0',torch.bfloat16)
   with torch.inference_mode():
    expected=model(**inputs,use_cache=True,logits_to_keep=1)
    schedule=install_causal_prefill(model,torch=torch,progress=prefill,memory_probe=memory_probe)
    actual=model(**inputs,past_key_values=fixed_native_cache(model,capacity=inputs['input_ids'].shape[1]+17),use_cache=True,logits_to_keep=1)
    logit_difference=float((actual.logits.float()-expected.logits.float()).abs().max())
    assert torch.allclose(actual.logits,expected.logits,atol=.125,rtol=.01),logit_difference
    assert int(actual.logits[0,-1].argmax())==int(expected.logits[0,-1].argmax()),'Native next token diverged'
    cache_errors=[]
    assert len(actual.past_key_values.layers)==len(expected.past_key_values.layers)
    for left,right in zip(actual.past_key_values.layers,expected.past_key_values.layers):
     for key in ['keys','values']:
      x,y=getattr(left,key),getattr(right,key);x=x[...,:y.shape[-2],:]
      difference=float((x.float()-y.float()).abs().max());cache_errors.append(difference)
      assert torch.allclose(x,y,atol=.0625,rtol=.01),(key,difference)
    generated=[]
    for _ in range(16):
     check_stop();token=actual.logits[:,-1:].argmax(-1)
     assert torch.equal(token,expected.logits[:,-1:].argmax(-1)),'Greedy16 continuation divergence'
     generated.append(int(token));actual=model(input_ids=token,past_key_values=actual.past_key_values,use_cache=True,logits_to_keep=1)
     expected=model(input_ids=token,past_key_values=expected.past_key_values,use_cache=True,logits_to_keep=1)
    torch.cuda.synchronize()
   atomic_json(a.run/'published-gpu-causal-control.json',{
    'state':'PASS_PUBLISHED_NATIVE_BF16_PREFILL_AND16_GREEDY_TOKENS','audioSha256':B['controlAudioSha256'],
    'audioSeconds':receipt['audioSeconds'],'logitMaxAbsDifference':logit_difference,'cacheMaxAbsDifferences':cache_errors,
    'logitTolerance':{'atol':.125,'rtol':.01},'cacheTolerance':{'atol':.0625,'rtol':.01},
    'next16TokenIds':generated,'prefillStats':schedule,'fullContextRetained':True,'bitwiseEqualityClaimed':False,
    'qualityQualified':False,'meaning':'Numerical execution control on original public training audio, not a quality score.'})
   state.update(state='PASS_NATIVE_CPU_AND_PUBLISHED_GPU_CAUSAL_PREFILL')
  else:
   schedule=install_causal_prefill(model,torch=torch,progress=prefill,memory_probe=memory_probe)
   for case in read(C/'full-audio-only.json'):
    check_stop();assert sha(case['audio'])==case['audioSha256']
    state.update(state='PREPARING_COMPLETE_ORIGINAL_RECORDING',meeting=case['meeting'],generatedTokens=0);save()
    inputs,input_receipt=prepare_wave(processor,case['audio'],a.run/'inputs'/case['meeting'],torch=torch)
    assert input_receipt['frames']==case['frames'] and input_receipt['audioSeconds']==case['audioSeconds']
    atomic_json(a.run/(case['meeting']+'-input.json'),input_receipt)
    inputs=inputs.to('cuda:0',torch.bfloat16);length=inputs['input_ids'].shape[1]
    before=execution['encoderCalls'];tick=time.perf_counter();last_token_save=[0.]
    class StopOwned(StoppingCriteria):
     def __call__(self,input_ids,scores,**kwargs):
      check_stop();count=input_ids.shape[1]-length
      if count==1 or time.monotonic()-last_token_save[0]>15:
       generated=input_ids[0,length:].cpu().tolist()
       state.update(state='GENERATING_WHOLE_MEETING_WORDS_SPEAKERS_TIMES',generatedTokens=count,
        executionStats=dict(execution),prefillStats=dict(schedule));save()
       atomic_json(a.run/(case['meeting']+'-partial-ids.json'),{'audioSha256':case['audioSha256'],
        'generatedIds':generated,'notFinal':True,'qualityQualified':False});last_token_save[0]=time.monotonic()
      return False
    cache=fixed_native_cache(model,capacity=length+32768)
    with torch.inference_mode():ids=model.generate(**inputs,past_key_values=cache,disable_compile=True,
     max_new_tokens=32768,do_sample=False,logits_to_keep=1,stopping_criteria=StoppingCriteriaList([StopOwned()]))
    torch.cuda.synchronize();generated=ids[0,length:].cpu().tolist();elapsed=time.perf_counter()-tick
    raw=processor.tokenizer.decode(generated,skip_special_tokens=False,clean_up_tokenization_spaces=False)
    parsed=processor.decode(ids[:,length:],return_format='parsed')[0]
    eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
    packet={'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
     'generatedIds':generated,'rawDecoded':raw,'parsedSegments':parsed,'naturalEos':bool(generated and generated[-1] in eos),
     'seconds':elapsed,'inputTokens':length,'completeOriginalRecordingInput':True,'noSpeakerResetOrContextTruncation':True,
     'timestampOutOfBoundsSegments':[i for i,r in enumerate(parsed) if not 0<=r['Start']<r['End']<=case['audioSeconds']],
     'referenceUsed':False,'speakerCountsUsed':False,'newWeightTraining':False,'qualityQualified':False,
     'executionStats':dict(execution),'prefillStats':dict(schedule),'kvStorage':'NativeStaticCache BF16 full capacity, eager generation, no quantization'}
    atomic_json(a.run/(case['meeting']+'-raw.json'),packet)
    assert packet['naturalEos'],'Output cap reached: retain incomplete output, do not classify as complete'
    assert execution['encoderCalls']-before==1
    state['completed'].append({'meeting':case['meeting'],'seconds':elapsed,'generatedTokens':len(generated),
     'segments':len(parsed),'naturalEos':True,'timestampOutOfBounds':len(packet['timestampOutOfBoundsSegments'])});save()
    del inputs,ids,parsed,generated,cache;gc.collect();torch.cuda.empty_cache()
   state.update(state='COMPLETE_FOUR_ORIGINAL_MEETING_JOINT_OUTPUTS_SCORING_PENDING')
 except BaseException as error:state.update(state='FAILED_OR_STOPPED_'+a.phase.upper()+'_RETAINED',error=repr(error));raise
 finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-started);save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
