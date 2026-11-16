"""No model: verify the isolated native ABI and an inventory containing CPU only."""
from pathlib import Path
import ctypes,hashlib,json,os,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/cpu-pcm-candidate-r1'
B=json.loads((C/'binding.json').read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not (C/'cpu-runtime-abi-control.json').exists()
for row in B['runtimeFiles']+B['pythonFiles']:assert sha(row['file'])==row['sha256']
assert not any('vulkan' in Path(r['file']).name.lower() for r in B['runtimeFiles'])
cookie=os.add_dll_directory(str(Path(B['library']).parent));os.environ['TRANSCRIBE_LIBRARY']=B['library'];sys.path.insert(0,B['pythonRoot'])
try:
 import transcribe_cpp as cpp
 assert cpp.native_version()=='0.4.2' and cpp.native_commit()=='275cd50'
 devices=cpp.backends();assert devices and all(d.kind=='cpu' for d in devices)
 assert cpp.backend_available('cpu') and not cpp.backend_available('vulkan')
 result={'state':'PASS_CPU_ONLY_NATIVE_ABI_AND_DEVICE_INVENTORY_NO_MODEL','nativeVersion':cpp.native_version(),'nativeCommit':cpp.native_commit(),
  'devices':[{'kind':d.kind,'description':d.description} for d in devices],'sourceBindingSha256':sha(C/'binding.json'),
  'runtimeContractSha256':B['runtimeContractSha256'],'modelLoaded':False,'newNeuralCalls':0,'gpuDeviceEnumerated':False,'qualityQualified':False,'limits':limits.query()}
 (C/'cpu-runtime-abi-control.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
finally:cookie.close()
