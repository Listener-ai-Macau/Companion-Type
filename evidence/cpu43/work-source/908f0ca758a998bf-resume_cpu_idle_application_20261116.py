"""Preserve prior accepted first block; test idle/reload while finishing only the tail."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess,sys,time,psutil
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession,read_json,atomic_json,exclusive_file
from practical_io_20261107 import stop_owned_family
from moss_windows_resource_limits_20261104 import SystemRamPressure
import run_cpu_application_schema_20261116 as app
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');root=E/'cpu-idle-app-r3';out=root/'resume-r1';assert not out.exists();out.mkdir();stream=root/'stream';session=PcmSession(stream/'session');F=E/'cpu-internal-app-fixture-r5'
read=read_json
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert read(root/'run.json')['state']=='INCOMPLETE_CPU_IDLE_APP_TEST_RETAINED_NO_AUTOMATIC_RETRY'
assert session.state()['confirmedFrames']==480000 and (stream/'audio.pcm').stat().st_size==960000
before={p.name:sha(p) for p in (session.root/'results').glob('*.json')};assert len(before)>=1 and any(read(p)['request']['blockFinal'] for p in (session.root/'results').glob('*.json'))
original_workers={str(p) for p in stream.glob('decoder-run-*/worker-state.json')};old_states=[read(p) for p in stream.glob('decoder-run-*/worker-state.json')];assert any(x.get('idleModelReleases',0)>=1 for x in old_states)
case=read(root/'protocol.json')['source'];wav=root/'public75.wav'
with __import__('wave').open(str(wav),'rb') as f:pcm=f.readframes(f.getnframes())
assert len(pcm)//2==case['testFrames'] and hashlib.sha256(pcm).hexdigest()==case['pcmSha256']
app.package=read(F/'package.json');bundle=root/'bundle.json';manifest=root/'stream-manifest.json';preview=stream/'preview.json';pressure=SystemRamPressure();child=owned=None
state={'state':'WAITING_ORIGINAL_MEMORY_GATE_STABLE60','startedAt':datetime.now().astimezone().isoformat(),'priorAcceptedFiles':before,'priorHarnessFailureRetained':True,'qualityQualified':False}
def save():atomic_json(out/'run.json',state)
def deadline():assert datetime.now().astimezone()<datetime.fromisoformat('2026-11-16T15:40:00+08:00')
save();stable=None
try:
 while True:
  deadline();healthy=not pressure.low() and psutil.virtual_memory().available>=int(3.18*1024**3)
  stable=time.monotonic() if healthy and stable is None else (stable if healthy else None)
  if stable is not None and time.monotonic()-stable>=60:break
  time.sleep(1)
 tick=time.monotonic();state['state']='RESUMING_ACCEPTED_PREFIX_AND_TESTING_SECOND_BLOCK_IDLE_RELEASE';save()
 with (out/'stream.stdout.log').open('xb') as output,(out/'stream.stderr.log').open('xb') as errors:
  child=subprocess.Popen(app.command(manifest,bundle),stdout=output,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);owned=psutil.Process(child.pid)
  with (stream/'audio.pcm').open('ab',buffering=0) as f:f.write(pcm[480000*2:960000*2]);os.fsync(f.fileno())
  idle=None
  while child.poll() is None:
   deadline();assert time.monotonic()-tick<210
   if preview.exists():assert not read(preview).get('error')
   for path in stream.glob('decoder-run-*/worker-state.json'):
    if str(path) in original_workers:continue
    value=read(path)
    if value.get('idleModelReleases',0)>=1 and value.get('modelLoaded') is False:
     idle=value;worker_file=path;break
   if idle is not None:break
   time.sleep(.1)
  assert idle is not None and child.poll() is None and session.state()['confirmedFrames']==960000
  for name,digest in before.items():assert sha(session.root/'results'/name)==digest
  release=idle['lastIdleRelease'];assert release['beforeWorkingSetBytes']-release['afterWorkingSetBytes']>=512*1024**2
  decoder=read(worker_file.parent/'run.json');worker=psutil.Process(idle['limits']['pid']);assert worker.pid==decoder['pid'] or decoder['pid'] in [p.pid for p in worker.parents()]
  model_name=Path(read(F/'controls/pcm/binding.json')['model']['file']).name.lower();assert not [x for x in worker.memory_maps(grouped=True) if Path(x.path).name.lower()==model_name]
  pause_cache={p.name:sha(p) for p in (session.root/'results').glob('*.json')};memory=worker.memory_info();time.sleep(2);assert pause_cache=={p.name:sha(p) for p in (session.root/'results').glob('*.json')}
  atomic_json(out/'idle-observation.json',{'release':release,'actualIdleWorkerRssBytes':memory.rss,'actualIdleWorkerPrivateBytes':memory.private,'modelWeightMappingAbsent':True,'acceptedResultsUnchangedWhilePaused':True,'confirmedFrames':960000})
  with (stream/'audio.pcm').open('ab',buffering=0) as f:f.write(pcm[960000*2:]);os.fsync(f.fileno())
  atomic_json(stream/'sealed.json',{'frames':case['testFrames']})
  while child.poll() is None:
   deadline();assert time.monotonic()-tick<360
   if preview.exists():assert not read(preview).get('error')
   time.sleep(.1)
 assert child.returncode==0 and session.document()['isFinal'] and sha(session.audio)==case['pcmSha256']
 for name,digest in pause_cache.items():assert sha(session.root/'results'/name)==digest
 final_worker=read(worker_file);assert final_worker['modelLoads']==2 and final_worker['idleModelReleases']>=1
 assert not any(x['block']==0 for x in final_worker['completed']),'The previously accepted first30s block must not be redecoded'
 previous=read(E/'cpu-app-schema-test-r3/ES2003b/stream-final-call/stdout.json');assert session.document()['text']==previous['text']
 cached={p.name:sha(p) for p in (session.root/'results').glob('*.json')};final_manifest=out/'final-manifest.json'
 atomic_json(final_manifest,{'schema':'companion.local-meeting-input.v1','localOnly':True,'finalize':True,'language':'auto','files':[{'path':str(wav),'sha256':sha(wav),'pcmBytes':len(pcm)}],'ownedStreamRoots':[str(stream)]})
 with exclusive_file(stream/'stream.lock'):final_doc,seconds=app.closed_call(out/'final-call',final_manifest,bundle)
 assert final_doc['text']==session.document()['text'] and cached=={p.name:sha(p) for p in (session.root/'results').glob('*.json')}
 jobs=list((root/'final-jobs').glob('*'));assert len(jobs)==1;job=read(jobs[0]/'job.json');assert job['adoptedCompatibleStreamCache'] and [x['stage'] for x in job['attempts']]==['cpu-speaker']
 again,reload_seconds=app.closed_call(out/'reopen-call',final_manifest,bundle);assert again==final_doc and read(jobs[0]/'job.json')['attempts']==job['attempts']
 result={'state':'PASS_ACTUAL_CPU_IDLE_MODEL_UNLOAD_RELOAD_SOURCE_AND_CACHE_RECOVERY_TEXT_NO_REGRESSION_NOT_QUALITY_QUALIFIED','at':datetime.now().astimezone().isoformat(),
  'sourceFrames':case['testFrames'],'idleRelease':release,'idleWorkerRssBytes':memory.rss,'idleWorkerPrivateBytes':memory.private,'modelWeightMappingAbsentDuringPause':True,
  'resumedWorkerModelLoads':2,'priorAcceptedFirst30sNotRedecoded':True,'priorAndNewAcceptedCachesPreservedExactly':True,'allOriginalPcmPreserved':True,
  'finalTextEqualsPreviousProtectedCpuAppRun':True,'finalizationReusedAllAsrResults':True,'finalizationAfterCachedAsrSeconds':seconds,'completedCacheReloadSeconds':reload_seconds,
  'actualCpuSpeakerJournalApplied':True,'nativeUiTested':False,'cardHardwareTested':False,'newModelTraining':False,'sourceUploaded':False,'qualityQualified':False,'productDefaultChanged':False}
 atomic_json(out/'result.json',result);state['state']=result['state'];print(json.dumps(result,ensure_ascii=False))
except BaseException as error:state.update(state='INCOMPLETE_CPU_IDLE_RESUME_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));raise
finally:
 if child is not None and child.poll() is None:stop_owned_family(child,owned)
 pressure.close();state['finishedAt']=datetime.now().astimezone().isoformat();save()
