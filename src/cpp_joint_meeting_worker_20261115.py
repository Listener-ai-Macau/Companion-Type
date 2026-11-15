"""Pinned upstream C ABI, selected6800XT Vulkan, complete original recordings."""
from pathlib import Path
from datetime import datetime
import argparse,dataclasses,gc,hashlib,json,math,os,sys,threading,time,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 TRANSCRIBE_NO_REPETITION_GUARD='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def finite(value):
 if isinstance(value,float) and not math.isfinite(value):return {'nativeNonfinite':str(value)}
 if isinstance(value,dict):return {k:finite(v) for k,v in value.items()}
 if isinstance(value,(tuple,list)):return [finite(v) for v in value]
 return value
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['inventory','full'],required=True)
 for flag in ['control','run']:p.add_argument('--'+flag,type=Path,required=True)
 a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 B=read(a.control/'cpp-binding.json');assert B['workerSha256']==sha(__file__)
 for path,digest in B['helpers'].items():assert sha(path)==digest
 runtime=read(a.control/'runtime-ready.json');python=read(a.control/'python-source.json')
 for file in runtime['files']+python['files']:assert sha(file['file'])==file['sha256']
 library=next(Path(r['file']) for r in runtime['files'] if Path(r['file']).name=='transcribe.dll')
 dll_scope=os.add_dll_directory(str(library.parent));os.environ['TRANSCRIBE_LIBRARY']=str(library)
 sys.path.insert(0,python['root'])
 state={'state':'STARTING_PINNED_CPP_'+a.phase.upper(),'startedAt':datetime.now().astimezone().isoformat(),
  'completed':[],'qualityQualified':False,'newWeightTraining':False,'goldRead':False,'speakerCountHintUsed':False,
  'automaticRetries':0,'runtimeSha256':runtime['runtimeSha256']}
 guard=threading.RLock();stop_monitor=threading.Event()
 def save():
  with guard:state['limits']=limits.query();atomic_json(a.run/(a.phase+'-state.json'),state,progress=True)
 began=time.perf_counter();save()
 try:
  import transcribe_cpp as cpp
  assert cpp.native_version()=='0.4.2'
  devices=cpp.backends();candidates=[d for d in devices if d.kind=='vulkan' and 'RX 6800 XT' in d.description]
  assert len(candidates)==1,'Require unique live6800XT Vulkan device, no automatic CPU fallback'
  selected=candidates[0];assert selected.memory_total>=15*1024**3
  describe=lambda d:{k:getattr(d,k) for k in ['name','description','kind','device_type','device_id','memory_total','memory_free','index']}
  state.update(nativeVersion=cpp.native_version(),nativeCommit=cpp.native_commit(),selectedDevice=describe(selected))
  if a.phase=='inventory':
   state.update(state='PASS_PINNED_CPP_ABI_AND_LIVE_6800XT_VULKAN_NO_MODEL',devices=[describe(d) for d in devices]);save()
  else:
   inventory=read(a.run/'inventory-state.json')
   assert inventory['state']=='PASS_PINNED_CPP_ABI_AND_LIVE_6800XT_VULKAN_NO_MODEL'
   assert selected.device_id==inventory['selectedDevice']['device_id'] and selected.description==inventory['selectedDevice']['description']
   assert (datetime.now().astimezone()-datetime.fromisoformat(inventory['finishedAt'])).total_seconds()<1800
   model_info=read(a.control/'model-ready.json');assert sha(model_info['file'])==model_info['sha256']
   assert sha(a.control.parent/'full-audio-only.json')==B['wholeManifestSha256']
   assert sha(B['smokeAudio'])==B['smokeAudioSha256']
   log_lock=threading.Lock();last_log_save=[0.]
   def log(level,message):
    with log_lock:
     with (a.run/'native.log').open('a',encoding='utf-8') as out:out.write(str(level)+' '+message)
    if time.monotonic()-last_log_save[0]>10:
     with guard:state['lastNativeMessage']=message[-700:]
     save();last_log_save[0]=time.monotonic()
   cpp.set_log_callback(log)
   state.update(state='LOADING_BF16_JOINT_MODEL_ON_VULKAN');save()
   with cpp.Model(model_info['file'],backend='vulkan',device=selected) as model:
    assert model.device.description==selected.description and model.device.device_id==selected.device_id
    assert model.device.kind=='vulkan' and 'moss' in model.arch.lower()
    state.update(modelArch=model.arch,modelVariant=model.variant,actualBackend=model.backend,
     capabilities=finite(dataclasses.asdict(model.capabilities)),modelLoadSeconds=time.perf_counter()-began);save()
    def monitor():
     while not stop_monitor.wait(10):save()
    observer=threading.Thread(target=monitor,daemon=True);observer.start()
    def audio(path,frames):
     import numpy as np
     with wave.open(path,'rb') as w:
      assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(1,2,16000) and w.getnframes()==frames
      return np.frombuffer(w.readframes(frames),dtype='<i2').astype(np.float32)/32768
    cases=[{'meeting':'runtime-smoke61','audio':B['smokeAudio'],'audioSha256':B['smokeAudioSha256'],
     'frames':976048,'audioSeconds':976048/16000}]+read(a.control.parent/'full-audio-only.json')
    for case in cases:
     if (a.run/'stop.request').exists():raise InterruptedError('Owned stop before complete original recording')
     assert sha(case['audio'])==case['audioSha256'];samples=audio(case['audio'],case['frames'])
     state.update(state='RUNNING_CPP_JOINT_COMPLETE_RECORDING',meeting=case['meeting'],audioSeconds=case['audioSeconds']);save()
     tick=time.perf_counter();semantic_error=None;result=None
     with model.session(n_threads=1,kv_type='f16',n_ctx=65536) as session:
      session_limits=dataclasses.asdict(session.limits)
      assert session_limits['effective_max_audio_ms']==0 or session_limits['effective_max_audio_ms']>=math.ceil(case['audioSeconds']*1000)
      done=threading.Event()
      def cancel_when_requested():
       while not done.wait(.25):
        if (a.run/'stop.request').exists():session.cancel();return
      canceller=threading.Thread(target=cancel_when_requested,daemon=True);canceller.start()
      try:
       result=session.run(samples,language=None,timestamps='segment',diarize='on',keep_special_tags=True,spec_k_drafts=0)
      except cpp.OutputTruncated as error:result=error.partial_result;semantic_error=repr(error)
      finally:done.set();canceller.join(timeout=1)
      was_truncated=session.was_truncated
     assert result is not None
     packet={'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
      'seconds':time.perf_counter()-tick,'backend':model.backend,'device':describe(model.device),
      'nativeVersion':cpp.native_version(),'nativeCommit':cpp.native_commit(),'modelSha256':model_info['sha256'],
      'result':finite(dataclasses.asdict(result)),'wasTruncated':was_truncated,'semanticError':semantic_error,
      'sessionLimits':session_limits,'sourceAudioComplete':case['meeting']!='runtime-smoke61',
      'noSourceStitchingOrSpeakerReset':True,'noReferenceOrSpeakerCountInput':True,'qualityQualified':False,
      'postEditPolicy':'Preserve upstream raw_text and raw token/segment structures; score raw marker content, no filler/number/tag cleanup.'}
     atomic_json(a.run/(case['meeting']+'-raw.json'),packet)
     assert not semantic_error and not was_truncated,'Incomplete native result retained; no retry or shortened re-run'
     assert result.raw_text and result.segments
     state['completed'].append({'meeting':case['meeting'],'seconds':packet['seconds'],'segments':len(result.segments),
      'tokens':len(result.tokens),'wasTruncated':was_truncated,'sourceAudioComplete':packet['sourceAudioComplete']});save()
     del samples,result;gc.collect()
    state.update(state='COMPLETE_CPP_JOINT_FOUR_WHOLE_MEETING_OUTPUTS_SCORING_PENDING')
 except BaseException as error:state.update(state='FAILED_CPP_JOINT_'+a.phase.upper()+'_RETAINED_NO_RETRY',error=repr(error));raise
 finally:
  stop_monitor.set();state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began);save();dll_scope.close()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
