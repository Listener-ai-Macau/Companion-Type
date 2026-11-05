use crate::{backend,companion_v1::CompanionV1HostSession};
use serde::Deserialize;
use std::path::Path;

#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Request {session_key:String,title:String,transcript:String,duration_millis:u64,endpoint:String,model:String,
    #[serde(default)] template:Option<crate::companion_v1::MinutesTemplate>,#[serde(default)] supplements:Vec<String>,
    #[serde(default)] utterances:Vec<crate::meeting_transcript::Utterance>}

pub fn generate_json(request:&str,key:&str,cache:&Path)->Result<String,String> {
    generate_json_observed(request,key,cache,|_,_|Ok(()))
}

pub fn generate_json_observed(request:&str,key:&str,cache:&Path,
    progress:impl FnMut(u64,u64)->Result<(),String>+'static)->Result<String,String> {
    if request.len()>3*1024*1024{return Err("纪要请求过大；原转写保持不变。".into());}
    let request:Request=serde_json::from_str(request).map_err(|_|"纪要请求格式不正确。")?;
    if request.session_key.trim().is_empty()||request.title.len()>1024||request.transcript.trim().is_empty()
        ||request.duration_millis==0||request.model.trim().is_empty()||key.trim().is_empty()||cache.as_os_str().is_empty()||!cache.is_absolute() {
        return Err("纪要来源、服务配置或私有缓存目录不完整；原转写保持不变。".into());
    }
    let template=request.template.as_ref().map(|t|t.normalized()).transpose()?;
    if request.supplements.iter().any(|text|text.trim().is_empty()) {
        return Err("补充内容不能为空；原转写保持不变。".into());
    }
    let document=crate::meeting_transcript::Document{text:request.transcript,utterances:request.utterances};
    document.validate(Some(request.duration_millis))?;
    let transcript=if document.utterances.is_empty(){document.text}else{crate::meeting_transcript::source_text(&document.utterances)};
    let supplements=request.supplements;
    let session=CompanionV1HostSession{id:request.session_key,title:request.title,source:"mobile".into(),
        transcript_text:transcript,duration_ms:request.duration_millis,meeting_mode:"offlineStore".into(),
        meeting_notes:supplements.iter().map(|text|crate::companion_v1::Note{text:text.clone()}).collect(),..Default::default()};
    let mut result=backend::generate_observed_template(&session,&request.endpoint,&request.model,key,cache,template.as_ref(),progress)?;
    if let Some(template)=template.as_ref() {
        if result.quality!="final" || result.llm_note.is_some() || result.processing.as_ref().is_some_and(|p|!p.is_complete()) {
            return Err(format!("按模板整理未完成：{}。原文和已有结果保留。",result.llm_note.as_deref().unwrap_or("请重试")));
        }
        result.markdown=format!("> 整理视角：{}\n\n{}",template.name,result.markdown);
    }
    let mut value=serde_json::to_value(&result).map_err(|_|"纪要结果无法读取。")?;
    if let Some(template)=template {value["template"]=serde_json::to_value(template).map_err(|_|"模板无法读取。")?;}
    // An explicit empty list distinguishes a new original-only result from a
    // legacy result whose supplement provenance was never recorded.
    value["sourceSupplements"]=serde_json::to_value(supplements).map_err(|_|"补充来源无法读取。")?;
    serde_json::to_string(&value).map_err(|_|"纪要结果无法读取；原转写保持不变。".into())
}

