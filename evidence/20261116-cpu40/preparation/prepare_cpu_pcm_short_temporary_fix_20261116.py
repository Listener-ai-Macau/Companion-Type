from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys,uuid
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src';sys.path.insert(0,str(S))
from companion_local_pcm_session_20261114 import PcmSession
B=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/joint-architecture-r1';E=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
old=B/'cpu-pcm-candidate-r2';C=B/'cpu-pcm-candidate-r3';assert not C.exists();C.mkdir()
proof=E/'cpu-pcm-short-temp-proof-r1';assert not proof.exists();proof.mkdir()
# Match the request-directory length of the actual failing app fixture.
suffix='/session/requests';padding=196-len(str(proof))-len(suffix)-1
session=PcmSession.create(proof/('p'*padding)/'session',recording_id=str(uuid.uuid4()))
assert len(str(session.root/'requests'))==196
pcm=b'\1\0'*96000;session.append(0,pcm);session.seal(96000)
assert session.audio.read_bytes()==pcm and session.state()['sealed'] and len(list((session.root/'requests').glob('*.json')))==2
result={'state':'PASS_WINDOWS_APP_CACHE_LENGTH_225_FINAL_234_TEMP_PREVIOUS262_TEMP_FAILED','at':datetime.now().astimezone().isoformat(),
 'sourceSha256':sha(S/'companion_local_pcm_session_20261114.py'),'requestDirectoryLength':196,'originalFailureLog':str(E/'cpu-app-schema-test-r1/ES2003b/offline-call/stderr.log'),
 'originalFailureBeforeAnyNeuralStage':True,'newNeuralCalls':0,'allPcmBytesRetained':True}
(proof/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
binding=read(old/'binding.json');binding['helpers'][str(S/'companion_local_pcm_session_20261114.py')]=result['sourceSha256'];binding.update(at=result['at'],shortTemporaryFileProof=str(proof/'result.json'))
(C/'binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ['runtime-contract.json','dualroute-protocol.json']:shutil.copyfile(old/name,C/name)
print(json.dumps(result,ensure_ascii=False))
