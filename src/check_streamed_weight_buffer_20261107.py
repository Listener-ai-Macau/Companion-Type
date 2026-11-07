"""CPU byte-level control against the official safetensors reader."""
from pathlib import Path
import hashlib,json,os,tempfile,time
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
limits=WorkerLimits(cpu_percent=5)
pressure=SystemRamPressure()
assert not pressure.low(),'Actual Windows low RAM; no control started'
tick=time.perf_counter()
import torch
torch.set_num_threads(2)
from safetensors.torch import save_file,load_file
from moss_streamed_weights_20261104 import load_streamed_weights
assert not torch.cuda.is_initialized()
root=Path('E:/CodexData/Companion/.model-cache/generation-recovery-20261107')
root.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='streamed-buffer-',dir=root) as folder:
    path=Path(folder)/'test.safetensors'
    values={'bf16':torch.arange(140,dtype=torch.bfloat16).reshape(14,10),'fp32':torch.tensor([1.25,-2.5,-0.,float('inf'),float('-inf'),float('nan')]),'int64':torch.arange(10,dtype=torch.int64),'uint8':torch.arange(130,dtype=torch.uint8)}
    save_file(values,path)
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    actual,receipt=load_streamed_weights(path,torch=torch,device='cpu',expected_sha256=checksum,chunk_bytes=64)
    official=load_file(path)
    for name in official:
        assert actual[name].dtype==official[name].dtype
        assert torch.equal(actual[name].view(torch.uint8),official[name].view(torch.uint8)),name
    assert receipt['deviceRoundtripSha256']==checksum and receipt['roundtripBufferBytes']==64 and receipt['roundtripCpuBufferReused']
    rejected=False
    try: load_streamed_weights(path,torch=torch,device='cpu',expected_sha256='0'*64,chunk_bytes=64)
    except AssertionError: rejected=True
    assert rejected and not torch.cuda.is_initialized()
    result={'state':'PASS_REUSED_CPU_ROUNDTRIP_BUFFER_OFFICIAL_BYTE_CONTROL','allTensorBytesAndDtypesMatchOfficialReader':True,'bf16NanInfSignedZeroAndChunkBoundariesPreserved':True,'wrongFileHashRejected':True,'receipt':receipt,'gpuUsed':False,'modelLoaded':False,'seconds':time.perf_counter()-tick,'limits':limits.query(),'scope':'Exact transfer bytes and bounded CPU return-buffer allocation only; no measured full-weight system-RAM saving or model-quality claim.'}
pressure.close()
out=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/reused-weight-buffer-check.json')
assert not out.exists()
out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps(result),flush=True)
