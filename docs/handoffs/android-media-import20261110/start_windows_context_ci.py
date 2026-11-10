from pathlib import Path
from datetime import datetime
import ast,json,os,shutil,subprocess,sys,re
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent;version=sys.argv[1] if len(sys.argv)>1 else 'windows083';assert version in ['windows083','windows084','windows087'];O=C/version;v=json.loads((O/'windows-verification.json').read_text());freeze=json.loads((O/'source-freeze.json').read_text());assert v['version']=='0.1.'+str(int(version[7:])) and v['sourceCommit']==freeze['sourceCommit'] and v['ciWrapperOverallPassed']
target=S/'docs/handoffs/android-media-import20261110'/version;target.mkdir(parents=True,exist_ok=True)
for file in O.iterdir():
 if file.is_file() and file.suffix in ['.json','.py']:shutil.copy2(file,target/file.name)
workflow=S/'.github/workflows/windows-candidate.yml';wf=workflow.read_text(encoding='utf-8');wf,count=re.subn(r'docs/handoffs/android-media-import20261110/windows[0-9]+/runtime-spec.json','docs/handoffs/android-media-import20261110/'+version+'/runtime-spec.json',wf);assert count==1;workflow.write_text(wf,encoding='utf-8')
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
paths=['.github/workflows/windows-candidate.yml']+['tools/qa/core_acceptance20261109/'+n for n in ['run_ci.py','windows_meeting.py','windows_context_ui.cjs','windows_context_backend.py']]+['docs/handoffs/android-media-import20261110/'+version]
for name in paths[:5]:
 p=S/name;old=subprocess.run(['git','show','HEAD:'+name],cwd=S,capture_output=True,check=True).stdout;data=p.read_bytes().replace(b'\r\n',b'\n');p.write_bytes(data.replace(b'\n',b'\r\n') if b'\r\n' in old else data)
head=scope['ship'](S,paths,'[core-context] Verify grouped image-note composer, delete and recovery in matched '+version);record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'MATCHED_'+version.upper()+'_CONTEXT_RUNTIME_STARTED','testSourceCommit':head,'appSourceCommit':v['sourceCommit'],'buildRun':v['ciRunId'],'nativeRecompiled':False,'ownerForegroundUsed':False,'runtimeQualified':False};(O/'runtime-source.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
