"""Candidate CPU consumer for the existing durable incremental/offline PCM session."""
from pathlib import Path
from datetime import datetime
import argparse,contextlib,ctypes,dataclasses,gc,hashlib,json,os,sys,threading,time,psutil
os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',TRANSCRIBE_NO_REPETITION_GUARD='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
from companion_local_pcm_session_20261114 import PcmSession,SessionConflict,read_json
from cpu_window_joint_worker_20261116 import finite
from companion_moss_raw_output_20261116 import parse_native
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def scheduled_jobs(session):
 """Final blocks first; one accepted, nonempty draft per open block.

 Empty/failed drafts can be superseded by the newest frozen source prefix.
 Complete blocks always take priority, so draft work cannot starve the final
 queue. Requests/source/results remain durable, including initial silence.
 """
 jobs=session.pending();finals=[r for r in jobs if r['blockFinal']]
 if finals:return finals[:1]
 if session.state()['sealed']:return []
 results=[read_json(p) for p in (session.root/'results').glob('*.json')]
 seen={r['request']['block'] for r in results if r['result'].get('accepted') is True and r['result']['text'].strip()}
 return [r for r in jobs if not r['blockFinal'] and r['block'] not in seen][:1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);p.add_argument('--follow-seconds',type=float,default=0);a=p.parse_args()
 B=read_json(a.control/'binding.json');assert sha(__file__)==B['workerSha256']
 assert B['ownerCpuBudgetPermission']['quote']=='允许约 25% CPU，继续后台实测'
 limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);rate=CpuRate(5,2500)
 limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
 assert limits.query()['cpuRate']==2500 and limits.query()['jobPrivateCommitLimitBytes']==2*1024**3
 for path,digest in B['helpers'].items():assert sha(path)==digest
 for row in B['runtimeFiles']+B['pythonFiles']:assert sha(row['file'])==row['sha256']
 assert not any('vulkan' in Path(r['file']).name.lower() for r in B['runtimeFiles'])
 assert sha(B['model']['file'])==B['model']['sha256']
 folder=Path(B['library']).parent;cookie=os.add_dll_directory(str(folder));os.environ['TRANSCRIBE_LIBRARY']=B['library'];sys.path.insert(0,B['pythonRoot'])
 session=PcmSession(a.session);lock_deadline=time.monotonic()+3
 while True:
  try:session.reconcile();break
  except SessionConflict as error:
   if 'Another operation owns this session lock' not in str(error) or time.monotonic()>=lock_deadline:raise
   time.sleep(.01)
 config=session.state()['config']
 assert config['language']=='auto' and config['blockFrames']==30*16000 and config['draftFrames']==5*16000
 state={'state':'LOADING_CANDIDATE_CPU_PCM_CONSUMER','startedAt':datetime.now().astimezone().isoformat(),'completed':[],
  'localOnly':True,'sourceUploaded':False,'qualityQualified':False,'productDefaultChanged':False,'tokenIdsAvailable':False,
  'fullSpeakerJournalFinalized':False,'draftPolicy':'One accepted nonempty draft per open block; empty/failed drafts may advance to the newest frozen prefix. Complete final blocks always run first.'}
 def save():state['limits']=limits.query();atomic_json(a.run/'worker-state.json',state,progress=True)
 deadline=datetime.fromisoformat(B['neuralDeadline']);began=time.monotonic();save()
 def stopping():return (a.run/'stop.request').exists() or datetime.now().astimezone()>=deadline
 try:
  import numpy as np
  import transcribe_cpp as cpp
  assert cpp.native_version()=='0.4.2' and cpp.native_commit().startswith('275cd50')
  def native_log(level,message):
   with (a.run/'native.log').open('a',encoding='utf-8') as f:f.write(str(level)+' '+message)
  cpp.set_log_callback(native_log)
  session.state()
  inference_binding={'schema':'companion.local-moss-cpu.v1','modelSha256':B['model']['sha256'],'nativeCommit':cpp.native_commit(),
   'runtimeContractSha256':B['runtimeContractSha256'],'workerSha256':B['workerSha256'],'languagePolicy':'Original bilingual model, language=None, no reference or count hints.',
   'generation':'Unmodified native greedy/EOS, f16 KV, no repetition guard or word postediting.'}
  for file in (session.root/'results').glob('*.json'):
   assert read_json(file)['inferenceBinding']==inference_binding,'Preserve the old session; cached model/runtime/language policy differs'
  idle_seconds=B.get('modelIdleReleaseSeconds',15.);assert 15<=idle_seconds<=60
  model=None;last_busy=time.monotonic();state.update(modelLoaded=False,modelLoads=0,idleModelReleases=0,idleReleaseSeconds=idle_seconds)
  with contextlib.ExitStack() as models:
   while True:
    if stopping():raise InterruptedError('Owned stop/deadline; confirmed PCM and immutable results retained')
    jobs=scheduled_jobs(session)
    if not jobs:
     document=session.document();atomic_json(a.run/'document.json',document,progress=True)
     if document['isFinal']:break
     if session.state()['sealed']:state['state']='CPU_PCM_SEALED_WITH_UNACCEPTED_OUTPUTS_RETAINED';break
     if time.monotonic()-began>=a.follow_seconds:state['state']='CPU_PCM_FOLLOW_WINDOW_ENDED_SOURCE_RETAINED';break
     if model is not None and time.monotonic()-last_busy>=idle_seconds:
      before=psutil.Process().memory_info();models.close();model=None;gc.collect();after=psutil.Process().memory_info()
      state.update(state='CPU_PCM_IDLE_MODEL_RELEASED_SOURCE_AND_RESULTS_RETAINED',modelLoaded=False,idleModelReleases=state['idleModelReleases']+1,
       lastIdleRelease={'at':datetime.now().astimezone().isoformat(),'beforeWorkingSetBytes':before.rss,'afterWorkingSetBytes':after.rss,
        'beforePrivateBytes':before.private,'afterPrivateBytes':after.private,'confirmedFrames':session.state()['confirmedFrames']});save()
     time.sleep(.25);continue
    if model is None:
     if psutil.virtual_memory().available<int(3.18*1024**3):
      state['state']='CPU_PCM_WAITING_ORIGINAL_RAM_START_GATE_BEFORE_MODEL_RELOAD';save();time.sleep(.25);continue
     model=models.enter_context(cpp.Model(B['model']['file'],backend='cpu',no_mmap=False));assert model.device.kind=='cpu'
     state.update(modelLoaded=True,modelLoads=state['modelLoads']+1,backend=model.backend,device=model.device.description);save()
    job=jobs[0];pcm=session.read_request_pcm(job);samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
    state.update(state='RUNNING_CANDIDATE_CPU_PCM_REQUEST',activeJob=job['jobId']);save();tick=time.perf_counter();result=None;semantic_error=None;aborted_error=None
    with model.session(n_threads=4,kv_type='f16',n_ctx=65536) as native:
     done=threading.Event()
     def cancel():
      while not done.wait(.25):
       if stopping():native.cancel();return
     task=threading.Thread(target=cancel,daemon=True);task.start()
     try:result=native.run(samples,language=None,timestamps='segment',diarize='on',keep_special_tags=True,spec_k_drafts=0)
     except cpp.OutputTruncated as error:result=error.partial_result;semantic_error=repr(error)
     except cpp.Aborted as error:result=error.partial_result;semantic_error=repr(error);aborted_error=error
     finally:done.set();task.join(timeout=1)
     truncated=bool(cpp._lib.transcribe_was_truncated(native._h))
    assert result is not None
    parsed,all_rows,residual=parse_native(result.raw_text);text=' '.join(r['text'] for r in all_rows)
    payload={'text':text,'language':None,'rawGeneratedIds':[],'tokenIdsAvailable':False,'rawDecoded':result.raw_text,
     'nativeResult':finite(dataclasses.asdict(result)),'naturalEos':not truncated and semantic_error is None,
     'accepted':not truncated and semantic_error is None,'reviewRequired':True,'seconds':time.perf_counter()-tick,
     'rawSpeakerIdsAreLocalToThisRequest':True,'speakerIdentityVerified':False,'wordsRewritten':False,'qualityQualified':False,
     'semanticError':semantic_error,'unconfirmedAudioIntervals':[] if not truncated and semantic_error is None else [{'startFrame':job['startFrame'],'endFrame':job['endFrame'],'reason':'incomplete_native_output'}]}
    if aborted_error is not None:
     atomic_json(a.run/(job['jobId']+'-interrupted.json'),{'request':job,'result':payload});raise aborted_error
    session.save_result(job,payload,inference_binding=inference_binding)
    document=session.document();atomic_json(a.run/'document.json',document,progress=True)
    state['completed'].append({'job':job['jobId'],'block':job['block'],'blockFinal':job['blockFinal'],'inputFrames':job['endFrame']-job['startFrame'],
     'seconds':payload['seconds'],'accepted':payload['accepted'],'resultFile':str(session.root/'results'/(job['jobId']+'.json'))});last_busy=time.monotonic();save()
   if session.document()['isFinal']:state['state']='COMPLETE_CPU_PCM_FINAL_TEXT_SPEAKERS_PENDING_NOT_QUALIFIED'
 except BaseException as error:state.update(state='INCOMPLETE_CPU_PCM_RETAINED',error=repr(error));raise
 finally:state['finishedAt']=datetime.now().astimezone().isoformat();save();cookie.close()
 print(json.dumps({k:v for k,v in state.items() if k!='completed'},ensure_ascii=False))
if __name__=='__main__':main()
