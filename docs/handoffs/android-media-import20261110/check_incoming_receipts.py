from pathlib import Path
import sys,subprocess,json,os,time
from datetime import datetime
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");A=R/"companion-core-android20261109";C=Path(__file__).parent
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2)
out=Path("E:/CodexData/Companion/.build-cache/document-context20261110")/("incoming-receipts-"+str(time.time_ns()));out.mkdir()
j=Path("C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin");jar=Path("E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar");classes=out/"classes";classes.mkdir();cp=os.pathsep.join(map(str,[classes,jar]))
main=A/"apps/android/app/src/main/java/com/denzic/companion/app";test=A/"apps/android/app/src/test/java/com/denzic/companion/app"
record={"at":datetime.now().astimezone().isoformat(timespec="seconds"),"results":[],"logs":str(out),"nativeCandidateBuilt":False}
current_source=json.loads((C/"incoming-complete-source-checks.json").read_text(encoding="utf-8"));appclasses=Path(current_source["logs"])/"android35";storecp=os.pathsep.join(map(str,[classes,appclasses,jar]))
for name,args in [("compile",[j/"javac.exe","-J-Xmx128m","-J-XX:ActiveProcessorCount=1","--release","8","-encoding","UTF-8","-cp",cp,"-d",classes,main/"IncomingFileQueue.java",test/"IncomingFileQueueTest.java"]),("receipt-recovery",[j/"java.exe","-Xmx128m","-XX:ActiveProcessorCount=1","-cp",cp,"com.denzic.companion.app.IncomingFileQueueTest",out/"queue"]),("current-store-compile",[j/"javac.exe","-J-Xmx128m","-J-XX:ActiveProcessorCount=1","--release","8","-encoding","UTF-8","-cp",storecp,"-d",classes,test/"IncomingAttachmentStoreTest.java"]),("current-attachment-stores",[j/"java.exe","-Xmx128m","-XX:ActiveProcessorCount=1","-cp",storecp,"com.denzic.companion.app.IncomingAttachmentStoreTest",out/"attachments"])]:
 q=subprocess.run(list(map(str,args)),cwd=A,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW);(out/(name+".log")).write_bytes(q.stdout+q.stderr);record["results"].append({"check":name,"exitCode":q.returncode});print(name,q.returncode,flush=True)
 if q.returncode:break
record["state"]="PASSED" if len(record["results"])==4 and all(v["exitCode"]==0 for v in record["results"]) else "FAILED";record["limits"]=limits.query();(C/"incoming-receipt-checks.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");assert record["state"]=="PASSED"
