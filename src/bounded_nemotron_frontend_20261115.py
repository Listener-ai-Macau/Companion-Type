"""Bound allocations while retaining the upstream per-frame frontend formula.

The extractor still handles full-recording preemphasis, lengths and masking.
Only its STFT/mel call is partitioned at exact hop boundaries, after global
edge padding. Each block calls the unmodified installed upstream method.
No model, cache geometry, threshold or learned weights are changed.
"""


def install_bounded_frontend(extractor, frames_per_block=3000):
    import torch

    original = extractor._torch_extract_fbank_features
    hop, fft = extractor.hop_length, extractor.n_fft
    assert frames_per_block == 3000 and fft == 512 and hop == 160

    def bounded(waveform, device="cpu", center=True):
        assert device == "cpu" and waveform.device.type == "cpu"
        assert waveform.ndim == 2 and waveform.dtype == torch.float32
        if center:
            waveform = torch.nn.functional.pad(waveform, (fft // 2, fft // 2))
        frames = (waveform.shape[-1] - fft) // hop + 1
        assert frames > 0
        result = torch.empty(
            (waveform.shape[0], frames, extractor.feature_size), dtype=torch.float32
        )
        for first in range(0, frames, frames_per_block):
            last = min(first + frames_per_block, frames)
            block = waveform[:, first * hop : (last - 1) * hop + fft]
            value = original(block, device=device, center=False)
            assert value.shape[1] == last - first
            result[:, first:last] = value
        return result

    extractor._torch_extract_fbank_features = bounded
    return original
