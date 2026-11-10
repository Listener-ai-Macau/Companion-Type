from pathlib import Path
import os,sys,time,subprocess,json,datetime
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");A=R/"companion-core-android20261109";C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110");D=Path("E:/CodexData/Companion/.build-cache/document-context20261110")
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2)
out=D/("manual-current-store-"+str(time.time_ns()));out.mkdir();classes=out/"classes";classes.mkdir();J=Path("C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin")
api=sorted(D.glob("manual-complete-source-*"),key=lambda p:p.stat().st_mtime)[-1]/"android35";assert (api/"com/denzic/companion/app/MainActivity.class").exists()
cp=os.pathsep.join(map(str,[classes,api,P/"app-classes",P/"backend-classes",Path("E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar"),P/"base-classes.jar"]))
test=A/"apps/android/app/src/test/java/com/denzic/companion/app";fixture=C/"android132/table-reading.json";archive=P/"phone134/Companion-public-reader134-entry.zip"
jobs=[("compile",[J/"javac.exe","-J-Xmx128m","-J-XX:ActiveProcessorCount=1","--release","8","-encoding","UTF-8","-cp",cp,"-d",classes,*[test/(n+".java") for n in ["ImportedAudioIntegrationTest","ManualNoteContextTest","ManualNoteStoreIntegrationTest"]]]),("source-binding",[J/"java.exe","-Xmx128m","-XX:ActiveProcessorCount=1","-cp",cp,"com.denzic.companion.app.ManualNoteContextTest",fixture]),("current-source-store-exports",[J/"java.exe","-Xmx128m","-XX:ActiveProcessorCount=1","-cp",cp,"com.denzic.companion.app.ManualNoteStoreIntegrationTest",fixture,archive,out/"library",out/"restored"])]
results=[]
for name,args in jobs:
 q=subprocess.run(list(map(str,args)),cwd=A,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=90);(out/(name+".log")).write_bytes(q.stdout+q.stderr);results.append({"check":name,"exitCode":q.returncode});print(name,q.returncode,(q.stdout+q.stderr).decode(errors="replace")[-1200:])
 if q.returncode:break
j={"at":datetime.datetime.now().astimezone().isoformat(timespec="seconds"),"state":"CURRENT_PLATFORM_COMPILED_NOTE_STORE_SOURCE_EXPORTS_PASSED" if len(results)==3 and all(x["exitCode"]==0 for x in results) else "FAILED","results":results,"logs":str(out),"actualApiClasses":str(api),"limits":limits.query(),"directorySyncAndRasterCheckMocked":True,"ordinaryBackupRestoreQualified":False,"modelsRun":False}
(C/"manual-current-store-checks.json").write_text(json.dumps(j,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");assert j["state"]!="FAILED"
