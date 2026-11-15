"""Close only bounded same-identity activity holes, preserving conflicts."""
def fill_same_speaker_gaps(active,maximum_seconds):
 import numpy as np
 if active.ndim!=2 or active.dtype!=np.bool_ or not 0<=maximum_seconds<=1:raise ValueError('Invalid bounded gap policy')
 fill=np.zeros_like(active);maximum_frames=round(maximum_seconds*100)
 for speaker in range(active.shape[1]):
  edges=np.diff(np.r_[0,active[:,speaker],0].astype(np.int8));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
  for end,start in zip(ends[:-1],starts[1:]):
   if 0<start-end<=maximum_frames and not active[end:start].any():fill[end:start,speaker]=True
 # Two different identities proposing the same silent region are ambiguous.
 fill[fill.sum(axis=1)>1]=False
 return active|fill,fill
