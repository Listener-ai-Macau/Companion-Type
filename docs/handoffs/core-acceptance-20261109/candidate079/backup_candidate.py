"""Back up the exact inspected MSI to a private draft and verify download."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,subprocess
C=Path('C:/Users/Billy/Desktop/Denzic/Companion/docs/handoffs/20261109-core-acceptance/candidate079')
D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/candidate079')
v=json.loads((C/'windows-verification.json').read_text(encoding='utf8'))
assert v['state']=='WINDOWS079_CI_SOURCE_MSI_PAYLOAD_LICENSES_AND_UPGRADE_VERIFIED'
tag='windows-0.1.79-'+v['sourceCommit'][:8]+'-candidate';repo='Listener-ai-Macau/Companion-Type'
msi=Path(v['msi'])
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(msi)==v['msiSha256']
def gh(*args,required=True):
 p=subprocess.run(['C:/Program Files/GitHub CLI/gh.exe',*map(str,args)],capture_output=True,text=True,encoding='utf8',errors='replace',env={**os.environ,'GH_PROMPT_DISABLED':'1'},creationflags=subprocess.CREATE_NO_WINDOW)
 if required:assert p.returncode==0,(p.stdout+p.stderr)[-2500:]
 return p
view=gh('release','view',tag,'--repo',repo,'--json','isDraft,url',required=False)
if view.returncode:
 assert 'not found' in (view.stdout+view.stderr).lower(),view.stderr
 notes=C/'draft-release-notes.txt'
 notes.write_text('Windows 0.1.79 集中会议候选备份。\n\n源 '+v['sourceCommit']+'；正常优化原生构建、包内EXE/DLL/许可证/同升级身份已核对。\n本批集中提供主导出入口、原音导出直达、转写前的明确下一步、会中问题的中性含义。\n真实公开会议原音/MP3/AI整理证据沿原任务；手机、板卡、模型、旧系统分享及整机售卖门仍按原待办。\n此草稿仅用于工程恢复，没有发布正式版本。\nMSI SHA-256 '+v['msiSha256']+'\n',encoding='utf8')
 gh('release','create',tag,msi,C/'windows-verification.json','--repo',repo,'--draft','--target',v['sourceCommit'],'--title','Windows 0.1.79 · 集中会议候选','--notes-file',notes)
 view=gh('release','view',tag,'--repo',repo,'--json','isDraft,url')
info=json.loads(view.stdout);assert info['isDraft'],'Never publish or replace an existing published release'
dest=D/'draft-download-readback';dest.mkdir(exist_ok=False)
gh('release','download',tag,'--repo',repo,'--pattern',msi.name,'--dir',dest)
assert sha(dest/msi.name)==v['msiSha256']
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'PRIVATE_DRAFT_MSI_DOWNLOADED_AND_HASH_VERIFIED','tag':tag,'url':info['url'],'sourceCommit':v['sourceCommit'],'msiSha256':v['msiSha256'],'draft':True,'published':False,'readbackByteIdentical':True,'saleQualified':False}
(C/'remote-candidate-backup.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
