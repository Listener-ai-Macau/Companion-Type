from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import copy,hashlib,io,json,os,subprocess,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';B=R/'companion-android-device-closure055'
F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/word062'
record=json.loads((F/'native-word062.json').read_text());lib=Path(record['library']).read_bytes();assert hashlib.sha256(lib).hexdigest()==record['sha256']
env={**os.environ,'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(repo,*args):
    p=subprocess.run(['git',*args],cwd=repo,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
pin=git(B,'rev-parse','HEAD');assert pin==record['sourceCommit'] and not git(B,'status','--porcelain')
assert git(B,'diff','34dee9ff','--name-only').splitlines()==['apps/windows/src-tauri/src/backend/meeting_document_export.rs']
aar=S/'apps/android/app/libs/companion-android-backend.aar';old=aar.read_bytes();meta=json.loads(aar.with_suffix('.provenance.json').read_text());assert hashlib.sha256(old).hexdigest()==meta['aarSha256']
out=io.BytesIO()
with zipfile.ZipFile(io.BytesIO(old)) as before,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as after:
    for entry in before.infolist():
        payload=before.read(entry.filename);after.writestr(copy.copy(entry),lib if entry.filename=='jni/arm64-v8a/libcompanion_mobile_audio.so' else payload)
with zipfile.ZipFile(io.BytesIO(old)) as before,zipfile.ZipFile(io.BytesIO(out.getvalue())) as after:
    for name in before.namelist():
        if name!='jni/arm64-v8a/libcompanion_mobile_audio.so':assert before.read(name)==after.read(name)
aar.write_bytes(out.getvalue());meta.update(aarSha256=hashlib.sha256(out.getvalue()).hexdigest(),backendSourceCommit=pin,nativeSourceCommit=pin,nativeLibrarySha256=record['sha256'],nativeProductionSourceIdenticalTo5197a7b=False,nativeProductionSourceDiffFrom5197a7b=['apps/windows/src-tauri/src/backend/meeting_document_export.rs'],javaClassesIdenticalTo061=True,allOtherAarEntriesByteIdenticalTo061=True,scope='061 Unicode-safe selected Word plus shared native Word footer property sequence. Retain060 continuous OTA/control; no ASR/model source or weight change.',ordinaryPhoneAcceptance=False)
aar.with_suffix('.provenance.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
gradle=S/'apps/android/app/build.gradle';v=gradle.read_text();assert 'versionCode 61' in v;gradle.write_text(v.replace('versionCode 61','versionCode 62').replace("versionName '0.1.61'","versionName '0.1.62'"),encoding='utf8')
git(S,'add','--','apps/android/app/build.gradle','apps/android/app/libs/companion-android-backend.aar','apps/android/app/libs/companion-android-backend.provenance.json','apps/windows/src-tauri/src/backend/meeting_document_export.rs')
git(S,'-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Correct shared Word footer OpenXML order in Android062 and desktop source')
main=git(S,'rev-parse','HEAD');branch=git(S,'branch','--show-current');git(S,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}');assert git(S,'ls-remote','origin',f'refs/heads/{branch}').split()[0]==main
source={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'versionName':'0.1.62','versionCode':62,'frontendSourceCommit':main,'frontendBranch':branch,'backendSourceCommit':pin,'backendBranch':record['sourceBranch'],'remoteReadback':True,'installed':False,'nativeRebuilt':True,'modelsRun':False,'wordPhoneAcceptancePending':True,'windowsFooterSourceCorrectedButNotPackaged':True}
(F/'source.json').write_text(json.dumps(source,indent=2),encoding='utf8');print(json.dumps(source))
