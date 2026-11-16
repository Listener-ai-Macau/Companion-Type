"""One bounded availability/allocation/kernel probe of the remaining local iGPU; no model."""
from pathlib import Path
from datetime import datetime
import os,sys,json,time,psutil
os.environ.update(HIP_VISIBLE_DEVICES='0',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from companion_local_pcm_session_20261114 import exclusive_file
from companion_community1_adapter_20261115 import pin_rocm_blas
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure()
out=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/available-780m-probe-r1');assert not out.exists();out.mkdir()
result={'state':'STARTING_AVAILABLE_780M_NO_MODEL_PROBE','at':datetime.now().astimezone().isoformat(),'neuralModelLoaded':False,'qualityQualified':False,'systemConfigurationChanged':False}
def save():
 result['limits']=limits.query();(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save()
with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
 try:
  import torch
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  result['blas']=pin_rocm_blas(Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll'),'88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0')
  assert torch.cuda.device_count()==1
  p=torch.cuda.get_device_properties(0);assert p.name=='AMD Radeon 780M Graphics' and p.gcnArchName.startswith('gfx1103')
  result['selected']={'name':p.name,'architecture':p.gcnArchName,'totalMemory':p.total_memory,'logicalOrdinal':0}
  rows=[];proc=psutil.Process()
  for size in [64*1024**2,256*1024**2,512*1024**2]:
   assert not pressure.low()
   before=proc.memory_info().private;available=psutil.virtual_memory().available
   value=torch.empty((size//2,),device='cuda:0',dtype=torch.bfloat16);value.fill_(.5);torch.cuda.synchronize()
   assert value[:32].cpu().tolist()==[.5]*32
   row={'bytes':size,'privateBefore':before,'privateAfter':proc.memory_info().private,'availableBefore':available,
    'availableAfter':psutil.virtual_memory().available,'allocated':torch.cuda.memory_allocated(),'reserved':torch.cuda.memory_reserved()}
   del value;torch.cuda.empty_cache();row['privateAfterFree']=proc.memory_info().private
   rows.append(row);result['rows']=rows;save()
  result['state']='PASS_AVAILABLE_780M_BF16_KERNEL_AND_BOUNDED_COMMIT_NO_MODEL'
 except BaseException as error:result.update(state='FAILED_AVAILABLE_780M_NO_MODEL_NO_RETRY',error=repr(error));raise
 finally:pressure.close();result['finishedAt']=datetime.now().astimezone().isoformat();save()
print(json.dumps(result))
