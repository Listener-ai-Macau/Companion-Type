from pathlib import Path
from datetime import datetime
import os,json,hashlib,subprocess,shutil
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");S=R/"companion-device-closure055";A=R/"companion-core-android20261109";C=Path(__file__).parent
assert not (C/"incoming-candidate-sources.json").exists(),"Reuse this batch; do not allocate another version."
checks=json.loads((C/"incoming-complete-source-checks.json").read_text());assert checks["state"]=="SOURCE_CHECKS_PASSED" and len(checks["results"])==3
assert json.loads((C/"incoming-receipt-checks.json").read_text())["state"]=="PASSED"
assert json.loads((C/"incoming-rust-syntax-format.json").read_text())["exitCode"]==0
env={**os.environ,"GIT_TERMINAL_PROMPT":"0","GIT_SSH_COMMAND":"ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2"}
def git(root,*args):
 p=subprocess.run(["git","-c","maintenance.auto=false","-c","gc.auto=0",*args],cwd=root,env=env,capture_output=True,text=True,encoding="utf-8",timeout=120)
 if p.returncode:raise RuntimeError((p.stdout+p.stderr)[-3500:])
 return p.stdout.rstrip()
p=R/"docs/product_backlog.json";before=p.read_bytes();d=json.loads(before);shared=d["owner_module_execution"]["sharedWindowsIntegration20261110"];assert shared["reservedVersion"]=="0.1.99" and shared.get("pendingUnifiedVersion") is None
for file in ["package.json","package-lock.json","apps/windows/src-tauri/Cargo.toml","apps/windows/src-tauri/Cargo.lock","apps/windows/src-tauri/tauri.conf.json"]:
 path=S/file;b=path.read_bytes();assert b'"0.1.99"' in b or b'"0.1.100"' in b,file;path.write_bytes(b.replace(b'"0.1.99"',b'"0.1.100"'))
