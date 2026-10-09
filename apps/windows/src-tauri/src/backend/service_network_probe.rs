//! Installed production-adapter fault checks against private, ephemeral
//! loopback API fixtures. This is not real ASR, a GUI preview or board evidence.
use super::minutes::{finalize_minutes, rules_l0_minutes, run_deepseek_request};
use crate::companion_v1::{fixture_snapshot, synced_device_session, CompanionV1ControlRequest};
use denzic_host_audio_v1_core::{
    asr::BatchAsrProvider,
    asr_openai::{OpenAiAsrConfig, OpenAiCompatibleAsr},
    http_policy,
};
use serde_json::{json, Value};
use std::{
    fs,
    io::{Read, Write},
    net::TcpListener,
    path::Path,
    thread,
    time::{Duration, Instant},
};

const PRIVATE: &str = "network-probe-secret";

fn response(status: &str, body: &str) -> Vec<u8> {
    format!("HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len()).into_bytes()
}

fn fixture(
    bytes: Vec<u8>,
    delay: Duration,
    header_first: bool,
) -> Result<(String, thread::JoinHandle<Result<Vec<u8>, String>>), String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|_| "HTTP fixture bind failed")?;
    listener
        .set_nonblocking(true)
        .map_err(|_| "HTTP fixture setup failed")?;
    let endpoint = format!(
        "http://{}/v1/test?private={PRIVATE}",
        listener
            .local_addr()
            .map_err(|_| "HTTP fixture address failed")?
    );
    let worker = thread::spawn(move || {
        let started = Instant::now();
        let mut stream = loop {
            match listener.accept() {
                Ok((stream, _)) => break stream,
                Err(error)
                    if error.kind() == std::io::ErrorKind::WouldBlock
                        && started.elapsed() < Duration::from_secs(3) =>
                {
                    thread::sleep(Duration::from_millis(10))
                }
                _ => return Err("HTTP fixture accept failed".into()),
            }
        };
        stream
            .set_read_timeout(Some(Duration::from_secs(2)))
            .map_err(|_| "HTTP fixture read setup failed")?;
        stream
            .set_write_timeout(Some(Duration::from_secs(2)))
            .map_err(|_| "HTTP fixture write setup failed")?;
        let mut request = Vec::new();
        let mut buffer = [0u8; 4096];
        while request.len() <= 128 * 1024 {
            let count = stream
                .read(&mut buffer)
                .map_err(|_| "HTTP fixture request failed")?;
            if count == 0 {
                return Err("HTTP fixture incomplete request".into());
            }
            request.extend_from_slice(&buffer[..count]);
            let headers = String::from_utf8_lossy(&request);
            if let Some(end) = headers.find("\r\n\r\n") {
                let length = headers[..end]
                    .lines()
                    .find_map(|line| {
                        let (name, value) = line.split_once(':')?;
                        name.eq_ignore_ascii_case("content-length")
                            .then(|| value.trim().parse::<usize>().ok())
                            .flatten()
                    })
                    .unwrap_or(0);
                if request.len() >= end + 4 + length {
                    break;
                }
            }
        }
        if request.len() > 128 * 1024 {
            return Err("HTTP fixture request too large".into());
        }
        let split = if header_first {
            bytes
                .windows(4)
                .position(|window| window == b"\r\n\r\n")
                .map(|index| index + 4)
                .unwrap_or(0)
        } else {
            0
        };
        if split > 0 {
            let _ = stream.write_all(&bytes[..split]);
        }
        if !delay.is_zero() {
            thread::sleep(delay);
        }
        // Timeouts and response-size rejection deliberately close the client
        // before the fixture has finished sending its body.
        let _ = stream.write_all(&bytes[split..]);
        Ok(request)
    });
    Ok((endpoint, worker))
}

fn minutes_body(content: &str, finish_reason: &str) -> String {
    json!({"choices":[{"finish_reason":finish_reason,"message":{"content":content}}]}).to_string()
}

