from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,shutil,subprocess
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;A=R/'companion-core-android20261109';S=R/'companion-device-closure055';P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110')
result=json.loads((P/'android120-ci/core-ui-output/result.json').read_text());assert result['state']=='GROUPED_MEETING_UI_SOURCE_CONTRACTS_PASSED' and result['sourceCommit']=='3dfb6742127b1173dc52dd068122cb2bb28a1ca2'
(C/'source-contracts-final.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
logs=C/'checks';logs.mkdir(exist_ok=True)
for folder in [P/'android120-ci/core-ui-output',P/'owned-progress-final-crash-temp']:
 for p in folder.glob('*.log'):
  raw=p.read_bytes();(logs/(p.name+'.json')).write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'utf8':raw.decode('utf8',errors='replace')},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
for root in [A,S]:
 dest=root/'docs/handoffs/nonmodel-core-playback20261110';dest.mkdir(parents=True,exist_ok=True)
 for p in C.rglob('*'):
  if p.is_file() and p.suffix in ['.py','.json']:
   target=dest/p.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'remoteReadbackVerified':True,'privateOwnerDataUploaded':False,'installed':False,'sourceCandidate':'3dfb6742127b1173dc52dd068122cb2bb28a1ca2','nativePhoneRuntimeQualified':False}
for name,root in [('android',A),('windows',S)]:record[name]=scope['ship'](root,['docs/product_backlog.json','docs/development_log.md','docs/handoffs/nonmodel-core-playback20261110'],'[skip ci] Preserve Android120 nonmodel candidate, true phone gate and original priorities')
(C/'publication.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record))
