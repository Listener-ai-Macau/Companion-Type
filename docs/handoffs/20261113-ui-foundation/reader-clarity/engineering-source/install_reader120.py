from pathlib import Path
from types import SimpleNamespace
import json,sys,subprocess
sys.path.insert(0,str(Path(__file__).parent));from windows_candidate_delivery import install
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'docs/handoffs/20261112-product-closure/windows120';frozen=json.loads((B/'frozen-source.json').read_bytes())
previous=R/'docs/handoffs/20261112-imu-pointer/complete-experience20261113/windows119/installation.json'
observed=json.loads(previous.read_bytes());controller=json.loads(Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112/complete-experience20261113/owner119-tilt-only-recovered/result.json').read_bytes())
assert controller['state']=='OWNER_EXPERIENCE_ENDED'and all(item['ownedAppAndLinkClosed']and item['release']['result']=='TURN_RELEASED'for item in controller['sessions'])
subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','merge-base','--is-ancestor',observed['sourceCommit'],frozen['sourceCommit']],cwd=R/'companion-device-closure055',check=True)
record=dict(state='CURRENT119_NORMAL_INSTALL_AND_CLOSED_OWNER_CONTROLLER_MATCHED_BEFORE120_UPGRADE',actualPreviousReceipt=str(previous),actualPreviousVersion=observed['installedVersion'],actualPreviousSource=observed['sourceCommit'],owner119ExperienceEnded=controller['finishedAt'],candidateRetainsCurrentCommitted119Source=True,initial118PredecessorAssumptionRejectedBeforeMsiStarted=True,initialAttemptPreserved='E:/CodexData/Companion/.build-cache/product-closure20261112/windows120/upgrade-private')
(B/'upgrade-predecessor.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows120/install-from119');cache.mkdir(exist_ok=False)
args=SimpleNamespace(batch=B,cache=cache,previous_installation_receipt=previous)
result=install(args,frozen,'WINDOWS120');print(json.dumps(result,ensure_ascii=False),flush=True)
