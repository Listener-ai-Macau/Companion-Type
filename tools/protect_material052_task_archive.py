"""Explicitly include the canonical snapshot despite the repository ZIP ignore rule."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, os, subprocess, hashlib, zipfile, shutil
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'recovered-software050'
b=r/'docs/handoffs/20261106-material-exports052';dest=s/'docs/handoffs/20261106-material-exports052'
branch='work/material-exports052-20261106';rel=dest.relative_to(s).as_posix()
env=os.environ.copy();env.update(GIT_SSH_COMMAND='ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2',GIT_TERMINAL_PROMPT='0')
def git(*args):
    p=subprocess.run(['git',*args],cwd=s,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    assert p.returncode==0,p.stdout+p.stderr
    return p.stdout.strip()
assert git('branch','--show-current')==branch
assert git('rev-parse','HEAD')=='54103004d2676568b7d5937e251fb729badd19f7'
old=json.loads((b/'remote-verification.json').read_text(encoding='utf8'))
old.update(status='INITIAL_SAFE_RECEIPTS_PUSHED_CANONICAL_ZIP_WAS_IGNORED',sourceAndTaskBackupProtected=False,
           reason='Repository *.zip rule excluded new canonical snapshot; explicit tracking required before claiming backup.')
(b/'remote-verification-initial.json').write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(b/'remote-verification.json').write_text(json.dumps({'status':'CANONICAL_ARCHIVE_EXPLICIT_PUSH_PENDING','sourceAndTaskBackupProtected':False},indent=2)+'\n',encoding='utf8')
log=r/'docs/development_log.md';before=log.read_bytes()
marker='## 2026-11-06T09:48:28+08:00｜白天无独显：Windows052已安装，已存材料PPTX/PNG交付，原资料保持'.encode('utf8')
assert marker in before
note='\n备份收尾原失败保留：交付安全收据54103004已推远端，但目录git add受原*.zip忽略规则影响，唯一任务/日志快照未被纳入；首次“任务备份已保护”收据标记已纠正。随后显式跟踪该6MB快照，并以远端分支及提交树实际对象校验为准，见同批remote-verification.json；原资料清单/备份不纳入。\n'
start=before.index(marker)+len(marker)
after=before[:start]+note.encode('utf8')+before[start:]
assert log.read_bytes()==before
log.write_bytes(after)
archive=dest/'canonical-task-history-20261106-delivery.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
    for name in ['docs/product_backlog.json','docs/development_log.md','docs/PRODUCT_BACKLOG.md']:z.write(r/name,name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    d=json.loads(z.read('docs/product_backlog.json'))
    rows=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCompetitiveParity20261105']['coverage']
    assert len(rows)==36 and all(x['ownerAcceptance']['status']=='PENDING' for x in rows)
shutil.copy2(b/'remote-verification-initial.json',dest/'remote-verification-initial.json')
readme=dest/'README.md'
readme.write_text(readme.read_text(encoding='utf8')+'\nPost-build source comparison: 1085 files match frozen SHA exactly; Cargo.toml differs only in CRLF/LF and its normalized content is identical. See post-build-source-check.json. The canonical ZIP is explicitly tracked despite the generic *.zip ignore rule.\n',encoding='utf8')
shutil.copy2(Path(__file__),s/'tools/protect_material052_task_archive.py')
git('add','--',rel+'/README.md',rel+'/remote-verification-initial.json','tools/protect_material052_task_archive.py')
git('add','-f','--',rel+'/canonical-task-history-20261106-delivery.zip')
assert rel+'/canonical-task-history-20261106-delivery.zip' in git('diff','--cached','--name-only').splitlines()
git('-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Track canonical Windows 052 task and timeline recovery snapshot explicitly')
commit=git('rev-parse','HEAD')
blob=git('rev-parse','HEAD:'+rel+'/canonical-task-history-20261106-delivery.zip')
assert blob==git('hash-object',str(archive))
assert int(git('cat-file','-s',blob))==archive.stat().st_size
print('COMMITTED '+commit+'; canonical archive object '+blob,flush=True)
git('-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
remote=git('ls-remote','origin',f'refs/heads/{branch}').split()[0];assert remote==commit
result={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        'status':'SOURCE_SAFE_RECEIPTS_AND_CANONICAL_ARCHIVE_REMOTE_READBACK_VERIFIED',
        'branch':branch,'functionalSourceCommit':'e684fa73b3c14423c0f62cd961af6732470b3a02',
        'receiptCommit':commit,'remoteReadback':remote,'canonicalArchiveGitBlob':blob,
        'canonicalSnapshotBytes':archive.stat().st_size,'canonicalSnapshotSha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'sourceAndTaskBackupProtected':True,'privateAppDataUploaded':False,'binaryPackagesUploaded':False,
        'priorIncompleteBackupReceipt':'remote-verification-initial.json'}
(b/'remote-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False),flush=True)
