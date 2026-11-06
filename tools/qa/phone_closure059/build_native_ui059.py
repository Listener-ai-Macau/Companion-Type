from pathlib import Path
import os,subprocess,zipfile,hashlib,json
W=Path(__file__).parent;C=Path('E:/CodexData/Companion/.build-cache/device-phone055/native-ui059');C.mkdir(exist_ok=True)
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot');SDK=Path('E:/CodexData/Companion/.build-cache/android-sdk');BT=SDK/'build-tools/36.0.0';API=SDK/'platforms/android-35/android.jar'
env={**os.environ,'JAVA_HOME':str(J),'PATH':str(J/'bin')+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2'}
def run(args):
    p=subprocess.run(list(map(str,args)),env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);assert p.returncode==0,p.stdout+p.stderr;return p.stdout+p.stderr
manifest=C/'AndroidManifest.xml';manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.denzic.companion.uidriver059" android:versionCode="1" android:versionName="059-qa"><uses-sdk android:minSdkVersion="30" android:targetSdkVersion="35"/><application android:label="Companion 虚拟屏验收" android:debuggable="true" android:testOnly="true"/><instrumentation android:name=".NativeUi059" android:targetPackage="com.denzic.companion.uidriver059"/></manifest>',encoding='utf8')
classes=C/'classes';classes.mkdir(exist_ok=True);run([J/'bin/javac.exe','--release','8','-encoding','UTF-8','-cp',API,'-d',classes,W/'shareqa059/NativeUi059.java'])
jar=C/'driver.jar'
with zipfile.ZipFile(jar,'w',zipfile.ZIP_DEFLATED) as z:
    for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
dex=C/'dex';dex.mkdir(exist_ok=True);run([os.environ['COMSPEC'],'/d','/c',BT/'d8.bat','--min-api','30','--lib',API,'--output',dex,jar])
unsigned=C/'unsigned.apk';run([BT/'aapt2.exe','link','-I',API,'--manifest',manifest,'-o',unsigned])
with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as z:
    for p in dex.glob('*.dex'):z.write(p,p.name)
aligned=C/'aligned.apk';run([BT/'zipalign.exe','-f','4',unsigned,aligned]);apk=C/'Companion-Native-UI059-QA.apk'
run([os.environ['COMSPEC'],'/d','/c',BT/'apksigner.bat','sign','--ks','C:/Users/Billy/.android/debug.keystore','--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned])
run([os.environ['COMSPEC'],'/d','/c',BT/'apksigner.bat','verify',apk]);print(json.dumps({'apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'mainDisplayRootRead':False,'noNetworkPermission':True}))
