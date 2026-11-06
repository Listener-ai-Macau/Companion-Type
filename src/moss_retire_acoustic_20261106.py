"""Retire completed acoustic weights after their final inference use.

Only the existing encoder/adaptor storage is released. Projected acoustic
features and all language-model weights/context remain unchanged. No offload,
quantization or CPU copy is made; a second acoustic call fails explicitly.
"""
import gc


def retire_completed_acoustic_modules(model, *, torch, device):
    if model.training or not torch.is_inference_mode_enabled():
        raise RuntimeError('Acoustic retirement requires eval inference mode')
    if getattr(model, '_completed_acoustic_weights_retired', False):
        raise RuntimeError('Acoustic weights were already retired')
    backbone = model.model
    acoustic = [backbone.whisper_encoder, backbone.vq_adaptor]
    retained = {id(p) for p in backbone.language_model.parameters()}
    retained.update(id(p) for p in model.lm_head.parameters())
    if any(id(p) in retained for module in acoustic for p in module.parameters()):
        raise RuntimeError('Acoustic and language weights alias; refuse retirement')
    if any(t.device != device for module in acoustic for t in list(module.parameters()) + list(module.buffers())):
        raise RuntimeError('Unexpected acoustic storage device')
    language_storage = [(p, p.data_ptr(), p._version) for p in backbone.language_model.parameters()]
    before = torch.cuda.memory_allocated(device)
    storage_bytes = sum(t.numel() * t.element_size() for module in acoustic for t in list(module.parameters()) + list(module.buffers()))

    def refuse_reuse(*unused, **kwargs):
        raise RuntimeError('Completed acoustic weights retired; start a new worker to encode new audio')

    # Guards are installed before storage is removed. A changed generation path
    # must stop rather than accidentally run an empty acoustic module.
    for module in acoustic:
        module.register_forward_pre_hook(refuse_reuse)
    for module in acoustic:
        module.to_empty(device=torch.device('meta'))
    gc.collect()
    torch.cuda.synchronize(device)
    torch.cuda.empty_cache()
    if any(not t.is_meta for module in acoustic for t in list(module.parameters()) + list(module.buffers())):
        raise RuntimeError('Acoustic storage retirement incomplete')
    if any(p.data_ptr() != pointer or p._version != version for p, pointer, version in language_storage):
        raise RuntimeError('Language weight identity changed during acoustic retirement')
    if model.lm_head.weight.data_ptr() != backbone.language_model.embed_tokens.weight.data_ptr():
        raise RuntimeError('Tied output embedding changed')
    model._completed_acoustic_weights_retired = True
    return {
        'state': 'COMPLETED_ACOUSTIC_STORAGE_RETIRED_LANGUAGE_WEIGHTS_PRESERVED',
        'retiredStorageBytes': storage_bytes,
        'gpuAllocatedBytesBefore': before,
        'gpuAllocatedBytesAfter': torch.cuda.memory_allocated(device),
        'retainedLanguageParameterIdentityChecked': True,
        'outputEmbeddingStillTied': True,
        'acousticReuseRefused': True,
        'offloadedToCpu': False,
        'scope': 'Execution lifetime only. System-RAM reduction and complete-meeting quality require measurement.'
    }
