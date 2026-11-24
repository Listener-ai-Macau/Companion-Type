//! Native local minutes: fixed SDK/model, one source-only fact bank then
//! ID-only organization. No Python, paid fallback, judge rewrite or daemon.
mod assets;
mod transport;
mod probe;
mod evidence_document;
mod atomic_document;
mod chapter_spans;
mod chapter_labels;
mod reader_ranking;
mod source_windows;
mod source_authority;
mod source_commitments;
mod source_grounding;
mod source_context;
mod delivery_evidence;
mod reader_scope;
mod reader_context;
mod reader_turns;
mod confirmed_handoffs;
mod reader_exchanges;
mod reader_agenda;
mod reader_coverage;
mod timed_evidence;
mod source_checkpoint;
mod source_review;
mod closing_recap;
mod conversational_close;
mod participant_background;
pub(crate) use probe::candidate as verify_candidate;
pub(super) use source_commitments::stated_group_deliverable;
use std::{collections::HashMap,net::TcpListener,sync::{Arc,Mutex},time::Instant};
use serde_json::{json,Value};
use crate::companion_v1::{CompanionV1HostSession,CompanionV1MeetingMinutes};

const SOURCE_OUTPUT_TOKENS: usize = 2048;

// Enabled only after the frozen implementation passes the actual whole-meeting
// content and installed-app gates. Diagnostics do not promote their own output.
pub(crate) const CONTENT_QUALIFIED:bool=false;
pub(crate) fn assets_present()->bool{assets::present()}
pub(crate) fn supported()->bool{(CONTENT_QUALIFIED||delivery_preview_root().is_some())&&assets::cpu_supported()}
pub(crate) fn prepare()->Result<(),String>{assets::prepare()}
pub(crate) fn check_assets()->Result<(),String>{
    if !supported(){return Err("本地会议整理尚未准备好。".into());}
    assets::runtime()?;assets::verified(&assets::model_path()?,assets::MODEL_BYTES,assets::MODEL_SHA)
}

#[cfg(feature="local-minutes-delivery-preview")]
fn delivery_preview_root()->Option<std::path::PathBuf>{
    let root=std::path::PathBuf::from(std::env::var_os("COMPANION_TYPE_LOCAL_MINUTES_PREVIEW_ROOT")?)
        .canonicalize().ok()?;
    for name in ["COMPANION_TYPE_STATE_PATH","COMPANION_TYPE_PRODUCT_SETTINGS_PATH"] {
        let path=std::path::PathBuf::from(std::env::var_os(name)?);
        if !path.parent()?.canonicalize().ok()?.starts_with(&root) { return None; }
    }
    Some(root)
}

#[cfg(not(feature="local-minutes-delivery-preview"))]
fn delivery_preview_root()->Option<std::path::PathBuf>{None}

enum RuntimePolicy<'a> {
    Cpu,
    ExplicitVulkan(&'a std::path::Path),
    Application,
}

fn arguments(model:&std::path::Path,port:u16,key:&str,alias:&str,device:Option<&str>,context:transport::Context)->Result<Vec<String>,String>{
    let model=model.to_str().ok_or("无法读取本地模型路径。")?;
    let profile=transport::profile()?;
    let template=json!({"enable_thinking":profile["enableThinking"]}).to_string();
    // Upload weights to the verified discrete GPU without keeping the GGUF
    // file mapped into the server's host working set. The CPU still uses mmap.
    let (layers,load_mode)=if device.is_some(){("99","none")}else{("0","mmap")};
    let mut args=["-m",model,"--host","127.0.0.1","--port",&port.to_string(),"--api-key",key,"--alias",alias,
        "-c",&context.tokens().to_string(),"-np","1","-ngl",layers,"-t","4","-tb","4","-b","128","-ub","64",
        "--fit","off","--load-mode",load_mode,"--no-repack","--cache-ram","256","-lv","0",
        "--no-warmup","--no-context-shift","--no-webui","--chat-template-kwargs",&template]
        .into_iter().map(str::to_owned).collect::<Vec<_>>();
    if let Some(device)=device{args.extend(["--device".to_owned(),device.to_owned()]);}
    Ok(args)
}

