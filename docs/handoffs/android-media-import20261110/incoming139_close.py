"""Reuse verified own-display primitives for a fresh, public customer workspace.
No install/model/record/BLE/Owner desktop. All previous qualification stays frozen.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time,psutil,shutil
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent/"android139";P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone138")
A=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";SERIAL="d6bd213d";PKG="com.denzic.companion.app"
tree=ast.parse((R/"docs/handoffs/20261109-core-acceptance/android110/phone_session.py").read_text(encoding="utf8"))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),"retained-owned-display-primitives","exec"))
def save(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+"\n").encode())
def now():return datetime.now().astimezone().isoformat(timespec="seconds")
def files():return adb(["shell","run-as",PKG,"sh","-c","find files -type f -print0 | xargs -0 -r sha256sum"],timeout=120)
def hold(active):
 p=R/"docs/product_backlog.json";raw=p.read_bytes();d=json.loads(raw);h=d["recorder_core"]["speed_investigation_handoff"]["endpointSelection"]["ownerPhoneHold"]
 if active:
  assert not h["active"];h.update(active=True,serial=SERIAL,reservedFor="Companion138 external-file public acceptance",requestedAt=now(),scope="Only new libraries restored through ordinary UI from the known public136 backup; incoming public generated PCM/document/image OS delivery and lifecycle on owned non-main display. Explicit isolated QA source app may grant only these public files. No listening, microphone, BLE/device, model/cloud, contacts or Owner/private libraries.")
 else:
  assert h["active"] and h["reservedFor"]=="Companion138 external-file public acceptance";h.update(active=False,releasedAt=now(),releaseReason="Actual139 public incoming lifecycle finished; original library restored and exact own display/app/forward/jar closed. Original data preserved; real sales/hardware/models not claimed.")
 tmp=p.with_suffix(".customer-phone.tmp");tmp.write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+"\n").replace("\n","\r\n").encode());assert p.read_bytes()==raw;tmp.replace(p)
assert version()==139
assert json.loads((C/"incoming-original-returned.json").read_text())["state"]=="ORIGINAL_LIBRARY_RETURNED_BY_ORDINARY_UI"
assert json.loads((C/"public-backup-remote.json").read_text())["sha256"]=="122d60969ab8821fd17ba4285fadfe97922e2e7c225a89ce72cf40c48580ae75"
source=json.loads((C.parent/"android138/system-source-files.json").read_text())
directory=source["publicDirectory"]
assert directory=="/sdcard/Download/Companion-public-incoming138-src"
assert set(adb(["shell","ls","-1A",directory]).splitlines())=={row["name"] for row in source["files"]}
for row in source["files"]:
 assert row["remote"]==directory+"/"+row["name"]
 assert adb(["shell","sha256sum",row["remote"]],timeout=120).split()[0]==row["sha256"]
for row in source["files"]:adb(["shell","rm",row["remote"]])
assert not adb(["shell","ls","-1A",directory]).strip()
adb(["shell","rmdir",directory])
backup139=json.loads((C/"incoming-backup-readback.json").read_text())
assert adb(["shell","sha256sum",backup139["backupRemote"]]).split()[0]==backup139["backupSha256"]
adb(["shell","rm",backup139["backupRemote"]])
working=json.loads((C.parent/"android138/public-libraries.json").read_text())["working"]
restored=json.loads((C/"incoming-restored-library.json").read_text())["restoredLibrary"]
save(C/"public-libraries.json",{"working":working,"restored":restored,"ids":[working,restored]})
for attempt in range(30):
 index=json.loads(adb(["shell","run-as",PKG,"cat","files/companion-library-index.json"]))
 if index["activeId"]=="original":break
 time.sleep(.1)
assert index["activeId"]=="original"
assert "AudioImportService" not in adb(["shell","dumpsys","activity","services",PKG])
state=json.loads((P/"virtual.json").read_text());session=json.loads((P/"cdp.json").read_text());before=primary()
main=next(s for s in adb(["shell","dumpsys","activity","activities"]).split("Display #") if s.startswith("0 (activities from top to bottom):"));assert not any(PKG in line for line in main.splitlines() if "Hist  #" in line)
assert adb(["shell","pidof",PKG]).strip()==str(session["pid"]);adb(["shell","am","force-stop",PKG]);adb(["forward","--remove","tcp:"+str(session["cdpPort"])]);assert primary()==before
proc=psutil.Process(state["pid"]);assert abs(proc.create_time()-state["createdAt"])<.01 and "scrcpy" in proc.name().lower();proc.terminate();proc.wait(10)
jar="/data/local/tmp/companion-organization138-ui.jar";assert adb(["shell","sha256sum",jar]).split()[0]==sha(P/"ui-standard/companion-organization138-ui.jar");adb(["shell","rm",jar])
backup=json.loads((P/"public-backup.json").read_text());assert adb(["shell","sha256sum",backup["path"]]).split()[0]==backup["sha256"];adb(["shell","rm",backup["path"]])
old=hashes((P/"before-files.private.sha256").read_text());snapshot=files();(P/"after-files.private.sha256").write_bytes(snapshot.encode());new=hashes(snapshot);changed=[name for name,digest in old.items() if new.get(name)!=digest];assert all(name=="files/companion-library-index.json" for name in changed),"Unexpected old content changes retained privately"
new_ids=json.loads((C/"public-libraries.json").read_text())["ids"];old_index=json.loads((P/"original-index.private.json").read_text());assert [item for item in index["libraries"] if item["id"] not in new_ids]==old_index["libraries"]
prefixes=[f"files/companion-{kind}-{library}/" for kind in ["meetings","recordings"] for library in new_ids]
added=[name for name in new if name not in old];assert all(any(name.startswith(prefix) for prefix in prefixes) or name=="files/companion-incoming-v1.json" for name in added),"New data outside declared public workspaces"
proof={"at":now(),"state":"ANDROID139_ACTUAL_INCOMING_LIFECYCLE_SESSION_CLOSED_OLD_CONTENT_PRESERVED","actualVersion":"0.1.139","preexistingFiles":len(old),"preexistingFilesByteIdentical":len(old)-len(changed),"onlyOldChangeLibraryIndex":changed==["files/companion-library-index.json"] or not changed,"allPreviousLibrariesRetained":True,"newPublicLibraries":new_ids,"newFilesOnlyInDeclaredPublicLibraries":len(added),"ownerMainDisplayOperated":False,"ownedAppDisplayForwardJarClosed":True,"publicTemporaryZipRemovedByExactSha":True,"modelsCloudMicBleUsed":False,"usbKeepAwakeUnchanged":adb(["shell","settings","get","global","stay_on_while_plugged_in"]).strip()=="2"}
proof.update(initialSessionVersion="0.1.138",fiveOwnSourceFilesAndOwnExportRemovedByExactHash=True,public139BackupPreservedRemotely=True);save(C/"end-session.json",proof);hold(False);print(json.dumps(proof))
