from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import copy,hashlib,io,json,os,shutil,subprocess,time,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';B=R/'companion-android-device-closure055';W=Path(__file__).parent
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/word061');C.mkdir(exist_ok=True)
P=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12';F=P/'word061';F.mkdir(exist_ok=True)
J=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.0.36-hotspot/bin');API='E:/CodexData/Companion/.build-cache/android-sdk/platforms/android-35/android.jar';JSON_JAR='E:/CodexData/Companion/.build-cache/android054-materials/json-20240303.jar'
env={**os.environ,'JAVA_TOOL_OPTIONS':'-XX:ActiveProcessorCount=2','GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def run(args,cwd=None):
    p=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS,timeout=120)
    assert p.returncode==0,p.stdout+p.stderr;return p.stdout+p.stderr
def git(repo,*args):return run(['git',*args],repo).strip()
def sha(data):return hashlib.sha256(data).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
bad=Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059/saved/QA059-all.docx');shutil.copy2(bad,F/'Android059-Word-invalid-surrogate-original.docx')
write(F/'original-failure.json',{'actualAndroidVersion':'0.1.59','fileSha256':sha(bad.read_bytes()),'bytes':bad.stat().st_size,'error':'word/document.xml invalid XML1.0 numeric character references: &#55357;&#56832; instead of one supplementary scalar. Actual system save and real recipient file both retained these bytes.','ordinaryTransferPassedButContentQualified':False,'scope':'Android selected-content Word uses DOM Transformer; other seven formats did not have this XML failure.'})
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
canonical=R/'docs/product_backlog.json';raw=canonical.read_bytes();d=json.loads(raw);front=d['owner_module_execution']['frontendWindowsMobile20261102'];task=front['ownerDevicePhoneClosure055']
task['state']='ANDROID059_INSTALLED_ACTUAL_EXPORT_TRANSPORT_PASSED_WORD_UNICODE_CONTENT_FIX_ACTIVE'
task['latestInstalledVersionObservation']={'version':'0.1.59/code59','exactApkSha256':'dd4ab648d355b99cafb29b543cfb42bb4ae80d9e44fc39e5f93fc7442b0357b3','originalAppFilesByteIdentical':562,'receipt':str(P/'installation059.json')}
task['ownerPriority12']['state']=task['state'];task['ownerPriority12']['actualProgress']={'at':now,'ordinaryUi':'Actual Android App on isolated display2; primary display remained with owner or locked, no main-screen input.','savedFormats':['txt','markdown','word','pdf','pptx','xlsx','mindmap','png'],'actualShareReceipts':8,'actualPublicClipboardPastedAndVerified':True,'wordContentQualification':'FAILED_INVALID_SURROGATE_XML_FIX_IN_PROGRESS','allOtherContentQualification':'UNDER_INDEPENDENT_CHECK','originalLibraryReturnPending':True}
task['next']='修Word所选导出的Android UTF16代理项非法XML并集中合并已提交060 OTA候选，出061后仅重验受影响Word保存/分享和内容；切回原库，续普通新录音控制/回听/删除及原音导出。模型未运行。'
d['owner_module_execution']['nextBatch'].update(status=task['state'],next=task['next'],at=now)
assert canonical.read_bytes()==raw
tmp=canonical.with_suffix('.word061.tmp');write(tmp,d);os.replace(tmp,canonical)
shutil.copy2(Path('E:/CodexData/Companion/.build-cache/device-phone055/acceptance059/installation059.json'),P/'installation059.json')
classes=C/'classes';classes.mkdir(exist_ok=True);src=B/'apps/android-backend/src/main/java';tests=B/'apps/android-backend/src/test/java/com/denzic/companion/mobile'
test_names=['MeetingDocumentUnicodeTest','NativeControlMetadataTest','SystemUpdateTest']
log=run([J/'javac.exe','--release','8','-encoding','UTF-8','-cp',API,'-d',classes,*src.rglob('*.java'),*[tests/(name+'.java') for name in test_names]])
cp=os.pathsep.join([str(classes),JSON_JAR,API])
unicode_result=run([J/'java.exe','-Xmx192m','-cp',cp,'com.denzic.companion.mobile.MeetingDocumentUnicodeTest'])
metadata_result=run([J/'java.exe','-Xmx192m','-cp',cp,'com.denzic.companion.mobile.NativeControlMetadataTest','E:/CodexData/Companion/.build-cache/device-phone055/new-e7-metadata.bin',C/('metadata-'+str(time.time_ns()))])
ota_result=run([J/'java.exe','-Xmx256m','-cp',cp,'com.denzic.companion.mobile.SystemUpdateTest','E:/CodexData/Companion/.build-cache/firmware/fw66685-package'])
(F/'host-checks.log').write_text(log+unicode_result+metadata_result+ota_result,encoding='utf8')
assert not git(B,'diff','5197a7b','--','apps/android-backend/native/src','apps/android-backend/native/Cargo.toml','apps/android-backend/native/Cargo.lock')
git(B,'add','--','apps/android-backend/src/main/java/com/denzic/companion/mobile/MeetingDocumentSections.java','apps/android-backend/src/test/java/com/denzic/companion/mobile/MeetingDocumentUnicodeTest.java')
if git(B,'diff','--cached','--name-only') or (B/'.git/MERGE_HEAD').exists():git(B,'-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Preserve supplementary Unicode in Android selected Word documents and retain continuous OTA candidate')
pin=git(B,'rev-parse','HEAD');branch=git(B,'branch','--show-current');git(B,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}');assert git(B,'ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
aar=S/'apps/android/app/libs/companion-android-backend.aar';base=aar.read_bytes();previous=json.loads(aar.with_suffix('.provenance.json').read_text(encoding='utf8'));assert sha(base)==previous['aarSha256']
production={p.relative_to(classes).as_posix():p.read_bytes() for p in classes.rglob('*.class') if not any(p.name.startswith(t) for t in test_names)}
changed=[]
with zipfile.ZipFile(io.BytesIO(base)) as old:
    jarout=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(old.read('classes.jar'))) as jar,zipfile.ZipFile(jarout,'w',zipfile.ZIP_DEFLATED) as newjar:
        assert {n for n in jar.namelist() if n.endswith('.class')}==set(production)
        for entry in jar.infolist():
            before=jar.read(entry.filename);after=production.get(entry.filename,before);newjar.writestr(copy.copy(entry),after)
            if before!=after:changed.append(entry.filename)
    assert 'com/denzic/companion/mobile/MeetingDocumentSections.class' in changed and all(name.startswith('com/denzic/companion/mobile/MeetingDocumentSections') for name in changed),changed
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as new:
        for entry in old.infolist():
            before=old.read(entry.filename);new.writestr(copy.copy(entry),jarout.getvalue() if entry.filename=='classes.jar' else before)
    with zipfile.ZipFile(io.BytesIO(out.getvalue())) as new:
        for name in old.namelist():
            if name!='classes.jar':assert old.read(name)==new.read(name)
        assert sha(new.read('jni/arm64-v8a/libcompanion_mobile_audio.so'))=='156acc23dcf6ba2ab50e74c1f9fded9fb56036dcd0fb9f85f2591cc46c942898'