pub(crate) fn generate(session:&CompanionV1HostSession,base:&CompanionV1MeetingMinutes)->Result<CompanionV1MeetingMinutes,String>{
    if !supported(){return Err("本地会议整理尚未准备好，已有文字和纪要保留。".into());}
    let (minutes,trace)=recorded_attempt(session,base,new_trace(),&source_checkpoint::CheckedSourcePrefix::default(),RuntimePolicy::Application);
    if let Some(root)=delivery_preview_root(){
        let fields=["backend","vulkanDevice","runtimeFallback","sourceWindow","inferenceRequestAttempts","contextTokens","contextFallback",
            "freshWholeRun","reusedSourceWindows","serviceReleaseConfirmed","seconds","error","runtimeSha256","modelLoadMode","newCloudCalls"];
        let summary=fields.into_iter().map(|key|(key.to_owned(),trace[key].clone())).collect::<serde_json::Map<_,_>>();
        let _=std::fs::write(root.join("local-minutes-delivery-trace.json"),Value::Object(summary).to_string());
    }
    let mut minutes=minutes?;
    minutes.quality="final".into();
    Ok(minutes)
}

pub(crate) fn attempt(session:&CompanionV1HostSession,base:&CompanionV1MeetingMinutes)->(Result<CompanionV1MeetingMinutes,String>,Value){
    recorded_attempt(session,base,new_trace(),&source_checkpoint::CheckedSourcePrefix::default(),RuntimePolicy::Cpu)
}
fn new_trace()->transport::Trace{
    Arc::new(Mutex::new(json!({"provider":"local","model":"Qwen3.5-4B-Q4_K_M","runtimeSha256":assets::SERVER_SHA,
        "modelSha256":assets::MODEL_SHA,"stage":"preflight","calls":[],"newCloudCalls":0,"trainingUpdates":0,"semanticAccuracyCertificate":false,"contentQualified":false})))
}
fn recorded_attempt(session:&CompanionV1HostSession,base:&CompanionV1MeetingMinutes,trace:transport::Trace,reused:&source_checkpoint::CheckedSourcePrefix,policy:RuntimePolicy<'_>)->(Result<CompanionV1MeetingMinutes,String>,Value){
    let start=Instant::now();
    let mut release_confirmed=false;
    let outcome=(||{
        if !session.meeting_notes.is_empty(){return Err("当前本地整理不能合并补充说明，已有内容保留。".into());}
        if !assets::cpu_supported(){return Err("这台电脑暂不支持当前本地纪要引擎，可选择云端整理。".into());}
        let windows=source_windows::SourceWindows::new(&session.transcript_text)?;
        if let Ok(mut trace)=trace.lock() {
            trace["reusedSourceWindows"] = json!(reused.len());
            trace["freshWholeRun"] = json!(reused.len() == 0);
            if reused.reuses_vulkan_on_cpu() {
                trace["reusedSourceBackend"] = json!("vulkan");
            }
        }
        let _lease=assets::compute_lease()?;
        let model=assets::model_path()?;assets::verified(&model,assets::MODEL_BYTES,assets::MODEL_SHA)?;
        let accelerator = match policy {
            RuntimePolicy::Cpu=>None,
            RuntimePolicy::ExplicitVulkan(root)=>Some(assets::engineering_vulkan(root)?),
            RuntimePolicy::Application=>{
                let root=assets::runtime_root()?.join("vulkan");
                match assets::engineering_vulkan(&root) {
                    Ok(found)=>Some(found),
                    Err(reason)=>{
                        if let Ok(mut trace)=trace.lock(){
                            trace["runtimeFallback"]=json!(reason);
                        }
                        None
                    }
                }
            }
        };
        let runtime = match &accelerator {
            Some((path, _)) => path.clone(),
            None => assets::runtime()?,
        };
        if let Ok(mut trace) = trace.lock() {
            trace["backend"] = json!(if accelerator.is_some() { "vulkan" } else { "cpu" });
            trace["modelLoadMode"] = json!(if accelerator.is_some() { "none" } else { "mmap" });
            if let Some((_, device)) = &accelerator {
                trace["runtimeSha256"] = json!(assets::VULKAN_SERVER_SHA);
                trace["vulkanDevice"] = json!(device);
            }
        }
        let socket=TcpListener::bind(("127.0.0.1",0)).map_err(|_|"无法创建本地纪要连接。")?;
        let port=socket.local_addr().map_err(|_|"无法创建本地纪要连接。")?.port();drop(socket);
        let key=uuid::Uuid::new_v4().simple().to_string();let alias=format!("companion-local-{}",uuid::Uuid::new_v4().simple());
        let program=runtime.to_str().ok_or("本地纪要引擎路径无效。")?;
        let cancellation=super::super::meeting_processing_job::current();
        let run = |context, earlier: &ContextRetry| {
            let args=arguments(&model,port,&key,&alias,accelerator.as_ref().map(|(_,device)|device.as_str()),context)?;
            if let Ok(mut trace)=trace.lock() {
                trace["stage"]=json!("loading-engine");
                trace["contextTokens"]=json!(context.tokens());
                trace["contextLimit"]=Value::Null;
                trace["reusedIndependentSourceReviewBatches"]=json!(0);
                trace["reusedOrganizationRequests"]=json!(0);
            }
            super::super::external_command::with_local_service(program,&args,cancellation.as_ref().map(|c|c.flag()),accelerator.is_some(),|stop|{
            let mut facts=Vec::new();
            let mut reviewed=Vec::new();
            let mut excerpt_requests = 0;
            for index in 0..windows.len(){
                if let Ok(mut trace)=trace.lock(){trace["sourceWindow"]=json!({"current":index+1,"total":windows.len()});}
                let (encoding, saved) = reused.window(index)
                    .unwrap_or((source_windows::SourceEncoding::DirectSingleRole, None));
                let raw = if let Some(call) = saved.or_else(|| earlier.windows.get(&index)) {
                    let mut replay = call.clone();
                    replay["reused"] = json!(true);
                    let raw = replay["output"].as_str().expect("validated reusable response").to_owned();
                    if let Ok(mut trace)=trace.lock() {
                        if !trace["calls"].is_array() { trace["calls"] = json!([]); }
                        trace["calls"].as_array_mut().unwrap().push(replay);
                    }
                    raw
                } else if windows.requires_model(index, encoding) {
                    let (input,schema)=windows.contract(index, encoding);
                    let raw=transport::generate(port,&key,&alias,encoding.prompt(),input,schema,stop,&trace,context,SOURCE_OUTPUT_TOKENS)?;
                    record_call(&trace,&format!("source-window-{}",index+1));
                    raw
                } else { "{}".into() };
                let mut checked = windows.check_encoded(index, &raw, encoding)?;
                if let Some((input, schema)) = windows.excerpt_request(&checked) {
                    let reply = if excerpt_requests < 4 {
                        excerpt_requests += 1;
                        let result = transport::generate(port, &key, &alias,
                            source_windows::EXCERPT_PROMPT, input, schema, stop, &trace, context, 768);
                        let reply = match result {
                            Ok(reply) => Some(reply),
                            Err(reason) if context.retry_full(&reason) => return Err(reason),
                            Err(_) => None,
                        };
                        record_call(&trace, &format!("source-excerpt-{}", index + 1));
                        if stop.load(std::sync::atomic::Ordering::Acquire) {
                            return Err("已取消本地纪要整理，完整转写与已有纪要保留。".into());
                        }
                        reply
                    } else {
                        None
                    };
                    windows.finish_deferred(&mut checked, reply.as_deref());
                }
                facts.append(&mut checked.facts);
                reviewed.push(json!({"window":index+1,"sourceEncoding":encoding.name(),"sentences":checked.reviewed}));
                if let Ok(mut trace)=trace.lock(){trace["reviewedSourceWindows"]=json!(reviewed);}
                if facts.len()>atomic_document::MAX_FACTS{return Err(atomic_document::fail());}
            }
            let generated_review;
            let review = if let Some((review, calls)) = reused.independent_source_review(context) {
                if let Ok(mut trace) = trace.lock() {
                    trace["reusedIndependentSourceReviewBatches"] = json!(calls.len());
                    if !trace["calls"].is_array() { trace["calls"] = json!([]); }
                    trace["calls"].as_array_mut().unwrap().extend_from_slice(calls);
                }
                review
            } else {
                let archived = reused.independent_source_review_prefix(context);
                let from_retry = archived.is_empty() && !earlier.reviews.is_empty();
                let mut saved_batches = if from_retry { earlier.reviews.as_slice() } else { archived }.iter();
                let retry_profile = from_retry.then(transport::profile).transpose()?;
                let result=source_review::review(&session.transcript_text,|prompt,input,schema,stage| {
                    if let Some(call) = saved_batches.next() {
                        let compatible = if let Some(profile) = retry_profile.as_ref() {
                            matches_review_request(call, stage, prompt, &input, &schema, profile)?
                        } else {
                            if call["stage"] != stage { return Err(atomic_document::fail()); }
                            true
                        };
                        if compatible {
                            let raw = call["output"].as_str().ok_or_else(atomic_document::fail)?;
                            if let Ok(mut trace) = trace.lock() {
                                if !trace["calls"].is_array() { trace["calls"] = json!([]); }
                                let mut replay = call.clone();
                                replay["reused"] = json!(true);
                                trace["calls"].as_array_mut().unwrap().push(replay);
                                let count = trace["reusedIndependentSourceReviewBatches"].as_u64().unwrap_or(0);
                                trace["reusedIndependentSourceReviewBatches"] = json!(count + 1);
                            }
                            return Ok(raw.to_owned());
                        }
                    }
                    let result=transport::generate(port,&key,&alias,prompt,input,schema,stop,&trace,context,640)?;
                    record_call(&trace,stage);
                    Ok(result)
                });
                generated_review=match result {
                    Ok(review)=>review,
                    Err(reason) if !context.retry_full(&reason) && !stop.load(std::sync::atomic::Ordering::Acquire)=>{
                        if let Ok(mut trace)=trace.lock(){trace["independentSourceReviewFailure"]=json!(reason);}
                        source_review::Review::default()
                    },
                    Err(reason)=>return Err(reason),
                };
                &generated_review
            };
            let mut bank=atomic_document::build_session_bank(facts,session,review)?;
            if let Ok(mut trace)=trace.lock(){trace["atomicFactBank"]=bank.receipt.clone();trace["stage"]=json!("organizing-fact-ids");}
            let layout=if atomic_document::has_chapters(&bank) {
                let mut saved = reused.organization(context);
                let mut ask = |prompt, input, schema, stage: &str, tokens| {
                    if let Some((call, raw)) = saved.next(stage, prompt, &input, &schema, tokens) {
                        if let Ok(mut trace) = trace.lock() {
                            if !trace["calls"].is_array() { trace["calls"] = json!([]); }
                            trace["calls"].as_array_mut().unwrap().push(call);
                            let count = trace["reusedOrganizationRequests"].as_u64().unwrap_or(0);
                            trace["reusedOrganizationRequests"] = json!(count + 1);
                        }
                        return Ok(raw);
                    }
                    let raw = if stage == transport::COMPACT_CORE_STAGE {
                        transport::generate_compact_core(port,&key,&alias,prompt,input,schema,stop,&trace,context)?
                    } else {
                        transport::generate(port,&key,&alias,prompt,input,schema,stop,&trace,context,tokens)?
                    };
                    record_call(&trace,stage);
                    Ok(raw)
                };
                let core = ask(atomic_document::layout_prompt(&bank), atomic_document::layout_input(&bank),
                    atomic_document::layout_schema(&bank)?, transport::COMPACT_CORE_STAGE, context.layout_output())?;
                let layout = atomic_document::review_chapters(&mut bank,Some(&core),&session.transcript_text,
                    |prompt,input,schema,stage| ask(prompt,input,schema,stage,768))?;
                if let Err(reason) = atomic_document::review_reply_groups(&mut bank,&session.transcript_text,
                    |prompt,input,schema,stage| ask(prompt,input,schema,stage,128))
                {
                    if stop.load(std::sync::atomic::Ordering::Acquire) { return Err(reason); }
                    if let Ok(mut trace) = trace.lock() { trace["readerReplyGroupFailure"] = json!(reason); }
                }
                layout
            } else {
                let result=transport::generate(port,&key,&alias,atomic_document::layout_prompt(&bank),atomic_document::layout_input(&bank),atomic_document::layout_schema(&bank)?,stop,&trace,context,context.layout_output())?;
                record_call(&trace,"id-only-organization");
                result
            };
            if let Ok(mut trace)=trace.lock(){trace["atomicFactBank"]=bank.receipt.clone();}
            atomic_document::organize(&layout,&bank,session,base)
            })
        };
        let preferred = if accelerator.is_some() { transport::Context::Full } else { transport::Context::ReducedCpu };
        let parsed = match run(preferred,&ContextRetry::default()) {
            Err(reason) if preferred.retry_full(&reason) => {
                let earlier = retained_for_context_retry(&trace);
                run(transport::Context::Full,&earlier)
            }
            result => result,
        }?;
        release_confirmed=true;
        if let Ok(mut trace)=trace.lock(){trace["documentReceipt"]=parsed.receipt;trace["stage"]=json!("candidate-parsed");}
        Ok(parsed.minutes)
    })();
    let mut receipt=trace.lock().map(|t|t.clone()).unwrap_or_else(|_|json!({"traceUnavailable":true}));
    receipt["seconds"]=json!(start.elapsed().as_secs_f64());receipt["error"]=json!(outcome.as_ref().err());
    receipt["serviceReleaseConfirmed"]=json!(release_confirmed);
    receipt["ownedJobKillOnCloseEnabled"]=json!(true);
    (outcome,receipt)
}

