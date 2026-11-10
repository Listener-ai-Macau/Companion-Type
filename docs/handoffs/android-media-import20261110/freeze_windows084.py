from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,subprocess,tomllib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=Path(__file__).parent;O=C/'windows084';O.mkdir(exist_ok=False)
prior=json.loads((C/'windows083/runtime-result.json').read_text(encoding='utf-8'));assert prior['state']=='WINDOWS083_REAL_PUBLIC_AUDIO_IMAGE_CONTEXT_UI_AND_BACKUP_RESTORE_CLEANUP_PASSED'
uiroot=Path('E:/CodexData/Companion/.build-cache/windows-note-context20261110/ui-followup-passed');ui=json.loads(next(uiroot.glob('*/result.json')).read_text(encoding='utf-8'));assert ui['state']=='GROUPED_MEETING_UI_SOURCE_CONTRACTS_PASSED';assert all(r['exitCode']==0 for r in ui['results']);ui['run']=42769157968;(O/'ui-source-result.json').write_text(json.dumps(ui,indent=2)+'\n',encoding='utf-8')
names=['package.json','package-lock.json','apps/windows/src-tauri/Cargo.toml','apps/windows/src-tauri/Cargo.lock','apps/windows/src-tauri/tauri.conf.json']
oldlock=tomllib.loads((S/names[3]).read_text(encoding='utf-8'))
for name in names:
 p=S/name;raw=p.read_bytes();assert b'"0.1.83"' in raw,name;p.write_bytes(raw.replace(b'"0.1.83"',b'"0.1.84"'))
newlock=tomllib.loads((S/names[3]).read_text(encoding='utf-8'));assert [x for x in oldlock['package'] if x['name']!='companion-type']==[x for x in newlock['package'] if x['name']!='companion-type']
manifest=S/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json';m=json.loads(manifest.read_text(encoding='utf-8'))
for name in m['lockedInputs']:m['lockedInputs'][name]=hashlib.sha256((S/name).read_bytes()).hexdigest()
raw=manifest.read_bytes();text=json.dumps(m,ensure_ascii=False,indent=2)+'\n';manifest.write_bytes(text.replace('\n','\r\n').encode('utf-8') if b'\r\n' in raw else text.encode('utf-8'))
check=subprocess.run(['node','tools/verify_third_party_notices.mjs'],cwd=S,capture_output=True,text=True);(O/'license-preflight.log').write_text(check.stdout+check.stderr,encoding='utf-8');assert check.returncode==0,check.stdout+check.stderr
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
paths=names+['apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json','.github/workflows/windows-candidate.yml']
for name in paths:
 p=S/name;old=subprocess.run(['git','show','HEAD:'+name],cwd=S,capture_output=True,check=True).stdout;data=p.read_bytes().replace(b'\r\n',b'\n');p.write_bytes(data.replace(b'\n',b'\r\n') if b'\r\n' in old else data)
head=scope['ship'](S,paths,'[windows-build] Package grouped image-note time, preview and input feedback improvements')
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'WINDOWS084_CONTEXT_USABILITY_CANDIDATE_REMOTE_BUILD_STARTED','sourceCommit':head,'version':'0.1.84','priorNativeCandidatePassed':'0.1.83/ff025d6f9e1bf84bbcbf9a77940e84b9f9f0bc8b','priorRuntimeRun':42769086328,'uiSourceRun':42769157968,'externalDependenciesUnchanged':True,'modelsChangedOrRun':False,'localHeavyBuild':False,'installed':False,'saleQualified':False,'cache':'Pinned official actions/cache v4.3.0; Rust still rebuilds changed sources with --locked and freeze/payload checks. First cache population does not promise a speedup.'}
(O/'source-freeze.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,ensure_ascii=False))
