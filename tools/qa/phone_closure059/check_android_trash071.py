from pathlib import Path
import os,subprocess,hashlib,json,zipfile,psutil,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/android-trash071';O.mkdir(exist_ok=True)
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/trash071');C.mkdir(exist_ok=True)
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');API=Path('E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar');JSON=Path('E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar')
aar=S/'apps/android/app/libs/companion-android-backend.aar';receipt=json.loads(aar.with_suffix('.provenance.json').read_text(encoding='utf8'))
assert hashlib.sha256(aar.read_bytes()).hexdigest()==receipt['aarSha256']
with zipfile.ZipFile(aar) as z:(C/'backend-classes.jar').write_bytes(z.read('classes.jar'))
classes=C/'classes';classes.mkdir(exist_ok=True)
env={**os.environ,'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2 -Xmx384m'}
psutil.Process().cpu_affinity([12,13]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
results=[]
def run(name,args,cwd=S):
 start=time.perf_counter();p=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
 (O/(name+'.log')).write_text(p.stdout+p.stderr,encoding='utf8');row={'name':name,'exitCode':p.returncode,'seconds':round(time.perf_counter()-start,3)};results.append(row)
 (O/'checks.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(json.dumps(row),flush=True)
 assert p.returncode==0,(p.stdout+p.stderr)[-5000:]
cp=os.pathsep.join([str(API),str(C/'backend-classes.jar')])
run('full-app-java-compile',[J/'javac.exe','--release','8','-encoding','UTF-8','-cp',cp,'-d',classes,*sorted((S/'apps/android/app/src/main/java').rglob('*.java')),S/'tools/LocalRecordingLifecycle071Test.java'])
cp=os.pathsep.join([str(classes),str(C/'backend-classes.jar'),str(JSON),str(API)])
run('local-lifecycle-data-safety',[J/'java.exe','-Xmx192m','-cp',cp,'com.denzic.companion.app.LocalRecordingLifecycle071Test',C])
run('mobile-types',['C:/Program Files/nodejs/node.exe','node_modules/typescript/bin/tsc','-p','apps/mobile/tsconfig.json','--noEmit'])
print('All current Android lifecycle checks passed. No UI, model or device IO.',flush=True)
