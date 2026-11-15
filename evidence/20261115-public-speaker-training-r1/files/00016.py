"""Bounded supervised adaptation utilities for the original speaker model."""
from pathlib import Path
from datetime import datetime
import gc,hashlib,importlib.util,json,math
import numpy as np
import torch
from torch import nn
from companion_community1_adapter_20261115 import pin_rocm_blas
from public_nemotron_supervision_20261115 import ActivityLoss,PhantomLoss,BCEWithLogitsLoss,get_ats_targets_hungarian,get_pil_targets_hungarian

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load_original(P):
 import yaml
 from accelerate import init_empty_weights
 assert sha(P['converter'])==P['converterSha256'] and sha(P['extractedCheckpoint'])==P['extractedCheckpointSha256']
 spec=importlib.util.spec_from_file_location('original_nemotron_converter_for_adaptation',P['converter'])
 up=importlib.util.module_from_spec(spec);spec.loader.exec_module(up)
 import tarfile
 with tarfile.open(P['checkpoint']) as archive:config=yaml.safe_load(archive.extractfile('model_config.yaml').read())
 original=torch.load(P['extractedCheckpoint'],map_location='cpu',weights_only=True,mmap=True)
 conf=up.build_config(config);conf._attn_implementation='eager'
 with init_empty_weights(include_buffers=False):
  model=up.Nemotron3DiarizationForAudioFrameClassification(conf).eval()
 mapped=up.convert_state_dict(original);model.load_state_dict(mapped,strict=True,assign=True)
 actual=model.state_dict();assert actual.keys()==mapped.keys()
 assert all(torch.equal(actual[k].to(v.dtype),v) for k,v in mapped.items())
 # Restore the original, inference-unused auxiliary head for its published
 # silence/single/overlap training objective. Every auxiliary weight is frozen.
 activity=nn.Sequential(nn.LayerNorm(192),nn.Linear(192,3))
 aux={k.removeprefix('sortformer_modules.activity_head.'):v.float() for k,v in original.items() if k.startswith('sortformer_modules.activity_head.')}
 assert set(aux)==set(activity.state_dict());activity.load_state_dict(aux,strict=True)
 for k,v in activity.state_dict().items():assert torch.equal(v,aux[k])
 receipt={'originalMappedTensors':len(mapped),'allOriginalMappedTensorValuesExact':True,
  'restoredAuxiliaryKeys':list(aux),'auxiliaryOriginalValuesExact':True}
 del mapped,actual,aux,original;gc.collect()
 model=model.to('cuda:0',dtype=torch.float32).eval().requires_grad_(False)
 activity=activity.to('cuda:0',dtype=torch.float32).eval().requires_grad_(False)
 return model,activity,receipt

class LowRankLinear(nn.Module):
 def __init__(self,base,rank=8,alpha=16):
  super().__init__();self.base=base;self.scale=alpha/rank;self.enabled=True
  self.lora_a=nn.Parameter(torch.empty(rank,base.in_features,device=base.weight.device,dtype=base.weight.dtype))
  self.lora_b=nn.Parameter(torch.zeros(base.out_features,rank,device=base.weight.device,dtype=base.weight.dtype))
  nn.init.kaiming_uniform_(self.lora_a,a=math.sqrt(5))
 def forward(self,x):
  original=self.base(x)
  if not self.enabled:return original
  return original+torch.nn.functional.linear(torch.nn.functional.linear(x,self.lora_a),self.lora_b)*self.scale

def install_adapter(model):
 modules=[]
 for index in range(23,31):
  attn=model.model.audio_tower.layers[index].self_attn
  for name in ['q_proj','v_proj']:
   original=getattr(attn,name);assert isinstance(original,nn.Linear)
   new=LowRankLinear(original);setattr(attn,name,new)
   modules.append((f'model.audio_tower.layers.{index}.self_attn.{name}',new))
 model.eval();return modules

def frozen_fingerprints(model,activity):
 result={}
 for root,module in [('speaker',model),('activity',activity)]:
  for name,p in module.named_parameters():
   if p.requires_grad:continue
   # Copy only one parameter at a time. Never clone the whole CPU backbone.
   array=p.detach().cpu().contiguous().numpy()
   result[root+'.'+name]=hashlib.sha256(memoryview(array).cast('B')).hexdigest()
 return result

def adapter_state(modules):
 return {name+'.'+suffix:param.detach().cpu().contiguous() for name,module in modules for suffix,param in [('lora_a',module.lora_a),('lora_b',module.lora_b)]}

def load_adapter(modules,file):
 from safetensors.torch import load_file
 saved=load_file(str(file),device='cpu');expected={n+'.'+s for n,m in modules for s in ['lora_a','lora_b']};assert set(saved)==expected
 with torch.no_grad():
  for name,module in modules:
   for suffix in ['lora_a','lora_b']:
    target=getattr(module,suffix);value=saved[name+'.'+suffix];assert value.shape==target.shape
    target.copy_(value.to(target.device));assert torch.equal(target.detach().cpu(),value)
 return len(saved)

