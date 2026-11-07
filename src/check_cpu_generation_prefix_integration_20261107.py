"""Tiny synthetic architecture integration, not published-weight ASR quality."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, os, psutil, sys, time, traceback
from moss_windows_resource_limits_20261104 import WorkerLimits, SystemRamPressure

os.environ.update(OPENBLAS_NUM_THREADS='2', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
limits = WorkerLimits(cpu_percent=5)
psutil.Process().cpu_affinity([12,13])
pressure = SystemRamPressure()
target = Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/cpu-prefix-integration-result.json')
assert not target.exists(), 'Preserve previous test evidence'
result = {'state':'STARTING_SYNTHETIC_CPU_INTEGRATION','publishedModelWeightsUsed':False,'newAsrAccuracyEvidence':False,'gpuUsed':False}
tick = time.perf_counter()
try:
    if pressure.low(): raise RuntimeError('Actual Windows low RAM before CPU control')
    import torch
    torch.set_num_threads(2); torch.set_num_interop_threads(1); torch.manual_seed(0)
    assert not torch.cuda.is_initialized()
    if pressure.low(): raise RuntimeError('Actual Windows low RAM after Torch import')
    sys.path.insert(0,'E:/CodexData/Companion/asr-accuracy-latency-20261103/multispeaker-ai/joint-moss-architecture-20261104/official-source')
    from moss_transcribe_diarize import MossTranscribeDiarizeConfig, MossTranscribeDiarizeForConditionalGeneration
    from transformers import GenerationConfig
    from moss_generation_checkpoint_20261107 import TokenLedger, restore, digest, append_retained_prefix
    config = MossTranscribeDiarizeConfig(text_config={'vocab_size':96,'hidden_size':16,'intermediate_size':32,'num_hidden_layers':2,'num_attention_heads':2,'num_key_value_heads':1,'head_dim':8,'max_position_embeddings':128,'layer_types':['full_attention']*2,'pad_token_id':0,'bos_token_id':1,'eos_token_id':2},audio_config={'num_mel_bins':80,'d_model':16,'encoder_layers':1,'encoder_attention_heads':2,'encoder_ffn_dim':32,'max_source_positions':32,'dropout':0.,'attention_dropout':0.,'activation_dropout':0.,'encoder_layerdrop':0.},audio_token_id=90,audio_merge_size=4,pad_token_id=0)
    config._attn_implementation='sdpa'
    model=MossTranscribeDiarizeForConditionalGeneration(config).eval()
    ids=torch.tensor([[1]+[90]*8+[5]])
    inputs={'input_ids':ids,'attention_mask':torch.ones_like(ids),'input_features':torch.linspace(-1,1,80*64).reshape(1,80,64),'audio_feature_lengths':torch.tensor([8]),'audio_chunk_mapping':torch.tensor([0])}
    def generation(count): return GenerationConfig(max_new_tokens=count,min_new_tokens=count,forced_eos_token_id=2,eos_token_id=2,bos_token_id=1,pad_token_id=0,do_sample=False,use_cache=True,no_repeat_ngram_size=2,suppress_tokens=[90])
    with torch.inference_mode():
        baseline=model.generate(**inputs,generation_config=generation(20))
        generated=baseline[0,ids.shape[-1]:].tolist()
        assert len(generated)==20 and generated[-1]==2 and len(set(generated))>2
        comparisons=[]
        for count in [7,13]:
            if pressure.low(): raise RuntimeError('Actual Windows low RAM during CPU integration')
            directory=target.parent/('synthetic-cpu-ledger-%d'%count)
            binding={'syntheticOnly':True,'maximumGeneratedTokens':20,'promptSha256':digest(ids.numpy().tobytes())}
            ledger=TokenLedger(directory,binding=binding,vocab_size=96,eos_ids={2})
            manifest,_=ledger.append(generated[:count])
            prefix,_=restore({'manifest':str(manifest),'sha256':digest(manifest.read_bytes())},expected_binding=binding,vocab_size=96,eos_ids={2})
            appended=append_retained_prefix(inputs,prefix,torch=torch,vocab_size=96,audio_token_id=90)
            assert torch.equal(inputs['input_ids'],ids) and appended['input_features'] is inputs['input_features']
            assert appended['audio_chunk_mapping'] is inputs['audio_chunk_mapping']
            assert appended['audio_feature_lengths'] is inputs['audio_feature_lengths']
            output=model.generate(**appended,generation_config=generation(20-count))
            actual=output[0,ids.shape[-1]:].tolist()
            assert actual==generated,'Synthetic generation changed after complete-context prefix recovery'
            comparisons.append({'retainedTokens':count,'newTokens':20-count,'all20GeneratedIdsIdentical':True,'wholeAudioTensorObjectsPreserved':True})
    assert not torch.cuda.is_initialized()
    result.update(state='PASS_TINY_CPU_MOSS_ARCHITECTURE_PREFIX_RECOVERY_ONLY',comparisons=comparisons,parameterCount=sum(p.numel() for p in model.parameters()),cudaInitialized=False,limits=limits.query(),scope='Same author MOSS/Qwen3/Whisper generation APIs and real shared prefix assembler, tiny random synthetic dimensions, forced test length. Not the0.9B published model, real speech, GPU-resume equivalence or any accuracy gate.')
except BaseException as error:
    result.update(state='CPU_INTEGRATION_FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc())
    raise
finally:
    pressure.close()
    result.update(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),seconds=time.perf_counter()-tick)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
