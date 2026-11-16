# The dynamic program below is derived from HuggingFace Transformers loss_tdt.py.
# Copyright2026 The HuggingFace Team. Licensed under the Apache License,Version2.0.
# You may obtain a copy at https://www.apache.org/licenses/LICENSE-2.0 .
# Distributed on an AS IS BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
"""Exact selected-probability TDT DP with checkpointed, bounded joint logits.

Training labels/audio are unchanged. Only materialization of the dense
T×(U+1)×vocabulary tensor is split; native loss/gradient equivalence must pass
on the actual GPU before use. This module imports no neural runtime itself.
"""
import math
from functools import lru_cache

def selected_tdt_loss(blank_lp,label_lp,duration_lp,logit_lengths,target_lengths,
                      durations,*,torch,heartbeat=None):
    device=blank_lp.device;batch_size,max_t,max_u=blank_lp.shape
    assert blank_lp.dtype==label_lp.dtype==duration_lp.dtype==torch.float32
    assert label_lp.shape==(batch_size,max_t,max_u-1)
    assert duration_lp.shape==(batch_size,max_t,max_u,len(durations))
    alpha=torch.full((batch_size,max_t,max_u),float('-inf'),device=device)
    alpha[:,0,0]=0.;neg_inf=torch.tensor(float('-inf'),device=device)
    for n in range(1,max_t+max_u-1):
        if heartbeat is not None and n%16==0:heartbeat()
        u=torch.arange(max(0,n-max_t+1),min(n+1,max_u),device=device)
        t=n-u;candidates=[]
        for i,dur in enumerate(durations):
            previous=t-dur;valid_t=previous>=0
            if not valid_t.any():continue
            src=previous.clamp(min=0)
            if dur>0:
                value=alpha[:,src,u]+blank_lp[:,src,u]+duration_lp[:,src,u,i]
                candidates.append(torch.where(valid_t.unsqueeze(0),value,neg_inf))
            valid=valid_t&(u>0)
            if valid.any():
                src_u=(u-1).clamp(min=0)
                label_u=src_u.clamp(max=max_u-2) if max_u>1 else src_u
                value=alpha[:,src,src_u]+label_lp[:,src,label_u]+duration_lp[:,src,src_u,i]
                candidates.append(torch.where(valid.unsqueeze(0),value,neg_inf))
        if candidates:alpha[:,t,u]=torch.logsumexp(torch.stack(candidates,dim=0),dim=0)
    index=torch.arange(batch_size,device=device)
    probability=torch.full((batch_size,),float('-inf'),device=device)
    for i,dur in enumerate(durations):
        if dur==0:continue
        last=logit_lengths-dur;valid=last>=0
        if not valid.any():continue
        last=last.clamp(min=0)
        terminal=alpha[index,last,target_lengths]+blank_lp[index,last,target_lengths]+duration_lp[index,last,target_lengths,i]
        probability=torch.where(valid,torch.logsumexp(torch.stack([probability,terminal]),dim=0),probability)
    return (-probability/target_lengths.float()).mean()

def blocked_joint_loss(joint,encoder,decoder,labels,lengths,*,vocab_size,
                       blank_token_id,durations,torch,chunk_frames=16,
                       heartbeat=None,checkpoint_joint=True):
    from torch.utils.checkpoint import checkpoint
    assert encoder.ndim==decoder.ndim==3 and labels.ndim==2
    assert decoder.shape[1]==labels.shape[1]+1 and labels.shape[1]>0
    max_t=int(lengths.max());encoder=encoder[:,:max_t]
    def selected(enc,dec):
        logits=joint(encoder_hidden_states=enc[:,:,None,:],decoder_hidden_states=dec[:,None,:,:])
        token_lp=torch.log_softmax(logits[...,:vocab_size].float(),dim=-1)
        duration_lp=torch.log_softmax(logits[...,vocab_size:].float(),dim=-1)
        # Clone this tiny slice. Returning a view would retain the entire
        # vocabulary log-probability storage and defeat bounded materialization.
        blank=token_lp[...,blank_token_id].clone()
        target=labels[:,None,:].expand(-1,enc.shape[1],-1).long()
        lexical=torch.gather(token_lp[:,:,:-1,:],3,target.unsqueeze(-1)).squeeze(-1)
        return blank,lexical,duration_lp
    parts=[]
    for start in range(0,max_t,chunk_frames):
        if heartbeat is not None:heartbeat()
        enc=encoder[:,start:start+chunk_frames]
        if checkpoint_joint and torch.is_grad_enabled():
            values=checkpoint(selected,enc,decoder,use_reentrant=False,preserve_rng_state=True)
        else:values=selected(enc,decoder)
        parts.append(values)
    blank=torch.cat([x[0] for x in parts],dim=1)
    lexical=torch.cat([x[1] for x in parts],dim=1)
    duration=torch.cat([x[2] for x in parts],dim=1)
    target_lengths=torch.full((labels.shape[0],),labels.shape[1],dtype=torch.long,device=labels.device)
    return selected_tdt_loss(blank,lexical,duration,lengths,target_lengths,durations,torch=torch,heartbeat=heartbeat)

