//! Fixed loopback transport. No service URL, credentials, paid-provider client,
//! or proxy environment can redirect a local request off this machine.
use std::{io::{BufRead,BufReader,Read},sync::{Arc,Mutex,atomic::{AtomicBool,Ordering}},time::{Duration,Instant}};
use reqwest::blocking::Client;
use serde_json::{json,Value};

// Bound an entire request against the context actually allocated by the engine.
// The CPU normally starts with a smaller KV cache. The full profile stays
// available for requests whose exact token counts exceed that allocation.
pub(super) const MAX_NEW_TOKENS:usize=6144;
pub(super) const COMPACT_CORE_STAGE: &str = "compact-core-organization";

// A complete eight-chapter layout from the pinned model used 547 tokens. The
// compact request returns IDs and labels only, with no reasoning or prose.
const COMPACT_CORE_MIN_OUTPUT: usize = 1024;
pub(super) const CONTEXT_LIMIT: &str = "本场文字超出本地模型容量，未截断转写，已有内容保留。";

#[derive(Clone, Copy, PartialEq, Eq)]
pub(super) enum Context { ReducedCpu, Full }

impl Context {
    pub(super) fn tokens(self) -> usize {
        match self { Self::ReducedCpu => 8192, Self::Full => 16384 }
    }

    pub(super) fn layout_output(self) -> usize {
        match self { Self::ReducedCpu => 1536, Self::Full => 3072 }
    }

    pub(super) fn compact_core_output(self, input: usize, thinking: bool) -> usize {
        let preferred = self.layout_output();
        if self == Self::ReducedCpu && !thinking {
            self.tokens().saturating_sub(input).clamp(COMPACT_CORE_MIN_OUTPUT, preferred)
        } else {
            preferred
        }
    }

    fn fits(self, input: usize, output: usize) -> bool {
        input <= 12288 && input.saturating_add(output) <= self.tokens()
    }

    pub(super) fn retry_full(self, reason: &str) -> bool {
        self == Self::ReducedCpu && reason == CONTEXT_LIMIT
    }
}
// Keep at least2048 answer tokens inside the unchanged total-output/context cap.
// The1024-token pilot exhausted its reasoning budget on every completed stage;
// counting its answer with the official tokenizer proved a forced stop rather
// than a naturally completed deliberation. This is one controlled capacity fix.
const MAX_REASONING_TOKENS:u64=(MAX_NEW_TOKENS-2048)as u64;
const MAX_RESPONSE:u64=4*1024*1024;
const MAX_OUTPUT:usize=256*1024;
pub(super) type Trace=Arc<Mutex<Value>>;
fn error()->String{"本地纪要引擎未能完整返回结果，原文和已有纪要保留。".into()}
pub(super) fn profile()->Result<Value,String>{
    let value:Value=serde_json::from_str(include_str!("generation-profile.json")).map_err(|_|error())?;
    let enabled=value["enableThinking"].as_bool().ok_or_else(error)?;
    let budget=value["reasoningBudgetTokens"].as_u64().ok_or_else(error)?;
    if (enabled&&!(1..=MAX_REASONING_TOKENS).contains(&budget))||(!enabled&&budget!=0){return Err(error());}
    Ok(value)
}
fn check(stop:&AtomicBool)->Result<(),String>{if stop.load(Ordering::Acquire){Err("本地纪要已停止，已有内容保留。".into())}else{Ok(())}}
fn limited_json(response:reqwest::blocking::Response)->Result<Value,String>{
    if !response.status().is_success(){return Err(error());}
    let mut bytes=Vec::new();response.take(MAX_RESPONSE+1).read_to_end(&mut bytes).map_err(|_|error())?;
    if bytes.len()as u64>MAX_RESPONSE{return Err(error());}
    serde_json::from_slice(&bytes).map_err(|_|error())
}
fn post(client:&Client,address:&str,key:&str,path:&str,body:&Value,stop:&AtomicBool)->Result<Value,String>{
    check(stop)?;
    limited_json(client.post(format!("{address}{path}")).bearer_auth(key).json(body).timeout(Duration::from_secs(30)).send().map_err(|_|error())?)
}

