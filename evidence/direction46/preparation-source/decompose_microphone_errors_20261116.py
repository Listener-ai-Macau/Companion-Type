"""Compare fixed-reference edit allocations; no new inference or words."""
from pathlib import Path
from datetime import datetime
from collections import Counter,defaultdict
import json
import sys

R=Path('C:/Users/Billy/Desktop/Denzic/Companion'); S=R/'model-research/src';sys.path.insert(0,str(S))
from rapidfuzz.distance import Levenshtein
from score_sequential_meetings_20261115 import tokens
from meeting_acoustic_contract_20261116 import sha,read,require
from moss_windows_resource_limits_20261104 import WorkerLimits
from practical_io_20261107 import atomic_json
D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
J=D/'joint-architecture-r1'; C=J/'microphone-diagnostic-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/microphone-diagnostic-r1/gpu-run')
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
report=read(J/'english-acoustic-omission-review20261116.json')
base={r['id']:r for r in read(D/'sequential-meeting-stageA-r2/raw-text-baseline.json')['cases']}
cases={r['id']:r for r in read(D/'sequential-meeting-stageA-r2/scoring-only.json')}
state=read(E/'completed.json'); score=read(C/'diagnostic-score.json')
require(state['nativeControlExact'] and len(state['completed'])==13,'Incomplete diagnostic')
near_counts=Counter();far_counts=Counter(); transitions=Counter(); by_energy=defaultdict(Counter);rows=[]
for entry in state['completed']:
    require(sha(entry['file'])==entry['sha256'],'Output changed')
    out=read(entry['file'])
    if out['kind']=='native-distant-control':continue
    name=out['caseId']; reference=tokens(cases[name]['rawReferenceText'],'English')
    near=Levenshtein.editops(reference,tokens(out['text'],'English'))
    far=Levenshtein.editops(reference,tokens(base[name]['hypothesis'],'English'))
    a={o.src_pos:o.tag for o in far if o.tag!='insert'}; b={o.src_pos:o.tag for o in near if o.tag!='insert'}
    fc=Counter(o.tag for o in far);nc=Counter(o.tag for o in near)
    far_counts.update(fc);near_counts.update(nc)
    for word in [r for r in report['wordInspection'] if r['id']==name]:
        index=word['referenceIndex']; require(word['edit']==a.get(index,'equal'),'Original allocation changed')
        before=a.get(index,'equal');after=b.get(index,'equal');transitions[(before,after)]+=1
        group='lowestEnergyQuartile' if word['relativeToClipMedianRms']<=report['lowerQuartileThresholdRelativeRms'] else 'otherWords'
        by_energy[group].update(words=1,farDeletions=int(before=='delete'),headsetDeletions=int(after=='delete'),
            farDeletedNowExact=int(before=='delete' and after=='equal'))
    rows.append({'id':name,'farEdits':dict(fc),'headsetEdits':dict(nc)})
require(sum(far_counts.values())==141 and sum(near_counts.values())==83,'Frozen WER changed')
result={'state':'COMPLETE_SAME_WORD_MICROPHONE_ERROR_DECOMPOSITION_NO_NEW_INFERENCE',
    'at':datetime.now().astimezone().isoformat(timespec='seconds'),'farEdits':dict(far_counts),
    'headsetEdits':dict(near_counts),'referenceWordTransitions':[
       {'far':a,'headset':b,'words':n} for (a,b),n in sorted(transitions.items())],
    'byOriginalFarFieldWordEnergy':{k:dict(v) for k,v in by_energy.items()},'rows':rows,
    'limitations':['Reference-index edit allocations are not phonetic alignment and can vary for repeated words.',
        'Headset mix changes recording condition and microphone coverage; no pure-SNR or hardware defect attribution.',
        'No reference word is removed or post-edited; original product scores remain unchanged.'],
    'scoreSha256':sha(C/'diagnostic-score.json'),'sourceSha256':sha(__file__),
    'newNeuralCalls':0,'trainingUpdates':0,'qualityQualified':False,'limits':limits.query()}
require(not (C/'error-decomposition.json').exists(),'Preserve completed decomposition')
atomic_json(C/'error-decomposition.json',result)
print(json.dumps({k:result[k] for k in ['state','farEdits','headsetEdits','byOriginalFarFieldWordEnergy']},ensure_ascii=False))
