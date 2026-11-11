"""Independently inspect the exact grouped MSI before runtime or installation."""
from pathlib import Path
from datetime import datetime
import hashlib,json,msilib,os,shutil,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261110-android-media-import/windows095';D=Path('E:/CodexData/Companion/.build-cache/windows-note-context20261110')
A=next((D/'ci-artifact095').iterdir());run_id=42876404149
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
receipt=json.loads((A/'result.json').read_text(encoding='utf8'));freeze=json.loads((C/'source-freeze.json').read_text(encoding='utf8'))
assert receipt['state']=='CI_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING'
assert receipt['normalReleaseOptimization'] and receipt['nativeAndWebUnchangedAfterBundle']
assert receipt['version']=='0.1.95' and receipt['sourceCommit']==freeze['sourceCommit']
assert receipt['platformCommit']=='6f30ab5888e3f603084d71359f3099ab5b8f66fc'
equivalent=[]
for row in receipt['sourceFiles']:
 p=S/row['path'];raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=row['sha256']:
  variants=[raw.replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
  assert any(hashlib.sha256(v).hexdigest()==row['sha256'] for v in variants),row['path']
  equivalent.append(row['path'])
for row in receipt['nativeFiles']:assert sha(A/'windows-bin'/row['path'])==row['sha256']
origin=A/receipt['msi'];assert sha(origin)==receipt['msiSha256']
msi=C/'Companion-Windows-0.1.95-candidate.msi';shutil.copy2(origin,msi)
inspection=D/'msi-inspection095';inspection.mkdir(exist_ok=False)
dark=Path(os.environ['LOCALAPPDATA'])/'tauri/WixTools314/dark.exe'
with (inspection/'decompile.log').open('wb') as log:
 p=subprocess.run([str(dark),'-x',str(inspection/'files'),'-o',str(inspection/'installer.wxs'),str(msi)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
assert p.returncode==0,'Retain decompile.log; do not install'
files=[p for p in (inspection/'files').rglob('*') if p.is_file()];hashes={sha(p) for p in files}
assert receipt['expectedEmbeddedExeSha256'] in hashes and receipt['expectedDllSha256'] in hashes
for row in receipt['licenseFiles']:assert row['sha256'] in hashes,row['path']
db=msilib.OpenDatabase(str(msi),msilib.MSIDBOPEN_READONLY)
def rows(sql,n):
 view=db.OpenView(sql);view.Execute(None);result=[]
 while True:
  item=view.Fetch()
  if not item:return result
  result.append([item.GetString(i) for i in range(1,n+1)])
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='ProductVersion'",1)==[['0.1.95']]
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='UpgradeCode'",1)==[['{62662888-B24B-54F1-B21F-623BE6017A26}']]
up=rows('SELECT `VersionMin`,`VersionMax`,`ActionProperty` FROM `Upgrade`',3)
assert any(row[0]=='0.1.95' and row[2]=='WIX_DOWNGRADE_DETECTED' for row in up)
assert any(row[1]=='0.1.95' and row[2]=='WIX_UPGRADE_DETECTED' for row in up)
assert any(row[0]=='NOT WIX_DOWNGRADE_DETECTED' for row in rows('SELECT `Condition`,`Description` FROM `LaunchCondition`',2))
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'WINDOWS095_CI_SOURCE_MSI_PAYLOAD_LICENSES_AND_UPGRADE_VERIFIED','version':'0.1.95','sourceCommit':receipt['sourceCommit'],'msi':str(msi),'msiSha256':sha(msi),'embeddedExeSha256':receipt['expectedEmbeddedExeSha256'],'dllSha256':receipt['expectedDllSha256'],'licenseFilesMatched':len(receipt['licenseFiles']),'sourceFilesMatched':len(receipt['sourceFiles']),'sourceFilesWithOnlyCheckoutEolDifference':equivalent,'sameUpgradeIdentity':True,'newerVersionGuard':True,'ciSourceAndNativeFrozenTogether':True,'nativeProfile':'normal release on dedicated Windows runner','ciRunId':run_id,'ciWrapperOverallPassed':True,'localHeavyBuild':False,'installed':False,'wholeCoreCandidateQualified':False,'oldWinRTSharePickerFixed':False,'saleQualified':False,'modelsRun':False,'inspectionLimits':limits.query()}
(C/'windows-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
fixture=S/'tools/qa/core_acceptance20261109/fixtures/document-context/manifest.json'
spec={'buildRun':run_id,'verification':record,'documentFixtureManifest':fixture.relative_to(S).as_posix(),'documentFixtureManifestSha256':sha(fixture)}
(C/'runtime-spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
dest=S/'docs/handoffs/android-media-import20261110/windows095';dest.mkdir(parents=True,exist_ok=True)
for p in [C/'windows-verification.json',C/'runtime-spec.json',C/'source-freeze.json',Path(__file__)]:shutil.copyfile(p,dest/p.name)
print(json.dumps({k:v for k,v in record.items() if k not in ['sourceFilesWithOnlyCheckoutEolDifference','inspectionLimits']},ensure_ascii=False))
