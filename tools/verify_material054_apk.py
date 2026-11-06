from pathlib import Path
import subprocess,os,json,re,hashlib,zipfile,shutil
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'recovered-software050';b=r/'docs/handoffs/20261106-android-material-exports054';c=Path('E:/CodexData/Companion/.build-cache/android054-materials')
apk=c/'build/app/outputs/apk/debug/app-debug.apk';bt=Path('E:/CodexData/Companion/.build-cache/android-sdk/build-tools/36.0.0');j=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot')
env={**os.environ,'JAVA_HOME':str(j),'PATH':str(j/'bin')+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2'}
def run(args):
 p=subprocess.run([str(x) for x in args],env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);assert p.returncode==0,p.stdout+p.stderr;return p.stdout+p.stderr
assert json.loads((b/'apk-build-result.json').read_text(encoding='utf8'))['exitCode']==0
badging=run([bt/'aapt2.exe','dump','badging',apk]);assert "package: name='com.denzic.companion.app' versionCode='54' versionName='0.1.54'" in badging
def signer(path):
 text=run([os.environ['COMSPEC'],'/d','/c',bt/'apksigner.bat','verify','--verbose','--print-certs',path]);m=re.search(r'Signer #1 certificate SHA-256 digest: (\w+)',text);assert m,text;return m.group(1),text
current,proof=signer(apk);previous,_=signer(r/'docs/handoffs/20261105-ai-workspace050-preserved/Companion-Android-0.1.50-会议AI工作台-r2.apk');assert current==previous
(b/'apk-signature.log').write_text(proof,encoding='utf8');run([bt/'zipalign.exe','-c','-P','16','4',apk])
assets=[]
with zipfile.ZipFile(apk) as z,zipfile.ZipFile(s/'apps/android/app/libs/companion-android-backend.aar') as aar:
 for p in (s/'apps/mobile/dist').rglob('*'):
  if p.is_file():
   name=p.relative_to(s/'apps/mobile/dist').as_posix();expected=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(z.read('assets/www/'+name)).hexdigest()==expected;assets.append({'path':name,'sha256':expected})
 native=[]
 for n in aar.namelist():
  if n.startswith('jni/arm64-v8a/') and n.endswith('.so'):
   value=aar.read(n);assert value==z.read(n.replace('jni/','lib/',1));native.append({'name':n,'sha256':hashlib.sha256(value).hexdigest()})
 assert len(native)==3
dest=b/'Companion-Android-0.1.54-材料导出与导图.apk';shutil.copy2(apk,dest)
record={'status':'ANDROID054_APK_VERSION_SIGNATURE_WEB_ASSETS_NATIVE_PAYLOAD_AND_16K_ALIGNMENT_VERIFIED','versionName':'0.1.54','versionCode':54,'apk':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'signerMatches050r2':True,'certificateSha256':current,'zip16KiBAligned':True,'webAssets':assets,'nativeLibrariesIdenticalTo053Aar':native,'backendSourceCommit':json.loads((s/'apps/android/app/libs/companion-android-backend.provenance.json').read_text(encoding='utf8'))['backendSourceCommit'],'ownerAppInstalledThisBatch':False,'phoneBitmapTest':'phone-native-result.json','windowsInstalledThisBatch':False,'modelsRun':False}
(b/'apk-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in record.items() if k not in ['webAssets','nativeLibrariesIdenticalTo053Aar']},ensure_ascii=False))
