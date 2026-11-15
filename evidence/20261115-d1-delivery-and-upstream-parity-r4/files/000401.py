"""Exact absent-signal guard: never suppress weak but nonzero audio."""
def is_exact_digital_silence(samples):
    import numpy as np
    values=np.asarray(samples)
    if values.ndim!=1 or values.size==0:raise ValueError('Require nonempty normalized mono input')
    if values.dtype.kind not in 'fiu':raise ValueError('Require real PCM samples')
    if values.dtype.kind=='f' and not np.isfinite(values).all():raise ValueError('Nonfinite PCM input')
    return not bool(np.any(values))
