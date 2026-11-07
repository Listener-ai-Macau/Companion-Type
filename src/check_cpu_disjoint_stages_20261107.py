"""Exercise the actual stage loader/cache/generator with tiny author modules.

Synthetic CPU integration only; cannot qualify published-weight speech quality.
"""
from pathlib import Path
import argparse,gc,hashlib,json,os,psutil,sys,time,traceback
os.environ.update(OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5);psutil.Process().cpu_affinity([12,13]);pressure=SystemRamPressure()
parser=argparse.ArgumentParser();parser.add_argument('--attempt',default='r2');args=parser.parse_args()
assert args.attempt and all(c.isalnum() or c in '-_' for c in args.attempt)
target=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery')/('cpu-disjoint-stages-'+args.attempt+'-result.json')
assert not target.exists()
work=Path('E:/CodexData/Companion/.model-cache/generation-recovery-20261107')/('cpu-disjoint-'+args.attempt);work.mkdir(parents=True,exist_ok=False)
result={'state':'STARTING','publishedModelWeightsUsed':False,'newAccuracyEvidence':False,'gpuUsed':False};tick=time.perf_counter()
try:
    if pressure.low():raise RuntimeError('Actual Windows low RAM before CPU integration')
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(0)
    sys.path.insert(0,'E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104/official-source')
    from moss_transcribe_diarize import MossTranscribeDiarizeConfig,MossTranscribeDiarizeForConditionalGeneration as Model
    from transformers import GenerationConfig
    from safetensors.torch import save_file
    from moss_stage_runtime_20261107 import GROUPS,build_stage_model,publish_features,load_features,tensor_record
    from moss_streamed_weights_20261104 import load_streamed_weights
    from moss_generation_checkpoint_20261107 import append_retained_prefix
    config=MossTranscribeDiarizeConfig(text_config={'vocab_size':96,'hidden_size':16,'intermediate_size':32,'num_hidden_layers':2,'num_attention_heads':2,'num_key_value_heads':1,'head_dim':8,'max_position_embeddings':128,'layer_types':['full_attention']*2,'pad_token_id':0,'bos_token_id':1,'eos_token_id':2},audio_config={'num_mel_bins':80,'d_model':16,'encoder_layers':1,'encoder_attention_heads':2,'encoder_ffn_dim':32,'max_source_positions':32,'dropout':0.,'attention_dropout':0.,'activation_dropout':0.,'encoder_layerdrop':0.},audio_token_id=90,audio_merge_size=4,pad_token_id=0)
    config._attn_implementation='sdpa';model=Model(config).eval()
    ids=torch.tensor([[1]+[90]*8+[5]])
    inputs={'input_ids':ids,'attention_mask':torch.ones_like(ids),'input_features':torch.linspace(-1,1,80*64).reshape(1,80,64),'audio_feature_lengths':torch.tensor([8]),'audio_chunk_mapping':torch.tensor([0])}
    generation=lambda n:GenerationConfig(max_new_tokens=n,min_new_tokens=n,forced_eos_token_id=2,eos_token_id=2,bos_token_id=1,pad_token_id=0,do_sample=False,use_cache=True,no_repeat_ngram_size=2,suppress_tokens=[90])
    with torch.inference_mode():
        baseline=model.generate(**inputs,generation_config=generation(20))[0,ids.shape[-1]:].tolist()
        baseline_features=model.model.get_audio_features(**{k:inputs[k] for k in ['input_features','audio_feature_lengths','audio_chunk_mapping']})
    file=work/'tiny.safetensors';save_file({k:v.contiguous() for k,v in model.state_dict().items() if k!='lm_head.weight'},str(file))
    checksum=hashlib.sha256(file.read_bytes()).hexdigest()
    del model;gc.collect()
    receipts=[]
    for stage in ['acoustic','language']:
        if pressure.low():raise RuntimeError('Actual Windows low RAM during CPU integration')
        tensors,transfer=load_streamed_weights(file,torch=torch,device='cpu',expected_sha256=checksum,tensor_prefixes=GROUPS[stage],chunk_bytes=128)
        model,loading=build_stage_model(Model,config,tensors,stage=stage,torch=torch,device='cpu',dtype=torch.float32)
        del tensors
        receipts.append({'stage':stage,'transfer':transfer,'loading':loading})
        if stage=='acoustic':
            with torch.inference_mode():features=model.model.get_audio_features(**{k:inputs[k] for k in ['input_features','audio_feature_lengths','audio_chunk_mapping']})
            assert all(torch.equal(a,b) for a,b in zip(features,baseline_features))
            case={'meeting':'synthetic-cpu','audioSha256':'synthetic-only','audioSeconds':1}
            protocol={'modelRevision':'synthetic','officialSourceCommit':'synthetic','weightSha256':checksum,'runtime':{'torch':torch.__version__,'transformers':'test','dtype':'float32','encoderBatch':1,'maxLength':128}}
            manifest,data=publish_features(features,directory=work/'features',inputs=inputs,case=case,protocol=protocol,torch=torch,provenance={'synthetic':True})
            cache={'manifest':str(manifest),'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}
            del features,model;gc.collect()
        else:
            features,receipt=load_features(cache,inputs=inputs,case=case,protocol=protocol,torch=torch,device='cpu')
            assert all(torch.equal(a,b) for a,b in zip(features,baseline_features))
            model.model.get_audio_features=lambda **kwargs:features
            comparisons=[]
            with torch.inference_mode():
                for prefix in [0,7,13]:
                    appended=append_retained_prefix(inputs,baseline[:prefix],torch=torch,vocab_size=96,audio_token_id=90) if prefix else inputs
                    actual=model.generate(**appended,generation_config=generation(20-prefix))[0,ids.shape[-1]:].tolist()
                    assert actual==baseline,'Staging changed generated tokens'
                    comparisons.append({'prefix':prefix,'all20IdsIdentical':True})
            altered={**inputs,'input_ids':ids.clone()};altered['input_ids'][0,-1]=6
            try:load_features(cache,inputs=altered,case=case,protocol=protocol,torch=torch,device='cpu')
            except AssertionError:pass
            else:raise AssertionError('Changed complete input was accepted')
    # BF16 byte checks must not depend on NumPy BF16 support.
    tensor_record(torch.tensor([1.25,-2.5],dtype=torch.bfloat16),torch)
    assert not torch.cuda.is_initialized()
    result.update(state='PASS_TINY_CPU_DISJOINT_AUTHOR_STAGES_AND_PREFIX_EQUIVALENCE_ONLY',receipts=receipts,comparisons=comparisons,projectedFeaturesBitwiseEqual=True,cacheRoundtripBitwiseEqual=True,changedInputRejected=True,bfloat16HashSupported=True,cudaInitialized=False,limits=limits.query())
except BaseException as error:
    result.update(state='CPU_STAGE_INTEGRATION_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
finally:
    pressure.close();result['seconds']=time.perf_counter()-tick
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
