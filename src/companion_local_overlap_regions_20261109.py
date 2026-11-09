"""Frozen powerset local speaker-count reconstruction, without global labels.

Reuses the maintained recipe's argmax classes and rounded cross-window count;
does not use clustering, a guessed participant count, or threshold search.
"""
def local_overlap_regions(logits, meta, *, source_frames):
    import numpy as np
    from bounded_speaker_20261107 import frame_start
    assert logits.ndim == 3 and logits.shape[-1] == 7
    assert meta['num_speakers'] == 3 and meta['powerset_max_classes'] == 2
    assert meta['sample_rate'] == 16000
    windows, frames = logits.shape[:2]
    full = (meta['window_size'] + (windows - 1) * meta['window_shift']) // meta['receptive_field_shift'] + 1
    weights = np.zeros(full, dtype=np.float32)
    count = np.zeros(full, dtype=np.float32)
    classes = np.array([0, 1, 1, 1, 2, 2, 2], dtype=np.uint8)
    for index in range(windows):
        first = frame_start(index, meta)
        last = first + frames
        assert last <= full
        weights[first:last] += 1
        count[first:last] += classes[np.argmax(logits[index], axis=-1)]
    expected = (count / (weights + np.float32(1e-12)) + np.float32(.5)).astype(np.int32)
    keep = full
    if (source_frames - meta['window_size']) % meta['window_shift'] > 0:
        keep = min(source_frames // meta['receptive_field_shift'] + 1, full)
    expected = expected[:keep]
    mask = expected >= 2
    edges = np.diff(np.r_[0, mask, 0].astype(np.int8))
    first = np.flatnonzero(edges == 1)
    last = np.flatnonzero(edges == -1)
    scale = np.float32(meta['receptive_field_shift'] / meta['sample_rate'])
    offset = np.float32(.5 * meta['receptive_field_size'] / meta['sample_rate'])
    at = lambda frame: float(np.float32(np.float32(frame) * scale + offset))
    duration = source_frames / meta['sample_rate']
    regions = []
    for a, b in zip(first, last):
        begin, end = max(0, at(a)), min(duration, at(b))
        if begin < end:
            regions.append({'start': begin, 'end': end})
    return regions, {'frames': keep, 'sourceFrames': source_frames,
                     'powersetArgmaxClassCount': 7, 'referenceRead': False,
                     'windowAggregation': 'published rounded mean local speaker count',
                     'globalSpeakerClusteringUsed': False}


def posterior_overlap_regions(log_probabilities, meta, *, source_frames):
    """Marginalize mutually exclusive pair classes before binary overlap decision.

    This is a fixed alternative to hard powerset argmax, not calibrated truth.
    The cutoff stays 0.5 on every recording; no fitted thresholds or smoothing.
    """
    import numpy as np
    from bounded_speaker_20261107 import frame_start
    assert log_probabilities.ndim == 3 and log_probabilities.shape[-1] == 7
    assert meta['num_speakers'] == 3 and meta['powerset_max_classes'] == 2
    assert meta['sample_rate'] == 16000
    windows, frames = log_probabilities.shape[:2]
    full = (meta['window_size'] + (windows - 1) * meta['window_shift']) // meta['receptive_field_shift'] + 1
    weights = np.zeros(full, dtype=np.float32)
    probability = np.zeros(full, dtype=np.float32)
    largest_normalization_error = 0.
    for index in range(windows):
        value = np.asarray(log_probabilities[index])
        if not np.isfinite(value).all():
            raise ValueError('Finite pinned log-softmax output required')
        value = np.exp(value)
        error = float(np.max(np.abs(value.sum(axis=-1) - 1)))
        if error > 2e-5:
            raise ValueError('Not normalized mutually exclusive powerset log-probabilities')
        largest_normalization_error = max(largest_normalization_error, error)
        first = frame_start(index, meta)
        last = first + frames
        assert last <= full
        weights[first:last] += 1
        # Classes4,5,6 are the mutually exclusive AB, AC, BC speaker pairs.
        probability[first:last] += value[:, 4:7].sum(axis=-1)
    probability /= weights + np.float32(1e-12)
    keep = full
    if (source_frames - meta['window_size']) % meta['window_shift'] > 0:
        keep = min(source_frames // meta['receptive_field_shift'] + 1, full)
    probability = probability[:keep]
    edges = np.diff(np.r_[0, probability >= np.float32(.5), 0].astype(np.int8))
    first = np.flatnonzero(edges == 1)
    last = np.flatnonzero(edges == -1)
    scale = np.float32(meta['receptive_field_shift'] / meta['sample_rate'])
    offset = np.float32(.5 * meta['receptive_field_size'] / meta['sample_rate'])
    at = lambda frame: float(np.float32(np.float32(frame) * scale + offset))
    duration = source_frames / meta['sample_rate']
    regions = []
    for a, b in zip(first, last):
        begin, end = max(0, at(a)), min(duration, at(b))
        if begin < end:
            regions.append({'start': begin, 'end': end})
    return regions, {'frames': keep, 'sourceFrames': source_frames,
                     'cutoff': .5, 'sourceOutputsAreLogProbabilities': True,
                     'largestProbabilityNormalizationError': largest_normalization_error,
                     'windowAggregation': 'uniform mean overlap marginal probability',
                     'globalSpeakerClusteringUsed': False,
                     'probabilitiesAreNotGuaranteedCalibrated': True}, probability
