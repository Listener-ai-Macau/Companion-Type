"""Compile actual provider source and exercise private extraction on a real response."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,os,re,shutil,subprocess,sys,time
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';M=R/'model-research';PARENT=R/'docs/handoffs/20261108-competitive-sale-standard';C=PARENT/'word-identity-audit-20261109';B=PARENT/'async-speaker-contract-r2';CACHE=Path('E:/CodexData/Companion/.model-cache/competitive-sale-standard-20261108/native-word-recovery-20261109');CACHE.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(M/'src'))
from moss_windows_resource_limits_20261104 import WorkerLimits
limits=WorkerLimits(cpu_percent=5,memory_bytes=2*1024**3)
source=S/'apps/windows/src-tauri/src/backend/volcengine.rs';source_bytes=source.read_bytes();log=(B/'native-test.log').read_text(encoding='utf8',errors='replace');deps=Path('E:/CodexData/Companion/.build-cache/windows051/target/debug/deps')
if (C/'native-check-result.json').exists():
 for name in ['native-check-result.json','native-check-build.log','native-check-harness.rs.txt']:
  shutil.copyfile(C/name,C/(name+'.initial-placeholder-failure'))
externs=[]
for name in ['futures','serde','serde_json','tokio','tokio_tungstenite','uuid']:
 matches=re.findall(r'--extern '+name+r'=([^ ]+\.rlib)',log);assert len(set(matches))==1
 file=Path(matches[0]);assert file.exists() and file.resolve().parent==deps.resolve();externs+=['--extern',name+'='+str(file)]
hook=r'''
// Check-only suffix in the isolated mirror. Everything before this suffix is
// an unchanged byte-for-byte copy of the actual production provider module.
pub fn check_word_recovery_from_actual_response(document: &serde_json::Value) -> serde_json::Value {
 let object=result_object(document).unwrap();
 let raw=object["text"].as_str().unwrap();
 let raw_utterances=object["utterances"].as_array().unwrap();
 let missing=raw_utterances.iter().filter(|u|u.get("text").and_then(serde_json::Value::as_str).is_none()).count();
 assert_eq!(missing,1);
 let complete=extract_text(document).unwrap();
 let utterances=extract_utterances(document);
 assert_eq!(utterances.len(),raw_utterances.len());
 let recovered=utterance_text(&raw_utterances[50]).unwrap();
 assert_eq!(text_signature(&recovered).chars().count(),94);
 assert_eq!(text_signature(&complete).chars().count(),text_signature(raw).chars().count()+94);
 assert!(complete.contains(&recovered));
 assert_eq!(utterances[50].text,recovered);
 assert_eq!(utterances[50].start_ms,241882);
 assert_eq!(utterances[50].end_ms,261542);
 assert_eq!(utterances[50].speaker.as_deref(),Some("0"));
 // Explicit formatted sentence wins over spelled-out number tokens.
 let formatted=serde_json::json!({"result":{"text":"2026年预算100元。","utterances":[{"text":"2026年预算100元。","start_time":0,"end_time":10,"words":[{"text":"二零二六年预算一百元","start_time":0,"end_time":10}]}]}});
 assert_eq!(extract_text(&formatted).as_deref(),Some("2026年预算100元。"));
 assert_eq!(extract_utterances(&formatted)[0].text,"2026年预算100元。");
 // A partial token list must not invent an incomplete replacement.
 let malformed=serde_json::json!({"result":{"text":"现有正文","utterances":[{"words":[{"text":"甲"},{"start_time":1}]}]}});
 assert!(utterance_text(&malformed["result"]["utterances"][0]).is_none());
 assert_eq!(extract_text(&malformed).as_deref(),Some("现有正文"));
 let conflict=serde_json::json!({"result":{"text":"独立正文","utterances":[{"text":"甲"},{"words":[{"text":"乙"}]}]}});
 assert_eq!(extract_text(&conflict).as_deref(),Some("独立正文"));
 let only_tokens=serde_json::json!({"result":{"utterances":[{"words":[{"text":"甲"},{"text":"乙"}]}]}});
 assert_eq!(extract_text(&only_tokens).as_deref(),Some("甲乙"));
 let empty=serde_json::json!({"result":{"text":"","utterances":[]}});
 assert_eq!(extract_text(&empty).as_deref(),Some(""));
 let provider=VolcengineSaucAsr::new(VolcengineCredentials{app_id:"test-app".into(),access_token:"test-key".into(),resource_id:"volc.bigasr.sauc.duration".into()});
 let config=provider.cache_configuration();
 assert_eq!(config["response_parser"],"utterance-text-or-complete-word-tokens-v2");
 assert_eq!(config["payload"]["request"]["enable_nonstream"],true);
 assert_eq!(config["payload"]["request"]["ssd_version"],"200");
 let mut old=config.clone();old.as_object_mut().unwrap().remove("response_parser");assert_ne!(config,old);
 serde_json::json!({"state":"PASS_REAL_RESPONSE_WORD_TEXT_RECOVERY_AND_REGRESSIONS","text":complete,"utterances":utterances,"recoveredActualCharacters":94,"originalUtteranceCount":raw_utterances.len(),"recoveredUtteranceCount":missing,"formattedTextPreserved":true,"malformedTokensRefused":true,"unexplainedTopTextPreserved":true,"emptyProbePreserved":true,"cacheParserPolicyChanged":true})
}
'''
mirror=CACHE/'backend';(mirror/'volcengine').mkdir(parents=True,exist_ok=True)
(mirror/'volcengine.rs').write_bytes(source_bytes+hook.encode('utf8'));shutil.copyfile(source.parent/'volcengine/network_probe.rs',mirror/'volcengine/network_probe.rs')
assert (mirror/'volcengine.rs').read_bytes()[:len(source_bytes)]==source_bytes
harness='''#![allow(dead_code,unused_imports)]
mod backend {pub mod volcengine;}
fn main(){let data=std::fs::read_to_string(r"@@RESPONSE_PATH@@").unwrap();let value:serde_json::Value=serde_json::from_str(&data).unwrap();let result=backend::volcengine::check_word_recovery_from_actual_response(&value);std::fs::write(r"@@OUTPUT_PATH@@",serde_json::to_vec_pretty(&result).unwrap()).unwrap();println!("PASS_REAL_PROVIDER_RESPONSE_WORD_RECOVERY");}
'''.replace('@@RESPONSE_PATH@@',str(B/'prefix-final-response.json')).replace('@@OUTPUT_PATH@@',str(C/'native-recovered-transcript.json'))
(CACHE/'check.rs').write_text(harness,encoding='utf8');(C/'native-check-harness.rs.txt').write_text(harness,encoding='utf8');(C/'native-check-hook.rs.txt').write_text(hook,encoding='utf8')
command=['C:/Users/Billy/.rustup/toolchains/stable-x86_64-pc-windows-msvc/bin/rustc.exe','--edition=2021','--crate-name','companion_word_recovery',str(CACHE/'check.rs'),'-L','dependency='+str(deps),*externs,'-C','debuginfo=0','-o',str(CACHE/'check.exe')]
started=time.perf_counter();p=subprocess.run(command,capture_output=True,text=True);(C/'native-check-build.log').write_text(p.stdout+p.stderr,encoding='utf8')
result={'at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'state':'NATIVE_WORD_RECOVERY_CHECK_FAILED','compileExitCode':p.returncode,'productionSourceSha256':hashlib.sha256(source_bytes).hexdigest(),'actualProductionSourcePrefixUnchanged':True,'checkOnlySuffixAddedInPrivateMirror':True,'fullAppBuildPassed':False,'installed':False,'newNetworkCalls':0}
if p.returncode==0:
 check=subprocess.run([str(CACHE/'check.exe')],capture_output=True,text=True);(C/'native-check-run.log').write_text(check.stdout+check.stderr,encoding='utf8');result.update(runExitCode=check.returncode,output=check.stdout.strip())
 if check.returncode==0 and 'PASS_REAL_PROVIDER_RESPONSE_WORD_RECOVERY' in check.stdout:result['state']='NATIVE_WORD_RECOVERY_CHECK_PASSED'
result['wallSeconds']=time.perf_counter()-started;(C/'native-check-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