pub(super) fn request_body(alias: &str, prompt: &str, input: Value, schema: Value, max_output_tokens: usize, profile: &Value) -> Result<Value, String> {
    if !(1..=MAX_NEW_TOKENS).contains(&max_output_tokens) {
        return Err(error());
    }
    let thinking=profile["enableThinking"].as_bool().ok_or_else(error)?;
    let kwargs=json!({"enable_thinking":thinking});
    let messages=json!([{"role":"system","content":prompt},{"role":"user","content":super::super::canonical_brief::source_first_input(&input)}]);
    let mut body=json!({"model":alias,"messages":messages,"max_tokens":max_output_tokens,
        "stream":true,"stream_options":{"include_usage":true},"chat_template_kwargs":kwargs,
        "reasoning_format":"deepseek","reasoning_budget_tokens":profile["reasoningBudgetTokens"],
        "response_format":{"type":"json_schema","schema":schema}});
    let allowed=["temperature","top_p","top_k","min_p","presence_penalty","repeat_penalty","seed"];
    for(key,value)in profile["requestParameters"].as_object().ok_or_else(error)?{
        if !allowed.contains(&key.as_str()){return Err(error());}body[key]=value.clone();
    }
    Ok(body)
}

pub(super) fn use_vulkan_schema(body: &mut Value) {
    // The pinned Vulkan server reads the OpenAI-style wrapper. The CPU wire
    // format is preserved to keep validated CPU checkpoints compatible.
    let schema = body["response_format"]["schema"].take();
    body["response_format"] = json!({"type":"json_schema","json_schema":{"schema":schema}});
}

pub(super) fn generate(port:u16,key:&str,alias:&str,prompt:&str,input:Value,schema:Value,stop:&AtomicBool,trace:&Trace,context:Context,max_output_tokens:usize)->Result<String,String>{
    generate_with_budget(port, key, alias, prompt, input, schema, stop, trace, context, max_output_tokens, false)
}

pub(super) fn generate_compact_core(
    port: u16, key: &str, alias: &str, prompt: &str, input: Value, schema: Value,
    stop: &AtomicBool, trace: &Trace, context: Context,
) -> Result<String, String> {
    generate_with_budget(port, key, alias, prompt, input, schema, stop, trace, context, context.layout_output(), true)
}

