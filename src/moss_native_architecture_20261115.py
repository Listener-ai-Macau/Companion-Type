"""Official native joint model; exact published tensor reuse, no learned changes."""
from pathlib import Path
import hashlib,json,time
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def empty_native(config,*,torch,dtype):
 from accelerate import init_empty_weights
 from transformers import AutoModelForCausalLM
 with init_empty_weights(include_buffers=False):
  model=AutoModelForCausalLM.from_config(config,dtype=dtype,attn_implementation='eager',trust_remote_code=False)
 assert all(p.is_meta for p in model.parameters())
 buffers={name:value.detach().cpu().clone() for name,value in model.named_buffers()}
 assert all(not value.is_meta for value in buffers.values())
 return model,buffers
def materialize(model,weights,buffers,*,torch,device):
 result=model.load_state_dict(weights,strict=False,assign=True)
 assert not result.unexpected_keys and set(result.missing_keys)<={'lm_head.weight'},result
 model.tie_weights();assert not any(p.is_meta for p in model.parameters())
 model=model.to(device).eval()
 for name,value in model.named_buffers():assert torch.equal(value.detach().cpu(),buffers[name]),name
 assert model.lm_head.weight.data_ptr()==model.model.language_model.embed_tokens.weight.data_ptr()
 return model,result
def load_public_native(control,root,*,torch,device):
 from transformers import MossTranscribeDiarizeConfig,GenerationConfig
 from moss_streamed_weights_20261104 import load_streamed_weights
 control,root=Path(control),Path(root);start=time.perf_counter()
 proof=json.loads((control/'tensor-reuse-proof.json').read_text(encoding='utf-8'))
 assert proof['state']=='PASS_EXACT_PUBLISHED_NATIVE_CHECKPOINT_SHA_FROM_EXISTING_AUTHOR_TENSORS'
 config=MossTranscribeDiarizeConfig.from_pretrained(root,local_files_only=True)
 model,buffers=empty_native(config,torch=torch,dtype=torch.bfloat16)
 weights,receipt=load_streamed_weights(proof['authorCheckpoint'],torch=torch,device=device,
  expected_sha256=proof['authorCheckpointSha256'],chunk_bytes=8*1024**2)
 mapping={r['author']:r['native'] for r in proof['mapping']}
 assert set(weights)==set(mapping) and all(v.dtype==torch.bfloat16 for v in weights.values())
 native={mapping[k]:v for k,v in weights.items()}
 model,loaded=materialize(model,native,buffers,torch=torch,device=device)
 model.generation_config=GenerationConfig.from_pretrained(root,local_files_only=True)
 del weights,native
 receipt.update(nativeClass=type(model).__name__,nativePublishedCheckpointSha256=proof['nativeCheckpointSha256'],
  tensorReuseProofSha256=sha(control/'tensor-reuse-proof.json'),allNativeKeysLoadedExceptTiedHead=loaded.missing_keys,
  deterministicBuffersPreserved=list(buffers),weightsChanged=False,remoteCodeUsed=False,loadSeconds=time.perf_counter()-start)
 return model,receipt
def tiny_loader_control(torch):
 from transformers import MossTranscribeDiarizeConfig,MossTranscribeDiarizeForConditionalGeneration
 torch.manual_seed(20261115)
 config=MossTranscribeDiarizeConfig(audio_config={'model_type':'moss_transcribe_diarize_audio',
  'hidden_size':16,'num_hidden_layers':2,'num_attention_heads':2,'intermediate_size':32,'num_mel_bins':80,'max_source_positions':8},
  text_config={'model_type':'qwen3','vocab_size':128,'hidden_size':16,'intermediate_size':32,'num_hidden_layers':2,
   'num_attention_heads':2,'num_key_value_heads':1,'head_dim':8,'max_position_embeddings':256,'eos_token_id':2,'pad_token_id':0},
  audio_token_id=98,audio_chunk_size=2560,pad_token_id=0)
 config._attn_implementation='eager'
 standard=MossTranscribeDiarizeForConditionalGeneration(config).float().eval()
 weights={k:v.detach().clone() for k,v in standard.state_dict().items() if k!='lm_head.weight'}
 bounded,buffers=empty_native(config,torch=torch,dtype=torch.float32)
 bounded,_=materialize(bounded,weights,buffers,torch=torch,device='cpu')
 inputs={'input_ids':torch.tensor([[1,98,98,4]]),'attention_mask':torch.ones((1,4),dtype=torch.long),
  'input_features':torch.randn((1,80,16)),'input_features_mask':torch.ones((1,16),dtype=torch.long),
  'padding_mask':torch.ones((1,2560),dtype=torch.long)}
 with torch.inference_mode():
  left=standard(**inputs,use_cache=False).logits;right=bounded(**inputs,use_cache=False).logits
 assert torch.equal(left,right),'Native loader changed tiny logits'
 return {'state':'PASS_NATIVE_STANDARD_AND_BOUNDED_EMPTY_LOADER_EXACT_LOGITS','maxAbsDifference':0.,
  'tensors':len(weights),'deterministicBuffersPreserved':list(buffers),'loaderSourceSha256':sha(__file__)}
