from pathlib import Path
import sys,subprocess,zipfile,hashlib,json,os,re
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");S=R/"companion-device-closure055";C=Path(__file__).parent;O=C/"windows100";W=Path("E:/CodexData/Companion/.build-cache/windows-note-context20261110/package100-132bd93f")
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,768*1024**2)
meta=json.loads((O/"build-attempt2-result.json").read_text());assert meta["sourceCommit"]=="132bd93ff8fad2d3978522a0aef721ba37b64ba6" and meta["state"]=="CI_BUILD_FAILED_RETAINED"
def sha(p):return hashlib.file_digest(Path(p).open("rb"),"sha256").hexdigest()
archive=W.parent/"100-attempt2-132bd93f.zip";assert sha(archive)==json.loads((O/"build-attempt2-artifact-readback.json").read_text())["sha256"]
native=W/"immutable-native";target=W/"target";native.mkdir(parents=True,exist_ok=True);(target/"release").mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive) as package:
 for row in meta["nativeFiles"]:
  data=package.read("windows-bin/"+row["path"]);assert hashlib.sha256(data).hexdigest()==row["sha256"]
  for directory in [native,target/"release"]:
   file=directory/row["path"]
   if file.exists():
    if directory==target/"release" and row["path"]=="companion-type.exe":
     current=file.read_bytes();patched=data.replace(b"__TAURI_BUNDLE_TYPE_VAR_UNK",b"__TAURI_BUNDLE_TYPE_VAR_MSI");assert current in [data,patched],"Unknown changed native pair"
     if current!=data:file.write_bytes(data)
    else:assert sha(file)==row["sha256"],"Never overwrite a changed/private native pair"
   else:file.write_bytes(data)
q=subprocess.run([sys.executable,str(S/"tools/check_type_build_target.py"),"--target-dir",str(target),"--project",str(S),"--artifact-dir",str(native)],cwd=S,capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
(O/"package-only-preflight.json").write_bytes(q.stdout);assert q.returncode==0,q.stderr.decode(errors="replace")[-600:]
env={**os.environ,"CARGO_TARGET_DIR":str(target)}
q=subprocess.run(["node",str(S/"node_modules/@tauri-apps/cli/tauri.js"),"bundle","-vv","--bundles","msi","--ci","--no-sign"],cwd=S/"apps/windows",env=env,capture_output=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
(O/"package-only-verbose.log").write_bytes(q.stdout+q.stderr)
record={"sourceCommit":meta["sourceCommit"],"sourceNativeRun":42932133336,"state":"DIAGNOSTIC_PACKAGE_SUCCEEDED_NOT_INSTALLED" if q.returncode==0 else "DIAGNOSTIC_PACKAGE_FAILED","exitCode":q.returncode,"nativeRecompiled":False,"nativeTestsReusedOnlyAsPassedInOriginalCI":True,"target":str(target),"limits":limits.query()}
(O/"package-only-result.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
text=(q.stdout+q.stderr).decode(errors="replace");print(text[-14000:]);print(json.dumps(record))
