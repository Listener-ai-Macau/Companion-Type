//! Local WebSocket fault fixtures for the actual production client. No saved
//! credentials, real service, user audio, device or GUI is accessed.
use super::*;
use serde_json::json;

fn server_frame(payload: &str, final_result: bool) -> Vec<u8> {
    frame_build(
        MessageType::FullServerResponse,
        if final_result {
            Flags::LastPacket
        } else {
            Flags::None
        },
        Serialization::Json,
        payload.as_bytes(),
        None,
    )
}

fn provider(endpoint: String) -> VolcengineSaucAsr {
    VolcengineSaucAsr {
        credentials: VolcengineCredentials {
            app_id: "network-probe-app".into(),
            access_token: "network-probe-secret".into(),
            resource_id: "volc.seedasr.sauc.duration".into(),
        },
        endpoint,
        // Do not inherit the user's environment hotwords in a fault fixture.
        payload_template: json!({"user":{"uid":""}, "audio":{"format":"pcm","rate":16000,"bits":16,"channel":1},
            "request":{"model_name":"bigmodel","reqid":"","language":"auto"}}),
    }
}

fn fixture(
    frames: Vec<Vec<u8>>,
) -> Result<(String, std::thread::JoinHandle<Result<(), String>>), String> {
    fixture_with_audio(frames, None)
}

fn fixture_with_audio(
    frames: Vec<Vec<u8>>,
    expected: Option<(Vec<u8>, Vec<usize>)>,
) -> Result<(String, std::thread::JoinHandle<Result<(), String>>), String> {
    let listener =
        std::net::TcpListener::bind("127.0.0.1:0").map_err(|_| "WS fixture bind failed")?;
    let endpoint = format!(
        "ws://{}/",
        listener
            .local_addr()
            .map_err(|_| "WS fixture address failed")?
    );
    listener
        .set_nonblocking(true)
        .map_err(|_| "WS fixture setup failed")?;
    let worker = std::thread::spawn(move || {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|_| "WS fixture runtime failed")?;
        runtime.block_on(async {
            let listener = tokio::net::TcpListener::from_std(listener)
                .map_err(|_| "WS fixture listener failed")?;
            let (stream, _) = tokio::time::timeout(Duration::from_secs(3), listener.accept())
                .await
                .map_err(|_| "WS fixture accept timed out")?
                .map_err(|_| "WS fixture accept failed")?;
            let mut ws = tokio_tungstenite::accept_async(stream)
                .await
                .map_err(|_| "WS fixture handshake failed")?;
            // Wait for the client's real end-of-audio framing before sending
            // results, so a test close cannot race its remaining uploads.
            let mut pcm = Vec::new();
            let mut packet_lengths = Vec::new();
            let mut next_sequence = 2;
            loop {
                let message = tokio::time::timeout(Duration::from_secs(3), ws.next())
                    .await
                    .map_err(|_| "WS fixture audio timed out")?
                    .ok_or("WS fixture closed early")?
                    .map_err(|_| "WS fixture read failed")?;
                if let Message::Binary(bytes) = message {
                    let parsed = frame_parse(&bytes).ok_or("WS fixture invalid request")?;
                    if parsed.message_type == Some(MessageType::AudioOnlyRequest) {
                        if expected.is_some() {
                            let sequence = if parsed.is_final() { -next_sequence } else { next_sequence };
                            if parsed.sequence != Some(sequence) {
                                return Err("WS fixture unexpected saved-meeting sequence".into());
                            }
                            next_sequence += 1;
                            if !parsed.payload.is_empty() {
                                packet_lengths.push(parsed.payload.len());
                                pcm.extend_from_slice(&parsed.payload);
                            }
                        }
                        if parsed.is_final() {
                            break;
                        }
                    }
                }
            }
            if let Some((expected_pcm, expected_lengths)) = expected {
                if pcm != expected_pcm || packet_lengths != expected_lengths {
                    return Err("WS fixture saved-meeting audio differs".into());
                }
            }
            for frame in frames {
                if ws.send(Message::Binary(frame)).await.is_err() {
                    break;
                }
            }
            // The receiver may already have completed or rejected the result.
            let _ = ws.close(None).await;
            Ok(())
        })
    });
    Ok((endpoint, worker))
}

