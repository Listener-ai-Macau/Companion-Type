"""Locate the exact failing signal operation; no model, training, GPU, or limit change."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,time,wave
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from meeting_acoustic_contract_20261116 import read,sha,require
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1')
out=E/'published-frontend-trace-r3';out.mkdir(exist_ok=False)
P=read(J/'language-specific-adaptation-r1/prepared-r3/protocol.json');plan=read(P['dataPlan'])
row=next(json.loads(l) for l in Path(plan['trainingManifest']).read_text(encoding='utf-8').splitlines()
    if json.loads(l)['id']==plan['largestJointCase']['id'])
state={'at':datetime.now().astimezone().isoformat(),'state':'TRACE_PREPARING','sourceSha256':sha(__file__),
    'selectedTrainId':row['id'],'frames':row['frames'],'neuralCalls':0,'parameterUpdates':0,'modelInstances':0,'operations':0}
def save(**values):
    import psutil
    state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query(),
        privateBytes=psutil.Process().memory_info().private,availableBytes=psutil.virtual_memory().available)
    atomic_json(out/'state.json',state,progress=True)
save()
import torch,numpy as np,psutil
from torch.utils._python_dispatch import TorchDispatchMode
from threadpoolctl import threadpool_info
from transformers.models.parakeet.feature_extraction_parakeet import ParakeetFeatureExtractor
torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
require(not torch.cuda.is_initialized(),'CPU signal trace initialized GPU')
frontend=ParakeetFeatureExtractor.from_pretrained(P['modelRoot'],local_files_only=True)
save(state='CPU_SIGNAL_EXTRACTOR_READY',torchConfig=torch.__config__.show(),blasThreads=threadpool_info(),
    processThreadCount=psutil.Process().num_threads(),environment={n:os.environ.get(n) for n in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']},
    relevantModules=[m.path for m in psutil.Process().memory_maps() if any(n in m.path.lower() for n in ['blas','mkl','torch_cpu','libomp'])])
with wave.open(row['audio'],'rb') as w:raw=w.readframes(w.getnframes())
samples=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768
require(sha(row['audio'])==row['audioSha256'],'Original PCM changed')
def shapes(x):
    if isinstance(x,torch.Tensor):return {'shape':list(x.shape),'dtype':str(x.dtype),'device':str(x.device)}
    if isinstance(x,(tuple,list)):return [shapes(v) for v in x[:8]]
    return type(x).__name__
class Trace(TorchDispatchMode):
    def __torch_dispatch__(self,func,types,args=(),kwargs=None):
        state['operations']+=1;save(state='ENTERING_SIGNAL_OPERATION',currentOperation=str(func),inputShapes=shapes(args))
        result=func(*args,**(kwargs or {}));save(state='COMPLETED_SIGNAL_OPERATION',outputShapes=shapes(result));return result
try:
    with Trace():result=frontend(samples,sampling_rate=16000,return_tensors='pt',truncation=False,device='cpu')
    save(state='COMPLETE_SIGNAL_OPERATION_TRACE_NO_MODEL',featureShape=list(result['input_features'].shape),gpuInitialized=torch.cuda.is_initialized())
    atomic_json(out/'completed.json',state)
except BaseException as error:save(state='FAILED_SIGNAL_TRACE_RETAINED',error=repr(error));raise
print(json.dumps(state,ensure_ascii=False))
