"""Load exact author tensors with the retained bounded, roundtrip-verified loader."""
from pathlib import Path
import importlib,json,sys,types

def author_classes(source_root, *, package_name='companion_pinned_sedicow'):
    module=types.ModuleType(package_name);module.__path__=[str(source_root)];sys.modules[package_name]=module
    config=importlib.import_module(package_name+'.config').DiCoWConfig
    model=importlib.import_module(package_name+'.modeling_dicow').DiCoWForConditionalGeneration
    return config,model

def load_model(source_root, weight_file, *, torch, device, expected_sha256, config_override=None):
    from moss_streamed_weights_20261104 import load_streamed_weights
    Config,Model=author_classes(source_root)
    data=json.loads((Path(source_root)/'config.json').read_text())
    if config_override:data.update(config_override)
    config=Config(**data);config._attn_implementation='eager'
    with torch.device('meta'):model=Model(config)
    expected=model.state_dict(keep_vars=True)
    aliases={}
    for key,value in expected.items():aliases.setdefault(id(value),[]).append(key)
    weights,receipt=load_streamed_weights(weight_file,torch=torch,device=device,expected_sha256=expected_sha256)
    restored={}
    for names in aliases.values():
        available=[key for key in names if key in weights]
        if not available:raise ValueError('Checkpoint lacks expected weights: '+str(names))
        for key in names:
            if key not in weights:weights[key]=weights[available[0]];restored[key]=available[0]
    assert set(weights)==set(expected),'Unexpected or missing checkpoint state'
    assert all(tuple(weights[key].shape)==tuple(value.shape) for key,value in expected.items())
    model.load_state_dict(weights,strict=True,assign=True)
    # assign=True can wrap shared tensors in separate Parameter objects. Restore
    # the author's declared ties, preserving both values and parameter identity.
    model.tie_weights()
    actual=model.state_dict(keep_vars=True)
    assert all(len({id(actual[key]) for key in names})==1 for names in aliases.values())
    assert not any(p.is_meta for p in model.parameters())
    assert not any(p.is_meta for p in model.buffers())
    model.eval().requires_grad_(False)
    receipt.update(restoredTiedAliases=restored,strictModelStateLoaded=True,modelParameters=sum(p.numel() for p in model.parameters()),dtypeConversion=False)
    return model,receipt
