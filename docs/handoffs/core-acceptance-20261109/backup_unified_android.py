"""Protect the signed Android cohort beside the Windows recovery artifacts."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-core-acceptance');O=C/'android110';D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-remote-readback')
j=json.loads((O/'build-result.json').read_text(encoding='utf8'));assert j['state']=='ANDROID110_UNIFIED_SOURCE_SIGNED_PAYLOAD_VERIFIED_PHONE_PENDING' and j['signerMatchesPreviouslyTrustedApp']
apk=Path(j['apk']);meta=O/'Android110-core-candidate-verification.json';shutil.copyfile(O/'build-result.json',meta)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(apk)==j['apkSha256']
gh='C:/Program Files/GitHub CLI/gh.exe';repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
def call(*args):
 p=subprocess.run([gh,*map(str,args)],capture_output=True,text=True,encoding='utf8',env={**os.environ,'GH_PROMPT_DISABLED':'1'},creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,(p.stdout+p.stderr)[-2000:];return p.stdout
info=json.loads(call('api','repos/'+repo+'/releases/438762888'));assert info['draft']
names={a['name'] for a in info['assets']};missing=[p for p in [apk,meta] if p.name not in names]
if missing:call('release','upload',tag,*missing,'--repo',repo)
D.mkdir(exist_ok=False);call('release','download',tag,'--repo',repo,'--pattern',apk.name,'--dir',D);assert sha(D/apk.name)==j['apkSha256']
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID110_PRIVATE_DRAFT_BACKUP_DOWNLOADED_AND_HASH_VERIFIED','sourceCommit':j['sourceCommit'],'apkSha256':j['apkSha256'],'tag':tag,'draft':True,'published':False,'oldArtifactsReplaced':False,'downloadByteIdentical':True,'installed':False,'phoneOrdinaryFlowQualified':False}
(O/'remote-backup.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
