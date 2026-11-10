from pathlib import Path
import sys,subprocess,json
r=Path("C:/Users/Billy/Desktop/Denzic/Companion");sys.path.insert(0,str(r/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,768*1024**2);c=Path(__file__).parent
q=subprocess.run(["node","--max-old-space-size=192",str(c/"check_manual_layout.cjs")],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180);(c/"manual-layout/source-check.log").write_bytes(q.stdout+q.stderr);print((q.stdout+q.stderr).decode(errors="replace")[-1800:])
p=c/"manual-layout/result.json";j=json.loads(p.read_text());j["limits"]=limits.query();p.write_text(json.dumps(j,indent=2)+"\n");print("LAYOUT_STATE",j["state"],"cases",len(j["checks"]));assert q.returncode==0 and "PASSED" in j["state"]
