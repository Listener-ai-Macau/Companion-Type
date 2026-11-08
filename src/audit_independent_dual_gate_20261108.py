"""Attribute lost utterances to predicted activity, posthoc, without changing text."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from full_meeting_transcript_metrics_20261103 import normalize
from reference_textgrid_20261104 import read_reference_intervals
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-dual-mic-independent-meetings')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=10,memory_bytes=256*1024**2);review=read(C/'review.json');assert not (C/'gate-audit.json').exists()
def merge(spans):
    result=[]
    for a,b in sorted(spans):
        if b<=a:continue
        if result and a<=result[-1][1]:result[-1]=(result[-1][0],max(b,result[-1][1]))
        else:result.append((a,b))
    return result
coverage=[]
for case in read(C/'spatial-audio-only.json'):
    scoring=next(r for r in read(C/'scoring-only.json') if r['originalMeeting']==case['meeting'] and r['sourceChannel']==0);assert sha(scoring['reference'])==scoring['referenceSha256'];truth=read_reference_intervals(scoring['reference']);lo,hi=case['rootStartSample']/16000,case['rootEndSample']/16000;journal=read(case['journal'])['segments']
    for person in [r for r in review['perPerson'] if r['case']==case['id']]:
        slot=person['predictedSlot'];predicted=merge([(max(lo,r['start']),min(hi,r['end'])) for r in journal if r['speaker']==slot]) if slot is not None else [];utterances=[]
        for row in truth:
            if row['speaker']!=person['referencePersonForScoringOnly'] or not normalize(row['text']) or not lo<=(row['start']+row['end'])/2<hi:continue
            a,b=max(lo,row['start']),min(hi,row['end']);covered=sum(max(0,min(b,y)-max(a,x)) for x,y in predicted)
            utterances.append({'start':row['start'],'end':row['end'],'text':row['text'],'withinClipSeconds':b-a,'predictedTargetCoverageSeconds':covered,'completelyRemovedByPredictedGate':covered==0,'fullyContainedInClip':row['start']>=lo and row['end']<=hi})
        coverage.append({'case':case['id'],'referencePersonForPosthocAudit':person['referencePersonForScoringOnly'],'predictedSlot':slot,'referenceTargetSeconds':sum(r['withinClipSeconds'] for r in utterances),'coveredTargetSeconds':sum(r['predictedTargetCoverageSeconds'] for r in utterances),'fullyContainedCompletelyRemovedCharacters':sum(len(normalize(r['text'])) for r in utterances if r['fullyContainedInClip'] and r['completelyRemovedByPredictedGate']),'utterances':utterances,'ordinaryBypassDoesNotApplyThisGate':case['kind']=='ordinary-regression'})
report={'at':datetime.now().astimezone().isoformat(),'state':'COMPLETE_POSTHOC_PREDICTED_GATE_OMISSION_AUDIT','sourceReviewSha256':sha(C/'review.json'),'coverage':coverage,'wholeInteriorCharsExcludedByPredictedGate':sum(r['fullyContainedCompletelyRemovedCharacters'] for r in coverage if not r['ordinaryBypassDoesNotApplyThisGate']),'newModelCalls':0,'generatedTextChanged':False,'referenceOnlyUsedForPosthocAudit':True,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'gate-audit.json',report);print(json.dumps({'state':report['state'],'wholeInteriorCharsExcludedByPredictedGate':report['wholeInteriorCharsExcludedByPredictedGate']}),flush=True)
