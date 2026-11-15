"""Scale-sensitive positive waveform preservation plus spectral/source consistency."""
def positive_loss(estimate,target,*,torch):
    assert estimate.ndim==target.ndim==1 and estimate.shape==target.shape
    scale=target.abs().mean().detach().clamp_min(1e-4);time=(estimate-target).abs().mean()/scale;spectral=[]
    for size in [256,512,1024]:
        window=torch.hann_window(size,device=estimate.device,dtype=estimate.dtype)
        a=torch.stft(estimate,size,size//4,window=window,return_complex=True).abs();b=torch.stft(target,size,size//4,window=window,return_complex=True).abs()
        convergence=(a-b).norm()/b.norm().detach().clamp_min(1e-5);log=(a.clamp_min(1e-5).log()-b.clamp_min(1e-5).log()).abs().mean();spectral.append(convergence+log)
    return time+sum(spectral)/len(spectral)
def consistency_loss(first,second,mixture,*,torch):return (first+second-mixture).abs().mean()/mixture.abs().mean().detach().clamp_min(1e-4)
def absence_loss(estimate,mixture,*,torch):return estimate.abs().mean()/mixture.abs().mean().detach().clamp_min(1e-4)
def waveform_metrics(estimate,target,*,torch):
    with torch.no_grad():
        denominator=target.abs().mean().clamp_min(1e-4);ratio=estimate.square().mean().sqrt()/target.square().mean().sqrt().clamp_min(1e-6);error=estimate-target;sdr=10*torch.log10(target.square().mean().clamp_min(1e-10)/error.square().mean().clamp_min(1e-10))
        return {'normalizedL1':float(error.abs().mean()/denominator),'rmsGain':float(ratio),'absoluteRmsGainError':float((ratio-1).abs()),'scaleSensitiveSdrDb':float(sdr)}
