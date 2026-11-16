"""Single queued contrast in this active task; no automatic retry or model grid."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
C=B/'english-asr-specialist-r1';run=E/'english-asr-specialist-run-r1';PY='E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Scripts/python.exe'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
deadline=datetime.fromisoformat(read(C/'protocol.json')['neuralDeadline'])
while datetime.now().astimezone()<deadline:
 speaker=read(E/'cpu-native8-r2/run.json')
 if speaker.get('finishedAt'):break
 time.sleep(5)
else:raise TimeoutError('No new neural model after task deadline')
assert speaker['state']=='COMPLETE_CPU_ONLY_NATIVE8_FULL4_NOT_QUALIFIED','No queued model start after a failed/resource-stopped speaker run'
assert datetime.now().astimezone()<deadline
with (C/'execution.log').open('xb') as log:
 result=subprocess.run([PY,str(S/'run_english_specialist_cpu_20261116.py'),'--control',str(C),'--run',str(run)],stdout=log,stderr=subprocess.STDOUT,
  creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
assert result.returncode==0,result.returncode
with (C/'scoring.log').open('xb') as log:
 result=subprocess.run([PY,str(S/'score_english_specialist_cpu_20261116.py'),'--control',str(C),'--run',str(run)],stdout=log,stderr=subprocess.STDOUT,
  creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
assert result.returncode==0,result.returncode
score=read(C/'score.json');print(json.dumps({k:score[k] for k in ['state','aggregate','meetings','advanceToWholeEnglish']},ensure_ascii=False))
