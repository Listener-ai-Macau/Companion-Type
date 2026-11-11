from pathlib import Path
import sys,subprocess,json,hashlib,zipfile,os
R=Path("C:/Users/Billy/Desktop/Denzic/Companion");C=Path(__file__).parent;S=R/"companion-device-closure055/tools/qa/core_acceptance20261109";O=Path("E:/CodexData/Companion/.build-cache/android-media-import20261110/phone138/source-app");O.mkdir()
sys.path.insert(0,str(R/"model-research/src"));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(10,512*1024**2)
J=Path("C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin");sdk=Path("E:/CodexData/Companion/.build-cache/android-sdk");bt=sdk/"build-tools/36.0.0";android=sdk/"platforms/android-35/android.jar"
def run(name,args):
 p=subprocess.run(list(map(str,args)),capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW);(O/(name+".log")).write_bytes(p.stdout+p.stderr);assert p.returncode==0,(name,p.stderr.decode(errors="replace")[-1500:])
manifest=O/"AndroidManifest.xml";manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.denzic.companion.qa.incoming138" android:versionCode="1" android:versionName="138-public-qa"><uses-sdk android:minSdkVersion="30" android:targetSdkVersion="35"/><application android:label="Companion 公开文件来源验收" android:debuggable="true" android:testOnly="true" android:allowBackup="false"><activity android:name=".IncomingSource138" android:exported="true" android:launchMode="singleTop"/><provider android:name=".IncomingSourceProvider138" android:authorities="com.denzic.companion.qa.incoming138.files" android:exported="false" android:grantUriPermissions="true"/></application></manifest>',encoding="utf-8")
classes=O/"classes";classes.mkdir();dex=O/"dex";dex.mkdir()
sources=[S/"IncomingSource138.java",S/"IncomingSourceProvider138.java"]
run("java",[J/"javac.exe","-J-Xmx128m","-J-XX:ActiveProcessorCount=1","--release","8","-encoding","UTF-8","-cp",android,"-d",classes,*sources])
jar=O/"source.jar"
with zipfile.ZipFile(jar,"w") as z:
 for p in classes.rglob("*.class"):z.write(p,p.relative_to(classes).as_posix())
run("dex",[J/"java.exe","-Xmx192m","-XX:ActiveProcessorCount=1","-cp",bt/"lib/d8.jar","com.android.tools.r8.D8","--min-api","30","--lib",android,"--output",dex,jar])
unsigned=O/"unsigned.apk";run("manifest",[bt/"aapt2.exe","link","-I",android,"--manifest",manifest,"-o",unsigned])
with zipfile.ZipFile(unsigned,"a") as z:
 for p in dex.glob("*.dex"):z.write(p,p.name)
aligned=O/"aligned.apk";run("align",[bt/"zipalign.exe","-f","4",unsigned,aligned]);apk=O/"Companion-Public-Incoming138-Source-QA.apk"
base=[J/"java.exe","-Xmx128m","-XX:ActiveProcessorCount=1","-jar",bt/"lib/apksigner.jar"]
run("sign",base+["sign","--ks","C:/Users/Billy/.android/debug.keystore","--ks-key-alias","androiddebugkey","--ks-pass","pass:android","--key-pass","pass:android","--out",apk,aligned]);run("verify",base+["verify",apk])
proof={"state":"BOUNDED_PUBLIC_SOURCE_APP_BUILT","package":"com.denzic.companion.qa.incoming138","apk":str(apk),"sha256":hashlib.sha256(apk.read_bytes()).hexdigest(),"sourceHashes":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},"internetMicrophoneContactsOrBroadStoragePermissions":False,"providerExported":False,"providerReadOnly":True,"onlyFiveNamedPublicFiles":True,"actualIntentGrantTestingOnly":True,"installed":False,"limits":limits.query()}
(C/"android138/source-app-build.json").write_text(json.dumps(proof,indent=2)+"\n");print(json.dumps({k:v for k,v in proof.items() if k!="limits"}))
