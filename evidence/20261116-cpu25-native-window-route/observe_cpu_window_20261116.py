from pathlib import Path
import argparse,datetime,json,psutil,time
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
target=a.run/'physical-resource-observations.jsonl';assert not target.exists()
previous={};old=time.monotonic();start=psutil.virtual_memory().available
with target.open('x',encoding='utf-8') as f:
 while True:
  run=read(a.run/'run.json');state=read(a.run/'inference-state.json');now=time.monotonic();family=[];cpu=0.
  try:
   parent=psutil.Process(run['pid']);assert abs(parent.create_time()-run['pidCreatedAt'])<.1
   for proc in [parent]+parent.children(recursive=True):
    try:
     t=proc.cpu_times();key=(proc.pid,proc.create_time());value=t.user+t.system
     if key in previous:cpu+=max(0,value-previous[key]);previous[key]=value
     else:previous[key]=value
     m=proc.memory_info();family.append({'pid':proc.pid,'privateBytes':m.private,'workingSetBytes':m.rss})
    except psutil.Error:pass
  except (psutil.Error,AssertionError,KeyError):pass
  available=psutil.virtual_memory().available
  row={'at':datetime.datetime.now().astimezone().isoformat(),'state':run['state'],'cases':len(state['completed']),'family':family,
   'totalMachineCpuPercent':100*cpu/max(.01,now-old)/psutil.cpu_count(),'systemAvailableBytes':available,'availableBytesAtObserverStart':start,
   'availableDifferenceIsNotAttributableOnlyToThisJob':True};f.write(json.dumps(row)+'\n');f.flush();old=now
  if run['state']!='RUNNING_CPU_WINDOW_COHORT':break
  time.sleep(5)
print(json.dumps(row))
