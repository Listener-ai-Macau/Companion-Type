"""Independent entire-meeting activity diagnostics after label-free forward."""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json
import numpy as np
from moss_windows_resource_limits_20261104 import WorkerLimits
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def metrics(truth,pred):
    tp=int((truth&pred).sum());fp=int((~truth&pred).sum());fn=int((truth&~pred).sum())
    return dict(truePositiveSeconds=tp*.01,falsePositiveSeconds=fp*.01,falseNegativeSeconds=fn*.01,
        precision=tp/(tp+fp) if tp+fp else 0.,recall=tp/(tp+fn) if tp+fn else 0.,
        f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
    P=read(a.control/'protocol.json');state=read(Path(P['observationRun'])/'state.json')
    assert state['state']=='COMPLETE_ORIGINAL_ACTIVITY_HEAD_OBSERVATION_SCORING_PENDING'
    assert state['allOriginalSpeakerPredictionsBitExact'] and not state['referenceRead']
    source=a.control.parent.parent/'public-speaker-adaptation-r1/validation-scoring-only.json'
    assert sha(source)==P['validationScoringSha256'];labels={r['meeting']:r for r in read(source)}
    results=[]
    for row in state['results']:
        label=labels[row['meeting']];assert sha(label['labels'])==label['labelsSha256']
        n=label['validSupervisedFrames'];y=(np.load(label['labels'],mmap_mode='r')[:n]>.5).sum(axis=1).clip(0,2)
        arrays={}
        for key,item in row['outputs'].items():
            assert sha(item['file'])==item['sha256'];arrays[key]=np.load(item['file'],allow_pickle=False)[:n]
        predicted=arrays['activity-class'];confusion=np.bincount(y.astype(np.int64)*3+predicted,minlength=9).reshape(3,3)
        results.append(dict(meeting=row['meeting'],validFrames=n,truthActivityFrames=np.bincount(y,minlength=3).tolist(),
            auxiliaryActivityConfusion=confusion.tolist(),
            originalSpeakerOverlap=metrics(y==2,arrays['legacy-overlap']),
            auxiliaryOverlap=metrics(y==2,predicted==2),
            guardedOverlap=metrics(y==2,arrays['guarded-overlap']),
            guardedIsOriginalSubset=bool((~arrays['guarded-overlap']|arrays['legacy-overlap']).all())))
    result=dict(state='COMPLETE_FIXED_ACTIVITY_GUARD_SOURCE_DIAGNOSTICS_WORD_GATE_PENDING',
        at=datetime.now().astimezone().isoformat(),meetings=results,allOriginalSpeakerPredictionsBitExact=True,
        thresholdOrRuleSelectedUsingTheseLabels=False,newNeuralCalls=0,qualityQualified=False,
        scope='Full original segment-level labels at10ms; silence inside lexical turns can be annotated as speech. Report unchanged labels. Final original complete-used-word and person/bilingual gates remain decisive; no source-F1 substitute.')
    target=a.control/'activity-diagnostic.json';assert not target.exists()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
