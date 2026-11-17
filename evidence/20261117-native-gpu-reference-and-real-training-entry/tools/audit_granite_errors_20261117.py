"""Attribute the completed fixed-reference errors without changing any score."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import hashlib,json,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from score_sequential_meetings_20261115 import tokens,measure
from rapidfuzz.distance import Levenshtein
J=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1'
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
score=read(C/'score.json');prior=read(J/'english-transducer-r1/score.json')
control=read(J/'english-transducer-r1/scoring-control.json');refs={v['id']:v for v in read(control['references'])}
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
