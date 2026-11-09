"""One real F32 self-enrolled target-ASR diagnostic with bounded CPU streaming."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,sys,time
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',HF_HUB_DISABLE_TELEMETRY='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
from practical_io_20261107 import atomic_json
from practical_qwen_bounded_decode_20261107 import repeated_block
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--control',required=True);a=p.parse_args();C=Path(a.control);P=read(C/'protocol.json');assert sha(__file__)==P['workerSha256'];limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();start=time.perf_counter();C.mkdir(exist_ok=True);state={'state':'STARTING_CPU_STREAMED_DIAGNOSTIC','pid':os.getpid(),'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'newNeuralCalls':0,'referencePassedToWorker':False,'training':False,'results':[],'trace':[],'saleQualified':False};checkpoint=None
 def save():state.update(wallSeconds=time.perf_counter()-start,limits=limits.query());atomic_json(C/'state.json',state)
 def progress(row):state['trace'].append(dict(row));state['lastBlock']=dict(row);save()
 save()
 try:
  assert not pressure.low(),'ActualWindowsLOWRAM before importing model'
  for row in P['supportSources']:assert sha(row['file'])==row['sha256']
  sys.path.insert(0,P['isolatedRuntime'])
  import torch,numpy as np,transformers
  torch.set_num_threads(1);torch.set_num_interop_threads(1);assert torch.__version__=='2.12.0+cpu' and transformers.__version__=='4.55.0'
  source=read(P['sourceManifest']);assert sha(P['sourceManifest'])==P['sourceManifestSha256']
  for row in source['files']:assert sha(row['file'])==row['sha256']
  from companion_sedicow_cpu_stream_20261109 import stream_model
  from companion_sedicow_decode_trace_20261109 import capture_raw_greedy_sequences
  from transformers import AutoTokenizer,GenerationConfig
  state['state']='VERIFYING_AND_STREAMING_ORIGINAL_F32_CHECKPOINT';save();model,checkpoint=stream_model(source['sourceRoot'],P['weightFile'],torch=torch,expected_sha256=source['weight']['sha256'],attention='sdpa',stop=pressure.low,progress=progress)
  tokenizer=AutoTokenizer.from_pretrained(source['sourceRoot'],local_files_only=True);model.tokenizer=tokenizer;model.generation_config=GenerationConfig.from_pretrained(source['sourceRoot'],local_files_only=True);assert model.generation_config.ctc_weight==0
  state.update(state='READY_REAL_TARGET_ASR',checkpoint=checkpoint.receipt(),attentionImplementation='sdpa',originalAuthorFloat32Weights=True,ctcOnlyModulesNotAllocatedBecauseAuthorGenerationWeightZero=True);save()
  job=read(C/'audio-only.json');assert sha(C/'audio-only.json')==P['inputManifestSha256']
  for key in ['originalAudio','enrollmentAudio','modelInputs']:assert sha(job[key])==job[key+'Sha256']
  with np.load(job['modelInputs'],allow_pickle=False) as arrays:
   tensor=lambda key:torch.from_numpy(arrays[key]);features=tensor('input_features');attention=tensor('attention_mask');mask=tensor('stno_mask');enroll={'input_features':tensor('enrollment_input_features'),'stno_mask':tensor('enrollment_stno_mask'),'attention_mask':tensor('enrollment_attention_mask')}
   if pressure.low():raise RuntimeError('ActualWindowsLOWRAM before target recognition')
   tick=time.perf_counter();state.update(state='RUNNING_REAL_TARGET_ASR',attemptedTarget=job['id']);save()
   with torch.inference_mode(),capture_raw_greedy_sequences(model) as trace:output=model.generate(input_features=features,attention_mask=attention,stno_mask=mask,enrollments=enroll,language='zh',task='transcribe',return_timestamps=True,do_sample=False)
  ids=output[0].detach().cpu().tolist();text=tokenizer.decode(ids,skip_special_tokens=True);raw={'id':job['id'],'sourceStartSample':job['sourceStartSample'],'sourceEndSample':job['sourceEndSample'],'audioSha256':job['originalAudioSha256'],'modelInputsSha256':job['modelInputsSha256'],'authorReconstructedIds':ids,'authorReconstructedWithSpecialTokens':tokenizer.decode(ids,skip_special_tokens=False),'rawGreedySequences':trace,'rawGreedyWithSpecialTokens':[[tokenizer.decode(row,skip_special_tokens=False) for row in call] for call in trace],'text':text,'seconds':time.perf_counter()-tick,'naturalEos':bool(trace and all(row and row[-1]==model.config.eos_token_id for call in trace for row in call)),'loop':any(repeated_block(row) for call in trace for row in call),'referencePassedToInference':False,'training':False,'dtypeConversion':False,'exactOriginalMixtureAudio':True,'separatedWaveformUsed':False,'checkpoint':checkpoint.receipt(),'attentionImplementation':'sdpa','saleQualified':False};atomic_json(C/'raw.json',raw);state['results'].append({'file':str(C/'raw.json'),'sha256':sha(C/'raw.json')});state['newNeuralCalls']=1
  if not raw['naturalEos'] or raw['loop']:raise RuntimeError('Unfinished or repeating raw decode retained without rewrite')
  state.update(state='COMPLETE_REAL_CPU_TARGET_ASR_NOT_QUALIFIED',text=text,checkpoint=checkpoint.receipt());save();print(json.dumps(raw,ensure_ascii=False),flush=True)
 except BaseException as exc:state.update(state='FAILED',failureType=type(exc).__name__,reason=str(exc));save();raise
 finally:
  if checkpoint is not None:checkpoint.stream.close()
if __name__=='__main__':main()
