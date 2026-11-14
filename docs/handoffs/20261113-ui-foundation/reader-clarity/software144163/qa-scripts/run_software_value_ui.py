from pathlib import Path
import json,os,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
assert not SystemRamPressure().low();limits=WorkerLimits(5,1536*1024**2)
stage=sys.argv[1];Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/software-value20261114');log=Q/(stage+'.log');assert not log.exists()
with log.open('xb')as f:r=subprocess.run(['node','--max-old-space-size=384',str(Path(__file__).with_name('check_software_value_ui.cjs')),stage],env={**os.environ,'GOMAXPROCS':'2','GOMEMLIMIT':'256MiB'},stdout=f,stderr=subprocess.STDOUT,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
print(log.read_text(encoding='utf8',errors='replace')[-4000:]);(Q/(stage+'-resource.json')).write_text(json.dumps(dict(exitCode=r.returncode,limits=limits.receipt),indent=2),encoding='utf8');raise SystemExit(r.returncode)
