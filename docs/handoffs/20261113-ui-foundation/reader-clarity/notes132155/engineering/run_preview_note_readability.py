from pathlib import Path
import json,os,subprocess,sys
sys.path.insert(0,'C:/Users/Billy/Desktop/Denzic/Companion/model-research/src')
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
assert not SystemRamPressure().low()
limits=WorkerLimits(5,1536*1024**2)
out=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113')
attempt=int(sys.argv[1]) if len(sys.argv)>1 else 3;assert 2<=attempt<=5
logfile=out/('note-readability-preview-r'+str(attempt)+'.log')
with logfile.open('xb')as log:
 run=subprocess.run(['node','--max-old-space-size=256','work/preview_note_readability.cjs',str(attempt)],env={**os.environ,'GOMAXPROCS':'2','GOMEMLIMIT':'256MiB'},stdout=log,stderr=subprocess.STDOUT,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
(out/('note-readability-preview-r'+str(attempt)+'-resource.json')).write_text(json.dumps(dict(exitCode=run.returncode,limits=limits.receipt),indent=2),encoding='utf8')
print(logfile.read_text(errors='replace')[-3500:]);raise SystemExit(run.returncode)
