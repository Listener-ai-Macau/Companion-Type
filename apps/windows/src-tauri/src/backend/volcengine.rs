//! Companion-Type Volcengine SAUC bigmodel ASR adapter.
//!
//! Batch + live streaming wrappers over the Volcengine SAUC WebSocket protocol
//! (`wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async` for the
//! purchased Seed ASR 2.0 hourly service). Seed 2.0 still uses its v2 framing
//! contract even though this account's enabled route carries the `_async`
//! suffix; the `/bigmodel` route rejects this resource at handshake time.
//! - Batch: read a 16 kHz mono WAV, stream PCM, return final text.
//! - Live (`stream_pcm_session`): accept PCM frames while recording and emit
//!   provisional hypotheses via callback for `onlineLive`.
//! **Meeting hotwords** are sent in first-frame `request.corpus.context`.
//!
//! Protocol ported from Listener-Type (`asr/volcengine.rs` + `asr/frame.rs`),
//! trimmed to the batch `transcribe_file` shape. The binary frame codec below
//! is a verbatim copy of Listener's `frame.rs` (renamed to avoid collisions).

use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use futures::{SinkExt, StreamExt};
use serde_json::{json, Value};
use tokio::sync::oneshot;
use tokio_tungstenite::connect_async_with_config;
use tokio_tungstenite::tungstenite::protocol::WebSocketConfig;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::header::HeaderValue;
use tokio_tungstenite::tungstenite::protocol::frame::coding::CloseCode;
use tokio_tungstenite::tungstenite::Message;
use uuid::Uuid;

const SAUC_ENDPOINT_ASYNC: &str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async";
const SAUC_ENDPOINT_NOSTREAM: &str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream";
pub(super) const HOURLY_V1_RESOURCE: &str = "volc.bigasr.sauc.duration";
/// 100 ms of 16 kHz / 16-bit / mono PCM.
const TARGET_AUDIO_CHUNK_BYTES: usize = 3_200;
const SAVED_MEETING_AUDIO_CHUNK_BYTES: usize = 6_400;
pub(super) const SAVED_HOURLY_WINDOW_SECONDS: usize = 60;
const MAX_ACCELERATED_MEETING_PCM_BYTES: usize = SAVED_HOURLY_WINDOW_SECONDS * 32_000;
const FINAL_RESULT_TIMEOUT: Duration = Duration::from_secs(30);
const WEBSOCKET_SEND_TIMEOUT: Duration = Duration::from_millis(2_000);
const WEBSOCKET_CONNECT_TIMEOUT: Duration = Duration::from_secs(8);
const WEBSOCKET_MAX_RESPONSE_BYTES: usize = 4 * 1024 * 1024;
const BATCH_REQUEST_MAX_DURATION: Duration = Duration::from_secs(3 * 60 * 60);
pub(super) const NO_SPEECH_ERROR: &str = "Volcengine ASR completed without recognized speech";

async fn await_live_session<F>(future: F) -> Result<String, String>
where F: std::future::Future<Output = Result<String, String>> {
    // A live session lasts until capture ends or the provider reports an error.
    // Connection, individual sends and the final response have separate bounds.
    future.await
}

pub(super) fn is_no_speech_error(error: &str) -> bool {
    error.ends_with(NO_SPEECH_ERROR)
}

mod network_probe;
pub(super) use network_probe::verify as verify_network;

struct ReceiveTask<T>(tokio::task::JoinHandle<T>);
impl<T> Drop for ReceiveTask<T> {
    fn drop(&mut self) { self.0.abort(); }
}

async fn connect_bounded(request: tokio_tungstenite::tungstenite::http::Request<()>) -> Result<(
    tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>,
    tokio_tungstenite::tungstenite::handshake::client::Response,
), String> {
    let config = WebSocketConfig { max_message_size: Some(WEBSOCKET_MAX_RESPONSE_BYTES),
        max_frame_size: Some(WEBSOCKET_MAX_RESPONSE_BYTES), ..WebSocketConfig::default() };
    // This API connects only to the supplied endpoint; it does not retry
    // HTTP redirects. Bound DNS/TCP/TLS/handshake and allocated frame bodies.
    tokio::time::timeout(WEBSOCKET_CONNECT_TIMEOUT, connect_async_with_config(request, Some(config), false))
        .await.map_err(|_| "Volcengine connection timed out".to_string())?
        .map_err(classify_connect_error)
}

fn safe_ws_error(error: tokio_tungstenite::tungstenite::Error) -> &'static str {
    use tokio_tungstenite::tungstenite::Error;
    match error {
        Error::Capacity(_) => "Volcengine response exceeds size limit",
        Error::Io(error) if error.kind() == std::io::ErrorKind::TimedOut => "Volcengine connection timed out",
        Error::Protocol(_) | Error::Utf8 => "Volcengine response protocol invalid",
        _ => "Volcengine network connection failed",
    }
}

fn safe_provider_error(code: Option<u32>) -> String {
    format!("Volcengine ASR error code={}", code.map(|code| code.to_string()).unwrap_or_else(|| "unknown".into()))
}
/// Cap hotwords sent per request (Volcengine supports thousands; keep small for latency).
const HOTWORD_CAP: usize = 64;

