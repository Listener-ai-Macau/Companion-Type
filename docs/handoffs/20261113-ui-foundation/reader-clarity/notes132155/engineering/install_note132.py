from pathlib import Path
from types import SimpleNamespace
import json,subprocess,sys
sys.path.insert(0,str(Path(__file__).parent))
from windows_candidate_delivery import install,sha
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261112-product-closure/windows132';frozen=json.loads((B/'frozen-source.json').read_bytes());prior=R/'docs/handoffs/20261112-product-closure/windows129/installation.json';old=json.loads(prior.read_bytes());installed=Path('C:/Program Files/Companion Type')
assert sha(installed/'companion-type.exe')==old['installedExeSha256'] and sha(installed/'companion_type_lib.dll')==old['installedDllSha256'],'Installed predecessor changed; preserve it and inspect the new receipt before any upgrade'
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','merge-base','--is-ancestor',old['sourceCommit'],frozen['sourceCommit']],cwd=R/'companion-device-closure055',check=True)
cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows132/install-from129');cache.mkdir(exist_ok=False)
print(json.dumps(install(SimpleNamespace(batch=B,cache=cache,previous_installation_receipt=prior),frozen,'WINDOWS132'),ensure_ascii=False))
