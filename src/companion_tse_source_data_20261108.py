"""Shared immutable PCM and real-annotation helpers for known-component training."""
from pathlib import Path
import hashlib,json,math,wave
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pcm_write(path,value):
    import numpy as np
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);value=np.asarray(value,dtype='<i2');assert value.ndim==2
    if path.exists():assert np.array_equal(pcm_read(path,value.shape[1]),value),'Never overwrite a different prepared source'
    else:
        with wave.open(str(path),'wb') as f:f.setnchannels(value.shape[1]);f.setsampwidth(2);f.setframerate(16000);f.writeframes(value.tobytes())
    return {'audio':str(path),'audioSha256':sha(path),'audioSeconds':len(value)/16000,'channels':value.shape[1]}
def pcm_read(path,channels):
    import numpy as np
    with wave.open(str(path),'rb') as f:assert f.getnchannels()==channels and f.getframerate()==16000 and f.getsampwidth()==2;return np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,channels).copy()
def overlap(a,b,c,d):return max(0.,min(b,d)-max(a,c))
def truth_rows(reference):
    from reference_textgrid_20261104 import read_reference_intervals
    from full_meeting_transcript_metrics_20261103 import normalize
    return [x for x in read_reference_intervals(reference) if normalize(x['text'])]
def profile_interval(truth,person,duration):
    own=[x for x in truth if x['speaker']==person];other=[x for x in truth if x['speaker']!=person];choices=[]
    # Earliest maximum-coverage eight-second single-person enrollment.
    for x in own:
        for a in [max(0.,x['start']-.05),max(0.,x['end']-7.95)]:
            b=a+8.
            if b>duration or any(overlap(a,b,y['start'],y['end'])>0 for y in other):continue
            coverage=sum(overlap(a,b,y['start'],y['end']) for y in own)
            if coverage>=2.:choices.append((coverage,-a,a,b))
    assert choices,'No valid eight-second independent profile: '+person
    _,_,a,b=max(choices);return math.floor(a*16000),math.ceil(b*16000)
