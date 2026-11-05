from pathlib import Path
import hashlib,json,tempfile
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5)
import torch
torch.set_num_threads(1)
from safetensors.torch import save_file,load_file
from moss_streamed_weights_20261104 import load_streamed_weights
root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
with tempfile.TemporaryDirectory(prefix='streamed-weights-',dir=root) as folder:
    path=Path(folder)/'fixture.safetensors'
    tensors={'bf16':torch.arange(140,dtype=torch.bfloat16).reshape(14,10),
      'fp32':torch.tensor([1.25,-2.5,0.]),'int64':torch.arange(10,dtype=torch.int64)}
    save_file(tensors,path)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    result,receipt=load_streamed_weights(path,torch=torch,device='cpu',expected_sha256=digest,chunk_bytes=64)
    official=load_file(path)
    assert result.keys()==official.keys()
    assert all(torch.equal(result[k],official[k]) and result[k].dtype==official[k].dtype for k in result)
    assert receipt['maximumTransferChunkBytes']<=64
    rejected=False
    try:load_streamed_weights(path,torch=torch,device='cpu',expected_sha256='0'*64,chunk_bytes=64)
    except AssertionError:rejected=True
    assert rejected
    output={'state':'PASS_STREAMED_FORMAT_BYTES_AND_HASH_REGRESSION','receipt':receipt,
      'matchesOfficialSafetensorsReader':True,'wrongHashRejected':True,'modelLoaded':False,'gpuComputationLaunched':False}
    target=root/'streamed-weight-format-check-r9.json';assert not target.exists();target.write_text(json.dumps(output,indent=2),encoding='utf8')
    print(json.dumps(output))
