"""CPU window transcription candidate; raw words/times retained for global-speaker composition."""
from pathlib import Path
from datetime import datetime
import argparse,ctypes,dataclasses,gc,hashlib,json,math,os,sys,threading,time,wave
os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',TRANSCRIBE_NO_REPETITION_GUARD='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def finite(v):
 if isinstance(v,float) and not math.isfinite(v):return {'nativeNonfinite':str(v)}
 if isinstance(v,dict):return {k:finite(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [finite(x) for x in v]
 return v
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args()
 B=read(a.control/'binding.json');assert sha(__file__)==B['workerSha256']
 assert B['ownerCpuBudgetPermission']['quote']=='允许约 25% CPU，继续后台实测'
 limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 rate=CpuRate(5,2500);limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
 assert limits.query()['cpuRate']==2500 and limits.query()['jobPrivateCommitLimitBytes']==2*1024**3
 for path,digest in B['helpers'].items():assert sha(path)==digest,path
 C=Path(B['cppControl']);runtime=read(C/'runtime-ready.json');python=read(C/'python-source.json');model_info=read(C/'model-ready.json')
 for row in runtime['files']+python['files']:assert sha(row['file'])==row['sha256']
 assert sha(model_info['file'])==model_info['sha256']
 library=next(Path(x['file']) for x in runtime['files'] if Path(x['file']).name=='transcribe.dll')
 scope=os.add_dll_directory(str(library.parent));os.environ['TRANSCRIBE_LIBRARY']=str(library);sys.path.insert(0,python['root'])
 state={'state':'LOADING_CPU_WINDOW_JOINT_CANDIDATE','startedAt':datetime.now().astimezone().isoformat(),
  'completed':[],'newWeightTraining':False,'productDefaultChanged':False,'qualityQualified':False,
  'referencesRead':False,'trueSpeakerCountsRead':False,'wholeMeetingAcceptance':False,'executionDevice':'cpu'}
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
  with cpp.Model(model_info['file'],backend='cpu',no_mmap=False) as model:
   assert model.device.kind=='cpu' and 'moss' in model.arch.lower()
   state.update(state='CPU_WINDOW_MODEL_READY',backend=model.backend,device=model.device.description,
    modelArch=model.arch,modelSha256=model_info['sha256'],nativeCommit=cpp.native_commit());save()
   def observe():
    while not watch_stop.wait(10):save()
   threading.Thread(target=observe,daemon=True).start()
   for case in B['cases']:
    if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):raise InterruptedError('Owned stop/deadline, all original inputs and completed outputs retained')
    assert sha(case['wav'])==case['wavSha256'];state.update(state='RUNNING_CPU_WINDOW_ORIGINAL_AUDIO',activeCase=case['id']);save()
    with wave.open(case['wav'],'rb') as wav:
     assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())==(1,2,16000,case['frames'])
     samples=np.frombuffer(wav.readframes(case['frames']),dtype='<i2').astype(np.float32)/32768
    tick=time.perf_counter();result=None;semantic_error=None
    with model.session(n_threads=4,kv_type='f16',n_ctx=65536) as session:
     done=threading.Event()
     def cancel():
      while not done.wait(.25):
       if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):session.cancel();return
     task=threading.Thread(target=cancel,daemon=True);task.start()
     try:result=session.run(samples,language=None,timestamps='segment',diarize='on',keep_special_tags=True,spec_k_drafts=0)
     except cpp.OutputTruncated as error:result=error.partial_result;semantic_error=repr(error)
     finally:done.set();task.join(timeout=1)
     truncated=session.was_truncated
    assert result is not None
    packet={'case':case,'seconds':time.perf_counter()-tick,'backend':model.backend,'device':model.device.description,
     'modelSha256':model_info['sha256'],'nativeVersion':cpp.native_version(),'nativeCommit':cpp.native_commit(),
     'result':finite(dataclasses.asdict(result)),'rawDecoded':result.raw_text,
     'naturalEos':not truncated and semantic_error is None,'wasTruncated':truncated,'semanticError':semantic_error,
     'originalClipComplete':True,'speakerIdsScopedToThisInput':True,'referenceRead':False,
     'wordsRewritten':False,'newWeightTraining':False,'wholeMeetingAcceptance':False,'qualityQualified':False}
    target=a.run/(case['id']+'-raw.json');atomic_json(target,packet)
    assert packet['naturalEos'] and result.raw_text,'Incomplete raw output retained; no automatic retry or shortened input'
    state['completed'].append({'id':case['id'],'file':str(target),'sha256':sha(target),'seconds':packet['seconds'],'audioSeconds':case['audioSeconds']});save()
    del samples,result;gc.collect()
   state.update(state='COMPLETE_CPU_WINDOW_COHORT_COMPOSITION_AND_SCORING_PENDING');state.pop('activeCase',None)
 except BaseException as error:state.update(state='INCOMPLETE_CPU_WINDOW_RUN_RETAINED',error=repr(error));raise
 finally:watch_stop.set();state['finishedAt']=datetime.now().astimezone().isoformat();save();scope.close()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
