"""Deploy the existing preferred Qwen family on CPU, one fixed Q8 port only."""
from pathlib import Path
from datetime import datetime
import ctypes,hashlib,json,os,sys,time,urllib.request,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from practical_io_20261107 import atomic_json
limits=WorkerLimits(cpu_percent=1,memory_bytes=256*1024**2);rate=CpuRate(5,50)
limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution';B=D/'joint-architecture-r1';C=B/'qwen-cpu-port-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/qwen-cpu-port-r1')
assert not C.exists() and not E.exists();C.mkdir();E.mkdir();read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
repository='handy-computer/Qwen3-ASR-1.7B-gguf';api='https://huggingface.co/api/models/'+repository+'?blobs=true'
with urllib.request.urlopen(urllib.request.Request(api,headers={'User-Agent':'Companion-existing-Qwen-CPU-port/1.0'}),timeout=30) as response:raw=response.read(2*1024**2);assert response.read(1)==b''
metadata=json.loads(raw);assert not metadata.get('gated');(C/'publisher-metadata.json').write_bytes(raw)
files=[r for r in metadata['siblings'] if r['rfilename']=='Qwen3-ASR-1.7B-Q8_0.gguf'];assert len(files)==1;file=files[0]
roles={r['id']:r['role'] for r in read(D/'sequential-meeting-stageA-r2/scoring-only.json')}
old=read(B/'stagea-cpu-composition-r2/binding.json');cases=[r for r in old['cases'] if roles[r['id']]=='validation'];assert len(cases)==24
source={'repository':repository,'revision':metadata['sha'],'gated':False,'file':file,'api':api,
 'portDocumentation':'https://github.com/handy-computer/transcribe.cpp/blob/275cd50d2c4104c204009a197ac091b9687668e5/docs/models/qwen3-asr-1.7b.md',
 'upstreamAuthorRevision':'7278e1e70fe206f11671096ffdd38061171dd6e5','license':'Apache-2.0','newWeightTraining':False}
atomic_json(C/'source.json',source)
protocol={'state':'FROZEN_EXISTING_QWEN_FAMILY_CPU_DEPLOYMENT_COMPARISON_BEFORE_INFERENCE','at':datetime.now().astimezone().isoformat(),'source':source,'cases':cases,
 'purpose':'Retain the better existing Chinese Qwen family while validating a portable CPU implementation. This is a separately versioned quantized port of the author checkpoint, not an assertion of bitwise equality with the native HF GPU baseline. No new ASR family or parameter grid.',
 'settings':{'backend':'cpu','nativeThreads':4,'cpuPercent':25,'familyPrivateBytes':2147483648,'quant':'Q8_0 only','kvType':'f16','nCtx':2048,
  'contextReason':'All fixed cohort inputs are at most30s, as in the existing PCM contract; complete natural EOS is required and no truncated output can pass.',
  'language':'Same per-case known language policy as the frozen native Qwen baseline; no reference text/prompts/vocabulary/speaker counts.',
  'timestamps':'none','diarize':'off','postEditWords':False,'cuts':'Existing annotation-selected StageA-r2 clips, unchanged; development/regression only.'},
 'deploymentAdvanceGate':{'EnglishMaximumErrors':141,'EnglishReferenceWords':709,'ChineseMaximumErrors':73,'ChineseReferenceCharacters':1258,
  'eachMeetingNoMoreErrorsThanNativeQwenBaseline':True,'all24NaturalEosWithinOriginalResources':True,
  'ifPass':'Validate complete original Chinese recordings with unchanged fixed30s input contract before any deployment decision.',
  'ifFail':'Retain native Qwen baseline and reject this CPU port; do not sweep quantization, context or prompts.'},
 'originalProductGatesUnchanged':True,'speakerWordAssociationNotProvedByAsrOnly':True,'qualityQualified':False,'saleQualified':False,'productDefaultChanged':False,
 'trainingStarted':False,'newNeuralCalls':0,'finalHoldoutOpened':False,'neuralDeadline':'2026-11-16T15:40:00+08:00'}
atomic_json(C/'protocol.json',protocol);assert psutil.disk_usage('E:/').free>50*1024**3
url='https://huggingface.co/'+repository+'/resolve/'+source['revision']+'/'+file['rfilename'];target=E/file['rfilename'];partial=target.with_suffix('.gguf.partial')
state={'state':'DOWNLOADING_ONE_EXISTING_QWEN_CPU_PRESET_NO_INFERENCE','startedAt':datetime.now().astimezone().isoformat(),'url':url,'bytes':0,'expectedBytes':file['size'],'expectedSha256':file['lfs']['sha256'],'newNeuralCalls':0};atomic_json(E/'download.json',state);tick=time.monotonic();last=0
try:
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-existing-Qwen-CPU-port/1.0'}),timeout=30) as response,partial.open('xb',buffering=65536) as output:
  h=hashlib.sha256()
  while True:
   if time.monotonic()-tick>1800:raise TimeoutError('Bounded public model transfer')
   data=response.read(256*1024)
   if not data:break
   output.write(data);h.update(data);state['bytes']+=len(data);assert state['bytes']<=file['size']
   if time.monotonic()-last>10:atomic_json(E/'download.json',state);last=time.monotonic()
  output.flush();os.fsync(output.fileno())
 assert state['bytes']==file['size'] and h.hexdigest()==file['lfs']['sha256'];partial.replace(target)
 atomic_json(C/'model-ready.json',{'file':str(target),'sha256':h.hexdigest(),'bytes':state['bytes'],'sourceRevision':source['revision']})
 state.update(state='COMPLETE_EXISTING_QWEN_CPU_PRESET_DOWNLOAD_VERIFIED_NO_INFERENCE',file=str(target),sha256=h.hexdigest())
except BaseException as error:state.update(state='INCOMPLETE_MODEL_DOWNLOAD_RETAINED_NO_INFERENCE',error=repr(error));raise
finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),limits=limits.query());atomic_json(E/'download.json',state)
print(json.dumps({k:v for k,v in state.items() if k!='limits'}))
