"""Same published model in disjoint acoustic/language loading lifetimes.

Missing weights stay on meta, never random CPU/GPU storage. Only known Qwen3
nonpersistent RoPE buffers are reconstructed with their original constructor.
All omitted/loaded keys and generated buffers are checked explicitly.
"""
import hashlib, json, os
from pathlib import Path

GROUPS={'acoustic':('model.whisper_encoder.','model.vq_adaptor.'),'language':('model.language_model.',)}


def build_stage_model(model_class, config, tensors, *, stage, torch, device, dtype):
    prefixes=GROUPS[stage]
    with torch.device('meta'):
        model=model_class(config)
    model=model.to(dtype=dtype).eval()
    expected={name for name in model.state_dict() if any(name.startswith(p) for p in prefixes)}
    assert set(tensors)==expected,('Stage tensor keys differ',sorted(expected-set(tensors)),sorted(set(tensors)-expected))
    for name,value in tensors.items():
        planned=model.state_dict()[name]
        assert list(planned.shape)==list(value.shape) and value.dtype==dtype and value.device==torch.device(device),name
    loaded=model.load_state_dict(tensors,strict=False,assign=True)
    omitted=set(model.state_dict())-expected
    assert not loaded.unexpected_keys and set(loaded.missing_keys)==omitted
    model.tie_weights()
    if stage=='language':
        # RoPE buffers are configuration-derived, nonpersistent and absent
        # from safetensors. Never copy an uninitialized meta buffer to GPU.
        old=model.model.language_model.rotary_emb
        with torch.device(device):replacement=type(old)(config.text_config)
        model.model.language_model.rotary_emb=replacement
    selected=[model.model.whisper_encoder,model.model.vq_adaptor] if stage=='acoustic' else [model.model.language_model,model.lm_head]
    omitted_modules=[model.model.language_model,model.lm_head] if stage=='acoustic' else [model.model.whisper_encoder,model.model.vq_adaptor]
    assert all(p.device==torch.device(device) for module in selected for p in module.parameters())
    assert all(p.is_meta for module in omitted_modules for p in module.parameters())
    assert all(not b.is_meta for module in selected for b in module.buffers()),'Unmaterialized active buffer'
    assert model.lm_head.weight is model.model.language_model.embed_tokens.weight
    return model,{'stage':stage,'loadedTensorKeys':len(expected),'omittedTensorKeys':len(omitted),'selectedParameterBytes':sum(p.numel()*p.element_size() for name,p in model.named_parameters() if not p.is_meta),'omittedParametersRemainMeta':True,'languageOutputEmbeddingTied':True,'rotaryBuffersFromOriginalConstructor':stage=='language','wholeCpuStateDictCreated':False}


def tensor_record(value,torch):
    cpu=value.detach().cpu().contiguous()
    return {'shape':list(cpu.shape),'dtype':str(cpu.dtype),'sha256':hashlib.sha256(memoryview(cpu.view(torch.uint8).numpy()).cast('B')).hexdigest()}


def input_binding(inputs,case,protocol,torch):
    return {'meeting':case['meeting'],'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
        **{key:protocol[key] for key in ['modelRevision','officialSourceCommit','weightSha256']},
        'runtime':{key:protocol['runtime'][key] for key in ['torch','transformers','dtype','encoderBatch','maxLength']},
        'inputTensors':{key:tensor_record(value,torch) for key,value in sorted(inputs.items())}}


def publish_features(features,*,directory,inputs,case,protocol,torch,provenance):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    assert isinstance(features,list) and features and all(value.ndim==3 and value.shape[0]==1 and bool(torch.isfinite(value).all().item()) for value in features)
    binding=input_binding(inputs,case,protocol,torch)
    cpu={str(index):value.detach().cpu().contiguous() for index,value in enumerate(features)}
    records={key:tensor_record(value,torch) for key,value in cpu.items()}
    file=directory/'encoded-audio.pt';temporary=file.with_suffix('.tmp')
    with temporary.open('xb') as out:
        torch.save(cpu,out);out.flush();os.fsync(out.fileno())
    os.replace(temporary,file)
    loaded=torch.load(file,weights_only=True,map_location='cpu',mmap=True)
    assert set(loaded)==set(cpu) and all(torch.equal(cpu[key],loaded[key]) for key in cpu)
    with file.open('rb') as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
    manifest={'version':1,'state':'EXACT_AUTHOR_AUDIO_FEATURES_STAGED_NO_TEXT_GENERATED','binding':binding,'tensorFile':file.name,'tensorFileSha256':checksum,'tensors':records,'provenance':provenance,'roundtripAllFeaturesBitwiseIdentical':True,'referenceUsed':False,'scope':'Original whole-audio projected features. No transcription, speaker labels or audio segmentation/reset.'}
    target=directory/'manifest.json';target.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    return target,manifest


def load_features(cache,*,inputs,case,protocol,torch,device):
    path=Path(cache['manifest'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==cache['sha256'],'Encoded feature manifest changed'
    data=json.loads(path.read_text(encoding='utf8'))
    assert data['version']==1 and data['state']=='EXACT_AUTHOR_AUDIO_FEATURES_STAGED_NO_TEXT_GENERATED'
    assert data['binding']==input_binding(inputs,case,protocol,torch),'Encoded features belong to different complete input/model/encoder execution'
    assert data['roundtripAllFeaturesBitwiseIdentical'] and not data['referenceUsed'] and data['tensorFile']=='encoded-audio.pt'
    file=path.parent/data['tensorFile']
    with file.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==data['tensorFileSha256']
    loaded=torch.load(file,weights_only=True,map_location='cpu',mmap=True)
    assert set(loaded)==set(data['tensors']) and set(loaded)=={str(i) for i in range(len(loaded))}
    for name,value in loaded.items():assert tensor_record(value,torch)==data['tensors'][name]
    result=[loaded[str(i)].to(device) for i in range(len(loaded))]
    return result,{'manifest':str(path),'manifestSha256':cache['sha256'],'allFeatureBytesChecked':True,'provenance':data['provenance']}
