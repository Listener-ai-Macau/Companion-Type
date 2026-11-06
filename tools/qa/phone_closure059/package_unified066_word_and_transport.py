from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import copy,hashlib,io,json,os,subprocess,time,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';B=R/'companion-android-device-closure055'
P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';F=P/'unified066';F.mkdir(exist_ok=True)
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/unified066');C.mkdir(exist_ok=True)
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin')
API='E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar';JSON_JAR='E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar'
env={**os.environ,'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2','GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
sha=lambda data:hashlib.sha256(data).hexdigest()
def run(args,cwd=None):
    value=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=150,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    assert value.returncode==0,value.stdout+value.stderr
    return value.stdout+value.stderr
def git(repo,*args):return run(['git','-c','maintenance.auto=false',*args],repo).strip()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
assert not git(B,'status','--porcelain') and not git(S,'status','--porcelain')
assert not git(B,'diff','c542833ace333344af04ce106e72548fbe806567','--','apps/android-backend/src','apps/android-backend/native','apps/windows/src-tauri/src/backend/meeting_document_export.rs')
assert not git(B,'diff','4d86908f27e6789459f5d97caf3405148febb3b9','--','apps/android-backend/native','apps/windows/src-tauri/src')
classes=C/'classes';classes.mkdir(exist_ok=True)
src=B/'apps/android-backend/src/main/java';tests=B/'apps/android-backend/src/test/java/com/denzic/companion/mobile'
test_names=['MeetingDocumentUnicodeTest','NativeControlMetadataTest','SystemUpdateTest']
compile_log=run([J/'javac.exe','--release','8','-encoding','UTF-8','-cp',API,'-d',classes,*src.rglob('*.java'),*[tests/(name+'.java') for name in test_names]])
cp=os.pathsep.join([str(classes),JSON_JAR,API]);results={}
results['unicode']=run([J/'java.exe','-Xmx192m','-cp',cp,'com.denzic.companion.mobile.MeetingDocumentUnicodeTest'])
results['metadata']=run([J/'java.exe','-Xmx192m','-cp',cp,'com.denzic.companion.mobile.NativeControlMetadataTest','E:/CodexData/Companion/.build-cache/device-phone055/new-e7-metadata.bin',C/('metadata-'+str(time.time_ns()))])
results['ota']=run([J/'java.exe','-Xmx256m','-cp',cp,'com.denzic.companion.mobile.SystemUpdateTest','E:/CodexData/Companion/.build-cache/firmware/fw66685-package'])
(F/'host-checks.log').write_text(compile_log+'\n'.join(results.values()),encoding='utf8')
pin=git(B,'rev-parse','HEAD');branch=git(B,'branch','--show-current')
git(B,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git(B,'ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
aar=S/'apps/android/app/libs/companion-android-backend.aar';before=aar.read_bytes();previous=json.loads(aar.with_suffix('.provenance.json').read_text(encoding='utf8'))
assert sha(before)==previous['aarSha256'] and previous['nativeSourceCommit']=='4d86908f27e6789459f5d97caf3405148febb3b9'
write(F/'inherited062-provenance-original.json',previous)
production={p.relative_to(classes).as_posix():p.read_bytes() for p in classes.rglob('*.class') if not any(p.name.startswith(test) for test in test_names)}
changed=[];buf=io.BytesIO()
with zipfile.ZipFile(io.BytesIO(before)) as old:
    jarbuf=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(old.read('classes.jar'))) as jar,zipfile.ZipFile(jarbuf,'w',zipfile.ZIP_DEFLATED) as newjar:
        assert {n for n in jar.namelist() if n.endswith('.class')}==set(production)
        for entry in jar.infolist():
            original=jar.read(entry.filename);after=production.get(entry.filename,original)
            newjar.writestr(copy.copy(entry),after)
            if original!=after:changed.append(entry.filename)
    assert changed and all(name.startswith(('com/denzic/companion/mobile/AndroidGattLink','com/denzic/companion/mobile/SystemUpdateClient')) for name in changed),changed
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as packed:
        for entry in old.infolist():packed.writestr(copy.copy(entry),jarbuf.getvalue() if entry.filename=='classes.jar' else old.read(entry.filename))
    with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as packed:
        for name in old.namelist():
            if name!='classes.jar':assert old.read(name)==packed.read(name)
        native=sha(packed.read('jni/arm64-v8a/libcompanion_mobile_audio.so'))
        assert native=='212ec44db8f2b06d2d3c3dc5e16fb2c8ff14f88c29fe6e7a0003c45a045df08f'
aar.write_bytes(buf.getvalue())
provenance={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'aarSha256':sha(buf.getvalue()),'backendSourceCommit':pin,'backendSourceWorkspace':str(B),'remoteSourceVerified':True,
 'nativeSourceCommit':'4d86908f27e6789459f5d97caf3405148febb3b9','nativeLibrarySha256':native,'nativeLibrary16KiBElfAligned':True,'nativeRebuiltThisBatch':False,
 'nativeProductionSourceIdenticalToNativeSourceCommit':True,'nativeInheritedReceipt':str(P/'word062/native-word062.json'),
 'aarBase062Sha256':sha(before),'javaClassesChangedFrom062':changed,'allNonClassAarEntriesByteIdenticalTo062':True,
 'wordUnicodeAndFooterCorrectionsRetained':True,'latestOtaLateCreditAndShared2MPreferenceRetained':True,'ordinaryPhoneAcceptance':False,
 'modelsRun':False,'speechRuntimeBinariesAndWeightsChanged':False,
 'scope':'Exact Java source equals tested c542833; retain Word062 native212ec44d with correct footer. This batch changes Java transport only, not native model code or weights. Prior062 provenance with inherited historical flags retained separately.'}
write(aar.with_suffix('.provenance.json'),provenance)
gradle=S/'apps/android/app/build.gradle';value=gradle.read_text(encoding='utf8');assert 'versionCode 62' in value
gradle.write_text(value.replace('versionCode 62','versionCode 66').replace("versionName '0.1.62'","versionName '0.1.66'"),encoding='utf8')
git(S,'add','--','apps/android/app/build.gradle','apps/android/app/libs/companion-android-backend.aar','apps/android/app/libs/companion-android-backend.provenance.json')
git(S,'commit','-m','Unify Android066 corrected Word native with current OTA and recording transport fixes')
main=git(S,'rev-parse','HEAD');mainbranch=git(S,'branch','--show-current')
git(S,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{mainbranch}')
assert git(S,'ls-remote','origin',f'refs/heads/{mainbranch}').split()[0]==main
source={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'versionName':'0.1.66','versionCode':66,'frontendSourceCommit':main,'frontendBranch':mainbranch,
 'backendSourceCommit':pin,'backendBranch':branch,'remoteReadback':True,'installed':False,'nativeRebuilt':False,'nativeReusedFromWord062':True,'modelsRun':False,
 'scope':'Combine062 actual Word source repair and latest065 Java transport; recheck actual installed identity and current lease before any installation. Never replace a newer unrelated candidate.'}
write(F/'source.json',source);write(F/'aar-verification.json',provenance)
print(json.dumps({'frontendSourceCommit':main,'backendSourceCommit':pin,'nativeReusedFrom062':True,'changedJavaClasses':changed,'hostResults':{k:v.splitlines()[0] for k,v in results.items()},'installed':False},ensure_ascii=False),flush=True)
