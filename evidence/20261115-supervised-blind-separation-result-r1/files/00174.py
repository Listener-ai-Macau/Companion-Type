"""Exclude three damaged outputs; fsync new predictions before journaling."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'model-research/src'
T=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/supervised-blind-separation-r1'
E=Path('E:/CodexData/Companion/product-d1d2-20261114/supervised-blind-separation-r1')
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
failure=read(E/'candidate-r2/state.json')
assert failure['explicitNeuralCalls']==0 and failure['state']=='FAILED_FIXED_BLIND_SEPARATOR_SUPERVISED_PHASE_RETAINED'
assert not psutil.pid_exists(read(E/'candidate-r2/run.json')['pid'])
C=T/'candidate-recovery-r3';assert not C.exists();C.mkdir()
for name in ['state.json','run.json','worker.log']:shutil.copyfile(E/'candidate-r2'/name,C/('recovery-r2-'+name))
for name in ['blind_separator_validation_recovery_worker_20261115.py','run_blind_separator_validation_recovery_20261115.py']:
    shutil.copyfile(S/name,C/('before-repair-'+name))
shutil.copyfile(T/'candidate-recovery-r2/worker-binding.json',C/'before-repair-worker-binding.json')
old=E/'candidate-r1/state.json';state=read(old);valid=[];invalid=[]
for item in state['results']:
    actual=sha(item['file'])
    (valid if actual==item['sha256'] else invalid).append(item if actual==item['sha256'] else dict(**item,actualFileSha256=actual))
assert len(valid)==2 and len(invalid)==3
write(C/'resume-source.json',dict(originalState=str(old),originalStateSha256=sha(old),results=valid,
    completedVerifiedPredictions=2,invalidOriginalPredictions=invalid,
    reason='External interruption left3original prediction files with mismatched SHA. They remain untouched, excluded from reuse. First recovery correctly rejected before any new neural call. Preserve2verified outputs, regenerate82, fsync before journal. No training/parameter/model change.'))
for name in ['protocol.json','validation-audio-only.json']:shutil.copyfile(T/name,C/name)
worker=S/'blind_separator_validation_recovery_worker_20261115.py'
text=worker.read_text(encoding='utf-8')
assert 'assert len(cached)==5' in text
text=text.replace('assert len(cached)==5',"assert len(cached)==resume['completedVerifiedPredictions']")
text=text.replace('save(reusedVerifiedPredictions=5,automaticRetries=0)',"save(reusedVerifiedPredictions=len(cached),automaticRetries=0)")
needle="                file=a.run/(row['id']+'.npy');np.save(file,value,allow_pickle=False)"
replacement="""                file=a.run/(row['id']+'.npy')
                with file.open('wb') as durable:
                    np.save(durable,value,allow_pickle=False)
                    durable.flush();os.fsync(durable.fileno())"""
assert text.count(needle)==1;text=text.replace(needle,replacement)
compile(text,str(worker),'exec');worker.write_text(text,encoding='utf-8')
binding=read(T/'worker-binding.json');binding['workerSha256']=sha(worker)
binding['runnerSha256']=sha(S/'run_blind_separator_validation_recovery_20261115.py')
binding['helpers'][str(C/'resume-source.json')]=sha(C/'resume-source.json')
write(C/'worker-binding.json',binding)
shutil.copyfile(T/'candidate-execution.json',C/'previous-candidate-execution.json')
write(T/'candidate-execution.json',dict(run=str(E/'candidate-r3'),control=str(C),protocolUnchanged=True,
    originalProtocolSha256=sha(T/'protocol.json'),alreadyCompletedPredictions=2,
    remainingNewPredictions=82,invalidOriginalPredictions=3,trainingRepeated=False,
    fsyncBeforeJournaling=True,ownerActionRequired=False,at=datetime.now().astimezone().isoformat()))
print(json.dumps(read(T/'candidate-execution.json')))
