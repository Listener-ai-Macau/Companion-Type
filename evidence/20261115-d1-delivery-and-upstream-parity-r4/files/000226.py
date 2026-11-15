from pathlib import Path
import json
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5)
import torch
torch.set_num_threads(1)
from torch.nn.attention import sdpa_kernel,SDPBackend
from moss_key_streamed_attention_20261104 import key_streamed_sdpa
torch.manual_seed(0);checks=[]
for dtype in [torch.float32,torch.bfloat16]:
    for kind in ['plain','causal','upper-left-unequal','broadcast-bool','query-bool','additive','gqa','all-masked']:
        qlen,klen=(7,23) if kind=='upper-left-unequal' else (19,23)
        heads,kvheads=(4,2) if kind=='gqa' else (4,4)
        q=torch.randn(2,heads,qlen,16,dtype=dtype);k=torch.randn(2,kvheads,klen,16,dtype=dtype);v=torch.randn(2,kvheads,klen,12,dtype=dtype)
        mask=None
        if kind in ['broadcast-bool','query-bool','additive','all-masked']:
            mask=torch.ones(2,1,1 if kind=='broadcast-bool' else qlen,klen,dtype=torch.bool);mask[...,-5:]=False
            if kind=='all-masked':mask.zero_()
            if kind=='additive':mask=torch.zeros_like(mask,dtype=dtype).masked_fill(~mask,float('-inf'))
        options=dict(attn_mask=mask,is_causal=kind in ['causal','upper-left-unequal'],enable_gqa=kind=='gqa',scale=.37)
        with sdpa_kernel(SDPBackend.MATH):expected=torch.nn.functional.scaled_dot_product_attention(q,k,v,**options)
        stats={'keyStreamedCalls':0,'keyTiles':0,'maximumScoreTileElements':0}
        actual=key_streamed_sdpa(q,k,v,**options,key_block=7,stats=stats)
        torch.testing.assert_close(actual,expected,rtol=3e-5 if dtype==torch.float32 else .016,atol=3e-6 if dtype==torch.float32 else .016)
        assert torch.isfinite(actual).all()
        assert stats['maximumScoreTileElements']<=2*4*qlen*7
        checks.append({'dtype':str(dtype),'case':kind,'maximumAbsoluteDifference':float((actual-expected).abs().max()),'stats':stats})
root=Path('E:/CodexData/Companion/pretrained-route-selection-20261104/night-6800xt-20261104')
target=root/'key-streamed-attention-cpu-control-r11.json';assert not target.exists()
result={'state':'PASS_CPU_ONLINE_SOFTMAX_MEMORY_AND_MATH_CONTROL','cases':checks,
 'modelLoaded':False,'gpuWorkLaunched':False,'limits':'Math/working-memory control only. Not a real model or whole-meeting quality result.'}
target.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps({'state':result['state'],'cases':len(checks),'maximumFp32Difference':max(x['maximumAbsoluteDifference'] for x in checks if x['dtype']=='torch.float32'),'maximumBf16Difference':max(x['maximumAbsoluteDifference'] for x in checks if x['dtype']=='torch.bfloat16')}))
