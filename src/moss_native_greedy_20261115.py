"""Same batch1 greedy argmax/EOS rule with CPU-owned stopping and prefix replay."""
def install_prefix_replay_attention(*,torch):
 import torch.nn.functional as F
 from moss_amd_execution_20261104 import bounded_sdpa
 from moss_key_streamed_attention_20261104 import key_streamed_sdpa
 original=F.scaled_dot_product_attention
 def keyed(q,k,v,attn_mask=None,dropout_p=0.,is_causal=False,*,scale=None,enable_gqa=False):
  if q.shape[-2]>1 and k.shape[-2]>1024:
   return key_streamed_sdpa(q,k,v,attn_mask,dropout_p,is_causal,scale=scale,enable_gqa=enable_gqa,key_block=1024)
  return original(q,k,v,attn_mask=attn_mask,dropout_p=dropout_p,is_causal=is_causal,scale=scale,enable_gqa=enable_gqa)
 def scheduled(*args,**kwargs):return bounded_sdpa(keyed,*args,**kwargs,query_block=128)
 F.scaled_dot_product_attention=scheduled
def greedy(model,cache,logits,*,torch,max_tokens,expected_prefix,resume_prefix,checkpoint,progress,
           step_pause_seconds=0.,synchronize_each_forward=False,release_unused_interval=0,on_memory_release=None):
 import time
 assert 0.<=step_pause_seconds<=.25
 assert isinstance(release_unused_interval,int) and release_unused_interval>=0
 forward_count=0;release_count=0
 def release_allocator(reason):
  nonlocal release_count
  torch.cuda.synchronize()
  event={'forwardCount':forward_count,'contextTokens':int(cache.get_seq_length()),'reason':reason,
   'beforeAllocatedBytes':torch.cuda.memory_allocated(),'beforeReservedBytes':torch.cuda.memory_reserved()}
  torch.cuda.empty_cache();release_count+=1
  event.update(afterAllocatedBytes=torch.cuda.memory_allocated(),afterReservedBytes=torch.cuda.memory_reserved())
  if on_memory_release:on_memory_release(event)
 def settle():
  nonlocal forward_count
  forward_count+=1
  if synchronize_each_forward:torch.cuda.synchronize()
  if release_unused_interval and forward_count%release_unused_interval==0:
   release_allocator('periodic-unused-allocation-release')
  if step_pause_seconds:time.sleep(step_pause_seconds)
  checkpoint()
 assert not model.training and not torch.is_grad_enabled()
 config=model.generation_config
 for name,value in {'num_beams':1,'repetition_penalty':1.,'no_repeat_ngram_size':0,
  'forced_bos_token_id':None,'forced_eos_token_id':None,'bad_words_ids':None,'suppress_tokens':None,
  'begin_suppress_tokens':None,'sequence_bias':None}.items():
  observed=getattr(config,name,None)
  # Transformers5.22 leaves omitted generation fields as None until generate
  # merges standard defaults. The pinned model file specifies none of these.
  assert observed is None or observed==value,(name,observed)
 eos=config.eos_token_id;eos=[eos] if isinstance(eos,int) else list(eos)
 generated=list(resume_prefix);initial=int(cache.get_seq_length())
 if generated:
  assert int(logits[0,-1].float().argmax().item())==generated[0]
  assert generated[:len(expected_prefix)]==list(expected_prefix)[:len(generated)]
  assert not any(t in eos for t in generated)
  for start in range(0,len(generated),128):
   checkpoint();block=torch.tensor([generated[start:start+128]],device='cuda:0',dtype=torch.long)
   result=model(input_ids=block,past_key_values=cache,use_cache=True,logits_to_keep=1)
   settle()
   assert result.past_key_values is cache;logits=result.logits
  assert int(cache.get_seq_length())==initial+len(generated)
  if release_unused_interval:release_allocator('retained-prefix-replay-complete')
 while len(generated)<max_tokens:
  checkpoint();token=int(logits[0,-1].float().argmax().item())
  if len(generated)<len(expected_prefix):assert token==expected_prefix[len(generated)],('Native greedy prefix diverged',len(generated)+1)
  generated.append(token);progress(generated)
  if token in eos or len(generated)==max_tokens:break
  result=model(input_ids=torch.tensor([[token]],device='cuda:0'),past_key_values=cache,use_cache=True,logits_to_keep=1)
  settle()
  assert result.past_key_values is cache;logits=result.logits
 return generated,{'savedFirstLogitsUsedOrVerified':True,'originalGeneratedPrefixTokensReplayed':len(resume_prefix),
  'noReferenceTeacherForcing':True,'allOriginalGeneratedPrefixIdsPreserved':True,'cpuEosDecision':True,
  'stepPauseSeconds':step_pause_seconds,'synchronizeEachForward':synchronize_each_forward,
  'unusedAllocatorReleaseInterval':release_unused_interval,'unusedAllocatorReleaseCount':release_count}
