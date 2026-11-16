from pathlib import Path
from datetime import datetime
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';C=B/'english-asr-specialist-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
old=read(B/'cpu-pcm-candidate-r1/binding.json');protocol=read(C/'protocol.json')
binding={k:old[k] for k in ['workerPython','ownerCpuBudgetPermission','neuralDeadline','runtimeFiles','library','pythonFiles','pythonRoot','helpers','cpuPercent','privateBytes']}
binding.update(at=datetime.now().astimezone().isoformat(),workerSha256=sha(S/'english_specialist_cpu_worker_20261116.py'),
 runnerSha256=sha(S/'run_english_specialist_cpu_20261116.py'),model=read(C/'model-ready.json'),cases=protocol['cases'],settings=protocol['settings'],
 protocolSha256=sha(C/'protocol.json'),qualityQualified=False,productDefaultChanged=False,newWeightTraining=False)
assert not (C/'binding.json').exists();(C/'binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
source=Path(read(B/'stagea-cpu-composition-r2/scoring-binding.json')['sourceControl'])
files={str(p):sha(p) for p in [C/'protocol.json',C/'binding.json',source/'scoring-only.json',B/'stagea-cpu-composition-r2/score.json',S/'score_sequential_meetings_20261115.py']}
score={'reference':str(source/'scoring-only.json'),'mossScore':str(B/'stagea-cpu-composition-r2/score.json'),'files':files,
 'scorerSha256':sha(S/'score_english_specialist_cpu_20261116.py'),'hypothesis':'Native Result.text; no external rewrite; native raw result retained.',
 'inferenceReadsScoringReferences':False}
(C/'scoring-binding.json').write_text(json.dumps(score,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ['english_specialist_cpu_worker_20261116.py','run_english_specialist_cpu_20261116.py','score_english_specialist_cpu_20261116.py']:compile((S/name).read_text(encoding='utf-8'),str(S/name),'exec')
print(json.dumps({'control':str(C),'model':binding['model']['sha256'],'cases':len(binding['cases']),'settingsFrozen':True,'neuralCalls':0}))
