"""Exact-context inference attention with bounded temporary score tensors.

Online softmax keeps all keys while bounding one score tile; no context/audio
truncation and no speaker reset. FP32 intermediates match the math SDPA policy
for FP16/BF16 inputs, with normal floating-point reduction differences tested.
"""
import math
import torch


def key_streamed_sdpa(query,key,value,attn_mask=None,dropout_p=0.0,is_causal=False,
                      *,scale=None,enable_gqa=False,key_block=1024,stats=None,pacer=None):
    assert dropout_p==0. and key_block>0 and not (is_causal and attn_mask is not None)
    qlen,klen=query.shape[-2],key.shape[-2]
    assert qlen>0 and klen>0
    compute=torch.float64 if query.dtype==torch.float64 else torch.float32
    q=query.to(compute);factor=1/math.sqrt(query.shape[-1]) if scale is None else scale
    if enable_gqa:
        assert query.shape[-3]%key.shape[-3]==0 and key.shape[-3]==value.shape[-3]
        repeats=query.shape[-3]//key.shape[-3]
    else:repeats=1
    running_max=None;denominator=None;numerator=None
    if stats is not None:stats['keyStreamedCalls']+=1
    for start in range(0,klen,key_block):
        stop=min(klen,start+key_block)
        k=key[...,start:stop,:].to(compute);v=value[...,start:stop,:].to(compute)
        if repeats!=1:k=k.repeat_interleave(repeats,dim=-3);v=v.repeat_interleave(repeats,dim=-3)
        scores=torch.matmul(q,k.transpose(-2,-1))*factor
        if is_causal:
            causal=torch.arange(start,stop,device=query.device)[None,:]<=torch.arange(qlen,device=query.device)[:,None]
            scores=scores.masked_fill(~causal,float('-inf'))
        elif attn_mask is not None:
            mask=attn_mask[...,start:stop]
            scores=scores.masked_fill(~mask,float('-inf')) if mask.dtype==torch.bool else scores+mask.to(compute)
        block_max=scores.amax(dim=-1,keepdim=True)
        new_max=block_max if running_max is None else torch.maximum(running_max,block_max)
        # All-masked rows yield zero, as math SDPA does; never exp(-inf-(-inf)).
        safe_max=torch.where(torch.isfinite(new_max),new_max,torch.zeros_like(new_max))
        probabilities=torch.exp(scores-safe_max)
        contribution=torch.matmul(probabilities,v)
        block_sum=probabilities.sum(dim=-1,keepdim=True)
        if running_max is None:numerator=contribution;denominator=block_sum
        else:
            rescale=torch.exp(running_max-safe_max)
            numerator=numerator*rescale+contribution
            denominator=denominator*rescale+block_sum
        running_max=new_max
        if stats is not None:
            stats['keyTiles']+=1
            stats['maximumScoreTileElements']=max(stats['maximumScoreTileElements'],scores.numel())
        if pacer is not None:pacer.checkpoint()
    output=torch.where(denominator>0,numerator/denominator.clamp_min(torch.finfo(compute).tiny),torch.zeros_like(numerator))
    return output.to(query.dtype)
