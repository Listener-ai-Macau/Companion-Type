from pathlib import Path
import hashlib,json,os,subprocess,zipfile,psutil
W=Path(__file__).parent;R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/android-trash071'
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/lifecycleqa071');C.mkdir(exist_ok=True)
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot');SDK=Path('E:/CodexData/Companion/.build-cache/android-sdk');BT=SDK/'build-tools/36.0.0';API=SDK/'platforms/android-35/android.jar'
psutil.Process().cpu_affinity([12,13]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
env={**os.environ,'JAVA_HOME':str(J),'PATH':str(J/'bin')+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2 -Xmx192m'}
def run(args):
 p=subprocess.run(list(map(str,args)),env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW,timeout=120);assert p.returncode==0,p.stdout+p.stderr;return p.stdout+p.stderr
manifest=C/'AndroidManifest.xml';manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.denzic.companion.lifecycleqa071" android:versionCode="1" android:versionName="071-qa"><uses-sdk android:minSdkVersion="26" android:targetSdkVersion="35"/><application android:label="Companion 回收站本机验收" android:debuggable="true" android:testOnly="true"/><instrumentation android:name="com.denzic.companion.app.LifecycleQa071" android:targetPackage="com.denzic.companion.lifecycleqa071"/></manifest>',encoding='utf8')
backend=C/'backup-only.jar'
with zipfile.ZipFile(S/'apps/android/app/libs/companion-android-backend.aar') as aar,zipfile.ZipFile(__import__('io').BytesIO(aar.read('classes.jar'))) as jar,zipfile.ZipFile(backend,'w',zipfile.ZIP_DEFLATED) as out:
 for name in jar.namelist():
  if name.startswith('com/denzic/companion/mobile/LibraryBackup') and name.endswith('.class'):out.writestr(name,jar.read(name))
classes=C/'classes';classes.mkdir(exist_ok=True)
source=S/'apps/android/app/src/main/java/com/denzic/companion/app/LocalRecordingLifecycle.java'
run([J/'bin/javac.exe','--release','8','-encoding','UTF-8','-cp',str(API)+os.pathsep+str(backend),'-d',classes,source,W/'lifecycleqa071/LifecycleQa071.java'])
combined=C/'qa.jar'
with zipfile.ZipFile(combined,'w',zipfile.ZIP_DEFLATED) as out:
 for p in classes.rglob('*.class'):out.write(p,p.relative_to(classes).as_posix())
 with zipfile.ZipFile(backend) as jar:
  for name in jar.namelist():out.writestr(name,jar.read(name))
dex=C/'dex';dex.mkdir(exist_ok=True);run([os.environ['COMSPEC'],'/d','/c',BT/'d8.bat','--min-api','26','--lib',API,'--output',dex,combined])
unsigned=C/'unsigned.apk';run([BT/'aapt2.exe','link','-I',API,'--manifest',manifest,'-o',unsigned])
with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as out:
 for p in dex.glob('*.dex'):out.write(p,p.name)
aligned=C/'aligned.apk';run([BT/'zipalign.exe','-f','4',unsigned,aligned]);apk=O/'Companion-Local-Lifecycle-QA071.apk'
run([os.environ['COMSPEC'],'/d','/c',BT/'apksigner.bat','sign','--ks','C:/Users/Billy/.android/debug.keystore','--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned]);run([os.environ['COMSPEC'],'/d','/c',BT/'apksigner.bat','verify',apk])
record={'apk':str(apk),'apkSha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'productionLifecycleSourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'selfTargetPackage':'com.denzic.companion.lifecycleqa071','internetPermission':False,'bluetoothPermission':False,'ownerCompanionDataAccessible':False,'hasActivityOrUi':False,'builtOnly':True,'installed':False,'stages':['create','reopen','interrupt','retry'],'scope':'Same production lifecycle class plus source-pinned backup; separate app UID, tiny synthetic fixtures only. This is Android filesystem acceptance, not Companion UI acceptance.'}
(O/'native-qa-prepared.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(json.dumps(record),flush=True)
