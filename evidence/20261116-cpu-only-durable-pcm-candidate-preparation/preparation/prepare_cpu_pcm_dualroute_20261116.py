from pathlib import Path
from datetime import datetime
import hashlib,json,wave
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';BASE=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';C=BASE/'cpu-pcm-candidate-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
B=read(C/'binding.json');assert B['workerSha256']==sha(C/'worker-before-intake-contention.py')
B['workerSha256']=sha(S/'companion_local_moss_cpu_worker_20261116.py');B['intakeContention']='Retry only an observed nonblocking intake-lock collision for up to3s before neural work; no source changes or model retries. Atomic read-only state observation needs no intake lock.'
(C/'binding.json').write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
original=read(BASE/'cpu-fixed-whole-r2/binding.json');cases=[]
for source in original['meetings'][:2]:
 assert sha(source['audio'])==source['audioSha256']
 with wave.open(source['audio'],'rb') as w:pcm=w.readframes(75*16000+4000)
 cases.append({**source,'testFrames':len(pcm)//2,'testAudioSeconds':len(pcm)/32000,'sourceStartFrame':0,'pcmSha256':hashlib.sha256(pcm).hexdigest(),
  'protocol':'Both paths submit exactly the same first75.25s real original mono PCM; live packets paced every5s, one byte-identical replay; offline intake sealed before inference. No microphones, speakers, private audio or clouds.'})
P={'at':datetime.now().astimezone().isoformat(),'cases':cases,'cpuPercent':25,'nativeThreads':4,'privateBytes':2147483648,
 'testScope':'Actual candidate CPU ASR integration through existing durable PcmSession; transcript equality across incremental/offline final blocks, live first text and completion timing. Does not qualify speaker identity/quality/card or Android.',
 'acceptance':['All original PCM bytes and final intervals equal, no missing/duplicate acknowledged source.','Actual native CPU ASR, no optional Vulkan plugin in the isolated candidate runtime.','Both final documents cover all original frames, all completed blocks reach natural EOS.','Final texts and raw decoded final blocks match across live and offline paths.','First nonempty text while source is still being ingested; report observed timing even if this fails.','First two complete30s outputs reproduce the already completed full-source native CPU candidate for the same source bytes.'],
 'noNeuralCallsDuringPreparation':True,'qualityQualified':False,'productDefaultChanged':False}
assert not (C/'dualroute-protocol.json').exists();(C/'dualroute-protocol.json').write_text(json.dumps(P,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'cases':[(r['meeting'],r['testAudioSeconds']) for r in cases],'workerSha256':B['workerSha256'],'newNeuralCalls':0},ensure_ascii=False))
