from pathlib import Path
import os,subprocess,json,time,hashlib
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'companion-device-closure055';b=r/'docs/handoffs/20261106-device-phone-closure055';c=Path('E:/CodexData/Companion/.build-cache/device-phone055');j=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot');sdk=Path('E:/CodexData/Companion/.build-cache/android-sdk');gradle=Path('E:/CodexData/Companion/.build-cache/gradle-9.7.1/bin/gradle.bat')
env={**os.environ,'JAVA_HOME':str(j),'PATH':str(j/'bin')+os.pathsep+'C:/Program Files/nodejs'+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2','ANDROID_HOME':str(sdk),'ANDROID_SDK_ROOT':str(sdk),'GRADLE_USER_HOME':'E:/CodexData/Companion/.build-cache/gradle-user','TEMP':str(c),'TMP':str(c)}
receipt=json.loads((s/'apps/android/app/libs/companion-android-backend.provenance.json').read_text());assert hashlib.sha256((s/'apps/android/app/libs/companion-android-backend.aar').read_bytes()).hexdigest()==receipt['aarSha256']
init=c/'own-build-dir.gradle';init.write_text("allprojects { layout.buildDirectory.set(new File('"+str(c/'build').replace('\\','/')+"', project.name)) }\n")
log=b/('apk-build-'+str(time.time_ns())+'.log');started=time.perf_counter()
with log.open('wb') as out:
 p=subprocess.run(['C:/Program Files/nodejs/npm.cmd','run','build:mobile'],cwd=s,env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS);assert p.returncode==0,log.read_text(encoding='utf-8',errors='replace')
 p=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(gradle),'--offline','--no-daemon','--max-workers=1','-Dorg.gradle.jvmargs=-Xmx768m','--project-cache-dir',str(c/'gradle-project'),'-I',str(init),':app:assembleDebug'],cwd=s/'apps/android',env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
record={'exitCode':p.returncode,'wallSeconds':round(time.perf_counter()-started,3),'sourceWorkspace':str(s),'cache':str(c),'log':str(log),'workers':1,'javaHeapMiB':768,'nativeSpeechRebuild':False,'modelsRun':False}
(b/'apk-build-result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));print(log.read_text(encoding='utf8',errors='replace')[-4500:]);assert p.returncode==0
