"""Actual native live hub, source-preserving finalization and privacy actions.

Isolated library, fixed public technical PCM; no microphone, board, foreground
window or cloud provider. The native/model children keep their original bounds.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,msvcrt,os,shutil,subprocess,sys,time
import psutil
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import SystemRamPressure
from practical_io_20261107 import stop_owned_family
from companion_windows_power_request_20261115 import PowerLease
E=Path('E:/CodexData/Companion/product-d1d2-20261114');OUT=E/'app-candidate-r5';P=OUT/'profile';Q=OUT/'qa/live-resume-privacy-r2'
assert not Q.exists();Q.mkdir()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
binary=OUT/'companion-type.exe';assert sha(binary)==read(OUT/'source-binding.json')['binarySha256']
sid=read(OUT/'qa/import-receipt.json')['sessionId']
sample=Path('E:/CodexData/Companion/.model-cache/local-bilingual-20261114/public-probe90.wav');source_sha=sha(sample)
env={**os.environ,'COMPANION_TYPE_STATE_PATH':str(P/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(P/'recordings'),
 'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(P/'settings.json'),'COMPANION_TYPE_LOCAL_MEETING_CONFIG':str(E/'local-package-r8/package.json'),
 'COMPANION_TYPE_ASR_PROVIDER':'local-meeting','COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED':'0',
 'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1',
 'COMPANION_LOCAL_PUBLIC_PROBE_OWNER':sid,'COMPANION_LOCAL_PUBLIC_PROBE_RESULT':str(Q/'actual-live-hub.json')}
for key in ['COMPANION_TYPE_TRANSCRIPT_TEXT','COMPANION_TYPE_ASR_COMMAND','COMPANION_TYPE_LIVE_ASR_MOCK','COMPANION_TYPE_LIVE_ASR_OFF',
            'COMPANION_LOCAL_ARTIFACT_ROOT','COMPANION_LOCAL_ARTIFACT_ROOTS','PYTHONPATH']:
 env.pop(key,None)
assert not read(E/'local-package-r8/bundle.json')['completedPcmCaches']
assert not read(E/'local-package-r8/bundle.json')['completedSpeakerCaches']
state={'state':'STARTING_ACTUAL_NATIVE_LIVE_RESUME_PRIVACY','startedAt':now(),'sessionId':sid,'steps':[],
 'privateInputUsed':False,'sourceUploaded':False,'cloudTextOrMinutesRequested':False,'qualityQualified':False}
save=lambda:(Q/'run.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def run(name,args,*,timeout=600):
 child=owned=None;pressure=SystemRamPressure();began=time.monotonic();peak=0
 state.update(state='RUNNING_'+name.upper());save()
 try:
  assert not pressure.low()
  with (Q/(name+'.log')).open('xb') as log:
   child=subprocess.Popen([str(x) for x in args],env=env,stdout=log,stderr=subprocess.STDOUT,
       creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   owned=psutil.Process(child.pid);state.update(activePid=child.pid,activeCreatedAt=owned.create_time());save()
   while child.poll() is None:
    if pressure.low() or (Q/'stop.request').exists() or time.monotonic()-began>timeout:
     stop_owned_family(child,owned);raise InterruptedError('Actual resource/owned stop/deadline; source and completed progress retained')
    try:
     memory=sum(p.memory_info().private for p in [owned]+owned.children(recursive=True));peak=max(peak,memory)
     if memory>2*1024**3:stop_owned_family(child,owned);raise MemoryError('Actual model family reached unchanged2GiB bound')
    except psutil.Error:pass
    time.sleep(.5)
  return child.returncode
 finally:
  if child is not None and child.poll() is None:stop_owned_family(child,owned)
  pressure.close();state.pop('activePid',None);state.pop('activeCreatedAt',None)
  state['steps'].append({'step':name,'exitCode':child.returncode if child else None,'seconds':time.monotonic()-began,'privatePeakBytes':peak});save()

def call(name,flag,payload,*,timeout=600,success=True):
 request=Q/(name+'-input.json');target=Q/(name+'-result.json');request.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
 code=run(name,[binary,flag,request,target],timeout=timeout)
 if success:assert code==0,'Actual native '+name+' failed; evidence retained'
 return read(target) if target.exists() else None,code

with PowerLease():
 try:
  prior=OUT/'qa/live-resume-privacy-r1'
  live=read(prior/'actual-live-hub.json')
  assert live['state']=='PASS_ACTUAL_NATIVE_LIVE_HUB_PACED90_SOURCE_AND_DRAFT_LEASE_RELEASED'
  stream=Path(live['streamRoot'])
  assert (stream/'audio.pcm').stat().st_size==90*16000*2
  other=read(prior/'import-other-result.json')
  other_row=next(r for r in other['host']['sessions'] if r['id']!=sid);other_id=other_row['id']
  other_original=Path(other_row['audioPath']);other_sha=sha(other_original)
  state['retainedActualNativeLiveProbe']=str(prior/'actual-live-hub.json')
  state['repeatNativeLiveInference']=False
  finalized,_=call('finalize','--meeting-transcribe-request',{'sessionId':sid},timeout=900)
  assert finalized.get('operationError') is None
  row=next(r for r in finalized['snapshot']['host']['sessions'] if r['id']==sid)
  assert row['transcriptFinal'] and row['utterances'] and row['transcriptText']
  original_path=Path(row['audioPath']);original_sha=sha(original_path)
  cache=P/'recordings/.asr-chunk-cache/local-meeting';journal=read(cache/'.local-meeting-owners.json')
  entries=[r for r in journal['entries'] if r['owner']==sid]
  complete=next(r for r in entries if r['key'].startswith('complete-') and (cache/r['id']/'final-document.json').exists());work=cache/complete['id']
  job=read(work/'job.json');assert job['adoptedCompletedAsrCache'] is False
  assert Path(job['asrSession'])==stream/'session'
  assert read(work/'stream-cache-lineage.json')['immutableRequestsRewritten'] is False
  assert sha(Path(job['asrSession'])/'audio.pcm')==sha(stream/'audio.pcm')
  state['finalization']={'characters':len(row['transcriptText']),'utterances':len(row['utterances']),
      'stream':live,'privateJobRoot':str(work),'noStaticPublicAsrCacheUsed':True,
      'nativeSourceSha256':original_sha,'ownedCacheDirectories':len(entries)};save()
  # Keep only explicit technical-test evidence outside managed private caches.
  for path in [work/'job.json',work/'input-binding.json',work/'final-binding.json',Path(job['asrSession'])/'document.json']:
   if path.exists():shutil.copyfile(path,Q/('retained-'+path.name))
  with (cache/('.job-'+complete['id']+'.lock')).open('r+b') as busy:
   busy.seek(0);msvcrt.locking(busy.fileno(),msvcrt.LK_LOCK,1)
   try:failed,code=call('busy-clear','--library-control-request',{'action':'privacyEraseTranscript','sessionId':sid},success=False)
   finally:busy.seek(0);msvcrt.locking(busy.fileno(),msvcrt.LK_UNLCK,1)
  assert code!=0,'Busy cache must refuse successful erasure'
  snapshot,_=call('after-busy','--local-recording-snapshot',{})
  current=next(r for r in snapshot['snapshot']['host']['sessions'] if r['id']==sid)
  assert current['transcriptText']==row['transcriptText'] and sha(original_path)==original_sha
  cleared,_=call('clear-transcript','--library-control-request',{'action':'privacyEraseTranscript','sessionId':sid})
  current=next(r for r in cleared['host']['sessions'] if r['id']==sid)
  assert not current['transcriptText'] and current['audioStored'] and sha(original_path)==original_sha
  assert all(not (cache/e['id']).exists() for e in entries)
  assert not any(e['owner']==sid for e in read(cache/'.local-meeting-owners.json')['entries'])
  assert sha(other_original)==other_sha
  deleted,_=call('delete-session','--library-control-request',{'action':'privacyDeleteSession','sessionId':sid})
  assert not any(r['id']==sid for r in deleted['host']['sessions']) and not original_path.exists()
  assert any(r['id']==other_id for r in deleted['host']['sessions']) and sha(other_original)==other_sha
  assert sha(sample)==source_sha
  state.update(state='PASS_NATIVE_LIVE_STOP_FINALIZE_OWNED_CACHE_PRIVACY_AND_OTHER_MEETING_PRESERVED',
    managedModelCachesDeleted=True,busyCachePreservedTranscriptAndSource=True,selectedAudioPreservedOnTranscriptClear=True,
    otherMeetingPreserved=True,originalPublicInputUnchanged=True)
 except BaseException as error:
  state.update(state='INCOMPLETE_ACTUAL_NATIVE_FLOW_RETAINED',error=repr(error));raise
 finally:state.update(finishedAt=now());save()
print(json.dumps(state,ensure_ascii=False))
