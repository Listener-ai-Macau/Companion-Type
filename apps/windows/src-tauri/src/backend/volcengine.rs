//! Companion-Type Volcengine SAUC bigmodel ASR adapter.
//!
//! Batch wrapper over the Volcengine streaming SAUC WebSocket protocol
//! (`wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async`). Reads a
//! 16 kHz / 16-bit / mono WAV, streams its PCM to the provider in 100 ms
//! frames, sends a negative-sequence end frame, and returns the final
//! transcript text. Companion-Type is a "record-then-transcribe" batch host,
//! so this intentionally omits the partial-callback / cadence / hotword /
//! cancel machinery the Listener dictation path needs.
//!
//! Protocol ported from Listener-Type (`asr/volcengine.rs` + `asr/frame.rs`),
//! trimmed to the batch `transcribe_file` shape. The binary frame codec below
//! is a verbatim copy of Listener's `frame.rs` (renamed to avoid collisions).

use std::path::Path;
use std::time::Duration;

use futures::{SinkExt, StreamExt};
use serde_json::{json, Value};
use tokio::sync::oneshot;
use tokio_tungstenite::connect_async;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::header::HeaderValue;
use tokio_tungstenite::tungstenite::Message;
use uuid::Uuid;

const SAUC_ENDPOINT: &str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async";
/// 100 ms of 16 kHz / 16-bit / mono PCM.
const TARGET_AUDIO_CHUNK_BYTES: usize = 3_200;
const FINAL_RESULT_TIMEOUT: Duration = Duration::from_secs(30);
const WEBSOCKET_SEND_TIMEOUT: Duration = Duration::from_millis(2_000);

// ===========================================================================
// Binary frame codec — verbatim port of Listener asr/frame.rs.
// ===========================================================================

const HEADER_BYTE_0: u8 = 0x11;
const COMPRESSION_NONE: u8 = 0b0000;

#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum MessageType {
    FullClientRequest = 0b0001,
    AudioOnlyRequest = 0b0010,
    FullServerResponse = 0b1001,
    ErrorMessage = 0b1111,
}

impl MessageType {
    fn from_raw(raw: u8) -> Option<Self> {
        match raw {
            0b0001 => Some(Self::FullClientRequest),
            0b0010 => Some(Self::AudioOnlyRequest),
            0b1001 => Some(Self::FullServerResponse),
            0b1111 => Some(Self::ErrorMessage),
            _ => None,
        }
    }
}

#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Flags {
    None = 0b0000,
    PositiveSequence = 0b0001,
    LastPacket = 0b0010,
    NegativeSequence = 0b0011,
}

#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Serialization {
    None = 0b0000,
    Json = 0b0001,
}

#[derive(Debug, Clone)]
struct ParsedFrame {
    message_type: Option<MessageType>,
    flags: u8,
    sequence: Option<i32>,
    error_code: Option<u32>,
    payload: Vec<u8>,
}

impl ParsedFrame {
    fn is_final(&self) -> bool {
        self.flags == Flags::LastPacket as u8
            || self.flags == Flags::NegativeSequence as u8
            || self.sequence.unwrap_or(0) < 0
    }
}

fn frame_build(
    message_type: MessageType,
    flags: Flags,
    serialization: Serialization,
    payload: &[u8],
    sequence: Option<i32>,
) -> Vec<u8> {
    let mut frame = Vec::with_capacity(4 + 4 + 4 + payload.len());
    frame.push(HEADER_BYTE_0);
    frame.push(((message_type as u8) << 4) | (flags as u8));
    frame.push(((serialization as u8) << 4) | COMPRESSION_NONE);
    frame.push(0x00);

    let needs_seq = matches!(flags, Flags::PositiveSequence | Flags::NegativeSequence);
    if needs_seq {
        if let Some(seq) = sequence {
            frame.extend_from_slice(&seq.to_be_bytes());
        }
    }

    let size: u32 = payload.len() as u32;
    frame.extend_from_slice(&size.to_be_bytes());
    frame.extend_from_slice(payload);
    frame
}

