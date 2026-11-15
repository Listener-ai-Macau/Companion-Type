"""Separate interior-utterance omissions from clip-edge scoring ambiguity."""
import os
os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib,json
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
from reference_textgrid_20261104 import read_reference_intervals
from full_meeting_transcript_metrics_20261103 import normalize,Levenshtein

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261108-target-activity-adaptation/oracle-activity-diagnostic'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
assert not (C/'residual-boundary-audit.json').exists()
source=next(r for r in read(R/'docs/handoffs/20261107-model-generation-recovery/practical-target-activity-r1/scoring-only.json') if r['meeting']=='L_R003S01C02')
assert sha(source['reference'])==source['referenceSha256']
reference=read_reference_intervals(source['reference']);review=read(C/'review.json');inputs={r['laneId']:r for r in read(C/'scoring-only.json')};items=[]
for row in review['allLaneDetails']:
    lo=row['rootIndex']*30;hi=lo+30
    truth=[r for r in sorted(reference,key=lambda x:(x['start'],x['end'])) if r['speaker']==row['referencePerson'] and lo<=(r['start']+r['end'])/2<hi and normalize(r['text'])]
    chars=[];origins=[]
    for index,r in enumerate(truth):
        text=normalize(r['text']);chars.extend(text);origins.extend([index]*len(text))
    text=''.join(chars);assert text==normalize(inputs[row['sourceLane']]['referenceText'])
    record={'rootIndex':row['rootIndex'],'referencePerson':row['referencePerson'],'referenceCharacters':len(text),
        'interiorReferenceCharacters':sum(len(normalize(r['text'])) for r in truth if r['start']>=lo and r['end']<=hi),'conditions':{}}
    for key in ['ungatedSeparated','oracleGatedMixture','oracleGatedSeparated']:
        ops=Levenshtein.editops(text,normalize(row[key]['text']));counts=Counter();misses=Counter()
        for op in ops:
            if op.tag=='insert':counts['insertionsBoundaryUnassigned']+=1;continue
            source_row=truth[origins[op.src_pos]];interior=source_row['start']>=lo and source_row['end']<=hi
            counts[('interior_' if interior else 'boundary_')+op.tag]+=1
            if op.tag=='delete' and interior:misses[origins[op.src_pos]]+=1
        assert sum(counts.values())==row[key]['edits']['total']
        record['conditions'][key]={'editProvenance':dict(counts),'interiorUtterancesWithDeletedCharacters':[{'start':truth[i]['start'],'end':truth[i]['end'],'text':truth[i]['text'],'deletedCharacters':n} for i,n in sorted(misses.items())]}
    items.append(record)
summary={key:{field:sum(r['conditions'][key]['editProvenance'].get(field,0) for r in items) for field in ['interior_delete','interior_replace','boundary_delete','boundary_replace','insertionsBoundaryUnassigned']} for key in ['ungatedSeparated','oracleGatedMixture','oracleGatedSeparated']}
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ORACLE_RESIDUAL_INTERIOR_WORD_LOSS_AUDITED',
    'sourceReviewSha256':sha(C/'review.json'),'referenceSha256':source['referenceSha256'],'totals':summary,'perPerson':items,
    'method':'Assign reference-side substitutions/deletions in one minimum Levenshtein alignment to their original whole utterance. Fully contained utterances are distinguished from clip-edge-straddling ones. Insertions are not assigned to an arbitrary reference boundary.',
    'limits':'Repeated fillers can have multiple equally optimal alignments. This checks that clip edges alone do not explain residual omissions; it is not clean-waveform proof, isolated pure-overlapCER or a product result.',
    'newNeuralCalls':0,'generatedTextModified':False,'qualityQualified':False,'resourceLimits':limits.query()}
atomic_json(C/'residual-boundary-audit.json',result)
print(json.dumps({'state':result['state'],'totals':summary,'newNeuralCalls':0},ensure_ascii=False),flush=True)
