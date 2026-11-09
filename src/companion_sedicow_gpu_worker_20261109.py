"""One fixed self-enrolled target-ASR pilot, no automatic CPU fallback or training."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,sys,time
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',HF_HUB_DISABLE_TELEMETRY='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import repeated_block
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--all-targets',action='store_true');a=p.parse_args();C=Path(a.control);P=read(C/'gpu-protocol.json');assert sha(__file__)==P['workerSha256'];limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();out=C/('all-targets' if a.all_targets else 'pilot');out.mkdir(exist_ok=False);start=time.perf_counter();state={'state':'CHECKING_DEDICATED_GPU','pid':os.getpid(),'referencePassedToWorker':False,'newNeuralCalls':0,'results':[]}
 def save():state.update(limits=limits.query(),wallSeconds=time.perf_counter()-start);atomic_json(out/'state.json',state)
 save()
 try:
  if pressure.low():raise RuntimeError('ActualWindowsLOWRAM beforemodel')
  assert sha(C/'input-protocol.json')==P['inputProtocolSha256'] and sha(C/'audio-only-inputs.json')==P['audioOnlyInputsSha256']
  sys.path.insert(0,P['isolatedTransformersRuntime'])
  import torch,numpy as np,transformers
  torch.set_num_threads(1);torch.set_num_interop_threads(1);assert transformers.__version__=='4.55.0' and torch.version.hip
  devices=[torch.cuda.get_device_properties(i) for i in range(torch.cuda.device_count())];choices=[i for i,d in enumerate(devices) if 'RX 6800 XT' in d.name and d.gcnArchName.startswith('gfx1030')];assert len(choices)==1,'Unique external6800XT required; no integratedorCPU fallback';device='cuda:'+str(choices[0]);torch.cuda.set_device(choices[0]);state.update(gpu=devices[choices[0]].name,state='LOADING_EXACT_AUTHOR_F32_WEIGHTS');save()
  source=read(C/'source.json');weights=read(C/'weight-download.json');assert weights['state']=='READY_PINNED_SE_DICOW_WEIGHTS_NOT_INFERRED' and weights['sha256']==source['weight']['sha256']
  for row in source['files']:assert sha(row['file'])==row['sha256']
  for row in P['supportSources']:assert sha(row['file'])==row['sha256']
  from companion_sedicow_checkpoint_20261109 import load_model
  from companion_sedicow_decode_trace_20261109 import capture_raw_greedy_sequences
  model,receipt=load_model(source['sourceRoot'],weights['weightFile'],torch=torch,device=device,expected_sha256=weights['sha256']);atomic_json(out/'weight-roundtrip.json',receipt)
  from transformers import AutoTokenizer,GenerationConfig
  tokenizer=AutoTokenizer.from_pretrained(source['sourceRoot'],local_files_only=True)
  tokenizer.upper_cased_tokens={}
  vocab=tokenizer.get_vocab()
  for token,index in vocab.items():
   if not token:continue
   lower=(token[0]+token[1].lower()+token[2:]) if token[0]=='Ġ' and len(token)>1 else token[0].lower()+token[1:]
   if lower!=token and lower in vocab:tokenizer.upper_cased_tokens[vocab[lower]]=index
  # set_tokenizer also creates a ~300MiB training-only timestamp smoothing
  # matrix. Forward with labels=None and generation never read that helper.
  # Keep all inference tokenizer inputs while avoiding that unused allocation.
  model.tokenizer=tokenizer
  model.generation_config=GenerationConfig.from_pretrained(source['sourceRoot'],local_files_only=True)
  jobs=read(C/'audio-only-inputs.json');jobs=[j for j in jobs if a.all_targets or j['pilot']];state.update(state='READY_SPEAKER_CONDITIONED_ASR',jobs=len(jobs),authorFloat32WeightsPreserved=True);save()
  for job in jobs:
   if pressure.low():raise RuntimeError('ActualWindowsLOWRAM stopbeforenexttarget')
   assert sha(job['modelInputs'])==job['modelInputsSha256'] and sha(job['originalAudio'])==job['originalAudioSha256'] and sha(job['enrollmentAudio'])==job['enrollmentAudioSha256']
   arrays=np.load(job['modelInputs'],allow_pickle=False);tensor=lambda key:torch.from_numpy(arrays[key]).to(device=device);features=tensor('input_features');mask=tensor('stno_mask');attention=tensor('attention_mask');enroll={'input_features':tensor('enrollment_input_features'),'stno_mask':tensor('enrollment_stno_mask'),'attention_mask':tensor('enrollment_attention_mask')};tick=time.perf_counter()
   with torch.inference_mode(),capture_raw_greedy_sequences(model) as trace:tokens=model.generate(input_features=features,attention_mask=attention,stno_mask=mask,enrollments=enroll,language='zh',task='transcribe',return_timestamps=True,do_sample=False)
   ids=tokens[0].detach().cpu().tolist();text=tokenizer.decode(ids,skip_special_tokens=True);raw={'id':job['id'],'sourceStartSample':job['sourceStartSample'],'sourceEndSample':job['sourceEndSample'],'sourceAudioSha256':job['originalAudioSha256'],'conditioningInputSha256':job['modelInputsSha256'],'authorReconstructedIds':ids,'authorReconstructedWithSpecialTokens':tokenizer.decode(ids,skip_special_tokens=False),'rawGreedySequences':trace,'rawGreedyWithSpecialTokens':[[tokenizer.decode(row,skip_special_tokens=False) for row in call] for call in trace],'text':text,'seconds':time.perf_counter()-tick,'endedWithEos':bool(trace and all(row and row[-1]==model.config.eos_token_id for call in trace for row in call)),'loop':any(repeated_block(row) for call in trace for row in call),'referencePassedToModel':False,'checkpointSha256':weights['sha256'],'exactOriginalMixtureInput':True,'waveformSeparationBeforeAsr':False};path=out/(job['id']+'.json');atomic_json(path,raw);state['results'].append({'id':job['id'],'file':str(path),'sha256':sha(path)});state['newNeuralCalls']+=1;save();print(json.dumps({'id':job['id'],'text':text,'seconds':raw['seconds']},ensure_ascii=False),flush=True)
   if raw['loop'] or not raw['endedWithEos']:raise RuntimeError('Rawfaileddecode retained; no repetitionfix/referencebasedrewrite')
   del features,mask,attention,enroll,tokens,arrays;time.sleep(1)
  state.update(state='COMPLETE_TARGET_ASR_PILOT_NOT_QUALIFIED',finishedAt=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),saleQualified=False);save()
 except BaseException as exc:state.update(state='FAILED',failureType=type(exc).__name__,reason=str(exc));save();raise
if __name__=='__main__':main()
