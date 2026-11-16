"""Real paced public PCM intake and actual CPU decoding, then identical offline input."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,subprocess,sys,threading,time,traceback,uuid,wave,psutil
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession,read_json
from practical_io_20261107 import atomic_json,stop_owned_family
R=S.parent.parent;BASE=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run_phase(root,control,case,pcm,live):
 root.mkdir();session=PcmSession.create(root/'session',recording_id=str(uuid.uuid4()))
 run=root/'decoder-r1';stop=threading.Event();producer_error=[];ingress={};events=[];first_text=first_closed=final_time=None;module_evidence=None
 if not live:
  for start in range(0,len(pcm),960000):session.append(start//2,pcm[start:start+960000])
  session.seal(len(pcm)//2)
 tick=time.perf_counter();ingress['startedAt']=datetime.now().astimezone().isoformat()
 def produce():
  try:
   for first in range(0,len(pcm)//2,80000):
    end=min(first+80000,len(pcm)//2);due=end/16000
    while time.perf_counter()-tick<due:
     if stop.wait(min(.05,due-(time.perf_counter()-tick))):return
    packet=pcm[first*2:end*2];ack=session.append(first,packet)
    events.append({'seconds':time.perf_counter()-tick,'event':'packet','startFrame':first,'endFrame':end,'ack':ack})
    if first==80000:
     duplicate=session.append(0,pcm[:160000]);assert duplicate['duplicate'] and duplicate['newFrames']==0
     events.append({'seconds':time.perf_counter()-tick,'event':'byte_identical_retransmission','ack':duplicate})
   session.seal(len(pcm)//2);ingress['sealedSeconds']=time.perf_counter()-tick
  except BaseException as error:
   producer_error.append({'error':repr(error),'errno':getattr(error,'errno',None),'winerror':getattr(error,'winerror',None),'traceback':traceback.format_exc()});stop.set()
 if live:
  producer=threading.Thread(target=produce,daemon=True);producer.start()
 else:producer=None;ingress['sealedSeconds']=0.
 child=owned=None;last=None
 try:
  with (root/'controller.log').open('xb') as log:
   child=subprocess.Popen([sys.executable,str(S/'run_local_moss_cpu_decoder_20261116.py'),'--session',str(session.root),
    '--control',str(control),'--run',str(run),'--follow-seconds',str(case['testAudioSeconds']+180 if live else 0)],
    stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
   owned=psutil.Process(child.pid)
   while child.poll() is None:
    if producer_error:raise RuntimeError('Original PCM producer failed: '+str(producer_error))
    if time.perf_counter()-tick>case['testAudioSeconds']+240:
     if run.exists():(run/'stop.request').write_text('Bounded dual-route control deadline.\n',encoding='utf-8')
     raise TimeoutError('Actual CPU PCM path exceeded its fixed control deadline')
    doc=session.document();key=(doc['confirmedAudioFrames'],doc['finalDecodedFrames'],doc['text'],doc['isFinal'])
    now=time.perf_counter()-tick
    if doc['text'].strip() and first_text is None:first_text=now
    if doc['finalDecodedFrames']>=480000 and first_closed is None:first_closed=now
    if doc['isFinal'] and final_time is None:final_time=now
    if key!=last:events.append({'seconds':now,'event':'document','confirmedFrames':doc['confirmedAudioFrames'],'finalDecodedFrames':doc['finalDecodedFrames'],
     'textCharacters':len(doc['text']),'isFinal':doc['isFinal'],'revisions':[r['revision'] for r in doc['utterances']]});last=key
    worker_file=run/'worker-state.json'
    if module_evidence is None and worker_file.exists():
     worker=read_json(worker_file)
     if worker.get('backend')=='CPU' and worker['completed']:
      try:
       pid=worker['limits']['pid'];family={p.pid for p in [owned]+owned.children(recursive=True)};assert pid in family
       modules=sorted({m.path for m in psutil.Process(pid).memory_maps() if m.path.lower().endswith('.dll')})
       module_evidence={'workerPid':pid,'cpuKernelModules':[x for x in modules if 'ggml' in x.lower() or 'transcribe' in x.lower()],
        'optionalGpuComputeModules':[x for x in modules if any(t in Path(x).name.lower() for t in ['ggml-vulkan','ggml-cuda','amdhip','cublas','torch'])]}
      except psutil.Error:pass
    time.sleep(.1)
  if producer:producer.join(timeout=1)
  assert not producer_error and child.returncode==0,(child.returncode,producer_error)
  document=session.document();assert document['isFinal'] and document['finalDecodedFrames']==case['testFrames']
  assert sha(session.audio)==case['pcmSha256'] and session.audio.read_bytes()==pcm
  worker=read_json(run/'worker-state.json');assert worker['state']=='COMPLETE_CPU_PCM_FINAL_TEXT_SPEAKERS_PENDING_NOT_QUALIFIED' and worker['backend']=='CPU'
  assert module_evidence is not None and not module_evidence['optionalGpuComputeModules']
  records=[read_json(p) for p in (session.root/'results').glob('*.json')];finals=sorted((r for r in records if r['request']['blockFinal']),key=lambda r:r['request']['startFrame'])
  cursor=0
  for row in finals:
   job=row['request'];assert job['startFrame']==cursor and row['result']['accepted'] and row['result']['naturalEos'];cursor=job['endFrame']
  assert cursor==case['testFrames']
  result={'state':'PASS_ACTUAL_CPU_PCM_PHASE_NOT_QUALITY_QUALIFIED','live':live,'meeting':case['meeting'],'frames':cursor,
   'firstTextSeconds':first_text,'firstCompleteBlockSeconds':first_closed,'ingressSealSeconds':ingress['sealedSeconds'],
   'finalDocumentSeconds':final_time if final_time is not None else time.perf_counter()-tick,
   'firstTextBeforeInputSeal':first_text is not None and first_text<ingress['sealedSeconds'] if live else None,
   'finalIntervals':[{k:r['request'][k] for k in ['startFrame','endFrame','pcmSha256']} for r in finals],
   'finalRawDecoded':[r['result']['rawDecoded'] for r in finals],'finalText':document['text'],
   'document':document,'nativeModules':module_evidence,'decoderRun':read_json(run/'run.json'),
   'completedRequests':worker['completed'],'modelNativeInferencePerformed':True,'gpuComputeUsed':False,'sourceUploaded':False,
   'qualityQualified':False,'speakerIdentityVerified':False,'cardHardwareUsed':False,'inputIsPacedPublicFileReplay':live}
  atomic_json(root/'events.json',events);atomic_json(root/'result.json',result);return result
 except BaseException as error:
  atomic_json(root/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'producerErrors':producer_error,
   'ingress':ingress,'firstTextSeconds':first_text,'firstCompleteBlockSeconds':first_closed,'elapsedSeconds':time.perf_counter()-tick,
   'confirmedState':session.state(),'qualityQualified':False})
  atomic_json(root/'events.json',events)
  raise
 finally:
  stop.set()
  if child is not None and child.poll() is None:
   if run.exists():(run/'stop.request').write_text('Owned dual-route control terminated; durable audio retained.\n',encoding='utf-8')
   try:child.wait(timeout=8)
   except subprocess.TimeoutExpired:stop_owned_family(child,owned)
  if producer:producer.join(timeout=1)
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,default=BASE/'cpu-pcm-candidate-r1');p.add_argument('--root',type=Path,required=True);a=p.parse_args()
 assert not a.root.exists();a.root.mkdir();P=read_json(a.control/'dualroute-protocol.json');summaries=[]
 for case in P['cases']:
  assert sha(case['audio'])==case['audioSha256']
  with wave.open(case['audio'],'rb') as w:pcm=w.readframes(case['testFrames'])
  assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256']
  folder=a.root/case['meeting'];folder.mkdir();live=run_phase(folder/'incremental',a.control,case,pcm,True);offline=run_phase(folder/'offline',a.control,case,pcm,False)
  assert live['finalIntervals']==offline['finalIntervals'] and live['finalRawDecoded']==offline['finalRawDecoded'] and live['finalText']==offline['finalText']
  expected=P['originalFullCandidateFirstTwoChunks'][case['meeting']]
  for i,row in enumerate(expected):assert sha(row['file'])==row['sha256'] and read_json(row['file'])['rawDecoded']==live['finalRawDecoded'][i]
  summary={'meeting':case['meeting'],'language':case['language'],'audioSeconds':case['testAudioSeconds'],'firstLiveTextSeconds':live['firstTextSeconds'],
   'liveInputSealSeconds':live['ingressSealSeconds'],'liveFinalDocumentSeconds':live['finalDocumentSeconds'],'offlineFinalDocumentSeconds':offline['finalDocumentSeconds'],
   'liveTextVisibleBeforeSeal':live['firstTextBeforeInputSeal'],'incrementalAndOfflineFinalRawTextExactlyEqual':True,
   'firstTwoChunksMatchOriginalWholeCandidateExactly':True,'allFinalFramesCoveredExactlyOnce':True,'byteIdenticalReplayAcceptedWithoutExtraSource':True,
   'gpuComputeModulesLoaded':False,'cpuPercent':25,'nativeThreads':4,'qualityQualified':False,'sourceUploaded':False}
  summaries.append(summary);atomic_json(a.root/'progress.json',{'completed':summaries,'qualityQualified':False});print(json.dumps(summary,ensure_ascii=False),flush=True)
 result={'state':'PASS_BILINGUAL_ACTUAL_CPU_INCREMENTAL_OFFLINE_INTEGRATION_NOT_QUALITY_QUALIFIED','cases':summaries,
  'scriptSha256':sha(__file__),'controlBindingSha256':sha(a.control/'binding.json'),'protocolSha256':sha(a.control/'dualroute-protocol.json'),
  'qualityQualified':False,'saleQualified':False,'speakerIdentityVerified':False,'cardHardwareUsed':False,'installedPackageChanged':False}
 atomic_json(a.root/'result.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
