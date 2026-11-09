"""Package the one unified Android cohort; do not install or run a model."""
from pathlib import Path
from datetime import datetime
import ast,hashlib,json,os,re,shutil,struct,subprocess,sys,time,uuid,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-core-android20261109';W=R/'companion-device-closure055';C=R/'docs/handoffs/20261109-core-acceptance';O=C/'android110';O.mkdir(exist_ok=True)
D=Path('E:/CodexData/Companion/.build-cache/core-acceptance20261109')/('android110-'+uuid.uuid4().hex);D.mkdir()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
aar=S/'apps/android/app/libs/companion-android-backend.aar';receipt=json.loads(aar.with_suffix('.provenance.json').read_text(encoding='utf8'));assert receipt['backendSourceCommit']=='608790132701ede93fa24a00b687874cb7e70c6b' and sha(aar)==receipt['aarSha256']
p=S/'apps/android/app/build.gradle';raw=p.read_bytes();assert b'versionCode 109' in raw and b"versionName '0.1.109'" in raw;p.write_bytes(raw.replace(b'versionCode 109',b'versionCode 110').replace(b"versionName '0.1.109'",b"versionName '0.1.110'"))
tree=ast.parse((W/'docs/handoffs/model-joint-neural-spatial-20261108/preserve_joint_neural_spatial_20261108.py').read_text(encoding='utf8'));scope={'os':os,'subprocess':subprocess,'env':{**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':'ssh -o HostName=github.com -p 22 -o ProxyCommand=none -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2'}};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['git','ship']],type_ignores=[]),'<existing-publisher>','exec'),scope)
head=scope['ship'](S,['apps/android/app/build.gradle'],'Freeze Android110 for the unified recording library and meeting candidate')
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits,SystemRamPressure
pressure=SystemRamPressure();assert not pressure.low(),'Actual Windows low-memory signal; keep the remote source checkpoint, no build started'
limits=WorkerLimits(cpu_percent=5,memory_bytes=1536*1024**2)
java=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot');sdk=Path('E:/CodexData/Companion/.build-cache/android-sdk');gradle=Path('E:/CodexData/Companion/.build-cache/gradle-9.7.1/bin/gradle.bat');assert (java/'bin/java.exe').is_file() and gradle.is_file() and sdk.is_dir()
env={**os.environ,'JAVA_HOME':str(java),'PATH':str(java/'bin')+os.pathsep+os.environ['PATH'],'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2','ANDROID_HOME':str(sdk),'ANDROID_SDK_ROOT':str(sdk),'GRADLE_USER_HOME':'E:/CodexData/Companion/.build-cache/gradle-user','TEMP':str(D),'TMP':str(D)}
record={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'BUILDING_ONE_UNIFIED_ANDROID_CANDIDATE','sourceCommit':head,'versionName':'0.1.110','versionCode':110,'backendSourceCommit':receipt['backendSourceCommit'],'backendAarSha256':sha(aar),'newNativeBackendBuilt':False,'modelsRun':False,'deviceAccess':False,'phoneAccess':False,'installed':False,'wholeProductQualified':False,'privateBuildDirectory':str(D),'steps':[]}
def save():(O/'build-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def run(name,args,cwd=S):
 started=time.perf_counter()
 with (O/(name+'.log')).open('wb') as log:
  p=subprocess.Popen(list(map(str,args)),cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  while p.poll() is None:
   if pressure.low():
    import psutil
    parent=psutil.Process(p.pid)
    for child in reversed(parent.children(recursive=True)):
     try:child.terminate()
     except psutil.NoSuchProcess:pass
    parent.terminate();record['stoppedForActualLowMemory']=True;save();raise RuntimeError('Actual low-memory signal; stopped only the owned build family')
   time.sleep(.5)
 record['steps'].append({'name':name,'exitCode':p.returncode,'seconds':time.perf_counter()-started});save();assert p.returncode==0,name+' failed; see retained log'
 return O/(name+'.log')
save()
try:
 node=Path('C:/Program Files/nodejs/node.exe');npm=Path('C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js')
 run('01-npm-ci',[node,npm,'ci','--prefer-offline','--no-audit','--no-fund'])
 run('02-mobile-web',[node,npm,'run','build:mobile'])
 web=S/'apps/mobile/dist';web_manifest=[{'path':p.relative_to(web).as_posix(),'sha256':sha(p)} for p in web.rglob('*') if p.is_file()];assert (web/'index.html').is_file()
 init=D/'own-build-dir.gradle';init.write_text("allprojects { layout.buildDirectory.set(new File('"+str(D/'build').replace('\\','/')+"', project.name)) }\n",encoding='utf8')
 run('03-assemble-current-native-and-ui',[os.environ['COMSPEC'],'/d','/c',gradle,'--offline','--no-daemon','--max-workers=1','-Dorg.gradle.jvmargs=-Xmx768m','--project-cache-dir',D/'gradle-project','-I',init,':app:assembleDebug'],S/'apps/android')
 built=D/'build/app/outputs/apk/debug/app-debug.apk';assert built.is_file();apk=O/'Companion-Android-0.1.110-core-candidate.apk';shutil.copy2(built,apk)
 tools=next(p for p in sorted((sdk/'build-tools').iterdir(),reverse=True) if (p/'apksigner.bat').is_file() and (p/'zipalign.exe').is_file() and (p/'aapt2.exe').is_file())
 old=R/'docs/handoffs/20261109-mobile-library-location/phone100/Companion-Android-0.1.100-录音与内容修复候选.apk'
 new_sign=run('04-new-apk-signature',[os.environ['COMSPEC'],'/d','/c',tools/'apksigner.bat','verify','--print-certs',apk])
 old_sign=run('05-known-app-signature',[os.environ['COMSPEC'],'/d','/c',tools/'apksigner.bat','verify','--print-certs',old])
 certificate=lambda p:re.search(r'Signer #1 certificate SHA-256 digest: ([a-fA-F0-9]+)',p.read_text(encoding='utf8')).group(1)
 assert certificate(new_sign)==certificate(old_sign)
 run('06-apk-alignment',[tools/'zipalign.exe','-c','-P','16','4',apk])
 info=run('07-package-identity',[tools/'aapt2.exe','dump','badging',apk]).read_text(encoding='utf8');assert "name='com.denzic.companion.app'" in info and "versionCode='110'" in info and "versionName='0.1.110'" in info
 native=[]
 with zipfile.ZipFile(aar) as source,zipfile.ZipFile(apk) as package:
  for name in source.namelist():
   if not name.startswith('jni/arm64-v8a/') or not name.endswith('.so'):continue
   raw=source.read(name);packed=package.read('lib/'+name[4:]);assert packed==raw
   assert raw[:5]==b'\x7fELF\x02' and raw[5]==1
   off=struct.unpack_from('<Q',raw,32)[0];size,count=struct.unpack_from('<HH',raw,54);align=[]
   for i in range(count):
    if struct.unpack_from('<I',raw,off+i*size)[0]==1:align.append(struct.unpack_from('<Q',raw,off+i*size+48)[0])
   assert align and min(align)>=16384,name
   native.append({'name':name,'sha256':hashlib.sha256(raw).hexdigest(),'elf16KiBAligned':True})
  for item in web_manifest:assert hashlib.sha256(package.read('assets/www/'+item['path'])).hexdigest()==item['sha256'],item['path']
 assert sha(aar)==record['backendAarSha256']
 record.update(state='ANDROID110_UNIFIED_SOURCE_SIGNED_PAYLOAD_VERIFIED_PHONE_PENDING',finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),apk=str(apk),apkSha256=sha(apk),apkBytes=apk.stat().st_size,signerMatchesPreviouslyTrustedApp=True,zip16KiBAligned=True,nativeLibraries=native,webAssets=web_manifest,cpuAndMemory=limits.query(),phoneOrdinaryFlowQualified=False)
 save();print(json.dumps({k:v for k,v in record.items() if k not in ['steps','webAssets','nativeLibraries','cpuAndMemory']},ensure_ascii=False),flush=True)
except BaseException as error:record.update(state='ANDROID_UNIFIED_BUILD_STOPPED_FAILURE_RETAINED',error=repr(error),finishedAt=datetime.now().astimezone().isoformat(timespec='seconds'),cpuAndMemory=limits.query());save();raise
finally:pressure.close()
