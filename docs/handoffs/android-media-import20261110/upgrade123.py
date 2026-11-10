from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone122');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app';now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
def fastFiles():return adb(['shell','run-as',PKG,'sh','-c','find files -type f -print0 | xargs -0 -r sha256sum'],timeout=120)
assert version()==122;state=json.loads((P/'virtual.json').read_text());session=json.loads((P/'cdp.json').read_text());before=primary();activities=adb(['shell','dumpsys','activity','activities']);main=next(s for s in activities.split('Display #') if s.startswith('0 (activities from top to bottom):'));assert not any(PKG in row for row in main.splitlines() if 'Hist  #' in row)
assert not 'AudioImportService' in adb(['shell','dumpsys','activity','services',PKG]);assert adb(['shell','pidof',PKG]).strip()==str(session['pid']);adb(['shell','am','force-stop',PKG]);adb(['forward','--remove','tcp:'+str(session['cdpPort'])]);snapshot=fastFiles();(P/'before123-install.sha256').write_text(snapshot);old=hashes(snapshot)
proof=json.loads((C/'android123/build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256'];assert 'Success' in adb(['install','-r','-t',apk],timeout=120) and version()==123;after=fastFiles();(P/'after123-install.sha256').write_text(after);assert hashes(after)==old and primary()==before
code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',code]).split()[0]==proof['apkSha256'];save(C/'android123/installation.json',{'at':now(),'state':'ANDROID123_EXACT_APK_INSTALLED_EXISTING_CONTENT_IDENTICAL','source':proof['sourceCommit'],'apkSha256':proof['apkSha256'],'existingFilesByteIdentical':len(old),'primaryUnchangedDuringInstall':True,'nativeBackendAndModelsUnchangedFrom122':True})
adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);pid=''
for _ in range(30):
 pid=adb(['shell','pidof',PKG],required=False).strip()
 if pid.isdigit():break
 time.sleep(.2)
assert pid.isdigit();port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();save(P/'cdp.json',{'at':now(),'displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'mainBefore':before,'mainUnchangedDuringOperation':primary()==before});print('Android123 installed with all current content identical; owned display restored.')
