from pathlib import Path
from datetime import datetime
import hashlib,json,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113');p=R/'docs/handoffs/20261113-ui-foundation/reader-clarity/notes132155-delivery.json';record=json.loads(p.read_bytes());archive=Path(record['archive']);repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,1024**3)
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(archive)==record['sha256']
assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate']
release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft']
existing=next((a for a in release['assets']if a['name']==archive.name),None)
if existing:assert existing['digest']=='sha256:'+record['sha256']
else:subprocess.run(['gh','release','upload',tag,str(archive),'--repo',repo],check=True,timeout=180)
back=O/'notes132155-private-readback';back.mkdir(exist_ok=True)
if not(back/archive.name).exists():subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',archive.name,'--dir',str(back)],check=True,timeout=180)
assert sha(back/archive.name)==record['sha256']
record.update(privateRemoteReadbackVerified=True,privateDraft=release['url'],remoteArchiveName=archive.name,privateReadbackSha256=record['sha256'],privateRemoteProtectedAt=datetime.now().astimezone().isoformat(timespec='seconds'),publishedPublicly=False)
for dest in [p,archive.parent/'Companion-Notes-132-155-20261113-status.json']:dest.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:record[k]for k in ['sha256','privateRemoteReadbackVerified','publishedPublicly','fullAcceptancePassed']}))