/// 0 = unknown legacy/malformed source, 1 = exact match, 2 = changed.
pub(crate) fn supplement_status(result_json:&str,current:&[String])->i32 {
    let Ok(value)=serde_json::from_str::<serde_json::Value>(result_json) else{return 0};
    let Some(array)=value.get("sourceSupplements").and_then(serde_json::Value::as_array) else{return 0};
    let Some(saved)=array.iter().map(|item|item.as_str()).collect::<Option<Vec<_>>>() else{return 0};
    if saved.len()==current.len() && saved.iter().zip(current).all(|(a,b)|*a==b) {1}else{2}
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json,Value};
    use std::{io::{Read,Write},net::TcpListener,sync::{Arc,Mutex,atomic::{AtomicUsize,Ordering}},thread};

    fn server(responses:Vec<(u16,Value)>)->(String,Arc<AtomicUsize>,thread::JoinHandle<()>) {
        server_with_retry_assertions(responses,false)
    }
    fn server_with_retry_assertions(responses:Vec<(u16,Value)>,check_retry:bool)->(String,Arc<AtomicUsize>,thread::JoinHandle<()>) {
        let listener=TcpListener::bind("127.0.0.1:0").unwrap();let addr=listener.local_addr().unwrap();
        let calls=Arc::new(AtomicUsize::new(0));let observed=calls.clone();
        let job=thread::spawn(move||for(status,content)in responses {
            let(mut stream,_)=listener.accept().unwrap();stream.set_read_timeout(Some(std::time::Duration::from_secs(5))).unwrap();
            let mut data=Vec::new();let mut buf=[0u8;4096];let mut body_start=None;let mut length=0usize;
            loop {let n=stream.read(&mut buf).unwrap();if n==0{break;}data.extend_from_slice(&buf[..n]);
                if body_start.is_none(){if let Some(i)=data.windows(4).position(|w|w==b"\r\n\r\n") {body_start=Some(i+4);
                    let headers=String::from_utf8_lossy(&data[..i]);length=headers.lines().find_map(|line|line.split_once(':').filter(|(k,_)|k.eq_ignore_ascii_case("content-length")).map(|(_,v)|v.trim().parse().unwrap())).unwrap();}}
                if body_start.is_some_and(|start|data.len()>=start+length){break;}}
            let body=&data[body_start.unwrap()..];assert!(String::from_utf8_lossy(body).contains("synthetic"));
            let call=observed.fetch_add(1,Ordering::SeqCst);
            if check_retry && call<3 {
                let request:Value=serde_json::from_slice(body).unwrap();
                let instruction=request["messages"][0]["content"].as_str().unwrap();
                let input=request["messages"][1]["content"].as_str().unwrap();
                assert_eq!(instruction.contains("你是原文引用助手"),call==1);
                if call==1 {
                    let retry:Value=serde_json::from_str(input).unwrap();
                    assert_eq!(retry["items"]["summary"][0],"follow up report");
                    assert!(retry["transcript"].as_str().unwrap().contains("follow up report"));
                }
            }
            let body=if status==200 {json!({"choices":[{"finish_reason":"stop","message":{"content":content.to_string()}}]}).to_string()}else{"{}".into()};
            write!(stream,"HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",body.len(),body).unwrap();
        });
        (format!("http://{addr}/chat/completions"),calls,job)
    }
    fn request(endpoint:&str,transcript:&str)->String {json!({"sessionKey":"synthetic-session","title":"Synthetic","transcript":transcript,"durationMillis":10000,"endpoint":endpoint,"model":"synthetic-model"}).to_string()}
    fn cache()->std::path::PathBuf {std::env::temp_dir().join(format!("companion-mobile-minutes-test-{}",uuid::Uuid::new_v4()))}
    fn content()->Value {json!({"summary":["明天检查样品"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"检查样品","questionClassification":[{"sourceId":1,"kind":"statement"}]})}

    #[test]
    fn long_meeting_includes_selected_supplement_and_reconciles_current_actions() {
        let chapter=json!({"summary":["小王周五发报价"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"分段",
            "evidence":[{"field":"summary","index":0,"quote":"小王周五发报价"}]});
        let combined=json!({"summary":["报价已取消"],"decisions":["取消发报价"],"actionItems":[],"questions":[],"keywords":[],"markdown":"综合"});
        let(url,calls,job)=server(vec![(200,chapter),(200,combined)]);let root=cache();
        let mut req:Value=serde_json::from_str(&request(&url,"小王周五发报价。" )).unwrap();
        req["durationMillis"]=json!(7_200_000);req["supplements"]=json!(["取消发报价"]);
        let result:Value=serde_json::from_str(&generate_json(&req.to_string(),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        assert_eq!(result["sourceSupplements"],json!(["取消发报价"]));assert_eq!(result["actionItems"],json!([]));
        assert!(result["markdown"].as_str().unwrap().contains("用户补充"));assert_eq!(calls.load(Ordering::SeqCst),2);
        job.join().unwrap();
    }

    #[test]
    fn saved_supplement_status_distinguishes_changed_and_legacy_results() {
        let saved=json!({"sourceSupplements":["第一条\n补充","\"引号\"与🌿"]}).to_string();
        assert_eq!(supplement_status(&saved,&["第一条\n补充".into(),"\"引号\"与🌿".into()]),1);
        assert_eq!(supplement_status(&saved,&["第一条\n补充".into(),"已更改".into()]),2);
        assert_eq!(supplement_status(&json!({"sourceSupplements":[]}).to_string(),&[]),1);
        assert_eq!(supplement_status("{\"summary\":[]}",&[]),0);
        assert_eq!(supplement_status("{\"sourceSupplements\":[1]}",&[]),0);
        assert_eq!(supplement_status("not json",&[]),0);
    }

    #[test]
    fn long_context_merge_failure_keeps_chapters_for_retry() {
        let chapter=json!({"summary":["小王周五发报价"],"decisions":[],"actionItems":[{"text":"发报价","owner":"小王","due":"周五"}],"questions":[],"keywords":[],"markdown":"分段",
            "evidence":[{"field":"summary","index":0,"quote":"小王周五发报价"},{"field":"actionItems","index":0,"quote":"小王周五发报价"}]});
        let combined=json!({"summary":["报价已取消"],"decisions":["取消发报价"],"actionItems":[],"questions":[],"keywords":[],"markdown":"综合"});
        let(url,calls,job)=server(vec![(200,chapter),(503,json!({})),(200,combined)]);let root=cache();
        let mut req:Value=serde_json::from_str(&request(&url,"小王周五发报价。" )).unwrap();
        req["durationMillis"]=json!(7_200_000);req["supplements"]=json!(["取消发报价"]);
        let first:Value=serde_json::from_str(&generate_json(&req.to_string(),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(first["quality"],"draft");assert!(first["llmNote"].as_str().unwrap().contains("尚未综合"));assert_eq!(first["actionItems"],json!([]));
        let second:Value=serde_json::from_str(&generate_json(&req.to_string(),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(second["quality"],"final");assert_eq!(second["processing"]["resumedChunks"],1);
        assert_eq!(second["actionItems"],json!([]));assert_eq!(calls.load(Ordering::SeqCst),3);job.join().unwrap();
    }

    #[test]
    fn long_context_keeps_unverified_chapter_content_as_reference() {
        let chapter=json!({"summary":["小王周五发报价","未核对的样品讨论"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"分段",
            "evidence":[{"field":"summary","index":0,"quote":"小王周五发报价"}]});
        let evidence=json!({"evidence":[{"field":"summary","index":0,"quote":"小王周五发报价"}]});
        let combined=json!({"summary":["报价已取消"],"decisions":["取消发报价"],"actionItems":[],"questions":[],"keywords":[],"markdown":"综合"});
        let(url,_,job)=server(vec![(200,chapter),(200,evidence),(200,combined)]);let root=cache();
        let mut req:Value=serde_json::from_str(&request(&url,"小王周五发报价。" )).unwrap();
        req["durationMillis"]=json!(7_200_000);req["supplements"]=json!(["取消发报价"]);
        let result:Value=serde_json::from_str(&generate_json(&req.to_string(),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");let markdown=result["markdown"].as_str().unwrap();
        assert!(markdown.contains("未核对的参考草稿"));assert!(markdown.contains("未核对的样品讨论"));
        assert!(markdown.contains("分段录音文字与用户补充依据"));job.join().unwrap();
    }

    // Explicitly run against the already-authorized public VCSum recording's
    // local transcription. The added correction is fictional, not user audio.
    #[test]
    #[ignore]
    fn public_two_hour_context_real_service() {
        let source=std::env::var("COMPANION_PUBLIC_TRANSCRIPT_JSON").unwrap();
        let out=std::path::PathBuf::from(std::env::var("COMPANION_PUBLIC_CONTEXT_OUT").unwrap());
        std::fs::create_dir_all(&out).unwrap();
        let rows:Value=serde_json::from_slice(&std::fs::read(source).unwrap()).unwrap();
        let transcript=rows[0]["transcriptText"].as_str().unwrap();
        let key=std::env::var("DEEPSEEK_API_KEY").unwrap();
        let base=std::env::var("DEEPSEEK_BASE_URL").unwrap_or_else(|_|"https://api.deepseek.com/v1".into());
        let model=std::env::var("DEEPSEEK_MODEL").unwrap_or_else(|_|"deepseek-v4-flash".into());
        let note="虚构测试补充：小王原计划周五发送测试报价，现在已经取消该任务。";
        let request=json!({"sessionKey":"public-context-evaluation","title":"公开衍生品圆桌与虚构补充",
            "transcript":transcript,"durationMillis":7_817_648u64,"endpoint":format!("{}/chat/completions",base.trim_end_matches('/')),
            "model":model,"supplements":[note]});
        let result=generate_json(&request.to_string(),&key,&out).unwrap();
        std::fs::write(out.join("result.json"),&result).unwrap();
        let value:Value=serde_json::from_str(&result).unwrap();
        assert_eq!(value["quality"],"final","{}",value["llmNote"]);
        assert_eq!(value["processing"]["complete"],true);
        assert_eq!(value["sourceSupplements"],json!([note]));
        assert!(!value["actionItems"].as_array().unwrap().iter().any(|v|v["text"].as_str().unwrap_or("").contains("发送测试报价")));
        let combined=format!("{} {}",value["summary"],value["decisions"]);
        assert!(combined.contains("报价") && combined.contains("取消"),"补充没有进入当前纪要，请查本机结果");
    }

    #[test]
    fn verbose_short_minutes_show_overview_without_losing_details_or_extra_requests() {
        for valid in [true,false] {
            let mut result=content();
            result["summary"]=json!((0..10).map(|i|format!("产品包装讨论重点{i}")).collect::<Vec<_>>());
            result["overview"]=if valid {json!([
                {"text":"讨论产品包装方案。","sources":[0,1]},
                {"text":"比较包装细节。","sources":[3,4]},
                {"text":"明确后续方向。","sources":[8,9]}])
            } else {json!([{"text":"不应显示的概览。","sources":[99]}])};
            let (url,calls,job)=server(vec![(200,result)]);let root=cache();
            let mut req:Value=serde_json::from_str(&request(&url,"明天检查样品。")).unwrap();req["durationMillis"]=json!(420_000);
            let output:Value=serde_json::from_str(&generate_json(&req.to_string(),"synthetic-key",&root).unwrap()).unwrap();
            assert_eq!(output["quality"],"final");
            assert_eq!(output["summary"].as_array().unwrap().len(),10);
            let markdown=output["markdown"].as_str().unwrap();
            assert!(markdown.contains("产品包装讨论重点9"));
            assert_eq!(markdown.contains("## 会议概览"),valid);
            assert!(!markdown.contains("不应显示的概览"));
            assert_eq!(calls.load(Ordering::SeqCst),1);job.join().unwrap();
        }
    }

    #[test]
    fn ordinary_minutes_keep_useful_content_when_question_classification_is_missing() {
        let mut result=content();result.as_object_mut().unwrap().remove("questionClassification");
        result["questions"]=json!(["模型推测的问题？"]);
        let (url,calls,job)=server(vec![(200,result)]);let root=cache();
        let req=request(&url,"明天检查样品吗？不确定交付日期。");
        let output:Value=serde_json::from_str(&generate_json(&req,"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(output["quality"],"final");
        assert!(output["summary"].to_string().contains("明天检查样品"));
        let questions=output["questions"].as_array().unwrap();
        assert!(questions.iter().any(|q|q.as_str().unwrap().contains("明天检查样品吗？")));
        assert!(questions.iter().any(|q|q.as_str().unwrap().contains("仅按问号摘录")));
        assert!(!questions.iter().any(|q|q.as_str().unwrap().contains("模型推测的问题")));
        assert_eq!(calls.load(Ordering::SeqCst),1);job.join().unwrap();
    }

    #[test]
    fn template_keeps_useful_minutes_when_question_classification_is_missing() {
        let mut result=content();result.as_object_mut().unwrap().remove("questionClassification");
        let (url,calls,job)=server(vec![(200,result)]);let root=cache();
        let mut req:Value=serde_json::from_str(&request(&url,"明天检查样品吗？不确定交付日期。")).unwrap();
        req["template"]=json!({"id":"interview"});
        let output:Value=serde_json::from_str(&generate_json(&req.to_string(),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(output["quality"],"final");assert_eq!(output["template"]["id"],"interview");
        let questions=output["questions"].as_array().unwrap();assert!(questions.iter().any(|q|q.as_str().unwrap().contains("明天检查样品吗？")));
        assert!(questions.iter().any(|q|q.as_str().unwrap().contains("仅按问号摘录")));
        assert!(!questions.iter().any(|q|q.as_str().unwrap().contains("不确定交付日期")));
        assert_eq!(calls.load(Ordering::SeqCst),1);job.join().unwrap();
    }

    #[test]
    fn selected_template_reaches_service_and_is_returned_with_result() {
        let listener=TcpListener::bind("127.0.0.1:0").unwrap();let address=listener.local_addr().unwrap();
        let (tx,rx)=std::sync::mpsc::channel();
        let worker=thread::spawn(move||{
            let(mut stream,_)=listener.accept().unwrap();stream.set_read_timeout(Some(std::time::Duration::from_secs(5))).unwrap();
            let mut data=Vec::new();let mut buf=[0u8;4096];let mut start=None;let mut length=0;
            loop {let n=stream.read(&mut buf).unwrap();if n==0{break;}data.extend_from_slice(&buf[..n]);
                if start.is_none(){if let Some(i)=data.windows(4).position(|w|w==b"\r\n\r\n") {start=Some(i+4);
                    let headers=String::from_utf8_lossy(&data[..i]);length=headers.lines().find_map(|line|line.split_once(':').filter(|(k,_)|k.eq_ignore_ascii_case("content-length")).map(|(_,v)|v.trim().parse::<usize>().unwrap())).unwrap();}}
                if start.is_some_and(|i|data.len()>=i+length){break;}}
            let request:Value=serde_json::from_slice(&data[start.unwrap()..]).unwrap();tx.send(request).unwrap();
            let body=json!({"choices":[{"finish_reason":"stop","message":{"content":content().to_string()}}]}).to_string();
            write!(stream,"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",body.len(),body).unwrap();
        });
        let root=cache();let mut req:Value=serde_json::from_str(&request(&format!("http://{address}/chat/completions"),"明天检查样品。")).unwrap();
        req["template"]=json!({"id":"custom","name":"项目复盘","instructions":"突出原因与风险"});
        let output:Value=serde_json::from_str(&generate_json(&req.to_string(),"synthetic-key",&root).unwrap()).unwrap();
        let sent=rx.recv_timeout(std::time::Duration::from_secs(5)).unwrap();
        assert!(sent["messages"][0]["content"].as_str().unwrap().contains("突出原因与风险"));
        assert!(sent["messages"][1]["content"].as_str().unwrap().contains("明天检查样品"));
        assert_eq!(output["template"]["name"],"项目复盘");assert!(output["markdown"].as_str().unwrap().contains("整理视角：项目复盘"));
        worker.join().unwrap();
    }

    #[test]
    fn stop_long_minutes_after_saved_chapter_then_resume_remaining_only() {
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let (url,calls,job)=server(vec![(200,chapter.clone()),(200,chapter.clone()),(200,chapter.clone()),(200,chapter)]);
        let root=cache();let transcript="follow up report. ".repeat(3200);let request=request(&url,&transcript);
        let observed=Arc::new(AtomicUsize::new(0));let seen=observed.clone();
        let result=generate_json_observed(&request,"synthetic-key",&root,move |done,total|{
            assert_eq!(total,57_600);seen.store(done as usize,Ordering::SeqCst);
            if done>0 {Err(backend::mobile_minutes_progress::CANCELLED.into())} else {Ok(())}
        });
        assert_eq!(result.unwrap_err(),backend::mobile_minutes_progress::CANCELLED);
        assert!(observed.load(Ordering::SeqCst)>0);assert_eq!(calls.load(Ordering::SeqCst),1);
        let resumed:Value=serde_json::from_str(&generate_json(&request,"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(resumed["quality"],"final");assert_eq!(resumed["processing"]["resumedChunks"],1);
        assert_eq!(calls.load(Ordering::SeqCst),4);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();assert_eq!(resolved.parent(),Some(std::env::temp_dir().canonicalize().unwrap().as_path()));
        std::fs::remove_dir_all(resolved).unwrap();
    }
    #[test]
    fn stop_before_invalid_response_retry_sends_no_second_request() {
        let missing=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report"});
        let (url,calls,job)=server(vec![(200,missing)]);let root=cache();
        let transcript="follow up report. ".repeat(3200);let observations=Arc::new(AtomicUsize::new(0));let count=observations.clone();
        let result=generate_json_observed(&request(&url,&transcript),"synthetic-key",&root,move |_,_|{
            if count.fetch_add(1,Ordering::SeqCst)>=3 {Err(backend::mobile_minutes_progress::CANCELLED.into())}else{Ok(())}
        });
        assert_eq!(result.unwrap_err(),backend::mobile_minutes_progress::CANCELLED);assert_eq!(calls.load(Ordering::SeqCst),1);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();assert_eq!(resolved.parent(),Some(std::env::temp_dir().canonicalize().unwrap().as_path()));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn similar_tasks_keep_their_own_owner_and_date() {
        let response=json!({"summary":["小王负责周五之前把红色样品寄给客户。", "小李负责周四之前把蓝色样品寄给客户。"],
            "decisions":[],"actionItems":[{"text":"把红色样品寄给客户","owner":"小王","due":"周五之前"},
                {"text":"把蓝色样品寄给客户","owner":"小李","due":"周四之前"}],
            "questions":[],"keywords":[],"markdown":"样品安排",
            "questionClassification":[{"sourceId":1,"kind":"statement"},{"sourceId":2,"kind":"statement"}]});
        let (url,_,job)=server(vec![(200,response)]);let root=cache();
        let input="小王负责周五之前把红色样品寄给客户。小李负责周四之前把蓝色样品寄给客户。";
        let value:Value=serde_json::from_str(&generate_json(&request(&url,input),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(value["quality"],"final");
        let actions=value["actionItems"].as_array().unwrap();
        assert!(actions.iter().any(|a|a["text"].as_str().unwrap_or("").contains("红色") && a["owner"]=="小王" && a["due"]=="周五之前"), "actions={actions:?}");
        assert!(actions.iter().any(|a|a["text"].as_str().unwrap_or("").contains("蓝色") && a["owner"]=="小李" && a["due"]=="周四之前"), "actions={actions:?}");
        job.join().unwrap();
        if root.exists() {
            let resolved=root.canonicalize().unwrap();
            assert_eq!(resolved.parent(),Some(std::env::temp_dir().canonicalize().unwrap().as_path()));
            std::fs::remove_dir_all(resolved).unwrap();
        }
    }

    #[test]
    fn short_ai_result_exposes_only_verbatim_optional_source_quotes() {
        let mut response=content();response["evidence"]=json!([
            {"field":"summary","index":0,"quote":"明天检查样品。"},
            {"field":"summary","index":0,"quote":"明天付款。"}
        ]);
        let (url,calls,job)=server(vec![(200,response)]);let root=cache();
        let value:Value=serde_json::from_str(&generate_json(&request(&url,"明天检查样品。"),"synthetic-key",&root).unwrap()).unwrap();
        let markdown=value["markdown"].as_str().unwrap();assert_eq!(value["quality"],"final");
        assert!(markdown.contains("## 原话核对")&&markdown.contains("原话：“明天检查样品。”"));
        assert!(!markdown.contains("明天付款"));assert_eq!(calls.load(Ordering::SeqCst),1);job.join().unwrap();
    }

    #[test]
    fn short_meeting_uses_desktop_rules_and_failure_remains_draft() {
        let (url,calls,job)=server(vec![(200,content()),(401,json!({}))]);let root=cache();
        let request=request(&url,"明天检查样品。");
        let value:Value=serde_json::from_str(&generate_json(&request,"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(value["source"],"llm_deepseek");assert_eq!(value["quality"],"final");
        assert_eq!(value["actionItems"][0]["text"],"明天检查样品");
        let retry:Value=serde_json::from_str(&generate_json(&request,"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(retry["quality"],"draft");assert_eq!(retry["source"],"rules_l0");assert!(retry["llmNote"].as_str().unwrap().contains("401"));
        assert_eq!(calls.load(Ordering::SeqCst),2);job.join().unwrap();
    }

    #[test]
    fn paraphrased_short_summary_keeps_original_only_as_reviewable_excerpt() {
        let response=json!({"summary":["发言者希望解决问题并引入学员。"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"发言者希望解决问题并引入学员。","questionClassification":[{"sourceId":1,"kind":"statement"}]});
        let (url,_,job)=server(vec![(200,response)]);let root=cache();
        let input="以往的或者以后的我尽量把这个问题给你们解决了呃呃解决问题基础以上咱要把今年的招生学员引系到咱学校微咱学校啊这个微咱这个这个教育机构啊";
        let value:Value=serde_json::from_str(&generate_json(&request(&url,input),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(value["quality"],"final");assert_eq!(value["summary"].as_array().unwrap().len(),1);
        assert!(!value["summary"][0].as_str().unwrap().contains("呃呃"));
        let markdown=value["markdown"].as_str().unwrap();assert!(markdown.contains("## 补充原文（供核对）"));assert!(markdown.contains(input));
        job.join().unwrap();
    }

    #[test]
    fn long_meeting_keeps_exact_source_quote_longer_than_1024_bytes() {
        let quote="follow up report. ".repeat(90);assert!(quote.len()>1024);
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report",
            "evidence":[{"field":"summary","index":0,"quote":quote}]});
        let (url,calls,job)=server(vec![(200,chapter.clone()),(200,chapter.clone()),(200,chapter.clone()),(200,chapter)]);
        let root=cache();let transcript="follow up report. ".repeat(3200);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        assert!(result["summary"].as_array().unwrap().iter().any(|v|v=="follow up report"));
        assert!(!result["markdown"].as_str().unwrap().contains("无法对应原文"));
        assert_eq!(calls.load(Ordering::SeqCst),4);job.join().unwrap();
        if root.exists() {std::fs::remove_dir_all(root).unwrap();}
    }
    #[test]
    fn long_meeting_keeps_completed_chunks_and_resumes_after_failure() {
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let (url,calls,job)=server(vec![(200,chapter.clone()),(500,json!({})),(200,chapter.clone()),(200,chapter.clone()),(200,chapter)]);
        let root=cache();let transcript="follow up report. ".repeat(3200);let request=request(&url,&transcript);
        let first:Value=serde_json::from_str(&generate_json(&request,"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(first["quality"],"draft");assert_eq!(first["processing"]["complete"],false);
        assert_eq!(first["processing"]["completedChunks"],1);
        let second:Value=serde_json::from_str(&generate_json(&request,"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(second["quality"],"final");assert_eq!(second["processing"]["complete"],true);
        assert_eq!(second["processing"]["resumedChunks"],1);assert_eq!(second["processing"]["sourceBytes"],transcript.len());
        assert_eq!(calls.load(Ordering::SeqCst),5);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn long_meeting_keeps_conditional_followup_without_extra_chunk_requests() {
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let mut responses=vec![(200,chapter);4];
        responses.push((200,json!({"possiblyUnrelated":[],"duplicateGroups":[]})));
        let (url,calls,job)=server(responses);let root=cache();
        let transcript=format!("{}\n如果客户提出修改，小陈下周一再确认交货日期。\n如果客户更改要求，王芳负责下周一确认产品交货时间。\n如果报价通过，下周一负责整理方案。\n旧安排已经取消，小吴不需要寄纸质文件。", "follow up report. ".repeat(3200));
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        let actions=result["actionItems"].as_array().unwrap();
        let conditional=actions.iter().find(|a|a["text"].as_str().is_some_and(|s|s.contains("如果客户提出修改"))).unwrap();
        assert!(conditional["text"].as_str().unwrap().contains("确认交货日期"));assert!(conditional["due"].is_null());
        let named=actions.iter().find(|a|a["text"].as_str().is_some_and(|s|s.contains("如果客户更改要求"))).unwrap();
        assert_eq!(named["owner"],"王芳");assert!(named["text"].as_str().unwrap().contains("交货时间"));assert!(named["due"].is_null());
        let timing=actions.iter().find(|a|a["text"].as_str().is_some_and(|s|s.contains("如果报价通过"))).unwrap();
        assert!(timing["owner"].is_null());assert!(timing["due"].is_null());
        assert!(!actions.iter().any(|a|a["text"].as_str().is_some_and(|s|s.contains("小吴"))));
        assert_eq!(calls.load(Ordering::SeqCst),5,"four chapters plus existing background review, no extra action requests");job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn missing_evidence_is_retried_without_user_restart() {
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let mut missing=chapter.clone();missing.as_object_mut().unwrap().remove("evidence");
        let evidence=json!({"evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let (url,calls,job)=server_with_retry_assertions(vec![(200,missing),(200,evidence),(200,chapter.clone()),(200,chapter.clone()),(200,chapter)],true);
        let root=cache();let transcript="follow up report. ".repeat(3200);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        assert_eq!(result["processing"]["sourceBytes"],transcript.len());assert_eq!(calls.load(Ordering::SeqCst),5);
        job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }
    #[test]
    fn partial_evidence_retry_recovers_missing_item_and_keeps_first_quote() {
        let partial=json!({"summary":["follow up report","check blue sample"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"meeting",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let recovered=json!({"evidence":[{"field":"summary","index":1,"quote":"check blue sample"}]});
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"meeting",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let (url,calls,job)=server(vec![(200,partial),(200,recovered),(200,chapter.clone()),(200,chapter.clone()),(200,chapter)]);
        let root=cache();let transcript="follow up report and check blue sample. ".repeat(1500);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        assert!(result["summary"].as_array().unwrap().iter().any(|v|v=="follow up report"));
        assert!(result["summary"].as_array().unwrap().iter().any(|v|v=="check blue sample"));
        assert!(!result["markdown"].as_str().unwrap().contains("已略过"));assert_eq!(calls.load(Ordering::SeqCst),5);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();assert_eq!(resolved.parent(),Some(std::env::temp_dir().canonicalize().unwrap().as_path()));std::fs::remove_dir_all(resolved).unwrap();
    }
    #[test]
    fn partial_evidence_retry_failure_keeps_grounded_items_and_continues() {
        let partial=json!({"summary":["follow up report","check blue sample"],"decisions":[],"actionItems":[{"text":"send quote","owner":"Alex","due":"Friday"}],"questions":[],"keywords":[],"markdown":"meeting",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"meeting",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        // The regenerated chapter omits the previously saved first item.
        let repaired=json!({"summary":["check blue sample"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"meeting",
            "evidence":[{"field":"summary","index":0,"quote":"check blue sample"}]});
        let (url,calls,job)=server(vec![(200,partial),(500,json!({})),(200,chapter.clone()),(200,chapter.clone()),(200,chapter),(503,json!({})),(503,json!({})),(200,repaired),(503,json!({}))]);
        let root=cache();let transcript="follow up report and check blue sample. ".repeat(1500);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        assert!(result["summary"].as_array().unwrap().iter().any(|v|v=="follow up report"));
        assert!(!result["summary"].as_array().unwrap().iter().any(|v|v=="check blue sample"));
        let markdown=result["markdown"].as_str().unwrap();
        assert!(markdown.contains("有2条内容无法对应原文"));
        let draft=markdown.split("## 未核对的参考草稿").nth(1).expect("omitted item is visible");
        assert!(draft.contains("check blue sample"));
        assert!(draft.contains("send quote"));
        assert!(result["actionItems"].as_array().unwrap().is_empty());
        assert!(!draft.split("## 分段原文依据").next().unwrap().contains("讨论：follow up report"));
        assert_eq!(calls.load(Ordering::SeqCst),6);
        let failed:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(failed["quality"],"draft");assert!(failed["summary"].as_array().unwrap().iter().any(|v|v=="follow up report"));
        assert!(failed["markdown"].as_str().unwrap().contains("本次补充未完成"));assert_eq!(calls.load(Ordering::SeqCst),7);
        assert!(failed["markdown"].as_str().unwrap().contains("check blue sample"),"retry must retain previous unverified reference");
        let resumed:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(resumed["quality"],"final");assert_eq!(resumed["processing"]["resumedChunks"],3);
        assert!(resumed["summary"].as_array().unwrap().iter().any(|v|v=="check blue sample"));
        assert!(resumed["summary"].as_array().unwrap().iter().any(|v|v=="follow up report"));
        assert!(resumed["markdown"].as_str().unwrap().contains("send quote"),"unresolved earlier action remains visible");
        assert!(!resumed["markdown"].as_str().unwrap().contains("讨论：check blue sample"),"newly verified item is not duplicated as draft");
        assert!(!resumed["markdown"].as_str().unwrap().contains("已略过"));assert_eq!(calls.load(Ordering::SeqCst),9);job.join().unwrap();
        let checkpoint:Value=std::fs::read_dir(root.join("minutes-work")).unwrap().map(|e|e.unwrap().path())
            .filter(|p|p.extension().is_some_and(|e|e=="json"))
            .filter_map(|p|serde_json::from_slice::<Value>(&std::fs::read(p).ok()?).ok())
            .find(|v|v["chapters"][0]["minutes"]["actionItems"].as_array().is_some_and(|a|a.is_empty())).unwrap();
        let first=checkpoint["chapters"][0]["minutes"]["summary"].as_array().unwrap();
        assert!(first.iter().any(|v|v=="follow up report")&&first.iter().any(|v|v=="check blue sample"));
        assert!(checkpoint["chapters"][0]["evidence"].as_array().unwrap().iter().any(|e|e["quote"]=="follow up report"));
        let resolved=root.canonicalize().unwrap();assert_eq!(resolved.parent(),Some(std::env::temp_dir().canonicalize().unwrap().as_path()));std::fs::remove_dir_all(resolved).unwrap();
    }
    #[test]
    fn missing_chapter_is_revisited_after_later_chapters_with_monotonic_progress() {
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let mut missing=chapter.clone();missing.as_object_mut().unwrap().remove("evidence");
        let (url,calls,job)=server(vec![(200,chapter.clone()),(200,chapter.clone()),(200,missing.clone()),(200,missing),(200,chapter.clone()),(200,chapter)]);
        let root=cache();let transcript="follow up report. ".repeat(3200);
        let progress=Arc::new(Mutex::new(Vec::new()));let observed=progress.clone();
        let result:Value=serde_json::from_str(&generate_json_observed(&request(&url,&transcript),"synthetic-key",&root,move |done,total| {
            observed.lock().unwrap().push((done,total));Ok(())
        }).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        assert_eq!(result["processing"]["sourceBytes"],transcript.len());assert_eq!(calls.load(Ordering::SeqCst),6);
        let seen=progress.lock().unwrap();assert!(seen.windows(2).all(|w|w[0].0<=w[1].0));
        assert_eq!(seen.last().unwrap().0,transcript.len() as u64);drop(seen);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }
    #[test]
    fn unsupported_quotes_retry_then_finish_later_chunks_before_revisiting() {
        let chapter=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report",
            "evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let mut invalid=chapter.clone();invalid["evidence"][0]["quote"]=json!("quote not in this recording");
        let (url,calls,job)=server(vec![(200,chapter.clone()),(200,chapter.clone()),(200,invalid.clone()),(200,invalid),(200,chapter.clone()),(200,chapter)]);
        let root=cache();let transcript="follow up report. ".repeat(3200);
        let progress=Arc::new(Mutex::new(Vec::new()));let observed=progress.clone();
        let result:Value=serde_json::from_str(&generate_json_observed(&request(&url,&transcript),"synthetic-key",&root,move |done,total| {
            observed.lock().unwrap().push((done,total));Ok(())
        }).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        assert_eq!(result["processing"]["sourceBytes"],transcript.len());assert_eq!(calls.load(Ordering::SeqCst),6);
        let seen=progress.lock().unwrap();assert!(seen.windows(2).all(|w|w[0].0<=w[1].0));
        assert_eq!(seen.last().unwrap().0,transcript.len() as u64);drop(seen);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn extra_evidence_keeps_a_fully_supported_assignment_in_long_minutes() {
        let chapter=json!({"summary":["报价已经确定"],"decisions":[],
            "actionItems":[{"text":"整理并发送报价","owner":"小王","due":"周五"}],"questions":[],"keywords":[],"markdown":"整理并发送报价",
            "evidence":[{"field":"summary","index":0,"quote":"报价已经确定。"},
                {"field":"actionItems","index":0,"quote":"小王负责整理报价，周五前发送。"},
                {"field":"actionItems","index":0,"quote":"报价已经确定。"}]});
        let (url,calls,job)=server(vec![(200,chapter.clone()),(200,chapter.clone()),(200,chapter.clone()),(200,chapter)]);
        let root=cache();let transcript="小王负责整理报价，周五前发送。报价已经确定。\n".repeat(900);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        assert!(result["actionItems"].as_array().unwrap().iter().any(|a|a["owner"]=="小王"&&a["due"]=="周五"));
        assert_eq!(calls.load(Ordering::SeqCst),4);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }
    #[test]
    fn long_meeting_flags_background_and_consolidates_cited_duplicate_actions() {
        let chapter=json!({"summary":["会议讨论产品报价，旁边有家务闲聊。"],"decisions":[],
            "actionItems":[{"text":"整理报价","owner":"小王","due":"周五"},
                {"text":"买猫粮","owner":null,"due":"周六"},
                {"text":"按时整理报价","owner":"小王","due":"周五"}],
            "questions":[],"keywords":[],"markdown":"报价会议",
            "evidence":[{"field":"summary","index":0,"quote":"会议讨论产品报价。旁边有家务闲聊。"},
                {"field":"actionItems","index":0,"quote":"小王周五整理报价"},
                {"field":"actionItems","index":1,"quote":"旁边的家人说周六买猫粮"},
                {"field":"actionItems","index":2,"quote":"小王周五整理报价"}]});
        let mut replies=vec![(200,chapter);7];
        replies.push((200,json!({"possiblyUnrelated":[1],"duplicateGroups":[[0,2]]})));
        let (url,calls,job)=server(replies); let root=cache();
        let transcript="会议讨论产品报价。旁边有家务闲聊。小王周五整理报价。旁边的家人说周六买猫粮。\n".repeat(900);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        let actions=result["actionItems"].as_array().unwrap();assert_eq!(actions.len(),2);
        assert_eq!(actions[0]["owner"],"小王");assert_eq!(actions[0]["due"],"周五");
        assert!(actions[1]["text"].as_str().unwrap().starts_with("可能来自背景对话，请核对："));
        assert!(result["markdown"].as_str().unwrap().contains("旁边的家人说周六买猫粮"));
        assert_eq!(calls.load(Ordering::SeqCst),8);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn mixed_background_summary_keeps_normal_content_visible() {
        let quote="旁边说先更新软件并确保安装都是最新版本";
        let first=json!({"summary":["会议讨论产品报价，也提到确保安装都是最新版本。"],"decisions":[],
            "actionItems":[{"text":"更新软件","owner":null,"due":null}],"questions":[],"keywords":[],"markdown":"会议",
            "evidence":[{"field":"summary","index":0,"quote":"会议讨论产品报价"},
                {"field":"summary","index":0,"quote":quote},{"field":"actionItems","index":0,"quote":quote}]});
        let rest=json!({"summary":["会议讨论产品报价"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"会议",
            "evidence":[{"field":"summary","index":0,"quote":"会议讨论产品报价"}]});
        let mut replies=vec![(200,first),(200,rest)];
        replies.push((200,json!({"possiblyUnrelated":["a0"],"duplicateGroups":[],"backgroundSummary":["s0"]})));
        let (url,calls,job)=server(replies);let root=cache();
        let transcript=format!("会议讨论产品报价。{quote}。\n{}","会议讨论产品报价。\n".repeat(900));
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"final");assert_eq!(result["processing"]["complete"],true);
        let markdown=result["markdown"].as_str().unwrap();
        assert!(markdown.contains("部分内容可能来自背景对话，请核对"));
        assert!(markdown.contains("会议讨论产品报价，也提到确保安装都是最新版本。"));
        assert_eq!(calls.load(Ordering::SeqCst),3);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn long_meeting_concise_overview_accepts_many_valid_sources() {
        let summary=(0..16).map(|i|format!("正常议题{i}")).collect::<Vec<_>>();
        let evidence=(0..16).map(|i|json!({"field":"summary","index":i,"quote":"会议讨论产品报价"})).collect::<Vec<_>>();
        let chapter=json!({"summary":summary,"decisions":[],"actionItems":[],"questions":[],
            "keywords":[],"markdown":"报价会议","evidence":evidence});
        let mut replies=vec![(200,chapter);7];
        replies.push((200,json!({"possiblyUnrelated":[],"duplicateGroups":[],"backgroundSummary":[],"backgroundDecisions":[],"backgroundQuestions":[]})));
        replies.push((200,json!({"overview":[{"text":"会议综合讨论了多项报价议题。","sources":[0,1,2,3,4,5,6,7,8]}]})));
        let (url,calls,job)=server(replies);let root=cache();
        let transcript="会议讨论产品报价。旁边有家务闲聊。小王周五整理报价。旁边的家人说周六买猫粮。\n".repeat(900);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["processing"]["complete"],true);
        let markdown=result["markdown"].as_str().unwrap();
        assert!(markdown.starts_with("## 会议概览"));
        assert!(markdown.contains("会议综合讨论了多项报价议题。"));
        assert!(markdown.contains("正常议题"));
        assert_eq!(calls.load(Ordering::SeqCst),9);job.join().unwrap();
        if root.exists() { std::fs::remove_dir_all(root).unwrap(); }
    }

    #[test]
    fn long_meeting_fallback_overview_uses_filtered_summary() {
        let mut summary=vec!["背景闲聊".to_string()];
        summary.extend((1..16).map(|i|format!("正常议题{i}")));
        let evidence=(0..16).map(|i|json!({"field":"summary","index":i,"quote":"会议讨论产品报价"})).collect::<Vec<_>>();
        let chapter=json!({"summary":summary,"decisions":[],"actionItems":[],"questions":[],
            "keywords":[],"markdown":"报价会议","evidence":evidence});
        let mut replies=vec![(200,chapter);7];
        replies.push((200,json!({"possiblyUnrelated":[],"duplicateGroups":[],"backgroundSummary":[0],"backgroundDecisions":[],"backgroundQuestions":[]})));
        replies.push((503,json!({})));
        replies.extend([(200,json!({"indices":[0,1]})),(200,json!({"indices":[5,6]})),(200,json!({"indices":[10,11]}))]);
        let (url,calls,job)=server(replies);let root=cache();
        let transcript="会议讨论产品报价。旁边有家务闲聊。小王周五整理报价。旁边的家人说周六买猫粮。\n".repeat(900);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["processing"]["complete"],true);
        let markdown=result["markdown"].as_str().unwrap();
        let overview=markdown.split_once("\n\n> 长会议").unwrap().0;
        assert!(overview.starts_with("## 全会重点"));assert!(overview.contains("正常议题1"));
        assert!(!overview.contains("背景闲聊"));
        assert!(markdown.contains("## 可能来自背景对话，请核对"));
        assert_eq!(calls.load(Ordering::SeqCst),12);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn long_meeting_keeps_multitopic_content_after_excessive_background_labels() {
        let summary=(0..16).map(|i|format!("正常议题{i}")).collect::<Vec<_>>();
        let mut evidence=(0..16).map(|i|json!({"field":"summary","index":i,"quote":"会议讨论产品报价"})).collect::<Vec<_>>();
        evidence.extend([json!({"field":"decisions","index":0,"quote":"会议讨论产品报价"}),
            json!({"field":"decisions","index":1,"quote":"小王周五整理报价"}),
            json!({"field":"questions","index":0,"quote":"会议讨论产品报价"}),
            json!({"field":"actionItems","index":0,"quote":"小王周五整理报价"})]);
        let chapter=json!({"summary":summary,"decisions":["报价确定","包装确定"],
            "actionItems":[{"text":"整理报价","owner":"小王","due":"周五"}],
            "questions":["报价何时发送？"],"keywords":[],"markdown":"报价会议","evidence":evidence});
        let mut replies=vec![(200,chapter);7];
        replies.push((200,json!({"possiblyUnrelated":[0],"duplicateGroups":[],
            "backgroundSummary":[0,1,2,3,4,5,6,7],"backgroundDecisions":[0,1],"backgroundQuestions":[0]})));
        let (url,calls,job)=server(replies);let root=cache();
        let transcript="会议讨论产品报价。旁边有家务闲聊。小王周五整理报价。旁边的家人说周六买猫粮。\n".repeat(900);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["processing"]["complete"],true);
        assert!(!result["markdown"].as_str().unwrap().contains("## 可能来自背景对话，请核对"));
        assert!(!result["actionItems"][0]["text"].as_str().unwrap().starts_with("可能来自背景对话"));
        assert!(result["markdown"].as_str().unwrap().contains("正常议题0"));
        assert_eq!(calls.load(Ordering::SeqCst),8);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn long_meeting_separates_background_content_and_keeps_sources() {
        let chapter=json!({"summary":["会议讨论产品报价。","旁边有家务闲聊。"],
            "decisions":["确定报价。","购买猫粮。"],"actionItems":[],
            "questions":["报价何时发送？","猫粮在哪里买？"],"keywords":[],"markdown":"报价会议",
            "evidence":[{"field":"summary","index":0,"quote":"会议讨论产品报价"},
                {"field":"summary","index":1,"quote":"旁边有家务闲聊"},
                {"field":"decisions","index":0,"quote":"会议讨论产品报价"},
                {"field":"decisions","index":1,"quote":"旁边的家人说周六买猫粮"},
                {"field":"questions","index":0,"quote":"小王周五整理报价"},
                {"field":"questions","index":1,"quote":"旁边的家人说周六买猫粮"}]});
        let mut replies=vec![(200,chapter);7];
        // A real provider returned summary IDs in the action field although
        // this meeting has no actions; valid source-backed sections still apply.
        replies.push((200,json!({"possiblyUnrelated":[5,6],"duplicateGroups":[],
            "backgroundSummary":[1],"backgroundDecisions":[1],"backgroundQuestions":[1]})));
        let (url,calls,job)=server(replies);let root=cache();
        let transcript="会议讨论产品报价。旁边有家务闲聊。小王周五整理报价。旁边的家人说周六买猫粮。\n".repeat(900);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["processing"]["complete"],true);
        let markdown=result["markdown"].as_str().unwrap();
        let (main,other)=markdown.split_once("## 可能来自背景对话，请核对").unwrap();
        assert!(main.contains("会议讨论产品报价"));assert!(!main.contains("旁边有家务闲聊"));
        assert!(other.contains("旁边有家务闲聊"));assert!(other.contains("购买猫粮"));assert!(other.contains("猫粮在哪里买"));
        assert!(other.contains("## 分段原文依据"));assert_eq!(result["summary"].as_array().unwrap().len(),2);
        assert_eq!(calls.load(Ordering::SeqCst),8);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }

    #[test]
    fn background_keywords_are_marked_only_when_source_is_unique() {
        let quote="旁人说要盘点仓库里的库存。";
        for legitimate in [false,true] {
            let first=json!({"summary":["会议讨论产品报价"],"decisions":[],
                "actionItems":[{"text":"盘点仓库库存","owner":null,"due":null}],
                "questions":[],"keywords":["库存盘点"],"markdown":"会议讨论产品报价",
                "evidence":[{"field":"summary","index":0,"quote":"会议讨论产品报价"},
                    {"field":"actionItems","index":0,"quote":quote}]});
            let later=json!({"summary":["会议讨论产品报价"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],
                "markdown":"会议讨论产品报价","evidence":[{"field":"summary","index":0,"quote":"会议讨论产品报价"}]});
            let (url,calls,job)=server(vec![(200,first),(200,later.clone()),(200,later.clone()),(200,later),
                (200,json!({"possiblyUnrelated":[0],"duplicateGroups":[]}))]);
            let root=cache();let mut transcript=format!("{quote}\n{}","会议讨论产品报价。\n".repeat(2100));
            if legitimate {transcript.push_str("会议后来讨论盘点仓库库存。\n");}
            let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
            assert_eq!(result["processing"]["complete"],true);assert_eq!(calls.load(Ordering::SeqCst),5);
            let markdown=result["markdown"].as_str().unwrap();
            assert_eq!(markdown.contains("库存盘点（可能来自背景对话，请核对）"),!legitimate);
            assert!(markdown.contains(quote));assert!(result["keywords"].as_array().unwrap().iter().any(|v|v=="库存盘点"));
            job.join().unwrap();let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
            assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
            std::fs::remove_dir_all(resolved).unwrap();
        }
    }

    #[test]
    fn repeated_missing_evidence_stays_draft_and_authentication_is_not_retried() {
        let missing=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"follow up report"});
        let transcript="follow up report. ".repeat(3200);
        for (responses,expected_calls) in [(vec![(200,missing.clone()),(200,missing.clone()),(200,missing.clone()),(200,missing)],4),
                                            (vec![(401,json!({}))],1)] {
            let (url,calls,job)=server(responses);let root=cache();
            let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
            assert_eq!(result["quality"],"draft");assert_eq!(result["processing"]["complete"],false);
            assert_eq!(result["processing"]["completedChunks"],0);assert_eq!(calls.load(Ordering::SeqCst),expected_calls);
            job.join().unwrap();
            let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
            assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
            std::fs::remove_dir_all(resolved).unwrap();
        }
    }
    #[test]
    fn unverified_chapter_content_remains_visible_as_draft_after_citation_retries() {
        let missing=json!({"summary":["讨论产品包装"],"decisions":[],
            "actionItems":[{"text":"发送报价","owner":"小王","due":"周五"}],
            "questions":[],"keywords":[],"markdown":"讨论产品包装"});
        let good=json!({"summary":["follow up report"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],
            "markdown":"follow up report","evidence":[{"field":"summary","index":0,"quote":"follow up report"}]});
        let (url,calls,job)=server(vec![(200,missing),(200,json!({})),(200,good.clone()),(200,good.clone()),(200,good),(200,json!({}))]);
        let root=cache();let transcript="follow up report. ".repeat(3200);
        let result:Value=serde_json::from_str(&generate_json(&request(&url,&transcript),"synthetic-key",&root).unwrap()).unwrap();
        assert_eq!(result["quality"],"draft");assert_eq!(result["processing"]["complete"],false);
        assert_eq!(result["processing"]["completedChunks"],3);
        let text=result["markdown"].as_str().unwrap();
        assert!(text.contains("未核对的参考草稿"));assert!(text.contains("讨论产品包装"));
        assert!(text.contains("可能的行动：发送报价"));assert!(text.contains("可能的负责人：小王"));
        assert!(result["actionItems"].as_array().unwrap().is_empty(),"unverified items must not become tasks");
        assert_eq!(calls.load(Ordering::SeqCst),6);job.join().unwrap();
        let resolved=root.canonicalize().unwrap();let temp=std::env::temp_dir().canonicalize().unwrap();
        assert!(resolved.parent()==Some(temp.as_path())&&resolved.file_name().unwrap().to_string_lossy().starts_with("companion-mobile-minutes-test-"));
        std::fs::remove_dir_all(resolved).unwrap();
    }
    #[test]
    fn rejects_insecure_remote_endpoint_before_sending() {
        assert!(generate_json(&request("http://example.com/chat/completions","synthetic"),"synthetic-key",&cache()).is_err());
    }
}