/// Ordinary customer recordings have no assumed meeting topic or people.
/// Domain terms can still be supplied explicitly via COMPANION_TYPE_ASR_HOTWORDS.
const DEFAULT_MEETING_HOTWORDS: &[&str] = &[];

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
    if data.len() < 8 || data.len() > WEBSOCKET_MAX_RESPONSE_BYTES || data[0] >> 4 != 1 {
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
        if data.len() != offset + message_size {
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
    if data.len() != offset + payload_size {
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

/// Read Volc credentials from Companion product env (settings apply into env).
pub fn credentials_from_env() -> Option<VolcengineCredentials> {
    let app_id = std::env::var("COMPANION_TYPE_VOLC_APP_KEY")
        .ok()
        .filter(|s| !s.trim().is_empty())?;
    let access_token = std::env::var("COMPANION_TYPE_VOLC_ACCESS_KEY")
        .ok()
        .filter(|s| !s.trim().is_empty())?;
    let resource_id = std::env::var("COMPANION_TYPE_VOLC_RESOURCE_ID")
        .ok()
        .filter(|s| !s.trim().is_empty())
        .unwrap_or_else(|| VolcengineCredentials::default_resource_id().to_string());
    Some(VolcengineCredentials {
        app_id,
        access_token,
        resource_id,
    })
}

/// Batch Volcengine SAUC transcriber. Stateless; construct per transcription.
pub struct VolcengineSaucAsr {
    credentials: VolcengineCredentials,
    endpoint: String,
    // Freeze the effective request (including hotwords) with the credentials.
    // Cache identity and the request on the wire must describe the same run.
    payload_template: Value,
}

impl VolcengineSaucAsr {
    /// Dedicated runtime bounds the complete probe and drops any receive task
    /// on timeout. Called only by the explicit service-test blocking worker.
    pub(crate) fn probe_silent_audio(&self) -> Result<(), String> {
        let runtime = tokio::runtime::Builder::new_multi_thread().worker_threads(1)
            .enable_all().build().map_err(|_| "build connection test runtime")?;
        runtime.block_on(async {
            let silence = vec![0u8; 32_000];
            tokio::time::timeout(
                Duration::from_secs(25),
                self.transcribe_pcm_inner(&silence, true, TARGET_AUDIO_CHUNK_BYTES, None),
            ).await
                .map_err(|_| "connection test timed out".to_string())?
                .map(|_| ())
        })
    }
    pub fn new(credentials: VolcengineCredentials) -> Self {
        let endpoint = endpoint_for_resource(&credentials.resource_id).to_string();
        let payload_template = build_first_frame_payload(
            "", is_seed_asr_v2(&credentials.resource_id), &companion_meeting_hotwords(),
        );
        Self {
            credentials,
            endpoint,
            payload_template,
        }
    }

    pub(crate) fn cache_configuration(&self) -> Value {
        // Do not put credentials or unredacted account/hotword data in a
        // persisted profile. The cache layer hashes this effective request.
        let mut configuration = json!({
            "provider": "volcengine-sauc",
            // Old cached results may have discarded a words-only utterance.
            // Parser policy belongs in cache identity even when the request is unchanged.
            "response_parser": "utterance-text-or-complete-word-tokens-v2",
            "endpoint": self.endpoint,
            "resource": self.credentials.resource_id,
            "model": if is_seed_asr_v2(&self.credentials.resource_id) { "seed-asr-v2" } else { "bigmodel" },
            "language": "auto",
            "account": self.credentials.app_id,
            "payload": self.payload_template,
        });
        if self.credentials.resource_id.eq_ignore_ascii_case(HOURLY_V1_RESOURCE) {
            // A cached older final may have explicitly covered only part of the clip.
            configuration["final_audio_coverage"] = json!("reported-duration-v1");
        }
        configuration
    }

    fn session_payload(&self, connect_id: &str) -> Value {
        let mut payload = self.payload_template.clone();
        payload["user"]["uid"] = Value::String(connect_id.to_string());
        if is_seed_asr_v2(&self.credentials.resource_id) {
            payload["request"]["reqid"] = Value::String(connect_id.to_string());
        }
        payload
    }

    /// Live streaming session: read PCM frames from `pcm_rx` until the channel
    /// closes or `stop` is set, call `on_partial` for each non-empty hypothesis,
    /// return the best final text.
    pub fn stream_pcm_session<F>(
        &self,
        pcm_rx: std::sync::mpsc::Receiver<Vec<u8>>,
        stop: Arc<AtomicBool>,
        on_partial: F,
    ) -> Result<String, String>
    where
        F: FnMut(&str) + Send + 'static,
    {
        if let Ok(handle) = tokio::runtime::Handle::try_current() {
            return tokio::task::block_in_place(move || {
                handle.block_on(await_live_session(self.stream_pcm_session_async(pcm_rx, stop, on_partial)))
            });
        }
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .worker_threads(2)
            .enable_all()
            .build()
            .map_err(|e| format!("build tokio runtime: {e}"))?;
        runtime.block_on(await_live_session(self.stream_pcm_session_async(pcm_rx, stop, on_partial)))
    }

    async fn stream_pcm_session_async<F>(
        &self,
        pcm_rx: std::sync::mpsc::Receiver<Vec<u8>>,
        stop: Arc<AtomicBool>,
        mut on_partial: F,
    ) -> Result<String, String>
    where
        F: FnMut(&str) + Send + 'static,
    {
        let connect_id = Uuid::new_v4().to_string();
        let seed_v2 = is_seed_asr_v2(&self.credentials.resource_id);
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
        if seed_v2 {
            // Seed ASR 2.0's SAUC v2 handshake accepts the App Key and also
            // expects the explicit App Id header. They are the same console
            // value for Companion's token-based credentials.
            headers.insert(
                "X-Api-App-Id",
                HeaderValue::from_str(&self.credentials.app_id)
                    .map_err(|e| format!("app id header: {e}"))?,
            );
        }
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

        let (ws, _resp) = connect_bounded(request).await?;
        let (mut write, mut read) = ws.split();

        let payload = self.session_payload(&connect_id);
        let payload_bytes =
            serde_json::to_vec(&payload).map_err(|e| format!("encode session config json: {e}"))?;
        let first_frame = frame_build(
            MessageType::FullClientRequest,
            if seed_v2 {
                Flags::None
            } else {
                Flags::PositiveSequence
            },
            Serialization::Json,
            &payload_bytes,
            if seed_v2 { None } else { Some(1) },
        );
        send_binary(&mut write, first_frame)
            .await
            .map_err(|error| safe_ws_error(error).to_string())?;

        let best = Arc::new(std::sync::Mutex::new(String::new()));
        let best_r = Arc::clone(&best);
        let (final_tx, mut final_rx) = oneshot::channel::<Result<(), String>>();
        let audio_ended = Arc::new(AtomicBool::new(false));
        let audio_ended_r = Arc::clone(&audio_ended);
        let _receiver_task = ReceiveTask(tokio::spawn(async move {
            let outcome = run_receive_loop_live(&mut read, |text| {
                if text.is_empty() {
                    return;
                }
                if let Ok(mut b) = best_r.lock() {
                    *b = text.to_string();
                }
                // Publish on reception, including while waiting for the final
                // result after microphone upload has stopped.
                on_partial(text);
            }, audio_ended_r)
            .await;
            let _ = final_tx.send(outcome);
        }));

        // Drain PCM: accumulate to 100 ms frames, pace mildly to keep session alive.
        let mut seq: i32 = 2;
        let mut pending = Vec::<u8>::with_capacity(TARGET_AUDIO_CHUNK_BYTES * 2);
        loop {
            // The service can reject the stream while the microphone keeps
            // producing. Do not wait for STOP before surfacing that failure.
            match final_rx.try_recv() {
                Ok(Err(error)) => return Err(error),
                Ok(Ok(())) => return Err("Volcengine live result ended before recording input".into()),
                Err(oneshot::error::TryRecvError::Closed) => return Err("Volcengine live final channel closed".into()),
                Err(oneshot::error::TryRecvError::Empty) => {}
            }
            if stop.load(Ordering::SeqCst) {
                // The recorder has stopped producing. Drain every already
                // accepted buffer before sending EOS so the final transcript
                // covers the same tail as the saved original audio.
                match pcm_rx.try_recv() {
                    Ok(chunk) => pending.extend_from_slice(&chunk),
                    Err(std::sync::mpsc::TryRecvError::Empty | std::sync::mpsc::TryRecvError::Disconnected) => break,
                }
            } else {
                match pcm_rx.recv_timeout(Duration::from_millis(50)) {
                    Ok(chunk) => pending.extend_from_slice(&chunk),
                    Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {}
                    Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => break,
                }
            }
            while pending.len() >= TARGET_AUDIO_CHUNK_BYTES {
                let frame_bytes: Vec<u8> = pending.drain(..TARGET_AUDIO_CHUNK_BYTES).collect();
                let frame = frame_build(
                    MessageType::AudioOnlyRequest,
                    if seed_v2 {
                        Flags::None
                    } else {
                        Flags::PositiveSequence
                    },
                    Serialization::None,
                    &frame_bytes,
                    if seed_v2 { None } else { Some(seq) },
                );
                if let Err(error) = send_binary(&mut write, frame).await {
                    return Err(safe_ws_error(error).to_string());
                }
                seq = seq.wrapping_add(1);
                tokio::time::sleep(Duration::from_millis(20)).await;
            }
        }
        // Flush remainder.
        // Seed v2 marks the last audio packet itself (flags=2, no sequence).
        // The legacy async route instead expects an empty negative-sequence
        // packet whose sequence is one past the last positive audio packet.
        let (last_payload, last_flags, last_sequence) = if seed_v2 {
            (pending.as_slice(), Flags::LastPacket, None)
        } else {
            if !pending.is_empty() {
                let frame = frame_build(
                    MessageType::AudioOnlyRequest,
                    Flags::PositiveSequence,
                    Serialization::None,
                    &pending,
                    Some(seq),
                );
                send_binary(&mut write, frame)
                    .await
                    .map_err(|error| safe_ws_error(error).to_string())?;
                seq = seq.wrapping_add(1);
            }
            (&[][..], Flags::NegativeSequence, Some(-seq))
        };
        let last_frame = frame_build(
            MessageType::AudioOnlyRequest,
            last_flags,
            Serialization::None,
            last_payload,
            last_sequence,
        );
        audio_ended.store(true, Ordering::Release);
        send_binary(&mut write, last_frame)
            .await
            .map_err(|error| safe_ws_error(error).to_string())?;

        match tokio::time::timeout(FINAL_RESULT_TIMEOUT, final_rx).await {
            Ok(Ok(Ok(()))) => {}
            Ok(Ok(Err(e))) => return Err(e),
            Ok(Err(_)) => return Err("Volcengine live final channel closed".to_string()),
            Err(_) => return Err("Volcengine live final result timed out; partial text retained".to_string()),
        }
        let text = best.lock().map(|t| t.clone()).unwrap_or_default();
        if text.is_empty() {
            Err("Volcengine live session produced empty transcript".to_string())
        } else {
            Ok(text)
        }
    }

    /// Read a 16 kHz / mono / 16-bit WAV, stream its PCM to Volcengine SAUC,
    /// and return the final transcript text plus the timed utterances (when
    /// the server returns them). The utterances carry start/end ms so the
    /// caller can align them against diarization speaker segments.
    pub fn transcribe_file(&self, wav_path: &Path) -> Result<(String, Vec<Utterance>), String> {
        let pcm = read_pcm16k_mono_wav(wav_path)?;
        self.transcribe_pcm_bytes(&pcm)
    }

    pub(crate) fn transcribe_pcm_bytes(&self, pcm: &[u8]) -> Result<(String, Vec<Utterance>), String> {
        self.transcribe_pcm_with_packet_bytes(pcm, TARGET_AUDIO_CHUNK_BYTES, None)
    }

    /// Pace each owned saved-meeting chunk at the verified rate. Cached audio
    /// identity and recognition parameters are independent of packet size.
    pub(crate) fn transcribe_saved_meeting_pcm_bytes(&self, pcm: &[u8]) -> Result<(String, Vec<Utterance>), String> {
        let hourly_v1 = self.credentials.resource_id.eq_ignore_ascii_case(HOURLY_V1_RESOURCE);
        let packet_bytes = saved_meeting_packet_bytes(hourly_v1, pcm.len());
        self.transcribe_pcm_with_packet_bytes(pcm, packet_bytes, hourly_v1.then_some(pcm.len() as u64 / 32))
    }

    fn transcribe_pcm_with_packet_bytes(&self, pcm: &[u8], packet_bytes: usize, expected_duration_ms: Option<u64>) -> Result<(String, Vec<Utterance>), String> {
        let deadline = Duration::from_secs((pcm.len() as u64 / 32_000).saturating_add(60)).min(BATCH_REQUEST_MAX_DURATION);
        // The transcription path is normally reached from a Tauri
        // spawn_blocking thread (no runtime context). Be defensive anyway: if
        // a caller already holds a tokio runtime, reuse it via block_in_place
        // instead of panicking on nested runtime creation.
        if let Ok(handle) = tokio::runtime::Handle::try_current() {
            return tokio::task::block_in_place(move || handle.block_on(async {
                tokio::time::timeout(deadline, self.transcribe_pcm_inner(pcm, false, packet_bytes, expected_duration_ms)).await
                    .map_err(|_| "Volcengine request timed out".to_string())?
            }));
        }
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .worker_threads(2)
            .enable_all()
            .build()
            .map_err(|e| format!("build tokio runtime: {e}"))?;
        runtime.block_on(async { tokio::time::timeout(deadline, self.transcribe_pcm_inner(pcm, false, packet_bytes, expected_duration_ms)).await
            .map_err(|_| "Volcengine request timed out".to_string())? })
    }

    async fn transcribe_pcm_inner(&self, pcm: &[u8], probe: bool, packet_bytes: usize, expected_duration_ms: Option<u64>) -> Result<(String, Vec<Utterance>), String> {
        if pcm.is_empty() {
            return Err("Volcengine ASR received empty PCM".to_string());
        }
        let connect_id = Uuid::new_v4().to_string();
        let seed_v2 = is_seed_asr_v2(&self.credentials.resource_id);

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
        if seed_v2 {
            headers.insert(
                "X-Api-App-Id",
                HeaderValue::from_str(&self.credentials.app_id)
                    .map_err(|e| format!("app id header: {e}"))?,
            );
        }
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

        let (ws, _resp) = connect_bounded(request).await?;
        let (mut write, mut read) = ws.split();

        // 1. First frame: FullClientRequest with session config (seq = 1).
        let mut payload = self.session_payload(&connect_id);
        if probe {
            if let Some(request) = payload.get_mut("request").and_then(Value::as_object_mut) { request.remove("context"); }
        }
        let payload_bytes =
            serde_json::to_vec(&payload).map_err(|e| format!("encode session config json: {e}"))?;
        let first_frame = frame_build(
            MessageType::FullClientRequest,
            if seed_v2 {
                Flags::None
            } else {
                Flags::PositiveSequence
            },
            Serialization::Json,
            &payload_bytes,
            if seed_v2 { None } else { Some(1) },
        );
        send_binary(&mut write, first_frame)
            .await
            .map_err(|error| safe_ws_error(error).to_string())?;

        // 2. Spawn the receive loop. It collects the best transcript text and
        //    resolves once the server signals the final frame (or errors).
        let (final_tx, mut final_rx) = oneshot::channel::<Result<(String, Vec<Utterance>), String>>();
        let audio_ended = Arc::new(AtomicBool::new(false));
        let audio_ended_r = Arc::clone(&audio_ended);
        let _receiver_task = ReceiveTask(tokio::spawn(async move {
            let outcome = run_receive_loop(&mut read, probe, audio_ended_r, expected_duration_ms).await;
            let _ = final_tx.send(outcome);
        }));

        // 3. Stream PCM in consecutive AudioOnlyRequest frames.
        let mut seq: i32 = 2; // seq=1 was consumed by the config frame.
        let chunks: Vec<&[u8]> = pcm.chunks(packet_bytes).collect();
        for (index, chunk) in chunks.iter().enumerate() {
            let seed_last = seed_v2 && index + 1 == chunks.len();
            if seed_last {
                audio_ended.store(true, Ordering::Release);
            }
            let frame = frame_build(
                MessageType::AudioOnlyRequest,
                if seed_last {
                    Flags::LastPacket
                } else if seed_v2 {
                    Flags::None
                } else {
                    Flags::PositiveSequence
                },
                Serialization::None,
                chunk,
                if seed_v2 { None } else { Some(seq) },
            );
            send_binary(&mut write, frame)
                .await
                .map_err(|error| safe_ws_error(error).to_string())?;
            seq = seq.wrapping_add(1);
            // Keep a 100 ms cadence even for larger saved-meeting packets.
            // Unpaced upload has previously caused incomplete cloud results.
            tokio::select! {
                outcome = &mut final_rx => {
                    return outcome.map_err(|_| "Volcengine final-result channel closed".to_string())?;
                }
                _ = tokio::time::sleep(Duration::from_millis(100)) => {}
            }
        }

        // 4. End-of-stream frame: NegativeSequence + negative seq signals end.
        //    The seq must be -(next positive seq) — one past the last audio
        //    frame's seq — matching the server's auto-assigned counter. A fixed
        //    -1 is rejected with "autoAssignedSequence mismatch".
        if !seed_v2 {
            let last_frame = frame_build(
                MessageType::AudioOnlyRequest,
                Flags::NegativeSequence,
                Serialization::None,
                &[],
                Some(-seq),
            );
            audio_ended.store(true, Ordering::Release);
            send_binary(&mut write, last_frame)
                .await
                .map_err(|error| safe_ws_error(error).to_string())?;
        }

        // 5. Await the final transcript (bounded). Do NOT close the write
        //    half here — the server still has to emit its final response,
        //    and a premature close makes it drop the transcript.
        match tokio::time::timeout(FINAL_RESULT_TIMEOUT, final_rx).await {
            Ok(Ok(Ok(pair))) => Ok(pair),
            Ok(Ok(Err(e))) => Err(e),
            Ok(Err(_)) => Err("Volcengine final-result channel closed".to_string()),
            Err(_) => Err(format!(
                "Volcengine final result timed out after {} s",
                FINAL_RESULT_TIMEOUT.as_secs()
            )),
        }
    }
}

fn saved_meeting_packet_bytes(hourly_v1: bool, pcm_len: usize) -> usize {
    if hourly_v1 && pcm_len <= MAX_ACCELERATED_MEETING_PCM_BYTES {
        SAVED_MEETING_AUDIO_CHUNK_BYTES
    } else {
        TARGET_AUDIO_CHUNK_BYTES
    }
}

fn endpoint_for_resource(resource_id: &str) -> &'static str {
    if is_seed_asr_v2(resource_id) {
        SAUC_ENDPOINT_NOSTREAM
    } else {
        SAUC_ENDPOINT_ASYNC
    }
}

fn is_seed_asr_v2(resource_id: &str) -> bool {
    resource_id
        .trim()
        .to_ascii_lowercase()
        .starts_with("volc.seedasr.sauc.")
}

fn explicit_empty_recognition(json: &Value, text: Option<&str>) -> bool {
    if let Some(text) = text { return text.trim().is_empty(); }
    // Observed Seed response: after EOS it returns only result.additions and
    // audio_info.duration, without a text field. The preceding control frame
    // has the same additions but no audio_info; that is not a final result.
    let Some(result) = json.get("result").and_then(Value::as_object) else { return false; };
    result.len() == 1 && result.get("additions").is_some_and(Value::is_object)
        && json.get("audio_info").and_then(|audio| audio.get("duration"))
            .and_then(Value::as_u64).is_some_and(|duration| duration > 0)
}

async fn run_receive_loop<S>(
    read: &mut S,
    allow_silent_probe: bool,
    audio_ended: Arc<AtomicBool>,
    expected_duration_ms: Option<u64>,
) -> Result<(String, Vec<Utterance>), String>
where S: futures::Stream<Item = Result<Message, tokio_tungstenite::tungstenite::Error>> + Unpin,
{
    let mut empty_final_after_audio = false;
    let mut premature_text_final = false;
    let mut shortened_final = false;
    while let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Binary(data)) => {
                let Some(parsed) = frame_parse(&data) else {
                    return Err("Volcengine response protocol invalid".into());
                };
                if parsed.message_type == Some(MessageType::ErrorMessage) {
                    return Err(safe_provider_error(parsed.error_code));
                }
                if parsed.message_type == Some(MessageType::FullServerResponse) {
                    if parsed.payload.is_empty() { continue; }
                    let json = serde_json::from_slice::<Value>(&parsed.payload)
                        .map_err(|_| "Volcengine response protocol invalid")?;
                    if json.get("error").is_some() { return Err(safe_provider_error(None)); }
                    let text = extract_text(&json);
                    let response_has_content = text.as_ref().is_some_and(|text| !text.trim().is_empty());
                    if !allow_silent_probe && std::env::var("COMPANION_TYPE_VOLC_TRACE_FRAMES").as_deref() == Ok("1") {
                        eprintln!(
                            "volc_frame type=server flags={} sequence={:?} payload_bytes={} content={} audio_ended={} result_object={} result_array={} result_keys={:?} text_field={} audio_info={}",
                            parsed.flags,
                            parsed.sequence,
                            parsed.payload.len(),
                            response_has_content,
                            audio_ended.load(Ordering::Acquire),
                            json.get("result").is_some_and(Value::is_object),
                            json.get("result").is_some_and(Value::is_array),
                            result_object(&json).and_then(Value::as_object).map(|object|
                                ["text", "utterances", "additions"].into_iter().filter(|key| object.contains_key(*key)).collect::<Vec<_>>()),
                            result_object(&json).is_some_and(|object| object.get("text").is_some()),
                            json.get("audio_info").is_some_and(Value::is_object),
                        );
                    }
                    // A transcript cannot complete before all owned audio was
                    // submitted. Ignore premature finals; a later post-EOS final
                    // may replace them, otherwise report incomplete recognition.
                    if parsed.is_final() && !audio_ended.load(Ordering::Acquire) {
                        premature_text_final |= response_has_content;
                        continue;
                    }
                    // Seed v2 can emit empty control frames carrying a final
                    // flag while the audio stream is still active. Treating
                    // those as the session result races long inputs and
                    // produces the misleading "final frame with no text".
                    let explicit_empty = parsed.is_final() && explicit_empty_recognition(&json, text.as_deref());
                    if parsed.is_final() && (response_has_content || explicit_empty) &&
                        reported_duration_is_short(&json, expected_duration_ms)
                    {
                        shortened_final = true;
                        continue;
                    }
                    if parsed.is_final() && (response_has_content || (allow_silent_probe && text.is_some())) {
                        // A final frame is authoritative. Never combine it
                        // with text or speaker timings from an earlier partial.
                        return Ok((text.unwrap_or_default(), extract_utterances(&json)));
                    }
                    if explicit_empty && audio_ended.load(Ordering::Acquire) {
                        // Seed may send an empty control final even after EOS,
                        // followed by the real result. Wait for that result or
                        // a normal close; a timeout/transport error stays an
                        // incomplete recognition rather than hiding failures.
                        empty_final_after_audio = true;
                    }
                }
            }
            Ok(Message::Close(frame)) => {
                if frame.is_some_and(|frame| frame.code != CloseCode::Normal) {
                    return Err("Volcengine service closed before a valid final result".into());
                }
                break;
            }
            Ok(_) => { /* ignore text / ping / pong */ }
            Err(error) => return Err(safe_ws_error(error).to_string()),
        }
    }
    if premature_text_final { return Err("Volcengine final arrived before complete audio input".into()); }
    if shortened_final { return Err("Volcengine final covers less audio than the saved recording; original audio preserved".into()); }
    if empty_final_after_audio { return Err(NO_SPEECH_ERROR.into()); }
    Err(if allow_silent_probe { "connection test closed without a valid final response" }
        else { "Volcengine connection closed without a final result" }.into())
}

