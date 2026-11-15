"""Native joint architecture feasibility only; audio-only, no quality claim."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,time,wave
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['control','pilot'],required=True)
 for flag in ['control','inventory','run']:p.add_argument('--'+flag,type=Path,required=True)
 a=p.parse_args();limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
 B=read(a.control/'pilot-binding.json')
 assert B['workerSha256']==sha(__file__)
 for file,digest in B['helpers'].items():assert sha(file)==digest
 assert sha(a.control/'pilot-audio-only.json')==B['audioManifestSha256']
 state={'state':'STARTING_NATIVE_JOINT_'+a.phase.upper(),'startedAt':datetime.now().astimezone().isoformat(),
  'completed':[],'validationLabelsRead':False,'speakerCountHintUsed':False,'newWeightTraining':False,'qualityQualified':False}
 def save():state['limits']=limits.query();atomic_json(a.run/(a.phase+'-state.json'),state,progress=True)
 began=time.perf_counter();save()
 try:
  import torch
  torch.set_num_threads(1);torch.set_num_interop_threads(1)
  from moss_native_architecture_20261115 import tiny_loader_control,load_public_native
  if a.phase=='control':
   proof=tiny_loader_control(torch);atomic_json(a.run/'tiny-native-control.json',proof)
   state.update(state='PASS_NATIVE_JOINT_TINY_LOADING_CONTROL',neuralMeetingCalls=0)
  else:
   assert read(a.run/'tiny-native-control.json')['state']=='PASS_NATIVE_STANDARD_AND_BOUNDED_EMPTY_LOADER_EXACT_LOGITS'
   assert torch.version.hip and torch.cuda.device_count()==1
   gpu=torch.cuda.get_device_properties(0);assert 'RX 6800 XT' in gpu.name and gpu.gcnArchName.startswith('gfx1030')
   from companion_community1_adapter_20261115 import pin_rocm_blas
   state['blas']=pin_rocm_blas(Path(B['blas']),B['blasSha256'])
   P=read(a.control/'preparation.json')
   for asset in P['files']:assert sha(asset['file'])==asset['sha256']
   from transformers import AutoProcessor,StoppingCriteria,StoppingCriteriaList
   import numpy as np
   processor=AutoProcessor.from_pretrained(P['nativeModelRoot'],local_files_only=True,trust_remote_code=False)
   state.update(state='LOADING_OFFICIAL_NATIVE_JOINT_MODEL');save()
   model,receipt=load_public_native(a.control,P['nativeModelRoot'],torch=torch,device='cuda:0')
   atomic_json(a.run/'weight-roundtrip.json',receipt)
   for case in read(a.control/'pilot-audio-only.json'):
    assert set(case)=={'meeting','audio','audioSha256','frames','purpose'} and sha(case['audio'])==case['audioSha256']
    with wave.open(case['audio'],'rb') as wav:
     assert (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,16000) and wav.getnframes()==case['frames']
     samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
    state.update(state='RUNNING_NATIVE_JOINT_THREE_MINUTE_PORTABILITY',meeting=case['meeting']);save()
    inputs=processor.apply_transcription_request(audio=samples,processor_kwargs={'audio_kwargs':{'sampling_rate':16000}}).to('cuda:0',torch.bfloat16)
    length=inputs['input_ids'].shape[1]
    class StopOwned(StoppingCriteria):
     def __call__(self,input_ids,scores,**kwargs):
      if (a.run/'stop.request').exists():raise InterruptedError('Owned stop; exact source and raw output retained')
      return False
    torch.cuda.synchronize();tick=time.perf_counter()
    with torch.inference_mode():ids=model.generate(**inputs,max_new_tokens=4096,do_sample=False,logits_to_keep=1,stopping_criteria=StoppingCriteriaList([StopOwned()]))
    torch.cuda.synchronize();elapsed=time.perf_counter()-tick;generated=ids[0,length:].cpu().tolist()
    raw=processor.tokenizer.decode(generated,skip_special_tokens=False,clean_up_tokenization_spaces=False)
    parsed=processor.decode(ids[:,length:],return_format='parsed')[0]
    eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
    packet={'meeting':case['meeting'],'audioSha256':case['audioSha256'],'generatedIds':generated,'rawDecoded':raw,
     'parsedSegments':parsed,'naturalEos':bool(generated and generated[-1] in eos),'seconds':elapsed,
     'audioSeconds':case['frames']/16000,'audioInputTokens':length,'completeMeeting':False,
     'purpose':'Runtime/format feasibility. Not cross-meeting quality, not training or final acceptance.',
     'qualityQualified':False,'referenceUsed':False,'speakerCountsUsed':False}
    atomic_json(a.run/(case['meeting']+'-raw.json'),packet)
    assert packet['naturalEos'] and parsed,'Incomplete native output retained; no automatic retry'
    assert all(0<=r['Start']<r['End']<=case['frames']/16000+.5 for r in parsed),'Native timestamp format/duration invalid'
    state['completed'].append({'meeting':case['meeting'],'seconds':elapsed,'generatedTokens':len(generated),'segments':len(parsed),'naturalEos':True});save()
   state.update(state='PASS_TWO_LANGUAGE_NATIVE_JOINT_RUNTIME_PILOT_NOT_QUALITY')
 except BaseException as error:state.update(state='FAILED_NATIVE_JOINT_'+a.phase.upper()+'_RETAINED_NO_RETRY',error=repr(error));raise
 finally:
  state.update(finishedAt=datetime.now().astimezone().isoformat(),seconds=time.perf_counter()-began);save()
 print(json.dumps(state,ensure_ascii=False))
if __name__=='__main__':main()
