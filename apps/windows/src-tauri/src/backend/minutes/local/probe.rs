//! Explicit headless candidate evidence. It reads only the named, hash-bound
//! source, never the user's meeting library, device, microphone or service key.
use std::{fs::{self,OpenOptions},io::Write,path::{Path,PathBuf},sync::atomic::{AtomicBool,Ordering},time::{Duration,Instant,SystemTime,UNIX_EPOCH}};
use serde::Deserialize;
use serde_json::{json,Value};
use sha2::{Digest,Sha256};
use crate::companion_v1::CompanionV1HostSession;
#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Input {
    source_file: PathBuf,
    expected_file_sha256: String,
    title: String,
    duration_ms: u64,
    reuse_checkpoint: Option<super::source_checkpoint::CheckpointInput>,
    vulkan_runtime_dir: Option<PathBuf>,
}
struct Finish<'a>(&'a AtomicBool);
impl Drop for Finish<'_>{fn drop(&mut self){self.0.store(true,Ordering::Release);}}

fn session(text:String,title:&str,duration:u64)->Result<CompanionV1HostSession,String>{
    serde_json::from_value(json!({"id":format!("local-candidate-{}",uuid::Uuid::new_v4()),"title":title,"source":"approvedEngineeringTranscript",
        "status":"transcribed","meetingMode":"offlineStore","durationMs":duration,"audioBytes":0,"audioStored":false,
        "chunks":[],"transcriptText":text,"transcriptPreview":"","transcriptSegments":1,"transcriptFinal":true,"exportMarkdown":"",
        "retention":{"audioCached":false,"transcriptCached":true,"minutesCached":false,"consentRequired":false,"retentionLabel":"isolated public-source candidate"}}))
        .map_err(|_|"工程原文输入结构不完整，未开始生成。".into())
}

fn save_new(path:&Path,value:&Value)->Result<(),String>{
    let mut file=OpenOptions::new().write(true).create_new(true).open(path).map_err(|_|"无法创建新的工程证据文件。")?;
    file.write_all(&serde_json::to_vec_pretty(value).map_err(|_|"无法编码工程证据。")?).and_then(|_|file.sync_all()).map_err(|_|"无法保存工程证据。".into())
}
fn state(root:&Path,value:&Value)->Result<(),String>{
    replace_state(root,"state",value)
}
fn replace_state(root:&Path,name:&str,value:&Value)->Result<(),String>{
    let temp=root.join(format!("{name}.tmp"));let target=root.join(format!("{name}.json"));
    let mut file=OpenOptions::new().write(true).create(true).truncate(true).open(&temp).map_err(|_|"无法保存工程进度。")?;
    file.write_all(&serde_json::to_vec_pretty(value).map_err(|_|"无法编码工程进度。")?).and_then(|_|file.sync_all()).map_err(|_|"无法保存工程进度。")?;
    drop(file);super::super::super::export::replace_file(&temp.canonicalize().map_err(|_|"无法定位工程进度。")?,&target)
}

