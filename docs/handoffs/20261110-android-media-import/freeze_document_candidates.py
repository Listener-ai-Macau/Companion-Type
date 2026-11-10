from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,subprocess,shutil,tomllib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';C=Path(__file__).parent
checks=json.loads((C/'document-ui-checks.json').read_text());assert checks['state']=='DOCUMENT_CONTEXT_AND_RELATED_READING_SOURCE_CHECKS_PASS'
assert json.loads((C/'document-reader-offline-final.json').read_text())['state']=='SHARED_DOCUMENT_READER_PRODUCTION_WORKER_OFFLINE_FIXTURES_PASS'
assert json.loads((C/'document-native-storage.json').read_text())['state']=='ANDROID_DOCUMENT_CONTEXT_STORAGE_BACKUP_AND_EXACT_PURGE_PASS'
assert not (C/'document-candidates-source.json').exists(),'Do not repeat a candidate freeze'
for root,old,new,files in [(S,'0.1.87','0.1.88',['package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json']),(A,'0.1.127','0.1.128',['apps/android/app/build.gradle'])]:
 for name in files:
  p=root/name;raw=p.read_bytes();before=raw
  if name.endswith('build.gradle'):assert (b'versionCode 127' in raw and b"versionName '0.1.127'" in raw) or (b'versionCode 128' in raw and b"versionName '0.1.128'" in raw);raw=raw.replace(b'versionCode 127',b'versionCode 128').replace(b"versionName '0.1.127'",b"versionName '0.1.128'")
  else:assert ('"'+old+'"').encode() in raw or ('"'+new+'"').encode() in raw,name;raw=raw.replace(('"'+old+'"').encode(),('"'+new+'"').encode())
  p.write_bytes(raw)
manifest=S/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';raw=manifest.read_bytes();m=json.loads(raw)
for name in m['lockedInputs']:m['lockedInputs'][name]=hashlib.sha256((S/name).read_bytes()).hexdigest()
text=json.dumps(m,ensure_ascii=False,indent=2)+'\n';manifest.write_bytes(text.replace('\n','\r\n').encode() if b'\r\n' in raw else text.encode())
subprocess.run(['node','tools/verify_third_party_notices.mjs'],cwd=S,check=True)
# Fold this meaningful document batch's related reading feedback into the same
# ordinary source check/build. Existing unaffected cases retain their baselines.
for root in [S,A]:
 p=root/'tools/qa/core_acceptance20261109/ui_source.cjs';raw=p.read_bytes();text=raw.decode('utf-8').replace('\r\n','\n');needle="'test_windows_note_images'" if root==S else "'test_recording_library_manager'";assert needle in text
 if "'test_document_context_panel'" not in text:text=text.replace(needle,needle+",'test_document_context_panel'",1)
 p.write_bytes(text.replace('\n','\r\n' if b'\r\n' in raw else '\n').encode())
for name in ['material.docx','material.docx.extraction.json','material.xlsx','material.pptx','chinese.pdf','protected.pdf','restricted.pdf','no-text.pdf','manifest.json']:
 for root in [S,A]:
  target=root/'tools/qa/core_acceptance20261109/fixtures/document-context'/name;target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(Path('E:/CodexData/Companion/.build-cache/document-context20261110/format-fixtures')/name,target)
path=R/'docs/product_backlog.json';before=path.read_bytes();d=json.loads(before);point=d['owner_module_execution']['frontendWindowsMobile20261102']['ownerCoreDeliveryPriority20261104']['ownerCoreAcceptanceCandidate20261109'];record=point['documentContext20261110'];record.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),status='DOCUMENT_CONTEXT_COMPLETE_NATIVE_UI_CANDIDATES_REMOTE_BUILD_PENDING',windowsVersion='0.1.88',androidVersion='0.1.128',checked='双端已接原件/分块读取/可取消后台提取/保存阅读/重试/另存原件/材料显式AI选择与来源回找；共享Office/PDF/离线中文/密码权限检查及受影响UI、Android原件与提取文字真实备份恢复/精确清除通过。Windows材料独立归属会议，音频清理与完整会议删除分开；完整Rust编译与对应测试及候选实际界面验收待本轮作业。',next='等待本批匹配Windows088/Android128原生构建；失败先修实际原因，成功后验证匹配候选原件/提取阅读/主动AI引用/来源回找及备份恢复和清除，再一并打包与远端保护。',appDelivered=False)
record['failuresRetained'].append('原WIP Windows实现沿图片把文档挂音频；代码复查识别音频单独清理会牵连文档的设计风险，未在Owner资料上执行。改独立受管会议材料归属根并补音频独立清理、无音频材料备份及旧窗口元数据防覆盖测试。')
temp=path.with_suffix('.document-freeze.tmp');temp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');assert path.read_bytes()==before;temp.replace(path)
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf-8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
publication={}
for label,root in [('windows',S),('android',A)]:
 dest=root/'docs/handoffs/android-media-import20261110'
 for name in ['freeze_document_candidates.py','document-reader-offline-final.json','document-ui-checks.json','check_document_ui.cjs','document-native-storage.json']:shutil.copyfile(C/name,dest/name)
 shutil.copyfile(path,root/'docs/product_backlog.json')
 status=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root,text=True).splitlines();paths=[]
 for line in status:
  file=line[3:].replace('\\','/')
  if file.startswith(('core-ui-output/','tools/qa/core_acceptance20261109/__pycache__/')):continue
  assert file.startswith(('apps/','packages/','vendor/','tools/','.github/','docs/handoffs/android-media-import20261110/')) or file in ['.gitattributes','package.json','package-lock.json','docs/product_backlog.json'],file
  paths.append(file)
 for file in paths:
  p=root/file
  if file.endswith(('.ts','.tsx','.rs','.py','.css','.json','.yml','.cjs','.gradle','.toml')) and not '/fixtures/' in file and not file.startswith('apps/windows/src-tauri/resources/licenses/'):
   old=subprocess.run(['git','show','HEAD:'+file],cwd=root,capture_output=True)
   if old.returncode==0:
    raw=p.read_bytes().replace(b'\r\n',b'\n');p.write_bytes(raw.replace(b'\n',b'\r\n') if b'\r\n' in old.stdout else raw)
 # EOL matching above preserves raw lock text; refresh its exact identity.
 if root==S:
  p=root/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';raw=p.read_bytes();m=json.loads(raw)
  for name in m['lockedInputs']:m['lockedInputs'][name]=hashlib.sha256((S/name).read_bytes()).hexdigest()
  text=json.dumps(m,ensure_ascii=False,indent=2)+'\n';p.write_bytes(text.replace('\n','\r\n').encode() if b'\r\n' in raw else text.encode())
 publication[label]=scope['ship'](root,paths,'[windows-build] Build complete local document-context candidate 0.1.88' if root==S else 'Build Android128 local document context and related meeting reading candidate')
out={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'DOCUMENT_CONTEXT_CANDIDATES_SOURCE_REMOTE_VERIFIED','windowsSource':publication['windows'],'androidSource':publication['android'],'backendSource':'f55f8e83b77c10ca34db442971a045eca1acfdf4','windowsVersion':'0.1.88','androidVersion':'0.1.128','localHeavyNativeBuild':False,'installed':False,'appDelivered':False,'saleQualified':False};(C/'document-candidates-source.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
