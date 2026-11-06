from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess,json,re
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');b=r/'docs/handoffs/20261106-device-phone-closure055';c=Path('E:/CodexData/Companion/.build-cache/device-phone055');adb=r/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';serial='6LCAPVHE9PBE45DU';prefix=[str(adb),'-s',serial];pkg='com.denzic.companion.app'
def call(args,timeout=90):return subprocess.run(prefix+args,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
def text(args,timeout=90):
 p=call(args,timeout);assert p.returncode==0,p.stderr.decode('utf8',errors='replace');return p.stdout.decode('utf8',errors='replace')
def focus():return [x.strip() for x in text(['shell','dumpsys','activity','activities']).splitlines() if 'topResumedActivity=' in x or 'ResumedActivity:' in x]
old=json.loads((c/'owner-file-hashes-before.json').read_text(encoding='utf8'));new=json.loads((c/'owner-file-hashes-after.json').read_text(encoding='utf8'));assert old and all(new.get(n)==v for n,v in old.items())
ap=json.loads((b/'apk-verification.json').read_text(encoding='utf8'));paths=text(['shell','pm','path',pkg]).strip().splitlines();assert len(paths)==1;path=paths[0].removeprefix('package:');digest=text(['shell','sha256sum',path]).split()[0];assert digest==ap['sha256']
version=[x.strip() for x in text(['shell','dumpsys','package',pkg]).splitlines() if 'versionName=' in x or 'versionCode=' in x];assert any('versionName=0.1.55' in x for x in version)
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'phoneSerial':serial,'mainInstalled':True,'installedVersion':version,'mainApkSha256':digest,'mainApkExactInstalledBytes':True,'originalFileCount':len(old),'originalFilesByteIdentical':True,'newFileCount':len(new)-len(old),'privateFileHashesRetainedLocallyOnly':True,'mainAppUiStarted':False,'boardUsed':False,'modelsRun':False,'previousVersion':'Not persisted by the first harness; latest previous observation053 is historical only'}
(b/'phone-main-install-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
previous=b/'phone-native-qa.log'
if previous.exists() and not (b/'phone-native-qa-harness-start-failure.log').exists():previous.rename(b/'phone-native-qa-harness-start-failure.log')
qa=json.loads((b/'phone-qa-build.json').read_text());installed=False;before=focus()
try:
 p=call(['install','-t',qa['apk']],timeout=120);out=(p.stdout+p.stderr).decode('utf8',errors='replace');(b/'phone-qa-install-final.log').write_text(out,encoding='utf8');assert p.returncode==0 and 'Success' in out,out;installed=True
 out=text(['shell','am','instrument','-w',qa['package']+'/com.denzic.companion.app.DeviceClosureInstrumentation'],timeout=45);(b/'phone-native-qa.log').write_text(out,encoding='utf8');assert 'PASS_ANDROID_NATIVE_PACKAGE_AND_INTERRUPTION_STATE_ONLY' in out and 'INSTRUMENTATION_CODE: -1' in out,out;record['nativeQa']='PASS_ANDROID_NATIVE_PACKAGE_AND_INTERRUPTION_STATE_ONLY'
finally:
 if installed:record['ownQaPackageRemoved']='Success' in text(['uninstall',qa['package']])
record['foregroundBefore']=before;record['foregroundAfter']=focus();record['observedResumedActivitySame']=bool(before) and before==record['foregroundAfter'];record['foregroundObservationScope']='Actual resumed records immediately around final no-Activity QA only, not an all-session foreground claim.'
record['firstQaFailure']='Harness initially omitted Instrumentation.start() so onStart did not run; own QA process stopped and package removed. No product Bluetooth/service/Activity action ran; actual first failure retained.'
record['remaining']=['Ordinary main App real system pairing/list/select receive/delete/maintenance','Main App SAF save and real share recipient grant','Physical Android OTA, background/disconnect and process recovery; native state checks are not these passes']
(b/'phone-native-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in record.items() if not k.startswith('foreground')},ensure_ascii=False))
