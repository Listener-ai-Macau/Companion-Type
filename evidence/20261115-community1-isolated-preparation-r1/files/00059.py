from pathlib import Path
from datetime import datetime
import ast,hashlib,json
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/community1-comparison-r1'
p=S/'community1_comparison_worker_20261115.py';old=D/'worker-used-for-feature-control.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cut='\n  else:\n   feature_proof='
before=old.read_text(encoding='utf-8');after=p.read_text(encoding='utf-8')
assert before.count(cut)==after.count(cut)==1
a,b=before.split(cut)[0],after.split(cut)[0]
assert a==b and a.rstrip().endswith('upstreamFeatureMethodUnchanged=True)')
ast.parse(after)
failure={'state':'PREPARATION_ASSERTION_ONLY_NO_INFERENCE','at':datetime.now().astimezone().isoformat(),
 'reason':'Prior command required an arbitrary>5000source-character minimum; actual complete prefix is4605characters and exactly equal. Replace length guess with unique branch-boundary and exact ending/equality checks. No feature/model rerun or tolerance change.'}
(D/'source-binding-preparation-note.json').write_text(json.dumps(failure,indent=2)+'\n',encoding='utf-8')
proof={'state':'PASS_PRE_MODEL_FULL_BRANCH_ONLY_REPAIR_FEATURE_EXECUTION_SOURCE_EXACT',
 'passedFeatureWorkerSha256':sha(old),'currentWorkerSha256':sha(p),
 'executedFeaturePrefixExact':True,'executedFeaturePrefixSha256':hashlib.sha256(a.encode()).hexdigest(),
 'changes':'Full branch validates frozen audio before reading and marks NN count unknown before upstream model loading, including partial failure. Passed numerical feature path/helpers/protocol unchanged; no repeated GPU control.'}
f=D/'feature-source-compatibility.json';assert not f.exists();f.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
v=json.loads((D/'worker-binding.json').read_text(encoding='utf-8'));v['workerSha256']=sha(p);v['featureSourceCompatibilitySha256']=sha(f)
(D/'worker-binding.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof))
