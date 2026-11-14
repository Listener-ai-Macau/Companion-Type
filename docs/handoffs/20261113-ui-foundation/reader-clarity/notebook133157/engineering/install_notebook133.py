from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
import json,subprocess,sys
sys.path.insert(0,str(Path(__file__).parent));from windows_candidate_delivery import install,sha
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';H=R/'docs/handoffs/20261112-product-closure/windows133';O=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/template-full20261113/whole-delivery133156')
frozen=json.loads((H/'frozen-source.json').read_bytes());prior=H.parent/'windows132/installation.json';old=json.loads(prior.read_bytes());installed=Path('C:/Program Files/Companion Type');assert sha(installed/'companion-type.exe')==old['installedExeSha256'] and sha(installed/'companion_type_lib.dll')==old['installedDllSha256'],'A new installed predecessor must be reviewed, never overwritten'
g=['git','-c','maintenance.auto=false','-c','gc.auto=0'];diff=lambda *args:subprocess.check_output(g+['diff','--name-only',*args],cwd=S,text=True).splitlines()
versions=['package.json','package-lock.json','apps/windows/src-tauri/tauri.conf.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json']
pointer=['packages/desktop-input','apps/windows/src/DesktopPointer.tsx','apps/windows/src-tauri/src/backend/desktop_pointer.rs','apps/windows/src-tauri/src/backend/ble_bridge/desktop_input_stream.rs','third_party/imu-pointer']
assert not diff(frozen['saved131SourcePreserved'],frozen['sourceCommit'],'--',*pointer)
input_changes=diff(old['sourceCommit'],frozen['saved131SourcePreserved'],'--',*pointer);changes=diff(old['sourceCommit'],frozen['sourceCommit']);assert set(changes)<=set(frozen['relatedAuthoringFiles']+versions+input_changes),changes
assert not diff(old['sourceCommit'],frozen['sourceCommit'],'--',*frozen['unchangedModelScope'])
scope=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),oldSource=old['sourceCommit'],currentSource=frozen['sourceCommit'],savedInputBase=frozen['saved131SourcePreserved'],saved131InputPreservedExactly=True,installed132ModelLogicUnchanged=True,changedFiles=changes,knownInputChanges=input_changes,uncommittedOtherInputIncluded=False,reason='Exact own UI overlay on saved131. Source lineage branches from132; no ancestry claim, complete affected file set verified.')
(O/'installed-source-composition.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2),encoding='utf8')
cache=O/'install-from132';cache.mkdir(exist_ok=False);print(json.dumps(install(SimpleNamespace(batch=H,cache=cache,previous_installation_receipt=prior),frozen,'WINDOWS133'),ensure_ascii=False))
