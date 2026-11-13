from pathlib import Path
from datetime import datetime
import subprocess,json,hashlib,re,os,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';E=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');B=R/'docs/handoffs/20261112-product-closure/windows120';H=R/'docs/handoffs/20261113-ui-foundation/reader-clarity';B.mkdir(exist_ok=False);H.mkdir(exist_ok=False)
git=['git','-c','maintenance.auto=false','-c','gc.auto=0','-c','pack.threads=1','-c','pack.windowMemory=64m','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol']
def head(root):return subprocess.check_output(git+['rev-parse','HEAD'],cwd=root,text=True).strip()
def commit(root,paths,message):
 for args in [['add','--',*paths],['diff','--cached','--check','--',*paths],['commit','--only','-m',message,'--',*paths]]:subprocess.run(git+args,cwd=root,check=True)
 ref=head(root);subprocess.run(git+['push','origin','HEAD'],cwd=root,env={**os.environ,'SHELL':'C:/Program Files/Git/usr/bin/sh.exe'},check=True);return ref
# Adapt the actual visible routes without weakening any persistence/source/export assertions.
for rel in ['windows_product_ui.cjs','windows_product_reopen_ui.cjs','windows_real_public_ui.cjs']:
 p=S/'tools/qa/core_acceptance20261109'/rel;s=p.read_text(encoding='utf8');s=s.replace("nav().getByRole('button',{name:'导出',exact:true})","page.locator('.ct-reader-export')").replace('name:/补充/','name:/笔记/').replace("name:'编辑清单',exact:true","name:'编辑纪要',exact:true")
 s=s.replace("await readiness.getByRole('heading',{name:'录音卡',exact:true}).waitFor();","await page.locator('#ct-device-recording-page').getByRole('heading',{name:'录音卡',exact:true}).waitFor();")
 p.write_bytes(s.replace('\n','\r\n').encode('utf8'))
windows=['packages/ui/src/CompanionDashboard.tsx','packages/ui/src/NotebookNavigation.tsx','packages/ui/src/MeetingWorkspaceNav.tsx','packages/ui/src/MeetingReadingFrame.tsx','packages/ui/src/MeetingReferenceWorkspace.tsx','packages/ui/src/meetingReferenceWorkspace.css','packages/ui/src/meetingReading.ts','packages/ui/src/notebookFoundation.css','tools/component_test_environment.mjs','tools/test_customer_reading.tsx','tools/test_calendar_export_review.tsx','tools/test_checklist_phone.tsx','tools/qa/core_acceptance20261109/meeting_workspace_harness.tsx','tools/qa/core_acceptance20261109/verify_workspace.cjs','tools/qa/core_acceptance20261109/inspect_reader_clarity.cjs','tools/qa/core_acceptance20261109/fixtures/public-recorded019f.json','tools/qa/core_acceptance20261109/windows_product_ui.cjs','tools/qa/core_acceptance20261109/windows_product_reopen_ui.cjs','tools/qa/core_acceptance20261109/windows_real_public_ui.cjs']
authoring=commit(S,windows,'Separate app navigation and recording reading; put replay and export in stable places')
p=A/'apps/android/app/build.gradle';raw=p.read_bytes();assert raw.count(b'versionCode 145')==1 and raw.count(b"versionName '0.1.145'")==1;p.write_bytes(raw.replace(b'versionCode 145',b'versionCode 146').replace(b"versionName '0.1.145'",b"versionName '0.1.146'"))
android=commit(A,['apps/mobile/src/App.tsx','apps/mobile/src/RecordingContentNavigation.tsx','apps/mobile/src/notebookMobile.css','packages/ui/src/MeetingReadingFrame.tsx','packages/ui/src/MeetingReferenceWorkspace.tsx','packages/ui/src/meetingReferenceWorkspace.css','packages/ui/src/meetingReading.ts','apps/android/app/build.gradle'],'Freeze146 around title replay reading and deliberate secondary tools')
assert not subprocess.check_output(git+['status','--porcelain'],cwd=E,text=True).strip(),'Fixed source busy or dirty; do not replace it'
if subprocess.run(git+['cat-file','-e',authoring+'^{commit}'],cwd=E,capture_output=True).returncode:subprocess.run(git+['fetch','origin',authoring],cwd=E,check=True)
subprocess.run(git+['switch','-c','work/reader120-frozen-20261113',authoring],cwd=E,check=True)
# Keep the shared authoring checkout on its independently owned119 identity.
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
for rel,count in [('package.json',1),('package-lock.json',2),('apps/windows/src-tauri/tauri.conf.json',1)]:
 p=E/rel;raw=p.read_bytes();assert raw.count(b'"version": "0.1.119"')==count;p.write_bytes(raw.replace(b'"version": "0.1.119"',b'"version": "0.1.120"'))
p=E/'apps/windows/src-tauri/Cargo.toml';raw=p.read_bytes();assert raw.count(b'version = "0.1.119"')==1;p.write_bytes(raw.replace(b'version = "0.1.119"',b'version = "0.1.120"'))
p=E/'apps/windows/src-tauri/Cargo.lock';raw,n=re.subn(rb'(name = "companion-type"\r?\nversion = ")0\.1\.119(")',rb'\g<1>0.1.120\2',p.read_bytes());assert n==1;p.write_bytes(raw)
p=E/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';raw=p.read_bytes();d=json.loads(raw)
for rel,old in d['lockedInputs'].items():
 new=hashlib.sha256((E/rel).read_bytes()).hexdigest()
 if new!=old:assert raw.count(old.encode())==1;raw=raw.replace(old.encode(),new.encode())
p.write_bytes(raw);frozen=commit(E,versions,'Freeze120 normal release for one reader clarity delivery without changing shared119 authoring identity')
record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='READER120146_SOURCE_FROZEN_NORMAL_BUILD_PENDING',version='0.1.120',sourceCommit=frozen,authoringSourceCommit=authoring,sourceRoot=str(E),frozenSourceRoot=str(E),branch='work/reader120-frozen-20261113',androidVersion='0.1.146',androidSourceCommit=android,ownerExperienceAccepted=False,uncommittedConcurrentPointerFilesIncluded=False,previousInstalledWindows='0.1.118',previousInstalledAndroid='0.1.145',physicalOrModelsRetested=False)
for p in [B/'frozen-source.json',H/'source-checkpoints.json']:p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(record,ensure_ascii=False),flush=True)
