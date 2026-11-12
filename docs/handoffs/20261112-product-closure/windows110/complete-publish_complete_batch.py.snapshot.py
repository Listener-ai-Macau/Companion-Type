from pathlib import Path
from datetime import datetime
import subprocess,json,hashlib

root=Path('C:/Users/Billy/Desktop/Denzic/Companion');batch=root/'docs/handoffs/20261112-product-closure/windows110';p=batch/'complete-delivery.json';record=json.loads(p.read_text(encoding='utf-8'));file=Path(record['archive'])
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(file)==record['sha256'] and record['allArchiveMemberChecksumsMatched']
repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate']
release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True));assert release['isDraft']
existing=next((x for x in release['assets']if x['name']==file.name),None)
if existing:assert existing['digest']=='sha256:'+record['sha256'],'Preserve existing private asset; never overwrite a different batch'
else:subprocess.run(['gh','release','upload',tag,str(file),'--repo',repo],check=True)
back=Path('E:/CodexData/Companion/deliveries/readback-20261112-complete');back.mkdir(exist_ok=True);remote=back/file.name
if not remote.exists():subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',file.name,'--dir',str(back)],check=True)
assert sha(remote)==record['sha256'] and remote.stat().st_size==record['bytes']
record.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='ONE_COMPLETE_CANDIDATE_PRIVATE_DELIVERY_FULL_READBACK_VERIFIED',privateRemoteReadbackVerified=True,remoteReadbackSha256=sha(remote),privateDraft=release['url'],publishedPublicly=False)
text=json.dumps(record,ensure_ascii=False,indent=2)+'\n';p.write_text(text,encoding='utf-8');Path('outputs/Companion-Complete-Candidate-20261112.json').write_text(text,encoding='utf-8')
print(json.dumps({k:v for k,v in record.items()if k!='manifest'},ensure_ascii=False,indent=2))
