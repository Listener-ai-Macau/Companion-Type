"""CPU-only native control, then original full recordings; one owned model at a time."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,subprocess,time,psutil
from moss_windows_resource_limits_20261104 import SystemRamPressure
from companion_local_pcm_session_20261114 import exclusive_file
from run_moss_overnight_20261115 import PowerLease
from practical_io_20261107 import atomic_json,stop_owned_family
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 assert not a.run.exists();a.run.mkdir(parents=True);B=read(a.control/'binding.json');S=Path(__file__).resolve().parent
 assert sha(__file__)==B['runnerSha256'] and sha(S/'cpu25_nemotron_wrapper_20261116.py')==B['wrapperSha256']
 for name in ['protocol.json','binding.json','audio-only.json']:(a.run/name).write_bytes((a.control/name).read_bytes())
 cases=read(a.run/'audio-only.json');assert len(cases)==5 and cases[0]['audioSeconds']==61
 pressure=SystemRamPressure();child=owned=None
 state={'state':'PREPARING_CPU_ONLY_NATIVE8','startedAt':datetime.now().astimezone().isoformat(),'results':[],
  'privatePeakBytes':0,'familyWorkingSetPeakBytes':0,'systemAvailableMinBytes':psutil.virtual_memory().available,
  'qualityQualified':False,'wholeMeetingAcceptance':False,'automaticRetries':0,'executionDevice':'cpu','newWeightTraining':False}
 def save():atomic_json(a.run/'run.json',state)
 save()
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')),PowerLease():
  try:
   assert not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
   for index,case in enumerate(cases):
    for phase in (['activity','cli-control'] if index==0 else ['activity']):
     if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):raise InterruptedError('Owned stop/deadline')
     tick=time.perf_counter();state.update(state='RUNNING_CPU_ONLY_NATIVE8',activeMeeting=case['meeting'],activePhase=phase);save()
     with (a.run/(case['meeting']+'-'+phase+'.log')).open('xb') as log:
      child=subprocess.Popen([B['workerPython'],str(S/'cpu25_nemotron_wrapper_20261116.py'),'--control',str(a.run),'--index',str(index),'--phase',phase],
       stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
      owned=psutil.Process(child.pid);state.update(pid=child.pid,pidCreatedAt=owned.create_time());save();last=0.
      while child.poll() is None:
       if pressure.low() or (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):
        state['stopReason']='actual_windows_low_memory' if pressure.low() else 'owned_stop_or_deadline';save()
        (a.run/'stop.request').write_text('Owned resource/deadline stop; preserve all committed probabilities.\n',encoding='utf-8')
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:stop_owned_family(child,owned)
        raise InterruptedError('CPU speaker outputs retained; continuous cache is not exported, no automatic replay')
       try:
        memory=[p.memory_info() for p in [owned]+owned.children(recursive=True)];private=sum(x.private for x in memory)
        state['privatePeakBytes']=max(state['privatePeakBytes'],private);state['familyWorkingSetPeakBytes']=max(state['familyWorkingSetPeakBytes'],sum(x.rss for x in memory))
        state['systemAvailableMinBytes']=min(state['systemAvailableMinBytes'],psutil.virtual_memory().available)
        if private>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Original2GiB family private guard')
       except psutil.Error:pass
       if time.monotonic()-last>15:save();last=time.monotonic()
       time.sleep(.5)
     file=a.run/'results'/case['meeting']/('completed-state.json' if phase=='activity' else 'native-cli-control.json');receipt=read(file) if file.exists() else {}
     expected='COMPLETE_CPU_SPEAKER_JOURNAL_UNQUALIFIED' if phase=='activity' else 'PASS_NATIVE61_C_ABI_AND_OFFICIAL_CLI_SEGMENTS'
     state['results'].append({'meeting':case['meeting'],'phase':phase,'exitCode':child.returncode,'state':receipt.get('state'),'seconds':time.perf_counter()-tick,'file':str(file),'sha256':sha(file) if file.exists() else None});save()
     assert child.returncode==0 and receipt.get('state')==expected and not receipt['gpuUsed']
    if index==0:
     state['cpu61ControlPassed']=True;save()
   state.update(state='COMPLETE_CPU_ONLY_NATIVE8_FULL4_NOT_QUALIFIED')
  except BaseException as error:state.update(state='INCOMPLETE_CPU_ONLY_NATIVE8_RETAINED',error=repr(error));raise
  finally:
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
