"""Exact native classifier loading control; random tiny weights are not speech quality."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,psutil,traceback
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-alignment-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
for member in psutil.process_iter(['cmdline']):
    try:
        assert not any(Path(a).name in ['practical_qwen_boundaries_worker_20261107.py','run_practical_qwen_boundaries_20261107.py','practical_qwen_checkpoint_worker_20261107.py'] for a in member.info['cmdline'] or []),'Wait for prior neural stage to exit'
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
inventory=read(C.parent/'practical-qwen-author-boundaries-r6/hip-inventory.json')
for key in ['CUDA_VISIBLE_DEVICES','ROCR_VISIBLE_DEVICES','GPU_DEVICE_ORDINAL','PYTHONPATH']:os.environ.pop(key,None)
os.environ.update(HIP_VISIBLE_DEVICES=str(inventory['selected']['ordinal']),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3);target=C/'tiny-loader-proof.json';assert not target.exists()
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PREPARING_TINY_NATIVE_CLASSIFIER_LOADING_CONTROL','syntheticOnly':True,'publishedNeuralWeightsLoaded':False,'accuracyMeasured':False}
atomic_json(target,result)
try:
    import torch
    from transformers import AutoConfig,AutoModelForTokenClassification
    from practical_alignment_loader_20261107 import load_aligner
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    assert torch.version.hip and torch.cuda.device_count()==1 and 'RX 6800 XT' in torch.cuda.get_device_name(0)
    torch.cuda.set_device(0);torch.manual_seed(413)
    config=AutoConfig.from_pretrained(read(C/'model-source.json')['modelRoot'],local_files_only=True)
    for k,v in dict(d_model=32,encoder_layers=1,encoder_attention_heads=4,num_key_value_heads=4,encoder_ffn_dim=64,output_dim=32,downsample_hidden_size=8,n_window_infer=100).items():setattr(config.audio_config,k,v)
    for k,v in dict(hidden_size=32,intermediate_size=64,num_attention_heads=4,num_key_value_heads=2,head_dim=8,num_hidden_layers=2,layer_types=['full_attention']*2,vocab_size=64,max_position_embeddings=512).items():setattr(config.text_config,k,v)
    config.audio_token_id=7;config.pad_token_id=0;config.eos_token_id=[2];config.timestamp_token_id=9;config.num_labels=128
    original=AutoModelForTokenClassification.from_config(config,dtype=torch.bfloat16,attn_implementation='eager').eval()
    cache=Path('E:/CodexData/Companion/.model-cache/qwen-native-aligner-20261107/tiny-loader-control');cache.mkdir(exist_ok=False)
    original.save_pretrained(cache,safe_serialization=True);del original
    reference=AutoModelForTokenClassification.from_pretrained(cache,local_files_only=True,dtype=torch.bfloat16,device_map={'':0},attn_implementation='eager').eval()
    with (cache/'model.safetensors').open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    streamed,receipt=load_aligner(cache,torch=torch,device='cuda:0',expected_sha256=digest)
    inputs={'input_ids':torch.tensor([[1]+[7]*13+[9]],dtype=torch.long,device='cuda:0'),
        'attention_mask':torch.ones((1,15),dtype=torch.long,device='cuda:0'),
        'input_features':torch.randn((1,128,100),dtype=torch.bfloat16,device='cuda:0'),
        'input_features_mask':torch.ones((1,100),dtype=torch.long,device='cuda:0')}
    with torch.inference_mode():left=reference(**inputs,use_cache=False).logits;right=streamed(**inputs,use_cache=False).logits
    assert torch.equal(left,right),'No tolerance relaxation after a classifier-loader mismatch'
    result.update(state='PASS_STANDARD_AND_STREAMED_TINY_ALIGNER_EXACT_LOGITS',sameLogits=True,
        samePredictedTimestampClasses=torch.equal(left.argmax(-1),right.argmax(-1)),weightRoundtrip=receipt,
        sourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),wholePretrainedAccuracyQualified=False)
except BaseException as error:
    result.update(state='ALIGNER_TINY_LOADER_CONTROL_FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    result['limits']=limits.query();atomic_json(target,result);print(json.dumps(result),flush=True)
