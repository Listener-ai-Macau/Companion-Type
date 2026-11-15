from pathlib import Path
import json,os,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
import torch
p=Path('E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1/new-ordinary-run-r2/model_weights.ckpt')
value=torch.load(p,map_location='meta',weights_only=True,mmap=True)
print(json.dumps({'checkpoint':str(p),'auxiliary':{k:{'shape':list(v.shape),'dtype':str(v.dtype)} for k,v in value.items() if 'activity_head' in k},'gpuInitialized':torch.cuda.is_initialized(),'limits':limits.query()}))
