use crate::{backend,companion_v1::CompanionV1HostSession};
use serde::Deserialize;
use std::path::Path;

#[derive(Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Request {session_key:String,title:String,transcript:String,duration_millis:u64,endpoint:String,model:String}

pub fn generate_json(request:&str,key:&str,cache:&Path)->Result<String,String> {
    if request.len()>3*1024*1024{return Err("纪要请求过大；原转写保持不变。".into());}
    let request:Request=serde_json::from_str(request).map_err(|_|"纪要请求格式不正确。")?;
    if request.session_key.trim().is_empty()||request.title.len()>1024||request.transcript.trim().is_empty()
        ||request.duration_millis==0||request.model.trim().is_empty()||key.trim().is_empty()||cache.as_os_str().is_empty()||!cache.is_absolute() {
        return Err("纪要来源、服务配置或私有缓存目录不完整；原转写保持不变。".into());
    }
    let session=CompanionV1HostSession{id:request.session_key,title:request.title,source:"mobile".into(),
        transcript_text:request.transcript,duration_ms:request.duration_millis,meeting_mode:"offlineStore".into(),..Default::default()};
    let result=backend::generate(&session,&request.endpoint,&request.model,key,cache)?;
    serde_json::to_string(&result).map_err(|_|"纪要结果无法读取；原转写保持不变。".into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json,Value};
    use std::{io::{Read,Write},net::TcpListener,sync::{Arc,atomic::{AtomicUsize,Ordering}},thread};

    fn server(responses:Vec<(u16,Value)>)->(String,Arc<AtomicUsize>,thread::JoinHandle<()>) {
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
            observed.fetch_add(1,Ordering::SeqCst);
            let body=if status==200 {json!({"choices":[{"finish_reason":"stop","message":{"content":content.to_string()}}]}).to_string()}else{"{}".into()};
            write!(stream,"HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",body.len(),body).unwrap();
        });
        (format!("http://{addr}/chat/completions"),calls,job)
    }
    fn request(endpoint:&str,transcript:&str)->String {json!({"sessionKey":"synthetic-session","title":"Synthetic","transcript":transcript,"durationMillis":10000,"endpoint":endpoint,"model":"synthetic-model"}).to_string()}
    fn cache()->std::path::PathBuf {std::env::temp_dir().join(format!("companion-mobile-minutes-test-{}",uuid::Uuid::new_v4()))}
    fn content()->Value {json!({"summary":["明天检查样品"],"decisions":[],"actionItems":[],"questions":[],"keywords":[],"markdown":"检查样品","questionClassification":[{"sourceId":1,"kind":"statement"}]})}

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
    fn rejects_insecure_remote_endpoint_before_sending() {
        assert!(generate_json(&request("http://example.com/chat/completions","synthetic"),"synthetic-key",&cache()).is_err());
    }
}
