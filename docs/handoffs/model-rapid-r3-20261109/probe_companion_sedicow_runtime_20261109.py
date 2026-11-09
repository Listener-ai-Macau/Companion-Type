"""Architecture/API check with tiny random parameters, never a quality benchmark."""
from pathlib import Path
import hashlib,importlib,json,os,sys,types,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261109-sedicow-r1';sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);start=time.perf_counter();sys.path.insert(0,'E:/CodexData/Companion/.model-cache/sedicow-runtime-20261109');source=json.loads((C/'source.json').read_text());root=Path(source['sourceRoot']);result={'state':'STARTED_TINY_ARCHITECTURE_ONLY','pretrainedWeightsLoaded':False,'realAudioRecognitionRun':False,'sourceRevision':source['revision']}
try:
 for row in source['files']:assert hashlib.sha256(Path(row['file']).read_bytes()).hexdigest()==row['sha256']
 import torch,transformers
 torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(0);assert transformers.__version__=='4.55.0'
 package=types.ModuleType('companion_pinned_sedicow');package.__path__=[str(root)];sys.modules[package.__name__]=package
 Config=importlib.import_module(package.__name__+'.config').DiCoWConfig
 Model=importlib.import_module(package.__name__+'.modeling_dicow').DiCoWForConditionalGeneration
 data=json.loads((root/'config.json').read_text());data.update(d_model=16,encoder_attention_heads=2,decoder_attention_heads=2,encoder_ffn_dim=32,decoder_ffn_dim=32,encoder_layers=2,num_hidden_layers=2,decoder_layers=1,scb_layers=1,max_source_positions=8);config=Config(**data);config._attn_implementation='eager';model=Model(config).eval();features=torch.randn(1,128,16);mask=torch.zeros(1,4,8);mask[:,1]=1
 with torch.inference_mode():output=model(input_features=features,stno_mask=mask,decoder_input_ids=torch.tensor([[50258,50259]]),enrollments={'input_features':features.clone(),'stno_mask':mask.clone()},return_dict=True)
 assert tuple(output.logits.shape)==(1,2,51866) and torch.isfinite(output.logits).all()
 result.update(state='PASS_TINY_SE_ENROLLMENT_STNO_FORWARD_NO_TRAINED_MODEL',torch=torch.__version__,transformers=transformers.__version__,logitsShape=list(output.logits.shape),allOutputsFinite=True,tinyParameterCount=sum(p.numel() for p in model.parameters()),installedGlobalRuntimeChanged=False)
except BaseException as exc:result.update(state='FAILED_TINY_ARCHITECTURE_CHECK',failureType=type(exc).__name__,reason=str(exc));raise
finally:result.update(seconds=time.perf_counter()-start,limits=limits.query(),saleQualified=False);(C/'runtime-probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
