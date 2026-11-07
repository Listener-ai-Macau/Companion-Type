"""Keep original ASR text; attribute model token onsets conservatively.

Onsets are model estimates. No true word durations or real names are inferred.
"""
import math

def normalized_journal(journal):
    """Display consecutive anonymous IDs; preserve native IDs in provenance."""
    ordered=sorted(journal['segments'],key=lambda row:(row['start'],row['end'],row['speaker']))
    mapping={value:index for index,value in enumerate(dict.fromkeys(row['speaker'] for row in ordered))}
    return {**journal,'segments':[{**row,'speaker':mapping[row['speaker']]} for row in journal['segments']]},mapping

def token_text_spans(text,tokens):
    pieces=[str(t).replace('▁',' ').removesuffix('@@') for t in tokens]
    visible=[(i,c) for i,c in enumerate(text) if not c.isspace()]
    compact=lambda t:''.join(c for c in t if not c.isspace())
    if ''.join(compact(p) for p in pieces)!=''.join(c for _,c in visible):return None
    cursor=0;previous=0;result=[]
    for piece in pieces:
        n=len(compact(piece))
        end=visible[cursor+n-1][0]+1 if n else previous
        result.append([previous,end]);previous=end;cursor+=n
    if result:result[-1][1]=len(text)
    assert ''.join(text[a:b] for a,b in result)==text
    return result

def onset_attribution(onset,journal,*,duration,margin=.06):
    if not math.isfinite(onset) or not 0<=onset<=duration:raise ValueError('Invalid model onset')
    low=max(0.,onset-margin);high=min(duration,onset+margin)
    relevant=[r for r in journal if r['start']<high and r['end']>low]
    points=sorted({low,high}|{max(low,min(high,r[k])) for r in relevant for k in ['start','end']})
    sets=[{r['speaker'] for r in relevant if r['start']<b and r['end']>a} for a,b in zip(points,points[1:]) if b>a]
    candidates=sorted(set().union(*sets)) if sets else []
    stable=bool(sets and len(candidates)==1 and all(s=={candidates[0]} for s in sets))
    overlap=any(len(s)>1 for s in sets)
    return {'speaker':candidates[0] if stable else None,'candidateSpeakers':candidates,'attribution':'single_predicted_speaker_around_estimated_onset' if stable else 'overlap_requires_recovery' if overlap else 'boundary_or_gap_unconfirmed','overlapDetectedNearOnset':overlap,'timeUncertaintyMarginSeconds':margin}

def align_window(raw,journal,*,audio_seconds):
    text=raw['text'];tokens=raw['tokens'];times=raw['timestamps'];start=raw['startSample']/16000;end=raw['endSample']/16000
    if not isinstance(text,str) or not 0<=start<end<=audio_seconds:raise ValueError('Invalid original window')
    if len(tokens)!=len(times) or any(not math.isfinite(t) or not 0<=t<end-start or round((start+t)*1000)>=round(end*1000) for t in times) or times!=sorted(times):raise ValueError('Invalid native token timing')
    spans=token_text_spans(text,tokens)
    if spans is None or (text and not spans):
        return {'alignmentAvailable':False,'rawText':text,'tokenEstimates':[],'utterances':([{'text':text,'startMs':round(start*1000),'endMs':round(end*1000),'speaker':None,'approximateTiming':True,'attribution':'token_text_alignment_unavailable'}] if text else [])}
    rows=[]
    for token,offset,span in zip(tokens,times,spans):
        onset=min(audio_seconds,start+offset)
        rows.append({'token':token,'textStart':span[0],'textEnd':span[1],'estimatedOnsetSeconds':onset,**onset_attribution(onset,journal,duration=audio_seconds)})
    groups=[]
    for row in rows:
        key=(row['speaker'],row['attribution'],tuple(row['candidateSpeakers']))
        if groups and groups[-1]['key']==key:groups[-1]['rows'].append(row)
        else:groups.append({'key':key,'rows':[row]})
    utterances=[];leading=''
    for group in groups:
        first=group['rows'][0];last=group['rows'][-1];fragment=text[first['textStart']:last['textEnd']]
        if not fragment:continue
        if not fragment.strip():
            if utterances:utterances[-1]['text']+=fragment
            else:leading+=fragment
            continue
        fragment=leading+fragment;leading=''
        utterances.append({'text':fragment,'startMs':round(first['estimatedOnsetSeconds']*1000),'endMs':max(round(first['estimatedOnsetSeconds']*1000)+1,round(min(end,last['estimatedOnsetSeconds']+.06)*1000)),'speaker':first['speaker'],'approximateTiming':True,'attribution':first['attribution'],'candidateSpeakers':first['candidateSpeakers'],'sourceWindow':raw['index'],'timeScope':'Native token onset estimates; end is last onset plus one60ms frame, not verified word duration.'})
    assert ''.join(r['text'] for r in utterances)==text,'Attribution must never drop or rewrite ASR text'
    return {'alignmentAvailable':True,'rawText':text,'tokenEstimates':rows,'utterances':utterances}
