"""Pinned native Vulkan backend for the same joint-model architecture.

Avoid the already-failed Windows HIP/LLVM full-context execution path. Runtime
and model downloads are public, hash-bound, isolated; no driver/app changes.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,sys,tarfile,urllib.request
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'joint-architecture-r1/cpp-r1';C.mkdir()
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/cpp-r1');E.mkdir()
runtime='https://github.com/handy-computer/transcribe.cpp/releases/download/v0.4.2/transcribe-native-0.4.2-windows-x86_64-cpu-vulkan.tar.gz'
runtime_sha='6094102cf57b404b050707ceb258b12ce647b92e801b5d46077214e5b030c8aa'
commit='275cd50d2c4104c204009a197ac091b9687668e5'
revision='5780e665a3eb60694e0402ed25b6775ee587681b'
model_url=f'https://huggingface.co/handy-computer/MOSS-Transcribe-Diarize-gguf/resolve/{revision}/MOSS-Transcribe-Diarize-BF16.gguf'
model_sha='155eb3ed6390300c7891edc56cce0c9fb5103a8dcc09a708a2fb7502d99b8a30'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def download(url,dest,size,digest):
 assert not dest.exists();partial=dest.with_suffix(dest.suffix+'.partial');assert not partial.exists()
 with urllib.request.urlopen(url,timeout=90) as response,partial.open('xb') as out:
  count=0
  while True:
   block=response.read(1024*1024)
   if not block:break
   count+=len(block);assert count<=size;out.write(block)
  out.flush();os.fsync(out.fileno())
 assert count==size and sha(partial)==digest;partial.rename(dest)
write(C/'protocol.json',{'at':datetime.now().astimezone().isoformat(),
 'reason':'Native Transformers whole35min entered all71 acoustic windows and full27924-token prefill, then Windows LLVM reported out-of-memory/0xC0000005 and family exceeded2GiB. Retain that failure; do not repeat HIP or raise its budget. Use a prebuilt native C++/Vulkan execution stack for the same0.9B joint task.',
 'runtime':runtime,'runtimeSha256':runtime_sha,'sourceCommit':commit,'release':'v0.4.2','releasePublishedAt':'2026-11-12T11:35:42Z',
 'model':model_url,'modelSha256':model_sha,'modelRevision':revision,'precision':'BF16; do not try a quantization grid',
 'publicRuntimeDocs':'https://github.com/handy-computer/transcribe.cpp/blob/main/docs/models/moss-transcribe-diarize.md',
 'wholeMeetingSelection':str(D/'joint-architecture-r1/full-audio-only.json'),'newWeightsTrained':False,
 'memoryBudgetGiB':2,'cpuPercent':5,'actualWindowsLowMemoryStop':True,'existingProductDefaultChanged':False,'qualityQualified':False})
assert shutil.disk_usage(E).free>30*1024**3+1826883264+18052817
archive=E/'runtime.tar.gz';download(runtime,archive,18052817,runtime_sha)
with tarfile.open(archive) as tar:
 for member in tar.getmembers():
  target=(E/'runtime'/member.name).resolve();assert target.is_relative_to((E/'runtime').resolve())
  assert not member.issym() and not member.islnk()
 tar.extractall(E/'runtime',filter='data')
header_url=f'https://raw.githubusercontent.com/handy-computer/transcribe.cpp/{commit}/include/transcribe.h'
with urllib.request.urlopen(header_url,timeout=30) as response:header=response.read()
assert hashlib.sha1(b'blob '+str(len(header)).encode()+b'\0'+header).hexdigest()=='717b3cc92d21044e32ef6f52e065f667190f544c'
(C/'transcribe.h').write_bytes(header)
write(C/'runtime-ready.json',{'state':'PINNED_NATIVE_WINDOWS_VULKAN_RUNTIME_EXTRACTED_NOT_LOADED','root':str(E/'runtime'),
 'runtimeSha256':sha(archive),'headerSource':header_url,'headerSha256':sha(C/'transcribe.h'),
 'files':[{'file':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in (E/'runtime').rglob('*') if p.is_file()]})
print('PINNED_NATIVE_VULKAN_RUNTIME_READY_NOT_LOADED',flush=True)
download(model_url,E/'MOSS-BF16.gguf',1826883264,model_sha)
write(C/'model-ready.json',{'state':'PINNED_PUBLIC_BF16_GGUF_READY_NO_INFERENCE','file':str(E/'MOSS-BF16.gguf'),
 'sha256':model_sha,'bytes':1826883264,'sourceRevision':revision,'precision':'BF16','newTraining':False,'qualityQualified':False})
print('PINNED_BF16_JOINT_GGUF_READY_NO_INFERENCE',flush=True)
