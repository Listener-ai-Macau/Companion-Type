"""Native BF16 CPU inference with read-only weights and shared file-backed full KV.

Windows copy-on-write views can reserve private commit for the entire view.
Weights therefore use ACCESS_READ, and mutable KV uses ACCESS_WRITE on real
files. This bounds private allocations; actual mapped working RAM is separate
and must continue to be monitored by the existing Windows pressure guard.
"""
from pathlib import Path
import gc,hashlib,json,math,mmap,struct,time,types

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load_cpu_mapped_native(control,root,*,torch):
 from transformers import MossTranscribeDiarizeConfig,GenerationConfig
 from moss_native_architecture_20261115 import empty_native,materialize
 control,root=Path(control),Path(root);started=time.perf_counter()
 proof=json.loads((control/'tensor-reuse-proof.json').read_text(encoding='utf-8'))
 assert proof['state']=='PASS_EXACT_PUBLISHED_NATIVE_CHECKPOINT_SHA_FROM_EXISTING_AUTHOR_TENSORS'
 source=Path(proof['authorCheckpoint']);assert sha(source)==proof['authorCheckpointSha256']
 stream=source.open('rb');header_size=struct.unpack('<Q',stream.read(8))[0]
 assert 0<header_size<100*1024**2
 header=json.loads(stream.read(header_size));offset=8+header_size
 mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ)
 config=MossTranscribeDiarizeConfig.from_pretrained(root,local_files_only=True)
 model,buffers=empty_native(config,torch=torch,dtype=torch.bfloat16)
 names={r['author']:r['native'] for r in proof['mapping']};weights={};data_bytes=0
 assert set(names)==set(header)-{'__metadata__'}
 for author,native in names.items():
  row=header[author];assert row['dtype']=='BF16'
  start,end=row['data_offsets'];numel=math.prod(row['shape'])
  assert end-start==numel*2 and offset+end<=source.stat().st_size
  value=torch.frombuffer(mapping,dtype=torch.bfloat16,count=numel,offset=offset+start).reshape(row['shape'])
  weights[native]=value;data_bytes+=end-start
 model,loaded=materialize(model,weights,buffers,torch=torch,device='cpu')
 for name,param in model.named_parameters():assert param.data_ptr()==weights[name].data_ptr(),name
 model.requires_grad_(False);model.generation_config=GenerationConfig.from_pretrained(root,local_files_only=True)
 model._readonly_weight_mapping_owners=(stream,mapping)
 assert all(p.device.type=='cpu' and p.dtype==torch.bfloat16 for p in model.parameters())
 receipt={'state':'EXACT_PINNED_BF16_NATIVE_CPU_WEIGHTS_READONLY_FILE_MAPPED',
  'file':str(source),'fileSha256':proof['authorCheckpointSha256'],'nativePublishedCheckpointSha256':proof['nativeCheckpointSha256'],
  'tensorCount':len(weights),'tensorBytes':data_bytes,'weightsChanged':False,'quantizationUsed':False,
  'mapping':'mmap.ACCESS_READ; no copy-on-write and no whole private CPU state_dict copy',
  'allNativeKeysLoadedExceptTiedHead':loaded.missing_keys,'deterministicBuffersPreserved':list(buffers),
  'device':'cpu','gpuUsed':False,'seconds':time.perf_counter()-started}
 return model,receipt

def cpu_file_cache(model,directory,*,torch,capacity):
 from moss_causal_prefill_20261115 import fixed_native_cache
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
 cache=fixed_native_cache(model,capacity=capacity);owners=[];files=[]
 def allocate(index,kind,shape,dtype):
  assert dtype==torch.bfloat16
  path=directory/(str(index)+'-'+kind+'.kv');size=math.prod(shape)*2
  f=path.open('x+b');f.truncate(size)
  mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_WRITE)
  value=torch.frombuffer(mm,dtype=dtype,count=math.prod(shape)).reshape(shape)
  owners.append((f,mm));files.append({'file':str(path),'bytes':size,'shape':list(shape),'dtype':'torch.bfloat16'})
  return value
 for index,layer in enumerate(cache.layers):
  def initialize(self,keys,values,index=index):
   assert keys.device.type==values.device.type=='cpu'
   self.dtype,self.device=keys.dtype,keys.device;self.batch_size,self.num_heads=keys.shape[:2]
   self.k_head_dim,self.v_head_dim=keys.shape[-1],values.shape[-1]
   self.keys=allocate(index,'keys',(self.batch_size,self.num_heads,self.max_cache_len,self.k_head_dim),self.dtype)
   self.values=allocate(index,'values',(self.batch_size,self.num_heads,self.max_cache_len,self.v_head_dim),self.dtype)
   self.cumulative_length=self.cumulative_length.to('cpu');self.is_initialized=True
  layer.lazy_initialization=types.MethodType(initialize,layer)
 cache._shared_file_mapping_owners=owners;cache._shared_file_mapping_files=files
 return cache

def restore_cpu_prefill(source,model,target,*,torch,checkpoint):
 import numpy as np
 source=Path(source);manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
 assert manifest['state']=='COMPLETE_NATIVE_CAUSAL_PREFILL_CACHE_BIT_EXACT_TRANSFER'
 files={r['name']:r for r in manifest['files']}
 cache=cpu_file_cache(model,target,torch=torch,capacity=manifest['capacity'])
 def load(name):
  checkpoint();row=files[name];assert sha(row['file'])==row['sha256']
  array=np.load(row['file'],mmap_mode='r',allow_pickle=False);assert list(array.shape)==row['shape']
  value=torch.from_numpy(array)
  return value.view(torch.bfloat16) if row['dtype']=='torch.bfloat16' else value
 for i,layer in enumerate(cache.layers):
  keys,values=load(str(i)+'-keys'),load(str(i)+'-values')
  layer.lazy_initialization(keys[...,:1,:],values[...,:1,:])
  layer.keys[...,:manifest['tokens'],:].copy_(keys);layer.values[...,:manifest['tokens'],:].copy_(values)
  layer.cumulative_length.fill_(manifest['tokens'])
  assert torch.equal(layer.keys[...,:manifest['tokens'],:],keys) and torch.equal(layer.values[...,:manifest['tokens'],:],values)
  del keys,values;gc.collect();checkpoint()
 ids,mask,logits=load('input_ids'),load('attention_mask'),load('logits')
 return cache,logits,ids,mask,manifest

def retire_cpu_audio(model,*,torch):
 class CompletedAudio(torch.nn.Module):
  def forward(self,*args,**kwargs):raise RuntimeError('Completed acoustic stage cannot be run in decoder')
 model.model.audio_tower=CompletedAudio();model.model.multi_modal_projector=CompletedAudio();gc.collect()
 assert model.device.type=='cpu'
