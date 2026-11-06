from pathlib import Path
import copy, hashlib, io, json, os, subprocess, time, zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

R = Path('C:/Users/Billy/Desktop/Denzic/Companion')
S = R/'companion-device-closure055'
B = R/'companion-android-device-closure055'
C = Path('E:/CodexData/Companion/.build-cache/device-phone055/unified058')
F = R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058'
J = Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin')
SDK = Path('E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar')
JSON_JAR = Path('E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar')
C.mkdir(parents=True, exist_ok=True)
F.mkdir(parents=True, exist_ok=True)
ENV = {**os.environ, 'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2',
       'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2',
       'GIT_TERMINAL_PROMPT':'0'}

def run(args, cwd=None):
    p = subprocess.run(list(map(str,args)), cwd=cwd, env=ENV, capture_output=True,
        text=True, encoding='utf8', errors='replace',
        creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    assert p.returncode == 0, p.stdout+p.stderr
    return p.stdout+p.stderr

def git(repo, *args):
    return run(['git',*args],repo).strip()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
pin = git(B,'rev-parse','HEAD')
assert not git(B,'status','--porcelain')
assert not git(B,'diff','5197a7b',pin,'--','apps/android-backend/native/src','apps/android-backend/native/Cargo.toml','apps/android-backend/native/Cargo.lock'), 'Native production source must match already built056 exactly'
branch = git(B,'branch','--show-current')
git(B,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}')
assert git(B,'ls-remote','origin',f'refs/heads/{branch}').split()[0] == pin

backlog_path=R/'docs/product_backlog.json'
backlog=json.loads(backlog_path.read_text(encoding='utf-8-sig'))
frontend=backlog['owner_module_execution']['frontendWindowsMobile20261102']
task=frontend['ownerDevicePhoneClosure055']
task['continuation058']={'at':now,'state':'INTEGRATING_COMMITTED057_WITH_VERIFIED_DATED_METADATA_FIX',
    'installedObservedVersion':'0.1.57','backendSourceCommit':pin,
    'phoneReadyByOwner':True,'sharedPhoneAndBoardOwnedByOtherFlow':True,
    'scope':'Keep057 OTA full-file retention, capability wait, foreground transfer ownership and bookmark lifecycle repairs; retain056 legacy112/dated120B metadata validation and nonblocking Android kernel lock.',
    'ordinaryAppAcceptance':False,'wholeProductQualified':False,
    'next':'Prepare integrated058 without taking the active phone/board lease; once free, verify installed version first, then ordinary control and only newly-created test recording receive/playback/delete, followed by public-library save/copy/share. Do not downgrade057 or touch original audio.'}
task['state']='INTEGRATING058_PHONE_READY_SHARED_DEVICE_BUSY'
task['next']=task['continuation058']['next']
backlog['owner_module_execution']['nextBatch']['status']=task['state']
backlog['owner_module_execution']['nextBatch']['next']=task['next']
write(backlog_path,backlog)
with (R/'docs/development_log.md').open('a',encoding='utf8') as out:
    out.write(f'\n\n### {now} — 手机恢复可用后的058合并工作点\n\nOwner已说明手机可用；实际安装为057，另一既有流程持有“Companion手机057普通OTA及维护验收”，本流程未安装、未点击手机、未占BLE。057代码包含新的升级完成/前台所有权及回听书签修复，但其Java/native本地录音校验仍只收112B；已保护056兼容实际新录音120B元数据。先在原分支合并已提交源，保留两侧修复，复用字节与生产源码一致的056原生库，不重跑模型或重复原生构建。后端合并提交{pin}已推送并核对远端；真机用户链仍未验，不改Owner验收或整机售卖资格。\n')

classes=C/'classes'
classes.mkdir(exist_ok=True)
java_root=B/'apps/android-backend/src/main/java'
test_root=B/'apps/android-backend/src/test/java/com/denzic/companion/mobile'
tests=[test_root/'NativeControlMetadataTest.java',test_root/'SystemUpdateTest.java']
output=run([J/'javac.exe','--release','8','-encoding','UTF-8','-cp',SDK,'-d',classes,*java_root.rglob('*.java'),*tests])
cp=os.pathsep.join(map(str,[classes,JSON_JAR,SDK]))
metadata_result=run([J/'java.exe','-Xmx192m','-cp',cp,'com.denzic.companion.mobile.NativeControlMetadataTest',
    'E:/CodexData/Companion/.build-cache/device-phone055/new-e7-metadata.bin',C/('metadata-case-'+str(time.time_ns()))])
ota_result=run([J/'java.exe','-Xmx192m','-cp',cp,'com.denzic.companion.mobile.SystemUpdateTest',
    'E:/CodexData/Companion/.build-cache/firmware/fw66685-package'])
(F/'merged-java-checks.log').write_text(output+metadata_result+ota_result,encoding='utf8')

aar=S/'apps/android/app/libs/companion-android-backend.aar'
old=aar.read_bytes()
previous_receipt=json.loads(aar.with_suffix('.provenance.json').read_text(encoding='utf8'))
assert sha(old)==previous_receipt['aarSha256']
native_receipt=json.loads((F.parent/'native-final-library.json').read_text(encoding='utf8'))
lib=Path(native_receipt['library']).read_bytes()
assert sha(lib)==native_receipt['sha256'] and native_receipt['sixteenKiBCompatible']
assert native_receipt['sourceCommit'].startswith('5197a7b')
test_classes={p.stem for p in tests}
production={p.relative_to(classes).as_posix():p.read_bytes() for p in classes.rglob('*.class')
    if not any(p.name.startswith(name) for name in test_classes)}
changed=[]
with zipfile.ZipFile(io.BytesIO(old)) as old_aar:
    oldjar=old_aar.read('classes.jar')
    manifest=json.loads(old_aar.read('assets/companion-android-native-components.json'))
    assert sha((B/'apps/android-backend/native/Cargo.lock').read_bytes())==manifest['cargoLockSha256']
    jarout=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(oldjar)) as old_jar,zipfile.ZipFile(jarout,'w',zipfile.ZIP_DEFLATED) as new_jar:
        assert {n for n in old_jar.namelist() if n.endswith('.class')}==set(production)
        for entry in old_jar.infolist():
            previous=old_jar.read(entry.filename)
            data=production.get(entry.filename,previous)
            new_jar.writestr(copy.copy(entry),data)
            if previous!=data:changed.append(entry.filename)
    allowed=('com/denzic/companion/mobile/NativeRecordingControl',
             'com/denzic/companion/mobile/RecordingClient',
             'com/denzic/companion/mobile/SystemUpdateClient')
    assert changed and all(n.startswith(allowed) for n in changed),changed
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as new_aar:
        for entry in old_aar.infolist():
            previous=old_aar.read(entry.filename)
            data=jarout.getvalue() if entry.filename=='classes.jar' else lib if entry.filename=='jni/arm64-v8a/libcompanion_mobile_audio.so' else previous
            new_aar.writestr(copy.copy(entry),data)
    with zipfile.ZipFile(io.BytesIO(result.getvalue())) as new_aar:
        assert old_aar.namelist()==new_aar.namelist()
        for name in old_aar.namelist():
            if name not in ['classes.jar','jni/arm64-v8a/libcompanion_mobile_audio.so']:
                assert old_aar.read(name)==new_aar.read(name),name
