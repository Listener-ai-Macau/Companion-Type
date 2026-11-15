"""Original whole-meeting speaker model, bounded exact frontend; no gold input."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,wave,gc,importlib.util,tarfile
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from companion_local_pcm_session_20261114 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser()
 for flag in ['control','inventory','run']:p.add_argument('--'+flag,type=Path,required=True)
 a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 binding=read(a.control/'worker-binding.json');P=read(a.control/'protocol.json')
 assert binding['workerSha256']==sha(__file__) and sha(a.control/'protocol.json')==binding['protocolSha256']
 for file,digest in binding['helpers'].items():assert sha(file)==digest
 assert sha(a.control/'audio-only.json')==P['audioOnlySha256'];cases=read(a.control/'audio-only.json')
 assert len(cases)==2 and all(set(c)=={'meeting','audio','audioSha256'} for c in cases)
 state={'state':'PREPARING_STAGE_A_WHOLE_MEETING_SPEAKER','startedAt':datetime.now().astimezone().isoformat(),
  'completed':[],'goldRead':False,'newTraining':False,'qualityQualified':False,'automaticRetries':0}
 def save():state.update(limits=limits.query());atomic_json(a.run/'speaker-state.json',state)
 began=time.perf_counter();save()
 try:
  import torch,numpy as np,yaml
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  assert torch.version.hip and torch.cuda.device_count()==1
  gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
  from public_nemotron_adaptation_20261115 import load_original,collect
  from companion_community1_adapter_20261115 import pin_rocm_blas
  from disk_nemotron_frontend_20261115 import extract_wave
  state['blas']=pin_rocm_blas(Path(P['blas']),P['blasSha256'])
  spec=importlib.util.spec_from_file_location('original_stageA_frontend',P['converter']);up=importlib.util.module_from_spec(spec);spec.loader.exec_module(up)
  with tarfile.open(P['checkpoint']) as archive:config=yaml.safe_load(archive.extractfile('model_config.yaml').read())
  extractor=up.build_feature_extractor(config)
  # Before full data: direct upstream vs disk extraction on61.003s, including
  # multiple block boundaries, global first/last samples and the masked tail.
  case=cases[0];assert sha(case['audio'])==case['audioSha256']
  with wave.open(case['audio'],'rb') as wav:pcm=wav.readframes(976048)
  control=a.run/'frontend-control.wav'
  with wave.open(str(control),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000);out.writeframes(pcm)
  reference=extractor(np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768,sampling_rate=16000,return_tensors='pt')['input_features'][0].numpy()
  extract_wave(extractor,control,a.run/'frontend-control.npy',torch=torch)
  actual=np.load(a.run/'frontend-control.npy',allow_pickle=False)
  exact=np.array_equal(actual,reference);difference=float(np.max(np.abs(actual-reference)))
  atomic_json(a.run/'frontend-control.json',{'state':'PASS_EXACT' if exact else 'FAIL_DIFFERENT','maxAbsDifference':difference,
   'frames':len(reference),'upstreamFeatureSourceSha256':sha(importlib.util.find_spec(type(extractor).__module__).origin)})
  assert exact,'Disk frontend must be bitwise exact before model inference'
  del reference,actual;gc.collect()
  prepared=[]
  for case in cases:
   assert sha(case['audio'])==case['audioSha256'];directory=a.run/case['meeting'];directory.mkdir()
   state.update(state='PREPARING_EXACT_DISK_FEATURES',activeMeeting=case['meeting']);save()
   path=directory/'features.npy';receipt=extract_wave(extractor,case['audio'],path,torch=torch)
   prepared.append({**case,'features':str(path),'featuresSha256':sha(path),**receipt})
  atomic_json(a.run/'features.json',prepared);gc.collect()
  state.update(state='LOADING_ORIGINAL_WHOLE_MEETING_SPEAKER');save()
  model,activity,receipt=load_original(P);atomic_json(a.run/'weight-roundtrip.json',receipt)
  def stop():
   if (a.run/'stop.request').exists():raise InterruptedError('Owned stop; raw data retained')
  for case in prepared:
   state.update(state='RUNNING_ORIGINAL_WHOLE_MEETING_SPEAKER',activeMeeting=case['meeting']);save()
   def progress(first,last):state.update(completedFrames=last);save()
   logits,aux=collect(model,activity,case,stop=stop,progress=progress)
   probabilities=torch.from_numpy(logits).sigmoid().numpy();directory=a.run/case['meeting']
   for name,value in [('logits',logits),('probabilities',probabilities),('activity-logits',aux)]:
    with (directory/(name+'.npy')).open('xb') as f:np.save(f,value,allow_pickle=False);f.flush();os.fsync(f.fileno())
   state['completed'].append({'meeting':case['meeting'],'audioSha256':case['audioSha256'],
    'featuresSha256':case['featuresSha256'],'probabilities':str(directory/'probabilities.npy'),
    'probabilitiesSha256':sha(directory/'probabilities.npy'),'frames':case['frames'],'validFrames':case['validFrames']});save()
   del logits,aux,probabilities;gc.collect()
  state.update(state='COMPLETE_STAGE_A_ORIGINAL_WHOLE_SPEAKER_UNQUALIFIED')
 except BaseException as error:state.update(state='INCOMPLETE_STAGE_A_SPEAKER_RETAINED_NO_RETRY',error=repr(error));raise
 finally:
  state.update(seconds=time.perf_counter()-began,finishedAt=datetime.now().astimezone().isoformat());save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
