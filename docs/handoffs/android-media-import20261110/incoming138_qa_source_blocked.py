from pathlib import Path
import ast,hashlib,json,os,re,shlex,subprocess,sys,time
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone138");A=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";SERIAL="d6bd213d";PKG="com.denzic.companion.app"
tree=ast.parse((R/"docs/handoffs/20261109-core-acceptance/android110/phone_session.py").read_text(encoding="utf-8"));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),"retained-phone-primitives","exec"))
helper="com.denzic.companion.qa.incoming138";action=sys.argv[1];name=sys.argv[2] if len(sys.argv)>2 else "public-incoming138.wav";mode=sys.argv[3] if len(sys.argv)>3 else "send"
assert name in ["public-incoming138.wav","material.docx","public-whiteboard138.png","public-bad138.wav","public-long138.wav"] and mode in ["send","view"]
state=json.loads((P/"virtual.json").read_text());display=state["displayId"];assert display>0
env={**os.environ,"COMPANION_PHONE_QA_CODE":"138"};before=primary()
main=next(s for s in adb(["shell","dumpsys","activity","activities"]).split("Display #") if s.startswith("0 (activities from top to bottom):"));assert not any(PKG in line for line in main.splitlines() if "Hist  #" in line)
if action=="cold":
 old=json.loads((P/"cdp.json").read_text());assert adb(["shell","pidof",PKG]).strip()==str(old["pid"]);adb(["shell","am","force-stop",PKG]);adb(["forward","--remove","tcp:"+str(old["cdpPort"])])
if action in ["cold","send","multiple","revoke","grant"]:
 adb(["shell","am","start","--display",display,"-n",helper+"/.IncomingSource138","--es","name",name,"--es","mode",mode])
 label={"cold":"公开：分享选定文件","send":"公开：分享选定文件","multiple":"公开：分享文档和图片","revoke":"公开：撤销选定文件读取权限","grant":"公开：恢复选定文件读取权限"}[action]
 q=subprocess.run([sys.executable,str(C/"organization_native.py"),"tap",label],env=env,capture_output=True,timeout=30);assert q.returncode==0,q.stderr.decode(errors="replace")[-1400:]
 if action in ["revoke","grant"]:adb(["shell","am","start","--display",display,"-n",PKG+"/.MainActivity"])
 if action=="cold":
  pid=""
  for attempt in range(40):
   pid=adb(["shell","pidof",PKG],required=False).strip()
   if pid.isdigit():break
   time.sleep(.2)
  assert pid.isdigit();port=adb(["forward","tcp:0","localabstract:webview_devtools_remote_"+pid]).strip();save(P/"cdp.json",{"displayId":display,"pid":int(pid),"cdpPort":int(port),"mainBefore":before,"mainUnchangedDuringOperation":primary()==before})
else:raise ValueError(action)
assert primary()==before
print(json.dumps({"action":action,"name":name,"intent":mode,"ownedDisplay":display,"ownerMainUnchanged":True,"businessBackendMutatedByVerifier":False}))