aar.write_bytes(result.getvalue())
receipt={'at':now,'aarSha256':sha(result.getvalue()),'backendSourceCommit':pin,
    'backendSourceWorkspace':str(B),'remoteSourceVerified':True,
    'nativeChanges':True,'nativeSourceCommit':native_receipt['sourceCommit'],
    'nativeProductionSourceIdenticalToIntegratedBackend':True,
    'nativeLibrarySha256':sha(lib),'nativeLibrary16KiBElfAligned':True,
    'inheritedNativeReceipt':str(F.parent/'native-final-library.json'),
    'javaClassesChangedFrom057':changed,'allOtherAarEntriesIdenticalTo057':True,
    'speechRuntimeBinariesAndWeightsChanged':False,
    'scope':'057 retention/capability/ownership and playback fixes with validated dated120B recorder metadata and Android kernel file exclusion; no new model inference.',
    'ordinaryPhoneAcceptance':False}
write(aar.with_suffix('.provenance.json'),receipt)
write(F/'aar-verification.json',receipt)
write(F/'java-verification.json',{'metadata':metadata_result,'ota':ota_result,
    'backendSourceCommit':pin,'classesDirectory':str(classes),'physicalAndroidAcceptance':False})
p=S/'apps/android/app/build.gradle'
text=p.read_text(encoding='utf8')
assert 'versionCode 57' in text
p.write_text(text.replace('versionCode 57','versionCode 58').replace("versionName '0.1.57'","versionName '0.1.58'"),encoding='utf8')
git(S,'add','--','apps/android/app/build.gradle','apps/android/app/libs/companion-android-backend.aar','apps/android/app/libs/companion-android-backend.provenance.json')
bookmark=run(['C:/Program Files/nodejs/node.exe','tools/test_mobile_playback_bookmark_lifecycle.cjs'],S)
(F/'bookmark-regression.log').write_text(bookmark,encoding='utf8')
git(S,'-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Integrate Android058 dated recorder compatibility with057 OTA and playback fixes')
main_pin=git(S,'rev-parse','HEAD')
main_branch=git(S,'branch','--show-current')
git(S,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{main_branch}')
assert git(S,'ls-remote','origin',f'refs/heads/{main_branch}').split()[0]==main_pin
write(F/'source.json',{'at':now,'versionName':'0.1.58','versionCode':58,
    'frontendSourceCommit':main_pin,'frontendBranch':main_branch,'backendSourceCommit':pin,
    'backendBranch':branch,'remoteReadback':True,'installed':False,
    'scope':'Unified recorder-control/dated-metadata and committed057 OTA/playback changes.'})
print(json.dumps({'frontendSourceCommit':main_pin,'backendSourceCommit':pin,
    'aarSha256':receipt['aarSha256'],'changedJavaClasses':changed,
    'metadataResult':metadata_result.splitlines()[0],
    'otaResult':ota_result.splitlines()[0],
    'bookmarkResult':bookmark[:600],'remoteReadback':True},ensure_ascii=False))
