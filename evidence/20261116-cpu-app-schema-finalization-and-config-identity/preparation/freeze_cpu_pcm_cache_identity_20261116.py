from pathlib import Path
import hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';C=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1/cpu-pcm-candidate-r1'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=C/'binding.json';B=json.loads(p.read_text(encoding='utf-8'));assert B['workerSha256']==sha(C/'worker-before-cache-identity-check.py')
B['workerSha256']=sha(S/'companion_local_moss_cpu_worker_20261116.py');B['existingCachePolicy']='Before model initialization, require every existing result to have the exact CPU model/runtime/worker/language policy binding. The candidate app preview and final job also fail closed across changed configuration; full bundle identity is part of the final job key.'
p.write_text(json.dumps(B,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'workerSha256':B['workerSha256'],'sourcePolicy':'exact-cache-binding-before-model-init','neuralCalls':0}))
