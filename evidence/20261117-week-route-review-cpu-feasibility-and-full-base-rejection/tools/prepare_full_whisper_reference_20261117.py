"""One full-base English reference after auditing the old TurboQ8 rejection."""
from pathlib import Path
from datetime import datetime,timedelta
import hashlib,json,shutil,sys,time,urllib.request
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from durable_model_state_20261117 import atomic_json
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
R=S.parent.parent;J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
C=E/'english-full-base-r1';C.mkdir(exist_ok=False)
cache=Path('E:/CodexData/Companion/.model-cache/english-full-whisper-reference-20261117');cache.mkdir(exist_ok=False)
assert shutil.disk_usage(cache).free>50*1024**3
repo='handy-computer/whisper-large-v3-gguf';rev='274ad1d1cf680b7ee53cc70f78461394cd3a344b'
name='whisper-large-v3-F16.gguf';expected='e633ab1d74b0e98f4f57daedaee34291297dbbf01389bda3d890766600c1c584';size=3107236640
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
url='https://huggingface.co/'+repo+'/resolve/'+rev+'/'+name
metadata={'at':datetime.now().astimezone().isoformat(),'repository':repo,'revision':rev,
 'file':name,'expectedBytes':size,'expectedSha256':expected,'gated':False,
 'upstream':'openai/whisper-large-v3','publisherUpstreamRevision':'06f233f',
 'selectionReason':'Old195/709 failure isTurboQ8, not full large-v3. Compare a single full architecture before undertaking local ASR adaptation. No model/precision/beam grid.',
 'source':'https://huggingface.co/'+repo,'rawAudioUploaded':False,'newTraining':False}
atomic_json(C/'source.json',metadata)
tick=time.monotonic();n=0;h=hashlib.sha256();target=cache/name;last=0
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-full-base-reference'}),timeout=45) as response,target.open('xb') as out:
 while chunk:=response.read(1024**2):
  n+=len(chunk);assert n<=size and time.monotonic()-tick<900
  out.write(chunk);h.update(chunk)
  if n-last>=256*1024**2:
   atomic_json(C/'download-progress.json',{'bytes':n,'expectedBytes':size,'seconds':time.monotonic()-tick});last=n
assert n==size and h.hexdigest()==expected
old=json.loads((J/'english-asr-specialist-r1/binding.json').read_text(encoding='utf-8'))
library=E/'cpp-r1/runtime/transcribe-native-windows-x86_64-cpu-vulkan/transcribe.dll'
runtime={p.name:sha(p) for p in library.parent.iterdir() if p.is_file() and p.suffix.lower() in ['.dll','.exe']}
protocol={**metadata,'model':str(target),'modelSha256':expected,'library':str(library),
 'nativeFiles':runtime,'pythonRoot':old['pythonRoot'],'pythonFiles':old['pythonFiles'],'cases':old['cases'],
 'worker':'C:/Users/Billy/Documents/Codex/2026-11-14/xu-y/work/run_full_whisper_reference_20261117.py',
 'workerSha256':sha(Path('work/run_full_whisper_reference_20261117.py')),
 'device':'explicitAMD780MOnly','cpuPercent':25,'nativeThreads':4,'privateLimitBytes':2147483648,
 'minimumAvailableBytes':3414499000,'cpuTemperatureMode':'owner-authorized-observe-only',
 'stopAt':(datetime.now().astimezone()+timedelta(minutes=25)).isoformat(),
 'settings':{'language':'en','task':'transcribe','timestamps':'segment','diarize':'off','keep_special_tags':True},
 'decoder':'Original native defaults. No prompt/context/vocabulary, word rewrite, denoise, VAD, beam or temperature grid.',
 'gate':{'maximumEnglishErrors':99,'referenceWords':709,'eachMeetingAtMostMossBaseline':True,
    'actionIfPass':'Original whole-source validation, not product adoption.','actionIfFail':'Retain and close this full-base profile without automatic parameter/precision variants.'},
 'priorTurboQ8Result':str(J/'english-asr-specialist-r1/score.json'),'originalReferencesAndCutsUnchanged':True,
 'sourceIndependentHeldout':False,'cutsOriginallyAnnotationSelected':True,
 'qualityQualified':False,'saleQualified':False}
atomic_json(C/'protocol.json',protocol)
atomic_json(C/'download-completed.json',{'bytes':n,'sha256':h.hexdigest(),'seconds':time.monotonic()-tick,'limits':limits.query()})
print(json.dumps({'control':str(C),'bytes':n,'sha256':h.hexdigest(),'seconds':time.monotonic()-tick}),flush=True)
