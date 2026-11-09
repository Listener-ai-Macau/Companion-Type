"""Inspect downloaded CI package before any installation; no product data IO."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess,os,json,hashlib,shutil,msilib
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
C=R/'docs/handoffs/20261109-windows-file-copy078';A=C/'ci-artifact'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
receipt=json.loads((A/'result.json').read_text(encoding='utf8'));expected=json.loads((C/'ci-current.json').read_text())
recovery=None
if receipt['state']=='CI_BUILD_FAILED_RETAINED':
 recovery=json.loads((C/'bundle-recovery.json').read_text(encoding='utf8'))
 assert receipt['error']=='AssertionError()' and recovery['ciSourceCommit']==receipt['sourceCommit']
 assert recovery['ciExactWebAssetsMatched'] and recovery['ciExactNativePairUnchanged'] and not recovery['nativeRecompiled']
 assert len(recovery['sourceChanges'])==1
 change=recovery['sourceChanges'][0]
 assert change['path']=='apps/windows/src-tauri/Cargo.toml' and change['onlyLineEndings'] and change['tomlSemanticallyIdentical']
 assert change['beforeSha256']==next(row['sha256'] for row in receipt['sourceFiles'] if row['path']==change['path'])
 assert 'Finished `release` profile [optimized]' in (A/'cargo-release.log').read_text(encoding='utf8')
 raw=(A/'windows-bin/companion-type.exe').read_bytes();assert raw.count(b'__TAURI_BUNDLE_TYPE_VAR_UNK')==1
 receipt['expectedEmbeddedExeSha256']=hashlib.sha256(raw.replace(b'__TAURI_BUNDLE_TYPE_VAR_UNK',b'__TAURI_BUNDLE_TYPE_VAR_MSI')).hexdigest()
 receipt['expectedDllSha256']=sha(A/'windows-bin/companion_type_lib.dll')
 resources=Path(recovery['privateSource'])/'apps/windows/src-tauri/resources'
 receipt['licenseFiles']=[{'path':p.relative_to(resources).as_posix(),'sha256':sha(p)} for p in (resources/'licenses').rglob('*') if p.is_file()]
 receipt['licenseFiles'].append({'path':'opus-license.txt','sha256':sha(resources/'opus-license.txt')})
else:
 assert receipt['state']=='CI_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING'
 assert receipt['normalReleaseOptimization'] and receipt['nativeAndWebUnchangedAfterBundle']
assert receipt['version']=='0.1.78' and receipt['sourceCommit']==expected['sourceCommit']
assert receipt['platformCommit']=='6f30ab5888e3f603084d71359f3099ab5b8f66fc'
# Source changes made by another session cannot silently inherit this receipt.
equivalent=[]
for row in receipt['sourceFiles']:
 p=S/row['path'];assert p.is_file(),row['path'];raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=row['sha256']:
  variants=[raw.replace(b'\r\n',b'\n'),raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
  assert any(hashlib.sha256(v).hexdigest()==row['sha256'] for v in variants),row['path']
  equivalent.append(row['path'])
for row in receipt['nativeFiles']:assert sha(A/'windows-bin'/row['path'])==row['sha256']
msi=C/'Companion-Windows-0.1.78-文件复制候选.msi'
if recovery:assert sha(msi)==recovery['msiSha256']
else:
 origin=A/receipt['msi'];assert sha(origin)==receipt['msiSha256'];shutil.copy2(origin,msi)
inspection=C/'msi-inspection';inspection.mkdir(exist_ok=False)
dark=Path(os.environ['LOCALAPPDATA'])/'tauri/WixTools314/dark.exe'
run=subprocess.run([str(dark),'-x',str(inspection/'files'),'-o',str(inspection/'installer.wxs'),str(msi)],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
(inspection/'decompile.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0
files=[p for p in (inspection/'files').rglob('*') if p.is_file()];hashes={sha(p) for p in files}
assert receipt['expectedEmbeddedExeSha256'] in hashes
assert receipt['expectedDllSha256'] in hashes
for row in receipt['licenseFiles']:assert row['sha256'] in hashes,row['path']
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
web_match=[]
for row in receipt['webAssets']:
 p=S/'apps/windows/dist'/row['path'];web_match.append(p.is_file() and sha(p)==row['sha256'])
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'WINDOWS078_CI_NATIVE_PRIVATE_MSI_SOURCE_PAYLOAD_AND_UPGRADE_VERIFIED','version':'0.1.78','sourceCommit':receipt['sourceCommit'],'msi':str(msi),'msiSha256':sha(msi),'embeddedExeSha256':receipt['expectedEmbeddedExeSha256'],'dllSha256':receipt['expectedDllSha256'],'licenseFilesMatched':len(receipt['licenseFiles']),'sourceFilesMatched':len(receipt['sourceFiles']),'sourceFilesWithOnlyCheckoutEolDifference':equivalent,'sameUpgradeIdentity':True,'newerVersionGuard':True,'localAndCIWebAssetsByteIdentical':all(web_match),'ciSourceAndNativeFrozenTogether':True,'nativeProfile':'normal release on clean dedicated Windows runner','ciRunId':expected['runId'],'recoveredAfterCiSourceEolGuard':bool(recovery),'ciWrapperOverallPassed':not bool(recovery),'sourceSemanticsChangedByBundle':False,'installed':False,'ordinaryThirdPartyPasteQualified':False,'oldWinRTSharePickerFixed':False,'wholeProductQualified':False,'modelsRun':False}
(C/'windows-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in record.items() if k!='sourceFilesWithOnlyCheckoutEolDifference'},ensure_ascii=False))
