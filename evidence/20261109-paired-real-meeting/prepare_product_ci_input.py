"""Only public frozen WAVs; no references, personal files or model configuration."""
from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent
P=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/product-ci');P.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=160*1024**2)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
items=json.loads((C/'fixed-asr-audio-only.json').read_text());manifest=[]
archive=P/'Companion-public-R8001-M8004-five-inputs-20261110.zip'
assert not archive.exists(),'Preserve the original input bundle'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_STORED) as z:
    for row in items:
        assert sha(row['audio'])==row['audioSha256'];name=row['id']+'.wav';z.write(row['audio'],name)
        manifest.append({'id':row['id'],'wav':name,'sha256':row['audioSha256'],'seconds':row['audioSeconds']})
    z.writestr('audio-only.json',json.dumps(manifest,indent=2)+'\n')
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'archive':str(archive),'name':archive.name,'sha256':sha(archive),'bytes':archive.stat().st_size,'cases':manifest,'referencesIncluded':False,'privateContentsIncluded':False,'sourceAudioChanged':False,'limits':limits.query()}
(C/'product-ci-input.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:record[k] for k in ['name','sha256','bytes']},ensure_ascii=False))
