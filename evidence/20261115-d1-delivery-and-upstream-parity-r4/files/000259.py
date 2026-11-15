"""Extend the original bounded recovery to ambiguous automatic empty output.

No language guess or missing word is inserted. A nonzero span producing
language None and no text is re-examined through disjoint audio halves. If
still ambiguous at the original bounds, retain an explicit review interval.
"""
from practical_qwen_bounded_decode_20261107 import accepted

def ambiguous_empty(raw,language_mode):
    return (language_mode=='auto' and not raw.get('exactDigitalSilence')
            and raw.get('language') is None and not raw['text'].strip())

def recover_local_decode(start,end,*,infer,load,save,language_mode,depth=0,key='root'):
    assert type(start) is int and type(end) is int and 0<=start<end
    raw=load(key)
    if raw is None:
        raw=infer(start,end)
        assert raw['startSample']==start and raw['endSample']==end
        save(key,raw)
    assert raw['startSample']==start and raw['endSample']==end
    valid=accepted(raw);ambiguous=ambiguous_empty(raw,language_mode)
    if valid and not ambiguous:
        return [{'key':key,'raw':raw,'reviewRequired':False}]
    middle=(start+end)//2
    if depth>=2 or min(middle-start,end-middle)<120000:
        if valid and ambiguous:
            return [{'key':key,'raw':raw,'reviewRequired':True,
                     'reviewReason':'Nonzero audio has no transcript and no identified language; speech absence unverified'}]
        raise RuntimeError('Original bounded decode recovery exhausted; all failed raw nodes retained')
    left=recover_local_decode(start,middle,infer=infer,load=load,save=save,language_mode=language_mode,depth=depth+1,key=key+'a')
    right=recover_local_decode(middle,end,infer=infer,load=load,save=save,language_mode=language_mode,depth=depth+1,key=key+'b')
    result=left+right
    assert result[0]['raw']['startSample']==start and result[-1]['raw']['endSample']==end
    assert all(a['raw']['endSample']==b['raw']['startSample'] for a,b in zip(result,result[1:]))
    return result