fn reported_duration_is_short(json: &Value, expected_ms: Option<u64>) -> bool {
    let reported = json.get("audio_info")
        .and_then(|audio| value_millis(audio, &["duration"]))
        .and_then(|duration| u64::try_from(duration).ok());
    // The provider exposes integer milliseconds. Permit one millisecond of
    // rounding, and keep compatibility with responses without audio metadata.
    matches!((reported, expected_ms), (Some(actual), Some(expected)) if actual.saturating_add(1) < expected)
}

/// Live receive loop: notify on every non-empty hypothesis; exit on final/close.
async fn run_receive_loop_live<S, F>(
    read: &mut S,
    mut on_text: F,
    audio_ended: Arc<AtomicBool>,
) -> Result<(), String>
where
    F: FnMut(&str),
    S: futures::Stream<Item = Result<Message, tokio_tungstenite::tungstenite::Error>> + Unpin,
{
    let mut empty_final_after_audio = false;
    let mut premature_text_final = false;
    while let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Binary(data)) => {
                let Some(parsed) = frame_parse(&data) else {
                    return Err("Volcengine response protocol invalid".into());
                };
                if parsed.message_type == Some(MessageType::ErrorMessage) {
                    return Err(safe_provider_error(parsed.error_code));
                }
                if parsed.message_type == Some(MessageType::FullServerResponse) {
                    if parsed.payload.is_empty() { continue; }
                    let json = serde_json::from_slice::<Value>(&parsed.payload)
                        .map_err(|_| "Volcengine response protocol invalid")?;
                    if json.get("error").is_some() { return Err(safe_provider_error(None)); }
                    let text = extract_text(&json);
                    if parsed.is_final() && !audio_ended.load(Ordering::Acquire) {
                        premature_text_final |= text.as_ref().is_some_and(|text| !text.trim().is_empty());
                        continue; // An early terminal is not a live hypothesis.
                    }
                    if let Some(text) = text.as_ref().filter(|text| !text.trim().is_empty()) {
                        on_text(&text);
                        if parsed.is_final() { return Ok(()); }
                    }
                    if parsed.is_final() && explicit_empty_recognition(&json, text.as_deref()) &&
                       audio_ended.load(Ordering::Acquire) {
                        empty_final_after_audio = true;
                    }
                }
            }
            Ok(Message::Close(frame)) => {
                if frame.is_some_and(|frame| frame.code != CloseCode::Normal) {
                    return Err("Volcengine service closed before a valid final result".into());
                }
                break;
            }
            Ok(_) => {}
            Err(error) => return Err(safe_ws_error(error).to_string()),
        }
    }
    if premature_text_final { return Err("Volcengine final arrived before complete audio input".into()); }
    if empty_final_after_audio { return Err(NO_SPEECH_ERROR.into()); }
    Err("Volcengine connection closed without a final result".into())
}

