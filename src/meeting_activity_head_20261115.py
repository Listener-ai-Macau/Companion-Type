"""Diagnostic composition of the checkpoint's original activity and identity heads.

Relative slot mass is a routing condition, not a calibrated identity probability.
Nothing is fed back into AOSC, and existing active slots are never replaced.
"""
def single_head_fallback(probabilities,activity_logits,active):
 import numpy as np
 if activity_logits.shape!=(len(active),3) or probabilities.shape!=active.shape:raise ValueError('Head alignment mismatch')
 a=np.asarray(activity_logits,dtype=np.float64);a-=a.max(axis=1,keepdims=True);a=np.exp(a);a/=a.sum(axis=1,keepdims=True)
 mass=probabilities.sum(axis=1);winners=probabilities.argmax(axis=1)
 ratio=np.divide(probabilities.max(axis=1),mass,out=np.zeros(len(mass),dtype=np.float64),where=mass>0)
 proposed=(~active.any(axis=1))&(a[:,1]>.5)&(ratio>=.8)
 fill=np.zeros_like(active);fill[np.flatnonzero(proposed),winners[proposed]]=True
 return active|fill,fill
