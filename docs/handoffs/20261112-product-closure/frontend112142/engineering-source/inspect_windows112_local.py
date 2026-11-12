from pathlib import Path
from datetime import datetime
import json,subprocess,shutil,msilib,sys
sys.path.insert(0,str(Path(__file__).parent));from windows_candidate_delivery import blobs,sha,write
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=Path('E:/CodexData/Companion/.build-cache/frozen-windows-delivery-source');cache=Path('E:/CodexData/Companion/.build-cache/product-closure20261112/windows112');build=cache.parent/'windows112-local-r2';batch=r/'docs/handoffs/20261112-product-closure/windows112';batch.mkdir(exist_ok=True);cache.mkdir(exist_ok=True)
receipt=json.loads((build/'result.json').read_bytes());assert receipt['state']=='LOCAL_WINDOWS_CANDIDATE_BUILT_PAYLOAD_INSPECTION_PENDING' and receipt['version']=='0.1.112';assert receipt['normalReleaseOptimization'] and receipt['nativeAndWebUnchangedAfterBundle'] and receipt['hostedCiRun'] is None
assert not (batch/'windows-verification.json').exists()
prefix='third_party/denzic-platform/';own=[x for x in receipt['sourceFiles'] if not x['path'].startswith(prefix)];platform=[x for x in receipt['sourceFiles'] if x['path'].startswith(prefix)]
eol=blobs(own,s,receipt['sourceCommit'])+blobs(platform,s/'third_party/denzic-platform',receipt['platformCommit'],prefix)
for item in receipt['nativeFiles']:assert sha(build/'windows-bin'/item['path'])==item['sha256']
msi=Path(receipt['msi']);assert sha(msi)==receipt['msiSha256'];extraction=cache/'msi-inspection';extraction.mkdir(exist_ok=False)
dark=Path('C:/Users/Billy/AppData/Local/tauri/WixTools314/dark.exe')
with (extraction/'decompile.log').open('wb') as log:result=subprocess.run([str(dark),'-x',str(extraction/'files'),'-o',str(extraction/'installer.wxs'),str(msi)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
assert result.returncode==0
hashes={sha(p):p for p in (extraction/'files').rglob('*') if p.is_file()}
assert receipt['expectedEmbeddedExeSha256'] in hashes and receipt['expectedDllSha256'] in hashes
for item in receipt['licenseFiles']:assert item['sha256'] in hashes,item['path']
db=msilib.OpenDatabase(str(msi),msilib.MSIDBOPEN_READONLY)
def rows(query,count):
 v=db.OpenView(query);v.Execute(None);result=[]
 while True:
  row=v.Fetch()
  if not row:return result
  result.append([row.GetString(i) for i in range(1,count+1)])
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='ProductVersion'",1)==[['0.1.112']]
assert rows("SELECT `Value` FROM `Property` WHERE `Property`='UpgradeCode'",1)==[['{62662888-B24B-54F1-B21F-623BE6017A26}']]
upgrades=rows('SELECT `VersionMin`,`VersionMax`,`ActionProperty` FROM `Upgrade`',3);assert any(x[0]=='0.1.112' and x[2]=='WIX_DOWNGRADE_DETECTED' for x in upgrades) and any(x[1]=='0.1.112' and x[2]=='WIX_UPGRADE_DETECTED' for x in upgrades)
assert any(x[0]=='NOT WIX_DOWNGRADE_DETECTED' for x in rows('SELECT `Condition`,`Description` FROM `LaunchCondition`',2))
native=cache/'frozen-msi-native';native.mkdir(exist_ok=False)
for digest,name in [(receipt['expectedEmbeddedExeSha256'],'companion-type.exe'),(receipt['expectedDllSha256'],'companion_type_lib.dll')]:shutil.copyfile(hashes[digest],native/name)
proof=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='WINDOWS112_LOCAL_SOURCE_MSI_PAYLOAD_LICENSES_AND_UPGRADE_VERIFIED',version='0.1.112',sourceCommit=receipt['sourceCommit'],artifactSourceCommit=receipt['sourceCommit'],msi=str(msi),msiSha256=receipt['msiSha256'],embeddedExeSha256=receipt['expectedEmbeddedExeSha256'],dllSha256=receipt['expectedDllSha256'],licenseFilesMatched=len(receipt['licenseFiles']),sourceFilesMatched=len(receipt['sourceFiles']),sourceCheckoutEolOnly=eol,sourceBinding='Independently matched exact committed blobs or identical checkout EOL; compiled normal local release',sameUpgradeIdentity=True,newerVersionGuard=True,sourceAndNativeFrozenTogether=True,localBuildSourceAndNativeFrozenTogether=True,ciSourceAndNativeFrozenTogether=False,ciRunId=None,ciWrapperOverallPassed=False,nativeRoot=str(native),frozenSourceRoot=str(s),sourceProtectedBranch='work/ui-usability112-frozen-20261112',installed=False,modelsRun=False,wholeCoreCandidateQualified=False,saleQualified=False)
write(batch/'windows-verification.json',proof);write(batch/'frozen-source.json',dict(version='0.1.112',sourceCommit=receipt['sourceCommit'],buildKind='normal local release',buildReceipt=str(build/'result.json')))
# Tauri's permitted manifest EOL rewrite is not a pending product repair.
manifest=s/'apps/windows/src-tauri/Cargo.toml';committed=subprocess.check_output(['git','show',receipt['sourceCommit']+':apps/windows/src-tauri/Cargo.toml'],cwd=s);assert manifest.read_bytes().replace(b'\r\n',b'\n')==committed.replace(b'\r\n',b'\n');manifest.write_bytes(committed)
print(json.dumps({k:v for k,v in proof.items() if k not in ['sourceCheckoutEolOnly']},ensure_ascii=False))
