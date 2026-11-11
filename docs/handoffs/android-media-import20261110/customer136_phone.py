"""Reuse verified own-display primitives for a fresh, public customer workspace.
No install/model/record/BLE/Owner desktop. All previous qualification stays frozen.
"""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shlex,subprocess,sys,time,psutil,shutil
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent/"customer-edit136";P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/customer-edit136-20261111")
A=R/".cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe";SERIAL="d6bd213d";PKG="com.denzic.companion.app"
tree=ast.parse((R/"docs/handoffs/20261109-core-acceptance/android110/phone_session.py").read_text(encoding="utf8"))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),"retained-owned-display-primitives","exec"))
def save(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+"\n").encode())
def now():return datetime.now().astimezone().isoformat(timespec="seconds")
def files():return adb(["shell","run-as",PKG,"sh","-c","find files -type f -print0 | xargs -0 -r sha256sum"],timeout=120)
def hold(active):
 p=R/"docs/product_backlog.json";raw=p.read_bytes();d=json.loads(raw);h=d["recorder_core"]["speed_investigation_handoff"]["endpointSelection"]["ownerPhoneHold"]
 if active:
  assert not h["active"];h.update(active=True,serial=SERIAL,reservedFor="Companion136 fresh public customer workspace",requestedAt=now(),scope="Only new libraries restored through ordinary UI from the known public136 backup; ordinary AI simulated customer use on owned non-main display. No actual listening, microphone/recording, BLE/device, models/ASR/cloud AI, global clipboard/share or Owner/private libraries.")
 else:
  assert h["active"] and h["reservedFor"]=="Companion136 fresh public customer workspace";h.update(active=False,releasedAt=now(),releaseReason="Fresh public AI simulated customer workspace ended; original library restored and own display/app/forward/jar closed. Real sales/hardware/models not claimed.")
 tmp=p.with_suffix(".customer-phone.tmp");tmp.write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+"\n").replace("\n","\r\n").encode());assert p.read_bytes()==raw;tmp.replace(p)
