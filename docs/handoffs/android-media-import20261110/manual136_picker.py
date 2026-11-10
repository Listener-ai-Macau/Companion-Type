from pathlib import Path
import subprocess,sys,json,os,time
C=Path(__file__).parent;O=C/"android136";P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone136");ADB=Path("C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe")
name=sys.argv[1];assert name in ["Companion-public-reader136-entry.zip","Companion-public-manual136-backup.zip"]
item=next(item for item in json.loads((O/"reader-external-files.json").read_text())["files"] if item["path"].endswith("/"+name))
def adb(args):return subprocess.check_output([str(ADB),"-s","d6bd213d",*map(str,args)],text=True,encoding="utf-8",timeout=30)
assert adb(["shell","sha256sum",item["path"]]).split()[0]==item["sha256"]
def index():return json.loads(adb(["shell","run-as","com.denzic.companion.app","cat","files/companion-library-index.json"]))
before=index();known={x["id"] for x in before["libraries"]}
def native(*args):
 p=subprocess.run(["python",str(C/"organization_native.py"),*args],env={**os.environ,"COMPANION_PHONE_QA_CODE":"136"},capture_output=True,text=True,encoding="utf-8",timeout=30);assert p.returncode==0,p.stderr[-1500:];return json.loads(p.stdout)
nodes=native("dump")["nodes"];edit="com.google.android.documentsui:id/search_src_text"
if not any(n.get("id")==edit for n in nodes):native("tap","id:com.google.android.documentsui:id/option_menu_search")
native("setText","id:"+edit,name.rsplit(".",1)[0]);native("tap","id:"+edit)
display=json.loads((P/"virtual.json").read_text())["displayId"];assert display>0;adb(["shell","input","-d",display,"keyevent","KEYCODE_ENTER"])
nodes=native("dump")["nodes"];assert any(n.get("text")==name for n in nodes);native("tap",name)
for _ in range(60):
 current=index();fresh=[x["id"] for x in current["libraries"] if x["id"] not in known]
 if len(fresh)==1 and current["activeId"]==fresh[0]:break
 time.sleep(.2)
assert len(fresh)==1 and current["activeId"]==fresh[0];assert [x for x in current["libraries"] if x["id"] in known]==before["libraries"]
path=O/"manual-public-libraries.json";j=json.loads(path.read_text()) if path.exists() else {"ids":[]};j["ids"]+=fresh;j["working" if name.endswith("entry.zip") else "restored"]=fresh[0];path.write_text(json.dumps(j,indent=2)+"\n")
print(json.dumps({"state":"EXACT_DECLARED_PUBLIC_ZIP_RESTORED_BY_ORDINARY_OWNED_DISPLAY_PICKER","display":display,"activeId":fresh[0],"earlierLibraryEntriesRetained":True}))
