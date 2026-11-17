"""Fixed ONNX weights/decoder: reproduce old frontend, then reference frontend.

The reference frontend is evaluated only if all12 old outputs reproduce exactly
(whitespace/NFC only). No reference labels, search, changed weights or training.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,hashlib,json,os,sys,threading,time,unicodedata
os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from meeting_acoustic_worker_20261116 import own_limits
from durable_model_state_20261117 import atomic_json
from companion_local_pcm_session_20261114 import exclusive_file
from moss_windows_resource_limits_20261104 import SystemRamPressure
ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--execute',action='store_true');a=ap.parse_args()
limits=own_limits(25 if a.execute else 5)
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117');O=C/'preprocessing-contract-20261118'
protocol=O/'protocol-r1.json';out=O/'cpu-contract-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
if a.prepare:
 import onnxruntime
 old=read(C/'selected-cpu-segmentation-protocol-r1.json');features=read(O/'feature-inputs-r2/completed.json')
 assert features['state']=='COMPLETE_CPU_FRONTEND_INPUTS_NO_MODEL_INFERENCE' and len(features['cases'])==12
 ortroot=Path(onnxruntime.__file__).parent
 runtimeFiles=[dict(file=str(p),sha256=sha(p)) for p in ortroot.rglob('*') if p.is_file() and p.suffix in ('.pyd','.dll')]
 cases=[]
 for case in features['cases']:
  previous=C/'selected-cpu-segmentation-r1'/('whole_case--'+case['id']+'.json')
  cases.append(dict(case,oldOutput=str(previous),oldOutputSha256=sha(previous)))
 P=dict(state='FROZEN_FRONTEND_COMPONENT_CONTRACT_WITH_NATIVE_OUTPUT_CONTROL',at=now(),workerSha256=sha(__file__),
  cases=cases,modelFiles=old['modelFiles'],modelRevision=old['modelRevision'],runtime='onnxruntime'+onnxruntime.__version__,runtimeFiles=runtimeFiles,
  tokenizer='E:/CodexData/Companion/.model-cache/english-transducer-official20261116/tokenizer.json',
  tokenizerSha256=sha('E:/CodexData/Companion/.model-cache/english-transducer-official20261116/tokenizer.json'),
  threads=2,provider='CPUExecutionProvider',neuralLock=old['neuralLock'],minimumAvailableBytes=old['minimumAvailableBytes'],
  maximumSeconds=600,privateLimitBytes=2*1024**3,
  modes=['installed_frontend','published_hf_frontend'],baselineOutputExactMatchRequired=12,
  changedComponent='Feature frontend only; fixed ONNX INT8 weights, ORT provider, TDT decoder and input audio.',
  stop='Any baseline output mismatch ends before reference-frontend inference. No changed-parameter retry.',
  newTrainingUpdates=0,referenceLabelsRead=False,qualityQualified=False,saleQualified=False)
 assert not protocol.exists();atomic_json(protocol,P);print(json.dumps(dict(state=P['state'],cases=12,modes=P['modes'],runtime=P['runtime'])));raise SystemExit(0)
P=read(protocol);assert sha(__file__)==P['workerSha256'];out.mkdir(exist_ok=False)
start=time.monotonic();done=threading.Event();pressure=SystemRamPressure()
state=dict(state='ADMITTING_FRONTEND_CONTRACT_CONTROL',at=now(),pid=os.getpid(),createdAt=__import__('psutil').Process().create_time(),
 completed=[],newNeuralCalls=0,newTrainingUpdates=0,referenceRead=False,qualityQualified=False,saleQualified=False)
def save(**v):
 state.update(v,observedAt=now(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
def watch():
 import psutil
 while not done.wait(.5):
  if pressure.low() or psutil.virtual_memory().available<P['minimumAvailableBytes'] or time.monotonic()-start>P['maximumSeconds']:
   save(state='STOPPED_FRONTEND_RESOURCE_OR600S_BOUNDARY');atomic_json(out/'completed.json',state);os._exit(76)
def canonical(text):return unicodedata.normalize('NFC',' '.join(text.split()))
try:
 with exclusive_file(Path(P['neuralLock'])):
  save();threading.Thread(target=watch,daemon=True).start()
  import numpy as np,onnxruntime as ort,tokenizers
  assert 'torch' not in sys.modules and 'onnxruntime'+ort.__version__==P['runtime']
  for f in P['runtimeFiles']+P['modelFiles']:assert sha(f['file'])==f['sha256']
  assert sha(P['tokenizer'])==P['tokenizerSha256']
  models={Path(f['file']).name:f['file'] for f in P['modelFiles']}
  options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
  options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
  sessions=[ort.InferenceSession(models[n],sess_options=options,providers=['CPUExecutionProvider']) for n in ['encoder.int8.onnx','decoder.int8.onnx','joiner.int8.onnx']]
  assert all(s.get_providers()==['CPUExecutionProvider'] for s in sessions);encoder,decoder,joiner=sessions
  state['modelIo']=[dict(inputs=[dict(name=x.name,type=x.type,shape=x.shape) for x in s.get_inputs()],outputs=[dict(name=x.name,type=x.type,shape=x.shape) for x in s.get_outputs()]) for s in sessions]
  tokenizer=tokenizers.Tokenizer.from_file(P['tokenizer']);blank=8192;save(state='LOADED_FIXED_CPU_MODELS')
  dtype=lambda x:np.int64 if x.type=='tensor(int64)' else np.int32
  def call(s,values):
   state['newNeuralCalls']+=1;return s.run(None,{x.name:v for x,v in zip(s.get_inputs(),values,strict=True)})
  def dec(token,states):
   ins=decoder.get_inputs();values=[np.array([[token]],dtype=dtype(ins[0])),np.ones(1,dtype=dtype(ins[1])),*states]
   result=call(decoder,values);return result[0],[result[2],result[3]]
  def infer(features,length):
   ins=encoder.get_inputs();encoded,encoded_length=call(encoder,[np.ascontiguousarray(features.T[None,:,:]),np.array([length],dtype=dtype(ins[1]))])
   assert encoded.ndim==3 and encoded.shape[0]==1
   decoder_value,decoder_states=dec(blank,[np.zeros((2,1,640),np.float32),np.zeros((2,1,640),np.float32)])
   n=int(encoded_length.reshape(-1)[0]);assert 0<n<=encoded.shape[-1]
   tokens=[];t=0;this_frame=0
   while t<n:
    logits=call(joiner,[np.ascontiguousarray(encoded[:,:,t:t+1]),decoder_value])[0].reshape(-1)
    assert len(logits)==8198 and np.isfinite(logits).all()
    y=int(logits[:8193].argmax());skip=int(logits[8193:].argmax())
    if y!=blank:
     tokens.append(y);decoder_value,decoder_states=dec(y,decoder_states);this_frame+=1
    if skip>0:this_frame=0
    if this_frame>=5:this_frame=0;skip=1
    if y==blank and skip==0:this_frame=0;skip=1
    t+=skip
   return tokenizer.decode(tokens,skip_special_tokens=True),tokens
  for mode in P['modes']:
   matches=[]
   for case in P['cases']:
    f=next(f for f in case['features'] if f['mode']==mode);assert sha(f['file'])==f['sha256']
    features=np.load(f['file'],allow_pickle=False);assert list(features.shape)==f['shape']
    tick=time.perf_counter();text,tokens=infer(features,f['length']);seconds=time.perf_counter()-tick
    old=read(case['oldOutput']);assert sha(case['oldOutput'])==case['oldOutputSha256']
    match=canonical(text)==canonical(old['text']);matches.append(match)
    packet=dict(id=case['id'],mode=mode,audioSha256=case['audioSha256'],inputFrames=case['frames'],text=text,tokenIds=tokens,
     seconds=seconds,oldOutputMatch=match,wordsPostEdited=False,referenceUsed=False,featureSha256=f['sha256'],protocolSha256=sha(protocol))
    file=out/(mode+'--'+case['id']+'.json');atomic_json(file,packet);state['completed'].append(dict(file=str(file),sha256=sha(file)))
    save(state='DECODING_FIXED_FRONTEND_CONTRACT',mode=mode,activeCase=case['id'])
   if mode=='installed_frontend':
    save(baselineExactOutputMatches=sum(matches))
    if sum(matches)!=12:
     save(state='STOP_BASELINE_CONTRACT_NOT_REPRODUCED_NO_REFERENCE_FRONTEND_INFERENCE');atomic_json(out/'completed.json',state);raise SystemExit(78)
  save(state='COMPLETE_FIXED_FRONTEND_CONTRACT_PENDING_INDEPENDENT_SCORE',seconds=time.monotonic()-start)
  atomic_json(out/'completed.json',state);print(json.dumps(dict(state=state['state'],baselineExactOutputMatches=state['baselineExactOutputMatches'],completed=len(state['completed']),seconds=state['seconds'])))
except Exception as error:
 import traceback
 save(state='FAILED_FRONTEND_CONTRACT_RETAINED_NO_RETRY',error=repr(error),traceback=traceback.format_exc());atomic_json(out/'completed.json',state);raise
finally:done.set();pressure.close()
