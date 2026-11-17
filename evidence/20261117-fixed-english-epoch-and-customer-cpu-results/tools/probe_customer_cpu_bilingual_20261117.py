"""Isolated CPU capability probe of two already installed customer model assets.

No client edits, downloads, GPU inference or private recordings. Run only after
the active GPU work releases the shared model lock. This is not an installed
binary test: the available Python sherpa runtime is1.13.4, clientDLLs1.13.1.
"""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse,gc,hashlib,json,os,sys,threading,time,wave
os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='-1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from meeting_acoustic_worker_20261116 import own_limits
from companion_local_pcm_session_20261114 import exclusive_file
from durable_model_state_20261117 import atomic_json
from moss_windows_resource_limits_20261104 import SystemRamPressure
ap=argparse.ArgumentParser();mode=ap.add_mutually_exclusive_group(required=True)
mode.add_argument('--prepare',action='store_true');mode.add_argument('--execute',action='store_true');mode.add_argument('--score',action='store_true');a=ap.parse_args()
limits=own_limits(25 if a.execute else 5)
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
out=C/'customer-cpu-probe-r1';protocol=C/'customer-cpu-probe-protocol-r1.json'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
if a.prepare:
 import sherpa_onnx
 refs=read(J.parent/'sequential-meeting-stageA-r2/scoring-only.json')
 cases=[dict(id=c['id'],audio=c['wav'],audioSha256=c['wavSha256'],pcmSha256=c['pcmSha256'],frames=c['frames']) for c in refs if c['role']=='validation']
 assert len(cases)==24 and all('L_R003' not in c['id'] for c in cases)
 root=Path.home()/'AppData/Roaming/Companion Type/models/local-asr'
 profiles=[dict(name='existing_chinese_default',kind='paraformer',model=str(root/'funasr-paraformer-large-zh-2024/model.int8.onnx'),
  tokens=str(root/'funasr-paraformer-large-zh-2024/tokens.txt'),expectedModelSha256='8234905d74db17f7466a1cd110ce20f57c1ff9c1fc95db0615d8931955da5c54'),
  dict(name='existing_multilingual_auto',kind='sense_voice',language='auto',model=str(root/'sherpa-onnx-sense-voice-2024-07-17/model.int8.onnx'),
  tokens=str(root/'sherpa-onnx-sense-voice-2024-07-17/tokens.txt'),expectedModelSha256='c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51')]
 for p in profiles:
  assert sha(p['model'])==p['expectedModelSha256'];p['tokensSha256']=sha(p['tokens'])
 package=Path(sherpa_onnx.__file__).parent
 files=[dict(file=str(p),sha256=sha(p)) for p in package.rglob('*') if p.suffix in ('.pyd','.dll')]
 assert files and sherpa_onnx.__version__=='1.13.4'
 P=dict(state='FROZEN_EXISTING_CPU_CUSTOMER_CAPABILITY_PROBE',at=datetime.now().astimezone().isoformat(),
  workerSha256=sha(__file__),runtime='sherpa-onnx1.13.4',clientPinnedRuntime='1.13.1',installedClientBinaryTest=False,
  files=files,cases=cases,profiles=profiles,provider='cpu',threads=2,privateLimitBytes=2*1024**3,
  minimumAvailableBytes=3414499000,maximumSeconds=1200,neuralLock='E:/CodexData/Companion/.model-cache/local-qwen-decoder.lock',
  originalReferences= str(J.parent/'sequential-meeting-stageA-r2/scoring-only.json'),sourceOfQuietCut=str(R/'companion-device-closure055/apps/windows/src-tauri/src/backend/transcription/paraformer_shared.rs'),
  cpuTemperatureMode='observe-only',newModelCandidatesDownloaded=0,productQualification=False)
 assert not protocol.exists();atomic_json(protocol,P);print(json.dumps({'state':P['state'],'cases':24,'profiles':2,'runtime':P['runtime'],'provider':'cpu','modelInferencePerformed':False}));raise SystemExit(0)
P=read(protocol);assert sha(__file__)==P['workerSha256']
if a.score:
 from score_sequential_meetings_20261115 import measure
 state=read(out/'completed.json');assert state['state']=='COMPLETE_EXISTING_CPU_BILINGUAL_PROBE'
 refs={c['id']:c for c in read(P['originalReferences']) if c['role']=='validation'};groups=defaultdict(list)
 for entry in state['completed']:
  assert sha(entry['file'])==entry['sha256'];v=read(entry['file']);c=refs[v['id']]
  m=measure(c['rawReferenceText'],v['text'],c['language']);groups[(v['profile'],c['language'])].append(dict(id=v['id'],seconds=v['seconds'],audioSeconds=v['frames']/16000,**m))
 summaries=[]
 for (profile,language),rows in sorted(groups.items()):
  n=sum(c['referenceUnits'] for c in rows);e=sum(c['errors'] for c in rows);seconds=sum(c['seconds'] for c in rows);audio=sum(c['audioSeconds'] for c in rows)
  summaries.append(dict(profile=profile,language=language,cases=len(rows),referenceUnits=n,errors=e,errorRate=e/n,
   seconds=seconds,audioSeconds=audio,realTimeFactor=seconds/audio,
   **{k:sum(c[k] for c in rows) for k in ['substitutions','deletions','insertions']}))
 result=dict(state='CPU_CUSTOMER_CAPABILITY_PROBE_SCORED_NOT_PRODUCT_QUALIFIED',summaries=summaries,
  provider='cpu',privatePeakBytes=state['limits']['jobPeakPrivateCommitBytes'],installedClientBinaryTest=False,
  originalReferencesUnchanged=True,finalHoldoutOpened=False,newInferenceByScorer=0,qualityQualified=False,saleQualified=False)
 atomic_json(out/'score.json',result);print(json.dumps(result));raise SystemExit(0)
