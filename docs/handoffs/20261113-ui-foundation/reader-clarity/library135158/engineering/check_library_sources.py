from pathlib import Path
from datetime import datetime
import json,os,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';Q=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/library-closure20261114/source-checks');Q.mkdir(exist_ok=False)
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,1536*1024**2);record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),steps=[],resourceLimits=limits.receipt)
commands=[('windows-types',S,['node','node_modules/typescript/bin/tsc','-p','apps/windows/tsconfig.json']),('mobile-types',A,['node','node_modules/typescript/bin/tsc','-p','apps/mobile/tsconfig.json']),('mobile-web',A,[os.environ['COMSPEC'],'/d','/c','npm.cmd','run','build:mobile'])]
for name,root,cmd in commands:
 with(Q/(name+'.log')).open('xb')as log:r=subprocess.run(cmd,cwd=root,env={**os.environ,'NODE_OPTIONS':'--max-old-space-size=512','GOMAXPROCS':'2','GOMEMLIMIT':'256MiB'},stdout=log,stderr=subprocess.STDOUT,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
 record['steps'].append(dict(name=name,exitCode=r.returncode));(Q/'result.json').write_text(json.dumps(record,indent=2),encoding='utf8')
 assert r.returncode==0,(Q/(name+'.log')).read_text(errors='replace')[-3000:]
record.update(state='AFFECTED_TYPES_AND_MOBILE_PRODUCTION_WEB_PASSED',finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'));(Q/'result.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(record['state'])
