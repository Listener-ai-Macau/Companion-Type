"""Pin official compatible self-enrolled target ASR, source review before execution."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,sys,urllib.request
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=R/'docs/handoffs/20261109-sedicow-r1';C.mkdir(exist_ok=False);sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=256*1024**2)
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Companion-public-research'}),timeout=30) as f:return f.read()
model='BUT-FIT/SE-DiCoW';metadata=json.loads(get('https://huggingface.co/api/models/'+model+'?blobs=true'));assert metadata['gated'] is False and metadata['cardData']['license']=='apache-2.0';revision=metadata['sha'];source=M/'upstream-tse'/('sedicow-'+revision);source.mkdir(exist_ok=False);files=[]
for row in metadata['siblings']:
 name=row['rfilename']
 if Path(name).suffix not in ['.py','.json','.txt','.md']:continue
 if row.get('size',0)>6*1024**2:continue
 assert not Path(name).is_absolute() and '..' not in Path(name).parts
 data=get('https://huggingface.co/'+model+'/resolve/'+revision+'/'+name)
 if row.get('blobId'):assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==row['blobId']
 target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);files.append({'file':str(target),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'gitBlobSha1':row.get('blobId')})
weight=next(r for r in metadata['siblings'] if r['rfilename']=='model.safetensors')
write(C/'source.json',{'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'PINNED_OFFICIAL_COMPATIBLE_SOURCE_NOT_EXECUTED_NO_WEIGHTS','model':model,'revision':revision,'sourceRoot':str(source),'gated':False,'license':metadata['cardData']['license'],'files':files,'weight':{'file':'model.safetensors','bytes':weight['size'],'sha256':weight['lfs']['sha256'],'url':'https://huggingface.co/'+model+'/resolve/'+revision+'/model.safetensors'},'olderUnderscoreVariantExcluded':'OfficialBUT-FIT/SE_DiCoW README directs users to hyphenSE-DiCoW for code compatibility. Choose officialrecommended variant, notmultiplecheckpoints.','whyDifferent':'Target-speaker ASR directly conditioned on STNO activity plus self-enrollment, without a waveformseparator. Tests whether PS4waveform-content distortion can be bypassed. Keep normalQwen and all rawaudio.','existingDiarizerToReuse':'OuralreadymeasuredNemotron automatic8speaker probabilities, not bundledCC-BY-NC DiariZen weights.','primarySources':['https://huggingface.co/BUT-FIT/SE-DiCoW','https://github.com/BUTSpeechFIT/TS-ASR-Whisper','https://arxiv.org/abs/2601.19194','https://www.isca-archive.org/mlcslm_2025/polok25_mlcslm.pdf'],'limitations':'Officialbenchmarks are mostlyEnglish; Chinese accuracy under5% and robustness to our imperfectdiarization remain unproven. Speakeractivity-conditioning is not post-hocword relabeling. No qualityclaim from sourcedownload.','codeExecuted':False,'weightsDownloaded':False,'saleQualified':False})
print(json.dumps({'model':model,'revision':revision,'source':str(source),'codeFiles':len(files),'weightsBytes':weight['size'],'weightsDownloaded':False},ensure_ascii=False),flush=True)
