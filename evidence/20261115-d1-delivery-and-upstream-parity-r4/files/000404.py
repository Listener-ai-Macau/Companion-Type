"""Same official model, bounded input buffers, exact device weight roundtrip.

Reuse the already-verified streamed reader instead of safe_open's whole-file
storage allocation. Preserve computed nonpersistent buffers; never to_empty.
"""
from pathlib import Path
import hashlib,time

def load_model(root,*,torch,device,expected_sha256):
    from accelerate import init_empty_weights
    from transformers import AutoConfig,AutoModelForMultimodalLM,GenerationConfig
    from moss_streamed_weights_20261104 import load_streamed_weights
    root=Path(root);tick=time.perf_counter()
    config=AutoConfig.from_pretrained(root,local_files_only=True)
    assert config.model_type=='qwen3_asr' and config.tie_word_embeddings
    # include_buffers=False leaves deterministic rotary/position buffers real;
    # only the large parameters are meta. Moving the completed model normally
    # preserves these values, unlike to_empty on the entire module.
    with init_empty_weights(include_buffers=False):
        model=AutoModelForMultimodalLM.from_config(config,dtype=torch.bfloat16,attn_implementation='eager')
    assert all(p.is_meta for p in model.parameters())
    buffers_before={name:value.detach().cpu().clone() for name,value in model.named_buffers()}
    assert all(not value.is_meta for value in buffers_before.values()),'Computed buffers need an explicit source, not uninitialized memory'
    weights,receipt=load_streamed_weights(root/'model.safetensors',torch=torch,device=device,expected_sha256=expected_sha256,chunk_bytes=16*1024**2)
    assert all(value.dtype==torch.bfloat16 for value in weights.values())
    loaded=model.load_state_dict(weights,strict=False,assign=True)
    assert not loaded.unexpected_keys and set(loaded.missing_keys)<= {'lm_head.weight'},'Do not silently skip mismatched official weights'
    model.tie_weights()
    assert not any(p.is_meta for p in model.parameters())
    assert model.lm_head.weight.data_ptr()==model.model.language_model.embed_tokens.weight.data_ptr()
    model=model.to(device).eval()
    for name,value in model.named_buffers():assert torch.equal(value.detach().cpu(),buffers_before[name]),'A computed position/rotary buffer changed during loading'
    model.generation_config=GenerationConfig.from_pretrained(root,local_files_only=True)
    # Transformers5 leaves absent generation options as None until generate
    # resolves defaults. Make our original no-filter contract explicit.
    assert model.generation_config.repetition_penalty in (None,1.0) and model.generation_config.no_repeat_ngram_size in (None,0)
    model.generation_config.repetition_penalty=1.0;model.generation_config.no_repeat_ngram_size=0
    del weights
    receipt.update(modelClass=type(model).__name__,allExpectedParametersLoaded=True,missingOnlyTiedLmHead=loaded.missing_keys==['lm_head.weight'],missingKeys=loaded.missing_keys,tiedOutputEmbeddingPreserved=True,computedBuffersPreserved=list(buffers_before),wholeModelToEmptyUsed=False,generationConfigFromOfficialFiles=True,loadSeconds=time.perf_counter()-tick,streamReaderSourceSha256=hashlib.sha256(Path(__file__).with_name('moss_streamed_weights_20261104.py').read_bytes()).hexdigest(),loaderSourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),modelMathChanged=False)
    return model,receipt
