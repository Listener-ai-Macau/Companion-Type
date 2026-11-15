from pathlib import Path
import os,sys,json
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
import torch,numpy as np
root=Path('E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1')
data=torch.load(root/'smoke-run-r2/model_weights.ckpt',map_location='cpu',weights_only=True,mmap=True)
win=data['preprocessor.featurizer.window'];fb=data['preprocessor.featurizer.fb']
report={'windowShape':list(win.shape),'windowDtype':str(win.dtype),'melShape':list(fb.shape),'melDtype':str(fb.dtype),
 'lastWindowValues':win.reshape(-1)[-4:].float().tolist(),'firstWindowValues':win.reshape(-1)[:4].float().tolist(),
 'comparison':{},'modelInferenceCalls':0,'cudaInitialized':torch.cuda.is_initialized(),'limits':limits.query()}
for periodic in [False,True]:
 value=torch.hann_window(win.numel(),periodic=periodic)
 report['comparison'][str(periodic)]={'maxAbsoluteError':float((value-win.reshape(-1).float()).abs().max()),
  'equalAfterOriginalDtypeRoundtrip':torch.equal(value.to(win.dtype),win.reshape(-1))}
out=root/'original-frontend-buffer-audit.json';assert not out.exists();out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
