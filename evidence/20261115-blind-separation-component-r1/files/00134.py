from pathlib import Path
from datetime import datetime
from email.parser import BytesParser
import hashlib,json,sys,urllib.request,zipfile
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=1024**3)
R=S.parent.parent;D=R/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution'
C=D/'blind-separation-composition-r1';K=Path('E:/CodexData/Companion/.model-cache/blind-separation-composition-20261115')
target=K/'isolated-dependencies';target.mkdir(exist_ok=False)
wheelroot=K/'wheels';wheelroot.mkdir(exist_ok=True)
items=[]
for package,version in [('einops','0.8.2'),('rotary-embedding-torch','0.8.9'),('torchinfo','1.8.0')]:
    metadata=json.load(urllib.request.urlopen('https://pypi.org/pypi/'+package+'/'+version+'/json',timeout=30))
    wheel=next(r for r in metadata['urls'] if r['filename'].endswith('py3-none-any.whl'))
    path=wheelroot/wheel['filename'];raw=urllib.request.urlopen(wheel['url'],timeout=30).read()
    assert hashlib.sha256(raw).hexdigest()==wheel['digests']['sha256'];path.write_bytes(raw)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():assert not name.startswith('/') and '..' not in Path(name).parts
        archive.extractall(target)
        entry=next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
        info=BytesParser().parsebytes(archive.read(entry));dependencies=info.get_all('Requires-Dist',[])
    items.append(dict(package=package,version=version,wheel=str(path),sha256=wheel['digests']['sha256'],source=wheel['url'],dependencies=dependencies))
result=dict(state='ISOLATED_THREE_PURE_PYTHON_DEPENDENCIES_NO_BASE_RUNTIME_CHANGES',
            at=datetime.now().astimezone().isoformat(),target=str(target),packages=items,
            installedWithNoDependencyUpgrade=True,baseTorchOrTransformersChanged=False,
            newNeuralCalls=0,limits=limits.query())
(C/'isolated-runtime.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='limits'}))
