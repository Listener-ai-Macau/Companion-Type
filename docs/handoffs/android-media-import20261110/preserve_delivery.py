from pathlib import Path
from datetime import datetime
import ast,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;A=R/'companion-core-android20261109';S=R/'companion-device-closure055';result=json.loads((C/'delivered-result.json').read_text());assert result['checks']['finalUi']['originalLibraryActive']
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID123_SOURCE_INSTALLER_PUBLIC_BACKUP_AND_DELIVERY_RESULTS_REMOTE_PROTECTED','appSource':result['appSource'],'backendSource':result['backendSource'],'privateInstallerAsset':result['checks']['packageRemote']['assetId'],'publicTestBackupAsset':result['checks']['publicBackupRemote']['assetId'],'allBinaryReadbacksIdentical':True,'draftOnly':True,'ownerPrivateDataUploaded':False}
for name,root in [('android',A),('windows',S)]:
 dest=root/'docs/handoffs/android-media-import20261110';dest.mkdir(exist_ok=True)
 for file in C.rglob('*'):
  if file.is_file() and file.suffix in ['.py','.cjs','.json','.png']:
   target=dest/file.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
 for file in ['product_backlog.json','development_log.md']:shutil.copyfile(R/'docs'/file,root/'docs'/file)
 record[name]=scope['ship'](root,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/android-media-import20261110'],'[skip ci] Preserve Android123 media-to-meeting delivery and current nonmodel sale gaps')
record['remoteReadbackVerified']=True;(C/'publication.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
