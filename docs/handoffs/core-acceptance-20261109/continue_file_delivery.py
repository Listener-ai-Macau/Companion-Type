"""Freeze one Windows file-delivery improvement with the existing candidate tools."""
from pathlib import Path
from datetime import datetime
import ast,copy,hashlib,json,os,shutil,subprocess,tomllib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=R/'docs/handoffs/20261109-core-acceptance';O=C/'candidate081';O.mkdir(exist_ok=True)
names=['package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json']
old_rust=tomllib.loads((S/names[3]).read_text(encoding='utf8'));old_npm=json.loads((S/names[1]).read_text(encoding='utf8'))
for name in names:
 p=S/name;raw=p.read_bytes();assert b'"0.1.80"' in raw,name;p.write_bytes(raw.replace(b'"0.1.80"',b'"0.1.81"'))
new_rust=tomllib.loads((S/names[3]).read_text(encoding='utf8'));new_npm=json.loads((S/names[1]).read_text(encoding='utf8'))
for lock in [old_rust,new_rust]:
 for row in lock['package']:
  if row['name']=='companion-type':row['version']='PRODUCT_ONLY'
assert old_rust==new_rust
for lock in [old_npm,new_npm]:lock['version']='PRODUCT_ONLY';lock['packages']['']['version']='PRODUCT_ONLY'
assert old_npm==new_npm
lic_path=S/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';lic=json.loads(lic_path.read_text(encoding='utf8'))
for name in lic['lockedInputs']:lic['lockedInputs'][name]=hashlib.sha256((S/name).read_bytes()).hexdigest()
lic_path.write_text(json.dumps(lic,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
spec=C/'whole-delivery-spec.json';data=json.loads(spec.read_text(encoding='utf8'));data['browserAttachmentReceipt']=True;spec.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
shutil.copyfile(spec,S/'docs/handoffs/core-acceptance-20261109/whole-delivery-spec.json')
at=datetime.now().astimezone().isoformat(timespec='seconds')
record={'at':at,'state':'WINDOWS_FILE_DELIVERY_BATCH_IMPLEMENTED_BUILD_AND_RECEIPT_RUNNING','version':'0.1.81','purpose':'纪要、所选正文和原音/MP3可从主入口复制为完整文件并在接收应用粘贴为附件。','baselineProductSource':'f339e22a45e7cb79704e0dcea707dcb3f39fecb4','baselineFailure':'WinRT068/069请求改写与自定义Shell site均未修复系统面板；文件CF_HDROP及真实Shell收件已通过。','newEvidence':'真实有头Edge从系统文件剪贴板触发可信paste，File经标准FormData到本机收件器；收件器不给原文件路径/字节，核对实际收到的文件。','systemPickerRepaired':False,'newAsrOrAiCalls':False,'phoneOnline':False,'boardAccessed':False,'installed':False,'saleQualified':False}
bp=R/'docs/product_backlog.json';original=bp.read_bytes();backlog=json.loads(original);quality=copy.deepcopy(backlog['quality_targets']);b=backlog['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109'];b['activeFileDelivery']=record;b['lastOwnerQuote']='你不要老是说还有什么东西没做，你说什么东西没做难道是因为你不能做吗？直接把它做了就好了。';assert backlog['quality_targets']==quality and bp.read_bytes()==original
bp.write_text(json.dumps(backlog,ensure_ascii=False,indent=2)+'\n',encoding='utf8');shutil.copyfile(bp,S/'docs/product_backlog.json')
paths=names+['apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json','packages/ui/src/ContentExportPanel.tsx','packages/ui/src/CompanionDashboard.tsx','tools/test_content_export_panel051.tsx','tools/qa/core_acceptance20261109/windows_browser_paste.cjs','tools/qa/core_acceptance20261109/windows_file_receiver.py','tools/qa/core_acceptance20261109/run_ci.py','tools/qa/core_acceptance20261109/ui_source.cjs','docs/handoffs/core-acceptance-20261109/whole-delivery-spec.json','docs/product_backlog.json']
source=(S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8');tree=ast.parse(source)
scope={'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<existing-publisher>','exec'),scope)
commit=scope['ship'](S,paths,'[windows-build] [core-ui] [core-whole-delivery] Deliver desktop meeting documents and audio as directly copyable attachments')
record.update(sourceCommit=commit,sourceRemoteReadbackVerified=True);(O/'source-freeze.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