fn frame_parse(data: &[u8]) -> Option<ParsedFrame> {
    if data.len() < 8 {
        return None;
    }

    let header_size = (data[0] & 0x0F) as usize * 4;
    if header_size < 4 || data.len() < header_size + 4 {
        return None;
    }

    let message_type_raw = (data[1] >> 4) & 0x0F;
    let message_type = MessageType::from_raw(message_type_raw);
    let flags_raw = data[1] & 0x0F;
    let compression = data[2] & 0x0F;
    if compression != COMPRESSION_NONE {
        return None;
    }

    let mut offset = header_size;
    let mut sequence: Option<i32> = None;

    if has_sequence(flags_raw) {
        let value = read_i32(data, offset)?;
        sequence = Some(value);
        offset += 4;
    }

    if message_type == Some(MessageType::ErrorMessage) {
        let code = read_u32(data, offset)?;
        let message_size = read_u32(data, offset + 4)? as usize;
        offset += 8;
        if data.len() < offset + message_size {
            return None;
        }
        let payload = data[offset..offset + message_size].to_vec();
        return Some(ParsedFrame {
            message_type,
            flags: flags_raw,
            sequence,
            error_code: Some(code),
            payload,
        });
    }

    let payload_size = read_u32(data, offset)? as usize;
    offset += 4;
    if data.len() < offset + payload_size {
        return None;
    }
    let payload = data[offset..offset + payload_size].to_vec();
    Some(ParsedFrame {
        message_type,
        flags: flags_raw,
        sequence,
        error_code: None,
        payload,
    })
}

fn has_sequence(flags: u8) -> bool {
    flags == Flags::PositiveSequence as u8 || flags == Flags::NegativeSequence as u8
}

fn read_u32(data: &[u8], offset: usize) -> Option<u32> {
    if data.len() < offset + 4 {
        return None;
    }
    let bytes: [u8; 4] = data[offset..offset + 4].try_into().ok()?;
    Some(u32::from_be_bytes(bytes))
}

fn read_i32(data: &[u8], offset: usize) -> Option<i32> {
    let unsigned = read_u32(data, offset)?;
    Some(unsigned as i32)
}

// ===========================================================================
// Credentials + batch client.
// ===========================================================================

#[derive(Clone, Debug)]
pub struct VolcengineCredentials {
    pub app_id: String,
    pub access_token: String,
    pub resource_id: String,
}

impl VolcengineCredentials {
    pub fn default_resource_id() -> &'static str {
        "volc.bigasr.sauc.duration"
    }
}

/// Batch Volcengine SAUC transcriber. Stateless; construct per transcription.
pub struct VolcengineSaucAsr {
    credentials: VolcengineCredentials,
    endpoint: String,
}

impl VolcengineSaucAsr {
    pub fn new(credentials: VolcengineCredentials) -> Self {
        Self {
            credentials,
            endpoint: SAUC_ENDPOINT.to_string(),
        }
    }

    /// Read a 16 kHz / mono / 16-bit WAV, stream its PCM to Volcengine SAUC,
    /// and return the final transcript text.
    pub fn transcribe_file(&self, wav_path: &Path) -> Result<String, String> {
        let pcm = read_pcm16k_mono_wav(wav_path)?;
        // The transcription path is normally reached from a Tauri
        // spawn_blocking thread (no runtime context). Be defensive anyway: if
        // a caller already holds a tokio runtime, reuse it via block_in_place
        // instead of panicking on nested runtime creation.
        if let Ok(handle) = tokio::runtime::Handle::try_current() {
            return tokio::task::block_in_place(move || handle.block_on(self.transcribe_pcm(&pcm)));
        }
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .worker_threads(2)
            .enable_all()
            .build()
            .map_err(|e| format!("build tokio runtime: {e}"))?;
        runtime.block_on(self.transcribe_pcm(&pcm))
    }

