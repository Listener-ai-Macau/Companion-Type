"""Freeze one UI-only release; retain all external dependencies and upgrade identity."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,subprocess,tomllib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent
O=C/'windows082';O.mkdir(exist_ok=True)
old_rust=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text())
old_npm=json.loads((S/'package-lock.json').read_text())
names=['package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json']
for name in names:
    p=S/name;raw=p.read_bytes();assert b'"0.1.81"' in raw,name
    p.write_bytes(raw.replace(b'"0.1.81"',b'"0.1.82"'))
new_rust=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text())
new_npm=json.loads((S/'package-lock.json').read_text())
for lock in [old_rust,new_rust]:
    for item in lock['package']:
        if item['name']=='companion-type':item['version']='PRODUCT_VERSION_ONLY'
assert old_rust==new_rust
for lock in [old_npm,new_npm]:
    lock['version']=lock['packages']['']['version']='PRODUCT_VERSION_ONLY'
assert old_npm==new_npm
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
license_path=S/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json'
license_data=json.loads(license_path.read_text())
for name in license_data['lockedInputs']:license_data['lockedInputs'][name]=sha(S/name)
license_path.write_text(json.dumps(license_data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'))
scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
head=scope['ship'](S,names+['apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json'],'[windows-build] Freeze Windows082 saved-action filtering and scoped followup')
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'WINDOWS082_SOURCE_FROZEN_REMOTE_BUILD_PENDING','sourceCommit':head,'version':'0.1.82','priorUiSource':'f24aa2f2b651aeae5325eb731f3381d61d134a65','sourceChecksPassedRun':42723216750,'externalDependenciesUnchanged':True,'localHeavyBuild':False,'modelsRun':False,'remoteReadbackVerified':True,'installed':False,'nativeRuntimeQualified':False,'saleQualified':False}
(O/'source-freeze.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(record))
