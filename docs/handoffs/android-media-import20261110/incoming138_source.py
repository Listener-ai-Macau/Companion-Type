from pathlib import Path
import ast,hashlib,json,os,re,shlex,subprocess,sys,time
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone138");A=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";SERIAL="d6bd213d";PKG="com.denzic.companion.app"
tree=ast.parse((R/"docs/handoffs/20261109-core-acceptance/android110/phone_session.py").read_text(encoding="utf-8"));exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),"retained-phone-primitives","exec"))
action=sys.argv[1];name=sys.argv[2] if len(sys.argv)>2 else "public-incoming138.wav";mode=sys.argv[3] if len(sys.argv)>3 else "view"
assert action in ["cold","send","move","restore"] and mode in ["send","view"]
entry=next(row for row in json.loads((C/"android138/system-source-files.json").read_text())["files"] if row["name"]==name)
state=json.loads((P/"virtual.json").read_text());display=state["displayId"];assert display>0;before=primary()
main=next(s for s in adb(["shell","dumpsys","activity","activities"]).split("Display #") if s.startswith("0 (activities from top to bottom):"));assert not any(PKG in line for line in main.splitlines() if "Hist  #" in line)
if action in ["move","restore"]:
 source=entry["remote"]+(".temporarily-moved" if action=="restore" else "");dest=entry["remote"]+(".temporarily-moved" if action=="move" else "")
 assert adb(["shell","sha256sum",source]).split()[0]==entry["sha256"];check=subprocess.run([str(A),"-s",SERIAL,"shell","test","!","-e",dest],capture_output=True);assert check.returncode==0;adb(["shell","mv",source,dest])
else:
 assert adb(["shell","sha256sum",entry["remote"]]).split()[0]==entry["sha256"]
 if action=="cold":
  old=json.loads((P/"cdp.json").read_text());assert adb(["shell","pidof",PKG]).strip()==str(old["pid"]);adb(["shell","am","force-stop",PKG]);adb(["forward","--remove","tcp:"+str(old["cdpPort"])])
 mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if name.endswith(".docx") else "image/png" if name.endswith(".png") else "audio/wav"
 args=["shell","am","start","--display",display,"-n",PKG+"/.MainActivity","-a","android.intent.action."+("VIEW" if mode=="view" else "SEND"),"-t",mime,"--grant-read-uri-permission"]
 if mode=="view":args+=["-d",entry["uri"]]
 else:args+=["--eu","android.intent.extra.STREAM",entry["uri"]]
 output=adb(args);assert "Error" not in output and "Exception" not in output,output[-800:]
 if action=="cold":
  pid=""
  for attempt in range(40):
   pid=adb(["shell","pidof",PKG],required=False).strip()
   if pid.isdigit():break
   time.sleep(.2)
  assert pid.isdigit();port=adb(["forward","tcp:0","localabstract:webview_devtools_remote_"+pid]).strip();save(P/"cdp.json",{"displayId":display,"pid":int(pid),"cdpPort":int(port),"mainBefore":before,"mainUnchangedDuringOperation":primary()==before})
assert primary()==before
print(json.dumps({"action":action,"name":name,"intent":mode,"provider":"actual system DocumentsProvider","sender":"Android shell OS intent, not a third-party customer tap","ownedDisplay":display,"ownerMainUnchanged":True,"businessBackendMutatedByVerifier":False}))
