from pathlib import Path
import subprocess,os,zipfile,json,hashlib,sys
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109/android110-phone-d6');O=P/'ui-shell';O.mkdir(exist_ok=True)
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');SDK=Path('E:/CodexData/Companion/.build-cache/android-sdk');API=SDK/'platforms/android-35/android.jar';BT=SDK/'build-tools/36.0.0'
sys.path.insert(0,str(R/'model-research/src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=512*1024**2)
def run(args):
 p=subprocess.run(list(map(str,args)),capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,p.stderr.decode('utf8',errors='replace')[-1500:]
classes=O/'classes';classes.mkdir(exist_ok=True);run([J/'javac.exe','-J-Xmx128m','--release','8','-encoding','UTF-8','-cp',API,'-d',classes,C/'NativeUi110.java'])
jar=O/'classes.jar'
with zipfile.ZipFile(jar,'w') as z:
 for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
dex=O/'dex';dex.mkdir(exist_ok=True);run([J/'java.exe','-Xmx192m','-XX:ActiveProcessorCount=1','-cp',BT/'lib/d8.jar','com.android.tools.r8.D8','--min-api','30','--lib',API,'--output',dex,jar])
out=O/'companion-native-ui110.jar'
with zipfile.ZipFile(out,'w') as z:z.write(dex/'classes.dex','classes.dex')
a=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';run([a,'-s','d6bd213d','push',out,'/data/local/tmp/companion-native-ui110.jar'])
record={'jarSha256':hashlib.sha256(out.read_bytes()).hexdigest(),'ordinaryUiOnly':True,'nonMainDisplayOnly':True,'installedApk':False,'accessibilitySettingsChanged':False,'noPhysicalWindowRoots':True};(C/'phone-d6/native-ui-tool.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(json.dumps(record))
