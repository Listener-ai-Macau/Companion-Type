"""Prepare only the official checksum-pinned Vulkan runtime; no model inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,stat,urllib.request,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=R/'docs/handoffs/20261107-model-generation-recovery/nemotron-speaker-20261107-prep';E=Path('E:/CodexData/Companion/.model-cache/nemotron-speaker-20261107')
metadata=json.loads((C/'release-metadata.json').read_text(encoding='utf8'));asset=next(x for x in metadata['assets'] if x['name']=='nemo-speech-0.3.0-windows-x86_64-vulkan.zip');path=E/asset['name'];expected=asset['digest'].removeprefix('sha256:')
def sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
if not path.exists():
    temporary=path.with_suffix('.zip.part')
    with urllib.request.urlopen(asset['browser_download_url'],timeout=45) as source,temporary.open('wb') as dest:shutil.copyfileobj(source,dest,1024*1024);dest.flush();os.fsync(dest.fileno())
    assert temporary.stat().st_size==asset['size'] and sha(temporary)==expected;os.replace(temporary,path)
assert path.stat().st_size==asset['size'] and sha(path)==expected
out=E/'runtime-0.3.0-vulkan';out.mkdir(exist_ok=True)
with zipfile.ZipFile(path) as archive:
    for member in archive.infolist():assert (out/member.filename).resolve().is_relative_to(out.resolve()) and not stat.S_ISLNK(member.external_attr>>16)
    archive.extractall(out)
exe=next(out.rglob('nemo-speech.exe'));record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'OFFICIAL_VULKAN_RUNTIME_PREPARED_NO_INFERENCE','runtime':str(exe),'runtimeSha256':sha(exe),'archive':{'file':str(path),'sha256':expected,'bytes':asset['size'],'source':asset['browser_download_url']},'backend':'Vulkan, not the failed Windows HIP decoder','gpuSelectionRequired':'Actual native registry must uniquely identify RX6800XT; no fallback to integrated780M','inferencePerformed':False}
(C/'vulkan-prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False),flush=True)
