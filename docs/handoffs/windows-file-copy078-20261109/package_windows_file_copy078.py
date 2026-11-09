"""Package the matching Windows078 native pair from private copies; no compile."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess,os,json,hashlib,shutil,msilib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-windows-file-copy078'
D=Path('E:/CodexData/Companion/.build-cache/windows-file-copy078');shared=Path('E:/CodexData/Companion/.build-cache/windows051/target')
target=D/'package-target'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
native=json.loads((C/'native-release-paged-result.json').read_text())
assert native['exitCode']==0 and native['state']=='PASS_NATIVE_RELEASE-PAGED'
assert native['applicationBuildOverrides'] is None
frozen=json.loads((C/'source-frozen.json').read_text(encoding='utf8'))
assert native['sourceCommit']==frozen['sourceCommit']
def require_frozen():
 for row in frozen['sourceFiles']:assert sha(S/row['path'])==row['sha256'],row['path']
 for row in frozen['windowsWebAssets']:assert sha(S/'apps/windows/dist'/row['path'])==row['sha256'],row['path']
require_frozen()
def guard(name,folder,pair=None):
 args=[os.sys.executable,str(R/'tools/check_type_build_target.py'),'--target-dir',str(folder),'--project',str(S/'apps/windows/src-tauri'),'--source-dir',str(S)]
 if pair:args+=['--artifact-dir',str(pair)]
 run=subprocess.run(args,capture_output=True,text=True,encoding='utf8',errors='replace')
 (C/name).write_text(run.stdout,encoding='utf8');assert run.returncode==0,run.stdout+run.stderr
guard('native-copy-preflight.json',shared)
pair=C/'windows-bin';pair.mkdir(exist_ok=False)
started=datetime.fromisoformat(native['at']).timestamp()
for name in ['companion-type.exe','companion_type_lib.dll']:
 source=shared/'release'/name;assert source.is_file() and source.stat().st_mtime>=started,name
 shutil.copy2(source,pair/name)
 destination=target/'release'/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(pair/name,destination)
guard('shared-post-copy-preflight.json',shared,pair)
guard('private-bundle-preflight.json',target,pair)
env={**os.environ,'CARGO_TARGET_DIR':str(target),'CARGO_BUILD_JOBS':'1','RAYON_NUM_THREADS':'1','TEMP':str(D),'TMP':str(D)}
with (C/'msi-bundle.log').open('wb') as log:
 run=subprocess.run(['C:/Program Files/nodejs/node.exe',str(S/'node_modules/@tauri-apps/cli/tauri.js'),'bundle','--bundles','msi','--ci','--no-sign'],cwd=S/'apps/windows',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
assert run.returncode==0,(C/'msi-bundle.log').read_text(encoding='utf8',errors='replace')[-4500:]
require_frozen()
for name in ['companion-type.exe','companion_type_lib.dll']:assert sha(pair/name)==sha(target/'release'/name)
generated=list((target/'release/bundle/msi').glob('*0.1.78*x64*.msi'));assert len(generated)==1,generated
msi=C/'Companion-Windows-0.1.78-文件复制候选.msi';shutil.copy2(generated[0],msi)
inspection=C/'msi-inspection';inspection.mkdir(exist_ok=False)
dark=Path(os.environ['LOCALAPPDATA'])/'tauri/WixTools314/dark.exe'
run=subprocess.run([str(dark),'-x',str(inspection/'files'),'-o',str(inspection/'installer.wxs'),str(msi)],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
(inspection/'decompile.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0
files=[p for p in (inspection/'files').rglob('*') if p.is_file()]
raw=(pair/'companion-type.exe').read_bytes();assert raw.count(b'__TAURI_BUNDLE_TYPE_VAR_UNK')==1
expected=raw.replace(b'__TAURI_BUNDLE_TYPE_VAR_UNK',b'__TAURI_BUNDLE_TYPE_VAR_MSI')
exe=next(p for p in files if p.stat().st_size==len(expected) and p.read_bytes()==expected)
dll=next(p for p in files if p.stat().st_size==(pair/'companion_type_lib.dll').stat().st_size and sha(p)==sha(pair/'companion_type_lib.dll'))
hashes={sha(p) for p in files};licenses=[p for p in (S/'apps/windows/src-tauri/resources/licenses').rglob('*') if p.is_file()]
assert all(sha(p) in hashes for p in licenses)
db=msilib.OpenDatabase(str(msi),msilib.MSIDBOPEN_READONLY)
def rows(sql,n):
 view=db.OpenView(sql);view.Execute(None);result=[]
 while True:
  item=view.Fetch()
  if not item:return result
  result.append([item.GetString(i) for i in range(1,n+1)])
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='ProductVersion'",1)==[['0.1.78']]
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='UpgradeCode'",1)==[['{62662888-B24B-54F1-B21F-623BE6017A26}']]
up=rows('SELECT `VersionMin`,`VersionMax`,`ActionProperty` FROM `Upgrade`',3);conditions=rows('SELECT `Condition`,`Description` FROM `LaunchCondition`',2)
assert any(row[0]=='0.1.78' and row[2]=='WIX_DOWNGRADE_DETECTED' for row in up)
assert any(row[1]=='0.1.78' and row[2]=='WIX_UPGRADE_DETECTED' for row in up)
assert any(row[0]=='NOT WIX_DOWNGRADE_DETECTED' for row in conditions)
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'WINDOWS078_MATCHING_PRIVATE_NATIVE_MSI_VERIFIED','version':'0.1.78','sourceCommit':frozen['sourceCommit'],'msi':str(msi),'msiSha256':sha(msi),'embeddedExeSha256':sha(exe),'dllSha256':sha(dll),'licenseFilesMatched':len(licenses),'sameUpgradeIdentity':True,'newerVersionGuard':True,'nativeProfile':'normal release; only process resource limits changed','privateBundleTarget':str(target),'installed':False,'ordinaryThirdPartyPasteQualified':False,'oldWinRTSharePickerFixed':False,'wholeProductQualified':False,'modelsRun':False}
(C/'windows-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
