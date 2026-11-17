"""One selected CPU export, two frozen segmentation modes; no training/grid."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,gc,hashlib,json,os,sys,threading,time,wave
os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from meeting_acoustic_worker_20261116 import own_limits
from durable_model_state_20261117 import atomic_json
from companion_local_pcm_session_20261114 import exclusive_file
from moss_windows_resource_limits_20261104 import SystemRamPressure
ap=argparse.ArgumentParser();m=ap.add_mutually_exclusive_group(required=True)
m.add_argument('--prepare',action='store_true');m.add_argument('--execute',action='store_true');m.add_argument('--score',action='store_true');a=ap.parse_args()
limits=own_limits(25 if a.execute else 5)
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1');C=E/'english-accuracy-reference-20261117';T=E/'gpu-owned-evening20261117-r2'
protocol=C/'selected-cpu-segmentation-protocol-r1.json';out=C/'selected-cpu-segmentation-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
if a.prepare:
 original=read(C/'customer-cpu-probe-protocol-r1.json');ids={read(e['file'])['id'] for e in read(T/'baseline/completed.json')['completed']}
 cases=[c for c in original['cases'] if c['id'] in ids];assert len(cases)==12
 acquired=read(C/'parakeet-cpu-export-acquisition-r1/completed.json');assert acquired['newInference']==0
 P=dict(state='FROZEN_SINGLE_CPU_EXPORT_SEGMENTATION_COMPARISON',at=now(),workerSha256=sha(__file__),
  runtime=original['runtime'],runtimeFiles=original['files'],modelFiles=acquired['files'],modelRevision=acquired['revision'],
  cases=cases,modes=['whole_case','quiet16_incremental'],provider='cpu',threads=2,modelType='nemo_transducer',
  decodingMethod='greedy_search',maximumSeconds=600,privateLimitBytes=2*1024**3,minimumAvailableBytes=3414499000,
  neuralLock=original['neuralLock'],originalReferences=original['originalReferences'],
  decisionRules=['Same-weight whole-versus-cut error difference describes segmentation effect for this exported model only.',
   'Different-family/precision/runtime comparisons are deployment-profile comparisons, not pureCPU or quantization causality.',
   'Retain and stop both predefined modes after the fixed12 outputs. No threshold/model/precision/window variants.',
   'Original5/2percent and independent complete-meeting/person/client gates remain; no automatic deployment.'],
  newTrainingUpdates=0,installedClientBinaryTest=False,qualityQualified=False,saleQualified=False)
 assert not protocol.exists();atomic_json(protocol,P);print(json.dumps(dict(state=P['state'],cases=12,modes=P['modes'],maximumSeconds=600)));raise SystemExit(0)
P=read(protocol);assert sha(__file__)==P['workerSha256']
if a.score:
 from score_sequential_meetings_20261115 import measure
 state=read(out/'completed.json');assert state['state']=='COMPLETE_FROZEN_CPU_SEGMENTATION_COMPARISON'
 refs={r['id']:r for r in read(P['originalReferences']) if r['language']=='English' and r['role']=='validation'}
 groups={mode:[] for mode in P['modes']}
 for entry in state['completed']:
  assert sha(entry['file'])==entry['sha256'];p=read(entry['file']);r=refs[p['id']]
  assert p['audioSha256']==r['wavSha256'] and p['allInputFramesPreservedExactlyOnce'] and not p['wordsPostEdited']
  groups[p['mode']].append(dict(id=p['id'],meeting=r['meeting'],seconds=p['seconds'],audioSeconds=p['frames']/16000,
   **measure(r['rawReferenceText'],p['text'],'English')))
 summaries=[]
 for mode,rows in groups.items():
  assert len(rows)==12;words=sum(r['referenceUnits'] for r in rows);assert words==709
  errors=sum(r['errors'] for r in rows);seconds=sum(r['seconds'] for r in rows);audio=sum(r['audioSeconds'] for r in rows)
  summaries.append(dict(mode=mode,errors=errors,referenceWords=words,wer=errors/words,seconds=seconds,audioSeconds=audio,
   realTimeFactor=seconds/audio,meetings=[dict(meeting=meeting,errors=sum(r['errors'] for r in rows if r['meeting']==meeting),referenceWords=sum(r['referenceUnits'] for r in rows if r['meeting']==meeting)) for meeting in sorted({r['meeting'] for r in rows})],cases=rows))
 result=dict(state='SCORED_FIXED_SAME_CPU_MODEL_SEGMENTATION_COMPARISON_NOT_PRODUCT_ACCEPTANCE',at=now(),summaries=summaries,
  incrementalMinusWholeErrors=summaries[1]['errors']-summaries[0]['errors'],sameWeightsRuntimePrecisionAndInputs=True,
  changedVariable='segmentation',privatePeakBytes=state['limits']['jobPeakPrivateCommitBytes'],provider='cpu',threads=2,
  runtime=P['runtime'],modelRevision=P['modelRevision'],installedClientBinaryTest=False,
  originalReferencesUnchanged=True,comparisonToNativeResearchIsNotControlledQuantizationAblation=True,
  newScorerInference=0,newTrainingUpdates=0,finalHoldoutOpened=False,qualityQualified=False,saleQualified=False)
 target=out/'score.json';assert not target.exists();atomic_json(target,result)
 print(json.dumps({k:result[k] for k in ['state','summaries','incrementalMinusWholeErrors','privatePeakBytes']},ensure_ascii=False));raise SystemExit(0)
out.mkdir(exist_ok=False);start=time.monotonic();closing=threading.Event();pressure=SystemRamPressure()
state=dict(state='ADMITTING_FIXED_CPU_SEGMENTATION_COMPARISON',at=now(),pid=os.getpid(),createdAt=__import__('psutil').Process().create_time(),
 completed=[],newNeuralCalls=0,newTrainingUpdates=0,referenceRead=False,qualityQualified=False,saleQualified=False)
def save(**v):
 state.update(v,observedAt=now(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
def watch():
 import psutil
 while not closing.wait(.5):
  if pressure.low() or psutil.virtual_memory().available<P['minimumAvailableBytes'] or time.monotonic()-start>P['maximumSeconds']:
   save(state='STOPPED_FIXED_CPU_RESOURCE_OR_TIME_BOUNDARY');atomic_json(out/'completed.json',state);os._exit(76)
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
  for f in P['runtimeFiles']+P['modelFiles']:assert sha(f['file'])==f['sha256']
  import numpy as np,sherpa_onnx
  assert sherpa_onnx.__version__=='1.13.4' and 'torch' not in sys.modules
  model={Path(f['file']).name:f['file'] for f in P['modelFiles']};tick=time.perf_counter()
  recognizer=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=model['encoder.int8.onnx'],decoder=model['decoder.int8.onnx'],
   joiner=model['joiner.int8.onnx'],tokens=model['tokens.txt'],num_threads=2,provider='cpu',model_type='nemo_transducer',decoding_method='greedy_search')
  assert recognizer.config.model_config.provider=='cpu'
  save(state='RUNNING_FIXED_SAME_CPU_MODEL_TWO_SEGMENTATION_MODES',modelLoadSeconds=time.perf_counter()-tick)
  for mode in P['modes']:
   for case in P['cases']:
    assert sha(case['audio'])==case['audioSha256']
    with wave.open(case['audio'],'rb') as w:
     assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes())==(1,2,16000,case['frames']);pcm=w.readframes(case['frames'])
    assert hashlib.sha256(pcm).hexdigest()==case['pcmSha256']
    tick=time.perf_counter();offset=0;chunks=[]
    while offset<len(pcm):
     block=pcm[offset:] if mode=='whole_case' else pcm[offset:offset+20*16000*2+2]
     count=len(block)//2 if mode=='whole_case' else cut(block);block=block[:count*2]
     stream=recognizer.create_stream();stream.accept_waveform(16000,np.frombuffer(block,dtype='<i2').astype(np.float32)/32768)
     recognizer.decode_stream(stream);chunks.append(dict(startFrame=offset//2,frames=count,text=stream.result.text));offset+=len(block);del stream
    assert offset==len(pcm) and sum(c['frames'] for c in chunks)==case['frames']
    packet=dict(id=case['id'],mode=mode,audioSha256=case['audioSha256'],frames=case['frames'],provider='cpu',threads=2,
     text=' '.join(c['text'] for c in chunks),chunks=chunks,seconds=time.perf_counter()-tick,
     allInputFramesPreservedExactlyOnce=True,wordsPostEdited=False,referenceUsed=False,protocolSha256=sha(protocol))
    file=out/(mode+'--'+case['id']+'.json');atomic_json(file,packet);state['completed'].append(dict(file=str(file),sha256=sha(file)))
    state['newNeuralCalls']+=len(chunks);save(mode=mode,activeCase=case['id']);gc.collect()
  save(state='COMPLETE_FROZEN_CPU_SEGMENTATION_COMPARISON');atomic_json(out/'completed.json',state)
except BaseException as error:
 save(state='FAILED_FIXED_CPU_COMPARISON_RETAINED_NO_AUTOMATIC_RETRY',error=repr(error));atomic_json(out/'completed.json',state);raise
finally:closing.set();pressure.close()
