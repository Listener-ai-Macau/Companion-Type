"""Actual existing app JSON schemas through the frozen internal CPU command entry."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,subprocess,sys,threading,time,traceback,uuid,wave,psutil
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession,atomic_json,exclusive_file
from practical_io_20261107 import stop_owned_family
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1');F=E/'cpu-internal-app-fixture-r1'
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/cpu-pcm-candidate-r2')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
package=None
def command(manifest,bundle):return [package['program'],'-u',package['entryScript'],'--manifest',str(manifest),'--bundle',str(bundle)]
def closed_call(folder,manifest,bundle):
 folder.mkdir();tick=time.monotonic();child=owned=None
 try:
  with (folder/'stdout.json').open('xb') as output,(folder/'stderr.log').open('xb') as errors:
   child=subprocess.Popen(command(manifest,bundle),stdout=output,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);owned=psutil.Process(child.pid)
   while child.poll() is None:
    if time.monotonic()-tick>300:raise TimeoutError('Fixed75s application entry budget')
    time.sleep(.25)
  assert child.returncode==0,(child.returncode,str(folder/'stderr.log'));return read(folder/'stdout.json'),time.monotonic()-tick
 finally:
  if child is not None and child.poll() is None:stop_owned_family(child,owned)
def main():
 global F,package
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--fixture',type=Path,default=F);args=parser.parse_args();F=args.fixture
 package=read(F/'package.json');assert sha(package['program'])==package['programSha256'] and sha(package['entryScript'])==package['entryScriptSha256']
 root=args.root;assert not root.exists();root.mkdir()
 protocol=read(C/'dualroute-protocol.json');rows=[]
 atomic_json(root/'protocol.json',{'at':datetime.now().astimezone().isoformat(),'scriptSha256':sha(__file__),'packageSha256':sha(F/'package.json'),
  'cases':protocol['cases'],'scope':'Direct versioned backend command schemas, not installed native UI/card/phone testing. Model is rejected for quality; no release/default promotion.',
  'sequence':['fresh offline ASR+CPU speaker finalization','paced growing-file app stream','finalize using unchanged accepted stream ASR cache','reload identical completed final cache without new neural stage'],
  'qualityQualified':False,'newWeightTraining':False,'productDefaultChanged':False})
 for case in protocol['cases']:
  folder=root/case['meeting'];folder.mkdir();assert sha(case['audio'])==case['audioSha256']
  with wave.open(case['audio'],'rb') as source:pcm=source.readframes(case['testFrames'])
  assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256'];wav=folder/'public75.wav'
  with wave.open(str(wav),'wb') as output:output.setparams((1,2,16000,0,'NONE','not compressed'));output.writeframes(pcm)
  base=read(F/'bundle.json');offline_bundle=folder/'offline-bundle.json';offline={**base,'workRoot':str(folder/'offline-jobs')};atomic_json(offline_bundle,offline)
  files=[{'path':str(wav),'sha256':sha(wav),'pcmBytes':len(pcm)}]
  offline_manifest=folder/'offline-manifest.json';atomic_json(offline_manifest,{'schema':'companion.local-meeting-input.v1','localOnly':True,'finalize':True,'language':'auto','files':files,'ownedStreamRoots':[]})
  offline_doc,offline_seconds=closed_call(folder/'offline-call',offline_manifest,offline_bundle)
  stream=folder/'stream';stream.mkdir();raw=stream/'audio.pcm';raw.touch();status=stream/'preview.json';recording=str(uuid.uuid4())
  stream_bundle=folder/'stream-bundle.json';atomic_json(stream_bundle,{**base,'workRoot':str(folder/'stream-final-jobs'),'streamRoot':str(folder/'streams')})
  live_manifest=folder/'stream-manifest.json';atomic_json(live_manifest,{'schema':'companion.local-meeting-stream.v1','localOnly':True,'language':'auto','sessionPath':str(stream/'session'),
   'pcmPath':str(raw),'statusPath':str(status),'recordingId':recording})
  stop=threading.Event();producer_errors=[];tick=time.monotonic();first=None;sealed=None;events=[]
  def produce():
   nonlocal sealed
   try:
    with raw.open('ab',buffering=0) as output:
     for start in range(0,len(pcm)//2,80000):
      end=min(start+80000,len(pcm)//2)
      while time.monotonic()-tick<end/16000:
       if stop.wait(.02):return
      output.write(pcm[start*2:end*2]);os.fsync(output.fileno());events.append({'seconds':time.monotonic()-tick,'event':'source_pcm','endFrame':end})
    atomic_json(stream/'sealed.json',{'frames':len(pcm)//2});sealed=time.monotonic()-tick
   except BaseException as error:producer_errors.append({'error':repr(error),'traceback':traceback.format_exc()})
  producer=threading.Thread(target=produce,daemon=True);child=owned=None
  try:
   with (stream/'stdout.log').open('xb') as output,(stream/'stderr.log').open('xb') as errors:
    child=subprocess.Popen(command(live_manifest,stream_bundle),stdout=output,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);owned=psutil.Process(child.pid);producer.start()
    while child.poll() is None:
     if producer_errors:raise RuntimeError(str(producer_errors))
     if time.monotonic()-tick>315:raise TimeoutError('Bounded paced stream test')
     if status.exists():
      value=read(status)
      if value['text'].strip() and first is None:first=time.monotonic()-tick
      if value.get('error'):raise RuntimeError(value['error'])
     time.sleep(.1)
   producer.join(timeout=1);assert child.returncode==0 and not producer_errors,(child.returncode,producer_errors)
   assert first is not None and sealed is not None and first<sealed
   session=PcmSession(stream/'session');assert session.document()['isFinal'] and sha(session.audio)==case['pcmSha256']
   cached={p.name:sha(p) for p in (session.root/'results').glob('*.json')}
   final_manifest=folder/'stream-final-manifest.json';atomic_json(final_manifest,{'schema':'companion.local-meeting-input.v1','localOnly':True,'finalize':True,'language':'auto','files':files,'ownedStreamRoots':[str(stream)]})
   with exclusive_file(stream/'stream.lock'):final_doc,final_seconds=closed_call(folder/'stream-final-call',final_manifest,stream_bundle)
   assert cached=={p.name:sha(p) for p in (session.root/'results').glob('*.json')},'Accepted incremental results must not be rewritten/redecoded'
   jobdirs=list((folder/'stream-final-jobs').glob('*'));assert len(jobdirs)==1;job=jobdirs[0];state=read(job/'job.json')
   assert state['adoptedCompatibleStreamCache'] and [r['stage'] for r in state['attempts']]==['cpu-speaker']
   assert final_doc['text']==offline_doc['text']==session.document()['text'] and ''.join(r['text'] for r in final_doc['utterances'])==final_doc['text']
   assert final_doc['isFinal'] and final_doc['speakerJournalApplied'] and final_doc['reviewRequired'] and not final_doc['qualityQualified']
   attempts=state['attempts'];again,reload_seconds=closed_call(folder/'reload-final-call',final_manifest,stream_bundle)
   assert again==final_doc and read(job/'job.json')['attempts']==attempts
   row={'meeting':case['meeting'],'language':case['language'],'frames':case['testFrames'],'firstLiveTextSeconds':first,'sourceSealSeconds':sealed,
    'freshOfflineSeconds':offline_seconds,'streamFinalizationSeconds':final_seconds,'completedCacheReloadSeconds':reload_seconds,
    'incrementalAndOfflineFinalTextExactlyEqual':True,'streamFinalizationReusedEveryAsrResultWithoutRewrite':True,'completedFinalReloadAddedNoNeuralStage':True,
    'actualCpuSpeakerJournalApplied':True,'wordCharactersPreservedExactly':True,'productDefaultChanged':False,'qualityQualified':False,'saleQualified':False,
    'nativeUiTested':False,'cardHardwareUsed':False,'sourceUploaded':False,'job':str(job)}
   rows.append(row);atomic_json(folder/'result.json',row);atomic_json(stream/'events.json',events);atomic_json(root/'progress.json',{'cases':rows,'qualityQualified':False});print(json.dumps(row,ensure_ascii=False),flush=True)
  finally:
   stop.set()
   if child is not None and child.poll() is None:stop_owned_family(child,owned)
   if producer.is_alive():producer.join(timeout=1)
 result={'state':'PASS_ACTUAL_CPU_BACKEND_APP_SCHEMAS_STREAM_OFFLINE_FINALIZATION_AND_CACHE_NOT_QUALITY_QUALIFIED','cases':rows,
  'protocolSha256':sha(root/'protocol.json'),'scriptSha256':sha(__file__),'qualityQualified':False,'saleQualified':False,'installedPackageChanged':False,'nativeUiTested':False}
 atomic_json(root/'result.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
