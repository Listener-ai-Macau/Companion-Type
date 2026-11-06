from pathlib import Path
import psutil
psutil.Process().cpu_affinity([12,13]);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share070'
C=Path('E:/CodexData/Companion/.build-cache/windows051');target=C/'target'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,cwd=None):
    value=subprocess.run(list(map(str,args)),cwd=cwd,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
    assert value.returncode==0,value.stdout+value.stderr
    return value.stdout.strip()
assert run(['git','-C',S,'status','--porcelain'])=='','Source must be clean before freeze'
commit=run(['git','-C',S,'rev-parse','HEAD'])
files=run(['git','-C',S,'ls-files','apps/windows','packages','package.json','package-lock.json','tsconfig.json','tools/verify_third_party_notices.mjs']).splitlines()
frozen={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'sourceCommit':commit,
 'sourceFiles':[{'path':n,'sha256':sha(S/n)} for n in files if (S/n).is_file()],
 'windowsWebAssets':[{'path':p.relative_to(S/'apps/windows/dist').as_posix(),'sha256':sha(p)} for p in (S/'apps/windows/dist').rglob('*') if p.is_file()],
 'version':'0.1.68','scope':'Explicit documented Explorer file-selection sharing route for content/audio; no private shell handlers, UI automation, device IO or inference.'}
assert frozen['windowsWebAssets']
(F/'source-frozen.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
env={**os.environ,'PATH':'C:/Users/Billy/.cargo/bin'+os.pathsep+os.environ['PATH'],
 'CARGO_TARGET_DIR':str(target),'CARGO_BUILD_JOBS':'1','CARGO_INCREMENTAL':'0','RAYON_NUM_THREADS':'2','TEMP':str(C),'TMP':str(C)}
pre=subprocess.run([os.sys.executable,str(R/'tools/check_type_build_target.py'),'--target-dir',str(target),'--project',str(S/'apps/windows/src-tauri'),'--source-dir',str(S)],capture_output=True,text=True,encoding='utf8',errors='replace')
(F/'native-preflight.json').write_text(pre.stdout,encoding='utf8');assert pre.returncode==0,pre.stdout+pre.stderr
started=time.perf_counter();log=F/('cargo-release-'+str(time.time_ns())+'.log')
with log.open('wb') as stream:
    process=subprocess.Popen(['C:/Users/Billy/.cargo/bin/cargo.exe','build','--release','--offline','--locked'],cwd=S/'apps/windows/src-tauri',env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    (F/'running-native.json').write_text(json.dumps({'pid':process.pid,'sourceCommit':commit,'target':str(target),'log':str(log),'jobs':1,'modelsRun':False}),encoding='utf8')
    import psutil
    own=psutil.Process(process.pid);cpus=own.cpu_affinity()[-4:];own.cpu_affinity(cpus)
    peak_rss=0;pressure_since=None;resource_stop=False
    while process.poll() is None:
        for child in own.children(recursive=True):
            try:
                if child.name().lower() in ['cargo.exe','rustc.exe','link.exe']:child.cpu_affinity(cpus);child.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        family=[own]+own.children(recursive=True);rss=0
        for member in family:
            try:rss+=member.memory_info().rss
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        peak_rss=max(peak_rss,rss)
        pressure=psutil.virtual_memory().percent>=97 and rss>1536*1024*1024
        pressure_since=(pressure_since or time.monotonic()) if pressure else None
        if pressure_since and time.monotonic()-pressure_since>15:
            resource_stop=True
            for member in reversed(family):
                try:member.terminate()
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            break
        time.sleep(1)
    code=process.wait()
result={'exitCode':code,'peakOwnRssMiB':round(peak_rss/2**20),'stoppedForActualMemoryPressure':resource_stop,'sourceCommit':commit,'wallSeconds':round(time.perf_counter()-started,3),'jobs':1,'priority':'below-normal','modelsRun':False,'log':str(log),'installed':False}
for item in frozen['sourceFiles']:assert sha(S/item['path'])==item['sha256'],item['path']
for item in frozen['windowsWebAssets']:assert sha(S/'apps/windows/dist'/item['path'])==item['sha256'],item['path']
if code==0:
    import shutil
    dest=F/'windows-bin';dest.mkdir(exist_ok=True)
    result['privateNative']=[]
    for name in ['companion-type.exe','companion_type_lib.dll']:
        source=target/'release'/name;shutil.copy2(source,dest/name)
        result['privateNative'].append({'name':name,'sha256':sha(dest/name),'bytes':(dest/name).stat().st_size})
(F/'cargo-release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False));print(log.read_text(encoding='utf8',errors='replace')[-3500:]);raise SystemExit(code)