action=sys.argv[1]
if action=="prepare":
 assert version()==136 and not adb(["shell","pidof",PKG],required=False).strip();P.mkdir(exist_ok=False);C.mkdir(exist_ok=False)
 index=adb(["shell","run-as",PKG,"cat","files/companion-library-index.json"]);assert json.loads(index)["activeId"]=="original";(P/"original-index.private.json").write_bytes(index.encode());(P/"before-files.private.sha256").write_bytes(files().encode())
 assert not adb(["shell","pidof",PKG],required=False).strip();hold(True)
 save(P/"preparation.json",{"at":now(),"version":version(),"mainFingerprint":primary(),"oldFiles":len(hashes((P/"before-files.private.sha256").read_text()))})
 backup=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone136/Companion-public-reader136-entry.zip");assert backup.is_file()
 remote="/sdcard/Download/Companion-public-customer-edit136-20261111.zip";check=subprocess.run([str(A),"-s",SERIAL,"shell","test","!","-e",remote],capture_output=True);assert check.returncode==0
 adb(["push",backup,remote],timeout=90);assert adb(["shell","sha256sum",remote]).split()[0]==sha(backup)
 save(P/"public-backup.json",{"path":remote,"sha256":sha(backup),"bytes":backup.stat().st_size,"source":"Known public-only four-record reader136 entry; old human engineering notes remain and are an auxiliary condition; not Owner library."})
 jar=P/"ui-standard/companion-organization136-ui.jar";jar.parent.mkdir();shutil.copyfile(Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone136/ui-standard/companion-organization136-ui.jar"),jar)
 adb(["push",jar,"/data/local/tmp/companion-organization136-ui.jar"]);assert adb(["shell","sha256sum","/data/local/tmp/companion-organization136-ui.jar"]).split()[0]==sha(jar)
 print("Fresh public customer scope prepared; no app started or prior qualification changed.")
elif action=="display":
 assert version()==136 and not adb(["shell","pidof",PKG],required=False).strip();assert not (P/"virtual.json").exists();before=primary()
 exe=Path("E:/CodexData/Companion/.build-cache/device-phone055/background-display/scrcpy-win64-v5.0.1/scrcpy.exe")
 args=[exe,"-s",SERIAL,"--new-display=1440x3200/589","--no-window","--record=NUL","--record-format=mkv","--no-audio","--no-clipboard-autosync","--display-ime-policy=local","--keyboard=disabled","--mouse=disabled","--no-power-on","--no-vd-system-decorations","--no-terminal-title","--max-fps=1","--video-bit-rate=128K"]
 with (P/"virtual.log").open("wb") as log:child=subprocess.Popen(list(map(str,args)),env={**os.environ,"ADB":str(A)},stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 state={"at":now(),"pid":child.pid,"createdAt":psutil.Process(child.pid).create_time(),"mainBefore":before,"physicalInput":False,"audioForwarded":False};save(P/"virtual.json",state)
 for _ in range(40):
  match=re.search(r"New display:[^\n]*\(id=(\d+)\)",(P/"virtual.log").read_text(errors="replace"));assert child.poll() is None
  if match:state["displayId"]=int(match[1]);break
  time.sleep(.2)
 assert state.get("displayId",0)>0 and primary()==before;save(P/"virtual.json",state);adb(["shell","am","start","--display",state["displayId"],"-n",PKG+"/.MainActivity"])
 pid=""
 for _ in range(40):
  pid=adb(["shell","pidof",PKG],required=False).strip()
  if pid.isdigit():break
  time.sleep(.2)
 assert pid.isdigit();port=adb(["forward","tcp:0","localabstract:webview_devtools_remote_"+pid]).strip();save(P/"cdp.json",{"at":now(),"displayId":state["displayId"],"pid":int(pid),"cdpPort":int(port),"mainBefore":before,"mainUnchangedDuringOperation":primary()==before})
 print("Owned non-main customer display ready; original library has not been inspected.")
elif action=="close":
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
 jar="/data/local/tmp/companion-organization136-ui.jar";assert adb(["shell","sha256sum",jar]).split()[0]==sha(P/"ui-standard/companion-organization136-ui.jar");adb(["shell","rm",jar])
 backup=json.loads((P/"public-backup.json").read_text());assert adb(["shell","sha256sum",backup["path"]]).split()[0]==backup["sha256"];adb(["shell","rm",backup["path"]])
 old=hashes((P/"before-files.private.sha256").read_text());snapshot=files();(P/"after-files.private.sha256").write_bytes(snapshot.encode());new=hashes(snapshot);changed=[name for name,digest in old.items() if new.get(name)!=digest];assert all(name=="files/companion-library-index.json" for name in changed),"Unexpected old content changes retained privately"
 new_ids=json.loads((C/"public-libraries.json").read_text())["ids"];old_index=json.loads((P/"original-index.private.json").read_text());assert [item for item in index["libraries"] if item["id"] not in new_ids]==old_index["libraries"]
 prefixes=[f"files/companion-{kind}-{library}/" for kind in ["meetings","recordings"] for library in new_ids]
 added=[name for name in new if name not in old];assert all(any(name.startswith(prefix) for prefix in prefixes) for name in added),"New data outside declared public workspaces"
 proof={"at":now(),"state":"ANDROID136_FRESH_PUBLIC_CUSTOMER_WORKSPACES_CLOSED_OLD_CONTENT_PRESERVED","actualVersion":"0.1.136","preexistingFiles":len(old),"preexistingFilesByteIdentical":len(old)-len(changed),"onlyOldChangeLibraryIndex":changed==["files/companion-library-index.json"] or not changed,"allPreviousLibrariesRetained":True,"newPublicLibraries":new_ids,"newFilesOnlyInDeclaredPublicLibraries":len(added),"ownerMainDisplayOperated":False,"ownedAppDisplayForwardJarClosed":True,"publicTemporaryZipRemovedByExactSha":True,"modelsCloudMicBleUsed":False,"usbKeepAwakeUnchanged":adb(["shell","settings","get","global","stay_on_while_plugged_in"]).strip()=="2"}
 save(C/"end-session.json",proof);hold(False);print(json.dumps(proof))
else:raise ValueError(action)
