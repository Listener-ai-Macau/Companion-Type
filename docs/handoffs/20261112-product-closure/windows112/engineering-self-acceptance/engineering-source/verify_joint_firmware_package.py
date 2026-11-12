"""Validate a selected normal CUP using the exact installed111 offline command."""
from pathlib import Path
from datetime import datetime
import json,hashlib,subprocess,os,sys,re
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');windows_batch=sys.argv[2] if len(sys.argv)>2 else 'windows111';assert re.fullmatch(r'windows\d+',windows_batch);batch=r/'docs/handoffs/20261112-product-closure'/windows_batch;version=int(sys.argv[1]);assert 66815<=version<67000
out=Path('E:/CodexData/Companion/.build-cache/product-closure20261112')/windows_batch/('offline-validator-fw'+str(version));out.mkdir(exist_ok=False)
sys.path.insert(0,str(r/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(5,384*1024**2)
proof=json.loads((batch/'windows-verification.json').read_bytes());installed=Path('C:/Program Files/Companion Type');manifest=Path('E:/CodexData/Companion/.build-cache/imu-pointer20261112')/('fw'+str(version)+'-package/ota_manifest.json')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert proof['version']=='0.1.'+windows_batch.removeprefix('windows') and sha(installed/'companion-type.exe')==proof['embeddedExeSha256'] and sha(installed/'companion_type_lib.dll')==proof['dllSha256']
for name in ['roaming','local','temp','recordings']:(out/name).mkdir()
env={**os.environ,'APPDATA':str(out/'roaming'),'LOCALAPPDATA':str(out/'local'),'TEMP':str(out/'temp'),'TMP':str(out/'temp'),'COMPANION_TYPE_STATE_PATH':str(out/'sessions.json'),'COMPANION_TYPE_RECORDING_DIR':str(out/'recordings'),'COMPANION_TYPE_PRODUCT_SETTINGS_PATH':str(out/'settings.json'),'COMPANION_TYPE_DISABLE_AUTO_RECOVERY':'1','COMPANION_TYPE_DISABLE_AUTO_RECONNECT':'1','COMPANION_TYPE_BLE_NATIVE_DISABLED':'1'}
result=subprocess.run([str(installed/'companion-type.exe'),'--system-ota-validate',str(manifest)],env=env,capture_output=True,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW);(out/'stdout.log').write_bytes(result.stdout);(out/'stderr.log').write_bytes(result.stderr);assert result.returncode==0,result.stderr.decode(errors='replace')[-1400:]
payload=json.loads(next(x.split('=',1)[1] for x in result.stdout.decode('utf-8').splitlines() if x.startswith('resource_ota_validate_json=')));assert payload['status']=='PASS'
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'INSTALLED'+windows_batch.removeprefix('windows')+'_OFFLINE_VALIDATOR_ACCEPTED_SELECTED_SIGNED_NORMAL_PACKAGE','windowsVersion':proof['version'],'sourceCommit':proof['sourceCommit'],'firmware':version,'manifestSha256':sha(manifest),'validation':payload,'boardAccessed':False,'transferCommands':0,'hostMicCommands':0,'modelsRun':False,'ownerPrivateLibraryRead':False,'residentBootStillAuthenticatesActualSignature':True,'physicalTotalAcceptancePassed':False}
for p in [out/'result.json',batch/('offline-validator-fw'+str(version)+'.json')]:p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='validation'},ensure_ascii=False))
