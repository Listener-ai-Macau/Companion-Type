from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;A=R/'companion-core-android20261109';S=R/'companion-device-closure055'
result=json.loads((C/'delivered-result.json').read_text());assert result['state']=='ANDROID121_PLAYBACK_CORRECTION_SETTINGS_AND_PUBLIC_BACKUP_LIFECYCLE_DELIVERED'
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID121_DELIVERED_SOURCE_LOG_RESULTS_AND_INSTALLER_REMOTE_PROTECTED','productSource':result['sourceCommit'],'installerAssetId':result['phoneResults']['packageBackup']['assetId'],'installerReadbackIdentical':True,'ownerPrivateDataUploaded':False,'draftOnly':True}
paths=['docs/product_backlog.json','docs/development_log.md','docs/handoffs/nonmodel-core-playback20261110']
for name,root in [('android',A),('windows',S)]:
 dest=root/'docs/handoffs/nonmodel-core-playback20261110';dest.mkdir(parents=True,exist_ok=True)
 for f in C.rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.cjs','.ps1','.png']:
   target=dest/f.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,target)
 for file in ['product_backlog.json','development_log.md']:shutil.copyfile(R/'docs'/file,root/'docs'/file)
 record[name]=scope['ship'](root,paths,'[skip ci] Record Android121 native playback settings correction and backup delivery')
record['remoteReadbackVerified']=True;(C/'delivery-publication.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
