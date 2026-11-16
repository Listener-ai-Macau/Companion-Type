"""Preserve GQA by grouping query heads into batch, enabling native CPU fused SDPA."""

def grouped_cpu_sdpa(original,query,key,value,attn_mask=None,dropout_p=0.,is_causal=False,*,scale=None,enable_gqa=False):
 assert query.device.type==key.device.type==value.device.type=='cpu'
 assert query.shape[0]==key.shape[0]==value.shape[0]==1 and dropout_p==0.
 heads,kv_heads=query.shape[1],key.shape[1];assert heads%kv_heads==0
 groups=heads//kv_heads
 if groups==1:
  return original(query,key,value,attn_mask=attn_mask,dropout_p=dropout_p,is_causal=is_causal,scale=scale,enable_gqa=False)
 assert enable_gqa and key.shape==value.shape
 q=query.reshape(1,kv_heads,groups,query.shape[-2],query.shape[-1]).permute(0,2,1,3,4).reshape(groups,kv_heads,query.shape[-2],query.shape[-1])
 # Batch stride0 is a view of the exact same K/V. Every query group sees all
 # original keys without a full head-repeated copy or an FP32 key conversion.
 k=key.expand(groups,-1,-1,-1);v=value.expand(groups,-1,-1,-1)
 answer=original(q,k,v,attn_mask=attn_mask,dropout_p=0.,is_causal=is_causal,scale=scale,enable_gqa=False)
 return answer.reshape(1,groups,kv_heads,query.shape[-2],value.shape[-1]).permute(0,2,1,3,4).reshape(1,heads,query.shape[-2],value.shape[-1])

def install_cpu_grouped_attention(*,torch):
 import torch.nn.functional as F
 original=F.scaled_dot_product_attention
 torch.backends.cuda.enable_flash_sdp(True);torch.backends.cuda.enable_math_sdp(True)
 torch.backends.cuda.enable_mem_efficient_sdp(False);torch.backends.cuda.enable_cudnn_sdp(False)
 def scheduled(*args,**kwargs):return grouped_cpu_sdpa(original,*args,**kwargs)
 F.scaled_dot_product_attention=scheduled
