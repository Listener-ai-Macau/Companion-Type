"""Isolated unmodified TorchAudio Python frontend; no system/DLL installation."""
from pathlib import Path,PurePosixPath
from datetime import datetime
import hashlib,io,json,tarfile,urllib.request
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
C=R/'docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1'
revision='34c52a67e8941bbd8e6adaca0eb0b9eabec11d78';folder=M/'upstream-tse'/('torchaudio-python-'+revision)
assert not (C/'audio-frontend-source.json').exists();folder.mkdir(exist_ok=False)
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
tree=json.load(urllib.request.urlopen('https://api.github.com/repos/pytorch/audio/git/trees/'+revision+'?recursive=1',timeout=30));assert not tree['truncated']
expected={r['path']:r['sha'] for r in tree['tree'] if r['type']=='blob'}
archive=urllib.request.urlopen('https://codeload.github.com/pytorch/audio/tar.gz/'+revision,timeout=45).read()
rows=[]
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    for item in tar:
        bits=PurePosixPath(item.name).parts;rel='/'.join(bits[1:])
        if not item.isfile() or not (rel=='LICENSE' or rel.startswith('src/torchaudio/') and rel.endswith('.py')):continue
        assert rel in expected
        content=tar.extractfile(item).read()
        assert hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()==expected[rel]
        dest=folder.joinpath(*PurePosixPath(rel).parts);assert dest.resolve().is_relative_to(folder.resolve())
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
        rows.append({'file':str(dest),'sha256':hashlib.sha256(content).hexdigest(),'gitBlob':expected[rel]})
assert any(r['file'].endswith('torchaudio/__init__.py') or r['file'].endswith('torchaudio\\__init__.py') for r in rows)
atomic_json(C/'audio-frontend-source.json',{'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'OFFICIAL_TORCHAUDIO211_PYTHON_SOURCE_VERIFIED_NO_IMPORT_OR_INFERENCE',
    'revision':revision,'tag':'v2.11.0','pythonPath':str(folder/'src'),'archiveObservedSha256':hashlib.sha256(archive).hexdigest(),
    'files':rows,'scope':'Unmodified official Python transforms/functional package; no native audio extension compiled, no TorchCodec I/O used. PCM wave I/O remains standard-library. Only this worker sys.path; existing AMD runtime/global packages unchanged.',
    'limits':limits.query()})
print(json.dumps({'state':'PINNED_ISOLATED_OFFICIAL_AUDIO_FRONTEND_READY','files':len(rows)}))
