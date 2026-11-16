"""General bounded-lifetime CPU alignment; never resumes a stateful speaker model."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,sys,time,psutil
from companion_cpu_guarded_stage_20261116 import run_cpu_stage
from companion_local_pcm_session_20261114 import read_json,atomic_json
from moss_windows_resource_limits_20261104 import SystemRamPressure
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def batches(rows):return [rows[i:i+16] for i in range(0,len(rows),16)]
def validate(item,expected,binding):
 assert sha(item['file'])==item['sha256'];packet=read_json(item['file']);assert packet['case']==expected
 assert packet['modelSha256']==binding['modelSha256'] and packet['gpuUsed'] is False
 payload=packet['payload'];assert payload['originalText']==expected['text']==''.join(x['text'] for x in payload['units']) and payload['allOriginalCharactersPreserved']
 return item
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 B=read_json(a.control/'binding.json');contract=read_json(a.control/'orchestration-binding.json');assert sha(__file__)==contract['coordinatorSha256']
 for file,digest in contract['files'].items():assert sha(file)==digest
 assert contract['maximumLeavesPerWorker']==16;cases={x['id']:x for x in B['cases']};assert len(cases)==len(B['cases'])>0
 completed=[]
 if B.get('reuseCompleted'):
  old=B['reuseBinding'];assert sha(old['file'])==old['sha256'];old_binding=read_json(old['file'])
  for key in ['workerSha256','helpers','modelRoot','modelSha256','cpuTorchSite']:assert old_binding[key]==B[key]
  for item in B['reuseCompleted']:completed.append(validate(item,cases[item['id']],B))
 assert len({x['id'] for x in completed})==len(completed)
 saved={x['id'] for x in completed};pending=[x for x in B['cases'] if x['id'] not in saved]
 assert not a.run.exists();a.run.mkdir(parents=True);state={'state':'PREPARING_BOUNDED_STATELESS_CPU_ALIGNMENT','startedAt':datetime.now().astimezone().isoformat(),'completed':completed,
  'maximumLeavesPerWorker':16,'reusedLeaves':len(completed),'newWorkerProcesses':0,'newNeuralCalls':0,'statefulSpeakerModelHandled':False,'qualityQualified':False}
 def save():atomic_json(a.run/'worker-state.json',state)
 save();pressure=SystemRamPressure()
 try:
  if pending:
   stable=None
   while True:
    if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):raise InterruptedError('Owned stop/deadline before model startup')
    healthy=not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
    stable=time.monotonic() if healthy and stable is None else (stable if healthy else None)
    if stable is not None and time.monotonic()-stable>=60:break
    time.sleep(1)
  for index,rows in enumerate(batches(pending)):
   control=a.run/('batch-control-'+str(index));control.mkdir();attempt=a.run/('batch-run-'+str(index));part=dict(B,cases=rows,reuseCompleted=[]);part.pop('reuseBinding',None)
   atomic_json(control/'binding.json',part);state.update(state='RUNNING_BOUNDED_STATELESS_CPU_ALIGNMENT',activeBatch=index);save();state['newWorkerProcesses']+=1
   try:
    run_cpu_stage(a.run,state,'alignment_batch_'+str(index),[sys.executable,str(Path(__file__).with_name('run_cpu_forced_alignment_20261116.py')),
     '--control',str(control),'--run',str(attempt)],timeout=3600,deadline=B['neuralDeadline'])
   finally:
    terminal=attempt/'worker-state.json'
    if terminal.exists():
     result=read_json(terminal)
     for item in result['completed']:completed.append(validate(item,cases[item['id']],B))
     state['newNeuralCalls']+=result['newNeuralCalls'];state['completed']=completed;save()
   assert read_json(attempt/'worker-state.json')['state']=='COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED'
  assert len(completed)==len(cases) and {x['id'] for x in completed}==set(cases)
  order={x['id']:i for i,x in enumerate(B['cases'])};state['completed']=sorted(completed,key=lambda x:order[x['id']]);state.update(state='COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED');state.pop('activeBatch',None)
 except BaseException as error:state.update(state='INCOMPLETE_BOUNDED_STATELESS_CPU_ALIGNMENT_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
 finally:pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
 print(json.dumps({k:v for k,v in state.items() if k!='completed'},ensure_ascii=False))
if __name__=='__main__':main()
