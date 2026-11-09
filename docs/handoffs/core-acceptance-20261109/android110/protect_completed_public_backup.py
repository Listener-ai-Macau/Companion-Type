"""Protect only the verified public meeting backup in the existing private draft."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess
C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6')
proof=json.loads((C/'phone-d6/backup-restore112.json').read_text());archive=P/'Companion-QA112-S_R004S03C01-complete-backup.zip'
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
assert sha(archive)==proof['backupSha256'] and proof['serviceKeyAbsent'] and proof['restoredFilesVerified']==13
meta=C/'phone-d6/Android112-Public-Meeting-Restore-Verification.json';shutil.copyfile(C/'phone-d6/backup-restore112.json',meta)
repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
def gh(*args):
    p=subprocess.run(['gh',*map(str,args)],capture_output=True,text=True,env={**os.environ,'GH_PROMPT_DISABLED':'1'},creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stderr[-1000:];return p.stdout
release=json.loads(gh('api','repos/'+repo+'/releases/438762888'));assert release['draft'] and release['tag_name']==tag
names={x['name'] for x in release['assets']};missing=[p for p in [archive,meta] if p.name not in names]
if missing:gh('release','upload',tag,*missing,'--repo',repo)
back=P/'remote-public-backup-readback';back.mkdir(exist_ok=True)
if not (back/archive.name).exists():gh('release','download',tag,'--repo',repo,'--pattern',archive.name,'--dir',back)
assert sha(back/archive.name)==proof['backupSha256']
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'COMPLETE_PUBLIC_PHONE_MEETING_BACKUP_REMOTE_READBACK_IDENTICAL','archive':archive.name,'bytes':archive.stat().st_size,'sha256':proof['backupSha256'],'privateDraftReleaseId':438762888,'draft':True,'published':False,'downloadHashIdentical':True,'ownerOriginalPhoneFilesUploaded':False,'serviceCredentialsUploaded':False}
(C/'phone-d6/public-meeting-remote-backup112.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
