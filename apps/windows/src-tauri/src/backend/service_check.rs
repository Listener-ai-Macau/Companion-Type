//! Explicit, bounded service probes. Never read a meeting, microphone or device.
use std::io::Read;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum Service { Asr, Minutes }

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CheckResult {
    pub service: Service,
    pub status: &'static str,
    pub message: &'static str,
    pub elapsed_ms: u64,
    pub checked_at_unix_ms: u64,
}

#[derive(Debug, PartialEq, Eq)]
enum Failure { Missing, Disabled, Configuration, Auth, RateLimit, Network, Timeout, Response, Service }
#[derive(Debug)]
enum ProbeKind { Cloud, LocalAsr, LocalMeeting, LocalMinutes }

fn env(key: &str) -> Option<String> { std::env::var(key).ok().map(|v| v.trim().to_string()).filter(|v| !v.is_empty()) }
fn required(value: Option<String>) -> Result<String, Failure> { value.ok_or(Failure::Missing) }

fn http_error(error: reqwest::Error) -> Failure {
    if error.is_timeout() { Failure::Timeout } else { Failure::Network }
}

fn status_error(status: u16) -> Failure {
    match status { 401 | 403 => Failure::Auth, 402 | 429 => Failure::RateLimit,
        400 | 404 | 405 | 422 => Failure::Configuration, _ => Failure::Service }
}

fn endpoint(value: &str) -> Result<reqwest::Url, Failure> {
    let url = reqwest::Url::parse(value).map_err(|_| Failure::Configuration)?;
    if !matches!(url.scheme(), "http" | "https") || url.host_str().is_none()
        || !url.username().is_empty() || url.password().is_some() || url.fragment().is_some() {
        return Err(Failure::Configuration);
    }
    // Use the same self-hosted endpoint the user saved; never probe other hosts
    // or follow redirects with a credential-bearing request.
    Ok(url)
}

fn response_json(response: reqwest::blocking::Response) -> Result<Value, Failure> {
    if !response.status().is_success() { return Err(status_error(response.status().as_u16())); }
    let mut bytes = Vec::new();
    response.take(65_537).read_to_end(&mut bytes).map_err(|_| Failure::Response)?;
    if bytes.len() > 65_536 { return Err(Failure::Response); }
    serde_json::from_slice(&bytes).map_err(|_| Failure::Response)
}

fn silent_wav() -> Vec<u8> {
    let mut wav = Vec::with_capacity(32_044);
    wav.extend(b"RIFF"); wav.extend(32_036u32.to_le_bytes()); wav.extend(b"WAVEfmt ");
    wav.extend(16u32.to_le_bytes()); wav.extend(1u16.to_le_bytes()); wav.extend(1u16.to_le_bytes());
    wav.extend(16_000u32.to_le_bytes()); wav.extend(32_000u32.to_le_bytes());
    wav.extend(2u16.to_le_bytes()); wav.extend(16u16.to_le_bytes()); wav.extend(b"data");
    wav.extend(32_000u32.to_le_bytes()); wav.resize(32_044, 0); wav
}

fn minutes_probe_body(model: &str) -> Value {
    let mut body = json!({"model":model,"stream":false,"max_tokens":16,
        "messages":[{"role":"user","content":"Connection test. Reply OK."}]});
    // DeepSeek defaults to thinking. Its reasoning consumed the entire tiny
    // probe budget and returned empty content with finish_reason=length.
    // Disable thinking only for this fixed probe, never for real minutes.
    // https://api-docs.deepseek.com/guides/thinking_mode/
    if model.to_ascii_lowercase().starts_with("deepseek-") {
        body["thinking"] = json!({"type":"disabled"});
    }
    body
}

fn http_probe(service: Service, address: &str, key: &str, model: &str) -> Result<(), Failure> {
    if key.trim().is_empty() || model.trim().is_empty() { return Err(Failure::Missing); }
    let url = endpoint(address)?;
    let client = reqwest::blocking::Client::builder().connect_timeout(Duration::from_secs(8))
        .timeout(Duration::from_secs(25)).redirect(reqwest::redirect::Policy::none())
        .build().map_err(|_| Failure::Network)?;
    let request = client.post(url).bearer_auth(key);
    let response = match service {
        Service::Minutes => request.json(&minutes_probe_body(model)).send(),
        Service::Asr => {
            let audio = reqwest::blocking::multipart::Part::bytes(silent_wav())
                .file_name("companion-connection-test.wav").mime_str("audio/wav").map_err(|_| Failure::Configuration)?;
            request.multipart(reqwest::blocking::multipart::Form::new().text("model", model.to_string())
                .text("response_format", "json").part("file", audio)).send()
        }
    }.map_err(http_error)?;
    let value = response_json(response)?;
    if value.get("error").is_some() { return Err(Failure::Response); }
    let valid = match service {
        // Empty text is normal for our silence probe. A JSON error object or
        // arbitrary 200 HTML response must not be reported as a working API.
        Service::Asr => value.get("text").and_then(Value::as_str).is_some(),
        Service::Minutes => value.pointer("/choices/0/message/content").and_then(Value::as_str)
            .is_some_and(|content| !content.trim().is_empty())
            && value.pointer("/choices/0/finish_reason")
                .is_none_or(|reason| reason.as_str() == Some("stop")),
    };
    if valid { Ok(()) } else { Err(Failure::Response) }
}

