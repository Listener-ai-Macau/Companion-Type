from pathlib import Path
import hashlib,json,os,re,shutil,subprocess,time,zipfile
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');B=R/'companion-android-device-closure055';S=R/'companion-device-closure055'
F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/word062';F.mkdir(exist_ok=True)
C=Path('E:/CodexData/Companion/.build-cache/device-phone055/native056');O=C.parent/'word062';O.mkdir(exist_ok=True)
NDK=Path('E:/CodexData/Companion/.build-cache/android-native-tools/android-ndk-r27d/toolchains/llvm/prebuilt/windows-x86_64/bin');clang=NDK/'aarch64-linux-android26-clang.cmd'
env={**os.environ,'PATH':'C:/Users/Billy/.cargo/bin'+os.pathsep+os.environ['PATH'],'CARGO_TARGET_DIR':str(C/'target'),'CARGO_BUILD_JOBS':'1','CARGO_INCREMENTAL':'0','TEMP':str(C),'TMP':str(C),'CC_aarch64_linux_android':str(clang),'AR_aarch64_linux_android':str(NDK/'llvm-ar.exe'),'CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER':str(clang),'GIT_SSH_COMMAND':'ssh -o ProxyCommand=none -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=2','GIT_TERMINAL_PROMPT':'0'}
def git(repo,*args):
    p=subprocess.run(['git',*args],cwd=repo,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');assert p.returncode==0,p.stdout+p.stderr;return p.stdout.strip()
old_doc=C.parent/'acceptance059/saved/QA061-all.docx';shutil.copy2(old_doc,F/'Android061-Word-footer-schema-failure.docx');shutil.copy2(C.parent/'acceptance059/openxml-validation.json',F/'original-footer-schema-failure.json')
with zipfile.ZipFile(S/'apps/android/app/libs/companion-android-backend.aar') as z:(O/'previous061-mobile-audio.so').write_bytes(z.read('jni/arm64-v8a/libcompanion_mobile_audio.so'))
rel='apps/windows/src-tauri/src/backend/meeting_document_export.rs';git(B,'add','--',rel);git(B,'-c','user.name=Codex','-c','user.email=codex@local','commit','-m','Write shared Word footer run properties in the required OpenXML sequence')
pin=git(B,'rev-parse','HEAD');branch=git(B,'branch','--show-current');git(B,'-c','pack.threads=1','-c','pack.windowMemory=32m','push','origin',f'HEAD:refs/heads/{branch}');assert git(B,'ls-remote','origin',f'refs/heads/{branch}').split()[0]==pin
cmd=['C:/Users/Billy/.cargo/bin/cargo.exe','rustc','--offline','--locked','--release','--jobs','1','--features','mobile-asr,mobile-local-asr,mobile-calendar,mobile-control','--target','aarch64-linux-android','--manifest-path',str(B/'apps/android-backend/native/Cargo.toml'),'--lib','--','-C','link-arg=-Wl,-z,max-page-size=16384']
log=F/('native-word062-'+str(time.time_ns())+'.log');start=time.perf_counter()
with log.open('wb') as out:p=subprocess.run(cmd,cwd=B,env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
lib=C/'target/aarch64-linux-android/release/libcompanion_mobile_audio.so';assert p.returncode==0,log.read_text(encoding='utf8',errors='replace')[-4000:]
header=subprocess.check_output([str(NDK/'llvm-readelf.exe'),'-lW',str(lib)],text=True);loads=[s for s in header.splitlines() if 'LOAD ' in s];assert loads and all(int(s.split()[-1],16)>=16384 for s in loads)
def symbols(path):
    syms=subprocess.check_output([str(NDK/'llvm-readelf.exe'),'--dyn-syms','--wide',str(path)],text=True)
    deps=subprocess.check_output([str(NDK/'llvm-readelf.exe'),'-dW',str(path)],text=True)
    return sorted(set(re.findall(r'\b(?:Java_[A-Za-z0-9_]+|JNI_OnLoad)\b',syms))),sorted(set(re.findall(r'\(NEEDED\).*?\[(.*?)\]',deps)))
assert symbols(O/'previous061-mobile-audio.so')==symbols(lib)
destination=O/'libcompanion_mobile_audio.so';shutil.copy2(lib,destination)
record={'sourceCommit':pin,'sourceBranch':branch,'library':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'bytes':destination.stat().st_size,'sixteenKiBCompatible':True,'jniAndDynamicDependenciesUnchanged':True,'rootCrateRelinkOnly':True,'wallSeconds':round(time.perf_counter()-start,3),'log':str(log),'modelsRun':False,'modelSourcesOrWeightsChanged':False,'scope':'Shared Word footer w:color precedes w:sz per OpenXML; no ASR, recording, transfer or neural source change.'}
(F/'native-word062.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(json.dumps(record),flush=True)
