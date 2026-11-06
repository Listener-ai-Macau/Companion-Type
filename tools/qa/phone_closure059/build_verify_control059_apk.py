from pathlib import Path
import hashlib, json, os, re, shutil, subprocess, sys, time, zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion')
S=R/'companion-device-closure055'
VERSION=int(sys.argv[1]) if len(sys.argv)>1 else 59
F=Path(sys.argv[2]) if len(sys.argv)>2 else R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058'
C=Path('E:/CodexData/Companion/.build-cache/device-phone055')
SDK=Path('E:/CodexData/Companion/.build-cache/android-sdk')
BT=SDK/'build-tools/36.0.0'
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot')
GRADLE=Path('E:/CodexData/Companion/.build-cache/gradle-9.7.1/bin/gradle.bat')
READELF=Path('E:/CodexData/Companion/.build-cache/android-native-tools/android-ndk-r27d/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-readelf.exe')
source=json.loads((F/'source.json').read_text(encoding='utf8'))
assert source['versionCode']==VERSION and ('versionCode '+str(VERSION)) in (S/'apps/android/app/build.gradle').read_text()
ENV={**os.environ,'JAVA_HOME':str(J),'PATH':str(J/'bin')+os.pathsep+'C:/Program Files/nodejs'+os.pathsep+os.environ['PATH'],
    'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2','ANDROID_HOME':str(SDK),'ANDROID_SDK_ROOT':str(SDK),
    'GRADLE_USER_HOME':'E:/CodexData/Companion/.build-cache/gradle-user','TEMP':str(C),'TMP':str(C),'NODE_OPTIONS':'--max-old-space-size=512','GOMAXPROCS':'2'}
def run(args):
    p=subprocess.run(list(map(str,args)),env=ENV,capture_output=True,text=True,encoding='utf8',errors='replace',
        creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    assert p.returncode==0,p.stdout+p.stderr
    return p.stdout+p.stderr
def sha(data):return hashlib.sha256(data).hexdigest()
aar=S/'apps/android/app/libs/companion-android-backend.aar'
provenance=json.loads(aar.with_suffix('.provenance.json').read_text(encoding='utf8'))
assert sha(aar.read_bytes())==provenance['aarSha256']
assert source['backendSourceCommit']==provenance['backendSourceCommit']
assert run(['git','-C',S,'rev-parse','HEAD']).strip()==source['frontendSourceCommit']
log=F/('apk'+str(VERSION)+'-build-'+str(time.time_ns())+'.log')
start=time.perf_counter()
with log.open('wb') as out:
    if 'build-web' in sys.argv[3:]:
        p=subprocess.run(['C:/Program Files/nodejs/npm.cmd','run','build:mobile'],cwd=S,env=ENV,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        assert p.returncode==0,log.read_text(encoding='utf8',errors='replace')[-3000:]
    p=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(GRADLE),'--offline','--no-daemon','--max-workers=1',
        '-Dorg.gradle.jvmargs=-Xmx768m','--project-cache-dir',str(C/'gradle-project'),'-I',str(C/'own-build-dir.gradle'),':app:assembleDebug'],
        cwd=S/'apps/android',env=ENV,stdout=out,stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
assert p.returncode==0,log.read_text(encoding='utf8',errors='replace')[-4500:]
apk=C/'build/app/outputs/apk/debug/app-debug.apk'
badging=run([BT/'aapt2.exe','dump','badging',apk])
assert f"package: name='com.denzic.companion.app' versionCode='{VERSION}' versionName='0.1.{VERSION}'" in badging
signature=run([os.environ['COMSPEC'],'/d','/c',BT/'apksigner.bat','verify','--verbose','--print-certs',apk])
assert 'ecebce83705d3336731610451cd1685cadb2d87fba29e41a471b2b44d46c45da' in signature
run([BT/'zipalign.exe','-c','-P','16','4',apk])
(F/('apk'+str(VERSION)+'-signature.log')).write_text(signature,encoding='utf8')
native=[];assets=[];extract=C/'unified058/native-apk-check';extract.mkdir(exist_ok=True)
with zipfile.ZipFile(apk) as z,zipfile.ZipFile(aar) as a:
    for name in a.namelist():
        if name.startswith('jni/arm64-v8a/') and name.endswith('.so'):
            data=a.read(name);assert data==z.read(name.replace('jni/','lib/',1))
            path=extract/Path(name).name;path.write_bytes(data)
            loads=[line for line in run([READELF,'-lW',path]).splitlines() if 'LOAD ' in line]
            assert loads and all(int(line.split()[-1],16)>=16384 for line in loads),name
            native.append({'name':name,'sha256':sha(data),'elf16KiBAligned':True})
    for path in (S/'apps/mobile/dist').rglob('*'):
        if path.is_file():
            name=path.relative_to(S/'apps/mobile/dist').as_posix()
            assert path.read_bytes()==z.read('assets/www/'+name)
            assets.append(name)
assert len(native)==3
dest=F/f'Companion-Android-0.1.{VERSION}-录音与内容修复候选.apk'
shutil.copy2(apk,dest)
record={'result':f'ANDROID{VERSION}_SIGNED_SOURCE_AND_CONTENT_VERIFIED_CANDIDATE',
    'versionName':f'0.1.{VERSION}','versionCode':VERSION,'apk':str(dest),'sha256':sha(dest.read_bytes()),'bytes':dest.stat().st_size,
    'frontendSourceCommit':source['frontendSourceCommit'],'backendSourceCommit':source['backendSourceCommit'],
    'signerMatches050r2And055':True,'zip16KiBAligned':True,'nativeLibraries':native,'webAssetsExact':assets,
    'buildLog':str(log),'buildWallSeconds':round(time.perf_counter()-start,3),'installed':False,
    'reasonNotInstalled':'Build receipt only; actual ordinary-phone installation and affected-path acceptance are separate steps.',
    'actualOrdinaryControlButtonsAccepted':False,'modelsRun':False,
    'nativeRebuilt':source.get('nativeRebuilt',False),'nativeRebuiltByApkBuildStep':False}
(F/('apk'+str(VERSION)+'-verification.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in record.items() if k not in ['nativeLibraries','webAssetsExact']},ensure_ascii=False))
