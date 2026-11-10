"""Publication-only resume: no versions, fixtures or product sources are changed."""
from pathlib import Path
from datetime import datetime
import ast,json,os,subprocess,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';A=R/'companion-core-android20261109';C=Path(__file__).parent
assert json.loads((S/'package.json').read_text())['version']=='0.1.88'
assert 'versionCode 128' in (A/'apps/android/app/build.gradle').read_text()
assert not (C/'document-candidates-source.json').exists()
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf-8'));scope={'subprocess':subprocess,'env':env};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
publication={}
for label,root in [('windows',S),('android',A)]:
 dest=root/'docs/handoffs/android-media-import20261110';shutil.copyfile(C/'finish_document_source.py',dest/'finish_document_source.py');shutil.copyfile(R/'docs/product_backlog.json',root/'docs/product_backlog.json')
 status=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=root,text=True).splitlines();paths=[]
 for line in status:
  file=line[3:].replace('\\','/')
  if file.startswith(('core-ui-output/','tools/qa/core_acceptance20261109/__pycache__/')):continue
  assert file.startswith(('apps/','packages/','vendor/','tools/','.github/','docs/handoffs/android-media-import20261110/')) or file in ['.gitattributes','package.json','package-lock.json','docs/product_backlog.json'],file
  paths.append(file)
 publication[label]=scope['ship'](root,paths,'[windows-build] Build complete local document-context candidate 0.1.88' if root==S else 'Build Android128 local document context and related meeting reading candidate')
out={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'DOCUMENT_CONTEXT_CANDIDATES_SOURCE_REMOTE_VERIFIED','windowsSource':publication['windows'],'androidSource':publication['android'],'backendSource':'f55f8e83b77c10ca34db442971a045eca1acfdf4','windowsVersion':'0.1.88','androidVersion':'0.1.128','localHeavyNativeBuild':False,'installed':False,'appDelivered':False,'saleQualified':False};(C/'document-candidates-source.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
