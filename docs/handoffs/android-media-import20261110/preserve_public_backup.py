from pathlib import Path
from datetime import datetime
import subprocess,json,hashlib
C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone122');file=P/'Companion-public-import-backup-123.zip';proof=json.loads((C/'android123/content-bytes-result.json').read_text());digest=hashlib.sha256(file.read_bytes()).hexdigest();assert digest==proof['backupSha256'];repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
def call(args):
 q=subprocess.run(args,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert q.returncode==0,q.stderr.decode(errors='replace')[-1000:];return q.stdout
release=json.loads(call(['gh','release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft'];found=[a for a in release['assets'] if a['name']==file.name]
if not found:
 call(['gh','release','upload',tag,str(file),'--repo',repo]);release=json.loads(call(['gh','release','view',tag,'--repo',repo,'--json','isDraft,assets']));assert release['isDraft'];found=[a for a in release['assets'] if a['name']==file.name]
assert len(found)==1 and found[0]['digest']=='sha256:'+digest;asset=found[0];out=P/'remote-public-backup-readback.zip'
with out.open('wb') as stream:q=subprocess.run(['gh','api','repos/'+repo+'/releases/assets/'+asset['apiUrl'].rsplit('/',1)[1],'-H','Accept: application/octet-stream'],stdout=stream,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
assert q.returncode==0 and hashlib.sha256(out.read_bytes()).hexdigest()==digest
r={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PUBLIC_IMPORT_BACKUP_PRIVATE_DRAFT_READBACK_IDENTICAL','assetId':int(asset['apiUrl'].rsplit('/',1)[1]),'sha256':digest,'bytes':file.stat().st_size,'ownerPrivateDataUploaded':False,'credentialIncluded':False,'draftOnly':True};(C/'android123/public-backup-remote.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
