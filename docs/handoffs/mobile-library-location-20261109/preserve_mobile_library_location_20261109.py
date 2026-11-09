"""Preserve a mobile source candidate without installing or touching user data."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ast
import hashlib
import json
import os
import shutil
import subprocess
import time

R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-mobile-library-location'
D=S/'docs/handoffs/mobile-library-location-20261109'
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,d):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env=os.environ.copy()
env.update(GIT_TERMINAL_PROMPT='0',GIT_SSH_COMMAND='ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2')
helper=S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py'
tree=ast.parse(helper.read_text(encoding='utf8'))
ns={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),str(helper),'exec'),ns)
git,ship=ns['git'],ns['ship']
assert not git(S,'diff','--cached','--name-only')
files=['apps/mobile/src/App.tsx','apps/mobile/src/LibraryBackups.tsx','apps/mobile/src/LibraryLocation.tsx','apps/mobile/src/libraryStatus.ts','apps/mobile/src/libraryLocation.css','tools/verify_mobile_library_location_20261109.cjs']
proof=json.loads((C/'browser-verification.json').read_bytes())
assert len(proof['results'])==6 and all(r['result']=='PASS' for r in proof['results'])
record={'at':now(),'ownerQuote':'目前还没有显卡, 所以还有什么能做吗, 做手机相关?',
 'state':'MOBILE_LIBRARY_LOCATION_SOURCE_BUILT_CONTROLLED_UI_VERIFIED_PHONE_PENDING',
 'userOutcome':'恢复备份后在录音库持续看见当前资料位置，并能直接返回原有资料或进入备份管理；接收/升级时拒绝切库，普通单库页面保持简洁。',
 'originalTasks':['CP27-01','backup_restore','local_protection_and_trash'],
 'sourceBefore':git(S,'rev-parse','HEAD'),'sourceFiles':{p:sha(S/p) for p in files},
 'changes':['Actual mobile library page now shows restored-library provenance and guarded original-library return.',
  'Share native-status validation and labels with backup settings; malformed dates, duplicate IDs, missing active/original entries cannot create an actionable switch.',
  'Request generations discard late status snapshots; one pending action guard preserves token binding and cancel behavior.',
  'Use existing libraryActivate and existing confirmation; receive/OTA blocking preserved; no new native bridge, model, deletion or Bluetooth action.',
  'Restore feedback now points to the library return entry. Single original-library users do not get extra switch UI.'],
 'verification':proof,
 'build':{'command':'node npm-cli.js run build:mobile','typescriptPassed':True,'vitePassed':True,
  'assets':{str(p.relative_to(S/'apps/mobile/dist')).replace('\\','/'):sha(p) for p in (S/'apps/mobile/dist').rglob('*') if p.is_file()},
  'shellPreparationFailure':'Initial npm.ps1 could not load this host PowerShell built-in modules. It did not run a build; using the installed node/npm CLI directly completed the actual TypeScript/Vite build. Host shell settings unchanged.'},
 'currentPhone':'ADB device list empty on this turn; no phone foreground/background task or installation performed.',
 'candidateScope':'Web source and built mobile App verified with a controlled public bridge. No APK rebuilt or installed; no real native library switch, picker, export recipient or acoustic test.',
 'installedOrDeviceDataChanged':False,'phoneAccessed':False,'boardAccessed':False,'modelsRun':False,
 'modelWorkpointPreserved':'ownerCoreDeliveryPriority20261104/ownerNightGpuModelPriority20261104: paired real source audited; same-Qwen comparison awaits external6800XT. No model selection resumed.',
 'ownerAccepted':False,'wholeProductQualified':False,
 'next':'当前手机不在线。新库位置提示与返回入口已完成源码/构建和受控App验证；实际手机接入后先读取已装版本及共享现场，基于最新手机源合并本次Web改动，集中打包并验真实资料识别/切回、回收站保护/恢复、Word保存及本机分享收件，保留原资料与现有连接修复，不装旧069候选或降级。外部音频导入及纪要/回听阅读沿原竞品待办继续；模型仍待外置GPU。'}
dump(C/'result.json',record)
D.mkdir(parents=True,exist_ok=True)
for name in ['browser-verification.json','restored-light.png','restored-dark.png','result.json']:
 shutil.copyfile(C/name,D/name)
shutil.copyfile(__file__,D/Path(__file__).name)
attr=S/'.gitattributes';text=attr.read_text(encoding='utf8')
rule='docs/handoffs/mobile-library-location-20261109/** -text -whitespace'
if rule not in text:attr.write_text(text+'\n'+rule+'\n',encoding='utf8')
paths=files+['.gitattributes','docs/handoffs/mobile-library-location-20261109']
git(S,'add','--',*paths)
git(S,'-c','core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof','diff','--cached','--check','--',*paths)
git(S,'commit','--only','-m','Show restored mobile library and guarded return to original recordings','--',*paths)
code=git(S,'rev-parse','HEAD')
record['sourceCommit']=code
path=R/'docs/product_backlog.json'
for attempt in range(8):
 original=path.read_bytes();d=json.loads(original)
 quality=json.dumps(d['quality_targets'],sort_keys=True,ensure_ascii=False)
 frontend=d['owner_module_execution']['frontendWindowsMobile20261102']
 node=frontend['ownerDevicePhoneClosure055']
 key='ownerDaytimeLibraryLocation20261109'
 prior=node.get(key)
 record['previousPhoneNext']=prior.get('previousPhoneNext') if prior else node.get('next')
 node[key]=record
 node['next']=record['next']
 assert quality==json.dumps(d['quality_targets'],sort_keys=True,ensure_ascii=False)
 tmp=path.with_suffix('.mobile-location.tmp');dump(tmp,d)
 if path.read_bytes()!=original:tmp.unlink();continue
 try:os.replace(tmp,path)
 except PermissionError:
  tmp.unlink(missing_ok=True);time.sleep(min(.05*2**attempt,2));continue
 break
else:raise RuntimeError('Canonical backlog busy; source committed, retain remaining publication step')
log=R/'docs/development_log.md';before=log.read_bytes();marker='手机恢复资料可见位置与返回原库20261109'
if marker not in before.decode('utf8'):
 entry=('\n\n## '+record['at']+'｜'+marker+'\n\n'
  'Owner确认当前无显卡，询问推进手机事项。沿原P0资料保留/恢复工作，模型配对对照保持待外置卡；本轮ADB无设备，不访问手机/板或用户资料。'
  '手机录音库增加当前恢复资料提示及直接返回原有资料，复用原生libraryActivate/token/既有确认；接收与升级期间不切库。'
  '与备份设置共用资料状态/日期校验，重复ID、缺失原库或当前库、异常日期不给切换入口；旧响应不覆盖新位置，普通单库无额外卡片。'
  '实际mobile App源码TypeScript/Vite构建通过，受控公开桥浏览器验证六场景（取消、正确token返回、设置往返、接收禁用、坏快照/缺原库重读、旧请求晚返回、普通单库），360/393/430浅深色无横向溢出；实际截图已检查。'
  '最初npm.ps1因宿主PowerShell模块损坏没有执行构建，改用现有node/npm CLI后实际构建成功，未改宿主设置。'
  '源码提交'+code+'；Web候选并非APK或手机交付，无真实资料切换、保存分享接收端或Owner验收，未用受控桥代签；原36项及全机售卖门仍开。下一项：'+record['next']+'\n')
 with log.open('ab') as handle:handle.write(entry.encode('utf8'))
 assert log.read_bytes().startswith(before)
for p in [path,log]:shutil.copyfile(p,S/'docs'/p.name)
dump(D/'final-result.json',record)
head=ship(S,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/mobile-library-location-20261109/final-result.json'],'Record mobile library recovery candidate and remaining phone acceptance')
node=json.loads(path.read_bytes())['owner_module_execution']['frontendWindowsMobile20261102']['ownerDevicePhoneClosure055']
assert node[key]['sourceCommit']==code
print(json.dumps({'state':record['state'],'sourceCommit':code,'remoteHead':head,'remoteReadbackVerified':True,'workingTree':git(S,'status','--short'),'phoneTested':False,'modelsRun':False,'nextReadback':node['next']},ensure_ascii=False),flush=True)
