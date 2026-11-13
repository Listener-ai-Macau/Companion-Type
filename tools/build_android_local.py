"""One bounded Android software build using shared compilation caches.

No device, recorder, model, or cloud access. Reuses the verified native AAR.
"""
from pathlib import Path
from datetime import datetime
import argparse,hashlib,json,os,re,shutil,subprocess,sys,time,zipfile

SOURCE=Path(__file__).resolve().parents[1]
ROOT=SOURCE.parent
CACHE=Path('E:/CodexData/Companion/.build-cache')
WORK=CACHE/'shared-android-build'
sys.path.insert(0,str(ROOT.parent/'ai-collaboration-workflow/scripts'))
from development_storage import exclusive_build,preflight
sys.path.insert(0,str(ROOT/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits

def sha(path):
 with Path(path).open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--evidence',type=Path,required=True);a=parser.parse_args()
 output=a.evidence.resolve();assert output!=WORK and not output.is_relative_to(WORK) and not WORK.is_relative_to(output)
 assert not output.exists(),'Keep prior build evidence'
 # This entry compiles/packages only. Its private commit, CPU and low worker
 # priorities remain bounded; it may page under system RAM pressure. Model
 # inference and app acceptance retain their separate actual-pressure guards.
 limits=WorkerLimits(5,2*1024**3)
 jdk=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot');sdk=CACHE/'android-sdk';bt=sdk/'build-tools/36.0.0';gradle=CACHE/'gradle-9.7.1/bin/gradle.bat';jsonjar=CACHE/'android054-materials/json-20240303.jar'
 required=[jdk/'bin/java.exe',jdk/'bin/javac.exe',gradle,sdk/'platforms/android-35/android.jar',bt/'apksigner.bat',bt/'zipalign.exe',bt/'aapt2.exe',jsonjar,SOURCE/'node_modules/esbuild/bin/esbuild',SOURCE/'node_modules/typescript/bin/tsc',Path(os.environ['USERPROFILE'])/'.android/debug.keystore']
 missing=[str(p)for p in required if not p.is_file()];assert not missing,missing
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=SOURCE,text=True).strip(),'Freeze the complete software source before building'
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()
 configuration=(SOURCE/'apps/android/app/build.gradle').read_text(encoding='utf-8');version=int(re.search(r'versionCode (\d+)',configuration)[1]);version_name=re.search(r"versionName '([^']+)'",configuration)[1]
 aar=SOURCE/'apps/android/app/libs/companion-android-backend.aar';backend=json.loads(aar.with_suffix('.provenance.json').read_text(encoding='utf-8'));assert sha(aar)==backend['aarSha256']
 resources=json.loads((SOURCE/'apps/android/app/src/main/resources/com/denzic/companion/mobile/provenance.json').read_text(encoding='utf-8'))
 for row in resources['resources']:
  p=SOURCE/'apps/android/app/src/main/resources/com/denzic/companion/mobile'/row['name'];assert p.stat().st_size==row['bytes']and sha(p)==row['sha256']
 expected_json=json.loads((ROOT/'docs/handoffs/20261106-android-material-exports054/java-qa-dependency.json').read_text(encoding='utf-8'))['sha256'];assert sha(jsonjar)==expected_json
 with exclusive_build(CACHE/'.shared-android-build.lock'):
  storage=preflight(CACHE,reserve_gib=2)
  WORK.mkdir(exist_ok=True);output.mkdir(parents=True)
  env={**os.environ,'JAVA_HOME':str(jdk),'PATH':str(jdk/'bin')+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2','ANDROID_HOME':str(sdk),'ANDROID_SDK_ROOT':str(sdk),'GRADLE_USER_HOME':str(CACHE/'gradle-user'),'TEMP':str(WORK),'TMP':str(WORK)}
  record=dict(at=datetime.now().astimezone().isoformat(timespec='seconds'),state='BUILDING_COMPLETE_ANDROID_SOFTWARE_CANDIDATE',sourceCommit=commit,versionCode=version,versionName=version_name,sharedWorkspace=str(WORK),storageBefore=storage,nativeAarSha256=backend['aarSha256'],backendSourceCommit=backend['backendSourceCommit'],nativeLibrariesRebuilt=False,modelsRun=False,boardAccessed=False,phoneAccessed=False,steps=[])
  def save():(output/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  def run(name,args,cwd=SOURCE):
   started=time.monotonic()
   with (output/(name+'.log')).open('wb')as log:r=subprocess.run(list(map(str,args)),cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
   record['steps'].append(dict(name=name,exitCode=r.returncode,seconds=round(time.monotonic()-started,3)));save();print(name+': exit='+str(r.returncode),flush=True)
   assert r.returncode==0,(output/(name+'.log')).read_text(encoding='utf-8',errors='replace')[-4000:]
  save()
  try:
   run('selected-note-and-editor-ui',['node','tools/check_android_delivery_source.cjs'])
   run('mobile-source-and-web-build',[os.environ['COMSPEC'],'/d','/c','npm.cmd','run','build:mobile'])
   init=WORK/'shared-build-dir.gradle';init.write_text("allprojects { layout.buildDirectory.set(new File('"+str(WORK/'build').replace('\\','/')+"', project.name)) }\n",encoding='utf-8')
   run('normal-android-apk',[os.environ['COMSPEC'],'/d','/c',gradle,'--offline','--no-daemon','--max-workers=1','-Dorg.gradle.jvmargs=-Xmx768m','--project-cache-dir',WORK/'gradle-project','-I',init,':app:assembleDebug'],SOURCE/'apps/android')
   classes=WORK/'build/app/intermediates/javac/debug/compileDebugJavaWithJavac/classes';assert(classes/'com/denzic/companion/app/ExportContents.class').is_file()
   qa=WORK/'qa-classes';qa.mkdir(exist_ok=True);backend_classes=WORK/'backend-classes.jar'
   with zipfile.ZipFile(aar)as z:backend_classes.write_bytes(z.read('classes.jar'))
   cp=os.pathsep.join(str(p)for p in [qa,jsonjar,classes,backend_classes,sdk/'platforms/android-35/android.jar'])
   run('compile-real-backend-selection-check',[jdk/'bin/javac.exe','-encoding','UTF-8','-cp',cp,'-d',qa,SOURCE/'apps/android/app/src/test/java/com/denzic/companion/app/ContentExportTest.java'])
   run('actual-java-store-preview-export-reopen',[jdk/'bin/java.exe','-Xmx256m','-cp',cp,'com.denzic.companion.app.ContentExportTest',output/'public-java-flow'])
   apk=WORK/'build/app/outputs/apk/debug/app-debug.apk';assert apk.is_file()
   with zipfile.ZipFile(apk)as z,zipfile.ZipFile(aar)as native:
    assets=[]
    for p in (SOURCE/'apps/mobile/dist').rglob('*'):
     if p.is_file():
      path=p.relative_to(SOURCE/'apps/mobile/dist').as_posix();assert hashlib.sha256(z.read('assets/www/'+path)).hexdigest()==sha(p),path;assets.append(dict(path=path,sha256=sha(p)))
    libs=[]
    for path in native.namelist():
     if path.startswith('jni/arm64-v8a/')and path.endswith('.so'):
      data=native.read(path);assert z.read('lib/'+path[4:])==data;libs.append(dict(path=path,sha256=hashlib.sha256(data).hexdigest()))
    for row in resources['resources']:assert hashlib.sha256(z.read('com/denzic/companion/mobile/'+row['name'])).hexdigest()==row['sha256']
   run('apk16k-alignment',[bt/'zipalign.exe','-c','-P','16','4',apk])
   run('apk-signature',[os.environ['COMSPEC'],'/d','/c',bt/'apksigner.bat','verify','--verbose','--print-certs',apk])
   signature=(output/'apk-signature.log').read_text(encoding='utf-8');signer=re.search(r'Signer #1 certificate SHA-256 digest: (\w+)',signature)[1];assert signer=='ecebce83705d3336731610451cd1685cadb2d87fba29e41a471b2b44d46c45da'
   run('apk-identity',[bt/'aapt2.exe','dump','badging',apk]);assert f"package: name='com.denzic.companion.app' versionCode='{version}' versionName='{version_name}'"in(output/'apk-identity.log').read_text(encoding='utf-8')
   target=output/('Companion-Android-'+version_name+'.apk');shutil.copyfile(apk,target)
   assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip()==commit and not subprocess.check_output(['git','diff','--name-only'],cwd=SOURCE,text=True).strip(),'Source changed during build'
   record.update(state='ANDROID_SOFTWARE_CANDIDATE_BUILT_SOURCE_NATIVE_PAYLOAD_SIGNER_AND_DATA_FLOW_VERIFIED',apk=str(target),apkSha256=sha(target),apkBytes=target.stat().st_size,signerSha256=signer,signerMatchesExisting141=True,zip16KiBAligned=True,webAssets=assets,nativeLibraries=libs,intermediateCopies=0,phoneInstalled=False,physicalTotalAcceptancePassed=False,saleQualified=False)
  except BaseException as error:record.update(state='ANDROID_LOCAL_BUILD_NOT_CONFIRMED_FAILURE_RETAINED',error=str(error));save();raise
  save();print(json.dumps({k:v for k,v in record.items()if k not in ['steps','webAssets','nativeLibraries']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