async fn send_binary(
    write: &mut futures::stream::SplitSink<
        tokio_tungstenite::WebSocketStream<
            tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
        >,
        Message,
    >,
    data: Vec<u8>,
) -> Result<(), tokio_tungstenite::tungstenite::Error> {
    tokio::time::timeout(WEBSOCKET_SEND_TIMEOUT, write.send(Message::Binary(data)))
        .await
        .map_err(|_| tokio_tungstenite::tungstenite::Error::Io(std::io::Error::new(
            std::io::ErrorKind::TimedOut, "send timed out")))??;
    Ok(())
}

/// Encode the JSON string carried by the first request's corpus context.
fn hotword_context(words: &[String]) -> Option<String> {
    let mut seen: Vec<String> = Vec::new();
    for w in words {
        let trimmed = w.trim();
        if trimmed.is_empty() {
            continue;
        }
        if seen.iter().any(|s| s.eq_ignore_ascii_case(trimmed)) {
            continue;
        }
        seen.push(trimmed.to_string());
        if seen.len() >= HOTWORD_CAP {
            break;
        }
    }
    if seen.is_empty() {
        return None;
    }
    let words: Vec<Value> = seen.into_iter().map(|w| json!({ "word": w })).collect();
    serde_json::to_string(&json!({ "hotwords": words })).ok()
}

/// Default product hotwords + optional `COMPANION_TYPE_ASR_HOTWORDS` (comma-separated).
/// Set `COMPANION_TYPE_ASR_HOTWORDS=none` (or `0` / `off`) to disable for A/B.
pub fn companion_meeting_hotwords() -> Vec<String> {
    if let Ok(extra) = std::env::var("COMPANION_TYPE_ASR_HOTWORDS") {
        let t = extra.trim();
        if t.eq_ignore_ascii_case("none") || t.eq_ignore_ascii_case("off") || t == "0" {
            return Vec::new();
        }
    }
    let mut out: Vec<String> = DEFAULT_MEETING_HOTWORDS
        .iter()
        .map(|s| (*s).to_string())
        .collect();
    if let Ok(extra) = std::env::var("COMPANION_TYPE_ASR_HOTWORDS") {
        for part in extra.split(|c| c == ',' || c == ';' || c == '\n') {
            let t = part.trim();
            if t.is_empty() {
                continue;
            }
            if !out.iter().any(|s| s.eq_ignore_ascii_case(t)) {
                out.push(t.to_string());
            }
        }
    }
    out
}

fn build_first_frame_payload(connect_id: &str, seed_v2: bool, hotwords: &[String]) -> Value {
    let mut request = if seed_v2 {
        json!({
            "model_name": "bigmodel",
            "reqid": connect_id,
            "sequence": 1,
            "enable_itn": true,
            "enable_punc": true,
            "show_utterances": true,
            "enable_speaker_info": true,
            "additions": { "with_speaker_info": "True" },
            "result_type": "full",
        })
    } else {
        json!({
            "model_name": "bigmodel",
            // The async route requires the second pass and large-model SSD
            // together for speaker labels. A speaker-info flag on its own can
            // return every utterance as speaker 0 on a real multi-person file.
            // https://docs.volcengine.com/docs/doubao-voice/large-model-streaming-automatic-speech-recognition-api-1?lang=en
            "enable_nonstream": true,
            "ssd_version": "200",
            "enable_itn": true,
            "enable_punc": true,
            "show_utterances": true,
            "enable_speaker_info": true,
            "result_type": "full",
        })
    };
    if let Some(context) = hotword_context(hotwords) {
        request["corpus"] = json!({ "context": context });
    }
    if seed_v2 {
        json!({
            "user": { "uid": connect_id },
            "audio": {
                "format": "pcm",
                "rate": 16000,
                "sample_rate": 16000,
                "bits": 16,
                "channel": 1,
            },
            "request": request,
        })
    } else {
        json!({
            "user": { "uid": connect_id },
            "audio": {
                "format": "pcm",
                "rate": 16000,
                "bits": 16,
                "channel": 1,
                "codec": "raw",
            },
            "request": request,
        })
    }
}

/// One timed ASR utterance (text + millisecond bounds), used to align the
/// transcript against diarization speaker segments.
#[derive(Clone, Debug, PartialEq, Eq, serde::Deserialize, serde::Serialize)]
pub struct Utterance {
    pub text: String,
    pub start_ms: u64,
    pub end_ms: u64,
    /// Provider speaker label when the ASR product returned
    /// `utterance.additions.speaker`; kept as an opaque string because provider
    /// ids may be zero- or one-based.
    pub speaker: Option<String>,
}

/// Resolve the `result` object from a server response, mirroring Listener's
/// `volcengine_transcript::normalized_result`: unwrap `result` (object or
/// array-of-one), fall back to the top-level object when it carries `text`.
fn result_object(json: &Value) -> Option<&Value> {
    if let Some(r) = json.get("result") {
        if r.is_object() {
            return Some(r);
        }
        if let Some(arr) = r.as_array() {
            return arr.first();
        }
        return None;
    }
    if json.get("text").and_then(|v| v.as_str()).is_some() {
        return Some(json);
    }
    None
}