out.mkdir(exist_ok=False);pressure=SystemRamPressure();closing=threading.Event();start=time.monotonic()
state=dict(state='PREPARING_EXISTING_CPU_BILINGUAL_PROBE',pid=os.getpid(),createdAt=__import__('psutil').Process().create_time(),completed=[],newNeuralCalls=0,newTrainingUpdates=0,referenceRead=False,provider='cpu',gpuRequired=False,qualityQualified=False)
def save(**values):
 state.update(values,at=datetime.now().astimezone().isoformat(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
def watch():
 import psutil
 while not closing.wait(.5):
  if pressure.low() or psutil.virtual_memory().available<P['minimumAvailableBytes'] or time.monotonic()-start>P['maximumSeconds']:
   save(state='STOPPED_CPU_PROBE_RESOURCE_BOUNDARY');atomic_json(out/'completed.json',state);os._exit(76)
def cut(pcm):
 count=len(pcm)//2
 if count<=20*16000:return count
 values=__import__('numpy').frombuffer(pcm,dtype='<i2').astype('int64');best=(2**64-1,16*16000)
 for i in range(14*16000,18*16000+1,16000//5):
  score=int(abs(values[i-800:i+800]).sum())+abs(i-16*16000)//20
  if score<best[0]:best=(score,i)
 return best[1]
try:
 with exclusive_file(Path(P['neuralLock'])):
  save();threading.Thread(target=watch,daemon=True).start()
  for f in P['files']:assert sha(f['file'])==f['sha256']
  import numpy as np,sherpa_onnx
  assert sherpa_onnx.__version__=='1.13.4' and 'torch' not in sys.modules
  for p in P['profiles']:
   assert sha(p['model'])==p['expectedModelSha256'] and sha(p['tokens'])==p['tokensSha256']
   tick=time.perf_counter();common=dict(tokens=p['tokens'],num_threads=2,provider='cpu',debug=False)
   recognizer=sherpa_onnx.OfflineRecognizer.from_paraformer(paraformer=p['model'],**common) if p['kind']=='paraformer' else sherpa_onnx.OfflineRecognizer.from_sense_voice(model=p['model'],language='auto',use_itn=False,**common)
   assert recognizer.config.model_config.provider=='cpu'
   save(state='RUNNING_EXISTING_CUSTOMER_MODEL_ON_CPU',profile=p['name'],loadSeconds=time.perf_counter()-tick)
   for c in P['cases']:
    assert sha(c['audio'])==c['audioSha256']
    with wave.open(c['audio'],'rb') as w:
     assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,c['frames']);pcm=w.readframes(c['frames'])
    assert hashlib.sha256(pcm).hexdigest()==c['pcmSha256']
    tick=time.perf_counter();offset=0;parts=[]
    while offset<len(pcm):
     block=pcm[offset:offset+20*16000*2+2];count=cut(block);block=block[:count*2];assert count>0
     stream=recognizer.create_stream();stream.accept_waveform(16000,np.frombuffer(block,dtype='<i2').astype(np.float32)/32768)
     recognizer.decode_stream(stream);parts.append(dict(startFrame=offset//2,frames=count,text=stream.result.text,language=getattr(stream.result,'lang','')))
     offset+=len(block);del stream
    assert offset==len(pcm) and sum(v['frames'] for v in parts)==c['frames']
    packet=dict(id=c['id'],profile=p['name'],provider='cpu',threads=2,frames=c['frames'],audioSha256=c['audioSha256'],pcmSha256=c['pcmSha256'],
     text=' '.join(v['text'] for v in parts if v['text']),chunks=parts,seconds=time.perf_counter()-tick,allInputFramesPreservedExactlyOnce=True,referenceUsed=False,wordsPostEdited=False)
    file=out/(p['name']+'--'+c['id']+'.json');atomic_json(file,packet);state['completed'].append(dict(file=str(file),sha256=sha(file)));state['newNeuralCalls']+=len(parts);save(activeCase=c['id'])
   del recognizer;gc.collect()
  save(state='COMPLETE_EXISTING_CPU_BILINGUAL_PROBE');atomic_json(out/'completed.json',state)
except BaseException as error:
 save(state='FAILED_EXISTING_CPU_PROBE_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));atomic_json(out/'completed.json',state);raise
finally:closing.set();pressure.close()
