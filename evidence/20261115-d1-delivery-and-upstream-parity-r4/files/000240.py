"""Failure recovery coverage and sticky cached refusals; no neural imports."""
from practical_qwen_bounded_decode_20261107 import accepted,recover,repeated_block

def raw(a,b,ids=None,eos=True,text='unchanged'):
    return {'startSample':a,'endSample':b,'generatedIds':[1,2,3] if ids is None else ids,'naturalEos':eos,'text':text}

assert repeated_block([9]+[1,2]*20+[8])=={'offset':1,'blockTokens':2,'repetitions':20}
assert repeated_block([9]+[1,2]*20,suffix_only=True)['blockTokens']==2
assert repeated_block([1,2]*19) is None
assert not accepted(raw(0,480000,[1,2]*20,eos=True))
cache={};calls=[]
def infer(a,b):
    calls.append((a,b))
    return raw(a,b,[7,8]*20,eos=False) if b-a>120000 else raw(a,b,text=str((a,b)))
leaves=recover(0,480000,infer=infer,load=cache.get,save=lambda k,v:cache.__setitem__(k,v))
assert len(leaves)==4 and len(cache)==7 and len(calls)==7
assert [(x['raw']['startSample'],x['raw']['endSample']) for x in leaves]==[(0,120000),(120000,240000),(240000,360000),(360000,480000)]
before=list(calls);again=recover(0,480000,infer=infer,load=cache.get,save=lambda k,v:cache.__setitem__(k,v))
assert again==leaves and calls==before
# A completed, normal node retains its exact raw object and never subdivides.
normal=raw(0,480000,text='嗯，原话原字。')
assert recover(0,480000,infer=lambda *_:(_ for _ in ()).throw(AssertionError('No inference expected')),load=lambda _:normal,save=lambda *_:None)[0]['raw'] is normal
# Exhaustion is an explicit failure, not an empty/cleaned success.
failed={}
try:recover(0,480000,infer=lambda a,b:raw(a,b,[5]*20,eos=False),load=failed.get,save=lambda k,v:failed.__setitem__(k,v))
except RuntimeError:pass
else:raise AssertionError('Expected bounded failure')
assert len(failed)==3 and all(not accepted(r) for r in failed.values())
print('PASS_BOUNDED_COVERAGE_RAW_PRESERVATION_CACHE_REUSE_AND_EXHAUSTION_NO_MODEL')
