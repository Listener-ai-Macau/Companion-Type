"""Resolve public additions against a frozen installed runtime; no installation."""
from pathlib import Path
from datetime import datetime
from importlib.metadata import distributions
import hashlib,json,os,subprocess,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/community1-preflight-r1'
base=Path(sys.executable).parent.parent/'Lib/site-packages'
extra=Path('E:/CodexData/Companion/.model-cache/community1-preflight-20261115/isolated-torchaudio-r1')
assert (D/'torchaudio-import-control.json').exists()
rows=[];seen={}
for dist in distributions(path=[str(base),str(extra)]):
 name=dist.metadata['Name'];version=dist.version;canonical=name.lower().replace('_','-').replace('.','-')
 assert canonical not in seen or seen[canonical]==version
 seen[canonical]=version;rows.append({'name':name,'version':version})
assert seen['torch']=='2.11.0+rocm10.0.0' and seen['torchaudio']=='2.11.1'
target=D/'frozen-existing-runtime.txt';assert not target.exists()
target.write_text('\n'.join(sorted({r['name']+'=='+r['version'] for r in rows}))+'\n',encoding='utf-8')
(D/'frozen-existing-runtime.json').write_text(json.dumps({'at':datetime.now().astimezone().isoformat(),
 'baseSite':str(base),'additionalSite':str(extra),'distributions':rows,
 'torchInitSha256':hashlib.sha256((base/'torch/__init__.py').read_bytes()).hexdigest()},indent=2)+'\n',encoding='utf-8')
env=dict(os.environ);env['PYTHONPATH']=str(extra)
env['PIP_CACHE_DIR']='E:/CodexData/Companion/.model-cache/community1-preflight-20261115/pip-cache'
command=[sys.executable,'-m','pip','--isolated','install','--disable-pip-version-check','--dry-run',
 '--report',str(D/'dependency-resolution.json'),'--index-url','https://pypi.org/simple',
 '--constraint',str(target),'pyannote.audio==4.0.7','torchaudio==2.11.1']
with (D/'dependency-resolution.log').open('xb') as log:
 code=subprocess.call(command,env=env,stdout=log,stderr=subprocess.STDOUT)
receipt={'state':'DEPENDENCIES_RESOLVED_WITH_EXISTING_RUNTIME_FROZEN' if code==0 else 'DEPENDENCY_CONFLICT_RETAINED_NO_INSTALL',
 'at':datetime.now().astimezone().isoformat(),'exitCode':code,'installed':False,'existingRuntimeChanged':False,
 'limits':limits.query()}
(D/'dependency-resolution-state.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt));sys.exit(code)
