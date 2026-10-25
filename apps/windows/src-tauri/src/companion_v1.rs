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
    pub device_status_service_uuid: &'static str,
    pub device_status_uuid: &'static str,
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
    device_status_service_uuid: "8f7a0001-7b7d-4f3d-9d6f-6c2d1b7c0000",
    device_status_uuid: "8f7a1001-7b7d-4f3d-9d6f-6c2d1b7c0000",
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
    pub minutes_context_supported: bool,
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
    pub find_supported: bool,
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
    /// Last valid DEVICE_STATUS.active_mode reading. This is board capture
    /// state, independent from the host meeting reducer.
    pub recording: bool,
    pub last_sync_at: Option<String>,
    pub firmware_version: Option<u32>,
    pub build_id: Option<u32>,
    pub board_id: Option<u32>,
    pub hardware_revision: Option<String>,
    /// Raw 96-bit STM32 UID bytes, lowercase hex, when exposed by the WBA
    /// backward-compatible DEVICE_STATUS tail.
    pub mcu_uid: Option<String>,
    /// Active, validated UI resource generation reported by WBA. None on
    /// legacy 20-byte DEVICE_STATUS payloads or before assets mount.
    pub ui_generation: Option<u32>,
    pub recording_capacity: Option<CompanionV1RecordingCapacity>,
    /// Transactional BLE state. `ready` means the exact device was verified;
    /// the GATT link itself is opened on demand for each operation.
    pub connection_phase: String,
    pub remembered_device_id: Option<String>,
    pub auto_reconnect_enabled: bool,
    pub manual_disconnect: bool,
    pub last_connected_at: Option<String>,
    pub last_reconnect_attempt_at: Option<String>,
    pub reconnect_attempt_count: u32,
    pub message: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1RecordingCapacity {
    pub layout_version: u8,
    pub busy: bool,
    pub confirmed_discard_supported: bool,
    pub used_entries: u8,
    pub max_entries: u8,
    pub catalog_generation: u32,
    pub data_bytes: u32,
    pub free_bytes: u32,
    pub largest_free_extent: u32,
    pub protected_bytes: u32,
    pub consumed_bytes: u32,
    pub bytes_per_second: u32,
    pub reserve_headroom: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub segment_frames: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub segment_extent_bytes: Option<u32>,
    pub local_limit_seconds: u32,
    pub unsynced_entries: u8,
    pub writing_entries: u8,
    pub consumed_entries: u8,
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
    /// Host-only result of the latest explicit cleanup in this app session.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_cleanup: Option<CompanionV1PrivacyCleanup>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1PrivacyCleanup {
    pub operation: &'static str,
    pub completed_at: String,
    pub deleted_files: usize,
    pub skipped_files: usize,
    pub shared_files: usize,
    pub unverified_cache_files: usize,
    /// File effects can precede an index-save failure; never imply both succeeded.
    pub index_saved: bool,
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
    #[serde(default = "default_supported_meeting_modes")]
    pub supported_meeting_modes: Vec<String>,
    #[serde(default = "default_meeting_mode_offline")]
    pub default_meeting_mode: String,
    #[serde(default = "default_offline_store_guide")]
    pub offline_store_guide: String,
    #[serde(default = "default_online_live_guide")]
    pub online_live_guide: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1HostState {
    pub persistence: CompanionV1PersistenceState,
    pub recording_policy: CompanionV1RecordingPolicy,
    pub active_session_id: Option<String>,
    pub selected_session_id: Option<String>,
    pub sessions: Vec<CompanionV1HostSession>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1PersistenceState {
    pub status: String,
    pub message: Option<String>,
    pub recovery_path: Option<String>,
}

impl Default for CompanionV1PersistenceState {
    fn default() -> Self {
        Self { status: "ready".into(), message: None, recovery_path: None }
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1RecordingKey {
    // Strings preserve all 64 bits through the desktop/JavaScript boundary.
    pub device_uid: String,
    pub format_epoch: String,
    pub session_id: String,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub enum CompanionV1RecordingEndReason { User, StorageFull, DurationLimit, LowBattery, Silence }
impl CompanionV1RecordingEndReason {
    pub(crate) fn from_code(code:u8)->Result<Option<Self>,String> {
        Ok(match code {0=>None,1=>Some(Self::User),2=>Some(Self::StorageFull),
            3=>Some(Self::DurationLimit),4=>Some(Self::LowBattery),5=>Some(Self::Silence),
            _=>return Err("设备录音停止原因不受支持，未声明保存或回收。".into())})
    }
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1HostSession {
    pub id: String,
    pub title: String,
    pub source: String,
    pub status: String,
    /// offlineStore = store-first batch ASR later; onlineLive = live partials while recording.
    #[serde(default = "default_meeting_mode_offline")]
    pub meeting_mode: String,
    /// Durable user choice, separate from retry/recovery state. Old rows retain
    /// automatic behavior; a plain recording only uses cloud services on demand.
    #[serde(default)]
    pub processing_policy: CompanionV1ProcessingPolicy,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pending_reason: Option<String>,
    pub started_at: Option<String>,
    pub stopped_at: Option<String>,
    pub duration_ms: u64,
    pub audio_path: Option<String>,
    pub audio_bytes: u64,
    #[serde(default)]
    pub audio_stored: bool,
    /// Stable durable-board identity. None for host/imported sessions.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub device_recording_id: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub device_recording_key: Option<CompanionV1RecordingKey>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub device_total_length: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub device_sha256: Option<String>,
    /// True only after the exact board extent acknowledged reclaim.
    #[serde(default)]
    pub device_reclaimed: bool,
    #[serde(default)]
    pub capture_incomplete: bool,
    /// CRC-checked device terminal metadata/live exact original, never a UI guess.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub device_recording_end_reason: Option<CompanionV1RecordingEndReason>,
    /// Exact native Bluetooth address that produced the durable board extent.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_device_id: Option<String>,
    /// Exact CMC3 intent/confirmation belonging to this original device row.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub recorder_control: Option<crate::backend::recorder_control::Journal>,
    /// Restart/disconnection is uncertainty, never an invented STOP.
    #[serde(default)]
    pub recorder_control_uncertain: bool,
    pub chunks: Vec<CompanionV1AudioChunk>,
    pub transcript_text: String,
    /// True only for a completed batch/import result. onlineLive prefixes are
    /// intentionally false so restart recovery cannot mistake them for final.
    #[serde(default)]
    pub transcript_final: bool,
    #[serde(default)]
    pub live_transcript_text: String,
    pub transcript_preview: String,
    pub transcript_segments: usize,
    /// Timed, speaker-attributed utterances from the diarization-aware
    /// transcription path. Empty for sessions transcribed before this field
    /// existed or when diarization timing is unavailable.
    #[serde(default)]
    pub utterances: Vec<CompanionV1UtteranceSegment>,
    /// Human review is an overlay; never replace the provider's ASR evidence.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub transcript_review: Option<crate::backend::transcript_review::TranscriptReview>,
    #[serde(default)]
    pub bookmark_revision: u64,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub bookmarks: Vec<crate::backend::recording_bookmarks::Bookmark>,
    #[serde(default,skip_serializing_if="crate::backend::library_organization::Metadata::is_empty")]
    pub organization: crate::backend::library_organization::Metadata,
    /// Imported device-event IDs survive a user deleting a bookmark. A
    /// repeated segment publication must not resurrect that deleted point.
    #[serde(default,skip_serializing_if="Vec::is_empty")]
    pub device_bookmark_imports: Vec<String>,
    #[serde(default)]
    pub note_revision: u64,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub meeting_notes: Vec<crate::backend::meeting_notes::Note>,
    pub minutes: Option<CompanionV1MeetingMinutes>,
    /// Two independently persisted products may coexist for one durable board recording.
    #[serde(default)]
    pub minutes_by_mode: CompanionV1MinutesByMode,
    /// Durable, explicit authorization for restart recovery. Legacy/imported
    /// WAV rows deserialize to `intent=none` and are never auto-submitted.
    #[serde(default)]
    pub recovery: CompanionV1MeetingRecovery,
    pub export_markdown: String,
    pub exported_at: Option<String>,
    pub retention: CompanionV1SessionRetention,
}

pub const CAPTURE_ONLY_PROMPT: &str = "__companion_capture_only__";

#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub enum CompanionV1ProcessingPolicy {
    #[default]
    Automatic,
    Manual,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1MeetingRecovery {
    /// `processMeeting` is set only by an explicit product capture/sync path.
    pub intent: String,
    /// Frozen at capture time so restart recovery cannot silently switch route.
    pub requested_meeting_mode: String,
    /// idle | pendingTranscription | pendingMinutes | retryBackoff | paused | complete
    pub stage: String,
    pub attempt_count: u8,
    pub max_attempts: u8,
    /// transcription | minutes; identifies what retryBackoff resumes.
    #[serde(default)]
    pub retry_stage: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub next_retry_at_unix_ms: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub last_error: Option<String>,
    /// Explicit processing choice for this recovered, immutable original.
    /// Older checkpoints default to unreviewed; syncing never authorizes it.
    #[serde(default)]
    pub capture_review_confirmed: bool,
}

impl Default for CompanionV1MeetingRecovery {
    fn default() -> Self {
        Self {
            intent: "none".to_string(),
            requested_meeting_mode: String::new(),
            stage: "idle".to_string(),
            attempt_count: 0,
            max_attempts: 3,
            retry_stage: String::new(),
            next_retry_at_unix_ms: None,
            last_error: None,
            capture_review_confirmed: false,
        }
    }
}

impl CompanionV1MeetingRecovery {
    pub(crate) fn armed(meeting_mode: &str) -> Self {
        Self {
            intent: "processMeeting".to_string(),
            requested_meeting_mode: meeting_mode.to_string(),
            stage: "pendingTranscription".to_string(),
            ..Self::default()
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1MinutesByMode {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub offline_store: Option<CompanionV1MinutesVariant>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub online_live: Option<CompanionV1MinutesVariant>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1MinutesVariant {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub processing: Option<CompanionV1MinutesProcessing>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_review_revision: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_note_context: Option<crate::backend::minutes_context::Source>,
    pub status: String,
    pub markdown: String,
    pub source: String,
    pub quality: String,
    pub generated_at: Option<String>,
    #[serde(default)]
    pub partial_count: u32,
}

fn cache_fixture_minutes_for_mode(session: &mut CompanionV1HostSession) {
    let Some(minutes) = session.minutes.as_ref() else {
        return;
    };
    let variant = CompanionV1MinutesVariant {
        processing: minutes.processing.clone(),
        source_note_context: minutes.source_note_context.clone(), source_review_revision: minutes.source_review_revision,
        status: "minutesReady".to_string(),
        markdown: minutes.markdown.clone(),
        source: minutes.source.clone(),
        quality: minutes.quality.clone(),
        generated_at: Some(minutes.generated_at.clone()),
        partial_count: 0,
    };
    if session.meeting_mode == "onlineLive" {
        session.minutes_by_mode.online_live = Some(variant);
    } else {
        session.minutes_by_mode.offline_store = Some(variant);
    }
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
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub processing: Option<CompanionV1MinutesProcessing>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_review_revision: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_note_context: Option<crate::backend::minutes_context::Source>,
    pub generated_at: String,
    pub source: String,
    pub quality: String,
    pub summary: Vec<String>,
    pub decisions: Vec<String>,
    pub action_items: Vec<CompanionV1ActionItem>,
    pub questions: Vec<String>,
    pub keywords: Vec<String>,
    pub markdown: String,
    /// LLM downgrade reason. Populated when L1 (DeepSeek) failed and we fell
    /// back to the L0 rule draft, so the UI can surface *why* final minutes
    /// weren't produced instead of silently showing a draft. None in normal
    /// operation. `default` lets persisted sessions that predate this field
    /// deserialize without the key.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub llm_note: Option<String>,
}

/// Coverage of the submitted source, not a claim of semantic accuracy.
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionV1MinutesProcessing {
    pub strategy: String,
    pub source_bytes: usize,
    pub processed_source_bytes: usize,
    pub total_chunks: usize,
    pub completed_chunks: usize,
    pub resumed_chunks: usize,
    pub complete: bool,
}

impl CompanionV1MinutesProcessing {
    pub fn is_complete(&self) -> bool {
        self.strategy == "chunkedSourceBacked"
            && self.complete && self.total_chunks != 0
            && self.completed_chunks == self.total_chunks
            && self.resumed_chunks <= self.completed_chunks
            && self.source_bytes != 0 && self.processed_source_bytes == self.source_bytes
    }
}

/// One timed, speaker-attributed transcript utterance. Populated by the
/// diarization-aware transcription path so exports can render timed formats
/// (SRT subtitles) and the UI can show per-utterance speaker/timing. `speaker`
/// is a 0-based diarization id; `None` when diarization could not attribute it.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
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
    HostRetrySave,
    MeetingRestoreAudio,
    DeviceScan,
    DeviceConnect,
    DeviceDisconnect,
    DeviceEnableAutoReconnect,
    DeviceDisableAutoReconnect,
    DeviceSyncRecordings,
    StageBleName,
    ApplyBleName,
    ResetBleName,
    OobeRunChecks,
    MeetingStart,
    MeetingStop,
    MeetingFinalize,
    MeetingPause,
    MeetingResume,
    MeetingRecoverControl,
    MeetingAppendLiveTranscript,
    MeetingImportTranscript,
    MeetingTranscribeAudio,
    MeetingGenerateMinutes,
    MeetingExportMarkdown,
    MeetingExportTxt,
    MeetingExportJson,
    MeetingExportSrt,
    MeetingExportActionsTodo,
    MeetingExportActionsIcal,
    MeetingLoadDemo,
    MeetingSelectSession,
    MeetingResetSession,
    PrivacyEraseAudio,
    PrivacyEraseTranscript,
    PrivacyEraseAll,
    PrivacyDeleteSession,
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
    /// Explicit one-time inclusion of this exact saved note revision; never recovery consent.
    #[serde(default)]
    pub context_note_revision: Option<u64>,
    pub ble_name: Option<String>,
    pub session_id: Option<String>,
    pub prompt_id: Option<String>,
    pub title: Option<String>,
    pub transcript_text: Option<String>,
    pub meeting_mode: Option<String>,
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
        minutes_context_supported: false,
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
            supported: false,
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
            supported: false,
            find_supported: false,
            online: false,
            muted: true,
            volume: 0,
            status: "notPopulated".to_string(),
        },
        wake_word: CompanionV1WakeWordState {
            supported: false,
            armed: false,
            engine: "notPopulated".to_string(),
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
    snapshot: CompanionV1Snapshot,
    request: CompanionV1ControlRequest,
) -> Result<CompanionV1Snapshot, String> {
    apply_control_at(snapshot, request, "fixture")
}

/// Pure state transition with a caller-owned observation time. The product
/// backend supplies the wall clock; fixtures retain their deterministic clock.
pub(crate) fn apply_control_at(
    mut snapshot: CompanionV1Snapshot,
    request: CompanionV1ControlRequest,
    observed_at: &str,
) -> Result<CompanionV1Snapshot, String> {
    let now = observed_at.to_string();
    crate::backend::library_lifecycle::validate_privacy(&snapshot,&request)?;
    snapshot.updated_at = now.clone();

    if (matches!(
        request.action,
        CompanionV1ControlAction::SpeakerPrompt | CompanionV1ControlAction::SpeakerStop
    ) && (!snapshot.connected || !snapshot.speaker.supported))
        || matches!(
            request.action,
            CompanionV1ControlAction::WakeArm
                | CompanionV1ControlAction::WakeDisable
                | CompanionV1ControlAction::WakeTestDetect
        )
    {
        return Err(
            "Companion peripheral capability is unavailable on the connected hardware".to_string(),
        );
    }

    match request.action {
        CompanionV1ControlAction::HostRetrySave => {}
        CompanionV1ControlAction::MeetingRestoreAudio => {
            return Err("回听文件恢复需要本机原音与校验记录；演示模式不会生成替代音频。".into());
        }
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
            snapshot.device.connection_phase = "discovered".to_string();
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
            snapshot.device.connection_phase = "ready".to_string();
            snapshot.connected = true;
        }
        CompanionV1ControlAction::DeviceDisconnect => {
            snapshot.device.recording_capacity=None;
            snapshot.device.connected = false;
            snapshot.device.message = "Companion device disconnected".to_string();
            snapshot.device.connection_phase = "manualDisconnected".to_string();
            snapshot.connected = false;
        }
        CompanionV1ControlAction::DeviceEnableAutoReconnect => {
            snapshot.device.auto_reconnect_enabled = true;
            snapshot.device.manual_disconnect = false;
            snapshot.device.connection_phase = if snapshot.device.remembered_device_id.is_some() {
                "offline"
            } else {
                "idle"
            }
            .to_string();
        }
        CompanionV1ControlAction::DeviceDisableAutoReconnect => {
            snapshot.device.auto_reconnect_enabled = false;
        }
        CompanionV1ControlAction::DeviceSyncRecordings => {
            let session = synced_device_session(&snapshot, &request, &now);
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
            if let Some(name) = request.ble_name.as_deref() {
                let name = name.trim();
                if !companion_ble_name_is_valid(name) {
                    return Err("BLE name must be printable ASCII and 1..29 bytes".to_string());
                }
                snapshot.ble_name.staged_name = name.to_string();
            }
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
                    "固件与板卡身份",
                    "warn",
                    "Fixture only：未连接实板，未读取 DEVICE_STATUS",
                ),
                oobe_check(
                    "bluetooth",
                    "蓝牙连接",
                    "warn",
                    "Fixture only：未执行物理扫描、配对或连接",
                ),
                oobe_check(
                    "gatt",
                    "核心 GATT",
                    "warn",
                    "Fixture only：未发现或读取实板 GATT",
                ),
                oobe_check(
                    "boardMicrophone",
                    "板端录音链路",
                    "warn",
                    "未实测；主机麦克风不能作为板端通过证据",
                ),
                oobe_check("clock", "自动校时", "warn", "未执行写后读回"),
                oobe_check("imu", "IMU", "warn", "未读取 IMU_STATUS"),
                oobe_check("speaker", "扬声器", "warn", "未读取 SPEAKER_STATUS；未播放测试音"),
                oobe_check("display", "墨水屏", "warn", "未检查；无屏幕自检 GATT"),
                oobe_check("touch", "触摸", "warn", "未检查；无触摸自检 GATT"),
                oobe_check("power", "电源与充电", "warn", "未检查；无电源/充电自检 GATT"),
                oobe_check(
                    "remoteServices",
                    "ASR / 纪要服务",
                    "warn",
                    "Fixture 检查不会调用外部服务",
                ),
            ];
        }
        CompanionV1ControlAction::MeetingPause | CompanionV1ControlAction::MeetingResume
        | CompanionV1ControlAction::MeetingRecoverControl => {
            return Err("设备暂停控制必须由正式后端确认，不能用模拟状态代替。".into());
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
            let live = snapshot.host.sessions[index]
                .live_transcript_text
                .trim()
                .to_string();
            let existing = snapshot.host.sessions[index]
                .transcript_text
                .trim()
                .to_string();
            let final_transcript = if !existing.is_empty() { existing } else { live };
            let has_transcript = !final_transcript.is_empty();
            let is_online = snapshot.host.sessions[index].meeting_mode == "onlineLive";
            let status = if has_transcript && is_online {
                "transcribed"
            } else {
                "captured"
            };
            snapshot.host.sessions[index].status = status.to_string();
            snapshot.host.sessions[index].pending_reason = if has_transcript {
                None
            } else {
                Some("needs_transcription".to_string())
            };
            snapshot.host.sessions[index].stopped_at = Some(now.clone());
            snapshot.host.sessions[index].duration_ms = duration_ms;
            snapshot.host.sessions[index].audio_bytes = request
                .audio_bytes
                .unwrap_or_else(|| estimate_pcm_bytes(duration_ms));
            snapshot.host.sessions[index].audio_stored = true;
            if has_transcript {
                snapshot.host.sessions[index].transcript_text = final_transcript.clone();
                snapshot.host.sessions[index].transcript_preview = preview_text(&final_transcript);
                snapshot.host.sessions[index].transcript_segments =
                    split_segments(&final_transcript).len();
                snapshot.host.sessions[index].retention.transcript_cached = true;
            }
            snapshot.host.sessions[index].retention.audio_cached = true;
            snapshot.host.sessions[index].chunks = seal_session_chunks(
                &snapshot.host.sessions[index],
                &now,
                duration_ms,
                request.audio_bytes,
            );
            snapshot.host.active_session_id = None;
            snapshot.meeting.active = false;
            snapshot.meeting.status = status.to_string();
            snapshot.meeting.duration_ms = duration_ms;
            snapshot.meeting.transcript_count = count_transcript_sessions(&snapshot);
        }
        CompanionV1ControlAction::MeetingAppendLiveTranscript => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            if snapshot.host.sessions[index].meeting_mode != "onlineLive" {
                return Err("Live transcript append requires meetingMode=onlineLive.".to_string());
            }
            if snapshot.host.sessions[index].status != "recording" {
                return Err(
                    "Live transcript append requires an active recording session.".to_string(),
                );
            }
            let delta = normalize_transcript(request.transcript_text.as_deref().unwrap_or(""));
            if delta.is_empty() {
                return Err("Live transcript append requires non-empty transcriptText.".to_string());
            }
            let live = if snapshot.host.sessions[index]
                .live_transcript_text
                .trim()
                .is_empty()
            {
                delta
            } else {
                normalize_transcript(&format!(
                    "{} {}",
                    snapshot.host.sessions[index].live_transcript_text, delta
                ))
            };
            snapshot.host.sessions[index].live_transcript_text = live.clone();
            snapshot.host.sessions[index].transcript_text = live.clone();
            snapshot.host.sessions[index].transcript_preview = preview_text(&live);
            snapshot.host.sessions[index].transcript_segments = split_segments(&live).len();
            snapshot.host.sessions[index].pending_reason = None;
            snapshot.host.sessions[index].retention.transcript_cached = true;
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
                snapshot.host.sessions[index].retention.minutes_cached = true;
                snapshot.host.sessions[index].minutes = Some(minutes);
                cache_fixture_minutes_for_mode(&mut snapshot.host.sessions[index]);
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
            cache_fixture_minutes_for_mode(&mut snapshot.host.sessions[index]);
            snapshot.host.sessions[index].retention.minutes_cached = true;
            snapshot.meeting.active = false;
            snapshot.meeting.status = "minutesReady".to_string();
            snapshot.meeting.transcript_count = count_transcript_sessions(&snapshot);
        }
        CompanionV1ControlAction::MeetingExportMarkdown
        | CompanionV1ControlAction::MeetingExportTxt
        | CompanionV1ControlAction::MeetingExportJson
        | CompanionV1ControlAction::MeetingExportSrt
        | CompanionV1ControlAction::MeetingExportActionsTodo
        | CompanionV1ControlAction::MeetingExportActionsIcal => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            if request
                .meeting_mode
                .as_deref()
                .is_some_and(|mode| mode != snapshot.host.sessions[index].meeting_mode)
            {
                return Err("export meeting mode does not match the selected session".to_string());
            }
            let session = &snapshot.host.sessions[index];
            let export = match request.action {
                CompanionV1ControlAction::MeetingExportMarkdown => {
                    let variant = if session.meeting_mode == "onlineLive" {
                        session.minutes_by_mode.online_live.as_ref()
                    } else {
                        session.minutes_by_mode.offline_store.as_ref()
                    }
                    .filter(|variant| !variant.markdown.trim().is_empty())
                    .ok_or_else(|| "completed minutes are required for Markdown export".to_string())?;
                    if variant.status == "minutesReady" && variant.quality != "draft" {
                        variant.markdown.clone()
                    } else {
                        format!(
                            "> 草稿：纪要服务尚未完成；以下为已保存在本机的内容。\n\n{}",
                            variant.markdown
                        )
                    }
                }
                CompanionV1ControlAction::MeetingExportTxt => {
                    let final_transcript = session.transcript_final
                        || (session.recovery.intent == "none"
                            && matches!(session.status.as_str(), "transcribed" | "minutesReady"));
                    if !final_transcript || session.transcript_text.trim().is_empty() {
                        return Err("a final transcript is required for text export".to_string());
                    }
                    crate::backend::export::render_txt(session)
                }
                CompanionV1ControlAction::MeetingExportJson => {
                    let final_transcript = session.transcript_final
                        || (session.recovery.intent == "none"
                            && matches!(session.status.as_str(), "transcribed" | "minutesReady"));
                    if !final_transcript || session.transcript_text.trim().is_empty() {
                        return Err("a final transcript is required for JSON export".to_string());
                    }
                    crate::backend::export::render_json(session)?
                }
                CompanionV1ControlAction::MeetingExportSrt => {
                    let final_transcript = session.transcript_final
                        || (session.recovery.intent == "none"
                            && matches!(session.status.as_str(), "transcribed" | "minutesReady"));
                    if !final_transcript
                        || session.utterances.is_empty()
                        || session.utterances.iter().any(|utterance| {
                            utterance.text.trim().is_empty()
                                || utterance.end_ms <= utterance.start_ms
                        })
                    {
                        return Err(
                            "SRT export requires a final transcript with real timed utterances"
                                .to_string(),
                        );
                    }
                    crate::backend::export::render_srt(session)
                }
                CompanionV1ControlAction::MeetingExportActionsTodo => {
                    if session.minutes.is_none() {
                        return Err("completed minutes are required for action export".to_string());
                    }
                    crate::backend::export::render_action_items_todo(session)
                }
                CompanionV1ControlAction::MeetingExportActionsIcal => {
                    if session.minutes.is_none() {
                        return Err("completed minutes are required for action export".to_string());
                    }
                    crate::backend::export::render_action_items_ical(session)
                }
                _ => unreachable!(),
            };
            snapshot.host.sessions[index].export_markdown = export;
            snapshot.host.sessions[index].exported_at = Some(now.clone());
            snapshot.meeting.active = false;
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
                    context_note_revision: None, ble_name: None,
                    session_id: request.session_id.clone(),
                    prompt_id: None,
                    title: Some(
                        request
                            .title
                            .clone()
                            .unwrap_or_else(|| "一键演示纪要".to_string()),
                    ),
                    transcript_text: None,
                    meeting_mode: None,
                    audio_path: Some(request.audio_path.clone().unwrap_or_else(|| {
                        "demo://companion-type/mechanical-voice.wav".to_string()
                    })),
                    audio_bytes: Some(
                        request
                            .audio_bytes
                            .unwrap_or_else(|| estimate_pcm_bytes(duration_ms)),
                    ),
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
            cache_fixture_minutes_for_mode(&mut session);
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
        CompanionV1ControlAction::MeetingSelectSession => {
            let id = request
                .session_id
                .as_deref()
                .ok_or_else(|| "sessionId is required".to_string())?;
            if !snapshot
                .host
                .sessions
                .iter()
                .any(|session| session.id == id)
            {
                return Err(format!("session not found: {id}"));
            }
            snapshot.host.selected_session_id = Some(id.to_string());
        }
        CompanionV1ControlAction::MeetingResetSession => {
            // Starting a new workspace is not authorization to erase the library.
            snapshot.host.selected_session_id = None;
            snapshot.host.active_session_id = None;
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
            snapshot.host.sessions[index].audio_stored = false;
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
            snapshot.host.sessions[index].recovery = CompanionV1MeetingRecovery::default();
            snapshot.host.sessions[index].pending_reason = None;
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
            snapshot.host.sessions[index].transcript_final = false;
            snapshot.host.sessions[index].live_transcript_text.clear();
            snapshot.host.sessions[index].transcript_preview.clear();
            snapshot.host.sessions[index].transcript_segments = 0;
            snapshot.host.sessions[index].utterances.clear();
            snapshot.host.sessions[index].transcript_review = None;
            snapshot.host.sessions[index].meeting_notes.clear();
            snapshot.host.sessions[index].note_revision = snapshot.host.sessions[index].note_revision.saturating_add(1);
            snapshot.host.sessions[index].minutes = None;
            snapshot.host.sessions[index].minutes_by_mode = Default::default();
            snapshot.host.sessions[index].export_markdown.clear();
            snapshot.host.sessions[index].exported_at = None;
            snapshot.host.sessions[index].retention.transcript_cached = false;
            snapshot.host.sessions[index].retention.minutes_cached = false;
            snapshot.host.sessions[index].recovery = CompanionV1MeetingRecovery::default();
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
        CompanionV1ControlAction::PrivacyDeleteSession => {
            let index = ensure_selected_session(&mut snapshot, &request, &now);
            let removed_id = snapshot.host.sessions[index].id.clone();
            snapshot.host.sessions.remove(index);
            snapshot.host.selected_session_id =
                snapshot.host.sessions.iter().find(|s|s.organization.trashed_at.is_none()).map(|s| s.id.clone());
            snapshot.host.active_session_id = snapshot
                .host
                .active_session_id
                .filter(|id| id != &removed_id);
            snapshot.meeting.transcript_count = count_transcript_sessions(&snapshot);
            snapshot.privacy.last_erase_at = Some(now.clone());
        }
        CompanionV1ControlAction::SpeakerPrompt => {
            snapshot.speaker.online = true;
            snapshot.speaker.status = "prompting".to_string();
        }
        CompanionV1ControlAction::SpeakerStop => {
            snapshot.speaker.status = "idle".to_string();
        }
        CompanionV1ControlAction::WakeArm
        | CompanionV1ControlAction::WakeDisable
        | CompanionV1ControlAction::WakeTestDetect => unreachable!("rejected above"),
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
        persistence: Default::default(),
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
            supported_meeting_modes: default_supported_meeting_modes(),
            default_meeting_mode: default_meeting_mode_offline(),
            offline_store_guide: default_offline_store_guide(),
            online_live_guide: default_online_live_guide(),
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
        recording: false,
        last_sync_at: None,
        firmware_version: None,
        build_id: None,
        board_id: None,
        hardware_revision: None,
        mcu_uid: None,
        ui_generation: None,
        recording_capacity: None,
        connection_phase: "idle".to_string(),
        remembered_device_id: None,
        auto_reconnect_enabled: true,
        manual_disconnect: false,
        last_connected_at: None,
        last_reconnect_attempt_at: None,
        reconnect_attempt_count: 0,
        message: "Not scanned".to_string(),
    }
}

fn default_oobe_state() -> CompanionV1OobeState {
    CompanionV1OobeState {
        complete: false,
        last_run_at: None,
        checks: vec![
            oobe_check("bluetooth", "蓝牙连接", "pending", "等待实板检查"),
            oobe_check("firmware", "固件与板卡身份", "pending", "等待实板检查"),
            oobe_check("gatt", "核心 GATT", "pending", "等待实板检查"),
            oobe_check("boardMicrophone", "板端录音链路", "pending", "等待实板检查"),
            oobe_check("clock", "自动校时", "pending", "等待实板检查"),
            oobe_check("imu", "IMU", "pending", "等待实板检查"),
            oobe_check("speaker", "扬声器", "pending", "等待实板检查"),
            oobe_check("display", "墨水屏", "pending", "等待实板观察"),
            oobe_check("touch", "触摸", "pending", "等待实板操作"),
            oobe_check("power", "电源与充电", "pending", "等待实板测量"),
            oobe_check(
                "remoteServices",
                "ASR / 纪要服务",
                "pending",
                "不在硬件检查中调用",
            ),
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
        last_cleanup: None,
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

pub(crate) fn create_host_session(
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
    let meeting_mode = request
        .meeting_mode
        .as_deref()
        .map(str::trim)
        .filter(|mode| *mode == "onlineLive" || *mode == "offlineStore")
        .map(str::to_string)
        .unwrap_or_else(|| snapshot.host.recording_policy.default_meeting_mode.clone());
    let processing_policy=if request.prompt_id.as_deref()==Some(CAPTURE_ONLY_PROMPT) {
        CompanionV1ProcessingPolicy::Manual
    } else {CompanionV1ProcessingPolicy::Automatic};
    CompanionV1HostSession {
        note_revision: 0, meeting_notes: vec![],
        bookmark_revision: 0,
        bookmarks: vec![],
        organization: Default::default(),
        device_bookmark_imports: vec![],
        transcript_review: None,
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
        meeting_mode,
        processing_policy,
        pending_reason: None,
        started_at: Some(now.to_string()),
        stopped_at: None,
        duration_ms,
        audio_path: Some(audio_path.clone()),
        audio_bytes,
        audio_stored: false,
        device_recording_id: None,
        device_recording_key: None,
        device_total_length: None,
        device_sha256: None,
        device_reclaimed: false, capture_incomplete: false, device_recording_end_reason: None,
        source_device_id: request.device_id.clone(),
        recorder_control: None, recorder_control_uncertain: false,
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
        transcript_final: false,
        live_transcript_text: String::new(),
        transcript_preview: String::new(),
        transcript_segments: 0,
        utterances: Vec::new(),
        minutes: None,
        minutes_by_mode: Default::default(),
        recovery: Default::default(),
        export_markdown: String::new(),
        exported_at: None,
        retention: session_retention(true, false, false),
    }
}

pub(crate) fn synced_device_session(
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
            context_note_revision: None, ble_name: None,
            session_id: request.session_id.clone(),
            prompt_id: None,
            title: Some(
                request
                    .title
                    .clone()
                    .unwrap_or_else(|| "Companion device recording".to_string()),
            ),
            transcript_text: None,
            meeting_mode: Some("offlineStore".to_string()),
            audio_path: Some(audio_path.clone()),
            audio_bytes: Some(audio_bytes),
            device_id: request.device_id.clone(),
            duration_ms: Some(duration_ms),
        },
        now,
    );
    session.source = "deviceFlash".to_string();
    session.meeting_mode = "offlineStore".to_string();
    session.status = "captured".to_string();
    session.pending_reason = Some("needs_transcription".to_string());
    session.recovery = CompanionV1MeetingRecovery::armed(&session.meeting_mode);
    session.started_at = None;
    session.stopped_at = Some(now.to_string());
    session.duration_ms = duration_ms;
    session.audio_bytes = audio_bytes;
    session.audio_stored = true;
    session.device_recording_id = None;
    session.device_total_length = None;
    session.device_sha256 = None;
    session.device_reclaimed = false;
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
    snapshot.host.sessions[index].transcript_final = true;
    snapshot.host.sessions[index].retention.transcript_cached = true;
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

fn default_meeting_mode_offline() -> String {
    "offlineStore".to_string()
}

fn default_supported_meeting_modes() -> Vec<String> {
    vec!["offlineStore".to_string(), "onlineLive".to_string()]
}

fn default_offline_store_guide() -> String {
    "Offline: store WAV/chunks first (no live ASR); later batch transcribe → L0/L1 minutes"
        .to_string()
}

fn default_online_live_guide() -> String {
    "Online: live partial transcript while recording; audio still stored as backup; stop → minutes"
        .to_string()
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
        retention_label: "Local until manually deleted".to_string(),
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
        .map(|session| (session.transcript_text.len() + session.meeting_notes.iter().map(|n| n.text.len()).sum::<usize>()) as u64)
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
        processing: None,
        source_note_context: None, source_review_revision: None,
        generated_at: generated_at.to_string(),
        source: "rules_l0".to_string(),
        quality: "draft".to_string(),
        summary,
        decisions,
        action_items,
        questions,
        keywords,
        markdown: String::new(),
        llm_note: None,
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
        CompanionV1ControlAction::HostRetrySave | CompanionV1ControlAction::MeetingRestoreAudio => COMPANION_V1_HOST_RECORDING_CHANNEL,
        CompanionV1ControlAction::DeviceScan
        | CompanionV1ControlAction::DeviceConnect
        | CompanionV1ControlAction::DeviceDisconnect
        | CompanionV1ControlAction::DeviceSyncRecordings
        | CompanionV1ControlAction::DeviceEnableAutoReconnect
        | CompanionV1ControlAction::DeviceDisableAutoReconnect => COMPANION_V1_HOST_DEVICE_CHANNEL,
        CompanionV1ControlAction::StageBleName => COMPANION_V1_HOST_DEVICE_CHANNEL,
        CompanionV1ControlAction::ApplyBleName
        | CompanionV1ControlAction::ResetBleName => COMPANION_V1_GATT_BOUNDARY.ble_name_config_uuid,
        CompanionV1ControlAction::OobeRunChecks => COMPANION_V1_HOST_SETUP_CHANNEL,
        CompanionV1ControlAction::MeetingStart
        | CompanionV1ControlAction::MeetingStop
        | CompanionV1ControlAction::MeetingPause
        | CompanionV1ControlAction::MeetingResume
        | CompanionV1ControlAction::MeetingRecoverControl
        | CompanionV1ControlAction::MeetingFinalize => {
            COMPANION_V1_GATT_BOUNDARY.meeting_control_uuid
        }
        CompanionV1ControlAction::MeetingImportTranscript
        | CompanionV1ControlAction::MeetingAppendLiveTranscript
        | CompanionV1ControlAction::MeetingTranscribeAudio
        | CompanionV1ControlAction::MeetingSelectSession
        | CompanionV1ControlAction::MeetingResetSession => COMPANION_V1_HOST_RECORDING_CHANNEL,
        CompanionV1ControlAction::MeetingGenerateMinutes
        | CompanionV1ControlAction::MeetingExportMarkdown
        | CompanionV1ControlAction::MeetingExportTxt
        | CompanionV1ControlAction::MeetingExportJson
        | CompanionV1ControlAction::MeetingExportSrt
        | CompanionV1ControlAction::MeetingExportActionsTodo
        | CompanionV1ControlAction::MeetingExportActionsIcal
        | CompanionV1ControlAction::MeetingLoadDemo => COMPANION_V1_HOST_MINUTES_CHANNEL,
        CompanionV1ControlAction::SpeakerPrompt | CompanionV1ControlAction::SpeakerStop => {
            COMPANION_V1_GATT_BOUNDARY.speaker_control_uuid
        }
        CompanionV1ControlAction::PrivacyEraseAudio
        | CompanionV1ControlAction::PrivacyEraseTranscript
        | CompanionV1ControlAction::PrivacyEraseAll
        | CompanionV1ControlAction::PrivacyDeleteSession => COMPANION_V1_HOST_PRIVACY_CHANNEL,
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
        CompanionV1ControlAction::MeetingPause => 4,
        CompanionV1ControlAction::MeetingResume => 5,
        CompanionV1ControlAction::MeetingRecoverControl => 0,
        CompanionV1ControlAction::HostRetrySave => 0x8e,
        CompanionV1ControlAction::MeetingRestoreAudio => 0x8f,
        CompanionV1ControlAction::DeviceScan => 0x10,
        CompanionV1ControlAction::DeviceConnect => 0x11,
        CompanionV1ControlAction::DeviceDisconnect => 0x12,
        CompanionV1ControlAction::DeviceSyncRecordings => 0x13,
        CompanionV1ControlAction::DeviceEnableAutoReconnect => 0x14,
        CompanionV1ControlAction::DeviceDisableAutoReconnect => 0x15,
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
        CompanionV1ControlAction::MeetingExportActionsTodo => 0x8a,
        CompanionV1ControlAction::MeetingExportActionsIcal => 0x8b,
        CompanionV1ControlAction::MeetingResetSession => 0x84,
        CompanionV1ControlAction::MeetingTranscribeAudio => 0x85,
        CompanionV1ControlAction::MeetingLoadDemo => 0x86,
        CompanionV1ControlAction::MeetingAppendLiveTranscript => 0x8c,
        CompanionV1ControlAction::MeetingSelectSession => 0x8d,
        CompanionV1ControlAction::PrivacyEraseAudio => 0x90,
        CompanionV1ControlAction::PrivacyEraseTranscript => 0x91,
        CompanionV1ControlAction::PrivacyEraseAll => 0x92,
        CompanionV1ControlAction::PrivacyDeleteSession => 0x93,
    }
}

fn host_only_action(action: CompanionV1ControlAction) -> bool {
    matches!(
        action,
        CompanionV1ControlAction::HostRetrySave
            | CompanionV1ControlAction::MeetingRestoreAudio
            | CompanionV1ControlAction::DeviceScan
            | CompanionV1ControlAction::DeviceConnect
            | CompanionV1ControlAction::DeviceDisconnect
            | CompanionV1ControlAction::DeviceSyncRecordings
            | CompanionV1ControlAction::DeviceEnableAutoReconnect
            | CompanionV1ControlAction::DeviceDisableAutoReconnect
            | CompanionV1ControlAction::OobeRunChecks
            | CompanionV1ControlAction::StageBleName
            | CompanionV1ControlAction::MeetingImportTranscript
            | CompanionV1ControlAction::MeetingAppendLiveTranscript
            | CompanionV1ControlAction::MeetingTranscribeAudio
            | CompanionV1ControlAction::MeetingGenerateMinutes
            | CompanionV1ControlAction::MeetingExportMarkdown
            | CompanionV1ControlAction::MeetingExportTxt
            | CompanionV1ControlAction::MeetingExportJson
            | CompanionV1ControlAction::MeetingExportSrt
            | CompanionV1ControlAction::MeetingExportActionsTodo
            | CompanionV1ControlAction::MeetingExportActionsIcal
            | CompanionV1ControlAction::MeetingLoadDemo
            | CompanionV1ControlAction::MeetingSelectSession
            | CompanionV1ControlAction::MeetingResetSession
            | CompanionV1ControlAction::PrivacyEraseAudio
            | CompanionV1ControlAction::PrivacyEraseTranscript
            | CompanionV1ControlAction::PrivacyEraseAll
            | CompanionV1ControlAction::PrivacyDeleteSession
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
    fn local_stage_does_not_claim_a_device_write_and_apply_accepts_direct_name() {
        let snapshot = apply_fixture_control(
            fixture_snapshot(),
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::StageBleName,
                context_note_revision: None, ble_name: Some("companion-v1".to_string()),
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let echo = snapshot.last_control.as_ref().unwrap();
        assert_eq!(
            echo.characteristic_uuid,
            COMPANION_V1_HOST_DEVICE_CHANNEL
        );
        let applied = apply_fixture_control(
            snapshot,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::ApplyBleName,
                context_note_revision: None, ble_name: Some("Companion Two".to_string()),
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        assert_eq!(applied.ble_name.active_name, "Companion Two");
        assert_eq!(
            applied.last_control.unwrap().characteristic_uuid,
            COMPANION_V1_GATT_BOUNDARY.ble_name_config_uuid
        );
    }

    #[test]
    fn meeting_finalize_is_separate_state() {
        let snapshot = apply_fixture_control(
            fixture_snapshot(),
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingFinalize,
                context_note_revision: None, ble_name: None,
                session_id: Some("meeting-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
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
    fn unpopulated_board_features_are_honest_and_fail_closed() {
        let snapshot = fixture_snapshot();
        assert!(!snapshot.imu.supported);
        assert!(!snapshot.speaker.supported);
        assert!(snapshot.speaker.muted);
        assert_eq!(snapshot.speaker.volume, 0);
        assert_eq!(snapshot.speaker.status, "notPopulated");
        assert!(!snapshot.wake_word.supported);
        assert!(!snapshot.wake_word.armed);
        assert_eq!(snapshot.wake_word.engine, "notPopulated");
        assert_eq!(snapshot.wake_word.confidence, 0.0);

        for action in [
            CompanionV1ControlAction::SpeakerPrompt,
            CompanionV1ControlAction::SpeakerStop,
            CompanionV1ControlAction::WakeArm,
            CompanionV1ControlAction::WakeDisable,
            CompanionV1ControlAction::WakeTestDetect,
        ] {
            let result = apply_fixture_control(
                fixture_snapshot(),
                CompanionV1ControlRequest {
                    action,
                    context_note_revision: None, ble_name: None,
                    session_id: None,
                    prompt_id: None,
                    title: None,
                    transcript_text: None,
                    meeting_mode: None,
                    audio_path: None,
                    audio_bytes: None,
                    device_id: None,
                    duration_ms: None,
                },
            );
            assert!(result.is_err());
        }
    }

    #[test]
    fn measured_connected_speaker_can_enter_prompting_state() {
        let mut snapshot = fixture_snapshot();
        snapshot.connected = true;
        snapshot.device.connected = true;
        snapshot.speaker.supported = true;
        snapshot.speaker.online = true;
        snapshot.speaker.volume = 65;
        snapshot.speaker.muted = false;
        let updated = apply_fixture_control(
            snapshot,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::SpeakerPrompt,
                context_note_revision: None, ble_name: None,
                session_id: None,
                prompt_id: Some("confirm".to_string()),
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        assert!(updated.speaker.supported && updated.speaker.online);
        assert_eq!(updated.speaker.status, "prompting");
        assert_eq!(updated.speaker.volume, 65);
    }

    #[test]
    fn host_minutes_workflow_exports_markdown() {
        let initial = fixture_snapshot();
        let started = apply_fixture_control(
            initial,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStart,
                context_note_revision: None, ble_name: None,
                session_id: None,
                prompt_id: None,
                title: Some("Companion host workflow".to_string()),
                transcript_text: None,
                meeting_mode: None,
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
                context_note_revision: None, ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
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
                context_note_revision: None, ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: Some("Decision: host owns long recordings.\nAction owner: Chen due: July 5 validates Markdown.\nQuestion: wake word now?".to_string()),
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let generated = apply_fixture_control(
            transcribed,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingGenerateMinutes,
                context_note_revision: None, ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let exported = apply_fixture_control(
            generated,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingExportMarkdown,
                context_note_revision: None, ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
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

    #[test]
    fn recovery_privacy_erasure_revokes_intent_and_clears_transcript_proof() {
        let mut snapshot = fixture_snapshot();
        let sync_request = CompanionV1ControlRequest {
            action: CompanionV1ControlAction::DeviceSyncRecordings,
            context_note_revision: None, ble_name: None,
            session_id: Some("privacy-session".to_string()),
            prompt_id: None,
            title: Some("privacy".to_string()),
            transcript_text: None,
            meeting_mode: Some("offlineStore".to_string()),
            audio_path: Some("C:/test/privacy.wav".to_string()),
            audio_bytes: Some(16),
            device_id: Some("test-device".to_string()),
            duration_ms: Some(1_000),
        };
        let mut session = synced_device_session(&snapshot, &sync_request, "test");
        session.transcript_text = "final and private".to_string();
        session.transcript_final = true;
        session.live_transcript_text = "live and private".to_string();
        session.utterances = vec![CompanionV1UtteranceSegment {
            text: "speaker text".to_string(),
            start_ms: 0,
            end_ms: 100,
            speaker: Some(0),
        }];
        snapshot.host.sessions = vec![session];
        snapshot.host.selected_session_id = Some("privacy-session".to_string());

        let erased_text = apply_fixture_control(
            snapshot,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::PrivacyEraseTranscript,
                session_id: Some("privacy-session".to_string()),
                context_note_revision: None, ble_name: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let session = &erased_text.host.sessions[0];
        assert_eq!(session.recovery, CompanionV1MeetingRecovery::default());
        assert!(!session.transcript_final);
        assert!(session.transcript_text.is_empty());
        assert!(session.live_transcript_text.is_empty());
        assert!(session.utterances.is_empty());

        let mut audio_snapshot = erased_text;
        audio_snapshot.host.sessions[0].recovery =
            CompanionV1MeetingRecovery::armed("offlineStore");
        audio_snapshot.host.sessions[0].pending_reason =
            Some("recovery_processing".to_string());
        let erased_audio = apply_fixture_control(
            audio_snapshot,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::PrivacyEraseAudio,
                session_id: Some("privacy-session".to_string()),
                context_note_revision: None, ble_name: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            },
        )
        .unwrap();
        let session = &erased_audio.host.sessions[0];
        assert_eq!(session.recovery, CompanionV1MeetingRecovery::default());
        assert!(session.pending_reason.is_none());
        assert!(session.audio_path.is_none());
        assert_eq!(session.audio_bytes, 0);
    }

    #[test]
    fn legacy_export_never_generates_missing_minutes_or_fake_srt() {
        let mut snapshot = apply_fixture_control(
            fixture_snapshot(),
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingLoadDemo,
                context_note_revision: None, ble_name: None,
                session_id: Some("export-existing-only".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: Some("已有文字".to_string()),
                meeting_mode: Some("offlineStore".to_string()),
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: Some(1_000),
            },
        )
        .unwrap();
        snapshot.host.sessions[0].transcript_final = true;
        let mut missing = snapshot.clone();
        missing.host.sessions[0].minutes = None;
        missing.host.sessions[0].minutes_by_mode = Default::default();
        assert!(apply_fixture_control(
            missing,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingExportMarkdown,
                context_note_revision: None, ble_name: None,
                session_id: Some("export-existing-only".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: Some("offlineStore".to_string()),
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            }
        )
        .unwrap_err()
        .contains("completed minutes"));
        assert!(apply_fixture_control(
            snapshot,
            CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingExportSrt,
                context_note_revision: None, ble_name: None,
                session_id: Some("export-existing-only".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: Some("offlineStore".to_string()),
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            }
        )
        .unwrap_err()
        .contains("real timed utterances"));
    }
}
