from pathlib import Path
import subprocess,json,os
C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone135");item=json.loads((C/"android135/manual-public-image.json").read_text());ADB=Path("C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe")
def adb(args):return subprocess.check_output([str(ADB),"-s","d6bd213d",*map(str,args)],text=True,encoding="utf-8",timeout=30)
assert adb(["shell","sha256sum",item["phonePath"]]).split()[0]==item["sha256"]
def native(*args):
 q=subprocess.run(["python",str(C/"organization_native.py"),*args],env={**os.environ,"COMPANION_PHONE_QA_CODE":"135"},capture_output=True,text=True,encoding="utf-8",timeout=30);assert q.returncode==0,q.stderr[-1200:];return json.loads(q.stdout)
nodes=native("dump")["nodes"];edit="com.google.android.documentsui:id/search_src_text"
if not any(n.get("id")==edit for n in nodes):native("tap","id:com.google.android.documentsui:id/option_menu_search")
native("setText","id:"+edit,item["name"].rsplit(".",1)[0]);native("tap","id:"+edit);display=json.loads((P/"virtual.json").read_text())["displayId"];assert display>0;adb(["shell","input","-d",display,"keyevent","KEYCODE_ENTER"])
nodes=native("dump")["nodes"];matches=[n for n in nodes if n.get("text")==item["name"] or n.get("desc","").startswith(item["name"]+",")];assert len(matches)==1;native("tap",matches[0].get("desc") or item["name"]);print("Selected exact observed public whiteboard in owned-display ordinary image picker.")
