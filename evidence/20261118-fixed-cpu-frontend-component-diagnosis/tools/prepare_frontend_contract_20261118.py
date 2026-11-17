"""Pin the existing runtime's exact frontend dependency in an isolated directory."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,sys,zipfile,requests
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from meeting_acoustic_worker_20261116 import own_limits
limits=own_limits(5)
C=Path('E:/CodexData/Companion/product-d1d2-20261114/joint-architecture-r1/language-specific-adaptation-r1/english-accuracy-reference-20261117/preprocessing-contract-20261118');C.mkdir(exist_ok=False)
root=Path('E:/CodexData/Companion/.model-cache/frontend-contract-knf1223-20261118');root.mkdir(exist_ok=False)
session=requests.Session();response=session.get('https://pypi.org/pypi/kaldi-native-fbank/1.22.3/json',timeout=20);response.raise_for_status();meta=response.json()
wheel=next(x for x in meta['urls'] if 'cp311-cp311-win_amd64.whl' in x['filename'])
response=session.get(wheel['url'],timeout=30);response.raise_for_status();payload=response.content
assert len(payload)==wheel['size']<10*1024**2 and hashlib.sha256(payload).hexdigest()==wheel['digests']['sha256']
target=root/wheel['filename'];target.write_bytes(payload)
with zipfile.ZipFile(target) as z:
 for name in z.namelist():assert (root/name).resolve().is_relative_to(root.resolve())
 z.extractall(root)
sources=[]
for repo,tag,path in [
 ('k2-fsa/sherpa-onnx','v1.13.4','cmake/kaldi-native-fbank.cmake'),
 ('k2-fsa/sherpa-onnx','v1.13.4','sherpa-onnx/csrc/offline-recognizer-transducer-nemo-impl.h'),
 ('k2-fsa/sherpa-onnx','v1.13.4','sherpa-onnx/csrc/offline-transducer-greedy-search-nemo-decoder.cc'),
 ('k2-fsa/sherpa-onnx','v1.13.4','sherpa-onnx/csrc/math.cc'),
 ('csukuangfj/kaldi-native-fbank','v1.22.3','kaldi-native-fbank/csrc/feature-fbank.cc')]:
 url=f'https://raw.githubusercontent.com/{repo}/{tag}/{path}';response=session.get(url,timeout=20);response.raise_for_status()
 p=C/(Path(path).name);p.write_bytes(response.content);sources.append(dict(url=url,file=str(p),sha256=hashlib.sha256(response.content).hexdigest()))
sys.path.insert(0,str(root));import kaldi_native_fbank as knf
opts=knf.FbankOptions()
record=dict(at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),state='PINNED_ISOLATED_NATIVE_FRONTEND_CONTRACT_READY',
 dependencyVersion=meta['info']['version'],wheelFile=str(target),wheelSha256=wheel['digests']['sha256'],isolatedModuleRoot=str(root),
 fbankOptions=[x for x in dir(opts) if not x.startswith('_')],melOptions=[x for x in dir(opts.mel_opts) if not x.startswith('_')],
 frameOptions=[x for x in dir(opts.frame_opts) if not x.startswith('_')],sources=sources,
 globalPythonPackagesChanged=False,newNeuralCalls=0,newTrainingUpdates=0,limits=limits.query())
(C/'preparation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,ensure_ascii=False))
