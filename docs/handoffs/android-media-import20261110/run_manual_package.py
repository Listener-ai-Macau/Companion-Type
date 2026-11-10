from pathlib import Path
import sys,subprocess
r=Path("C:/Users/Billy/Desktop/Denzic/Companion");sys.path.insert(0,str(r/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2);c=Path(__file__).parent
q=subprocess.run(["python",str(c/"package_manual_followup_candidate.py"),*sys.argv[1:]],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=240)
print((q.stdout+q.stderr).decode(errors="replace")[-2500:]);assert q.returncode==0
