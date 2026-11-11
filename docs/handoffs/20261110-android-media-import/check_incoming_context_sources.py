from pathlib import Path
from datetime import datetime
import sys,os,json,time,subprocess
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");S=R/"companion-device-closure055";A=R/"companion-core-android20261109";C=Path(__file__).parent;P=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110");D=Path("E:/CodexData/Companion/.build-cache/document-context20261110")
sys.path.insert(0,str(R/"model-research/src"))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,768*1024*1024)
out=D/("incoming-complete-source-"+str(time.time_ns()));out.mkdir()
results=[]
def run(name,args,root,timeout=180):
 q=subprocess.run(list(map(str,args)),cwd=root,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=timeout)
 (out/(name+".log")).write_bytes(q.stdout+q.stderr);results.append({"check":name,"exitCode":q.returncode});print(name,q.returncode,flush=True);return q.returncode
record={"at":datetime.now().astimezone().isoformat(timespec="seconds"),"state":"CHECKING","results":results,"logs":str(out),"nativeCandidateBuilt":False,"modelsRun":False}
try:
 for root,label in [(A,"mobile")]:
  run(label+"-types",["node","--max-old-space-size=512",root/"node_modules/typescript/bin/tsc","-p",root/("apps/"+label+"/tsconfig.json"),"--noEmit"],root)
 j=Path("C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin");sdk=Path("E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar")
 classes=out/"android35";classes.mkdir()
 cp=os.pathsep.join(map(str,[sdk,P/"app-classes",P/"backend-classes",P/"base-classes.jar"]))
 sources=list((A/"apps/android/app/src/main/java").rglob("*.java"))
 run("actual-android35-all-app-api",[j/"javac.exe","-J-Xmx192m","-J-XX:ActiveProcessorCount=1","--release","8","-encoding","UTF-8","-cp",cp,"-d",classes,*sources],A)
 record["state"]="SOURCE_CHECKS_PASSED" if all(v["exitCode"]==0 for v in results) else "SOURCE_CHECKS_FAILED"
finally:
 record["limits"]=limits.query()
 (C/"incoming-complete-source-checks.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
assert record["state"]=="SOURCE_CHECKS_PASSED"
