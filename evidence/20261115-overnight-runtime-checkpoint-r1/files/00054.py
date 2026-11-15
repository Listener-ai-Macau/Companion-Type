"""Bound all decoder prefill operators, preserving full causal context and KV.

This is token scheduling inside a single native language-model forward. It does
not split the audio/session, re-prompt, reset speaker identities or discard KV.
Unsupported training/attention/positional modes are refused, not approximated.
"""
def fixed_native_cache(model, *, capacity):
 from transformers import StaticCache
 # Keep native in-place FP16/BF16 storage and mask lengths. The flag prevents
 # GenerationMixin from constructing a whole-prompt4D mask/compiling before
 # this module can schedule token blocks. It does not change stored values.
 class EagerStaticCache(StaticCache):
  @property
  def is_compileable(self):return False
 return EagerStaticCache(config=model.config.text_config,max_cache_len=capacity)

def install_causal_prefill(model, *, torch, token_block=128, progress=None, memory_probe=None):
 from transformers.modeling_outputs import BaseModelOutputWithPast
 assert not model.training and token_block==128
 language=model.model.language_model
 cfg=language.config
 assert cfg.rope_parameters['rope_type']=='default'
 assert all(v=='full_attention' for v in cfg.layer_types)
 original=language.forward
 stats={'prefillCalls':0,'blocks':0,'maximumBlockTokens':0,'maximumRetainedTokens':0,
  'tokenBlock':token_block,'allKeysRetained':True,'speakerOrAudioResets':0}
 def scheduled(input_ids=None,attention_mask=None,position_ids=None,past_key_values=None,
               inputs_embeds=None,use_cache=None,**kwargs):
  value=inputs_embeds if inputs_embeds is not None else input_ids
  length=value.shape[1]
  if length<=token_block:
   return original(input_ids=input_ids,attention_mask=attention_mask,position_ids=position_ids,
    past_key_values=past_key_values,inputs_embeds=inputs_embeds,use_cache=use_cache,**kwargs)
  assert not torch.is_grad_enabled(),'Inference-only bounded prefill'
  assert use_cache is True,'Native generation must retain the complete KV cache'
  assert input_ids is None and inputs_embeds is not None and inputs_embeds.shape[0]==1
  assert attention_mask is None or (attention_mask.ndim==2 and attention_mask.shape[0]==1)
  assert not kwargs.get('output_attentions') and not kwargs.get('output_hidden_states')
  assert set(kwargs)<= {'return_dict','output_attentions','output_hidden_states'},set(kwargs)
  assert kwargs.get('return_dict',True) is not False
  initial=int(past_key_values.get_seq_length()) if past_key_values is not None else 0
  if attention_mask is not None:assert attention_mask.shape[-1]==initial+length
  if position_ids is not None:assert position_ids.shape[-1]==length
  if memory_probe:memory_probe('prefill-before-unused-cache-release')
  # Native audio encoding has finished. Release only unreferenced allocator
  # blocks before allocating decoder workspaces; all live tensors/KV remain.
  if inputs_embeds.device.type=='cuda':
   import gc
   gc.collect();torch.cuda.synchronize();torch.cuda.empty_cache()
  if memory_probe:memory_probe('prefill-after-unused-cache-release')
  stats['prefillCalls']+=1;pieces=[];cache=past_key_values
  for start in range(0,length,token_block):
   stop=min(length,start+token_block)
   result=original(inputs_embeds=inputs_embeds[:,start:stop],
    attention_mask=attention_mask[...,:initial+stop] if attention_mask is not None else None,
    position_ids=position_ids[...,start:stop] if position_ids is not None else None,
    past_key_values=cache,use_cache=True,**kwargs)
   cache=result.past_key_values
   assert cache is not None and int(cache.get_seq_length())==initial+stop
   assert result.attentions is None and result.hidden_states is None
   assert result.last_hidden_state.shape[:2]==(1,stop-start)
   pieces.append(result.last_hidden_state)
   stats['blocks']+=1;stats['maximumBlockTokens']=max(stats['maximumBlockTokens'],stop-start)
   stats['maximumRetainedTokens']=max(stats['maximumRetainedTokens'],initial+stop)
   if progress:progress(initial+stop,initial+length,stats)
  return BaseModelOutputWithPast(last_hidden_state=torch.cat(pieces,dim=1),past_key_values=cache)
 language.forward=scheduled
 return stats

def tiny_cpu_control(*, torch):
 from transformers import MossTranscribeDiarizeConfig,MossTranscribeDiarizeForConditionalGeneration
 from transformers import Qwen3Config
 torch.manual_seed(20261115)
 text=Qwen3Config(vocab_size=64,hidden_size=32,intermediate_size=64,num_hidden_layers=2,
  num_attention_heads=4,num_key_value_heads=2,head_dim=8,max_position_embeddings=4096)
 config=MossTranscribeDiarizeConfig(text_config=text,
  audio_config={'d_model':32,'encoder_layers':1,'encoder_attention_heads':4,'encoder_ffn_dim':64,
   'num_mel_bins':4,'max_source_positions':4})
 model=MossTranscribeDiarizeForConditionalGeneration(config).eval()
 model.set_attn_implementation('sdpa')
 embeddings=torch.randn((1,389,32));mask=torch.ones((1,389),dtype=torch.long)
 # Explicit nonzero absolute positions also exercise preservation of native IDs.
 positions=torch.arange(11,400)[None,:]
 with torch.inference_mode():
  expected=model.model.language_model(inputs_embeds=embeddings,attention_mask=mask,position_ids=positions,use_cache=True)
  stats=install_causal_prefill(model,torch=torch)
  actual=model.model.language_model(inputs_embeds=embeddings,attention_mask=mask,position_ids=positions,use_cache=True)
  error=float((actual.last_hidden_state-expected.last_hidden_state).abs().max())
  assert torch.allclose(actual.last_hidden_state,expected.last_hidden_state,atol=2e-5,rtol=2e-5),error
  cache_errors=[]
  for left,right in zip(actual.past_key_values.layers,expected.past_key_values.layers):
   for key in ['keys','values']:
    a,b=getattr(left,key),getattr(right,key);diff=float((a-b).abs().max());cache_errors.append(diff)
    assert torch.allclose(a,b,atol=2e-5,rtol=2e-5),(key,diff)
  token=torch.tensor([[7]])
  a=model.model.language_model(input_ids=token,position_ids=torch.tensor([[400]]),past_key_values=actual.past_key_values,use_cache=True)
  b=model.model.language_model(input_ids=token,position_ids=torch.tensor([[400]]),past_key_values=expected.past_key_values,use_cache=True)
  assert torch.allclose(a.last_hidden_state,b.last_hidden_state,atol=2e-5,rtol=2e-5)
 return {'state':'PASS_NATIVE_CAUSAL_PREFILL_HIDDEN_KV_AND_NEXT_TOKEN_CPU_CONTROL',
  'hiddenMaxAbsDifference':error,'cacheMaxAbsDifferences':cache_errors,'stats':stats,
  'all389InputPositionsRetained':True,'nativePositionIdsPreserved':True}
