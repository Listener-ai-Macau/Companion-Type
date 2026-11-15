"""Actual official tiny-Qwen GPU model: standard vs bounded loading equality."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,traceback
p=argparse.ArgumentParser();p.add_argument('--attempt',type=int,default=1);args=p.parse_args();assert args.attempt in [1,2]
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-qwen-native-r1')
inventory=json.loads((C/'hip-inventory.json').read_text())
os.environ.update(HIP_VISIBLE_DEVICES=str(inventory['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
os.environ.pop('CUDA_VISIBLE_DEVICES',None);os.environ.pop('ROCR_VISIBLE_DEVICES',None)
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);target=C/('streamed-loader-proof.json' if args.attempt==1 else 'streamed-loader-proof-r2.json');assert not target.exists()
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PREPARING_TINY_OFFICIAL_ARCHITECTURE_CONTROL','syntheticOnly':True,'publishedNeuralWeightsLoaded':False,'accuracyMeasured':False}
atomic_json(target,result)
try:
    import torch
    from transformers import AutoConfig,AutoModelForMultimodalLM
    from practical_qwen_streamed_loader_20261107 import load_model
    torch.set_num_threads(1);assert torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0);torch.cuda.set_device(0);torch.manual_seed(413)
    config=AutoConfig.from_pretrained('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/model',local_files_only=True)
    for k,v in dict(d_model=32,encoder_layers=1,encoder_attention_heads=4,num_key_value_heads=4,encoder_ffn_dim=64,output_dim=32,downsample_hidden_size=8,n_window_infer=100).items():setattr(config.audio_config,k,v)
    for k,v in dict(hidden_size=32,intermediate_size=64,num_attention_heads=4,num_key_value_heads=2,head_dim=8,num_hidden_layers=2,layer_types=['full_attention']*2,vocab_size=64,max_position_embeddings=512).items():setattr(config.text_config,k,v)
    config.audio_token_id=7;config.pad_token_id=0;config.eos_token_id=[2]
    original=AutoModelForMultimodalLM.from_config(config,dtype=torch.bfloat16,attn_implementation='eager').eval()
    original.generation_config.eos_token_id=[2];original.generation_config.pad_token_id=0
    cache=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107')/('tiny-loader-control' if args.attempt==1 else 'tiny-loader-control-r2');cache.mkdir(exist_ok=False);original.save_pretrained(cache,safe_serialization=True);del original
    reference=AutoModelForMultimodalLM.from_pretrained(cache,local_files_only=True,dtype=torch.bfloat16,device_map={'':0},attn_implementation='eager').eval()
    reference.generation_config.repetition_penalty=1.0;reference.generation_config.no_repeat_ngram_size=0
    with (cache/'model.safetensors').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    streamed,receipt=load_model(cache,torch=torch,device='cuda:0',expected_sha256=digest)
    inputs={'input_ids':torch.tensor([[1]+[7]*13+[3]],dtype=torch.long,device='cuda:0'),'attention_mask':torch.ones((1,15),dtype=torch.long,device='cuda:0'),'input_features':torch.randn((1,128,100),dtype=torch.bfloat16,device='cuda:0'),'input_features_mask':torch.ones((1,100),dtype=torch.long,device='cuda:0')}
    with torch.inference_mode():
        a=reference(**inputs).logits;b=streamed(**inputs).logits
        left=reference.generate(**inputs,max_new_tokens=8,do_sample=False);right=streamed.generate(**inputs,max_new_tokens=8,do_sample=False)
    assert torch.equal(a,b) and torch.equal(left,right),'Do not relax exact loading/architecture control after a mismatch'
    result.update(state='PASS_STANDARD_AND_STREAMED_TINY_QWEN_EXACT_LOGITS_AND_GENERATION',sameLogits=True,sameGeneratedIds=True,generatedIds=left.cpu().tolist(),weightRoundtrip=receipt,sourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),wholePretrainedAccuracyQualified=False)
except BaseException as error:
    result.update(state='STREAMED_LOADER_CONTROL_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    result['limits']=limits.query();atomic_json(target,result);print(json.dumps(result),flush=True)