def oracle_tdt_loss(token_logits,duration_logits,targets,blank,durations):
    """Independent scalar path recursion for a tiny training-contract proof."""
    def log_softmax(values):
        high=max(values);normal=high+math.log(sum(math.exp(x-high) for x in values))
        return [x-normal for x in values]
    token=[[log_softmax(row) for row in time] for time in token_logits]
    duration=[[log_softmax(row) for row in time] for time in duration_logits]
    T=len(token);U=len(targets)
    def logsum(values):
        if not values:return float('-inf')
        high=max(values)
        return high+math.log(sum(math.exp(x-high) for x in values)) if high!=float('-inf') else high
    @lru_cache(None)
    def path(t,u):
        branches=[]
        for i,dur in enumerate(durations):
            next_t=t+dur
            if dur>0 and next_t<=T:
                tail=0. if next_t==T and u==U else path(next_t,u) if next_t<T else float('-inf')
                branches.append(token[t][u][blank]+duration[t][u][i]+tail)
            if u<U and next_t<T:
                branches.append(token[t][u][targets[u]]+duration[t][u][i]+path(next_t,u+1))
        return logsum(branches)
    return -path(0,0)/U

def gpu_loss_contract(torch,device):
    """No optimizer/model training; validates loss values and GPU gradients."""
    from transformers.loss.loss_tdt import tdt_loss
    torch.manual_seed(20261116)
    token=torch.randn((1,4,3,7),device=device,requires_grad=True)
    duration=torch.randn((1,4,3,5),device=device,requires_grad=True)
    labels=torch.tensor([[1,2]],device=device);lengths=torch.tensor([4],device=device)
    target_lengths=torch.tensor([2],device=device);durations=[0,1,2,3,4];blank=6
    dense=tdt_loss(token,duration,labels,lengths,target_lengths,blank,durations)
    dense_grad=torch.autograd.grad(dense,(token,duration),retain_graph=True)
    lp=torch.log_softmax(token,-1);dp=torch.log_softmax(duration,-1)
    lexical=torch.gather(lp[:,:,:-1,:],3,labels[:,None,:].expand(-1,4,-1).unsqueeze(-1)).squeeze(-1)
    selected=selected_tdt_loss(lp[...,blank],lexical,dp,lengths,target_lengths,durations,torch=torch)
    selected_grad=torch.autograd.grad(selected,(token,duration))
    expected=oracle_tdt_loss(token.detach().cpu()[0].tolist(),duration.detach().cpu()[0].tolist(),[1,2],blank,durations)
    assert abs(float(dense)-expected)<1e-5 and torch.allclose(dense,selected,atol=1e-6,rtol=1e-6)
    for left,right in zip(dense_grad,selected_grad):
        assert torch.isfinite(left).all() and torch.isfinite(right).all()
        assert torch.allclose(left,right,atol=1e-6,rtol=1e-5)
    # Exercise checkpointed vocabulary chunking and parameter/input gradients.
    class Joint(torch.nn.Module):
        def __init__(self):super().__init__();self.head=torch.nn.Linear(8,12)
        def forward(self,encoder_hidden_states,decoder_hidden_states):
            return self.head(torch.relu(encoder_hidden_states+decoder_hidden_states))
    joint=Joint().to(device);enc=torch.randn((1,4,8),device=device,requires_grad=True)
    dec=torch.randn((1,3,8),device=device,requires_grad=True)
    logits=joint(enc[:,:,None,:],dec[:,None,:,:])
    reference=tdt_loss(logits[...,:7],logits[...,7:],labels,lengths,target_lengths,blank,durations)
    variables=[enc,dec,*joint.parameters()]
    reference_grad=torch.autograd.grad(reference,variables)
    chunked=blocked_joint_loss(joint,enc,dec,labels,lengths,vocab_size=7,blank_token_id=blank,
        durations=durations,torch=torch,chunk_frames=2,checkpoint_joint=True)
    chunked_grad=torch.autograd.grad(chunked,variables)
    assert torch.allclose(reference,chunked,atol=1e-5,rtol=1e-5)
    difference=max(float((a-b).abs().max()) for a,b in zip(reference_grad,chunked_grad))
    for left,right in zip(reference_grad,chunked_grad):
        assert torch.isfinite(right).all() and torch.allclose(left,right,atol=1e-5,rtol=1e-4)
    return {'state':'PASS_NATIVE_DENSE_SELECTED_ORACLE_AND_CHECKPOINTED_JOINT_GPU_LOSS_GRADIENTS',
        'nativeLoss':float(dense),'scalarOracle':expected,'chunkedLoss':float(chunked),
        'maximumChunkedGradientDifference':difference,'parameterUpdates':0,
        'cpuModelTraining':False,'actualPretrainedLargestShapeProven':False}
