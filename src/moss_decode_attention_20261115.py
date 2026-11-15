"""Single-query GQA executed as grouped GEMM; no head/KV duplication."""
import math
def grouped_decode(query,key,value,attn_mask=None,dropout_p=0.,is_causal=False,*,scale=None,enable_gqa=False,pad_queries=False):
 import torch
 assert query.shape[-2]==1 and dropout_p==0. and not is_causal
 batch,heads,_,width=query.shape;kv_heads=key.shape[1];length=key.shape[-2]
 assert batch==1 and key.shape==value.shape and heads%kv_heads==0
 groups=heads//kv_heads;assert enable_gqa or groups==1
 q=query.reshape(batch,kv_heads,groups,width).float();k=key.float();v=value.float()
 repeats=128//groups if pad_queries else 1
 assert groups*repeats<=128
 if repeats>1:q=q.repeat(1,1,repeats,1)
 scores=torch.matmul(q,k.transpose(-2,-1))*(scale if scale is not None else 1/math.sqrt(width))
 if attn_mask is not None:
  assert attn_mask.shape[-2]==1 and attn_mask.shape[-1]==length
  mask=attn_mask.expand(batch,heads,1,length).reshape(batch,kv_heads,groups,length)
  if repeats>1:mask=mask.repeat(1,1,repeats,1)
  scores=scores.masked_fill(~mask,float('-inf')) if mask.dtype==torch.bool else scores+mask.float()
 probabilities=torch.softmax(scores,dim=-1);probabilities=torch.nan_to_num(probabilities,nan=0.)
 context=torch.matmul(probabilities,v)
 return context[...,:groups,:].reshape(batch,heads,1,width).to(query.dtype)

def microbenchmark(torch):
 import time
 import torch.nn.functional as F
 torch.backends.cuda.enable_flash_sdp(False);torch.backends.cuda.enable_mem_efficient_sdp(False)
 torch.backends.cuda.enable_math_sdp(True);torch.backends.cuda.enable_cudnn_sdp(False)
 torch.manual_seed(20261115);reports=[]
 for length in [2053,27924]:
  q=torch.randn((1,16,1,128),dtype=torch.bfloat16,device='cuda:0')
  k=torch.randn((1,8,length,128),dtype=torch.bfloat16,device='cuda:0');v=torch.randn_like(k)
  methods={'native':lambda:F.scaled_dot_product_attention(q,k,v,enable_gqa=True),
   'grouped':lambda:grouped_decode(q,k,v,enable_gqa=True),
   'grouped128':lambda:grouped_decode(q,k,v,enable_gqa=True,pad_queries=True)}
  with torch.inference_mode():
   expected=methods['native']()
   for name,fn in methods.items():
    output=fn();torch.cuda.synchronize();difference=float((output.float()-expected.float()).abs().max())
    assert torch.allclose(output,expected,atol=.008,rtol=.008),(length,name,difference)
    times=[]
    for _ in range(3):
     tick=time.perf_counter();output=fn();torch.cuda.synchronize();times.append(time.perf_counter()-tick)
    reports.append({'length':length,'method':name,'seconds':times,'medianSeconds':sorted(times)[1],
     'maxAbsDifference':difference,'tolerance':{'atol':.008,'rtol':.008}})
 return {'state':'COMPLETE_NATIVE_VS_TWO_EQUIVALENT_GQA_EXECUTION_SCHEDULES','rows':reports,
  'modelLoaded':False,'qualityQualified':False,'scope':'Kernel execution timing/equivalence only, not model or decoding-parameter selection.'}
