"""Regression checks for device renumbering and absent external hardware."""
from moss_gpu_identity_20261106 import select_rx6800xt,DeclaredGpuUnavailable

igpu={'index':0,'name':'AMD Radeon 780M Graphics','architecture':'gfx1103','reportedMemoryBytes':1}
external={'index':1,'name':'AMD Radeon RX 6800 XT','architecture':'gfx1030','reportedMemoryBytes':16*1024**3}
assert select_rx6800xt([igpu,external],1)['index']==1
renumbered={**external,'index':0}
assert select_rx6800xt([renumbered],1)['index']==0
assert select_rx6800xt([renumbered],1)['indexChangedFromHint']
for devices in [[igpu],[],[external,{**external,'index':2}],[{**external,'architecture':'gfx1103'}]]:
    try:select_rx6800xt(devices,1)
    except DeclaredGpuUnavailable:pass
    else:raise AssertionError('Missing, ambiguous or inconsistent declared GPU must not run another device')
print('GPU identity checks passed: original order, renumbered external card, absent/ambiguous/wrong architecture rejected.')
