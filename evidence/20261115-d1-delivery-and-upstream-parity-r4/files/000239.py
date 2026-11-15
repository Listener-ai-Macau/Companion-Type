"""Actual completed-tree reopen and sticky missing-node refusal, zero models."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-bounded-r4'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
name='S_R004S03C01';source=C/'full/transcripts'/name
state=read(source/'completed-state.json');assert state['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
target=C/'cache-recovery-proof.json';assert not target.exists()
root=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/bounded-complete-cache-control');root.mkdir(exist_ok=False)
for file in ['protocol.json','seed-manifest.json','audio-only.json']:shutil.copyfile(C/file,root/file)
(root/'pilot').mkdir();shutil.copyfile(C/'pilot/state.json',root/'pilot/state.json')
out=root/'full/transcripts'/name;out.mkdir(parents=True)
for file in ['state.json','completed-state.json','model-output.json','attribution-review.json']:shutil.copyfile(source/file,out/file)
for folder in ['nodes','windows']:shutil.copytree(source/folder,out/folder)
output_sha=sha(source/'model-output.json');node_sha={p.name:sha(p) for p in (source/'nodes').glob('*.json')}
worker=Path(__file__).with_name('practical_qwen_bounded_worker_20261107.py')
command=[sys.executable,str(worker),'--control',str(root),'--phase','full','--index','0','--resume']
def run(label):
    with (C/(label+'.log')).open('xb') as log:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW).returncode
    return code,read(out/'state.json')
code,reopened=run('complete-bounded-cache-reopen')
assert code==0 and reopened['newNeuralCalls']==0 and not reopened['modelLoaded'] and reopened['completedCacheOnly']
assert sha(out/'model-output.json')==output_sha and {p.name:sha(p) for p in (out/'nodes').glob('*.json')}==node_sha
missing=out/'nodes/000001-root.json';held=missing.with_suffix('.json.held')
assert missing.resolve().is_relative_to(root.resolve()) and held.resolve().is_relative_to(root.resolve()) and not held.exists();missing.rename(held)
for label in ['missing-bounded-cache-refusal','missing-bounded-cache-refusal-again']:
    code,failed=run(label)
    assert code!=0 and failed['newNeuralCalls']==0 and not failed['modelLoaded'] and failed['completedCacheOnly']
    assert sha(out/'model-output.json')==output_sha and sha(held)==node_sha[missing.name]
    assert {p.name:sha(p) for p in (out/'nodes').glob('*.json')}=={k:v for k,v in node_sha.items() if k!=missing.name}
assert sha(source/'model-output.json')==output_sha and {p.name:sha(p) for p in (source/'nodes').glob('*.json')}==node_sha
proof={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_BOUNDED_COMPLETE_CACHE_IDENTICAL_ZERO_MODEL_STICKY_NODE_REFUSAL',
  'sourceMeeting':name,'sourceOutputSha256':output_sha,'modelLoadedInControls':False,'newNeuralCalls':0,
  'completeReopenExactDocumentAndNodeBytes':True,'missingCommittedNodeRefusedTwice':True,
  'noReferenceProvided':True,'originalExperimentUnchanged':True,'heldNodeRawPreserved':True,'qualityQualified':False}
target.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8');print(json.dumps(proof))
