"""CPU-only complete-context inference, read-only mapped weights and shared file-backed KV."""
from pathlib import Path
from datetime import datetime
import argparse,faulthandler,hashlib,json,os,time
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
faulthandler.enable()
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['prefill','decode'],required=True)
 p.add_argument('--meeting',required=True)
 for key in ['control','run']:p.add_argument('--'+key,type=Path,required=True)
 a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 B=read(a.control/'staged-binding.json');assert sha(__file__)==B['workerSha256']
 for file,digest in B['helpers'].items():assert sha(file)==digest,file
 C=Path(B['modelControl']);case=next(r for r in B['cases'] if r['meeting']==a.meeting)
 deadline=datetime.fromisoformat(B['neuralDeadline']);began=time.perf_counter();last=[0.]
 state={'state':'STARTING_'+a.phase.upper(),'meeting':a.meeting,'startedAt':datetime.now().astimezone().isoformat(),
  'referenceRead':False,'speakerCountsUsed':False,'qualityQualified':False,'newWeightTraining':False,'automaticRetries':0}
 def save():state['limits']=limits.query();atomic_json(a.run/(a.meeting+'-'+a.phase+'-state.json'),state,progress=True)
 def checkpoint():
  if (a.run/'stop.request').exists() or datetime.now().astimezone()>=deadline:raise InterruptedError('Owned stop/deadline, original cache retained')
 def progress(label,**values):
  checkpoint();state.update(state=label,**values)
  if time.monotonic()-last[0]>10:save();last[0]=time.monotonic()
 save()
 try:
  import torch
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  state['executionDevice']='cpu';state['cpuCapability']=torch.backends.cpu.get_cpu_capability()
  from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
  from moss_cpu_mapped_runtime_20261116 import load_cpu_mapped_native,cpu_file_cache,restore_cpu_prefill,retire_cpu_audio
  from moss_native_full_execution_20261115 import prepare_wave,install_native_bounded
  from moss_causal_prefill_20261115 import fixed_native_cache,install_causal_prefill
  from moss_native_cache_store_20261115 import store,restore,retire_audio,provide_prefill_once
  P=read(C/'preparation.json')
  for row in P['files']:assert sha(row['file'])==row['sha256']
  processor=AutoProcessor.from_pretrained(P['nativeModelRoot'],local_files_only=True,trust_remote_code=False)
  model,proof=load_cpu_mapped_native(C,P['nativeModelRoot'],torch=torch)
  atomic_json(a.run/(a.meeting+'-'+a.phase+'-weights.json'),proof)
  cache_dir=Path(case['reusedPrefill']['cache']) if case.get('reusedPrefill') else a.run/'cache'/a.meeting
  if a.phase=='prefill':
   assert sha(case['audio'])==case['audioSha256']
   execution=install_native_bounded(model,torch=torch,
    encoder_progress=lambda done,total:progress('ENCODING_ALL_ORIGINAL_AUDIO',encoderDone=done,encoderTotal=total))
   schedule=install_causal_prefill(model,torch=torch,
    progress=lambda done,total,stats:progress('PREFILL_ALL_CONTEXT_NO_RESET',done=done,total=total,prefillStats=dict(stats)))
   inputs,receipt=prepare_wave(processor,case['audio'],a.run/'inputs'/a.meeting,torch=torch)
   assert receipt['frames']==case['frames'];atomic_json(a.run/(a.meeting+'-input.json'),receipt)
   inputs=inputs.to('cpu',torch.bfloat16);cache=cpu_file_cache(model,a.run/'mapped-prefill'/a.meeting,torch=torch,capacity=inputs['input_ids'].shape[1]+32768)
   tick=time.perf_counter()
   with torch.inference_mode():output=model(**inputs,past_key_values=cache,use_cache=True,logits_to_keep=1)
   prefill_seconds=time.perf_counter()-tick
   assert execution['encoderCalls']==1
   manifest=store(cache_dir,cache,output.logits,inputs,torch=torch,checkpoint=checkpoint,
    metadata={'meeting':a.meeting,'audioSha256':case['audioSha256'],'frames':case['frames'],
     'audioSeconds':case['audioSeconds'],'prefillSeconds':prefill_seconds,'allOriginalWindows':receipt['allOriginalAudioWindows'],
     'executionStats':execution,'prefillStats':schedule,'nativeWeightProof':proof})
   state.update(state='COMPLETE_FULL_AUDIO_PREFILL_STORED_NO_WORDS_GENERATED',cacheManifestSha256=sha(cache_dir/'manifest.json'),
    tokens=manifest['tokens'],prefillSeconds=prefill_seconds)
  else:
   prefill_path=Path(case['reusedPrefill']['state']) if case.get('reusedPrefill') else a.run/(a.meeting+'-prefill-state.json')
   if case.get('reusedPrefill'):assert sha(prefill_path)==case['reusedPrefill']['stateSha256']
   prefill=read(prefill_path)
   assert prefill['state']=='COMPLETE_FULL_AUDIO_PREFILL_STORED_NO_WORDS_GENERATED'
   assert sha(cache_dir/'manifest.json')==prefill['cacheManifestSha256']
   retire_cpu_audio(model,torch=torch)
   cache,logits,ids,mask,manifest=restore_cpu_prefill(cache_dir,model,a.run/'mapped-decode'/a.meeting,torch=torch,checkpoint=checkpoint)
   assert manifest['metadata']['audioSha256']==case['audioSha256'] and manifest['metadata']['frames']==case['frames']
   assert int(cache.get_seq_length())==ids.shape[1]==manifest['tokens']
   model.model.language_model.set_attn_implementation('sdpa')
   torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False)
   torch.backends.cuda.enable_math_sdp(True);torch.backends.cuda.enable_cudnn_sdp(False)
   manual=B.get('cpuEosGreedy',False)
   restored=None if manual else provide_prefill_once(model,cache,logits,ids,torch=torch)
   length=ids.shape[1];tick=time.perf_counter();token_times=[]
   expected=case.get('expectedPrefixIds',[])
   class StopOwned(StoppingCriteria):
    def __call__(self,input_ids,scores,**kwargs):
     checkpoint();n=input_ids.shape[1]-length
     if n<=len(expected):assert int(input_ids[0,-1])==expected[n-1],('Retained native prefix diverged',n)
     if n<=64:token_times.append({'tokens':n,'seconds':time.perf_counter()-tick})
     if n==1 or time.monotonic()-last[0]>15:
      generated=input_ids[0,length:].cpu().tolist();state.update(state='DECODING_RESTORED_WHOLE_CAUSAL_CONTEXT',generatedTokens=n,
       decodeSeconds=time.perf_counter()-tick,tokensPerSecond=n/(time.perf_counter()-tick));save()
      atomic_json(a.run/(a.meeting+'-partial-ids.json'),{'generatedIds':generated,'audioSha256':case['audioSha256'],
       'notFinal':True,'qualityQualified':False});last[0]=time.monotonic()
     return False
   if manual:
    from moss_native_greedy_20261115 import greedy,install_prefix_replay_attention
    install_prefix_replay_attention(torch=torch)
    resume=case.get('resumeGeneratedIds',[])
    if case.get('resumeGeneratedPrefix'):
     bound=case['resumeGeneratedPrefix'];assert sha(bound['file'])==bound['sha256']
     source=read(bound['file']);assert source['audioSha256']==case['audioSha256'];resume=source['generatedIds']
    def advance(generated):
     n=len(generated)
     if len(token_times)<64:token_times.append({'tokens':n,'seconds':time.perf_counter()-tick})
     if n==1 or time.monotonic()-last[0]>15:
      state.update(state='DECODING_COMPLETE_CONTEXT_CPU_EOS',generatedTokens=n,retainedPrefixTokens=len(resume),
       decodeSeconds=time.perf_counter()-tick,tokensPerSecond=(n-len(resume))/(time.perf_counter()-tick),
       mappedWorkingSetBytes=__import__('psutil').Process().memory_info().rss,availableSystemBytes=__import__('psutil').virtual_memory().available);save()
      atomic_json(a.run/(a.meeting+'-partial-ids.json'),{'generatedIds':generated,'audioSha256':case['audioSha256'],
       'notFinal':True,'qualityQualified':False});last[0]=time.monotonic()
    def allocator_release(event):
     event=dict(event,at=datetime.now().astimezone().isoformat(),meeting=a.meeting)
     state['gpuLastUnusedCacheRelease']=event
     with (a.run/(a.meeting+'-gpu-allocator-events.jsonl')).open('a',encoding='utf-8') as log:
      log.write(json.dumps(event)+'\n')
    with torch.inference_mode():generated,restored=greedy(model,cache,logits,torch=torch,
     max_tokens=case.get('maxNewTokens',32768),expected_prefix=expected,resume_prefix=resume,checkpoint=checkpoint,progress=advance,
     step_pause_seconds=B.get('decodeStepPauseSeconds',0.),synchronize_each_forward=B.get('synchronizeEachDecodeForward',False),
     release_unused_interval=0,on_memory_release=allocator_release,
     on_prefix_replay=lambda done,total:progress('REPLAYING_RETAINED_MODEL_PREFIX_CPU',replayedTokens=done,replayedTotal=total))
    output=torch.tensor([generated],dtype=torch.long)
   else:
    with torch.inference_mode():output=model.generate(input_ids=ids,attention_mask=mask,past_key_values=cache,disable_compile=True,
     do_sample=False,max_new_tokens=case.get('maxNewTokens',32768),logits_to_keep=1,stopping_criteria=StoppingCriteriaList([StopOwned()]))
    generated=output[0,length:].cpu().tolist()
   elapsed=time.perf_counter()-tick
   assert (restored.get('savedFirstLogitsUsedOrVerified') if manual else restored['served']) and generated[:len(expected)]==expected
   atomic_json(a.run/(a.meeting+'-generated-ids.json'),{'generatedIds':generated,'audioSha256':case['audioSha256'],
    'seconds':elapsed,'expectedPrefixMatched':len(expected),'qualityQualified':False})
   raw=processor.tokenizer.decode(generated,skip_special_tokens=False,clean_up_tokenization_spaces=False)
   decoded_ids=output if manual else output[:,length:]
   parsed=[] if case.get('runtimeControl') else processor.decode(decoded_ids,return_format='parsed')[0]
   native_parse_error=None
   if not isinstance(parsed,list) or not all(isinstance(row,dict) for row in parsed):
    native_parse_error={'type':type(parsed).__name__,'value':parsed};parsed=[]
   eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
   packet={'meeting':a.meeting,'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
    'generatedIds':generated,'rawDecoded':raw,'parsedSegments':parsed,'naturalEos':bool(generated and generated[-1] in eos),
    'seconds':elapsed,'inputTokens':length,'completeOriginalRecordingInput':not case.get('runtimeControl',False),
    'noSpeakerResetOrContextTruncation':True,'referenceUsed':False,'speakerCountsUsed':False,'newWeightTraining':False,
    'qualityQualified':False,'stagedCacheRestoredBitExact':True,'cacheManifestSha256':prefill['cacheManifestSha256'],
    'cachedPrefillLogitsReplayedOnce':not manual,'completedAcousticModulesRemovedBeforeRestore':True,'prefixMatched':len(expected),
    'executionDevice':'cpu','weightsReadonlyMapped':True,'kvSharedFileMapped':True,
    'generationLoop':'batch1-native-argmax-cpu-eos' if manual else 'native-GenerationMixin',
    'resumeProof':restored,'nativeParseError':native_parse_error,
    'first64TokenTiming':token_times,'producer':manifest['metadata'],
    'timestampOutOfBoundsSegments':[i for i,r in enumerate(parsed) if not 0<=r['Start']<r['End']<=case['audioSeconds']]}
   atomic_json(a.run/(a.meeting+'-raw.json'),packet)
   if case.get('runtimeControl'):assert generated==expected
   else:assert packet['naturalEos'],'Incomplete output cap retained, no retry'
   state.update(state='PASS_BIT_EXACT_STAGED_NATIVE16_TOKEN_CONTROL' if case.get('runtimeControl') else 'COMPLETE_WHOLE_MEETING_JOINT_OUTPUT_SCORING_PENDING',
    generatedTokens=len(generated),decodeSeconds=elapsed,naturalEos=packet['naturalEos'],retainedPrefixMatched=len(expected),
    newGeneratedTokens=len(generated)-(len(resume) if manual else 0),
    tokensPerSecond=(len(generated)-(len(resume) if manual else 0))/elapsed)
 except BaseException as error:state.update(state='FAILED_OR_STOPPED_STAGED_'+a.phase.upper(),error=repr(error));raise
 finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began);save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
