"""Pin one complete public target-speaker extractor; no model or reference inference."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,urllib.request
from practical_io_20261107 import atomic_json
from moss_windows_resource_limits_20261104 import WorkerLimits
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research'
C=R/'docs/handoffs/20261107-model-generation-recovery/practical-conditioned-ps4-r1'
E=Path('E:/CodexData/Companion/.model-cache/ps4-target-extraction-20261107');E.mkdir(parents=True,exist_ok=True);C.mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
model='TaurenMountain/PS4';revision='8feb7a1b3da1264659f155c42bfb40a5be88d730'
data=json.load(urllib.request.urlopen('https://huggingface.co/api/models/'+model+'/revision/'+revision+'?blobs=true',timeout=30));assert data['sha']==revision
atomic_json(C/'model-source-api.json',data)
folder=M/'upstream-tse'/('ps4-'+revision);folder.mkdir(parents=True,exist_ok=True)
files=[]
for item in data['siblings']:
    name=item['rfilename']
    if name=='.gitattributes':continue
    assert name in ['README.md','inference.py','checkpoint_epoch037.pt']
    dest=(E if name.endswith('.pt') else folder)/name
    if not dest.exists():
        part=dest.with_suffix(dest.suffix+'.part');assert not part.exists(),'Retain partial transfer; do not overwrite'
        endpoint='resolve' if name.endswith('.pt') else 'raw'
        request=urllib.request.Request('https://huggingface.co/'+model+'/'+endpoint+'/'+revision+'/'+name+'?download=true',headers={'User-Agent':'Companion-pinned-public-TSE-development-control'})
        with urllib.request.urlopen(request,timeout=45) as response,part.open('xb') as stream:
            while chunk:=response.read(1024*1024):stream.write(chunk)
            stream.flush();os.fsync(stream.fileno())
        assert part.stat().st_size==item['size'];os.replace(part,dest)
    assert dest.stat().st_size==item['size']
    expected=item.get('lfs',{}).get('sha256')
    if expected:assert sha(dest)==expected
    else:assert hashlib.sha1(b'blob '+str(item['size']).encode()+b'\0'+dest.read_bytes()).hexdigest()==item['blobId']
    files.append({'file':str(dest),'bytes':item['size'],'sha256':sha(dest)})
target=C/'model-ready.json';assert not target.exists()
atomic_json(target,{'at':datetime.now().astimezone().isoformat(timespec='seconds'),
    'state':'PINNED_PS4_AUTHOR_SOURCE_AND_WEIGHTS_VERIFIED_NO_INFERENCE','modelId':model,'revision':revision,
    'sourceRoot':str(folder),'weight':str(E/'checkpoint_epoch037.pt'),'files':files,
    'publicSourceUrl':'https://huggingface.co/'+model+'/tree/'+revision,
    'sourceLicenseDeclared':'Apache-2.0 model card; upstream components retain their licenses',
    'trainingDomain':'Author reports real AISHELL4/AliMeeting/AMI/CHiME6; exact overlap with our exposed recordings unknown. This is a development screen, not independent generalization acceptance.',
    'whyDifferent':'Complete author BSRNN+native ECAPA cue encoder fine-tuned with real-conversation/ASR proxy objectives. Not old VoxLock or fixed8-slot TSSEP transfer; actual enrollment audio uses the matching checkpoint encoder.',
    'inferenceStarted':False,'qualityQualified':False,'limits':limits.query()})
print(json.dumps({'state':read(target)['state'],'files':files}))
