"""One full large-v3 F16 English reference, explicit780M; no training/grid."""
from pathlib import Path
from datetime import datetime
import argparse,ctypes,dataclasses,gc,hashlib,json,os,sys,threading,time,traceback,wave
os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='4',TRANSCRIBE_NO_REPETITION_GUARD='1')
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate,SystemRamPressure
from durable_model_state_20261117 import atomic_json
from companion_local_pcm_session_20261114 import exclusive_file
from cpu_window_joint_worker_20261116 import finite
import psutil
parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,default=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/english-full-base-r1'));args=parser.parse_args();C=args.control
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(C/'protocol.json');out=C/'run';out.mkdir(exist_ok=False)
limits=WorkerLimits(cpu_percent=5,memory_bytes=P['privateLimitBytes']);rate=CpuRate(5,2500)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
pressure=SystemRamPressure();tick=time.monotonic();closing=threading.Event();active=None
state={'state':'PREPARING_FULL_WHISPER_780M_REFERENCE','pid':os.getpid(),'createdAt':psutil.Process().create_time(),
 'startedAt':datetime.now().astimezone().isoformat(),'protocolSha256':sha(C/'protocol.json'),
 'completed':[],'newTrainingUpdates':0,'referenceRead':False,'qualityQualified':False,'saleQualified':False}
mutex=threading.RLock()
def save(**values):
 with mutex:
  state.update(values,observedAt=datetime.now().astimezone().isoformat(),limits=limits.query())
  atomic_json(out/'state.json',state,progress=True)
def reason():
 if (C/'stop.request').exists():return 'Owned stop request'
 if datetime.now().astimezone()>=datetime.fromisoformat(P['stopAt']):return 'Bounded25min cutoff'
 if pressure.low() or psutil.virtual_memory().available<P['minimumAvailableBytes']:return 'Original realRAM floor'
 if psutil.Process().memory_info().private>P['privateLimitBytes']:return 'Original2GiB private-memory budget'
 return None
def watch():
 while not closing.wait(.5):
  why=reason()
  if why:
   atomic_json(out/'stop-observed.json',{'at':datetime.now().astimezone().isoformat(),'reason':why,'state':state,'limits':limits.query()})
   if active is not None:
    active.cancel()
    if closing.wait(5):return
   # This task owns this process/job only; never touch another application.
   os._exit(76)
  if int(time.monotonic()-tick)%5==0:save()
try:
 with exclusive_file(Path('E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock')):
  save();assert sha(__file__)==P['workerSha256'];assert sha(P['model'])==P['modelSha256']
  for name,digest in P['nativeFiles'].items():assert sha(Path(P['library']).parent/name)==digest
  for item in P['pythonFiles']:assert sha(item['file'])==item['sha256']
  start=time.monotonic()
  while time.monotonic()-start<60:
   why=reason();assert why is None,why;time.sleep(1)
  scope=os.add_dll_directory(str(Path(P['library']).parent));os.environ['TRANSCRIBE_LIBRARY']=P['library'];sys.path.insert(0,P['pythonRoot'])
  import numpy as np,transcribe_cpp as cpp
  assert cpp.native_version()=='0.4.2' and cpp.native_commit().startswith('275cd50')
  def log(level,message):
   with mutex:
    with (out/'native.log').open('a',encoding='utf-8') as f:f.write(str(level)+' '+message)
  cpp.set_log_callback(log)
  backend=P.get('executionBackend','vulkan')
  inventory=cpp.backends()
  matches=[d for d in inventory if d.kind=='cpu'] if backend=='cpu' else [d for d in inventory if d.kind=='vulkan' and 'radeon780mgraphics' in ''.join(d.description.lower().split())]
  assert len(matches)==1,'Unique explicitly requested device required; no automatic fallback'
  selected=matches[0]
  save(state='LOADING_FULL_WHISPER_F16_EXPLICIT_'+backend.upper(),device=dataclasses.asdict(selected),nativeCommit=cpp.native_commit())
  threading.Thread(target=watch,daemon=True).start()
  with cpp.Model(P['model'],backend=backend,device=selected,no_mmap=False) as model:
   assert model.device==selected and model.device.kind==backend and 'whisper' in model.arch.lower()
   save(state='FULL_WHISPER_EXPLICIT_DEVICE_READY',modelArch=model.arch,actualDevice=dataclasses.asdict(model.device))
   for case in P['cases']:
    assert reason() is None,reason();assert sha(case['wav'])==case['wavSha256']
    with wave.open(case['wav'],'rb') as f:
     assert (f.getnchannels(),f.getsampwidth(),f.getframerate(),f.getnframes())==(1,2,16000,case['frames'])
     pcm=f.readframes(f.getnframes())
    assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256']
    samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768;began=time.perf_counter()
    save(state='DECODING_FIXED_ENGLISH_FULL_BASE',activeCase=case['id'])
    with model.session(n_threads=4) as session:
     active=session
     result=session.run(samples,**P['settings'])
     truncated=bool(cpp._lib.transcribe_was_truncated(session._h));active=None
    packet={'case':case,'seconds':time.perf_counter()-began,'backend':model.backend,'device':model.device.description,
     'modelSha256':P['modelSha256'],'nativeVersion':cpp.native_version(),'nativeCommit':cpp.native_commit(),
     'result':finite(dataclasses.asdict(result)),'rawDecoded':result.raw_text,'hypothesis':result.text,
     'naturalEos':not truncated,'wasTruncated':truncated,'originalClipComplete':True,
     'referenceRead':False,'wordsRewritten':False,'newWeightTraining':False,'qualityQualified':False}
    file=out/(case['id']+'-raw.json');atomic_json(file,packet)
    assert packet['naturalEos'] and result.text,'Incomplete native output; no changed-parameter retry'
    state['completed'].append({'id':case['id'],'file':str(file),'sha256':sha(file),'seconds':packet['seconds']});save()
    del result,samples,pcm;gc.collect()
   save(state='COMPLETE_FULL_BASE_12_CLIPS_PENDING_INDEPENDENT_SCORE')
  scope.close()
except BaseException as error:
 state.update(state='FAILED_FULL_BASE_REFERENCE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
 active=None;closing.set();pressure.close();save(finishedAt=datetime.now().astimezone().isoformat(),wholeWorkerSeconds=time.monotonic()-tick)
 atomic_json(out/'completed.json',state)
 print(json.dumps({k:v for k,v in state.items() if k!='completed'},ensure_ascii=False),flush=True)
