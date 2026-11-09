"""Stream a single verified public checkpoint to E cache, without loading tensors."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,sys,time,urllib.request
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261109-sedicow-r1';sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);pressure=SystemRamPressure();read=lambda p:json.loads(p.read_text());P=read(C/'source.json');assert read(C/'runtime-probe.json')['state']=='PASS_TINY_SE_ENROLLMENT_STNO_FORWARD_NO_TRAINED_MODEL';root=Path('E:/CodexData/Companion/.model-cache/sedicow-20261109');root.mkdir(exist_ok=False);target=root/'model.safetensors';part=root/'model.safetensors.part';state={'state':'DOWNLOADING_ONE_PINNED_CHECKPOINT_NO_INFERENCE','at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'bytes':0,'model':P['model'],'revision':P['revision']};started=time.perf_counter()
def save():state.update(seconds=time.perf_counter()-started,limits=limits.query());(C/'weight-download.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
save()
try:
 h=hashlib.sha256()
 with urllib.request.urlopen(urllib.request.Request(P['weight']['url'],headers={'User-Agent':'Companion-public-model-validation'}),timeout=30) as response,part.open('xb') as f:
  for block in iter(lambda:response.read(1024*1024),b''):
   if pressure.low():raise RuntimeError('ActualWindowsLOWRAM;partialfilekept')
   f.write(block);h.update(block);state['bytes']+=len(block)
   if state['bytes']%(32*1024**2)==0:save()
 assert state['bytes']==P['weight']['bytes'] and h.hexdigest()==P['weight']['sha256'];part.rename(target);state.update(state='READY_PINNED_SE_DICOW_WEIGHTS_NOT_INFERRED',weightFile=str(target),sha256=h.hexdigest(),trainedModelLoaded=False)
except BaseException as exc:state.update(state='FAILED',failureType=type(exc).__name__,reason=str(exc));raise
finally:save();print(json.dumps(state,ensure_ascii=False),flush=True)
