"""Bounded local blind separation using the unmodified public network.

Upstream YAML fixes2s windows/1.5s stride. This adapter preserves every sample,
matches anonymous output permutations over the shared waveform, and normalizes
only overlap-add weights. It does not amplify each output to mixture loudness.
It is a local CSS adapter, not a claim of upstream-wrapper byte equivalence.
"""
from pathlib import Path
from types import SimpleNamespace
import json,math,wave
from companion_community1_adapter_20261115 import sha

def read_audio(case,np):
    assert sha(case['wav'])==case['wavSha256']
    with wave.open(case['wav'],'rb') as f:
        assert (f.getframerate(),f.getnchannels(),f.getsampwidth())==(16000,1,2)
        n=f.getnframes();raw=f.readframes(n)
    assert n/16000==case['audioSeconds']
    return np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768

def separate_continuous(samples,forward,np,*,window=32000,stride=24000):
    assert samples.ndim==1 and samples.dtype==np.float32 and np.isfinite(samples).all()
    n=len(samples);assert n>0 and window==32000 and stride==24000
    if not np.any(samples):return np.zeros((2,n),dtype=np.float32),[]
    starts=list(range(0,max(0,n-window)+1,stride))
    if starts[-1]+window<n:starts.append(n-window)
    assert starts[0]==0 and len(starts)==len(set(starts))
    output=np.zeros((2,n),dtype=np.float32);weight=np.zeros(n,dtype=np.float32)
    previous=None;previous_start=None;trace=[]
    for index,start in enumerate(starts):
        length=min(window,n-start);part=np.zeros(window,dtype=np.float32);part[:length]=samples[start:start+length]
        value=forward(part);assert value.shape==(2,window) and value.dtype==np.float32 and np.isfinite(value).all()
        overlap=0;swap=False;keep_cost=swap_cost=None
        if previous is not None:
            overlap=previous_start+window-start;assert 0<overlap<=window
            old=previous[:,window-overlap:];new=value[:,:overlap]
            keep_cost=float(np.square(old-new,dtype=np.float64).mean())
            swap_cost=float(np.square(old-new[::-1],dtype=np.float64).mean())
            swap=swap_cost<keep_cost
            if swap:value=value[::-1].copy()
        envelope=np.ones(length,dtype=np.float32)
        if index:
            count=min(overlap,length);envelope[:count]*=np.arange(1,count+1,dtype=np.float32)/(count+1)
        if index+1<len(starts):
            count=min(start+window-starts[index+1],length)
            envelope[-count:]*=np.arange(count,0,-1,dtype=np.float32)/(count+1)
        output[:,start:start+length]+=value[:,:length]*envelope
        weight[start:start+length]+=envelope
        trace.append(dict(startFrame=start,validFrames=length,overlapFrames=overlap,swapped=swap,
                          keepMse=keep_cost,swapMse=swap_cost))
        previous=value;previous_start=start
    assert (weight>0).all(),'No input tail or shared sample may disappear'
    output/=weight
    assert output.shape==(2,n) and np.isfinite(output).all()
    return output,trace

def verify_stitching(np):
    rng=np.random.default_rng(20261115);rows=[]
    for n in [1,4096,32000,32001,74001]:
        signal=rng.normal(0,.03,n).astype(np.float32);counter=[0]
        def alternating(part):
            values=np.stack([part,np.zeros_like(part)])
            if counter[0]%2:values=values[::-1].copy()
            counter[0]+=1;return values
        result,trace=separate_continuous(signal,alternating,np)
        error=float(np.max(np.abs(result[0]-signal)))
        assert error<=1e-6 and np.count_nonzero(result[1])==0
        rows.append(dict(frames=n,maximumWaveformError=error,swaps=sum(t['swapped'] for t in trace)))
    empty,trace=separate_continuous(np.zeros(74001,dtype=np.float32),lambda x:(_ for _ in ()).throw(AssertionError('Silence must bypass NN')),np)
    assert np.count_nonzero(empty)==0 and not trace
    return rows

def load_separator(control,torch):
    from accelerate import init_empty_weights
    from models.mossformer2_ss.mossformer2 import MossFormer2_SS_16K
    root=Path(control['sourceRoot']).resolve()
    import inspect
    assert Path(inspect.getfile(MossFormer2_SS_16K)).resolve().is_relative_to(root)
    options=SimpleNamespace(encoder_embedding_dim=512,mossformer_sequence_dim=512,
                            num_mossformer_layer=24,encoder_kernel_size=16,num_spks=2)
    # The public file also contains the optimizer. Map it read-only and retain
    # only the model dictionary; never materialize the optimizer or a second
    # full CPU copy of the model.
    payload=torch.load(control['checkpoint'],map_location='cpu',mmap=True,weights_only=True)
    state=payload['model'];del payload
    with init_empty_weights(include_buffers=False):model=MossFormer2_SS_16K(options).model
    assert set(model.state_dict())==set(state)
    model.load_state_dict(state,strict=True,assign=True)
    assert all(torch.equal(value,state[name]) for name,value in model.state_dict().items())
    model.eval().requires_grad_(False)
    return model,dict(stateTensors=len(state),parameters=sum(p.numel() for p in model.parameters()),
                      strictAllCheckpointTensorsExact=True,optimizerLoadedForTraining=False,
                      metaSkeletonAndMappedModelOnly=True)
