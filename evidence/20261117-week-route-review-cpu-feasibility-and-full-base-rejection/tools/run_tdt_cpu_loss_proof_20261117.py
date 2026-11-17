"""Run the previously unexecuted loss/gradient contract on CPU, no training."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,sys,time,traceback
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from durable_model_state_20261117 import atomic_json
from companion_local_pcm_session_20261114 import exclusive_file
import psutil
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure()
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
run=E/'language-specific-adaptation-r1/cpu-loss-reference-r1';run.mkdir(exist_ok=False)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
source=S/'tdt_selected_loss_20261116.py';tick=time.monotonic()
state={'at':datetime.now().astimezone().isoformat(),'state':'PREPARING_CPU_LOSS_GRADIENT_CONTROL',
 'pid':os.getpid(),'sourceSha256':sha(source),'device':'cpu','newPretrainedModelCalls':0,
 'parameterUpdates':0,'newGoalCreated':False,'qualityQualified':False}
try:
    with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
        assert not pressure.low() and psutil.virtual_memory().available>=3414499000
        atomic_json(run/'state.json',state)
        import torch
        from companion_community1_adapter_20261115 import pin_rocm_blas
        blas=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll')
        state['blas']=pin_rocm_blas(blas,'88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0')
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        assert not torch.cuda.is_initialized()
        from tdt_selected_loss_20261116 import gpu_loss_contract
        result=gpu_loss_contract(torch,torch.device('cpu'))
        state.update(state='PASS_CPU_NATIVE_DENSE_SELECTED_ORACLE_AND_CHECKPOINTED_GRADIENTS',
            originalHelperResult=result,gpuBackendProven=False,
            actualPretrainedForwardBackwardLargestShapeProven=False,gpuInitialized=torch.cuda.is_initialized())
        assert not state['gpuInitialized']
except BaseException as error:
    state.update(state='FAIL_CPU_LOSS_GRADIENT_CONTRACT_RETAINED',error=repr(error),traceback=traceback.format_exc())
finally:
    state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.monotonic()-tick,limits=limits.query())
    pressure.close();atomic_json(run/'result.json',state);print(json.dumps(state,ensure_ascii=False))