#[derive(Default)]
struct ContextRetry {
    windows: HashMap<usize,Value>,
    reviews: Vec<Value>,
}

fn matches_review_request(
    call: &Value, stage: &str, prompt: &str, input: &Value, schema: &Value, profile: &Value,
) -> Result<bool,String> {
    let Some(alias) = call["request"]["model"].as_str() else { return Ok(false) };
    let expected = transport::request_body(alias,prompt,input.clone(),schema.clone(),640,profile)?;
    Ok(call["stage"] == stage && call["finishReason"] == "stop" && call["request"] == expected)
}

fn retained_for_context_retry(trace: &transport::Trace) -> ContextRetry {
    let Ok(mut trace) = trace.lock() else { return ContextRetry::default(); };
    let mut retained = ContextRetry::default();
    let review_usable = trace["independentSourceReviewFailure"].is_null();
    if let Value::Array(calls) = trace["calls"].take() {
        for call in calls {
            if call["finishReason"] != "stop" || call["reused"] == true { continue; }
            let Some(stage) = call["stage"].as_str() else { continue };
            let index = stage.strip_prefix("source-window-")
                .and_then(|index| index.parse::<usize>().ok()).and_then(|index| index.checked_sub(1));
            if let Some(index) = index {
                retained.windows.insert(index,call);
            } else if review_usable && stage.starts_with("independent-source-review-")
                && call["output"].as_str().is_some()
            {
                retained.reviews.push(call);
            }
        }
    }
    trace["contextFallback"]=json!({
        "initialContextTokens":transport::Context::ReducedCpu.tokens(),
        "reusedCompletedSourceWindows":retained.windows.len(),
        "reviewRepliesAvailableForVerification":retained.reviews.len(),
        "firstAttemptRequests":trace["inferenceRequestAttempts"],
        "limit":trace["contextLimit"],
        "lastFinishReason":trace["finishReason"],
    });
    retained
}

