"""Deadline-bounded native state transfer, one owned family, scoring per meeting."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,subprocess,sys,time
import psutil
from companion_local_pcm_session_20261114 import atomic_json,exclusive_file
from companion_windows_power_request_20261115 import PowerLease
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 assert not a.run.exists();a.run.mkdir(parents=True)
 B=read(a.control/'staged-binding.json');S=Path(__file__).resolve().parent;worker=S/'moss_staged_meeting_worker_20261115.py'
 assert sha(worker)==B['workerSha256'] and sha(__file__)==B['runnerSha256']
 assert psutil.disk_usage('E:/').free>50*1024**3
 deadline=datetime.fromisoformat(B['neuralDeadline']);pressure=SystemRamPressure();child=owned=None;started=time.monotonic()
 state={'state':'PREPARING_NATIVE_STAGED_WHOLE_MEETING_RUN','startedAt':datetime.now().astimezone().isoformat(),
  'phases':[],'completed':[],'privatePeakBytes':0,'qualityQualified':False,'newWeightTraining':False,
  'automaticRetries':0,'neuralDeadline':B['neuralDeadline'],'reportDeadline':B['reportDeadline']}
 def save():atomic_json(a.run/'run.json',state)
 def inventory(name):
  root=a.run/name
  with (a.run/(name+'.log')).open('xb') as log:
   code=subprocess.call([sys.executable,str(S/'run_practical_qwen_native_20261107.py'),'--phase','inventory','--control',str(root)],
    stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
  value=read(root/'hip-inventory.json');assert code==0 and value['state']=='PASS_CURRENT_HIP_DEVICE_INVENTORY_NO_MODEL'
  assert value['selected']['name']=='AMD Radeon RX 6800 XT' and value['selected']['architecture']=='gfx1030'
  return root,value
 save()
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),PowerLease():
  try:
   inv,value=inventory('inventory-0');refreshes=0
   for case in B['cases']:
    meeting=case['meeting']
    if not case.get('runtimeControl'):
     assert read(a.run/'runtime-control61-decode-state.json')['state']=='PASS_BIT_EXACT_STAGED_NATIVE16_TOKEN_CONTROL'
    for phase in ['prefill','decode']:
     assert not pressure.low() and datetime.now().astimezone()<deadline
     if (datetime.now().astimezone()-datetime.fromisoformat(value['finishedAt'])).total_seconds()>1700:
      refreshes+=1;inv,value=inventory('inventory-'+str(refreshes))
     env={k:v for k,v in os.environ.items() if k not in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','HIP_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']}
     env.update(HIP_VISIBLE_DEVICES=str(value['selected']['ordinal']),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
     command=[B['gpuPython'],str(worker),'--phase',phase,'--meeting',meeting,'--control',str(a.control),
      '--run',str(a.run),'--inventory',str(inv/'hip-inventory.json')]
     peak=0;tick=time.monotonic();last_save=0.
     with (a.run/(meeting+'-'+phase+'-worker.log')).open('xb') as log:
      child=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,
       creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
      owned=psutil.Process(child.pid);state.update(state='RUNNING_'+phase.upper(),activeMeeting=meeting,pid=child.pid,pidCreatedAt=owned.create_time());save()
      while child.poll() is None:
       if pressure.low() or (a.run/'stop.request').exists() or datetime.now().astimezone()>=deadline:
        (a.run/'stop.request').write_text('Owned stop, actual Windows low RAM or frozen overnight deadline.\n',encoding='utf-8')
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:stop_owned_family(child,owned)
        raise InterruptedError('Stopped at original resource or overnight deadline; cache/outputs retained')
       try:
        memory=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));peak=max(peak,memory)
        state['privatePeakBytes']=max(state['privatePeakBytes'],memory)
        if memory>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Owned staged family reached2GiB; no automatic retry')
       except psutil.Error:pass
       if time.monotonic()-last_save>15:save();last_save=time.monotonic()
       time.sleep(.5)
     result=read(a.run/(meeting+'-'+phase+'-state.json'))
     state['phases'].append({'meeting':meeting,'phase':phase,'exitCode':child.returncode,'state':result['state'],
      'seconds':time.monotonic()-tick,'privatePeakBytes':peak});save()
     expected='COMPLETE_FULL_AUDIO_PREFILL_STORED_NO_WORDS_GENERATED' if phase=='prefill' else (
      'PASS_BIT_EXACT_STAGED_NATIVE16_TOKEN_CONTROL' if case.get('runtimeControl') else 'COMPLETE_WHOLE_MEETING_JOINT_OUTPUT_SCORING_PENDING')
     assert child.returncode==0 and result['state']==expected,'Preserve failure and inspect source before changed continuation'
    state['completed'].append(meeting);state.pop('activeMeeting',None);save()
    if not case.get('runtimeControl'):
     with (a.run/(meeting+'-scoring.log')).open('xb') as log:
      code=subprocess.call([B['scoringPython'],str(S/'score_joint_whole_meetings_20261115.py'),'--control',B['scoringControl'],
       '--run',str(a.run),'--meeting',meeting],stdout=log,stderr=subprocess.STDOUT,
       creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
     assert code==0,'Inference retained; fix CPU scorer without repeating inference'
   state.update(state='COMPLETE_FOUR_NATIVE_STAGED_MEETINGS_AND_ORIGINAL_SCORES_REVIEW_PENDING')
  except BaseException as error:state.update(state='INCOMPLETE_NATIVE_STAGED_FAILURE_OR_DEADLINE_RETAINED',error=repr(error));raise
  finally:
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   pressure.close();state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.monotonic()-started);save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
