"""Read verified public wheel metadata/source; never install or import it."""
from pathlib import Path
from datetime import datetime
import hashlib,io,json,sys,urllib.request,urllib.parse,zipfile
S=Path('C:/Users/Billy/Desktop/Denzic/Companion/model-research/src');sys.path.insert(0,str(S))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
D=S.parent.parent/'docs/handoffs/20261109-paired-real-meeting/bilingual-local20261114/d1d2-execution/community1-preflight-r1'
OUT=Path('E:/CodexData/Companion/.model-cache/community1-preflight-20261115/public-packages-r1');OUT.mkdir(parents=True,exist_ok=False)
def fetch(url,max_bytes):
 req=urllib.request.Request(url,headers={'User-Agent':'Companion-local-public-dependency-audit/1.0'})
 with urllib.request.urlopen(req,timeout=30) as response:
  assert urllib.parse.urlsplit(response.url).hostname in {'pypi.org','files.pythonhosted.org'}
  raw=response.read(max_bytes+1);assert len(raw)<=max_bytes
 return raw
packages=[]
for name,version in [('pyannote.audio','4.0.7'),('torchaudio','2.11.1')]:
 url='https://pypi.org/pypi/'+name+'/'+version+'/json';metadata=fetch(url,2*1024**2)
 value=json.loads(metadata);assert value['info']['version']==version
 files=[f for f in value['urls'] if f['packagetype']=='bdist_wheel' and (f['filename'].endswith('py3-none-any.whl') or f['filename'].endswith('py3-none-win_amd64.whl'))]
 assert len(files)==1
 entry=files[0];assert not entry['yanked']
 wheel=fetch(entry['url'],4*1024**2)
 assert len(wheel)==entry['size'] and hashlib.sha256(wheel).hexdigest()==entry['digests']['sha256']
 (OUT/entry['filename']).write_bytes(wheel);(OUT/(name+'.pypi.json')).write_bytes(metadata)
 archive=zipfile.ZipFile(io.BytesIO(wheel));names=archive.namelist()
 assert not any(n.startswith('/') or '..' in Path(n).parts for n in names)
 metadata_name=next(n for n in names if n.endswith('.dist-info/METADATA'))
 source_root=D/'public-source'/name;source_root.mkdir(parents=True,exist_ok=False)
 relevant=([n for n in names if n.endswith('/core/io.py') or n.endswith('/core/pipeline.py') or n.endswith('/pipelines/speaker_diarization.py') or n.endswith('/pyannote.py') or n.endswith('/wespeaker.py')]
  if name=='pyannote.audio' else [n for n in names if n in ['torchaudio/__init__.py','torchaudio/functional/functional.py']])
 sources=[]
 for n in [metadata_name]+relevant:
  raw=archive.read(n);target=source_root/(n.replace('/','__')+'.source.txt');target.write_bytes(raw)
  sources.append({'wheelPath':n,'saved':str(target),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
 packages.append({'name':name,'version':version,'pypiMetadataUrl':url,'wheel':str(OUT/entry['filename']),
  'wheelUrl':entry['url'],'wheelSha256':entry['digests']['sha256'],'wheelBytes':len(wheel),
  'requiresPython':value['info']['requires_python'],'requiresDist':value['info']['requires_dist'],
  'nativeExtensions':[n for n in names if n.endswith(('.pyd','.dll','.so'))],
  'sources':sources,'sourceExecuted':False,'installed':False})
report={'state':'COMPLETE_PUBLIC_WHEEL_SOURCE_AND_METADATA_READ_ONLY','at':datetime.now().astimezone().isoformat(),
 'packages':packages,'gpuInitialized':False,'gatedWeightsDownloaded':False,'localCredentialsRead':False,
 'existingRuntimeChanged':False,'limits':limits.query(),'qualityQualified':False}
(D/'public-wheel-inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'state':report['state'],'packages':[{k:r[k] for k in ['name','version','requiresDist','nativeExtensions']} for r in packages]},ensure_ascii=False))
