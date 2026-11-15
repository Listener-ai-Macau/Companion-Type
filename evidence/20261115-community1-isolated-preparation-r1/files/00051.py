from pathlib import Path
import hashlib,json,subprocess,sys
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/community1-preflight-r1'
report=json.loads((D/'public-wheel-inspection.json').read_text(encoding='utf-8'))
entry=next(p for p in report['packages'] if p['name']=='torchaudio')
assert hashlib.sha256(Path(entry['wheel']).read_bytes()).hexdigest()==entry['wheelSha256']
target=Path('E:/CodexData/Companion/.model-cache/community1-preflight-20261115/isolated-torchaudio-r1');assert not target.exists()
with (D/'torchaudio-isolated-install.log').open('xb') as log:
 code=subprocess.call([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-index','--no-deps',
  '--no-compile','--target',str(target),entry['wheel']],stdout=log,stderr=subprocess.STDOUT)
assert code==0,'Retain installation failure; do not change existing runtime'
print(json.dumps({'isolatedTarget':str(target),'installedWithoutDependencies':True,'limits':limits.query()}))