fn record_call(trace:&transport::Trace,stage:&str){
    if let Ok(mut trace)=trace.lock(){
        let mut call=json!({"stage":stage});
        for key in ["request","inputTokens","output","reasoningCharacters","usage","finishReason","generationSeconds"]{call[key]=trace[key].clone();}
        if !trace["calls"].is_array(){trace["calls"]=json!([]);}
        trace["calls"].as_array_mut().unwrap().push(call);
    }
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]
    fn local_minutes_arguments_keep_the_proven_cpu_memory_profile_and_loopback(){
        let args=arguments(std::path::Path::new("C:/fixture/model.gguf"),12345,"test-key","test-model",None,transport::Context::ReducedCpu).unwrap();
        assert!(args.windows(2).any(|p|p==["--load-mode","mmap"]));assert!(args.contains(&"--no-repack".into()));
        assert!(args.windows(2).any(|p|p==["-ngl","0"]));assert!(args.windows(2).any(|p|p==["--host","127.0.0.1"]));
        assert!(args.windows(2).any(|p|p==["--cache-ram","256"]));
        assert!(args.windows(2).any(|p|p==["-c","8192"]));
    }
    #[test]
    fn local_minutes_vulkan_streams_the_same_model_with_the_same_context(){
        let model=std::path::Path::new("C:/fixture/model.gguf");
        let args=arguments(model,12345,"test-key","test-model",Some("Vulkan0"),transport::Context::Full).unwrap();
        for pair in [["-m","C:/fixture/model.gguf"],["--load-mode","none"],["-ngl","99"],
            ["--device","Vulkan0"],["-c","16384"],["--cache-ram","256"]] {
            assert!(args.windows(2).any(|actual|actual==pair));
        }
    }

    #[test]
    fn context_retry_requires_the_original_review_prompt_scope_and_completed_reply() {
        let profile = transport::profile().unwrap();
        let stage = "independent-source-review-1";
        let prompt = "Check only this source batch";
        let input = json!({"turns":[["e0014","约定下周继续核对",true]]});
        let schema = json!({"type":"object"});
        let request = transport::request_body("original-alias",prompt,input.clone(),schema.clone(),640,&profile).unwrap();
        let mut call = json!({"stage":stage,"request":request,"finishReason":"stop","output":"{}"});
        assert!(matches_review_request(&call,stage,prompt,&input,&schema,&profile).unwrap());
        let changed = json!({"turns":[["e0014","建议下周继续核对",true]]});
        assert!(!matches_review_request(&call,stage,prompt,&changed,&schema,&profile).unwrap());
        assert!(!matches_review_request(&call,"independent-source-review-2",prompt,&input,&schema,&profile).unwrap());
        call["finishReason"] = json!("length");
        assert!(!matches_review_request(&call,stage,prompt,&input,&schema,&profile).unwrap());
    }

    #[test]
    fn the_full_context_retry_retains_finished_fresh_sources_and_review_replies() {
        let trace = new_trace();
        {
            let mut row = trace.lock().unwrap();
            row["contextLimit"] = json!({"inputTokens":7000,"outputLimit":1536,"contextTokens":8192});
            row["inferenceRequestAttempts"] = json!(4);
            row["calls"] = json!([
                {"stage":"source-window-1","finishReason":"stop","output":"{}"},
                {"stage":"source-window-2","finishReason":"length","output":"{"},
                {"stage":"source-window-3","finishReason":"stop","output":"{}","reused":true},
                {"stage":"independent-source-review-1","finishReason":"stop","output":"{}"},
            ]);
        }
        let kept=retained_for_context_retry(&trace);
        assert_eq!(kept.windows.len(),1);
        assert_eq!(kept.windows[&0]["output"],"{}");
        assert_eq!(kept.reviews.len(),1);
        assert_eq!(kept.reviews[0]["stage"],"independent-source-review-1");
        let row=trace.lock().unwrap();
        assert_eq!(row["contextFallback"]["reusedCompletedSourceWindows"],1);
        assert_eq!(row["contextFallback"]["limit"]["inputTokens"],7000);
        assert_eq!(row["inferenceRequestAttempts"],4);
        assert!(row["calls"].is_null());
    }
}
