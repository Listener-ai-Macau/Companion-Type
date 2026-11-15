"""Actual cache-only compatibility/refusal control, no neural model loaded."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/practical-verbatim-r1'
source=Path('E:/CodexData/Companion/.model-cache/entry-check-20261107-r1/attempt-0001')
dest=Path('E:/CodexData/Companion/.model-cache/verbatim-control-20261107/cache-compat-r1')
assert not dest.exists();dest.mkdir(parents=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name in ['audio-only.json','asr-protocol.json']:shutil.copyfile(source/name,dest/name)
for name in ['transcripts','results']:shutil.copytree(source/name,dest/name)
case=read(dest/'audio-only.json')[0];out=dest/'transcripts'/case['meeting'];before=sha(out/'model-output.json');raw={p.name:sha(p) for p in (out/'windows').glob('*.raw.json')}
cmd=[sys.executable,str(Path(__file__).with_name('practical_transcript_worker_20261107.py')),'--control',str(dest),'--index','0','--resume','--cached-only']
with (C/'default-cache-compatibility.log').open('xb') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
assert r.returncode==0 and sha(out/'model-output.json')==before
first=read(out/'completed-state.json');assert not first['modelLoaded'] and first['newNeuralWindows']==0
protocol=read(dest/'asr-protocol.json');protocol['useItn']=False
(dest/'asr-protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
with (C/'changed-itn-cache-refusal.log').open('xb') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
second=read(out/'completed-state.json');assert r.returncode!=0 and second['state']=='FAILED_RETAINED_RESUMABLE' and not second['modelLoaded'] and second['newNeuralWindows']==0
assert sha(out/'model-output.json')==before and raw=={p.name:sha(p) for p in (out/'windows').glob('*.raw.json')}
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PASS_DEFAULT_CACHE_COMPATIBILITY_AND_CHANGED_ITN_REFUSAL_NO_MODEL',
 'sourceWorkerSha256':sha(Path(__file__).with_name('practical_transcript_worker_20261107.py')),'unchangedOutputSha256':before,
 'rawFilesUnchanged':True,'defaultOldProtocolWithNoUseItnStillMeansTrue':True,'changedFlagCannotReuseOldNeuralCache':True,
 'neuralWindowsAdded':0,'modelLoadedInEitherControl':False,'public30sOnly':True,'qualityQualified':False}
(C/'cache-binding-proof.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
