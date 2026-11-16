"""One real long-KV geometry, fixed existing tolerance; kernel evidence, no model/ASR claim."""
from pathlib import Path
from datetime import datetime
import os,sys,time,json,argparse
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_local_pcm_session_20261114 import exclusive_file
from companion_community1_adapter_20261115 import pin_rocm_blas
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
p=argparse.ArgumentParser();p.add_argument('--attempt',type=int,default=1);args=p.parse_args();assert args.attempt in [1,2]
root=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')/('cpu-grouped-attention-probe-r'+str(args.attempt));assert not root.exists();root.mkdir()
with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
 import torch
 import torch.nn.functional as F
 from torch.nn.attention import sdpa_kernel,SDPBackend
 from moss_key_streamed_attention_20261104 import key_streamed_sdpa
 from moss_cpu_grouped_attention_20261116 import grouped_cpu_sdpa
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 blas=pin_rocm_blas(Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104/amd-runtime/Lib/site-packages/_rocm_sdk_core/bin/rocm-openblas.dll'),'88f7631d9f7c49cfbf710551a7fa69bef2fd54052007532a518d7ba3699534c0')
 torch.manual_seed(20261116)
 q=torch.randn((1,16,128,128),dtype=torch.bfloat16);k=torch.randn((1,8,33105,128),dtype=torch.bfloat16);v=torch.randn_like(k)
 rows=[]
 with torch.inference_mode():
  print('START forced native CPU fused GQA via grouped batch',flush=True)
  with sdpa_kernel(SDPBackend.FLASH_ATTENTION):
   t=time.perf_counter();actual=grouped_cpu_sdpa(F.scaled_dot_product_attention,q,k,v,enable_gqa=True);elapsed=time.perf_counter()-t
   rows.append({'method':'grouped-native-cpu-fused-gqa','seconds':elapsed});print(json.dumps(rows[-1]),flush=True)
  print('START bounded all-key FP32 reference; original full math attempt exited before a result',flush=True)
  t=time.perf_counter();expected=key_streamed_sdpa(q,k,v,enable_gqa=True,key_block=1024);elapsed=time.perf_counter()-t
  diff=float((actual.float()-expected.float()).abs().max());assert torch.allclose(actual,expected,atol=.008,rtol=.008)
  rows.append({'method':'prior-key-streamed-fp32','seconds':elapsed,'maxAbsDifference':diff});print(json.dumps(rows[-1]),flush=True)
 result={'at':datetime.now().astimezone().isoformat(),'state':'PASS_ONE_FULL_LONG_KV_CPU_ATTENTION_GEOMETRY','shape':{'q':list(q.shape),'k':list(k.shape)},'rows':rows,'existingTolerance':{'atol':.008,'rtol':.008},'blas':blas,'limits':limits.query(),'modelLoaded':False,'qualityQualified':False,'productDefaultChanged':False}
 (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