/// Pull the transcript text out of a server response: prefer `result.text`,
/// fall back to top-level `text`.
fn extract_text(json: &Value) -> Option<String> {
    let result = result_object(json)?;
    let original = result.get("text").and_then(Value::as_str).map(str::to_string);
    let Some(utterances) = result.get("utterances").and_then(Value::as_array) else {
        return original;
    };
    let mut explicit = String::new();
    let mut complete = String::new();
    let mut recovered = false;
    for utterance in utterances {
        if let Some(text) = utterance.get("text").and_then(Value::as_str).filter(|s| !s.trim().is_empty()) {
            explicit.push_str(text);
            complete.push_str(text);
        } else if let Some(text) = utterance_text(utterance) {
            complete.push_str(&text);
            recovered = true;
        } else if utterance.get("words").and_then(Value::as_array).is_some_and(|words| !words.is_empty()) {
            // A malformed token list cannot justify replacing the summary text.
            return original;
        }
    }
    if !complete.trim().is_empty() && (original.as_ref().is_none_or(|s| s.trim().is_empty())
        || recovered && text_signature(original.as_deref().unwrap_or_default()) == text_signature(&explicit)) {
        return Some(complete);
    }
    original
}

fn text_signature(text: &str) -> String {
    text.chars().filter(|c| c.is_alphanumeric()).flat_map(char::to_lowercase).collect()
}

/// Preserve the provider's formatted sentence when present. Some definite
/// two-pass results omit it but retain all timed word tokens: recover only
/// from that actual response, refusing partial/malformed token lists.
fn utterance_text(utterance: &Value) -> Option<String> {
    if let Some(text) = utterance.get("text").and_then(Value::as_str).filter(|s| !s.trim().is_empty()) {
        return Some(text.to_string());
    }
    let words = utterance.get("words")?.as_array()?;
    if words.is_empty() { return None; }
    let parts = words.iter().map(|word| word.get("text")?.as_str()).collect::<Option<Vec<_>>>()?;
    let text = parts.concat();
    (!text.trim().is_empty()).then_some(text)
}

/// Extract timed utterances from a server response. Ported from Listener's
/// `volcengine_transcript::transcript_segment_from_utterance`: the
/// utterance-level `start_time` can be stale, so prefer word-level timing
/// (`words[0].start_time` / `words[last].end_time`) and fall back to the
/// utterance-level fields. Timestamps are milliseconds and may arrive as int
/// or string. Utterances without usable timing are dropped.
fn extract_utterances(json: &Value) -> Vec<Utterance> {
    let Some(result) = result_object(json) else {
        return Vec::new();
    };
    let Some(utterances) = result.get("utterances").and_then(|v| v.as_array()) else {
        return Vec::new();
    };
    let start_keys = ["start_time", "startTime", "start_ms"];
    let end_keys = ["end_time", "endTime", "end_ms"];
    let mut out = Vec::new();
    for utt in utterances {
        let Some(text) = utterance_text(utt) else {
            continue;
        };
        let text = text.trim();
        if text.is_empty() {
            continue;
        }
        let Some(start_ms) = first_word_millis(utt, &start_keys)
            .or_else(|| value_millis(utt, &start_keys))
            .and_then(|ms| u64::try_from(ms.max(0)).ok())
        else {
            continue;
        };
        let end_ms = last_word_millis(utt, &end_keys)
            .or_else(|| value_millis(utt, &end_keys))
            .and_then(|ms| u64::try_from(ms.max(0)).ok())
            .unwrap_or(start_ms)
            .max(start_ms);
        out.push(Utterance {
            text: text.to_string(),
            start_ms,
            end_ms,
            speaker: utterance_speaker(utt),
        });
    }
    out
}

fn utterance_speaker(utterance: &Value) -> Option<String> {
    let direct = ["speaker", "speaker_id", "speakerId", "spk_id"]
        .iter()
        .find_map(|key| utterance.get(*key))
        .and_then(value_as_nonempty_string);
    if direct.is_some() {
        return direct;
    }
    let additions = utterance.get("additions")?;
    if let Some(value) = ["speaker", "speaker_id", "speakerId", "spk_id"]
        .iter()
        .find_map(|key| additions.get(*key))
        .and_then(value_as_nonempty_string)
    {
        return Some(value);
    }
    // Some gateways preserve `additions` as a JSON string.
    let parsed = serde_json::from_str::<Value>(additions.as_str()?).ok()?;
    ["speaker", "speaker_id", "speakerId", "spk_id"]
        .iter()
        .find_map(|key| parsed.get(*key))
        .and_then(value_as_nonempty_string)
}

fn value_as_nonempty_string(value: &Value) -> Option<String> {
    let text = match value {
        Value::String(text) => text.trim().to_string(),
        Value::Number(number) => number.to_string(),
        _ => return None,
    };
    (!text.is_empty()).then_some(text)
}

fn first_word_millis(value: &Value, keys: &[&str]) -> Option<i64> {
    value
        .get("words")
        .and_then(|words| words.as_array())
        .and_then(|words| words.iter().find_map(|word| value_millis(word, keys)))
}

fn last_word_millis(value: &Value, keys: &[&str]) -> Option<i64> {
    value
        .get("words")
        .and_then(|words| words.as_array())
        .and_then(|words| words.iter().rev().find_map(|word| value_millis(word, keys)))
}

fn value_millis(value: &Value, keys: &[&str]) -> Option<i64> {
    keys.iter()
        .filter_map(|key| value.get(*key))
        .find_map(value_as_i64)
}

fn value_as_i64(value: &Value) -> Option<i64> {
    if let Some(n) = value.as_i64() {
        return Some(n);
    }
    if let Some(n) = value.as_u64() {
        return i64::try_from(n).ok();
    }
    if let Some(n) = value.as_f64() {
        if n.is_finite() {
            return Some(n.round() as i64);
        }
    }
    value.as_str()?.trim().parse::<i64>().ok()
}

