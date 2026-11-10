from pathlib import Path
from datetime import datetime
import ast,json,os,subprocess,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';C=Path(__file__).parent
p=R/'docs/product_backlog.json';before=p.read_bytes();d=json.loads(before);point=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109'];record=point['documentContext20261110'];record.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),status='DOCUMENT_ORIGINAL_READING_AND_EXPLICIT_AI_SOURCE_NATIVE_UI_IMPLEMENTATION_WIP',checked='共享Office/PDF实际生产worker与离线中文字表、密码/权限/取消；Android原件/提取文字真实JVM存储、重试、实际备份恢复、保留已移除原件及精确清除；双端UI类型与前端构建通过。Windows新原生语法检查通过，完整Rust编译/受影响测试及原生打包/实际界面验收尚未完成。',next='完成本批受影响UI检查与原生Windows编译，再集中Android128/Windows088候选打包，验普通入口原件/提取阅读/主动AI引用/来源回找/备份恢复/移除清除；不把源码当交付。',appDelivered=False)
record['failuresRetained'].append('新增中文CID PDF在独立worker中无文字，查明PDF.js默认DOM binary factory依赖document.baseURI；显式useWorkerFetch并停用页面渲染后本地CMap读取通过。纯文字读取不随包分发可选Liberation TTF或图像WASM；系统字体模式及所有本地资源请求通过。')
record['evidence']=[str(C/name) for name in ['document-reader-offline-final.json','document-native-storage.json']]
body=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8');temp=p.with_suffix('.document-work.tmp');temp.write_bytes(body);assert p.read_bytes()==before;temp.replace(p)
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf-8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
published={}
for label,root in [('android',A),('windows',S)]:
 attr=root/'.gitattributes';text=attr.read_text(encoding='utf-8')
 for line in ['/packages/document-context/ThirdPartyNotices.txt text eol=lf -whitespace','/vendor/document-context/*LICENSE -text -whitespace']:
  if line not in text:text+='\n'+line+'\n'
 attr.write_text(text,encoding='utf-8',newline='\n')
 dest=root/'docs/handoffs/android-media-import20261110';dest.mkdir(exist_ok=True)
 for name in ['document-reader-offline-final.json','document-native-storage.json','preserve_document_work.py','integrate_document_android.py','integrate_document_mobile_ui.py','integrate_document_windows_backend.py','check_document_context.py']:
  shutil.copyfile(C/name,dest/name)
 shutil.copyfile(p,root/'docs/product_backlog.json')
 status=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root,text=True).splitlines();paths=[]
 for row in status:
  file=row[3:].replace('\\','/')
  if file.startswith(('core-ui-output/','tools/qa/core_acceptance20261109/__pycache__/')):continue
  assert file.startswith(('apps/','packages/','vendor/','tools/','.github/','docs/handoffs/android-media-import20261110/')) or file in ['.gitattributes','package.json','package-lock.json','docs/product_backlog.json'],file
  paths.append(file)
 # Match each preexisting text source's committed EOL. Never normalize exact
 # third-party text hashes or archive bytes.
 for file in paths:
  target=root/file
  if file.endswith(('.ts','.tsx','.rs','.py','.css','.json','.yml')) and not file.startswith('apps/windows/src-tauri/resources/licenses/'):
   old=subprocess.run(['git','show','HEAD:'+file],cwd=root,capture_output=True)
   if old.returncode==0 and target.is_file():
    raw=target.read_bytes().replace(b'\r\n',b'\n');target.write_bytes(raw.replace(b'\n',b'\r\n') if b'\r\n' in old.stdout else raw)
 published[label]=scope['ship'](root,paths,'[skip ci] Preserve coherent local document context native and UI work in progress')
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'DOCUMENT_CONTEXT_NATIVE_AND_UI_WIP_REMOTE_PROTECTED','commits':published,'appDelivered':False};(C/'document-work-publication.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
