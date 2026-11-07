"""Bounded loader for the official native timestamp classifier, not an LM head."""
from pathlib import Path
import hashlib,time

def load_aligner(root,*,torch,device,expected_sha256):
    from accelerate import init_empty_weights
    from transformers import AutoConfig,AutoModelForTokenClassification
    from moss_streamed_weights_20261104 import load_streamed_weights
    root=Path(root);tick=time.perf_counter()
    config=AutoConfig.from_pretrained(root,local_files_only=True)
    assert config.model_type=='qwen3_asr' and config.architectures==['Qwen3ASRForTokenClassification']
    with init_empty_weights(include_buffers=False):
        model=AutoModelForTokenClassification.from_config(config,dtype=torch.bfloat16,attn_implementation='eager')
    assert all(p.is_meta for p in model.parameters())
    buffers={name:value.detach().cpu().clone() for name,value in model.named_buffers()}
    assert all(not value.is_meta for value in buffers.values())
    weights,receipt=load_streamed_weights(root/'model.safetensors',torch=torch,device=device,expected_sha256=expected_sha256,chunk_bytes=16*1024**2)
    assert all(value.dtype==torch.bfloat16 for value in weights.values())
    loaded=model.load_state_dict(weights,strict=True,assign=True)
    assert not loaded.missing_keys and not loaded.unexpected_keys and not any(p.is_meta for p in model.parameters())
    assert hasattr(model,'score') and not hasattr(model,'lm_head')
    model=model.to(device).eval()
    for name,value in model.named_buffers():assert torch.equal(value.detach().cpu(),buffers[name])
    del weights
    receipt.update(modelClass=type(model).__name__,allExpectedParametersLoaded=True,
        missingKeys=loaded.missing_keys,unexpectedKeys=loaded.unexpected_keys,
        noLanguageGenerationHead=True,computedBuffersPreserved=list(buffers),wholeModelToEmptyUsed=False,
        loadSeconds=time.perf_counter()-tick,modelMathChanged=False,
        loaderSourceSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        streamReaderSourceSha256=hashlib.sha256(Path(__file__).with_name('moss_streamed_weights_20261104.py').read_bytes()).hexdigest())
    return model,receipt
