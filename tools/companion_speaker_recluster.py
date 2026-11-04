"""Research-only recording-global re-clustering of anonymous speaker groups.

Inputs are model-produced groups and normalized embeddings, never reference
labels or a guessed participant count. Simultaneous predicted voices cannot
merge. The output is not connected to either shipping application.
"""
from __future__ import annotations
import numpy as np

def constrained_average_link(vectors:np.ndarray,cannot_link:np.ndarray,threshold:float=.68)->list[int]:
    vectors=np.asarray(vectors,dtype=np.float32);cannot_link=np.asarray(cannot_link,dtype=bool)
    if vectors.ndim!=2 or cannot_link.shape!=(len(vectors),len(vectors)) or not np.isfinite(vectors).all():raise ValueError('invalid input')
    norms=np.linalg.norm(vectors,axis=1)
    if np.any(norms<1e-8):raise ValueError('empty embedding')
    vectors=vectors/norms[:,None];similarity=vectors@vectors.T
    clusters=[[i] for i in range(len(vectors))]
    while len(clusters)>1:
        best=None
        for a in range(len(clusters)):
            for b in range(a+1,len(clusters)):
                pair=np.ix_(clusters[a],clusters[b])
                if cannot_link[pair].any():continue
                score=float(similarity[pair].mean())
                if score>=threshold and (best is None or score>best[0]):best=(score,a,b)
        if best is None:break
        _,a,b=best;clusters[a].extend(clusters.pop(b))
    result=[0]*len(vectors)
    for label,cluster in enumerate(clusters):
        for index in cluster:result[index]=label
    return result