pub(crate) fn candidate(input:&Path,output:&Path)->Result<Value,String>{
    if input.metadata().map_err(|_|"无法读取工程输入。")?.len()>16*1024{return Err("工程输入配置过大，未读取会议。".into());}
    let input:Input=serde_json::from_slice(&fs::read(input).map_err(|_|"无法读取工程输入。")?).map_err(|_|"工程输入配置不完整。")?;
    if input.source_file.metadata().map_err(|_|"指定原文不存在。")?.len()>super::source_windows::MAX_SOURCE_BYTES as u64 + 3 {
        return Err("指定原文超出本批容量，未截断内容。".into());
    }
    let bytes=fs::read(&input.source_file).map_err(|_|"无法读取指定原文。")?;
    let file_hash=format!("{:x}",Sha256::digest(&bytes));
    if file_hash!=input.expected_file_sha256{return Err("指定原文哈希不匹配，未开始生成。".into());}
    let text=String::from_utf8(bytes).map_err(|_|"指定原文不是UTF-8。")?;
    let text=text.strip_prefix('\u{feff}').unwrap_or(&text).replace("\r\n","\n");
    let source_hash=format!("{:x}",Sha256::digest(text.as_bytes()));
    let reused = input.reuse_checkpoint.as_ref().map(|checkpoint| {
        super::source_checkpoint::CheckedSourcePrefix::load(checkpoint, &text, &source_hash, input.duration_ms,
            input.vulkan_runtime_dir.is_some())
    }).transpose()?.unwrap_or_default();
    let session=session(text,&input.title,input.duration_ms)?;
    fs::create_dir(output).map_err(|_|"工程输出目录必须是新的目录，已有证据保留。")?;
    let root=output.canonicalize().map_err(|_|"无法定位工程输出目录。")?;
    let header=json!({"state":"running-native-local-candidate","processId":std::process::id(),"sourceFile":input.source_file,
        "sourceFileSha256":file_hash,"sourceSha256":source_hash,"sourceCharacters":session.transcript_text.chars().count(),
        "sourceNormalization":"UTF-8 BOM stripped and CRLF to LF only; original file never changed","durationMs":input.duration_ms,
        "newCloudCalls":0,"trainingUpdates":0,"normalApplicationSaveVerified":false,"contentQualified":false});
    state(&root,&header)?;println!("local_minutes_candidate_started={header}");
    let trace=super::new_trace();let finished=AtomicBool::new(false);let job_id=uuid::Uuid::new_v4().to_string();
    let base=super::super::rules_l0_minutes(&session,"engineering-candidate");
    let mut receipt=None;
    let result=std::thread::scope(|scope|{
        let monitor=scope.spawn(||{
            let mut last_checkpoint=None;
            while !finished.load(Ordering::Acquire){
                if root.join("stop.request").exists(){let _=super::super::super::meeting_processing_job::cancel(&session.id,&job_id);}
                let mut live=header.clone();
                let observed=SystemTime::now().duration_since(UNIX_EPOCH).map(|d|d.as_millis()).unwrap_or(0);
                live["observedAtUnixMs"]=json!(observed);
                let mut checkpoint=None;
                if let Ok(trace)=trace.lock(){
                    live["stage"]=trace["stage"].clone();live["generationSeconds"]=trace["generationSeconds"].clone();
                    live["sourceWindow"]=trace["sourceWindow"].clone();
                    live["outputCharacters"]=json!(trace["output"].as_str().map(|s|s.chars().count()).unwrap_or(0));
                    live["reasoningCharacters"]=trace["reasoningCharacters"].clone();
                    if last_checkpoint.is_none_or(|last:Instant|last.elapsed()>=Duration::from_secs(10)){
                        checkpoint=Some(trace.clone());last_checkpoint=Some(Instant::now());
                    }
                }
                // One bounded, overwritten checkpoint for this explicitly named
                // engineering source. Preserve partial answers/call receipts on
                // interruption; internal thoughts and authorization keys never
                // enter the trace. This is never a publishable or saved meeting.
                if let Some(trace)=checkpoint{
                    let _=replace_state(&root,"generation-checkpoint",&json!({"state":"INCOMPLETE_ENGINEERING_CHECKPOINT_NOT_PUBLICATION",
                        "observedAtUnixMs":observed,"contentQualified":false,"normalApplicationSaveVerified":false,"trace":trace}));
                }
                let _=state(&root,&live);std::thread::sleep(Duration::from_millis(500));
            }
        });
        let finish=Finish(&finished);
        let result=super::super::super::meeting_processing_job::run(&session.id,&job_id,
            super::super::super::meeting_processing_job::Kind::Minutes,||{
                let policy=input.vulkan_runtime_dir.as_deref().map_or(super::RuntimePolicy::Cpu,super::RuntimePolicy::ExplicitVulkan);
                let(result,record)=super::recorded_attempt(&session,&base,trace.clone(),&reused,policy);receipt=Some(record);result
            });
        drop(finish);let _=monitor.join();result
    });
    let mut report=header;report["state"]=json!(if result.is_ok(){"native-candidate-engineer-review-required"}else{"native-candidate-failed-retained"});
    report["error"]=json!(result.as_ref().err());report["receipt"]=receipt.unwrap_or(Value::Null);
    if let Ok(minutes)=&result{
        save_new(&root.join("candidate.json"),&serde_json::to_value(minutes).map_err(|_|"无法编码候选纪要。")?)?;
        let mut file=OpenOptions::new().write(true).create_new(true).open(root.join("candidate.txt")).map_err(|_|"无法创建候选纪要证据。")?;
        file.write_all(minutes.markdown.as_bytes()).and_then(|_|file.sync_all()).map_err(|_|"无法保存候选纪要证据。")?;
    }
    save_new(&root.join("completed.json"),&report)?;state(&root,&report)?;
    if let Err(error)=result{return Err(error);}Ok(report)
}

#[cfg(test)]
mod tests{
    use super::*;

