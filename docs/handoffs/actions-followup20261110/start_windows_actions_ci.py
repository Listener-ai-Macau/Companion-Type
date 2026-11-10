from pathlib import Path
from datetime import datetime
import ast,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent;O=C/'windows082';destination=S/'docs/handoffs/actions-followup20261110/windows082';destination.mkdir(parents=True,exist_ok=True)
for name in ['windows-verification.json','runtime-spec.json','source-freeze.json','inspect_candidate.py']:shutil.copyfile(O/name,destination/name)
tree=ast.parse((C/'push_sources.py').read_text(encoding='utf8'))
# Preserve the already-established selective ship implementation only.
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
old=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in old.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'publisher','exec'),scope)
names=['tools/qa/core_acceptance20261109/windows_actions_ui.cjs','tools/qa/core_acceptance20261109/windows_meeting.py','tools/qa/core_acceptance20261109/windows_meeting_ui.cjs','tools/qa/core_acceptance20261109/run_ci.py','.github/workflows/windows-candidate.yml','docs/handoffs/actions-followup20261110/windows082','apps/mobile/src/MinutesDocument.tsx','apps/mobile/src/MobileActionCards.tsx','tools/test_action_review_tools.tsx']
for name in names:
    p=S/name
    if not p.is_file():continue
    prior=subprocess.run(['git','show','HEAD:'+name],cwd=S,capture_output=True)
    if prior.returncode==0 and b'\r\n' not in prior.stdout:p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
head=scope['ship'](S,names,'[core-actions] Verify Windows082 native saved-action scope, durable completion and clipboard')
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'testSource':head,'appSource':'e72d16ed941cb7070cc7bd6e8d21f3b830192254','remoteReadbackVerified':True,'newNativeBuild':False,'modelsRun':False}
(O/'runtime-source.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
