"""Original frontend patches and conservative contextual source association."""
from pathlib import Path
import wave

def raw_slice(path,start,end,np):
    assert end>start
    with wave.open(str(path),'rb') as f:
        assert (f.getframerate(),f.getnchannels(),f.getsampwidth())==(16000,1,2)
        n=f.getnframes();lo=max(0,start);hi=min(n,end)
        value=np.zeros(end-start,dtype=np.float32)
        if hi>lo:
            f.setpos(lo);value[lo-start:hi-start]=np.frombuffer(f.readframes(hi-lo),dtype='<i2').astype(np.float32)/32768
    return value,n

def feature_block(audio,first,last,extractor,torch,np,*,replacement=None):
    """Same unnormalized frontend block shape, global preemphasis and padding."""
    assert last>first and extractor.n_fft==512 and extractor.hop_length==160
    start=first*160-256;end=(last-1)*160+256
    raw,n=raw_slice(audio,start-1,end,np)
    if replacement is not None:
        low,high,mask,stream=replacement
        lo=max(0,start-1,low);hi=min(n,end,high)
        if hi>lo:
            local=np.arange(lo,hi)-low;selected=mask[local]
            raw[np.arange(lo,hi)[selected]-(start-1)]=stream[local[selected]]
    x=torch.from_numpy(raw);value=x[1:]-extractor.preemphasis*x[:-1]
    if start<=0<end:value[-start]=x[1-start]
    if start<0:value[:min(len(value),-start)]=0
    if end>n:value[max(0,n-start):]=0
    with torch.no_grad():output=extractor._torch_extract_fbank_features(value[None],device='cpu',center=False)[0]
    assert output.shape==(last-first,128)
    # The original frontend masks the final padded feature, even if its STFT exists.
    valid=n//160
    if last>valid:output[max(0,valid-first):]=0
    return output

def active_slots(probabilities,np):
    result=[]
    for channel in range(8):
        values=probabilities[:,channel]
        last=np.maximum.accumulate(np.where(values!=.5,np.arange(len(values)),-1))
        result.append((last>=0)&(values[np.maximum(last,0)]>.5))
    return np.stack(result,axis=1)

def blocks_for_mask(low,mask,total_frames,np):
    changed=np.flatnonzero(mask)+low;assert len(changed)
    first=max(0,(int(changed[0])-512)//160)
    last=min(total_frames,(int(changed[-1])+512)//160+2)
    return [(start,min(start+3000,total_frames)) for start in range(first//3000*3000,last,3000)]

def associate_case(case,slots,legacy,queries,np):
    """No reference identities; ambiguous source pairs remain explicitly unknown."""
    low,high=case['sourceStartFrame'],case['sourceEndFrame']
    first=low//160;last=(high+159)//160;segments=[];resolved=unresolved=0
    for g in range(first,last):
        start=max(low,g*160)-low;end=min(high,(g+1)*160)-low
        ids=np.flatnonzero(slots[g]).tolist();overlap=bool(legacy[g])
        speakers=[ids[0] if len(ids)==1 else None,None]
        reason='original-single-slot' if len(ids)==1 else 'original-activity-uncertain'
        if overlap:
            local=g-first;pred=[q['probabilities'][local] for q in queries]
            hints=[int(q['activity'][local].argmax()) for q in queries]
            winners=[int(p.argmax()) for p in pred]
            unique=all(int((p==p.max()).sum())==1 for p in pred)
            ok=len(ids)==2 and unique and winners[0]!=winners[1] and set(winners)==set(ids) and hints==[1,1]
            speakers=winners if ok else [None,None]
            reason='contextual-distinct-single-source-agreement' if ok else 'separated-source-association-unconfirmed'
            if ok:resolved+=end-start
            else:unresolved+=end-start
        key=(overlap,tuple(speakers),reason)
        if segments and segments[-1]['key']==key:segments[-1]['endFrame']=end
        else:segments.append(dict(startFrame=start,endFrame=end,key=key,predictedModelSlots=speakers,
            overlapRoute=overlap,associationReason=reason,originalPredictedSlots=ids))
    assert segments[0]['startFrame']==0 and segments[-1]['endFrame']==high-low
    assert all(a['endFrame']==b['startFrame'] for a,b in zip(segments,segments[1:]))
    for row in segments:
        row.pop('key');row['globalPredictedSpeakerIds']=[case['meeting']+'/group'+str(i) if i is not None else None for i in row['predictedModelSlots']]
    return dict(id=case['id'],meeting=case['meeting'],frames=high-low,segments=segments,
        overlapResolvedFrames=resolved,overlapUnconfirmedFrames=unresolved,
        sourceAudioAndWordsChanged=False,speakerIdentityVerified=False,wordSpeakerAlignmentImplemented=False)
