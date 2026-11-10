from pathlib import Path
from datetime import datetime
import json,hashlib,subprocess,os,shutil
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");S=R/"companion-device-closure055";A=R/"companion-core-android20261109";C=Path(__file__).parent
assert not (C/"manual-followup-candidate-sources.json").exists(),"Reuse frozen source receipt; do not allocate another version."
assert json.loads((C/"manual-complete-source-checks.json").read_text())["state"]=="WINDOWS_AND_ANDROID_TYPES_AND_ALL_APP_ANDROID35_API_COMPILED"
assert json.loads((C/"manual-followup-ui-source-checks.json").read_text())["state"]=="MANUAL_FOLLOWUP_COMPONENTS_AND_AFFECTED_NOTES_PASSED"
assert json.loads((C/"manual-current-store-checks.json").read_text())["state"]=="CURRENT_PLATFORM_COMPILED_NOTE_STORE_SOURCE_EXPORTS_PASSED"
env={**os.environ,"GIT_TERMINAL_PROMPT":"0","GIT_SSH_COMMAND":"ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2"}
def git(root,*args):
 p=subprocess.run(["git","-c","maintenance.auto=false","-c","gc.auto=0",*args],cwd=root,env=env,capture_output=True,text=True,encoding="utf-8")
 if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-3000:])
 return p.stdout.rstrip()
p=R/"docs/product_backlog.json";before=p.read_bytes();data=json.loads(before);shared=data["owner_module_execution"]["sharedWindowsIntegration20261110"];assert shared.get("pendingUnifiedVersion") in [None,"0.1.99"] and shared["reservedVersion"]=="0.1.98"
for root,old,new,files in [(S,"0.1.98","0.1.99",["package.json","package-lock.json","apps/windows/src-tauri/Cargo.toml","apps/windows/src-tauri/Cargo.lock","apps/windows/src-tauri/tauri.conf.json"]),(A,"0.1.134","0.1.135",["apps/android/app/build.gradle"])]:
 for file in files:
  path=root/file;b=path.read_bytes()
  if file.endswith("build.gradle"):
   assert (b"versionCode 134" in b and b"versionName '0.1.134'" in b) or (b"versionCode 135" in b and b"versionName '0.1.135'" in b)
   b=b.replace(b"versionCode 134",b"versionCode 135").replace(b"versionName '0.1.134'",b"versionName '0.1.135'")
  else:
   assert ('"'+old+'"').encode() in b or ('"'+new+'"').encode() in b,file
   b=b.replace(('"'+old+'"').encode(),('"'+new+'"').encode())
  path.write_bytes(b)
for root in [S,A]:
 path=root/"tools/qa/core_acceptance20261109/ui_source.cjs";b=path.read_bytes();needle=b"'test_document_context_panel'";assert b.count(needle)==1
 if b"'test_manual_followup_notes'" not in b:b=b.replace(needle,needle+b",'test_manual_followup_notes','test_manual_followup_documents'");path.write_bytes(b)
