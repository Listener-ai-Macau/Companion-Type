"""One real public stream: draft, pause until model unload, resume, cached final."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess,sys,time,uuid,wave,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession,atomic_json,exclusive_file,read_json
from practical_io_20261107 import stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
import run_cpu_application_schema_20261116 as app
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
F=E/'cpu-internal-app-fixture-r5';root=E/'cpu-idle-app-r3';assert not root.exists();root.mkdir()
read=read_json
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
state={'state':'WAITING_EXISTING_CLASSIFIER_FAMILY_TO_CLOSE','startedAt':datetime.now().astimezone().isoformat(),'qualityQualified':False,'automaticRetries':0};pressure=SystemRamPressure();child=owned=None
def save():atomic_json(root/'run.json',state)
def deadline():assert datetime.now().astimezone()<datetime.fromisoformat('2026-11-16T15:40:00+08:00')
save()
try:
 while True:
  deadline();preceding=read(B/'cpu-retained-baseline-alignment-r2/run.json')
  if preceding.get('finishedAt'):
   assert preceding['state']=='COMPLETE_RETAINED_NATIVE_ASR_CPU_ALIGNMENT_VOICES_FULL_RECORDING_CHARACTERIZATION_NOT_QUALIFIED';break
  time.sleep(1)
 state['state']='WAITING_ORIGINAL_318GIB_MEMORY_GATE_STABLE60';save();stable=None
 while True:
  deadline();healthy=not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
  stable=time.monotonic() if healthy and stable is None else (stable if healthy else None)
  if stable is not None and time.monotonic()-stable>=60:break
  time.sleep(1)
 app.package=read(F/'package.json');package=app.package;assert sha(package['entryScript'])==package['entryScriptSha256']
 protocol=read(B/'cpu-pcm-candidate-r2/dualroute-protocol.json');case=next(x for x in protocol['cases'] if x['meeting']=='ES2003b')
 assert sha(case['audio'])==case['audioSha256']
 with wave.open(case['audio'],'rb') as f:pcm=f.readframes(case['testFrames'])
 assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256'];wav=root/'public75.wav'
 with wave.open(str(wav),'wb') as f:f.setparams((1,2,16000,0,'NONE','not compressed'));f.writeframes(pcm)
 stream=root/'stream';stream.mkdir();raw=stream/'audio.pcm';raw.touch();preview=stream/'preview.json';recording=str(uuid.uuid4());base=read(F/'bundle.json')
 bundle=root/'bundle.json';atomic_json(bundle,{**base,'workRoot':str(root/'final-jobs'),'streamRoot':str(root/'streams')})
 manifest=root/'stream-manifest.json';atomic_json(manifest,{'schema':'companion.local-meeting-stream.v1','localOnly':True,'language':'auto','sessionPath':str(stream/'session'),'pcmPath':str(raw),'statusPath':str(preview),'recordingId':recording})
 atomic_json(root/'protocol.json',{'at':datetime.now().astimezone().isoformat(),'scriptSha256':sha(__file__),'packageSha256':sha(F/'package.json'),
  'idlePolicy':read(B/'cpu-pcm-candidate-r6/idle-policy-protocol.json'),'source':case,'pauseAfterSourceFrames':480000,'acceptedCacheKind':'first completed30s block',
  'prior5sDraftPauseProof':str(E/'cpu-idle-app-r2/idle-observation.json'),'priorDriverFailure':'Transient Windows preview-reader denial; bounded read retry is now independently verified. Prior accepted draft retained without rewrite.',
  'localPublicInputOnly':True,'nativeUiTested':False,'qualityQualified':False})
 tick=time.monotonic();state['state']='RUNNING_ACTUAL_BACKEND_DRAFT_PAUSE_UNLOAD_RESUME';save()
 with (root/'stream.stdout.log').open('xb') as output,(root/'stream.stderr.log').open('xb') as errors:
  child=subprocess.Popen(app.command(manifest,bundle),stdout=output,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);owned=psutil.Process(child.pid)
  with raw.open('ab',buffering=0) as f:f.write(pcm[:480000*2]);os.fsync(f.fileno())
  first=None;idle=None;worker_pid=None
  while child.poll() is None:
   deadline();assert time.monotonic()-tick<180
   if preview.exists():
    value=read(preview);assert not value.get('error'),value
    if value['text'].strip() and first is None:first=time.monotonic()-tick
   for path in stream.glob('decoder-run-*/worker-state.json'):
    result=read(path)
    if result.get('idleModelReleases',0)>=1 and result.get('modelLoaded') is False:
     idle=result;decoder=read(path.parent/'run.json');worker_pid=result['limits']['pid'];break
   if idle is not None:break
   time.sleep(.1)
  assert child.poll() is None and first is not None and idle is not None
  release=idle['lastIdleRelease'];assert release['beforeWorkingSetBytes']-release['afterWorkingSetBytes']>=512*1024**2
  session=PcmSession(stream/'session');before={p.name:sha(p) for p in (session.root/'results').glob('*.json')};assert len(before)==1
  worker=psutil.Process(worker_pid);assert worker.pid==decoder['pid'] or decoder['pid'] in [x.pid for x in worker.parents()]
  assert 0<=worker.create_time()-decoder['pidCreatedAt']<10
  weight_name=Path(read(F/'controls/pcm/binding.json')['model']['file']).name.lower();mapped=[m.path for m in worker.memory_maps(grouped=True) if Path(m.path).name.lower()==weight_name]
  assert mapped==[],'Idle native model weight mapping must be gone, rather than just relabeling state'
  idle_sample=worker.memory_info();time.sleep(2);assert before=={p.name:sha(p) for p in (session.root/'results').glob('*.json')}
  atomic_json(root/'idle-observation.json',{'release':release,'actualIdleWorkerRssBytes':idle_sample.rss,'actualIdleWorkerPrivateBytes':idle_sample.private,
   'modelWeightMappingAbsent':True,'acceptedResultsUnchangedWhilePaused':True,'confirmedFrames':session.state()['confirmedFrames'],'firstTextSeconds':first})
  with raw.open('ab',buffering=0) as f:f.write(pcm[480000*2:]);os.fsync(f.fileno())
  atomic_json(stream/'sealed.json',{'frames':case['testFrames']})
  while child.poll() is None:
   deadline();assert time.monotonic()-tick<360
   if preview.exists():assert not read(preview).get('error')
   time.sleep(.1)
 assert child.returncode==0
 session=PcmSession(stream/'session');document=session.document();assert document['isFinal'] and sha(session.audio)==case['pcmSha256']
 for name,digest in before.items():assert sha(session.root/'results'/name)==digest
 worker_states=[read(p) for p in stream.glob('decoder-run-*/worker-state.json')];assert len(worker_states)==1 and worker_states[0]['modelLoads']==2 and worker_states[0]['idleModelReleases']>=1
 previous=read(E/'cpu-app-schema-test-r3/ES2003b/stream-final-call/stdout.json');assert document['text']==previous['text']
 cached={p.name:sha(p) for p in (session.root/'results').glob('*.json')};final_manifest=root/'final-manifest.json'
 atomic_json(final_manifest,{'schema':'companion.local-meeting-input.v1','localOnly':True,'finalize':True,'language':'auto','files':[{'path':str(wav),'sha256':sha(wav),'pcmBytes':len(pcm)}],'ownedStreamRoots':[str(stream)]})
 with exclusive_file(stream/'stream.lock'):final_doc,seconds=app.closed_call(root/'final-call',final_manifest,bundle)
 assert final_doc['text']==document['text'] and cached=={p.name:sha(p) for p in (session.root/'results').glob('*.json')}
 jobs=list((root/'final-jobs').glob('*'));assert len(jobs)==1;job=read(jobs[0]/'job.json');assert job['adoptedCompatibleStreamCache'] and [x['stage'] for x in job['attempts']]==['cpu-speaker']
 again,reload_seconds=app.closed_call(root/'reopen-call',final_manifest,bundle);assert again==final_doc and read(jobs[0]/'job.json')['attempts']==job['attempts']
 result={'state':'PASS_ACTUAL_CPU_IDLE_MODEL_RELEASE_AND_RESUME_FINAL_CACHE_TEXT_NO_REGRESSION_NOT_QUALITY_QUALIFIED','at':datetime.now().astimezone().isoformat(),
  'sourceFrames':case['testFrames'],'firstTextSeconds':first,'idleRelease':release,'idleWorkerRssBytes':idle_sample.rss,'idleWorkerPrivateBytes':idle_sample.private,
  'modelWeightMappingAbsentDuringPause':True,'modelLoads':2,'acceptedFirstFinalBlockPreservedExactly':True,'allOriginalPcmPreserved':True,'finalTextEqualsPreviousProtectedCpuAppRun':True,
  'finalizationReusedAllAsrResults':True,'finalizationAfterCachedAsrSeconds':seconds,'completedCacheReloadSeconds':reload_seconds,'actualCpuSpeakerJournalApplied':True,
  'nativeUiTested':False,'cardHardwareTested':False,'newModelTraining':False,'sourceUploaded':False,'qualityQualified':False,'productDefaultChanged':False}
 atomic_json(root/'result.json',result);state['state']=result['state'];print(json.dumps(result,ensure_ascii=False))
except BaseException as error:state.update(state='INCOMPLETE_CPU_IDLE_APP_TEST_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
finally:
 if child is not None and child.poll() is None:stop_owned_family(child,owned)
 pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
