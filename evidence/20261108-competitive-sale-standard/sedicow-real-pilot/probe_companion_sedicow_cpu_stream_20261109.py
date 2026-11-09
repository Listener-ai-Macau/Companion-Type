"""Tiny model equality check before a real CPU-streamed diagnostic."""
from pathlib import Path
import hashlib,json,os,sys,time
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261109-sedicow-r1';sys.path.insert(0,str(M/'src'));sys.path.insert(0,'E:/CodexData/Companion/.model-cache/sedicow-runtime-20261109')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();tick=time.perf_counter();out={'state':'STARTED_CPU_STREAM_PARITY','trainedModelInferred':False,'saleQualified':False}
try:
 assert not pressure.low()
 import torch
 from companion_sedicow_checkpoint_20261109 import load_model
 from companion_sedicow_cpu_stream_20261109 import stream_model
 torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(9)
 source=json.loads((C/'source.json').read_text());root=source['sourceRoot'];tiny=Path('E:/CodexData/Companion/.model-cache/sedicow-20261109/tiny-random-checkpoint.safetensors');digest=hashlib.sha256(tiny.read_bytes()).hexdigest();override=dict(d_model=16,encoder_attention_heads=2,decoder_attention_heads=2,encoder_ffn_dim=32,decoder_ffn_dim=32,encoder_layers=2,num_hidden_layers=2,decoder_layers=1,scb_layers=1,max_source_positions=8)
 reference,receipt=load_model(root,tiny,torch=torch,device='cpu',expected_sha256=digest,config_override=override)
 x=torch.randn(1,128,16);mask=torch.rand(1,4,8);mask/=mask.sum(dim=1,keepdim=True);kwargs=dict(input_features=x,stno_mask=mask,decoder_input_ids=torch.tensor([[50258,50260,50360]]),enrollments={'input_features':x.clone(),'stno_mask':mask.clone()},return_dict=True)
 with torch.inference_mode():expected=reference(**kwargs).logits
 results=[]
 for attention in ['eager','sdpa']:
  candidate,checkpoint=stream_model(root,tiny,torch=torch,expected_sha256=digest,attention=attention,config_override=override,stop=pressure.low)
  with torch.inference_mode():actual=candidate(**kwargs).logits
  equal=torch.equal(expected,actual);maximum=(expected-actual).abs().max().item();assert equal if attention=='eager' else torch.allclose(expected,actual,atol=1e-6,rtol=1e-5)
  assert len(candidate._cpu_stream_trace)==4 and all(r['state']=='RELEASED' for r in candidate._cpu_stream_trace[:3]) and candidate._cpu_stream_trace[-1]['state']=='RESIDENT_AFTER_ENCODER'
  results.append({'attention':attention,'bitExact':equal,'maxAbsError':maximum,'allcloseAtol':1e-6,'allcloseRtol':1e-5,'streamTrace':candidate._cpu_stream_trace,'weightReceipt':checkpoint.receipt()});checkpoint.stream.close();del candidate
 out.update(state='PASS_TINY_STREAMED_EAGER_EXACT_SDPA_TOLERANCE',results=results,realWeightOrAudioInference=False)
except BaseException as exc:out.update(state='FAILED',failureType=type(exc).__name__,reason=str(exc));raise
finally:out.update(seconds=time.perf_counter()-tick,limits=limits.query());(C/'cpu-stream-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(out),flush=True)
