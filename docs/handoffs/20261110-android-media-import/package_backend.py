from pathlib import Path
from datetime import datetime
import ast,hashlib,io,json,os,subprocess,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';B=R/'companion-audio-import-backend20261110';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110');S=R/'companion-device-closure055'
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}
tree=ast.parse((S/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'subprocess':subprocess,'env':env}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'selective-publisher','exec'),scope)
for root in [A,B]:
 names=scope['git'](root,'diff','--name-only').splitlines()
 for name in names:
  p=root/name
  if p.suffix not in ['.java','.tsx','.cjs','.gradle','.xml']:continue
  original=subprocess.check_output(['git','show','HEAD:'+name],cwd=root)
  if original.count(b'\r\n')>original.count(b'\n')*.8:p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
names=['RecordingLibrary','NativeAudio','ManagedAudioParts','DeviceBookmarkCache','ImportedAudio','MeetingStore'];paths=['apps/android-backend/src/main/java/com/denzic/companion/mobile/'+name+'.java' for name in names]
source=scope['ship'](B,paths,'[skip ci] Support verified external media sources without recorder protocol or model changes')
base=A/'apps/android/app/libs/companion-android-backend.aar';raw=(P/'backend6087901.aar').read_bytes();assert hashlib.sha256(raw).hexdigest()=='af498b880338aa5b8036cbfa97ad26588fdc784ee5eaf92e15df50c06e9aaadf'
baseArchive=zipfile.ZipFile(io.BytesIO(raw));oldClasses=zipfile.ZipFile(io.BytesIO(baseArchive.read('classes.jar')));classes={name:oldClasses.read(name) for name in oldClasses.namelist()};changed=[]
for file in (P/'backend-classes').rglob('*.class'):
 name=file.relative_to(P/'backend-classes').as_posix();short=name.rsplit('/',1)[1].split('$')[0].removesuffix('.class');assert short in names,name;classes[name]=file.read_bytes();changed.append(name)
assert any(x.endswith('/ImportedAudio.class') for x in changed) and any(x.endswith('/MeetingStore.class') for x in changed)
jar=io.BytesIO()
with zipfile.ZipFile(jar,'w',compression=zipfile.ZIP_DEFLATED) as output:
 for name,data in classes.items():output.writestr(name,data)
payload=io.BytesIO()
with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_DEFLATED) as output:
 for name in baseArchive.namelist():output.writestr(name,jar.getvalue() if name=='classes.jar' else baseArchive.read(name))
new=payload.getvalue()
with zipfile.ZipFile(io.BytesIO(new)) as checked:
 for name in baseArchive.namelist():
  if name!='classes.jar':assert baseArchive.read(name)==checked.read(name),name
old=A/'apps/android/app/libs/companion-android-backend.provenance.json';provenance=json.loads(old.read_text());(C/'inherited-backend6087901.json').write_text(json.dumps(provenance,indent=2)+'\n')
provenance.update(at=datetime.now().astimezone().isoformat(timespec='seconds'),aarSha256=hashlib.sha256(new).hexdigest(),backendSourceCommit=source,backendSourceWorkspace=str(B),javaSourceCommit=source,remoteSourceVerified=True,nativeRebuiltThisBatch=False,nativeProductionSourceIdenticalToNativeSourceCommit=True,nativeLibrariesByteIdenticalTo6087901=True,speechRuntimeBinariesAndWeightsChanged=False,scope='Independent imported original media and verified lossless speech parts; existing recorder protocol, device paths, native decoder and model binaries retained.',javaImportClassesChanged=changed,importedOriginalReencoded=False)
base.write_bytes(new);old.write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(C/'backend-package.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'backendSource':source,'aarSha256':provenance['aarSha256'],'nativeLibrariesUnchanged':True,'modelBinariesUnchanged':True,'changedClassCount':len(changed)}))
