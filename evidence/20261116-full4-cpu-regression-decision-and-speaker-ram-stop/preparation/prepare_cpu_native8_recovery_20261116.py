from pathlib import Path
from datetime import datetime
import hashlib,json,psutil,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import SystemRamPressure
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';BASE=D/'joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
old=BASE/'cpu-native8-r1';closed=E/old.name;C=BASE/'cpu-native8-r2';run=E/C.name;assert not C.exists() and not run.exists()
previous=read(closed/'run.json');assert previous['finishedAt'] and previous['cpu61ControlPassed'] and previous['stopReason']=='actual_windows_low_memory'
pressure=SystemRamPressure();samples=[];stable=None;began=time.monotonic()
try:
 while time.monotonic()-began<=300:
  available=psutil.virtual_memory().available;low=pressure.low();now=time.monotonic();samples.append({'at':datetime.now().astimezone().isoformat(),'availableBytes':available,'actualWindowsLowMemory':low})
  if not low and available>=int(3.18*1024**3):
   if stable is None:stable=now
   if now-stable>=60:break
  else:stable=None
  time.sleep(5)
 else:raise RuntimeError('Original recovery gate not stable; no new neural attempt created')
finally:
 pressure.close()
 observation=E/('cpu-native8-recovery-observation-'+str(time.time_ns())+'.json')
 observation.write_text(json.dumps({'observedAt':datetime.now().astimezone().isoformat(),'samples':samples,'stableRecoveryReached':stable is not None and time.monotonic()-stable>=60,'newNeuralCalls':0},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert stable is not None and time.monotonic()-stable>=60
C.mkdir();P=read(old/'protocol.json');P['probabilityCacheRoot']=str(run/'probabilities');B=read(old/'binding.json')
assert B['runnerSha256']==sha(old/'runner-before-control-proof-resume.py')
B.update(at=datetime.now().astimezone().isoformat(),runnerSha256=sha(S/'run_cpu25_nemotron_20261116.py'),
 reusedCpu61Control={'run':str(closed/'run.json'),'runSha256':sha(closed/'run.json'),'protocol':str(closed/'protocol.json'),'binding':str(closed/'binding.json'),
 'reason':'61s CPU C ABI and official CPU CLI already passed; actual Windows low-RAM interrupted the first full source. After60s recovery, preserve that partial and restart the continuous speaker state from source start once, without repeating control or any completed ASR.'},
 recoveryEvidence=samples,qualityQualified=False)
for name,value in [('protocol.json',P),('binding.json',B)]:
 (C/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(C/'audio-only.json').write_bytes((old/'audio-only.json').read_bytes())
p=Path('work/bilingual_progress.json');d=read(p);o=d['ownerOvernightRun20261115'];o.update(currentCpuSpeakerControl=str(C),currentCpuSpeakerRun=str(run),cpuSpeakerRuntimeState='CPU61_PASSED_RESOURCE_RECOVERED_FULL4_PENDING')
d['logResult']+='\n'+B['at']+' CPU-only native8原61s实际通过：C ABI全音3.270s、官方CPU CLI逐段/毫秒一致，GPU=false/25%/2GiB。随后首场整会因Windows真实低内存（可用约813MB）自停，非私有2GiB超限/模型算错；原partial概率/控制保留，隐藏cache无导出不伪续。恢复后原3.18GiB+Windows正常连续60s，r2复用已过CPU控制，仅重新从整会源起点跑连续声纹，全部ASR290条不重算。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'control':str(C),'run':str(run),'stableRecoverySeconds':time.monotonic()-stable,'lastAvailableBytes':samples[-1]['availableBytes'],'controlsReusedNoRerun':True}))
