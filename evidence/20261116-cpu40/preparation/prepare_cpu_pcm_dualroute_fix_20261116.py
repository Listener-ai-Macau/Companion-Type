from pathlib import Path
from datetime import datetime
import hashlib,json,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
old=B/'cpu-pcm-candidate-r1';C=B/'cpu-pcm-candidate-r2';assert not C.exists();C.mkdir()
failure=read(E/'cpu-pcm-reader-collision-r1/result.json');proof=read(E/'cpu-pcm-reader-collision-fix-r1/result.json')
assert failure['winerror']==5 and proof['state']=='PASS_ACTUAL_WINDOWS_ATOMIC_COMMIT_OWNERSHIP_AND_DURABLE_REPLAY'
for name in ['runtime-contract.json','dualroute-protocol.json']:shutil.copyfile(old/name,C/name)
binding=read(old/'binding.json');key=str(S/'companion_local_pcm_session_20261114.py');assert binding['helpers'][key]==failure['sourceSha256']
binding['helpers'][key]=sha(key);binding.update(at=datetime.now().astimezone().isoformat(),changedCondition='Original ASR/model/runtime/scheduler unchanged. PCM atomic commit now waits bounded3s for Windows reader sharing; intake acquisition bounded3s, semantic conflicts remain immediate.',
 sourceFailureProof=str(E/'cpu-pcm-reader-collision-r1/result.json'),sourceFixProof=str(E/'cpu-pcm-reader-collision-fix-r1/result.json'))
(C/'binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
protocol=read(C/'dualroute-protocol.json');protocol.update(scriptSha256=sha('work/run_cpu_pcm_dualroute_20261116.py'),
 preparationOnlyChanges=['Windows state commit/intake concurrency fix and failure-event persistence; no model/settings/audio change.'],
 previousFailedRoot=str(E/'cpu-pcm-dualroute-r1'),newNeuralCallsForFixProof=0)
(C/'dualroute-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'control':str(C),'originalFailureRetained':True,'newHelperSha256':binding['helpers'][key],'modelUnchanged':True}))
