"""Recompute residual RNN activations without changing weights or model math."""
def checkpoint_residual_rnns(base, *, torch, observer=None):
    from torch.utils.checkpoint import checkpoint
    modules = [(name, module) for name, module in base.named_modules()
               if type(module).__name__ == 'ResRNN']
    assert len(modules) == 12, 'Pinned six-repeat author backbone expected'
    assert not getattr(base, '_activation_checkpoint_installed', False)
    for name, module in modules:
        original = module.forward
        def forward(value, original=original, module=module, name=name):
            if observer is not None:
                observer(name, 'before')
            if module.training and torch.is_grad_enabled():
                result = checkpoint(original, value, use_reentrant=False,
                                    preserve_rng_state=True)
            else:
                result = original(value)
            if observer is not None:
                observer(name, 'after')
            return result
        module.forward = forward
    base._activation_checkpoint_installed = True
    return [name for name, module in modules]
