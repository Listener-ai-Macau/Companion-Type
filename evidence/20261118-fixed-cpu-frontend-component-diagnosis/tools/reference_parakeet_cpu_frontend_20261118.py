"""CPU-only implementation of the pinned Parakeet v3 signal contract.

Keep the exact signed PCM scaling, valid-frame count and zeroed final padding
used by the reference implementation. This module loads no model or Torch.
"""
import numpy as np

SAMPLE_RATE = 16000
HOP = 160
FFT_SIZE = 512
WINDOW = 400
MEL_BINS = 128


def slaney_filter_bank():
    linear_step = 200.0 / 3
    log_break = 1000.0 / linear_step
    log_step = np.log(6.4) / 27
    nyquist_mel = log_break + np.log((SAMPLE_RATE / 2) / 1000.0) / log_step
    mel_points = np.linspace(0.0, nyquist_mel, MEL_BINS + 2)
    frequencies = mel_points * linear_step
    logarithmic = mel_points >= log_break
    frequencies[logarithmic] = 1000.0 * np.exp(log_step * (mel_points[logarithmic] - log_break))
    fft_frequencies = np.fft.rfftfreq(FFT_SIZE, 1.0 / SAMPLE_RATE)
    differences = np.diff(frequencies)
    slopes = frequencies[:, None] - fft_frequencies[None, :]
    lower = -slopes[:-2] / differences[:-1, None]
    upper = slopes[2:] / differences[1:, None]
    weights = np.maximum(0.0, np.minimum(lower, upper)).astype(np.float32)
    weights *= (2.0 / (frequencies[2:] - frequencies[:-2]))[:, None]
    return weights


FILTERS = slaney_filter_bank()
HANN = np.pad(np.hanning(WINDOW).astype(np.float32), ((FFT_SIZE - WINDOW) // 2,) * 2)


def extract(pcm16):
    waveform = np.frombuffer(pcm16, dtype='<i2').astype(np.float32) / 32768
    valid_frames = len(waveform) // HOP
    if valid_frames < 2:
        raise ValueError('At least two feature frames are required for sample variance')

    emphasized = waveform.copy()
    emphasized[1:] -= np.float32(0.97) * waveform[:-1]
    padded = np.pad(emphasized, (FFT_SIZE // 2, FFT_SIZE // 2))
    windows = np.lib.stride_tricks.sliding_window_view(padded, FFT_SIZE)[::HOP]
    spectrum = np.fft.rfft(windows * HANN, axis=-1)
    power = np.abs(spectrum).astype(np.float32) ** 2
    energies = power @ FILTERS.T
    logged = np.log(energies + np.float32(2**-24))

    features = np.zeros_like(logged)
    valid = logged[:valid_frames]
    mean = valid.mean(axis=0, dtype=np.float32)
    variance = ((valid - mean) ** 2).sum(axis=0, dtype=np.float32) / (valid_frames - 1)
    features[:valid_frames] = (valid - mean) / (np.sqrt(variance) + np.float32(1e-5))
    return np.ascontiguousarray(features), valid_frames
