from pathlib import Path
import sys,subprocess,json
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,768*1024**2)
freeze=json.loads((C/"android138/source-freeze.json").read_text());run=int(freeze["buildRun"]);source=freeze["sourceCommit"]
p=subprocess.run(["gh","run","view",str(run),"--repo","Listener-ai-Macau/Companion-Type","--json","status,conclusion,headSha"],capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0
state=json.loads(p.stdout);assert state=={"status":"completed","conclusion":"success","headSha":source},state
p=subprocess.run([sys.executable,str(C/"sign_candidate.py"),"--code","138","--run",str(run),"--source",source],capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
(C/"android138/signing.log").write_bytes(p.stdout+p.stderr);print(p.stdout.decode(errors="replace")[-1800:]);assert p.returncode==0,p.stderr.decode(errors="replace")[-2000:]
(C/"android138/signing-resource-limits.json").write_text(json.dumps(limits.query(),indent=2)+"\n")
