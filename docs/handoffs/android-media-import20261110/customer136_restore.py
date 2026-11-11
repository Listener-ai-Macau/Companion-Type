"""Ordinary restore of the same public backup into another fresh customer library."""
from pathlib import Path
import subprocess,os,json,time
C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/customer-edit136-20261111")
A=Path("C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe")
env={**os.environ,"COMPANION_PHONE_QA_CODE":"136","COMPANION_PHONE_QA_SESSION":"customer-edit136-20261111"}
def index():return json.loads(subprocess.check_output([str(A),"-s","d6bd213d","shell","run-as","com.denzic.companion.app","cat","files/companion-library-index.json"],text=True,encoding="utf8"))
before=index();known={x["id"] for x in before["libraries"]};role=__import__("sys").argv[1];assert role in ["presale","afteruse"]
backup=json.loads((P/"public-backup.json").read_text());assert subprocess.check_output([str(A),"-s","d6bd213d","shell","sha256sum",backup["path"]],text=True).split()[0]==backup["sha256"]
def native(*args):
 p=subprocess.run(["python",str(C/"organization_native.py"),*args],env=env,capture_output=True,text=True,timeout=30);assert p.returncode==0,p.stderr[-1200:];return json.loads(p.stdout)
p=subprocess.run(["node",str(C/"organization_ui.cjs"),"restore"],env=env,capture_output=True,text=True,timeout=35);assert p.returncode==0,p.stderr[-1200:]
nodes=native("dump")["nodes"];edit="com.google.android.documentsui:id/search_src_text"
if not any(n.get("id")==edit for n in nodes):
 assert any(n.get("id")=="com.google.android.documentsui:id/option_menu_search" for n in nodes);native("tap","id:com.google.android.documentsui:id/option_menu_search")
native("setText","id:"+edit,"Companion-public-customer-edit136-20261111");native("tap","id:"+edit)
display=json.loads((P/"virtual.json").read_text())["displayId"];assert display>0
subprocess.run([str(A),"-s","d6bd213d","shell","input","-d",str(display),"keyevent","KEYCODE_ENTER"],capture_output=True,check=True)
nodes=native("dump")["nodes"];name="Companion-public-customer-edit136-20261111.zip";assert any(n.get("text")==name for n in nodes);native("tap",name)
for _ in range(40):
 current=index();ids=[x["id"] for x in current["libraries"] if x["id"] not in known]
 if len(ids)==1 and current["activeId"]==ids[0]:break
 time.sleep(.25)
assert len(ids)==1 and current["activeId"]==ids[0];assert [x for x in current["libraries"] if x["id"] in known]==before["libraries"]
path=C/"customer-edit136/public-libraries.json";proof=json.loads(path.read_text()) if path.exists() else {"ids":[]};proof["ids"]+=ids;proof[role]=ids[0];path.write_bytes((json.dumps(proof,ensure_ascii=False,indent=2)+"\n").encode())
print(json.dumps({"state":"SECOND_FRESH_PUBLIC_CUSTOMER_LIBRARY_RESTORED_BY_ORDINARY_PICKER","activeId":ids[0],"allEarlierLibraryEntriesRetained":True,"display":display}))
