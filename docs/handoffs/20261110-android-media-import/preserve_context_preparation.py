from pathlib import Path
from datetime import datetime
import ast,json,os,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
names=['.github/workflows/windows-candidate.yml']+['tools/qa/core_acceptance20261109/'+n for n in ['run_ci.py','windows_meeting.py','windows_meeting_ui.cjs','windows_native_dialog.py','windows_context_ui.cjs','windows_context_backend.py','fixtures/public-whiteboard124.png']]
for name in names:
 p=S/name;old=subprocess.run(['git','show','HEAD:'+name],cwd=S,capture_output=True)
 if old.returncode==0 and b'\r\n' not in old.stdout:p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
head=scope['ship'](S,names,'[skip ci] Prepare isolated image-context native UI and recovery acceptance');record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'testSourceCommit':head,'appSourceCommit':'ff025d6f9e1bf84bbcbf9a77940e84b9f9f0bc8b','appBuildRun':42762906819,'state':'ISOLATED_CONTEXT_ACCEPTANCE_PREPARATION_REMOTE_PROTECTED_NOT_EXECUTED','remoteReadbackVerified':True,'nativeRebuildTriggered':False,'ownerForegroundUsed':False};(C/'windows083/acceptance-preparation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
