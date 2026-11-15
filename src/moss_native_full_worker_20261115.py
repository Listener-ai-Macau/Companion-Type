"""One complete-session joint model comparison, no reference inputs or resets."""
from pathlib import Path
from datetime import datetime
import argparse,gc,hashlib,json,os,time,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['execution-control','full'],required=True)
 for flag in ['control','inventory','run']:p.add_argument('--'+flag,type=Path,required=True)
 a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 B=read(a.control/'full-binding.json');assert B['workerSha256']==sha(__file__)
 for file,digest in B['helpers'].items():assert sha(file)==digest
 assert sha(a.control/'full-audio-only.json')==B['audioManifestSha256']
 state={'state':'STARTING_NATIVE_JOINT_'+a.phase.upper(),'startedAt':datetime.now().astimezone().isoformat(),
  'completed':[],'referenceRead':False,'speakerCountHintUsed':False,'qualityQualified':False,'newWeightTraining':False,'automaticRetries':0}
 def save():state['limits']=limits.query();atomic_json(a.run/(a.phase+'-state.json'),state,progress=True)
 began=time.perf_counter();save()
 try:
  import torch,numpy as np
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  assert torch.version.hip and torch.cuda.device_count()==1
  gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
  from companion_community1_adapter_20261115 import pin_rocm_blas
  state['blas']=pin_rocm_blas(Path(B['blas']),B['blasSha256'])
  from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
  from moss_native_full_execution_20261115 import prepare_wave,attention_control,install_native_bounded
  P=read(a.control/'preparation.json')
  for asset in P['files']:assert sha(asset['file'])==asset['sha256']
  processor=AutoProcessor.from_pretrained(P['nativeModelRoot'],local_files_only=True,trust_remote_code=False)
  if a.phase=='execution-control':
   result=attention_control(torch);atomic_json(a.run/'attention-control.json',result)
   case=read(a.control/'pilot-audio-only.json')[0]
   with wave.open(case['audio'],'rb') as w:pcm=w.readframes(976048)
   target=a.run/'frontend-control.wav'
   with wave.open(str(target),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm)
   samples=np.frombuffer(pcm,dtype='<i2').astype(np.float32)/32768
   expected=processor.apply_transcription_request(audio=samples,processor_kwargs={'audio_kwargs':{'sampling_rate':16000}})
   actual,receipt=prepare_wave(processor,target,a.run/'frontend-proof',torch=torch)
   errors={};exact={}
   for key in expected:
    assert actual[key].shape==expected[key].shape
    if key=='input_features':
     error=float((actual[key]-expected[key]).abs().max());assert error<=1e-5,error;errors[key]=error
    else:assert torch.equal(actual[key],expected[key]),key
    exact[key]=torch.equal(actual[key],expected[key])
   receipt.update(state='PASS_NATIVE_WHOLE_REQUEST_CHUNK_FEATURE_AND_TOKEN_LAYOUT',maxAbsDifferences=errors,
    elementwiseEqualIgnoringMaskStorageDtype=exact,partialLastWindowIncluded=True,originalPaddingMaskDtype=str(expected['padding_mask'].dtype),
    boundedPaddingMaskDtype=str(actual['padding_mask'].dtype))
   atomic_json(a.run/'frontend-control.json',receipt)
   state.update(state='PASS_NATIVE_JOINT_LONG_EXECUTION_CONTROLS')
  else:
   assert read(a.run/'execution-control-state.json')['state']=='PASS_NATIVE_JOINT_LONG_EXECUTION_CONTROLS'
   from moss_native_architecture_20261115 import load_public_native
   state.update(state='LOADING_NATIVE_COMPLETE_MEETING_MODEL');save()
   model,receipt=load_public_native(a.control,P['nativeModelRoot'],torch=torch,device='cuda:0')
   atomic_json(a.run/'weight-roundtrip.json',receipt)
   last_save=[0.]
   def check_stop():
    if (a.run/'stop.request').exists():raise InterruptedError('Owned stop; sources, partial generated IDs and completed meetings retained')
   def encoder_progress(done,total):
    check_stop();state.update(state='ENCODING_ALL_ORIGINAL_WHISPER_WINDOWS',encoderDone=done,encoderTotal=total);save()
   def attention_progress(stats):
    check_stop()
    if time.monotonic()-last_save[0]>10:
     state.update(state='JOINT_WHOLE_CONTEXT_PREFILL_OR_DECODE',executionStats=dict(stats));save();last_save[0]=time.monotonic()
   stats=install_native_bounded(model,torch=torch,encoder_progress=encoder_progress,attention_progress=attention_progress)
   for case in read(a.control/'full-audio-only.json'):
    check_stop();assert set(case)=={'meeting','audio','audioSha256','audioSeconds','frames'}
    assert sha(case['audio'])==case['audioSha256']
    state.update(state='PREPARING_COMPLETE_ORIGINAL_RECORDING',meeting=case['meeting'],generatedTokens=0);save()
    inputs,input_receipt=prepare_wave(processor,case['audio'],a.run/'inputs'/case['meeting'],torch=torch)
    assert input_receipt['frames']==case['frames'] and input_receipt['audioSeconds']==case['audioSeconds']
    atomic_json(a.run/(case['meeting']+'-input.json'),input_receipt)
    inputs=inputs.to('cuda:0',torch.bfloat16);length=inputs['input_ids'].shape[1]
    encoder_calls_before=stats['encoderCalls'];tick=time.perf_counter();last_token_save=[0.]
    class StopOwned(StoppingCriteria):
     def __call__(self,input_ids,scores,**kwargs):
      check_stop();n=input_ids.shape[1]-length
      if n==1 or time.monotonic()-last_token_save[0]>10:
       generated=input_ids[0,length:].cpu().tolist()
       state.update(state='DECODING_COMPLETE_MEETING_JOINT_WORDS_AND_PEOPLE',generatedTokens=n,executionStats=dict(stats));save()
       atomic_json(a.run/(case['meeting']+'-partial-ids.json'),{'audioSha256':case['audioSha256'],
        'generatedIds':generated,'notFinal':True,'qualityQualified':False})
       last_token_save[0]=time.monotonic()
      return False
    with torch.inference_mode():ids=model.generate(**inputs,max_new_tokens=32768,do_sample=False,logits_to_keep=1,
     stopping_criteria=StoppingCriteriaList([StopOwned()]))
    torch.cuda.synchronize();elapsed=time.perf_counter()-tick;generated=ids[0,length:].cpu().tolist()
    raw=processor.tokenizer.decode(generated,skip_special_tokens=False,clean_up_tokenization_spaces=False)
    parsed=processor.decode(ids[:,length:],return_format='parsed')[0]
    eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
    packet={'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
     'generatedIds':generated,'rawDecoded':raw,'parsedSegments':parsed,'naturalEos':bool(generated and generated[-1] in eos),
     'seconds':elapsed,'inputTokens':length,'completeOriginalRecordingInput':True,'noSpeakerResetOrContextTruncation':True,
     'timestampOutOfBoundsSegments':[i for i,r in enumerate(parsed) if not 0<=r['Start']<r['End']<=case['audioSeconds']],
     'referenceUsed':False,'speakerCountsUsed':False,'newWeightTraining':False,'qualityQualified':False,
     'executionStats':dict(stats)}
    atomic_json(a.run/(case['meeting']+'-raw.json'),packet)
    assert stats['encoderCalls']-encoder_calls_before==1,'Native decoder unexpectedly re-encoded audio'
    state['completed'].append({'meeting':case['meeting'],'seconds':elapsed,'generatedTokens':len(generated),
     'segments':len(parsed),'naturalEos':packet['naturalEos'],'timestampOutOfBounds':len(packet['timestampOutOfBoundsSegments'])});save()
    del inputs,ids,parsed,generated;gc.collect();torch.cuda.empty_cache()
   state.update(state='COMPLETE_FOUR_WHOLE_MEETING_JOINT_OUTPUTS_SCORING_PENDING')
 except BaseException as error:state.update(state='FAILED_NATIVE_JOINT_'+a.phase.upper()+'_RETAINED_NO_RETRY',error=repr(error));raise
 finally:state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began);save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
