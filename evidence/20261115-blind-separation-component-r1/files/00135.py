from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,zipfile
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from companion_community1_adapter_20261115 import pin_rocm_blas
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/blind-separation-composition-r1'
P=Path('E:/CodexData/Companion/.model-cache/blind-separation-composition-20261115/model/last_best_checkpoint.pt')
pressure=SystemRamPressure()
try:assert not pressure.low()
finally:pressure.close()
blas=pin_rocm_blas('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll','88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0')
import torch
assert zipfile.is_zipfile(P),'Do not silently materialize an unsupported full legacy checkpoint'
loaded=torch.load(P,map_location='cpu',mmap=True,weights_only=True)
result=dict(at=datetime.now().astimezone().isoformat(),state='INSPECTED_PUBLIC_CHECKPOINT_NO_MODEL_OR_FORWARD',
            topKeys=list(loaded),topTypes={k:type(v).__name__ for k,v in loaded.items()},
            dictionaries={k:dict(keys=len(v),firstKeys=list(v)[:5]) for k,v in loaded.items() if isinstance(v,dict)},
            tensorCount=sum(isinstance(v,torch.Tensor) for v in loaded.values()),
            firstTopTensorShapes={k:list(v.shape) for k,v in list(loaded.items())[:5] if isinstance(v,torch.Tensor)},
            neuralCalls=0,parameterUpdates=0,cudaInitialized=torch.cuda.is_initialized(),blas=blas,limits=limits.query())
(C/'checkpoint-layout.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['topKeys','topTypes','limits']},ensure_ascii=False))
