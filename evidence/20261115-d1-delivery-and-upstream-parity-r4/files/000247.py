"""Actual completed-cache reuse/refusal on an isolated copy of public full S.

No reference file is provided. The original full experiment and weights stay
untouched. A cleaned committed raw window must not silently load a model.
"""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-qwen-signal-r3';source=C/'full';name='S_R004S03C01'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
completed=read(source/'transcripts'/name/'completed-state.json');assert completed['state']=='COMPLETE_RECOVERABLE_CPU_TRANSCRIPT_UNQUALIFIED'
target=C/'cache-recovery-proof.json';assert not target.exists()
cache=Path('E:/CodexData/Companion/.model-cache/qwen-native-asr-20261107/full-cache-recovery-control');cache.mkdir(exist_ok=False);control=cache/'full';control.mkdir()
for file in ['protocol.json','short-native-state.json','S-original-first30s-output.json']:shutil.copyfile(C/file,cache/file)
shutil.copyfile(source/'audio-only.json',control/'audio-only.json')
out=control/'transcripts'/name;out.mkdir(parents=True)
for file in ['state.json','completed-state.json','model-output.json','attribution-review.json']:shutil.copyfile(source/'transcripts'/name/file,out/file)
(out/'windows').mkdir()
raw_source=source/'transcripts'/name/'windows'
for file in raw_source.glob('*.raw.json'):shutil.copyfile(file,out/'windows'/file.name)
before_output=sha(out/'model-output.json');before_raw={f.name:sha(f) for f in (out/'windows').glob('*.raw.json')}
worker=Path(__file__).with_name('practical_qwen_full_worker_20261107.py')
command=[sys.executable,str(worker),'--control',str(control),'--index','0','--resume']
def run(label):
    with (C/(label+'.log')).open('xb') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    return r.returncode,read(out/'completed-state.json')
code,state=run('completed-full-cache-reopen');assert code==0 and state['newNeuralWindows']==0 and not state['modelLoaded'] and state['reusedWindows']==state['totalWindows']
assert sha(out/'model-output.json')==before_output and before_raw=={f.name:sha(f) for f in (out/'windows').glob('*.raw.json')}
missing=out/'windows/000001.raw.json';held=out/'windows/000001.raw.json.held';assert missing.resolve().is_relative_to(cache.resolve()) and held.resolve().is_relative_to(cache.resolve()) and not held.exists();missing.rename(held)
for label in ['missing-full-cache-refusal','missing-full-cache-refusal-again']:
    code,state=run(label)
    assert code!=0 and state['newNeuralWindows']==0 and not state['modelLoaded'] and state['completedCacheOnly']
    assert sha(out/'model-output.json')==before_output and sha(held)==before_raw['000001.raw.json']
    assert {f.name:sha(f) for f in (out/'windows').glob('*.raw.json')}=={k:v for k,v in before_raw.items() if k!='000001.raw.json'}
assert sha(source/'transcripts'/name/'model-output.json')==before_output and before_raw=={f.name:sha(f) for f in raw_source.glob('*.raw.json')}
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_FULL_CACHE_IDENTICAL_ZERO_MODEL_AND_STICKY_MISSING_RAW_REFUSAL','meeting':name,'audioSha256':completed['audioSha256'],'outputSha256':before_output,'workerSourceSha256':sha(worker),'neuralInferenceAdded':0,'modelLoadedInControls':False,'referenceFilesProvided':False,'originalExperimentRawAndOutputUnchanged':True,'isolatedHeldRawBytesPreserved':True,'fullCacheReopenSameBytes':True,'missingCacheRefusedTwice':True,'qualityQualified':False}
target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
