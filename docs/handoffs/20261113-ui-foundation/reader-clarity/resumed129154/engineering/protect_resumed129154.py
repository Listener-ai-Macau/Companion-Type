from pathlib import Path
from datetime import datetime
import hashlib, json, os, subprocess, sys

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity'
V=Path(__file__).resolve().parent.parent/'outputs'
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,1024**3)

def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
    Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
g=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m']
env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe','GIT_TERMINAL_PROMPT':'0'}
expected={
    'work/template129-complete-reader-20261113':'ad84482609f37d7780d6e1518256257d7e361f7e',
    'work/template129-complete-frozen-20261113':'af02c09d6b7b5773ed9d7ef76ffc0be98937bb81',
    'work/template154-complete-reader-20261113':'cecb43a5e755405a49cb4fe01fc44fd0a0ac591b',
}
rows=subprocess.check_output(g+['ls-remote','origin',*['refs/heads/'+b for b in expected]],cwd=R/'companion-device-closure055',env=env,text=True,timeout=45).splitlines()
actual={ref.removeprefix('refs/heads/'):commit for commit,ref in (row.split() for row in rows)}
assert actual==expected,(actual,expected)
source=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),verifiedRemoteHeads=actual,privateRepo='Listener-ai-Macau/Companion-Type',frozenAndAndroidTreesClean=True)
save(O/'source-protection129154.json',source)

p=H/'complete-product129154-software.json'
record=json.loads(p.read_bytes());archive=Path(record['archive'])
assert sha(archive)==record['sha256']
repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
assert json.loads(subprocess.check_output(['gh','repo','view',repo,'--json','isPrivate'],text=True))['isPrivate']
release=json.loads(subprocess.check_output(['gh','release','view',tag,'--repo',repo,'--json','isDraft,url,assets'],text=True))
assert release['isDraft']
existing=next((a for a in release['assets'] if a['name']==archive.name),None)
if existing:
    assert existing['digest']=='sha256:'+record['sha256']
else:
    subprocess.run(['gh','release','upload',tag,str(archive),'--repo',repo],check=True,timeout=180)
back=O/'complete-software-readback129154'
back.mkdir(exist_ok=True)
if not (back/archive.name).exists():
    subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',archive.name,'--dir',str(back)],check=True,timeout=180)
assert sha(back/archive.name)==record['sha256']
record.update(privateRemoteReadbackVerified=True,privateDraft=release['url'],remoteArchiveName=archive.name,privateReadbackSha256=sha(back/archive.name),privateRemoteProtectedAt=datetime.now().astimezone().isoformat(timespec='seconds'),sourceProtectionReceipt=str(O/'source-protection129154.json'),publishedPublicly=False,fullAcceptancePassed=False,inviteOwnerAcceptance=False)
for dest in [p,V/'Companion-Software-129-154-20261113-status.json',H/'resumed129154/result.json']:
    save(dest,record)
print(json.dumps({key:record[key] for key in ['archive','sha256','privateRemoteReadbackVerified','publishedPublicly','fullAcceptancePassed']},ensure_ascii=False))
