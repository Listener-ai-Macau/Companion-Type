from pathlib import Path
from datetime import datetime
import ast,json,os,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
names=['packages/ui/src/'+n for n in ['CompanionDashboard.tsx','CompanionMeetingNotes.tsx','knownOperationErrors.ts','companionUi.css']]+['tools/test_windows_note_images.tsx']
for name in names:
 p=S/name;old=subprocess.run(['git','show','HEAD:'+name],cwd=S,capture_output=True,check=True).stdout;data=p.read_bytes().replace(b'\r\n',b'\n');p.write_bytes(data.replace(b'\n',b'\r\n') if b'\r\n' in old else data)
head=scope['ship'](S,names,'[core-ui] Make picture-note time association explicit and retain useful image input feedback')
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'WINDOWS_CONTEXT_USABILITY_SOURCE_REMOTE_PROTECTED_RUNTIME_PENDING','sourceCommit':head,'scope':['Direct current-playback bookmark selection in the note composer, same durable bookmark API and retry identity','Specific authored image-validation messages without exposing unknown OS/provider details','Full uncropped note preview and clear image/notes entry'],'installed':False,'newNativeBuild':False,'baseNativeCandidate':'0.1.83/ff025d6f9e1bf84bbcbf9a77940e84b9f9f0bc8b','saleQualified':False}
(C/'windows083/followup-ui-source.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,ensure_ascii=False))
