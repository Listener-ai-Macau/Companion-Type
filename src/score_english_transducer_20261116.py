"""Frozen English specialist admission; no Chinese or whole-product claim."""
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import argparse
import json
from meeting_acoustic_contract_20261116 import read,require,sha
from score_sequential_meetings_20261115 import measure
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2);C=read(a.control)
    for item in C['files']:require(sha(item['file'])==item['sha256'],'English score dependency changed')
    P=read(C['protocol']);state=read(a.run/'completed.json')
    require(state['state']=='COMPLETE_ONE_NATIVE_ENGLISH_TRANSDUCER_PENDING_INDEPENDENT_SCORING'
        and len(state['completed'])==12 and state['binding']['protocolSha256']==sha(C['protocol'])
        and state['binding']['modelSha256']==P['weights']['sha256'],'Incomplete/different English specialist')
    proof=read(a.run/'weight-roundtrip.json')
    require(proof['fileSha256']==proof['deviceRoundtripSha256']==P['weights']['sha256'],'Published tensor roundtrip missing')
    refs={c['id']:c for c in read(C['references']) if c['language']=='English' and c['role']=='validation'}
    original={c['id']:c for c in read(C['qwenBaseline'])['cases']}
    old={c['id']:c for c in read(C['mossBaseline'])['cases']};audio={c['id']:c for c in read(P['audioOnly'])}
    rows=[]
    for entry in state['completed']:
        require(sha(entry['file'])==entry['sha256'],'English output changed')
        out=read(entry['file']);case=refs[out['id']]
        require(out['binding']==state['binding'] and out['naturalTermination']
            and out['audioSha256']==audio[case['id']]['audioSha256'],'English input/model mismatch')
        score=measure(case['rawReferenceText'],out['text'],'English')
        baseline=old[case['id']]['raw']
        require(score['referenceUnits']==original[case['id']]['referenceUnits']==baseline['referenceUnits'],
                'Original English reference denominator changed')
        rows.append({'id':case['id'],'meeting':case['meeting'],'referenceWords':score['referenceUnits'],
            'errors':score['errors'],'qwenErrors':original[case['id']]['errors'],'mossErrors':baseline['errors'],
            'substitutions':score['substitutions'],'deletions':score['deletions'],'insertions':score['insertions'],
            'seconds':out['seconds'],'encoderExhausted':out['encoderExhausted']})
    require(len({r['id'] for r in rows})==12,'Duplicate/missing English case')
    n=sum(r['referenceWords'] for r in rows);q=sum(r['qwenErrors'] for r in rows);m=sum(r['mossErrors'] for r in rows)
    errors=sum(r['errors'] for r in rows);require((n,q,m)==(709,141,124),'Frozen English baselines changed')
    groups=defaultdict(list)
    for row in rows:groups[row['meeting']].append(row)
    meetings=[{'meeting':name,'referenceWords':sum(r['referenceWords'] for r in items),
        'errors':sum(r['errors'] for r in items),'qwenErrors':sum(r['qwenErrors'] for r in items),
        'mossErrors':sum(r['mossErrors'] for r in items)} for name,items in groups.items()]
    keep=errors<=99 and all(r['errors']<=r['mossErrors'] for r in meetings)
    result={'state':'NATIVE_ENGLISH_TRANSDUCER_'+('ADVANCE_TO_COMPLETE_SOURCE_VALIDATION' if keep else 'REJECT_FIXED_CLIP_ADMISSION_NO_GRID'),
        'at':datetime.now().astimezone().isoformat(timespec='seconds'),'referenceWords':n,'errors':errors,'wer':errors/n,
        'qwenErrors':q,'mossErrors':m,'relativeErrorReductionVsBestPriorMoss':(m-errors)/m,
        'meetings':meetings,'cases':rows,'advanceToCompleteSources':keep,
        'admissionGate':C['admissionGate'],'rawFivePercentGate':errors/n<.05,
        'substitutions':sum(r['substitutions'] for r in rows),'deletions':sum(r['deletions'] for r in rows),
        'insertions':sum(r['insertions'] for r in rows),'inferenceSeconds':sum(r['seconds'] for r in rows),
        'languageScope':'English only; original Chinese engine retained. Automatic bilingual/code-switch routing, speaker identities and full meetings are not accepted by this clip result.',
        'trainingUpdates':0,'newInferenceByScorer':0,'qualityQualified':False,'saleQualified':False,
        'originalReferencesAndWordsUnchanged':True,'protocolSha256':sha(C['protocol']),
        'scorerSha256':sha(__file__),'limits':limits.query()}
    require(not a.output.exists(),'Preserve completed English specialist score')
    atomic_json(a.output,result);print(json.dumps({k:result[k] for k in ['state','errors','wer','advanceToCompleteSources','meetings']},ensure_ascii=False))


if __name__=='__main__':main()
