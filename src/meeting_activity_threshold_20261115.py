"""Calibrated activity decisions; keep native probabilities and anonymous slots."""
def active_frames(probabilities,threshold=.5):
 import numpy as np
 data=np.asarray(probabilities)
 if data.ndim!=2 or not 0<threshold<1 or not np.isfinite(data).all():raise ValueError('Invalid activity input')
 active=np.zeros(data.shape,dtype=bool);n=len(data)
 for speaker in range(data.shape[1]):
  v=data[:,speaker];last=np.maximum.accumulate(np.where(v!=threshold,np.arange(n),-1))
  active[:,speaker]=(last>=0)&(v[np.maximum(last,0)]>threshold)
 return active
def exclusive_segments(probabilities,active,seconds):
 import numpy as np
 values=np.where(active,probabilities,-np.inf);best=values.max(axis=1)
 winners=values.argmax(axis=1);ties=(values==best[:,None]).sum(axis=1)!=1
 winners[~active.any(axis=1)|ties]=-1;rows=[]
 for speaker in range(active.shape[1]):
  edges=np.diff(np.r_[0,winners==speaker,0].astype(np.int8))
  for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
   low,high=float(a/100),min(float(b/100),seconds)
   if low<high:rows.append({'start':low,'end':high,'speaker':speaker})
 return sorted(rows,key=lambda r:(r['start'],r['end'],r['speaker']))
