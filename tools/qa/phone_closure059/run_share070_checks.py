from pathlib import Path
import hashlib,json,os,psutil,subprocess,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055'
O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share070';O.mkdir(exist_ok=True)
C=Path('E:/CodexData/Companion/.build-cache/windows051');target=C/'target'
env={**os.environ,'CARGO_BUILD_JOBS':'1','CARGO_INCREMENTAL':'0','CARGO_TARGET_DIR':str(target),'RAYON_NUM_THREADS':'2','TEMP':str(C),'TMP':str(C)}
psutil.Process().cpu_affinity([12,13,14,15])
pre=subprocess.run([os.sys.executable,str(R/'tools/check_type_build_target.py'),'--target-dir',str(target),'--project',str(S/'apps/windows/src-tauri'),'--source-dir',str(S)],capture_output=True,text=True,encoding='utf8',errors='replace')
(O/'test-build-preflight.json').write_text(pre.stdout,encoding='utf8');assert pre.returncode==0,pre.stdout+pre.stderr
start=time.perf_counter();log=O/('source-tests-'+str(time.time_ns())+'.jsonl')
print('Building matching native library tests, one job on four CPU slots; no UI, model or device operation.',flush=True)
with log.open('wb') as stream:
 run=subprocess.run(['C:/Users/Billy/.cargo/bin/cargo.exe','test','--offline','--locked','--lib','--no-run','--message-format=json'],cwd=S/'apps/windows/src-tauri',env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
if run.returncode:
 for line in log.read_text(encoding='utf8',errors='replace').splitlines():
  try:row=json.loads(line)
  except ValueError:continue
  if row.get('reason')=='compiler-message' and row.get('message',{}).get('level')=='error':print(row['message'].get('rendered'),flush=True)
 raise RuntimeError('Native test build failed: '+str(log))
artifacts=[]
for line in log.read_text(encoding='utf8',errors='replace').splitlines():
 try:row=json.loads(line)
 except ValueError:continue
 if row.get('reason')=='compiler-artifact' and row.get('profile',{}).get('test') and row.get('executable') and row.get('target',{}).get('name')=='companion_type_lib':artifacts.append(row['executable'])
assert len(artifacts)==1;exe=Path(artifacts[0])
run=subprocess.run([str(exe),'content_handoff::tests::','--test-threads=1','--nocapture'],env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=45,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
(O/'targeted-native-tests.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,run.stdout+run.stderr
assert 'content070_file_location_resolves_only_existing_exact_file_without_opening_explorer ... ok' in run.stdout
record={'state':'FOLDER_SHARE_SOURCE_AND_SHELL_PATH_TESTS_PASSED_NO_UI_OPENED','wallSeconds':round(time.perf_counter()-start,3),'sourceSha256':hashlib.sha256((S/'apps/windows/src-tauri/src/content_handoff.rs').read_bytes()).hexdigest(),'testExeSha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'jobs':1,'cpuSlots':[12,13,14,15],'modelsRun':False,'computerUse':False,'uiOpened':False,'actualShareRecipientVerified':False,'installedVersionUnchanged':'0.1.67'}
(O/'native-test-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(record),flush=True)
