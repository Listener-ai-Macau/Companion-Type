from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import os,subprocess,json,time,hashlib,zipfile,shutil,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/android-trash071'
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/trash071');J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot');SDK=Path('E:/CodexData/Companion/.build-cache/android-sdk');GRADLE=Path('E:/CodexData/Companion/.build-cache/gradle-9.7.1/bin/gradle.bat')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=json.loads((O/'source-release.json').read_text(encoding='utf8'))
def git(*args):return subprocess.check_output(['git',*args],cwd=S,text=True,encoding='utf8').strip()
assert git('status','--porcelain')=='' and git('rev-parse','HEAD')==source['sourceCommit']
names=git('ls-files','apps/android','apps/mobile','packages/ui','package.json','package-lock.json').splitlines()
frozen=[{'path':n,'sha256':sha(S/n)} for n in names if (S/n).is_file()]
(O/'source-frozen.json').write_text(json.dumps({'sourceCommit':source['sourceCommit'],'files':frozen},indent=2),encoding='utf8')
aar=S/'apps/android/app/libs/companion-android-backend.aar';provenance=json.loads(aar.with_suffix('.provenance.json').read_text(encoding='utf8'));assert sha(aar)==provenance['aarSha256']
with zipfile.ZipFile(aar) as z:native=hashlib.sha256(z.read('jni/arm64-v8a/libcompanion_mobile_audio.so')).hexdigest()
assert native==provenance['nativeLibrarySha256']=='212ec44db8f2b06d2d3c3dc5e16fb2c8ff14f88c29fe6e7a0003c45a045df08f'
psutil.Process().cpu_affinity([12,13]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
env={**os.environ,'JAVA_HOME':str(J),'PATH':str(J/'bin')+os.pathsep+'C:/Program Files/nodejs'+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2','ANDROID_HOME':str(SDK),'ANDROID_SDK_ROOT':str(SDK),'GRADLE_USER_HOME':'E:/CodexData/Companion/.build-cache/gradle-user','TEMP':str(C),'TMP':str(C)}
init=C/'own-build-dir.gradle';init.write_text("allprojects { layout.buildDirectory.set(new File('"+str(C/'build').replace('\\','/')+"', project.name)) }\n")
start=time.perf_counter();log=O/('apk-build-'+str(time.time_ns())+'.log')
with log.open('wb') as stream:
 p=subprocess.run(['C:/Program Files/nodejs/node.exe','C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js','run','build:mobile'],cwd=S,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW);assert p.returncode==0,log.read_text(encoding='utf8',errors='replace')[-4000:]
 p=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(GRADLE),'--offline','--no-daemon','--max-workers=1','-Dorg.gradle.jvmargs=-Xmx768m','--project-cache-dir',str(C/'gradle-project'),'-I',str(init),':app:assembleDebug'],cwd=S/'apps/android',env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
assert p.returncode==0,log.read_text(encoding='utf8',errors='replace')[-5000:]
for row in frozen:assert sha(S/row['path'])==row['sha256'],row['path']
generated=C/'build/app/outputs/apk/debug/app-debug.apk';assert generated.is_file()
apk=O/'Companion-Android-0.1.69-本机保护与回收站.apk';shutil.copy2(generated,apk)
assets={p.relative_to(S/'apps/mobile/dist').as_posix():p for p in (S/'apps/mobile/dist').rglob('*') if p.is_file()}
with zipfile.ZipFile(apk) as z:
 assert hashlib.sha256(z.read('lib/arm64-v8a/libcompanion_mobile_audio.so')).hexdigest()==native
 for name,path in assets.items():assert hashlib.sha256(z.read('assets/www/'+name)).hexdigest()==sha(path),name
sign=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(SDK/'build-tools/36.0.0/apksigner.bat'),'verify','--print-certs',str(apk)],capture_output=True,text=True,encoding='utf8',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW);assert sign.returncode==0,sign.stdout+sign.stderr
(O/'signature-verification.log').write_text(sign.stdout+sign.stderr,encoding='utf8')
badging=subprocess.run([str(SDK/'build-tools/36.0.0/aapt2.exe'),'dump','badging',str(apk)],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW);assert badging.returncode==0 and "versionCode='69'" in badging.stdout and "versionName='0.1.69'" in badging.stdout
(O/'apk-identity.log').write_text(badging.stdout,encoding='utf8')
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'ANDROID069_LOCAL_PROTECTION_TRASH_RECOVERY_CANDIDATE_BUILT_BACKGROUND_CHECKED_UNINSTALLED','sourceCommit':source['sourceCommit'],'apk':str(apk),'apkSha256':sha(apk),'versionName':'0.1.69','versionCode':69,'wallSeconds':round(time.perf_counter()-start,3),'workers':1,'cpuSlots':[12,13],'javaHeapMiB':768,'assetsMatched':len(assets),'nativeLibrarySha256':native,'nativeSpeechRebuilt':False,'aarSha256':sha(aar),'inheritedBackendSourceCommit':provenance['backendSourceCommit'],'installed':False,'computerUse':False,'phoneIo':False,'modelsRun':False,'actualPhoneLifecycleQualified':False,'wholeProductQualified':False}
(O/'apk-build-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False),flush=True)
