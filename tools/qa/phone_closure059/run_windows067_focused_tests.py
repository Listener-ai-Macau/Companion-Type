from pathlib import Path
import hashlib,json,os,psutil,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';F=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering';F.mkdir(exist_ok=True)
C=Path('E:/CodexData/Companion/.build-cache/windows051');target=C/'target'
env={**os.environ,'CARGO_BUILD_JOBS':'1','CARGO_INCREMENTAL':'0','CARGO_TARGET_DIR':str(target),'RAYON_NUM_THREADS':'2','TEMP':str(C),'TMP':str(C)}
pre=subprocess.run([os.sys.executable,str(R/'tools/check_type_build_target.py'),'--target-dir',str(target),'--project',str(S/'apps/windows/src-tauri'),'--source-dir',str(S)],capture_output=True,text=True,encoding='utf8',errors='replace')
(F/'test-build-preflight.json').write_text(pre.stdout,encoding='utf8');assert pre.returncode==0,pre.stdout+pre.stderr
stamp=str(time.time_ns());start=time.perf_counter();log=F/('cargo-focused-tests-build-'+stamp+'.jsonl')
with log.open('wb') as stream:
 p=subprocess.Popen(['C:/Users/Billy/.cargo/bin/cargo.exe','test','--offline','--locked','--lib','--no-run','--message-format=json'],cwd=S/'apps/windows/src-tauri',env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 own=psutil.Process(p.pid);cpus=own.cpu_affinity()[-4:];own.cpu_affinity(cpus)
 while p.poll() is None:
  for child in own.children(recursive=True):
   try:
    if child.name().lower() in ['cargo.exe','rustc.exe','link.exe']:child.cpu_affinity(cpus);child.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
   except (psutil.NoSuchProcess,psutil.AccessDenied):pass
  time.sleep(1)
lines=log.read_text(encoding='utf8',errors='replace').splitlines();artifacts=[]
for line in lines:
 try:value=json.loads(line)
 except ValueError:continue
 if value.get('reason')=='compiler-artifact' and value.get('profile',{}).get('test') and value.get('executable') and value.get('target',{}).get('name')=='companion_type_lib':artifacts.append(value['executable'])
record={'testBuildExitCode':p.returncode,'testBuildSeconds':round(time.perf_counter()-start,3),'jobs':1,'cpuSlots':cpus,'modelsRun':False,'buildLog':str(log)}
(F/'test-build-result.json').write_text(json.dumps(record,indent=2),encoding='utf8')
assert p.returncode==0,'Test compilation failed; see '+str(log)
assert len(artifacts)==1,artifacts;exe=Path(artifacts[0]);listing=subprocess.run([str(exe),'--list'],env=env,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
prefixes=['backend::content_export::tests::','backend::meeting_document_export::tests::','backend::presentation_export::tests::','backend::mindmap_image_export::tests::','backend::pdf_export::tests::','backend::export_text_layout::tests::','backend::external_command::windows::tests::']
names=[line.removesuffix(': test') for line in listing.stdout.splitlines() if line.endswith(': test') and any(line.startswith(prefix) for prefix in prefixes)]
assert any('content067_' in name for name in names),names
results=[]
for name in names:
 test_env=dict(env)
 if name.endswith('content051_generate_files_for_external_reader_checks'):test_env['COMPANION_CONTENT_EXPORT_FIXTURE_DIR']=str(F/('native-files-'+stamp))
 run=subprocess.run([str(exe),'--exact',name,'--test-threads=1','--nocapture'],env=test_env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
 results.append({'name':name,'exitCode':run.returncode,'output':run.stdout+run.stderr})
 (F/'focused-test-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
 assert run.returncode==0,results[-1]
record.update(result='FOCUSED_PRODUCT_SOURCE_TESTS_PASSED',tests=len(results),testExecutableSha256=hashlib.sha256(exe.read_bytes()).hexdigest())
(F/'test-build-result.json').write_text(json.dumps(record,indent=2),encoding='utf8');print(json.dumps(record),flush=True)
