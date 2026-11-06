from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess,json,re,time,hashlib
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');b=r/'docs/handoffs/20261106-device-phone-closure055';c=Path('E:/CodexData/Companion/.build-cache/device-phone055');adb=r/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';serial='6LCAPVHE9PBE45DU';prefix=[str(adb),'-s',serial];pkg='com.denzic.companion.app'
def call(args,timeout=90):return subprocess.run(prefix+args,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
def text(args,timeout=90):
 p=call(args,timeout);assert p.returncode==0,p.stderr.decode('utf8',errors='replace');return p.stdout.decode('utf8',errors='replace')
def foreground():
 t=text(['shell','dumpsys','activity','activities']);return [line.strip() for line in t.splitlines() if 'topResumedActivity=' in line or 'ResumedActivity:' in line]
def version():
 t=text(['shell','dumpsys','package',pkg]);return [line.strip() for line in t.splitlines() if 'versionName=' in line or 'versionCode=' in line]
def snapshot(label):
 # Only hash app-private files; no decoding, copying or uploading recording payloads.
 command="run-as "+pkg+" sh -c 'find files -type f -exec sha256sum {} \\;'"
 value=text(['shell',command],timeout=180)
 rows={}
 for line in value.splitlines():
  m=re.match(r'^([0-9a-f]{64})\s+(.+)$',line);assert m,line;rows[m.group(2)]=m.group(1)
 assert rows,'No files were measured';(c/('owner-file-hashes-'+label+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');return rows
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'phoneSerial':serial,'mainAppUiStarted':False,'boardUsed':False,'modelsRun':False}
assert text(['get-state']).strip()=='device'
before=foreground();record['beforeVersion']=version();old=snapshot('before');ap=json.loads((b/'apk-verification.json').read_text());assert hashlib.sha256(Path(ap['apk']).read_bytes()).hexdigest()==ap['sha256']
p=call(['install','-r','-t',ap['apk']],timeout=120);output=(p.stdout+p.stderr).decode('utf8',errors='replace');(b/'phone-main-install.log').write_text(output,encoding='utf8');assert p.returncode==0 and 'Success' in output,output
record['afterVersion']=version();assert any('versionName=0.1.55' in x for x in record['afterVersion']);new=snapshot('after');changed=[name for name,digest in old.items() if new.get(name)!=digest];assert not changed,'Original private app files changed: '+repr(changed[:3]);record.update(mainInstalled=True,mainApkSha256=ap['sha256'],originalFileCount=len(old),originalFilesByteIdentical=True,newFileCount=len(new)-len(old),ownerArchiveNotCreated=True)
qa=json.loads((b/'phone-qa-build.json').read_text());installed=False
try:
 p=call(['install','-t',qa['apk']],timeout=120);output=(p.stdout+p.stderr).decode('utf8',errors='replace');(b/'phone-qa-install.log').write_text(output,encoding='utf8');assert p.returncode==0 and 'Success' in output,output;installed=True
 result=text(['shell','am','instrument','-w',qa['package']+'/com.denzic.companion.app.DeviceClosureInstrumentation'],timeout=90);(b/'phone-native-qa.log').write_text(result,encoding='utf8');assert 'PASS_ANDROID_NATIVE_PACKAGE_AND_INTERRUPTION_STATE_ONLY' in result and 'INSTRUMENTATION_CODE: -1' in result,result
 record['nativeQa']='PASS_ANDROID_NATIVE_PACKAGE_AND_INTERRUPTION_STATE_ONLY'
finally:
 if installed:record['ownQaPackageRemoved']='Success' in text(['uninstall',qa['package']])
record['foregroundBefore']=before;record['foregroundAfter']=foreground();record['observedResumedActivitySame']=bool(before) and before==record['foregroundAfter'];record['foregroundObservationScope']='Actual dumpsys activity resumed records before/after only; no Activity launched by QA, no Windows or Android input injected.'
record['remaining']=['Ordinary main App system pairing/list/select receive/delete/maintenance path','Main App SAF save and actual share recipient grant','Physical Android OTA, background/disconnect and process recovery; native state checks are not these passes']
(b/'phone-native-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in record.items() if not k.startswith('foreground')},ensure_ascii=False))
