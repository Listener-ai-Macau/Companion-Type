"""Train only the existing conditioned head; retain native inference/state names."""
import torch

class MeetingActivityAdapter(torch.nn.Module):
    def __init__(self,native):
        super().__init__();self.native=native
        assert hasattr(type(native).forward,'__wrapped__'),'Require the pinned author no_grad wrapper, not an assumed alternate graph'
        self._native_forward=type(native).forward.__wrapped__
        for parameter in self.native.parameters():parameter.requires_grad_(True)
        for parameter in self.native.backbone.parameters():parameter.requires_grad_(False)
        self.native.backbone.eval()

    def train(self,mode=True):
        super().train(mode);self.native.backbone.eval();return self

    def forward(self,speaker_embedding,fbank,lengths):
        # The exact author function body, with only its inference-only decorator
        # bypassed. Frozen backbone/inputs do not accumulate gradients.
        return self._native_forward(self.native,speaker_embedding.detach(),fbank,lengths)

    def from_frozen_features(self,speaker_embedding,frame_features,lengths,input_frames):
        native=self.native
        x=native.film(frame_features.detach(),speaker_embedding.detach())
        x=native.feat_proj(x);x=native.speech_encoder(x);x=native.det_decoder(x)
        logits=native.classifier_det(native._extract_chunks(x))
        return {'chunk_logits':logits,'chunk_mask':native._compute_chunk_mask(lengths,input_frames)}

    def trainable_parameters(self):return [p for p in self.parameters() if p.requires_grad]

    def head_state_dict(self):return {k:v.detach().cpu() for k,v in self.native.state_dict().items() if not k.startswith('backbone.')}

    def load_head_state(self,state):
        expected={k for k in self.native.state_dict() if not k.startswith('backbone.')};assert set(state)==expected
        complete=self.native.state_dict();complete.update(state);return self.native.load_state_dict(complete,strict=True)