    async fn transcribe_pcm(&self, pcm: &[u8]) -> Result<String, String> {
        if pcm.is_empty() {
            return Err("Volcengine ASR received empty PCM".to_string());
        }
        let connect_id = Uuid::new_v4().to_string();

        let mut request = self
            .endpoint
            .as_str()
            .into_client_request()
            .map_err(|e| format!("build ws request: {e}"))?;
        let headers = request.headers_mut();
        headers.insert(
            "X-Api-App-Key",
            HeaderValue::from_str(&self.credentials.app_id)
                .map_err(|e| format!("app key header: {e}"))?,
        );
        headers.insert(
            "X-Api-Access-Key",
            HeaderValue::from_str(&self.credentials.access_token)
                .map_err(|e| format!("access key header: {e}"))?,
        );
        headers.insert(
            "X-Api-Resource-Id",
            HeaderValue::from_str(&self.credentials.resource_id)
                .map_err(|e| format!("resource id header: {e}"))?,
        );
        headers.insert(
            "X-Api-Connect-Id",
            HeaderValue::from_str(&connect_id).map_err(|e| format!("connect id header: {e}"))?,
        );

        let (ws, _resp) = connect_async(request)
            .await
            .map_err(classify_connect_error)?;
        let (mut write, mut read) = ws.split();

        // 1. First frame: FullClientRequest with session config (seq = 1).
        let payload = build_first_frame_payload(&connect_id);
        let payload_bytes = serde_json::to_vec(&payload)
            .map_err(|e| format!("encode session config json: {e}"))?;
        let first_frame = frame_build(
            MessageType::FullClientRequest,
            Flags::PositiveSequence,
            Serialization::Json,
            &payload_bytes,
            Some(1),
        );
        send_binary(&mut write, first_frame)
            .await
            .map_err(|e| format!("send session config: {e}"))?;

        // 2. Spawn the receive loop. It collects the best transcript text and
        //    resolves once the server signals the final frame (or errors).
        let (final_tx, final_rx) = oneshot::channel::<Result<String, String>>();
        tokio::spawn(async move {
            let outcome = run_receive_loop(&mut read).await;
            let _ = final_tx.send(outcome);
        });

        // 3. Stream PCM in 100 ms AudioOnlyRequest frames (positive sequence).
        let mut seq: i32 = 2; // seq=1 was consumed by the config frame.
        for chunk in pcm.chunks(TARGET_AUDIO_CHUNK_BYTES) {
            let frame = frame_build(
                MessageType::AudioOnlyRequest,
                Flags::PositiveSequence,
                Serialization::None,
                chunk,
                Some(seq),
            );
            send_binary(&mut write, frame)
                .await
                .map_err(|e| format!("send audio seq={seq}: {e}"))?;
            seq = seq.wrapping_add(1);
            // Pace near real-time (~100 ms per 3200-byte frame). The SAUC
            // bigmodel_async server ends the session if it does not receive the
            // next audio packet within ~8 s; fast-bursting a long recording
            // starves its VAD timeline and aborts with "timeout waiting next
            // packet". Short clips survive a burst, long ones do not.
            tokio::time::sleep(Duration::from_millis(100)).await;
        }

        // 4. End-of-stream frame: NegativeSequence + negative seq signals end.
        //    The seq must be -(next positive seq) — one past the last audio
        //    frame's seq — matching the server's auto-assigned counter. A fixed
        //    -1 is rejected with "autoAssignedSequence mismatch".
        let last_frame = frame_build(
            MessageType::AudioOnlyRequest,
            Flags::NegativeSequence,
            Serialization::None,
            &[],
            Some(-seq),
        );
        send_binary(&mut write, last_frame)
            .await
            .map_err(|e| format!("send end-of-stream frame: {e}"))?;

        // 5. Await the final transcript (bounded). Do NOT close the write
        //    half here — the server still has to emit its final response,
        //    and a premature close makes it drop the transcript.
        match tokio::time::timeout(FINAL_RESULT_TIMEOUT, final_rx).await {
            Ok(Ok(Ok(text))) => Ok(text),
            Ok(Ok(Err(e))) => Err(e),
            Ok(Err(_)) => Err("Volcengine final-result channel closed".to_string()),
            Err(_) => Err(format!(
                "Volcengine final result timed out after {} s",
                FINAL_RESULT_TIMEOUT.as_secs()
            )),
        }
    }
}