pub(in super::super) fn verify() -> Result<Vec<Value>, String> {
    let mut checks = Vec::new();
    let mut check = |name: &str, passed: bool| -> Result<(), String> {
        checks.push(json!({"name":name,"passed":passed}));
        if passed {
            Ok(())
        } else {
            Err(format!("WebSocket network probe failed: {name}"))
        }
    };
    let partial = server_frame(
        r#"{"result":{"text":"Controlled partial","utterances":[{"text":"stale","start_time":1,"end_time":2}]}}"#,
        false,
    );
    let empty_final = server_frame(r#"{"result":{"text":""}}"#, true);
    let final_frame = server_frame(r#"{"result":{"text":"Controlled final"}}"#, true);
    let mut error_frame = vec![HEADER_BYTE_0, 0xf0, 0x10, 0];
    error_frame.extend_from_slice(&45000001u32.to_be_bytes());
    let private_error = b"network-probe-secret private meeting body";
    error_frame.extend_from_slice(&(private_error.len() as u32).to_be_bytes());
    error_frame.extend_from_slice(private_error);
    for (name, frames, expected) in [
        (
            "ws_batch_final_is_authoritative",
            vec![partial.clone(), empty_final.clone(), final_frame.clone()],
            Ok("Controlled final"),
        ),
        (
            "ws_partial_close_is_not_final",
            vec![partial.clone()],
            Err("without a final result"),
        ),
        (
            "ws_empty_final_cannot_promote_partial",
            vec![partial.clone(), empty_final.clone()],
            Err(NO_SPEECH_ERROR),
        ),
        (
            "ws_empty_metadata_after_eos_closes_without_speech",
            vec![server_frame(r#"{"result":{"additions":{}},"audio_info":{"duration":100}}"#, true)],
            Err(NO_SPEECH_ERROR),
        ),
        (
            "ws_malformed_json_is_not_transcript",
            vec![server_frame("network-probe-secret", true)],
            Err("protocol invalid"),
        ),
        (
            "ws_error_body_is_redacted",
            vec![error_frame],
            Err("code=45000001"),
        ),
        (
            "ws_oversized_frame_is_rejected",
            vec![vec![0u8; WEBSOCKET_MAX_RESPONSE_BYTES + 1]],
            Err("size limit"),
        ),
    ] {
        let (endpoint, worker) = fixture(frames)?;
        let result = provider(endpoint).transcribe_pcm_bytes(&vec![0u8; TARGET_AUDIO_CHUNK_BYTES]);
        worker.join().map_err(|_| "WS fixture thread failed")??;
        let passed = match (expected, &result) {
            (Ok(expected), Ok((text, utterances))) => text == expected && utterances.is_empty(),
            (Err(expected), Err(error)) => {
                error.contains(expected)
                    && !error.contains("network-probe-secret")
                    && !error.contains("private meeting body")
            }
            _ => false,
        };
        check(name, passed)?;
    }
    for (name, frames, success) in [
        (
            "ws_live_final_replaces_partial",
            vec![partial.clone(), empty_final.clone(), final_frame],
            true,
        ),
        (
            "ws_live_close_retains_partial_without_success",
            vec![partial.clone(), empty_final],
            false,
        ),
    ] {
        let (endpoint, worker) = fixture(frames)?;
        let (tx, rx) = std::sync::mpsc::channel();
        tx.send(vec![0u8; TARGET_AUDIO_CHUNK_BYTES])
            .map_err(|_| "WS fixture PCM channel failed")?;
        drop(tx);
        let observations = Arc::new(std::sync::Mutex::new(Vec::<String>::new()));
        let recorded = Arc::clone(&observations);
        let result = provider(endpoint).stream_pcm_session(
            rx,
            Arc::new(AtomicBool::new(false)),
            move |text| {
                if let Ok(mut seen) = recorded.lock() {
                    seen.push(text.into());
                }
            },
        );
        worker
            .join()
            .map_err(|_| "WS live fixture thread failed")??;
        let seen = observations
            .lock()
            .map_err(|_| "WS fixture observation failed")?;
        check(
            name,
            seen.iter().any(|text| text == "Controlled partial")
                && if success {
                    result.as_deref() == Ok("Controlled final")
                        && seen.last().is_some_and(|text| text == "Controlled final")
                } else {
                    result.as_ref().is_err_and(|error| is_no_speech_error(error))
                        && seen.last().is_some_and(|text| text == "Controlled partial")
                },
        )?;
    }
    // Cancellation must drop the receive task as well as its result channel.
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|_| "WS cancellation runtime failed")?;
    let cancelled = runtime.block_on(async {
        let (tx, rx) = oneshot::channel::<()>();
        let task = ReceiveTask(tokio::spawn(async move {
            let _guard = tx;
            std::future::pending::<()>().await;
        }));
        tokio::task::yield_now().await;
        drop(task);
        matches!(
            tokio::time::timeout(Duration::from_secs(1), rx).await,
            Ok(Err(_))
        )
    });
    check("ws_cancel_aborts_receive_task", cancelled)?;
    let redirect_target = std::net::TcpListener::bind("127.0.0.1:0")
        .map_err(|_| "WS redirect fixture bind failed")?;
    redirect_target
        .set_nonblocking(true)
        .map_err(|_| "WS redirect fixture setup failed")?;
    for (name, status, expected) in [
        (
            "ws_handshake_error_is_redacted",
            "401 Unauthorized",
            "auth rejected (HTTP 401)",
        ),
        (
            "ws_handshake_redirect_not_followed",
            "302 Found",
            "HTTP 302",
        ),
    ] {
        use std::io::{Read, Write};
        let listener = std::net::TcpListener::bind("127.0.0.1:0")
            .map_err(|_| "WS handshake fixture bind failed")?;
        let endpoint = format!(
            "ws://{}/?private=network-probe-secret",
            listener
                .local_addr()
                .map_err(|_| "WS handshake fixture address failed")?
        );
        let response = format!("HTTP/1.1 {status}\r\nLocation: http://{}/private\r\nX-Tt-Logid: network-probe-secret\r\nContent-Length: 20\r\n\r\nnetwork-probe-secret",
            redirect_target.local_addr().map_err(|_| "WS redirect fixture address failed")?);
        listener
            .set_nonblocking(true)
            .map_err(|_| "WS handshake fixture setup failed")?;
        let worker = std::thread::spawn(move || {
            let started = std::time::Instant::now();
            let mut stream = loop {
                match listener.accept() {
                    Ok((stream, _)) => break stream,
                    Err(error)
                        if error.kind() == std::io::ErrorKind::WouldBlock
                            && started.elapsed() < Duration::from_secs(3) =>
                    {
                        std::thread::sleep(Duration::from_millis(10))
                    }
                    _ => return Err("WS handshake fixture accept failed"),
                }
            };
            stream
                .set_read_timeout(Some(Duration::from_secs(2)))
                .map_err(|_| "WS handshake fixture timeout failed")?;
            let mut bytes = [0u8; 4096];
            let _ = stream
                .read(&mut bytes)
                .map_err(|_| "WS handshake fixture read failed")?;
            stream
                .write_all(response.as_bytes())
                .map_err(|_| "WS handshake fixture send failed")
        });
        let error = provider(endpoint)
            .transcribe_pcm_bytes(&vec![0u8; TARGET_AUDIO_CHUNK_BYTES])
            .err()
            .unwrap_or_default();
        worker
            .join()
            .map_err(|_| "WS handshake fixture thread failed")??;
        check(
            name,
            error.contains(expected)
                && !error.contains("network-probe-secret")
                && !error.contains("127.0.0.1")
                && matches!(redirect_target.accept(), Err(error) if error.kind() == std::io::ErrorKind::WouldBlock),
        )?;
    }
    Ok(checks)
}

#[cfg(test)]
mod tests {
    #[test]
    fn production_websocket_paths_reject_incomplete_and_unsafe_results() {
        assert_eq!(super::verify().unwrap().len(), 12);
    }

    #[test]
    fn saved_hourly_meeting_sends_larger_packets_without_changing_pcm() {
        use super::*;

        let pcm: Vec<u8> = (0..13_800).map(|index| (index % 251) as u8).collect();
        for (saved, expected_lengths) in [
            (true, vec![6_400, 6_400, 1_000]),
            (false, vec![3_200, 3_200, 3_200, 3_200, 1_000]),
        ] {
            let final_frame = server_frame(r#"{"result":{"text":"Controlled final"}}"#, true);
            let (endpoint, worker) = fixture_with_audio(vec![final_frame], Some((pcm.clone(), expected_lengths))).unwrap();
            let mut client = provider(endpoint);
            client.credentials.resource_id = "volc.bigasr.sauc.duration".into();
            let result = if saved {
                client.transcribe_saved_meeting_pcm_bytes(&pcm)
            } else {
                client.transcribe_pcm_bytes(&pcm)
            };
            worker.join().unwrap().unwrap();
            assert_eq!(result.unwrap().0, "Controlled final");
        }
    }

    #[test]
    fn saved_hourly_meeting_rejects_reported_short_finals() {
        use super::*;

        let cases = [
            (vec![server_frame(r#"{"result":{"text":"a misleading partial"},"audio_info":{"duration":96}}"#, true)], false),
            (vec![server_frame(r#"{"result":{"additions":{}},"audio_info":{"duration":96}}"#, true)], false),
            (vec![
                server_frame(r#"{"result":{"text":"a misleading partial"},"audio_info":{"duration":96}}"#, true),
                server_frame(r#"{"result":{"text":"Full text"},"audio_info":{"duration":199}}"#, true),
            ], true),
        ];
        for (frames, expect_full) in cases {
            let (endpoint, worker) = fixture(frames).unwrap();
            let mut client = provider(endpoint);
            client.credentials.resource_id = HOURLY_V1_RESOURCE.into();
            let result = client.transcribe_saved_meeting_pcm_bytes(&vec![0; SAVED_MEETING_AUDIO_CHUNK_BYTES]);
            worker.join().unwrap().unwrap();
            if expect_full {
                assert_eq!(result.unwrap().0, "Full text");
            } else {
                let error = result.unwrap_err();
                assert!(error.contains("covers less audio"));
                assert!(!is_no_speech_error(&error));
            }
        }
    }

    #[test]
    fn saved_hourly_profile_accounts_for_head_speech_parameter() {
        use super::*;

        let mut client = provider("ws://127.0.0.1:9".into());
        assert_eq!(client.saved_meeting_cache_configuration(), client.cache_configuration());
        client.credentials.resource_id = HOURLY_V1_RESOURCE.into();
        let baseline = client.cache_configuration();
        let saved = client.saved_meeting_cache_configuration();
        assert!(baseline["payload"]["request"].get("force_to_speech_time").is_none());
        assert_eq!(saved["payload"]["request"]["force_to_speech_time"], json!(500));
        assert!(client.session_payload("live")["request"].get("force_to_speech_time").is_none());
        let mut wire = client.session_payload("");
        configure_saved_meeting_head(&mut wire);
        assert_eq!(wire["request"], saved["payload"]["request"]);
    }
}