pub(crate) fn verify(output: &Path) -> Result<Value, String> {
    fs::create_dir(output)
        .map_err(|_| "Network probe requires a fresh, creatable output folder")?;
    let audio = output.join("controlled-silence.wav");
    let mut wav = Vec::from(&b"RIFF"[..]);
    wav.extend_from_slice(&(36u32 + 3200).to_le_bytes());
    wav.extend_from_slice(b"WAVEfmt ");
    wav.extend_from_slice(&16u32.to_le_bytes());
    wav.extend_from_slice(&1u16.to_le_bytes());
    wav.extend_from_slice(&1u16.to_le_bytes());
    wav.extend_from_slice(&16000u32.to_le_bytes());
    wav.extend_from_slice(&32000u32.to_le_bytes());
    wav.extend_from_slice(&2u16.to_le_bytes());
    wav.extend_from_slice(&16u16.to_le_bytes());
    wav.extend_from_slice(b"data");
    wav.extend_from_slice(&3200u32.to_le_bytes());
    wav.resize(wav.len() + 3200, 0);
    fs::write(&audio, wav).map_err(|_| "Cannot write controlled audio fixture")?;
    let request: CompanionV1ControlRequest = serde_json::from_value(json!({"action":"deviceSyncRecordings","title":"Controlled network fixture", "durationMs":100}))
        .map_err(|_| "Cannot create controlled session")?;
    let mut session = synced_device_session(&fixture_snapshot(), &request, "network-fixture");
    session.source = "controlledNetworkFixture".into();
    session.audio_path = Some(audio.to_string_lossy().into());
    session.transcript_text = "Decision: Keep the controlled source fact.".into();
    session.transcript_final = true;
    let l0 = rules_l0_minutes(&session, "network-fixture");
    let mut checks = Vec::new();
    let mut check = |name: &str, passed: bool| -> Result<(), String> {
        checks.push(json!({"name":name,"passed":passed}));
        if passed {
            Ok(())
        } else {
            Err(format!("Service network probe failed: {name}"))
        }
    };
    let native_content = json!({"summary":["Keep the controlled source fact."],"decisions":["Keep the controlled source fact."],
        "actionItems":[], "questions":[],"keywords":[],"markdown":"# Controlled minutes\nKeep the controlled source fact."}).to_string();
    for minutes in [false, true] {
        let prefix = if minutes { "minutes" } else { "asr" };
        let body = if minutes {
            minutes_body(&native_content, "stop")
        } else {
            json!({"text":"Controlled final"}).to_string()
        };
        let (endpoint, worker) = fixture(response("200 OK", &body), Duration::ZERO, false)?;
        let passed = if minutes {
            let client = http_policy::client(Duration::from_secs(2))
                .map_err(|_| "Cannot create fixture HTTP client")?;
            let result = run_deepseek_request(
                &endpoint,
                "controlled-model",
                PRIVATE,
                &session,
                &l0,
                &client,
            );
            result.is_ok_and(|value| {
                value.quality == "final"
                    && value.source == "llm_deepseek"
                    && value.markdown.contains("controlled source fact")
            })
        } else {
            let mut config = OpenAiAsrConfig::new(&endpoint, PRIVATE);
            config.timeout = Duration::from_secs(2);
            OpenAiCompatibleAsr::new(config)
                .transcribe_file(&audio)
                .is_ok_and(|value| value.is_final && value.text == "Controlled final")
        };
        let captured = worker.join().map_err(|_| "HTTP fixture thread failed")??;
        let captured = String::from_utf8_lossy(&captured).to_lowercase();
        check(
            &format!("{prefix}_production_request_and_valid_result"),
            passed
                && captured.contains("post /v1/test")
                && captured.contains(&format!("authorization: bearer {PRIVATE}"))
                && captured.contains(if minutes {
                    "controlled-model"
                } else {
                    "multipart/form-data"
                }),
        )?;
        let redirect_target =
            TcpListener::bind("127.0.0.1:0").map_err(|_| "Redirect fixture bind failed")?;
        redirect_target
            .set_nonblocking(true)
            .map_err(|_| "Redirect fixture setup failed")?;
        let redirect = format!("HTTP/1.1 302 Found\r\nLocation: http://{}/secret-target\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            redirect_target.local_addr().map_err(|_| "Redirect fixture address failed")?).into_bytes();
        let over = http_policy::MAX_RESPONSE_BYTES as usize + 1;
        let oversized_chunk = format!("HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n{over:x}\r\n{}\r\n0\r\n\r\n", "X".repeat(over)).into_bytes();
        for (name, bytes, expected, delay) in [
            (
                "auth_body_redacted",
                response("401 Unauthorized", PRIVATE),
                "401",
                Duration::ZERO,
            ),
            (
                "rate_limit_classified",
                response("429 Too Many Requests", PRIVATE),
                "429",
                Duration::ZERO,
            ),
            (
                "provider_failure_redacted",
                response("503 Service Unavailable", PRIVATE),
                "503",
                Duration::ZERO,
            ),
            ("redirect_not_followed", redirect, "302", Duration::ZERO),
            (
                "oversized_length_rejected",
                format!("HTTP/1.1 200 OK\r\nContent-Length: {over}\r\n\r\n{PRIVATE}").into_bytes(),
                "size limit",
                Duration::ZERO,
            ),
            (
                "oversized_stream_rejected",
                oversized_chunk,
                "size limit",
                Duration::ZERO,
            ),
            (
                "html_is_not_final",
                response("200 OK", PRIVATE),
                "invalid",
                Duration::ZERO,
            ),
            (
                "error_json_is_not_final",
                response("200 OK", &json!({"error": PRIVATE}).to_string()),
                "invalid",
                Duration::ZERO,
            ),
            (
                "truncated_body_is_not_final",
                format!("HTTP/1.1 200 OK\r\nContent-Length: 9999\r\n\r\n{PRIVATE}").into_bytes(),
                "read completely",
                Duration::ZERO,
            ),
            (
                "deadline_is_enforced",
                response("200 OK", &body),
                "timed out",
                Duration::from_millis(700),
            ),
            (
                "body_deadline_is_enforced",
                response("200 OK", &body),
                "timed out",
                Duration::from_millis(700),
            ),
        ] {
            let (endpoint, worker) = fixture(bytes, delay, name == "body_deadline_is_enforced")?;
            let timeout = if delay.is_zero() {
                Duration::from_secs(2)
            } else {
                Duration::from_millis(150)
            };
            let started = Instant::now();
            let error = if minutes {
                let client = http_policy::client(timeout)
                    .map_err(|_| "Cannot create fixture HTTP client")?;
                let result = run_deepseek_request(
                    &endpoint,
                    "controlled-model",
                    PRIVATE,
                    &session,
                    &l0,
                    &client,
                );
                let fallback = finalize_minutes(result, l0.clone(), &session);
                if fallback.quality != "draft" || fallback.markdown != l0.markdown {
                    return Err("Minutes fixture lost its local draft".into());
                }
                fallback.llm_note.unwrap_or_default()
            } else {
                let mut config = OpenAiAsrConfig::new(&endpoint, PRIVATE);
                config.timeout = timeout;
                match OpenAiCompatibleAsr::new(config).transcribe_file(&audio) {
                    Ok(_) => {
                        return Err(format!(
                            "Service network probe accepted invalid response: {prefix}_{name}"
                        ))
                    }
                    Err(error) => {
                        use denzic_host_audio_v1_core::asr::AsrErrorKind;
                        let valid_class = match name {
                            "auth_body_redacted" => {
                                error.kind == AsrErrorKind::Auth && !error.retryable
                            }
                            "rate_limit_classified" => {
                                error.kind == AsrErrorKind::RateLimited && error.retryable
                            }
                            "provider_failure_redacted" => {
                                error.kind == AsrErrorKind::Provider && error.retryable
                            }
                            "deadline_is_enforced" | "body_deadline_is_enforced" => {
                                error.kind == AsrErrorKind::Network && error.retryable
                            }
                            _ => true,
                        };
                        if !valid_class {
                            return Err(format!(
                                "Service network probe error classification failed: {name}"
                            ));
                        }
                        error.to_string()
                    }
                }
            };
            let elapsed = started.elapsed();
            worker.join().map_err(|_| "HTTP fixture thread failed")??;
            check(
                &format!("{prefix}_{name}"),
                error.contains(expected)
                    && !error.contains(PRIVATE)
                    && !error.contains("127.0.0.1")
                    && (delay.is_zero() || elapsed < Duration::from_millis(500)),
            )?;
            if name == "redirect_not_followed" {
                check(
                    &format!("{prefix}_redirect_target_never_contacted"),
                    matches!(redirect_target.accept(), Err(error) if error.kind() == std::io::ErrorKind::WouldBlock),
                )?;
            }
        }
    }
    for (name, content, reason) in [
        (
            "minutes_plain_text_is_not_final",
            PRIVATE.to_string(),
            "stop",
        ),
        (
            "minutes_incomplete_fields_are_not_final",
            "{}".to_string(),
            "stop",
        ),
        (
            "minutes_truncated_completion_is_not_final",
            native_content,
            "length",
        ),
    ] {
        let (endpoint, worker) = fixture(
            response("200 OK", &minutes_body(&content, reason)),
            Duration::ZERO,
            false,
        )?;
        let client = http_policy::client(Duration::from_secs(2))
            .map_err(|_| "Cannot create fixture HTTP client")?;
        let result = run_deepseek_request(
            &endpoint,
            "controlled-model",
            PRIVATE,
            &session,
            &l0,
            &client,
        );
        let fallback = finalize_minutes(result, l0.clone(), &session);
        worker.join().map_err(|_| "HTTP fixture thread failed")??;
        check(
            name,
            fallback.quality == "draft"
                && fallback.markdown == l0.markdown
                && fallback
                    .llm_note
                    .is_some_and(|error| error.contains("invalid") && !error.contains(PRIVATE)),
        )?;
    }
    check(
        "original_audio_and_transcript_retained",
        audio.is_file()
            && fs::metadata(&audio).is_ok_and(|metadata| metadata.len() == 3244)
            && session.transcript_text == "Decision: Keep the controlled source fact.",
    )?;
    checks.extend(super::volcengine::verify_network()?);
    let report = json!({"schema":"companion.type.service_network_probe.v1", "result":"PASS_LOCAL_SERVICE_FAULTS_ONLY", "checks":checks,
        "loopbackNetworkOnly":true,"remoteNetworkAccess":false,"realUserProfileAccess":false,"deviceAccess":false,
        "scope":"native OpenAI-compatible ASR, DeepSeek minutes and Volcengine batch/live adapters; advanced external wrappers are not covered",
        "trueAsrAcceptance":"NOT_RUN","guiAcceptance":"NOT_RUN","fullChainAcceptance":"NOT_RUN"});
    fs::write(
        output.join("result.json"),
        serde_json::to_vec_pretty(&report).map_err(|_| "Cannot encode network report")?,
    )
    .map_err(|_| "Cannot save network report")?;
    Ok(report)
}

#[cfg(test)]
mod tests {
    #[test]
    fn installed_probe_exercises_production_adapters_and_refuses_existing_output() {
        let output =
            std::env::temp_dir().join(format!("companion-network-probe-{}", uuid::Uuid::new_v4()));
        let report = super::verify(&output).unwrap();
        assert!(report["checks"].as_array().unwrap().len() >= 37);
        assert!(super::verify(&output).is_err());
        assert_eq!(report["fullChainAcceptance"], "NOT_RUN");
    }
}
