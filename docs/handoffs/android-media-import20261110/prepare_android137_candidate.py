from pathlib import Path
import sys,subprocess,json,hashlib,zipfile
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;A=R/"companion-core-android20261109";P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110")
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,768*1024**2)
run=42931037723;source="aac73ae44d9aff77680699be8b760d4199907b79"
def gh(args):
 q=subprocess.run(["gh",*args],cwd=A,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW);assert q.returncode==0,q.stderr.decode(errors="replace")[-600:];return q.stdout
state=json.loads(gh(["run","view",str(run),"--json","status,conclusion,headSha"]));assert state=={"status":"completed","conclusion":"success","headSha":source}
dest=P/"android137-ci";archive=P/"android137-ci-artifact.zip"
if not dest.exists():
 info=json.loads(gh(["api",f"repos/Listener-ai-Macau/Companion-Type/actions/runs/{run}/artifacts"]));artifact=next(v for v in info["artifacts"] if v["name"]=="companion-android-core-ui-"+source)
 from release_readback import download
 transfer=download("Listener-ai-Macau/Companion-Type",artifact["id"],archive,artifact["size_in_bytes"],artifact["digest"].removeprefix("sha256:"),kind="artifact")
 digest=hashlib.file_digest(archive.open("rb"),"sha256").hexdigest();assert digest==artifact["digest"].removeprefix("sha256:") and archive.stat().st_size==artifact["size_in_bytes"]
 with zipfile.ZipFile(archive) as package:
  names=package.namelist();assert len(names)==len(set(names)) and len(names)<20000 and sum(v.file_size for v in package.infolist())<1024**3
  for name in names:assert not Path(name).is_absolute() and ":" not in name and "\\" not in name and all(part not in [".",".."] for part in Path(name).parts) and (dest/name).resolve().is_relative_to(dest.resolve())
  dest.mkdir()
  package.extractall(dest)
 (dest/"artifact-transfer.json").write_text(json.dumps({"artifactId":artifact["id"],"sha256":digest,"bytes":archive.stat().st_size,"transport":transfer,"completeReadbackVerified":True},indent=2)+"\n")
q=subprocess.run([sys.executable,str(C/"sign_candidate.py"),"--code","137","--run",str(run),"--source",source],cwd=C,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
(C/"android137/signing.log").write_bytes(q.stdout+q.stderr);print(q.stdout.decode(errors="replace")[-2000:]);assert q.returncode==0,q.stderr.decode(errors="replace")[-1200:]
(C/"android137/signing-resource-limits.json").write_text(json.dumps(limits.query(),indent=2)+"\n")
