"""Owned runtime thread/FP32 numeric control, no speech model inference."""
from pathlib import Path
from datetime import datetime
import ctypes,hashlib,json,os,sys,time
ROOT=Path('E:/CodexData/Companion/product-d1d2-20261114/official-native-parity-r1')
inventory=json.loads((ROOT/'smoke-run-r4/inventory/hip-inventory.json').read_text(encoding='utf-8'))
assert inventory['selected']['name']=='AMD Radeon RX 6800 XT' and inventory['selected']['architecture']=='gfx1030'
assert 0<=(datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()<1800
os.environ.update(HIP_VISIBLE_DEVICES=str(inventory['selected']['ordinal']),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
root=ROOT/'rocm-fp32-runtime-control-r1';assert not root.exists();root.mkdir()
state={'state':'IMPORTING_OWN_GPU_RUNTIME','speechModelInferenceCalls':0,'gpuName':inventory['selected']['name']}
def save(**values):
 state.update(values,at=datetime.now().astimezone().isoformat(timespec='seconds'),limits=limits.query());(root/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
save()
import torch,numpy as np
torch.set_num_threads(1);torch.set_num_interop_threads(1)
path=Path(sys.prefix)/'Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll';lib=ctypes.CDLL(str(path))
get=lib.openblas_get_num_threads;get.restype=ctypes.c_int;get.argtypes=[]
set_threads=lib.openblas_set_num_threads;set_threads.argtypes=[ctypes.c_int];set_threads.restype=None
before=get();set_threads(1);assert get()==1
save(state='ROCM_BLAS_THREADS_SET_TO_ONE',threadsBefore=before,threadsAfter=get(),runtimeLibrary=str(path),runtimeLibrarySha256=hashlib.sha256(path.read_bytes()).hexdigest())
assert torch.cuda.device_count()==1
props=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in props.name and props.gcnArchName.startswith('gfx1030')
torch.cuda.set_device(0);temporary=torch.empty(1,device='cuda:0');torch.cuda.synchronize()
after_context=get();set_threads(1);assert get()==1
save(state='GPU_CONTEXT_READY_WITH_ONE_BLAS_THREAD',threadsAfterContext=after_context,threadsBeforeMatmul=get())
array=(np.arange(32*32,dtype=np.int64).reshape(32,32)%15)-7
expected=(array@array.T).astype(np.float32)
value=torch.from_numpy(array.astype(np.float32)).to('cuda:0');began=time.monotonic()
with torch.inference_mode():actual=(value@value.T).cpu().numpy()
torch.cuda.synchronize();assert np.array_equal(actual,expected)
save(state='PASS_OWN_ROCM_ONE_THREAD_FP32_GPU_MATMUL_EXACT_INDEPENDENT_INTEGER_REFERENCE',
 threadsAfterMatmul=get(),matmulSeconds=time.monotonic()-began,globalEnvironmentChanged=False,
 expectedSha256=hashlib.sha256(expected.tobytes()).hexdigest())
print(json.dumps(state))
