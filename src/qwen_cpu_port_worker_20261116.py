"""Existing preferred Qwen family CPU Q8 port; references never enter inference."""
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
 for path,digest in B['helpers'].items():assert sha(path)==digest
 for row in B['runtimeFiles']+B['pythonFiles']+[B['model']]:assert sha(row['file'])==row['sha256']
 scope=os.add_dll_directory(str(Path(B['library']).parent));os.environ['TRANSCRIBE_LIBRARY']=B['library'];sys.path.insert(0,B['pythonRoot'])
 state={'state':'LOADING_ONE_QWEN_CPU_PORT_CPU','startedAt':datetime.now().astimezone().isoformat(),'completed':[],
  'newWeightTraining':False,'productDefaultChanged':False,'qualityQualified':False,'referencesRead':False,'trueSpeakerCountsRead':False,
  'executionDevice':'cpu','inferenceSettings':B['settings'],'speakerAttributionVerified':False,'wordTimestampsVerified':False}
 lock=threading.RLock();watch_stop=threading.Event()
 def save():
  with lock:state['limits']=limits.query();atomic_json(a.run/'inference-state.json',state,progress=True)
 save()
 try:
  import numpy as np
  import transcribe_cpp as cpp
  assert cpp.native_version()=='0.4.2' and cpp.native_commit().startswith('275cd50')
  def log(level,message):
   with lock:
    with (a.run/'native.log').open('a',encoding='utf-8') as f:f.write(str(level)+' '+message)
  cpp.set_log_callback(log)
  with cpp.Model(B['model']['file'],backend='cpu',no_mmap=False) as model:
   assert model.device.kind=='cpu' and 'qwen' in model.arch.lower()
   state.update(backend=model.backend,device=model.device.description,modelArch=model.arch,modelSha256=B['model']['sha256'],nativeCommit=cpp.native_commit());save()
   def observe():
    while not watch_stop.wait(10):save()
   threading.Thread(target=observe,daemon=True).start()
   for case in B['cases']:
    if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):raise InterruptedError('Owned stop/deadline')
    assert sha(case['wav'])==case['wavSha256'];state.update(state='RUNNING_ONE_QWEN_CPU_PORT_CPU',activeCase=case['id']);save()
    with wave.open(case['wav'],'rb') as wav:
     assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())==(1,2,16000,case['frames'])
     pcm=wav.readframes(case['frames']);assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256']
     samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
    tick=time.perf_counter();result=None;semantic_error=None;aborted=None
    with model.session(n_threads=4,kv_type='f16',n_ctx=2048) as session:
     done=threading.Event()
     def cancel():
      while not done.wait(.25):
       if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):session.cancel();return
     task=threading.Thread(target=cancel,daemon=True);task.start()
     try:result=session.run(samples,language={'English':'en','Chinese':'zh'}[case['language']],task='transcribe',timestamps='none',diarize='off',keep_special_tags=True)
     except cpp.OutputTruncated as error:result=error.partial_result;semantic_error=repr(error)
     except cpp.Aborted as error:result=error.partial_result;semantic_error=repr(error);aborted=error
     finally:done.set();task.join(timeout=1)
     truncated=bool(cpp._lib.transcribe_was_truncated(session._h))
    assert result is not None
    packet={'case':case,'seconds':time.perf_counter()-tick,'backend':model.backend,'device':model.device.description,'modelSha256':B['model']['sha256'],
     'nativeVersion':cpp.native_version(),'nativeCommit':cpp.native_commit(),'result':finite(dataclasses.asdict(result)),
     'rawDecoded':result.raw_text,'hypothesis':result.text,'hypothesisSource':'Native Result.text, no external rewrites; full raw native result retained.',
     'naturalEos':not truncated and semantic_error is None,'wasTruncated':truncated,'semanticError':semantic_error,'originalClipComplete':True,
     'referenceRead':False,'wordsRewritten':False,'newWeightTraining':False,'qualityQualified':False,'speakerAttributionVerified':False}
    target=a.run/(case['id']+'-raw.json');atomic_json(target,packet)
    if aborted is not None:state.setdefault('interruptedOutputs',[]).append({'file':str(target),'sha256':sha(target)});save();raise aborted
    assert packet['naturalEos'] and result.text,'Incomplete/empty raw output retained without retry'
    state['completed'].append({'id':case['id'],'file':str(target),'sha256':sha(target),'seconds':packet['seconds'],'audioSeconds':case['audioSeconds']});save()
    del samples,result,pcm;gc.collect()
   state.update(state='COMPLETE_QWEN_CPU_PORT_CLIPS_SCORING_PENDING');state.pop('activeCase',None)
 except BaseException as error:state.update(state='INCOMPLETE_QWEN_CPU_PORT_RETAINED',error=repr(error));raise
 finally:watch_stop.set();state['finishedAt']=datetime.now().astimezone().isoformat();save();scope.close()
 print(json.dumps({k:v for k,v in state.items() if k!='completed'},ensure_ascii=False))
if __name__=='__main__':main()
