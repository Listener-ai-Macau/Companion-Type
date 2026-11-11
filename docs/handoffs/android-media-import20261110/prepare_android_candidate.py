from pathlib import Path
import sys,subprocess,json,re
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,768*1024**2)
code=sys.argv[1];assert re.fullmatch(r"[0-9]{3}",code) and int(code)>=122;output=C/("android"+code)
freeze=json.loads((output/"source-freeze.json").read_text());run=int(freeze["buildRun"]);source=freeze["sourceCommit"]
p=subprocess.run(["gh","api","-H","Cache-Control: no-cache","repos/Listener-ai-Macau/Companion-Type/actions/runs/"+str(run)],capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0
fresh=json.loads(p.stdout);state={"status":fresh["status"],"conclusion":fresh["conclusion"],"headSha":fresh["head_sha"]};assert state=={"status":"completed","conclusion":"success","headSha":source},state
p=subprocess.run([sys.executable,str(C/"sign_candidate.py"),"--code",code,"--run",str(run),"--source",source],capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
(output/"signing.log").write_bytes(p.stdout+p.stderr);print(p.stdout.decode(errors="replace")[-1800:]);assert p.returncode==0,p.stderr.decode(errors="replace")[-2000:]
(output/"signing-resource-limits.json").write_text(json.dumps(limits.query(),indent=2)+"\n")
