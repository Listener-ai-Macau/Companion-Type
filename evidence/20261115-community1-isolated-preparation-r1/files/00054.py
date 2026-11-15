"""Install only hash-pinned additions into a fresh isolated directory."""
from pathlib import Path
from datetime import datetime
from importlib.metadata import distributions
import hashlib,json,os,subprocess,sys,urllib.parse
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/community1-preflight-r1'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
frozen=read(D/'frozen-existing-runtime.json');resolution=read(D/'dependency-resolution.json')
canonical=lambda name:name.lower().replace('_','-').replace('.','-')
base=Path(frozen['baseSite']);expected={canonical(r['name']):r['version'] for r in frozen['distributions']}
def current():return {canonical(d.metadata['Name']):d.version for d in distributions(path=[str(base),frozen['additionalSite']])}
assert current()==expected and hashlib.sha256((base/'torch/__init__.py').read_bytes()).hexdigest()==frozen['torchInitSha256']
target=Path('E:/CodexData/Companion/.model-cache/community1-preflight-20261115/isolated-pyannote-r1');assert not target.exists()
lines=[]
for item in resolution['install']:
 name=item['metadata']['name'];assert canonical(name) not in expected
 info=item['download_info'];url=info['url'];assert urllib.parse.urlsplit(url).hostname=='files.pythonhosted.org' and url.endswith('.whl')
 digest=info['archive_info']['hashes']['sha256'];assert len(digest)==64
 lines.append(name+' @ '+url+' --hash=sha256:'+digest)
assert len(lines)==55
requirements=D/'isolated-additions-requirements.txt';assert not requirements.exists();requirements.write_text('\n'.join(lines)+'\n',encoding='utf-8')
command=[sys.executable,'-m','pip','--isolated','install','--disable-pip-version-check','--no-input',
 '--no-deps','--no-index','--only-binary=:all:','--no-compile','--no-warn-script-location','--require-hashes',
 '--cache-dir','E:/CodexData/Companion/.model-cache/community1-preflight-20261115/pip-cache',
 '--target',str(target),'--report',str(D/'isolated-additions-install.json'),'-r',str(requirements)]
with (D/'isolated-additions-install.log').open('xb') as log:
 code=subprocess.call(command,stdout=log,stderr=subprocess.STDOUT)
assert current()==expected and hashlib.sha256((base/'torch/__init__.py').read_bytes()).hexdigest()==frozen['torchInitSha256']
receipt={'state':'INSTALLED_ISOLATED_PUBLIC_ADDITIONS_BASE_DISTRIBUTIONS_EXACTLY_UNCHANGED' if code==0 else 'ISOLATED_INSTALL_FAILED_SOURCE_AND_BASE_RETAINED',
 'at':datetime.now().astimezone().isoformat(),'target':str(target),'exitCode':code,'addedDistributions':len(lines),
 'baseDistributionsExactBeforeAfter':True,'baseTorchInitExactBeforeAfter':True,'gatedModelAccessed':False,
 'newNeuralCalls':0,'qualityQualified':False,'limits':limits.query()}
(D/'isolated-additions-install-state.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt));sys.exit(code)
