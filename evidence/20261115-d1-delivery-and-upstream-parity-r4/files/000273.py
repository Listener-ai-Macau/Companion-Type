"""Probability-preserving STNO inputs for a pinned target-speaker ASR candidate."""
def stno_from_activity(activity, target_index):
    import numpy as np
    value = np.asarray(activity)
    if value.ndim != 2 or not 0 <= target_index < value.shape[1]:
        raise ValueError('Expected frames by anonymous speakers and a valid target')
    if not np.isfinite(value).all() or np.any(value < 0) or np.any(value > 1):
        raise ValueError('Speaker activity probabilities must lie in[0,1]')
    others = np.concatenate((value[:, :target_index], value[:, target_index + 1:]), axis=1)
    others_silent = np.prod(1 - others, axis=1)
    target = value[:, target_index]
    # Same STNO factorization as the author pipeline. No extra cutoff/calibration.
    result = np.stack(((1-target)*others_silent,
                       target*others_silent,
                       (1-target)*(1-others_silent),
                       target*(1-others_silent)), axis=0)
    if not np.allclose(result.sum(axis=0), 1, atol=1e-6):
        raise ValueError('Invalid STNO probability mass')
    return result

def project_stno(stno, *, source_step_seconds, source_start_seconds,
                 audio_samples, sample_rate=16000, frames=1500):
    """Integrate piecewise-constant source states onto20ms encoder cells.

    Source state probabilities are averaged before any display decisions.
    Any padding after real audio is silence; no last-speaker extension.
    """
    import numpy as np
    value = np.asarray(stno)
    if value.ndim != 2 or value.shape[0] != 4:
        raise ValueError('Expected fourSTNO states')
    if source_step_seconds <= 0 or source_start_seconds < 0 or audio_samples <= 0:
        raise ValueError('Invalid source clock or audio size')
    cell = .02
    duration = audio_samples / sample_rate
    if duration > frames*cell + 1e-9:
        raise ValueError('Audio exceeds this fixed encoder input')
    if source_start_seconds + duration > value.shape[1]*source_step_seconds + 1e-6:
        raise ValueError('Activity stream does not cover original audio')
    cumulative = np.pad(np.cumsum(value.astype(np.float64), axis=1), ((0,0),(1,0))) * source_step_seconds
    def integral(times):
        coordinate = np.minimum(np.asarray(times)/source_step_seconds, value.shape[1])
        left = np.floor(coordinate).astype(np.int64)
        fraction = coordinate-left
        return cumulative[:, left] + value[:, np.minimum(left, value.shape[1]-1)] * fraction * source_step_seconds
    starts = np.minimum(np.arange(frames)*cell, duration)
    ends = np.minimum((np.arange(frames)+1)*cell, duration)
    output = (integral(source_start_seconds+ends)-integral(source_start_seconds+starts))/cell
    output[0] += 1-(ends-starts)/cell
    output = output.astype(np.float32)
    if np.min(output) < -1e-5 or not np.allclose(output.sum(axis=0),1,atol=2e-5):
        raise ValueError('Clock projection lost probability mass')
    return output
