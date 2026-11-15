"""Trainable speaker-conditioned extraction with zero-impact spatial adapters.

The complete pinned mono backbone stays unmodified. Per-band spatial residuals
are injected through hooks with zero-initialized projections. Recognition math
is the official log-mel computation without the NumPy/detach boundary.
"""
import math,re

def differentiable_fbank(waveform,extractor,*,torch):
    """Same official single-wave log-mel frontend, retaining the input graph."""
    assert waveform.ndim==1 and extractor.dither==0.0 and extractor.sampling_rate==16000
    x=waveform
    if x.numel()<extractor.min_length:x=torch.nn.functional.pad(x,(0,extractor.min_length-x.numel()))
    window=torch.hann_window(extractor.n_fft,device=x.device,dtype=x.dtype)
    spec=torch.stft(x.unsqueeze(0),extractor.n_fft,extractor.hop_length,window=window,return_complex=True)
    power=spec[...,:-1].abs().square();mel=torch.as_tensor(extractor.mel_filters,device=x.device,dtype=x.dtype)
    log=(mel.T@power).clamp_min(1e-10).log10();maximum=log.max(dim=2,keepdim=True)[0].max(dim=1,keepdim=True)[0];log=torch.maximum(log,maximum-8.0);log=(log+4.0)/4.0
    frames=log.shape[-1];mask=torch.ones((1,frames),device=x.device,dtype=torch.long);multiple=extractor.n_window*2;pad=(-frames)%multiple if multiple>1 else 0
    if pad:log=torch.nn.functional.pad(log,(0,pad));mask=torch.nn.functional.pad(mask,(0,pad))
    return log,mask

def make_spatial_extractor(base,*,torch):
    class SpatialExtractor(torch.nn.Module):
        def __init__(self):
            super().__init__();self.base=base;self.spatial=torch.nn.ModuleList([torch.nn.Conv1d(3*width,base.feature_dim,1,bias=False) for width in base.band_width]);self._features=None;self._hooks=[]
            for projection in self.spatial:torch.nn.init.zeros_(projection.weight)
            for index,normalizer in enumerate(self.base.BN):
                def hook(module,inputs,output,index=index):
                    if self._features is None:return output
                    extra=self.spatial[index](self._features[index]);assert extra.shape==output.shape
                    return output+extra
                self._hooks.append(normalizer.register_forward_hook(hook))
            # Keep the speaker representation frozen; train the actual audio
            # separation backbone, complex mask heads and spatial projections.
            for name,p in self.base.named_parameters():p.requires_grad_(not name.startswith(('spk_model.','spk_encoder.','pred_linear.')))
        def forward(self,pair,profile):
            assert pair.ndim==3 and pair.shape[1] in (1,2) and profile.ndim==2
            self._features=None
            if pair.shape[1]==2:
                window=torch.hann_window(self.base.win,device=pair.device,dtype=pair.dtype)
                a=torch.stft(pair[:,0],self.base.win,self.base.stride,window=window,return_complex=True);b=torch.stft(pair[:,1],self.base.win,self.base.stride,window=window,return_complex=True)
                cross=a*b.conj();denominator=a.abs()*b.abs()+1e-8;cosine=cross.real/denominator;sine=cross.imag/denominator;level=((a.abs()+1e-8).log()-(b.abs()+1e-8).log()).clamp(-8,8)
                self._features=[];lo=0
                for width in self.base.band_width:
                    self._features.append(torch.cat([cosine[:,lo:lo+width],sine[:,lo:lo+width],level[:,lo:lo+width]],1));lo+=width
                assert lo==a.shape[1]
            try:return self.base(pair[:,0],profile)[0]
            finally:self._features=None
        def train(self,mode=True):
            super().train(mode);self.base.spk_model.eval();return self
    return SpatialExtractor()

def target_text(example):
    """Remove annotation control markers only; keep words, disfluencies/punctuation."""
    return re.sub(r'<[^>]*>','',example['referenceTranscriptForTrainingOnly']).replace('&','').strip()

def teacher_batch(waveform,text,processor,*,torch):
    # The standard processor supplies only the frozen prompt/token geometry.
    # Replace its detached acoustic values with the identical connected values.
    inputs=processor.apply_transcription_request(audio=waveform.detach().float().cpu().numpy(),language='Chinese',processor_kwargs={'audio_kwargs':{'sampling_rate':16000,'device':str(waveform.device)}})
    features,feature_mask=differentiable_fbank(waveform,processor.feature_extractor,torch=torch)
    assert features.shape==inputs['input_features'].shape and torch.equal(feature_mask.cpu(),inputs['input_features_mask'])
    prefix=inputs['input_ids'].to(waveform.device);prefix_length=prefix.shape[1];ids=processor.tokenizer.encode(text,add_special_tokens=False)+[processor.tokenizer.eos_token_id]
    targets=torch.tensor(ids,device=waveform.device,dtype=torch.long).unsqueeze(0);input_ids=torch.cat([prefix,targets],1)
    labels=torch.full_like(input_ids,-100);labels[:,prefix_length:]=targets
    positions=torch.arange(prefix_length-1,input_ids.shape[1]-1,device=waveform.device)
    return {'input_ids':input_ids,'attention_mask':torch.ones_like(input_ids),'input_features':features,'input_features_mask':feature_mask,'labels':labels,'target_ids':targets,'logit_positions':positions,'prefix_length':prefix_length}

def teacher_loss(teacher,batch,*,torch):
    outputs=teacher(input_ids=batch['input_ids'],attention_mask=batch['attention_mask'],input_features=batch['input_features'].to(teacher.dtype),input_features_mask=batch['input_features_mask'],use_cache=False,logits_to_keep=batch['logit_positions'])
    assert outputs.logits.shape[:2]==batch['target_ids'].shape
    return torch.nn.functional.cross_entropy(outputs.logits.float().reshape(-1,outputs.logits.shape[-1]),batch['target_ids'].reshape(-1))

def waveform_supervision(output,pair,example,*,torch):
    """Noisy annotated solo/absence targets; no invented clean overlap waveform."""
    assert output.ndim==1 and pair.shape==(2,output.numel());mask=torch.zeros_like(output,dtype=torch.bool);start=example['sourceStartSample']/16000
    for row in example['targetUtterancesForTrainingOnly']:
        a=max(0,math.floor((row['start']-start)*16000));b=min(output.numel(),math.ceil((row['end']-start)*16000));mask[a:b]=True
    scale=pair[0].abs().mean().clamp_min(1e-4)
    if example['category']=='absent_other_speech':
        assert not mask.any();return output.abs().mean()/scale,{'kind':'annotated_lexical_target_absent','supervisedSamples':output.numel()}
    if example['category']=='present_solo':
        target=torch.where(mask,pair[0],0.);return (output-target).abs().mean()/scale,{'kind':'noisy_original_target_during_nonoverlapping_annotation','supervisedSamples':output.numel()}
    assert example['category']=='present_overlap'
    inactive=~mask
    loss=output[inactive].abs().sum()/output.numel()/scale
    return loss,{'kind':'only_target_inactive_samples_supervised_no_clean_overlap_target','supervisedSamples':int(inactive.sum())}
