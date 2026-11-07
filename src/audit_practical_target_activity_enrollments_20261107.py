"""Posthoc enrollment contamination audit; never reselect a profile by GT."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import json
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1');read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert (C/'review.json').exists() and not (C/'enrollment-cause-review.json').exists()
def union(spans):
    result=[]
    for lo,hi in sorted(spans):
        if hi<=lo:continue
        if result and lo<=result[-1][1]:result[-1]=(result[-1][0],max(hi,result[-1][1]))
        else:result.append((lo,hi))
    return result
def length(spans):return sum(hi-lo for lo,hi in spans)
rows=[];review=read(C/'review.json')
for score in read(C/'scoring-only.json'):
    if score['referenceKind']=='rttm_only_words':
        reference=[]
        for line in Path(score['reference']).read_text(encoding='utf8').splitlines():
            f=line.split();lo=float(f[3]);reference.append({'start':lo,'end':lo+float(f[4]),'speaker':f[7]})
    else:reference=[r for r in read_reference_intervals(score['reference']) if normalize(r['text'])]
    meeting=next(m for m in review['meetings'] if m['meeting']==score['meeting']);mapping={int(p):v for p,v in meeting['fixedAnonymousMappingForScoringOnly'].items()}
    for anchor in [r for r in read(C/'automatic-enrollments.json') if r['meeting']==score['meeting']]:
        lo=anchor['startSample']/16000;hi=anchor['endSample']/16000;target=mapping[anchor['speaker']]
        target_spans=union((max(lo,r['start']),min(hi,r['end'])) for r in reference if r['speaker']==target and r['end']>lo and r['start']<hi)
        other_spans=union((max(lo,r['start']),min(hi,r['end'])) for r in reference if r['speaker']!=target and r['end']>lo and r['start']<hi)
        overlap=sum(max(0.,min(b,d)-max(a,c)) for a,b in target_spans for c,d in other_spans);allactive=length(union(target_spans+other_spans))
        rows.append({'meeting':score['meeting'],'anonymousSpeaker':anchor['speaker'],'referencePersonForAuditOnly':target,'enrollmentSeconds':anchor['audioSeconds'],
            'targetReferenceSpeechSeconds':length(target_spans),'otherReferenceSpeechSeconds':length(other_spans),'overlappingOtherVoiceSeconds':overlap,'targetOnlySeconds':length(target_spans)-overlap,
            'targetShareOfAllAnnotatedVoiceSeconds':length(target_spans)/(length(target_spans)+length(other_spans)) if length(target_spans)+length(other_spans)>0 else None,
            'unannotatedOrSilentSeconds':hi-lo-allactive,'candidatePositiveWindowRecallOnSeparateTestClips':meeting['perReferencePersonForEvaluationOnly']['candidate'][target]['positiveWindowRecall'],
            'candidateAbsentWindowFalseAcceptanceOnSeparateTestClips':meeting['perReferencePersonForEvaluationOnly']['candidate'][target]['absentWindowFalseAcceptance']})
clean=[r for r in rows if r['otherReferenceSpeechSeconds']==0 and r['enrollmentSeconds']>=9.5]
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'AUTOMATIC_PROFILE_QUALITY_POSTHOC_AUDITED_NO_RESELECTION','rows':rows,'longProfilesWithoutAnnotatedOtherVoice':len(clean),
    'cleanLongProfileFailures':[r for r in clean if r['candidatePositiveWindowRecallOnSeparateTestClips'] is not None and (r['candidatePositiveWindowRecallOnSeparateTestClips']<.95 or (r['candidateAbsentWindowFalseAcceptanceOnSeparateTestClips'] or 0)>.05)],
    'referenceDoesNotVerifyAcousticPurityBeyondItsAnnotation':True,'amiWordOnlySilenceDifferentFromAishellUtteranceAnnotation':True,'noProfilesReselectedOrFiltered':True,'newNeuralCalls':0,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'enrollment-cause-review.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
