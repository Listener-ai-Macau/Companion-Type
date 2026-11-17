"""Acquire only the maintained CPU INT8 export of the already selected family."""
from pathlib import Path
from datetime import datetime
import hashlib,json,shutil,sys,time,requests
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from meeting_acoustic_worker_20261116 import own_limits
from durable_model_state_20261117 import atomic_json
limits=own_limits(5)
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117')
meta=json.loads((C/'parakeet-cpu-export-asset-metadata.json').read_text(encoding='utf-8'))
root=Path('E:/CodexData/Companion/.model-cache/parakeet-v3-int8-cpu-official20261117');root.mkdir(exist_ok=False)
out=C/'parakeet-cpu-export-acquisition-r1';out.mkdir(exist_ok=False)
names=['encoder.int8.onnx','decoder.int8.onnx','joiner.int8.onnx','tokens.txt']
files={x['rfilename']:x for x in meta['siblings'] if x['rfilename'] in names};assert set(files)==set(names)
assert shutil.disk_usage(root).free>=30*1024**3+sum(x['size'] for x in files.values())
start=time.monotonic();state=dict(state='ACQUIRING_SINGLE_EXISTING_PARakeet_CPU_EXPORT',revision=meta['sha'],files=[],newInference=0,newTrainingUpdates=0,
 failedAdaptedWeightsIncluded=False,trainingCandidatePromoted=False,qualityQualified=False)
def save(**v):
 state.update(v,at=datetime.now().astimezone().isoformat(),limits=limits.query());atomic_json(out/'state.json',state,progress=True)
try:
 for name in names:
  record=files[name];target=root/name;part=target.with_suffix(target.suffix+'.partial')
  url=f'https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8/resolve/{meta["sha"]}/{name}'
  count=0;digest=hashlib.sha256();git=hashlib.sha1(('blob '+str(record['size'])+'\0').encode());save(activeFile=name,receivedBytes=0)
  with requests.get(url,stream=True,timeout=(20,30)) as response:
   response.raise_for_status()
   with part.open('xb') as f:
    for block in response.iter_content(4*1024**2):
     assert time.monotonic()-start<900,'Bounded acquisition window ended'
     if not block:continue
     count+=len(block);assert count<=record['size'];digest.update(block);git.update(block);f.write(block);save(activeFile=name,receivedBytes=count)
  assert count==record['size']
  assert digest.hexdigest()==record['lfs']['sha256'] if 'lfs' in record else git.hexdigest()==record['blobId']
  part.rename(target);state['files'].append(dict(file=str(target),bytes=count,sha256=digest.hexdigest(),sourceUrl=url));save()
 save(state='COMPLETE_PINNED_PARakeet_CPU_INT8_EXPORT_ACQUISITION',seconds=time.monotonic()-start)
 atomic_json(out/'completed.json',state);print(json.dumps(state,ensure_ascii=False))
except BaseException as error:
 save(state='FAILED_CPU_EXPORT_ACQUISITION_RETAINED',error=repr(error));atomic_json(out/'completed.json',state);raise
