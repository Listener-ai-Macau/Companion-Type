"""Rebundle a proven normal-release pair after a pinned MSI-only recipe repair."""
from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,subprocess,hashlib,zipfile,shutil,traceback
S=Path(__file__).resolve().parents[1];N=S/"apps/windows/src-tauri";C=S/"ci-output";C.mkdir(exist_ok=False)
spec_path=(S/os.environ["COMPANION_REUSE_NATIVE_SPEC"]).resolve();assert spec_path.is_relative_to(S)
spec=json.loads(spec_path.read_bytes());assert spec["version"]=="0.1.100"
repo="Listener-ai-Macau/Companion-Type"
def sha(path):
 with Path(path).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def capture(args):
 p=subprocess.run(list(map(str,args)),cwd=S,capture_output=True);assert p.returncode==0,p.stderr.decode(errors="replace")[-1000:];return p.stdout
def run(name,args,cwd=S):
 print("Starting "+name,flush=True);p=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True);(C/(name+".log")).write_bytes(p.stdout+p.stderr);assert p.returncode==0,name+" failed; retained log";print("Passed "+name,flush=True)
record={"state":"VERIFYING_PINNED_NATIVE_REUSE","sourceCommit":spec["nativeSourceCommit"],"packagingSourceCommit":capture(["git","rev-parse","HEAD"]).decode().strip(),"version":spec["version"],"modelsRun":False,"installed":False,"saleQualified":False}
def save():(C/"result.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
save()
try:
 upstream=json.loads(capture(["gh","run","view",str(spec["nativeBuildRun"]),"--repo",repo,"--json","status,conclusion,headSha"]))
 assert upstream=={"status":"completed","conclusion":"failure","headSha":spec["nativeSourceCommit"]}
 artifacts=json.loads(capture(["gh","api",f"repos/{repo}/actions/runs/{spec['nativeBuildRun']}/artifacts"]))["artifacts"]
 artifact=next(row for row in artifacts if row["id"]==spec["nativeArtifactId"])
 assert artifact["name"]=="companion-windows-candidate-"+spec["nativeSourceCommit"] and artifact["size_in_bytes"]==spec["nativeArtifactBytes"] and artifact["digest"]=="sha256:"+spec["nativeArtifactSha256"]
 archive=Path(os.environ["RUNNER_TEMP"])/"companion-native-reuse100.zip"
 with archive.open("wb") as out:
  process=subprocess.run(["gh","api",f"repos/{repo}/actions/artifacts/{artifact['id']}/zip"],cwd=S,stdout=out,stderr=subprocess.PIPE)
  assert process.returncode==0,"Native artifact transport failed"
 assert archive.stat().st_size==spec["nativeArtifactBytes"] and sha(archive)==spec["nativeArtifactSha256"]
 upstream_dir=Path(os.environ["RUNNER_TEMP"])/"companion-native-reuse100";upstream_dir.mkdir(exist_ok=False)
 with zipfile.ZipFile(archive) as package:
  names=package.namelist();assert len(names)==len(set(names)) and sum(v.file_size for v in package.infolist())<1024**3
  for name in names:assert not Path(name).is_absolute() and ":" not in name and "\\" not in name and ".." not in Path(name).parts and (upstream_dir/name).resolve().is_relative_to(upstream_dir.resolve())
  package.extractall(upstream_dir)
 native=json.loads((upstream_dir/"result.json").read_bytes())
 assert native["sourceCommit"]==spec["nativeSourceCommit"] and native["version"]==spec["version"] and native["state"]=="CI_BUILD_FAILED_RETAINED" and native["error"]=="RuntimeError('msi-bundle failed: 1; see retained log')" and native["modelsRun"] is False
 release_log=(upstream_dir/"cargo-release.log").read_text(encoding="utf-8",errors="replace")
 assert "Finished" in release_log and "release" in release_log and "optimized" in release_log
 for scope in native["affectedTestBinary"]["filters"]:
  assert "test result: ok." in (upstream_dir/(scope.replace("::","-")+"-context-regression.log")).read_text(encoding="utf-8",errors="replace"),scope
 assert "test result: ok." in (upstream_dir/"audio-edit-native-library-isolated.log").read_text(encoding="utf-8")
 change=spec["packagingChange"];assert change["path"]=="apps/windows/src-tauri/windows-open-with.wxs"
 matched=[];eol=[]
 for row in native["sourceFiles"]:
  path=S/row["path"];assert path.resolve().is_relative_to(S)
  raw=path.read_bytes();variants=[raw,raw.replace(b"\r\n",b"\n"),raw.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n")];hashes=[hashlib.sha256(v).hexdigest() for v in variants]
  if row["path"]==change["path"]:assert row["sha256"]==change["oldSha256"] and change["newSha256"] in hashes
  else:
   assert row["sha256"] in hashes,"Non-packaging source changed: "+row["path"];matched.append(row["path"])
   if row["sha256"]!=hashes[0]:eol.append(row["path"])
 record.update(nativeSourceCommit=spec["nativeSourceCommit"],artifactSourceCommit=record["packagingSourceCommit"],nativeBuildRun=spec["nativeBuildRun"],nativeArtifactReadback={"id":artifact["id"],"sha256":sha(archive),"bytes":archive.stat().st_size},nativeSourceFilesMatched=len(matched),checkoutEolOnly=eol,packagingOnlyInputChanges=[change],upstreamRunConclusion="failure: MSI only; original native compilation/tests/normal release passed",nativeRecompiled=False,nativeTestsRerun=False,normalReleaseOptimization=True,ordinaryRecipientTested=False)
 for key in ["platformCommit","lockedInputs","rustc","node","sourceFiles","webAssets","nativeFiles","affectedTestBinary"]:record[key]=native[key]
 shutil.copyfile(upstream_dir/"result.json",C/"upstream-native-result.json")
 for file in upstream_dir.glob("*regression.log"):shutil.copyfile(file,C/("upstream-"+file.name))
 for name in ["audio-edit-native-library-isolated.log","cargo-release.log","msi-bundle.log"]:shutil.copyfile(upstream_dir/name,C/("upstream-"+name))
 pair=C/"windows-bin";pair.mkdir();T=Path(os.environ["RUNNER_TEMP"])/"companion-package-only100";(T/"release").mkdir(parents=True,exist_ok=False)
 for row in native["nativeFiles"]:
  source=upstream_dir/"windows-bin"/row["path"];assert sha(source)==row["sha256"];shutil.copyfile(source,pair/row["path"]);shutil.copyfile(source,T/"release"/row["path"])
 env={**os.environ,"CARGO_TARGET_DIR":str(T),"RUSTUP_TOOLCHAIN":"1.95.0","PYTHONIOENCODING":"utf-8","PYTHONUTF8":"1"}
 record["state"]="REBUILDING_IDENTICAL_WEB_ASSETS_FOR_BUNDLE_INPUT";save()
 run("npm-ci",["npm.cmd","ci","--no-audit","--no-fund"]);run("windows-web",["npm.cmd","run","build:windows"])
 dist=S/"apps/windows/dist";assert {p.relative_to(dist).as_posix() for p in dist.rglob("*") if p.is_file()}=={v["path"] for v in native["webAssets"]}
 for row in native["webAssets"]:assert sha(dist/row["path"])==row["sha256"],row["path"]
 run("native-target-preflight",[sys.executable,S/"tools/check_type_build_target.py","--target-dir",T,"--project",S,"--artifact-dir",pair])
 record["state"]="BUNDLING_IDENTICAL_NATIVE_PAIR_WITH_FIXED_MSI_RECIPE";save()
 run("msi-bundle",["node",S/"node_modules/@tauri-apps/cli/tauri.js","bundle","-v","--bundles","msi","--ci","--no-sign"],S/"apps/windows")
 files=list((T/"release/bundle/msi").glob("*.msi"));assert len(files)==1;msi=C/files[0].name;shutil.copyfile(files[0],msi)
 for row in native["nativeFiles"]:assert sha(pair/row["path"])==row["sha256"]
 for row in native["webAssets"]:assert sha(dist/row["path"])==row["sha256"]
 for row in native["sourceFiles"]:
  raw=(S/row["path"]).read_bytes();hashes=[hashlib.sha256(v).hexdigest() for v in [raw,raw.replace(b"\r\n",b"\n"),raw.replace(b"\r\n",b"\n").replace(b"\n",b"\r\n")]]
  assert (change["newSha256"] if row["path"]==change["path"] else row["sha256"]) in hashes
 raw=(pair/"companion-type.exe").read_bytes();assert raw.count(b"__TAURI_BUNDLE_TYPE_VAR_UNK")==1
 record["expectedEmbeddedExeSha256"]=hashlib.sha256(raw.replace(b"__TAURI_BUNDLE_TYPE_VAR_UNK",b"__TAURI_BUNDLE_TYPE_VAR_MSI")).hexdigest();record["expectedDllSha256"]=sha(pair/"companion_type_lib.dll")
 resources=N/"resources";record["licenseFiles"]=[{"path":p.relative_to(resources).as_posix(),"sha256":sha(p)} for p in (resources/"licenses").rglob("*") if p.is_file()]+[{"path":"opus-license.txt","sha256":sha(resources/"opus-license.txt")}]
 record.update(state="CI_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING",msi=msi.name,msiSha256=sha(msi),nativeAndWebUnchangedAfterBundle=True,localMsiPayloadInspectionRequired=True,finishedAt=datetime.now(timezone.utc).isoformat());save()
 print(json.dumps({k:record[k] for k in ["state","sourceCommit","packagingSourceCommit","version","msiSha256","nativeRecompiled"]}),flush=True)
except BaseException as error:
 record.update(state="CI_PACKAGE_ONLY_FAILED_RETAINED",error=repr(error),finishedAt=datetime.now(timezone.utc).isoformat());save();(C/"failure.txt").write_text(traceback.format_exc());raise
