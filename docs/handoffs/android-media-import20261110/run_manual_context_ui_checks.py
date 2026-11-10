import pathlib,sys,subprocess,json
R=pathlib.Path("C:/Users/Billy/Desktop/Denzic/Companion");sys.path.insert(0,str(R/"model-research/src"))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2);c=pathlib.Path(__file__).parent
q=subprocess.run(["node","--max-old-space-size=192",str(c/"check_manual_context_ui.cjs")],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=240)
print((q.stdout+q.stderr).decode(errors="replace")[-3500:])
p=c/"manual-followup-ui-source-checks.json";j=json.loads(p.read_text());j["limits"]=limits.query();p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");assert q.returncode==0 and j["state"]=="MANUAL_FOLLOWUP_COMPONENTS_AND_AFFECTED_NOTES_PASSED"
