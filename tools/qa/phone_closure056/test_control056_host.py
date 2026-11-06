from pathlib import Path
import subprocess,os,json,time
r=Path('C:/Users/Billy/Desktop/Denzic/Companion');s=r/'companion-android-device-closure055';b=r/'docs/handoffs/20261106-device-phone-closure055/phone-followup';c=Path('E:/CodexData/Companion/.build-cache/device-phone055/native056');env={**os.environ,'PATH':'C:/Users/Billy/.cargo/bin'+os.pathsep+os.environ['PATH'],'CARGO_TARGET_DIR':str(c/'target'),'CARGO_BUILD_JOBS':'1','CARGO_INCREMENTAL':'0','TEMP':str(c),'TMP':str(c)}
cmd=['C:/Users/Billy/.cargo/bin/cargo.exe','test','--offline','--locked','--release','--jobs','1','--lib','--features','mobile-asr,mobile-local-asr,mobile-calendar,mobile-control','--target','x86_64-pc-windows-msvc','--manifest-path',str(s/'apps/android-backend/native/Cargo.toml'),'backend::control_','--','--test-threads=1'];log=b/('control-host-tests-'+str(time.time_ns())+'.log');start=time.perf_counter()
with log.open('wb') as out:p=subprocess.run(cmd,cwd=s,env=env,stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
text=log.read_text(encoding='utf8',errors='replace');assert p.returncode==0,text[-7000:];assert 'test result: ok.' in text and '0 failed' in text
java=(b/'metadata-java-result.log').read_text(encoding='utf8');assert 'PASS exact actual dated120B and legacy112B metadata callback' in java
phoneLock=json.loads((b/'production-lock-result.json').read_text());assert phoneLock['result']=='PASS_EXACT_PRODUCTION_LOCK_ON_WINDOWS_AND_ANDROID'
artifacts=[];armLog=sorted(b.glob('control-android-tests-build-*.log'),key=lambda x:x.stat().st_mtime)[-1]
for line in armLog.read_text(encoding='utf8',errors='replace').splitlines():
 try:v=json.loads(line)
 except ValueError:continue
 if v.get('reason')=='compiler-artifact' and v.get('profile',{}).get('test') and v.get('executable'):artifacts.append(v['executable'])
assert len(artifacts)==1 and Path(artifacts[0]).is_file()
record={'result':'PASS_HOST_CONTROL_ENGINE_AND_REAL_ANDROID_LOCK_ANDROID_ENGINE_EXECUTION_PENDING','hostSummary':text[text.rfind('running '):],'hostLog':str(log),'wallSeconds':round(time.perf_counter()-start,3),'javaResult':java.splitlines()[-1],'classesDirectory':str(c/'metadata-java-classes'),'androidUnitBinaryCompiled':artifacts[0],'androidEngineRuntime':'PENDING: adb device disappeared before upload; Owner now using phone, no reconnect request or foreground operation','actualAndroidProductionLockPassed':True,'phoneActivityStarted':False,'bluetoothUsed':False,'modelsRun':False,'ownerPhoneForegroundTouched':False,'scope':'Exact production recorder-control engine and112/120B metadata on host, production lock already actually exercised on Android. Full ARM suite compiled, not executed while disconnected; actual App button and recorder acceptance still open.'};(b/'control-background-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(record,ensure_ascii=False))
