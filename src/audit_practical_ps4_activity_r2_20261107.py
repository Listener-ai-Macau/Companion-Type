"""Exited-run cause audit. Reference coverage is diagnostic, never runtime selection."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import hashlib,json,wave
import numpy as np
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1');B=C.parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert read(C/'run-r2.json')['state']=='COMPLETE_TARGET_SEPARATION_AND_ASR_REVIEW_REQUIRED'
assert not (C/'activity-cause-review-r2.json').exists()
cases=read(C/'audio-only.json');lanes=read(C/'separation-manifest-r2.json');scores=read(B/'practical-qwen-native17-r5/full/scoring-only.json');anchors=[];energy=[];done=set()
for case in cases:
    journal=read(case['journal']);score=next(r for r in scores if r['meeting']==case['meeting']);refs=[r for r in read_reference_intervals(score['reference']) if normalize(r['text'])]
    fixed=read(B/'native8-f16-full-r1/results'/case['meeting']/'review.json')['perReferenceSpeakerForEvaluationOnly']
    for anchor in case['anchors']:
        pair=(case['meeting'],anchor['speaker'])
        if pair in done:continue
        done.add(pair);lo=anchor['startSample']/16000;hi=anchor['endSample']/16000
        per_person={ref:sum(max(0.,min(hi,r['end'])-max(lo,r['start'])) for r in refs if r['speaker']==ref) for ref in fixed}
        expected=next(ref for ref,v in fixed.items() if int(v['matchedAnonymousGroup'].removeprefix('speaker_'))==anchor['speaker'])
        anchors.append({'meeting':case['meeting'],'predictedSpeaker':anchor['speaker'],'expectedReferenceForPosthocAuditOnly':expected,
            'sourceStartSeconds':lo,'sourceEndSeconds':hi,'referenceActivitySeconds':per_person,
            'expectedPersonReferenceActivityFraction':per_person[expected]/(hi-lo),
            'otherPersonReferenceActivitySeconds':sum(v for ref,v in per_person.items() if ref!=expected),
            'neverUsedToReselectEnrollmentOrGateInference':True})
    for lane in [r for r in lanes if r['meeting']==case['meeting'] and r['rootIndex']==case['rootIndex']]:
        with wave.open(lane['audio'],'rb') as stream:value=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float64)/32768
        mask=np.zeros(len(value),dtype=np.bool_)
        for row in journal['segments']:
            if row['speaker']!=lane['predictedSpeaker']:continue
            lo=max(0,round(row['start']*16000)-case['startSample']);hi=min(len(value),round(row['end']*16000)-case['startSample'])
            if hi>lo:mask[lo:hi]=True
        on=float(np.square(value[mask]).sum());off=float(np.square(value[~mask]).sum())
        energy.append({'id':lane['id'],'predictedSpeaker':lane['predictedSpeaker'],'predictedActiveSeconds':int(mask.sum())/16000,
            'predictedInactiveSeconds':int((~mask).sum())/16000,'outputEnergyWhilePredictedInactiveFraction':off/(on+off) if on+off else None,
            'activeRms':float(np.sqrt(np.mean(np.square(value[mask])))) if mask.any() else None,
            'inactiveRms':float(np.sqrt(np.mean(np.square(value[~mask])))) if (~mask).any() else None,
            'scope':'Predicted activity, not true target absence; diarizer misses can make true target speech appear inactive.'})
review={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PS4_CACHED_ACTIVITY_AND_ENROLLMENT_CAUSE_AUDIT_NO_NEW_MODEL',
    'enrollmentReferenceCoverageForPosthocAuditOnly':anchors,'allExtractedLaneActivityEnergy':energy,
    'noNewNeuralCalls':True,'sourceAudioAndOutputsUnchanged':True,'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'activity-cause-review-r2.json',review);print(json.dumps(review,ensure_ascii=False))