# The inventory binds bytes of dependency locks, not a new dependency set.
path=S/"apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json";b=path.read_bytes();m=json.loads(b)
for file in m["lockedInputs"]:m["lockedInputs"][file]=hashlib.sha256((S/file).read_bytes()).hexdigest()
body=json.dumps(m,ensure_ascii=False,indent=2)+"\n";path.write_bytes(body.replace("\n","\r\n").encode() if b"\r\n" in b else body.encode())
now=datetime.now().astimezone().isoformat(timespec="seconds")
point=data["owner_module_execution"]["frontendWindowsMobile20261102"]["ownerCoreDeliveryPriority20261104"]["ownerCoreAcceptanceCandidate20261109"];node=point["documentContext20261110"]["manualFollowupSources20261111"]
node.update(at=now,state="SOURCE_COMPLETE_NATIVE_CANDIDATES_BUILD_NEXT",windowsVersion="0.1.99",androidVersion="0.1.135",implementedSource=["Human note/follow-up kind and literal - [ ] checklist, reusing existing revision/ownership stores.","Literal document paragraph/table-row and full-current-transcript identity capture, saving original/extraction hashes and location without file paths or ephemeral tokens.","Append evidence without erasing existing manual draft; explicit reference removal and follow-up editing; checkbox changes only one literal marker.","Stored-reference current-source validation; missing/changed source retains saved excerpt and gives an explicit error; no silent source matching.","Selected note text/JSON/portable image export and library search include human evidence, distinct from original transcript/generated decisions; metadata privacy deletion covers references."],notImplementedYet=[],checked=["Actual Windows/mobile TypeScript projects passed.","All current Android application Java sources compiled together against actual Android35 API, resolving obsolete retained derivation API classes in the earlier partial preparer.","Affected real React composer/table/checklist/cancel/retry/edit/source-change checks passed.","Current platform-compiled Android note/document files passed actual public XLSX identity, literal values, counterfeit/revision/foreign-record rejection, image+context preservation, legacy edit, source removal/new-root reopen, text/search/HTML+JSON bundle checks; directory sync/raster checks explicitly mocked."],sourceChecks=[str(C/f) for f in ["manual-complete-source-checks.json","manual-followup-ui-source-checks.json","manual-current-store-checks.json"]],failuresRetained=["Initial host JSON helper used APIs absent Android35; replaced with supported keys iterator/flat comparison and explicit string types before any candidate.","Partial app API preparer used older retained AudioDerivation classes; compiling all current app sources succeeds.","Source-check wrapper initially supplied bytes incorrectly and later called nonexistent snapshot(); no child failure in final source check, raw successful output/logs retained; runner now uses query()."],appDelivered=False,nativeWindowsQualified=False,phoneQualified=False,ordinaryBackupRestoreQualified=False,next="Use one grouped099/135 native candidate build. Fix actual failures, then verify ordinary save/reopen/checklist/source navigation, affected export, backup/restore, source removal and scoped lifecycle before delivery; retain098/134 installed qualification until exact new artifacts pass.",modelsRun=False,saleQualified=False)
shared.update(at=now,pendingUnifiedVersion="0.1.99",pendingUnifiedBranch="work/device-phone-closure055-20261106",pendingUnifiedReason="One coherent human follow-up and literal evidence workflow; preserve installed098 functions and independent physical app.",next="documentContext20261110.manualFollowupSources20261111")
raw=(json.dumps(data,ensure_ascii=False,indent=2)+"\n").replace("\n","\r\n").encode();tmp=p.with_suffix(".manual-followup.tmp");tmp.write_bytes(raw);assert p.read_bytes()==before;tmp.replace(p)
log=R/"docs/development_log.md";beforeLog=log.read_bytes();marker=b"<!-- document-context091-android129-delivered -->";assert beforeLog.count(marker)==1
line=(now+"集中人工跟进与原文依据源码批次：复用已交付098/134备注修订、文档原件/提取身份与原文入口，完成双端人工跟进类型、字面清单勾选、追加文档段落/表格原行/原始转写引用、保存时SHA与位置、来源变动/移除提示、保留旧引文、编辑与图片上下文、搜索及文字/JSON/图文导出；不把人工内容写成会议决定。双端类型、真实SDK35全部当前App Java、受影响React保存失败/取消/勾选/字面FALSE与0/来源变动检查、当前Java真实公开原件存储/导出已过。保留早期host JSON平台API、旧派生类准备与收据包装器失败，修来源后未重跑无关检查。099/135本批源码将一次集中构建；原安装098/134、整包e71502a9和独立物理录音端保留，完整原生普通流程/备份恢复及清理待本批产物，模型/服务/售卖门未关闭。下一只沿当前人工跟进来源事项完成实际交付，不再小标签单独重包。\r\n\r\n").encode()
after=beforeLog if "集中人工跟进与原文依据源码批次".encode() in beforeLog else beforeLog.replace(marker,marker+b"\r\n"+line);tmp=log.with_suffix(".manual-followup.tmp");tmp.write_bytes(after);assert log.read_bytes()==beforeLog;tmp.replace(log)
protected={}
for label,root,message in [("windows",S,"[windows-build] Build099 complete manual follow-up and literal evidence workflow"),("android",A,"Build Android135 complete human follow-up and source-reference workflow")]:
 dest=root/"docs/handoffs/android-media-import20261110"
 for name in ["freeze_manual_followup_candidates.py","manual-complete-source-checks.json","manual-followup-ui-source-checks.json","manual-current-store-checks.json","manual-note-context-native-source-checks.json","manual-note-context-app-source-checks.json","manual-note-context-initial-host-json-api.java","check_manual_context_sources.py","check_manual_context_ui.cjs","run_manual_context_ui_checks.py","check_manual_native_store.py"]:shutil.copyfile(C/name,dest/name)
 for file in [p,log]:shutil.copyfile(file,root/"docs"/file.name)
 paths=[]
 for row in git(root,"status","--porcelain","--untracked-files=all").splitlines():
  file=row[3:].replace("\\","/")
  if file.startswith(("core-ui-output/","tools/qa/core_acceptance20261109/__pycache__/")):continue
  assert file.startswith(("apps/","packages/","tools/","docs/handoffs/android-media-import20261110/")) or file in ["package.json","package-lock.json","docs/product_backlog.json","docs/development_log.md"],file
  paths.append(file)
 git(root,"add","--",*paths)
 git(root,"-c","core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof","diff","--cached","--check","--",*paths)
 git(root,"commit","--quiet","--only","-m",message,"--",*paths)
 head=git(root,"rev-parse","HEAD");branch=git(root,"branch","--show-current");git(root,"push","origin","HEAD:refs/heads/"+branch);assert git(root,"ls-remote","origin","refs/heads/"+branch).split()[0]==head;protected[label]=head
receipt={"at":now,"state":"GROUPED_MANUAL_FOLLOWUP_SOURCES_PUSHED_REMOTE_VERIFIED_BUILDS_PENDING","windowsSource":protected["windows"],"androidSource":protected["android"],"windowsVersion":"0.1.99","androidVersion":"0.1.135","backendSource":"f55f8e83b77c10ca34db442971a045eca1acfdf4","installedBaselineRetained":"098/134","modelsRun":False,"saleQualified":False}
(C/"manual-followup-candidate-sources.json").write_text(json.dumps(receipt,indent=2)+"\n");print(json.dumps(receipt),flush=True)
