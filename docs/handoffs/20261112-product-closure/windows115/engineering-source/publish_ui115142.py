from pathlib import Path
from datetime import datetime
import json,subprocess,hashlib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');O=Path(__file__).resolve().parent.parent/'outputs';P=R/'docs/handoffs/20261112-product-closure/frontend115142/software-delivery.json';record=json.loads(P.read_bytes());repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate']
release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft'];back=Path('E:/CodexData/Companion/deliveries/readback-ui115142');back.mkdir(exist_ok=True)
for file,digest in [(Path(record['archive']),record['sha256']),(O/'Companion-Windows-0.1.115.msi',record['manifest']['softwarePurposeClosure']['windows']['installerSha256'])]:
 assert sha(file)==digest;old=next((x for x in release['assets'] if x['name']==file.name),None)
 if old:assert old['digest']=='sha256:'+digest
 else:subprocess.run(['gh','release','upload',tag,str(file),'--repo',repo],check=True)
 target=back/file.name
 if not target.exists():subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',file.name,'--dir',str(back)],check=True)
 assert sha(target)==digest and target.stat().st_size==file.stat().st_size;print(file.name+' complete private readback matched.',flush=True)
record.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ONE_UI115142_KIT_INSTALLED_PRIVATE_DELIVERY_FULL_READBACK_VERIFIED',privateRemoteReadbackVerified=True,remoteReadbackSha256=record['sha256'],privateDraft=release['url'],individualWindowsMsiRemoteReadbackVerified=True)
for target in [P,O/'Companion-UI-115-142-20261112.json']:target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
