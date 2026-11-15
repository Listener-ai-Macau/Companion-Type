"""Frozen speaker-conditioned separation smoke test; preserve mixture and raw output."""
import argparse,gc,hashlib,importlib.util,json,os,sys,time,wave
from pathlib import Path
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from automatic_speaker_cpu_worker_20261109 import sha,read,write

def main():
 p=argparse.ArgumentParser();p.add_argument('--control',required=True);a=p.parse_args();C=Path(a.control);P=read(C/'overlap-protocol.json');I=read(C/'overlap-audio-only.json')
 assert sha(__file__)==P['workerSha256'] and sha(C/'overlap-audio-only.json')==P['audioOnlySha256']
 limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();started=time.perf_counter();out=C/'extraction-result.json'
 result={'state':'STARTED','outputs':[],'weightsChanged':False,'answersRead':False,'inputBinding':P['audioOnlySha256']}
 write(out,result)
 def check():
  if pressure.low():raise RuntimeError('Windows actual low-memory notification; stop this worker')
 try:
  check()
  for key in ('encoderResult','encoderProtocol','baseAudioOnly'):assert sha(I[key])==I[key+'Sha256']
  E=read(I['encoderResult']);assert E['state']=='COMPLETE';B=read(I['baseAudioOnly']);ready=read(B['modelReady']);assert sha(B['modelReady'])==read(I['encoderProtocol'])['modelReadySha256']
  sys.path.insert(0,B['torchaudioSource'])
  import torch,numpy as np
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  sys.path.append('E:/CodexData/Companion/.model-cache/audio-tools')
  import soundfile as sf
  for file in ready['files']:assert sha(file['file'])==file['sha256']
  spec=importlib.util.spec_from_file_location('pinned_ps4_extraction',Path(ready['sourceRoot'])/'inference.py');author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
  base=author.build_model(torch.device('cpu'));checkpoint=torch.load(ready['weight'],map_location='cpu',weights_only=True,mmap=True);state=checkpoint.get('model',checkpoint.get('state_dict',checkpoint))
  if all(k.startswith('module.') for k in state):state={k[7:]:v for k,v in state.items()}
  base.load_state_dict(state,strict=True);assert all(torch.equal(v,state[k]) for k,v in base.state_dict().items());base.eval().requires_grad_(False);del checkpoint,state;gc.collect()
  from companion_tse_reference_bank_20261108 import encode_reference
  def load(packet):
   assert sha(packet['audio'])==packet['audioSha256']
   with wave.open(packet['audio'],'rb') as f:
    assert (f.getnchannels(),f.getframerate(),f.getsampwidth())==(1,16000,2)
    x=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype('float32')/32768
   return torch.from_numpy(x).unsqueeze(0)
  output=Path(I['outputDirectory']);output.mkdir(exist_ok=False)
  groups={}
  for row in E['vectors']:
   if row['kind']=='profiles':groups.setdefault(row['nativePerson'],[]).append(torch.tensor(row['vector']).unsqueeze(0))
  prototypes={key:torch.stack(values).mean(0) for key,values in groups.items()}
  # One fresh same-input forward comparison validates the direct embedding branch.
  example=I['cases'][0];x=load(example);peak=x.abs().max();x=x/peak;enroll=load(B['profiles'][0]);enroll=enroll/enroll.abs().max()
  with torch.inference_mode():
   original,_=base(x,enroll);vector=encode_reference(base,enroll,torch=torch);base.joint_training=False;direct,_=base(x,vector)
  error=float((original-direct).abs().max());assert torch.allclose(original,direct,rtol=1e-5,atol=1e-6)
  result['directConditioningAuthorForwardProof']={'sameAudio':True,'maximumAbsoluteWaveformDifference':error,'allcloseRtol':1e-5,'allcloseAtol':1e-6}
  for case in I['cases']:
   check();waveform=load(case);peak=waveform.abs().max();assert float(peak)>0
   for person in case['targetNativePeople']:
    check();tick=time.perf_counter()
    with torch.inference_mode():extracted,_=base(waveform/peak,prototypes[person]);extracted=extracted*peak
    assert extracted.shape==waveform.shape and torch.isfinite(extracted).all()
    value=extracted[0].numpy();stem=case['id']+'-native-'+person;raw=output/(stem+'-raw-f32.wav');pcm=output/(stem+'-pcm16.wav')
    sf.write(str(raw),value,16000,subtype='FLOAT');sf.write(str(pcm),value,16000,subtype='PCM_16')
    checkraw,sr=sf.read(str(raw),dtype='float32');assert sr==16000 and np.array_equal(checkraw,value)
    row={'case':case['id'],'nativePerson':person,'sourceStartSample':case['sourceStartSample'],'sourceEndSample':case['sourceEndSample'],'frames':len(value),'audioSeconds':len(value)/16000,'inputSha256':case['audioSha256'],'rawFloatAudio':str(raw),'rawFloatSha256':sha(raw),'rawFloatReadbackBitExact':True,'pcmAudio':str(pcm),'pcmSha256':sha(pcm),'pcmClippedSampleCount':int(np.count_nonzero((value>=1)|(value< -1))),'extractionSeconds':time.perf_counter()-tick,'rms':float(np.sqrt(np.mean(value**2)))}
    result['outputs'].append(row);result.update(state='RUNNING',elapsedSeconds=time.perf_counter()-started,limits=limits.query());write(out,result);print(json.dumps(row,ensure_ascii=False),flush=True)
  result.update(state='COMPLETE_TARGETED_SEPARATION_NOT_ASR_QUALIFIED',elapsedSeconds=time.perf_counter()-started,limits=limits.query(),originalAudioUnchanged=all(sha(c['audio'])==c['audioSha256'] for c in I['cases']),contentRecoveryAccuracyMeasured=False,productDefaultChanged=False,saleQualified=False);write(out,result)
 except BaseException as exc:
  result.update(state='FAILED',error=type(exc).__name__+': '+str(exc),elapsedSeconds=time.perf_counter()-started,limits=limits.query());write(out,result);raise
if __name__=='__main__':main()
