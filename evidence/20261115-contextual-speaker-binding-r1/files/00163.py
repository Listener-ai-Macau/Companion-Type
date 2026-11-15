from pathlib import Path
from datetime import datetime
import json,hashlib,shutil
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
C=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/supervised-blind-separation-r1/contextual-speaker-binding-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
P=read(C/'protocol.json');old=Path(P['associationRun']);state=read(old/'state.json')
assert state['state']=='FAILED_CONTEXTUAL_SPEAKER_QUERY_RETAINED' and state['newEncoderCalls']==0 and state['newProjectionCalls']==1
assert 'Inplace update to inference tensor' in state['error']
snapshot=C.parent.parent/'ctx-scope-r1';assert not snapshot.exists();snapshot.mkdir()
for file in [S/'contextual_speaker_binding_worker_20261115.py',C/'worker-binding.json',C/'protocol.json',old/'state.json',old/'run.json',old/'worker.log']:
    shutil.copyfile(file,snapshot/file.name)
worker=S/'contextual_speaker_binding_worker_20261115.py';text=worker.read_text(encoding='utf-8')
needle="                        counter_features[:,first:last].copy_(value[None].to('cuda:0'))"
assert text.count(needle)==1
text=text.replace(needle,"                        with torch.inference_mode():counter_features[:,first:last].copy_(value[None].to('cuda:0'))")
compile(text,str(worker),'exec');worker.write_text(text,encoding='utf-8')
binding=read(C/'worker-binding.json');binding['workerSha256']=sha(worker)
(C/'worker-binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
execution=dict(run=str(old.with_name('association-r3')),protocolSha256=sha(C/'protocol.json'),
    at=datetime.now().astimezone().isoformat(),reason='Correct inference tensor write context only; no formula/weight/data/association-rule change.',
    sourceBeforeSha256=sha(snapshot/worker.name),sourceAfterSha256=sha(worker),
    oldNumericalControlUnaffected=True,previousSeparatedQueryEncoderCalls=0,previousProjectionCalls=1,automaticRetries=0)
(C/'association-execution.json').write_text(json.dumps(execution,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(execution))
