"""Bound native long-context allocations, keeping every audio window and key."""
from pathlib import Path
import gc,hashlib,os,wave
def prepare_wave(processor,audio,directory,*,torch):
 import numpy as np
 from transformers.feature_extraction_utils import BatchFeature
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
 extractor=processor.feature_extractor;features=[];masks=[]
 with wave.open(str(audio),'rb') as wav:
  assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000)
  frames=wav.getnframes();floating=np.memmap(directory/'original.f32',mode='w+',dtype=np.float32,shape=(frames,))
  for start in range(0,frames,480000):
   pcm=wav.readframes(min(480000,frames-start));samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
   floating[start:start+len(samples)]=samples
   # Native normalizes each independent Whisper window, not across windows.
   part=extractor(samples,sampling_rate=16000,return_tensors='np',device='cpu')
   features.append(np.array(part['input_features'][0],copy=True))
   masks.append(np.array(part['input_features_mask'][0],copy=True))
   del part,samples,pcm
  floating.flush()
 with (directory/'original.f32').open('rb+') as f:os.fsync(f.fileno())
 values={'input_features':np.stack(features),'input_features_mask':np.stack(masks),
  # The native processor/model only sum this0/1 mask. Boolean representation
  # retains every sample and exact length while avoiding an8x larger int mask.
  'padding_mask':np.ones((1,frames),dtype=np.bool_)}
 class CachedNativeFeatures:
  def __getattr__(self,key):return getattr(extractor,key)
  def __call__(self,audio_values,**kwargs):
   assert len(audio_values)==1 and len(audio_values[0])==frames
   return BatchFeature(data=values,tensor_type=kwargs.get('return_tensors'))
 processor.feature_extractor=CachedNativeFeatures()
 try:inputs=processor.apply_transcription_request(audio=floating,processor_kwargs={'audio_kwargs':{'sampling_rate':16000}})
 finally:processor.feature_extractor=extractor
 assert inputs['padding_mask'].sum().item()==frames
 receipt={'frames':frames,'audioSeconds':frames/16000,'allOriginalAudioWindows':len(features),
  'paddingRepresentation':'Boolean0/1, native sum unchanged; no sample/context truncation',
  'inputShapes':{k:list(v.shape) for k,v in inputs.items()},
  'inputSha256':{k:hashlib.sha256(memoryview(v.contiguous().numpy()).cast('B')).hexdigest() for k,v in inputs.items()}}
 del floating,features,masks,values;gc.collect()
 return inputs,receipt

def install_native_bounded(model,*,torch,encoder_progress=None,attention_progress=None):
 import torch.nn.functional as F
 from transformers.modeling_outputs import BaseModelOutputWithPooling
 from moss_amd_execution_20261104 import bounded_sdpa
 from moss_key_streamed_attention_20261104 import key_streamed_sdpa
 model.set_attn_implementation('sdpa')
 # Explicit official math backend; fused kernels are not assumed on gfx1030.
 torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False)
 torch.backends.cuda.enable_math_sdp(True);torch.backends.cuda.enable_cudnn_sdp(False)
 original=F.scaled_dot_product_attention;encoder_active=False
 stats={'sdpaCalls':0,'blockedCalls':0,'maxQueryTokens':0,'maxKeyTokens':0,'keyStreamedCalls':0,'keyTiles':0,
  'maximumScoreTileElements':0,'encoderCalls':0,'encoderChunks':0,'queryBlock':128,'keyBlock':1024,'encoderBatch':2}
 def language(q,k,v,attn_mask=None,dropout_p=0.,is_causal=False,*,scale=None,enable_gqa=False):
  if q.shape[-2]>1 and k.shape[-2]>1024:
   return key_streamed_sdpa(q,k,v,attn_mask,dropout_p,is_causal,scale=scale,enable_gqa=enable_gqa,key_block=1024,stats=stats)
  return original(q,k,v,attn_mask=attn_mask,dropout_p=dropout_p,is_causal=is_causal,scale=scale,enable_gqa=enable_gqa)
 def scheduled(q,k,v,attn_mask=None,dropout_p=0.,is_causal=False,*,scale=None,enable_gqa=False):
  if encoder_active:return original(q,k,v,attn_mask=attn_mask,dropout_p=dropout_p,is_causal=is_causal,scale=scale,enable_gqa=enable_gqa)
  answer=bounded_sdpa(language,q,k,v,attn_mask,dropout_p,is_causal,scale=scale,enable_gqa=enable_gqa,query_block=128,stats=stats)
  if attention_progress:attention_progress(stats)
  return answer
 F.scaled_dot_product_attention=scheduled
 encoder=model.model.audio_tower;forward=encoder.forward
 def encode(features,*args,**kwargs):
  nonlocal encoder_active
  assert not args and kwargs=={'return_dict':True},kwargs
  count=len(features);stats['encoderCalls']+=1;stats['encoderChunks']+=count;values=[];encoder_active=True
  try:
   for first in range(0,count,2):
    result=forward(features[first:first+2],return_dict=True);values.append(result.last_hidden_state)
    if encoder_progress:encoder_progress(min(first+2,count),count)
   return BaseModelOutputWithPooling(last_hidden_state=torch.cat(values,dim=0))
  finally:encoder_active=False
 encoder.forward=encode
 return stats

def attention_control(torch):
 import torch.nn.functional as F
 from moss_amd_execution_20261104 import bounded_sdpa
 from moss_key_streamed_attention_20261104 import key_streamed_sdpa
 torch.manual_seed(20261115)
 torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False)
 torch.backends.cuda.enable_math_sdp(True);torch.backends.cuda.enable_cudnn_sdp(False)
 q=torch.randn((1,4,2053,32),device='cuda:0',dtype=torch.bfloat16)
 k=torch.randn((1,2,2053,32),device='cuda:0',dtype=torch.bfloat16);v=torch.randn_like(k)
 original=F.scaled_dot_product_attention
 with torch.inference_mode():
  expected=original(q,k,v,is_causal=True,enable_gqa=True)
  def keyed(*args,**kwargs):return key_streamed_sdpa(*args,**kwargs,key_block=1024)
  actual=bounded_sdpa(keyed,q,k,v,is_causal=True,enable_gqa=True,query_block=128)
 difference=float((actual.float()-expected.float()).abs().max())
 assert torch.allclose(actual,expected,atol=.008,rtol=.008),difference
 return {'state':'PASS_GPU_BOUNDED_ALL_CONTEXT_CAUSAL_GQA_MATH_SDPA_CONTROL','maxAbsDifference':difference,
  'shape':[1,4,2053,32],'queryBlock':128,'keyBlock':1024,'allAllowedKeysRetained':True,'bitwiseEqualityClaimed':False}
