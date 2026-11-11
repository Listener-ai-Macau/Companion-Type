from pathlib import Path
import subprocess,json,os,time
C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone132");ADB=Path("C:/Users/Billy/Desktop/Denzic/Companion/.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe")
env={**os.environ,"COMPANION_PHONE_QA_CODE":"132"};name="Companion-public-table132-backup.zip"
def native(*args):
 p=subprocess.run(["python",str(C/"organization_native.py"),*args],env=env,capture_output=True,text=True,encoding="utf8",timeout=35);assert p.returncode==0,p.stderr[-1600:];return json.loads(p.stdout)
nodes=native("dump")["nodes"];edit="com.google.android.documentsui:id/search_src_text"
if not any(n.get("id")==edit for n in nodes):
 assert any(n.get("id")=="com.google.android.documentsui:id/option_menu_search" for n in nodes);native("tap","id:com.google.android.documentsui:id/option_menu_search")
native("setText","id:"+edit,name.removesuffix(".zip"));native("tap","id:"+edit)
display=json.loads((P/"virtual.json").read_text())["displayId"];assert display>0
subprocess.run([str(ADB),"-s","d6bd213d","shell","input","-d",str(display),"keyevent","KEYCODE_ENTER"],capture_output=True,check=True)
for _ in range(20):
 nodes=native("dump")["nodes"]
 if any(n.get("text")==name for n in nodes):break
 time.sleep(.2)
assert any(n.get("text")==name for n in nodes);native("tap",name)
print("Selected only the observed exact public132 backup through ordinary owned-display input.")
