from pathlib import Path
from datetime import datetime
import ast,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent;O=C/'windows083';v=json.loads((O/'windows-verification.json').read_text());assert v['version']=='0.1.83' and v['sourceCommit']=='ff025d6f9e1bf84bbcbf9a77940e84b9f9f0bc8b' and v['ciWrapperOverallPassed']
target=S/'docs/handoffs/android-media-import20261110/windows083';target.mkdir(parents=True,exist_ok=True)
for file in O.iterdir():
 if file.is_file() and file.suffix in ['.json','.py']:shutil.copy2(file,target/file.name)
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
paths=["tools/qa/core_acceptance20261109/windows_context_backend.py","tools/qa/core_acceptance20261109/windows_context_ui.cjs",'tools/qa/core_acceptance20261109/run_ci.py','docs/handoffs/android-media-import20261110/windows083']
head=scope['ship'](S,paths,'[core-context] Read actual UTF-8 image-note state for matched Windows083 backup recovery');record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'MATCHED_WINDOWS083_CONTEXT_RUNTIME_STARTED','testSourceCommit':head,'appSourceCommit':v['sourceCommit'],'buildRun':42762906819,'nativeRecompiled':False,'ownerForegroundUsed':False,'runtimeQualified':False};(O/'runtime-source.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
