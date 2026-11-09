from pathlib import Path
from datetime import datetime
import hashlib,json,os,shlex,subprocess,sys,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=Path(__file__).parent
P=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/mobile-product-baseline')
sys.path.insert(0,str(M/'src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=384*1024**2)
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';PKG='com.denzic.companion.app';TEST='com.denzic.companion.qa.paired20261109';SERIAL='d6bd213d'
def cmd(args):
    q=subprocess.run(list(map(str,args)),capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if q.returncode:(P/'instrumentation-command-failure.txt').write_bytes(q.stdout+q.stderr);raise RuntimeError('Build/install failed; evidence retained')
    return q.stdout
def adb(args):
    if args[0]=='shell':args=['shell',shlex.join(list(map(str,args[1:])))]
    return cmd([A,'-s',SERIAL,*args])
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
sdk=Path('E:/CodexData/Companion/.build-cache/android-sdk');bt=sdk/'build-tools/36.0.0';j=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');api=sdk/'platforms/android-35/android.jar'
classes=P/'instrumentation-classes';classes.mkdir(exist_ok=True);dex=P/'instrumentation-dex';dex.mkdir(exist_ok=True)
sources=[M/'src/CompanionPairedPhoneAsr20261109.java',M/'src/CompanionPairedPhoneInstrumentation20261109.java']
cmd([j/'javac.exe','-J-Xmx128m','--release','8','-encoding','UTF-8','-cp',api,'-d',classes,*sources])
jar=P/'instrumentation-classes.jar'
with zipfile.ZipFile(jar,'w') as z:
    for f in classes.rglob('*.class'):z.write(f,f.relative_to(classes).as_posix())
cmd([j/'java.exe','-Xmx160m','-XX:ActiveProcessorCount=1','-cp',bt/'lib/d8.jar','com.android.tools.r8.D8','--min-api','30','--lib',api,'--output',dex,jar])
manifest=P/'AndroidManifest.xml';manifest.write_text('<?xml version="1.0" encoding="utf-8"?><manifest xmlns:android="http://schemas.android.com/apk/res/android" package="'+TEST+'"><uses-sdk android:minSdkVersion="30" android:targetSdkVersion="35"/><application android:label="Companion public paired ASR QA" android:debuggable="true" android:hasCode="true"/><instrumentation android:name="com.denzic.companion.qa.CompanionPairedPhoneInstrumentation20261109" android:targetPackage="'+PKG+'" android:functionalTest="true"/></manifest>',encoding='utf8')
raw=P/'paired-instrumentation-raw.apk';cmd([bt/'aapt2.exe','link','-I',api,'--manifest',manifest,'-o',raw])
with zipfile.ZipFile(raw,'a') as z:z.write(dex/'classes.dex','classes.dex')
aligned=P/'paired-instrumentation-aligned.apk';cmd([bt/'zipalign.exe','-f','4',raw,aligned])
apk=P/'paired-instrumentation.apk';sign=[j/'java.exe','-Xmx128m','-XX:ActiveProcessorCount=1','-jar',bt/'lib/apksigner.jar']
cmd(sign+['sign','--ks','C:/Users/Billy/.android/debug.keystore','--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned]);cmd(sign+['verify',apk])
owner=subprocess.run([str(A),'-s',SERIAL,'shell','pidof',PKG],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
if owner.returncode not in (0,1):raise RuntimeError('Unable to check owner app state')
if owner.stdout.strip():raise RuntimeError('Owner app running; do not instrument an active app')
installation=adb(['install','-r',apk]).decode(errors='replace');(C/'instrumentation-install.txt').write_text(installation)
record={'at':datetime.now().astimezone().isoformat(),'state':'OWNED_NO_ACTIVITY_INSTRUMENTATION_BUILT_INSTALLED_NOT_RUN','testPackage':TEST,'apkSha256':sha(apk),'sourceSha256':{p.name:sha(p) for p in sources},'productApkChanged':False,'newProductVersion':False,'mainDisplayUsed':False,'limits':limits.query()}
(C/'instrumentation-prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
