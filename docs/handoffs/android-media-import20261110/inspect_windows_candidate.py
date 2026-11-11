"""Independently inspect the exact grouped MSI before runtime or installation."""
from pathlib import Path
from datetime import datetime
import hashlib,json,msilib,os,re,shutil,subprocess,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
code=sys.argv[1];assert re.fullmatch(r'\d{3}',code) and int(code)>=100;version='0.1.'+str(int(code))
C=R/'docs/handoffs/20261110-android-media-import'/('windows'+code);D=Path('E:/CodexData/Companion/.build-cache/windows-note-context20261110')
freeze=json.loads((C/'source-freeze.json').read_text(encoding='utf8'));A=D/('ci-artifact'+code)/freeze.get('artifactSourceCommit',freeze['sourceCommit']);run_id=freeze['buildRun']
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
subprocess.run([sys.executable,str(C.parent/'download_windows_candidate.py'),code,str(run_id)],check=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
receipt=json.loads((A/'result.json').read_text(encoding='utf8'));freeze=json.loads((C/'source-freeze.json').read_text(encoding='utf8'))
assert receipt['state']=='CI_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING'
assert receipt['normalReleaseOptimization'] and receipt['nativeAndWebUnchangedAfterBundle']
assert receipt['version']==version and receipt['sourceCommit']==freeze['sourceCommit']
assert receipt['platformCommit']=='6f30ab5888e3f603084d71359f3099ab5b8f66fc'
equivalent=[]
for row in receipt['sourceFiles']:
 p=S/row['path'];raw=p.read_bytes()
 if row['path']=='apps/windows/src-tauri/windows-open-with.wxs' and receipt.get('packagingOnlyInputChanges'):
  change=receipt['packagingOnlyInputChanges'][0];assert len(receipt['packagingOnlyInputChanges'])==1 and change['path']==row['path'] and change['oldSha256']==row['sha256'];assert change['newSha256'] in [hashlib.sha256(v).hexdigest() for v in [raw,raw.replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]];continue
 if hashlib.sha256(raw).hexdigest()!=row['sha256']:
  variants=[raw.replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
  assert any(hashlib.sha256(v).hexdigest()==row['sha256'] for v in variants),row['path']
  equivalent.append(row['path'])
for row in receipt['nativeFiles']:assert sha(A/'windows-bin'/row['path'])==row['sha256']
origin=A/receipt['msi'];assert sha(origin)==receipt['msiSha256']
msi=C/('Companion-Windows-'+version+'-candidate.msi');shutil.copy2(origin,msi)
inspection=D/('msi-inspection'+code);inspection.mkdir(exist_ok=False)
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
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='ProductVersion'",1)==[[version]]
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='UpgradeCode'",1)==[['{62662888-B24B-54F1-B21F-623BE6017A26}']]
up=rows('SELECT `VersionMin`,`VersionMax`,`ActionProperty` FROM `Upgrade`',3)
assert any(row[0]==version and row[2]=='WIX_DOWNGRADE_DETECTED' for row in up)
assert any(row[1]==version and row[2]=='WIX_UPGRADE_DETECTED' for row in up)
assert any(row[0]=='NOT WIX_DOWNGRADE_DETECTED' for row in rows('SELECT `Condition`,`Description` FROM `LaunchCondition`',2))
# Inspect the shipped MSI's actual registration, not just the WXS source.
quote=chr(96);registration=rows('SELECT '+','.join(quote+n+quote for n in ['Root','Key','Name','Value','Component_'])+' FROM '+quote+'Registry'+quote,5)
ours=[row for row in registration if row[4]=='CompanionOpenWith']
assert len(ours)==20,ours
assert all(row[0]=='1' and row[1].lower().startswith(r'software\classes\applications\companion-type.exe') for row in ours)
assert {row[2] for row in ours if row[1].lower().endswith(r'\supportedtypes')}=={'.'+v for v in ['wav','mp3','m4a','mp4','aac','flac','ogg','pdf','docx','xlsx','pptx','txt','md','csv','jpg','jpeg','png','webp']}
assert [row[3] for row in ours if row[1].lower().endswith(r'\shell\open\command')]==['"[INSTALLDIR]companion-type.exe" "%1"']
assert not any('userchoice' in row[1].lower() for row in registration)
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'WINDOWS'+code+'_CI_SOURCE_MSI_PAYLOAD_LICENSES_AND_UPGRADE_VERIFIED','version':version,'sourceCommit':receipt['sourceCommit'],'artifactSourceCommit':receipt.get('artifactSourceCommit',receipt['sourceCommit']),'packagingSourceCommit':receipt.get('packagingSourceCommit',receipt['sourceCommit']),'nativeBuildRun':receipt.get('nativeBuildRun',run_id),'packagingOnlyInputChanges':receipt.get('packagingOnlyInputChanges',[]),'msi':str(msi),'msiSha256':sha(msi),'embeddedExeSha256':receipt['expectedEmbeddedExeSha256'],'dllSha256':receipt['expectedDllSha256'],'licenseFilesMatched':len(receipt['licenseFiles']),'sourceFilesMatched':len(receipt['sourceFiles'])-len(receipt.get('packagingOnlyInputChanges',[])),'sourceFilesWithOnlyCheckoutEolDifference':equivalent,'sameUpgradeIdentity':True,'newerVersionGuard':True,'ciSourceAndNativeFrozenTogether':not bool(receipt.get('packagingOnlyInputChanges')),'nativeAndWebFrozenAtOriginalBuild':True,'packagingSourceIndependentlyBound':bool(receipt.get('packagingOnlyInputChanges')),'nativeProfile':'normal release on dedicated Windows runner','ciRunId':run_id,'ciWrapperOverallPassed':True,'localHeavyBuild':False,'openWithOnlyRegistrationVerified':True,'defaultAssociationOrUserChoiceWritten':False,'installed':False,'wholeCoreCandidateQualified':False,'oldWinRTSharePickerFixed':False,'saleQualified':False,'modelsRun':False,'inspectionLimits':limits.query()}
(C/'windows-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
fixture=S/'tools/qa/core_acceptance20261109/fixtures/document-context/manifest.json'
spec={'buildRun':run_id,'verification':record,'documentFixtureManifest':fixture.relative_to(S).as_posix(),'documentFixtureManifestSha256':sha(fixture)}
(C/'runtime-spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
dest=S/'docs/handoffs/android-media-import20261110'/('windows'+code);dest.mkdir(parents=True,exist_ok=True)
for p in [C/'windows-verification.json',C/'runtime-spec.json',C/'source-freeze.json',Path(__file__)]:shutil.copyfile(p,dest/p.name)
print(json.dumps({k:v for k,v in record.items() if k not in ['sourceFilesWithOnlyCheckoutEolDifference','inspectionLimits']},ensure_ascii=False))
