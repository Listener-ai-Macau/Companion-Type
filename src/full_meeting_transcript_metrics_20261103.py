"""Research-only anonymous per-speaker CER for real, full-meeting transcripts.

Unlike chronological mixed text, per-speaker concatenation preserves the
ordering of each person's own words during overlap. This is cpCER, with an
optimal anonymous speaker permutation; it does not establish real identity or
word timing. DER and future time-constrained scoring remain separate gates.
"""
from __future__ import annotations
import math,re,sys,unicodedata
sys.path.insert(0,'E:/CodexData/Companion/real-meeting-asr-validation-20261031/evaluation-deps')
from rapidfuzz.distance import Levenshtein
from scipy.optimize import linear_sum_assignment
import numpy as np

def normalize(text):
    return ''.join(c for c in re.sub(r'<[^>]*>','',text) if not c.isspace() and not unicodedata.category(c).startswith(('P','S'))).lower()

def group_transcripts(segments,audio_seconds):
    if not isinstance(audio_seconds,(int,float)) or not math.isfinite(audio_seconds) or audio_seconds<=0:raise ValueError('invalid full audio duration')
    grouped={}
    for row in segments:
        if not isinstance(row,dict):raise ValueError('invalid transcript segment')
        speaker=row.get('speaker');text=row.get('text');start=row.get('start');end=row.get('end')
        if not isinstance(speaker,(str,int)) or isinstance(speaker,bool) or not str(speaker):raise ValueError('explicit anonymous speaker ID required')
        if not isinstance(text,str) or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (start,end)):raise ValueError('invalid text or timing')
        if not (0<=start<end<=audio_seconds+.000001):raise ValueError('reference and audio bounds differ; do not discard crossing words')
        normalized=normalize(text)
        if normalized:grouped.setdefault(str(speaker),[]).append((start,end,normalized))
    return {key:''.join(s for _,_,s in sorted(rows,key=lambda x:(x[0],x[1]))) for key,rows in sorted(grouped.items())}

def speaker_cer(reference_segments,hypothesis_segments,audio_seconds):
    reference=group_transcripts(reference_segments,audio_seconds);hypothesis=group_transcripts(hypothesis_segments,audio_seconds)
    reference_characters=sum(map(len,reference.values()))
    if not reference_characters:raise ValueError('no reference characters')
    ref_names=list(reference);hyp_names=list(hypothesis);size=max(len(reference),len(hypothesis))
    refs=list(reference.values())+['']*(size-len(reference));hyps=list(hypothesis.values())+['']*(size-len(hypothesis))
    costs=np.asarray([[Levenshtein.distance(a,b) for b in hyps] for a in refs],dtype=np.int64)
    rows,columns=linear_sum_assignment(costs);counts={'replace':0,'delete':0,'insert':0};assignment=[]
    for i,j in zip(rows,columns):
        for op in Levenshtein.editops(refs[i],hyps[j]):counts[op.tag]+=1
        assignment.append({'referenceSpeaker':ref_names[i] if i<len(ref_names) else None,
                           'hypothesisSpeaker':hyp_names[j] if j<len(hyp_names) else None,'edits':int(costs[i,j])})
    errors=sum(counts.values())
    return {'metric':'cpCER','audioSeconds':audio_seconds,'referenceCharacters':reference_characters,
            'referenceSpeakers':len(reference),'predictedTextStreams':len(hypothesis),'edits':counts,'totalEdits':errors,
            'characterErrorRate':errors/reference_characters,'anonymousAssignmentForEvaluationOnly':assignment,
            'limits':'Full-meeting per-speaker text concatenation with optimal anonymous assignment; not temporal accuracy or verified real identity. Reference-only text is not a model input.'}
