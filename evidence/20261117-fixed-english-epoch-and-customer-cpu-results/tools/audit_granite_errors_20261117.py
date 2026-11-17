"""Attribute the completed fixed-reference errors without changing any score."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import argparse,hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from score_sequential_meetings_20261115 import tokens,measure
from rapidfuzz.distance import Levenshtein
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
score=read(C/'score.json');prior=read(J/'english-transducer-r1/score.json')
control=read(J/'english-transducer-r1/scoring-control.json');refs={v['id']:v for v in read(control['references'])}
ap=argparse.ArgumentParser();ap.add_argument('--baseline-only',action='store_true');ap.add_argument('--trained-final',action='store_true');args=ap.parse_args()
if args.trained_final:
 run=C.parent/'gpu-owned-evening20261117-r2';s=read(run/'paired-score.json')
 assert s['candidateOptimizerUpdates']==457 and s['trainingExamples']==1828
 operations={phase:{key:sum(c[phase+'Operations'][key] for c in s['cases']) for key in ['substitutions','deletions','insertions']} for phase in ['baseline','candidate']}
 assert sum(operations['candidate'].values())==s['candidateErrors']
 result=dict(state='FINAL_FIXED_EPOCH_ERROR_BUDGET_DIAGNOSIS_SCORE_UNCHANGED',at=datetime.now().astimezone().isoformat(),
  baselineErrors=s['baselineErrors'],candidateErrors=s['candidateErrors'],referenceWords=709,operations=operations,
  meetings=s['meetings'],improvedClips=sum(c['candidateErrors']<c['baselineErrors'] for c in s['cases']),
  worsenedClips=sum(c['candidateErrors']>c['baselineErrors'] for c in s['cases']),
  unchangedClips=sum(c['candidateErrors']==c['baselineErrors'] for c in s['cases']),
  furtherErrorsToRemoveForFivePercent=max(0,s['candidateErrors']-35),furtherErrorsToRemoveForTwoPercent=max(0,s['candidateErrors']-14),
  admissionPassed=s['advanceToCompleteSources'],decision='Reject and retain this fixed one-epoch recipe; no further epoch/LR/checkpoint grid and no full-source expansion of this rejected candidate.',
  newInference=0,newTrainingUpdates=0,originalReferencesUnchanged=True,finalHoldoutOpened=False,qualityQualified=False,saleQualified=False)
 target=C/'fixed-epoch-error-budget.json';assert not target.exists();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=False));raise SystemExit(0)
if args.baseline_only:
 run=C.parent/'gpu-owned-evening20261117-r2'
 state=read(run/'baseline/completed.json');rows=[]
 assert len(state['completed'])==12 and state['parameterUpdates']==0
 for c in state['completed']:
  packet=read(c['file']);value=measure(refs[packet['id']]['rawReferenceText'],packet['text'],'English')
  rows.append(dict(id=packet['id'],**{k:value[k] for k in ['errors','referenceUnits','substitutions','deletions','insertions']}))
 aggregate={k:sum(c[k] for c in rows) for k in ['errors','referenceUnits','substitutions','deletions','insertions']}
 assert aggregate['referenceUnits']==709
 result=dict(state='CURRENT_SAME_PROFILE_UNTRAINED_BASELINE_SCORED',aggregate=aggregate,cases=rows,
  priorOriginalErrors=prior['errors'],originalReferencesUnchanged=True,finalHoldoutOpened=False,newInferenceByScorer=0,trainingUpdates=0)
 target=C/'untrained-current-parakeet-baseline.json';assert not target.exists()
 target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result['aggregate']));raise SystemExit(0)
deletions=Counter();substitutions=Counter();insertions=Counter();cases=[]
explicit_fillers={'uh','um','erm','er','hmm','mm','mhm','uhh','uhum','ah','huh'}
for item in score['cases']:
 c=refs[item['id']];assert c['role']=='validation' and c['language']=='English'
 packet=read(C/'native-gpu-r1'/(item['id']+'.json'))
 ref,hyp=tokens(c['rawReferenceText'],'English'),tokens(packet['text'],'English')
 ops=Levenshtein.editops(ref,hyp)
 assert len(ops)==item['errors']
 detailed=[]
 for op in ops:
  expected=ref[op.src_pos] if op.tag!='insert' else None
  actual=hyp[op.dest_pos] if op.tag!='delete' else None
  if op.tag=='delete':deletions[expected]+=1
  elif op.tag=='replace':substitutions[(expected,actual)]+=1
  else:insertions[actual]+=1
  detailed.append(dict(operation=op.tag,expected=expected,actual=actual,
   referenceContext=ref[max(0,op.src_pos-3):op.src_pos+4],hypothesisContext=hyp[max(0,op.dest_pos-3):op.dest_pos+4]))
 cases.append(dict(id=item['id'],errors=len(ops),operations=detailed))
filler_deleted=sum(n for word,n in deletions.items() if word in explicit_fillers)
assert sum(deletions.values())==71 and sum(substitutions.values())==34 and sum(insertions.values())==8
result=dict(at=datetime.now().astimezone().isoformat(),state='COMPLETED_REFERENCE_ERROR_ATTRIBUTION_ORIGINAL_SCORE_UNCHANGED',
 errors=113,referenceWords=709,wer=113/709,prior=dict(errors=prior['errors'],substitutions=prior['substitutions'],deletions=prior['deletions'],insertions=prior['insertions'],seconds=prior['inferenceSeconds']),
 current=dict(substitutions=34,deletions=71,insertions=8,seconds=score['aggregate']['seconds']),
 deletedWords=deletions.most_common(),replacementPairs=[dict(expected=a,actual=b,count=n) for (a,b),n in substitutions.most_common()],insertedWords=insertions.most_common(),
 explicitFillerDefinition=sorted(explicit_fillers),explicitFillerDeletions=filler_deleted,
 otherDeletions=71-filler_deleted,errorsIfOnlyTheseFillerDeletionsWereCorrected=113-filler_deleted,
 thisIsACounterfactualDiagnosticNotANewScore=True,cases=cases,
 newInference=0,newTrainingUpdates=0,referenceChanged=False,finalHoldoutOpened=False,qualityQualified=False,saleQualified=False)
target=C/'granite-error-attribution.json';assert not target.exists();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['errors','prior','current','deletedWords','explicitFillerDeletions','otherDeletions','errorsIfOnlyTheseFillerDeletionsWereCorrected']},ensure_ascii=False))
