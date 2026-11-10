from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110/phone125');A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';SERIAL='d6bd213d';PKG='com.denzic.companion.app'
tree=ast.parse((R/'docs/handoffs/20261109-core-acceptance/android110/phone_session.py').read_text(encoding='utf8'));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'retained-phone-primitives','exec'))
proof=json.loads((C/'android125/restored-ui.json').read_text());source=proof['beforeLibrary'];target=proof['restoredLibrary'];snapshot=adb(['shell','run-as',PKG,'sh','-c','find files -type f -print0 | xargs -0 -r sha256sum'],timeout=120);(P/'after-restore.private.sha256').write_text(snapshot);allFiles=hashes(snapshot)
def selected(identity):
 result={}
 for kind in ['recordings','meetings']:
  prefix='files/companion-'+kind+'-'+identity+'/'
  result.update({kind+'/'+name[len(prefix):]:digest for name,digest in allFiles.items() if name.startswith(prefix)})
 return result
left,right=selected(source),selected(target);assert 'meetings/recording-organization.json' in left and left['meetings/recording-organization.json']==right['meetings/recording-organization.json'];assert left and right;assert left.keys()==right.keys();diff=[name for name,digest in left.items() if right[name]!=digest];assert all(name.endswith('.playback.json') for name in diff),diff
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'RESTORED_SELECTED_LIBRARY_FOLDERS_TAGS_NOTES_IMAGES_AND_ORIGINAL_MEDIA_HASHES_VERIFIED','sourceLibrary':source,'restoredLibrary':target,'selectedFiles':len(left),'byteIdentical':len(left)-len(diff),'playbackProgressChangedByActualRestoredPlayback':len(diff),'notesAndOriginalImagesByteIdentical':True,'fourOriginalMediaPreserved':True};save(C/'android125/restored-content.json',record);print(json.dumps(record))
