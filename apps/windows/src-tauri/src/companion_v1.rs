use serde::{Deserialize, Serialize};

pub const COMPANION_V1_SCHEMA: &str = "companion.host.v1";
pub const COMPANION_V1_DEFAULT_BLE_NAME: &str = "companion";
pub const COMPANION_V1_BLE_NAME_MAX_BYTES: usize = 29;
pub const COMPANION_V1_RAW_PCM_BYTES_PER_SECOND: u64 = 32_000;
pub const COMPANION_V1_DEVICE_FLASH_RECORDING_MAX_SECONDS: u64 = 60;
pub const COMPANION_V1_LONG_MEETING_TARGET_SECONDS: u64 = 3_600;
pub const COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES: u64 =
    COMPANION_V1_RAW_PCM_BYTES_PER_SECOND * COMPANION_V1_LONG_MEETING_TARGET_SECONDS;
pub const COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS: u64 = 300;
pub const COMPANION_V1_ASR_UPLOAD_MAX_BYTES: u64 = 25 * 1024 * 1024;
pub const COMPANION_V1_ONE_HOUR_CHUNKS: u64 =
    (COMPANION_V1_LONG_MEETING_TARGET_SECONDS + COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS - 1)
        / COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS;
pub const COMPANION_V1_HOST_RECORDING_CHANNEL: &str = "host://companion-type/recording";
pub const COMPANION_V1_HOST_MINUTES_CHANNEL: &str = "host://companion-type/minutes";
pub const COMPANION_V1_HOST_DEVICE_CHANNEL: &str = "host://companion-type/device";
pub const COMPANION_V1_HOST_SETUP_CHANNEL: &str = "host://companion-type/setup";
pub const COMPANION_V1_HOST_PRIVACY_CHANNEL: &str = "host://companion-type/privacy";

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1GattBoundary {
    pub settings_service_uuid: &'static str,
    pub ble_name_config_uuid: &'static str,
    pub meeting_service_uuid: &'static str,
    pub meeting_control_uuid: &'static str,
    pub meeting_status_uuid: &'static str,
    pub sensors_service_uuid: &'static str,
    pub imu_status_uuid: &'static str,
    pub audio_output_service_uuid: &'static str,
    pub speaker_control_uuid: &'static str,
    pub speaker_status_uuid: &'static str,
    pub wake_word_control_uuid: &'static str,
    pub wake_word_status_uuid: &'static str,
}