    #[test]
    fn local_minutes_replay_saved_chapter_selection() {
        use super::super::{atomic_document, source_checkpoint::{CheckedSourcePrefix, CheckpointInput}, source_windows::SourceWindows};
        use super::super::super::canonical_brief::source_first_input;
        let Some(directory)=std::env::var_os("COMPANION_TEST_CHAPTER_REPLAY_ROOT") else { return; };
        let directory=PathBuf::from(directory);
        let output=PathBuf::from(std::env::var_os("COMPANION_TEST_CHAPTER_REPLAY_OUTPUT").unwrap());
        fs::create_dir(&output).unwrap();
        for label in ["comparison","market"] {
            let from=directory.join(label);
            let manifest:Value=serde_json::from_slice(&fs::read(from.join("results.json")).unwrap()).unwrap();
            for (key,run) in manifest["results"].as_object().unwrap() {
                assert!(run["backend"]=="vulkan" && run["engineReleased"]==true);
                let input:Input=serde_json::from_slice(&fs::read(from.join(format!("{key}-input.json"))).unwrap()).unwrap();
                let bytes=fs::read(input.source_file).unwrap();
                assert_eq!(format!("{:x}",Sha256::digest(&bytes)),input.expected_file_sha256);
                let text=std::str::from_utf8(&bytes).unwrap();
                let text=text.trim_start_matches('\u{feff}').replace("\r\n","\n");
                let sha=format!("{:x}",Sha256::digest(text.as_bytes()));
                let path=from.join(key).join("completed.json");
                let raw=fs::read(&path).unwrap();
                let original:Value=serde_json::from_slice(&raw).unwrap();
                let original_sha=format!("{:x}",Sha256::digest(&raw));
                let checkpoint:CheckpointInput=serde_json::from_value(json!({"path":path,"sha256":original_sha})).unwrap();
                let prefix=CheckedSourcePrefix::load(&checkpoint,&text,&sha,input.duration_ms,true).unwrap();
                let windows=SourceWindows::new(&text).unwrap();
                assert_eq!(prefix.len(),windows.len());
                let mut facts=Vec::new();
                for index in 0..windows.len() {
                    let (encoding,call)=prefix.window(index).unwrap();
                    let raw=call.map(|call| call["output"].as_str().unwrap()).unwrap_or("{}");
                    facts.extend(windows.check_encoded(index,raw,encoding).unwrap().facts);
                }
                let mut bank=atomic_document::build_bank(facts,&text).unwrap();
                let calls=original["receipt"]["calls"].as_array().unwrap();
                let core=calls.iter().find(|call| call["stage"]=="compact-core-organization").unwrap();
                assert_eq!(core["request"]["messages"][0]["content"],atomic_document::layout_prompt(&bank));
                assert_eq!(core["request"]["messages"][1]["content"],source_first_input(&atomic_document::layout_input(&bank)));
                assert_eq!(core["request"]["response_format"]["json_schema"]["schema"],atomic_document::layout_schema(&bank).unwrap());
                let mut review=calls.iter().filter(|call| call["stage"].as_str().unwrap_or("").starts_with("chapter-review-"));
                let raw=atomic_document::review_chapters(&mut bank,core["output"].as_str(),&text,|prompt,input,schema,stage| {
                    let call=review.next().expect("every current chapter request must have a matching GPU reply");
                    assert_eq!(call["stage"],stage);
                    assert_eq!(call["request"]["messages"][0]["content"],prompt);
                    assert_eq!(call["request"]["messages"][1]["content"],source_first_input(&input));
                    assert_eq!(call["request"]["response_format"]["json_schema"]["schema"],schema);
                    Ok(call["output"].as_str().unwrap().to_owned())
                }).unwrap();
                assert!(review.next().is_none());
                let session=session(text,&input.title,input.duration_ms).unwrap();
                let base=super::super::super::rules_l0_minutes(&session,"engineering-candidate");
                let rendered=atomic_document::organize(&raw,&bank,&session,&base).unwrap();
                let result=output.join(key);
                fs::create_dir(&result).unwrap();
                fs::write(result.join("candidate.txt"),&rendered.minutes.markdown).unwrap();
                save_new(&result.join("replay.json"),&json!({
                    "mode":"deterministic-reader-replay-of-real-gpu-replies",
                    "originalGpuReceipt":path,"originalGpuReceiptSha":original_sha,
                    "sourceFileSha256":input.expected_file_sha256,"exactChapterRequestsVerified":true,
                    "newModelCalls":0,"documentReceipt":rendered.receipt
                })).unwrap();
            }
        }
    }

    #[test]
    fn local_minutes_probe_constructor_preserves_exact_source_and_never_claims_real_capture(){
        let source="观点：预算未批准。\n赵工承诺周五报告。";
        let row=session(source.into(),"公开原文",120000).unwrap();assert_eq!(row.transcript_text,source);
        assert!(row.audio_path.is_none()&&!row.audio_stored);assert_eq!(row.source,"approvedEngineeringTranscript");
        assert!(row.meeting_notes.is_empty()&&row.minutes.is_none());
    }
}