aar.write_bytes(out.getvalue());previous.update(aarSha256=sha(out.getvalue()),backendSourceCommit=pin,backendSourceWorkspace=str(B),remoteSourceVerified=True,wordUnicodeFixed=True,javaClassesChangedFrom060=changed,allNonClassAarEntriesByteIdenticalTo060=True,scope='Preserve supplementary Unicode scalars in selected Word DOM serialization, retaining committed060 measured continuous OTA and validated dated recorder/native control. Native model/runtime binaries unchanged.',ordinaryPhoneAcceptance=False)
write(aar.with_suffix('.provenance.json'),previous)
gradle=S/'apps/android/app/build.gradle';v=gradle.read_text(encoding='utf8');assert 'versionCode 60' in v;gradle.write_text(v.replace('versionCode 60','versionCode 61').replace("versionName '0.1.60'","versionName '0.1.61'"),encoding='utf8')
git(S,'add','--','apps/android/app/build.gradle','apps/android/app/libs/companion-android-backend.aar','apps/android/app/libs/companion-android-backend.provenance.json')
git(S,'-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Integrate Android061 Unicode-safe Word with committed060 recorder and OTA candidate')
main=git(S,'rev-parse','HEAD');main_branch=git(S,'branch','--show-current');git(S,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{main_branch}');assert git(S,'ls-remote','origin',f'refs/heads/{main_branch}').split()[0]==main
write(F/'source.json',{'at':now,'versionName':'0.1.61','versionCode':61,'frontendSourceCommit':main,'frontendBranch':main_branch,'backendSourceCommit':pin,'backendBranch':branch,'remoteReadback':True,'installed':False,'classesDirectory':str(classes),'nativeProductionSourceIdenticalTo5197a7b':True,'nativeRebuilt':False,'modelsRun':False,'ordinaryWordExportPending':True})
print(json.dumps({'frontendSourceCommit':main,'backendSourceCommit':pin,'hostUnicode':unicode_result.splitlines()[0],'hostOta':ota_result.splitlines()[0],'changedClasses':changed,'nativeRebuilt':False},ensure_ascii=False))