path=A/"apps/android/app/build.gradle";b=path.read_bytes();assert b"versionCode 136" in b and b"versionName '0.1.136'" in b;path.write_bytes(b.replace(b"versionCode 136",b"versionCode 137").replace(b"versionName '0.1.136'",b"versionName '0.1.137'"))
path=S/"apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json";b=path.read_bytes();m=json.loads(b)
for name in m["lockedInputs"]:m["lockedInputs"][name]=hashlib.sha256((S/name).read_bytes()).hexdigest()
out=json.dumps(m,ensure_ascii=False,indent=2)+"\n";path.write_bytes(out.replace("\n","\r\n").encode() if b"\r\n" in b else out.encode())
now=datetime.now().astimezone().isoformat(timespec="seconds");batch=d["owner_module_execution"]["frontendWindowsMobile20261102"]["ownerCoreDeliveryPriority20261104"]["ownerCoreAcceptanceCandidate20261109"];item=batch["documentContext20261110"]["systemInbound20261111"]
item.update(at=now,state="GROUPED_INCOMING100_ANDROID137_NATIVE_BUILD_NEXT",implemented="WINDOWS_AND_ANDROID_SOURCE_ONLY",windowsVersion="0.1.100",androidVersion="0.1.137",nativeCandidateBuilt=False,appDelivered=False,phoneQualified=False,windowsNativeQualified=False,saleQualified=False,next="Use the exact grouped100/137 sources for native candidate builds, then ordinary OS cold/warm receive, explicit attachment target, cancellation/bad/expired/retry, original integrity and backup/lifecycle. Keep099/136 as qualified installed baseline until exact new artifacts pass.")
item["sourceProgress"]=["Android SEND/SEND_MULTIPLE/content VIEW cold/warm adapter and Windows OpenWith/file-drop/same-library warm handoff reuse existing recording/document/image stores.","Pending receipts do not claim originals have been imported; opaque native source locations never enter frontend DTOs. Confirmation binds the current library and meeting; source expiry/missing files remain explicit.","Fixed native IDs recognize committed originals after a lost reply. Existing stored original verification is reused. Unconfirmed pre-index orphan files are conservatively retained and require library review/reopening, never overwritten or silently erased.","Both actual Windows/mobile TypeScript projects, all current Android sources against SDK35, pending queue concurrency/persistence/privacy/quota/corruption tests and current image/document original+idempotent/revision/reopen tests pass.","New Windows native modules parse/format; full native compile and added native import/receipt/source-preservation tests still pending CI. No native runtime or sale qualification is claimed."]
item["failuresRetained"]=["Initial Java8 test used Files.readString; fixture changed to supported readAllBytes, product unchanged.","First attachment test used a fake non-native meeting key; corrected fixture to the actual bounded hash:1:1 identity, product unchanged.","Native Windows source and OS launch/MSI registration still await the exact candidate; no engineering failure is hidden as a passed path."]
shared.update(at=now,reservedVersion="0.1.100",pendingUnifiedVersion="0.1.100",pendingUnifiedBranch="work/device-phone-closure055-20261106",pendingUnifiedReason="Complete ordinary external-file reception into existing core library, preserving099 installed and independent physical recorder.",next="documentContext20261110.systemInbound20261111")
raw=(json.dumps(d,ensure_ascii=False,indent=2)+"\n").replace("\n","\r\n").encode();tmp=p.with_suffix(".incoming.tmp");tmp.write_bytes(raw);assert p.read_bytes()==before;tmp.replace(p)
log=R/"docs/development_log.md";old=log.read_bytes();marker=b"<!-- document-context091-android129-delivered -->";assert old.count(marker)==1
entry=(now+" 集中外部文件接收源码批次（原CP27-03/import）：沿已安装099/136和53912fcc整包，完成Android系统SEND/SEND_MULTIPLE/content VIEW冷热启动接收、Windows打开方式/拖放/同资料库在用实例交接，先显示未导入的待接收清单，再明确资料库与所属会议；原件复制、解码、图片校验、文档保存继续使用既有存储。固定接收UUID保护丢回复重试，跨资料库/改目标拒绝，权限失效、坏文件、取消及未确认孤立文件明确；不改默认文件打开程序、不自动模型/上传。双端TS、当前全部Java真实SDK35 API、待接收并发/耐久/整批校验/配额/清单隐私和实际图片文档原件/丢回复重试/旧备注/修订/重开检查过；Windows新增原生模块仅语法格式已过，完整原生CI与普通系统入口待100/137匹配产物验证。本批保留Java8测试API及虚构录音key准备失败，均修夹具未改产品。源码先远端保护；下一集中构建和真流程后再打包，原099/136、Owner实物独立进程、模型/服务/正式售卖门不替代。\r\n\r\n").encode()
assert "集中外部文件接收源码批次".encode() not in old
new=old.replace(marker,marker+b"\r\n"+entry);tmp=log.with_suffix(".incoming.tmp");tmp.write_bytes(new);assert log.read_bytes()==old;tmp.replace(log)
protected={};evidence=["freeze_incoming_candidates.py","check_incoming_context_sources.py","check_incoming_receipts.py","format_incoming_rust.py","incoming-complete-source-checks.json","incoming-receipt-checks.json","incoming-receipt-attempt1-test-api.json","incoming-receipt-attempt2-fixture-key.json","incoming-rust-syntax-format.json","incoming-rust-syntax-format.log","incoming-source-checkpoint.json"]
for label,root,message in [("windows",S,"[windows-build] Build100 complete OS incoming file workflow"),("android",A,"Build Android137 complete external file reception workflow")]:
 dest=root/"docs/handoffs/android-media-import20261110";dest.mkdir(parents=True,exist_ok=True)
 for name in evidence:shutil.copyfile(C/name,dest/name)
 for file in [p,log]:shutil.copyfile(file,root/"docs"/file.name)
 paths=[]
 for row in git(root,"status","--porcelain","--untracked-files=all").splitlines():
  file=row[3:].replace("\\","/")
  if file.startswith(("core-ui-output/","tools/qa/core_acceptance20261109/__pycache__/")):continue
  assert file.startswith(("apps/","packages/","tools/","docs/handoffs/")) or file in ["package.json","package-lock.json","docs/product_backlog.json","docs/development_log.md"],file
  paths.append(file)
 git(root,"add","--",*paths);git(root,"-c","core.whitespace=blank-at-eol,space-before-tab,cr-at-eol,-blank-at-eof","diff","--cached","--check","--",*paths)
 git(root,"commit","--quiet","--only","-m",message,"--",*paths);head=git(root,"rev-parse","HEAD");branch=git(root,"branch","--show-current");git(root,"push","origin","HEAD:refs/heads/"+branch);assert git(root,"ls-remote","origin","refs/heads/"+branch).split()[0]==head;protected[label]=head;print(label,head,"REMOTE_VERIFIED",flush=True)
 target=C/("windows100" if label=="windows" else "android137");target.mkdir(exist_ok=True)
 (target/"source-freeze.json").write_text(json.dumps({"at":now,"sourceCommit":head,"branch":branch,"remoteVerified":True,"version":"0.1.100" if label=="windows" else "0.1.137","scope":"Grouped OS incoming reception; native compile/ordinary runtime still pending; keep099/136 qualified."},indent=2)+"\n")
record={"at":now,"state":"GROUPED_INCOMING_SOURCES_REMOTE_VERIFIED_BUILDS_PENDING","windowsSource":protected["windows"],"androidSource":protected["android"],"windowsVersion":"0.1.100","androidVersion":"0.1.137","backendSource":"f55f8e83b77c10ca34db442971a045eca1acfdf4","installedBaselineRetained":"099/136","nativeRuntimeQualified":False,"modelsRun":False,"saleQualified":False}
(C/"incoming-candidate-sources.json").write_text(json.dumps(record,indent=2)+"\n");print(json.dumps(record),flush=True)