fn probe(service: Service) -> Result<ProbeKind, Failure> {
    let (settings,minutes_provider)=match service{
        Service::Minutes=>super::product_settings::load_minutes_settings().map_err(|_|Failure::Configuration)?,
        Service::Asr=>(super::product_settings::try_load_settings().map_err(|_|Failure::Configuration)?,None),
    };
    let public = settings.to_effective_public("");
    match service {
        Service::Minutes => {
            if minutes_provider
                ==Some(super::product_settings::MinutesProvider::Local){
                #[cfg(windows)] {return super::minutes::local::check_assets().map(|_|ProbeKind::LocalMinutes).map_err(|_|Failure::Missing);}
                #[cfg(not(windows))] {return Err(Failure::Configuration);}
            }
            if !public.deepseek_minutes_enabled { return Err(Failure::Disabled); }
            if !public.deepseek_api_key_set { return Err(Failure::Missing); }
            let key = required(env("DEEPSEEK_API_KEY").or_else(|| (!settings.deepseek_api_key.trim().is_empty()).then_some(settings.deepseek_api_key)))?;
            http_probe(service, &format!("{}/chat/completions", public.deepseek_base_url.trim_end_matches('/')), &key, &public.deepseek_model).map(|_|ProbeKind::Cloud)
        }
        Service::Asr => match public.asr_provider.as_str() {
            "local-paraformer" => super::transcription::check_local_asr().map(|_|ProbeKind::LocalAsr).map_err(|_| Failure::Missing),
            "local-meeting" => super::transcription::check_local_asr().map(|_|ProbeKind::LocalMeeting).map_err(|_| Failure::Missing),
            "volcengine" => {
                if !public.volc_app_key_set || !public.volc_access_key_set { return Err(Failure::Missing); }
                let app_id = required(env("COMPANION_TYPE_VOLC_APP_KEY").or_else(|| (!settings.volc_app_key.trim().is_empty()).then_some(settings.volc_app_key)))?;
                let access_token = required(env("COMPANION_TYPE_VOLC_ACCESS_KEY").or_else(|| (!settings.volc_access_key.trim().is_empty()).then_some(settings.volc_access_key)))?;
                let credentials = super::volcengine::VolcengineCredentials { app_id, access_token, resource_id: public.volc_resource_id };
                super::volcengine::VolcengineSaucAsr::new(credentials).probe_silent_audio().map_err(|error| {
                    let error = error.to_ascii_lowercase();
                    if error.contains("auth rejected") || error.contains("unauthorized") || error.contains("45000001") { Failure::Auth }
                    else if error.contains("429") || error.contains("quota") || error.contains("rate limit") { Failure::RateLimit }
                    else if error.contains("timed out") || error.contains("timeout") { Failure::Timeout }
                    else if error.contains("header") { Failure::Configuration }
                    else if error.contains("connect") || error.contains("tls") || error.contains("dns") { Failure::Network }
                    else { Failure::Service }
                }).map(|_|ProbeKind::Cloud)
            }
            "openai" | "openai-compatible" => {
                if !public.openai_asr_api_key_set { return Err(Failure::Missing); }
                let key = required(env("COMPANION_TYPE_ASR_API_KEY").or_else(|| env("OPENAI_API_KEY"))
                    .or_else(|| (!settings.openai_asr_api_key.trim().is_empty()).then_some(settings.openai_asr_api_key)))?;
                http_probe(service, &public.openai_asr_endpoint, &key, &public.openai_asr_model).map(|_|ProbeKind::Cloud)
            }
            _ => Err(Failure::Configuration),
        }
    }
}

