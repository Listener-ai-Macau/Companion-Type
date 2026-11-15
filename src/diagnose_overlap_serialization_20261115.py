"""Bounded oracle-order diagnosis of frozen ASR outputs, never acceptance.

Only reorder complete utterances that overlap in their source annotation;
preserve nonoverlapping temporal order and each speaker's own utterance order.
The original raw chronological score remains unchanged. This is a diagnostic
lower bound over permitted reference serializations, not repaired model text,
not the official SOT/ORC metric and not proof of purely acoustic errors.
"""
from pathlib import Path
from datetime import datetime
from itertools import permutations,product
from collections import Counter
import argparse,hashlib,json,os,re,unicodedata
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from moss_windows_resource_limits_20261104 import WorkerLimits
from rapidfuzz.distance import Levenshtein

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def allowed_serializations(rows,normalize):
    rows=sorted(rows,key=lambda r:(r['start'],r['end'],r['speaker']))
    components=[];end=-1.
    for row in rows:
        if row['start']>=end:components.append([])
        components[-1].append(row);end=max(end,row['end'])
    choices=[];counts=[]
    for component in components:
        assert len(component)<=7,'Bounded diagnosis only; no unbounded permutation search'
        predecessors={(i,j) for i,a in enumerate(component) for j,b in enumerate(component)
                      if i!=j and (a['end']<=b['start'] or
                                   (a['speaker']==b['speaker'] and i<j))}
        accepted=[]
        for order in permutations(range(len(component))):
            position={v:i for i,v in enumerate(order)}
            if all(position[i]<position[j] for i,j in predecessors):
                accepted.append(''.join(normalize(component[i]['text']) for i in order))
        accepted=sorted(set(accepted));assert accepted
        choices.append(accepted);counts.append(len(accepted))
    count=1
    for values in choices:count*=len(values)
    assert count<=10000,'Bounded frozen cohort diagnosis only'
    return [''.join(parts) for parts in product(*choices)],counts

def main():
    p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert not a.output.exists()
    limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    cases=read(a.control/'scoring-only.json');baseline=read(a.control/'baseline-score.json')
    text=(Path(__file__).parent/'full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf-8')
    start=text.index('def normalize(');end=text.index('\ndef ',start+1)
    scope={'re':re,'unicodedata':unicodedata};exec(text[start:end],scope);normalize=scope['normalize']
    # Minimal semantic controls: true overlaps permit both orders, while
    # sequential turns and a speaker's own turns cannot be reversed.
    first=dict(start=0.,end=2.,speaker='a',text='甲')
    second=dict(start=1.,end=3.,speaker='b',text='乙')
    assert set(allowed_serializations([first,second],normalize)[0])=={'甲乙','乙甲'}
    assert allowed_serializations([first,{**second,'start':2.}],normalize)[0]==['甲乙']
    assert allowed_serializations([first,{**second,'speaker':'a'}],normalize)[0]==['甲乙']
    rows=[]
    for case in cases:
        if case['condition']!='multi-turn-context':continue
        old=next(r for r in baseline['cases'] if r['id']==case['id'])
        assert sha(Path(case['reference']))==case['referenceSha256']
        truth=normalize(case['rawReferenceText']);hyp=old['normalizedHypothesis']
        assert truth==old['normalizedReference'] and Levenshtein.distance(truth,hyp)==old['totalEdits']
        variants,counts=allowed_serializations(case['utterances'],normalize)
        assert truth in variants and all(len(s)==len(truth) for s in variants)
        best=min(variants,key=lambda s:(Levenshtein.distance(s,hyp),s))
        ops=Levenshtein.editops(best,hyp)
        rows.append(dict(id=case['id'],meeting=case['meeting'],referenceCharacters=len(truth),
                         chronologicalEdits=old['totalEdits'],allowedReferenceSerializations=len(variants),
                         componentAlternativeCounts=counts,minimumOrderEdits=len(ops),
                         editsRemovableByOracleReferenceOrder=old['totalEdits']-len(ops),
                         remainingEditTypes=dict(Counter(o.tag for o in ops)),
                         originalReference=truth,rawAsrText=old['rawAsrText'],
                         oracleReferenceForDiagnosisOnly=best))
    assert len(rows)==12
    chars=sum(r['referenceCharacters'] for r in rows);old=sum(r['chronologicalEdits'] for r in rows)
    reduced=sum(r['minimumOrderEdits'] for r in rows)
    result=dict(state='COMPLETE_FROZEN_OUTPUT_OVERLAP_ORDER_DIAGNOSIS_NOT_QUALIFICATION',
                at=datetime.now().astimezone().isoformat(),cases=rows,referenceCharacters=chars,
                originalChronologicalEdits=old,originalChronologicalCer=old/chars,
                minimumPermittedOrderEdits=reduced,minimumPermittedOrderCer=reduced/chars,
                oracleOrderRemovableEdits=old-reduced,oldScoresOrReferencesChanged=False,
                newNeuralCalls=0,newTrainingUpdates=0,ownerParticipationRequired=False,
                qualityQualified=False,d2Complete=False,finalHoldoutOpened=False,
                sources={'scoringOnlySha256':sha(a.control/'scoring-only.json'),
                         'baselineScoreSha256':sha(a.control/'baseline-score.json'),
                         'normalizationSourceSha256':hashlib.sha256(text[start:end].encode()).hexdigest()},
                limits=limits.query(),
                interpretation='Oracle label ordering diagnoses a confound only. Remaining edits still mix recognition, spelling/transcription and possible within-utterance ordering errors; do not call them proven acoustic failures. No hypothesis word is changed and no original acceptance score is replaced.',
                literature=['https://arxiv.org/html/2003.12687v2','https://arxiv.org/html/2305.18747v1'],
                sotBoundary='Speaker-wise FIFO SOT groups all words of each speaker and uses a speaker-change token. Plain chronological utterance concatenation/newlines is not a faithful reproduction of that method or its timestamped extension.')
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['cases','limits','sources']},ensure_ascii=False))

if __name__=='__main__':main()