async fn run_receive_loop(
    read: &mut futures::stream::SplitStream<tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>>,
) -> Result<String, String> {
    let mut best_text = String::new();
    let mut saw_final = false;
    while let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Binary(data)) => {
                let Some(parsed) = frame_parse(&data) else {
                    continue;
                };
                if parsed.message_type == Some(MessageType::ErrorMessage) {
                    let body = String::from_utf8_lossy(&parsed.payload).to_string();
                    return Err(format!(
                        "Volcengine ASR error code={:?}: {}",
                        parsed.error_code,
                        body.chars().take(300).collect::<String>()
                    ));
                }
                if parsed.message_type == Some(MessageType::FullServerResponse) {
                    if let Ok(json) = serde_json::from_slice::<Value>(&parsed.payload) {
                        if let Some(text) = extract_text(&json) {
                            if !text.is_empty() {
                                best_text = text;
                            }
                        }
                    }
                    if parsed.is_final() {
                        saw_final = true;
                        break;
                    }
                }
            }
            Ok(Message::Close(_)) => break,
            Ok(_) => { /* ignore text / ping / pong */ }
            Err(e) => return Err(format!("Volcengine receive loop error: {e}")),
        }
    }
    if !best_text.is_empty() {
        Ok(best_text)
    } else if saw_final {
        Err("Volcengine returned a final frame with no transcript text".to_string())
    } else {
        Err("Volcengine connection closed without a final result".to_string())
    }
}

async fn send_binary(
    write: &mut futures::stream::SplitSink<
        tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>,
        Message,
    >,
    data: Vec<u8>,
) -> Result<(), tokio_tungstenite::tungstenite::Error> {
    tokio::time::timeout(WEBSOCKET_SEND_TIMEOUT, write.send(Message::Binary(data)))
        .await
        .map_err(|_| {
            tokio_tungstenite::tungstenite::Error::AlreadyClosed
        })??;
    Ok(())
}

fn build_first_frame_payload(connect_id: &str) -> Value {
    json!({
        "user": { "uid": connect_id },
        "audio": {
            "format": "pcm",
            "rate": 16000,
            "bits": 16,
            "channel": 1,
            "codec": "raw",
        },
        "request": {
            "model_name": "bigmodel",
            "enable_nonstream": false,
            "enable_itn": true,
            "enable_punc": true,
            "show_utterances": true,
            "result_type": "full",
        }
    })
}

/// Pull the transcript text out of a server response, mirroring Listener's
/// `volcengine_transcript::normalized_result`: prefer `result.text`, fall
/// back to top-level `text`.
fn extract_text(json: &Value) -> Option<String> {
    let result = if let Some(r) = json.get("result") {
        if r.is_object() {
            r
        } else if let Some(arr) = r.as_array() {
            arr.first()?
        } else {
            return None;
        }
    } else if json.get("text").and_then(|v| v.as_str()).is_some() {
        json
    } else {
        return None;
    };
    result
        .get("text")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

fn read_pcm16k_mono_wav(path: &Path) -> Result<Vec<u8>, String> {
    let bytes =
        std::fs::read(path).map_err(|e| format!("read wav {}: {e}", path.display()))?;
    if bytes.len() < 44 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return Err(format!(
            "not a RIFF/WAVE file: {}",
            path.display()
        ));
    }
    // Walk chunks to find fmt + data. PCM fmt fields are at fixed offsets
    // inside the fmt chunk body.
    let mut offset = 12;
    let mut fmt: Option<(u16, u32, u16)> = None; // channels, sample_rate, bits
    let mut data: Option<(usize, usize)> = None; // start, len
    while offset + 8 <= bytes.len() {
        let id = &bytes[offset..offset + 4];
        let size = u32::from_le_bytes([
            bytes[offset + 4],
            bytes[offset + 5],
            bytes[offset + 6],
            bytes[offset + 7],
        ]) as usize;
        let body = offset + 8;
        if id == b"fmt " && body + 16 <= bytes.len() {
            let channels = u16::from_le_bytes([bytes[body + 2], bytes[body + 3]]);
            let sample_rate = u32::from_le_bytes([
                bytes[body + 4],
                bytes[body + 5],
                bytes[body + 6],
                bytes[body + 7],
            ]);
            let bits = u16::from_le_bytes([bytes[body + 14], bytes[body + 15]]);
            fmt = Some((channels, sample_rate, bits));
        } else if id == b"data" {
            let end = (body + size).min(bytes.len());
            data = Some((body, end - body));
            break;
        }
        offset = body + size + (size & 1);
    }
    if let Some((channels, sample_rate, bits)) = fmt {
        if channels != 1 || sample_rate != 16000 || bits != 16 {
            return Err(format!(
                "Volcengine SAUC needs 16 kHz / mono / 16-bit PCM WAV, got {} ch / {} Hz / {} bits ({}).",
                channels,
                sample_rate,
                bits,
                path.display()
            ));
        }
    }
    let (start, size) = data.ok_or_else(|| "WAV has no data chunk".to_string())?;
    let end = (start + size).min(bytes.len());
    Ok(bytes[start..end].to_vec())
}

