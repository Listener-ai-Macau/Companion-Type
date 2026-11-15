"""Sample-preserving original-mic/overlap routing; no text or references."""
def compose_routes(original,separated,overlap_mask,np):
    assert original.ndim==1 and separated.shape==(2,len(original))
    assert overlap_mask.shape==original.shape and overlap_mask.dtype==np.bool_
    assert original.dtype==separated.dtype==np.float32
    assert np.isfinite(original).all() and np.isfinite(separated).all()
    lanes=np.zeros_like(separated);lanes[0]=original
    lanes[0,overlap_mask]=separated[0,overlap_mask]
    lanes[1,overlap_mask]=separated[1,overlap_mask]
    assert np.array_equal(lanes[0,~overlap_mask],original[~overlap_mask])
    assert np.count_nonzero(lanes[1,~overlap_mask])==0
    assert np.array_equal(lanes[:,overlap_mask],separated[:,overlap_mask])
    return lanes
