"""Read every original PCM frame exactly once, using fixed30s CPU ASR sessions."""
from pathlib import Path
from datetime import datetime
import argparse,ctypes,dataclasses,gc,hashlib,json,os,sys,threading,time,wave
os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',TRANSCRIBE_NO_REPETITION_GUARD='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
from cpu_window_joint_worker_20261116 import finite
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 B=read(a.control/'binding.json');assert sha(__file__)==B['workerSha256']
 assert B['ownerCpuBudgetPermission']['quote']=='允许约 25% CPU，继续后台实测'
 limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);rate=CpuRate(5,2500)
 limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
 assert limits.query()['cpuRate']==2500 and limits.query()['jobPrivateCommitLimitBytes']==2*1024**3
 for path,digest in B['helpers'].items():assert sha(path)==digest,path
 C=Path(B['cppControl']);runtime=read(C/'runtime-ready.json');python=read(C/'python-source.json');model_info=read(C/'model-ready.json')
 for row in runtime['files']+python['files']:assert sha(row['file'])==row['sha256']
 assert sha(model_info['file'])==model_info['sha256']
 library=next(Path(x['file']) for x in runtime['files'] if Path(x['file']).name=='transcribe.dll')
 scope=os.add_dll_directory(str(library.parent));os.environ['TRANSCRIBE_LIBRARY']=str(library);sys.path.insert(0,python['root'])
 state={'state':'LOADING_CPU_FIXED_CHUNK_MODEL','startedAt':datetime.now().astimezone().isoformat(),'completed':[],
  'incompleteOutputCases':[],'newWeightTraining':False,'productDefaultChanged':False,'qualityQualified':False,'referencesRead':False,
  'trueSpeakerCountsRead':False,'wholeMeetingAcceptance':False,'executionDevice':'cpu','sourceFramesProcessed':0}
 lock=threading.RLock();watch_stop=threading.Event()
 def save():
  with lock:state['limits']=limits.query();atomic_json(a.run/'inference-state.json',state,progress=True)
 save()
 try:
  import numpy as np
  import transcribe_cpp as cpp
  assert cpp.native_version()=='0.4.2' and cpp.native_commit().startswith('275cd50')
  plans={r['id']:r for r in B['cases']};retained=set()
  for item in B.get('resumeCompleted',[]):
   assert sha(item['file'])==item['sha256'];packet=read(item['file']);case=plans[item['id']]
   assert packet['case']==case and packet['originalChunkInputComplete'] and packet['modelSha256']==model_info['sha256']
   assert packet['backend']=='CPU' and packet['nativeCommit']==cpp.native_commit() and item['id'] not in retained
   retained.add(item['id']);state['completed'].append(item);state['sourceFramesProcessed']+=case['frames']
   if not packet['naturalEos']:state['incompleteOutputCases'].append(item['id'])
  state.update(resumedCompleteInputs=len(retained),resumeSource=B.get('resumeSource'));save()
  def log(level,message):
   with lock:
    with (a.run/'native.log').open('a',encoding='utf-8') as f:f.write(str(level)+' '+message)
  cpp.set_log_callback(log)
  for meeting in B['meetings']:
   assert sha(meeting['audio'])==meeting['audioSha256']
   with wave.open(meeting['audio'],'rb') as wav:assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())==(1,2,16000,meeting['frames'])
   selected=[x for x in B['cases'] if x['meeting']==meeting['meeting']];cursor=0
   for c in selected:assert c['sourceStartFrame']==cursor;cursor+=c['frames']
   assert cursor==meeting['frames']
  with cpp.Model(model_info['file'],backend='cpu',no_mmap=False) as model:
   assert model.device.kind=='cpu' and 'moss' in model.arch.lower()
   state.update(backend=model.backend,device=model.device.description,modelArch=model.arch,modelSha256=model_info['sha256'],nativeCommit=cpp.native_commit());save()
   def observe():
    while not watch_stop.wait(10):save()
   threading.Thread(target=observe,daemon=True).start()
   for case in B['cases']:
    if case['id'] in retained:continue
    if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):raise InterruptedError('Owned stop/deadline, complete windows and inputs retained')
    state.update(state='RUNNING_CPU_FIXED_ORIGINAL_CHUNKS',activeCase=case['id'],activeMeeting=case['meeting']);save()
    with wave.open(case['audio'],'rb') as wav:
     wav.setpos(case['sourceStartFrame']);pcm=wav.readframes(case['frames']);assert len(pcm)==case['frames']*2
    pcm_sha=hashlib.sha256(pcm).hexdigest();samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
    tick=time.perf_counter();result=None;semantic_error=None;aborted_error=None
    with model.session(n_threads=4,kv_type='f16',n_ctx=65536) as session:
     done=threading.Event()
     def cancel():
      while not done.wait(.25):
       if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):session.cancel();return
     task=threading.Thread(target=cancel,daemon=True);task.start()
     try:result=session.run(samples,language=None,timestamps='segment',diarize='on',keep_special_tags=True,spec_k_drafts=0)
     except cpp.OutputTruncated as error:result=error.partial_result;semantic_error=repr(error)
     except cpp.Aborted as error:result=error.partial_result;semantic_error=repr(error);aborted_error=error
     finally:done.set();task.join(timeout=1)
     truncated=bool(cpp._lib.transcribe_was_truncated(session._h))
    assert result is not None
    packet={'case':case,'pcmSha256':pcm_sha,'seconds':time.perf_counter()-tick,'backend':model.backend,'device':model.device.description,
     'modelSha256':model_info['sha256'],'nativeVersion':cpp.native_version(),'nativeCommit':cpp.native_commit(),
     'result':finite(dataclasses.asdict(result)),'rawDecoded':result.raw_text,'naturalEos':not truncated and semantic_error is None,
     'wasTruncated':truncated,'semanticError':semantic_error,'originalChunkInputComplete':True,'speakerIdsScopedToThisInput':True,
     'referenceRead':False,'wordsRewritten':False,'newWeightTraining':False,'wholeMeetingAcceptance':False,'qualityQualified':False}
    target=a.run/(case['id']+'-raw.json');atomic_json(target,packet)
    if aborted_error is not None:
     state.setdefault('interruptedOutputs',[]).append({'id':case['id'],'file':str(target),'sha256':sha(target),'reason':semantic_error})
     save();raise aborted_error
    if not packet['naturalEos']:state['incompleteOutputCases'].append(case['id'])
    state['completed'].append({'id':case['id'],'file':str(target),'sha256':sha(target),'seconds':packet['seconds'],'audioSeconds':case['audioSeconds'],'naturalEos':packet['naturalEos']})
    state['sourceFramesProcessed']+=case['frames'];save();del samples,result,pcm;gc.collect()
   state.update(state='COMPLETE_CPU_FIXED_CHUNKS_COMPOSITION_AND_SCORING_PENDING');state.pop('activeCase',None)
 except BaseException as error:state.update(state='INCOMPLETE_CPU_FIXED_CHUNKS_RETAINED',error=repr(error));raise
 finally:watch_stop.set();state['finishedAt']=datetime.now().astimezone().isoformat();save();scope.close()
 print(json.dumps({k:v for k,v in state.items() if k!='completed'},ensure_ascii=False))
if __name__=='__main__':main()
