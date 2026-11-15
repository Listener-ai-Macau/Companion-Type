"""Frozen author speaker embeddings, reusable multi-reference enrollment, same mask weights."""
def encode_reference(base,wave,*,torch):
    assert wave.ndim==2 and wave.shape[0]==1 and wave.shape[1]>512
    assert base.feat_type=='consistent' and not base.spk_feat and isinstance(base.spk_transform,torch.nn.Identity)
    with torch.inference_mode():
        peak=wave.abs().max();assert float(peak)>0;wave=wave/peak
        value=base.preEmphasis(wave);value=base.spk_encoder(value)+1e-8;value=value.log();value=value-value.mean(dim=-1,keepdim=True);value=value.permute(0,2,1);value=base.spk_model(value);value=value[-1] if isinstance(value,tuple) else value;value=base.spk_transform(value);assert torch.isfinite(value).all()
    return value.detach().clone()
class SpeakerReferenceBank:
    """Known identity enrollment only; never infer identity from text or relabel data."""
    def __init__(self,base,*,torch):self.base=base;self.torch=torch;self._references={}
    def add(self,speaker_id,segment_id,wave):
        group=self._references.setdefault(speaker_id,{})
        if segment_id in group:raise ValueError('Reference segment already registered')
        group[segment_id]=encode_reference(self.base,wave,torch=self.torch)
        return group[segment_id].detach().clone()
    def prototype(self,speaker_id):
        group=self._references[speaker_id];assert group
        # Keep the author's raw embedding coordinate system and magnitude.
        # One reference is exactly the original conditioning vector.
        return self.torch.stack(list(group.values()),dim=0).mean(dim=0)
    def reference_count(self,speaker_id):return len(self._references[speaker_id])
def make_reference_embedding_extractor(base,*,torch):
    """Configure a dedicated inference instance once; no per-call global switches."""
    from companion_tse_training_20261108 import make_spatial_extractor
    assert base.joint_training and isinstance(base.spk_transform,torch.nn.Identity)
    extractor=make_spatial_extractor(base,torch=torch)
    # All modules and parameters stay present. The author forward supports
    # direct speaker vectors when the joint audio-encoder branch is skipped.
    base.joint_training=False
    return extractor.eval()
