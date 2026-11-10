from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time,zipfile
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone132");A=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";SERIAL="d6bd213d";PKG="com.denzic.companion.app"
tree=ast.parse((R/"docs/handoffs/20261109-core-acceptance/android110/phone_session.py").read_text(encoding="utf8"));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),"retained-phone-primitives","exec"))
def snapshot(name):
 raw=adb(["shell","run-as",PKG,"sh","-c","find files -type f -print0 | xargs -0 -r sha256sum"],timeout=120);(P/name).write_bytes(raw.encode());return hashes(raw)
action=sys.argv[1];backup=json.loads((C/"android132/table-backup.json").read_text(encoding="utf8"));local=P/backup["file"];at=datetime.now().astimezone().isoformat(timespec="seconds")
if action=="backup":
 remote="/sdcard/Download/"+backup["file"];digest=adb(["shell","sha256sum",remote]).split()[0]
 if not local.exists():adb(["pull",remote,local],timeout=120)
 assert sha(local)==digest
 current=snapshot("before-table-restore.private.sha256");checked=0
 with zipfile.ZipFile(local) as z:
  assert z.testzip() is None
  for name in z.namelist():
   if not name.startswith(("meetings/","recordings/")):continue
   kind,leaf=name.split("/",1);source="files/companion-"+kind+"-"+backup["sourceLibrary"]+"/"+leaf
   with z.open(name) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==current[source]
   checked+=1
  doc=backup["doc"];assert json.loads(z.read("meetings/"+doc["extraction"]["file"]))==backup["extracted"]
  assert hashlib.sha256(z.read("meetings/"+doc["file"])).hexdigest()==doc["sourceSha256"]
 assert checked>13
 save(C/"android132/table-external-files.json",{"files":[{"path":remote,"sha256":digest}],"deleteOnlyAfterClosureByExactSha":True})
 record={"at":at,"state":"ANDROID132_ORDINARY_FULL_BACKUP_ALL_CONTENT_BYTES_AND_SAVED_TABLE_LAYOUT_IDENTICAL","bytes":local.stat().st_size,"sha256":digest,"contentFilesChecked":checked,"workbookAndLayoutExact":True,"ownerDataUploaded":False}
 save(C/"android132/table-backup-bytes.json",record)
elif action=="restore":
 proof=json.loads((C/"android132/table-restored.json").read_text(encoding="utf8"));before=hashes((P/"before-table-restore.private.sha256").read_text());current=snapshot("after-table-restore.private.sha256");changed=[n for n,h in before.items() if current.get(n)!=h];assert all(n=="files/companion-library-index.json" for n in changed)
 checked=0
 with zipfile.ZipFile(local) as z:
  for name in z.namelist():
   if not name.startswith(("meetings/","recordings/")):continue
   kind,leaf=name.split("/",1);target="files/companion-"+kind+"-"+proof["restoredLibrary"]+"/"+leaf
   with z.open(name) as stream:assert hashlib.file_digest(stream,"sha256").hexdigest()==current[target]
   checked+=1
 assert checked>13
 record={"at":at,"state":"ANDROID132_ACTUAL_RESTORED_ALL_CONTENT_BYTES_IDENTICAL_OLD_FILES_PRESERVED","contentFilesChecked":checked,"allPreexistingFilesIdenticalExceptActiveIndex":True,"restoredLibrary":proof["restoredLibrary"],"preexistingFilesChecked":len(before),"ownerPrivateDataUploaded":False}
 save(C/"android132/table-restore-bytes.json",record)
else:raise ValueError(action)
print(json.dumps(record))
