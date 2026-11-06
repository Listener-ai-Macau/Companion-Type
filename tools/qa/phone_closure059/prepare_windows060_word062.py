from pathlib import Path
import hashlib,json,subprocess,tomllib,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'companion-device-closure055'
P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12'
F=P/'windows060-word062';F.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=tomllib.loads((R/'recovered-software050/apps/windows/src-tauri/Cargo.lock').read_text(encoding='utf8'))
new=tomllib.loads((S/'apps/windows/src-tauri/Cargo.lock').read_text(encoding='utf8'))
for lock in [old,new]:
    for package in lock['package']:
        if package['name']=='companion-type':package['version']='APP_VERSION_ONLY'
assert old==new,'Inspect real third-party dependency change before refreshing inventory'
path=S/'apps/windows/src-tauri/resources/licenses/ThirdPartyComponents.json'
data=json.loads(path.read_text(encoding='utf8'))
old_bytes=path.read_bytes();(F/'license-inventory-before.json').write_bytes(old_bytes)
changes=[]
for name,digest in data['lockedInputs'].items():
    actual=sha(S/name)
    if digest!=actual:changes.append({'path':name,'before':digest,'after':actual})
    data['lockedInputs'][name]=actual
for package in data.get('localCompanyInputs',[]):
    if package.get('name')=='companion-type':package['version']='0.1.60'
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
receipt={'externalCargoDependenciesUnchangedFrom052':True,'changedInputDigests':changes,
    'scope':'Local product version inventory refreshed for actual committed060 Windows source; no external package/license substitution.'}
(F/'license-refresh.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
candidate=P/'word062/apk62-verification.json';prior=candidate.read_bytes()
(P/'word062/apk62-verification-original-packaging-only-native-flag.json').write_bytes(prior)
value=json.loads(prior);value['nativeRebuilt']=True;value['nativeRebuiltByApkBuildStep']=False
value['nativeRebuildReceipt']='native-word062.json'
value['receiptCorrection']='Original generic APK packager hardcoded nativeRebuilt=false. Native source was actually rebuilt upstream in92.641sec; this packaging step reused that rebuilt library. Original receipt retained.'
candidate.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(receipt,ensure_ascii=False))
