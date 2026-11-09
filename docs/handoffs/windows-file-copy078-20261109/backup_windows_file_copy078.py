"""Back up the inspected candidate in a private draft and download-readback it."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import subprocess,json,hashlib,shutil
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-windows-file-copy078')
G='C:/Program Files/GitHub CLI/gh.exe';repo='Listener-ai-Macau/Companion-Type';tag='windows-0.1.78-bb1550c4-candidate'
v=json.loads((C/'windows-verification.json').read_text(encoding='utf8'))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def gh(*args):
 p=subprocess.run([G,*args],capture_output=True,text=True,encoding='utf8',errors='replace')
 assert p.returncode==0,(p.stdout+p.stderr)[-2000:]
 return p.stdout.strip()
assert json.loads(gh('api','repos/'+repo))['private']
msi=C/'Companion-Windows-0.1.78-candidate.msi';shutil.copy2(Path(v['msi']),msi);assert sha(msi)==v['msiSha256']
notes=C/'candidate-backup-notes.txt'
notes.write_text('Windows 0.1.78 工程候选备份。\n\n对应源码 '+v['sourceCommit']+'，共享核心 6f30ab5888e3f603084d71359f3099ab5b8f66fc。\n完整文件复制入口：所选内容文件、原音/MP3；不自动发送。\nMSI 已独立核对包内 EXE/DLL/许可证与同升级身份，原有245个资料文件升级前后哈希一致。\n普通第三方粘贴收件与旧 WinRT 系统分享面板仍未通过，整机售卖资格未完成。\n此草稿用于工程恢复，未发布正式版本。\nMSI SHA-256 '+v['msiSha256']+'\n',encoding='utf8')
matches=[r for r in json.loads(gh('api','repos/'+repo+'/releases?per_page=100')) if r['tag_name']==tag]
if not matches:
 gh('release','create',tag,str(msi),str(C/'windows-verification.json'),'--repo',repo,'--draft','--target',v['sourceCommit'],'--title','Windows 0.1.78 · 工程候选备份','--notes-file',str(notes))
 matches=[r for r in json.loads(gh('api','repos/'+repo+'/releases?per_page=100')) if r['tag_name']==tag]
assert len(matches)==1
r=matches[0];assert r['draft'] and r['target_commitish']==v['sourceCommit']
asset=next(a for a in r['assets'] if a['name']==msi.name)
if asset.get('digest'):assert asset['digest']=='sha256:'+v['msiSha256']
dest=C/'remote-draft-readback';dest.mkdir(exist_ok=False)
gh('release','download',tag,'--repo',repo,'--pattern',msi.name,'--dir',str(dest))
assert sha(dest/msi.name)==v['msiSha256']
record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'state':'PRIVATE_DRAFT_CANDIDATE_UPLOAD_AND_DOWNLOAD_SHA256_VERIFIED','repository':repo,'privateRepositoryVerified':True,'draft':True,'published':False,'tag':tag,'sourceCommit':v['sourceCommit'],'url':r['html_url'],'releaseId':r['id'],'assetId':asset['id'],'assetName':asset['name'],'msiSha256':v['msiSha256'],'downloadReadbackMatches':True,'saleQualified':False}
(C/'remote-candidate-backup.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
