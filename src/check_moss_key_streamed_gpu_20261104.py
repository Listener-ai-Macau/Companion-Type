import os
for variable in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[variable]='1'
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,time
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
limits=WorkerLimits(cpu_percent=5);sensor=SystemRamPressure()
assert not sensor.low(),'Owner system memory takes priority; no GPU probe'
import torch
torch.set_num_threads(1);torch.set_num_interop_threads(1)
from torch.nn.attention import sdpa_kernel,SDPBackend
from moss_key_streamed_attention_20261104 import key_streamed_sdpa
from moss_gpu_cooperative_pacing_20261104 import GpuPacer
root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
device=torch.device('cuda',1);assert 'RX 6800 XT' in torch.cuda.get_device_name(device)
torch.cuda.set_device(device);torch.manual_seed(0);torch.cuda.reset_peak_memory_stats(device)
pacer=GpuPacer(torch,device,duty=.25,stop_file=root/'stop.request')
try:
    # Real long-context dimensions, but one bounded query tile, no model.
    q=torch.randn(1,16,256,128,device=device,dtype=torch.bfloat16)
    k=torch.randn(1,8,31292,128,device=device,dtype=torch.bfloat16);v=torch.randn_like(k)
    mask=torch.arange(31292,device=device)[None,:] <= torch.arange(30000,30256,device=device)[:,None]
    stats={'keyStreamedCalls':0,'keyTiles':0,'maximumScoreTileElements':0};pacer.begin();tick=time.perf_counter()
    actual=key_streamed_sdpa(q,k,v,attn_mask=mask,enable_gqa=True,key_block=1024,stats=stats,pacer=pacer)
    torch.cuda.synchronize(device);gpu_seconds=time.perf_counter()-tick
    subset_path=root/'key-streamed-gpu-subset-r13.pt'
    torch.save({'q':q[:,:2,:8].cpu(),'k':k[:,:1].cpu(),'v':v[:,:1].cpu(),
        'mask':mask[:8].cpu(),'actual':actual[:,:2,:8].cpu()},subset_path)
    (root/'key-streamed-gpu-stage-r13.json').write_text(json.dumps({'state':'GPU_OPERATOR_COMPLETED_CPU_REFERENCE_PENDING',
        'stats':stats,'gpuWallWithPacingSeconds':gpu_seconds,'gpuPeakAllocatedBytes':torch.cuda.max_memory_allocated(device),
        'gpuPeakReservedBytes':torch.cuda.max_memory_reserved_bytes(device) if hasattr(torch.cuda,'max_memory_reserved_bytes') else torch.cuda.max_memory_reserved(device),
        'savedSubset':str(subset_path)},indent=2),encoding='utf8')
    # Verify a subset against CPU math rather than retrying the unsafe large
    # native GPU SDPA allocation. This uses under2GiB RAM with no model loaded.
    expected_heads=[]
    # Compare heads sequentially: a full CPU GQA reference itself duplicated
    # long keys and correctly hit the2GiB job budget in the retained r11 trial.
    # The budget stays unchanged; this changes only the reference workload.
    with sdpa_kernel(SDPBackend.MATH):
        for head in range(2):
            group=head//2
            expected_heads.append(torch.nn.functional.scaled_dot_product_attention(
                q[:,head:head+1,:8,:].cpu(),k[:,group:group+1].cpu(),v[:,group:group+1].cpu(),
                attn_mask=mask[:8].cpu()))
    expected=torch.cat(expected_heads,dim=1)
    subset=actual[:,:2,:8,:].cpu();difference=(subset.float()-expected.float()).abs()
    torch.testing.assert_close(subset,expected,rtol=.016,atol=.016)
    assert torch.isfinite(actual).all() and stats['maximumScoreTileElements']<=16*256*1024
    report={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
      'state':'PASS_BOUNDED_LONG_CONTEXT_GPU_OPERATOR_AND_CPU_MATH_CONTROL','gpu':torch.cuda.get_device_name(device),
      'queryShape':list(q.shape),'keyShape':list(k.shape),'stats':stats,
      'maximumScoreTileBytesFp32':stats['maximumScoreTileElements']*4,
      'hypotheticalDenseScoreBytesFp32':16*256*31292*4,
      'maximumSubsetDifference':float(difference.max()),'gpuRunWallWithPacingSeconds':gpu_seconds,
      'cpuReferenceSubsetHeads':2,'cpuReferenceSubsetQueries':8,
      'gpuPeakAllocatedBytes':torch.cuda.max_memory_allocated(device),'gpuPeakReservedBytes':torch.cuda.max_memory_reserved(device),
      'resourceLimits':limits.query(),'pacing':pacer.stats,'modelLoaded':False,
      'limits':'Long-shape operator only, not all28 model layers, full generation, ASR accuracy or driver/dock qualification.'}
    p=root/'key-streamed-long-shape-gpu-control-r13.json';assert not p.exists();p.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))
finally:sensor.close()
