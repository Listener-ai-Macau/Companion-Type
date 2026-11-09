from pathlib import Path
from datetime import datetime
import hashlib,json,os,shlex,subprocess,sys,wave,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');M=R/'model-research';C=Path(__file__).parent
assert not (C/'closed-unstarted.json').exists(),'This standalone entry was retired after actual startup/install failures; do not blindly retry it'
P=Path('E:/CodexData/Companion/.model-cache/paired-real-alimeeting-20261109/mobile-product-baseline');P.mkdir(exist_ok=True)
A=R/'.cache/ble-rate-20261019/android-central-diagnostic/platform-tools/adb.exe';PKG='com.denzic.companion.app';REMOTE='/data/user/0/'+PKG+'/cache/paired-asr-20261109-r1'
def command(args,**kwargs):
    q=subprocess.run(list(map(str,args)),capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,**kwargs)
    if q.returncode:(P/'command-failure.txt').write_bytes(q.stdout+q.stderr);raise RuntimeError('Owned comparator preparation failed; local evidence retained')
    return q.stdout
def adb(args):
    if args[0]=='shell':args=['shell',shlex.join(list(map(str,args[1:])))]
    return command([A,'-s','d6bd213d',*args])
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
sys.path.insert(0,str(M/'src'));from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=384*1024**2)
sdk=Path('E:/CodexData/Companion/.build-cache/android-sdk');bt=sdk/'build-tools/36.0.0';java=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');api=sdk/'platforms/android-35/android.jar';classes=P/'classes';classes.mkdir(exist_ok=True)
source=M/'src/CompanionPairedPhoneAsr20261109.java'
command([java/'javac.exe','-J-Xmx128m','--release','8','-encoding','UTF-8','-cp',api,'-d',classes,source])
jar=P/'classes.jar'
with zipfile.ZipFile(jar,'w') as z:
    for f in classes.rglob('*.class'):z.write(f,f.relative_to(classes).as_posix())
dex=P/'dex';dex.mkdir(exist_ok=True)
command([java/'java.exe','-Xmx160m','-XX:ActiveProcessorCount=1','-cp',bt/'lib/d8.jar','com.android.tools.r8.D8','--min-api','30','--lib',api,'--output',dex,jar])
driver=P/'companion-paired-asr-20261109.jar'
with zipfile.ZipFile(driver,'w') as z:z.write(dex/'classes.dex','classes.dex')
adb(['shell','run-as',PKG,'mkdir','-p',REMOTE]);adb(['push',driver,'/data/local/tmp/companion-paired-asr-20261109.jar'])
first=json.loads((C.parent/'fixed-asr-audio-only.json').read_text())[0];smoke=P/'public-first30s.wav'
with wave.open(first['audio'],'rb') as original,wave.open(str(smoke),'wb') as out:out.setparams(original.getparams());out.writeframes(original.readframes(30*16000))
adb(['push',smoke,'/data/local/tmp/companion-paired-first30s.wav']);adb(['shell','run-as',PKG,'cp','/data/local/tmp/companion-paired-first30s.wav',REMOTE+'/public-first30s.wav']);adb(['shell','rm','/data/local/tmp/companion-paired-first30s.wav'])
inputs=[{'id':'compat-first30s','wav':'public-first30s.wav','sha256':sha(smoke)}];manifest=P/'audio-only.json';manifest.write_text(json.dumps(inputs)+'\n')
adb(['push',manifest,'/data/local/tmp/companion-paired-input.json']);adb(['shell','run-as',PKG,'cp','/data/local/tmp/companion-paired-input.json',REMOTE+'/audio-only.json']);adb(['shell','rm','/data/local/tmp/companion-paired-input.json'])
apk=json.loads((C/'phone-preflight.json').read_text())['apkPath']
inner='CLASSPATH=/data/local/tmp/companion-paired-asr-20261109.jar taskset 3 /system/bin/app_process /system/bin com.denzic.companion.qa.CompanionPairedPhoneAsr20261109 '+shlex.join([apk,REMOTE,'inventory'])
result=adb(['shell','run-as',PKG,'sh','-c',inner]).decode();(C/'native-api-inventory.txt').write_text(result)
actual=json.loads(adb(['shell','run-as',PKG,'cat',REMOTE+'/state.json']))
assert actual['state']=='INSTALLED_NATIVE_ASR_API_LOADED_NO_MODEL' and actual['mode']=='inventory','A zero shell exit code is insufficient proof of a started ART worker'
record={'at':datetime.now().astimezone().isoformat(),'state':'INSTALLED_PHONE_NATIVE_ASR_API_INVENTORY_PASSED','driverSha256':sha(driver),'sourceSha256':sha(source),'smokeAudioSha256':sha(smoke),'classLoaderUsesInstalledApk':True,'newApkInstalled':False,'mainDisplayUsed':False,'modelWeightsChanged':False,'referencePassed':False,'phoneCpuMask':'0,1','androidPriority':'THREAD_PRIORITY_LOWEST','limits':limits.query()}
(C/'prepared.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');(P/'run-command.json').write_text(json.dumps({'adb':str(A),'serial':'d6bd213d','remote':REMOTE,'command':['shell','run-as',PKG,'sh','-c',inner.removesuffix('inventory')+'run']}))
print(json.dumps(record,ensure_ascii=False))
