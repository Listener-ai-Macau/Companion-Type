"""Bit-exact bounded disk transfer of native BF16 KV and first-token logits."""
from pathlib import Path
import gc,hashlib,json,os
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def store(directory,cache,logits,inputs,*,torch,metadata,checkpoint):
 import numpy as np
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);length=int(cache.get_seq_length());files=[]
 assert length==inputs['input_ids'].shape[1]
 def save(name,tensor):
  checkpoint();assert tensor.dtype in [torch.bfloat16,torch.int64]
  value=tensor.detach().cpu().contiguous()
  if tensor.dtype==torch.bfloat16:value=value.view(torch.uint16)
  path=directory/(name+'.npy')
  with path.open('xb') as out:np.save(out,value.numpy(),allow_pickle=False);out.flush();os.fsync(out.fileno())
  files.append({'name':name,'file':str(path),'sha256':sha(path),'shape':list(tensor.shape),'dtype':str(tensor.dtype)})
  del value;gc.collect()
 for i,layer in enumerate(cache.layers):
  assert int(layer.get_seq_length())==length
  for key in ['keys','values']:save(str(i)+'-'+key,getattr(layer,key)[...,:length,:])
 save('logits',logits);save('input_ids',inputs['input_ids']);save('attention_mask',inputs['attention_mask'])
 manifest={'state':'COMPLETE_NATIVE_CAUSAL_PREFILL_CACHE_BIT_EXACT_TRANSFER','tokens':length,'layers':len(cache.layers),
  'capacity':cache.layers[0].max_cache_len,'files':files,'metadata':metadata,'qualityQualified':False,
  'audioOrSpeakerReset':False,'quantizationUsed':False}
 path=directory/'manifest.json'
 with path.open('x',encoding='utf-8') as out:json.dump(manifest,out,ensure_ascii=False,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
 return manifest
def restore(directory,model,*,torch,checkpoint):
 import numpy as np
 from moss_causal_prefill_20261115 import fixed_native_cache
 directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
 assert manifest['state']=='COMPLETE_NATIVE_CAUSAL_PREFILL_CACHE_BIT_EXACT_TRANSFER'
 files={r['name']:r for r in manifest['files']};cache=fixed_native_cache(model,capacity=manifest['capacity'])
 assert len(cache.layers)==manifest['layers']
 def load(name):
  checkpoint();row=files[name];assert sha(row['file'])==row['sha256']
  value=np.load(row['file'],mmap_mode='r',allow_pickle=False)
  assert list(value.shape)==row['shape']
  tensor=torch.from_numpy(np.array(value,copy=True)).to('cuda:0')
  if row['dtype']=='torch.bfloat16':tensor=tensor.view(torch.bfloat16)
  else:assert row['dtype']=='torch.int64' and tensor.dtype==torch.int64
  return tensor
 for i,layer in enumerate(cache.layers):
  keys=load(str(i)+'-keys');values=load(str(i)+'-values')
  assert keys.shape[-2]==manifest['tokens']
  layer.lazy_initialization(keys[...,:1,:],values[...,:1,:])
  layer.keys[...,:manifest['tokens'],:].copy_(keys);layer.values[...,:manifest['tokens'],:].copy_(values)
  layer.cumulative_length.fill_(manifest['tokens'])
  assert torch.equal(layer.keys[...,:manifest['tokens'],:],keys) and torch.equal(layer.values[...,:manifest['tokens'],:],values)
  del keys,values;gc.collect()
 ids,mask,logits=load('input_ids'),load('attention_mask'),load('logits')
 torch.cuda.synchronize();torch.cuda.empty_cache()
 return cache,logits,ids,mask,manifest
def retire_audio(model,*,torch):
 class CompletedAudio(torch.nn.Module):
  def forward(self,*args,**kwargs):raise RuntimeError('Completed acoustic stage cannot run in decoder process')
 model.model.audio_tower=CompletedAudio();model.model.multi_modal_projector=CompletedAudio()
 gc.collect();torch.cuda.synchronize();torch.cuda.empty_cache()
 assert model.device.type=='cuda'
def provide_prefill_once(model,cache,logits,ids,*,torch):
 from functools import wraps
 from transformers.models.moss_transcribe_diarize.modeling_moss_transcribe_diarize import MossTranscribeDiarizeCausalLMOutputWithPast
 original=model.forward;status={'served':False}
 @wraps(original)
 def saved(*args,**kwargs):
  assert not args and not status['served'] and kwargs['past_key_values'] is cache
  assert torch.equal(kwargs['input_ids'],ids),'Restore only the exact complete original prompt'
  status['served']=True;model.forward=original
  return MossTranscribeDiarizeCausalLMOutputWithPast(logits=logits,past_key_values=cache)
 model.forward=saved
 return status
