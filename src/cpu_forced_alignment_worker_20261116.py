"""Native CPU-only classifier: toy load parity, then unchanged recognized public text."""
from pathlib import Path
from datetime import datetime
import argparse,ctypes,gc,hashlib,json,os,sys,time,wave
os.environ.update(OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from moss_windows_resource_limits_20261104 import WorkerLimits,CpuRate
from companion_windows_working_set_20261116 import WorkingSetCeiling
from practical_io_20261107 import atomic_json
from practical_alignment_text_20261107 import source_text_spans
from companion_cpu_aligner_loader_20261116 import load_cpu_aligner
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('--run',type=Path,required=True);a=p.parse_args();B=read(a.control/'binding.json')
 assert sha(__file__)==B['workerSha256']
 for file,digest in B['helpers'].items():assert sha(file)==digest
 limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);rate=CpuRate(5,2500)
 limits._check(limits.kernel.SetInformationJobObject(limits.job,15,ctypes.byref(rate),ctypes.sizeof(rate)))
 ws=WorkingSetCeiling(1879048192);assert 'torch' not in sys.modules;sys.path.insert(0,B['cpuTorchSite'])
 state={'state':'IMPORTING_OFFICIAL_CPU_TORCH_CLASSIFIER','startedAt':datetime.now().astimezone().isoformat(),'completed':[],'newNeuralCalls':0,
  'modelLoaded':False,'newWeightTraining':False,'referenceWordsRead':False,'speakerLabelsRead':False,'qualityQualified':False,'workingSetControl':ws.query()}
 def save():state['limits']=limits.query();atomic_json(a.run/'worker-state.json',state,progress=True)
 def check():
  if (a.run/'stop.request').exists() or datetime.now().astimezone()>=datetime.fromisoformat(B['neuralDeadline']):raise InterruptedError('Owned classifier stop/deadline; immutable recognized text retained')
 save();model=None
 try:
  import torch,transformers,numpy as np
  from transformers import AutoConfig,AutoModelForTokenClassification,AutoProcessor
  assert torch.__version__=='2.11.0+cpu' and torch.version.cuda is None and torch.version.hip is None and Path(torch.__file__).is_relative_to(Path(B['cpuTorchSite']))
  assert transformers.__version__=='5.22.1';torch.set_num_threads(4);torch.set_num_interop_threads(1)
  state.update(torchVersion=torch.__version__,torchModule=str(torch.__file__),cudaCompiled=False,hipCompiled=False,transformersVersion=transformers.__version__);save()
  if B.get('reuseTinyControl'):
   prior=B['reuseTinyControl'];assert sha(prior['file'])==prior['sha256'];proof=read(prior['file'])
   assert proof['state']=='PASS_CPU_STANDARD_AND_MAPPED_TINY_ALIGNER_EXACT_LOGITS' and proof['loaderSha256']==sha(Path(__file__).with_name('companion_cpu_aligner_loader_20261116.py'))
  else:
   check();torch.manual_seed(413);config=AutoConfig.from_pretrained(B['modelRoot'],local_files_only=True)
   for key,value in dict(d_model=32,encoder_layers=1,encoder_attention_heads=4,num_key_value_heads=4,encoder_ffn_dim=64,output_dim=32,downsample_hidden_size=8,n_window_infer=100).items():setattr(config.audio_config,key,value)
   for key,value in dict(hidden_size=32,intermediate_size=64,num_attention_heads=4,num_key_value_heads=2,head_dim=8,num_hidden_layers=2,layer_types=['full_attention']*2,vocab_size=64,max_position_embeddings=512).items():setattr(config.text_config,key,value)
   config.audio_token_id=7;config.pad_token_id=0;config.eos_token_id=[2];config.timestamp_token_id=9;config.num_labels=128
   original=AutoModelForTokenClassification.from_config(config,dtype=torch.bfloat16,attn_implementation='eager').eval().requires_grad_(False)
   tiny=a.run/'tiny';original.save_pretrained(tiny,safe_serialization=True);del original
   reference=AutoModelForTokenClassification.from_pretrained(tiny,local_files_only=True,dtype=torch.bfloat16,device_map='cpu',attn_implementation='eager').eval().requires_grad_(False)
   mapped,receipt=load_cpu_aligner(tiny,torch=torch,expected_sha256=sha(tiny/'model.safetensors'))
   inputs={'input_ids':torch.tensor([[1]+[7]*13+[9]],dtype=torch.long),'attention_mask':torch.ones((1,15),dtype=torch.long),
    'input_features':torch.randn((1,128,100),dtype=torch.bfloat16),'input_features_mask':torch.ones((1,100),dtype=torch.long)}
   with torch.inference_mode():left=reference(**inputs,use_cache=False).logits;right=mapped(**inputs,use_cache=False).logits
   assert torch.equal(left,right) and torch.equal(left.argmax(-1),right.argmax(-1))
   proof={'state':'PASS_CPU_STANDARD_AND_MAPPED_TINY_ALIGNER_EXACT_LOGITS','syntheticOnly':True,'speechQualityMeasured':False,'torchVersion':torch.__version__,
    'loaderSha256':sha(Path(__file__).with_name('companion_cpu_aligner_loader_20261116.py')),'weightRoundtrip':receipt,'gpuUsed':False}
   atomic_json(a.run/'tiny-control.json',proof);state['tinyControlPassed']=True;save();del reference,mapped,inputs,left,right;gc.collect()
  processor=AutoProcessor.from_pretrained(B['modelRoot'],local_files_only=True)
  for case in B['cases']:
   check();assert sha(case['wav'])==case['wavSha256'] and sha(case['rawAsrFile'])==case['rawAsrSha256'];assert read(case['rawAsrFile'])['hypothesis']==case['text']
   state.update(state='ALIGNING_RETAINED_PUBLIC_ASR_TEXT_CPU',activeCase=case['id']);save()
   if not case['text']:
    payload={'originalText':'','units':[],'allOriginalCharactersPreserved':True,'neuralInferencePerformed':False,'seconds':0.,'wordTimeAccuracyQualified':False}
   else:
    if model is None:
     check();model,receipt=load_cpu_aligner(B['modelRoot'],torch=torch,expected_sha256=B['modelSha256']);atomic_json(a.run/'weight-roundtrip.json',receipt);state.update(modelLoaded=True,modelLoadSeconds=receipt['seconds']);save()
    with wave.open(case['wav'],'rb') as source:
     assert (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getnframes())==(1,2,16000,case['frames'])
     samples=np.frombuffer(source.readframes(case['frames']),dtype='<i2').astype(np.float32)/32768
    inputs,words=processor.prepare_forced_aligner_inputs(audio=samples,transcript=case['text'],language=case['language'],processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':'cpu'}})
    mapping=source_text_spans(case['text'],words[0]);assert mapping is not None,'Cannot map tokenizer units; preserve text instead of substituting words'
    inputs=inputs.to('cpu',model.dtype);valid_frames=int(inputs['input_features_mask'].sum());assert valid_frames>=len(samples)//160
    tick=time.perf_counter()
    with torch.inference_mode():logits=model(**inputs,use_cache=False).logits
    elapsed=time.perf_counter()-tick;check();classes=logits.argmax(-1)[0][inputs['input_ids'][0]==model.config.timestamp_token_id].tolist();assert len(classes)==2*len(mapping)
    decoded=processor.decode_forced_alignment(logits=logits,input_ids=inputs['input_ids'],word_lists=words,timestamp_token_id=model.config.timestamp_token_id)[0]
    assert len(decoded)==len(mapping);units=[]
    for row,span in zip(decoded,mapping):
     assert row['text']==span['alignmentUnit'];start,end=row['start_time'],row['end_time'];valid=0<=start<end<=case['frames']/16000
     units.append({**span,'predictedStartSeconds':start,'predictedEndSeconds':end,'absoluteStartSeconds':case.get('sourceStartFrame',0)/16000+start if valid else None,
      'absoluteEndSeconds':case.get('sourceStartFrame',0)/16000+end if valid else None,'positiveAndInOriginalLeafBounds':valid,'timestampVerifiedAgainstTruth':False})
    assert ''.join(row['text'] for row in units)==case['text'];payload={'originalText':case['text'],'rawTimestampClassIds':classes,'units':units,'allOriginalCharactersPreserved':True,
     'neuralInferencePerformed':True,'seconds':elapsed,'inputNotTruncated':True,'validMelFrames':valid_frames,'unresolvedTimeUnits':sum(not r['positiveAndInOriginalLeafBounds'] for r in units),'wordTimeAccuracyQualified':False}
    state['newNeuralCalls']+=1;del logits,inputs,samples;gc.collect()
   file=a.run/(case['id']+'-alignment.json');atomic_json(file,{'case':case,'payload':payload,'modelSha256':B['modelSha256'],'gpuUsed':False,'qualityQualified':False})
   state['completed'].append({'id':case['id'],'file':str(file),'sha256':sha(file),'seconds':payload['seconds']});save()
  state.update(state='COMPLETE_NATIVE_CPU_ALIGNMENT_CHARACTERS_PRESERVED_NOT_TIME_QUALIFIED');state.pop('activeCase',None)
 except BaseException as error:state.update(state='INCOMPLETE_CPU_ALIGNMENT_RETAINED',error=repr(error));raise
 finally:state['finishedAt']=datetime.now().astimezone().isoformat();save()
 print(json.dumps({k:v for k,v in state.items() if k!='completed'},ensure_ascii=False))
if __name__=='__main__':main()
