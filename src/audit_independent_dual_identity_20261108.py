"""Posthoc identity/activity attribution of already-missed interior utterances.

This audit never makes new labels, selects a threshold or changes recognition.
"""
from pathlib import Path
from datetime import datetime
import json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261108-dual-mic-independent-meetings');E=Path('E:/CodexData/Companion/.model-cache/dual-mic-independent-meetings-20261108')
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));limits=WorkerLimits(cpu_percent=10,memory_bytes=256*1024**2)
assert not (C/'identity-audit.json').exists();g=read(C/'gate-audit.json');cases=read(C/'spatial-audio-only.json');full=read(C/'journal-review.json')['fullMeetingReviews'];rows=[]
for case in cases:
    failed=[r for r in g['coverage'] if r['case']==case['id'] and r['fullyContainedCompletelyRemovedCharacters'] and not r['ordinaryBypassDoesNotApplyThisGate']]
    for person in failed:
        utterances=[r for r in person['utterances'] if r['fullyContainedInClip'] and r['completelyRemovedByPredictedGate']]
        entry={'case':case['id'],'referencePersonForEvaluationOnly':person['referencePersonForPosthocAudit'],'fullyContainedCompletelyRemovedCharacters':person['fullyContainedCompletelyRemovedCharacters'],'utterancesForEvaluationOnly':utterances,'micDiagnostics':[]}
        for channel in [0,1]:
            result=next(r for r in full if r['meeting']==case['meeting']+f'-mic{channel}');byref=result['review']['perReferenceSpeakerForEvaluationOnly'];mapped=byref[person['referencePersonForPosthocAudit']]['matchedAnonymousGroup'];slot=int(mapped.removeprefix('speaker_')) if mapped is not None else None
            journal=read(Path(result['resultDirectory'])/'speaker-journal.json');frames=int(np.ceil(journal['audioSeconds']*100));mask=np.zeros((8,frames),dtype=bool)
            for seg in journal['segments']:mask[seg['speaker'],round(seg['start']*100):min(frames,round(seg['end']*100))]=True
            indices=np.concatenate([np.arange(max(0,int(np.ceil(r['start']*100))),min(frames,int(np.floor(r['end']*100)))) for r in utterances]);assert len(indices)>0
            probs=np.load(E/'probabilities'/(case['meeting']+f'-mic{channel}')/'attempt-1/probabilities.npy',mmap_mode='r')
            values=probs[indices];activity=mask[:,indices];target=activity[slot] if slot is not None else np.zeros(len(indices),dtype=bool);any_activity=activity.any(0)
            entry['micDiagnostics'].append({'channel':channel,'globallyMappedExpectedSlotForEvaluationOnly':slot,'auditedInteriorReferenceSecondsAt10ms':len(indices)/100,'correctTargetActiveSeconds':float(target.sum()/100),'noSpeakerActiveSeconds':float((~any_activity).sum()/100),'targetAbsentButOtherSpeakerActiveSeconds':float((~target&any_activity).sum()/100),'predictedActiveSecondsBySlot':activity.sum(1).astype(float).__truediv__(100).tolist(),'meanPosteriorBySlot':values.mean(0).astype(float).tolist(),'maximumPosteriorBySlot':values.max(0).astype(float).tolist(),'thresholdChanged':False})
        rows.append(entry)
report={'at':datetime.now().astimezone().isoformat(),'state':'COMPLETE_POSTHOC_LOST_UTTERANCE_IDENTITY_VS_SILENCE_AUDIT','rows':rows,'scope':'10ms diagnostic quantization only, not a replacement for standard continuous-time DER. Other-slot activity can be another real overlapping person or wrong identity; it is not proof that all such activity is a label swap. Reference annotations used only to diagnose existing failures.','generatedTextChanged':False,'newModelCalls':0,'referenceDataPassedToWorker':False,'thresholdSweepPerformed':False,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'identity-audit.json',report)
print(json.dumps({'state':report['state'],'rows':[{'case':r['case'],'person':r['referencePersonForEvaluationOnly'],'chars':r['fullyContainedCompletelyRemovedCharacters'],'channels':[{k:v for k,v in x.items() if k in ['channel','correctTargetActiveSeconds','noSpeakerActiveSeconds','targetAbsentButOtherSpeakerActiveSeconds']} for x in r['micDiagnostics']]} for r in rows]},ensure_ascii=False),flush=True)
