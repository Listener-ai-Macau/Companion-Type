"""Pin one tiny published WindowsCPU WebRTCVAD wheel, without touching shared runtimes."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import sys
import urllib.request
import zipfile

S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
OUT=Path('E:/CodexData/Companion/.model-cache/webrtcvad-wheels-20261117')
assert not OUT.exists();OUT.mkdir()
with urllib.request.urlopen('https://pypi.org/pypi/webrtcvad-wheels/json',timeout=25) as response:
    raw=response.read(5*1024**2);assert len(raw)<5*1024**2
metadata=json.loads(raw);(OUT/'pypi-metadata.json').write_bytes(raw)
files=[r for r in metadata['urls'] if r['filename'].endswith('cp311-cp311-win_amd64.whl')]
assert len(files)==1,'One exact published Python3.11Windowsx64 wheel required'
item=files[0];assert item['size']<1024**2
with urllib.request.urlopen(item['url'],timeout=25) as response:
    wheel_bytes=response.read(1024**2);assert len(wheel_bytes)==item['size']
assert hashlib.sha256(wheel_bytes).hexdigest()==item['digests']['sha256']
wheel=OUT/item['filename'];wheel.write_bytes(wheel_bytes)
package=OUT/'package';package.mkdir()
with zipfile.ZipFile(wheel) as archive:
    for member in archive.infolist():
        p=Path(member.filename);assert not p.is_absolute() and '..' not in p.parts
        if member.is_dir():continue
        target=package/p;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(archive.read(member))
license_files=[p for p in package.rglob('*') if p.is_file() and 'license' in p.name.lower()]
assert license_files
receipt={'state':'PINNED_PUBLISHED_CPU_WEBRTCVAD_WHEEL_NOT_SHARED_RUNTIME_INSTALL',
    'at':datetime.now().astimezone().isoformat(),'distribution':'webrtcvad-wheels',
    'version':metadata['info']['version'],'projectUrls':metadata['info']['project_urls'],
    'pypiMetadataSha256':hashlib.sha256(raw).hexdigest(),'wheel':str(wheel),
    'wheelBytes':len(wheel_bytes),'wheelSha256':item['digests']['sha256'],'wheelPublisherUrl':item['url'],
    'localImportRoot':str(package),'licenseFiles':[str(p) for p in license_files],
    'packageFiles':[{'file':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in package.rglob('*') if p.is_file()],
    'sharedPythonOrSystemPackagesChanged':False,'newNeuralCalls':0,'parameterUpdates':0,
    'upstreamWrapper':'https://github.com/daanzu/py-webrtcvad-wheels',
    'originalWrapper':'https://github.com/wiseman/py-webrtcvad','limits':limits.query()}
(OUT/'asset-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:receipt[k] for k in ['state','version','wheelBytes','wheelSha256','localImportRoot']},ensure_ascii=False))
