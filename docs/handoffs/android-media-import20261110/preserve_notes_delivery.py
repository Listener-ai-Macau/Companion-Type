from pathlib import Path
from datetime import datetime
import ast,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;A=R/'companion-core-android20261109';S=R/'companion-device-closure055';result=json.loads((C/'notes-delivered-result.json').read_text());assert result['checks']['closed']['ownerOriginalContentByteIdentical']
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
org=json.loads((C/'organization-delivered-result.json').read_text(encoding='utf-8'));win=json.loads((C/'windows-context-delivered-result.json').read_text(encoding='utf-8'))
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID125_WINDOWS087_DELIVERIES_AND126_FIRST_USE127_REPAIR_PROGRESS_REMOTE_PROTECTED','appSource':org['sourceCommit'],'windowsSource':win['sourceCommit'],'backendSource':org['backendSource'],'installerAsset':org['checks']['remote-candidate-backup']['assetId'],'windowsInstallerAsset':win['checks']['remote-candidate-backup']['assetId'],'publicBackupAsset':org['checks']['public-backup-remote']['assetId'],'binaryReadbacksIdentical':True,'draftOnly':True,'ownerPrivateDataUploaded':False}
if (C/'library127-source.json').exists():record['currentReadingRepairSource']=json.loads((C/'library127-source.json').read_text(encoding='utf-8'))['sourceCommit']
for name,root in [('android',A),('windows',S)]:
 dest=root/'docs/handoffs/android-media-import20261110';dest.mkdir(exist_ok=True)
 for file in C.rglob('*'):
  if file.is_file() and file.suffix in ['.py','.cjs','.json','.png','.md']:
   target=dest/file.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
 for file in ['product_backlog.json','development_log.md']:shutil.copyfile(R/'docs'/file,root/'docs'/file)
 record[name]=scope['ship'](root,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/android-media-import20261110'],'[skip ci] Preserve Android125 organization and Windows087 image-context delivery')
record['remoteReadbackVerified']=True;(C/'notes-publication.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