pub const COMPANION_V1_GATT_BOUNDARY: CompanionV1GattBoundary = CompanionV1GattBoundary {
    settings_service_uuid: "8f7a0004-7b7d-4f3d-9d6f-6c2d1b7c0000",
    ble_name_config_uuid: "8f7a4002-7b7d-4f3d-9d6f-6c2d1b7c0000",
    meeting_service_uuid: "8f7a0008-7b7d-4f3d-9d6f-6c2d1b7c0000",
    meeting_control_uuid: "8f7a8001-7b7d-4f3d-9d6f-6c2d1b7c0000",
    meeting_status_uuid: "8f7a8002-7b7d-4f3d-9d6f-6c2d1b7c0000",
    sensors_service_uuid: "8f7a0009-7b7d-4f3d-9d6f-6c2d1b7c0000",
    imu_status_uuid: "8f7a9001-7b7d-4f3d-9d6f-6c2d1b7c0000",
    audio_output_service_uuid: "8f7a000a-7b7d-4f3d-9d6f-6c2d1b7c0000",
    speaker_control_uuid: "8f7aa001-7b7d-4f3d-9d6f-6c2d1b7c0000",
    speaker_status_uuid: "8f7aa002-7b7d-4f3d-9d6f-6c2d1b7c0000",
    wake_word_control_uuid: "8f7aa003-7b7d-4f3d-9d6f-6c2d1b7c0000",
    wake_word_status_uuid: "8f7aa004-7b7d-4f3d-9d6f-6c2d1b7c0000",
};

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1Snapshot {
    pub schema: &'static str,
    pub source: &'static str,
    pub device_id: Option<String>,
    pub connected: bool,
    pub updated_at: String,
    pub gatt: CompanionV1GattBoundary,
    pub meeting: CompanionV1MeetingState,
    pub imu: CompanionV1ImuState,
    pub speaker: CompanionV1SpeakerState,
    pub wake_word: CompanionV1WakeWordState,
    pub ble_name: CompanionV1BleNameState,
    pub device: CompanionV1DeviceTransportState,
    pub oobe: CompanionV1OobeState,
    pub privacy: CompanionV1PrivacyState,
    pub host: CompanionV1HostState,
    pub last_control: Option<CompanionV1ControlEcho>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1MeetingState {
    pub supported: bool,
    pub active: bool,
    pub status: String,
    pub started_at: Option<String>,
    pub duration_ms: u64,
    pub transcript_count: u32,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1ImuState {
    pub supported: bool,
    pub online: bool,
    pub sample_hz: u16,
    pub motion: String,
    pub accel: CompanionV1Vector3,
    pub gyro: CompanionV1Vector3,
}

#[derive(Clone, Debug, Serialize)]
pub struct CompanionV1Vector3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1SpeakerState {
    pub supported: bool,
    pub online: bool,
    pub muted: bool,
    pub volume: u8,
    pub status: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1WakeWordState {
    pub supported: bool,
    pub armed: bool,
    pub engine: String,
    pub keyword: String,
    pub last_detected_at: Option<String>,
    pub confidence: f32,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1BleNameState {
    pub active_name: String,
    pub staged_name: String,
    pub max_len: u8,
    pub status: String,
    pub pending_restart: bool,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1DeviceTransportState {
    pub supported: bool,
    pub provider_id: String,
    pub mode: String,
    pub scanning: bool,
    pub connected: bool,
    pub device_id: Option<String>,
    pub last_seen_at: Option<String>,
    pub signal_rssi: Option<i16>,
    pub recordings_available: u32,
    pub last_sync_at: Option<String>,
    pub message: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1OobeCheck {
    pub id: String,
    pub label: String,
    pub status: String,
    pub message: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1OobeState {
    pub complete: bool,
    pub last_run_at: Option<String>,
    pub checks: Vec<CompanionV1OobeCheck>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1PrivacyState {
    pub local_only: bool,
    pub consent_required: bool,
    pub retention_days: u16,
    pub audio_cache_bytes: u64,
    pub transcript_bytes: u64,
    pub minutes_bytes: u64,
    pub last_erase_at: Option<String>,
    pub policy_label: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1RecordingPolicy {
    pub owner: String,
    pub device_flash_raw_cache_seconds: u64,
    pub target_meeting_seconds: u64,
    pub raw_pcm_bytes_per_second: u64,
    pub one_hour_raw_pcm_bytes: u64,
    pub chunk_seconds: u64,
    pub one_hour_chunk_count: u64,
    pub max_asr_upload_bytes: u64,
    pub preferred_long_recording_source: String,
    pub device_role: String,
    pub long_meeting_strategy: String,
    pub asr_provider_mode: String,
    pub short_capture_guide: String,
    pub long_meeting_guide: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1HostState {
    pub recording_policy: CompanionV1RecordingPolicy,
    pub active_session_id: Option<String>,
    pub selected_session_id: Option<String>,
    pub sessions: Vec<CompanionV1HostSession>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1HostSession {
    pub id: String,
    pub title: String,
    pub source: String,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pending_reason: Option<String>,
    pub started_at: Option<String>,
    pub stopped_at: Option<String>,
    pub duration_ms: u64,
    pub audio_path: Option<String>,
    pub audio_bytes: u64,
    pub chunks: Vec<CompanionV1AudioChunk>,
    pub transcript_text: String,
    pub transcript_preview: String,
    pub transcript_segments: usize,
    /// Timed, speaker-attributed utterances from the diarization-aware
    /// transcription path. Empty for sessions transcribed before this field
    /// existed or when diarization timing is unavailable.
    #[serde(default)]
    pub utterances: Vec<CompanionV1UtteranceSegment>,
    pub minutes: Option<CompanionV1MeetingMinutes>,
    pub export_markdown: String,
    pub exported_at: Option<String>,
    pub retention: CompanionV1SessionRetention,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1AudioChunk {
    pub id: String,
    pub path: Option<String>,
    pub started_at: Option<String>,
    pub stopped_at: Option<String>,
    pub duration_ms: u64,
    pub bytes: u64,
    pub status: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1SessionRetention {
    pub audio_cached: bool,
    pub transcript_cached: bool,
    pub minutes_cached: bool,
    pub consent_required: bool,
    pub retention_label: String,
    pub expires_at: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1ActionItem {
    pub text: String,
    pub owner: Option<String>,
    pub due: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1MeetingMinutes {
    pub generated_at: String,
    pub source: String,
    pub quality: String,
    pub summary: Vec<String>,
    pub decisions: Vec<String>,
    pub action_items: Vec<CompanionV1ActionItem>,
    pub questions: Vec<String>,
    pub keywords: Vec<String>,
    pub markdown: String,
}

/// One timed, speaker-attributed transcript utterance. Populated by the
/// diarization-aware transcription path so exports can render timed formats
/// (SRT subtitles) and the UI can show per-utterance speaker/timing. `speaker`
/// is a 0-based diarization id; `None` when diarization could not attribute it.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1UtteranceSegment {
    pub text: String,
    pub start_ms: u64,
    pub end_ms: u64,
    pub speaker: Option<usize>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1ControlEcho {
    pub action: CompanionV1ControlAction,
    pub characteristic_uuid: &'static str,
    pub payload_hex: String,
    pub accepted: bool,
    pub message: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum CompanionV1ControlAction {
    DeviceScan,
    DeviceConnect,
    DeviceDisconnect,
    DeviceSyncRecordings,
    StageBleName,
    ApplyBleName,
    ResetBleName,
    OobeRunChecks,
    MeetingStart,
    MeetingStop,
    MeetingFinalize,
    MeetingImportTranscript,
    MeetingTranscribeAudio,
    MeetingGenerateMinutes,
    MeetingExportMarkdown,
    MeetingExportTxt,
    MeetingExportJson,
    MeetingExportSrt,
    MeetingLoadDemo,
    MeetingResetSession,
    PrivacyEraseAudio,
    PrivacyEraseTranscript,
    PrivacyEraseAll,
    SpeakerPrompt,
    SpeakerStop,
    WakeArm,
    WakeDisable,
    WakeTestDetect,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1ControlRequest {
    pub action: CompanionV1ControlAction,
    pub ble_name: Option<String>,
    pub session_id: Option<String>,
    pub prompt_id: Option<String>,
    pub title: Option<String>,
    pub transcript_text: Option<String>,
    pub audio_path: Option<String>,
    pub audio_bytes: Option<u64>,
    pub device_id: Option<String>,
    pub duration_ms: Option<u64>,
}

pub fn companion_ble_name_is_valid(name: &str) -> bool {
    let bytes = name.as_bytes();
    if bytes.is_empty() || bytes.len() > COMPANION_V1_BLE_NAME_MAX_BYTES {
        return false;
    }
    bytes.iter().all(|byte| {
        (0x20..=0x7e).contains(byte) && !matches!(byte, b'"' | b'\'' | b';' | b'=' | b'\\')
    })
}

pub fn fixture_snapshot() -> CompanionV1Snapshot {
    CompanionV1Snapshot {
        schema: COMPANION_V1_SCHEMA,
        source: "fixture",
        device_id: Some("fixture-companion-v1".to_string()),
        connected: false,
        updated_at: "fixture".to_string(),
        gatt: COMPANION_V1_GATT_BOUNDARY,
        meeting: CompanionV1MeetingState {
            supported: true,
            active: false,
            status: "idle".to_string(),
            started_at: None,
            duration_ms: 0,
            transcript_count: 0,
        },
        imu: CompanionV1ImuState {
            supported: true,
            online: false,
            sample_hz: 0,
            motion: "unknown".to_string(),
            accel: CompanionV1Vector3 {
                x: 0.0,
                y: 0.0,
                z: 1.0,
            },
            gyro: CompanionV1Vector3 {
                x: 0.0,
                y: 0.0,
                z: 0.0,
            },
        },
        speaker: CompanionV1SpeakerState {
            supported: true,
            online: false,
            muted: false,
            volume: 65,
            status: "idle".to_string(),
        },
        wake_word: CompanionV1WakeWordState {
            supported: true,
            armed: false,
            engine: "fixture".to_string(),
            keyword: "hey companion".to_string(),
            last_detected_at: None,
            confidence: 0.0,
        },
        ble_name: CompanionV1BleNameState {
            active_name: COMPANION_V1_DEFAULT_BLE_NAME.to_string(),
            staged_name: COMPANION_V1_DEFAULT_BLE_NAME.to_string(),
            max_len: COMPANION_V1_BLE_NAME_MAX_BYTES as u8,
            status: "clean".to_string(),
            pending_restart: false,
        },
        device: default_device_state(),
        oobe: default_oobe_state(),
        privacy: default_privacy_state(),
        host: default_host_state(),
        last_control: None,
    }
}

pub fn apply_fixture_control(
    mut snapshot: CompanionV1Snapshot,
    request: CompanionV1ControlRequest,
) -> Result<CompanionV1Snapshot, String> {
    let now = "fixture".to_string();
    snapshot.updated_at = now.clone();

    match request.action {
        CompanionV1ControlAction::DeviceScan => {
            snapshot.device.scanning = false;
            snapshot.device.connected = false;
            snapshot.device.device_id = Some(
                request
                    .device_id
                    .clone()
                    .unwrap_or_else(|| "companion-nucleo-wb55rg".to_string()),
            );
            snapshot.device.last_seen_at = Some(now.clone());
            snapshot.device.signal_rssi = Some(-48);
            snapshot.device.recordings_available = snapshot.device.recordings_available.max(1);
            snapshot.device.message = "Companion device discovered".to_string();
            snapshot.connected = false;
        }
        CompanionV1ControlAction::DeviceConnect => {
            snapshot.device.connected = true;
            snapshot.device.device_id = Some(
                request
                    .device_id
                    .clone()
                    .or(snapshot.device.device_id.clone())
                    .unwrap_or_else(|| "companion-nucleo-wb55rg".to_string()),
            );
            snapshot.device.last_seen_at = Some(now.clone());
            snapshot.device.signal_rssi = snapshot.device.signal_rssi.or(Some(-48));
            snapshot.device.message = "Companion device connected".to_string();
            snapshot.connected = true;
        }
        CompanionV1ControlAction::DeviceDisconnect => {
            snapshot.device.connected = false;
            snapshot.device.message = "Companion device disconnected".to_string();
            snapshot.connected = false;
        }
        CompanionV1ControlAction::DeviceSyncRecordings => {
            let session = create_synced_device_session(&snapshot, &request, &now);
            let session_id = session.id.clone();
            snapshot.host.sessions.retain(|item| item.id != session_id);
            snapshot.host.sessions.insert(0, session.clone());
            snapshot.host.selected_session_id = Some(session_id);
            snapshot.host.active_session_id = None;
            snapshot.device.connected = true;
            snapshot.device.last_sync_at = Some(now.clone());
            snapshot.device.recordings_available =
                snapshot.device.recordings_available.saturating_sub(1);
            snapshot.device.message =
                "Device recording synced; session captured — needs transcription before minutes"
                    .to_string();
            snapshot.connected = true;
            snapshot.meeting.active = false;
            snapshot.meeting.status = "captured".to_string();
            snapshot.meeting.started_at = None;
            snapshot.meeting.duration_ms = session.duration_ms;
        }
        CompanionV1ControlAction::StageBleName => {
            let name = request
                .ble_name
                .clone()
                .ok_or_else(|| "bleName is required".to_string())?;
            if !companion_ble_name_is_valid(&name) {
                return Err("invalid Companion BLE name".to_string());
            }
            snapshot.ble_name.staged_name = name;
            snapshot.ble_name.status = "staged".to_string();
            snapshot.ble_name.pending_restart = true;
        }
        CompanionV1ControlAction::ApplyBleName => {
            snapshot.ble_name.active_name = snapshot.ble_name.staged_name.clone();
            snapshot.ble_name.status = "pendingRestart".to_string();
            snapshot.ble_name.pending_restart = true;
        }
        CompanionV1ControlAction::ResetBleName => {
            snapshot.ble_name.staged_name = COMPANION_V1_DEFAULT_BLE_NAME.to_string();
            snapshot.ble_name.status = "staged".to_string();
            snapshot.ble_name.pending_restart = true;
        }
        CompanionV1ControlAction::OobeRunChecks => {
            snapshot.oobe.complete = true;
            snapshot.oobe.last_run_at = Some(now.clone());
            snapshot.oobe.checks = vec![
                oobe_check(
                    "firmware",
                    "Firmware",
                    "pass",
                    "STM32CubeProgrammer or firmware helper ready",
                ),
                oobe_check(
                    "bluetooth",
                    "Bluetooth",
                    if snapshot.device.supported {
                        "pass"
                    } else {
                        "warn"
                    },
                    &snapshot.device.provider_id,
                ),
                oobe_check(
                    "microphone",
                    "Microphone",
                    "pass",
                    "Host WAV recorder ready",
                ),
                oobe_check(
                    "asr",
                    "ASR",
                    "pass",
                    &format!(
                        "{} (configure cloud/local before auto-transcribe)",
                        snapshot.host.recording_policy.asr_provider_mode
                    ),
                ),
                oobe_check("privacy", "Privacy", "pass", &snapshot.privacy.policy_label),
            ];
        }
        CompanionV1ControlAction::MeetingStart => {
            let session = create_host_session(&snapshot, &request, &now);
            let session_id = session.id.clone();
            snapshot.host.sessions.retain(|item| item.id != session_id);
            snapshot.host.sessions.insert(0, session);
            snapshot.host.active_session_id = Some(session_id.clone());
            snapshot.host.selected_session_id = Some(session_id);
            snapshot.meeting.active = true;
            snapshot.meeting.status = "recording".to_string();
            snapshot.meeting.started_at = Some(now.clone());
            snapshot.meeting.duration_ms = 0;
        }
        CompanionV1ControlAction::MeetingStop => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            let duration_ms = request
                .duration_ms
                .unwrap_or_else(|| snapshot.host.sessions[index].duration_ms.max(60_000));
            snapshot.host.sessions[index].status = "captured".to_string();
            snapshot.host.sessions[index].pending_reason =
                if snapshot.host.sessions[index].transcript_text.trim().is_empty() {
                    Some("needs_transcription".to_string())
                } else {
                    None
                };
            snapshot.host.sessions[index].stopped_at = Some(now.clone());
            snapshot.host.sessions[index].duration_ms = duration_ms;
            snapshot.host.sessions[index].audio_bytes = request
                .audio_bytes
                .unwrap_or_else(|| estimate_pcm_bytes(duration_ms));
            snapshot.host.sessions[index].chunks = seal_session_chunks(
                &snapshot.host.sessions[index],
                &now,
                duration_ms,
                request.audio_bytes,
            );
            snapshot.host.active_session_id = None;
            snapshot.meeting.active = false;
            snapshot.meeting.status = "captured".to_string();
            snapshot.meeting.duration_ms = duration_ms;
        }
        CompanionV1ControlAction::MeetingFinalize => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            if snapshot.host.sessions[index]
                .transcript_text
                .trim()
                .is_empty()
            {
                snapshot.host.sessions[index].status = "captured".to_string();
                snapshot.host.sessions[index].pending_reason =
                    Some("needs_transcription".to_string());
                if snapshot.host.sessions[index].stopped_at.is_none() {
                    snapshot.host.sessions[index].stopped_at = Some(now.clone());
                }
                snapshot.meeting.status = "finalized".to_string();
            } else {
                let minutes = build_minutes(&snapshot.host.sessions[index], &now);
                snapshot.host.sessions[index].status = "minutesReady".to_string();
                snapshot.host.sessions[index].pending_reason = None;
                snapshot.host.sessions[index].export_markdown = minutes.markdown.clone();
                snapshot.host.sessions[index].exported_at = Some(now.clone());
                snapshot.host.sessions[index]
                    .retention
                    .minutes_cached = true;
                snapshot.host.sessions[index].minutes = Some(minutes);
                snapshot.meeting.status = "minutesReady".to_string();
            }
            snapshot.meeting.active = false;
            snapshot.host.active_session_id = None;
            snapshot.meeting.transcript_count = count_transcript_sessions(&snapshot);
        }
        CompanionV1ControlAction::MeetingImportTranscript => {
            let transcript = normalize_transcript(request.transcript_text.as_deref().unwrap_or(""));
            if transcript.is_empty() {
                return Err("Import requires non-empty transcript text.".to_string());
            }
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            apply_transcript(&mut snapshot, index, transcript, true);
        }
        CompanionV1ControlAction::MeetingTranscribeAudio => {
            let transcript = normalize_transcript(request.transcript_text.as_deref().unwrap_or(""));
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            if transcript.is_empty() {
                snapshot.host.sessions[index].status = "captured".to_string();
                snapshot.host.sessions[index].pending_reason =
                    Some(if snapshot.privacy.local_only {
                        "needs_transcription".to_string()
                    } else {
                        "needs_network".to_string()
                    });
                snapshot.meeting.active = false;
                snapshot.meeting.status = "captured".to_string();
            } else {
                apply_transcript(&mut snapshot, index, transcript, false);
            }
        }
        CompanionV1ControlAction::MeetingGenerateMinutes => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            if snapshot.host.sessions[index]
                .transcript_text
                .trim()
                .is_empty()
            {
                snapshot.host.sessions[index].status = "captured".to_string();
                snapshot.host.sessions[index].pending_reason =
                    Some("needs_transcription".to_string());
                snapshot.meeting.status = "captured".to_string();
                return Err(
                    "Generate minutes requires a transcript. Import text or run Transcribe after configuring ASR."
                        .to_string(),
                );
            }
            let minutes = build_minutes(&snapshot.host.sessions[index], &now);
            snapshot.host.sessions[index].status = "minutesReady".to_string();
            snapshot.host.sessions[index].pending_reason = None;
            snapshot.host.sessions[index].export_markdown = minutes.markdown.clone();
            snapshot.host.sessions[index].minutes = Some(minutes);
            snapshot.host.sessions[index].retention.minutes_cached = true;
            snapshot.meeting.active = false;
            snapshot.meeting.status = "minutesReady".to_string();
            snapshot.meeting.transcript_count = count_transcript_sessions(&snapshot);
        }
        CompanionV1ControlAction::MeetingExportMarkdown
        | CompanionV1ControlAction::MeetingExportTxt
        | CompanionV1ControlAction::MeetingExportJson
        | CompanionV1ControlAction::MeetingExportSrt => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            let minutes = snapshot.host.sessions[index]
                .minutes
                .clone()
                .unwrap_or_else(|| build_minutes(&snapshot.host.sessions[index], &now));
            snapshot.host.sessions[index].status = "minutesReady".to_string();
            snapshot.host.sessions[index].export_markdown = minutes.markdown.clone();
            snapshot.host.sessions[index].exported_at = Some(now.clone());
            snapshot.host.sessions[index].minutes = Some(minutes);
            snapshot.host.sessions[index].retention.minutes_cached = true;
            snapshot.meeting.active = false;
            snapshot.meeting.status = "minutesReady".to_string();
            snapshot.meeting.transcript_count = count_transcript_sessions(&snapshot);
        }
        CompanionV1ControlAction::MeetingLoadDemo => {
            let demo_text = normalize_transcript(
                request.transcript_text.as_deref().unwrap_or(
                    "Decision: Companion host owns long meeting recordings.\nAction owner: Chen due: Friday validates minutes export.\nQuestion: should offline show needs_transcription?",
                ),
            );
            let duration_ms = request.duration_ms.unwrap_or(15_000);
            let mut session = create_host_session(
                &snapshot,
                &CompanionV1ControlRequest {
                    action: CompanionV1ControlAction::MeetingStart,
                    ble_name: None,
                    session_id: request.session_id.clone(),
                    prompt_id: None,
                    title: Some(
                        request
                            .title
                            .clone()
                            .unwrap_or_else(|| "一键演示纪要".to_string()),
                    ),
                    transcript_text: None,
                    audio_path: Some(
                        request
                            .audio_path
                            .clone()
                            .unwrap_or_else(|| "demo://companion-type/mechanical-voice.wav".to_string()),
                    ),
                    audio_bytes: Some(request.audio_bytes.unwrap_or_else(|| estimate_pcm_bytes(duration_ms))),
                    device_id: None,
                    duration_ms: Some(duration_ms),
                },
                &now,
            );
            session.source = "hostMicrophone".to_string();
            session.status = "minutesReady".to_string();
            session.pending_reason = None;
            session.started_at = Some(now.clone());
            session.stopped_at = Some(now.clone());
            session.duration_ms = duration_ms;
            session.transcript_text = demo_text.clone();
            session.transcript_preview = preview_text(&demo_text);
            session.transcript_segments = split_segments(&demo_text).len();
            session.chunks = vec![audio_chunk(
                &format!("{}-demo", session.id),
                session.audio_path.clone(),
                Some(now.clone()),
                Some(now.clone()),
                duration_ms,
                session.audio_bytes,
                "sealed",
            )];
            let minutes = build_minutes(&session, &now);
            session.export_markdown = minutes.markdown.clone();
            session.exported_at = Some(now.clone());
            session.minutes = Some(minutes);
            session.retention = session_retention(true, true, true);
            let session_id = session.id.clone();
            snapshot.host.sessions.retain(|item| item.id != session_id);
            snapshot.host.sessions.insert(0, session);
            snapshot.host.selected_session_id = Some(session_id);
            snapshot.host.active_session_id = None;
            snapshot.meeting.active = false;
            snapshot.meeting.status = "minutesReady".to_string();
            snapshot.meeting.started_at = None;
            snapshot.meeting.duration_ms = duration_ms;
            snapshot.meeting.transcript_count = count_transcript_sessions(&snapshot);
        }
        CompanionV1ControlAction::MeetingResetSession => {
            snapshot.host = default_host_state();
            snapshot.meeting.active = false;
            snapshot.meeting.status = "idle".to_string();
            snapshot.meeting.started_at = None;
            snapshot.meeting.duration_ms = 0;
            snapshot.meeting.transcript_count = 0;
        }
        CompanionV1ControlAction::PrivacyEraseAudio => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            snapshot.host.sessions[index].audio_path = None;
            snapshot.host.sessions[index].audio_bytes = 0;
            snapshot.host.sessions[index].chunks = snapshot.host.sessions[index]
                .chunks
                .iter()
                .map(|chunk| CompanionV1AudioChunk {
                    id: chunk.id.clone(),
                    path: None,
                    started_at: chunk.started_at.clone(),
                    stopped_at: chunk.stopped_at.clone(),
                    duration_ms: chunk.duration_ms,
                    bytes: 0,
                    status: "erased".to_string(),
                })
                .collect();
            snapshot.host.sessions[index].retention.audio_cached = false;
            snapshot.privacy.last_erase_at = Some(now.clone());
        }
        CompanionV1ControlAction::PrivacyEraseTranscript => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            let has_audio = snapshot.host.sessions[index].audio_path.is_some()
                || snapshot.host.sessions[index].audio_bytes > 0;
            snapshot.host.sessions[index].status =
                if has_audio { "captured" } else { "idle" }.to_string();
            snapshot.host.sessions[index].pending_reason = if has_audio {
                Some("needs_transcription".to_string())
            } else {
                None
            };
            snapshot.host.sessions[index].transcript_text.clear();
            snapshot.host.sessions[index].transcript_preview.clear();
            snapshot.host.sessions[index].transcript_segments = 0;
            snapshot.host.sessions[index].minutes = None;
            snapshot.host.sessions[index].export_markdown.clear();
            snapshot.host.sessions[index].exported_at = None;
            snapshot.host.sessions[index].retention.transcript_cached = false;
            snapshot.host.sessions[index].retention.minutes_cached = false;
            snapshot.meeting.status = if has_audio { "captured" } else { "idle" }.to_string();
            snapshot.meeting.transcript_count = count_transcript_sessions(&snapshot);
            snapshot.privacy.last_erase_at = Some(now.clone());
        }
        CompanionV1ControlAction::PrivacyEraseAll => {
            snapshot.host = default_host_state();
            snapshot.meeting.active = false;
            snapshot.meeting.status = "idle".to_string();
            snapshot.meeting.started_at = None;
            snapshot.meeting.duration_ms = 0;
            snapshot.meeting.transcript_count = 0;
            snapshot.privacy = default_privacy_state();
            snapshot.privacy.last_erase_at = Some(now.clone());
        }
        CompanionV1ControlAction::SpeakerPrompt => {
            snapshot.speaker.online = true;
            snapshot.speaker.status = "prompting".to_string();
        }
        CompanionV1ControlAction::SpeakerStop => {
            snapshot.speaker.status = "idle".to_string();
        }
        CompanionV1ControlAction::WakeArm => {
            snapshot.wake_word.armed = true;
        }
        CompanionV1ControlAction::WakeDisable => {
            snapshot.wake_word.armed = false;
            snapshot.wake_word.confidence = 0.0;
        }
        CompanionV1ControlAction::WakeTestDetect => {
            snapshot.wake_word.armed = true;
            snapshot.wake_word.last_detected_at = Some(now.clone());
            snapshot.wake_word.confidence = 0.92;
        }
    }

    snapshot.privacy = refresh_privacy_state(&snapshot, snapshot.privacy.last_erase_at.clone());

    let message = request
        .session_id
        .as_deref()
        .or(request.prompt_id.as_deref())
        .map(|id| format!("fixture accepted ({id})"))
        .unwrap_or_else(|| {
            if host_only_action(request.action) {
                "host workflow accepted".to_string()
            } else {
                "fixture accepted".to_string()
            }
        });

    snapshot.last_control = Some(CompanionV1ControlEcho {
        action: request.action,
        characteristic_uuid: characteristic_for_action(request.action),
        payload_hex: payload_hex(&request),
        accepted: true,
        message,
    });
    Ok(snapshot)
}

fn default_host_state() -> CompanionV1HostState {
    CompanionV1HostState {
        recording_policy: CompanionV1RecordingPolicy {
            owner: "host".to_string(),
            device_flash_raw_cache_seconds: COMPANION_V1_DEVICE_FLASH_RECORDING_MAX_SECONDS,
            target_meeting_seconds: COMPANION_V1_LONG_MEETING_TARGET_SECONDS,
            raw_pcm_bytes_per_second: COMPANION_V1_RAW_PCM_BYTES_PER_SECOND,
            one_hour_raw_pcm_bytes: COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES,
            chunk_seconds: COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS,
            one_hour_chunk_count: COMPANION_V1_ONE_HOUR_CHUNKS,
            max_asr_upload_bytes: COMPANION_V1_ASR_UPLOAD_MAX_BYTES,
            preferred_long_recording_source: "hostMicrophone".to_string(),
            device_role: "triggerAndShortCache".to_string(),
            long_meeting_strategy: "hostChunkedWav".to_string(),
            asr_provider_mode: "openaiCompatibleOrLocalCommand".to_string(),
            short_capture_guide: "Short: device flash cache (≤60s) → Sync/pull → host ASR → minutes"
                .to_string(),
            long_meeting_guide:
                "Long meeting: host microphone (5 min chunks); device is trigger/status only — not full-hour BLE pull"
                    .to_string(),
        },
        active_session_id: None,
        selected_session_id: None,
        sessions: Vec::new(),
    }
}

fn default_device_state() -> CompanionV1DeviceTransportState {
    CompanionV1DeviceTransportState {
        supported: true,
        provider_id: "companion-type-windows-ble".to_string(),
        mode: "windowsNative".to_string(),
        scanning: false,
        connected: false,
        device_id: None,
        last_seen_at: None,
        signal_rssi: None,
        recordings_available: 0,
        last_sync_at: None,
        message: "Not scanned".to_string(),
    }
}

fn default_oobe_state() -> CompanionV1OobeState {
    CompanionV1OobeState {
        complete: false,
        last_run_at: None,
        checks: vec![
            oobe_check("firmware", "Firmware", "pending", "Waiting"),
            oobe_check("bluetooth", "Bluetooth", "pending", "Waiting"),
            oobe_check("microphone", "Microphone", "pending", "Waiting"),
            oobe_check("asr", "ASR", "pending", "Waiting"),
            oobe_check("privacy", "Privacy", "pending", "Waiting"),
        ],
    }
}

fn default_privacy_state() -> CompanionV1PrivacyState {
    CompanionV1PrivacyState {
        local_only: true,
        consent_required: true,
        retention_days: 7,
        audio_cache_bytes: 0,
        transcript_bytes: 0,
        minutes_bytes: 0,
        last_erase_at: None,
        policy_label: "Local cache".to_string(),
    }
}

fn oobe_check(id: &str, label: &str, status: &str, message: &str) -> CompanionV1OobeCheck {
    CompanionV1OobeCheck {
        id: id.to_string(),
        label: label.to_string(),
        status: status.to_string(),
        message: message.to_string(),
    }
}

fn create_host_session(
    snapshot: &CompanionV1Snapshot,
    request: &CompanionV1ControlRequest,
    now: &str,
) -> CompanionV1HostSession {
    let duration_ms = request.duration_ms.unwrap_or(0);
    let supplied_audio_path = request.audio_path.clone();
    let audio_bytes = request.audio_bytes.unwrap_or_else(|| {
        if duration_ms > 0 {
            estimate_pcm_bytes(duration_ms)
        } else {
            0
        }
    });
    let id = request
        .session_id
        .clone()
        .unwrap_or_else(|| format!("meeting-fixture-{}", snapshot.host.sessions.len() + 1));
    let audio_path = supplied_audio_path
        .clone()
        .unwrap_or_else(|| default_host_audio_path(&id));
    CompanionV1HostSession {
        id: id.clone(),
        title: request
            .title
            .as_deref()
            .map(str::trim)
            .filter(|title| !title.is_empty())
            .unwrap_or("Companion meeting")
            .to_string(),
        source: if supplied_audio_path.is_some() {
            "deviceFlash".to_string()
        } else {
            "hostMicrophone".to_string()
        },
        status: "recording".to_string(),
        pending_reason: None,
        started_at: Some(now.to_string()),
        stopped_at: None,
        duration_ms,
        audio_path: Some(audio_path.clone()),
        audio_bytes,
        chunks: vec![audio_chunk(
            &format!("{id}-chunk-1"),
            Some(audio_path.clone()),
            Some(now.to_string()),
            None,
            duration_ms,
            audio_bytes,
            "open",
        )],
        transcript_text: String::new(),
        transcript_preview: String::new(),
        transcript_segments: 0,
        utterances: Vec::new(),
        minutes: None,
        export_markdown: String::new(),
        exported_at: None,
        retention: session_retention(true, false, false),
    }
}

fn create_synced_device_session(
    snapshot: &CompanionV1Snapshot,
    request: &CompanionV1ControlRequest,
    now: &str,
) -> CompanionV1HostSession {
    let duration_ms = request
        .duration_ms
        .unwrap_or(COMPANION_V1_DEVICE_FLASH_RECORDING_MAX_SECONDS * 1000);
    let audio_bytes = request
        .audio_bytes
        .unwrap_or_else(|| estimate_pcm_bytes(duration_ms));
    let audio_path = request
        .audio_path
        .clone()
        .unwrap_or_else(|| "device://companion/flash/latest.wav".to_string());
    let mut session = create_host_session(
        snapshot,
        &CompanionV1ControlRequest {
            action: CompanionV1ControlAction::MeetingStart,
            ble_name: None,
            session_id: request.session_id.clone(),
            prompt_id: None,
            title: Some(
                request
                    .title
                    .clone()
                    .unwrap_or_else(|| "Companion device recording".to_string()),
            ),
            transcript_text: None,
            audio_path: Some(audio_path.clone()),
            audio_bytes: Some(audio_bytes),
            device_id: request.device_id.clone(),
            duration_ms: Some(duration_ms),
        },
        now,
    );
    session.source = "deviceFlash".to_string();
    session.status = "captured".to_string();
    session.pending_reason = Some("needs_transcription".to_string());
    session.started_at = None;
    session.stopped_at = Some(now.to_string());
    session.duration_ms = duration_ms;
    session.audio_bytes = audio_bytes;
    session.chunks = vec![audio_chunk(
        &format!("{}-flash-cache", session.id),
        Some(audio_path),
        None,
        Some(now.to_string()),
        duration_ms,
        audio_bytes,
        "synced",
    )];
    session.retention = session_retention(true, false, false);
    session
}

fn apply_transcript(
    snapshot: &mut CompanionV1Snapshot,
    index: usize,
    transcript: String,
    from_import: bool,
) {
    if from_import && snapshot.host.sessions[index].source == "fixture" {
        snapshot.host.sessions[index].source = "importedTranscript".to_string();
    }
    snapshot.host.sessions[index].status = "transcribed".to_string();
    snapshot.host.sessions[index].pending_reason = None;
    snapshot.host.sessions[index].transcript_preview = preview_text(&transcript);
    snapshot.host.sessions[index].transcript_segments = split_segments(&transcript).len();
    snapshot.host.sessions[index].transcript_text = transcript;
    snapshot.host.sessions[index]
        .retention
        .transcript_cached = true;
    snapshot.meeting.active = false;
    snapshot.meeting.status = "transcribed".to_string();
    snapshot.meeting.transcript_count = count_transcript_sessions(snapshot);
}

fn ensure_selected_session(
    snapshot: &mut CompanionV1Snapshot,
    request: &CompanionV1ControlRequest,
    now: &str,
) -> usize {
    if let Some(id) = request.session_id.as_deref() {
        if let Some(index) = snapshot
            .host
            .sessions
            .iter()
            .position(|session| session.id == id)
        {
            snapshot.host.selected_session_id = Some(id.to_string());
            return index;
        }
    }
    if let Some(id) = snapshot
        .host
        .selected_session_id
        .as_deref()
        .or(snapshot.host.active_session_id.as_deref())
    {
        if let Some(index) = snapshot
            .host
            .sessions
            .iter()
            .position(|session| session.id == id)
        {
            return index;
        }
    }
    if !snapshot.host.sessions.is_empty() {
        snapshot.host.selected_session_id = Some(snapshot.host.sessions[0].id.clone());
        return 0;
    }

    let mut session = create_host_session(snapshot, request, now);
    session.status = "captured".to_string();
    session.pending_reason = Some("needs_transcription".to_string());
    session.started_at = None;
    session.stopped_at = Some(now.to_string());
    snapshot.host.selected_session_id = Some(session.id.clone());
    snapshot.host.sessions.insert(0, session);
    0
}

fn audio_chunk(
    id: &str,
    path: Option<String>,
    started_at: Option<String>,
    stopped_at: Option<String>,
    duration_ms: u64,
    bytes: u64,
    status: &str,
) -> CompanionV1AudioChunk {
    CompanionV1AudioChunk {
        id: id.to_string(),
        path,
        started_at,
        stopped_at,
        duration_ms,
        bytes,
        status: status.to_string(),
    }
}

fn seal_session_chunks(
    session: &CompanionV1HostSession,
    now: &str,
    duration_ms: u64,
    audio_bytes: Option<u64>,
) -> Vec<CompanionV1AudioChunk> {
    let total_bytes = audio_bytes.unwrap_or_else(|| estimate_pcm_bytes(duration_ms));
    let Some(audio_path) = session.audio_path.clone() else {
        return session.chunks.clone();
    };
    let chunk_duration_ms = COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS * 1000;
    let chunk_count = ((duration_ms.max(1) + chunk_duration_ms - 1) / chunk_duration_ms).max(1);
    let mut chunks = Vec::new();
    let mut remaining_bytes = total_bytes;

    for index in 0..chunk_count {
        let elapsed_before = index * chunk_duration_ms;
        let chunk_ms = if index == chunk_count - 1 {
            duration_ms.saturating_sub(elapsed_before)
        } else {
            chunk_duration_ms.min(duration_ms.saturating_sub(elapsed_before))
        };
        let bytes = if index == chunk_count - 1 {
            remaining_bytes
        } else if duration_ms > 0 {
            ((total_bytes as f64) * (chunk_ms as f64 / duration_ms as f64)).round() as u64
        } else {
            0
        };
        remaining_bytes = remaining_bytes.saturating_sub(bytes);
        chunks.push(audio_chunk(
            &format!("{}-chunk-{}", session.id, index + 1),
            Some(chunk_path(&audio_path, index, chunk_count)),
            if index == 0 {
                session.started_at.clone()
            } else {
                None
            },
            Some(now.to_string()),
            chunk_ms,
            bytes,
            "sealed",
        ));
    }
    chunks
}

pub fn seal_companion_v1_session_chunks(
    session: &CompanionV1HostSession,
    now: &str,
    duration_ms: u64,
    audio_bytes: Option<u64>,
) -> Vec<CompanionV1AudioChunk> {
    seal_session_chunks(session, now, duration_ms, audio_bytes)
}

fn default_host_audio_path(session_id: &str) -> String {
    format!("host://companion-type/recordings/{session_id}.wav")
}

fn chunk_path(base_path: &str, index: u64, total: u64) -> String {
    if total <= 1 || !base_path.starts_with("host://") {
        return base_path.to_string();
    }
    format!("{base_path}#chunk-{number:03}", number = index + 1)
}

fn session_retention(
    audio_cached: bool,
    transcript_cached: bool,
    minutes_cached: bool,
) -> CompanionV1SessionRetention {
    CompanionV1SessionRetention {
        audio_cached,
        transcript_cached,
        minutes_cached,
        consent_required: true,
        retention_label: "7 days local".to_string(),
        expires_at: None,
    }
}

fn estimate_pcm_bytes(duration_ms: u64) -> u64 {
    duration_ms.saturating_mul(COMPANION_V1_RAW_PCM_BYTES_PER_SECOND) / 1000
}

fn refresh_privacy_state(
    snapshot: &CompanionV1Snapshot,
    last_erase_at: Option<String>,
) -> CompanionV1PrivacyState {
    let audio_cache_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| session.audio_bytes)
        .sum();
    let transcript_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| session.transcript_text.as_bytes().len() as u64)
        .sum();
    let minutes_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| session.export_markdown.as_bytes().len() as u64)
        .sum();
    CompanionV1PrivacyState {
        audio_cache_bytes,
        transcript_bytes,
        minutes_bytes,
        last_erase_at,
        ..snapshot.privacy.clone()
    }
}

fn build_minutes(
    session: &CompanionV1HostSession,
    generated_at: &str,
) -> CompanionV1MeetingMinutes {
    let segments = split_segments(&session.transcript_text);
    let summary = if segments.is_empty() {
        vec!["No transcript content was available.".to_string()]
    } else {
        segments.iter().take(4).cloned().collect()
    };
    let decisions = segments
        .iter()
        .filter(|segment| has_decision_marker(segment))
        .take(5)
        .cloned()
        .collect::<Vec<_>>();
    let action_items = segments
        .iter()
        .filter(|segment| has_action_marker(segment))
        .take(8)
        .map(|segment| CompanionV1ActionItem {
            text: segment.clone(),
            owner: extract_marker_value(segment, "owner"),
            due: extract_marker_value(segment, "due"),
        })
        .collect::<Vec<_>>();
    let questions = segments
        .iter()
        .filter(|segment| segment.contains('?') || segment.contains('\u{ff1f}'))
        .take(5)
        .cloned()
        .collect::<Vec<_>>();
    let keywords = extract_keywords(&session.transcript_text);

    let mut minutes = CompanionV1MeetingMinutes {
        generated_at: generated_at.to_string(),
        source: "rules_l0".to_string(),
        quality: "draft".to_string(),
        summary,
        decisions,
        action_items,
        questions,
        keywords,
        markdown: String::new(),
    };
    minutes.markdown = render_minutes_markdown(session, &minutes);
    minutes
}

fn normalize_transcript(text: &str) -> String {
    text.replace("\r\n", "\n")
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .collect::<Vec<_>>()
        .join("\n")
}

fn split_segments(text: &str) -> Vec<String> {
    normalize_transcript(text)
        .lines()
        .flat_map(|line| line.split(". "))
        .map(str::trim)
        .filter(|segment| !segment.is_empty())
        .map(str::to_string)
        .collect()
}

fn preview_text(text: &str) -> String {
    let normalized = normalize_transcript(text);
    if normalized.chars().count() > 220 {
        format!("{}...", normalized.chars().take(217).collect::<String>())
    } else {
        normalized
    }
}

fn has_decision_marker(segment: &str) -> bool {
    let lower = segment.to_ascii_lowercase();
    lower.contains("decision")
        || lower.contains("decided")
        || lower.contains("agreed")
        || lower.contains("approved")
        || lower.contains("conclusion")
        || segment.contains("\u{51b3}\u{5b9a}")
        || segment.contains("\u{7ed3}\u{8bba}")
        || segment.contains("\u{540c}\u{610f}")
}

fn has_action_marker(segment: &str) -> bool {
    let lower = segment.to_ascii_lowercase();
    lower.contains("action")
        || lower.contains("todo")
        || lower.contains("follow up")
        || lower.contains("owner")
        || lower.contains("due")
        || lower.contains("assigned")
        || lower.contains("need to")
        || segment.contains("\u{8d1f}\u{8d23}")
        || segment.contains("\u{8ddf}\u{8fdb}")
        || segment.contains("\u{5f85}\u{529e}")
        || segment.contains("\u{9700}\u{8981}")
        || segment.contains("\u{5b89}\u{6392}")
}

fn extract_marker_value(segment: &str, marker: &str) -> Option<String> {
    let lower = segment.to_ascii_lowercase();
    let start = lower.find(marker)?;
    let after = &segment[start + marker.len()..];
    let value = after
        .trim_start_matches(|ch: char| ch.is_whitespace() || ch == ':' || ch == '=' || ch == '-')
        .split_whitespace()
        .take(3)
        .collect::<Vec<_>>()
        .join(" ");
    if value.is_empty() {
        None
    } else {
        Some(value)
    }
}

fn extract_keywords(text: &str) -> Vec<String> {
    let mut tokens = text
        .split(|ch: char| !ch.is_ascii_alphanumeric() && ch != '_' && ch != '-')
        .map(str::to_ascii_lowercase)
        .filter(|token| token.len() >= 3)
        .filter(|token| {
            !matches!(
                token.as_str(),
                "and"
                    | "are"
                    | "but"
                    | "for"
                    | "from"
                    | "have"
                    | "meeting"
                    | "need"
                    | "that"
                    | "the"
                    | "this"
                    | "will"
                    | "with"
            )
        })
        .collect::<Vec<_>>();
    tokens.sort();
    tokens.dedup();
    tokens.truncate(10);
    tokens
}

fn render_minutes_markdown(
    session: &CompanionV1HostSession,
    minutes: &CompanionV1MeetingMinutes,
) -> String {
    let mut lines = vec![
        format!("# {}", session.title),
        String::new(),
        format!("Generated: {}", minutes.generated_at),
        format!("Duration: {}", format_duration(session.duration_ms)),
        format!("Source: {}", session.source),
        format!("Minutes engine: {} ({})", minutes.source, minutes.quality),
        String::new(),
        "## Summary".to_string(),
    ];
    lines.extend(minutes.summary.iter().map(|item| format!("- {item}")));
    lines.push(String::new());
    lines.push("## Decisions".to_string());
    if minutes.decisions.is_empty() {
        lines.push("- None captured".to_string());
    } else {
        lines.extend(minutes.decisions.iter().map(|item| format!("- {item}")));
    }
    lines.push(String::new());
    lines.push("## Action Items".to_string());
    if minutes.action_items.is_empty() {
        lines.push("- None captured".to_string());
    } else {
        lines.extend(minutes.action_items.iter().map(|item| {
            let meta = [
                item.owner.as_ref().map(|owner| format!("owner: {owner}")),
                item.due.as_ref().map(|due| format!("due: {due}")),
            ]
            .into_iter()
            .flatten()
            .collect::<Vec<_>>()
            .join(", ");
            if meta.is_empty() {
                format!("- {}", item.text)
            } else {
                format!("- {} ({meta})", item.text)
            }
        }));
    }
    lines.push(String::new());
    lines.push("## Questions".to_string());
    if minutes.questions.is_empty() {
        lines.push("- None captured".to_string());
    } else {
        lines.extend(minutes.questions.iter().map(|item| format!("- {item}")));
    }
    lines.push(String::new());
    lines.push("## Keywords".to_string());
    lines.push(if minutes.keywords.is_empty() {
        "None captured".to_string()
    } else {
        minutes.keywords.join(", ")
    });
    lines.push(String::new());
    lines.join("\n")
}

fn format_duration(duration_ms: u64) -> String {
    let total_seconds = duration_ms / 1000;
    let hours = total_seconds / 3600;
    let minutes = (total_seconds % 3600) / 60;
    let seconds = total_seconds % 60;
    if hours > 0 {
        format!("{hours}h {minutes}m")
    } else if minutes > 0 {
        format!("{minutes}m {seconds}s")
    } else {
        format!("{seconds}s")
    }
}

fn count_transcript_sessions(snapshot: &CompanionV1Snapshot) -> u32 {
    snapshot
        .host
        .sessions
        .iter()
        .filter(|session| !session.transcript_text.trim().is_empty())
        .count() as u32
}

fn characteristic_for_action(action: CompanionV1ControlAction) -> &'static str {
    match action {
        CompanionV1ControlAction::DeviceScan
        | CompanionV1ControlAction::DeviceConnect
        | CompanionV1ControlAction::DeviceDisconnect
        | CompanionV1ControlAction::DeviceSyncRecordings => COMPANION_V1_HOST_DEVICE_CHANNEL,
        CompanionV1ControlAction::StageBleName
        | CompanionV1ControlAction::ApplyBleName
        | CompanionV1ControlAction::ResetBleName => COMPANION_V1_GATT_BOUNDARY.ble_name_config_uuid,
        CompanionV1ControlAction::OobeRunChecks => COMPANION_V1_HOST_SETUP_CHANNEL,
        CompanionV1ControlAction::MeetingStart
        | CompanionV1ControlAction::MeetingStop
        | CompanionV1ControlAction::MeetingFinalize => {
            COMPANION_V1_GATT_BOUNDARY.meeting_control_uuid
        }
        CompanionV1ControlAction::MeetingImportTranscript
        | CompanionV1ControlAction::MeetingTranscribeAudio
        | CompanionV1ControlAction::MeetingResetSession => COMPANION_V1_HOST_RECORDING_CHANNEL,
        CompanionV1ControlAction::MeetingGenerateMinutes
        | CompanionV1ControlAction::MeetingExportMarkdown
        | CompanionV1ControlAction::MeetingExportTxt
        | CompanionV1ControlAction::MeetingExportJson
        | CompanionV1ControlAction::MeetingExportSrt
        | CompanionV1ControlAction::MeetingLoadDemo => COMPANION_V1_HOST_MINUTES_CHANNEL,
        CompanionV1ControlAction::SpeakerPrompt | CompanionV1ControlAction::SpeakerStop => {
            COMPANION_V1_GATT_BOUNDARY.speaker_control_uuid
        }
        CompanionV1ControlAction::PrivacyEraseAudio
        | CompanionV1ControlAction::PrivacyEraseTranscript
        | CompanionV1ControlAction::PrivacyEraseAll => COMPANION_V1_HOST_PRIVACY_CHANNEL,
        CompanionV1ControlAction::WakeArm
        | CompanionV1ControlAction::WakeDisable
        | CompanionV1ControlAction::WakeTestDetect => {
            COMPANION_V1_GATT_BOUNDARY.wake_word_control_uuid
        }
    }
}

fn payload_hex(request: &CompanionV1ControlRequest) -> String {
    if host_only_action(request.action) {
        let payload = format!(
            "{:?}:{}:{}",
            request.action,
            request.session_id.as_deref().unwrap_or_default(),
            request.title.as_deref().unwrap_or_default()
        );
        return payload
            .as_bytes()
            .iter()
            .take(48)
            .map(|byte| format!("{byte:02x}"))
            .collect::<Vec<_>>()
            .join("");
    }

    let mut bytes = vec![action_command(request.action)];
    if matches!(
        request.action,
        CompanionV1ControlAction::StageBleName
            | CompanionV1ControlAction::ApplyBleName
            | CompanionV1ControlAction::ResetBleName
    ) {
        bytes.push(COMPANION_V1_BLE_NAME_MAX_BYTES as u8);
        bytes.extend(
            request
                .ble_name
                .as_deref()
                .unwrap_or("")
                .as_bytes()
                .iter()
                .take(COMPANION_V1_BLE_NAME_MAX_BYTES),
        );
    }
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn action_command(action: CompanionV1ControlAction) -> u8 {
    match action {
        CompanionV1ControlAction::DeviceScan => 0x10,
        CompanionV1ControlAction::DeviceConnect => 0x11,
        CompanionV1ControlAction::DeviceDisconnect => 0x12,
        CompanionV1ControlAction::DeviceSyncRecordings => 0x13,
        CompanionV1ControlAction::OobeRunChecks => 0x20,
        CompanionV1ControlAction::StageBleName
        | CompanionV1ControlAction::MeetingStart
        | CompanionV1ControlAction::SpeakerPrompt
        | CompanionV1ControlAction::WakeArm => 1,
        CompanionV1ControlAction::ApplyBleName
        | CompanionV1ControlAction::MeetingStop
        | CompanionV1ControlAction::SpeakerStop
        | CompanionV1ControlAction::WakeDisable => 2,
        CompanionV1ControlAction::ResetBleName
        | CompanionV1ControlAction::MeetingFinalize
        | CompanionV1ControlAction::WakeTestDetect => 3,
        CompanionV1ControlAction::MeetingImportTranscript => 0x81,
        CompanionV1ControlAction::MeetingGenerateMinutes => 0x82,
        CompanionV1ControlAction::MeetingExportMarkdown => 0x83,
        CompanionV1ControlAction::MeetingExportTxt => 0x87,
        CompanionV1ControlAction::MeetingExportJson => 0x88,
        CompanionV1ControlAction::MeetingExportSrt => 0x89,
        CompanionV1ControlAction::MeetingResetSession => 0x84,
        CompanionV1ControlAction::MeetingTranscribeAudio => 0x85,
        CompanionV1ControlAction::MeetingLoadDemo => 0x86,
        CompanionV1ControlAction::PrivacyEraseAudio => 0x90,
        CompanionV1ControlAction::PrivacyEraseTranscript => 0x91,
        CompanionV1ControlAction::PrivacyEraseAll => 0x92,
    }
}

fn host_only_action(action: CompanionV1ControlAction) -> bool {
    matches!(
        action,
        CompanionV1ControlAction::DeviceScan
            | CompanionV1ControlAction::DeviceConnect
            | CompanionV1ControlAction::DeviceDisconnect
            | CompanionV1ControlAction::DeviceSyncRecordings
            | CompanionV1ControlAction::OobeRunChecks
            | CompanionV1ControlAction::MeetingImportTranscript
            | CompanionV1ControlAction::MeetingTranscribeAudio
            | CompanionV1ControlAction::MeetingGenerateMinutes
            | CompanionV1ControlAction::MeetingExportMarkdown
            | CompanionV1ControlAction::MeetingExportTxt
            | CompanionV1ControlAction::MeetingExportJson
            | CompanionV1ControlAction::MeetingExportSrt
            | CompanionV1ControlAction::MeetingLoadDemo
            | CompanionV1ControlAction::MeetingResetSession
            | CompanionV1ControlAction::PrivacyEraseAudio
            | CompanionV1ControlAction::PrivacyEraseTranscript
            | CompanionV1ControlAction::PrivacyEraseAll
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ble_name_policy_matches_firmware_contract() {
        assert!(companion_ble_name_is_valid("companion-v1"));
        assert!(companion_ble_name_is_valid("companion lab"));
        assert!(!companion_ble_name_is_valid(""));
        assert!(!companion_ble_name_is_valid("companion=lab"));
        assert!(!companion_ble_name_is_valid(
            "companion-123456789012345678901"
        ));
    }

    #[test]
    fn stage_ble_name_uses_settings_characteristic() {
        let snapshot = apply_fixture_control(
            fixture_snapshot(),
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::StageBleName,
                ble_name: Some("companion-v1".to_string()),
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let echo = snapshot.last_control.unwrap();
        assert_eq!(
            echo.characteristic_uuid,
            COMPANION_V1_GATT_BOUNDARY.ble_name_config_uuid
        );
        assert!(echo.payload_hex.starts_with("011d"));
    }

    #[test]
    fn meeting_finalize_is_separate_state() {
        let snapshot = apply_fixture_control(
            fixture_snapshot(),
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingFinalize,
                ble_name: None,
                session_id: Some("meeting-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        assert_eq!(snapshot.meeting.status, "finalized");
        assert_eq!(snapshot.meeting.transcript_count, 0);
    }

    #[test]
    fn host_minutes_workflow_exports_markdown() {
        let initial = fixture_snapshot();
        let started = apply_fixture_control(
            initial,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStart,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: Some("Companion host workflow".to_string()),
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let stopped = apply_fixture_control(
            started,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStop,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: Some(3_600_000),
            },
        )
        .unwrap();
        let stopped_session = stopped.host.sessions.first().unwrap();
        assert_eq!(
            stopped_session.chunks.len() as u64,
            COMPANION_V1_ONE_HOUR_CHUNKS
        );
        assert_eq!(
            stopped_session
                .chunks
                .iter()
                .map(|chunk| chunk.bytes)
                .sum::<u64>(),
            COMPANION_V1_ONE_HOUR_RAW_PCM_BYTES
        );
        assert!(stopped_session
            .chunks
            .iter()
            .all(|chunk| chunk.duration_ms <= COMPANION_V1_HOST_RECORDING_CHUNK_SECONDS * 1000));
        assert!(stopped_session
            .chunks
            .iter()
            .all(|chunk| chunk.bytes < COMPANION_V1_ASR_UPLOAD_MAX_BYTES));
        let transcribed = apply_fixture_control(
            stopped,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingImportTranscript,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: Some("Decision: host owns long recordings.\nAction owner: Chen due: July 5 validates Markdown.\nQuestion: wake word now?".to_string()),
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let exported = apply_fixture_control(
            transcribed,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingExportMarkdown,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let session = exported.host.sessions.first().unwrap();
        assert_eq!(exported.meeting.status, "minutesReady");
        assert!(session
            .export_markdown
            .contains("# Companion host workflow"));
        assert!(session.export_markdown.contains("## Action Items"));
    }
}
