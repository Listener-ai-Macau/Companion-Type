from pathlib import Path
import sys,subprocess,json
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;kind=sys.argv[1];assert kind in ["android137","windows100","android138","windows102","android139","windows103"]
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2)
q=subprocess.run([sys.executable,str(C/"preserve_installer.py"),kind],cwd=C,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW);(C/kind/"preservation.log").write_bytes(q.stdout+q.stderr);print(q.stdout.decode(errors="replace")[-2000:]);assert q.returncode==0,q.stderr.decode(errors="replace")[-1200:]
(C/kind/"preservation-resource-limits.json").write_text(json.dumps(limits.query(),indent=2)+"\n")