pub fn check(service: Service) -> CheckResult {
    let start = Instant::now();
    let (status, message) = match probe(service) {
        Ok(ProbeKind::LocalMinutes)=>("available","本地纪要组件已校验；未发送会议或测试文字，整理效果仍以实际使用为准。"),
        Ok(ProbeKind::LocalAsr) => ("available", "本地转写模型已校验并加载；未上传录音，识别质量仍需实际使用验证。"),
        Ok(ProbeKind::LocalMeeting) => ("available", "本地中英文会议模型包已校验，打开录音后可离线生成终稿。"),
        Ok(ProbeKind::Cloud) => ("available", "本次测试请求成功。只验证服务调用，不代表录音、识别或纪要准确率已通过。"),
        Err(Failure::Missing) => ("notConfigured", "缺少服务凭据或模型，请先保存配置。"),
        Err(Failure::Disabled) => ("disabled", "智能纪要已关闭，没有发送测试请求。"),
        Err(Failure::Configuration) => ("invalidConfiguration", "服务地址、模型、资源或请求配置不匹配，请核对后重试。"),
        Err(Failure::Auth) => ("authenticationFailed", "服务拒绝鉴权，请检查密钥及资源访问权限。"),
        Err(Failure::RateLimit) => ("quotaOrRateLimit", "服务额度不足或请求受限，请检查账户后重试。"),
        Err(Failure::Network) => ("networkError", "无法连接服务，请检查网络、代理和证书。"),
        Err(Failure::Timeout) => ("timeout", "服务测试超时，请稍后重试。"),
        Err(Failure::Response) => ("invalidResponse", "服务已响应，但返回格式不符合当前接口，不能确认可用。"),
        Err(Failure::Service) => ("serviceError", "服务未完成测试请求，请核对资源状态后重试。"),
    };
    CheckResult { service, status, message, elapsed_ms: start.elapsed().as_millis() as u64,
        checked_at_unix_ms: SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as u64 }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;
    use std::io::{Read, Write};
    fn server(status: u16, body: &str) -> (String, std::thread::JoinHandle<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let url = format!("http://{}/probe", listener.local_addr().unwrap()); let body = body.to_string();
        let worker = std::thread::spawn(move || {
            let (mut socket, _) = listener.accept().unwrap(); socket.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
            let mut bytes = Vec::new(); let mut block = [0; 4096];
            loop {
                let count = socket.read(&mut block).unwrap(); if count == 0 { break; } bytes.extend(&block[..count]);
                if let Some(end) = bytes.windows(4).position(|s| s == b"\r\n\r\n") {
                    let header = String::from_utf8_lossy(&bytes[..end]).to_ascii_lowercase();
                    let length: usize = header.lines().find_map(|line| line.strip_prefix("content-length:")).unwrap_or("0").trim().parse().unwrap();
                    if bytes.len() >= end + 4 + length { break; }
                }
            }
            write!(socket, "HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len()).unwrap();
            String::from_utf8_lossy(&bytes).into_owned()
        }); (url, worker)
    }
    #[test]
    fn http_probes_send_only_fixed_test_content_and_validate_response() {
        let (url, worker) = server(200, r#"{"text":""}"#);
        assert_eq!(http_probe(Service::Asr, &url, "test-secret", "test-model"), Ok(()));
        let request = worker.join().unwrap(); assert!(request.contains("companion-connection-test.wav")); assert!(request.contains("RIFF"));
        let (url, worker) = server(200, r#"{"choices":[{"message":{"content":"OK"}}]}"#);
        assert_eq!(http_probe(Service::Minutes, &url, "test-secret", "test-model"), Ok(()));
        assert!(worker.join().unwrap().contains("Connection test. Reply OK."));
        // Reasoning-only and truncated text are not a completed probe.
        for body in [r#"{"choices":[{"finish_reason":"length","message":{"content":"","reasoning_content":"test-only reasoning"}}]}"#,
            r#"{"choices":[{"finish_reason":"length","message":{"content":"O"}}]}"#] {
            let (url, worker) = server(200, body);
            assert_eq!(http_probe(Service::Minutes, &url, "test-secret", "deepseek-v4-flash"), Err(Failure::Response));
            let request = worker.join().unwrap();
            let body: Value = serde_json::from_str(request.split("\r\n\r\n").nth(1).unwrap()).unwrap();
            assert_eq!(body["thinking"]["type"], "disabled");
            assert_eq!(body["max_tokens"], 16);
        }
        assert!(minutes_probe_body("compatible-model").get("thinking").is_none());
        for (status, body, expected) in [(401,"secret-provider-detail",Failure::Auth),(429,"quota",Failure::RateLimit),(200,"{}",Failure::Response),(302,"redirect",Failure::Service)] {
            let (url, worker) = server(status, body);
            assert_eq!(http_probe(Service::Asr, &url, "test-secret", "model"), Err(expected)); worker.join().unwrap();
        }
    }
    #[test]
    fn invalid_endpoint_and_missing_credentials_fail_before_network() {
        assert_eq!(http_probe(Service::Minutes,"file:///secret","key","model"),Err(Failure::Configuration));
        assert_eq!(http_probe(Service::Minutes,"https://user:secret@example.invalid","key","model"),Err(Failure::Configuration));
        assert_eq!(http_probe(Service::Asr,"http://127.0.0.1:1","","model"),Err(Failure::Missing));
    }
}
