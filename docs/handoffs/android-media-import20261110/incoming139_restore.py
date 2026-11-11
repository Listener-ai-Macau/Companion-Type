from pathlib import Path
import subprocess,os,json,time,sys
C=Path(__file__).parent;O=C/"android139";P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone138");A=Path("C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe")
env={**os.environ,"COMPANION_PHONE_QA_CODE":"138"}
def index():return json.loads(subprocess.check_output([str(A),"-s","d6bd213d","shell","run-as","com.denzic.companion.app","cat","files/companion-library-index.json"],text=True,encoding="utf-8"))
before=index();known={row["id"] for row in before["libraries"]};assert before["activeId"]=="7ebdda83-7869-49a7-83fd-86dc68048493"
backup=json.loads((O/"incoming-backup-readback.json").read_text());assert subprocess.check_output([str(A),"-s","d6bd213d","shell","sha256sum",backup["backupRemote"]],text=True).split()[0]==backup["backupSha256"]
def native(*args):
 p=subprocess.run([sys.executable,str(C/"organization_native.py"),*args],env=env,capture_output=True,text=True,encoding="utf-8",timeout=30);assert p.returncode==0,p.stderr[-1300:];return json.loads(p.stdout)
p=subprocess.run(["node","--max-old-space-size=192",str(C/"incoming139_ui.cjs"),"restore-open"],env=env,capture_output=True,text=True,encoding="utf-8",timeout=30);assert p.returncode==0,p.stderr[-1300:]
edit="com.google.android.documentsui:id/search_src_text";search="com.google.android.documentsui:id/option_menu_search"
for _ in range(25):
 nodes=native("dump")["nodes"]
 if any(n.get("id") in [edit,search] for n in nodes):break
 time.sleep(.1)
else:raise RuntimeError("Restore picker not ready; case retained.")
if not any(n.get("id")==edit for n in nodes):native("tap","id:"+search)
native("setText","id:"+edit,"Companion-public-incoming139-backup");native("tap","id:"+edit)
display=json.loads((P/"virtual.json").read_text())["displayId"];assert display==32
subprocess.run([str(A),"-s","d6bd213d","shell","input","-d",str(display),"keyevent","KEYCODE_ENTER"],capture_output=True,check=True)
name="Companion-public-incoming139-backup.zip"
for _ in range(25):
 nodes=native("dump")["nodes"]
 if any(n.get("text")==name for n in nodes):break
 time.sleep(.1)
else:raise RuntimeError("Exact public backup not visible; no other input selected.")
native("tap",name)
for _ in range(80):
 current=index();ids=[row["id"] for row in current["libraries"] if row["id"] not in known]
 if len(ids)==1 and current["activeId"]==ids[0]:break
 time.sleep(.25)
assert len(ids)==1 and current["activeId"]==ids[0]
assert [row for row in current["libraries"] if row["id"] in known]==before["libraries"]
(O/"incoming-restored-library.json").write_text(json.dumps({"state":"ORDINARY_NEW_INCOMING_BACKUP_RESTORED_WITH_ALL_PREVIOUS_LIBRARIES_RETAINED","sourceLibrary":before["activeId"],"restoredLibrary":ids[0],"allPreviousLibrariesRetained":True,"ownedDisplay":display},indent=2)+"\n")
print("Exact incoming backup restored through ordinary system picker into one new library; all earlier libraries retained.")