def detach_cache_updates():
 from transformers.models.nemotron3_diarization.modeling_nemotron3_diarization import Nemotron3DiarizationSpeakerCache
 original=Nemotron3DiarizationSpeakerCache.update
 def update(self,*args,**kwargs):
  # Only cached pre-encoder features, scores used for discrete selection and
  # frozen silence embeddings are stored. No trainable continuous cache path.
  with torch.no_grad():return original(self,*args,**kwargs)
 Nemotron3DiarizationSpeakerCache.update=update
 return original

def chunks(model,activity,features,*,stop=None):
 """Same offline340/40/264/40/300 geometry with persistent source state."""
 from transformers.models.nemotron3_diarization.modeling_nemotron3_diarization import Nemotron3DiarizationSpeakerCache
 cache=Nemotron3DiarizationSpeakerCache(model.config.streaming_config,fifo_length=40,speaker_cache_update_period=300)
 assert model.config.chunk_length==340 and model.config.chunk_right_context==40
 captured={}
 def capture(module,args,out):captured['activity']=activity(out.last_hidden_state)
 handle=model.model.register_forward_hook(capture)
 try:
  total=len(features)
  for first in range(0,total,340*8):
   if stop:stop()
   last=min(first+340*8,total);end=min(last+40*8,total)
   # End is a whole stacked frame unless this is the original final tail.
   ahead=(end-last+7)//8
   x=torch.from_numpy(np.array(features[first:end],dtype=np.float32,copy=True))[None].to('cuda:0')
   cached=cache.num_cache_frames+cache.num_fifo_frames
   output=model(input_features=x,speaker_cache=cache,num_lookahead_frames=ahead,num_lookback_frames=0)
   cache=output.speaker_cache
   z=output.logits[:,:last-first]
   a=captured.pop('activity')[:,cached*8:cached*8+z.shape[1]]
   assert z.shape==(1,last-first,8) and a.shape==(1,last-first,3)
   yield first,last,z,a
 finally:handle.remove()

def whole_loss_and_output_gradients(logits,activity_logits,targets,valid):
 """Original whole-meeting global assignments/losses, exact output gradients."""
 z=torch.from_numpy(np.array(logits,copy=True))[None].requires_grad_()
 a=torch.from_numpy(np.array(activity_logits,copy=True))[None].requires_grad_()
 target=torch.from_numpy(np.array(targets[:len(logits)],dtype=np.float32,copy=True))[None]
 lengths=torch.tensor([valid],dtype=torch.long)
 # Padded frontend-only tail is excluded from matching and the losses, exactly
 # like the original target-length convention. All audio remains in inference.
 pil,pi=get_pil_targets_hungarian(target[:,:valid],z.detach().sigmoid()[:,:valid])
 ats,ai=get_ats_targets_hungarian(target[:,:valid],z.detach().sigmoid()[:,:valid],tolerance=0)
 if valid<len(logits):
  pil=torch.nn.functional.pad(pil,(0,0,0,len(logits)-valid));ats=torch.nn.functional.pad(ats,(0,0,0,len(logits)-valid))
 bce=BCEWithLogitsLoss()
 terms={'pil':bce(z,pil,lengths),'ats':bce(z,ats,lengths),
  'activity':ActivityLoss()(a,target,lengths),
  'phantom':PhantomLoss(threshold=.25,temperature=.5)(z,torch.maximum(pil,ats),lengths)}
 loss=.75*terms['pil']+.25*terms['ats']+.5*terms['activity']+.1*terms['phantom']
 gz,ga=torch.autograd.grad(loss,[z,a]);assert torch.isfinite(gz).all() and torch.isfinite(ga).all()
 return gz[0].numpy(),ga[0].numpy(),{'total':float(loss.detach()),**{k:float(v.detach()) for k,v in terms.items()},
  'globalPilAssignment':pi.tolist(),'globalAtsAssignment':ai.tolist()}

def collect(model,activity,case,*,stop=None,progress=None):
 assert sha(case['features'])==case['featuresSha256']
 features=np.load(case['features'],mmap_mode='r',allow_pickle=False);assert features.shape==(case['frames'],128)
 logits=np.empty((len(features),8),dtype=np.float32);aux=np.empty((len(features),3),dtype=np.float32)
 with torch.inference_mode():
  for first,last,z,a in chunks(model,activity,features,stop=stop):
   logits[first:last]=z[0].cpu().numpy();aux[first:last]=a[0].cpu().numpy()
   if progress:progress(first,last)
 assert np.isfinite(logits).all() and np.isfinite(aux).all()
 return logits,aux
