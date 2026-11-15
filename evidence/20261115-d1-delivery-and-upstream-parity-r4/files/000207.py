"""Localize full-reference edit changes and test the hard activity-mask premise."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
import json,wave
import numpy as np
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from full_meeting_transcript_metrics_20261103 import normalize,group_transcripts,Levenshtein
from reference_textgrid_20261104 import read_reference_intervals
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1');B=C.parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert not (C/'root-cause-review.json').exists();review=read(C/'review.json');cases=read(C/'audio-only.json');lanes=read(C/'asr-manifest-r2.json')
scores=read(B/'practical-qwen-native17-r5/full/scoring-only.json');results=[];activity=[]
for name in dict.fromkeys(c['meeting'] for c in cases):
    scoring=next(r for r in scores if r['meeting']==name);duration=scoring['audioSeconds']
    refs=[r for r in read_reference_intervals(scoring['reference']) if normalize(r['text'])]
    base=B/'practical-alignment-r1/derived-onset/transcripts'/name;doc=read(base/'model-output.json');tokens=read(base/'attribution-review.json')['tokenEstimates']
    display={int(k):v for k,v in read(base/'attribution-review.json')['nativeToConsecutiveDisplaySpeakerIds'].items()}
    der=read(B/'native8-f16-full-r1/results'/name/'review.json')['perReferenceSpeakerForEvaluationOnly']
    fixed={ref:display[int(v['matchedAnonymousGroup'].removeprefix('speaker_'))] for ref,v in der.items()}
    def evaluate(utterances):
        hyps=[{'start':r['startMs']/1000,'end':r['endMs']/1000,'speaker':str(r['speaker']) if r['speaker'] is not None else '__unconfirmed__','text':r['text']} for r in utterances]
        rt=group_transcripts(refs,duration);ht=group_transcripts(hyps,duration)
        people={ref:Levenshtein.distance(text,ht.get(str(fixed[ref]),'')) for ref,text in rt.items()}
        extra=sum(len(text) for who,text in ht.items() if who not in {str(s) for s in fixed.values()})
        return {'totalEdits':sum(people.values())+extra,'personEdits':people,'extraUnmatchedTextCharacters':extra}
    original=evaluate(doc['utterances']);assert original['totalEdits']==next(r for r in review['results'] if r['meeting']==name)['fixedGlobalMappingBefore']['totalEdits']
    for case in [r for r in cases if r['meeting']==name]:
        kept=[r for r,t in zip(doc['utterances'],tokens) if int(t['sourceLeaf'].split('-')[0])!=case['rootIndex']]
        added=[]
        for lane in [r for r in lanes if r['meeting']==name and r['rootIndex']==case['rootIndex']]:
            for leaf in lane['acceptedLeaves']:
                if leaf['text'].strip():added.append({'text':leaf['text'],'startMs':round((case['startSample']+leaf['startSample'])/16),'endMs':round((case['startSample']+leaf['endSample'])/16),'speaker':display[lane['predictedSpeaker']]})
            with wave.open(lane['audio'],'rb') as stream:values=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float64)/32768
            predicted=np.zeros(len(values),dtype=np.bool_);truth=np.zeros(len(values),dtype=np.bool_)
            journal=read(case['journal']);ref_person=next(ref for ref,v in der.items() if int(v['matchedAnonymousGroup'].removeprefix('speaker_'))==lane['predictedSpeaker'])
            for intervals,mask in [([r for r in journal['segments'] if r['speaker']==lane['predictedSpeaker']],predicted),([r for r in refs if r['speaker']==ref_person],truth)]:
                for row in intervals:
                    lo=max(0,round(row['start']*16000)-case['startSample']);hi=min(len(values),round(row['end']*16000)-case['startSample'])
                    if hi>lo:mask[lo:hi]=True
            lost=truth&~predicted;total=float(np.square(values).sum())
            activity.append({'id':lane['id'],'referencePersonForDiagnosticOnly':ref_person,
                'predictedActiveSeconds':int(predicted.sum())/16000,'referenceTargetActiveSeconds':int(truth.sum())/16000,
                'trueTargetSecondsOutsidePredictedActivity':int(lost.sum())/16000,
                'outputEnergyInTrueTargetButPredictedInactiveFraction':float(np.square(values[lost]).sum())/total if total else None,
                'noOracleMaskOrReferenceUsedAtRuntime':True})
        current=evaluate(sorted(kept+added,key=lambda r:(r['startMs'],r['endMs'],str(r['speaker']))))
        results.append({'id':case['id'],'kind':case['kind'],'selectedSourceStartSeconds':case['startSample']/16000,
            'fullMeetingFixedEditsBefore':original['totalEdits'],'fullMeetingFixedEditsAfterOnlyThisRootReplaced':current['totalEdits'],
            'editDelta':current['totalEdits']-original['totalEdits'],
            'personEditDelta':{p:current['personEdits'][p]-original['personEdits'][p] for p in original['personEdits']},
            'unknownExtraTextDelta':current['extraUnmatchedTextCharacters']-original['extraUnmatchedTextCharacters'],
            'notPerClipOracleScoringOrAdoptionSelection':True})
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PS4_ROOT_CONTENT_AND_DIARIZATION_MISS_CAUSE_AUDIT',
    'rootChanges':results,'targetActivityCounterfactual':activity,'newNeuralCalls':0,
    'referenceUsedOnlyAfterCompleteInference':True,'individualRootResultsNotUsedToSelectWinningOutputs':True,
    'qualityQualified':False,'limits':limits.query()}
atomic_json(C/'root-cause-review.json',result);print(json.dumps(result,ensure_ascii=False))
