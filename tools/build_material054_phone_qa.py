from pathlib import Path
import subprocess,os,zipfile,json,hashlib,time
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');b=r/'docs/handoffs/20261106-android-material-exports054';c=Path('E:/CodexData/Companion/.build-cache/android054-materials');q=c/'phone-qa';q.mkdir(exist_ok=True)
j=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot');sdk=Path('E:/CodexData/Companion/.build-cache/android-sdk');bt=sdk/'build-tools/36.0.0';android=sdk/'platforms/android-35/android.jar';prod=c/'build/app/intermediates/javac/debug/compileDebugJavaWithJavac/classes'
env={**os.environ,'JAVA_HOME':str(j),'PATH':str(j/'bin')+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2'}
def run(args):
 p=subprocess.run([str(x) for x in args],env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);assert p.returncode==0,p.stdout+p.stderr;return p.stdout+p.stderr
manifest=q/'AndroidManifest.xml';manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.denzic.companion.materialqa054" android:versionCode="1" android:versionName="054-qa"><uses-sdk android:minSdkVersion="26" android:targetSdkVersion="35"/><application android:label="Companion format QA" android:debuggable="true" android:testOnly="true"/><instrumentation android:name="com.denzic.companion.app.MaterialFormatInstrumentation" android:targetPackage="com.denzic.companion.materialqa054" android:functionalTest="true"/></manifest>''',encoding='utf8')
classes=q/'classes';classes.mkdir(exist_ok=True)
cp=os.pathsep.join([str(android),str(c/'backend-classes.jar'),str(prod)])
print(run([j/'bin/javac.exe','-source','8','-target','8','-encoding','UTF-8','-cp',cp,'-d',classes,Path(__file__).parent/'MaterialFormatInstrumentation.java']),flush=True)
inputs=q/'qa-input.jar'
with zipfile.ZipFile(inputs,'w',zipfile.ZIP_DEFLATED) as z:
 for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
 for prefix in ['MaterialLayout','PresentationDocuments','Presentation054Base','StructuredWorkbook','MindmapLayout','MindmapImage']:
  for p in (prod/'com/denzic/companion/app').glob(prefix+'*.class'):z.write(p,p.relative_to(prod).as_posix())
 # Backend classes are compiled source dependencies only. No native libraries or speech weights included.
dex=q/'dex';dex.mkdir(exist_ok=True)
run([os.environ['COMSPEC'],'/d','/c',bt/'d8.bat','--min-api','26','--lib',android,'--output',dex,inputs,c/'backend-classes.jar'])
unsigned=q/'qa-unsigned.apk';run([bt/'aapt2.exe','link','-I',android,'--manifest',manifest,'-o',unsigned])
with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as z:
 for p in dex.glob('*.dex'):z.write(p,p.name)
aligned=q/'qa-aligned.apk';run([bt/'zipalign.exe','-f','4',unsigned,aligned])
apk=q/'Companion-Material054-NoActivity-QA.apk';
run([os.environ['COMSPEC'],'/d','/c',bt/'apksigner.bat','sign','--ks','C:/Users/Billy/.android/debug.keystore','--ks-key-alias','androiddebugkey','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned])
verified=run([os.environ['COMSPEC'],'/d','/c',bt/'apksigner.bat','verify','--verbose',apk])
record={'status':'NO_ACTIVITY_PHONE_QA_PACKAGE_BUILT','package':'com.denzic.companion.materialqa054','targetPackage':'com.denzic.companion.materialqa054','apk':str(apk),'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'ownerAppTargeted':False,'hasActivities':False,'nativeSpeechLibrariesIncluded':False,'modelsRun':False,'signatureVerified':True}
(b/'phone-qa-build.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