fn read_pcm16k_mono_wav(path: &Path) -> Result<Vec<u8>, String> {
    let bytes = std::fs::read(path).map_err(|e| format!("read wav {}: {e}", path.display()))?;
    if bytes.len() < 44 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return Err(format!("not a RIFF/WAVE file: {}", path.display()));
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
        return format!("Volcengine ws connect failed: HTTP {status}");
    }
    safe_ws_error(err).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn live_stream_does_not_end_at_three_hour_wall_clock_boundary() {
        let rt=tokio::runtime::Builder::new_current_thread().enable_all().start_paused(true).build().unwrap();
        rt.block_on(async {
            let (send,receive)=tokio::sync::oneshot::channel::<Result<String,String>>();
            let running=tokio::spawn(await_live_session(async move {receive.await.unwrap()}));
            tokio::task::yield_now().await;
            tokio::time::advance(Duration::from_secs(3*60*60+1)).await;
            tokio::task::yield_now().await;
            assert!(!running.is_finished(),"the active live stream was stopped by an elapsed-time limit");
            send.send(Ok("final after user stop".into())).unwrap();
            assert_eq!(running.await.unwrap().unwrap(),"final after user stop");
            let failure=await_live_session(async {Err("connection lost".to_string())}).await;
            assert_eq!(failure.unwrap_err(),"connection lost");
        });
    }


    #[test]
    fn eos_boundary_early_text_then_close_is_incomplete_not_no_speech() {
        let rt=tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
        let frame=|text:&str|Ok(Message::Binary(frame_build(MessageType::FullServerResponse,
            Flags::LastPacket,Serialization::Json,serde_json::to_vec(&json!({"result":{"text":text}})).unwrap().as_slice(),None)));
        rt.block_on(async {
            for late_empty in [false,true] { for live in [false,true] {
                let ended=Arc::new(AtomicBool::new(false));let flag=Arc::clone(&ended);
                let mut rows=vec![(false,frame("premature answer"))];
                if late_empty {rows.push((true,frame("")));}
                rows.push((late_empty,Ok(Message::Close(None))));
                let mut messages=futures::stream::iter(rows).map(move |(complete,msg)|{flag.store(complete,Ordering::Release);msg});
                let mut seen=Vec::new();
                let error=if live {run_receive_loop_live(&mut messages,|x|seen.push(x.to_string()),ended).await.unwrap_err()}
                    else {run_receive_loop(&mut messages,false,ended,None).await.unwrap_err()};
                assert!(seen.is_empty());assert!(!is_no_speech_error(&error));
                assert!(error.contains("before complete audio input"));
            }}
        });
    }

    #[test]
    fn eos_boundary_premature_text_final_cannot_complete_a_still_sending_input() {
        let rt=tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
        let frame=|text:&str|Ok(Message::Binary(frame_build(MessageType::FullServerResponse,
            Flags::LastPacket,Serialization::Json,serde_json::to_vec(&json!({"result":{"text":text}})).unwrap().as_slice(),None)));
        rt.block_on(async {
            for live in [false,true] {
                let ended=Arc::new(AtomicBool::new(false));let flag=Arc::clone(&ended);
                let mut messages=futures::stream::iter(vec![(false,frame("premature answer")),(true,frame("complete answer"))])
                    .map(move |(complete,msg)|{flag.store(complete,Ordering::Release);msg});
                if live {
                    let mut seen=Vec::new();run_receive_loop_live(&mut messages,|x|seen.push(x.to_string()),ended).await.unwrap();
                    assert_eq!(seen,["complete answer"],"early final text cannot be presented as a completed result");
                } else {
                    assert_eq!(run_receive_loop(&mut messages,false,ended,None).await.unwrap().0,"complete answer",
                        "early final cannot hide later complete text");
                }
            }
        });
    }


    #[test]
    fn eos_boundary_empty_terminal_requires_audio_end_and_valid_result_in_batch_and_live() {
        let runtime = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
        let response = |payload: &[u8]| Ok(Message::Binary(frame_build(
            MessageType::FullServerResponse, Flags::LastPacket, Serialization::Json, payload, None)));
        runtime.block_on(async {
            let empty = br#"{"result":{"text":""}}"#;
            let final_text = br#"{"result":{"text":"actual final text"}}"#;
            // Empty control finals before or after EOS cannot hide the real
            // final response. Only an explicit empty final + normal close is
            // a no-speech result.
            for initial_ended in [false, true] {
                for live in [false, true] {
                    let ended=Arc::new(AtomicBool::new(initial_ended));let flag=Arc::clone(&ended);
                    let mut messages=futures::stream::iter(vec![response(empty),response(final_text)])
                        .enumerate().map(move |(i,msg)|{if i==1 {flag.store(true,Ordering::Release);}msg});
                    if live {
                        let mut received=Vec::new();
                        run_receive_loop_live(&mut messages,|text|received.push(text.to_string()),ended).await.unwrap();
                        assert_eq!(received,["actual final text"]);
                    } else {assert_eq!(run_receive_loop(&mut messages,false,ended,None).await.unwrap().0,"actual final text");}
                }
            }

            let mut messages = futures::stream::iter(vec![response(empty)]);
            let error = run_receive_loop(&mut messages, false, Arc::new(AtomicBool::new(true)), None).await.unwrap_err();
            assert!(is_no_speech_error(&error));
            let mut messages = futures::stream::iter(vec![response(empty)]);
            assert!(is_no_speech_error(&run_receive_loop_live(&mut messages, |_| panic!("no partial text"),
                Arc::new(AtomicBool::new(true))).await.unwrap_err()));

            // A malformed/absent result or a mere close is still a protocol or
            // connection failure, even after upload. Silent probes remain separate.
            for body in [b"{}".as_slice(), empty] {
                let mut messages = futures::stream::iter(vec![response(body)]);
                let error = run_receive_loop(&mut messages, false, Arc::new(AtomicBool::new(false)), None).await.unwrap_err();
                assert!(!is_no_speech_error(&error));
            }
            let mut messages = futures::stream::iter(vec![response(b"{}")]);
            assert!(!is_no_speech_error(&run_receive_loop(&mut messages, false,
                Arc::new(AtomicBool::new(true)), None).await.unwrap_err()));
            let mut messages = futures::stream::iter(vec![response(empty)]);
            assert_eq!(run_receive_loop(&mut messages, true,
                Arc::new(AtomicBool::new(true)), None).await.unwrap().0, "");

            let metadata = br#"{"result":{"additions":{}},"audio_info":{"duration":21180}}"#;
            for body in [empty.as_slice(), metadata.as_slice()] {
                for ended in [false, true] {
                    let mut messages = futures::stream::iter(vec![response(body)]);
                    let error = run_receive_loop(&mut messages, false, Arc::new(AtomicBool::new(ended)), None).await.unwrap_err();
                    assert_eq!(is_no_speech_error(&error), ended);
                    let mut messages = futures::stream::iter(vec![response(body)]);
                    let error = run_receive_loop_live(&mut messages, |_| {}, Arc::new(AtomicBool::new(ended))).await.unwrap_err();
                    assert_eq!(is_no_speech_error(&error), ended);
                }
                let mut messages = futures::stream::iter(vec![response(body), response(final_text)]);
                assert_eq!(run_receive_loop(&mut messages, false, Arc::new(AtomicBool::new(true)), None).await.unwrap().0, "actual final text");
            }
            for body in [br#"{"result":{"additions":{}}}"#.as_slice(),
                         br#"{"result":{"additions":{}},"audio_info":{"duration":"unknown"}}"#,
                         br#"{"result":{"additions":{},"unknown":true},"audio_info":{"duration":100}}"#] {
                let mut messages = futures::stream::iter(vec![response(body)]);
                assert!(!is_no_speech_error(&run_receive_loop(&mut messages, false,
                    Arc::new(AtomicBool::new(true)), None).await.unwrap_err()));
            }

            for live in [false, true] {
                let mut messages = futures::stream::iter(vec![response(empty), response(b"invalid json")]);
                let error = if live {
                    run_receive_loop_live(&mut messages, |_| {}, Arc::new(AtomicBool::new(true))).await.unwrap_err()
                } else {
                    run_receive_loop(&mut messages, false, Arc::new(AtomicBool::new(true)), None).await.unwrap_err()
                };
                assert!(error.contains("protocol invalid") && !is_no_speech_error(&error));
            }
            // Provider overload/policy/abnormal shutdown after an empty
            // control final is not a completed quiet chunk. Only a normal
            // close may finish that result in either consumer path.
            for live in [false, true] {
                for code in [CloseCode::Normal, CloseCode::Away, CloseCode::Policy, CloseCode::Error] {
                    let close = Message::Close(Some(tokio_tungstenite::tungstenite::protocol::CloseFrame {
                        code, reason: "remote close reason is not transcript content".into(),
                    }));
                    let mut messages = futures::stream::iter(vec![response(empty), Ok(close)]);
                    let error = if live {
                        run_receive_loop_live(&mut messages, |_| {}, Arc::new(AtomicBool::new(true))).await.unwrap_err()
                    } else {
                        run_receive_loop(&mut messages, false, Arc::new(AtomicBool::new(true)), None).await.unwrap_err()
                    };
                    assert_eq!(is_no_speech_error(&error), code == CloseCode::Normal, "live={live} close={code:?}");
                }
            }
        });
    }

    #[test]
    fn cache_configuration_and_wire_request_share_a_frozen_hotword_snapshot() {
        let mut provider = VolcengineSaucAsr::new(VolcengineCredentials {
            app_id: "test-app".into(), access_token: "test-access-secret".into(),
            resource_id: "volc.seedasr.sauc.duration".into(),
        });
        let no_hotwords_payload = build_first_frame_payload("", true, &[]);
        provider.payload_template = build_first_frame_payload("", true, &["三元".into()]);
        let identity = provider.cache_configuration();
        let first = provider.session_payload("connection-one");
        let second = provider.session_payload("connection-two");
        assert_eq!(first["request"]["corpus"], identity["payload"]["request"]["corpus"]);
        assert_eq!(second["request"]["corpus"], identity["payload"]["request"]["corpus"]);
        assert_ne!(no_hotwords_payload, identity["payload"]);
        assert_eq!(identity["payload"]["request"]["corpus"]["context"], r#"{"hotwords":[{"word":"三元"}]}"#);
        assert_eq!(second["request"]["reqid"], "connection-two");
        assert_eq!(identity["payload"]["request"]["reqid"], "");
        assert_eq!(identity["payload"]["user"]["uid"], "");
        assert_eq!(identity, provider.cache_configuration());
        assert!(!identity.to_string().contains("test-access-secret"));
        let other_resource = VolcengineSaucAsr::new(VolcengineCredentials {
            app_id: "test-app".into(), access_token: "test-access-secret".into(),
            resource_id: "volc.bigasr.sauc.duration".into(),
        });
        assert_ne!(identity, other_resource.cache_configuration());
    }

    #[test]
    fn live_stop_drains_queued_pcm_before_final() {
        for resource in ["volc.bigasr.sauc.duration", "volc.seedasr.sauc.duration"] {
            let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
            let endpoint = format!("ws://{}", listener.local_addr().unwrap());
            listener.set_nonblocking(true).unwrap();
            let worker = std::thread::spawn(move || {
                let runtime = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
                runtime.block_on(async {
                    let listener = tokio::net::TcpListener::from_std(listener).unwrap();
                    let (stream, _) = listener.accept().await.unwrap();
                    let mut ws = tokio_tungstenite::accept_async(stream).await.unwrap();
                    let mut audio = Vec::new();
                    while let Some(message) = ws.next().await {
                        let Message::Binary(data) = message.unwrap() else { continue; };
                        let frame = frame_parse(&data).unwrap();
                        if frame.message_type == Some(MessageType::AudioOnlyRequest) {
                            audio.extend_from_slice(&frame.payload);
                            if frame.is_final() { break; }
                        }
                    }
                    ws.send(Message::Binary(frame_build(MessageType::FullServerResponse, Flags::LastPacket,
                        Serialization::Json, br#"{"result":{"text":"complete"}}"#, None))).await.unwrap();
                    audio
                })
            });
            let mut provider = VolcengineSaucAsr::new(VolcengineCredentials {
                app_id: "test-app".into(), access_token: "test-key".into(), resource_id: resource.into(),
            });
            provider.endpoint = endpoint;
            let (tx, rx) = std::sync::mpsc::channel();
            let mut expected = vec![1u8; TARGET_AUDIO_CHUNK_BYTES];
            expected.extend(vec![2u8; 1234]);
            tx.send(expected[..TARGET_AUDIO_CHUNK_BYTES].to_vec()).unwrap();
            tx.send(expected[TARGET_AUDIO_CHUNK_BYTES..].to_vec()).unwrap();
            drop(tx);
            let result = provider.stream_pcm_session(rx, Arc::new(AtomicBool::new(true)), |_| {});
            let actual = worker.join().unwrap();
            assert_eq!(result.unwrap(), "complete");
            assert_eq!(actual, expected, "queued PCM must be sent before final: {resource}");
        }
    }

    #[test]
    fn live_provider_error_is_reported_before_recording_stops() {
        let listener=std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint=format!("ws://{}",listener.local_addr().unwrap());listener.set_nonblocking(true).unwrap();
        let (sent_tx,sent_rx)=std::sync::mpsc::channel();
        let server=std::thread::spawn(move || {
            let rt=tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
            rt.block_on(async {
                let listener=tokio::net::TcpListener::from_std(listener).unwrap();
                let (stream,_)=listener.accept().await.unwrap();let mut ws=tokio_tungstenite::accept_async(stream).await.unwrap();
                assert!(matches!(ws.next().await.unwrap().unwrap(),Message::Binary(_)));
                ws.send(Message::Binary(frame_build(MessageType::FullServerResponse,Flags::None,Serialization::Json,
                    br#"{"result":{"text":"retained partial"}}"#,None))).await.unwrap();
                ws.send(Message::Binary(frame_build(MessageType::FullServerResponse,Flags::None,Serialization::Json,
                    br#"{"error":"synthetic failure"}"#,None))).await.unwrap();
                sent_tx.send(()).unwrap();tokio::time::sleep(Duration::from_millis(1800)).await;
            });
        });
        let mut provider=VolcengineSaucAsr::new(VolcengineCredentials{app_id:"test".into(),access_token:"test".into(),resource_id:"volc.seedasr.sauc.duration".into()});
        provider.endpoint=endpoint;let (pcm_tx,pcm_rx)=std::sync::mpsc::channel();let (result_tx,result_rx)=std::sync::mpsc::channel();
        let seen=Arc::new(std::sync::Mutex::new(String::new()));let callback=Arc::clone(&seen);
        let worker=std::thread::spawn(move || {
            let result=provider.stream_pcm_session(pcm_rx,Arc::new(AtomicBool::new(false)),move |text|*callback.lock().unwrap()=text.to_string());
            result_tx.send(result).unwrap();
        });
        sent_rx.recv_timeout(Duration::from_secs(5)).unwrap();
        let early=result_rx.recv_timeout(Duration::from_millis(900));let reported_before_stop=early.is_ok();
        drop(pcm_tx);let result=early.unwrap_or_else(|_|result_rx.recv_timeout(Duration::from_secs(5)).unwrap());
        worker.join().unwrap();server.join().unwrap();
        assert!(reported_before_stop,"service error remained hidden until recording stopped");
        assert!(result.is_err());assert_eq!(&*seen.lock().unwrap(),"retained partial");
    }

    #[test]
    fn saved_meeting_stops_upload_when_provider_rejects_request() {
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let endpoint = format!("ws://{}", listener.local_addr().unwrap());
        listener.set_nonblocking(true).unwrap();
        let server = std::thread::spawn(move || {
            let runtime = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
            runtime.block_on(async {
                let listener = tokio::net::TcpListener::from_std(listener).unwrap();
                let (stream, _) = listener.accept().await.unwrap();
                let mut socket = tokio_tungstenite::accept_async(stream).await.unwrap();
                assert!(matches!(socket.next().await.unwrap().unwrap(), Message::Binary(_)));
                let Message::Binary(first) = socket.next().await.unwrap().unwrap() else {
                    panic!("Expected the first audio packet");
                };
                assert_eq!(frame_parse(&first).unwrap().message_type, Some(MessageType::AudioOnlyRequest));
                socket.send(Message::Binary(frame_build(
                    MessageType::FullServerResponse, Flags::None, Serialization::Json,
                    br#"{"error":"synthetic failure"}"#, None,
                ))).await.unwrap();
                let mut packets_seen = 1;
                while let Ok(Some(Ok(Message::Binary(_)))) =
                    tokio::time::timeout(Duration::from_secs(2), socket.next()).await
                {
                    packets_seen += 1;
                }
                packets_seen
            })
        });
        let mut client = VolcengineSaucAsr::new(VolcengineCredentials {
            app_id: "test-app".into(),
            access_token: "test-key".into(),
            resource_id: "volc.bigasr.sauc.duration".into(),
        });
        client.endpoint = endpoint;
        let result = client.transcribe_saved_meeting_pcm_bytes(&vec![0; 20 * SAVED_MEETING_AUDIO_CHUNK_BYTES]);
        assert_eq!(result.unwrap_err(), safe_provider_error(None));
        assert!(server.join().unwrap() < 20, "client sent the entire recording after rejection");
    }

    #[test]
    fn service_probe_requires_final_protocol_result_and_sends_only_silence() {
        for (payload, expected_success) in [(r#"{"result":{"text":""}}"#, true), ("{}", false)] {
            let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
            let endpoint = format!("ws://{}", listener.local_addr().unwrap());
            listener.set_nonblocking(true).unwrap();
            let worker = std::thread::spawn(move || {
                let runtime = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
                runtime.block_on(async {
                    let listener = tokio::net::TcpListener::from_std(listener).unwrap();
                    let (stream, _) = listener.accept().await.unwrap();
                    let mut ws = tokio_tungstenite::accept_async(stream).await.unwrap();
                    let mut bytes = 0;
                    while let Some(message) = ws.next().await {
                        let Message::Binary(data) = message.unwrap() else { continue; };
                        let frame = frame_parse(&data).unwrap();
                        if frame.message_type == Some(MessageType::FullClientRequest) {
                            let config: Value = serde_json::from_slice(&frame.payload).unwrap();
                            assert!(config.pointer("/request/context").is_none());
                        } else if frame.message_type == Some(MessageType::AudioOnlyRequest) {
                            assert!(frame.payload.iter().all(|byte| *byte == 0)); bytes += frame.payload.len();
                            if frame.is_final() { break; }
                        }
                    }
                    assert_eq!(bytes, 32_000);
                    ws.send(Message::Binary(frame_build(MessageType::FullServerResponse, Flags::LastPacket,
                        Serialization::Json, payload.as_bytes(), None))).await.unwrap();
                    ws.close(None).await.unwrap();
                });
            });
            let mut provider = VolcengineSaucAsr::new(VolcengineCredentials {
                app_id: "test-app".into(), access_token: "test-key".into(), resource_id: "volc.bigasr.sauc.duration".into(),
            });
            provider.endpoint = endpoint;
            assert_eq!(provider.probe_silent_audio().is_ok(), expected_success);
            worker.join().unwrap();
        }
    }

    #[test]
    fn seed_asr_2_uses_high_accuracy_stream_input_route() {
        assert_eq!(
            endpoint_for_resource("volc.seedasr.sauc.duration"),
            SAUC_ENDPOINT_NOSTREAM
        );
        assert_eq!(
            endpoint_for_resource("volc.bigasr.sauc.duration"),
            SAUC_ENDPOINT_ASYNC
        );
    }

    #[test]
    fn seed_asr_2_keeps_compatible_request_and_current_sauc_fields() {
        let payload = build_first_frame_payload("seed-req", true, &[]);
        assert_eq!(payload["audio"]["sample_rate"], 16000);
        assert_eq!(payload["audio"]["rate"], 16000);
        assert_eq!(payload["request"]["reqid"], "seed-req");
        assert_eq!(payload["request"]["sequence"], 1);
        assert_eq!(payload["request"]["model_name"], "bigmodel");
    }

    #[test]
    fn meeting_requests_enable_current_provider_speaker_information() {
        // SAUC's documented boolean is outside additions; the legacy hint
        // alone did not return provider speaker labels on the real WBA clip.
        // Keep the working Seed transport framing, while both routes send the
        // current speaker/utterance switches and bind them into cache identity.
        for resource in ["volc.seedasr.sauc.duration", "volc.bigasr.sauc.duration"] {
            let asr = VolcengineSaucAsr::new(VolcengineCredentials {
                app_id: "test-app".into(), access_token: "test-key".into(), resource_id: resource.into(),
            });
            let payload = asr.session_payload("meeting-speakers");
            assert_eq!(payload["request"]["enable_speaker_info"], true);
            assert_eq!(payload["request"]["show_utterances"], true);
            let configuration = asr.cache_configuration();
            assert_eq!(configuration["payload"]["request"]["enable_speaker_info"], true);
            assert!(payload["request"].get("voiceprints").is_none());
            assert!(payload["request"].get("ssd_mode").is_none());
        }
    }

    #[test]
    fn async_speaker_request_requires_second_pass_and_large_model_ssd() {
        let provider = VolcengineSaucAsr::new(VolcengineCredentials {
            app_id: "test-app".into(), access_token: "test-key".into(),
            resource_id: "volc.bigasr.sauc.duration".into(),
        });
        let payload = provider.session_payload("meeting-speakers");
        assert_eq!(payload["request"]["enable_nonstream"], true);
        assert_eq!(payload["request"]["ssd_version"], "200");
        let current = provider.cache_configuration();
        assert_eq!(current["payload"]["request"], payload["request"]);
        assert_eq!(current["final_audio_coverage"], "reported-duration-v1");
        let mut before_coverage = current.clone();
        before_coverage.as_object_mut().unwrap().remove("final_audio_coverage");
        assert_ne!(current, before_coverage, "old finals must use a separate cache profile");
        let mut old = current.clone();
        old["payload"]["request"]["enable_nonstream"] = serde_json::json!(false);
        old["payload"]["request"].as_object_mut().unwrap().remove("ssd_version");
        assert_ne!(current, old, "cached single-speaker results must not shadow the corrected request");
        let seed = build_first_frame_payload("seed-meeting", true, &[]);
        assert!(seed["request"].get("enable_nonstream").is_none(), "the separate nostream route retains its transport contract");
    }

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
        let v =
            serde_json::from_str::<Value>(r#"{"result":{"text":"会议纪要","duration_ms":1000}}"#)
                .unwrap();
        assert_eq!(extract_text(&v).as_deref(), Some("会议纪要"));
    }

    #[test]
    fn extract_text_falls_back_to_top_level_text() {
        let v = serde_json::from_str::<Value>(r#"{"text":"fallback"}"#).unwrap();
        assert_eq!(extract_text(&v).as_deref(), Some("fallback"));
    }

    #[test]
    fn extract_utterances_parses_int_and_string_timing() {
        let v = serde_json::from_str::<Value>(
            r#"{"result":{"text":"","utterances":[
                {"text":"第一句。","start_time":0,"end_time":900},
                {"text":"第二句。","start_time":"1200","end_time":"2100"}
            ]}}"#,
        )
        .unwrap();
        let utts = extract_utterances(&v);
        assert_eq!(utts.len(), 2);
        assert_eq!(
            utts[0],
            Utterance {
                text: "第一句。".into(),
                start_ms: 0,
                end_ms: 900,
                speaker: None,
            }
        );
        assert_eq!(
            utts[1],
            Utterance {
                text: "第二句。".into(),
                start_ms: 1200,
                end_ms: 2100,
                speaker: None,
            }
        );
    }

    #[test]
    fn extract_utterances_preserves_provider_speaker_additions() {
        let value = serde_json::from_str::<Value>(
            r#"{"result":{"text":"甲乙","utterances":[
                {"text":"甲","start_time":0,"end_time":900,"additions":{"speaker_id":"7"}},
                {"text":"乙","start_time":1000,"end_time":1900,"additions":"{\"speaker\":\"9\"}"}
            ]}}"#,
        )
        .unwrap();
        let utterances = extract_utterances(&value);
        assert_eq!(utterances[0].speaker.as_deref(), Some("7"));
        assert_eq!(utterances[1].speaker.as_deref(), Some("9"));
    }

    #[test]
    fn extract_utterances_prefers_word_timing_when_utterance_start_is_stale() {
        // Utterance start_time (1452) is stale; words[0].start_time (6372) is
        // the real start. Port of Listener's "prefers word timing" behavior.
        let v = serde_json::from_str::<Value>(
            r#"{"result":{"text":"x","utterances":[{
                "text":"需要记录蓝牙包数。",
                "start_time":1452,"end_time":10402,
                "words":[
                    {"text":"需要","start_time":6372,"end_time":6452},
                    {"text":"包数","start_time":10100,"end_time":10402}
                ]
            }]}}"#,
        )
        .unwrap();
        let utts = extract_utterances(&v);
        assert_eq!(utts.len(), 1);
        assert_eq!(utts[0].start_ms, 6372);
        assert_eq!(utts[0].end_ms, 10402);
    }

    #[test]
    fn extract_utterances_empty_when_no_timing() {
        // Utterances with text but no start_time at all are dropped.
        let v =
            serde_json::from_str::<Value>(r#"{"result":{"utterances":[{"text":"无时间戳。"}]}}"#)
                .unwrap();
        assert!(extract_utterances(&v).is_empty());
    }

    #[test]
    fn hotword_context_keeps_domain_lexicon_explicit() {
        // The default must not bias ordinary customer recordings toward the
        // engineering meetings used during development.
        assert!(DEFAULT_MEETING_HOTWORDS.is_empty());
        let defaults: Vec<String> = DEFAULT_MEETING_HOTWORDS.iter().map(|s|s.to_string()).collect();
        assert!(hotword_context(&defaults).is_none());
        // Explicit vocabulary belongs to the corpus context on both endpoints.
        let words = vec!["Opus 16".to_string(), "fail closed".to_string()];
        for seed_v2 in [false, true] {
            let empty = build_first_frame_payload("test-session", seed_v2, &[]);
            let mut configured = build_first_frame_payload("test-session", seed_v2, &words);
            let request = configured["request"].as_object_mut().unwrap();
            assert!(!request.contains_key("context"));
            let corpus = request.remove("corpus").expect("explicit hotwords");
            let context = corpus["context"].as_str().unwrap();
            assert_eq!(serde_json::from_str::<Value>(context).unwrap(), json!({
                "hotwords": [{"word": "Opus 16"}, {"word": "fail closed"}]
            }));
            assert_eq!(configured, empty);
        }
    }

    #[test]
    fn hotword_context_dedupes_and_caps() {
        let mut words: Vec<String> = vec!["Foo".into(), "foo".into(), "  ".into(), "Bar".into()];
        for i in 0..100 {
            words.push(format!("w{i}"));
        }
        let ctx = hotword_context(&words).expect("ctx");
        assert!(ctx.contains("Foo"));
        assert!(ctx.contains("Bar"));
        assert!(ctx.matches("\"word\"").count() <= HOTWORD_CAP);
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
        let (text, utterances) = asr
            .transcribe_file(Path::new(&wav))
            .expect("real transcript");
        assert!(!text.trim().is_empty(), "transcript must be non-empty");
        eprintln!("volcengine_real_transcript={}", text);
        eprintln!("volcengine_real_utterances={}", utterances.len());
        eprintln!(
            "volcengine_real_speakers={:?}",
            utterances
                .iter()
                .map(|utterance| utterance.speaker.as_deref())
                .collect::<Vec<_>>()
        );
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
        let app_key =
            std::env::var("COMPANION_TYPE_VOLC_APP_KEY").expect("COMPANION_TYPE_VOLC_APP_KEY");
        let access_key = std::env::var("COMPANION_TYPE_VOLC_ACCESS_KEY")
            .expect("COMPANION_TYPE_VOLC_ACCESS_KEY");
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
        // Write WAV first, then play; host mic records the air path (true mechanical voice).
        let sapi_script = "Add-Type -AssemblyName System.Speech; \
            $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; \
            try { $s.SelectVoice('Microsoft Huihui Desktop') } catch {}; \
            $s.Rate = -2; \
            $s.Volume = 100; \
            $p = Join-Path $env:TEMP 'companion-type-mech-stimulus.wav'; \
            $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono); \
            $s.SetOutputToWaveFile($p, $fmt); \
            $s.Speak($env:COMPANION_TYPE_MECH_STIMULUS); \
            $s.Dispose(); \
            # Signal file ready so host can start mic just before playback. \
            Set-Content -Path (Join-Path $env:TEMP 'companion-type-mech-ready.flag') -Value '1'; \
            Start-Sleep -Milliseconds 300; \
            (New-Object Media.SoundPlayer $p).PlaySync()";
        let ready_flag = std::env::temp_dir().join("companion-type-mech-ready.flag");
        let _ = std::fs::remove_file(&ready_flag);
        let mut sapi = std::process::Command::new("pwsh")
            .args(["-NoProfile", "-Command", sapi_script])
            .spawn()
            .expect("spawn pwsh SAPI playback");

        // 2. Wait until TTS file is ready, then record physical microphone.
        std::env::set_var("COMPANION_TYPE_HOST_RECORDING_MODE", "real");
        let ready_deadline = std::time::Instant::now() + std::time::Duration::from_secs(30);
        while !ready_flag.exists() {
            if std::time::Instant::now() > ready_deadline {
                let _ = sapi.kill();
                panic!("timed out waiting for mechanical TTS wav ready flag");
            }
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
        std::thread::sleep(std::time::Duration::from_millis(200));
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
        let (transcript, _utterances) = asr
            .transcribe_file(&stop.path)
            .expect("volcengine transcript of the microphone recording");

        // 5. Coverage: LCS char ratio of normalized transcript vs stimulus.
        let expected = normalize_text(&stimulus);
        let actual = normalize_text(&transcript);
        let coverage = lcs_ratio(&expected, &actual);

        eprintln!("mech_e2e_wav={}", stop.path.display());
        eprintln!("mech_e2e_stimulus={}", stimulus);
        eprintln!("mech_e2e_transcript={}", transcript);
        eprintln!(
            "mech_e2e_peak={} rms={} duration_ms={} coverage={:.3}",
            peak, rms, stop.duration_ms, coverage
        );

        assert!(!transcript.trim().is_empty(), "transcript is empty");
        // Air path (speaker→mic) is lossy; 0.45 is the product mechanical gate.
        // Clean file-to-ASR remains higher fidelity elsewhere.
        assert!(
            coverage >= 0.45,
            "transcript coverage {coverage:.3} below 0.45 threshold; transcript={transcript}"
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
                cur[j + 1] = if ec == ac {
                    prev[j] + 1
                } else {
                    prev[j + 1].max(cur[j])
                };
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
        let rms = if n > 0 {
            (sum_sq / n as f64).sqrt()
        } else {
            0.0
        };
        (peak, rms)
    }
}