fn classify_connect_error(err: tokio_tungstenite::tungstenite::Error) -> String {
    use tokio_tungstenite::tungstenite::Error as WsError;
    if let WsError::Http(resp) = &err {
        let status = resp.status().as_u16();
        if status == 401 || status == 403 {
            return format!(
                "Volcengine auth rejected (HTTP {status}). Check COMPANION_TYPE_VOLC_APP_KEY / COMPANION_TYPE_VOLC_ACCESS_KEY and that the SAUC resource is enabled for this account."
            );
        }
    }
    format!("Volcengine ws connect failed: {err}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frame_round_trip_audio_last_packet_is_final() {
        let frame = frame_build(
            MessageType::AudioOnlyRequest,
            Flags::LastPacket,
            Serialization::None,
            &[],
            None,
        );
        let parsed = frame_parse(&frame).expect("frame should parse");
        assert_eq!(parsed.message_type, Some(MessageType::AudioOnlyRequest));
        assert!(parsed.is_final());
    }

    #[test]
    fn frame_round_trip_full_client_request_positive_sequence() {
        let payload = br#"{"hello":"world"}"#;
        let frame = frame_build(
            MessageType::FullClientRequest,
            Flags::PositiveSequence,
            Serialization::Json,
            payload,
            Some(1),
        );
        let parsed = frame_parse(&frame).expect("frame should parse");
        assert_eq!(parsed.sequence, Some(1));
        assert_eq!(parsed.payload, payload);
        assert!(!parsed.is_final());
    }

    #[test]
    fn extract_text_prefers_result_text() {
        let v = serde_json::from_str::<Value>(
            r#"{"result":{"text":"会议纪要","duration_ms":1000}}"#,
        )
        .unwrap();
        assert_eq!(extract_text(&v).as_deref(), Some("会议纪要"));
    }

    #[test]
    fn extract_text_falls_back_to_top_level_text() {
        let v = serde_json::from_str::<Value>(r#"{"text":"fallback"}"#).unwrap();
        assert_eq!(extract_text(&v).as_deref(), Some("fallback"));
    }

    #[test]
    fn read_pcm_rejects_non_wav() {
        let dir = std::env::temp_dir().join("companion-type-volcengine-test");
        let _ = std::fs::create_dir_all(&dir);
        let path = dir.join("not-a-wav.bin");
        std::fs::write(&path, b"definitely not a wav").unwrap();
        let err = read_pcm16k_mono_wav(&path).unwrap_err();
        assert!(err.contains("not a RIFF/WAVE file"));
    }

    /// Real-network smoke test. Disabled by default; run with the three
    /// Volcengine credentials set as env vars and a path to a real
    /// 16 kHz / mono / 16-bit WAV:
    ///
    /// ```sh
    /// $env:COMPANION_TYPE_VOLC_APP_KEY='<appKey from Listener vault>'
    /// $env:COMPANION_TYPE_VOLC_ACCESS_KEY='<accessKey>'
    /// $env:COMPANION_TYPE_VOLC_RESOURCE_ID='volc.bigasr.sauc.duration'
    /// $env:COMPANION_TYPE_VOLC_PROBE_WAV='<path to mechanical-meeting.wav>'
    /// cargo test --manifest-path apps/windows/src-tauri/Cargo.toml --lib \
    ///   volcengine_transcribes_real_wav -- --ignored --nocapture
    /// ```
    #[test]
    #[ignore = "requires real Volcengine credentials + a real WAV (env-driven)"]
    fn volcengine_transcribes_real_wav() {
        let app_key = std::env::var("COMPANION_TYPE_VOLC_APP_KEY").expect("APP_KEY");
        let access_key = std::env::var("COMPANION_TYPE_VOLC_ACCESS_KEY").expect("ACCESS_KEY");
        let resource_id = std::env::var("COMPANION_TYPE_VOLC_RESOURCE_ID")
            .unwrap_or_else(|_| VolcengineCredentials::default_resource_id().to_string());
        let wav = std::env::var("COMPANION_TYPE_VOLC_PROBE_WAV").expect("PROBE_WAV");

        let asr = VolcengineSaucAsr::new(VolcengineCredentials {
            app_id: app_key,
            access_token: access_key,
            resource_id,
        });
        let text = asr.transcribe_file(Path::new(&wav)).expect("real transcript");
        assert!(!text.trim().is_empty(), "transcript must be non-empty");
        eprintln!("volcengine_real_transcript={}", text);
    }

    /// Mechanical-voice physical-microphone end-to-end, mirroring Listener's
    /// `run_mechanical_voice_diagnostic.ps1` (case a1/a2): SAPI synthesizes a
    /// natural passage, plays it through the **speaker**, the **physical
    /// microphone** records it via HostRecordingManager, the Volcengine
    /// provider transcribes the recording, and we assert (a) the mic captured
    /// non-silent audio (peak > 500, proving it heard the speaker not just room
    /// noise) and (b) the transcript covers the stimulus text (LCS char ratio).
    ///
    /// This is the "mechanical voice simulates a person speaking, runs the
    /// whole physical chain" AI evidence — distinct from probe (which feeds a
    /// WAV directly to the provider, bypassing the microphone) and from the
    /// human signoff (which requires a real human voice).
    #[test]
    #[ignore = "requires real Volcengine credentials + speaker + physical microphone"]
    fn mechanical_voice_physical_microphone_e2e() {
        let app_key = std::env::var("COMPANION_TYPE_VOLC_APP_KEY").expect("COMPANION_TYPE_VOLC_APP_KEY");
        let access_key =
            std::env::var("COMPANION_TYPE_VOLC_ACCESS_KEY").expect("COMPANION_TYPE_VOLC_ACCESS_KEY");
        let resource_id = std::env::var("COMPANION_TYPE_VOLC_RESOURCE_ID")
            .unwrap_or_else(|_| VolcengineCredentials::default_resource_id().to_string());
        let stimulus = std::env::var("COMPANION_TYPE_MECH_STIMULUS").unwrap_or_else(|_| {
            // Chinese passage + Huihui (zh-CN TTS): the Volcengine bigmodel is
            // strongly zh-biased, so an English SAPI voice gets misrecognized
            // as Chinese near-homophones after speaker->air->mic loss. A zh
            // stimulus matches the provider's strong language.
            "决定：会议主机负责记录今天的整场讨论。行动：陈明在周五之前完成纪要验证。问题：物理麦克风链路是否已经为正式会议做好准备。".to_string()
        });
        let record_seconds: u64 = std::env::var("COMPANION_TYPE_MECH_RECORD_SECONDS")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(12);

        let asr = VolcengineSaucAsr::new(VolcengineCredentials {
            app_id: app_key,
            access_token: access_key,
            resource_id,
        });

        // 1. SAPI-synthesize + play the stimulus through the speaker.
        // Pass the stimulus to the child pwsh via env (avoids -Command quoting
        // issues with free-form English text — `--` + the passage was parsed
        // as a PowerShell statement and never reached $args[0]).
        std::env::set_var("COMPANION_TYPE_MECH_STIMULUS", &stimulus);
        let sapi_script = "Add-Type -AssemblyName System.Speech; \
            $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; \
            try { $s.SelectVoice('Microsoft Huihui Desktop') } catch {}; \
            $s.Rate = 2; \
            $p = Join-Path $env:TEMP 'companion-type-mech-stimulus.wav'; \
            $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono); \
            $s.SetOutputToWaveFile($p, $fmt); \
            $s.Speak($env:COMPANION_TYPE_MECH_STIMULUS); \
            $s.Dispose(); \
            (New-Object Media.SoundPlayer $p).PlaySync()";
        let mut sapi = std::process::Command::new("pwsh")
            .args(["-NoProfile", "-Command", sapi_script])
            .spawn()
            .expect("spawn pwsh SAPI playback");

        // 2. Record via HostRecordingManager (physical microphone).
        std::env::set_var("COMPANION_TYPE_HOST_RECORDING_MODE", "real");
        std::thread::sleep(std::time::Duration::from_millis(400)); // let the speaker ramp up
        let recorder = crate::backend::host_recording::HostRecordingManager::new();
        let _start = recorder
            .start("mech-e2e", "Mechanical Voice E2E")
            .expect("host recording start");
        std::thread::sleep(std::time::Duration::from_secs(record_seconds));
        let stop = recorder
            .stop(Some("mech-e2e"))
            .expect("host recording stop")
            .expect("active recording was expected");
        let _ = sapi.wait();

        // 3. Assert the microphone captured non-silent audio (peak > 500).
        let recorded = std::fs::read(&stop.path).expect("read recorded wav");
        let (peak, rms) = pcm_peak_rms(&recorded);
        assert!(
            peak > 500,
            "microphone captured near-silent audio (peak={peak}, rms={rms:.1}); check speaker is playing / mic is the default input"
        );

        // 4. Transcribe the recorded WAV via Volcengine.
        let transcript = asr
            .transcribe_file(&stop.path)
            .expect("volcengine transcript of the microphone recording");

        // 5. Coverage: LCS char ratio of normalized transcript vs stimulus.
        let expected = normalize_text(&stimulus);
        let actual = normalize_text(&transcript);
        let coverage = lcs_ratio(&expected, &actual);

        eprintln!("mech_e2e_stimulus={}", stimulus);
        eprintln!("mech_e2e_transcript={}", transcript);
        eprintln!(
            "mech_e2e_peak={} rms={} duration_ms={} coverage={:.3}",
            peak, rms, stop.duration_ms, coverage
        );

        assert!(!transcript.trim().is_empty(), "transcript is empty");
        assert!(
            coverage >= 0.55,
            "transcript coverage {coverage:.3} below 0.55 threshold; transcript={transcript}"
        );
    }

    fn normalize_text(text: &str) -> String {
        text.chars()
            .filter(|c| c.is_alphanumeric())
            .collect::<String>()
            .to_lowercase()
    }

    fn lcs_ratio(expected: &str, actual: &str) -> f64 {
        if expected.is_empty() {
            return 0.0;
        }
        let e: Vec<char> = expected.chars().collect();
        let a: Vec<char> = actual.chars().collect();
        let mut prev = vec![0usize; a.len() + 1];
        for ec in &e {
            let mut cur = vec![0usize; a.len() + 1];
            for (j, ac) in a.iter().enumerate() {
                cur[j + 1] = if ec == ac { prev[j] + 1 } else { prev[j + 1].max(cur[j]) };
            }
            prev = cur;
        }
        prev[a.len()] as f64 / e.len() as f64
    }

    fn pcm_peak_rms(wav: &[u8]) -> (i32, f64) {
        if wav.len() < 12 || &wav[0..4] != b"RIFF" {
            return (0, 0.0);
        }
        let mut offset = 12usize;
        let mut data: Option<(usize, usize)> = None;
        while offset + 8 <= wav.len() {
            let id = &wav[offset..offset + 4];
            let size = u32::from_le_bytes([
                wav[offset + 4],
                wav[offset + 5],
                wav[offset + 6],
                wav[offset + 7],
            ]) as usize;
            let body = offset + 8;
            if id == b"data" {
                let end = (body + size).min(wav.len());
                data = Some((body, end - body));
                break;
            }
            offset = body + size + (size & 1);
        }
        let (start, len) = match data {
            Some(d) => d,
            None => return (0, 0.0),
        };
        let end = (start + len).min(wav.len());
        let mut peak: i32 = 0;
        let mut sum_sq: f64 = 0.0;
        let mut n: u64 = 0;
        let mut i = start;
        while i + 1 < end {
            let s = i16::from_le_bytes([wav[i], wav[i + 1]]) as i32;
            let a = s.abs();
            if a > peak {
                peak = a;
            }
            sum_sq += (s as f64) * (s as f64);
            n += 1;
            i += 2;
        }
        let rms = if n > 0 { (sum_sq / n as f64).sqrt() } else { 0.0 };
        (peak, rms)
    }
}
