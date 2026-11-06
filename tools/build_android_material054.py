from pathlib import Path
import os,subprocess,json,time,hashlib,psutil
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'recovered-software050';b=r/'docs/handoffs/20261106-android-material-exports054'
c=Path('E:/CodexData/Companion/.build-cache/android054-materials');c.mkdir(parents=True,exist_ok=True)
j=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot');sdk=Path('E:/CodexData/Companion/.build-cache/android-sdk');gradle=Path('E:/CodexData/Companion/.build-cache/gradle-9.7.1/bin/gradle.bat')
assert gradle.is_file() and (j/'bin/java.exe').is_file() and (s/'apps/mobile/dist/index.html').is_file()
receipt=json.loads((s/'apps/android/app/libs/companion-android-backend.provenance.json').read_text(encoding='utf8'))
assert hashlib.sha256((s/'apps/android/app/libs/companion-android-backend.aar').read_bytes()).hexdigest()==receipt['aarSha256']
init=c/'own-build-dir.gradle';init.write_text("allprojects { layout.buildDirectory.set(new File('"+str(c/'build').replace('\\','/')+"', project.name)) }\n",encoding='utf8')
env={**os.environ,'JAVA_HOME':str(j),'PATH':str(j/'bin')+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2','ANDROID_HOME':str(sdk),'ANDROID_SDK_ROOT':str(sdk),'GRADLE_USER_HOME':'E:/CodexData/Companion/.build-cache/gradle-user','TEMP':str(c),'TMP':str(c)}
cmd=[os.environ['COMSPEC'],'/d','/c',str(gradle),'--offline','--no-daemon','--max-workers=1','-Dorg.gradle.jvmargs=-Xmx768m','--project-cache-dir',str(c/'gradle-project'),'-I',str(init),':app:assembleDebug']
import shutil
if (b/'apk-build.log').exists() and not (b/'apk-build-initial-provider-failure.log').exists():
 shutil.copy2(b/'apk-build.log',b/'apk-build-initial-provider-failure.log');shutil.copy2(b/'apk-build-result.json',b/'apk-build-initial-provider-failure.json')
start=time.perf_counter();logpath=b/('apk-build-'+str(time.time_ns())+'.log')
with logpath.open('wb') as log:p=subprocess.run(cmd,cwd=s/'apps/android',env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
record={'exitCode':p.returncode,'wallSeconds':round(time.perf_counter()-start,3),'workers':1,'javaHeapMiB':768,'sourceWorkspace':str(s),'nativeSpeechRebuild':False,'modelsRun':False,'cache':str(c),'log':str(logpath)}
(b/'apk-build-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(record,ensure_ascii=False));print(logpath.read_text(encoding='utf8',errors='replace')[-4000:]);assert p.returncode==0
