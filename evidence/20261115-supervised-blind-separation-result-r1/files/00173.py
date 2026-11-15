"""Preserve externally interrupted candidate inference; reuse only exact outputs."""
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
old=E/'candidate-r1';run=read(old/'run.json');state=read(old/'state.json')
assert not psutil.pid_exists(run['pid'])
assert state['phase']=='candidate' and state['completed']==len(state['results'])==5
assert read(E/'train-r1/state.json')['state']=='COMPLETE_ONE_FIXED_BLIND_SEPARATOR_TRAINING_PASS'
assert state['protocolSha256']==sha(T/'protocol.json')
C=T/'candidate-recovery-r2';assert not C.exists();C.mkdir()
for name in ['protocol.json','worker-binding.json']:shutil.copyfile(T/name,C/('original-'+name))
for name in ['state.json','run.json','worker.log']:shutil.copyfile(old/name,C/('interrupted-'+name))
write(C/'resume-source.json',dict(originalState=str(old/'state.json'),originalStateSha256=sha(old/'state.json'),
    results=state['results'],reason='Tool call aborted externally; recorded PID absent. Exact termination time/exit code unknown. No RAM failure evidence; no training repeated.'))
stamp=datetime.now().astimezone().isoformat()
run.update(state='INTERRUPTED_EXTERNAL_CONTROLLER_AND_WORKER_ABSENT',terminationObservedAt=stamp,
    finishedAt=None,exitCode=None,actualTerminationTimeUnknown=True,
    originalRunSnapshot=str(C/'interrupted-run.json'),automaticRetries=0)
write(old/'run.json',run)
for name in ['protocol.json','validation-audio-only.json']:shutil.copyfile(T/name,C/name)
worker=S/'blind_separator_validation_recovery_worker_20261115.py'
text=(S/'blind_separator_training_worker_20261115.py').read_text(encoding='utf-8')
needle="            rows=read(a.control/'validation-audio-only.json');results=[]"
replacement="""            rows=read(a.control/'validation-audio-only.json');results=[]
            resume=read(a.control/'resume-source.json')
            assert sha(resume['originalState'])==resume['originalStateSha256']
            cached={r['id']:r for r in resume['results']}
            assert len(cached)==5 and set(cached).issubset({r['id'] for r in rows})
            for item in cached.values():
                assert sha(item['file'])==item['sha256'] and item['referenceUsed'] is False
                array=np.load(item['file'],allow_pickle=False)
                assert array.shape==(2,32000) and array.dtype==np.float32 and np.isfinite(array).all()
            save(reusedVerifiedPredictions=5,automaticRetries=0)
"""
assert text.count(needle)==1;text=text.replace(needle,replacement)
needle='            for i,row in enumerate(rows):\n                x=data(row)'
replacement="""            for i,row in enumerate(rows):
                if row['id'] in cached:
                    results.append(cached[row['id']])
                    save(state='REUSING_EXACT_COMPLETED_SOURCE_PREDICTIONS',completed=i+1,total=len(rows),results=results)
                    continue
                x=data(row)"""
assert text.count(needle)==1;text=text.replace(needle,replacement)
assert not worker.exists();compile(text,str(worker),'exec');worker.write_text(text,encoding='utf-8')
runner=S/'run_blind_separator_validation_recovery_20261115.py'
text=(S/'run_supervised_blind_separator_20261115.py').read_text(encoding='utf-8')
assert text.count('blind_separator_training_worker_20261115.py')==1
text=text.replace('blind_separator_training_worker_20261115.py',worker.name)
assert not runner.exists();compile(text,str(runner),'exec');runner.write_text(text,encoding='utf-8')
binding=read(T/'worker-binding.json');binding['workerSha256']=sha(worker);binding['runnerSha256']=sha(runner)
binding['helpers'][str(C/'resume-source.json')]=sha(C/'resume-source.json')
write(C/'worker-binding.json',binding)
write(T/'candidate-execution.json',dict(run=str(E/'candidate-r2'),control=str(C),
    protocolUnchanged=True,originalProtocolSha256=sha(T/'protocol.json'),
    alreadyCompletedPredictions=5,remainingNewPredictions=79,trainingRepeated=False,
    actualOriginalTerminationTimeUnknown=True,ownerActionRequired=False))
print(json.dumps(read(T/'candidate-execution.json')))
