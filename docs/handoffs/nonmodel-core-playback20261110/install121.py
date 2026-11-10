from pathlib import Path
from datetime import datetime
import ast,hashlib,json,subprocess,shlex,time,re
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent/'android121';P=Path('E:/CodexData/Companion/.build-cache/nonmodel-playback20261110/phone120');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app';now=lambda:datetime.now().astimezone().isoformat(timespec='seconds')
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
assert version()==120 and not (C/'installation.json').exists()
session=json.loads((P/'cdp.json').read_text());state=json.loads((P/'virtual.json').read_text());assert state['displayId']>0 and adb(['shell','pidof',PKG]).strip()==str(session['pid'])
activities=adb(['shell','dumpsys','activity','activities']);main=next(s for s in activities.split('Display #') if s.startswith('0 (activities from top to bottom):'));assert not any(PKG in row for row in main.splitlines() if 'Hist  #' in row)
before=primary();adb(['shell','am','force-stop',PKG]);adb(['forward','--remove','tcp:'+str(session['cdpPort'])]);assert before==primary()
snapshot=files();(P/'before121-install.sha256').write_text(snapshot);old=hashes(snapshot)
proof=json.loads((C/'build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256']
assert 'Success' in adb(['install','-r','-t',apk],timeout=120) and version()==121
after=files();(P/'after121-install.sha256').write_text(after);assert hashes(after)==old
code=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',code]).split()[0]==proof['apkSha256'];assert before==primary()
record={'at':now(),'state':'ANDROID121_EXACT_APK_INSTALLED_EXISTING_FILES_IDENTICAL','sourceCommit':proof['sourceCommit'],'apkSha256':proof['apkSha256'],'existingFilesByteIdentical':len(old),'ownerMainUnchangedDuringInstall':True,'nativeBackendAndModelsUnchanged':True};save(C/'installation.json',record)
adb(['shell','am','start','--display',state['displayId'],'-n',PKG+'/.MainActivity']);pid=''
for _ in range(30):
 pid=adb(['shell','pidof',PKG],required=False).strip()
 if pid.isdigit():break
 time.sleep(.2)
assert pid.isdigit();port=adb(['forward','tcp:0','localabstract:webview_devtools_remote_'+pid]).strip();assert port.isdigit() and before==primary();save(P/'cdp.json',{'at':now(),'displayId':state['displayId'],'pid':int(pid),'cdpPort':int(port),'mainBefore':before,'mainUnchangedDuringInstall':True});print(json.dumps(record))
