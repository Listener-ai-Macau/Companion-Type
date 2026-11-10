from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone125');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app'
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
proof=json.loads((C/'android125/restored-purge.json').read_text());key=proof['purgedKey'];identity=proof['library'];digest=hashlib.sha256(key.encode()).hexdigest();old=hashes((P/'after-restore.private.sha256').read_text());snapshot=adb(['shell','run-as',PKG,'sh','-c','find files -type f -print0 | xargs -0 -r sha256sum'],timeout=120);(P/'after-purge.private.sha256').write_text(snapshot);current=hashes(snapshot)
recordings='files/companion-recordings-'+identity+'/';meetings='files/companion-meetings-'+identity+'/'
def target(path):return path.startswith(recordings+'import-'+digest+'/') or path.startswith(meetings+digest+'.') or path.startswith(meetings+'recording-lifecycle/'+digest+'.') or path==meetings+'recording-organization.json'
changed=[path for path,value in old.items() if current.get(path)!=value];assert changed and all(target(path) for path in changed),[path for path in changed if not target(path)]
assert not any(path.startswith(recordings+'import-'+digest+'/') or (path.startswith(meetings+digest+'.') and path!=meetings+digest+'.lock') for path in current)
assert current.get(meetings+digest+'.lock')==hashlib.sha256(b'').hexdigest(),'Only the existing empty synchronization lock may remain'
import zipfile
with zipfile.ZipFile(P/'Companion-public-organization125.zip') as z:before=json.loads(json.loads(z.read('meetings/recording-organization.json'))['body'])
envelope=json.loads(adb(['shell','run-as',PKG,'cat',meetings+'recording-organization.json']));assert hashlib.sha256(envelope['body'].encode()).hexdigest()==envelope['sha256'];after=json.loads(envelope['body']);expected=before['entries'];assert key in expected;expected.pop(key);assert after['entries']==expected and after['revision']==before['revision']+1
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ACTUAL_RESTORED_ONLY_PURGE_REMOVES_EXACT_AUDIO_NOTES_AND_CLASSIFICATION_OTHER_FILES_IDENTICAL','restoredLibrary':identity,'changedTargetFiles':len(changed),'allOtherPreexistingFilesByteIdentical':len(old)-len(changed),'otherClassifiedRecordingPreserved':True,'sourceAndOwnerLibrariesUnchanged':True};save(C/'android125/purge-content.json',result);print(json.dumps(result))
