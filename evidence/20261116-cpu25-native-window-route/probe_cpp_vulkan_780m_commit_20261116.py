"""Bounded allocation-only probe of the exact pinned Vulkan backend, without model/compute."""
from pathlib import Path
from datetime import datetime
import ctypes as c,os,sys,json,time,hashlib,psutil
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/cpp-r1')
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
OUT=E/'cpp-vulkan-780m-commit-probe-r1';OUT.mkdir(exist_ok=True);assert not (OUT/'result.json').exists()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
runtime=read(C/'runtime-ready.json');python=read(C/'python-source.json')
for row in runtime['files']+python['files']:
 with Path(row['file']).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==row['sha256']
library=next(Path(x['file']) for x in runtime['files'] if Path(x['file']).name=='transcribe.dll')
scope=os.add_dll_directory(str(library.parent));os.environ['TRANSCRIBE_LIBRARY']=str(library);sys.path.insert(0,python['root'])
import transcribe_cpp as cpp
devices=cpp.backends();selected=[x for x in devices if x.kind=='vulkan' and '780M Graphics' in x.description];assert len(selected)==1
libraries=[c.CDLL(str(library.parent/name)) for name in ['ggml-base.dll','ggml.dll','ggml-vulkan.dll']]
def bind(name,result,args):
 fn=next((getattr(lib,name) for lib in libraries if hasattr(lib,name)),None);assert fn is not None,name
 fn.restype=result;fn.argtypes=args;return fn
dev_by_name=bind('ggml_backend_dev_by_name',c.c_void_p,[c.c_char_p])
dev_init=bind('ggml_backend_dev_init',c.c_void_p,[c.c_void_p,c.c_char_p])
alloc=bind('ggml_backend_alloc_buffer',c.c_void_p,[c.c_void_p,c.c_size_t])
freebuf=bind('ggml_backend_buffer_free',None,[c.c_void_p])
freebackend=bind('ggml_backend_free',None,[c.c_void_p])
dev=dev_by_name(selected[0].name.encode());assert dev;backend=dev_init(dev,None);assert backend
proc=psutil.Process();rows=[]
try:
 for size in [64*1024**2,256*1024**2,512*1024**2]:
  before=proc.memory_info().private;buf=alloc(backend,size)
  after=proc.memory_info().private
  row={'requestedBytes':size,'allocated':bool(buf),'privateBefore':before,'privateAfter':after,'privateDelta':after-before}
  if buf:freebuf(buf)
  row['privateAfterFree']=proc.memory_info().private;rows.append(row)
  if not buf:break
finally:freebackend(backend);scope.close()
result={'at':datetime.now().astimezone().isoformat(),'state':'EXACT_PINNED_VULKAN_ALLOCATION_ONLY_NO_MODEL_OR_KERNEL',
 'device':selected[0].description,'runtimeSha256':runtime['runtimeSha256'],'rows':rows,'limits':limits.query(),
 'neuralInference':False,'guardRaised':False,'otherAppsChanged':False}
(OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
