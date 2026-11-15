"""Observe this single run until a real score or terminal state appears; no retries/actions."""
from pathlib import Path
from datetime import datetime
import argparse,json,time,psutil
p=argparse.ArgumentParser();p.add_argument('--until-scores',type=int,required=True);p.add_argument('--run',type=Path);a=p.parse_args()
run=a.run or Path(json.loads(Path('work/bilingual_progress.json').read_text(encoding='utf-8'))['ownerOvernightRun20261115']['currentStagedRun'])
control=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/overnight-r5')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
last=0.;old=None
while True:
 r=read(run/'run.json');meeting=r.get('activeMeeting');s={}
 if meeting:
  for phase in ['decode','prefill']:
   path=run/(meeting+'-'+phase+'-state.json')
   if path.exists():s=read(path);break
 scores=[p.name for p in control.glob('score-*.json')]
 terminal=bool(r.get('finishedAt'));identity=(meeting,s.get('state'),len(scores),terminal)
 if identity!=old or time.monotonic()-last>=55:
  row={'at':datetime.now().astimezone().isoformat(),'runState':r['state'],'meeting':meeting,
   'phaseState':s.get('state'),'generated':s.get('generatedTokens'),'retained':s.get('retainedPrefixTokens'),
   'decodeSeconds':s.get('decodeSeconds'),'privatePeakGiB':round(r['privatePeakBytes']/2**30,3),
   'availableMemoryGiB':round(psutil.virtual_memory().available/2**30,2),'scores':scores,'terminal':terminal}
  with (run/'observation-only.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  print(json.dumps(row,ensure_ascii=False),flush=True);old=identity;last=time.monotonic()
 if terminal or len(scores)>=a.until_scores:break
 time.sleep(5)
