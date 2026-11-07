"""Content-independent, bounded recovery of failed autoregressive decodes.

No repeated words are removed. A failed node is kept and its entire input
is covered by two disjoint children. A successful node keeps every raw ID.
The repetition definition is the pre-existing short control's20 copies of
a block of1..8 tokens. No reference, VAD, threshold sweep or hotword input.
"""

def repeated_block(ids,*,suffix_only=False):
    for size in range(1,9):
        length=size*20
        if len(ids)<length:continue
        offsets=[len(ids)-length] if suffix_only else range(len(ids)-length+1)
        for offset in offsets:
            block=ids[offset:offset+size]
            if ids[offset:offset+length]==block*20:
                return {'offset':offset,'blockTokens':size,'repetitions':20}
    return None

def accepted(raw):
    if raw.get('exactDigitalSilence'):
        assert raw['text']=='' and raw['generatedIds']==[] and raw['naturalEos'] is None
        return True
    return bool(raw['naturalEos']) and repeated_block(raw['generatedIds']) is None

def recover(start,end,*,infer,load,save,depth=0,key='root',seed=None):
    """Callbacks are scoped to one root; cache bindings belong to the caller."""
    assert isinstance(start,int) and isinstance(end,int) and 0<=start<end
    raw=load(key)
    if raw is None:
        raw=seed if seed is not None else infer(start,end)
        assert raw['startSample']==start and raw['endSample']==end
        save(key,raw)
    assert raw['startSample']==start and raw['endSample']==end
    if accepted(raw):return [{'key':key,'raw':raw}]
    # Exactly two levels, and no child shorter than7.5s at16kHz.
    middle=(start+end)//2
    if depth>=2 or min(middle-start,end-middle)<120000:
        raise RuntimeError('Bounded decode recovery exhausted; all failed raw output retained')
    left=recover(start,middle,infer=infer,load=load,save=save,depth=depth+1,key=key+'a')
    right=recover(middle,end,infer=infer,load=load,save=save,depth=depth+1,key=key+'b')
    result=left+right
    assert result[0]['raw']['startSample']==start and result[-1]['raw']['endSample']==end
    assert all(a['raw']['endSample']==b['raw']['startSample'] for a,b in zip(result,result[1:]))
    return result
