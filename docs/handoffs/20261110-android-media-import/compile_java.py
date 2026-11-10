from pathlib import Path
import zipfile,subprocess,os,hashlib,json
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');A=R/'companion-core-android20261109';B=R/'companion-audio-import-backend20261110';C=Path(__file__).parent;P=Path('E:/CodexData/Companion/.build-cache/android-media-import20261110');J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');SDK=Path('E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar')
base=P/'backend6087901.aar';assert hashlib.sha256(base.read_bytes()).hexdigest()=='af498b880338aa5b8036cbfa97ad26588fdc784ee5eaf92e15df50c06e9aaadf'
with zipfile.ZipFile(base) as z:(P/'base-classes.jar').write_bytes(z.read('classes.jar'))
backend=P/'backend-classes';backend.mkdir(exist_ok=True);app=P/'app-classes';app.mkdir(exist_ok=True)
names=['RecordingLibrary','NativeAudio','ManagedAudioParts','DeviceBookmarkCache','ImportedAudio','MeetingStore'];source=B/'apps/android-backend/src/main/java/com/denzic/companion/mobile'
checks=[]
for label,classpath,out,files in [('backend',[SDK,P/'base-classes.jar'],backend,[source/(name+'.java') for name in names]),('app',[SDK,backend,P/'base-classes.jar'],app,list((A/'apps/android/app/src/main/java').rglob('*.java')))]:
 args=[J/'javac.exe','-J-Xmx256m','-J-XX:ActiveProcessorCount=1','--release','8','-encoding','UTF-8','-cp',os.pathsep.join(map(str,classpath)),'-d',out,*files];q=subprocess.run(list(map(str,args)),capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=90);raw=q.stdout+q.stderr;(P/(label+'-compile.log')).write_bytes(raw);checks.append({'name':label,'exit':q.returncode});print(label,q.returncode,raw.decode(errors='replace')[-4200:]);
 if q.returncode:break
(C/'java-check.json').write_text(json.dumps({'checks':checks,'nativeLibrariesRebuilt':False,'modelsRun':False},indent=2)+'\n')
assert len(checks)==2 and all(c['exit']==0 for c in checks)