fn generate_with_budget(
    port: u16, key: &str, alias: &str, prompt: &str, input: Value, schema: Value,
    stop: &AtomicBool, trace: &Trace, context: Context, preferred_output: usize,
    compact_core: bool,
) -> Result<String, String> {
    let address=format!("http://127.0.0.1:{port}");
    let client=Client::builder().no_proxy().redirect(reqwest::redirect::Policy::none()).connect_timeout(Duration::from_secs(2))
        .timeout(Duration::from_secs(900)).build().map_err(|_|error())?;
    let started=Instant::now();let mut ready=false;
    while started.elapsed()<Duration::from_secs(180){
        check(stop)?;
        if let Ok(response)=client.get(format!("{address}/v1/models")).bearer_auth(key).timeout(Duration::from_secs(2)).send(){
            if let Ok(models)=limited_json(response){
                if models["data"].as_array().is_some_and(|rows|rows.iter().any(|r|r["id"]==alias)){ready=true;break;}
            }
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    if !ready{return Err("本地纪要引擎未就绪，已有内容保留。".into());}
    let profile=profile()?;
    let mut body = request_body(alias, prompt, input, schema, preferred_output, &profile)?;
    if trace.lock().map_err(|_| error())?["backend"] == "vulkan" {
        use_vulkan_schema(&mut body);
    }
    let rendered=post(&client,&address,key,"/apply-template",&json!({"messages":body["messages"],"chat_template_kwargs":body["chat_template_kwargs"]}),stop)?;
    let rendered=rendered["prompt"].as_str().ok_or_else(error)?;
    let tokenized=post(&client,&address,key,"/tokenize",&json!({"content":rendered,"add_special":false,"parse_special":true}),stop)?;
    let tokens=tokenized["tokens"].as_array().ok_or_else(error)?.len();
    let max_output_tokens = if compact_core {
        context.compact_core_output(tokens, profile["enableThinking"].as_bool().unwrap_or(true))
    } else {
        preferred_output
    };
    if !context.fits(tokens, max_output_tokens) {
        if let Ok(mut trace) = trace.lock() {
            trace["contextLimit"] = json!({"inputTokens":tokens,"outputLimit":max_output_tokens,"contextTokens":context.tokens()});
        }
        return Err(CONTEXT_LIMIT.into());
    }
    body["max_tokens"] = json!(max_output_tokens);
    if let Ok(mut trace)=trace.lock(){
        trace["generationProfile"]=profile;
        if max_output_tokens < preferred_output {
            trace["compactCoreBudget"] = json!({
                "inputTokens":tokens,"preferredOutput":preferred_output,
                "actualOutput":max_output_tokens,"contextTokens":context.tokens(),
            });
        }
    }
    let wire=super::evidence_document::wire(&body);
    if let Ok(mut trace)=trace.lock(){
        for key in ["output","reasoningCharacters","usage","finishReason","generationSeconds"]{trace[key]=Value::Null;}
        trace["request"]=body.clone();trace["inputTokens"]=json!(tokens);
        let count=trace["inferenceRequestAttempts"].as_u64().unwrap_or(0)+1;
        trace["inferenceRequestAttempts"]=json!(count);trace["stage"]=json!("generating");
    }
    check(stop)?;let generated=Instant::now();
    let response=client.post(format!("{address}/v1/chat/completions")).bearer_auth(key).header(reqwest::header::CONTENT_TYPE,"application/json").body(wire).send().map_err(|_|error())?;
    if !response.status().is_success(){return Err(error());}
    let mut reader=BufReader::new(response.take(MAX_RESPONSE+1));let mut line=String::new();let mut text=String::new();
    let mut received=0u64;let mut done=false;let mut finish=None;let mut usage=None;let mut last=Instant::now();let mut reasoning_characters=0usize;
    loop{
        check(stop)?;line.clear();let count=reader.read_line(&mut line).map_err(|_|error())?;
        if count==0{break;}received+=count as u64;
        if received>MAX_RESPONSE||text.len()>MAX_OUTPUT||generated.elapsed()>Duration::from_secs(900){return Err(error());}
        let Some(data)=line.strip_prefix("data:")else{continue;};let data=data.trim();
        if data=="[DONE]"{done=true;break;}
        let event:Value=serde_json::from_str(data).map_err(|_|error())?;
        if event["usage"].is_object(){usage=Some(event["usage"].clone());}
        if let Some(choices)=event["choices"].as_array(){for choice in choices{
            // Count only: internal model deliberation is never appended to the
            // document, source evidence, progress text, or diagnostic receipts.
            if let Some(part)=choice["delta"]["reasoning_content"].as_str(){reasoning_characters+=part.chars().count();}
            if let Some(part)=choice["delta"]["content"].as_str(){text.push_str(part);}
            if let Some(value)=choice["finish_reason"].as_str(){finish=Some(value.to_string());}
        }}
        if last.elapsed()>Duration::from_secs(10){
            if let Ok(mut trace)=trace.lock(){trace["output"]=json!(text);trace["reasoningCharacters"]=json!(reasoning_characters);trace["generationSeconds"]=json!(generated.elapsed().as_secs_f64());}
            last=Instant::now();
        }
    }
    if let Ok(mut trace)=trace.lock(){trace["output"]=json!(text);trace["reasoningCharacters"]=json!(reasoning_characters);trace["finishReason"]=json!(finish);trace["usage"]=json!(usage);trace["generationSeconds"]=json!(generated.elapsed().as_secs_f64());}
    if done && finish.as_deref()==Some("length")
        && context == Context::ReducedCpu && preferred_output == context.layout_output() {
        return Err(CONTEXT_LIMIT.into());
    }
    if !done||finish.as_deref()!=Some("stop")||text.trim().is_empty(){return Err("本地纪要返回不完整，未发布为完成结果。".into());}
    let usage=usage.ok_or_else(error)?;
    let measured=usage["prompt_tokens"].as_u64().ok_or_else(error)?as usize;
    if measured.abs_diff(tokens)>1{return Err("本地纪要输入核对不一致，已有内容保留。".into());}
    Ok(text)
}

#[cfg(test)]
#[test]
fn cpu_context_saves_layout_capacity_without_accepting_an_oversize_request() {
    // Longest recorded compact request once tokenized, with its old output cap.
    let cpu = Context::ReducedCpu;
    assert!(cpu.fits(6453,cpu.layout_output()));
    assert!(!cpu.fits(6453,Context::Full.layout_output()));
    assert!(Context::Full.fits(6453,Context::Full.layout_output()));
    assert!(cpu.fits(6656,cpu.layout_output()));
    assert!(!cpu.fits(6657,cpu.layout_output()));
    assert!(!Context::Full.fits(12289,1));
    assert!(cpu.retry_full(CONTEXT_LIMIT));
    assert!(!Context::Full.retry_full(CONTEXT_LIMIT));
    assert!(!cpu.retry_full("可用内存不足"));
}

#[cfg(test)]
#[test]
fn compact_core_fits_the_archived_eight_chapter_request_without_reducing_other_budgets() {
    let cpu = Context::ReducedCpu;
    assert_eq!(cpu.compact_core_output(6586, false), cpu.layout_output());
    assert_eq!(cpu.compact_core_output(6859, false), 1333);
    let output = cpu.compact_core_output(7005, false);
    assert_eq!(output, 1187);
    assert!(cpu.fits(7005, output));
    assert_eq!(cpu.compact_core_output(7168, false), COMPACT_CORE_MIN_OUTPUT);
    assert!(!cpu.fits(7169, cpu.compact_core_output(7169, false)));
    assert_eq!(cpu.compact_core_output(7005, true), cpu.layout_output());
    let full = Context::Full;
    assert_eq!(full.compact_core_output(7005, false), full.layout_output());
}
