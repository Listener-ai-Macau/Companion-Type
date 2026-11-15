"""Explain existing fixed errors; never filter words or rescore a product gate."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import argparse,json,re,unicodedata,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
from rapidfuzz.distance import Levenshtein
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);a=p.parse_args()
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
protocol=read(a.control/'protocol.json');decision=read(a.control/'decision.json')
routes={r['id']:r for r in read(a.control/'routed-composition-protocol.json')['cases']}
truth={r['id']:r for r in read(protocol['scoringManifest'])}
source=(S/'full_meeting_transcript_metrics_20261103.py').read_text(encoding='utf-8')
start=source.index('def normalize(');end=source.index('\ndef ',start+1)
scope=dict(re=re,unicodedata=unicodedata);exec(source[start:end],scope);normalize=scope['normalize']
rows=[]
for row in decision['cases']:
    refs=[normalize(r['text']) for r in truth[row['id']]['utterances']]
    assignment=row['candidate']['referenceAssignmentForDiagnosticOnly']
    joined=[''.join(r for r,k in zip(refs,assignment) if k==i) for i in range(2)]
    hyps=[normalize(x) for x in row['rawCandidateStreams']]
    spans=[];inserts=0
    for i in range(2):
        positions=[o.dest_pos for o in Levenshtein.editops(joined[i],hyps[i]) if o.tag=='insert']
        inserts+=len(positions);runs=[]
        for position in positions:
            if runs and runs[-1][-1]+1==position:runs[-1].append(position)
            else:runs.append([position])
        for run in runs:
            fragment=hyps[i][run[0]:run[-1]+1]
            spans.append(dict(stream=i,characters=len(fragment),text=fragment,
                exactFragmentAlsoInOtherOutput=fragment in hyps[1-i],
                otherStreamOffset=hyps[1-i].find(fragment),assignedReferenceIsEmpty=not joined[i]))
    assert inserts==row['candidate']['counts'].get('insert',0)
    rows.append(dict(id=row['id'],meeting=row['meeting'],condition=row['condition'],
        usedByFrozenRoute=routes[row['id']]['useBothSeparatedStreams'],insertionCharacters=inserts,
        wholeInsertionSpans=spans,emptyAssignedReferenceOutputCharacters=sum(len(h) for r,h in zip(joined,hyps) if not r)))
summary={}
for condition in ['multi-turn-context','clean-short-response']:
    selected=[r for r in rows if r['condition']==condition and r['usedByFrozenRoute']]
    spans=[s for r in selected for s in r['wholeInsertionSpans']]
    summary[condition]=dict(routedCases=len(selected),insertionCharactersInSeparatedUsedBranches=sum(r['insertionCharacters'] for r in selected),
        insertionSpanCharactersAlsoInOtherOutputAtLeast2=sum(s['characters'] for s in spans if s['characters']>=2 and s['exactFragmentAlsoInOtherOutput']),
        insertionSpanCharactersAlsoInOtherOutputAtLeast4=sum(s['characters'] for s in spans if s['characters']>=4 and s['exactFragmentAlsoInOtherOutput']),
        emptyAssignedReferenceOutputCharacters=sum(r['emptyAssignedReferenceOutputCharacters'] for r in selected))
target=a.control/'insertion-attribution.json';assert not target.exists()
target.write_text(json.dumps(dict(state='COMPLETE_CPU_ONLY_INSERTION_ATTRIBUTION_ORIGINAL_SCORES_UNCHANGED',
    at=datetime.now().astimezone().isoformat(),summary=summary,cases=rows,newNeuralCalls=0,
    diagnosticReferenceAllocationOnly=True,originalDecisionUnchanged=True,wordsRemovedOrSelected=False,
    scope='Exact text overlap between an insertion span and the other output shows lexical coincidence only; it does not prove identical time, acoustical leakage, source identity, or hallucination. Empty assigned reference uses the existing anonymous ORC diagnostic allocation, not a new true-speaker label.'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary))
