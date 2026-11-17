"""One pinned publisher sample, same CPU configuration; no parameter change."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,os,re,requests,sys,threading,time,wave
os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='-1',HIP_VISIBLE_DEVICES='-1')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from meeting_acoustic_worker_20261116 import own_limits
from companion_local_pcm_session_20261114 import exclusive_file
from durable_model_state_20261117 import atomic_json
from moss_windows_resource_limits_20261104 import SystemRamPressure
limits=own_limits(25)
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
P=read(C/'selected-cpu-segmentation-protocol-r1.json');meta=read(C/'parakeet-cpu-export-asset-metadata.json')
out=C/'selected-cpu-publisher-control-r1';out.mkdir(exist_ok=False)
source=next(x for x in meta['siblings'] if x['rfilename']=='test_wavs/en.wav')
url=f'https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/resolve/{P["modelRevision"]}/test_wavs/en.wav'
r=requests.get(url,timeout=(10,20));r.raise_for_status();data=r.content;assert len(data)==source['size']<1024**2
assert hashlib.sha256(data).hexdigest()==source['lfs']['sha256'] if 'lfs' in source else hashlib.sha1(('blob '+str(len(data))+'\0').encode()+data).hexdigest()==source['blobId']
audio=out/'publisher-en.wav';audio.write_bytes(data)
pressure=SystemRamPressure();closed=threading.Event();start=time.monotonic();state=dict(state='PREPARING_PUBLISHER_POSITIVE_CONTROL',pid=os.getpid(),newTrainingUpdates=0,newNeuralCalls=0,qualityQualified=False)
def save(**v):
 state.update(v,at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
def watch():
 import psutil
 while not closed.wait(.5):
  if pressure.low() or psutil.virtual_memory().available<P['minimumAvailableBytes'] or time.monotonic()-start>60:
   save(state='STOPPED_PUBLISHER_CONTROL_RESOURCE_OR60S_BOUND');atomic_json(out/'completed.json',state);os._exit(76)
try:
 with exclusive_file(Path(P['neuralLock'])):
  save();threading.Thread(target=watch,daemon=True).start()
  import numpy as np,sherpa_onnx
  models={Path(f['file']).name:f['file'] for f in P['modelFiles']}
  rec=sherpa_onnx.OfflineRecognizer.from_transducer(encoder=models['encoder.int8.onnx'],decoder=models['decoder.int8.onnx'],joiner=models['joiner.int8.onnx'],tokens=models['tokens.txt'],num_threads=2,provider='cpu',model_type='nemo_transducer',decoding_method='greedy_search')
  with wave.open(str(audio),'rb') as w:
   assert w.getnchannels()==1 and w.getsampwidth()==2;rate=w.getframerate();pcm=w.readframes(w.getnframes())
  samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768;stream=rec.create_stream();stream.accept_waveform(rate,samples)
  state['newNeuralCalls']=1;tick=time.perf_counter();rec.decode_stream(stream);text=stream.result.text
  expected='ask not what your country can do for you ask what you can do for your country'
  save(state='COMPLETE_PINNED_PUBLISHER_SAMPLE_CONTROL',text=text,publisherExpectedTokens=expected.split(),
   publisherExampleTextMatches=re.findall('[a-z]+',text.lower())==expected.split(),seconds=time.perf_counter()-tick,
   audioSha256=hashlib.sha256(data).hexdigest(),sourceUrl=url,modelRevision=P['modelRevision'],
   modelConfigurationChanged=False,productAcceptance=False)
  atomic_json(out/'completed.json',state);print(json.dumps(state,ensure_ascii=False))
except BaseException as error:
 save(state='FAILED_PUBLISHER_CONTROL_RETAINED',error=repr(error));atomic_json(out/'completed.json',state);raise
finally:closed.set();pressure.close()
