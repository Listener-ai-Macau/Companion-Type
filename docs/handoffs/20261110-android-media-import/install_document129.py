"""Replace the failed document128 candidate within its existing owned session."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone128');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app'
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf-8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
assert version()==128;assert not (C/'android129/installation.json').exists()
hold=json.loads((R/'docs/product_backlog.json').read_text(encoding='utf-8'))['recorder_core']['speed_investigation_handoff']['endpointSelection']['ownerPhoneHold'];assert hold['active'] and hold['reservedFor']=='Companion128 public recording-library acceptance'
state=json.loads((P/'virtual.json').read_text());old=json.loads((P/'cdp.json').read_text());assert state['displayId']==19
main=next(v for v in adb(['shell','dumpsys','activity','activities']).split('Display #') if v.startswith('0 (activities from top to bottom):'));assert not any(PKG in line for line in main.splitlines() if 'Hist  #' in line)
assert adb(['shell','pidof',PKG]).strip()==str(old['pid']);before=primary();adb(['shell','am','force-stop',PKG]);adb(['forward','--remove','tcp:'+str(old['cdpPort'])]);assert not adb(['shell','pidof',PKG],required=False).strip()
def files():return adb(['shell','run-as',PKG,'sh','-c','find files -type f -print0 | xargs -0 -r sha256sum'],timeout=120)
original=files();(P/'before-repair-install.private.sha256').write_text(original)
proof=json.loads((C/'android129/build-result.json').read_text());apk=Path(proof['apk']);assert sha(apk)==proof['apkSha256'];assert 'Success' in adb(['install','-r','-t',apk],timeout=120);assert version()==129
current=files();(P/'after-repair-install.private.sha256').write_text(current);assert hashes(current)==hashes(original);assert primary()==before
installed=adb(['shell','pm','path',PKG]).strip().removeprefix('package:');assert adb(['shell','sha256sum',installed]).split()[0]==proof['apkSha256']
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ANDROID129_EXACT_REPAIR_INSTALLED_WITHIN_EXISTING_OWNED_DISPLAY_SESSION','sourceCommit':proof['sourceCommit'],'apkSha256':proof['apkSha256'],'previousVersion':128,'version':129,'existingFilesByteIdentical':len(hashes(original)),'ownerMainUnchangedDuringInstall':True,'ownedDisplayId':19,'priorFailureRetained':str(C/'document129-repair.json'),'modelsRun':False,'boardAccessed':False};save(C/'android129/installation.json',record)
adb(['shell','am','start','--display','19','-n',PKG+'/.MainActivity']);print(json.dumps(record))
