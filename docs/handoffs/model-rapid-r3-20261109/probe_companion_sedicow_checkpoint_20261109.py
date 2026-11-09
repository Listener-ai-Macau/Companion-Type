"""Exact tiny load/generation plumbing, then real checkpoint metadata only."""
from pathlib import Path
import hashlib,json,os,struct,sys,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261109-sedicow-r1';sys.path.insert(0,str(M/'src'));sys.path.insert(0,'E:/CodexData/Companion/.model-cache/sedicow-runtime-20261109')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);pressure=SystemRamPressure();start=time.perf_counter();result={'state':'STARTED_CHECKPOINT_PLUMBING','realPretrainedTensorBytesLoaded':0,'realAudioRecognitionRun':False,'saleQualified':False}
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
try:
 assert not pressure.low()
 import torch,transformers
 from safetensors.torch import save_model
 from companion_sedicow_checkpoint_20261109 import author_classes,load_model
 from companion_sedicow_decode_trace_20261109 import capture_raw_greedy_sequences
 torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.manual_seed(0)
 source=read(C/'source.json');root=Path(source['sourceRoot']);Config,Model=author_classes(root)
 overrides=dict(d_model=16,encoder_attention_heads=2,decoder_attention_heads=2,encoder_ffn_dim=32,decoder_ffn_dim=32,encoder_layers=2,num_hidden_layers=2,decoder_layers=1,scb_layers=1,max_source_positions=8)
 data=read(root/'config.json');data.update(overrides);config=Config(**data);config._attn_implementation='eager';original=Model(config).eval()
 features=torch.randn(1,128,16);mask=torch.zeros(1,4,8);mask[:,1]=1;kw=dict(input_features=features,stno_mask=mask,decoder_input_ids=torch.tensor([[50258,50260]]),enrollments={'input_features':features.clone(),'stno_mask':mask.clone()},return_dict=True)
 with torch.inference_mode():expected=original(**kw).logits.clone()
 tiny=Path('E:/CodexData/Companion/.model-cache/sedicow-20261109/tiny-random-checkpoint.safetensors');save_model(original,str(tiny));digest=hashlib.sha256(tiny.read_bytes()).hexdigest()
 restored,receipt=load_model(root,tiny,torch=torch,device='cpu',expected_sha256=digest,config_override=overrides)
 assert set(original.state_dict())==set(restored.state_dict())
 assert all(torch.equal(value,restored.state_dict()[key]) for key,value in original.state_dict().items())
 assert sum(p.numel() for p in restored.parameters())==sum(p.numel() for p in original.parameters())
 with torch.inference_mode():actual=restored(**kw).logits
 assert torch.equal(expected,actual),'Tiny checkpoint load changed inference'
 result.update(tinyWeightRoundtrip=receipt,tinyForwardBitExact=True,tinyParameterCount=sum(p.numel() for p in restored.parameters()))
 # Real tokenizer, tiny random model; forced IDs test the API only, not ASR.
 tokenizer=transformers.AutoTokenizer.from_pretrained(root,local_files_only=True);restored.tokenizer=tokenizer;restored.generation_config=transformers.GenerationConfig.from_pretrained(root,local_files_only=True)
 assert restored.soft_label_creator is None
 class ForcedPlumbingTokens(transformers.LogitsProcessor):
  def __call__(self,input_ids,scores):
   ids=[50365,7751,50367,50257];offset=input_ids.shape[-1]-3;scores.fill_(-float('inf'));scores[:,ids[max(0,min(offset,3))]]=0;return scores
 with torch.inference_mode(),capture_raw_greedy_sequences(restored) as trace:
  output=restored.generate(input_features=features,attention_mask=torch.ones(1,16,dtype=torch.long),stno_mask=mask,enrollments={'input_features':features.clone(),'stno_mask':mask.clone(),'attention_mask':torch.ones(1,16,dtype=torch.long)},language='zh',task='transcribe',return_timestamps=True,do_sample=False,max_new_tokens=5,logits_processor=[ForcedPlumbingTokens()])
 assert trace and all(row[-1]==50257 for call in trace for row in call)
 result.update(tinyForcedGenerationApiPass=True,generationOutputType=type(output).__name__,rawGreedySequences=trace,authorReconstructedIds=output.cpu().tolist(),trainingOnlySmoothingMatrixOmitted=True,forcedTokensOnlyForPlumbingNotQuality=True)
 del original,restored,expected,actual
 # Instantiate the full author graph on meta; read header only, no real tensor.
 full=Config(**read(root/'config.json'));full._attn_implementation='eager'
 with torch.device('meta'):meta=Model(full)
 assert all(p.is_meta for p in meta.parameters()) and all(b.is_meta for b in meta.buffers())
 expected=meta.state_dict(keep_vars=True);groups={}
 for key,value in expected.items():groups.setdefault(id(value),[]).append(key)
 real=Path(read(C/'weight-download.json')['weightFile'])
 with real.open('rb') as stream:
  prefix=stream.read(8);size=struct.unpack('<Q',prefix)[0];header=json.loads(stream.read(size))
 header.pop('__metadata__',None);aliases={}
 for names in groups.values():
  available=[name for name in names if name in header];assert available,('Missing trained tensor',names)
  for name in names:
   if name not in header:aliases[name]=available[0]
 assert set(header).issubset(expected)
 assert all(tuple(value.shape)==tuple(header[aliases.get(name,name)]['shape']) for name,value in expected.items())
 assert all(row['dtype']=='F32' for row in header.values())
 result.update(state='PASS_EXACT_TINY_LOAD_GENERATION_AND_FULL_META_HEADER',fullCheckpointTensorCount=len(header),fullExpectedStateKeys=len(expected),fullTiedAliases=aliases,fullParameterCount=sum(p.numel() for p in meta.parameters()),fullCheckpointHeaderBytesRead=8+size,fullCheckpointF32Only=True,fullModelWeightsAllocatedOnCpu=False,transformers=transformers.__version__,torch=torch.__version__)
except BaseException as exc:result.update(state='FAILED_CHECKPOINT_PLUMBING',failureType=type(exc).__name__,reason=str(exc));raise
finally:
 result.update(seconds=time.perf_counter()-start,limits=limits.query());(C/'checkpoint-probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
