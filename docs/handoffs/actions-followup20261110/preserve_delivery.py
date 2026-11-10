"""Protect the delivery, original task tree and retained failures on both existing branches."""
from pathlib import Path
from datetime import datetime
import ast,copy,json,os,shutil,subprocess
import psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';C=Path(__file__).parent
P=Path('E:/CodexData/Companion/.build-cache/actions-followup20261110')
load=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
failed=P/'android117-incomplete-source-r1'
dest=C/'android117/incomplete-source-r1';dest.mkdir(exist_ok=True)
for p in failed.rglob('*'):
 if p.is_file() and p.suffix in ['.json','.log'] and p.stat().st_size<1024*1024:shutil.copyfile(p,dest/p.name)
record=load(C/'batch.json')
record['failuresRetained'].append({'stage':'Android117 first source-only CI42725435616','finding':'The selective first commit omitted the modified MinutesDocument parent; the new integrated scope test rejected it before APK packaging.','fix':'Committed the missing parent, source9b6b8858d36feb170a9347a56f57b0e0ee5980d2; full source checks and packaging42725482756 passed.','evidence':'android117/incomplete-source-r1','failedSource':'b3f443378efb4896f40a65ee3e4b3829f4a25d59'})
record['endOfBatchHardwareObservation']={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'presentDisplayAdapters':['AMD Radeon 780M Graphics'],'external6800XTPresent':False,'availablePhysicalBytes':psutil.virtual_memory().available,'initialActualLowMemoryFailureRetained':True,'modelsStarted':0,'userApplicationsClosed':False}
(C/'batch.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
path=R/'docs/product_backlog.json';raw=path.read_bytes();d=json.loads(raw);quality=copy.deepcopy(d['quality_targets']);core=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']
next(row for row in core['ownerCompetitiveParity20261105']['coverage'] if row['id']=='actions')['savedActionsFollowup20261110']=record
core['ownerCoreAcceptanceCandidate20261109']['activeActionsFollowup20261110']=record
assert d['quality_targets']==quality and path.read_bytes()==raw
temp=path.with_suffix('.actions-publication.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');os.replace(temp,path)
with (R/'docs/development_log.md').open('a',encoding='utf8') as stream:stream.write('\n同批补齐失败证据：117首次source-only CI42725435616（b3f4433）因选择性提交漏带MinutesDocument父组件被新增完整组合测试拒绝，未进入APK打包；9b6b885完整源42725482756随后全过，不覆盖失败。收尾实际仅检测到780M、未见外置6800XT；不把RAM随后恢复误报为可继续既定GPU任务。两端源码、公开验收/失败、唯一任务树和完整日志一并保护到原远端分支，不重建或重装已通过的版本。\n')
for root in [S,A]:
 for p in [path,R/'docs/development_log.md']:shutil.copyfile(p,root/'docs'/p.name)
 destination=root/'docs/handoffs/actions-followup20261110';destination.mkdir(parents=True,exist_ok=True)
 for p in C.rglob('*'):
  if p.is_file() and p.suffix.lower() in ['.py','.cjs','.java','.json','.png','.log','.txt'] and p.stat().st_size<3*1024*1024:
   target=destination/p.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-preserver','exec'),scope)
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'saleQualified':False,'remoteReadbackVerified':True,'privateOwnerDataUploaded':False}
for name,root in [('windows',S),('android',A)]:
 result[name]=scope['ship'](root,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/actions-followup20261110'],'[skip ci] Preserve delivered Windows082 Android117 action workflow, original backlog and failures')
(C/'publication.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
