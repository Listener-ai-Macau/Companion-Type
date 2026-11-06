from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess,os,json,hashlib,shutil,msilib
root=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=root/'companion-device-closure055';out=root/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows060-word062';cache=Path('E:/CodexData/Companion/.build-cache/windows051');target=cache/'target'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((out/'cargo-release.json').read_text())['exitCode']==0
frozen=json.loads((out/'source-frozen.json').read_text(encoding='utf8'))
for row in frozen['sourceFiles']:assert sha(s/row['path'])==row['sha256'],row['path']
for row in frozen['windowsWebAssets']:assert sha(s/'apps/windows/dist'/row['path'])==row['sha256'],row['path']
binary=out/'windows-bin';binary.mkdir(exist_ok=True)
for name in ['companion-type.exe','companion_type_lib.dll']:
    assert (target/'release'/name).exists(),name;shutil.copy2(target/'release'/name,binary/name)
env=os.environ.copy();env.update(CARGO_TARGET_DIR=str(target),CARGO_BUILD_JOBS='1',RAYON_NUM_THREADS='2',TEMP=str(cache),TMP=str(cache))
check=subprocess.run([os.sys.executable,str(root/'tools/check_type_build_target.py'),'--target-dir',str(target),'--project',str(s/'apps/windows/src-tauri'),'--source-dir',str(s),'--artifact-dir',str(binary)],capture_output=True,text=True,encoding='utf8',errors='replace')
(out/'bundle-preflight.json').write_text(check.stdout,encoding='utf8');assert check.returncode==0,check.stdout+check.stderr
with (out/'msi-bundle.log').open('wb') as log:
 r=subprocess.run(['C:/Program Files/nodejs/node.exe',str(s/'node_modules/@tauri-apps/cli/tauri.js'),'bundle','--bundles','msi','--ci','--no-sign'],cwd=s/'apps/windows',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
assert r.returncode==0,(out/'msi-bundle.log').read_text(encoding='utf8',errors='replace')[-4500:]
generated=list((target/'release/bundle/msi').glob('*0.1.60*x64*.msi'));assert len(generated)==1,generated
msi=out/'Companion-Windows-0.1.60-录音与Word兼容修复.msi';shutil.copy2(generated[0],msi)
inspection=out/'msi-inspection';inspection.mkdir(exist_ok=False)
dark=Path(os.environ['LOCALAPPDATA'])/'tauri/WixTools314/dark.exe'
run=subprocess.run([str(dark),'-x',str(inspection/'files'),'-o',str(inspection/'installer.wxs'),str(msi)],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
(inspection/'decompile.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0
files=[p for p in (inspection/'files').rglob('*') if p.is_file()]
raw=(binary/'companion-type.exe').read_bytes();assert raw.count(b'__TAURI_BUNDLE_TYPE_VAR_UNK')==1
expected=raw.replace(b'__TAURI_BUNDLE_TYPE_VAR_UNK',b'__TAURI_BUNDLE_TYPE_VAR_MSI')
exe=next(p for p in files if p.stat().st_size==len(expected) and p.read_bytes()==expected)
dll=next(p for p in files if p.stat().st_size==(binary/'companion_type_lib.dll').stat().st_size and sha(p)==sha(binary/'companion_type_lib.dll'))
hashes={sha(p) for p in files}
licenses=[p for p in (s/'apps/windows/src-tauri/resources/licenses').rglob('*') if p.is_file()]
assert all(sha(p) in hashes for p in licenses),'A corresponding-source/license file is missing from MSI'
db=msilib.OpenDatabase(str(msi),msilib.MSIDBOPEN_READONLY)
def rows(sql,n):
 view=db.OpenView(sql);view.Execute(None);result=[]
 while True:
  item=view.Fetch()
  if not item:return result
  result.append([item.GetString(i) for i in range(1,n+1)])
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='ProductVersion'",1)==[['0.1.60']]
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='UpgradeCode'",1)==[['{62662888-B24B-54F1-B21F-623BE6017A26}']]
up=rows('SELECT `VersionMin`,`VersionMax`,`ActionProperty` FROM `Upgrade`',3);conditions=rows('SELECT `Condition`,`Description` FROM `LaunchCondition`',2)
assert any(row[0]=='0.1.60' and row[2]=='WIX_DOWNGRADE_DETECTED' for row in up)
assert any(row[1]=='0.1.60' and row[2]=='WIX_UPGRADE_DETECTED' for row in up)
assert any(row[0]=='NOT WIX_DOWNGRADE_DETECTED' for row in conditions)
result={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'status':'WINDOWS060_WORD062_MSI_SOURCE_PAYLOAD_AND_UPGRADE_VERIFIED','version':'0.1.60','sourceCommit':frozen['sourceCommit'],'msi':str(msi),'msiSha256':sha(msi),'embeddedExeSha256':sha(exe),'dllSha256':sha(dll),'licenseFilesMatched':len(licenses),'sameUpgradeIdentity':True,'newerVersionGuard':True,'installed':False,'modelsRun':False,'ordinarySaveAsShareVerified':False,'wholeProductQualified':False}
(out/'windows-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
