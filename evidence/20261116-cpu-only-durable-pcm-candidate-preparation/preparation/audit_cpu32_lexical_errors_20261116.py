from pathlib import Path
from collections import Counter
import hashlib,json,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S));sys.path.append('E:/CodexData/Companion/.model-cache/scoring-runtime-clean-20261106/Lib/site-packages')
from score_sequential_meetings_20261115 import tokens
R=S.parent.parent;C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/stagea-cpu-composition-r2'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/stagea-cpu-composition-r2');read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
score=read(C/'score.json');groups=[]
for group in score['groups']:
 selected=[r for r in score['cases'] if r['language']==group['language'] and r['role']==group['role']]
 deleted=Counter();inserted=Counter();substituted=Counter();totals=Counter();operations=[]
 for row in selected:
  composed=read(E/'composition'/(row['id']+'.json'));join=' ' if row['language']=='English' else ''
  ref=tokens(row['baselineRaw']['reference'],row['language']);hyp=tokens(join.join(r['text'] for r in composed['rows']),row['language'])
  for op in row['raw']['editOperations']:
   kind=op['operation'];i,j=op['referenceIndex'],op['hypothesisIndex'];totals[kind]+=1
   r=ref[i] if kind!='insert' else None;h=hyp[j] if kind!='delete' else None
   if kind=='delete':deleted[r]+=1
   elif kind=='insert':inserted[h]+=1
   else:substituted[(r,h)]+=1
   operations.append({'id':row['id'],'operation':kind,'referenceToken':r,'hypothesisToken':h,'referenceIndex':i,'hypothesisIndex':j})
 assert sum(totals.values())==group['rawErrors']
 groups.append({'language':group['language'],'role':group['role'],'referenceUnits':group['referenceUnits'],'errors':group['rawErrors'],
  'operationCounts':dict(totals),'deletedTokens':deleted.most_common(),'insertedTokens':inserted.most_common(),
  'substitutions':[{'reference':a,'hypothesis':b,'count':n} for (a,b),n in substituted.most_common()],
  'extraErrorsUnderSpeakerAttribution':group['speakerAttributedErrors']-group['rawErrors'],
  'baselineExtraErrorsUnderSpeakerAttribution':group['baselineSpeakerAttributedErrors']-group['baselineRawErrors'],'operations':operations})
result={'state':'CPU32_LEXICAL_ERROR_DECOMPOSITION_NO_SCORE_CHANGE','sourceScore':str(C/'score.json'),'sourceScoreSha256':sha(C/'score.json'),
 'groups':groups,'hypothesesChanged':False,'referencesChanged':False,'fillersOrNumbersRemoved':False,'newNeuralCalls':0,
 'interpretation':'Validation raw errors remain dominant, especially English; changing identity attribution alone cannot satisfy the text gate. This edit alignment does not establish whether a disputed reference is acoustically correct. Do not retune thresholds or delete error classes based on this diagnostic.'}
target=C/'lexical-error-audit.json';assert not target.exists();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':result['state'],'groups':[{k:g[k] for k in ['language','role','operationCounts','extraErrorsUnderSpeakerAttribution','baselineExtraErrorsUnderSpeakerAttribution']} for g in groups]},ensure_ascii=False))
