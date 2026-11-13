from pathlib import Path
from datetime import datetime
import hashlib, json, os, subprocess

R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
W=Path(__file__).resolve().parent
D=Path('docs/handoffs/20261113-ui-foundation/reader-clarity')
files=[];inventory=[]

def copy_exact(source,rel):
    raw=source.read_bytes();target=S/rel;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(raw)
    assert source.read_bytes()==raw and target.read_bytes()==raw
    files.append(rel.as_posix())
    inventory.append(dict(file=rel.as_posix(),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))

for source,rel in [
    (R/'docs/product_backlog.json',Path('docs/product_backlog.json')),
    (R/'docs/development_log.md',Path('docs/development_log.md')),
    (R/'AGENTS.md',D/'root-project-rules129154-snapshot.txt'),
    (R/D/'complete-product129154-software.json',D/'complete-product129154-software.json'),
    (O/'source-protection129154.json',D/'resumed129154/source-protection.json'),
    (O/'storage-final129154.json',D/'resumed129154/fixed-cache-budget.json'),
    (O/'public-source-full30-127/reader129-result.json',D/'resumed129154/actual-native-reader.json'),
    (O/'public-source-full30-127/evaluation.json',D/'resumed129154/public-source-evaluation.json'),
    (R/'docs/handoffs/20261110-android-media-import/android154/end-session.json',D/'resumed129154/phone-closed.json'),
]: copy_exact(source,rel)

for name in [
    'run_public_level_control.py','stop_active_level_control.py','evaluate_resumed_level_controls.py',
    'close_resumed_public30.py','run_public_source127_round.py','run_resumed_phone154.py',
    'review_resumed_phone154.cjs','assemble_resumed129154.py','protect_resumed129154.py',
    'close_resumed129154_records.py','windows_candidate_delivery.py','protect_resumed129154_checkpoint.py',
]: copy_exact(W/name,D/'resumed129154/engineering'/name)

record=json.loads((R/D/'complete-product129154-software.json').read_bytes())
assert record['privateRemoteReadbackVerified'] and not record['fullAcceptancePassed']
metadata=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),role='Protection snapshots only. Root Companion docs remain sole editable backlog/timeline; never backflow snapshots.',softwareArchiveSha256=record['sha256'],sourceHeads=json.loads((O/'source-protection129154.json').read_bytes())['verifiedRemoteHeads'],actualInstalledWindows='0.1.129',actualInstalledAndroid='0.1.154',interrupted01a3Included=False,mixedRoom01a7AudioTextOrRawLogsIncluded=False,allFailuresAndOriginalRecordingsRetainedLocally=True,fullAcceptancePassed=False,ownerExperienceAccepted=False,inventory=inventory)
rel=D/'resumed129154/checkpoint.json'
(S/rel).write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf8');files.append(rel.as_posix())
g=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m']
env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe','GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
subprocess.run(g+['add','--',*files],cwd=S,check=True)
subprocess.run(g+['-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol','diff','--cached','--check','--',*files],cwd=S,check=True)
subprocess.run(g+['commit','--only','-m','Protect129154 unified software delivery and real remaining quality scope','--',*files],cwd=S,check=True)
head=subprocess.check_output(g+['rev-parse','HEAD'],cwd=S,text=True).strip()
branch='work/template129-complete-reader-20261113'
subprocess.run(g+['push','origin','HEAD:refs/heads/'+branch],cwd=S,env=env,check=True,timeout=180)
remote=subprocess.check_output(g+['ls-remote','origin','refs/heads/'+branch],cwd=S,env=env,text=True,timeout=45).split()[0]
assert remote==head
receipt=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),sourceCommit=head,protectedBranch=branch,remoteReadback=remote,files=files,otherSourceEditsNotStagedOrCommitted=True,canonicalRootStillSoleEditableSource=True,fullAcceptancePassed=False)
(O/'final-source-checkpoint129154.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(receipt,ensure_ascii=False))
