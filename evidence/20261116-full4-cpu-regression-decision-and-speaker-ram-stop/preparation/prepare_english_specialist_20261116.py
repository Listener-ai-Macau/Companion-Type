"""One public English specialist contrast; freeze selection before downloading weights."""
from pathlib import Path
from datetime import datetime
import ctypes,hashlib,json,os,sys,time,urllib.request,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=B/'english-asr-specialist-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/english-asr-specialist-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
source=read(C/'source.json');assert not source['gated'];assert source['file']['size']==886381728
old=read(B/'stagea-cpu-composition-r2/binding.json');cases=[r for r in old['cases'] if r['language']=='English'];assert len(cases)==12
protocol={'at':datetime.now().astimezone().isoformat(),'state':'FROZEN_ONE_ENGLISH_ASR_SPECIALIST_CONTRAST_BEFORE_INFERENCE',
 'modelSource':source,'cases':cases,'inputCohort':'Existing StageA-r2 12 English validation clips from ES2003b and EN2001a, already used for development; not a blind test.',
 'selectionReason':'Full4 fixed30MOSS regresses both Chinese recordings and leaves English aggregate27.74% raw errors. Keep protected Chinese Qwen. Test only one dedicated mature English ASR rather than tuning a universal model.',
 'settings':{'backend':'cpu','nativeThreads':4,'cpuPercent':25,'familyPrivateBytes':2*1024**3,'modelPreset':'publisher-recommended Q8_0 only',
  'language':'en','task':'transcribe','timestamps':'segment','diarize':'off','familyOptions':'upstream defaults; no reference text/prompt/vocabulary/prefix',
  'wordRewrite':False,'referenceSelectedCuts':False,'extraVAD':False,'denoise':False,'parameterGrid':False},
 'advanceGate':{'maximumEnglishErrors':99,'referenceUnits':709,'relativeReductionVsFixedMoss124ErrorsAtLeast':.20,
  'eachMeetingErrorsAtMostMossBaseline':True,'all12CompleteWithoutMemoryOrDecodeFailure':True,
  'actionIfPass':'One complete original English meeting per source under the same frozen ASR settings; no default promotion from clips alone.',
  'actionIfFail':'Retain raw failure and stop this candidate; no temperature/quantization/beam grid.'},
 'originalProductGatesUnchanged':{'rawAndEachPersonErrorRateBelow':.05,'DERZeroCollarAtMost':.10,'factRecallAtLeast':.95,'criticalFactsWrong':0},
 'speakerAttributionNotProvedByAsrText':True,'wordTimestampsNotSupportedByThisPort':True,
 'finalHoldoutOpened':False,'newNeuralCalls':0,'newWeightTraining':False,'productDefaultChanged':False,'qualityQualified':False,
 'neuralDeadline':'2026-11-16T15:40:00+08:00','reportDeadline':'2026-11-16T16:00:00+08:00'}
assert not (C/'protocol.json').exists();atomic_json(C/'protocol.json',protocol)
assert not E.exists();E.mkdir(parents=True);assert psutil.disk_usage('E:/').free>50*1024**3
name=source['file']['rfilename'];url='https://huggingface.co/'+source['repository']+'/resolve/'+source['revision']+'/'+name
state={'state':'DOWNLOADING_ONE_PUBLIC_PINNED_GGUF_NO_NEURAL_CALLS','startedAt':datetime.now().astimezone().isoformat(),'url':url,
 'expectedBytes':source['file']['size'],'expectedSha256':source['file']['lfs']['sha256'],'bytes':0,'newNeuralCalls':0}
atomic_json(E/'download.json',state);target=E/name;partial=E/(name+'.partial');tick=time.monotonic();last=0
try:
 request=urllib.request.Request(url,headers={'User-Agent':'Companion-public-model-provenance/1.0'})
 with urllib.request.urlopen(request,timeout=30) as response,partial.open('xb',buffering=64*1024) as output:
  state['resolvedHost']=urllib.parse.urlparse(response.url).hostname
  digest=hashlib.sha256()
  while True:
   if time.monotonic()-tick>1800:raise TimeoutError('Bounded public artifact transfer time')
   block=response.read(256*1024)
   if not block:break
   output.write(block);digest.update(block);state['bytes']+=len(block)
   assert state['bytes']<=state['expectedBytes']
   if time.monotonic()-last>10:state['limits']=limits.query();atomic_json(E/'download.json',state);last=time.monotonic()
  output.flush();os.fsync(output.fileno())
 assert state['bytes']==state['expectedBytes'] and digest.hexdigest()==state['expectedSha256']
 partial.replace(target);state.update(state='COMPLETE_PUBLIC_PINNED_GGUF_SHA_VERIFIED_NO_INFERENCE',file=str(target),sha256=digest.hexdigest())
 atomic_json(C/'model-ready.json',{'file':str(target),'sha256':digest.hexdigest(),'bytes':state['bytes'],'sourceRevision':source['revision'],'source':url})
except BaseException as error:state.update(state='INCOMPLETE_PUBLIC_DOWNLOAD_RETAINED_NO_NEURAL_CALLS',error=repr(error));raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),elapsedSeconds=time.monotonic()-tick,limits=limits.query());atomic_json(E/'download.json',state)
print(json.dumps(state,ensure_ascii=False))
