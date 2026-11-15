from pathlib import Path
import tempfile,copy,json
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
import torch
from moss_prepared_inputs_20261106 import publish,load,file_sha

root=Path(tempfile.mkdtemp(prefix='prepared-input-check-',dir='E:/CodexData/Companion/.model-cache'))
case={'meeting':'synthetic-binding-only','audioSha256':'a'*64,'audioSeconds':1.0}
protocol={'modelRevision':'pinned-model','officialSourceCommit':'pinned-author','weightSha256':'b'*64,'runtime':{'torch':torch.__version__,'transformers':'pinned-version','maxLength':131072}}
inputs={'input_ids':torch.tensor([[1,2,3]]),'attention_mask':torch.ones((1,3),dtype=torch.long),'input_features':torch.arange(80*4,dtype=torch.float32).reshape(1,80,4),'audio_feature_lengths':torch.tensor([3]),'audio_chunk_mapping':torch.tensor([0])}
path,manifest=publish(inputs,directory=root/'packet',case=case,protocol=protocol,torch=torch)
binding={'manifest':str(path),'sha256':file_sha(path)}
actual,receipt=load(binding=binding,case=case,protocol=protocol,device=torch.device('cpu'),torch=torch)
assert all(torch.equal(inputs[k],actual[k]) for k in inputs) and receipt['allTensorBytesChecked']
# Windows correctly prevents truncating an actively mapped tensor file. Release
# this successful load before simulating corruption of an idle saved artifact.
del actual
import gc;gc.collect()
def refused(fn):
    try:fn()
    except (AssertionError,ValueError):return
    raise AssertionError('invalid binding accepted')
changed={**case,'audioSha256':'c'*64};refused(lambda:load(binding=binding,case=changed,protocol=protocol,device='cpu',torch=torch))
changed_protocol=copy.deepcopy(protocol);changed_protocol['officialSourceCommit']='another-author-revision'
refused(lambda:load(binding=binding,case=case,protocol=changed_protocol,device='cpu',torch=torch))
changed=copy.deepcopy(manifest);changed['tensorFile']=str(root/'other-directory/author-inputs.pt');path.write_text(json.dumps(changed),encoding='utf8')
refused(lambda:load(binding=binding,case=case,protocol=protocol,device='cpu',torch=torch))
refused(lambda:load(binding={'manifest':str(path),'sha256':file_sha(path)},case=case,protocol=protocol,device='cpu',torch=torch))
path.write_text(json.dumps(manifest),encoding='utf8');binding['sha256']=file_sha(path)
target=Path(manifest['tensorFile']);data=target.read_bytes();target.write_bytes(data+b'changed')
refused(lambda:load(binding=binding,case=case,protocol=protocol,device='cpu',torch=torch))
print(json.dumps({'state':'EXACT_TENSOR_ROUNDTRIP_AND_STALE_AUDIO_PIN_MANIFEST_TENSOR_PATH_REJECTIONS_PASSED','modelLoaded':False,'gpuInference':False,'cpuPercentMaximum':5,'privateMemoryBudgetGiB':2,'root':str(root)}))
