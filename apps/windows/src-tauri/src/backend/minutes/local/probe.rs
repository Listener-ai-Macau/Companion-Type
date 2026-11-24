//! Explicit headless candidate evidence. It reads only the named, hash-bound
//! source, never the user's meeting library, device, microphone or service key.
use std::{fs::{self,OpenOptions},io::{Read,Write},path::{Path,PathBuf},sync::atomic::{AtomicBool,Ordering},time::{Duration,Instant,SystemTime,UNIX_EPOCH}};
use serde::Deserialize;
use serde_json::{json,Value};
use sha2::{Digest,Sha256};
use crate::companion_v1::{CompanionV1HostSession,CompanionV1UtteranceSegment};
#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Input {
    source_file: PathBuf,
    expected_file_sha256: String,
    title: String,
    duration_ms: u64,
    reuse_checkpoint: Option<super::source_checkpoint::CheckpointInput>,
    vulkan_runtime_dir: Option<PathBuf>,
    saved_utterances: Option<SavedUtterances>,
}
#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct SavedUtterances {
    path: PathBuf,
    sha256: String,
}

fn load_saved_utterances(input: &SavedUtterances) -> Result<Vec<CompanionV1UtteranceSegment>,String> {
    const MAX_BYTES: u64 = 2 * 1024 * 1024;
    let error = || "已保存发言片段的校验不匹配，未开始生成。".to_owned();
    let mut bytes=Vec::new();
    fs::File::open(&input.path).map_err(|_|error())?.take(MAX_BYTES+1)
        .read_to_end(&mut bytes).map_err(|_|error())?;
    if bytes.len() as u64>MAX_BYTES || format!("{:x}",Sha256::digest(&bytes))!=input.sha256 {
        return Err(error());
    }
    serde_json::from_slice(&bytes).map_err(|_|error())
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
    let mut session=session(text,&input.title,input.duration_ms)?;
    if let Some(saved) = &input.saved_utterances {
        session.utterances=load_saved_utterances(saved)?;
        let source=&session.transcript_text;
        let units=super::super::canonical_brief::source_units(source);
        let sentences=super::super::automatic_brief::factual_audit::evidence_sentences(&units);
        if super::timed_evidence::Timing::verified(source,&sentences,&session.utterances).is_none() {
            return Err("保存的发言片段与指定转写不一致，未开始生成。".into());
        }
    }
    fs::create_dir(output).map_err(|_|"工程输出目录必须是新的目录，已有证据保留。")?;
    let root=output.canonicalize().map_err(|_|"无法定位工程输出目录。")?;
    let header=json!({"state":"running-native-local-candidate","processId":std::process::id(),"sourceFile":input.source_file,
        "sourceFileSha256":file_hash,"sourceSha256":source_hash,"sourceCharacters":session.transcript_text.chars().count(),
        "sourceNormalization":"UTF-8 BOM stripped and CRLF to LF only; original file never changed","durationMs":input.duration_ms,
        "newCloudCalls":0,"trainingUpdates":0,"normalApplicationSaveVerified":false,"contentQualified":false,
        "savedUtterances":input.saved_utterances.as_ref().map(|case|json!({"path":case.path,"sha256":case.sha256,"count":session.utterances.len()}))});
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

    fn replay_reply(
        calls: &[Value], stage: &str, prompt: &str, input: Value, schema: Value,
        tokens: usize, profile: &Value, vulkan: bool,
    ) -> Result<String, String> {
        use super::super::transport;
        let Some(call) = calls.iter().find(|call| call["stage"] == stage) else {
            return Err(format!("no saved response for {stage}"));
        };
        let alias = call["request"]["model"].as_str().unwrap();
        let mut expected = transport::request_body(alias, prompt, input, schema, tokens, profile)?;
        if vulkan {
            transport::use_vulkan_schema(&mut expected);
        }
        assert_eq!(call["request"], expected, "saved request changed at {stage}");
        call["output"].as_str().filter(|_| call["finishReason"] == "stop").map(str::to_owned)
            .ok_or_else(|| format!("no complete saved response for {stage}"))
    }

    #[test]
    fn local_minutes_replay_saved_chapter_selection() {
        use super::super::{atomic_document, source_checkpoint::{CheckedSourcePrefix, CheckpointInput}, source_review, source_windows, transport};
        let Some(directory)=std::env::var_os("COMPANION_TEST_CHAPTER_REPLAY_ROOT") else { return; };
        let directory=PathBuf::from(directory);
        let output=PathBuf::from(std::env::var_os("COMPANION_TEST_CHAPTER_REPLAY_OUTPUT").unwrap());
        fs::create_dir(&output).unwrap();
        let choices = std::env::var("COMPANION_TEST_CHAPTER_REPLAY_CASES").unwrap_or_default();
        let selected: Vec<_> = choices.split(',').filter(|name| !name.is_empty()).collect();
        let facts_only = std::env::var("COMPANION_TEST_CHAPTER_REPLAY_FACTS_ONLY").as_deref() == Ok("1");
        let roots = if directory.join("results.json").is_file() { vec![directory] }
            else { vec![directory.join("comparison"), directory.join("market")] };
        let profile = transport::profile().unwrap();
        let mut replayed = 0;
        for from in roots {
            let manifest:Value=serde_json::from_slice(&fs::read(from.join("results.json")).unwrap()).unwrap();
            let runs = manifest.get("cases").unwrap_or(&manifest["results"]).as_object().unwrap();
            for (key,run) in runs {
                if !selected.is_empty() && !selected.contains(&key.as_str()) { continue; }
                if run.get("exit").is_some_and(|exit| exit != 0) { continue; }
                let vulkan = match run["backend"].as_str() {
                    Some("vulkan") => true,
                    Some("cpu") => false,
                    other => panic!("{key} has unsupported archived backend {other:?}"),
                };
                assert_eq!(run["engineReleased"], true);
                let input:Input=serde_json::from_slice(&fs::read(from.join(format!("{key}-input.json"))).unwrap()).unwrap();
                let bytes=fs::read(input.source_file).unwrap();
                assert_eq!(format!("{:x}",Sha256::digest(&bytes)),input.expected_file_sha256);
                let text=std::str::from_utf8(&bytes).unwrap();
                let text=text.trim_start_matches('\u{feff}').replace("\r\n","\n");
                let sha=format!("{:x}",Sha256::digest(text.as_bytes()));
                let path=from.join(key).join("completed.json");
                let raw=fs::read(&path).unwrap();
                let original:Value=serde_json::from_slice(&raw).unwrap();
                let receipt = &original["receipt"];
                assert_eq!(receipt["backend"], run["backend"]);
                assert_eq!(receipt["serviceReleaseConfirmed"], true);
                let calls=receipt["calls"].as_array().unwrap();
                let context = match (vulkan, receipt["contextTokens"].as_u64()) {
                    (false, Some(8192)) => transport::Context::ReducedCpu,
                    (_, Some(16384)) | (true, None) => transport::Context::Full,
                    (_, other) => panic!("{key} has unsupported archived context {other:?}"),
                };
                let reply = |stage: &str, prompt: &str, input, schema, tokens| {
                    replay_reply(calls, stage, prompt, input, schema, tokens, &profile, vulkan)
                };
                let original_sha=format!("{:x}",Sha256::digest(&raw));
                let mixed_sources = receipt["reusedSourceBackend"] == "vulkan";
                assert!(!mixed_sources || !vulkan, "{key} has conflicting archived runtimes");
                let checkpoint:CheckpointInput=serde_json::from_value(json!({
                    "path":path,"sha256":original_sha,"useVulkanSourceWindowsOnCpu":mixed_sources
                })).unwrap();
                let prefix=CheckedSourcePrefix::load(&checkpoint,&text,&sha,input.duration_ms,vulkan).unwrap();
                let windows=source_windows::SourceWindows::new(&text).unwrap();
                assert_eq!(prefix.len(),windows.len());
                let mut facts=Vec::new();
                let mut excerpts = 0;
                for index in 0..windows.len() {
                    let (encoding,call)=prefix.window(index).unwrap();
                    let raw=call.map(|call| call["output"].as_str().unwrap()).unwrap_or("{}");
                    let mut checked = windows.check_encoded(index,raw,encoding).unwrap();
                    if let Some((input, schema)) = windows.excerpt_request(&checked) {
                        let reply = if excerpts < 4 {
                            excerpts += 1;
                            let stage = format!("source-excerpt-{}", index + 1);
                            assert!(calls.iter().any(|call| call["stage"] == stage), "{key} missing {stage}");
                            reply(&stage, source_windows::EXCERPT_PROMPT, input, schema, 768).ok()
                        } else { None };
                        windows.finish_deferred(&mut checked, reply.as_deref());
                    }
                    facts.extend(checked.facts);
                }
                let review = if calls.iter().any(|call| call["stage"].as_str().unwrap_or("").starts_with("independent-source-review-")) {
                    source_review::review(&text, |prompt, input, schema, stage| {
                        reply(stage, prompt, input, schema, 640)
                    }).unwrap()
                } else { source_review::Review::default() };
                let mut session=session(text.clone(),&input.title,input.duration_ms).unwrap();
                if let Some(saved) = &input.saved_utterances {
                    session.utterances = load_saved_utterances(saved).unwrap();
                }
                let mut bank = atomic_document::build_session_bank(facts, &session, &review).unwrap();
                if facts_only {
                    let result = output.join(key);
                    fs::create_dir(&result).unwrap();
                    save_new(&result.join("fact-replay.json"), &json!({
                        "originalReceipt":path,"originalReceiptSha":original_sha,
                        "sourceFileSha256":input.expected_file_sha256,"newModelCalls":0,
                        "atomicFactBank":bank.receipt
                    })).unwrap();
                    replayed += 1;
                    continue;
                }
                let original_seals = &original["receipt"]["atomicFactBank"]["seals"];
                if original_seals.is_array() {
                    assert_eq!(&bank.receipt["seals"], original_seals, "{key} replay changed extracted facts");
                }
                let core_input_tokens = calls.iter().find(|call| call["stage"] == transport::COMPACT_CORE_STAGE)
                    .and_then(|call| call["inputTokens"].as_u64());
                let core_output = core_input_tokens.map_or(context.layout_output(), |tokens| {
                    context.compact_core_output(tokens as usize, profile["enableThinking"].as_bool().unwrap_or(true))
                });
                let core = reply(transport::COMPACT_CORE_STAGE, atomic_document::layout_prompt(&bank),
                    atomic_document::layout_input(&bank), atomic_document::layout_schema(&bank).unwrap(), core_output).unwrap();
                let core_only = std::env::var_os("COMPANION_TEST_REPLAY_COMPARE_CORE").map(|_| {
                    let base=super::super::super::rules_l0_minutes(&session,"engineering-candidate");
                    let direct = atomic_document::organize(&core, &bank, &session, &base).unwrap();
                    let layout: Value = serde_json::from_str(crate::backend::minutes::strip_code_fences(&core).trim()).unwrap();
                    let nominated = layout["chapters"].as_object().unwrap().values()
                        .flat_map(|chapter| chapter["mainFacts"].as_array().unwrap()).collect::<Vec<_>>();
                    bank.receipt["coreProposedReaderFactIds"] = json!(nominated);
                    let with_sources = atomic_document::organize(&core, &bank, &session, &base).unwrap();
                    bank.receipt.as_object_mut().unwrap().remove("coreProposedReaderFactIds");
                    (direct, with_sources)
                });
                let mut chapter_requests = 0;
                let raw=atomic_document::review_chapters(&mut bank,Some(&core),&text,|prompt,input,schema,stage| {
                    chapter_requests += 1;
                    reply(stage, prompt, input, schema, 768)
                }).unwrap();
                let grouped = |call: &Value| {
                    call["stage"].as_str().is_some_and(|stage| stage.starts_with(super::super::reader_exchanges::STAGE_PREFIX))
                };
                assert_eq!(chapter_requests, calls.iter().filter(|call| {
                    call["stage"].as_str().unwrap_or("").starts_with("chapter-review-") && !grouped(call)
                }).count());
                if calls.iter().any(grouped) {
                    atomic_document::review_reply_groups(&mut bank, &text, |prompt,input,schema,stage| {
                        reply(stage,prompt,input,schema,128)
                    }).unwrap();
                }
                if let Some(folder) = std::env::var_os("COMPANION_TEST_CAPTURE_REPLY_GROUPS") {
                    let folder = PathBuf::from(folder);
                    let reviewed = std::env::var_os("COMPANION_TEST_REVIEWED_REPLY_GROUPS")
                        .map(|folder| PathBuf::from(folder).join(format!("{key}.json")))
                        .map(|path| serde_json::from_slice::<Vec<Value>>(&fs::read(path).unwrap()).unwrap());
                    let mut captured = Vec::new();
                    atomic_document::review_reply_groups(&mut bank, &text, |prompt, input, schema, stage| {
                        let request = json!({"prompt":prompt,"input":input,"schema":schema,"stage":stage});
                        let mut answer = "{}".to_owned();
                        if let Some(supplied) = &reviewed {
                            let choice = supplied.get(captured.len()).ok_or("missing group reply".to_owned())?;
                            if choice["request"] != request { return Err("group request changed".to_owned()); }
                            answer = choice["output"].as_str().ok_or("missing exact group reply".to_owned())?.to_owned();
                        }
                        captured.push(request);
                        Ok(answer)
                    }).unwrap();
                    if let Some(supplied) = &reviewed { assert_eq!(captured.len(), supplied.len()); }
                    fs::write(folder.join(format!("{key}.json")),serde_json::to_vec_pretty(&captured).unwrap()).unwrap();
                }
                let base=super::super::super::rules_l0_minutes(&session,"engineering-candidate");
                let rendered=atomic_document::organize(&raw,&bank,&session,&base).unwrap();
                let result=output.join(key);
                fs::create_dir(&result).unwrap();
                fs::write(result.join("candidate.txt"),&rendered.minutes.markdown).unwrap();
                if let Some((core_only, with_sources)) = core_only {
                    fs::write(result.join("core-only.txt"), &core_only.minutes.markdown).unwrap();
                    fs::write(result.join("core-with-source-marks.txt"), &with_sources.minutes.markdown).unwrap();
                    let chapter_seconds: f64 = calls.iter().filter(|call| {
                        call["stage"].as_str().is_some_and(|stage| stage.starts_with("chapter-review-"))
                    }).filter_map(|call| call["generationSeconds"].as_f64()).sum();
                    save_new(&result.join("core-only.json"), &json!({
                        "experiment":"same archived facts and first layout, without the extra chapter passes",
                        "measuredArchivedChapterSeconds":chapter_seconds,"newModelCalls":0,
                        "documentReceipt":core_only.receipt,
                        "withCoreSourceMarks":with_sources.receipt,
                    })).unwrap();
                }
                let mut replay = json!({
                    "mode": if mixed_sources { "deterministic-reader-replay-of-cpu-draft-with-validated-vulkan-source" }
                        else if vulkan { "deterministic-reader-replay-of-real-gpu-replies" }
                        else { "deterministic-reader-replay-of-real-cpu-replies" },
                    "originalReceipt":path,"originalReceiptSha":original_sha,"backend":run["backend"],
                    "sourceFileSha256":input.expected_file_sha256,"exactChapterRequestsVerified":true,
                    "newModelCalls":0,"documentReceipt":rendered.receipt
                });
                if vulkan {
                    replay["originalGpuReceipt"] = json!(path);
                    replay["originalGpuReceiptSha"] = json!(original_sha);
                }
                save_new(&result.join("replay.json"),&replay).unwrap();
                replayed += 1;
            }
        }
        assert!(replayed > 0, "no completed case matched the supplied replay input");
        assert!(selected.is_empty() || replayed == selected.len(), "selected replay cases were not all verified");
    }

    #[test]
    #[ignore = "runs the native local model on an explicitly supplied transcript"]
    fn run_native_minutes_candidate_on_approved_input() {
        let input = std::env::var_os("COMPANION_TEST_LOCAL_MINUTES_INPUT").expect("provide a hash-bound input");
        let output = std::env::var_os("COMPANION_TEST_LOCAL_MINUTES_OUTPUT").expect("provide a new output directory");
        let result = candidate(Path::new(&input), Path::new(&output)).expect("run the local minutes candidate");
        assert_eq!(result["receipt"]["newCloudCalls"], 0);
        assert_eq!(result["state"], "native-candidate-engineer-review-required");
    }

    #[test]
    #[ignore = "continues a hash-bound real CPU receipt through the desktop recovery route"]
    fn resumes_desktop_minutes_from_a_real_memory_interruption() {
        let archive = std::env::var_os("COMPANION_TEST_DESKTOP_RETRY_REPORT").unwrap();
        let path = PathBuf::from(archive);
        let expected = std::env::var("COMPANION_TEST_DESKTOP_RETRY_SHA").unwrap();
        let output = PathBuf::from(std::env::var_os("COMPANION_TEST_DESKTOP_RETRY_OUTPUT").unwrap());
        fs::create_dir(&output).unwrap();
        let raw = fs::read(path).unwrap();
        assert_eq!(format!("{:x}", Sha256::digest(&raw)), expected);
        let saved: Value = serde_json::from_slice(&raw).unwrap();
        let source = std::fs::read_to_string(saved["sourceFile"].as_str().unwrap()).unwrap();
        let source = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        assert_eq!(format!("{:x}", Sha256::digest(source.as_bytes())), saved["sourceSha256"]);
        let error = crate::backend::external_command::LOCAL_SERVICE_LOW_MEMORY;
        assert_eq!(saved["error"], error);
        assert_eq!(saved["newCloudCalls"], 0);
        let session = session(source, "检查点实际续作", saved["durationMs"].as_u64().unwrap()).unwrap();
        let base = crate::backend::minutes::rules_l0_minutes(&session, "retry-proof");
        let retry_slot = super::super::desktop_retry::RetrySlot::new();
        let mut first = Some(saved["receipt"].clone());
        let started = Instant::now();
        let (result, trace) = super::super::desktop_retry::generate(&retry_slot, &session,
            |prefix, pressure_retry| {
                if let Some(trace) = first.take() {
                    assert!(!pressure_retry);
                    return (Err(error.into()), trace);
                }
                assert!(pressure_retry);
                println!("restored {} checked windows before opening the engine", prefix.len());
                super::super::recorded_attempt(&session, &base, super::super::new_trace(), prefix,
                    super::super::RuntimePolicy::Application { pressure_retry })
            },
            || crate::backend::external_command::wait_for_local_memory_recovery(None),
        );
        save_new(&output.join("desktop-retry-result.json"), &json!({
            "seconds":started.elapsed().as_secs_f64(),"receipt":trace,
            "error":result.as_ref().err(),"sourceSha256":saved["sourceSha256"],
            "candidate":result.as_ref().ok()
        })).unwrap();
        assert!(result.is_ok(), "{:?}", result.as_ref().err());
        assert!(trace["reusedSourceWindows"].as_u64().unwrap_or_default() > 0);
        assert_eq!(trace["newCloudCalls"], 0);
        assert_eq!(trace["cpuPromptCacheMiB"], 0);
    }

    #[test]
    fn produces_a_reviewable_draft_from_a_verified_pressure_receipt_without_starting_an_engine() {
        let Some(archive) = std::env::var_os("COMPANION_TEST_DESKTOP_RETRY_REPORT") else { return; };
        let failed = std::env::var_os("COMPANION_TEST_REVIEWABLE_DRAFT_TRACE").unwrap();
        let out = std::env::var_os("COMPANION_TEST_REVIEWABLE_DRAFT_OUTPUT").unwrap();
        let original: Value = serde_json::from_slice(&fs::read(archive).unwrap()).unwrap();
        let result: Value = serde_json::from_slice(&fs::read(failed).unwrap()).unwrap();
        let source = fs::read_to_string(original["sourceFile"].as_str().unwrap()).unwrap();
        let source = source.trim_start_matches('\u{feff}').replace("\r\n", "\n");
        assert_eq!(format!("{:x}", Sha256::digest(source.as_bytes())), original["sourceSha256"]);
        assert_eq!(original["sourceSha256"], result["sourceSha256"]);
        let session = session(source, "复核稿验证", original["durationMs"].as_u64().unwrap()).unwrap();
        let base = crate::backend::minutes::rules_l0_minutes(&session, "reviewable draft");
        let reason = result["error"].as_str().unwrap().to_owned();
        let mut trace = result["receipt"].clone();
        let requests = trace["inferenceRequestAttempts"].clone();
        let start = std::time::Instant::now();
        let minutes = super::super::finish_desktop_minutes(&session, &base, Err(reason.clone()), &mut trace).unwrap();
        assert_eq!(minutes.quality, "draft");
        assert_eq!(minutes.llm_note.as_deref(), Some(reason.as_str()));
        assert!(minutes.markdown.contains("本地复核草稿") && minutes.markdown.contains("## 主题原话"));
        assert!(!minutes.markdown.contains("## 会议主线"));
        assert_eq!(trace["inferenceRequestAttempts"], requests);
        assert_eq!(trace["reviewableDraft"], true);
        assert_eq!(trace["newCloudCalls"], 0);
        let mut interrupted_review = result["receipt"].clone();
        interrupted_review["calls"].as_array_mut().unwrap().retain(|call| {
            call["stage"].as_str().is_some_and(|stage| stage.starts_with("source-window-"))
        });
        let start_partial = std::time::Instant::now();
        let excerpts = super::super::finish_desktop_minutes(
            &session, &base, Err(reason.clone()), &mut interrupted_review,
        ).unwrap();
        let partial_seconds = start_partial.elapsed().as_secs_f64();
        assert_eq!(interrupted_review["reviewableDraft"], true);
        assert_eq!(interrupted_review["newCloudCalls"], 0);
        assert_eq!(excerpts.quality, "draft");
        assert!(excerpts.markdown.contains("独立复核尚未完成") && excerpts.markdown.contains("## 已整理原话"));
        assert!(!excerpts.markdown.contains("### 共同决定 · 原话") && !excerpts.markdown.contains("### 会后行动 · 原话"));
        assert!(excerpts.summary.is_empty() && excerpts.decisions.is_empty() && excerpts.action_items.is_empty());
        assert!(excerpts.questions.is_empty() && excerpts.source_action_evidence.is_none());
        let mut invalid = trace.clone();
        invalid["retainedSourceWindows"] = json!(0);
        assert!(super::super::finish_desktop_minutes(&session, &base, Err(reason), &mut invalid).is_err());
        save_new(Path::new(&out), &json!({
            "draft":minutes,"seconds":start.elapsed().as_secs_f64(),"sourceSha256":original["sourceSha256"],
            "validatedWindows":trace["retainedSourceWindows"],"additionalModelRequests":0,
            "beforeIndependentReview":{"draft":excerpts,"seconds":partial_seconds,
                "validatedWindows":interrupted_review["retainedSourceWindows"],"additionalModelRequests":0}
        })).unwrap();
    }

    #[test]
    fn local_minutes_probe_constructor_preserves_exact_source_and_never_claims_real_capture(){
        let source="观点：预算未批准。\n赵工承诺周五报告。";
        let row=session(source.into(),"公开原文",120000).unwrap();assert_eq!(row.transcript_text,source);
        assert!(row.audio_path.is_none()&&!row.audio_stored);assert_eq!(row.source,"approvedEngineeringTranscript");
        assert!(row.meeting_notes.is_empty()&&row.minutes.is_none());
    }
}
