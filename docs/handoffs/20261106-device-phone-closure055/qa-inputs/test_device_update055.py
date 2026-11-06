from pathlib import Path
import subprocess,os,json,time
from datetime import datetime
from zoneinfo import ZoneInfo
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'companion-device-closure055';backend=r/'companion-android-device-closure055';b=r/'docs/handoffs/20261106-device-phone-closure055';c=Path('E:/CodexData/Companion/.build-cache/device-phone055');j=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');sdk='E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar';jsonjar='E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar'
classes=c/('verification-classes-'+str(time.time_ns()));classes.mkdir();env={**os.environ,'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2'}
sources=list((backend/'apps/android-backend/src/main/java').rglob('*.java'))+list((s/'apps/android/app/src/main/java').rglob('*.java'))+[backend/'apps/android-backend/src/test/java/com/denzic/companion/mobile/SystemUpdateTest.java']
log=b/('ota-java-verification-'+str(time.time_ns())+'.log');started=time.perf_counter()
with log.open('wb') as out:
 compile=subprocess.run([str(j/'javac.exe'),'--release','8','-encoding','UTF-8','-classpath',sdk,'-d',str(classes),*map(str,sources)],env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 assert compile.returncode==0,log.read_text(encoding='utf-8',errors='replace')
 test=subprocess.run([str(j/'java.exe'),'-Xmx384m','-classpath',str(classes)+os.pathsep+jsonjar+os.pathsep+sdk,'com.denzic.companion.mobile.SystemUpdateTest','E:/CodexData/Companion/.build-cache/firmware/fw66685-package'],env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
record={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'result':'PASS_HOST_ONLY' if test.returncode==0 else 'FAIL_HOST_CHECK','compileExitCode':compile.returncode,'testExitCode':test.returncode,'wallSeconds':round(time.perf_counter()-started,3),'log':str(log),'classesDirectory':str(classes),'physicalHardwareUsed':False,'modelRun':False}
(b/'ota-java-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,ensure_ascii=False));print(log.read_text(encoding='utf8',errors='replace')[-4500:]);assert test.returncode==0
