"""Exact author-processor tensors, staged on local disk before loading weights.

This does not split/reset a meeting, change preprocessing math, trim audio, or
cache model output. The small manifest is bound to audio, pins and tensor bytes.
"""
from pathlib import Path
import hashlib,json,os

FIELDS={'input_ids','attention_mask','input_features','audio_feature_lengths','audio_chunk_mapping'}

def file_sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def tensor_record(value):
    value=value.detach().cpu().contiguous()
    return {'shape':list(value.shape),'dtype':str(value.dtype),'sha256':hashlib.sha256(memoryview(value.numpy()).cast('B')).hexdigest()}

def publish(inputs,*,directory,case,protocol,torch):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    assert set(inputs)==FIELDS,'Unknown author processor input: do not drop fields'
    cpu={key:inputs[key].detach().cpu().contiguous() for key in sorted(FIELDS)}
    records={key:tensor_record(value) for key,value in cpu.items()}
    target=directory/'author-inputs.pt';temporary=directory/'author-inputs.tmp'
    with temporary.open('xb') as stream:
        torch.save(cpu,stream);stream.flush();os.fsync(stream.fileno())
    temporary.replace(target)
    loaded=torch.load(target,map_location='cpu',weights_only=True,mmap=True)
    assert set(loaded)==FIELDS and all(torch.equal(cpu[key],loaded[key]) for key in FIELDS)
    manifest={'version':1,'state':'EXACT_AUTHOR_INPUT_TENSORS_PREPARED_NO_MODEL_LOADED','meeting':case['meeting'],
        'audioSha256':case['audioSha256'],'audioSeconds':case['audioSeconds'],
        'modelRevision':protocol['modelRevision'],'officialSourceCommit':protocol['officialSourceCommit'],
        'weightSha256':protocol['weightSha256'],'torch':protocol['runtime']['torch'],'transformers':protocol['runtime']['transformers'],
        'maxLength':protocol['runtime']['maxLength'],'tensorFile':str(target),'tensorFileSha256':file_sha(target),
        'tensors':records,'roundtripAllTensorsBitwiseIdentical':True,'modelLoaded':False,'referenceUsed':False,
        'scope':'Only original author prepare_inputs output; no model state, transcript, speaker count, reference, hotwords or labels.'}
    path=directory/'manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    return path,manifest

def load(*,binding,case,protocol,device,torch):
    path=Path(binding['manifest']);assert file_sha(path)==binding['sha256'],'Prepared input manifest changed'
    data=json.loads(path.read_text(encoding='utf8'))
    assert data['version']==1 and data['state']=='EXACT_AUTHOR_INPUT_TENSORS_PREPARED_NO_MODEL_LOADED'
    assert data['meeting']==case['meeting'] and data['audioSha256']==case['audioSha256'] and data['audioSeconds']==case['audioSeconds']
    for key in ('modelRevision','officialSourceCommit','weightSha256'):assert data[key]==protocol[key],key
    for key in ('torch','transformers','maxLength'):assert data[key]==protocol['runtime'][key],key
    assert data['roundtripAllTensorsBitwiseIdentical'] and not data['modelLoaded'] and not data['referenceUsed']
    tensor_path=Path(data['tensorFile']);assert tensor_path.parent.resolve()==path.parent.resolve(),'Unexpected input artifact directory'
    assert file_sha(tensor_path)==data['tensorFileSha256'],'Prepared tensor file changed'
    cpu=torch.load(tensor_path,map_location='cpu',weights_only=True,mmap=True)
    assert set(cpu)==FIELDS and set(data['tensors'])==FIELDS
    for key,value in cpu.items():assert tensor_record(value)==data['tensors'][key],key
    result={key:value.to(device) for key,value in cpu.items()}
    return result,{'manifest':str(path),'manifestSha256':binding['sha256'],'allTensorBytesChecked':True,
                   'audioSha256':data['audioSha256'],'source':'Exact original author processor in previous exited process'}
