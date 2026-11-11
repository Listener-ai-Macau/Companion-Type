"""Use existing Files/Share controls on the held non-main display.
Only this case's five hash-checked public inputs may be selected.
"""
from pathlib import Path
import ast,hashlib,json,os,re,shlex,subprocess,sys,time
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone138");A=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";SERIAL="d6bd213d";PKG="com.denzic.companion.app"
tree=ast.parse((R/"docs/handoffs/20261109-core-acceptance/android110/phone_session.py").read_text(encoding="utf-8"));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),"retained-phone-primitives","exec"))
state=json.loads((P/"virtual.json").read_text());assert state["displayId"]==32
index=json.loads(adb(["shell","run-as",PKG,"cat","files/companion-library-index.json"]));assert index["activeId"]=="7ebdda83-7869-49a7-83fd-86dc68048493"
sources=json.loads((C/"android138/system-source-files.json").read_text());expected={row["name"] for row in sources["files"]};assert set(adb(["shell","ls","-1",sources["publicDirectory"]]).splitlines())==expected
for row in sources["files"]:assert adb(["shell","sha256sum",row["remote"]]).split()[0]==row["sha256"]
env={**os.environ,"COMPANION_PHONE_QA_CODE":"138"};before=primary();old=adb(["shell","pidof",PKG]).strip();assert old.isdigit()
main=next(s for s in adb(["shell","dumpsys","activity","activities"]).split("Display #") if s.startswith("0 (activities from top to bottom):"));assert not any(PKG in line for line in main.splitlines() if "Hist  #" in line)
def native(*args):
 p=subprocess.run([sys.executable,str(C/"organization_native.py"),*args],env=env,capture_output=True,text=True,encoding="utf-8",timeout=25);assert p.returncode==0,p.stderr[-1400:]
 if args[0]!="dump":return
 log=max((P/"ui-standard").glob("result-*.private.txt"),key=lambda f:f.stat().st_mtime).read_text(encoding="utf-8");return json.loads(next(line for line in log.splitlines() if line.startswith("COMPANION_UI=")).split("=",1)[1])["nodes"]
def wait_controls(test):
 for _ in range(20):
  nodes=native("dump")
  if test(nodes):return nodes
  time.sleep(.1)
 raise RuntimeError("Owned Files UI did not expose the expected ordinary control; current case retained.")
if "--resume-share" not in sys.argv:
 adb(["shell","am","start","--display",32,"-n","com.google.android.documentsui/com.android.documentsui.LauncherActivity"])
nodes=wait_controls(lambda rows:any(n.get("text")=="Companion-public-incoming138-src" for n in rows))
assert {n.get("text") for n in nodes if n.get("text") in expected}==expected
if not any(n.get("desc")=="分享" and n.get("id")=="com.google.android.documentsui:id/action_menu_share" for n in nodes):
 native("tap","更多选项");wait_controls(lambda rows:any(n.get("text")=="全选" for n in rows));native("tap","全选")
nodes=wait_controls(lambda rows:any(n.get("text")=="已选择 5 项" for n in rows));assert any(n.get("desc")=="分享" for n in nodes)
native("click","id:com.google.android.documentsui:id/action_menu_share");wait_controls(lambda rows:any(n.get("text")=="Companion" for n in rows));native("tap","Companion")
assert adb(["shell","pidof",PKG]).strip()==old and primary()==before
save(C/"android139/ordinary-files-warm-reshare.json",{"state":"ACTUAL_FILES_WARM_SHARE_REGRANT_TO_SAME_INSTANCE","display":32,"fiveDeclaredPublicInputsOnly":True,"sourceHashesVerified":True,"sameCompanionProcess":True,"ownerMainUnchanged":True,"customQaSourceOrShellUriDelegationUsed":False,"modelsOrCloudUsed":False})
print("Actual Files→Share→Companion warm re-share completed on the same own instance; source grants supplied by system UI.")
