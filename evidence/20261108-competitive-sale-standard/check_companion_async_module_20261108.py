"""Compile the actual provider module alone, avoiding the full app test image."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,re,subprocess,sys,time,shutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';C=R/'docs/handoffs/20261108-competitive-sale-standard/async-speaker-contract-r2';CACHE=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/native-contract');CACHE.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(R/'model-research/src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
source=S/'apps/windows/src-tauri/src/backend/volcengine.rs';log=(C/'native-test.log').read_text(encoding='utf8',errors='replace');deps=Path('E:/CodexData/Companion/.build-cache/windows051/target/debug/deps')
required=['futures','serde','serde_json','tokio','tokio_tungstenite','uuid'];externs=[]
for name in required:
 matches=re.findall(r'--extern '+name+r'=([^ ]+\.rlib)',log);assert len(set(matches))==1,(name,matches)
 file=Path(matches[0]);assert file.exists() and file.resolve().parent==deps.resolve();externs+=['--extern',name+'='+str(file)]
if (C/'native-module-check.json').exists():
 for name in ['native-module-check.json','native-module-build.log','native-module-harness.rs.txt']:
  shutil.copyfile(C/name,C/(name+'.initial-module-path-failure'))
mirror=CACHE/'backend';(mirror/'volcengine').mkdir(parents=True,exist_ok=True)
shutil.copyfile(source,mirror/'volcengine.rs');shutil.copyfile(source.parent/'volcengine/network_probe.rs',mirror/'volcengine/network_probe.rs')
assert (mirror/'volcengine.rs').read_bytes()==source.read_bytes()
harness='''#![allow(dead_code,unused_imports)]
mod backend { pub mod volcengine; }
fn main() {
 use backend::volcengine::{VolcengineSaucAsr,VolcengineCredentials};
 let build=|resource:&str|VolcengineSaucAsr::new(VolcengineCredentials{app_id:"test-app".into(),access_token:"test-key".into(),resource_id:resource.into()}).cache_configuration();
 let current=build("volc.bigasr.sauc.duration");
 assert!(current["endpoint"].as_str().unwrap().ends_with("bigmodel_async"));
 assert_eq!(current["payload"]["request"]["enable_speaker_info"],true);
 assert_eq!(current["payload"]["request"]["show_utterances"],true);
 assert_eq!(current["payload"]["request"]["enable_nonstream"],true);
 assert_eq!(current["payload"]["request"]["ssd_version"],"200");
 let mut old=current.clone();old["payload"]["request"]["enable_nonstream"]=serde_json::json!(false);old["payload"]["request"].as_object_mut().unwrap().remove("ssd_version");
 assert_ne!(current,old);
 let seed=build("volc.seedasr.sauc.duration");
 assert!(seed["endpoint"].as_str().unwrap().ends_with("bigmodel_nostream"));
 assert!(seed["payload"]["request"].get("enable_nonstream").is_none());
 assert_eq!(seed["payload"]["request"]["enable_speaker_info"],true);
 println!("PASS_ACTUAL_PROVIDER_REQUEST_AND_CACHE_CONTRACT_SEED_UNCHANGED");
}
'''.replace('PRODUCTION_SOURCE',str(source))
(CACHE/'contract.rs').write_text(harness,encoding='utf8');(C/'native-module-harness.rs.txt').write_text(harness,encoding='utf8')
exe=CACHE/'contract.exe';command=['C:/Users/Billy/.rustup/toolchains/stable-x86_64-pc-windows-msvc/bin/rustc.exe','--edition=2021','--crate-name','companion_async_contract',str(CACHE/'contract.rs'),'-L','dependency='+str(deps),*externs,'-C','debuginfo=0','-o',str(exe)]
started=time.perf_counter();p=subprocess.run(command,capture_output=True,text=True);(C/'native-module-build.log').write_text(p.stdout+p.stderr,encoding='utf8')
result={'at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':'ACTUAL_PROVIDER_MODULE_CHECK_FAILED','compileExitCode':p.returncode,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'fullAppTestPassed':False,'previousFullAppCompileFailure':'Rustc allocation failure inside bounded2GiB full-app test build; original log preserved. No increased memory pressure or repeated full build.','installed':False,'sourceModuleRewrittenForHarness':False}
if p.returncode==0:
 test=subprocess.run([str(exe)],capture_output=True,text=True);result.update(runExitCode=test.returncode,output=test.stdout.strip());result['state']='ACTUAL_PROVIDER_MODULE_CHECK_PASSED' if test.returncode==0 and 'PASS_ACTUAL_PROVIDER_REQUEST_AND_CACHE_CONTRACT_SEED_UNCHANGED' in test.stdout else result['state']
result['wallSeconds']=time.perf_counter()-started;(C/'native-module-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
