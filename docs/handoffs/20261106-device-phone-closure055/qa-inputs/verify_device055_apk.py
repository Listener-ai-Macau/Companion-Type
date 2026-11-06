from pathlib import Path
import subprocess,os,json,re,hashlib,zipfile,shutil
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'companion-device-closure055';b=r/'docs/handoffs/20261106-device-phone-closure055';c=Path('E:/CodexData/Companion/.build-cache/device-phone055')
apk=c/'build/app/outputs/apk/debug/app-debug.apk';bt=Path('E:/CodexData/Companion/.build-cache/android-sdk/build-tools/36.0.0');j=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot')
env={**os.environ,'JAVA_HOME':str(j),'PATH':str(j/'bin')+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2'}
def run(args):
 p=subprocess.run([str(x) for x in args],env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);assert p.returncode==0,p.stdout+p.stderr;return p.stdout+p.stderr
assert json.loads((b/'apk-build-result.json').read_text())['exitCode']==0
badging=run([bt/'aapt2.exe','dump','badging',apk]);assert "package: name='com.denzic.companion.app' versionCode='55' versionName='0.1.55'" in badging
def signer(file):
 text=run([os.environ['COMSPEC'],'/d','/c',bt/'apksigner.bat','verify','--verbose','--print-certs',file]);m=re.search(r'Signer #1 certificate SHA-256 digest: (\w+)',text);assert m,text;return m.group(1),text
current,proof=signer(apk);previous,_=signer(r/'docs/handoffs/20261105-ai-workspace050-preserved/Companion-Android-0.1.50-会议AI工作台-r2.apk');assert current==previous
(b/'apk-signature.log').write_text(proof,encoding='utf8');run([bt/'zipalign.exe','-c','-P','16','4',apk])
assets=[];native=[]
with zipfile.ZipFile(apk) as z,zipfile.ZipFile(s/'apps/android/app/libs/companion-android-backend.aar') as aar:
 for p in (s/'apps/mobile/dist').rglob('*'):
  if p.is_file():
   name=p.relative_to(s/'apps/mobile/dist').as_posix();expected=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(z.read('assets/www/'+name)).hexdigest()==expected;assets.append({'path':name,'sha256':expected})
 for name in aar.namelist():
  if name.startswith('jni/arm64-v8a/') and name.endswith('.so'):
   value=aar.read(name);assert value==z.read(name.replace('jni/','lib/',1));native.append({'name':name,'sha256':hashlib.sha256(value).hexdigest()})
 assert len(native)==3
dest=b/'Companion-Android-0.1.55-设备连接维护与升级.apk';shutil.copy2(apk,dest)
record={'status':'ANDROID055_APK_VERSION_SIGNATURE_WEB_ASSETS_NATIVE_PAYLOAD_AND_16K_ALIGNMENT_VERIFIED','versionName':'0.1.55','versionCode':55,'apk':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'signerMatches050r2':True,'certificateSha256':current,'zip16KiBAligned':True,'webAssets':assets,'nativeLibrariesUnchanged':native,'backendSourceCommit':json.loads((s/'apps/android/app/libs/companion-android-backend.provenance.json').read_text())['backendSourceCommit'],'ownerAppInstalledThisBatch':False,'windowsInstalledThisBatch':False,'modelsRun':False}
(b/'apk-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in record.items() if k not in ('webAssets','nativeLibrariesUnchanged')},ensure_ascii=False))
