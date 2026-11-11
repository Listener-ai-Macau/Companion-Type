from pathlib import Path
import sys,subprocess,json
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,768*1024**2);freeze=json.loads((C/"windows103/source-freeze.json").read_text())
for name,args in [("download",[sys.executable,C/"download_windows_candidate.py","103",str(freeze["buildRun"])]),("inspect",[sys.executable,C/"windows103/inspect_candidate.py"])]:
 q=subprocess.run(list(map(str,args)),cwd=C,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW);(C/"windows103"/(name+"-candidate.log")).write_bytes(q.stdout+q.stderr);print(name,q.returncode,q.stdout.decode(errors="replace")[-1600:],flush=True);assert q.returncode==0,q.stderr.decode(errors="replace")[-1800:]
(C/"windows103/download-resource-limits.json").write_text(json.dumps(limits.query(),indent=2)+"\n")
