from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess,json,re,hashlib,time
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');b=r/'docs/handoffs/20261106-android-material-exports054';adb=r/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe'
qa=json.loads((b/'phone-qa-build.json').read_text(encoding='utf8'));pkg=qa['package'];assert pkg=='com.denzic.companion.materialqa054' and qa['targetPackage']==pkg and qa['ownerAppTargeted'] is False
def call(args,timeout=40):
 p=subprocess.run([str(adb),*args],capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);return p
def text(args,timeout=40):
 p=call(args,timeout);assert p.returncode==0,p.stderr.decode('utf8',errors='replace');return p.stdout.decode('utf8',errors='replace')
devices=re.findall(r'^(\S+)\s+device\s*$',text(['devices']),re.M)
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'status':'NOT_RUN','ownerDataUsed':False,'ownerAppLaunched':False,'deviceBleIo':False,'modelInference':False,'separateNoActivityPackage':pkg}
if len(devices)!=1 or not devices[0].endswith('45DU'):
 record.update(status='NO_SINGLE_PREVIOUSLY_AUTHORIZED_PHONE_AVAILABLE',onlineDeviceCount=len(devices));(b/'phone-native-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False));raise SystemExit(0)
serial=devices[0];prefix=['-s',serial]
assert not text(prefix+['shell','pm','list','packages',pkg]).strip(),'Unexpected existing test package; refuse replacement'
def focus():
 s=text(prefix+['shell','dumpsys','window','windows']);m=re.search(r'mCurrentFocus=(.*)',s);return hashlib.sha256(m.group(1).encode()).hexdigest() if m else None
def version():
 s=text(prefix+['shell','dumpsys','package','com.denzic.companion.app']);return re.findall(r'version(?:Code|Name)=[^\r\n]*',s)
beforeFocus=focus();beforeVersion=version();installed=False
try:
 p=call(prefix+['install','-t',qa['apk']],timeout=90);output=(p.stdout+p.stderr).decode('utf8',errors='replace');(b/'phone-qa-install.log').write_text(output,encoding='utf8')
 assert p.returncode==0 and 'Success' in output,output;installed=True
 print('Installed independent no-Activity QA package; running only public-fixture format writers.',flush=True)
 output=text(prefix+['shell','am','instrument','-w','-r',pkg+'/com.denzic.companion.app.MaterialFormatInstrumentation'],timeout=60);(b/'phone-qa-instrumentation.log').write_text(output,encoding='utf8')
 assert 'INSTRUMENTATION_CODE: -1' in output,output
 dest=b/('phone-native-files-'+str(time.time_ns()));dest.mkdir()
 for name in ['result.json','saved-material.png','saved-material.pptx','saved-material.xlsx','saved-material.mm']:
  p=call(prefix+['exec-out','run-as',pkg,'cat','files/public-material054/'+name]);assert p.returncode==0,p.stderr.decode('utf8',errors='replace');(dest/name).write_bytes(p.stdout)
 observed=json.loads((dest/'result.json').read_text(encoding='utf8'));assert observed['status']=='ANDROID_NATIVE_CANVAS_PNG_AND_FILE_EXPORTS_PASSED'
 record.update(status=observed['status'],publicFiles=str(dest),render=observed)
except Exception as error:
 record.update(status='PHONE_BACKGROUND_QA_FAILED',error=repr(error));raise
finally:
 if installed:
  cleanup=text(prefix+['uninstall',pkg]);record['ownQaPackageRemoved']='Success' in cleanup
 record['ownerForegroundUnchanged']=beforeFocus is not None and beforeFocus==focus();record['companionPackageMetadataUnchanged']=beforeVersion==version();record['companionVersionObserved']=beforeVersion
 (b/'phone-native-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False),flush=True)
