//! Companion backend service boundary.
//!
//! Commands call a coordinator, the coordinator owns state, and replaceable
//! backend services implement device/audio/transcription/minutes work behind
//! the same IPC contract.

mod ble_bridge;
pub(crate) use ble_bridge::release_one_saved_segment;

/// Read-only engineering admission check; never starts a firmware update.
pub(crate) fn inspect_engineering_ota_preservation(device_id: &str) -> Result<(), String> {
    if std::env::var("COMPANION_TYPE_ENGINEERING_PRESERVE_RECORDINGS").as_deref()!=Ok("1") {
        return Err("工程保留模式未启用，未连接设备。".into());
    }
    ble_bridge::CompanionBleBridge::detect_default().sync_recordings_before_ota(device_id)?;
    Ok(())
}
pub(crate) use ble_bridge::pet_find;
pub(crate) mod lifecycle;
pub(crate) use ble_bridge::release_process_device_links;
pub(crate) use ble_bridge::sync_selected_recording_key;
pub(crate) mod speaker_refinement;
pub(crate) mod meeting_transcript;
pub(crate) use ble_bridge::benchmark_recording_upload;
pub(crate) use ble_bridge::known_segmented_peer;
mod ble_mtu;
mod ble_link_budget;
use ble_bridge::CompanionBleOperation;
#[cfg(windows)]
mod ble_pairing;
/// Pairing needs the normal user/device ceremony; automatic reconnect must
/// retain the recording rather than repeatedly start that ceremony.
pub(crate) fn reconnect_requires_pairing(error: &str) -> bool {
    #[cfg(windows)]
    { ble_pairing::is_pairing_error(error) }
    #[cfg(not(windows))]
    { let _ = error; false }
}
#[cfg(windows)]
mod ble_throughput;
pub(crate) use ble_bridge::{owned_offline_recording_link,owned_segmented_recording_sync};
pub(crate) use device_connection::same_device_id;

pub(crate) fn segmented_link_change_allowed(snapshot: &CompanionV1Snapshot) -> bool {
    snapshot.source == "firmware" && snapshot.device.mode == "windowsNative"
        && snapshot.device.device_id.as_deref().is_some_and(|id|
            ble_bridge::known_segmented_recording(id) && snapshot.host.sessions.iter()
                .filter(|session| session.status == "recording")
                .all(|session| session.source == "boardDevice" && session.source_device_id.as_deref()
                    .is_some_and(|source| device_connection::same_device_id(source, id))))
}
pub(crate) fn automatic_original_reconnect_pending(snapshot:&CompanionV1Snapshot)->bool {
    !snapshot.device.connected && snapshot.device.remembered_device_id.as_deref()
        .and_then(|id|recorder_control::restart_recovery_request(snapshot,id)).is_some()
}
mod recording_capacity;
mod recording_metrics;
pub(crate) mod recording_bookmarks;
pub(crate) mod recording_pause_view;
pub(crate) mod meeting_notes;
pub(crate) mod minutes_context;
pub(crate) mod library_organization;
pub(crate) mod calendar_copy;
pub(crate) mod library_export;
pub(crate) mod library_backup;
pub(crate) mod library_lifecycle;
pub(crate) mod board_meeting;
mod board_stop;
mod interrupted_capture;
pub(crate) mod recording_transfer;
pub(crate) mod recording_sync;
pub(crate) mod ota_metrics;
mod ota_flow;
mod ota_credit_stream;
#[cfg(windows)]
mod ota_pending;
mod ota_submit_timing;
mod simple_ota_restart;
#[cfg(test)]
#[path = "recording_sync/flow_tests.rs"]
mod recording_sync_flow_tests;
pub(crate) mod recording_wire;
pub(crate) mod recorder_control;
pub(crate) mod recording_discard;
pub(crate) mod recording_discard_v3;
pub(crate) use ble_bridge::discard_oldest_recording;
mod audio_decode;
mod cop1;
pub(crate) mod audio_export;
mod audio_storage;
pub(crate) mod audio_artifacts;
pub(crate) mod audio_components;
pub(crate) use audio_decode::decode_recording;
pub(crate) use ble_bridge::pull_device_diagnostics;
mod device_connection;
pub(crate) mod hardware_identity;
pub(crate) mod desktop_update;
mod diarization;
pub(crate) use diarization::model_files_present as speaker_model_files_present;
pub(crate) use diarization::prepare_runtime as prepare_speaker_runtime;
pub(crate) mod diagnostics;
pub(crate) mod export;
mod meeting_document_export;
pub(crate) mod pdf_export;
pub(crate) mod file_storage_probe;
mod action_export;
pub(crate) mod service_check;
pub(crate) mod service_network_probe;
mod firmware_ota;
mod system_ota;
mod ota_readiness;
mod host_recording;
pub(crate) mod host_segmented_capture;
pub(crate) mod import_audio;
mod meeting_audio_timeline;
mod meeting_audio_tracks;
mod meeting_audio_recovery;
mod meeting_audio_mix;
mod meeting_audio_transcription;
#[cfg(windows)]
mod meeting_audio_capture;
mod host_interrupted_recovery;
mod live_asr;
mod minutes;
pub(crate) mod meeting_qa;
mod external_command;
pub(crate) mod external_command_probe;
#[cfg(windows)]
pub(crate) mod ota_winrt;
mod persistence;
mod session_store;
pub(crate) mod meeting_workspace;
pub(crate) mod transcript_review;
mod privacy;
pub(crate) use privacy::verify_privacy_delete;
pub mod product_settings;
/// In-memory import/fixture coordinator; the board owns physical NOR storage.
pub mod recording_ring;
pub(crate) mod transcription;
pub(crate) mod meeting_processing_job;
pub(crate) use transcription::prepare_local_asr;
#[cfg(test)]
mod meeting_processing_tests;
pub(crate) mod pet_chat;
mod pet_chat_language;
pub(crate) mod pet_profile;
pub(crate) mod pet_profile_model;
pub(crate) use transcription::verify_asr_cache;
pub(crate) use transcription::verify_cache_privacy;
mod volcengine;

use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::Serialize;
use sha2::{Digest, Sha256};

use crate::companion_v1::{
    apply_control_at, apply_fixture_control, fixture_snapshot, seal_companion_v1_session_chunks,
    CompanionV1AudioChunk, CompanionV1ControlAction, CompanionV1ControlRequest,
    CompanionV1HostSession, CompanionV1MeetingRecovery, CompanionV1MinutesByMode, CompanionV1MinutesVariant,
    CompanionV1OobeCheck, CompanionV1Snapshot, CompanionV1UtteranceSegment,
};

const MEETING_WORK_SUPERSEDED: &str = "处理期间会议内容已变化，旧结果未覆盖当前内容；已有原音和服务缓存保留，请按当前会议状态继续。";

fn unix_time_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX)
}

const UNCONFIRMED_HOST_AUDIO: &str = "本机录音保存尚未确认，请先尝试恢复原录音；未提交转写。";

fn host_audio_unconfirmed(session: &CompanionV1HostSession) -> bool {
    if session.transcript_final && !session.transcript_text.trim().is_empty() { return false; }
    match session.source.as_str() {
        "hostMicrophone" => !session.audio_stored || !session.retention.audio_cached || session.audio_bytes <= 44
            || session.audio_path.as_deref().is_none_or(|path| path.trim().is_empty()),
        "hostMeeting" => !session.audio_stored || !session.retention.audio_cached
            || session.meeting_tracks.as_ref().is_none_or(|tracks| tracks.microphone.is_empty() && tracks.system.is_empty()),
        _ => false,
    }
}

fn hold_unconfirmed_host_audio(session: &mut CompanionV1HostSession) {
    session.recovery.stage = "paused".into();
    session.recovery.next_retry_at_unix_ms = None;
    session.recovery.last_error = Some(UNCONFIRMED_HOST_AUDIO.into());
    session.pending_reason = Some("recovery_paused".into());
}

// A deliberate stop must not be interpreted on restart as a crashed job
// eligible for automatic retry. Keep its already-consumed attempt and cache.
fn pause_cancelled_meeting_work(snapshot: &mut CompanionV1Snapshot, id: &str, stage: &str, message: &str) -> Result<(), String> {
    let Some(session)=snapshot.host.sessions.iter_mut().find(|session|session.id==id) else {return Ok(());};
    if session.recovery.intent!="processMeeting" || session.recovery.stage!=stage {return Ok(());}
    session.recovery.stage="paused".into();
    session.recovery.next_retry_at_unix_ms=None;
    session.recovery.last_error=Some(message.into());
    session.pending_reason=Some("recovery_paused".into());
    persistence::save_snapshot(snapshot)
}

fn arm_meeting_recovery(session: &mut CompanionV1HostSession) {
    // This explicit short capture belongs to the pet reply worker. Its raw
    // audio keeps the normal durable library/consume contract, without an
    // additional automatic meeting ASR/minutes job after STOP or restart.
    if session.organization.trashed_at.is_some() || session.recovery.intent == pet_chat::CAPTURE_INTENT { return; }
    // An incomplete original is a recording warning even when the user has
    // selected manual processing. That policy prevents automatic paid work;
    // it must not hide the interruption or present it as a complete meeting.
    if interrupted_capture::hold(session) {return;}
    if session.processing_policy == crate::companion_v1::CompanionV1ProcessingPolicy::Manual {return;}
    if session.recovery.intent != "processMeeting" {
        session.recovery = CompanionV1MeetingRecovery::armed(&session.meeting_mode);
    }
    interrupted_capture::hold(session);
}

fn pause_incomplete_host_recording(session: &mut CompanionV1HostSession, error: &str, ownership_unconfirmed: bool) {
    // Keep the interruption visible after explicit processing or restart;
    // a prior confirmation cannot authorize a newly interrupted capture.
    session.capture_incomplete = true;
    session.recovery.capture_review_confirmed = false;
    arm_meeting_recovery(session);
    session.status = "captured".to_string();
    session.transcript_final = false;
    let multipart = host_segmented_capture::saved_parts(session);
    session.audio_stored = !ownership_unconfirmed && session.audio_bytes > 44 && match multipart {
        Ok(Some(_)) => true,
        Err(_) => false,
        Ok(None) => session.audio_path.as_deref().map(std::path::Path::new).filter(|path| path.is_absolute())
            .is_some_and(|path| std::fs::metadata(path).is_ok_and(|m| m.is_file() && m.len() == session.audio_bytes)
                && meeting_workspace::validate_wav(path).is_ok()),
    };
    session.recovery.stage = "paused".to_string();
    session.recovery.next_retry_at_unix_ms = None;
    session.recovery.last_error = Some(format!("录音不完整：{error}。已保留现有文件，请检查录音后再处理。"));
    session.pending_reason = Some("recovery_paused".to_string());
}

fn recovery_error_is_permanent(error: &str) -> bool {
    if volcengine::is_no_speech_error(error) {
        return true;
    }
    let error = error.to_ascii_lowercase();
    [
        "credential", "not configured", "missing", "invalid wav", "unsupported",
        "authentication", "unauthorized", "forbidden", "does not exist",
        "录音缺段", "录音分段重复", "长录音分段未完成", "truncated wav", "riff header",
    ]
    .iter()
    .any(|needle| error.contains(needle))
}

fn schedule_recovery_failure(session: &mut CompanionV1HostSession, error: &str) {
    arm_meeting_recovery(session);
    if !matches!(
        session.recovery.stage.as_str(),
        "transcribing" | "generatingMinutes"
    ) {
        session.recovery.attempt_count = session.recovery.attempt_count.saturating_add(1);
    }
    session.recovery.last_error = Some(error.chars().take(512).collect());
    let exhausted = session.recovery.attempt_count >= session.recovery.max_attempts.max(1);
    if exhausted || recovery_error_is_permanent(error)
        || session.processing_policy == crate::companion_v1::CompanionV1ProcessingPolicy::Manual {
        session.recovery.stage = "paused".to_string();
        session.recovery.next_retry_at_unix_ms = None;
        session.pending_reason = Some(if volcengine::is_no_speech_error(error) {
            "no_speech_detected"
        } else {
            "recovery_paused"
        }.to_string());
    } else {
        let exponent = u32::from(session.recovery.attempt_count.saturating_sub(1)).min(4);
        let delay_ms = 2_000u64.saturating_mul(1u64 << exponent).min(30_000);
        session.recovery.stage = "retryBackoff".to_string();
        session.recovery.next_retry_at_unix_ms = Some(unix_time_ms().saturating_add(delay_ms));
        session.pending_reason = Some("recovery_retry_wait".to_string());
    }
}

fn mark_recovery_transcribed(session: &mut CompanionV1HostSession) {
    if session.recovery.intent == "processMeeting" {
        session.recovery.stage = "pendingMinutes".to_string();
        session.recovery.retry_stage = "minutes".to_string();
        session.recovery.attempt_count = 0;
        session.recovery.next_retry_at_unix_ms = None;
        session.recovery.last_error = None;
        session.pending_reason = None;
    }
}

fn mark_recovery_complete(session: &mut CompanionV1HostSession) {
    if session.recovery.intent == "processMeeting" {
        session.recovery.stage = "complete".to_string();
        session.recovery.retry_stage.clear();
        session.recovery.attempt_count = 0;
        session.recovery.next_retry_at_unix_ms = None;
        session.recovery.last_error = None;
        session.pending_reason = None;
    } else if session.recovery.intent == "none"
        && session.processing_policy == crate::companion_v1::CompanionV1ProcessingPolicy::Manual
        && !session.capture_incomplete && !session.recorder_control_uncertain {
        // A manual retry can fail without arming automatic recovery. Once it
        // succeeds, that old processing error must not remain on the session.
        session.recovery.stage = "idle".to_string();
        session.recovery.retry_stage.clear();
        session.recovery.attempt_count = 0;
        session.recovery.next_retry_at_unix_ms = None;
        session.recovery.last_error = None;
    }
}

fn minutes_variant(
    minutes: &crate::companion_v1::CompanionV1MeetingMinutes,
    partial_count: u32,
) -> CompanionV1MinutesVariant {
    CompanionV1MinutesVariant {
        template: None, processing: minutes.processing.clone(),
        source_note_context: minutes.source_note_context.clone(), source_review_revision: minutes.source_review_revision,
        status: if minutes.llm_note.is_some() { "retryPending" } else { "minutesReady" }.to_string(),
        markdown: minutes.markdown.clone(),
        source: minutes.source.clone(),
        quality: minutes.quality.clone(),
        generated_at: Some(minutes.generated_at.clone()),
        partial_count,
    }
}

fn session_has_pending_dual_minutes(session: &CompanionV1HostSession) -> bool {
    match (&session.minutes_by_mode.offline_store, &session.minutes_by_mode.online_live) {
        (Some(offline), Some(online)) => [offline, online].into_iter().any(|variant| {
            variant.status == "retryPending" || !transcript_review::minutes_current(session, variant.source_review_revision)
                || variant.processing.as_ref().is_some_and(|p| !p.is_complete())
        }),
        _ => false,
    }
}

// A sealed online meeting owns two independent products. Retry only failed
// variants without changing the capture route, replaying ASR or replacing the
// successful product (including its user edits and live partial count).
fn refresh_minutes_products<F>(
    session: &mut CompanionV1HostSession,
    generated_at: &str,
    mut generate: F,
) -> Option<String>
where F: FnMut(&CompanionV1HostSession) -> crate::companion_v1::CompanionV1MeetingMinutes,
{
    refresh_minutes_products_for_mode(session, generated_at, None, &mut generate)
}

fn refresh_minutes_products_for_mode<F>(session: &mut CompanionV1HostSession, generated_at: &str,
    selected_mode: Option<&str>, mut generate: F) -> Option<String>
where F: FnMut(&CompanionV1HostSession) -> crate::companion_v1::CompanionV1MeetingMinutes,
{
    let modes: Vec<String> = if let Some(mode) = selected_mode { vec![mode.to_string()] }
    else if session_has_pending_dual_minutes(session) {
        ["offlineStore", "onlineLive"].into_iter().filter(|mode| {
            let variant = if *mode == "onlineLive" { &session.minutes_by_mode.online_live }
                          else { &session.minutes_by_mode.offline_store };
            variant.as_ref().is_some_and(|variant| variant.status == "retryPending"
                || variant.processing.as_ref().is_some_and(|p| !p.is_complete())
                || !transcript_review::minutes_current(session, variant.source_review_revision))
        }).map(str::to_string).collect()
    } else {
        vec![session.meeting_mode.clone()]
    };
    let mut failure = None;
    for mode in modes {
        // A sealed meeting can have two products. Do not submit the second
        // product after the user stopped the first; the outer job discards
        // this temporary session and preserves the durable version.
        if let Err(error) = meeting_processing_job::check_current() { return Some(error); }
        let mut input = session.clone();
        input.meeting_mode = mode.clone();
        let generated = generate(&input);
        if failure.is_none() { failure = generated.llm_note.clone(); }
        let partial_count = if mode == "onlineLive" {
            session.minutes_by_mode.online_live.as_ref().map(|variant| variant.partial_count)
                .unwrap_or_else(|| u32::from(!session.live_transcript_text.trim().is_empty()))
        } else { 0 };
        let variant = minutes_variant(&generated, partial_count);
        let previous = if mode == "onlineLive" { session.minutes_by_mode.online_live.clone() }
            else { session.minutes_by_mode.offline_store.clone() }
            .or_else(|| (mode == session.meeting_mode).then(|| session.minutes.as_ref().map(|m| minutes_variant(m, 0))).flatten());
        if let Some(previous) = previous {
            if !previous.markdown.trim().is_empty() && previous.markdown != variant.markdown {
                session.minutes_by_mode.history.push(crate::companion_v1::CompanionV1MinutesHistory {
                    mode: mode.clone(), archived_at: generated_at.into(), variant: previous,
                });
            }
        }
        if mode == "onlineLive" { session.minutes_by_mode.online_live = Some(variant); }
        else { session.minutes_by_mode.offline_store = Some(variant); }
        if mode == session.meeting_mode {
            session.export_markdown = generated.markdown.clone();
            session.exported_at = Some(generated_at.to_string());
            session.minutes = Some(generated);
        }
    }
    session.retention.minutes_cached = true;
    let has_old_variant = [&session.minutes_by_mode.offline_store, &session.minutes_by_mode.online_live]
        .into_iter().flatten().any(|variant| !transcript_review::minutes_current(session, variant.source_review_revision));
    session.status = if failure.is_some() || has_old_variant { "transcribed" } else { "minutesReady" }.to_string();
    if let Some(error) = failure.as_deref() {
        schedule_recovery_failure(session, error);
    } else if has_old_variant {
        session.pending_reason = Some("minutes_source_changed".into());
        session.recovery = Default::default();
    } else {
        session.pending_reason = None;
        mark_recovery_complete(session);
    }
    failure
}

pub(crate) fn session_has_final_minutes_product(session: &CompanionV1HostSession) -> bool {
    let mode_ready = if session.meeting_mode == "onlineLive" {
        session.minutes_by_mode.online_live.as_ref()
    } else {
        session.minutes_by_mode.offline_store.as_ref()
    };
    session.status == "minutesReady"
        && !session_has_pending_dual_minutes(session)
        && [&session.minutes_by_mode.offline_store, &session.minutes_by_mode.online_live].into_iter()
            .flatten().all(|variant| transcript_review::minutes_current(session, variant.source_review_revision)
                && variant.processing.as_ref().is_none_or(|p| p.is_complete()))
        && session.minutes.as_ref().is_some_and(|minutes| {
            minutes.quality == "final"
                && minutes.processing.as_ref().is_none_or(|p| p.is_complete())
                && minutes.llm_note.is_none()
                && !minutes.markdown.trim().is_empty()
                && transcript_review::minutes_current(session, minutes.source_review_revision)
        })
        && mode_ready.is_some_and(|minutes| {
            minutes.status == "minutesReady"
                && minutes.quality == "final"
                && minutes.processing.as_ref().is_none_or(|p| p.is_complete())
                && !minutes.markdown.trim().is_empty()
        })
        && (session.recovery.intent == "none" || session.recovery.stage == "complete")
}

fn normalized_native_device_id(device_id: &str) -> Option<String> {
    if !device_connection::stable_device_id(device_id) {
        return None;
    }
    Some(
        device_id
            .chars()
            .filter(|character| character.is_ascii_hexdigit())
            .flat_map(char::to_lowercase)
            .collect(),
    )
}

fn device_recording_session_id(device_id: Option<&str>, recording_id: u32) -> String {
    normalized_native_device_id(device_id.unwrap_or_default())
        .map(|device| format!("device-{device}-recording-{recording_id}"))
        .unwrap_or_else(|| format!("device-recording-{recording_id}"))
}

fn effective_device_target(
    requested_device_id: Option<&str>,
    current_device_id: Option<&str>,
) -> Option<String> {
    requested_device_id
        .and_then(|value| {
            let value = value.trim();
            (!value.is_empty()).then(|| value.to_string())
        })
        .or_else(|| {
            current_device_id.and_then(|value| {
                let value = value.trim();
                (!value.is_empty()).then(|| value.to_string())
            })
        })
}

fn verified_device_recording_ids(
    snapshot: &CompanionV1Snapshot,
    source_device_id: Option<&str>,
) -> Vec<u32> {
    verified_device_recording_ids_for_policy(
        snapshot, source_device_id, ble_bridge::delete_after_sync_enabled())
}

fn retain_stopped_recording_checkpoint(
    previous: &ble_bridge::CompanionBleOperation,
    mut retried: ble_bridge::CompanionBleOperation,
    device_id: &str,
    recording_id: u32,
) -> ble_bridge::CompanionBleOperation {
    let same_source = |source: &str| device_connection::same_device_id(source, device_id);
    if !previous.ready
        || !previous.device_id.as_deref().is_some_and(same_source)
        || retried.device_id.as_deref().is_some_and(|source| !same_source(source))
        || !previous.recordings.iter().any(|item| item.recording_id == recording_id
            && item.total_length > 0 && item.sha256.len() == 64)
    {
        return retried;
    }
    // A later reconnect failure or empty directory cannot undo an earlier
    // durable host receipt. Nor can directory absence stand in for an ACK.
    for item in &previous.recordings {
        if retried.recordings.iter().any(|next| next.recording_id == item.recording_id
            && (next.total_length != item.total_length || next.sha256 != item.sha256))
        {
            retried.ready = false;
            retried.message.push_str("; stopped recording identity changed during retry");
            return retried;
        }
    }
    for item in &previous.recordings {
        if let Some(next) = retried.recordings.iter_mut()
            .find(|next| next.recording_id == item.recording_id)
        {
            next.device_reclaimed |= item.device_reclaimed;
        } else {
            retried.recordings.push(item.clone());
        }
    }
    retried.ready = true;
    retried.device_id = Some(device_id.to_string());
    retried.recording_path = retried.recordings.iter()
        .find(|item| item.recording_id == recording_id)
        .map(|item| item.recording_path.clone());
    retried.message.push_str(&format!(
        "; durable STOP checkpoint retained; pending_device_consume={}; no missing ACK inferred",
        retried.recordings.iter().filter(|item| !item.device_reclaimed).count()));
    retried
}

fn verified_device_recording_ids_for_policy(
    snapshot: &CompanionV1Snapshot,
    source_device_id: Option<&str>,
    delete_after_sync: bool,
) -> Vec<u32> {
    let Some(source_device_id) = source_device_id.filter(|id| device_connection::stable_device_id(id)) else {
        return Vec::new();
    };
    snapshot
        .host
        .sessions
        .iter()
        .filter_map(|session| {
            if session
                .source_device_id
                .as_deref()
                .is_some_and(|source| device_connection::same_device_id(source, source_device_id))
                // A durable host copy does not acknowledge physical reclaim.
                // Keep an unacknowledged item eligible for the existing cursor
                // retry. The explicit retain-on-device policy still skips it.
                && (!delete_after_sync || session.device_reclaimed)
                && session.device_total_length.is_some()
                && session
                    .device_sha256
                    .as_deref()
                    .is_some_and(|sha| sha.len() == 64)
            {
                session.device_recording_id
            } else {
                None
            }
        })
        .collect()
}
pub use ble_bridge::CompanionBleBridgeStatus;
pub(crate) use ble_bridge::{
    record_board_online_live_controlled, BoardOnlineLiveReport,
    BoardPartialConsumer, BoardPartialObserver, BoardRecordingObserver, BoardBookmarkObserver,
};
use ble_bridge::{
    CompanionBleBridge, CompanionDeviceIdentity, CompanionMeetingControlReport,
    CompanionSpeakerControlReport, CompanionSyncedRecording,
};
pub use firmware_ota::{
    CompanionFirmwareOtaReport, CompanionFirmwareOtaRequest, CompanionOtaPackageValidation,
};
use host_recording::HostRecordingManager;
use live_asr::LiveAsrHub;
use minutes::CompanionMinutesManager;
use privacy::{PrivacyEraseReport, PrivacyManager};
pub(crate) use transcription::CompanionTranscriptionManager;

/// Return (WAV file bytes, PCM duration ms) from a RIFF/WAVE file. Device sync
/// must use the artifact it actually decoded instead of the old 60-second
/// fixture default (which reported every pull as 1,920,000 bytes / 60,000 ms).
fn wav_file_metrics(path: &str) -> Option<(u64, u64)> {
    let bytes = std::fs::read(path).ok()?;
    if bytes.len() < 12 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return None;
    }
    let mut offset = 12usize;
    let mut byte_rate = None;
    let mut data_bytes = None;
    while offset.checked_add(8)? <= bytes.len() {
        let id = &bytes[offset..offset + 4];
        let size = u32::from_le_bytes(bytes[offset + 4..offset + 8].try_into().ok()?) as usize;
        let body = offset + 8;
        let end = body.checked_add(size)?;
        if end > bytes.len() {
            return None;
        }
        if id == b"fmt " && size >= 12 {
            byte_rate =
                Some(u32::from_le_bytes(bytes[body + 8..body + 12].try_into().ok()?) as u64);
        } else if id == b"data" {
            data_bytes = Some(size as u64);
        }
        offset = end + (size & 1);
    }
    let rate = byte_rate?;
    let payload = data_bytes?;
    if rate == 0 {
        return None;
    }
    Some((bytes.len() as u64, payload.saturating_mul(1000) / rate))
}

/// Reattach a sealed board WAV/Opus pair to the newest interrupted onlineLive
/// row. Recovery is explicit: the caller supplies the exact recording id and
/// WAV, while the durable length/hash are derived from the pulled Opus bytes.
pub(crate) fn recover_persisted_board_recording(
    recording_id: u32,
    wav_path: &std::path::Path,
) -> Result<String, String> {
    recover_persisted_board_recording_at(recording_id, wav_path, &persistence::state_file_path())
}

fn recover_persisted_board_recording_at(
    recording_id: u32,
    wav_path: &std::path::Path,
    state_path: &std::path::Path,
) -> Result<String, String> {
    let expected_suffix = format!("-device-recording-{recording_id}.wav");
    let wav_name = wav_path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| format!("invalid recovery WAV path: {}", wav_path.display()))?;
    if !wav_name.ends_with(&expected_suffix) {
        return Err(format!(
            "recovery WAV filename does not match recording_id={recording_id}: {wav_name}"
        ));
    }
    let wav_path = wav_path
        .canonicalize()
        .map_err(|err| format!("canonicalize recovery WAV {}: {err}", wav_path.display()))?;
    let opus_path = wav_path.with_extension("opus");
    let opus = std::fs::read(&opus_path)
        .map_err(|err| format!("read recovery Opus {}: {err}", opus_path.display()))?;
    let total_length = u32::try_from(opus.len())
        .map_err(|_| format!("recovery Opus is too large: {} bytes", opus.len()))?;
    if total_length == 0 {
        return Err("recovery Opus is empty".to_string());
    }
    let sha256 = format!("{:x}", Sha256::digest(&opus));
    let (wav_bytes, duration_ms) = wav_file_metrics(&wav_path.to_string_lossy())
        .ok_or_else(|| format!("recovery WAV is invalid: {}", wav_path.display()))?;
    // Read, identify and commit under one store lock. Another process may
    // add a recording while this recovery validates WAV/Opus; replacing an
    // earlier whole-library snapshot would otherwise erase that newer row.
    let mut recovered_session = None;
    session_store::update_checked(state_path, |sessions| {
        let owner=legacy_recording_recovery_owner(sessions,recording_id)?;
        let session=&mut sessions[owner];
        session.source = "deviceFlash".to_string();
        session.status = "captured".to_string();
        session.pending_reason = Some("needs_transcription".to_string());
        board_meeting::retain_capture_dates(session);
        session.duration_ms = duration_ms;
        session.audio_path = Some(wav_path.to_string_lossy().to_string());
        session.audio_bytes = wav_bytes;
        session.audio_stored = true;
        session.device_recording_id = Some(recording_id);
        session.device_total_length = Some(total_length);
        session.device_sha256 = Some(sha256);
        session.device_reclaimed = false;
        arm_meeting_recovery(session);
        session.chunks = vec![audio_chunk(
            format!("{}-board-recovered", session.id),
            Some(wav_path.to_string_lossy().to_string()),
            session.started_at.clone(),
            session.stopped_at.clone(),
            duration_ms,
            wav_bytes,
            "synced",
        )];
        session.retention.audio_cached = true;
        recovered_session = Some(session.id.clone());
        Ok(())
    })?;
    recovered_session.ok_or_else(|| "recording recovery did not select a session".to_string())
}

fn legacy_recording_recovery_owner(sessions:&[CompanionV1HostSession],recording_id:u32)->Result<usize,String> {
    let exact=sessions.iter().enumerate().filter(|(_,row)|row.device_recording_id==Some(recording_id))
        .map(|(index,_)|index).collect::<Vec<_>>();
    if exact.len()>1 {return Err("Device recording number is ambiguous; original library was not changed".into());}
    if let Some(&index)=exact.first() {
        if sessions[index].device_recording_key.is_some() || sessions[index].recorder_control.is_some() {
            return Err("Segmented originals require their exact normal recovery proof, not legacy WAV reattachment; original library was not changed".into());
        }
        return Ok(index);
    }
    let pending=sessions.iter().enumerate().filter(|(_,row)|row.device_recording_id.is_none()
        && row.device_recording_key.is_none() && row.recorder_control.is_none()
        && row.meeting_mode=="onlineLive"
        && row.audio_path.as_deref().is_some_and(|path|path.starts_with("board://"))
        && matches!(row.status.as_str(),"recording"|"captured"))
        .map(|(index,_)|index).collect::<Vec<_>>();
    if pending.len()!=1 {return Err("No unique interrupted legacy meeting can own this recording; original library was not changed".into());}
    Ok(pending[0])
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionBackendCapabilities {
    pub backend_id: String,
    pub backend_kind: String,
    pub services: CompanionBackendServices,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionBackendServices {
    pub device_control: CompanionServiceBoundary,
    pub recording: CompanionServiceBoundary,
    pub transcription: CompanionServiceBoundary,
    pub minutes: CompanionServiceBoundary,
    pub export: CompanionServiceBoundary,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionServiceBoundary {
    pub provider_id: String,
    pub mode: String,
    pub supported: bool,
    pub notes: String,
}

pub trait CompanionBackend: Send + Sync {
    fn finish_host_recording_on_exit(&self) -> Result<(), String>;
    fn finish_meeting_processing_on_exit(&self, budget: std::time::Duration) -> Result<(), String>;
    fn request_manual_disconnect(&self,target:Option<&str>)->Result<(),String>;
    fn import_audio_file(&self,_path:&std::path::Path)->Result<CompanionV1Snapshot,String>{Err("当前环境不支持导入音频。".into())}
    fn restore_library_backup(&self,_path:&std::path::Path)->Result<CompanionV1Snapshot,String>{Err("当前环境不支持恢复会议备份。".into())}
    fn save_library_lifecycle(&self,_request:library_lifecycle::Request)->Result<CompanionV1Snapshot,String>{Err("当前环境不支持录音保护与回收站。".into())}
    fn save_library_organization(&self,_request:library_organization::Request)->Result<CompanionV1Snapshot,String>{Err("当前环境不支持保存资料分类。".into())}
    fn restore_local_recordings(&self) -> Result<recording_wire::receiver::LocalRestoreReport, String>;
    fn save_meeting_note(&self, request: meeting_notes::Request) -> Result<CompanionV1Snapshot, String>;
    fn save_bookmark(&self, request: recording_bookmarks::Request, stamp: Option<recording_bookmarks::LiveStamp>)
        -> Result<CompanionV1Snapshot,String>;
    fn save_meeting_edit(&self, request: meeting_workspace::MeetingEditRequest) -> Result<CompanionV1Snapshot, String>;
    fn refine_meeting_speakers(&self,_id:&str)->Result<CompanionV1Snapshot,String> {Err("当前环境未提供本地说话人区分。".into())}
    fn preview_meeting_transcription(&self,_id:&str,_job_id:&str)->Result<transcription::TranscriptionPreview,String> {Err("当前环境不支持重新转写。".into())}
    fn preview_meeting_gap(&self,_id:&str,_job_id:&str,_range:transcription::TranscriptionRange)->Result<transcription::TranscriptionPreview,String> {Err("当前环境不支持单段重新转写。".into())}
    fn capabilities(&self) -> CompanionBackendCapabilities;
    fn ble_bridge_status(&self) -> CompanionBleBridgeStatus;
    fn snapshot(&self) -> Result<CompanionV1Snapshot, String>;
    fn apply_control(
        &self,
        request: CompanionV1ControlRequest,
    ) -> Result<CompanionV1Snapshot, String>;
    fn record_meeting_recovery_failure(
        &self,
        session_id: &str,
        retry_stage: &str,
        error: &str,
    ) -> Result<(), String>;
    fn mark_meeting_exported(
        &self,
        session_id: &str,
        meeting_mode: &str,
        calendar_copy: Option<calendar_copy::Copy>,
    ) -> Result<(), String>;
    fn automatic_reconnect_once(&self) -> Result<CompanionV1Snapshot, String>;
    fn follow_recording_once(&self, original_session: Option<&str>,
        live:Option<&mut recording_wire::receiver::LiveCursor>) -> Result<bool, String>;
    fn transfer_firmware_ota(
        &self,
        request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionFirmwareOtaReport, String>;
    fn validate_ota_package(
        &self,
        request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionOtaPackageValidation, String>;
    fn complete_board_online_live(
        &self,
        session_id: &str,
        report: &BoardOnlineLiveReport,
    ) -> Result<CompanionV1Snapshot, String>;
    fn set_board_online_live_partial(
        &self,
        session_id: &str,
        transcript: &str,
    ) -> Result<CompanionV1Snapshot, String>;
    fn bind_board_online_live_recording(&self, session_id: &str, device_id: &str, recording_id: u32, start_ack_at: &str)
        -> Result<(), String>;
    fn fail_board_online_live(
        &self,
        session_id: &str,
        reason: &str,
    ) -> Result<CompanionV1Snapshot, String>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct PendingMeetingStart {
    session_id: String,
    device_id: Option<String>,
    max_seconds: u16,
}

fn reserve_pending_meeting_start(
    pending: &mut Option<PendingMeetingStart>,
    session_id: &str,
    device_id: Option<&str>,
    max_seconds: u16,
) -> Result<u16, String> {
    if let Some(existing) = pending.as_mut() {
        if existing.session_id != session_id {
            return Err(format!(
                "meeting START outcome is still unknown for session {}; retry that session or disconnect it explicitly",
                existing.session_id
            ));
        }
        if let (Some(bound), Some(requested)) = (existing.device_id.as_deref(), device_id) {
            if bound != requested {
                return Err(format!(
                    "meeting START retry is bound to device {bound}, not {requested}"
                ));
            }
        } else if existing.device_id.is_none() {
            existing.device_id = device_id.map(str::to_owned);
        }
        /* A retry must reproduce the original wire request exactly. The UI may
         * have refreshed its duration control while the BLE outcome was
         * unknown, but changing max_seconds under the same request id would be
         * a request-id collision at the device. */
        return Ok(existing.max_seconds);
    }
    *pending = Some(PendingMeetingStart {
        session_id: session_id.to_string(),
        device_id: device_id.map(str::to_owned),
        max_seconds,
    });
    Ok(max_seconds)
}

fn meeting_start_rejection_is_definitive(error: &str) -> bool {
    error.starts_with("board rejected V1 meeting command=1 ") || error.starts_with("recording preflight:")
}

fn recording_duration_seconds(duration_ms: Option<u64>) -> Result<u16,String> {
    let ms=duration_ms.unwrap_or(60_000);
    if ms==0 || ms>u64::from(u16::MAX)*1000 {
        return Err("请输入有效的完整录音时长（1 秒至 65535 秒），不会自动截短".into());
    }
    Ok(((ms+999)/1000) as u16)
}

fn apply_device_identity(snapshot: &mut CompanionV1Snapshot, identity: &CompanionDeviceIdentity) {
    snapshot.device.firmware_version = identity.firmware_version;
    snapshot.device.build_id = identity.build_id;
    snapshot.device.board_id = identity.board_id;
    snapshot.device.mcu_uid = identity.mcu_uid.clone();
    snapshot.device.ui_generation = identity.ui_generation;
    snapshot.device.recording_capacity = identity.recording_capacity.clone();
    if let Some(recording) = identity.recording {
        snapshot.device.recording = recording;
    }
    snapshot.device.hardware_revision = match identity.board_id {
        Some(0x5742_4155) => Some("COMPANION-WBA55-V1.1".to_string()),
        _ => None,
    };

    snapshot.imu.supported = identity.imu_supported.unwrap_or(false);
    snapshot.imu.online = identity.imu_online.unwrap_or(false);
    snapshot.imu.sample_hz = identity.imu_sample_hz.unwrap_or(0);
    snapshot.speaker.supported = identity.speaker_supported.unwrap_or(false);
    snapshot.speaker.find_supported = identity.speaker_find_supported.unwrap_or(false);
    snapshot.speaker.online = identity.speaker_online.unwrap_or(false);
    snapshot.speaker.volume = identity.speaker_volume.unwrap_or(0).min(100);
    snapshot.speaker.muted = snapshot.speaker.volume == 0;
    snapshot.speaker.status = if identity.speaker_supported == Some(false) {
        "notPopulated".to_string()
    } else if identity.speaker_online == Some(true) {
        "idle".to_string()
    } else if identity.speaker_supported == Some(true) {
        "error".to_string()
    } else {
        "unknown".to_string()
    };
}

fn oobe_check(id: &str, label: &str, status: &str, message: impl Into<String>) -> CompanionV1OobeCheck {
    CompanionV1OobeCheck {
        id: id.to_string(),
        label: label.to_string(),
        status: status.to_string(),
        message: message.into(),
    }
}

fn oobe_checks_from_probe(
    report: &ble_bridge::CompanionOobeProbeReport,
) -> Vec<CompanionV1OobeCheck> {
    let base_identity_complete = report.identity.firmware_version.is_some()
        && report.identity.build_id.is_some()
        && report.identity.board_id.is_some();
    let identity_complete = base_identity_complete
        && (report.identity.board_id != Some(0x5742_4155)
            || (report.identity.mcu_uid.is_some() && report.identity.ui_generation.is_some()));
    let firmware = if identity_complete {
        oobe_check(
            "firmware",
            "固件与板卡身份",
            "pass",
            format!(
                "FW=0x{:08x}, build=0x{:08x}, board=0x{:08x}, UID={}, UI={}",
                report.identity.firmware_version.unwrap_or_default(),
                report.identity.build_id.unwrap_or_default(),
                report.identity.board_id.unwrap_or_default(),
                report.identity.mcu_uid.as_deref().unwrap_or("legacy"),
                report.identity.ui_generation.map_or_else(|| "legacy".to_string(), |value| value.to_string())
            ),
        )
    } else if report.device_status_read {
        oobe_check(
            "firmware",
            "固件与板卡身份",
            "fail",
            "DEVICE_STATUS 已读取，但身份字段不完整",
        )
    } else {
        oobe_check(
            "firmware",
            "固件与板卡身份",
            "fail",
            "DEVICE_STATUS 未读到；设备可能未配对、未授权或固件协议不匹配",
        )
    };
    let gatt = if report.missing_required_gatt.is_empty() {
        oobe_check(
            "gatt",
            "核心 GATT",
            "pass",
            format!(
                "发现 {} 个服务、{} 个特征；核心特征齐全",
                report.service_count, report.characteristic_count
            ),
        )
    } else {
        oobe_check(
            "gatt",
            "核心 GATT",
            "fail",
            format!("缺少：{}", report.missing_required_gatt.join(", ")),
        )
    };
    let recording_gatt_missing = report.missing_required_gatt.iter().any(|item| {
        item.starts_with("meeting_") || item.starts_with("recording_")
    });
    let board_microphone = match (
        recording_gatt_missing,
        report.recording_list_error.as_deref(),
    ) {
        (false, None) => oobe_check(
            "boardMicrophone",
            "板端录音链路",
            "warn",
            format!(
                "录音控制/目录接口可访问，设备内 {} 条录音；为避免副作用，本检查未启动麦克风实录",
                report.recordings_available
            ),
        ),
        (true, _) => oobe_check(
            "boardMicrophone",
            "板端录音链路",
            "fail",
            "录音/会议核心 GATT 不完整，未启动实录",
        ),
        (false, Some(error)) => oobe_check(
            "boardMicrophone",
            "板端录音链路",
            "fail",
            format!("录音目录不可读：{error}"),
        ),
    };
    let clock = match (
        report.clock_sync_evidence.as_deref(),
        report.clock_sync_error.as_deref(),
    ) {
        (Some(evidence), _) => oobe_check("clock", "自动校时", "pass", evidence),
        (_, Some(error)) => oobe_check("clock", "自动校时", "fail", error),
        _ => oobe_check("clock", "自动校时", "fail", "未取得校时写后读回证据"),
    };
    let imu = match (
        report.imu_status_read,
        report.identity.imu_supported,
        report.identity.imu_online,
    ) {
        (true, Some(true), Some(true)) => oobe_check(
            "imu",
            "IMU",
            "pass",
            format!("在线，采样率 {} Hz", report.identity.imu_sample_hz.unwrap_or_default()),
        ),
        (true, Some(false), _) => oobe_check("imu", "IMU", "warn", "固件明确报告未装配"),
        (true, Some(true), _) => oobe_check("imu", "IMU", "fail", "已装配，但未在线"),
        _ => oobe_check(
            "imu",
            "IMU",
            "warn",
            "IMU_STATUS 未读到；未判定为通过",
        ),
    };
    let speaker = match (
        report.speaker_status_read,
        report.identity.speaker_supported,
        report.identity.speaker_online,
    ) {
        (true, Some(true), Some(true)) => oobe_check(
            "speaker",
            "扬声器",
            "pass",
            format!("在线，音量 {}%（未播放测试音）", report.identity.speaker_volume.unwrap_or_default()),
        ),
        (true, Some(false), _) => {
            oobe_check("speaker", "扬声器", "warn", "固件明确报告未装配")
        }
        (true, Some(true), _) => oobe_check("speaker", "扬声器", "fail", "已装配，但未在线"),
        _ => oobe_check(
            "speaker",
            "扬声器",
            "warn",
            "SPEAKER_STATUS 未读到；未判定为通过",
        ),
    };
    vec![
        oobe_check(
            "bluetooth",
            "蓝牙连接",
            "pass",
            format!("已临时连接并完成服务发现，检查后已断开：{}", report.device_id),
        ),
        firmware,
        gatt,
        board_microphone,
        clock,
        imu,
        speaker,
        oobe_check(
            "display",
            "墨水屏",
            "warn",
            "未检查；当前固件没有可读的屏幕自检 GATT，需实板观察刷新",
        ),
        oobe_check(
            "touch",
            "触摸",
            "warn",
            "未检查；当前固件没有可读的触摸自检 GATT，需实板操作",
        ),
        oobe_check(
            "power",
            "电源与充电",
            "warn",
            "未检查；当前固件没有可读的电源/充电自检 GATT，需实板测量",
        ),
        oobe_check(
            "remoteServices",
            "ASR / 纪要服务",
            "warn",
            "本次硬件检查未调用录音、ASR 或纪要服务；请在真实会议链路中单独验收",
        ),
    ]
}

fn failed_oobe_checks(error: &str) -> Vec<CompanionV1OobeCheck> {
    vec![
        oobe_check("bluetooth", "蓝牙连接", "fail", error),
        oobe_check("firmware", "固件与板卡身份", "fail", "未检查：设备连接失败"),
        oobe_check("gatt", "核心 GATT", "fail", "未检查：设备连接失败"),
        oobe_check(
            "boardMicrophone",
            "板端录音链路",
            "warn",
            "未检查；没有使用主机麦克风代替板端证据",
        ),
        oobe_check("clock", "自动校时", "fail", "未检查：设备连接失败"),
        oobe_check("imu", "IMU", "warn", "未检查"),
        oobe_check("speaker", "扬声器", "warn", "未检查；未播放测试音"),
        oobe_check(
            "display",
            "墨水屏",
            "warn",
            "未检查；当前固件没有可读的屏幕自检 GATT",
        ),
        oobe_check(
            "touch",
            "触摸",
            "warn",
            "未检查；当前固件没有可读的触摸自检 GATT",
        ),
        oobe_check(
            "power",
            "电源与充电",
            "warn",
            "未检查；当前固件没有可读的电源/充电自检 GATT",
        ),
        oobe_check(
            "remoteServices",
            "ASR / 纪要服务",
            "warn",
            "未调用外部服务",
        ),
    ]
}

fn oobe_blocked_by_active_recording(
    snapshot: &CompanionV1Snapshot,
    live_asr_active: bool,
) -> bool {
    live_asr_active
        || snapshot.meeting.active
        || snapshot
            .host
            .sessions
            .iter()
            .any(|session| session.status == "recording")
}

fn apply_connection_preference(
    snapshot: &mut CompanionV1Snapshot,
    preference: &device_connection::DeviceConnectionPreference,
) {
    if !snapshot.device.connected {snapshot.device.recording_capacity=None;}
    snapshot.device.remembered_device_id = preference.remembered_device_id.clone();
    snapshot.device.auto_reconnect_enabled = preference.auto_reconnect_enabled;
    snapshot.device.manual_disconnect = preference.manual_disconnect;
    snapshot.device.last_connected_at = preference.last_connected_at.clone();
    if !snapshot.device.connected && preference.pairing_required && preference.auto_reconnect_enabled && !preference.manual_disconnect {
        snapshot.device.connection_phase="pairingRequired".into();
        snapshot.device.message="Windows 配对未完成，已暂停自动重试。请检查设备配对入口后主动连接；原录音保留。".into();
    } else if !preference.pairing_required && snapshot.device.connection_phase=="pairingRequired" {
        snapshot.device.connection_phase=if snapshot.device.connected {"ready"}
            else if preference.manual_disconnect {"manualDisconnected"}
            else if preference.remembered_device_id.is_some() {"offline"} else {"idle"}.into();
    }
}

fn connection_timestamp() -> String {
    unix_time_ms().to_string()
}

fn observation_timestamp() -> String {
    chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Millis, true)
}

fn speaker_prompt_id(value: Option<&str>) -> Result<u8, String> {
    match value.map(str::trim).filter(|value| !value.is_empty()) {
        None | Some("confirm") | Some("0") => Ok(0),
        Some("recordingStarted") | Some("1") => Ok(1),
        Some("recordingStopped") | Some("2") => Ok(2),
        Some("error") | Some("3") => Ok(3),
        Some(value) => Err(format!("unsupported Companion speaker prompt_id: {value}")),
    }
}

pub struct FixtureCompanionBackend {
    snapshot: Mutex<CompanionV1Snapshot>,
    meeting_processing: Mutex<()>,
    host_recording: HostRecordingManager,
    shutdown_host_recording: Mutex<Option<String>>,
    live_asr: Arc<LiveAsrHub>,
    transcription: CompanionTranscriptionManager,
    minutes: CompanionMinutesManager,
    ble_bridge: CompanionBleBridge,
    privacy: PrivacyManager,
    pending_meeting_start: Mutex<Option<PendingMeetingStart>>,
    connection_preference: Mutex<device_connection::DeviceConnectionPreference>,
}

impl FixtureCompanionBackend {
    pub fn new() -> Self {
        let mut snapshot = fixture_snapshot();
        snapshot.minutes_context_supported = true;
        let (sessions, storage) = persistence::load_sessions_with_status();
        snapshot.host.persistence = storage;
        if let Some(sessions) = sessions {
            snapshot.host.sessions = sessions;
        } else if !cfg!(test) || snapshot.host.persistence.status == "blocked" {
            snapshot.host.sessions.clear();
            snapshot.host.selected_session_id = None;
            snapshot.host.active_session_id = None;
        }
        let connection_preference = device_connection::load();
        snapshot.device.remembered_device_id = connection_preference.remembered_device_id.clone();
        snapshot.device.auto_reconnect_enabled = connection_preference.auto_reconnect_enabled;
        snapshot.device.manual_disconnect = connection_preference.manual_disconnect;
        snapshot.device.last_connected_at = connection_preference.last_connected_at.clone();
        snapshot.device.device_id = connection_preference.remembered_device_id.clone();
        snapshot.device.connection_phase = if connection_preference.manual_disconnect {
            "manualDisconnected"
        } else if connection_preference.pairing_required {
            "pairingRequired"
        } else if connection_preference.remembered_device_id.is_some() {
            "offline"
        } else {
            "idle"
        }
        .to_string();
        snapshot.source = if connection_preference.remembered_device_id.is_some() {
            "lastKnown"
        } else {
            "unavailable"
        };
        apply_connection_preference(&mut snapshot,&connection_preference);
        // A restored library is readable before any control/selection action.
        refresh_privacy_counts(&mut snapshot);
        Self {
            snapshot: Mutex::new(snapshot),
            meeting_processing: Mutex::new(()),
            host_recording: HostRecordingManager::new(),
            shutdown_host_recording: Mutex::new(None),
            live_asr: Arc::new(LiveAsrHub::new()),
            transcription: CompanionTranscriptionManager::new(),
            minutes: CompanionMinutesManager::new(),
            ble_bridge: CompanionBleBridge::detect_default(),
            privacy: PrivacyManager::new(),
            pending_meeting_start: Mutex::new(None),
            connection_preference: Mutex::new(connection_preference),
        }
    }

    /// External ASR/minutes work must not own the UI/recorder state lock.
    /// Re-enter against the exact target, never a newly selected session, and
    /// reject late output after edits/deletion instead of restoring stale state.
    fn run_meeting_work<'a,T>(&'a self,
        snapshot: std::sync::MutexGuard<'a,CompanionV1Snapshot>,
        request: &CompanionV1ControlRequest, work: impl FnOnce()->T,
    )->Result<(std::sync::MutexGuard<'a,CompanionV1Snapshot>,T),String> {
        let input=request.session_id.as_deref()
            .and_then(|id|snapshot.host.sessions.iter().find(|s|s.id==id)).cloned();
        let input_bytes=serde_json::to_vec(&input).map_err(|_|"无法核对会议处理输入。")?;
        drop(snapshot);
        let result=work();
        let mut snapshot=self.snapshot.lock().map_err(|_|"Companion backend state lock failed")?;
        let current=request.session_id.as_deref()
            .and_then(|id|snapshot.host.sessions.iter().find(|s|s.id==id));
        if serde_json::to_vec(&current).map_err(|_|"无法核对会议处理结果。")?!=input_bytes {
            if let (Some(input),Some(current))=(input.as_ref(),request.session_id.as_deref()
                .and_then(|id|snapshot.host.sessions.iter_mut().find(|s|s.id==id))) {
                // Only retire our unchanged in-flight claim. A user import,
                // privacy action or pause may already have superseded it.
                if serde_json::to_vec(&current.recovery).map_err(|_|"无法核对当前处理状态。")?
                    ==serde_json::to_vec(&input.recovery).map_err(|_|"无法核对原处理状态。")?
                    && matches!(current.recovery.stage.as_str(),"transcribing"|"generatingMinutes") {
                    schedule_recovery_failure(current,MEETING_WORK_SUPERSEDED);
                    persistence::save_snapshot(&mut snapshot)?;
                }
            }
            return Err(MEETING_WORK_SUPERSEDED.into());
        }
        Ok((snapshot,result))
    }

    fn observe_pairing_failure(&self,snapshot:&mut CompanionV1Snapshot,target:Option<&str>,error:&str) {
        if !reconnect_requires_pairing(error) {return;}
        let Some(target)=target else{return;};
        let Ok(mut preference)=self.connection_preference.lock() else{return;};
        if !preference.mark_pairing_required(target) {return;}
        snapshot.connected=false;snapshot.device.connected=false;
        apply_connection_preference(snapshot,&preference);
        snapshot.device.message=error.into();
        if let Err(save_error)=device_connection::save(&preference) {
            snapshot.device.message=format!("{error}；自动重试已在本次运行暂停，但暂停状态未保存：{save_error}");
            eprintln!("[device-reconnect] pairing pause checkpoint failed; current process remains paused: {save_error}");
        }
    }

    fn retire_recovery_after_optout(&self,target:&str)->Result<Option<CompanionV1Snapshot>,String> {
        let mut snapshot=self.snapshot.lock().map_err(|_|"Companion backend state lock failed")?;
        let preference=self.connection_preference.lock().map_err(|_|"device connection preference lock failed")?;
        if preference.can_automatically_reconnect() && preference.remembered_device_id.as_deref()
            .is_some_and(|id|device_connection::same_device_id(id,target)) {return Ok(None);}
        // The recovery QUERY may have retained the original recorder while
        // the user requested Disconnect. Close only its exact connection,
        // without STOP/consume or retiring the original recording journal.
        ble_bridge::disconnect_retained_recording(Some(target))?;
        if snapshot.device.device_id.as_deref().is_none_or(|id|device_connection::same_device_id(id,target)) {
            snapshot.connected=false;snapshot.device.connected=false;
            snapshot.device.connection_phase=if preference.manual_disconnect {"manualDisconnected"} else {"offline"}.into();
            apply_connection_preference(&mut snapshot,&preference);
        }
        Ok(Some(snapshot.clone()))
    }

    fn merge_live_asr_into_session(
        session: &mut CompanionV1HostSession,
        live: &live_asr::LiveAsrSnapshot,
    ) {
        // A failed live stream does not stop the recorder. Surface that the
        // preserved audio still needs a complete transcription, even if the
        // provider failed before returning its first partial.
        if live.error.is_some() {
            session.pending_reason = Some("needs_transcription".to_string());
        }
        if live.text.trim().is_empty() {
            return;
        }
        session.live_transcript_text = live.text.clone();
        session.transcript_text = live.text.clone();
        session.transcript_final = false;
        session.transcript_preview = live.text.chars().take(120).collect();
        session.transcript_segments = live
            .text
            .split(|c: char| c == '\n' || c == '。' || c == '.')
            .filter(|s| !s.trim().is_empty())
            .count();
        session.retention.transcript_cached = true;
    }

    // A partial hypothesis remains useful, but only a successful final
    // response may complete transcription and unlock meeting generation.
    fn finish_live_nonempty(session: &mut CompanionV1HostSession, live: &live_asr::LiveAsrSnapshot) -> bool {
        Self::merge_live_asr_into_session(session, live);
        if live.error.is_some() {
            session.status = "captured".to_string();
            session.transcript_final = false;
            arm_meeting_recovery(session);
            session.pending_reason = Some("needs_transcription".to_string());
            return false;
        }
        session.transcript_final = true;
        session.status = "transcribed".to_string();
        session.pending_reason = None;
        arm_meeting_recovery(session);
        mark_recovery_transcribed(session);
        true
    }
}

#[cfg(test)]
mod live_stop_contract_tests {
    use super::*;
    use crate::companion_v1::{apply_fixture_control, fixture_snapshot};
    fn sample() -> CompanionV1HostSession {
        let request=serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
        let mut session=apply_fixture_control(fixture_snapshot(),request).unwrap().host.sessions.remove(0);
        session.meeting_mode="onlineLive".into();
        session.status="captured".into();
        session.audio_stored=true;
        session.audio_path=Some("owned-original.wav".into());
        session.audio_bytes=12345;
        session.retention.audio_cached=true;
        session
    }
    #[test]
    fn interrupted_live_preserves_partial_but_never_marks_it_final() {
        let mut session=sample();
        let live=live_asr::LiveAsrSnapshot {text:"前半句".into(),mode:"ws-sauc-streaming".into(),error:Some("connection closed before final".into()),partial_count:1,active:false};
        let complete=FixtureCompanionBackend::finish_live_nonempty(&mut session,&live);
        assert!(!complete,"provider failure cannot finalize a partial transcript");
        assert!(!session.transcript_final);
        assert_ne!(session.status,"transcribed");
        assert_eq!(session.transcript_text,"前半句");
        assert_eq!(session.audio_path.as_deref(),Some("owned-original.wav"));
        assert!(session.audio_stored && session.retention.audio_cached);
        assert!(session.pending_reason.is_some());
    }
    #[test]
    fn live_failure_is_visible_while_recording_even_before_first_partial() {
        for text in ["", "已有片段"] {
            let mut session=sample();session.status="recording".into();session.pending_reason=None;
            session.transcript_text.clear();session.live_transcript_text.clear();session.transcript_final=false;
            let live=live_asr::LiveAsrSnapshot {text:text.into(),mode:"ws-sauc-streaming".into(),error:Some("connection lost".into()),partial_count:u32::from(!text.is_empty()),active:false};
            FixtureCompanionBackend::merge_live_asr_into_session(&mut session,&live);
            assert_eq!(session.status,"recording");
            assert_eq!(session.pending_reason.as_deref(),Some("needs_transcription"));
            assert!(!session.transcript_final);
            assert_eq!(session.audio_path.as_deref(),Some("owned-original.wav"));
            if !text.is_empty(){assert_eq!(session.transcript_text,text);}
        }
    }
    #[test]
    fn recording_snapshot_reports_failed_live_stream_without_stopping_audio() {
        let backend=FixtureCompanionBackend::new();let mut session=sample();
        session.id="live-failure".into();session.status="recording".into();session.pending_reason=None;
        session.transcript_text.clear();session.live_transcript_text.clear();session.transcript_final=false;
        {
            let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.sessions=vec![session];
            snapshot.host.selected_session_id=Some("live-failure".into());snapshot.meeting.active=true;
        }
        backend.live_asr.set_failed_for_test("");
        let snapshot=backend.snapshot().unwrap();let session=&snapshot.host.sessions[0];
        assert!(snapshot.meeting.active);assert_eq!(session.status,"recording");
        assert_eq!(session.pending_reason.as_deref(),Some("needs_transcription"));
        assert_eq!(session.audio_path.as_deref(),Some("owned-original.wav"));
        assert!(!session.transcript_final);
    }
    #[test]
    fn confirmed_live_final_is_still_completed() {
        let mut session=sample();
        let live=live_asr::LiveAsrSnapshot {text:"完整文本".into(),mode:"ws-sauc-streaming".into(),error:None,partial_count:2,active:false};
        assert!(FixtureCompanionBackend::finish_live_nonempty(&mut session,&live));
        assert!(session.transcript_final);
        assert_eq!(session.status,"transcribed");
        assert_eq!(session.transcript_text,"完整文本");
        assert_eq!(session.audio_path.as_deref(),Some("owned-original.wav"));
    }
    #[test]
    fn stop_without_worker_keeps_preexisting_partial_unfinished() {
        let backend = FixtureCompanionBackend::new();
        let mut session = sample();
        session.id = "saved-partial-before-stop".into();
        session.source = "hostMicrophone".into();
        session.status = "recording".into();
        session.transcript_text = "前半句".into();
        session.live_transcript_text = "前半句".into();
        session.transcript_final = false;
        session.recovery = CompanionV1MeetingRecovery::default();
        session.processing_policy = crate::companion_v1::CompanionV1ProcessingPolicy::Manual;
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            snapshot.host.sessions = vec![session];
            snapshot.host.selected_session_id = Some("saved-partial-before-stop".into());
            snapshot.host.active_session_id = Some("saved-partial-before-stop".into());
            snapshot.meeting.active = true;
        }
        let request = serde_json::from_value(serde_json::json!({"action":"meetingStop", "sessionId":"saved-partial-before-stop"})).unwrap();
        let stopped = backend.apply_control(request).unwrap();
        let s = &stopped.host.sessions[0];
        assert_eq!(s.transcript_text, "前半句");
        assert!(!s.transcript_final);
        assert_eq!(s.status, "captured", "an unfinished prior partial must not be promoted by stop");
        assert!(!transcript_review::final_transcript_available(s));
        assert_eq!(s.pending_reason.as_deref(), Some("needs_transcription"));
    }

    #[test]
    fn finalize_with_unfinished_partial_never_creates_complete_minutes() {
        let mut snapshot = fixture_snapshot();
        let mut session = sample();
        session.id = "partial-finalize".into();
        session.status = "recording".into();
        session.transcript_text = "前半句".into();
        session.live_transcript_text = "前半句".into();
        session.transcript_final = false;
        session.recovery = CompanionV1MeetingRecovery::default();
        session.minutes = None;
        session.minutes_by_mode = Default::default();
        session.export_markdown.clear();
        snapshot.host.sessions = vec![session];
        snapshot.host.selected_session_id = Some("partial-finalize".into());
        snapshot.host.active_session_id = Some("partial-finalize".into());
        snapshot.meeting.active = true;
        let request = serde_json::from_value(serde_json::json!({"action":"meetingFinalize", "sessionId":"partial-finalize"})).unwrap();
        let result = apply_fixture_control(snapshot, request).unwrap();
        let s = &result.host.sessions[0];
        assert_eq!(s.transcript_text, "前半句");
        assert!(!s.transcript_final);
        assert!(s.minutes.is_none(), "incomplete live text cannot create final minutes");
        assert_eq!(s.pending_reason.as_deref(), Some("needs_transcription"));
    }

}

impl Default for FixtureCompanionBackend {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod manual_disconnect_tests {
    use super::*;
    const PEER:&str="C8:ED:45:EB:95:B4";

    #[test]
    fn manual_intent_does_not_wait_for_inflight_snapshot_and_restarts_suppressed() {
        let backend=std::sync::Arc::new(FixtureCompanionBackend::new());
        backend.connection_preference.lock().unwrap().remember_native_success(PEER,"before".into());
        let snapshot=backend.snapshot.lock().unwrap();
        let worker=std::sync::Arc::clone(&backend);let (tx,rx)=std::sync::mpsc::channel();
        let thread=std::thread::spawn(move||tx.send(worker.request_manual_disconnect(Some(PEER))).unwrap());
        let result=rx.recv_timeout(std::time::Duration::from_secs(2));
        drop(snapshot);thread.join().unwrap();result.unwrap().unwrap();
        let preference=backend.connection_preference.lock().unwrap().clone();
        assert!(preference.manual_disconnect && !preference.can_automatically_reconnect());
        let path=std::env::temp_dir().join(format!("companion-disconnect-intent-{}.json",uuid::Uuid::new_v4()));
        device_connection::save_to(&path,&preference).unwrap();
        let restarted=device_connection::load_from(&path).unwrap();
        assert_eq!(restarted,preference);assert!(!restarted.can_automatically_reconnect());
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn foreign_manual_intent_cannot_change_the_remembered_peer() {
        let backend=FixtureCompanionBackend::new();
        backend.connection_preference.lock().unwrap().remember_native_success(PEER,"before".into());
        let before=backend.connection_preference.lock().unwrap().clone();
        for target in ["AA:BB:CC:DD:EE:FF","Companion",""] {
            assert!(backend.request_manual_disconnect(Some(target)).is_err());
            assert_eq!(*backend.connection_preference.lock().unwrap(),before);
        }
        backend.request_manual_disconnect(Some("c8-ed-45-eb-95-b4")).unwrap();
        assert!(backend.connection_preference.lock().unwrap().manual_disconnect);
    }

    #[test]
    fn late_original_recovery_after_manual_intent_releases_link_without_ending_recording() {
        let backend=FixtureCompanionBackend::new();
        backend.connection_preference.lock().unwrap().remember_native_success(PEER,"before".into());
        let original={
            let mut s=backend.snapshot.lock().unwrap();s.source="firmware";s.connected=true;
            s.device.connected=true;s.device.device_id=Some(PEER.into());s.device.mode="windowsNative".into();
            s.device.recording=true;s.meeting.active=true;
            let mut row=crate::companion_v1::synced_device_session(&s,
                &crate::control_request(CompanionV1ControlAction::DeviceSyncRecordings,Some("original".into())),"before");
            row.status="recording".into();row.source="boardDevice".into();row.source_device_id=Some(PEER.into());
            s.host.sessions=vec![row];s.host.active_session_id=Some(s.host.sessions[0].id.clone());
            serde_json::to_value(&s.host).unwrap()
        };
        assert!(backend.retire_recovery_after_optout(PEER).unwrap().is_none());
        backend.request_manual_disconnect(Some(PEER)).unwrap();
        let s=backend.retire_recovery_after_optout(PEER).unwrap().unwrap();
        assert!(!s.connected && !s.device.connected);assert!(s.device.recording && s.meeting.active);
        assert_eq!(s.device.connection_phase,"manualDisconnected");
        assert_eq!(serde_json::to_value(&s.host).unwrap(),original);
        assert!(!backend.connection_preference.lock().unwrap().can_automatically_reconnect());
    }
}

impl CompanionBackend for FixtureCompanionBackend {
    fn finish_meeting_processing_on_exit(&self, budget: std::time::Duration) -> Result<(), String> {
        meeting_processing_job::wait_for_idle(&self.meeting_processing, budget)?;
        let mut snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用，无法确认处理状态已保存。")?;
        if snapshot.host.persistence.status!="ready" {
            persistence::save_snapshot(&mut snapshot)
                .map_err(|_|"会议状态尚未保存，请处理保存问题后再次关闭。")?;
        }
        Ok(())
    }
    fn finish_host_recording_on_exit(&self) -> Result<(), String> {
        // Only this process's own microphone is stopped. A board recording is
        // not owned by HostRecordingManager and must continue independently.
        let mut pending=self.shutdown_host_recording.lock().map_err(|_|"电脑录音收尾状态不可用。")?;
        if pending.is_none() { *pending=self.host_recording.active_session_id()?; }
        let Some(id)=pending.clone() else {return Ok(());};
        let active=self.host_recording.active_session_id()?;
        if active.as_deref().is_some_and(|active|active!=id) {
            return Err("另一场电脑录音仍在进行，未结束错误的录音。".into());
        }
        if active.as_deref()==Some(id.as_str()) {
            let mut request=crate::control_request(CompanionV1ControlAction::MeetingStop,Some(id.clone()));
            request.prompt_id=Some("__companion_shutdown_save_only__".into());
            self.apply_control(request)?;
        }
        let mut snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用。")?;
        let row=snapshot.host.sessions.iter().find(|row|row.id==id)
            .ok_or("电脑录音保存状态尚未确认，已保留原文件。")?;
        if row.source!="hostMicrophone" || row.status=="recording" || !row.audio_stored {
            return Err("电脑录音尚未完成保存，已保留原文件供恢复。".into());
        }
        if snapshot.host.persistence.status!="ready" {
            persistence::save_snapshot(&mut snapshot)
                .map_err(|_|"电脑录音已停止，但会议库尚未保存；请处理存储问题后再次关闭。")?;
        }
        *pending=None;
        Ok(())
    }
    fn request_manual_disconnect(&self,target:Option<&str>)->Result<(),String> {
        let mut preference=self.connection_preference.lock().map_err(|_|"device connection preference lock failed")?;
        if target.is_some_and(|id| !device_connection::stable_device_id(id) ||
            preference.remembered_device_id.as_deref().is_some_and(|known|!device_connection::same_device_id(id,known))) {
            return Err("断开请求与当前记住的设备不一致，未修改自动连接选择。".into());
        }
        let mut next=preference.clone();next.mark_manual_disconnect();
        device_connection::save(&next)?;
        *preference=next;
        Ok(())
    }
    fn save_library_lifecycle(&self,request:library_lifecycle::Request)->Result<CompanionV1Snapshot,String>{
        let mut snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用。")?;
        if snapshot.host.persistence.status!="ready"{return Err("请先恢复或保存会议库，未改变保护或回收站状态。".into());}
        if snapshot.meeting.active||snapshot.device.recording||snapshot.host.sessions.iter().any(|r|r.status=="recording"){
            return Err("请先结束并保存录音，再整理保护或回收站。".into());
        }
        if cfg!(test)&&std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none(){library_lifecycle::apply(&mut snapshot.host.sessions,&request,&connection_timestamp())?;}
        else{snapshot.host.sessions=library_lifecycle::commit(&persistence::state_file_path(),&request,&connection_timestamp())?;}
        snapshot.updated_at=connection_timestamp();refresh_privacy_counts(&mut snapshot);Ok(snapshot.clone())
    }
    fn import_audio_file(&self,path:&std::path::Path)->Result<CompanionV1Snapshot,String> {
        {
            let snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用。")?;
            if snapshot.host.persistence.status!="ready" {return Err("请先恢复或保存会议库，再导入音频。".into());}
        }
        let imported=import_audio::import(path)?;
        let mut snapshot=self.snapshot.lock().map_err(|_|"音频已保存，但会议库暂时不可用。")?;
        let now=connection_timestamp();
        let mut request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some(imported.id.clone()));
        request.title=Some(imported.title);request.prompt_id=Some(crate::companion_v1::CAPTURE_ONLY_PROMPT.into());
        request.meeting_mode=Some("offlineStore".into());
        let mut row=crate::companion_v1::create_host_session(&snapshot,&request,&now);
        row.source="importedAudio".into();row.status="captured".into();row.started_at=None;row.stopped_at=None;
        row.audio_path=Some(imported.anchor.to_string_lossy().into_owned());row.audio_stored=true;row.retention.audio_cached=true;
        let samples=imported.parts.iter().try_fold(0u64,|n,p|n.checked_add(p.samples).ok_or("导入音频时长无效。"))?;
        row.duration_ms=samples/16;
        row.audio_bytes=imported.parts.iter().try_fold(0u64,|n,p|p.samples.checked_mul(2).and_then(|x|x.checked_add(44)).and_then(|x|n.checked_add(x)).ok_or("导入音频容量无效。"))?;
        row.chunks=if imported.parts.len()>1 {host_segmented_capture::session_chunks(&row.id,&imported.parts)?}
            else {seal_companion_v1_session_chunks(&row,&now,row.duration_ms,Some(row.audio_bytes))};
        row.chunks.push(crate::companion_v1::CompanionV1AudioChunk {
            id:format!("{}-imported-original-{}",row.id,imported.original_sha256),
            path:Some(imported.original.to_string_lossy().into_owned()),started_at:None,stopped_at:None,
            duration_ms:row.duration_ms,bytes:imported.original_bytes,status:"importedOriginal".into(),
        });
        if !snapshot.meeting.active && !snapshot.device.recording {snapshot.host.selected_session_id=Some(row.id.clone());}
        snapshot.host.sessions.insert(0,row);snapshot.updated_at=observation_timestamp();
        refresh_privacy_counts(&mut snapshot);persistence::save_snapshot(&mut snapshot)?;Ok(snapshot.clone())
    }
    fn restore_library_backup(&self,path:&std::path::Path)->Result<CompanionV1Snapshot,String>{
        let mut snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用。")?;
        if snapshot.host.persistence.status=="unsaved" {return Err("请先保存当前窗口中尚未保存的内容，再恢复备份。".into());}
        if snapshot.meeting.active||snapshot.device.recording||snapshot.host.sessions.iter().any(|r|r.status=="recording"||matches!(r.recovery.stage.as_str(),"transcribing"|"generatingMinutes")) {
            return Err("请先完成录音和整理，再恢复备份。".into());
        }
        library_backup::check_conflicts(path,&snapshot.host.sessions)?;
        let root=audio_storage::recording_root()?;
        let restored=library_backup::restore_files(path,&root)?;
        library_backup::restore_index(&persistence::state_file_path(),&restored)?;
        snapshot.host.sessions=persistence::load_sessions_from(&persistence::state_file_path())
            .ok_or("备份已写入，请重新打开应用核对会议库。")?;
        snapshot.host.persistence=Default::default();
        snapshot.updated_at=connection_timestamp();refresh_privacy_counts(&mut snapshot);Ok(snapshot.clone())
    }
    fn save_library_organization(&self,request:library_organization::Request)->Result<CompanionV1Snapshot,String>{
        let mut snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用。")?;
        if snapshot.host.persistence.status!="ready" {return Err("请先恢复或重试保存资料库；分类输入仍保留。".into());}
        if snapshot.meeting.active||snapshot.device.recording||snapshot.host.sessions.iter().any(|r|r.status=="recording"){
            return Err("请先结束并保存录音，再整理资料库。".into());
        }
        if cfg!(test)&&std::env::var("COMPANION_TYPE_STATE_PATH").is_err(){
            library_organization::apply(&mut snapshot.host.sessions,&request)?;
        }else{
            snapshot.host.sessions=library_organization::commit(&persistence::state_file_path(),&request)?;
        }
        snapshot.updated_at=connection_timestamp();refresh_privacy_counts(&mut snapshot);Ok(snapshot.clone())
    }
    fn refine_meeting_speakers(&self,id:&str)->Result<CompanionV1Snapshot,String> {
        let _processing=self.meeting_processing.lock().map_err(|_|"会议处理队列暂时不可用。")?;
        if lifecycle::PROCESS.requested() {return Err(lifecycle::CLOSING.into());}
        let snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用。")?;
        if snapshot.host.persistence.status!="ready" {return Err("请先保存或恢复会议库。".into());}
        let input=speaker_refinement::prepare(&snapshot,id)?;
        let row=snapshot.host.sessions.iter().find(|s|s.id==id).ok_or("找不到这场会议")?;
        let parts=if let Some(parts)=host_segmented_capture::saved_parts(row)? {parts}
            else if row.device_recording_key.is_some() {recording_wire::receiver::Receiver::verified_audio_parts(row)?}
            else {Vec::new()};
        let path=meeting_workspace::local_audio_path(&snapshot,id)?;
        let request=CompanionV1ControlRequest { minutes_template: None, recording_source: None,action:CompanionV1ControlAction::MeetingTranscribeAudio,session_id:Some(id.into()),
            context_note_revision: None, ble_name:None,prompt_id:None,title:None,transcript_text:None,meeting_mode:None,audio_path:None,audio_bytes:None,device_id:None,duration_ms:None};
        let (mut snapshot,result)=self.run_meeting_work(snapshot,&request,||if parts.len()>1 {
            transcription::refine_saved_speakers_parts(&parts,&input.utterances)
        } else {transcription::refine_saved_speakers(&path,&input.utterances)})?;
        let labels=result?;
        let row=snapshot.host.sessions.iter_mut().find(|r|r.id==id).ok_or("这场录音已不存在，未重建。")?;
        if !speaker_refinement::apply(row,labels)? {return Ok(snapshot.clone());}
        if snapshot.host.selected_session_id.as_deref()==Some(id) {snapshot.meeting.status="transcribed".into();}
        snapshot.updated_at=observation_timestamp();persistence::save_snapshot(&mut snapshot)?;
        refresh_privacy_counts(&mut snapshot);Ok(snapshot.clone())
    }
    fn preview_meeting_transcription(&self,id:&str,job_id:&str)->Result<transcription::TranscriptionPreview,String> {
        if id.is_empty() || !job_id.starts_with("__meeting_job__") {return Err("转写任务身份无效。".into());}
        let _processing=self.meeting_processing.lock().map_err(|_|"会议处理队列暂时不可用。")?;
        if lifecycle::PROCESS.requested() {return Err(lifecycle::CLOSING.into());}
        let snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用。")?;
        if snapshot.host.persistence.status!="ready" {return Err("请先保存或恢复会议库。".into());}
        let row=snapshot.host.sessions.iter().find(|s|s.id==id).ok_or("找不到这场录音。")?;
        library_lifecycle::require_available(row)?;
        if row.status=="recording" || host_audio_unconfirmed(row) {return Err("请先完成并保存录音。".into());}
        if row.capture_incomplete && !row.recovery.capture_review_confirmed {return Err("请先确认已保存的录音片段。".into());}
        if matches!(row.pending_reason.as_deref(),Some("needs_local_audio"|"needs_segments")) {return Err("请先完成原音同步。".into());}
        let paths=transcription_chunk_paths(row)?;
        let audio_path=row.audio_path.clone();
        let tracks=row.meeting_tracks.clone();
        let expected=(row.audio_bytes,row.duration_ms,row.recovery.capture_review_confirmed);
        let request=CompanionV1ControlRequest { minutes_template: None, recording_source:None, action:CompanionV1ControlAction::MeetingTranscribeAudio,
            session_id:Some(id.into()),context_note_revision:None,ble_name:None,prompt_id:Some(job_id.into()),title:None,
            transcript_text:None,meeting_mode:None,audio_path:None,audio_bytes:None,device_id:None,duration_ms:None};
        let _privacy=library_lifecycle::privacy_guard(&snapshot,&request,&persistence::state_file_path())?;
        privacy::validate_control(&snapshot,&request,self.live_asr.snapshot().active)?;
        let (_snapshot,result)=self.run_meeting_work(snapshot,&request,||meeting_processing_job::run(id,job_id,
            meeting_processing_job::Kind::Transcription,|| {
                if let Some(tracks)=tracks {
                    if tracks.state!="captured" && !(tracks.state=="needsReview" && expected.2) {
                        return Err("会议音轨尚未确认，请先恢复原音。".into());
                    }
                    meeting_audio_recovery::verify_tracks(&tracks,expected.0,expected.1)?;
                    let mic=tracks.microphone.into_iter().map(|p|p.path).collect::<Vec<_>>();
                    let system=tracks.system.into_iter().map(|p|p.path).collect::<Vec<_>>();
                    let result=meeting_audio_transcription::transcribe_tracks(&self.transcription,id,&mic,&system)?;
                    Ok(result.transcript.into())
                } else {
                    self.transcription.transcribe_session_owned(id,audio_path.as_deref(),&paths).map(Into::into)
                }
            }))?;
        result
    }
    fn preview_meeting_gap(&self,id:&str,job_id:&str,range:transcription::TranscriptionRange)->Result<transcription::TranscriptionPreview,String> {
        if id.is_empty() || !job_id.starts_with("__meeting_job__") {return Err("转写任务身份无效。".into());}
        let _processing=self.meeting_processing.lock().map_err(|_|"会议处理队列暂时不可用。")?;
        if lifecycle::PROCESS.requested() {return Err(lifecycle::CLOSING.into());}
        let snapshot=self.snapshot.lock().map_err(|_|"会议库暂时不可用。")?;
        if snapshot.host.persistence.status!="ready" {return Err("请先保存或恢复会议库。".into());}
        let row=snapshot.host.sessions.iter().find(|s|s.id==id).ok_or("找不到这场录音。")?;
        library_lifecycle::require_available(row)?;
        let final_text=transcript_review::final_transcript_available(row);
        let marked_gap=transcript_review::effective_unrecognized(row).iter().any(|gap|gap.source.is_none()
            && gap.start_ms==range.start_ms && gap.end_ms==range.end_ms);
        // With no final text there are no saved gap markers. An explicitly
        // chosen playback range is still useful when the whole recording was
        // unrecognized. It only produces a preview and never replaces text.
        if row.source=="hostMeeting" || row.status=="recording" || host_audio_unconfirmed(row)
            || (final_text && !marked_gap) {
            return Err("所选未识别时段已变化，请刷新后重新选择。".into());
        }
        if matches!(row.pending_reason.as_deref(),Some("needs_local_audio"|"needs_segments")) {
            return Err("请先完成原音同步。".into());
        }
        if row.capture_incomplete && !row.recovery.capture_review_confirmed {return Err("请先确认已保存的录音片段。".into());}
        let path=meeting_workspace::local_audio_path(&snapshot,id)?;
        let request=CompanionV1ControlRequest { minutes_template: None, recording_source:None, action:CompanionV1ControlAction::MeetingTranscribeAudio,
            session_id:Some(id.into()),context_note_revision:None,ble_name:None,prompt_id:Some(job_id.into()),title:None,
            transcript_text:None,meeting_mode:None,audio_path:None,audio_bytes:None,device_id:None,duration_ms:None};
        let _privacy=library_lifecycle::privacy_guard(&snapshot,&request,&persistence::state_file_path())?;
        privacy::validate_control(&snapshot,&request,self.live_asr.snapshot().active)?;
        let (_snapshot,result)=self.run_meeting_work(snapshot,&request,||meeting_processing_job::run(id,job_id,
            meeting_processing_job::Kind::Transcription,||self.transcription.preview_gap(id,&path,&range)))?;
        result
    }
    fn restore_local_recordings(&self) -> Result<recording_wire::receiver::LocalRestoreReport,String> {
        let report=recording_wire::receiver::restore_local_product()?;
        if !report.restored.is_empty() || !report.failures.is_empty() {
            let mut snapshot=self.snapshot.lock().map_err(|_| "会议状态暂时不可用，原音已保存。")?;
            if !report.restored.is_empty() || snapshot.host.persistence.status=="ready" {
                // Publishing verified raw completeness can precede a failed
                // WAV write. Surface that durable state without restarting,
                // while failure-only refresh never discards unsaved edits.
                reload_segmented_library(&mut snapshot,&persistence::state_file_path())?;
                snapshot.updated_at=observation_timestamp();refresh_privacy_counts(&mut snapshot);
            }
        }
        Ok(report)
    }
    fn save_meeting_note(&self, request: meeting_notes::Request) -> Result<CompanionV1Snapshot, String> {
        let mut snapshot = self.snapshot.lock().map_err(|_| "会议库暂时不可用。")?;
        if snapshot.host.persistence.status != "ready" { return Err("请先恢复或重试保存会议库；备注输入仍保留。".into()); }
        let row = snapshot.host.sessions.iter_mut().find(|s| s.id == request.session_id).ok_or("这场会议已不存在，未修改其他会议。")?;
        meeting_notes::commit(row, &request, &connection_timestamp())?;
        snapshot.updated_at = connection_timestamp();
        refresh_privacy_counts(&mut snapshot);
        Ok(snapshot.clone())
    }
    fn save_bookmark(&self, request: recording_bookmarks::Request, stamp: Option<recording_bookmarks::LiveStamp>)
        -> Result<CompanionV1Snapshot,String> {
        use recording_bookmarks::{Action, CommitError};
        let mut snapshot=self.snapshot.lock().map_err(|_| "会议库暂时不可用。")?;
        if snapshot.host.persistence.status != "ready" {
            return Err("请先重试保存或恢复会议库；重点输入仍保留。".into());
        }
        let mut candidate=snapshot.host.sessions.iter().find(|s| s.id == request.session_id)
            .ok_or("这场会议已不存在，未修改其他会议。")?.clone();
        library_lifecycle::require_available(&candidate)?;
        if recording_bookmarks::duplicate(&candidate,&request)? { return Ok(snapshot.clone()); }
        if request.expected_revision != candidate.bookmark_revision {
            return Err("会议重点已变化；你的输入仍保留，请刷新后核对。".into());
        }
        let native_stamp = if request.action == Action::AddLive && stamp.is_none() {
            if !snapshot.connected || !snapshot.device.connected {
                return Err("设备连接已断开；请主动连接这台设备后再标记，当前录音和输入仍保留。".into());
            }
            if candidate.meeting_mode == "onlineLive" {
                return Err("在线录音须由正在采集的连接取得时间；请等待连接恢复或收录后标记。".into());
            }
            Some(ble_bridge::live_recording_stamp(candidate.source_device_id.as_deref().ok_or("尚无设备录音身份。")?,
                &candidate.id,candidate.device_recording_id.ok_or("设备尚未建立这场录音。")?,candidate.device_recording_key.as_ref(),candidate.recorder_control.as_ref())?)
        } else { stamp };
        let playback = if request.action == Action::AddAt {
            let path=meeting_workspace::local_audio_path(&snapshot,&request.session_id)?;
            Some(if let Some(parts)=host_segmented_capture::saved_parts(&candidate)? {
                parts.iter().try_fold(0u64,|sum,(_,samples)|sum.checked_add(*samples).ok_or("录音时长无效。"))?/16
            } else if candidate.device_recording_key.is_some() {
                let parts=recording_wire::receiver::Receiver::verified_audio_parts(&candidate)?;
                parts.iter().try_fold(0u64,|sum,(_,samples)|sum.checked_add(*samples).ok_or("录音时长无效。"))?/16
            } else {meeting_workspace::wav_duration_ms(&path)?})
        } else { None };
        recording_bookmarks::apply(&mut candidate,&request,native_stamp.as_ref(),playback,&connection_timestamp())?;
        candidate.exported_at=None;
        match recording_bookmarks::commit(&mut candidate,request.expected_revision) {
            Err(CommitError::Conflict(error)) => return Err(error),
            Err(CommitError::Storage(error)) => {
                if let Some(row)=snapshot.host.sessions.iter_mut().find(|s| s.id == candidate.id) { *row=candidate; }
                snapshot.host.persistence.status="unsaved".into();
                snapshot.host.persistence.message=Some(format!("重点尚未保存到磁盘，请保留窗口并重试保存：{error}"));
                return Err("重点尚未保存到磁盘；请保留窗口并重试保存，输入仍保留。".into());
            }
            Ok(()) => {}
        }
        if let Some(row)=snapshot.host.sessions.iter_mut().find(|s| s.id == candidate.id) { *row=candidate; }
        snapshot.updated_at=connection_timestamp();
        Ok(snapshot.clone())
    }
    fn save_meeting_edit(&self, request: meeting_workspace::MeetingEditRequest) -> Result<CompanionV1Snapshot, String> {
        let mut snapshot = self.snapshot.lock().map_err(|_| "会议库暂时不可用".to_string())?;
        if snapshot.host.persistence.status != "ready" {
            return Err("请先重试保存或恢复会议库，再修改会议。".into());
        }
        let other_recording_active = snapshot.meeting.active || snapshot.device.recording
            || snapshot.host.sessions.iter().any(|s| s.status == "recording");
        if other_recording_active && snapshot.host.active_session_id.as_deref() == Some(request.session_id.as_str()) {
            return Err("这场录音仍在进行，请结束并保存后修改。".into());
        }
        let session = snapshot.host.sessions.iter_mut().find(|s| s.id == request.session_id)
            .ok_or("这场会议已不存在；未修改其他会议。")?;
        if other_recording_active {
            // A saved row is committed independently; edit_session still rejects
            // the actual recording or a row undergoing transcription/minutes.
            meeting_workspace::commit_saved_row(session, &request, &connection_timestamp())?;
        } else {
            meeting_workspace::edit_session(session, &request, &connection_timestamp())?;
        }
        snapshot.updated_at = connection_timestamp();
        refresh_privacy_counts(&mut snapshot);
        if !other_recording_active { let _ = persistence::save_snapshot(&mut snapshot); }
        Ok(snapshot.clone())
    }

    fn capabilities(&self) -> CompanionBackendCapabilities {
        let ble_status = self.ble_bridge.status();
        CompanionBackendCapabilities {
            backend_id: "companion-type.hybrid-host".to_string(),
            backend_kind: "host-recording+standalone-transcription+fixture-control".to_string(),
            services: CompanionBackendServices {
                device_control: CompanionServiceBoundary {
                    provider_id: ble_status.provider_id.clone(),
                    mode: ble_status.mode.clone(),
                    supported: ble_status.ready,
                    notes: ble_status.message,
                },
                recording: CompanionServiceBoundary {
                    provider_id: "host-microphone-wav".to_string(),
                    mode: "real-host-wav+explicit-synthetic-tests".to_string(),
                    supported: true,
                    notes: "Records host microphone sessions as 16 kHz mono WAV files; tests can force synthetic mode."
                        .to_string(),
                },
                transcription: CompanionServiceBoundary {
                    provider_id: "companion-type-transcription".to_string(),
                    mode: "batch+onlineLive-streaming".to_string(),
                    supported: true,
                    notes: "Batch ASR for offlineStore; onlineLive uses Volc SAUC mid-meeting streaming (mock via COMPANION_TYPE_LIVE_ASR_MOCK=1). listener-type.exe is not used."
                        .to_string(),
                },
                minutes: CompanionServiceBoundary {
                    provider_id: "companion-type-minutes".to_string(),
                    mode: "rules_l0+optional-command".to_string(),
                    supported: true,
                    notes: "L0 rules_l0 draft always; optional COMPANION_TYPE_MINUTES_COMMAND for LLM upgrade."
                        .to_string(),
                },
                export: CompanionServiceBoundary {
                    provider_id: "fixture-markdown-export".to_string(),
                    mode: "markdown".to_string(),
                    supported: true,
                    notes: "Exports generated meeting minutes to Markdown in app state.".to_string(),
                },
            },
        }
    }

    fn ble_bridge_status(&self) -> CompanionBleBridgeStatus {
        self.ble_bridge.status()
    }

    fn snapshot(&self) -> Result<CompanionV1Snapshot, String> {
        #[cfg(windows)]
        let meeting_capture_error = self.host_recording.meeting_capture_error();
        let live = self.live_asr.snapshot();
        let mut guard = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        // While onlineLive recording, surface provisional stream text without a control click.
        if live.active || !live.text.trim().is_empty() || live.error.is_some() {
            if let Some(session) = selected_session_mut(&mut guard) {
                if session.meeting_mode == "onlineLive" && session.status == "recording" {
                    Self::merge_live_asr_into_session(session, &live);
                }
            }
        }
        let mut snapshot=guard.clone();
        if let Some((id,error))=self.host_recording.current_error() {
            if let Some(session)=snapshot.host.sessions.iter_mut().find(|session|session.id==id && session.status=="recording") {
                session.recovery.last_error=Some(format!("录音可能已中断：{error}；请结束录音并检查已保存内容。"));
            }
        }
        #[cfg(windows)]
        if let Some((id, error)) = meeting_capture_error {
            if let Some(row) = snapshot.host.sessions.iter_mut().find(|row| row.id == id && row.status == "recording") {
                if let Some(tracks) = row.meeting_tracks.as_mut() { tracks.issue = Some(error); }
            }
        }
        Ok(snapshot)
    }

    fn apply_control(
        &self,
        mut request: CompanionV1ControlRequest,
    ) -> Result<CompanionV1Snapshot, String> {
        // This backend owns the real persisted library despite its legacy
        // Fixture name. Synthetic samples belong only to the isolated pure
        // fixture reducer; renderer input must never fabricate a saved capture.
        if request.action == CompanionV1ControlAction::MeetingLoadDemo {
            return Err("演示只在隔离预览中可用，不会添加到本机录音库。".into());
        }
        const AUTO_RECOVERY_PROMPT_ID: &str = "__companion_auto_recovery__";
        let automatic_recovery = request.prompt_id.as_deref() == Some(AUTO_RECOVERY_PROMPT_ID);
        let shutdown_save_only = request.prompt_id.as_deref() == Some("__companion_shutdown_save_only__");

        // Default meeting mode from product settings / env when UI omits it.
        if matches!(request.action, CompanionV1ControlAction::MeetingStart)
            && request
                .meeting_mode
                .as_deref()
                .map(str::trim)
                .filter(|m| !m.is_empty())
                .is_none()
        {
            let mode = std::env::var("COMPANION_TYPE_DEFAULT_MEETING_MODE")
                .ok()
                .filter(|m| m == "onlineLive" || m == "offlineStore")
                .unwrap_or_else(|| product_settings::load_settings().default_meeting_mode);
            request.meeting_mode = Some(mode);
        }
        if let Some(source) = request.recording_source.as_deref() {
            if request.action != CompanionV1ControlAction::MeetingStart || source != "hostMeeting"
                || request.audio_path.is_some() || request.device_id.is_some() {
                return Err("会议录音来源无效，请重新选择。".into());
            }
            if request.meeting_mode.as_deref() != Some("offlineStore") {
                return Err("电脑会议双音轨目前先保存录音，结束后再转写。".into());
            }
            #[cfg(not(windows))]
            return Err("此平台暂不支持电脑会议音轨采集。".into());
        }

        // Serialize service jobs separately; a retry can wait here without
        // holding the shared state needed by snapshots, capture and selection.
        let action=request.action;
        let _processing=if matches!(action,CompanionV1ControlAction::MeetingTranscribeAudio
            | CompanionV1ControlAction::MeetingGenerateMinutes) {
            let guard=self.meeting_processing.lock().map_err(|_|"会议处理队列暂时不可用。")?;
            if lifecycle::PROCESS.requested() {return Err(lifecycle::CLOSING.into());}
            Some(guard)
        } else {None};
        let mut snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        // Capture the exact contents seen before a destructive operation; an
        // ID alone cannot authorize clearing newer audio added concurrently.
        let privacy_authorizations = if matches!(action,CompanionV1ControlAction::PrivacyEraseAudio
            | CompanionV1ControlAction::PrivacyDeleteSession | CompanionV1ControlAction::PrivacyEraseAll) {
            snapshot.host.sessions.iter().map(session_store::privacy_authorization)
                .collect::<Result<Vec<_>,_>>()?
        } else { Vec::new() };
        if matches!(action,CompanionV1ControlAction::MeetingTranscribeAudio
            | CompanionV1ControlAction::MeetingGenerateMinutes) && request.session_id.is_none() {
            request.session_id=selected_session(&snapshot).map(|s|s.id.clone());
        }
        let _library_privacy_guard=library_lifecycle::privacy_guard(&snapshot,&request,&persistence::state_file_path())?;
        privacy::validate_control(&snapshot, &request, self.live_asr.snapshot().active)?;
        if matches!(action,CompanionV1ControlAction::MeetingTranscribeAudio|CompanionV1ControlAction::MeetingGenerateMinutes|CompanionV1ControlAction::MeetingRestoreAudio){
            if let Some(row)=request.session_id.as_deref().and_then(|id|snapshot.host.sessions.iter().find(|s|s.id==id)){library_lifecycle::require_available(row)?;}
        }
        if action==CompanionV1ControlAction::MeetingTranscribeAudio {
            if let Some(row)=request.session_id.as_deref().or(snapshot.host.selected_session_id.as_deref())
                .and_then(|id|snapshot.host.sessions.iter().find(|s|s.id==id)) {
                if row.pending_reason.as_deref()==Some("needs_local_audio") {
                    return Err("原音已收齐，请先生成本机回听文件，再进行转写。".into());
                }
                if row.pending_reason.as_deref()==Some("needs_segments") {
                    return Err("原音分段尚未收齐，请先同步来源设备，再进行转写。".into());
                }
            }
        }
        if action == CompanionV1ControlAction::MeetingTranscribeAudio {
            let target=request.session_id.as_deref().or(snapshot.host.selected_session_id.as_deref());
            if let Some(index)=target.and_then(|id|snapshot.host.sessions.iter().position(|s|s.id==id)) {
                if host_audio_unconfirmed(&snapshot.host.sessions[index]) {
                    if !automatic_recovery { return Err(UNCONFIRMED_HOST_AUDIO.into()); }
                    if snapshot.host.sessions[index].recovery.intent == "processMeeting"
                        && !snapshot.device.recording && !snapshot.meeting.active
                        && !snapshot.host.sessions.iter().any(|row| row.status == "recording") {
                        hold_unconfirmed_host_audio(&mut snapshot.host.sessions[index]);
                        persistence::save_snapshot(&mut snapshot)?;
                    }
                    return Ok(snapshot.clone());
                }
            }
        }
        if action == CompanionV1ControlAction::HostRetrySave {
            if snapshot.host.persistence.status == "blocked" {
                let (sessions, storage) = persistence::load_sessions_with_status();
                snapshot.host.persistence = storage;
                if snapshot.host.persistence.status == "blocked" {
                    return Ok(snapshot.clone());
                }
                snapshot.host.sessions = sessions.unwrap_or_default();
                snapshot.host.selected_session_id = snapshot.host.sessions.first().map(|s| s.id.clone());
                snapshot.host.active_session_id = None;
            }
            if snapshot.host.persistence.status != "ready" {
                for session in &mut snapshot.host.sessions {
                    if session.status != "recording" {
                        // A failed checkpoint may have consumed an attempt
                        // before its worker could start. Do not leave a saved
                        // but permanently in-flight recovery after Retry.
                        persistence::reconcile_session_recovery(session);
                    }
                }
            }
            if persistence::save_snapshot(&mut snapshot).is_ok() {
                snapshot.last_control = None;
            }
            refresh_privacy_counts(&mut snapshot);
            return Ok(snapshot.clone());
        }
        // Keep STOP and read-only viewing available even when the disk failed.
        // Network retries and edits resume only after the checkpoint is durable.
        if snapshot.host.persistence.status != "ready"
            && !matches!(action,
                CompanionV1ControlAction::MeetingStop
                | CompanionV1ControlAction::MeetingSelectSession
                | CompanionV1ControlAction::DeviceConnect
                | CompanionV1ControlAction::DeviceDisconnect
                | CompanionV1ControlAction::SpeakerStop)
        {
            return Err("会议库尚未保存或恢复，请先使用提示中的重试按钮；当前内容仍可查看，录音仍可停止".into());
        }
        if action==CompanionV1ControlAction::MeetingRestoreAudio {
            let id=request.session_id.as_deref().or(snapshot.host.selected_session_id.as_deref())
                .ok_or("请先选择要生成回听文件的录音。")?.to_owned();
            let row=snapshot.host.sessions.iter().find(|row|row.id==id).ok_or("这份录音已不存在。")?;
            library_lifecycle::require_available(row)?;
            if row.status=="recording" {return Err("请先结束这份录音，再生成回听文件。".into());}
            if row.source == "hostMeeting" && !row.audio_stored {
                let expected = session_store::privacy_authorization(row)?;
                let path = persistence::state_file_path();
                let _privacy_lock = library_lifecycle::action_lock(&path)?;
                let outcome = meeting_audio_recovery::recover_session_at(&path, &id, &expected);
                let refreshed = reload_segmented_library(&mut snapshot, &path);
                if let Err(error) = outcome {
                    return Err(match refreshed { Ok(()) => error, Err(load) => format!("{error}；会议状态尚未刷新：{load}") });
                }
                refreshed?;
                snapshot.updated_at = observation_timestamp();
                snapshot.last_control = Some(crate::companion_v1::CompanionV1ControlEcho {
                    action, characteristic_uuid: crate::companion_v1::COMPANION_V1_HOST_RECORDING_CHANNEL,
                    payload_hex: String::new(), accepted: true,
                    message: "已找回会议音轨片段；原文件保留，结尾可能缺失。".into(),
                });
                refresh_privacy_counts(&mut snapshot);
                return Ok(snapshot.clone());
            }
            if row.source == "hostMicrophone" && !row.audio_stored {
                let expected = session_store::privacy_authorization(row)?;
                let path = persistence::state_file_path();
                // Serialize against explicit privacy and library lifecycle
                // actions while the raw original and copy are associated.
                let _privacy_lock = library_lifecycle::action_lock(&path)?;
                let outcome = host_interrupted_recovery::recover_session_at(&path, &id, &expected);
                let refreshed = reload_segmented_library(&mut snapshot, &path);
                if let Err(error) = outcome {
                    return Err(match refreshed { Ok(()) => error, Err(load) => format!("{error}；会议状态尚未刷新：{load}") });
                }
                refreshed?;
                snapshot.updated_at = observation_timestamp();
                snapshot.last_control = Some(crate::companion_v1::CompanionV1ControlEcho {
                    action, characteristic_uuid: crate::companion_v1::COMPANION_V1_HOST_RECORDING_CHANNEL,
                    payload_hex: String::new(), accepted: true,
                    message: "已恢复可回听片段；原文件保留，结尾可能缺失。".into(),
                });
                refresh_privacy_counts(&mut snapshot);
                return Ok(snapshot.clone());
            }
            // A completed host capture can contain only a WAV header (for
            // example, Stop before any microphone samples arrive). It has no
            // board segments, so do not report it as a deleted device record.
            if row.source == "hostMicrophone" && row.audio_stored
                && (!row.retention.audio_cached || row.audio_bytes <= 44
                    || row.audio_path.as_deref().is_none_or(|p| p.trim().is_empty())) {
                let empty_header = row.audio_path.as_deref().map(std::path::Path::new)
                    .filter(|path| path.is_absolute())
                    .and_then(|path| {
                        let meta=std::fs::symlink_metadata(path).ok()?;
                        if !meta.is_file() || meta.file_type().is_symlink() || meta.len()!=44 { return None; }
                        let mut file=std::fs::File::open(path).ok()?;
                        let mut header=[0u8;44];
                        std::io::Read::read_exact(&mut file,&mut header).ok()?;
                        Some(file.metadata().ok()?.len()==44 && header==denzic_host_audio_v1_core::wav::wav_header(0))
                    }).unwrap_or(false);
                return Err(if empty_header {
                    "当前本机录音文件只有文件头，没有可恢复的声音；原文件保留，请检查麦克风后重新录音。"
                } else {
                    "本机录音保存信息尚未确认，无法安全恢复；原文件保留，请检查录音文件。"
                }.into());
            }
            let report=recording_wire::receiver::restore_local_session(&id)?;
            let refreshed=reload_segmented_library(&mut snapshot,&persistence::state_file_path());
            if let Some(failure)=report.failures.first() {
                return Err(match refreshed {Ok(())=>failure.error.clone(),Err(error)=>format!("{}；本机状态更新未完成：{error}",failure.error)});
            }
            refreshed?;
            if !report.waiting_for_segments.is_empty() {return Err("本机原音仍有缺段，请连接来源设备补收；未恢复其它录音。".into());}
            if !snapshot.host.sessions.iter().any(|row|row.id==id&&row.audio_stored&&row.retention.audio_cached) {
                return Err("本机回听文件尚未生成，现有原音和恢复记录保留。".into());
            }
            snapshot.updated_at=observation_timestamp();
            snapshot.last_control=Some(crate::companion_v1::CompanionV1ControlEcho {
                action,characteristic_uuid:crate::companion_v1::COMPANION_V1_HOST_RECORDING_CHANNEL,
                payload_hex:String::new(),accepted:true,message:"回听文件已生成，可直接回听。".into(),
            });
            refresh_privacy_counts(&mut snapshot);return Ok(snapshot.clone());
        }
        if action == CompanionV1ControlAction::MeetingResetSession {
            if snapshot.host.sessions.iter().any(|r|r.status=="recording" && r.recorder_control.is_some()) {
                return Err("设备原录音尚未结束或核对，请先核对原录音；未重置或新开会议。".into());
            }
            self.host_recording.discard();
            self.host_recording.set_pcm_sink(None);
            let _ = self.live_asr.stop_and_take_text();
        }
        // Preflight before deleting board/audio data, then retain the same
        // command locks through the sanitized index checkpoint below.
        let mut privacy_retirement=recorder_control::prepare_privacy_retirement(
            &snapshot,&request,&persistence::state_file_path())?;
        let mut original_selected_session_id = snapshot.host.selected_session_id.clone();
        if snapshot.device.recording
            && owned_segmented_recording_sync(&snapshot,&request).is_none()
            && matches!(
                action,
                CompanionV1ControlAction::DeviceSyncRecordings
                    | CompanionV1ControlAction::OobeRunChecks
                    | CompanionV1ControlAction::SpeakerPrompt
                    | CompanionV1ControlAction::SpeakerStop
            )
        {
            return Err(
                "设备正在录音；请先在设备上结束录音，再读取设备状态后继续"
                    .to_string(),
            );
        }
        if action == CompanionV1ControlAction::OobeRunChecks
            && oobe_blocked_by_active_recording(&snapshot, self.live_asr.snapshot().active)
        {
            return Err(
                "正在录音或在线转写，不能运行首次使用检查；请先停止并完成当前会议"
                    .to_string(),
            );
        }
        if action == CompanionV1ControlAction::PrivacyEraseAll
            && oobe_blocked_by_active_recording(&snapshot, self.live_asr.snapshot().active)
        {
            return Err("正在录音或在线转写，不能清除本机资料；请先停止并完成当前会议".to_string());
        }
        if action == CompanionV1ControlAction::PrivacyEraseAll {
            self.host_recording.discard();
            self.host_recording.set_pcm_sink(None);
            let _ = self.live_asr.stop_and_take_text();
        }
        if action == CompanionV1ControlAction::MeetingGenerateMinutes {
            if let Some(template)=request.minutes_template.as_ref() {
                template.normalized()?;
                if automatic_recovery || request.meeting_mode.is_none() {
                    return Err("使用整理模板需要明确选择本次纪要；不会自动重试。".into());
                }
            }
            if request.meeting_mode.as_deref().is_some_and(|mode| !matches!(mode, "offlineStore" | "onlineLive")) {
                return Err("不支持的纪要版本".into());
            }
            let target = if let Some(id) = request.session_id.as_deref() {
                Some(
                    snapshot
                        .host
                        .sessions
                        .iter()
                        .find(|session| session.id == id)
                        .ok_or_else(|| format!("meeting target {id} is missing"))?,
                )
            } else {
                selected_session(&snapshot)
            };
            if let Some(revision) = request.context_note_revision {
                if automatic_recovery || request.meeting_mode.is_none() {
                    return Err("使用补充需要明确选择本次整理版本，不能自动重试提交。".into());
                }
                minutes_context::validate(target.ok_or("找不到要整理的录音。")?, revision)?;
            }
            if target.is_some_and(transcript_review::review_is_stale) {
                return Err("原始转写已更新，请先核对保留的修订或恢复原始转写，再生成纪要。".into());
            }
            if target.is_some_and(|session| !transcript_review::final_transcript_available(session)) {
                return Err("完整转写尚未保存，请先完成转写再生成纪要。".into());
            }
            if target.is_some_and(|session| {
                let mode = request.meeting_mode.as_deref().unwrap_or(&session.meeting_mode);
                let variant = if mode == "onlineLive" {
                    session.minutes_by_mode.online_live.as_ref()
                } else { session.minutes_by_mode.offline_store.as_ref() };
                let manually_edited = variant.is_some_and(|v| matches!(v.source.as_str(), "userEdited" | "userAuthored"))
                    || session.minutes.as_ref().is_some_and(|m| matches!(m.source.as_str(), "userEdited" | "userAuthored"));
                let requested_ready = if request.meeting_mode.is_some() {
                    variant.is_some_and(|v| v.status == "minutesReady" && v.quality == "final"
                        && v.processing.as_ref().is_none_or(|p| p.is_complete())
                        && transcript_review::minutes_current(session, v.source_review_revision))
                } else { session_has_final_minutes_product(session) };
                // A selected-mode request is an explicit regeneration of that
                // product. Background recovery and unscoped Generate remain
                // idempotent so completed work is not billed again implicitly.
                requested_ready && (automatic_recovery
                    || (request.meeting_mode.is_none() && !manually_edited))
            }) {
                return Ok(snapshot.clone());
            }
        }
        if matches!(
            action,
            CompanionV1ControlAction::MeetingExportMarkdown
                | CompanionV1ControlAction::MeetingExportTxt
                | CompanionV1ControlAction::MeetingExportJson
                | CompanionV1ControlAction::MeetingExportSrt
                | CompanionV1ControlAction::MeetingExportActionsTodo
                | CompanionV1ControlAction::MeetingExportActionsIcal
        ) {
            let target = if let Some(id) = request.session_id.as_deref() {
                snapshot
                    .host
                    .sessions
                    .iter()
                    .find(|session| session.id == id)
                    .ok_or_else(|| format!("meeting export target {id} is missing"))?
            } else {
                selected_session(&snapshot)
                    .ok_or_else(|| "meeting export has no selected session".to_string())?
            };
            if request
                .meeting_mode
                .as_deref()
                .is_some_and(|mode| mode != target.meeting_mode)
            {
                return Err("export meeting mode does not match the requested session".to_string());
            }
        }
        if matches!(
            action,
            CompanionV1ControlAction::MeetingTranscribeAudio
                | CompanionV1ControlAction::MeetingGenerateMinutes
        ) {
            let target_index = if let Some(id) = request.session_id.as_deref() {
                Some(
                    snapshot
                        .host
                        .sessions
                        .iter()
                        .position(|session| session.id == id)
                        .ok_or_else(|| format!("meeting recovery target {id} is missing"))?,
                )
            } else {
                selected_session(&snapshot).and_then(|selected| {
                    snapshot
                        .host
                        .sessions
                        .iter()
                        .position(|session| session.id == selected.id)
                })
            };
            let has_active_recording = snapshot.device.recording
                || snapshot.meeting.active
                || snapshot
                    .host
                    .sessions
                    .iter()
                    .any(|candidate| candidate.status == "recording");
            if let Some(index) = target_index {
                let session = &mut snapshot.host.sessions[index];
                if automatic_recovery && (session.recovery.intent != "processMeeting"
                    || session.processing_policy == crate::companion_v1::CompanionV1ProcessingPolicy::Manual) {
                    return Ok(snapshot.clone());
                }
                if automatic_recovery && interrupted_capture::hold(session) {
                    persistence::save_snapshot(&mut snapshot)?;
                    return Ok(snapshot.clone());
                }
                if !automatic_recovery {
                    interrupted_capture::confirm(session)?;
                }
                if session.recovery.intent == "processMeeting" {
                    let already_done = if action
                        == CompanionV1ControlAction::MeetingTranscribeAudio
                    {
                        session.transcript_final && !session.transcript_text.trim().is_empty()
                    } else {
                        false
                    };
                    if automatic_recovery {
                        if has_active_recording || already_done {
                            return Ok(snapshot.clone());
                        }
                        let due = session
                            .recovery
                            .next_retry_at_unix_ms
                            .is_none_or(|due| due <= unix_time_ms());
                        let expected_stage = if action
                            == CompanionV1ControlAction::MeetingTranscribeAudio
                        {
                            session.recovery.stage == "pendingTranscription"
                                || (session.recovery.stage == "retryBackoff"
                                    && session.recovery.retry_stage == "transcription"
                                    && due)
                        } else {
                            session.recovery.stage == "pendingMinutes"
                                || (session.recovery.stage == "retryBackoff"
                                    && session.recovery.retry_stage == "minutes"
                                    && due)
                        };
                        if !expected_stage
                            || session.recovery.requested_meeting_mode != session.meeting_mode
                            || session.recovery.attempt_count
                                >= session.recovery.max_attempts.max(1)
                        {
                            return Ok(snapshot.clone());
                        }
                    }
                    if !already_done {
                        if !automatic_recovery && session.recovery.stage == "paused" {
                            // A user-visible manual Retry explicitly resumes a
                            // paused job with a fresh bounded budget.
                            session.recovery.attempt_count = 0;
                        }
                        session.recovery.retry_stage = if action
                            == CompanionV1ControlAction::MeetingTranscribeAudio
                        {
                            "transcription"
                        } else {
                            "minutes"
                        }
                        .to_string();
                        session.recovery.attempt_count =
                            session.recovery.attempt_count.saturating_add(1);
                        session.recovery.stage = if action
                            == CompanionV1ControlAction::MeetingTranscribeAudio
                        {
                            "transcribing"
                        } else {
                            "generatingMinutes"
                        }
                        .to_string();
                        session.recovery.next_retry_at_unix_ms = None;
                        session.pending_reason = Some("recovery_processing".to_string());
                        // Commit the consumed attempt before any external work.
                        // A service may accept a call before a crash, so this is
                        // local completed-stage deduplication rather than a
                        // claim of remote exactly-once execution.
                        persistence::save_snapshot(&mut snapshot)?;
                    }
                }
            }
        }
        let recorder_target=request.device_id.clone().or_else(||request.session_id.as_deref()
            .and_then(|id|snapshot.host.sessions.iter().find(|s|s.id==id)).and_then(|s|s.source_device_id.clone()))
            .or_else(||snapshot.device.device_id.clone());
        let recorder_applied=match recorder_control::apply(&mut snapshot,&request,&self.ble_bridge) {
            Ok(applied)=>applied,
            Err(error)=>{self.observe_pairing_failure(&mut snapshot,recorder_target.as_deref(),&error);return Err(error);}
        };
        if recorder_applied {
            // A live CMC3 Connect returns here, before ordinary DeviceConnect.
            // Only the successful protected original-session observation may
            // retire a prior manual Disconnect and re-enable its follower.
            let mut preference = self.connection_preference.lock()
                .map_err(|_| "device connection preference lock failed".to_string())?;
            let pairing_confirmed=preference.observe_confirmed_pairing(&snapshot);
            if preference.remember_confirmed_recorder_connect(action, &snapshot, connection_timestamp()) || pairing_confirmed {
                device_connection::save(&preference)?;
                apply_connection_preference(&mut snapshot, &preference);
            }
            refresh_privacy_counts(&mut snapshot);
            return Ok(snapshot.clone());
        }
        let device_meeting_target = board_meeting::device_control_target(&snapshot, &request)?;
        let board_meeting_control = device_meeting_target.is_some();
        if matches!(action, CompanionV1ControlAction::DeviceDisconnect) {
            *self
                .pending_meeting_start
                .lock()
                .map_err(|_| "pending meeting state lock failed".to_string())? = None;
        }
        if matches!(action, CompanionV1ControlAction::MeetingStart) && request.session_id.is_none()
        {
            request.session_id = if snapshot.meeting.active {
                snapshot.host.active_session_id.clone()
            } else if board_meeting_control {
                self.pending_meeting_start
                    .lock()
                    .map_err(|_| "pending meeting state lock failed".to_string())?
                    .as_ref()
                    .map(|pending| pending.session_id.clone())
                    .or_else(|| {
                        Some(format!(
                            "meeting-{}-{}",
                            std::process::id(),
                            std::time::SystemTime::now()
                                .duration_since(std::time::UNIX_EPOCH)
                                .unwrap_or_default()
                                .as_micros()
                        ))
                    })
            } else {
                Some(format!(
                    "meeting-{}-{}",
                    std::process::id(),
                    std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_micros()
                ))
            };
        } else if matches!(
            action,
            CompanionV1ControlAction::MeetingStop | CompanionV1ControlAction::MeetingFinalize
        ) && request.session_id.is_none()
        {
            request.session_id = snapshot
                .host
                .active_session_id
                .clone()
                .or_else(|| snapshot.host.selected_session_id.clone());
        }
        let requested_session_id = request.session_id.clone();
        if board_meeting_control && action == CompanionV1ControlAction::MeetingStop {
            if let Some(session_id) = requested_session_id.as_deref() {
                if board_stop::completed_retry(&mut snapshot, session_id)? {
                    return Ok(snapshot.clone());
                }
            }
        }
        let mut transcription_note: Option<String> = None;
        let mut transcription_error: Option<String> = None;
        let mut track_transcription_warning: Option<String> = None;
        let mut device_note: Option<String> = None;
        let mut privacy_report: Option<PrivacyEraseReport> = None;
        let mut synced_batch = Vec::new();
        let mut segmented_library_updated = false;
        let mut meeting_device_report: Option<CompanionMeetingControlReport> = None;
        let mut meeting_device_observed_at: Option<String> = None;
        let mut meeting_device_recording: Option<CompanionSyncedRecording> = None;
        let mut meeting_sync_paused = false;
        let mut connected_device_identity: Option<CompanionDeviceIdentity> = None;
        let mut reconnected_closed_owner: Option<ble_bridge::OwnedRecorder> = None;
        let mut ble_name_report: Option<ble_bridge::CompanionBleNameReport> = None;
        let mut speaker_device_report: Option<CompanionSpeakerControlReport> = None;
        let mut oobe_probe: Option<Result<ble_bridge::CompanionOobeProbeReport, String>> = None;
        // Timed speaker utterances from the transcription path, threaded to the
        // session after the fixture reducer builds it (enables SRT export +
        // playback sync). None for non-volcengine / failed transcription.
        let mut transcript_utterances: Option<Vec<CompanionV1UtteranceSegment>> = None;
        let mut transcript_unrecognized = None;

        /* STOP keeps the original capture source across disconnections.
         * Fail closed instead of letting the host reducer claim device audio. */
        if board_meeting_control {
            let command = match action {
                CompanionV1ControlAction::MeetingStart => 1,
                CompanionV1ControlAction::MeetingStop => 2,
                CompanionV1ControlAction::MeetingFinalize => 3,
                _ => unreachable!(),
            };
            let requested_device = device_meeting_target.as_ref()
                .and_then(|target| target.device_id.clone());
            let requested_device = requested_device.as_deref();
            let expected_recording_id = device_meeting_target.as_ref()
                .and_then(|target| target.recording_id);
            let requested_max_seconds = if matches!(action, CompanionV1ControlAction::MeetingStart) {
                recording_duration_seconds(request.duration_ms)?
            } else {60};
            let session_key = request
                .session_id
                .as_deref()
                .ok_or_else(|| "V1 meeting control requires a stable session id".to_string())?;
            let max_seconds = if matches!(action, CompanionV1ControlAction::MeetingStart) {
                let mut pending = self
                    .pending_meeting_start
                    .lock()
                    .map_err(|_| "pending meeting state lock failed".to_string())?;
                reserve_pending_meeting_start(
                    &mut pending,
                    session_key,
                    requested_device,
                    requested_max_seconds,
                )?
            } else {
                requested_max_seconds
            };
            let expected_key = snapshot.host.sessions.iter().find(|row| row.id == session_key)
                .and_then(|row| row.device_recording_key.clone());
            let mut stopped_sync = None;
            let report_result = if matches!(action, CompanionV1ControlAction::MeetingStop) {
                let known_ids = verified_device_recording_ids(&snapshot, requested_device);
                self.ble_bridge.stop_and_sync_recordings(requested_device, session_key,
                    expected_recording_id.ok_or("原录音缺少设备录音编号，未发送停止命令。")?, &known_ids, expected_key.as_ref(),
                    |report, observed_at| {
                        board_stop::observe(&mut snapshot, session_key, report, observed_at)?;
                        // A failed pull or native cleanup must not lose the
                        // actual STOP ACK or leave the original marked active.
                        persistence::save_snapshot(&mut snapshot)
                    })
                    .map(|(report, observed_at, operation)| {
                        // The checkpoint preserves the first STOP ACK. A
                        // retry/receive time cannot rewrite capture history.
                        meeting_device_observed_at = snapshot.host.sessions.iter()
                            .find(|session| session.id == session_key)
                            .and_then(|session| session.stopped_at.clone())
                            .or(Some(observed_at));
                        stopped_sync = Some(operation);
                        report
                    })
            } else {
                self.ble_bridge.meeting_control_idempotent(
                    requested_device, command, max_seconds, session_key, expected_recording_id, expected_key.as_ref(),
                )
            };
            // Host observation of the actual ACK, not a fixture date or an
            // estimate of when the board sampled its first microphone frame.
            if meeting_device_observed_at.is_none() {
                meeting_device_observed_at=Some(observation_timestamp());
            }
            let report = match report_result {
                Ok(report) => report,
                Err(error) => {
                    if matches!(action, CompanionV1ControlAction::MeetingStart)
                        && meeting_start_rejection_is_definitive(&error)
                    {
                        *self
                            .pending_meeting_start
                            .lock()
                            .map_err(|_| "pending meeting state lock failed".to_string())? = None;
                    }
                    return Err(error);
                }
            };
            {
                let mut pending = self
                    .pending_meeting_start
                    .lock()
                    .map_err(|_| "pending meeting state lock failed".to_string())?;
                if pending
                    .as_ref()
                    .is_some_and(|item| item.session_id == session_key)
                {
                    *pending = None;
                }
            }
            request.device_id = Some(report.device_id.clone());

            if matches!(action, CompanionV1ControlAction::MeetingStop) {
                let known_recording_ids =
                    verified_device_recording_ids(&snapshot, Some(&report.device_id));
                let mut operation = stopped_sync.unwrap_or_else(|| self
                    .ble_bridge
                    .sync_stopped_recording(Some(&report.device_id), report.meeting_id, &known_recording_ids));
                if let Some(key) = report.logical_key.as_ref() {
                    // The V2 receiver publishes into the original durable row.
                    // V1 physical-ID retries and fixture paths cannot represent it.
                    reload_segmented_library(&mut snapshot,&persistence::state_file_path())?;
                    let row = snapshot.host.sessions.iter().find(|row| row.id == session_key
                        && row.device_recording_key.as_ref() == Some(&key.public_key()))
                        .ok_or("逻辑录音尚未耐久绑定到原会议；未创建替代录音。")?;
                    if !operation.ready && !operation.sync_paused {
                        return Err(format!("设备已停止，原会议和已收原音保留；分段同步失败：{}",operation.message));
                    }
                    request.audio_path = row.audio_stored.then(|| row.audio_path.clone()).flatten();
                    request.audio_bytes = Some(row.audio_bytes);
                    request.duration_ms = Some(row.duration_ms);
                    meeting_sync_paused = operation.sync_paused;
                    segmented_library_updated = true;
                } else {
                for _attempt in 2..=3 {
                    let exact_ready = operation.ready
                        && operation
                            .recordings
                            .iter()
                            .any(|item| item.recording_id == report.meeting_id &&
                                (!ble_bridge::delete_after_sync_enabled() || item.device_reclaimed));
                    if exact_ready || operation.sync_paused {
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(1_500));
                    let retried = self
                        .ble_bridge
                        .sync_stopped_recording(Some(&report.device_id), report.meeting_id, &known_recording_ids);
                    operation = retain_stopped_recording_checkpoint(
                        &operation, retried, &report.device_id, report.meeting_id);
                }
                if !operation.ready {
                    return Err(format!(
                        "V1 STOP finalized recording_id={} but Type pull failed: {}",
                        report.meeting_id, operation.message
                    ));
                }
                meeting_sync_paused = operation.sync_paused;
                synced_batch = operation.recordings.clone();
                // A partial batch may contain a different complete recording.
                // Only legacy helpers without a catalog may use their lone path.
                let legacy_path = if !operation.sync_paused && operation.recordings.is_empty() {
                    operation.recording_path.clone()
                } else { None };
                let recording = operation
                    .recordings
                    .into_iter()
                    .find(|item| item.recording_id == report.meeting_id)
                    .or_else(|| {
                        legacy_path.as_ref().map(|path| CompanionSyncedRecording {
                            recording_id: report.meeting_id,
                            duration_ms: report.duration_ms,
                            total_length: 0,
                            sha256: String::new(),
                            recording_path: path.clone(),
                            device_reclaimed: false, capture_incomplete: false,
                        })
                    });
                if let Some(recording) = recording {
                    if let Some((wav_bytes, duration_ms)) = wav_file_metrics(&recording.recording_path) {
                        request.audio_bytes = Some(wav_bytes);
                        request.duration_ms = Some(duration_ms);
                    } else {
                        request.audio_bytes = Some(recording.total_length as u64);
                        request.duration_ms = Some(recording.duration_ms as u64);
                    }
                    request.audio_path = Some(recording.recording_path.clone());
                    meeting_device_recording = Some(recording);
                } else if meeting_sync_paused {
                    // The microphone really stopped. Preserve that ACK without
                    // importing a fixture file or restarting the paused pull.
                    request.audio_path = None;
                    request.audio_bytes = Some(0);
                    request.duration_ms = Some(u64::from(report.duration_ms));
                } else {
                    return Err(
                        format!(
                            "V1 STOP finalized recording_id={} but sync returned no matching recording",
                            report.meeting_id
                        )
                    );
                }
                }
            }
            meeting_device_report = Some(report);
        }

        match action {
            CompanionV1ControlAction::ApplyBleName => {
                if !snapshot.connected || !snapshot.device.connected {
                    return Err("Connect and verify the Companion before saving its BLE name".to_string());
                }
                let name = request
                    .ble_name
                    .as_deref()
                    .map(str::trim)
                    .filter(|name| !name.is_empty())
                    .unwrap_or(snapshot.ble_name.staged_name.as_str())
                    .to_string();
                if !crate::companion_v1::companion_ble_name_is_valid(&name) {
                    return Err("BLE name must be printable ASCII, 1..29 bytes, without quotes, semicolon, equals or backslash".to_string());
                }
                let requested_device = request
                    .device_id
                    .as_deref()
                    .or(snapshot.device.device_id.as_deref());
                let report = self.ble_bridge.apply_ble_name(requested_device, &name)?;
                request.ble_name = Some(name);
                request.device_id = Some(report.device_id.clone());
                ble_name_report = Some(report);
            }
            CompanionV1ControlAction::ResetBleName => {
                if !snapshot.connected || !snapshot.device.connected {
                    return Err("Connect and verify the Companion before resetting its BLE name".to_string());
                }
                let requested_device = request
                    .device_id
                    .as_deref()
                    .or(snapshot.device.device_id.as_deref());
                let report = self.ble_bridge.reset_ble_name(requested_device)?;
                request.ble_name = Some(report.active_name.clone());
                request.device_id = Some(report.device_id.clone());
                ble_name_report = Some(report);
            }
            CompanionV1ControlAction::OobeRunChecks => {
                let requested_device = request
                    .device_id
                    .as_deref()
                    .or(snapshot.device.device_id.as_deref());
                oobe_probe = Some(self.ble_bridge.oobe_probe(requested_device));
            }
            CompanionV1ControlAction::DeviceScan => {
                let operation = self.ble_bridge.scan();
                if !operation.ready {
                    return Err(operation.message);
                }
                request.device_id = operation.device_id.clone();
                device_note = Some(format!(
                    "{} ({} / {})",
                    operation.message, operation.provider_id, operation.mode
                ));
            }
            CompanionV1ControlAction::DeviceConnect => {
                request.device_id = effective_device_target(
                    request.device_id.as_deref(),
                    snapshot.device.device_id.as_deref(),
                );
                let known_recording_ids =
                    verified_device_recording_ids(&snapshot, request.device_id.as_deref());
                let owned_recording = owned_offline_recording_link(&snapshot, &request);
                let operation = self
                    .ble_bridge
                    .connect_with_owned_recording(request.device_id.as_deref(), &known_recording_ids, owned_recording.as_ref());
                if !operation.ready {
                    let error=observe_failed_device_connect(&mut snapshot,&operation,&persistence::state_file_path());
                    self.observe_pairing_failure(&mut snapshot,request.device_id.as_deref(),&error);
                    return Err(error);
                }
                request.device_id = operation.device_id.clone();
                connected_device_identity = operation.device_identity.clone();
                segmented_library_updated = operation.mode == "windows-native-connect-auto-upload-segmented";
                if operation.mode.starts_with("windows-native-connect-auto-upload")
                    && connected_device_identity.as_ref().is_some_and(|identity| identity.recording == Some(false))
                {
                    // An owned native probe accepts idle only after matching
                    // the original control identity and sealed catalogue.
                    reconnected_closed_owner = owned_recording;
                }
                synced_batch = operation.recordings.clone();
                if matches!(operation.mode.as_str(), "windows-native-connect"
                    | "windows-native-connect-auto-upload" | "windows-native-connect-auto-upload-segmented") {
                    snapshot.source = "firmware";
                    {
                        let mut preference = self
                            .connection_preference
                            .lock()
                            .map_err(|_| "device connection preference lock failed".to_string())?;
                        if preference.remember_connected_probe(&operation.mode, operation.ready,
                            operation.device_id.as_deref(), connection_timestamp()) {
                            device_connection::save(&preference)?;
                            apply_connection_preference(&mut snapshot, &preference);
                        }
                    }
                }
                device_note = Some(format!(
                    "{} ({} / {})",
                    operation.message, operation.provider_id, operation.mode
                ));
            }
            CompanionV1ControlAction::DeviceDisconnect => {
                let mut preference = self
                    .connection_preference
                    .lock()
                    .map_err(|_| "device connection preference lock failed".to_string())?;
                preference.mark_manual_disconnect();
                device_connection::save(&preference)?;
                ble_bridge::disconnect_retained_recording(snapshot.device.device_id.as_deref())?;
                apply_connection_preference(&mut snapshot, &preference);
                device_note = Some(
                    "Manual disconnect saved; automatic reconnect remains suppressed until Connect or re-enable"
                        .to_string(),
                );
            }
            CompanionV1ControlAction::DeviceEnableAutoReconnect
            | CompanionV1ControlAction::DeviceDisableAutoReconnect => {
                let enabled = action == CompanionV1ControlAction::DeviceEnableAutoReconnect;
                let mut preference = self
                    .connection_preference
                    .lock()
                    .map_err(|_| "device connection preference lock failed".to_string())?;
                preference.set_auto_reconnect(enabled);
                device_connection::save(&preference)?;
                apply_connection_preference(&mut snapshot, &preference);
                device_note = Some(if enabled {
                    "Automatic reconnect enabled for the remembered exact device".to_string()
                } else {
                    "Automatic reconnect disabled".to_string()
                });
            }
            CompanionV1ControlAction::DeviceSyncRecordings => {
                let original=owned_segmented_recording_sync(&snapshot,&request);
                if original.is_none() && ble_bridge::requests_closed_segmented(&snapshot,&request) {
                    return Err("无法确认所选原录音的设备与归属，未同步其它录音。".into());
                }
                if original.is_some() && self.live_asr.snapshot().active {
                    return Err("在线转写仍持有当前音频链路，原录音保持采集，请稍后同步。".into());
                }
                request.device_id = effective_device_target(
                    request.device_id.as_deref(),
                    snapshot.device.device_id.as_deref(),
                );
                if let Some(original)=original.as_ref() {request.device_id=Some(original.device_id().into());}
                let known_recording_ids =
                    verified_device_recording_ids(&snapshot, request.device_id.as_deref());
                let operation = match original.as_ref() {
                    Some(original)=>self.ble_bridge.sync_original_recording(original),
                    None=>self.ble_bridge.sync_recordings(request.device_id.as_deref(), &known_recording_ids),
                };
                if !operation.ready {
                    return Err(operation.message);
                }
                if operation.mode == "windows-native-segmented-recording-pull" {
                    // V2 publishes complete OR still-growing sessions itself.
                    // The V1 reducer would create a physical-ID meeting and
                    // falsely clear active capture, so this path has no reducer.
                    observe_segmented_library(&mut snapshot, &operation,
                        &persistence::state_file_path(), CompanionV1ControlAction::DeviceSyncRecordings)?;
                    if let Some(original)=original.as_ref() {
                        if let Some(row)=snapshot.host.sessions.iter().find(|row|row.id==original.session_id()
                            && row.audio_stored && row.status!="recording") {
                            // LAST plus verified original segments/WAV proves
                            // this capture closed; preserve its actual command,
                            // and never manufacture a STOP acknowledgement.
                            recording_wire::receiver::Receiver::verify_saved_row(row)?;
                            let duration=row.duration_ms;
                            if snapshot.host.active_session_id.as_deref()==Some(original.session_id()) {
                                snapshot.host.active_session_id=None;snapshot.meeting.active=false;
                                snapshot.meeting.status="captured".into();snapshot.meeting.duration_ms=duration;
                            }
                        }
                    }
                    persistence::save_snapshot(&mut snapshot)?;
                    return Ok(snapshot.clone());
                }
                if operation.sync_paused && operation.recordings.is_empty() {
                    observe_empty_sync_pause(&mut snapshot, &operation);
                    let _ = persistence::save_snapshot(&mut snapshot);
                    return Ok(snapshot.clone());
                }
                // Empty device list is a successful BLE call but not a product sync.
                if operation.recording_path.is_none() && request.audio_path.is_none() {
                    return Err(if operation.message.contains("no stored recordings") {
                        "板子上没有录音。请先在设备上录一段短音频，再点「同步短录」。".to_string()
                    } else {
                        format!(
                            "同步未得到录音文件：{}。请确认板子已录完并仍有 list 条目。",
                            operation.message
                        )
                    });
                }
                request.device_id = operation.device_id.clone();
                if operation.mode.starts_with("windows-native-")
                    && operation.mode != "windows-native-env"
                {
                    snapshot.source = "firmware";
                }
                synced_batch = operation.recordings.clone();
                if !operation.recordings.is_empty() {
                    request.session_id = operation.recordings.last().map(|item|
                        received_recording_target(&snapshot.host.sessions, operation.device_id.as_deref(), item));
                    request.audio_path = operation
                        .recordings
                        .last()
                        .map(|item| item.recording_path.clone());
                } else {
                    if request.audio_path.is_none() {
                        request.audio_path = operation.recording_path.clone();
                    }
                    if request.duration_ms.is_none() || request.audio_bytes.is_none() {
                        if let Some(path) = request.audio_path.as_deref() {
                            if let Some((wav_bytes, duration_ms)) = wav_file_metrics(path) {
                                request.audio_bytes.get_or_insert(wav_bytes);
                                request.duration_ms.get_or_insert(duration_ms);
                            }
                        }
                    }
                }
                device_note = Some(format!(
                    "{} ({} / {})",
                    operation.message, operation.provider_id, operation.mode
                ));
            }
            CompanionV1ControlAction::PrivacyEraseAudio => {
                privacy_report = Some(self.privacy.erase_selected_audio(&snapshot));
            }
            CompanionV1ControlAction::PrivacyEraseTranscript => {
                privacy_report = Some(self.privacy.erase_selected_transcript(&snapshot));
            }
            CompanionV1ControlAction::PrivacyDeleteSession => {
                let requested_session_id = request
                    .session_id
                    .as_deref()
                    .map(str::trim)
                    .filter(|id| !id.is_empty())
                    .ok_or_else(|| "delete session requires an explicit sessionId".to_string())?;
                if snapshot.host.selected_session_id.as_deref() != Some(requested_session_id) {
                    return Err(format!(
                        "delete target {requested_session_id} is no longer the selected session"
                    ));
                }
                let session = snapshot
                    .host
                    .sessions
                    .iter()
                    .find(|session| session.id == requested_session_id)
                    .ok_or_else(|| format!("delete target {requested_session_id} is missing"))?;
                let board_extent = (
                    session.device_recording_id,
                    session.device_total_length,
                    session.device_sha256.clone(),
                    session.source_device_id.clone(),
                    session.device_reclaimed,
                );
                if request.prompt_id.as_deref()==Some(library_lifecycle::LOCAL_TRASH_PERMANENT){
                    if session.organization.trashed_at.is_none(){return Err("仅可永久清除已在本机回收站的录音。".into());}
                    device_note=Some("Only the explicitly selected local recycled recording was erased; device data was not accessed".into());
                }else{match board_extent {
                    (Some(recording_id), Some(total_length), Some(sha256), Some(source_device_id), false) => {
                        let requested_device_id = request
                            .device_id
                            .as_deref()
                            .or(snapshot.device.device_id.as_deref())
                            .ok_or_else(|| {
                                "source device is not selected; board recording was not deleted"
                                    .to_string()
                            })?;
                        if !device_connection::same_device_id(&source_device_id, requested_device_id) {
                            return Err(format!(
                                "session belongs to device {source_device_id}, not {requested_device_id}; board recording was not deleted"
                            ));
                        }
                        let operation = self.ble_bridge.delete_recording_exact(
                            Some(&source_device_id),
                            recording_id,
                            total_length,
                            &sha256,
                        );
                        if !operation.ready {
                            return Err(operation.message);
                        }
                        // The exact board deletion has already succeeded. Keep
                        // that fact across a local-file deletion failure so a
                        // retry does not require the reclaimed extent again.
                        if let Some(current) = snapshot.host.sessions.iter_mut()
                            .find(|current| current.id == requested_session_id) {
                            current.device_reclaimed = true;
                        }
                        persistence::save_snapshot(&mut snapshot)?;
                        device_note = Some(operation.message);
                    }
                    (Some(_), Some(_), Some(_), _, true) => {
                        device_note = Some(
                            "Local session deleted; its exact board extent was already reclaimed"
                                .to_string(),
                        );
                    }
                    (Some(_), Some(_), Some(_), None, false) => {
                        device_note = Some(
                            "Local session deleted; legacy row has no source-device identity, so the board recording was left untouched"
                                .to_string(),
                        );
                    }
                    _ => {
                        device_note = Some(
                            "Local-only session deleted; no board extent was associated"
                                .to_string(),
                        );
                    }
                }
                }
                privacy_report = Some(self.privacy.erase_selected_audio(&snapshot));
            }
            CompanionV1ControlAction::PrivacyEraseAll => {
                privacy_report = Some(self.privacy.erase_all_audio(&snapshot));
                device_note = Some(
                    "Only Type local data was cleared; use the device's local menu to clear recordings stored on the device"
                        .to_string(),
                );
            }
            CompanionV1ControlAction::SpeakerPrompt => {
                if !snapshot.connected || !snapshot.speaker.supported {
                    return Err("Connected device has not reported a populated speaker".to_string());
                }
                let prompt_id = speaker_prompt_id(request.prompt_id.as_deref())?;
                let requested_device = request
                    .device_id
                    .as_deref()
                    .or(snapshot.device.device_id.as_deref());
                let report = self.ble_bridge.speaker_prompt(
                    requested_device,
                    snapshot.speaker.volume.min(100),
                    prompt_id,
                )?;
                request.device_id = Some(report.device_id.clone());
                speaker_device_report = Some(report);
            }
            CompanionV1ControlAction::SpeakerStop => {
                return Err(
                    "Connected WBA speaker exposes bounded product cues; remote stop is not supported by the firmware contract"
                        .to_string(),
                );
            }
            _ => {}
        }

        let meeting_start_supplied_audio = action == CompanionV1ControlAction::MeetingStart
            && request
                .audio_path
                .as_ref()
                .map(|p| !p.trim().is_empty())
                .unwrap_or(false);

        let request = if action == CompanionV1ControlAction::MeetingTranscribeAudio {
            let session = request
                .session_id
                .as_deref()
                .and_then(|id| snapshot.host.sessions.iter().find(|session| session.id == id))
                .or_else(|| selected_session(&snapshot));
            let audio_path = request
                .audio_path
                .clone()
                .or_else(|| session.and_then(|session| session.audio_path.clone()));
            let chunk_paths = session.map(transcription_chunk_paths).transpose()?.unwrap_or_default();
            let meeting_tracks = session.and_then(|session| session.meeting_tracks.clone());
            let track_review_confirmed = session.is_some_and(|session| session.recovery.capture_review_confirmed);
            let expected_track_audio = session.map(|session| (session.audio_bytes, session.duration_ms));
            if session.is_some_and(|session| {
                session.transcript_final && !session.transcript_text.trim().is_empty()
            }) {
                transcription_note = Some("existing durable transcript reused; ASR not repeated".to_string());
                let mut request = request;
                request.transcript_text = session.map(|session| session.transcript_text.clone());
                request
            } else {
                let owner=session.map(|s|s.id.clone()).unwrap_or_default();
                let job_id=request.prompt_id.as_deref().filter(|id|id.starts_with("__meeting_job__") || id.starts_with("__transcription_job__"))
                    .map(str::to_owned).unwrap_or_else(||uuid::Uuid::new_v4().to_string());
                let (fresh,result)=self.run_meeting_work(snapshot,&request,|| {
                    let work = || {
                    if let Some(tracks) = meeting_tracks {
                        if tracks.state != "captured" && !(tracks.state == "needsReview" && track_review_confirmed) {
                            return Err("会议音轨尚未确认，请先恢复原音。".to_string());
                        }
                        let (bytes, duration) = expected_track_audio.ok_or("会议音轨记录不存在。")?;
                        meeting_audio_recovery::verify_tracks(&tracks, bytes, duration)?;
                        let mic = tracks.microphone.into_iter().map(|part| part.path).collect::<Vec<_>>();
                        let system = tracks.system.into_iter().map(|part| part.path).collect::<Vec<_>>();
                        meeting_audio_transcription::transcribe_tracks(&self.transcription, &owner, &mic, &system)
                            .map(|result| (result.transcript, result.warnings))
                    } else {
                        self.transcription.transcribe_session_owned(&owner,audio_path.as_deref(),&chunk_paths)
                            .map(|transcript| (transcript, vec![]))
                    }

                    };
                    if automatic_recovery { work() } else { meeting_processing_job::run(&owner,&job_id,meeting_processing_job::Kind::Transcription,work) }
                })?;
                snapshot=fresh;
                original_selected_session_id=snapshot.host.selected_session_id.clone();
                if result.as_ref().err().is_some_and(|error| error==meeting_processing_job::TRANSCRIPTION_CANCELLED) {
                    pause_cancelled_meeting_work(&mut snapshot,&owner,"transcribing",meeting_processing_job::TRANSCRIPTION_CANCELLED)?;
                    return Err(meeting_processing_job::TRANSCRIPTION_CANCELLED.into());
                }
                match result {
                Ok((transcript, warnings)) => {
                    if !warnings.is_empty() { track_transcription_warning = Some(warnings.join(" ")); }
                    transcription_note = Some(format!(
                        "{} ({}){}",
                        transcript.provider_id,
                        transcript.mode,
                        transcript
                            .evidence_path
                            .as_ref()
                            .map(|path| format!(" -> {}", path.to_string_lossy()))
                            .unwrap_or_default()
                    ));
                    let mut request = request;
                    request.transcript_text = Some(transcript.text);
                    transcript_utterances = Some(transcript.utterances);
                    transcript_unrecognized = Some(transcript.unrecognized);
                    if request.audio_path.is_none() {
                        request.audio_path = audio_path;
                    }
                    request
                }
                Err(err) => {
                    transcription_error = Some(err.clone());
                    transcription_note = Some(format!(
                        "ASR unavailable ({err}); session marked needs_transcription"
                    ));
                    let mut request = request;
                    request.transcript_text = None;
                    if request.audio_path.is_none() {
                        request.audio_path = audio_path;
                    }
                    request
                }
                }
            }
        } else {
            request
        };
        if let Some(identity) = connected_device_identity.as_ref() {
            apply_device_identity(&mut snapshot, identity);
        }
        if let Some(owner) = reconnected_closed_owner.as_ref() {
            owner.observe_closed(&mut snapshot)?;
        }
        if let Some(report) = privacy_report.as_ref().filter(|report| report.failed_files != 0) {
            return Err(format!(
                "本机资料尚未完全删除（{} 项失败）。会议记录和原音位置已保留，请解除文件占用后重试；已删除的文件不会恢复。",
                report.failed_files
            ));
        }
        let expected_host_library = if action == CompanionV1ControlAction::MeetingStart
            && !meeting_start_supplied_audio && meeting_device_report.is_none() {
            Some(snapshot.host.sessions.iter().map(session_store::privacy_authorization)
                .collect::<Result<std::collections::BTreeSet<_>, _>>()?)
        } else { None };
        let mut next = apply_control_at(snapshot.clone(), request.clone(), &observation_timestamp())?;
        if action == CompanionV1ControlAction::MeetingStart && meeting_device_report.is_none()
            && request.audio_path.as_deref().is_some_and(|path| path.starts_with("board://"))
        {
            // Creating the pending online session has not acknowledged START.
            // Bind the actual observation when its recording is identified.
            if let Some(session) = selected_session_mut(&mut next) {
                session.started_at = None;
                for chunk in &mut session.chunks { chunk.started_at = None; }
            }
            next.meeting.started_at = None;
        }

        if let Some(probe) = oobe_probe.as_ref() {
            next.oobe.complete = true;
            next.oobe.last_run_at = Some(next.updated_at.clone());
            match probe {
                Ok(report) => {
                    next.source = "firmware";
                    next.oobe.checks = oobe_checks_from_probe(report);
                    // The OOBE probe is deliberately transactional: it
                    // connects, reads/verifies, then disconnects. Reflect the
                    // actual post-probe transport state instead of leaving a
                    // stale "connected" badge in the UI.
                    next.connected = false;
                    next.device.connected = false;
                    next.device.device_id = Some(report.device_id.clone());
                    next.device.recordings_available = report.recordings_available as u32;
                    next.device.message = format!(
                        "首次使用检查完成并已断开：services={} characteristics={} recordings={}",
                        report.service_count,
                        report.characteristic_count,
                        report.recordings_available
                    );
                    apply_device_identity(&mut next, &report.identity);
                    if let Some(echo) = next.last_control.as_mut() {
                        let failures = next
                            .oobe
                            .checks
                            .iter()
                            .filter(|check| check.status == "fail")
                            .count();
                        echo.accepted = failures == 0;
                        echo.message = format!(
                            "physical first-use check completed with {failures} failure(s); recording and remote services were not invoked"
                        );
                    }
                }
                Err(error) => {
                    next.oobe.checks = failed_oobe_checks(error);
                    next.connected = false;
                    next.device.connected = false;
                    next.device.message = format!("首次使用检查失败：{error}");
                    if let Some(echo) = next.last_control.as_mut() {
                        echo.accepted = false;
                        echo.message = format!(
                            "physical first-use check failed without recording or remote calls: {error}"
                        );
                    }
                }
            }
        }

        if let Some(report) = ble_name_report.as_ref() {
            next.source = "firmware";
            next.device.device_id = Some(report.device_id.clone());
            next.connected = true;
            next.device.connected = true;
            next.device.connection_phase = "ready".to_string();
            next.ble_name.active_name = report.active_name.clone();
            next.ble_name.staged_name = report.active_name.clone();
            next.ble_name.status = "applied".to_string();
            next.ble_name.pending_restart = false;
            if let Some(echo) = next.last_control.as_mut() {
                echo.accepted = true;
                echo.message = format!(
                    "Device BLE name saved and read back as {:?}; transaction disconnected cleanly",
                    report.active_name
                );
            }
        }

        // One BLE drain can contain multiple durable journal entries. The
        // reducer historically accepted one audioPath, so merge every verified
        // result here with a stable device-recording-{id} key. Reconnects are
        // idempotent and never collapse the library to the last item.
        if action == CompanionV1ControlAction::DeviceSyncRecordings && !synced_batch.is_empty() {
            // The V1 fixture reducer creates a fresh session. Real sync must
            // preserve the original meeting, edits and requested mode.
            next.host.sessions = snapshot.host.sessions.clone();
            // The operation reports the device that actually supplied these
            // bytes. The reducer's previously selected device may differ.
            next.device.device_id = request.device_id.clone();
        }
        let stopped_selection = if action == CompanionV1ControlAction::MeetingStop {
            next.host.selected_session_id.clone()
        } else { None };
        merge_synced_recordings(&mut next, &synced_batch);
        if segmented_library_updated {
            reload_segmented_library(&mut next, &persistence::state_file_path())?;
            if action==CompanionV1ControlAction::DeviceConnect {
                if let Some(device)=request.device_id.as_deref() {recorder_control::restore_connected_local(&mut next,device)?;}
            }
            if let Some(owner) = reconnected_closed_owner.as_ref() {
                owner.retain_closed_after_reload(&mut next, &snapshot)?;
            }
        }
        if stopped_selection.is_some() { next.host.selected_session_id = stopped_selection; }

        if let Some(report) = meeting_device_report.as_ref() {
            next.source = "firmware";
            next.device.device_id = Some(report.device_id.clone());
            next.device.connected = true;
            next.connected = true;
            next.meeting.active = report.state == 1;
            next.meeting.duration_ms = report.duration_ms as u64;
            next.meeting.status = if report.state == 1 {
                "recording".to_string()
            } else {
                "captured".to_string()
            };
            if let Some(session) = selected_session_mut(&mut next) {
                session.source = "boardDevice".to_string();
                session.source_device_id = Some(report.device_id.clone());
                if action == CompanionV1ControlAction::MeetingStart {
                    let prior=snapshot.host.sessions.iter().find(|s|s.id==session.id);
                    board_meeting::observe_start(session,prior,meeting_device_observed_at.as_deref().ok_or("尚未取得设备开始确认时间。")?);
                }
                if let Some(key) = report.logical_key.as_ref() {
                    if session.device_recording_key.as_ref().is_some_and(|old| old != &key.public_key()) {
                        return Err("当前会议逻辑身份改变，未覆盖原会议。".into());
                    }
                    session.device_recording_key = Some(key.public_key());
                }
                if report.meeting_id != 0 {
                    /* START already carries the authoritative flash recording
                     * id.  Surface it immediately so the UI and board never
                     * spend the active interval in two different identities. */
                    session.device_recording_id = Some(report.meeting_id);
                    if report.state == 1 || report.logical_key.is_none() || !session.audio_stored {
                        session.duration_ms = report.duration_ms as u64;
                    }
                }
                if let Some(recording) = meeting_device_recording.as_ref() {
                    board_meeting::attach_recording(session,recording,meeting_device_observed_at.as_deref().ok_or("尚未取得设备停止确认时间。")?)?;
                    arm_meeting_recovery(session);
                } else if meeting_sync_paused && report.logical_key.is_none() {
                    board_meeting::pending_sync(session, report.meeting_id, report.duration_ms,
                        meeting_device_observed_at.as_deref().ok_or("尚未取得设备停止确认时间。")?)?;
                }
            }
            if let Some(session)=selected_session(&next) {
                let started=session.started_at.clone();let duration=session.duration_ms;
                next.meeting.started_at=started;
                if meeting_device_recording.is_some() {next.meeting.duration_ms=duration;}
            }
            if let Some(echo) = next.last_control.as_mut() {
                echo.accepted = report.last_error == 0;
                echo.message = format!(
                    "Companion V1 meeting real state={} request={} recording={} duration_ms={} sync={}",
                    report.state,
                    report.request_id,
                    report.meeting_id,
                    report.duration_ms,
                    report.sync_state
                );
                if meeting_sync_paused {
                    echo.message.push_str(&format!("；设备已停止录音。{}", recording_sync::PAUSED));
                }
            }
        }

        if let Some(report) = speaker_device_report.as_ref() {
            next.device.device_id = Some(report.device_id.clone());
            next.speaker.supported = true;
            next.speaker.online = matches!(report.state, 2..=4);
            next.speaker.volume = report.volume_percent;
            next.speaker.muted = report.volume_percent == 0;
            next.speaker.status = if report.state == 4 {
                "idle".to_string()
            } else {
                "prompting".to_string()
            };
        }

        // Attach the timed speaker utterances from the transcription path to
        // the selected session (the fixture reducer does not know about them).
        if let Some(utterances) = transcript_utterances.take() {
            if let Some(session) = selected_session_mut(&mut next) {
                session.utterances = utterances;
            }
        }
        if let Some(ranges) = transcript_unrecognized.take() {
            if let Some(session) = selected_session_mut(&mut next) {
                session.transcript_unrecognized = ranges;
            }
        }

        let cleanup_summary = privacy_report.as_ref().and_then(|report|
            privacy::cleanup_summary(action, report, next.updated_at.clone()));
        match action {
            CompanionV1ControlAction::DeviceScan
            | CompanionV1ControlAction::DeviceConnect
            | CompanionV1ControlAction::DeviceDisconnect
            | CompanionV1ControlAction::DeviceSyncRecordings
            | CompanionV1ControlAction::DeviceEnableAutoReconnect
            | CompanionV1ControlAction::DeviceDisableAutoReconnect => {
                if let Some(echo) = next.last_control.as_mut() {
                    echo.message = device_note
                        .unwrap_or_else(|| "Companion device boundary completed".to_string());
                }
            }
            CompanionV1ControlAction::PrivacyEraseAll => {
                if let Some(echo) = next.last_control.as_mut() {
                    let report = privacy_report.unwrap_or_default();
                    echo.message = match device_note.clone() {
                        Some(note) => format!(
                            "privacy erase completed: {} deleted, {} skipped, {} unverified legacy cache files preserved; {note}",
                            report.deleted_files, report.skipped_files, report.unverified_cache_files
                        ),
                        None => format!(
                            "privacy erase completed: {} deleted, {} skipped, {} unverified legacy cache files preserved",
                            report.deleted_files, report.skipped_files, report.unverified_cache_files
                        ),
                    };
                }
            }
            CompanionV1ControlAction::PrivacyEraseAudio => {
                if let Some(echo) = next.last_control.as_mut() {
                    let report = privacy_report.unwrap_or_default();
                    echo.message = format!(
                        "privacy erase completed locally: {} deleted, {} skipped, {} retained for other meetings, {} unverified legacy cache files preserved; the on-device recording was not changed (delete this exact session explicitly, or use the device's local menu)",
                        report.deleted_files, report.skipped_files, report.shared_files, report.unverified_cache_files
                    );
                }
            }
            CompanionV1ControlAction::PrivacyDeleteSession => {
                if let Some(echo) = next.last_control.as_mut() {
                    let report = privacy_report.unwrap_or_default();
                    echo.message = format!(
                        "selected recording deleted: {} local files, {} skipped, {} retained for other meetings, {} unverified legacy cache files preserved; {}",
                        report.deleted_files,
                        report.skipped_files,
                        report.shared_files,
                        report.unverified_cache_files,
                        device_note.unwrap_or_else(|| "no board extent".to_string())
                    );
                }
            }
            CompanionV1ControlAction::PrivacyEraseTranscript => {
                if let Some(echo) = next.last_control.as_mut() {
                    let report = privacy_report.unwrap_or_default();
                    echo.message = format!("transcript and minutes cleared: {} cache files deleted, {} retained for other meetings; {} unverified legacy cache files preserved", report.deleted_files, report.shared_files, report.unverified_cache_files);
                }
            }
            CompanionV1ControlAction::MeetingStart => {
                // Fixture always fills a placeholder audio_path; only skip the
                // real host mic when the control request explicitly supplied a path
                // (device sync / pre-seeded WAV tests).
                if let Some(session) = selected_session_mut(&mut next) {
                    if !meeting_start_supplied_audio && meeting_device_report.is_none() {
                        // A concurrent privacy action must be resolved before
                        // starting either the live provider or local capture.
                        let state_path = persistence::state_file_path();
                        let _privacy_lock = if cfg!(test) && std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none() {
                            None
                        } else { Some(library_lifecycle::action_lock(&state_path)?) };
                        let online = session.meeting_mode == "onlineLive";
                        let mut live_mode = "idle".to_string();
                        if online {
                            match self.live_asr.try_start_for_online_live() {
                                Ok(true) => {
                                    let hub = Arc::clone(&self.live_asr);
                                    self.host_recording.set_pcm_sink(Some(Arc::new(move |pcm| {
                                        hub.push_pcm_i16(pcm);
                                    })));
                                    live_mode = self.live_asr.snapshot().mode;
                                }
                                Ok(false) => {
                                    self.host_recording.set_pcm_sink(None);
                                    live_mode = self.live_asr.snapshot().mode;
                                }
                                Err(err) => {
                                    self.host_recording.set_pcm_sink(None);
                                    live_mode = format!("error:{err}");
                                }
                            }
                        } else {
                            let _ = self.live_asr.stop_and_take_text();
                            self.host_recording.set_pcm_sink(None);
                        }

                        let session_id = session.id.clone();
                        let title = session.title.clone();
                        let host_meeting = request.recording_source.as_deref() == Some("hostMeeting");
                        let mut prepared_auth = None;
                        let checkpoint = |path: &std::path::Path| {
                            session.source = if host_meeting { "hostMeeting" } else { "hostMicrophone" }.into();
                            session.audio_path = if host_meeting { None } else { Some(path.to_string_lossy().into_owned()) };
                            session.audio_stored = false;
                            session.audio_bytes = 0;
                            session.retention.audio_cached = false;
                            session.meeting_tracks = host_meeting.then(|| crate::companion_v1::CompanionV1MeetingTracks {
                                root: path.to_string_lossy().into_owned(), state: "recording".into(), microphone: vec![], system: vec![], discontinuity: false, issue: None,
                            });
                            session.chunks = if host_meeting { vec![] } else { vec![audio_chunk(format!("{}-host-open", session.id),
                                session.audio_path.clone(), session.started_at.clone(), None, 0, 0, "open")] };
                            if cfg!(test) && std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none() { return Ok(()); }
                            prepared_auth = Some(session_store::privacy_authorization(session)?);
                            session_store::update_checked(&state_path, |rows| {
                                // Compare the same migration view used at startup;
                                // older minutes may be projected into mode variants.
                                let encoded = serde_json::to_vec(rows).map_err(|_| "会议库无法核对。")?;
                                let normalized = persistence::migrate_sessions(encoded).ok_or("会议库无法核对。")?;
                                let actual = normalized.iter().map(session_store::privacy_authorization)
                                    .collect::<Result<std::collections::BTreeSet<_>, _>>()?;
                                if expected_host_library.as_ref() != Some(&actual) {
                                    return Err("会议库已在其他操作中变化，请刷新后重新开始；原资料保留。".into());
                                }
                                if rows.iter().any(|row| row.id == session.id) {
                                    return Err("会议编号已存在，请刷新后重新开始录音；原记录保留。".into());
                                }
                                rows.insert(0, session.clone());
                                Ok(())
                            })
                        };
                        #[cfg(windows)]
                        let attempt = if host_meeting {
                            self.host_recording.start_meeting_checkpointed(&session_id, &title, checkpoint)
                        } else { self.host_recording.start_checkpointed(&session_id, &title, checkpoint) };
                        #[cfg(not(windows))]
                        let attempt = self.host_recording.start_checkpointed(&session_id, &title, checkpoint);
                        let start = match attempt {
                            Ok(start) => start,
                            Err(error) => {
                                self.host_recording.set_pcm_sink(None);
                                let _ = self.live_asr.stop_and_take_text();
                                if let Some(expected) = prepared_auth {
                                    let loaded = session_store::load(&state_path);
                                    if loaded.state.status != "ready" {
                                        return Err(format!("{error}；会议状态尚未确认保存，请重试恢复。"));
                                    }
                                    let owned = loaded.bytes.as_ref()
                                        .and_then(|bytes| serde_json::from_slice::<Vec<crate::companion_v1::CompanionV1HostSession>>(bytes).ok())
                                        .is_some_and(|rows| rows.iter().any(|row|
                                            session_store::privacy_authorization(row).ok().as_ref() == Some(&expected)));
                                    // A rejected checkpoint may have failed before any commit,
                                    // or the same ID may belong to somebody else's session.
                                    // Neither case authorizes us to change that row.
                                    if !owned { return Err(error); }
                                    let settled = session_store::update_checked(&state_path, |rows| {
                                        let row = rows.iter_mut().find(|row| row.id == session_id)
                                            .ok_or("启动失败后的会议记录不存在。")?;
                                        if session_store::privacy_authorization(row)? != expected {
                                            return Err("会议记录已变化，未覆盖其他资料。".into());
                                        }
                                        row.status = "captured".into();
                                        row.capture_incomplete = true;
                                        row.pending_reason = Some("capture_start_failed".into());
                                        Ok(())
                                    });
                                    if settled.is_ok() {
                                        session.status = "captured".into();
                                        session.capture_incomplete = true;
                                        session.pending_reason = Some("capture_start_failed".into());
                                        next.host.active_session_id = None;
                                        next.meeting.active = false;
                                        next.meeting.status = "captured".into();
                                        *snapshot = next.clone();
                                    } else {
                                        return Err(format!("{error}；会议状态尚未确认保存，请重试恢复。"));
                                    }
                                }
                                return Err(error);
                            }
                        };
                        if !host_meeting {
                            session.audio_path = Some(start.path.to_string_lossy().to_string());
                            session.retention.audio_cached = true;
                            session.chunks = vec![audio_chunk(
                            format!("{}-host-open", session.id),
                            Some(start.path.to_string_lossy().to_string()),
                            session.started_at.clone(),
                            None,
                            0,
                            0,
                            "open",
                            )];
                            session.source = "hostMicrophone".to_string();
                        }
                        // Isolated experiment: production WAV writer, synthetic input,
                        // abrupt process exit before the ordinary snapshot save.
                        #[cfg(test)]
                        if !host_meeting && std::env::var_os("COMPANION_TEST_HOST_START_EXIT").is_some() {
                            let path = std::path::Path::new(session.audio_path.as_deref().unwrap());
                            let mut writer = denzic_host_audio_v1_core::wav::WavWriter::create(path).unwrap();
                            writer.append_bytes(&vec![42u8; 32000]).unwrap();
                            std::process::exit(0);
                        }
                        if let Some(echo) = next.last_control.as_mut() {
                            echo.message = format!(
                                "host recording started {} ({}) -> {}; liveAsr={}",
                                start.session_id,
                                start.mode,
                                start.path.to_string_lossy(),
                                live_mode
                            );
                        }
                    } else if meeting_device_report.is_none() {
                        if let Some(echo) = next.last_control.as_mut() {
                            echo.message =
                                "session uses supplied audioPath; host microphone was not started"
                                    .to_string();
                        }
                    }
                }
            }
            CompanionV1ControlAction::MeetingTranscribeAudio => {
                let target = requested_or_selected_session_mut(
                    &mut next,
                    requested_session_id.as_deref(),
                );
                if let Some(session) = target {
                    if let Some(error) = transcription_error.as_deref() {
                        schedule_recovery_failure(session, error);
                    } else if session.transcript_final
                        && !session.transcript_text.trim().is_empty()
                    {
                        mark_recovery_transcribed(session);
                    }
                }
                if let Some(echo) = next.last_control.as_mut() {
                    echo.message = track_transcription_warning.unwrap_or_else(|| format!(
                        "transcribed by Companion-Type provider {}", transcription_note.unwrap_or_else(|| "unknown".to_string())));
                }
            }
            CompanionV1ControlAction::MeetingImportTranscript => {
                let target = requested_or_selected_session_mut(
                    &mut next,
                    requested_session_id.as_deref(),
                );
                if let Some(session) = target {
                    if session.recovery.intent == "processMeeting"
                        && session.transcript_final
                        && !session.transcript_text.trim().is_empty()
                    {
                        mark_recovery_transcribed(session);
                    }
                }
            }
            CompanionV1ControlAction::MeetingGenerateMinutes => {
                let generated_at = next.updated_at.clone();
                // The fixture reducer creates a selected-mode L0 placeholder.
                // Plan recovery from the durable pre-reducer products so that
                // placeholder cannot erase a failed mode or a completed edit.
                let input = requested_session_id.as_deref()
                    .and_then(|id| snapshot.host.sessions.iter().find(|session| session.id == id))
                    .or_else(|| selected_session(&snapshot)).cloned();
                if let Some(mut session) = input.filter(|session| !session.transcript_text.trim().is_empty()) {
                    let template=request.minutes_template.as_ref().map(|t|t.normalized()).transpose()?;
                    let owner=session.id.clone();
                    let job_id=request.prompt_id.as_deref().filter(|id|id.starts_with("__meeting_job__"))
                        .map(str::to_owned).unwrap_or_else(||uuid::Uuid::new_v4().to_string());
                    let (fresh,result)=self.run_meeting_work(snapshot,&request,|| {
                        let mut work=|| Ok(refresh_minutes_products_for_mode(&mut session,&generated_at,request.meeting_mode.as_deref(),
                            |input| if let Some(template)=template.as_ref() {
                                self.minutes.generate_with_template(input,&generated_at,template,request.context_note_revision.is_some())
                            } else if request.context_note_revision.is_some() {
                                self.minutes.generate_with_context(input,&generated_at)
                            } else { self.minutes.generate(input,&generated_at) }));
                        if automatic_recovery { work() } else { meeting_processing_job::run(&owner,&job_id,meeting_processing_job::Kind::Minutes,work) }
                    })?;
                    snapshot=fresh;
                    if result.as_ref().err().is_some_and(|error| error==meeting_processing_job::MINUTES_CANCELLED) {
                        pause_cancelled_meeting_work(&mut snapshot,&owner,"generatingMinutes",meeting_processing_job::MINUTES_CANCELLED)?;
                        return Err(meeting_processing_job::MINUTES_CANCELLED.into());
                    }
                    let failure=result?;
                    if let (Some(_),Some(note))=(template.as_ref(),failure.as_ref()) {
                        // Do not replace the existing saved view with a failed template draft.
                        pause_cancelled_meeting_work(&mut snapshot,&owner,"generatingMinutes",note)?;
                        return Err(format!("按模板整理未完成：{note}。原文和已有纪要保留。"));
                    }
                    if let Some(template)=template {
                        let variant=if request.meeting_mode.as_deref()==Some("onlineLive") {&mut session.minutes_by_mode.online_live}
                            else {&mut session.minutes_by_mode.offline_store};
                        let Some(variant)=variant.as_mut().filter(|v|v.quality=="final" && v.status=="minutesReady"
                            && v.processing.as_ref().is_none_or(|p|p.is_complete())) else {
                            let note="模板整理尚未完成，原文和已有纪要保留。";
                            pause_cancelled_meeting_work(&mut snapshot,&owner,"generatingMinutes",note)?;
                            return Err(note.into());
                        };
                        variant.template=Some(template);
                    }
                    // Context inclusion belongs only to this explicit request.
                    // Do not let generic automatic recovery replace a failed
                    // combined result with an original-only result silently.
                    if request.context_note_revision.is_some() && failure.is_some() {
                        session.recovery.stage="paused".into();
                        session.recovery.next_retry_at_unix_ms=None;
                        session.recovery.last_error=Some("本次整理未完成，原话和补充仍保留。请点“重试整理”；内容未变化时会继续参考上次选择的原话与补充，内容变化时请重新选择。".into());
                        session.pending_reason=Some("recovery_paused".into());
                    }
                    original_selected_session_id=snapshot.host.selected_session_id.clone();
                    next=apply_control_at(snapshot.clone(),request.clone(),&observation_timestamp())?;
                    next.meeting.status = session.status.clone();
                    if let Some(target) = next.host.sessions.iter_mut().find(|target| target.id == session.id) {
                        *target = session;
                    }
                    if let Some(echo) = next.last_control.as_mut() {
                        echo.message = match failure {
                            Some(note) => format!("minutes recovery pending — {note}"),
                            None => "minutes products saved; completed variants retained".to_string(),
                        };
                    }
                }
            }
            CompanionV1ControlAction::MeetingExportMarkdown
            | CompanionV1ControlAction::MeetingExportTxt
            | CompanionV1ControlAction::MeetingExportJson
            | CompanionV1ControlAction::MeetingExportSrt
            | CompanionV1ControlAction::MeetingExportActionsTodo
            | CompanionV1ControlAction::MeetingExportActionsIcal => {
                if let Some(echo) = next.last_control.as_mut() {
                    echo.message = "exported existing meeting content; transcription and minutes generation were not rerun"
                        .to_string();
                }
            }
            CompanionV1ControlAction::MeetingStop | CompanionV1ControlAction::MeetingFinalize => {
                let mut host_capture_error = None;
                let mut host_ownership_unconfirmed = false;
                if meeting_device_report.is_none() {
                    if let Some(stop) = self.host_recording.stop(requested_session_id.as_deref())? {
                        host_capture_error = stop.capture_error.clone();
                        host_ownership_unconfirmed = !stop.ownership_confirmed;
                        if let Some(session) = selected_session_mut(&mut next) {
                            if session.id == stop.session_id {
                                session.duration_ms = stop.duration_ms;
                                session.audio_bytes = stop.bytes;
                                if let Some(tracks) = stop.meeting_tracks.clone() {
                                    session.source = "hostMeeting".into();
                                    session.audio_path = None;
                                    session.chunks.clear();
                                    session.audio_stored = stop.ownership_confirmed && stop.capture_error.is_none();
                                    session.retention.audio_cached = stop.ownership_confirmed;
                                    session.meeting_tracks = Some(tracks);
                                    session.pending_reason = Some("needs_transcription".into());
                                } else {
                                    session.audio_path = Some(stop.path.to_string_lossy().to_string());
                                    session.audio_stored = true;
                                    session.retention.audio_cached = true;
                                    let stopped_at = session.stopped_at.clone().unwrap_or_else(|| "host-recording-stop".to_string());
                                    session.chunks = if stop.parts.len()>1 && stop.ownership_confirmed { host_segmented_capture::session_chunks(&session.id,&stop.parts)? } else { seal_companion_v1_session_chunks(session, &stopped_at, session.duration_ms, Some(stop.bytes)) };
                                    session.source = "hostMicrophone".to_string();
                                    arm_meeting_recovery(session);
                                }
                                if let Some(echo) = next.last_control.as_mut() {
                                    echo.message = format!(
                                        "host recording stopped ({}) {} bytes -> {}",
                                        stop.mode,
                                        stop.bytes,
                                        stop.path.to_string_lossy()
                                    );
                                }
                            }
                        }
                        next.meeting.duration_ms = stop.duration_ms;
                    }
                }

                // onlineLive: finish mid-meeting stream first; batch only if still empty.
                if meeting_device_report.is_none() {
                    self.host_recording.set_pcm_sink(None);
                    let live = self.live_asr.stop_and_take_text();
                    let mode = selected_session(&next)
                        .map(|s| s.meeting_mode.clone())
                        .unwrap_or_default();
                    if mode == "onlineLive" && host_capture_error.is_none()
                        && !selected_session(&next).is_some_and(interrupted_capture::needs_review) {
                        if !live.text.trim().is_empty() {
                            let completed = selected_session_mut(&mut next)
                                .is_some_and(|session| Self::finish_live_nonempty(session, &live));
                            next.meeting.status = if completed { "transcribed" } else { "captured" }.to_string();
                            next.meeting.transcript_count =
                                next.host
                                    .sessions
                                    .iter()
                                    .filter(|s| !s.transcript_text.trim().is_empty())
                                    .count() as u32;
                            if let Some(echo) = next.last_control.as_mut() {
                                echo.message = if completed {
                                    format!("onlineLive live stream closed via {} (partials={})", live.mode, live.partial_count)
                                } else {
                                    "实时识别未完成，已保留录音和部分文字，可继续转写。".to_string()
                                };
                            }
                        } else {
                            let (audio, empty) = selected_session(&next)
                                .map(|s| {
                                    (
                                        s.audio_path.clone(),
                                        s.transcript_text.trim().is_empty()
                                            && s.live_transcript_text.trim().is_empty(),
                                    )
                                })
                                .unwrap_or((None, false));
                            if empty && !shutdown_save_only {
                                if let Some(path) = audio {
                                    match self
                                        .transcription
                                        .transcribe_session_owned(next.host.selected_session_id.as_deref().unwrap_or(""), Some(path.as_str()), &[])
                                    {
                                        Ok(transcript) => {
                                            if let Some(session) = selected_session_mut(&mut next) {
                                                session.transcript_text = transcript.text.clone();
                                                session.transcript_final = true;
                                                session.live_transcript_text =
                                                    transcript.text.clone();
                                                session.transcript_preview =
                                                    transcript.text.chars().take(120).collect();
                                                session.transcript_segments = transcript
                                                    .text
                                                    .split(|c: char| {
                                                        c == '\n' || c == '。' || c == '.'
                                                    })
                                                    .filter(|s| !s.trim().is_empty())
                                                    .count();
                                                session.status = "transcribed".to_string();
                                                session.pending_reason = None;
                                                session.retention.transcript_cached = true;
                                                session.utterances = transcript.utterances;
                                                arm_meeting_recovery(session);
                                                mark_recovery_transcribed(session);
                                            }
                                            next.meeting.status = "transcribed".to_string();
                                            next.meeting.transcript_count = next
                                                .host
                                                .sessions
                                                .iter()
                                                .filter(|s| !s.transcript_text.trim().is_empty())
                                                .count()
                                                as u32;
                                            if let Some(echo) = next.last_control.as_mut() {
                                                echo.message = format!(
                                                    "onlineLive fallback batch via {} ({}); liveErr={:?}",
                                                    transcript.provider_id,
                                                    transcript.mode,
                                                    live.error
                                                );
                                            }
                                        }
                                        Err(err) => {
                                            if let Some(session) = selected_session_mut(&mut next) {
                                                session.pending_reason =
                                                    Some("needs_transcription".to_string());
                                                session.status = "captured".to_string();
                                            }
                                            if let Some(echo) = next.last_control.as_mut() {
                                                echo.message = format!(
                                                    "onlineLive stop stored audio; ASR pending: {err}"
                                                );
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                if let Some(error) = host_capture_error.as_deref() {
                    if let Some(session) = selected_session_mut(&mut next) {
                        pause_incomplete_host_recording(session, error, host_ownership_unconfirmed);
                    }
                    next.meeting.status = "captured".to_string();
                    if let Some(echo) = next.last_control.as_mut() {
                        echo.message = format!("录音已停止，但音频不完整：{error}。已保留文件并暂停自动处理。");
                    }
                }
            }
            _ => {}
        }

        if matches!(action,CompanionV1ControlAction::MeetingTranscribeAudio
            | CompanionV1ControlAction::MeetingGenerateMinutes) {
            next=merge_meeting_work(&snapshot,next,requested_session_id.as_deref());
        }
        if automatic_recovery {
            next.host.selected_session_id = original_selected_session_id;
        }
        if let Some(retirement)=privacy_retirement.as_mut() {
            let deleted=retirement.erase()?;
            if let Some(echo)=next.last_control.as_mut() {
                echo.message.push_str(&format!("；已清除{deleted}份已结束录音的控制记录。"));
            }
        }
        refresh_privacy_counts(&mut next);
        // Do not silently dismiss an existing storage warning on a read-only
        // action. A stop must retain its real state even if saving fails.
        if next.host.persistence.status == "ready" || action == CompanionV1ControlAction::MeetingStop {
            // Only an explicitly requested local privacy operation may remove
            // rows; never let an older UI snapshot erase a newly published row.
            let selected_authorization: Vec<(String,String)> = privacy_authorizations.iter()
                .filter(|(id,_)| requested_session_id.as_deref()==Some(id.as_str())).cloned().collect();
            let allowed_removals: Vec<(String,String)> = match action {
                CompanionV1ControlAction::PrivacyDeleteSession => selected_authorization.clone(),
                CompanionV1ControlAction::PrivacyEraseAll => privacy_authorizations.clone(),
                _ => Vec::new(),
            };
            let allowed_audio_clear: Vec<(String,String)> = match action {
                CompanionV1ControlAction::PrivacyEraseAudio | CompanionV1ControlAction::PrivacyDeleteSession => selected_authorization,
                CompanionV1ControlAction::PrivacyEraseAll => privacy_authorizations,
                _ => Vec::new(),
            };
            let _ = persistence::save_snapshot_allowing_removals(&mut next, &allowed_removals, &allowed_audio_clear);
        }
        if let Some(mut result) = cleanup_summary {
            result.index_saved = next.host.persistence.status == "ready";
            next.privacy.last_cleanup = Some(result);
        }
        *snapshot = next.clone();
        Ok(next)
    }

    fn follow_recording_once(&self, original_session: Option<&str>,
        live:Option<&mut recording_wire::receiver::LiveCursor>) -> Result<bool, String> {
        // Keep this same state/library serialization as foreground V2 import:
        // an editor must not persist stale rows over a newly published segment.
        let mut snapshot = self.snapshot.lock().map_err(|_| "Companion backend state lock failed")?;
        if snapshot.source != "firmware" || !snapshot.device.connected
            || snapshot.device.mode != "windowsNative" || snapshot.device.manual_disconnect
            || snapshot.host.persistence.status != "ready" {
            return Ok(false);
        }
        let Some(id) = snapshot.device.device_id.clone() else { return Ok(false); };
        let scope = original_session.map(|session|
            ble_bridge::original_follow_scope(&snapshot, session)).transpose()?;
        let allowed = if scope.is_some() { recording_sync::owned_follow_allowed(&id) }
            else { recording_sync::automatic_allowed(&id) };
        if !allowed {
            return Ok(false);
        }
        if !ble_bridge::prepared_segmented_recording(&id) {
            if live.is_some() {
                snapshot.connected=false;snapshot.device.connected=false;snapshot.device.connection_phase="offline".into();
                return Err("原在线接收连接已释放，设备继续离线录音，接收断点保留。".into());
            }
            return Ok(false);
        }
        match ble_bridge::follow_prepared_recording_once(&id, scope.as_ref(),live) {
            Ok(Some(observation)) => {
                apply_device_identity(&mut snapshot, &observation.identity);
                let Some(operation) = observation.operation else { return Ok(snapshot.device.recording); };
                observe_segmented_library(&mut snapshot, &operation, &persistence::state_file_path(),
                    CompanionV1ControlAction::DeviceSyncRecordings)?;
                require_follow_sync_success(&mut snapshot, &operation, observation.connection_reusable)?;
                Ok(true)
            }
            Ok(None) => Ok(snapshot.device.recording),
            Err(error) => {
                // A saved prefix/receipt remains discoverable on any failure.
                reload_segmented_library(&mut snapshot, &persistence::state_file_path())?;
                snapshot.device.message = error.clone();
                snapshot.connected = false; snapshot.device.connected = false;
                snapshot.device.connection_phase = "offline".into();
                Err(error)
            }
        }
    }

    fn automatic_reconnect_once(&self) -> Result<CompanionV1Snapshot, String> {
        let preference = {
            self
                .connection_preference
                .lock()
                .map_err(|_| "device connection preference lock failed".to_string())?
                .clone()
        };
        if !preference.can_automatically_reconnect() {
            return self.snapshot();
        }
        let remembered_device_id = preference.remembered_device_id.ok_or_else(|| {
            "automatic reconnect has no stable remembered device".to_string()
        })?;
        let original_recovery = {
            let mut snapshot = self
                .snapshot
                .lock()
                .map_err(|_| "Companion backend state lock failed".to_string())?;
            let original=(!snapshot.device.connected).then(||
                recorder_control::restart_recovery_request(&snapshot,&remembered_device_id)).flatten();
            if oobe_blocked_by_active_recording(&snapshot, self.live_asr.snapshot().active)
                && (!segmented_link_change_allowed(&snapshot) && original.is_none()
                    || self.live_asr.snapshot().active) {
                return Ok(snapshot.clone());
            }
            if original.is_none() {snapshot.device.connection_phase = "reconnecting".to_string();}
            snapshot.device.last_reconnect_attempt_at = Some(connection_timestamp());
            snapshot.device.reconnect_attempt_count =
                snapshot.device.reconnect_attempt_count.saturating_add(1);
            original
        };
        if let Some(request)=original_recovery {
            // The coordinator's same device-operation gate serializes this
            // with explicit Disconnect/opt-out. Recheck its exact preference
            // before entering the normal durable recorder recovery path.
            let preference=self.connection_preference.lock().map_err(|_|"device connection preference lock failed")?;
            let current=preference.can_automatically_reconnect() && preference.remembered_device_id.as_deref()
                .is_some_and(|id|device_connection::same_device_id(id,&remembered_device_id));
            drop(preference);
            if !current {return self.snapshot();}
            eprintln!("[device-reconnect] recovering confirmed durable original={} no_new_start=1",request.session_id.as_deref().unwrap_or(""));
            let result=self.apply_control(request);
            if let Some(snapshot)=self.retire_recovery_after_optout(&remembered_device_id)? {return Ok(snapshot);}
            return result;
        }

        let operation = self.ble_bridge.probe_remembered(&remembered_device_id);
        let mut snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        let mut preference = self
            .connection_preference
            .lock()
            .map_err(|_| "device connection preference lock failed".to_string())?;
        let claim_still_current = preference.can_automatically_reconnect()
            && preference
                .remembered_device_id
                .as_deref()
                .is_some_and(|current| {
                    device_connection::same_device_id(current, &remembered_device_id)
                });
        if !claim_still_current {
            // The physical probe ran outside this state lock. A manual
            // disconnect must also retire its late idle connection, without
            // touching a newly owned active recording.
            ble_bridge::disconnect_retained_recording(Some(&remembered_device_id))?;
            snapshot.connected = false;
            snapshot.device.connected = false;
            snapshot.device.connection_phase = if preference.manual_disconnect {
                "manualDisconnected"
            } else {
                "offline"
            }
            .to_string();
            apply_connection_preference(&mut snapshot, &preference);
            return Ok(snapshot.clone());
        }
        if !operation.ready {
            snapshot.connected = false;
            snapshot.device.connected = false;
            snapshot.device.connection_phase = "offline".to_string();
            snapshot.device.message = operation.message.clone();
            // The exact remembered-device claim was rechecked above, so a
            // late failure cannot pause another device or overwrite opt-out.
            if reconnect_requires_pairing(&operation.message) && preference.mark_pairing_required(&remembered_device_id) {
                apply_connection_preference(&mut snapshot,&preference);
                snapshot.device.message=operation.message.clone();
                if let Err(error)=device_connection::save(&preference) {
                    snapshot.device.message=format!("{}；暂停状态未保存：{error}",operation.message);
                    eprintln!("[device-reconnect] pairing pause checkpoint failed: {error}");
                }
            }
            return Err(operation.message);
        }
        let returned_device_id = operation.device_id.as_deref().ok_or_else(|| {
            "remembered-device probe returned no native address".to_string()
        })?;
        if !device_connection::same_device_id(&remembered_device_id, returned_device_id) {
            snapshot.connected = false;
            snapshot.device.connected = false;
            snapshot.device.connection_phase = "offline".to_string();
            return Err("remembered-device probe returned a different device".to_string());
        }
        snapshot.connected = true;
        snapshot.source = "firmware";
        snapshot.device.connected = true;
        snapshot.device.device_id = Some(returned_device_id.to_string());
        snapshot.device.connection_phase = "ready".to_string();
        snapshot.device.message = operation.message;
        if let Some(identity) = operation.device_identity.as_ref() {
            apply_device_identity(&mut snapshot, identity);
        }
        preference.remember_native_success(returned_device_id, connection_timestamp());
        device_connection::save(&preference)?;
        apply_connection_preference(&mut snapshot, &preference);
        Ok(snapshot.clone())
    }

    fn record_meeting_recovery_failure(
        &self,
        session_id: &str,
        retry_stage: &str,
        error: &str,
    ) -> Result<(), String> {
        // The lock-free worker already reconciled its own superseded claim.
        // Do not re-arm a deleted/reviewed job or consume a second attempt.
        if error==MEETING_WORK_SUPERSEDED { return Ok(()); }
        let mut snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        let session = snapshot
            .host
            .sessions
            .iter_mut()
            .find(|session| session.id == session_id)
            .ok_or_else(|| format!("meeting recovery target {session_id} is missing"))?;
        if session.recovery.intent != "processMeeting"
            || matches!(session.recovery.stage.as_str(), "complete" | "paused")
        {
            return Ok(());
        }
        session.recovery.retry_stage = retry_stage.to_string();
        schedule_recovery_failure(session, error);
        persistence::save_snapshot(&mut snapshot)
    }

    fn mark_meeting_exported(
        &self,
        session_id: &str,
        meeting_mode: &str,
        calendar_copy: Option<calendar_copy::Copy>,
    ) -> Result<(), String> {
        let mut snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        if let Some(copy)=calendar_copy {
            if snapshot.host.persistence.status!="ready" {return Err("资料库尚未就绪，未记录新的日历副本。".into());}
            if copy.meeting_mode!=meeting_mode {return Err("日历副本与整理方式不一致。".into());}
            if cfg!(test)&&std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none(){
                calendar_copy::apply(&mut snapshot.host.sessions,session_id,copy)?;
            }else{
                let (revision,copies,slot_copies,exported_at)=calendar_copy::commit(&persistence::state_file_path(),session_id,copy)?;
                let row=snapshot.host.sessions.iter_mut().find(|r|r.id==session_id).ok_or("原记录已移除；未恢复原记录。")?;
                row.calendar_copy_revision=revision;row.calendar_copies=copies;row.calendar_slot_copies=slot_copies;row.exported_at=exported_at;
            }
            snapshot.updated_at=observation_timestamp();return Ok(());
        }
        let session = snapshot.host.sessions.iter_mut().find(|session| session.id == session_id)
            .ok_or_else(|| format!("meeting export target {session_id} is missing"))?;
        let mode_exists = match meeting_mode {
            "offlineStore" => session.minutes_by_mode.offline_store.is_some(),
            "onlineLive" => session.minutes_by_mode.online_live.is_some(),
            _ => return Err(format!("unsupported meeting mode {meeting_mode}")),
        } || (session.meeting_mode == meeting_mode
            && session.minutes_by_mode.offline_store.is_none()
            && session.minutes_by_mode.online_live.is_none());
        if !mode_exists {
            return Err(format!(
                "meeting {session_id} no longer has a saved {meeting_mode} product"
            ));
        }
        session.exported_at = Some(observation_timestamp());
        persistence::save_snapshot(&mut snapshot)
    }

    fn transfer_firmware_ota(
        &self,
        mut request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionFirmwareOtaReport, String> {
        let snapshot=self.snapshot()?;
        if snapshot.device.recording {
            return Err("设备正在录音；请先结束录音，再同步升级。".into());
        }
        if !system_ota::is_bundle(std::path::Path::new(&request.manifest_path))? {
            return firmware_ota::transfer(&self.ble_bridge,request);
        }
        let whole_started=std::time::Instant::now();
        let validation=firmware_ota::validate_ota_package(&request)?;
        if !validation.ok { return Err("升级包校验未通过，未开始录音同步或升级。".into()); }
        let device_id=effective_device_target(request.device_id.as_deref(),snapshot.device.device_id.as_deref())
            .or(snapshot.device.remembered_device_id).ok_or("请先选择要升级的设备。")?;
        request.device_id=Some(device_id.clone());
        eprintln!("[companion-ota] recording_drain_begin device={device_id} ota_begin_allowed=0");
        let drain_started=std::time::Instant::now();
        let operation=match self.ble_bridge.sync_recordings_before_ota(&device_id) {
            Ok(operation) => operation,
            Err(error) => {
                let mut snapshot=self.snapshot.lock().map_err(|_|format!("{error}；录音库暂时无法刷新，已保存原件保留。"))?;
                return Err(observe_failed_ota_drain(&mut snapshot, &persistence::state_file_path(), error));
            }
        };
        {
            let mut snapshot=self.snapshot.lock().map_err(|_|"录音库状态暂时不可用，未开始升级。")?;
            observe_segmented_library(&mut snapshot,&operation,&persistence::state_file_path(),CompanionV1ControlAction::DeviceSyncRecordings)?;
            persistence::save_snapshot(&mut snapshot)?;
        }
        let drain_ms=drain_started.elapsed().as_millis();
        eprintln!("[companion-ota] recording_drain_library_saved device={device_id} elapsed_ms={drain_ms} ota_begin_allowed=1");
        let mut report=firmware_ota::transfer(&self.ble_bridge,request)?;
        report.elapsed_ms=whole_started.elapsed().as_millis();
        if let Some(bundle)=report.system_bundle.as_mut().and_then(serde_json::Value::as_object_mut) {
            bundle.insert("recordingDrain".into(),serde_json::json!({"complete":true,"deviceId":device_id,
                "elapsedMs":drain_ms,"remainingMicrophoneSegments":0,"localLibrarySaved":true,
                "cloudProcessingRequired":false,"userPauseOverridden":false}));
        }
        Ok(report)
    }

    fn validate_ota_package(
        &self,
        request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionOtaPackageValidation, String> {
        firmware_ota::validate_ota_package(&request)
    }

    fn complete_board_online_live(
        &self,
        session_id: &str,
        report: &BoardOnlineLiveReport,
    ) -> Result<CompanionV1Snapshot, String> {
        if report.sync_paused {
            let mut snapshot = self.snapshot.lock()
                .map_err(|_| "Companion backend state lock failed".to_string())?;
            observe_paused_online_sync(&mut snapshot, session_id, report)?;
            let _ = persistence::save_snapshot(&mut snapshot);
            return Ok(snapshot.clone());
        }
        let final_path = report.final_recording_path.trim();
        if final_path.is_empty() || !std::path::Path::new(final_path).is_file() {
            return Err("board onlineLive completion is missing the pulled WAV".to_string());
        }
        if report.final_total_length == 0 || report.final_sha256.len() != 64 {
            return Err("board onlineLive completion is missing durable identity".to_string());
        }

        let (wav_bytes, duration_ms) = wav_file_metrics(final_path).unwrap_or((
            std::fs::metadata(final_path)
                .map(|metadata| metadata.len())
                .unwrap_or(0),
            report
                .partials
                .last()
                .map(|partial| u64::from(partial.duration_ms))
                .unwrap_or(0),
        ));

        let interrupted_needs_review;
        // Commit the sealed, integrity-checked board artifact before entering
        // slow network ASR. A process exit during transcription must leave an
        // actionable captured row, not an orphan WAV with a board:// index.
        {
            let mut snapshot = self
                .snapshot
                .lock()
                .map_err(|_| "Companion backend state lock failed".to_string())?;
            let session = snapshot
                .host
                .sessions
                .iter_mut()
                .find(|session| session.id == session_id)
                .ok_or_else(|| format!("board onlineLive session {session_id} disappeared"))?;
            board_meeting::observe_online_times(session, &report.device_id, report.recording_id,
                &report.start_ack_at, &report.stop_ack_at)?;
            session.source = "deviceFlash".to_string();
            session.meeting_mode = "onlineLive".to_string();
            session.status = "captured".to_string();
            session.pending_reason = Some("needs_transcription".to_string());
            session.duration_ms = duration_ms;
            session.audio_path = Some(final_path.to_string());
            session.audio_bytes = wav_bytes;
            session.audio_stored = true;
            session.device_recording_id = Some(report.recording_id);
            session.capture_incomplete = report.capture_incomplete;
            session.device_total_length = Some(report.final_total_length);
            session.device_sha256 = Some(report.final_sha256.clone());
            session.device_reclaimed = report.device_reclaimed;
            arm_meeting_recovery(session);
            interrupted_needs_review = interrupted_capture::hold(session);
            if !interrupted_needs_review {
                session.recovery.retry_stage = "transcription".to_string();
                session.recovery.attempt_count = session.recovery.attempt_count.saturating_add(1);
                session.recovery.stage = "transcribing".to_string();
                session.recovery.next_retry_at_unix_ms = None;
                session.pending_reason = Some("recovery_processing".to_string());
            }
            session.chunks = vec![audio_chunk(
                format!("{}-board-live", session.id),
                Some(final_path.to_string()),
                session.started_at.clone(),
                session.stopped_at.clone(),
                duration_ms,
                wav_bytes,
                "synced",
            )];
            session.retention.audio_cached = true;
            recording_bookmarks::bind_received(session);
            snapshot.host.active_session_id = None;
            snapshot.host.selected_session_id = Some(session_id.to_string());
            snapshot.meeting.active = false;
            snapshot.meeting.status = "captured".to_string();
            snapshot.meeting.duration_ms = duration_ms;
            snapshot.updated_at = observation_timestamp();
            refresh_privacy_counts(&mut snapshot);
            persistence::save_snapshot(&mut snapshot)?;
        }

        if interrupted_needs_review {
            return self.snapshot.lock().map(|s| s.clone())
                .map_err(|_| "Companion backend state lock failed".to_string());
        }
        // Batch the sealed WAV after STOP. This is deliberately independent of
        // the live prefix consumer: a slow/failed partial never weakens the
        // final transcript and the board audio remains the source of truth.
        let final_transcript = match self.transcription.transcribe_audio_owned(session_id, final_path) {
            Ok(transcript) if !transcript.text.trim().is_empty() => transcript,
            result => {
                let reason = match result {
                    Ok(_) => "board onlineLive final ASR returned empty text".to_string(),
                    Err(err) => err,
                };
                // Offline/network failure is not a recording failure. Persist
                // the verified WAV + board identity first; the normal
                // MeetingTranscribeAudio action can consume it after reconnect.
                let mut snapshot = self
                    .snapshot
                    .lock()
                    .map_err(|_| "Companion backend state lock failed".to_string())?;
                let session = snapshot
                    .host
                    .sessions
                    .iter_mut()
                    .find(|session| session.id == session_id)
                    .ok_or_else(|| format!("board onlineLive session {session_id} disappeared"))?;
                session.source = "deviceFlash".to_string();
                session.meeting_mode = "onlineLive".to_string();
                session.status = if session.live_transcript_text.trim().is_empty() {
                    "captured".to_string()
                } else {
                    "transcribed".to_string()
                };
                session.pending_reason = Some("needs_transcription".to_string());
                session.duration_ms = duration_ms;
                session.audio_path = Some(final_path.to_string());
                session.audio_bytes = wav_bytes;
                session.audio_stored = true;
                session.device_recording_id = Some(report.recording_id);
                session.capture_incomplete = report.capture_incomplete;
                session.device_total_length = Some(report.final_total_length);
                session.device_sha256 = Some(report.final_sha256.clone());
                session.device_reclaimed = report.device_reclaimed;
                session.chunks = vec![audio_chunk(
                    format!("{}-board-live", session.id),
                    Some(final_path.to_string()),
                    session.started_at.clone(),
                    session.stopped_at.clone(),
                    duration_ms,
                    wav_bytes,
                    "synced",
                )];
                session.retention.audio_cached = true;
                schedule_recovery_failure(session, &reason);
                snapshot.host.active_session_id = None;
                snapshot.host.selected_session_id = Some(session_id.to_string());
                snapshot.meeting.active = false;
                snapshot.meeting.status = "captured".to_string();
                snapshot.meeting.duration_ms = duration_ms;
                snapshot.updated_at = observation_timestamp();
                if let Some(echo) = snapshot.last_control.as_mut() {
                    echo.message = format!(
                        "board onlineLive audio saved; final ASR pending after reconnect: {reason}"
                    );
                }
                refresh_privacy_counts(&mut snapshot);
                let _ = persistence::save_snapshot(&mut snapshot);
                return Ok(snapshot.clone());
            }
        };

        // Final ASR is a separate durable stage. Commit it before minutes so a
        // crash or LLM failure retries minutes without submitting the WAV to
        // ASR again.
        {
            let mut snapshot = self
                .snapshot
                .lock()
                .map_err(|_| "Companion backend state lock failed".to_string())?;
            let session = snapshot
                .host
                .sessions
                .iter_mut()
                .find(|session| session.id == session_id)
                .ok_or_else(|| format!("board onlineLive session {session_id} disappeared"))?;
            session.transcript_text = final_transcript.text.clone();
            session.transcript_final = true;
            session.transcript_preview = final_transcript.text.chars().take(120).collect();
            session.transcript_segments = final_transcript
                .text
                .split(|ch: char| ch == '\n' || ch == '。' || ch == '.')
                .filter(|segment| !segment.trim().is_empty())
                .count();
            session.utterances = final_transcript.utterances.clone();
            session.retention.transcript_cached = true;
            mark_recovery_transcribed(session);
            session.recovery.attempt_count = 1;
            session.recovery.retry_stage = "minutes".to_string();
            session.recovery.stage = "generatingMinutes".to_string();
            session.pending_reason = Some("recovery_processing".to_string());
            snapshot.updated_at = observation_timestamp();
            persistence::save_snapshot(&mut snapshot)?;
        }

        let base_session = {
            let snapshot = self
                .snapshot
                .lock()
                .map_err(|_| "Companion backend state lock failed".to_string())?;
            snapshot
                .host
                .sessions
                .iter()
                .find(|session| session.id == session_id)
                .cloned()
                .ok_or_else(|| format!("board onlineLive session {session_id} is missing"))?
        };
        let generated_at = observation_timestamp();
        let mut offline_input = base_session.clone();
        offline_input.meeting_mode = "offlineStore".to_string();
        offline_input.transcript_text = final_transcript.text.clone();
        let offline_minutes = self.minutes.generate(&offline_input, &generated_at);

        let mut online_input = base_session;
        online_input.meeting_mode = "onlineLive".to_string();
        if online_input.live_transcript_text.trim().is_empty() {
            online_input.live_transcript_text = final_transcript.text.clone();
        }
        // Prefix/window partials are preview evidence, not additive deltas.
        // The sealed WAV batch is authoritative for both final products.
        online_input.transcript_text = final_transcript.text.clone();
        let online_minutes = self.minutes.generate(&online_input, &generated_at);
        let minutes_failure = online_minutes
            .llm_note
            .clone()
            .or_else(|| offline_minutes.llm_note.clone());

        let partial_count = report.partials.len() as u32;
        let mut snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        let session = snapshot
            .host
            .sessions
            .iter_mut()
            .find(|session| session.id == session_id)
            .ok_or_else(|| format!("board onlineLive session {session_id} disappeared"))?;
        session.source = "deviceFlash".to_string();
        session.meeting_mode = "onlineLive".to_string();
        session.status = if minutes_failure.is_some() {
            "transcribed"
        } else {
            "minutesReady"
        }
        .to_string();
        session.duration_ms = duration_ms;
        session.audio_path = Some(final_path.to_string());
        session.audio_bytes = wav_bytes;
        session.audio_stored = true;
        session.device_recording_id = Some(report.recording_id);
        session.capture_incomplete = report.capture_incomplete;
        session.source_device_id = Some(report.device_id.clone());
        session.device_total_length = Some(report.final_total_length);
        session.device_sha256 = Some(report.final_sha256.clone());
        session.device_reclaimed = report.device_reclaimed;
        session.chunks = vec![audio_chunk(
            format!("{}-board-live", session.id),
            Some(final_path.to_string()),
            session.started_at.clone(),
            session.stopped_at.clone(),
            duration_ms,
            wav_bytes,
            "synced",
        )];
        session.transcript_text = final_transcript.text.clone();
        session.transcript_final = true;
        if session.live_transcript_text.trim().is_empty() {
            session.live_transcript_text = final_transcript.text.clone();
        }
        session.transcript_preview = final_transcript.text.chars().take(120).collect();
        session.transcript_segments = final_transcript
            .text
            .split(|ch: char| ch == '\n' || ch == '。' || ch == '.')
            .filter(|segment| !segment.trim().is_empty())
            .count();
        session.utterances = final_transcript.utterances;
        session.minutes = Some(online_minutes.clone());
        session.minutes_by_mode = CompanionV1MinutesByMode {
            offline_store: Some(minutes_variant(&offline_minutes, 0)),
            online_live: Some(minutes_variant(&online_minutes, partial_count)),
            history: std::mem::take(&mut session.minutes_by_mode.history),
        };
        session.export_markdown = online_minutes.markdown;
        session.exported_at = Some(generated_at.to_string());
        session.retention.audio_cached = true;
        session.retention.transcript_cached = true;
        session.retention.minutes_cached = true;
        arm_meeting_recovery(session);
        if let Some(error) = minutes_failure.as_deref() {
            schedule_recovery_failure(session, error);
        } else {
            mark_recovery_complete(session);
        }
        snapshot.host.active_session_id = None;
        snapshot.host.selected_session_id = Some(session_id.to_string());
        snapshot.meeting.active = false;
        snapshot.meeting.status = if minutes_failure.is_some() {
            "transcribed"
        } else {
            "minutesReady"
        }
        .to_string();
        snapshot.meeting.duration_ms = duration_ms;
        snapshot.updated_at = observation_timestamp();
        snapshot.meeting.transcript_count = snapshot
            .host
            .sessions
            .iter()
            .filter(|item| !item.transcript_text.trim().is_empty())
            .count() as u32;
        refresh_privacy_counts(&mut snapshot);
        let _ = persistence::save_snapshot(&mut snapshot);
        Ok(snapshot.clone())
    }

    fn bind_board_online_live_recording(&self, session_id: &str, device_id: &str, recording_id: u32, start_ack_at: &str)
        -> Result<(), String> {
        chrono::DateTime::parse_from_rfc3339(start_ack_at)
            .map_err(|_| "板端录音缺少实际开始确认时间。")?;
        let mut snapshot = self.snapshot.lock().map_err(|_| "Companion backend state lock failed")?;
        let session = snapshot.host.sessions.iter_mut().find(|s| s.id == session_id)
            .ok_or("板端录音对应的会议已不存在，录音已请求停止。")?;
        if session.status != "recording" || session.meeting_mode != "onlineLive"
            || session.source_device_id.as_deref().is_some_and(|id| !device_connection::same_device_id(id, device_id))
            || session.device_recording_id.is_some_and(|id| id != recording_id) {
            return Err("板端录音与会议身份不一致，录音已请求停止。".into());
        }
        session.source_device_id = Some(device_id.into());
        session.device_recording_id = Some(recording_id);
        let prior = session.clone();
        board_meeting::observe_start(session, Some(&prior), start_ack_at);
        snapshot.meeting.started_at = session.started_at.clone();
        snapshot.updated_at = observation_timestamp();
        persistence::save_snapshot(&mut snapshot)
    }

    fn set_board_online_live_partial(
        &self,
        session_id: &str,
        transcript: &str,
    ) -> Result<CompanionV1Snapshot, String> {
        let transcript = transcript.trim();
        if transcript.is_empty() {
            return Err("board onlineLive partial is empty".to_string());
        }
        let mut snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        let session = snapshot
            .host
            .sessions
            .iter_mut()
            .find(|session| session.id == session_id)
            .ok_or_else(|| format!("board onlineLive session {session_id} is missing"))?;
        if session.status != "recording" || session.meeting_mode != "onlineLive" {
            return Err(format!(
                "board onlineLive partial rejected for inactive session {session_id}"
            ));
        }
        // Board ASR consumes a durable prefix (later a rolling window), so each
        // result supersedes the previous preview. Appending would duplicate the
        // same speech on every pull.
        session.live_transcript_text = transcript.to_string();
        session.transcript_text = transcript.to_string();
        session.transcript_final = false;
        session.transcript_preview = transcript.chars().take(120).collect();
        session.transcript_segments = transcript
            .split(|ch: char| ch == '\n' || ch == '。' || ch == '.')
            .filter(|segment| !segment.trim().is_empty())
            .count();
        session.pending_reason = None;
        session.retention.transcript_cached = true;
        snapshot.updated_at = observation_timestamp();
        let _ = persistence::save_snapshot(&mut snapshot);
        Ok(snapshot.clone())
    }

    fn fail_board_online_live(
        &self,
        session_id: &str,
        reason: &str,
    ) -> Result<CompanionV1Snapshot, String> {
        let mut snapshot = self
            .snapshot
            .lock()
            .map_err(|_| "Companion backend state lock failed".to_string())?;
        if let Some(session) = snapshot
            .host
            .sessions
            .iter_mut()
            .find(|session| session.id == session_id)
        {
            session.source = "deviceFlash".to_string();
            session.status = "captured".to_string();
            session.pending_reason = Some("needs_device_sync".to_string());
            // A failed transport/STOP is not an acknowledged capture end.
            board_meeting::retain_capture_dates(session);
            arm_meeting_recovery(session);
            session.recovery.stage = "paused".to_string();
            session.recovery.last_error = Some(reason.chars().take(512).collect());
        }
        snapshot.host.active_session_id = None;
        snapshot.meeting.active = false;
        snapshot.meeting.status = "captured".to_string();
        snapshot.updated_at = observation_timestamp();
        if let Some(echo) = snapshot.last_control.as_mut() {
            echo.accepted = false;
            echo.message = format!("board onlineLive failed: {reason}");
        }
        let _ = persistence::save_snapshot(&mut snapshot);
        Ok(snapshot.clone())
    }
}

/// A completed old meeting must not restore pre-work device/UI state or stop
/// a newer capture. Apply only its session into the latest locked snapshot.
fn merge_meeting_work(current:&CompanionV1Snapshot,next:CompanionV1Snapshot,id:Option<&str>)
    ->CompanionV1Snapshot {
    let Some(id)=id else {return next};
    let Some(session)=next.host.sessions.iter().find(|s|s.id==id) else {return next};
    let mut merged=current.clone();
    let Some(target)=merged.host.sessions.iter_mut().find(|s|s.id==id) else {return merged};
    *target=session.clone();
    if !current.meeting.active && current.host.selected_session_id.as_deref()==Some(id) {
        merged.meeting=next.meeting;
    }
    merged.meeting.transcript_count=merged.host.sessions.iter()
        .filter(|s|!s.transcript_text.trim().is_empty()).count() as u32;
    merged.updated_at=next.updated_at;
    merged.last_control=next.last_control;
    merged
}

fn selected_session_mut(snapshot: &mut CompanionV1Snapshot) -> Option<&mut CompanionV1HostSession> {
    let selected_id = snapshot
        .host
        .selected_session_id
        .clone()
        .or_else(|| snapshot.host.active_session_id.clone())
        .or_else(|| {
            snapshot
                .host
                .sessions
                .first()
                .map(|session| session.id.clone())
        })?;
    snapshot
        .host
        .sessions
        .iter_mut()
        .find(|session| session.id == selected_id)
}

fn requested_or_selected_session_mut<'a>(
    snapshot: &'a mut CompanionV1Snapshot,
    requested_id: Option<&str>,
) -> Option<&'a mut CompanionV1HostSession> {
    let target_id = requested_id
        .map(str::to_owned)
        .or_else(|| snapshot.host.selected_session_id.clone())
        .or_else(|| snapshot.host.active_session_id.clone())
        .or_else(|| snapshot.host.sessions.first().map(|session| session.id.clone()))?;
    snapshot
        .host
        .sessions
        .iter_mut()
        .find(|session| session.id == target_id)
}

fn transcription_chunk_paths(session: &CompanionV1HostSession) -> Result<Vec<String>, String> {
    // The preserved input is a library asset, not another speech segment.
    let filtered;
    let session=if session.source=="importedAudio" {
        filtered={let mut row=session.clone();row.chunks.retain(|chunk|chunk.status!="importedOriginal");row};
        &filtered
    } else {session};
    if let Some(parts)=host_segmented_capture::saved_parts(session)? {
        return Ok(parts.into_iter().map(|(path,_)|path.to_string_lossy().into_owned()).collect());
    }
    if session.device_recording_key.is_some() {
        // V2 chunks are immutable encoded originals, not independent WAVs.
        // Verify their exact receipt/CRC/SHA/sample axis and assembled audio
        // before handing all continuous WAV parts to the existing ASR pipeline.
        // The raw chunk metadata remains the provenance/consume contract.
        return Ok(recording_wire::receiver::Receiver::verified_audio_paths(session)?
            .into_iter().map(|path| path.to_string_lossy().into_owned()).collect());
    }
    // The host recorder seals five-minute timeline entries over ONE durable
    // WAV. Recognise that exact generated contract, not arbitrary duplicates:
    // independently declared physical segments must still be checked in full.
    if let Some(primary) = session.audio_path.as_ref().filter(|path| {
        !path.starts_with("host://") && !path.starts_with("device://")
    }) {
        let expected = seal_companion_v1_session_chunks(
            session, "", session.duration_ms, Some(session.audio_bytes),
        );
        if !session.chunks.is_empty()
            && expected.len() == session.chunks.len()
            && session.chunks.iter().zip(&expected).all(|(actual, expected)| {
                actual.id == expected.id && actual.status == "sealed"
                    && actual.path.as_ref() == Some(primary)
                    && actual.duration_ms == expected.duration_ms && actual.bytes == expected.bytes
            })
        {
            return Ok(vec![primary.clone()]);
        }
    }
    // Retain every declared entry, including unresolved device/host URIs and
    // missing paths. The transcription boundary reports its exact missing
    // position before any provider/cache can return a partial meeting.
    Ok(session.chunks.iter().map(|chunk| chunk.path.clone().unwrap_or_default()).collect())
}

fn selected_session(snapshot: &CompanionV1Snapshot) -> Option<&CompanionV1HostSession> {
    let selected_id = snapshot
        .host
        .selected_session_id
        .as_ref()
        .or(snapshot.host.active_session_id.as_ref());
    if let Some(selected_id) = selected_id {
        return snapshot
            .host
            .sessions
            .iter()
            .find(|session| &session.id == selected_id);
    }
    snapshot.host.sessions.first()
}

fn received_recording_target(sessions: &[CompanionV1HostSession], device_id: Option<&str>, item: &CompanionSyncedRecording) -> String {
    let matches: Vec<_> = sessions.iter().filter(|s|
        s.device_recording_id == Some(item.recording_id)
            && s.source_device_id.as_deref().zip(device_id).is_some_and(|(a,b)| device_connection::same_device_id(a,b))
            && s.device_sha256.as_deref().is_none_or(|sha| sha == item.sha256))
        .collect();
    if matches.len() == 1 { matches[0].id.clone() }
    else { format!("{}-{}", device_recording_session_id(device_id, item.recording_id), item.sha256) }
}
pub(crate) fn checkpoint_received_recording(
    path: &std::path::Path, device_id: &str, recording: &CompanionSyncedRecording,
) -> Result<(), String> {
    session_store::update(path, |sessions| {
        let mut checkpoint = fixture_snapshot();
        checkpoint.device.device_id = Some(device_id.into());
        checkpoint.host.sessions = std::mem::take(sessions);
        merge_synced_recordings(&mut checkpoint, std::slice::from_ref(recording));
        *sessions = checkpoint.host.sessions;
    })
}

fn observe_paused_online_sync(snapshot: &mut CompanionV1Snapshot, session_id: &str,
    report: &BoardOnlineLiveReport) -> Result<(), String> {
    if report.device_reclaimed || !report.final_recording_path.is_empty()
        || report.final_total_length != 0 || !report.final_sha256.is_empty()
    { return Err("暂停同步结果含有矛盾的录音完成标记，未修改会议。".into()); }
    let session = snapshot.host.sessions.iter_mut().find(|session| session.id == session_id)
        .ok_or_else(|| format!("board onlineLive session {session_id} disappeared"))?;
    let mut pending = session.clone();
    board_meeting::observe_online_times(&mut pending, &report.device_id, report.recording_id,
        &report.start_ack_at, &report.stop_ack_at)?;
    board_meeting::pending_sync(&mut pending, report.recording_id, report.sealed_duration_ms, &report.stop_ack_at)?;
    pending.source = "boardDevice".into();
    pending.source_device_id = Some(report.device_id.clone());
    *session = pending;
    snapshot.host.active_session_id = None;
    snapshot.meeting.active = false;
    snapshot.meeting.status = "captured".into();
    snapshot.meeting.duration_ms = u64::from(report.sealed_duration_ms);
    snapshot.updated_at = observation_timestamp();
    snapshot.last_control = Some(crate::companion_v1::CompanionV1ControlEcho {
        action: CompanionV1ControlAction::MeetingStop,
        characteristic_uuid: crate::companion_v1::COMPANION_V1_HOST_DEVICE_CHANNEL,
        payload_hex: String::new(), accepted: true,
        message: format!("设备已停止录音。{}", recording_sync::PAUSED),
    });
    refresh_privacy_counts(snapshot);
    Ok(())
}

fn observe_empty_sync_pause(snapshot: &mut CompanionV1Snapshot, operation: &CompanionBleOperation) {
    // This changes the outcome of the local sync command, not capture/library
    // state. In particular, do not run the fixture's synced-session reducer.
    snapshot.updated_at = observation_timestamp();
    snapshot.device.message = operation.message.clone();
    snapshot.last_control = Some(crate::companion_v1::CompanionV1ControlEcho {
        action: CompanionV1ControlAction::DeviceSyncRecordings,
        characteristic_uuid: crate::companion_v1::COMPANION_V1_HOST_DEVICE_CHANNEL,
        payload_hex: String::new(), accepted: true, message: operation.message.clone(),
    });
}

fn reload_segmented_library(snapshot: &mut CompanionV1Snapshot, path: &std::path::Path) -> Result<(), String> {
    let loaded = session_store::load(path);
    if loaded.state.status == "blocked" {
        return Err(loaded.state.message.unwrap_or_else(|| "连续录音库暂时无法读取，原音保持保存。".into()));
    }
    let rows = match loaded.bytes {
        Some(bytes) => serde_json::from_slice(&bytes).map_err(|_| "连续录音库格式不可用，原音保持保存。".to_string())?,
        None if snapshot.host.sessions.is_empty() => Vec::new(),
        None => return Err("会议库暂时不可读，未用空列表覆盖现有会议。".into()),
    };
    snapshot.host.sessions = rows;
    snapshot.host.persistence = loaded.state;
    if snapshot.host.selected_session_id.as_ref().is_none_or(|id|
        !snapshot.host.sessions.iter().any(|s| s.id == *id)) {
        snapshot.host.selected_session_id = snapshot.host.sessions.first().map(|s| s.id.clone());
    }
    Ok(())
}

// A failed drain may already have durably published some source segments.
// Refresh the current library before later UI writes, but never discard an
// independently unsaved in-memory edit to make the refresh appear successful.
fn observe_failed_ota_drain(snapshot: &mut CompanionV1Snapshot, index: &std::path::Path, mut error: String) -> String {
    if snapshot.host.persistence.status == "unsaved" {
        error.push_str("；窗口中有未保存的修改，原音仍已保留，请先处理保存问题。");
    } else if let Err(load_error) = reload_segmented_library(snapshot, index) {
        error.push_str(&format!("；已保存原音待重新读取：{load_error}"));
    }
    snapshot.device.message = error.clone();
    snapshot.updated_at = observation_timestamp();
    error
}

// The receiver may have committed partial rows before its transport failed.
// Bring those exact rows into the live model without promoting that failure to
// "connected", completing a pending recording, or acknowledging more bytes.
fn observe_failed_device_connect(snapshot:&mut CompanionV1Snapshot,operation:&CompanionBleOperation,index:&std::path::Path)->String {
    let mut error=operation.message.clone();
    if operation.mode=="windows-native-connect-auto-upload-segmented" {
        if let Err(e)=reload_segmented_library(snapshot,index){error.push_str(&format!("；本地已保存部分待重新读取：{e}"));}
    } else if !operation.recordings.is_empty() {
        if let Some(device)=operation.device_id.as_ref(){snapshot.device.device_id=Some(device.clone());}
        merge_synced_recordings(snapshot,&operation.recordings);
        if let Err(e)=persistence::save_snapshot(snapshot){error.push_str(&format!("；本地索引保存待重试：{e}"));}
    }
    if let Some(identity)=operation.device_identity.as_ref(){snapshot.source="firmware";apply_device_identity(snapshot,identity);}
    if let Some(device)=operation.device_id.as_ref(){snapshot.device.device_id=Some(device.clone());}
    snapshot.connected=false;snapshot.device.connected=false;snapshot.device.connection_phase="offline".into();
    snapshot.device.message=error.clone();snapshot.updated_at=observation_timestamp();
    snapshot.last_control=Some(crate::companion_v1::CompanionV1ControlEcho{
        action:CompanionV1ControlAction::DeviceConnect,characteristic_uuid:"8f7a3002-7b7d-4f3d-9d6f-6c2d1b7c0000",
        payload_hex:String::new(),accepted:false,message:error.clone(),
    });
    refresh_privacy_counts(snapshot);error
}

// A local receipt failure does not prove the active physical BLE connection
// failed. Report incomplete sync, but preserve a reusable connection.
fn require_follow_sync_success(snapshot: &mut CompanionV1Snapshot,
    operation: &CompanionBleOperation, connection_reusable: bool) -> Result<(), String> {
    if operation.ready { return Ok(()); }
    if !connection_reusable {
        snapshot.connected = false; snapshot.device.connected = false;
        snapshot.device.connection_phase = "offline".into();
    }
    Err(operation.message.clone())
}

#[cfg(test)]
mod follow_receipt_connection_tests {
    use super::*;
    #[test]
    fn local_receipt_failure_keeps_verified_connection_while_transport_failure_closes_it() {
        let mut snapshot = crate::companion_v1::fixture_snapshot();
        snapshot.connected=true;snapshot.device.connected=true;snapshot.device.connection_phase="connected".into();
        let operation=CompanionBleOperation { provider_id:"companion-type-windows-ble".into(),
            mode:"windows-native-segmented-recording-pull".into(), ready:false, sync_paused:false,
            device_id:Some("A1:B2:C3:D4:E5:F6".into()),recording_path:None,recordings:Vec::new(),
            device_identity:None,message:"录音恢复记录损坏，原件保留".into() };
        assert!(require_follow_sync_success(&mut snapshot,&operation,true).is_err());
        assert!(snapshot.connected&&snapshot.device.connected);assert_eq!(snapshot.device.connection_phase,"connected");
        assert!(require_follow_sync_success(&mut snapshot,&operation,false).is_err());
        assert!(!snapshot.connected&&!snapshot.device.connected);assert_eq!(snapshot.device.connection_phase,"offline");
    }
}

fn observe_segmented_library(snapshot: &mut CompanionV1Snapshot,
    operation: &CompanionBleOperation, index: &std::path::Path, action: CompanionV1ControlAction) -> Result<(), String> {
    reload_segmented_library(snapshot, index)?;
    snapshot.source = "firmware".into();
    snapshot.updated_at = observation_timestamp();
    snapshot.device.message = operation.message.clone();
    if let Some(device) = operation.device_id.as_ref() { snapshot.device.device_id = Some(device.clone()); }
    snapshot.device.last_sync_at = Some(snapshot.updated_at.clone());
    snapshot.last_control = Some(crate::companion_v1::CompanionV1ControlEcho {
        action, characteristic_uuid: "8f7a3002-7b7d-4f3d-9d6f-6c2d1b7c0000",
        payload_hex: String::new(), accepted: operation.ready, message: operation.message.clone(),
    });
    // Synchronizing sealed segments is not STOP. Keep the active recorder,
    // live text and user selection independent from the sync lifetime.
    Ok(())
}

fn merge_synced_recordings(snapshot: &mut CompanionV1Snapshot, recordings: &[CompanionSyncedRecording]) {
    if recordings.is_empty() { return; }
    let mut last_id = None;
    for item in recordings {
        let id = received_recording_target(&snapshot.host.sessions, snapshot.device.device_id.as_deref(), item);
        if !snapshot.host.sessions.iter().any(|s| s.id == id) {
            let metrics = wav_file_metrics(&item.recording_path);
            let request = CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::DeviceSyncRecordings, context_note_revision: None, ble_name: None, session_id: Some(id.clone()), prompt_id: None,
                title: Some(format!("设备录音 #{}", item.recording_id)), transcript_text: None,
                meeting_mode: Some("offlineStore".into()), audio_path: Some(item.recording_path.clone()),
                audio_bytes: metrics.map(|v|v.0).or(Some(item.total_length as u64)),
                device_id: snapshot.device.device_id.clone(), duration_ms: metrics.map(|v|v.1).or(Some(item.duration_ms as u64)),
            };
            let mut session = crate::companion_v1::synced_device_session(snapshot, &request, &snapshot.updated_at);
            // A pull observes receipt, not the original capture start/stop.
            session.started_at = None;
            session.stopped_at = None;
            snapshot.host.sessions.insert(0, session);
        }
        let session = snapshot.host.sessions.iter_mut().find(|s| s.id == id).expect("received session inserted");
        let was_waiting_for_sync = session.pending_reason.as_deref() == Some("needs_device_sync");
        session.device_recording_id = Some(item.recording_id);
        session.device_total_length = Some(item.total_length);
        session.device_sha256 = Some(item.sha256.clone());
        session.device_reclaimed = item.device_reclaimed;
        session.capture_incomplete = item.capture_incomplete;
        session.source_device_id = snapshot.device.device_id.clone();
        session.audio_path = Some(item.recording_path.clone());
        session.audio_bytes = std::fs::metadata(&item.recording_path).map(|m|m.len()).unwrap_or(0);
        session.audio_stored = true;
        session.retention.audio_cached = true;
        session.duration_ms = item.duration_ms as u64;
        recording_bookmarks::bind_received(session);
        board_meeting::retain_capture_dates(session);
        session.chunks = vec![audio_chunk(format!("{}-received", session.id), session.audio_path.clone(),
            session.started_at.clone(), session.stopped_at.clone(), session.duration_ms, session.audio_bytes, "synced")];
        if !session.transcript_final {
            session.status = "captured".into();
            session.pending_reason = Some("needs_transcription".into());
            if was_waiting_for_sync && session.processing_policy != crate::companion_v1::CompanionV1ProcessingPolicy::Manual {
                session.recovery = CompanionV1MeetingRecovery::armed(&session.meeting_mode);
            } else { arm_meeting_recovery(session); }
            interrupted_capture::hold(session);
        }
        last_id = Some(id);
    }
    snapshot.host.selected_session_id = last_id;
    snapshot.device.recordings_available = recordings.iter().filter(|r| !r.device_reclaimed).count() as u32;
}

fn audio_chunk(
    id: String,
    path: Option<String>,
    started_at: Option<String>,
    stopped_at: Option<String>,
    duration_ms: u64,
    bytes: u64,
    status: &str,
) -> CompanionV1AudioChunk {
    CompanionV1AudioChunk {
        id,
        path,
        started_at,
        stopped_at,
        duration_ms,
        bytes,
        status: status.to_string(),
    }
}

fn refresh_privacy_counts(snapshot: &mut CompanionV1Snapshot) {
    snapshot.privacy.audio_cache_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| session.audio_bytes.saturating_add(session.chunks.iter()
            .filter(|chunk|session.source=="importedAudio" && chunk.status=="importedOriginal")
            .fold(0u64,|total,chunk|total.saturating_add(chunk.bytes))))
        .sum();
    snapshot.privacy.transcript_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| (session.transcript_text.len() + session.meeting_notes.iter().map(|n| n.text.len()).sum::<usize>()) as u64)
        .sum();
    snapshot.privacy.minutes_bytes = snapshot
        .host
        .sessions
        .iter()
        .map(|session| session.export_markdown.as_bytes().len() as u64)
        .sum();
}

#[cfg(test)]
mod tests {
    #[test]
    #[ignore = "requires previously authorized real-card audio and installed local model"]
    fn gap_preview_authorized_weak_audio_preserves_source() {
        use super::*;
        use sha2::{Digest,Sha256};use std::io::Read;
        fn digest(path:&std::path::Path)->Vec<u8>{let mut f=std::fs::File::open(path).unwrap();let mut h=Sha256::new();let mut b=[0u8;65536];loop{let n=f.read(&mut b).unwrap();if n==0{break;}h.update(&b[..n]);}h.finalize().to_vec()}
        let root=std::path::PathBuf::from(std::env::var_os("COMPANION_TEST_CASE_ROOT").unwrap());
        let audio=std::path::PathBuf::from(std::env::var_os("COMPANION_LOCAL_ASR_TEST_WAV").unwrap());
        assert!(std::env::var_os("COMPANION_TYPE_LOCAL_ASR_DIR").is_some());std::fs::create_dir_all(&root).unwrap();
        std::env::set_var("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"));std::env::set_var("COMPANION_TYPE_RECORDING_DIR",root.join("recordings"));
        std::env::set_var("COMPANION_TYPE_ASR_CACHE_DIR",root.join("cache"));std::env::set_var("COMPANION_TYPE_ASR_PROVIDER","local-paraformer");
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        let original=digest(&audio);let backend=FixtureCompanionBackend::new();install_recovery_session(&backend,"authorized-gap",&audio);
        {let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.persistence.status="ready".into();
         let row=&mut snapshot.host.sessions[0];row.source="controlledLocalAudioFixture".into();row.status="transcribed".into();
         row.transcript_final=true;row.transcript_text="原转写保留".into();row.transcript_unrecognized=vec![crate::companion_v1::CompanionV1UnrecognizedAudio{start_ms:16600,end_ms:31400,source:None}];}
        let before=serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap();
        let outcome=backend.preview_meeting_gap("authorized-gap","__meeting_job__weak",transcription::TranscriptionRange{start_ms:16600,end_ms:31400});
        match outcome {Ok(result)=>println!("Authorized weak gap local preview returned {} characters; no audio or text uploaded",result.text.chars().count()),
            Err(error)=>{assert_eq!(error,transcription::LOCAL_NO_SPEECH);println!("Authorized weak gap still has no recognized words; no audio uploaded");}}
        assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),before);assert_eq!(digest(&audio),original);
    }
    #[test]
    #[ignore = "requires isolated public speech and installed local model"]
    fn gap_preview_real_public_speech_uses_only_selected_interval() {
        use super::*;
        let root=std::path::PathBuf::from(std::env::var_os("COMPANION_TEST_CASE_ROOT").unwrap());
        let audio=std::path::PathBuf::from(std::env::var_os("COMPANION_LOCAL_ASR_TEST_WAV").unwrap());
        assert!(std::env::var_os("COMPANION_TYPE_LOCAL_ASR_DIR").is_some());std::fs::create_dir_all(&root).unwrap();
        std::env::set_var("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"));
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",root.join("recordings"));
        std::env::set_var("COMPANION_TYPE_ASR_CACHE_DIR",root.join("cache"));
        std::env::set_var("COMPANION_TYPE_ASR_PROVIDER","local-paraformer");
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        let before_audio=std::fs::read(&audio).unwrap();let backend=FixtureCompanionBackend::new();install_recovery_session(&backend,"public-gap",&audio);
        {let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.persistence.status="ready".into();
         let row=&mut snapshot.host.sessions[0];row.source="controlledLocalAudioFixture".into();row.status="transcribed".into();
         row.transcript_final=true;row.transcript_text="原转写保留".into();row.transcript_unrecognized=vec![crate::companion_v1::CompanionV1UnrecognizedAudio{start_ms:10000,end_ms:25000,source:None}];}
        let before=serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap();
        let result=backend.preview_meeting_gap("public-gap","__meeting_job__public",transcription::TranscriptionRange{start_ms:10000,end_ms:25000}).unwrap();
        assert!(result.text.chars().count()>10);assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),before);
        assert_eq!(std::fs::read(&audio).unwrap(),before_audio);
        {let mut snapshot=backend.snapshot.lock().unwrap();let row=&mut snapshot.host.sessions[0];
         row.transcript_final=false;row.transcript_text.clear();row.transcript_unrecognized.clear();row.status="needsTranscription".into();}
        let empty_before=serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap();
        let retry=backend.preview_meeting_gap("public-gap","__meeting_job__public-empty",transcription::TranscriptionRange{start_ms:10000,end_ms:25000}).unwrap();
        assert!(retry.text.chars().count()>10);assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),empty_before);
        assert_eq!(std::fs::read(&audio).unwrap(),before_audio);
        println!("Public speech gap preview: {} characters from selected 15 seconds; source audio and session unchanged",result.text.chars().count());
    }
    #[test]
    #[ignore = "sets isolated state, recording and transcription environment"]
    fn gap_preview_processes_selected_range_without_modifying_session_or_original() {
        use super::*;
        let root=std::env::temp_dir().join(format!("companion-gap-preview-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        std::env::set_var("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"));
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",root.join("recordings"));
        std::env::set_var("COMPANION_TYPE_ASR_CACHE_DIR",root.join("cache"));
        std::env::set_var("COMPANION_TYPE_ASR_PROVIDER","isolated-test");
        std::env::set_var("COMPANION_TYPE_TRANSCRIPT_TEXT","这段新识别");
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
        let audio=root.join("meeting.wav");let mut wav=denzic_host_audio_v1_core::wav::wav_header(32_000).to_vec();wav.extend(vec![42u8;32_000]);std::fs::write(&audio,&wav).unwrap();
        let backend=FixtureCompanionBackend::new();install_recovery_session(&backend,"gap-meeting",&audio);
        {let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.persistence.status="ready".into();
         let row=&mut snapshot.host.sessions[0];row.source="controlledLocalAudioFixture".into();row.status="transcribed".into();
         row.transcript_final=true;row.transcript_text="旧转写".into();row.transcript_unrecognized=vec![crate::companion_v1::CompanionV1UnrecognizedAudio{start_ms:200,end_ms:800,source:None}];}
        let before=serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap();
        let range=transcription::TranscriptionRange{start_ms:200,end_ms:800};
        assert_eq!(backend.preview_meeting_gap("gap-meeting","__meeting_job__gap",range).unwrap().text,"这段新识别");
        assert!(backend.preview_meeting_gap("gap-meeting","__meeting_job__wrong",transcription::TranscriptionRange{start_ms:201,end_ms:800}).is_err());
        assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),before);assert_eq!(std::fs::read(&audio).unwrap(),wav);
        assert!(!std::fs::read_dir(root.join("recordings")).unwrap().any(|e|e.unwrap().file_name().to_string_lossy().contains("-range.wav")));
        // No transcript means no saved gap markers. An explicitly chosen
        // playback interval should still be previewable, without claiming the
        // whole recording was transcribed or changing the original session.
        {let mut snapshot=backend.snapshot.lock().unwrap();let row=&mut snapshot.host.sessions[0];
         row.transcript_final=false;row.transcript_text.clear();row.transcript_unrecognized.clear();row.status="needsTranscription".into();}
        let before_empty=serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap();
        assert_eq!(backend.preview_meeting_gap("gap-meeting","__meeting_job__chosen",transcription::TranscriptionRange{start_ms:201,end_ms:800}).unwrap().text,"这段新识别");
        assert!(backend.preview_meeting_gap("gap-meeting","__meeting_job__out-of-range",transcription::TranscriptionRange{start_ms:900,end_ms:2000}).is_err());
        assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),before_empty);
        assert_eq!(std::fs::read(&audio).unwrap(),wav);
    }
    #[test]
    fn retranscription_preview_success_and_failure_keep_existing_session() {
        use super::*;
        let root=std::env::temp_dir().join(format!("companion-retranscription-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        std::env::set_var("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"));
        std::env::set_var("COMPANION_TYPE_ASR_CACHE_DIR",root.join("cache"));
        std::env::set_var("COMPANION_TYPE_ASR_PROVIDER","isolated-test");
        std::env::set_var("COMPANION_TYPE_TRANSCRIPT_TEXT","本次新转写");
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
        let audio=root.join("meeting.wav");
        let mut wav=denzic_host_audio_v1_core::wav::wav_header(3200).to_vec();wav.extend(vec![42u8;3200]);
        std::fs::write(&audio,&wav).unwrap();
        let backend=FixtureCompanionBackend::new();install_recovery_session(&backend,"preview-meeting",&audio);
        {
            let mut snapshot=backend.snapshot.lock().unwrap();
            snapshot.host.persistence.status="ready".into();
            let row=&mut snapshot.host.sessions[0];row.source="controlledLocalAudioFixture".into();
            row.status="transcribed".into();row.transcript_final=true;row.transcript_text="之前的转写".into();
        }
        let before=serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap();
        assert_eq!(backend.preview_meeting_transcription("preview-meeting","__meeting_job__one").unwrap().text,"本次新转写");
        assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),before);
        assert_eq!(std::fs::read(&audio).unwrap(),wav);
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        assert!(backend.preview_meeting_transcription("preview-meeting","__meeting_job__two").is_err());
        assert!(backend.preview_meeting_transcription("missing","__meeting_job__three").is_err());
        assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),before);
        assert_eq!(std::fs::read(&audio).unwrap(),wav);
    }
    #[test]
    #[ignore = "requires isolated public WAV and installed local model"]
    fn retranscription_preview_public_local_model() {
        use super::*;
        let root=std::path::PathBuf::from(std::env::var_os("COMPANION_TEST_CASE_ROOT").unwrap());
        std::fs::create_dir_all(&root).unwrap();
        let audio=std::path::PathBuf::from(std::env::var_os("COMPANION_LOCAL_ASR_TEST_WAV").unwrap());
        assert!(std::env::var_os("COMPANION_TYPE_LOCAL_ASR_DIR").is_some());
        std::env::set_var("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"));
        std::env::set_var("COMPANION_TYPE_ASR_CACHE_DIR",root.join("cache"));
        std::env::set_var("COMPANION_TYPE_ASR_PROVIDER","local-paraformer");
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        let bytes=std::fs::read(&audio).unwrap();
        let backend=FixtureCompanionBackend::new();install_recovery_session(&backend,"public-preview",&audio);
        {
            let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.persistence.status="ready".into();
            let row=&mut snapshot.host.sessions[0];row.source="controlledLocalAudioFixture".into();
            row.status="transcribed".into();row.transcript_final=true;row.transcript_text="旧识别结果".into();
        }
        let before=serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap();
        let result=backend.preview_meeting_transcription("public-preview","__meeting_job__local").unwrap();
        assert!(!result.text.trim().is_empty());assert_ne!(result.text,"旧识别结果");
        assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),before);
        assert_eq!(std::fs::read(&audio).unwrap(),bytes);
        println!("public local-model preview: {} characters, original session and audio unchanged",result.text.chars().count());
    }
    #[test]
    #[ignore]
    fn empty_host_recording_restore_gives_relevant_error() {
        use super::*;
        let root=std::path::PathBuf::from(std::env::var_os("COMPANION_TEST_CASE_ROOT").unwrap());
        std::fs::create_dir_all(&root).unwrap();
        let wav=root.join("empty.wav");
        let bytes=denzic_host_audio_v1_core::wav::wav_header(0).to_vec();
        std::fs::write(&wav,&bytes).unwrap();
        let backend=FixtureCompanionBackend::new();
        install_recovery_session(&backend,"empty-host",&wav);
        let row={
            let mut snapshot=backend.snapshot.lock().unwrap();
            let s=&mut snapshot.host.sessions[0];
            s.source="hostMicrophone".into(); s.status="captured".into();
            s.audio_stored=true; s.audio_bytes=44; s.retention.audio_cached=true;
            s.device_recording_id=None; s.device_recording_key=None; s.recorder_control=None;
            s.clone()
        };
        persistence::save_sessions_to(&persistence::state_file_path(),&[row]).unwrap();
        drop(backend);
        let restarted=FixtureCompanionBackend::new();
        let error=restarted.apply_control(recovery_request(CompanionV1ControlAction::MeetingRestoreAudio,"empty-host",false)).unwrap_err();
        println!("restore_error={error}");
        assert!(error.contains("本机录音") && error.contains("没有"), "the restore error should explain the empty host recording");
        assert_eq!(std::fs::read(&wav).unwrap(),bytes);
        let mut with_samples=denzic_host_audio_v1_core::wav::wav_header(32000).to_vec();
        with_samples.extend(vec![42u8;32000]);
        std::fs::write(&wav,&with_samples).unwrap();
        let mismatch=restarted.apply_control(recovery_request(CompanionV1ControlAction::MeetingRestoreAudio,"empty-host",false)).unwrap_err();
        assert!(mismatch.contains("保存信息尚未确认") && !mismatch.contains("没有可恢复的声音"));
        assert_eq!(std::fs::read(&wav).unwrap(),with_samples);
    }

    #[test]
    #[ignore]
    fn unconfirmed_host_backoff_must_not_transcribe() {
        use super::*;
        let root=std::path::PathBuf::from(std::env::var_os("COMPANION_TEST_CASE_ROOT").unwrap());
        std::fs::create_dir_all(&root).unwrap();
        let wav=root.join("synthetic-unfinished.wav");
        let mut bytes=denzic_host_audio_v1_core::wav::wav_header(32000).to_vec();
        bytes.extend(vec![0u8; 32000]);
        std::fs::write(&wav,&bytes).unwrap();
        let backend=FixtureCompanionBackend::new();
        install_recovery_session(&backend,"unconfirmed-host",&wav);
        let row={
            let mut snapshot=backend.snapshot.lock().unwrap();
            let s=&mut snapshot.host.sessions[0];
            s.source="hostMicrophone".into();
            s.status="captured".into();
            s.audio_stored=false;
            s.audio_bytes=0;
            s.retention.audio_cached=false;
            s.capture_incomplete=false;
            s.transcript_text="existing partial".into();
            s.recovery=CompanionV1MeetingRecovery::armed("offlineStore");
            s.recovery.stage="retryBackoff".into();
            s.recovery.retry_stage="transcription".into();
            s.recovery.next_retry_at_unix_ms=None;
            s.pending_reason=Some("recovery_retry_wait".into());
            s.chunks[0].status="open".into();
            s.clone()
        };
        persistence::save_sessions_to(&persistence::state_file_path(),&[row]).unwrap();
        drop(backend);
        let restarted=FixtureCompanionBackend::new();
        let after=restarted.apply_control(recovery_request(CompanionV1ControlAction::MeetingTranscribeAudio,"unconfirmed-host",true)).unwrap();
        let row=&after.host.sessions[0];
        assert!(!row.transcript_final,"unconfirmed host recording was submitted for transcription");
        assert_eq!(row.recovery.attempt_count,0,"unconfirmed recording consumed retry budget");
        assert_eq!(row.recovery.stage,"paused");
        assert_eq!(row.transcript_text,"existing partial");
        assert_eq!(std::fs::read(&wav).unwrap(),bytes,"original recording changed");
        assert!(restarted.apply_control(recovery_request(CompanionV1ControlAction::MeetingTranscribeAudio,"unconfirmed-host",false)).is_err());
        {
            let mut snapshot=restarted.snapshot.lock().unwrap();
            let row=&mut snapshot.host.sessions[0];
            row.audio_stored=true;
            row.audio_bytes=bytes.len() as u64;
            row.retention.audio_cached=true;
            row.chunks[0].status="sealed".into();
            row.recovery=CompanionV1MeetingRecovery::armed("offlineStore");
        }
        let saved=restarted.apply_control(recovery_request(CompanionV1ControlAction::MeetingTranscribeAudio,"unconfirmed-host",false)).unwrap();
        assert!(saved.host.sessions[0].transcript_final,"confirmed host recording should still transcribe");
        assert_eq!(saved.host.sessions[0].transcript_text,"Synthetic forbidden result");
        assert_eq!(std::fs::read(&wav).unwrap(),bytes);
        {
            let mut snapshot=restarted.snapshot.lock().unwrap();
            let row=&mut snapshot.host.sessions[0];
            row.audio_stored=false;
            row.retention.audio_cached=false;
            row.recovery.stage="retryBackoff".into();
            row.recovery.retry_stage="minutes".into();
            persistence::reconcile_session_recovery(row);
            assert_eq!(row.recovery.stage,"retryBackoff","saved final text remains available for minutes");
            assert!(row.transcript_final);
        }
    }

    #[test]
    #[ignore]
    fn isolated_host_start_exit_child() {
        use super::*;
        if std::env::var_os("COMPANION_TEST_HOST_START_EXIT").is_none() { return; }
        let backend=FixtureCompanionBackend::new();
        let request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some("start-crash-owned".into()));
        backend.apply_control(request).unwrap();
        panic!("the injected process exit did not happen");
    }

    #[test]
    #[ignore]
    fn isolated_host_start_failure_child() {
        use super::*;
        if std::env::var_os("COMPANION_TEST_HOST_START_FAILURE").is_none() { return; }
        let backend=FixtureCompanionBackend::new();
        let request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some("start-failed-owned".into()));
        assert!(backend.apply_control(request).is_err());
        let saved=super::persistence::load_sessions_from(&super::persistence::state_file_path()).unwrap();
        let row=saved.iter().find(|s|s.id=="start-failed-owned").expect("partial audio owner retained");
        assert_ne!(row.status,"recording","failed start must not claim a live recording");
        assert!(!row.audio_stored && row.capture_incomplete);
        assert!(std::path::Path::new(row.audio_path.as_deref().unwrap()).is_file(),"partial original retained");
        let original_path=std::path::PathBuf::from(row.audio_path.as_deref().unwrap());
        let original_bytes=std::fs::read(&original_path).unwrap();
        {
            let snapshot=backend.snapshot.lock().unwrap();
            assert!(!snapshot.meeting.active);
            assert!(snapshot.host.sessions.iter().any(|s|s.id==row.id && s.status!="recording"));
        }
        let restore=crate::control_request(CompanionV1ControlAction::MeetingRestoreAudio,Some(row.id.clone()));
        let restored=backend.apply_control(restore).unwrap();
        let restored_row=restored.host.sessions.iter().find(|s|s.id==row.id).unwrap();
        assert!(restored_row.audio_stored && restored_row.capture_incomplete);
        let recovered=std::fs::read(restored_row.audio_path.as_deref().unwrap()).unwrap();
        assert_eq!(&recovered[44..],&original_bytes[44..]);
        assert_eq!(std::fs::read(&original_path).unwrap(),original_bytes);
    }

    #[test]
    fn failed_host_start_retains_partial_owner_without_claiming_recording() {
        let root=std::env::temp_dir().join(format!("host-start-failure-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("recordings")).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_host_start_failure_child","--ignored"])
            .env("COMPANION_TEST_HOST_START_FAILURE","1").env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_RECORDING_DIR",root.join("recordings")).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
    }

    #[test]
    #[ignore]
    fn isolated_host_duplicate_session_child() {
        use super::*;
        let Some(root)=std::env::var_os("COMPANION_TEST_DUPLICATE_ROOT") else { return; };
        let root=std::path::PathBuf::from(root); let existing=root.join("recordings/existing.wav");
        std::fs::write(&existing,b"original already saved").unwrap();
        let mut fixture=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(CompanionV1ControlAction::MeetingStart,Some("existing-owned".into()))).unwrap();
        let mut row=fixture.host.sessions.remove(0);row.id="existing-owned".into();row.status="captured".into();
        row.source="hostMicrophone".into();row.audio_path=Some(existing.to_string_lossy().into_owned());
        row.audio_stored=true;row.audio_bytes=22;row.retention.audio_cached=true;row.chunks.clear();
        super::persistence::save_sessions_to(&super::persistence::state_file_path(),&[row]).unwrap();
        let before=std::fs::read(super::persistence::state_file_path()).unwrap();
        let backend=FixtureCompanionBackend::new();
        let request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some("existing-owned".into()));
        assert!(backend.apply_control(request).is_err());
        assert_eq!(std::fs::read(super::persistence::state_file_path()).unwrap(),before);
        assert_eq!(std::fs::read(&existing).unwrap(),b"original already saved");
        let wavs=std::fs::read_dir(root.join("recordings")).unwrap().map(|e|e.unwrap().path())
            .filter(|p|p.extension().is_some_and(|x|x=="wav")).count();
        assert_eq!(wavs,1,"duplicate start cannot create an orphan file");
    }

    #[test]
    fn duplicate_host_start_preserves_saved_session_and_original() {
        let root=std::env::temp_dir().join(format!("host-duplicate-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("recordings")).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_host_duplicate_session_child","--ignored"])
            .env("COMPANION_TEST_DUPLICATE_ROOT",&root).env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_RECORDING_DIR",root.join("recordings")).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
    }

    #[test]
    #[ignore]
    fn isolated_host_start_stop_child() {
        use super::*;
        if std::env::var_os("COMPANION_TEST_START_STOP").is_none() { return; }
        let backend=FixtureCompanionBackend::new();
        let id="durable-start-stop";
        let started=backend.apply_control(crate::control_request(CompanionV1ControlAction::MeetingStart,Some(id.into()))).unwrap();
        let active=started.host.sessions.iter().find(|r|r.id==id).unwrap();
        assert_eq!(active.status,"recording"); assert!(!active.audio_stored);
        let disk:Vec<crate::companion_v1::CompanionV1HostSession>=serde_json::from_slice(&std::fs::read(super::persistence::state_file_path()).unwrap()).unwrap();
        let saved=disk.iter().find(|r|r.id==id).unwrap();
        assert_eq!(saved.status,"recording"); assert_eq!(saved.audio_path,active.audio_path);
        let stopped=backend.apply_control(crate::control_request(CompanionV1ControlAction::MeetingStop,Some(id.into()))).unwrap();
        let row=stopped.host.sessions.iter().find(|r|r.id==id).unwrap();
        assert_eq!(row.status,"captured");assert!(row.audio_stored && row.audio_bytes>44);
        let file=std::path::Path::new(row.audio_path.as_deref().unwrap());
        super::meeting_workspace::validate_wav(file).unwrap();
        let reloaded=FixtureCompanionBackend::new();let snapshot=reloaded.snapshot.lock().unwrap();
        let saved=snapshot.host.sessions.iter().find(|r|r.id==id).unwrap();
        assert!(saved.audio_stored);assert_eq!(saved.audio_path,row.audio_path);
    }

    #[test]
    fn host_start_and_stop_preserve_index_and_real_saved_wav() {
        let root=std::env::temp_dir().join(format!("host-start-stop-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("recordings")).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_host_start_stop_child","--ignored"])
            .env("COMPANION_TEST_START_STOP","1").env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_RECORDING_DIR",root.join("recordings")).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
    }

    #[test]
    #[ignore]
    fn isolated_cancelled_meeting_recovery_child() {
        if std::env::var_os("COMPANION_TEST_CANCELLED_RECOVERY").is_none() { return; }
        for (stage,message) in [("transcribing",meeting_processing_job::TRANSCRIPTION_CANCELLED),
            ("generatingMinutes",meeting_processing_job::MINUTES_CANCELLED)] {
            let mut snapshot=apply_fixture_control(fixture_snapshot(),
                recovery_request(CompanionV1ControlAction::MeetingStart,"cancelled-meeting",false)).unwrap();
            let row=&mut snapshot.host.sessions[0];
            row.status="captured".into();row.source="boardDevice".into();
            row.meeting_mode="offlineStore".into();
            row.recovery=CompanionV1MeetingRecovery::armed("offlineStore");
            row.recovery.stage=stage.into();row.recovery.attempt_count=1;
            if stage=="generatingMinutes" {row.transcript_text="示例会议原文".into();row.transcript_final=true;}
            let id=row.id.clone();
            pause_cancelled_meeting_work(&mut snapshot,&id,stage,message).unwrap();
            let mut reopened:Vec<CompanionV1HostSession>=serde_json::from_slice(
                &std::fs::read(persistence::state_file_path()).unwrap()).unwrap();
            let saved=reopened.iter_mut().find(|row|row.id==id).unwrap();
            assert_eq!(saved.recovery.stage,"paused");assert_eq!(saved.recovery.attempt_count,1);
            assert_eq!(saved.recovery.last_error.as_deref(),Some(message));
            persistence::reconcile_session_recovery(saved);
            assert_eq!(saved.recovery.stage,"paused");assert!(saved.recovery.next_retry_at_unix_ms.is_none());
        }
        // A failed stop-state save keeps the app open; a later close retries
        // the same in-memory state after storage access has been restored.
        let index=persistence::state_file_path();let backup=index.with_extension("cancel-test-backup");
        let backend=FixtureCompanionBackend::new();
        std::fs::rename(&index,&backup).unwrap();std::fs::create_dir(&index).unwrap();
        {let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.persistence.status="unsaved".into();}
        assert!(backend.finish_meeting_processing_on_exit(std::time::Duration::from_secs(1)).is_err());
        std::fs::remove_dir(&index).unwrap();std::fs::rename(&backup,&index).unwrap();
        backend.finish_meeting_processing_on_exit(std::time::Duration::from_secs(1)).unwrap();
        assert_eq!(backend.snapshot().unwrap().host.persistence.status,"ready");
    }

    #[test]
    fn cancelled_meeting_stays_paused_after_restart_and_failed_save_can_retry() {
        let root=std::env::temp_dir().join(format!("meeting-cancel-exit-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_cancelled_meeting_recovery_child","--ignored"])
            .env("COMPANION_TEST_CANCELLED_RECOVERY","1").env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
    }

    #[test]
    #[ignore]
    fn isolated_shutdown_host_capture_child() {
        if std::env::var_os("COMPANION_TEST_SHUTDOWN_HOST").is_none() { return; }
        let backend=FixtureCompanionBackend::new();
        // An independently recording board has no owned host microphone.
        {let mut s=backend.snapshot.lock().unwrap();s.device.recording=true;s.meeting.active=true;}
        let before=serde_json::to_vec(&backend.snapshot().unwrap()).unwrap();
        backend.finish_host_recording_on_exit().unwrap();
        assert_eq!(serde_json::to_vec(&backend.snapshot().unwrap()).unwrap(),before);
        {let mut s=backend.snapshot.lock().unwrap();s.device.recording=false;s.meeting.active=false;}
        let id="exit-host-recording";
        let mut request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some(id.into()));
        request.meeting_mode=Some("onlineLive".into());
        backend.apply_control(request).unwrap();
        backend.finish_host_recording_on_exit().unwrap();
        let stopped=backend.snapshot().unwrap();
        let row=stopped.host.sessions.iter().find(|r|r.id==id).unwrap();
        assert_eq!(row.status,"captured");assert!(row.audio_stored && row.audio_bytes>44);
        assert!(row.transcript_text.is_empty());
        assert!(!stopped.last_control.as_ref().unwrap().message.contains("fallback batch"));
        super::meeting_workspace::validate_wav(std::path::Path::new(row.audio_path.as_deref().unwrap())).unwrap();
        backend.finish_host_recording_on_exit().unwrap();
        let reopened=FixtureCompanionBackend::new().snapshot().unwrap();
        let saved=reopened.host.sessions.iter().find(|r|r.id==id).unwrap();
        assert!(saved.audio_stored);assert_eq!(saved.audio_path,row.audio_path);

        // A temporary failure writing the index must not be reported as a
        // successful exit. Restore the original test index, then retry.
        let second="exit-with-index-failure";
        backend.apply_control(crate::control_request(CompanionV1ControlAction::MeetingStart,Some(second.into()))).unwrap();
        let index=super::persistence::state_file_path();let backup=index.with_extension("exit-test-backup");
        std::fs::rename(&index,&backup).unwrap();std::fs::create_dir(&index).unwrap();
        assert!(backend.finish_host_recording_on_exit().is_err());
        assert_eq!(backend.shutdown_host_recording.lock().unwrap().as_deref(),Some(second));
        std::fs::remove_dir(&index).unwrap();std::fs::rename(&backup,&index).unwrap();
        backend.finish_host_recording_on_exit().unwrap();
        let recovered=FixtureCompanionBackend::new().snapshot().unwrap();
        assert!(recovered.host.sessions.iter().find(|r|r.id==second).unwrap().audio_stored);
    }

    #[test]
    fn shutdown_saves_owned_host_audio_without_touching_the_board() {
        let root=std::env::temp_dir().join(format!("host-exit-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("recordings")).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_shutdown_host_capture_child","--ignored"])
            .env("COMPANION_TEST_SHUTDOWN_HOST","1").env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_RECORDING_DIR",root.join("recordings")).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_LIVE_ASR_OFF","1").env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1")
            .env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
    }

    #[test]
    #[ignore]
    fn isolated_host_stale_library_child() {
        use super::*;
        if std::env::var_os("COMPANION_TEST_STALE_LIBRARY").is_none() { return; }
        let state=super::persistence::state_file_path();
        let mut fixture=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(CompanionV1ControlAction::MeetingStart,Some("deleted-owned".into()))).unwrap();
        let mut old=fixture.host.sessions.remove(0);old.id="deleted-owned".into();old.status="captured".into();
        old.audio_stored=false;old.audio_path=None;old.retention.audio_cached=false;old.chunks.clear();
        super::persistence::save_sessions_to(&state,&[old]).unwrap();
        let backend=FixtureCompanionBackend::new();
        // Model an explicit deletion by a different process after this snapshot was loaded.
        super::persistence::save_sessions_to(&state,&[]).unwrap();
        let request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some("new-owned".into()));
        assert!(backend.apply_control(request).is_err(),"a stale snapshot must not resurrect a deleted meeting");
        let current=super::persistence::load_sessions_from(&state).unwrap();
        assert!(current.is_empty(),"deleted meeting and attempted new meeting remain absent");
    }

    #[test]
    fn host_start_rejects_stale_library_after_other_process_deletion() {
        let root=std::env::temp_dir().join(format!("host-stale-library-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("recordings")).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_host_stale_library_child","--ignored"])
            .env("COMPANION_TEST_STALE_LIBRARY","1").env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_RECORDING_DIR",root.join("recordings")).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
    }

    #[test]
    #[ignore]
    fn isolated_host_legacy_minutes_child() {
        use super::*;
        if std::env::var_os("COMPANION_TEST_LEGACY_MINUTES").is_none() { return; }
        let mut fixture=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(CompanionV1ControlAction::MeetingStart,Some("older-meeting".into()))).unwrap();
        let mut row=fixture.host.sessions.remove(0);row.status="captured".into();
        row.minutes=Some(crate::companion_v1::CompanionV1MeetingMinutes {
            processing:None,source_note_context:None,source_review_revision:None,
            generated_at:"test".into(),source:"rules_l0".into(),quality:"draft".into(),
            summary:vec![],decisions:vec![],action_items:vec![],questions:vec![],keywords:vec![],
            markdown:"prior notes".into(),llm_note:None,
        });
        row.minutes_by_mode=Default::default();
        super::persistence::save_sessions_to(&super::persistence::state_file_path(),&[row]).unwrap();
        let backend=FixtureCompanionBackend::new();
        let request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some("new-legacy-test".into()));
        assert!(backend.apply_control(request).is_ok(),"normal legacy migration must not block a new recording");
        let disk=super::persistence::load_sessions_from(&super::persistence::state_file_path()).unwrap();
        assert!(disk.iter().any(|r|r.id=="older-meeting" && r.minutes.as_ref().is_some_and(|m|m.markdown=="prior notes")));
        assert!(disk.iter().any(|r|r.id=="new-legacy-test"));
    }

    #[test]
    fn host_start_accepts_unchanged_legacy_minutes_after_migration() {
        let root=std::env::temp_dir().join(format!("host-legacy-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("recordings")).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_host_legacy_minutes_child","--ignored"])
            .env("COMPANION_TEST_LEGACY_MINUTES","1").env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_RECORDING_DIR",root.join("recordings")).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
    }

    #[test]
    #[ignore]
    fn isolated_host_privacy_lock_child() {
        use super::*;
        if std::env::var_os("COMPANION_TEST_START_PRIVACY_LOCK").is_none() { return; }
        let state=super::persistence::state_file_path();
        let backend=FixtureCompanionBackend::new();
        let guard=super::library_lifecycle::action_lock(&state).unwrap();
        let mut request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some("lock-test".into()));
        request.meeting_mode=Some("onlineLive".into());
        assert!(backend.apply_control(request).is_err());
        assert!(!state.exists(),"no session is saved while privacy operation owns the library");
        assert!(!backend.snapshot.lock().unwrap().meeting.active);
        drop(guard);
    }

    #[test]
    fn host_start_waits_for_privacy_action_before_live_or_capture() {
        let root=std::env::temp_dir().join(format!("host-privacy-lock-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("recordings")).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_host_privacy_lock_child","--ignored"])
            .env("COMPANION_TEST_START_PRIVACY_LOCK","1").env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_RECORDING_DIR",root.join("recordings")).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
        assert!(!std::fs::read_dir(root.join("recordings")).unwrap().any(|entry|entry.unwrap().path().extension().is_some_and(|e|e=="wav")));
    }

    #[test]
    #[ignore]
    fn isolated_host_index_failure_child() {
        use super::*;
        if std::env::var_os("COMPANION_TEST_START_INDEX_FAILURE").is_none() { return; }
        let state=super::persistence::state_file_path();
        let backend=FixtureCompanionBackend::new();
        std::fs::create_dir(&state).unwrap();
        let request=crate::control_request(CompanionV1ControlAction::MeetingStart,Some("storage-failure".into()));
        assert!(backend.apply_control(request).is_err(),"cannot start without durable session ownership");
        assert!(!backend.snapshot.lock().unwrap().meeting.active);
    }

    #[test]
    fn host_start_does_not_open_audio_when_index_cannot_be_saved() {
        let root=std::env::temp_dir().join(format!("host-index-fail-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("recordings")).unwrap();
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_host_index_failure_child","--ignored"])
            .env("COMPANION_TEST_START_INDEX_FAILURE","1").env("COMPANION_TYPE_STATE_PATH",root.join("sessions.json"))
            .env("COMPANION_TYPE_RECORDING_DIR",root.join("recordings")).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}\n{}",String::from_utf8_lossy(&child.stdout),String::from_utf8_lossy(&child.stderr));
        assert!(!std::fs::read_dir(root.join("recordings")).unwrap().any(|entry|entry.unwrap().path().extension().is_some_and(|e|e=="wav")));
    }

    #[test]
    fn host_start_persists_owner_before_audio_can_arrive() {
        let root=std::env::temp_dir().join(format!("host-start-crash-{}",uuid::Uuid::new_v4()));
        let recordings=root.join("recordings");std::fs::create_dir_all(&recordings).unwrap();
        let state=root.join("sessions.json");
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::tests::isolated_host_start_exit_child","--ignored"])
            .env("COMPANION_TEST_HOST_START_EXIT","1").env("COMPANION_TYPE_STATE_PATH",&state)
            .env("COMPANION_TYPE_RECORDING_DIR",&recordings).env("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic")
            .env("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1").env("COMPANION_TYPE_BLE_NATIVE_DISABLED","1").output().unwrap();
        assert!(child.status.success(),"{}",String::from_utf8_lossy(&child.stderr));
        assert!(!String::from_utf8_lossy(&child.stdout).contains("test result:"),"failure injection did not exit");
        let wavs:Vec<_>=std::fs::read_dir(&recordings).unwrap().map(|e|e.unwrap().path())
            .filter(|p|p.extension().is_some_and(|x|x=="wav")).collect();
        assert_eq!(wavs.len(),1);assert_eq!(std::fs::read(&wavs[0]).unwrap().len(),32044);
        assert!(recordings.join(".audio-artifacts.json").exists());
        let saved=super::persistence::load_sessions_from(&state).unwrap_or_default();
        let row=saved.iter().find(|s|s.id=="start-crash-owned").expect("the active recording must have a durable meeting owner before PCM arrives");
        assert_eq!(super::audio_artifacts::reference_key(std::path::Path::new(row.audio_path.as_deref().unwrap())).unwrap(),
            super::audio_artifacts::reference_key(&wavs[0]).unwrap());
        assert!(!row.audio_stored);
        let original=std::fs::read(&wavs[0]).unwrap();
        std::env::set_var("COMPANION_TYPE_STATE_PATH",&state);
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&recordings);
        let backend=super::FixtureCompanionBackend::new();
        let restore=crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingRestoreAudio,Some("start-crash-owned".into()));
        let snapshot=super::CompanionBackend::apply_control(&backend,restore).unwrap();
        let restored=snapshot.host.sessions.iter().find(|s|s.id=="start-crash-owned").unwrap();
        assert!(restored.audio_stored && restored.capture_incomplete);
        let recovered=std::fs::read(restored.audio_path.as_deref().unwrap()).unwrap();
        assert_eq!(&recovered[44..],&original[44..]);
        assert_eq!(std::fs::read(&wavs[0]).unwrap(),original,"the original remains unchanged");
        std::env::remove_var("COMPANION_TYPE_STATE_PATH");
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
    }

    #[test]
    fn p582_persisted_control_refuses_demo_before_touching_existing_rows_or_recording_state() {
        let backend=FixtureCompanionBackend::new();
        {let mut snapshot=backend.snapshot.lock().unwrap();snapshot.host.persistence.status="blocked".into();snapshot.meeting.active=true;snapshot.device.recording=true;}
        let before=serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap();
        for source in ["fixture","hostMicrophone","boardDevice"] {
            let request=serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo","sessionId":"existing-record-must-not-be-replaced","title":source,"transcriptText":"fabricated","audioPath":"C:/not-opened.wav","audioBytes":4096,"durationMs":15000})).unwrap();
            assert_eq!(backend.apply_control(request).unwrap_err(),"演示只在隔离预览中可用，不会添加到本机录音库。");
            assert_eq!(serde_json::to_value(&*backend.snapshot.lock().unwrap()).unwrap(),before);
        }
    }
    #[test]
    fn p582_pure_isolated_demo_reducer_and_ordinary_selection_remain_available() {
        let snapshot=apply_fixture_control(fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo","sessionId":"isolated-only","title":"Isolated example","transcriptText":"明确虚构示例内容"})).unwrap()).unwrap();
        assert_eq!(snapshot.host.sessions[0].id,"isolated-only");
        let selected=apply_fixture_control(snapshot,serde_json::from_value(serde_json::json!({"action":"meetingSelectSession","sessionId":"isolated-only"})).unwrap()).unwrap();
        assert_eq!(selected.host.selected_session_id.as_deref(),Some("isolated-only"));
    }
    #[test]
    fn connect_transport_failure_reloads_durable_partials_without_stopping_original_or_rewriting_index() {
        let root=std::env::temp_dir().join(format!("companion-connect-result-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let index=root.join("sessions.json");
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            serde_json::from_value(serde_json::json!({"action":"meetingStart","sessionId":"ongoing-original"})).unwrap()).unwrap();
        snapshot.host.sessions[0].source="boardDevice".into();snapshot.device.recording=true;
        let mut partial=snapshot.host.sessions[0].clone();partial.id="saved-partial".into();partial.status="pending".into();
        partial.audio_stored=false;partial.device_reclaimed=false;partial.title="Original name retained".into();
        let mut durable=snapshot.host.sessions.clone();durable.push(partial.clone());
        session_store::save(&index,&durable).unwrap();let before=std::fs::read(&index).unwrap();
        let operation=CompanionBleOperation{provider_id:"companion-type-windows-ble".into(),
            mode:"windows-native-connect-auto-upload-segmented".into(),ready:false,sync_paused:false,
            device_id:Some("C8:92:FF:DD:3B:CA".into()),recording_path:None,recordings:Vec::new(),device_identity:None,
            message:"id18 offset2081: native GATT session lost".into()};
        let error=observe_failed_device_connect(&mut snapshot,&operation,&index);
        assert_eq!(error,operation.message);assert!(!snapshot.connected&&!snapshot.device.connected);
        assert_eq!(snapshot.device.connection_phase,"offline");assert_eq!(snapshot.device.message,error);
        assert!(!snapshot.last_control.as_ref().unwrap().accepted);
        assert_eq!(snapshot.last_control.as_ref().unwrap().action,CompanionV1ControlAction::DeviceConnect);
        assert!(snapshot.device.recording&&snapshot.meeting.active);
        assert_eq!(snapshot.host.active_session_id.as_deref(),Some("ongoing-original"));
        let loaded=snapshot.host.sessions.iter().find(|r|r.id==partial.id).unwrap();
        assert_eq!(serde_json::to_vec(loaded).unwrap(),serde_json::to_vec(&partial).unwrap());
        assert_eq!(std::fs::read(&index).unwrap(),before,"failure observation cannot consume or complete the saved partial");
        let retained=serde_json::to_vec(&snapshot.host.sessions).unwrap();
        assert!(observe_failed_device_connect(&mut snapshot,&operation,&root.join("missing.json")).contains("待重新读取"));
        assert_eq!(serde_json::to_vec(&snapshot.host.sessions).unwrap(),retained);
        std::fs::remove_file(&index).unwrap();
        for entry in std::fs::read_dir(&root).unwrap(){std::fs::remove_file(entry.unwrap().path()).unwrap();}
        std::fs::remove_dir(&root).unwrap();
    }

    #[test]
    fn manual_processing_policy_blocks_stale_automatic_work_but_accepts_manual_transcribe() {
        use super::*;
        use crate::companion_v1::{CAPTURE_ONLY_PROMPT,CompanionV1ProcessingPolicy};
        let mut start=crate::control_request(CompanionV1ControlAction::MeetingStart,Some("manual-policy".into()));
        start.prompt_id=Some(CAPTURE_ONLY_PROMPT.into());
        let mut state=apply_fixture_control(fixture_snapshot(),start).unwrap();
        state.host.active_session_id=None;state.meeting.active=false;state.device.recording=false;
        let row=&mut state.host.sessions[0];row.status="captured".into();row.audio_stored=true;
        row.audio_path=Some("manual-policy-unit-does-not-exist.wav".into());
        assert_eq!(row.processing_policy,CompanionV1ProcessingPolicy::Manual);
        arm_meeting_recovery(row);assert_eq!(row.recovery.intent,"none");
        // An interrupted capture or stale queued request may still carry an
        // armed recovery. The durable policy independently forbids auto work.
        row.recovery=CompanionV1MeetingRecovery::armed("offlineStore");
        let before=serde_json::to_value(&state).unwrap();
        let backend=FixtureCompanionBackend::new();*backend.snapshot.lock().unwrap()=state;
        let skipped=backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingTranscribeAudio,"manual-policy",true)).unwrap();
        assert_eq!(serde_json::to_value(&skipped).unwrap(),before);
        let attempted=backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingTranscribeAudio,"manual-policy",false)).unwrap();
        let row=attempted.host.sessions.iter().find(|r|r.id=="manual-policy").unwrap();
        assert_eq!(row.processing_policy,CompanionV1ProcessingPolicy::Manual);
        assert_eq!(row.recovery.stage,"paused");assert!(row.recovery.last_error.is_some());
        assert!(row.recovery.next_retry_at_unix_ms.is_none());
    }

    #[test]
    fn recording_library_scope_legacy_recovery_never_replaces_segmented_original() {
        let snapshot=super::apply_fixture_control(super::fixture_snapshot(),crate::control_request(
            crate::companion_v1::CompanionV1ControlAction::MeetingStart,Some("owner".into()))).unwrap();
        let mut legacy=snapshot.host.sessions.into_iter().find(|row|row.id=="owner").unwrap();
        legacy.device_recording_id=Some(3);legacy.device_recording_key=None;legacy.recorder_control=None;
        assert_eq!(super::legacy_recording_recovery_owner(&[legacy.clone()],3).unwrap(),0);
        let mut current=legacy.clone();current.id="new-original".into();
        current.device_recording_key=Some(crate::companion_v1::CompanionV1RecordingKey {
            device_uid:"180010000d50335754363720".into(),format_epoch:"5f72b599c3872a1f".into(),session_id:"0000000000000003".into()});
        assert!(super::legacy_recording_recovery_owner(&[current.clone()],3).unwrap_err().contains("Segmented originals"));
        assert!(super::legacy_recording_recovery_owner(&[legacy.clone(),current],3).unwrap_err().contains("ambiguous"));
        legacy.device_recording_id=None;legacy.meeting_mode="onlineLive".into();legacy.status="captured".into();legacy.audio_path=Some("board://pending".into());
        assert_eq!(super::legacy_recording_recovery_owner(&[legacy.clone()],3).unwrap(),0);
        let mut another=legacy.clone();another.id="another-pending".into();
        assert!(super::legacy_recording_recovery_owner(&[legacy,another],3).is_err());
    }

    #[test]
    fn legacy_recovery_preserves_later_recording() {
        let root=std::env::temp_dir().join(format!("companion-legacy-race-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap(); let path=root.join("sessions.json");
        let wav=root.join("fixture-device-recording-3.wav");
        // A tiny, private PCM WAV plus a separate nonempty fake Opus file.
        let mut bytes=Vec::new(); bytes.extend_from_slice(b"RIFF"); bytes.extend_from_slice(&38u32.to_le_bytes());
        bytes.extend_from_slice(b"WAVEfmt "); bytes.extend_from_slice(&16u32.to_le_bytes());
        bytes.extend_from_slice(&1u16.to_le_bytes()); bytes.extend_from_slice(&1u16.to_le_bytes());
        bytes.extend_from_slice(&16000u32.to_le_bytes()); bytes.extend_from_slice(&32000u32.to_le_bytes());
        bytes.extend_from_slice(&2u16.to_le_bytes()); bytes.extend_from_slice(&16u16.to_le_bytes());
        bytes.extend_from_slice(b"data"); bytes.extend_from_slice(&2u32.to_le_bytes()); bytes.extend_from_slice(&[0,0]);
        std::fs::write(&wav,&bytes).unwrap();std::fs::write(wav.with_extension("opus"),b"fictional").unwrap();
        let snapshot=super::apply_fixture_control(super::fixture_snapshot(),crate::control_request(
            crate::companion_v1::CompanionV1ControlAction::MeetingStart,Some("owner".into()))).unwrap();
        let mut original=snapshot.host.sessions.into_iter().find(|row|row.id=="owner").unwrap();
        original.device_recording_id=Some(3);original.device_recording_key=None;original.recorder_control=None;
        super::session_store::save(&path,&[original.clone()]).unwrap();
        let mut later=original.clone();later.id="new-recording".into();later.device_recording_id=Some(4);
        super::session_store::update_checked(&path,|rows|{rows.push(later);Ok(())}).unwrap();
        assert_eq!(super::recover_persisted_board_recording_at(3,&wav,&path).unwrap(),"owner");
        let rows=super::persistence::load_sessions_from(&path).unwrap();
        assert!(rows.iter().any(|row|row.id=="new-recording"));
        let recovered=rows.iter().find(|row|row.id=="owner").unwrap();
        assert!(recovered.audio_stored && recovered.retention.audio_cached);
        assert_eq!(recovered.device_recording_id,Some(3));
        let primary=std::fs::read(&path).unwrap();let backup=std::fs::read(root.join("sessions.json.bak")).unwrap();
        assert_eq!(primary,backup,"device data must remain recoverable from the backup");
        // A conflicting second owner must fail without changing either copy.
        let mut conflict=rows[0].clone();conflict.id="conflict".into();conflict.device_recording_id=Some(3);
        super::session_store::update_checked(&path,|rows|{rows.push(conflict);Ok(())}).unwrap();
        let before=std::fs::read(&path).unwrap();let before_backup=std::fs::read(root.join("sessions.json.bak")).unwrap();
        assert!(super::recover_persisted_board_recording_at(3,&wav,&path).is_err());
        assert_eq!(std::fs::read(&path).unwrap(),before);assert_eq!(std::fs::read(root.join("sessions.json.bak")).unwrap(),before_backup);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn stop_retry_keeps_durable_audio_without_inventing_physical_consumption() {
        let source = "C8:92:FF:DD:3B:CA";
        let operation = |ready, device_id: Option<&str>, reclaimed: Option<bool>| {
            super::ble_bridge::CompanionBleOperation {
                provider_id: "companion-type-windows-ble".into(),
                mode: "windows-native-recording-pull".into(), ready, sync_paused: false,
                device_id: device_id.map(str::to_string), recording_path: None,
                recordings: reclaimed.map(|device_reclaimed| super::CompanionSyncedRecording {
                    recording_id: 16, duration_ms: 300_420, total_length: 630_894,
                    sha256: "59".repeat(32), recording_path: "original.wav".into(),
                    device_reclaimed, capture_incomplete: false,
                }).into_iter().collect(), device_identity: None,
                message: "latest attempt".into(),
            }
        };
        let pending = operation(true, Some(source), Some(false));
        let failed = super::retain_stopped_recording_checkpoint(
            &pending, operation(false, None, None), source, 16);
        assert!(failed.ready);
        assert_eq!(failed.recording_path.as_deref(), Some("original.wav"));
        assert_eq!(failed.recordings.len(), 1);
        assert!(!failed.recordings[0].device_reclaimed);
        let absent = super::retain_stopped_recording_checkpoint(
            &failed, operation(true, Some(source), None), source, 16);
        assert!(!absent.recordings[0].device_reclaimed, "directory absence is not an ACK");
        let confirmed = super::retain_stopped_recording_checkpoint(
            &absent, operation(true, Some(source), Some(true)), source, 16);
        assert!(confirmed.recordings[0].device_reclaimed);
        let other = super::retain_stopped_recording_checkpoint(
            &pending, operation(false, Some("AA:BB:CC:DD:EE:FF"), None), source, 16);
        assert!(!other.ready);
        assert!(other.recordings.is_empty(), "never move a receipt across device identities");
    }

    #[test]
    fn offline_duration_is_preserved_and_invalid_input_is_rejected() {
        assert_eq!(super::recording_duration_seconds(Some(60*60*1000)).unwrap(),3600);
        assert_eq!(super::recording_duration_seconds(Some(1001)).unwrap(),2);
        assert!(super::recording_duration_seconds(Some(0)).is_err());
        assert!(super::recording_duration_seconds(Some(u64::MAX)).is_err());
    }
    #[test]
    fn incomplete_capture_preserves_audio_and_pauses_automatic_processing() {
        let mut snapshot = super::apply_fixture_control(
            super::fixture_snapshot(),
            recovery_request(super::CompanionV1ControlAction::MeetingStart, "partial-capture", false),
        ).unwrap();
        let session = &mut snapshot.host.sessions[0];
        let path = std::env::temp_dir().join(format!("valid-partial-{}.wav", uuid::Uuid::new_v4()));
        let wav = denzic_host_audio_v1_core::wav::encode_wav(&[100i16, -100, 50]);
        std::fs::write(&path, &wav).unwrap();
        session.audio_path = Some(path.to_string_lossy().to_string());
        session.audio_bytes = wav.len() as u64;
        session.transcript_final = true;
        session.recovery = super::CompanionV1MeetingRecovery::armed("offlineStore");
        session.recovery.capture_review_confirmed = true;
        super::pause_incomplete_host_recording(session, "麦克风已拔出", false);
        assert_eq!(session.audio_path.as_deref(), path.to_str());
        assert!(session.audio_stored);
        assert!(session.capture_incomplete, "the interruption must remain visible after processing and restart");
        assert!(!session.recovery.capture_review_confirmed, "a new interruption must require explicit review");
        assert!(!session.transcript_final);
        assert_eq!(session.status, "captured");
        assert_eq!(session.recovery.stage, "paused");
        assert!(session.recovery.next_retry_at_unix_ms.is_none());
        assert!(session.recovery.last_error.as_ref().unwrap().contains("麦克风已拔出"));
        let mut reopened: super::CompanionV1HostSession = serde_json::from_slice(&serde_json::to_vec(session).unwrap()).unwrap();
        super::persistence::reconcile_session_recovery(&mut reopened);
        assert!(reopened.capture_incomplete && !reopened.recovery.capture_review_confirmed);
        assert_eq!(reopened.recovery.stage, "paused");
        assert!(reopened.recovery.next_retry_at_unix_ms.is_none());
        reopened.audio_path = Some(path.with_file_name("missing-partial.wav").to_string_lossy().to_string());
        assert!(super::interrupted_capture::confirm(&mut reopened).is_err());
        assert!(!reopened.recovery.capture_review_confirmed);
    }

    #[test]
    fn host_save_failure_never_claims_an_invalid_file_is_playable() {
        let root=std::env::temp_dir().join(format!("host-invalid-capture-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let file=root.join("interrupted.wav");
        let mut raw=denzic_host_audio_v1_core::wav::wav_header(0).to_vec();
        raw.extend(vec![42u8;32000]);
        std::fs::write(&file,&raw).unwrap();
        let mut snapshot = super::apply_fixture_control(super::fixture_snapshot(),
            recovery_request(super::CompanionV1ControlAction::MeetingStart, "invalid-host", false)).unwrap();
        let session=&mut snapshot.host.sessions[0];
        session.audio_path=Some(file.to_string_lossy().to_string());session.audio_bytes=raw.len() as u64;
        session.audio_stored=true;session.retention.audio_cached=true;
        super::pause_incomplete_host_recording(session,"录音文件保存失败",false);
        assert!(!session.audio_stored, "a zero-length header plus PCM is not yet a playable WAV");
        assert!(session.retention.audio_cached, "raw local data is still retained");
        assert!(session.capture_incomplete);assert_eq!(std::fs::read(&file).unwrap(),raw);
    }

    #[test]
    fn completed_asr_without_speech_preserves_audio_and_pauses_reupload() {
        let mut snapshot = super::apply_fixture_control(super::fixture_snapshot(),
            recovery_request(super::CompanionV1ControlAction::MeetingStart, "no-speech", false)).unwrap();
        let session = &mut snapshot.host.sessions[0];
        session.status = "captured".to_string();
        session.audio_path = Some("actual-preserved.wav".into());
        session.audio_bytes = 32044;
        session.audio_stored = true;
        session.recovery.stage = "transcribing".into();
        session.recovery.attempt_count = 1;
        session.recovery.retry_stage = "transcription".into();
        super::schedule_recovery_failure(session, "Volcengine ASR completed without recognized speech");
        assert_eq!(session.recovery.stage, "paused");
        assert_eq!(session.recovery.attempt_count, 1);
        assert!(session.recovery.next_retry_at_unix_ms.is_none());
        assert_eq!(session.pending_reason.as_deref(), Some("no_speech_detected"));
        assert!(session.audio_stored);
        assert_eq!(session.audio_path.as_deref(), Some("actual-preserved.wav"));
        assert!(!session.transcript_final);
        super::persistence::reconcile_session_recovery(session);
        assert_eq!(session.pending_reason.as_deref(), Some("no_speech_detected"));
        assert_eq!(session.recovery.stage, "paused");
        assert!(!super::recovery_error_is_permanent("Volcengine connection closed without a final result"));
    }
    use super::*;
    use crate::companion_v1::{
        synced_device_session, CompanionV1ControlAction, CompanionV1ControlRequest,
    };

    #[test]
    fn stopped_host_recording_uses_measured_duration_instead_of_requested_limit() {
        let backend = FixtureCompanionBackend::new();
        let mut start = recovery_request(CompanionV1ControlAction::MeetingStart, "measured-duration", false);
        start.meeting_mode = Some("offlineStore".to_string());
        start.duration_ms = Some(1_800_000);
        backend.apply_control(start).unwrap();
        let mut stop = recovery_request(CompanionV1ControlAction::MeetingStop, "measured-duration", false);
        stop.duration_ms = Some(1_800_000);
        let stopped = backend.apply_control(stop).unwrap();
        let session = stopped.host.sessions.iter().find(|session| session.id == "measured-duration").unwrap();
        assert!(session.audio_bytes > 44);
        assert!(session.duration_ms > 0 && session.duration_ms < 10_000,
            "a short capture must not claim the requested thirty-minute limit");
        assert_eq!(stopped.meeting.duration_ms, session.duration_ms);
        assert!(!stopped.meeting.active);
    }

    fn recovery_request(
        action: CompanionV1ControlAction,
        session_id: &str,
        automatic: bool,
    ) -> CompanionV1ControlRequest {
        CompanionV1ControlRequest { minutes_template: None, recording_source: None,
            action,
            context_note_revision: None, ble_name: None,
            session_id: Some(session_id.to_string()),
            prompt_id: automatic.then(|| "__companion_auto_recovery__".to_string()),
            title: None,
            transcript_text: None,
            meeting_mode: None,
            audio_path: None,
            audio_bytes: None,
            device_id: None,
            duration_ms: None,
        }
    }

    #[test]
    fn received_recording_is_discoverable_before_ack_and_keeps_online_identity() {
        let root = std::env::temp_dir().join(format!("companion-received-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("sessions.json");
        let wav = root.join("received.wav");
        std::fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        let item = CompanionSyncedRecording { recording_id: 42, duration_ms: 10_000,
            total_length: 1000, sha256: "a".repeat(64), recording_path: wav.to_string_lossy().into_owned(), device_reclaimed: false, capture_incomplete: false };
        let mut request = recovery_request(CompanionV1ControlAction::MeetingStart, "original-online", false);
        request.meeting_mode = Some("onlineLive".into());
        request.audio_path = Some("board://online/original-online".into());
        request.device_id = Some("AA:BB:CC:DD:EE:FF".into());
        let prepared = apply_fixture_control(fixture_snapshot(), request).unwrap();
        let mut sessions = prepared.host.sessions;
        sessions[0].device_recording_id = Some(42);
        persistence::save_sessions_to(&path, &sessions).unwrap();
        checkpoint_received_recording(&path, "AA:BB:CC:DD:EE:FF", &item).unwrap();
        checkpoint_received_recording(&path, "AA:BB:CC:DD:EE:FF", &item).unwrap();
        std::fs::write(&path, b"torn after device ACK").unwrap();
        let restored = persistence::load_sessions_from(&path).unwrap();
        assert_eq!(restored.len(), 1);
        assert_eq!(restored[0].id, "original-online");
        assert_eq!(restored[0].meeting_mode, "onlineLive");
        assert_eq!(restored[0].device_recording_id, Some(42));
        assert_eq!(restored[0].device_total_length, Some(1000));
        assert_eq!(restored[0].device_sha256.as_deref(), Some(item.sha256.as_str()));
        assert_eq!(restored[0].audio_path.as_deref(), Some(item.recording_path.as_str()));
        assert!(!restored[0].device_reclaimed, "without device receipt reclaim cannot be claimed");
        let mut acknowledged = item.clone(); acknowledged.device_reclaimed = true;
        checkpoint_received_recording(&path, "AA:BB:CC:DD:EE:FF", &acknowledged).unwrap();
        let after_ack = persistence::load_sessions_from(&path).unwrap();
        assert_eq!(after_ack[0].id, "original-online");
        assert!(after_ack[0].device_reclaimed, "exact device ACK survives pending ASR and restart");
        assert_eq!(after_ack[0].device_sha256.as_deref(), Some(item.sha256.as_str()));
        assert_eq!(after_ack[0].audio_path.as_deref(), Some(item.recording_path.as_str()));
        assert!(after_ack[0].audio_stored && !after_ack[0].transcript_final);
        let mut second = item.clone(); second.recording_id = 43;
        checkpoint_received_recording(&path, "AA:BB:CC:DD:EE:FF", &second).unwrap();
        assert_eq!(persistence::load_sessions_from(&path).unwrap().len(), 2);
        std::fs::write(&path, b"unrecoverable primary").unwrap();
        std::fs::write(root.join("sessions.json.bak"), b"unrecoverable backup").unwrap();
        assert!(checkpoint_received_recording(&path, "AA:BB:CC:DD:EE:FF", &second).is_err(), "no device ACK after failed durable checkpoint");
        assert_eq!(std::fs::read(&path).unwrap(), b"unrecoverable primary");
    }

    #[test]
    fn interrupted_online_identity_and_sync_keep_user_edits() {
        let mut snapshot = fixture_snapshot();
        let request = CompanionV1ControlRequest { minutes_template: None, recording_source: None, action: CompanionV1ControlAction::MeetingStart,
            meeting_mode: Some("onlineLive".into()), audio_path: Some("board://online/known".into()),
            device_id: Some("AA:BB:CC:DD:EE:FF".into()), ..recovery_request(CompanionV1ControlAction::MeetingStart,"known",false) };
        snapshot = apply_fixture_control(snapshot, request).unwrap();
        let original = &mut snapshot.host.sessions[0];
        original.device_recording_id = Some(42);
        original.title = "用户保留的标题".into();
        original.status = "captured".into();
        original.pending_reason = Some("needs_device_sync".into());
        snapshot.device.device_id = Some("AA:BB:CC:DD:EE:FF".into());
        let root = std::env::temp_dir().join(format!("companion-merge-{}", uuid::Uuid::new_v4().simple()));
        std::fs::create_dir(&root).unwrap();
        let wav = root.join("received.wav"); std::fs::write(&wav,b"fixture-only").unwrap();
        let item = CompanionSyncedRecording {recording_id:42,duration_ms:1000,total_length:100,
            sha256:"a".repeat(64),recording_path:wav.to_string_lossy().into_owned(),device_reclaimed: false, capture_incomplete: false};
        merge_synced_recordings(&mut snapshot, std::slice::from_ref(&item));
        assert_eq!(snapshot.host.sessions.len(),1);
        assert_eq!(snapshot.host.sessions[0].id,"known");
        assert_eq!(snapshot.host.sessions[0].title,"用户保留的标题");
        assert_eq!(snapshot.host.sessions[0].meeting_mode,"onlineLive");
        assert_eq!(snapshot.host.sessions[0].pending_reason.as_deref(),Some("needs_transcription"));
        snapshot.host.sessions[0].transcript_text="已核对的完整文字".into();
        snapshot.host.sessions[0].transcript_final=true;
        snapshot.host.sessions[0].status="transcribed".into();
        merge_synced_recordings(&mut snapshot, std::slice::from_ref(&item));
        assert_eq!(snapshot.host.sessions[0].transcript_text,"已核对的完整文字");
        assert_eq!(snapshot.host.sessions[0].status,"transcribed");
        let mut reused=item.clone();reused.sha256="b".repeat(64);
        merge_synced_recordings(&mut snapshot, std::slice::from_ref(&reused));
        assert_eq!(snapshot.host.sessions.len(),2,"reused device ID with different content must not overwrite a meeting");
        assert_eq!(snapshot.host.sessions.iter().find(|s| s.id=="known").unwrap().device_sha256.as_deref(),Some(item.sha256.as_str()));
    }

    #[test]
    fn save_retry_requeues_interrupted_checkpoint_without_resetting_attempt_budget() {
        let backend = FixtureCompanionBackend::new();
        let demo = apply_fixture_control(fixture_snapshot(),
            recovery_request(CompanionV1ControlAction::MeetingLoadDemo, "retry-checkpoint", false)).unwrap();
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            snapshot.host.sessions = demo.host.sessions;
            let session = &mut snapshot.host.sessions[0];
            session.minutes = None; session.minutes_by_mode = Default::default();
            session.recovery = crate::companion_v1::CompanionV1MeetingRecovery::armed("offlineStore");
            session.recovery.stage = "generatingMinutes".into();
            session.recovery.attempt_count = 1;
            snapshot.host.persistence.status = "unsaved".into();
        }
        let saved = backend.apply_control(recovery_request(CompanionV1ControlAction::HostRetrySave, "", false)).unwrap();
        assert_eq!(saved.host.persistence.status, "ready");
        assert_eq!(saved.host.sessions[0].recovery.stage, "retryBackoff");
        assert_eq!(saved.host.sessions[0].recovery.retry_stage, "minutes");
        assert_eq!(saved.host.sessions[0].recovery.attempt_count, 1);
    }

    #[test]
    #[cfg(windows)]
    fn locked_original_keeps_session_and_can_be_deleted_after_retry() {
        use std::os::windows::fs::OpenOptionsExt;
        struct RecordingOverride(Option<std::ffi::OsString>);
        impl Drop for RecordingOverride {
            fn drop(&mut self) {
                if let Some(value) = &self.0 { std::env::set_var("COMPANION_TYPE_RECORDING_DIR", value); }
                else { std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); }
            }
        }
        let _restore = RecordingOverride(std::env::var_os("COMPANION_TYPE_RECORDING_DIR"));
        let root = std::env::temp_dir().join(format!("companion-delete-retry-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
        let audio = root.join("original.wav");
        std::fs::write(&audio, b"owned audio").unwrap();
        let backend = FixtureCompanionBackend::new();
        let mut demo = apply_fixture_control(fixture_snapshot(),
            recovery_request(CompanionV1ControlAction::MeetingLoadDemo, "delete-retry", false)).unwrap();
        demo.host.sessions.truncate(1);
        let session = &mut demo.host.sessions[0];
        session.audio_path = Some(audio.to_string_lossy().into());
        session.audio_stored = true; session.retention.audio_cached = true;
        session.device_recording_id = None; session.chunks.clear();
        let id = session.id.clone();
        demo.host.selected_session_id = Some(id.clone());
        *backend.snapshot.lock().unwrap() = demo;
        let held = std::fs::OpenOptions::new().read(true).share_mode(0).open(&audio).unwrap();
        for action in [CompanionV1ControlAction::PrivacyEraseAudio,
            CompanionV1ControlAction::PrivacyDeleteSession, CompanionV1ControlAction::PrivacyEraseAll] {
            let error = backend.apply_control(recovery_request(action, &id, false)).unwrap_err();
            assert!(error.contains("尚未完全删除"), "{error}");
            let snapshot = backend.snapshot().unwrap();
            assert_eq!(snapshot.host.sessions.len(), 1);
            assert!(snapshot.host.sessions[0].retention.audio_cached);
            assert_eq!(snapshot.host.sessions[0].audio_path.as_deref(), Some(audio.to_string_lossy().as_ref()));
        }
        drop(held);
        let cleared = backend.apply_control(recovery_request(CompanionV1ControlAction::PrivacyEraseAudio, &id, false)).unwrap();
        assert!(!cleared.host.sessions[0].retention.audio_cached);
        assert!(!audio.exists());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn storage_failure_preserves_edits_blocks_processing_and_retry_commits() {
        // This suite is run with --test-threads=1, like the existing environment
        // provider tests. Always restore the user's state override on unwind.
        struct StateOverride(Option<std::ffi::OsString>);
        impl Drop for StateOverride {
            fn drop(&mut self) {
                if let Some(value) = &self.0 { std::env::set_var("COMPANION_TYPE_STATE_PATH", value); }
                else { std::env::remove_var("COMPANION_TYPE_STATE_PATH"); }
            }
        }
        let _restore = StateOverride(std::env::var_os("COMPANION_TYPE_STATE_PATH"));
        let root = std::env::temp_dir().join(format!("companion-backend-storage-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("sessions.json");
        std::env::set_var("COMPANION_TYPE_STATE_PATH", &path);
        let demo = apply_fixture_control(fixture_snapshot(),
            recovery_request(CompanionV1ControlAction::MeetingLoadDemo, "stored", false)).unwrap();
        persistence::save_sessions_to(&path, &demo.host.sessions).unwrap();
        let id = demo.host.sessions[0].id.clone();
        let backend = FixtureCompanionBackend::new();
        let backup = root.join("sessions.json.bak");
        std::fs::remove_file(&backup).unwrap();
        std::fs::create_dir(&backup).unwrap(); // readable primary, unwritable backup destination
        let mut edit = recovery_request(CompanionV1ControlAction::MeetingImportTranscript, &id, false);
        edit.transcript_text = Some("本次新增的会议内容必须保留".into());
        let changed = backend.apply_control(edit).unwrap();
        assert_eq!(changed.host.persistence.status, "unsaved");
        assert!(changed.host.sessions[0].transcript_text.contains("必须保留"));
        assert!(!changed.last_control.unwrap().accepted);
        assert!(backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes, &id, true)).is_err());
        let viewed = backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingSelectSession, &id, false)).unwrap();
        assert_eq!(viewed.host.persistence.status, "unsaved", "viewing must not dismiss the warning");
        std::fs::remove_dir(&backup).unwrap();
        let retry = backend.apply_control(recovery_request(CompanionV1ControlAction::HostRetrySave, &id, false)).unwrap();
        assert_eq!(retry.host.persistence.status, "ready");
        assert!(retry.last_control.is_none());
        let restarted = FixtureCompanionBackend::new().snapshot().unwrap();
        assert_eq!(restarted.host.sessions[0].transcript_text, changed.host.sessions[0].transcript_text);

        // The meeting editor must retain accepted in-memory edits if the disk
        // fails, and only report them saved after the explicit retry commits.
        std::fs::remove_file(&backup).unwrap();
        std::fs::create_dir(&backup).unwrap();
        let renamed = backend.save_meeting_edit(meeting_workspace::MeetingEditRequest {
            create_manual: None, restore_history: None,
            transcript_review: None,
            session_id: id.clone(), title: Some("待保存的人工命名".into()),
            expected_title: Some(restarted.host.sessions[0].title.clone()),
            meeting_mode: None, markdown: None, expected_markdown: None,
        }).unwrap();
        assert_eq!(renamed.host.persistence.status, "unsaved");
        assert_eq!(renamed.host.sessions[0].title, "待保存的人工命名");
        std::fs::remove_dir(&backup).unwrap();
        let retry = backend.apply_control(recovery_request(CompanionV1ControlAction::HostRetrySave, &id, false)).unwrap();
        assert_eq!(retry.host.persistence.status, "ready");
        assert_eq!(FixtureCompanionBackend::new().snapshot().unwrap().host.sessions[0].title, "待保存的人工命名");

        std::fs::write(&path, b"torn index").unwrap();
        std::fs::write(&backup, b"torn backup").unwrap();
        let blocked = FixtureCompanionBackend::new();
        assert_eq!(blocked.snapshot().unwrap().host.persistence.status, "blocked");
        assert!(blocked.snapshot().unwrap().host.sessions.is_empty(), "damage cannot become a demo library");
        assert!(blocked.apply_control(recovery_request(CompanionV1ControlAction::MeetingStart, "new", false)).is_err());
        let again = blocked.apply_control(recovery_request(CompanionV1ControlAction::HostRetrySave, &id, false)).unwrap();
        assert_eq!(again.host.persistence.status, "blocked");
        assert_eq!(std::fs::read(&path).unwrap(), b"torn index");
        std::fs::write(&backup, serde_json::to_vec(&retry.host.sessions).unwrap()).unwrap();
        let restored = blocked.apply_control(recovery_request(CompanionV1ControlAction::HostRetrySave, &id, false)).unwrap();
        assert_eq!(restored.host.persistence.status, "ready");
        assert_eq!(restored.host.sessions[0].transcript_text, changed.host.sessions[0].transcript_text);

        let mut start = recovery_request(CompanionV1ControlAction::MeetingStart, "stop-during-disk-failure", false);
        start.meeting_mode = Some("offlineStore".into());
        blocked.apply_control(start).unwrap(); // cargo-test synthetic capture, never hardware evidence
        std::fs::remove_file(&backup).unwrap();
        std::fs::create_dir(&backup).unwrap();
        let stopped = blocked.apply_control(recovery_request(CompanionV1ControlAction::MeetingStop,
            "stop-during-disk-failure", false)).unwrap();
        assert_eq!(stopped.host.persistence.status, "unsaved");
        assert!(!stopped.meeting.active);
        assert!(stopped.host.active_session_id.is_none());
        assert!(stopped.host.sessions.iter().all(|s| s.status != "recording"));
        assert!(blocked.apply_control(recovery_request(CompanionV1ControlAction::MeetingStart, "too-soon", false)).is_err());
        std::fs::remove_dir(&backup).unwrap();
        let committed = blocked.apply_control(recovery_request(CompanionV1ControlAction::HostRetrySave, "", false)).unwrap();
        assert_eq!(committed.host.persistence.status, "ready");
        assert!(!committed.meeting.active);
    }

    #[test]
    fn manual_minutes_retry_clears_old_error_after_success() {
        let mut snapshot = apply_fixture_control(fixture_snapshot(),
            recovery_request(CompanionV1ControlAction::MeetingLoadDemo, "manual-retry", false)).unwrap();
        let session = &mut snapshot.host.sessions[0];
        session.processing_policy = crate::companion_v1::CompanionV1ProcessingPolicy::Manual;
        session.recovery = Default::default();
        session.recovery.stage = "paused".into();
        session.recovery.last_error = Some("纪要缺少问题来源分类".into());
        session.pending_reason = Some("recovery_paused".into());
        let mut minutes = session.minutes.clone().unwrap();
        minutes.quality = "final".into(); minutes.llm_note = None;
        assert!(refresh_minutes_products(session, "retry-succeeded", |_| minutes.clone()).is_none());
        assert_eq!(session.status, "minutesReady");
        assert_eq!(session.recovery.intent, "none");
        assert_eq!(session.recovery.stage, "idle");
        assert!(session.recovery.last_error.is_none());
        assert!(session.pending_reason.is_none());
        session.capture_incomplete = true;
        session.recovery.last_error = Some("录音不完整".into());
        mark_recovery_complete(session);
        assert_eq!(session.recovery.last_error.as_deref(), Some("录音不完整"));
    }

    #[test]
    fn paired_minutes_retry_only_failed_variant_and_preserve_capture_route() {
        for failed_mode in ["offlineStore", "onlineLive"] {
            let mut snapshot = apply_fixture_control(fixture_snapshot(),
                recovery_request(CompanionV1ControlAction::MeetingLoadDemo, "paired-recovery", false)).unwrap();
            let session = &mut snapshot.host.sessions[0];
            let mut completed = session.minutes.clone().unwrap();
            completed.quality = "final".into();
            completed.source = "userEdited".into();
            completed.llm_note = None;
            let mut failed = completed.clone();
            failed.quality = "draft".into();
            failed.source = "rules_l0".into();
            failed.llm_note = Some("service rejected minutes response".into());
            let ready = minutes_variant(&completed, 2);
            let retry = minutes_variant(&failed, 2);
            assert_eq!(ready.status, "minutesReady");
            assert_eq!(retry.status, "retryPending");
            session.meeting_mode = "onlineLive".into();
            session.minutes = Some(if failed_mode == "onlineLive" { failed.clone() } else { completed.clone() });
            session.minutes_by_mode.offline_store = Some(if failed_mode == "offlineStore" { retry.clone() } else { ready.clone() });
            session.minutes_by_mode.online_live = Some(if failed_mode == "onlineLive" { retry } else { ready });
            let preserved = serde_json::to_value(if failed_mode == "offlineStore" {
                &session.minutes_by_mode.online_live
            } else { &session.minutes_by_mode.offline_store }).unwrap();
            let original_text = session.transcript_text.clone();
            session.processing_policy = crate::companion_v1::CompanionV1ProcessingPolicy::Automatic;
            session.transcript_final = true;
            session.recovery = Default::default();
            arm_meeting_recovery(session);
            session.recovery.stage = "retryBackoff".into();
            session.recovery.retry_stage = "minutes".into();
            session.recovery.next_retry_at_unix_ms = Some(u64::MAX-1);
            session.status = "minutesReady".into(); // stale checkpoint must not close the failed peer
            assert!(!session_has_final_minutes_product(session));
            persistence::reconcile_session_recovery(session);
            assert_eq!(session.recovery.stage, "retryBackoff");
            assert_eq!(session.recovery.next_retry_at_unix_ms, Some(u64::MAX-1));
            let mut calls = Vec::new();
            assert!(refresh_minutes_products(session, "retry-failed", |input| {
                calls.push(input.meeting_mode.clone()); failed.clone()
            }).is_some());
            assert_eq!(calls, [failed_mode]);
            assert_eq!(session.recovery.stage, "retryBackoff");
            assert!(session_has_pending_dual_minutes(session));
            calls.clear();
            assert!(refresh_minutes_products(session, "retry-succeeded", |input| {
                calls.push(input.meeting_mode.clone()); completed.clone()
            }).is_none());
            assert_eq!(calls, [failed_mode]);
            assert_eq!(session.meeting_mode, "onlineLive");
            assert_eq!(session.recovery.requested_meeting_mode, "onlineLive");
            assert_eq!(session.transcript_text, original_text);
            assert_eq!(serde_json::to_value(if failed_mode == "offlineStore" {
                &session.minutes_by_mode.online_live
            } else { &session.minutes_by_mode.offline_store }).unwrap(), preserved);
            assert_eq!(session.recovery.stage, "complete");
            assert!(session_has_final_minutes_product(session));
        }
    }

    #[test]
    fn manually_reviewed_final_minutes_require_explicit_regeneration() {
        // Isolate provider switches; this is a serial, deterministic L0 test.
        struct RestoreEnv(Vec<(&'static str, Option<std::ffi::OsString>)>);
        impl Drop for RestoreEnv {
            fn drop(&mut self) {
                for (name, value) in &self.0 {
                    if let Some(value) = value { std::env::set_var(name, value); }
                    else { std::env::remove_var(name); }
                }
            }
        }
        let backend = FixtureCompanionBackend::new();
        let _restore = RestoreEnv(["COMPANION_TYPE_MINUTES_COMMAND", "COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED"]
            .into_iter().map(|name| (name, std::env::var_os(name))).collect());
        std::env::remove_var("COMPANION_TYPE_MINUTES_COMMAND");
        std::env::set_var("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED", "0");
        let mut snapshot = apply_fixture_control(fixture_snapshot(),
            recovery_request(CompanionV1ControlAction::MeetingLoadDemo, "reviewed-final", false)).unwrap();
        let session = &mut snapshot.host.sessions[0];
        let id = session.id.clone();
        session.minutes.as_mut().unwrap().quality = "final".into();
        session.minutes.as_mut().unwrap().llm_note = None;
        session.minutes_by_mode.offline_store.as_mut().unwrap().quality = "final".into();
        let live = session.minutes_by_mode.offline_store.clone().unwrap();
        session.minutes_by_mode.online_live = Some(live.clone());
        let original = session.minutes_by_mode.offline_store.as_ref().unwrap().markdown.clone();
        meeting_workspace::edit_session(session, &meeting_workspace::MeetingEditRequest {
            create_manual: None, restore_history: None,
            transcript_review: None,
            session_id: id.clone(), title: None, expected_title: None, meeting_mode: Some("offlineStore".into()),
            markdown: Some("# 人工校订，后台不得覆盖".into()), expected_markdown: Some(original),
        }, "reviewed").unwrap();
        assert!(session_has_final_minutes_product(session));
        *backend.snapshot.lock().unwrap() = snapshot;
        let automatic = backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes, &id, true)).unwrap();
        assert_eq!(automatic.host.sessions[0].minutes.as_ref().unwrap().source, "userEdited");
        assert_eq!(automatic.host.sessions[0].minutes.as_ref().unwrap().markdown, "# 人工校订，后台不得覆盖");
        let explicit = backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes, &id, false)).unwrap();
        assert_eq!(explicit.host.sessions[0].minutes.as_ref().unwrap().source, "rules_l0");
        assert_ne!(explicit.host.sessions[0].minutes.as_ref().unwrap().markdown, "# 人工校订，后台不得覆盖");
        assert_eq!(explicit.host.sessions[0].minutes_by_mode.online_live.as_ref().unwrap().markdown, live.markdown);

        // Exercise the real reducer + provider path, not only the retry planner:
        // its selected-mode draft placeholder must not replace the completed edit.
        let mut paired = automatic;
        let session = &mut paired.host.sessions[0];
        session.transcript_final = true;
        session.minutes_by_mode.online_live.as_mut().unwrap().status = "retryPending".into();
        session.minutes_by_mode.online_live.as_mut().unwrap().quality = "draft".into();
        arm_meeting_recovery(session);
        session.recovery.stage = "pendingMinutes".into();
        session.recovery.retry_stage = "minutes".into();
        *backend.snapshot.lock().unwrap() = paired;
        let repaired = backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes, &id, true)).unwrap();
        let session = &repaired.host.sessions[0];
        assert_eq!(session.meeting_mode, "offlineStore");
        assert_eq!(session.minutes.as_ref().unwrap().source, "userEdited");
        assert_eq!(session.minutes.as_ref().unwrap().markdown, "# 人工校订，后台不得覆盖");
        assert_eq!(session.minutes_by_mode.offline_store.as_ref().unwrap().source, "userEdited");
        assert_eq!(session.minutes_by_mode.online_live.as_ref().unwrap().source, "rules_l0");
        assert_eq!(session.minutes_by_mode.online_live.as_ref().unwrap().status, "minutesReady");
        assert_eq!(session.recovery.stage, "complete");
    }

    #[test]
    fn transcript_review_generates_requested_mode_without_changing_asr_or_peer() {
        struct RestoreEnv(Vec<(&'static str, Option<std::ffi::OsString>)>);
        impl Drop for RestoreEnv { fn drop(&mut self) { for (name,value) in &self.0 {
            if let Some(value) = value { std::env::set_var(name,value); } else { std::env::remove_var(name); }
        } } }
        let _restore = RestoreEnv(["COMPANION_TYPE_MINUTES_COMMAND","COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED"].into_iter()
            .map(|name| (name,std::env::var_os(name))).collect());
        std::env::remove_var("COMPANION_TYPE_MINUTES_COMMAND"); std::env::set_var("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED","0");
        let backend = FixtureCompanionBackend::new();
        let mut snapshot = apply_fixture_control(fixture_snapshot(),recovery_request(CompanionV1ControlAction::MeetingLoadDemo,"review-source",false)).unwrap();
        let session = &mut snapshot.host.sessions[0]; let id = session.id.clone();
        session.transcript_final = true; session.meeting_mode = "onlineLive".into();
        session.utterances = vec![CompanionV1UtteranceSegment { text:"owner 王 due 周五交录音。".into(),start_ms:1000,end_ms:3000,speaker:Some(0),approximate_timing:false }];
        session.minutes.as_mut().unwrap().quality = "final".into(); session.minutes_by_mode.offline_store.as_mut().unwrap().quality="final".into();
        session.minutes_by_mode.online_live = session.minutes_by_mode.offline_store.clone();
        let peer = serde_json::to_value(&session.minutes_by_mode.online_live).unwrap();
        let raw = session.transcript_text.clone(); let utterances = session.utterances.clone();
        let edit = meeting_workspace::MeetingEditRequest {
            create_manual: None, restore_history: None,
            session_id:id.clone(),title:None,expected_title:None,meeting_mode:None,markdown:None,expected_markdown:None,
            transcript_review:Some(transcript_review::TranscriptReviewEdit {
                expected_transcript_text:raw.clone(),expected_utterances:utterances.clone(),expected_revision:0,
                restore_original:false,text:None,utterance_edits:vec![transcript_review::UtteranceEdit {
                    index:0,text:"owner 王 due 周四交录音。".into(),speaker_name:None }],
                speaker_names:vec![transcript_review::SpeakerName {speaker:0,name:"小王".into()}],
                unrecognized:None,
            }),
        };
        *backend.snapshot.lock().unwrap()=snapshot;
        let edited=backend.save_meeting_edit(edit).unwrap(); let session=&edited.host.sessions[0];
        assert_eq!(session.transcript_text,raw); assert!(!session_has_final_minutes_product(session));
        let automatic=backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes,&id,true)).unwrap();
        assert_eq!(serde_json::to_value(&automatic.host.sessions[0].minutes_by_mode.online_live).unwrap(),peer);
        let mut request=recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes,&id,false); request.meeting_mode=Some("offlineStore".into());
        let generated=backend.apply_control(request.clone()).unwrap(); let session=&generated.host.sessions[0];
        assert_eq!(session.meeting_mode,"onlineLive"); assert_eq!(session.transcript_text,raw); assert_eq!(session.utterances,utterances);
        assert_eq!(serde_json::to_value(&session.minutes_by_mode.online_live).unwrap(),peer);
        let mode=session.minutes_by_mode.offline_store.as_ref().unwrap();
        assert_eq!(mode.source_review_revision,Some(1)); assert!(mode.markdown.contains("周四交录音"));
        assert!(mode.markdown.contains("**小王**")); assert_eq!(session.pending_reason.as_deref(),Some("minutes_source_changed"));
        assert!(!session_has_final_minutes_product(session));
        let current=transcript_review::active_revision(session); assert!(transcript_review::minutes_current(session,current));
        let root=std::env::temp_dir().join(format!("companion-review-binding-{}",uuid::Uuid::new_v4()));
        persistence::save_sessions_to(&root.join("sessions.json"),&generated.host.sessions).unwrap();
        let restored=persistence::load_sessions_from(&root.join("sessions.json")).unwrap();
        assert_eq!(restored[0].transcript_review.as_ref().unwrap().revision,1);
        assert_eq!(restored[0].minutes_by_mode.offline_store.as_ref().unwrap().source_review_revision,Some(1));
        std::fs::remove_dir_all(root).unwrap();
        backend.snapshot.lock().unwrap().host.sessions[0].utterances[0].end_ms+=1;
        assert!(backend.apply_control(request).unwrap_err().contains("原始转写已更新"));
    }

    #[test]
    fn synthetic_capture_survives_editing_previous_meeting() {
        let root=std::env::temp_dir().join(format!("companion-concurrent-edit-{}",uuid::Uuid::new_v4()));
        let recordings=root.join("recordings");std::fs::create_dir_all(&recordings).unwrap();let path=root.join("sessions.json");
        std::env::set_var("COMPANION_TYPE_STATE_PATH",&path);std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&recordings);
        std::env::set_var("COMPANION_TYPE_HOST_RECORDING_MODE","synthetic");std::env::set_var("COMPANION_TYPE_DISABLE_AUTO_RECOVERY","1");std::env::set_var("COMPANION_TYPE_BLE_NATIVE_DISABLED","1");
        let initial=apply_fixture_control(fixture_snapshot(),recovery_request(CompanionV1ControlAction::MeetingLoadDemo,"old-meeting",false)).unwrap();
        persistence::save_sessions_to(&path,&initial.host.sessions).unwrap();
        let backend=FixtureCompanionBackend::new();
        let started=backend.apply_control(crate::control_request(CompanionV1ControlAction::MeetingStart,Some("new-recording".into()))).unwrap();
        assert_eq!(started.host.active_session_id.as_deref(),Some("new-recording"));
        let selected=backend.apply_control(crate::control_request(CompanionV1ControlAction::MeetingSelectSession,Some("old-meeting".into()))).unwrap();
        let title=selected.host.sessions.iter().find(|r|r.id=="old-meeting").unwrap().title.clone();
        let edit=meeting_workspace::MeetingEditRequest{session_id:"old-meeting".into(),title:Some("录音时整理旧会议".into()),expected_title:Some(title),
            meeting_mode:None,markdown:None,expected_markdown:None,create_manual:None,restore_history:None,transcript_review:None};
        let edited=backend.save_meeting_edit(edit).unwrap();assert!(edited.meeting.active);
        let finished=backend.apply_control(crate::control_request(CompanionV1ControlAction::MeetingStop,Some("new-recording".into()))).unwrap();
        let new=finished.host.sessions.iter().find(|r|r.id=="new-recording").unwrap();assert!(new.audio_stored&&new.audio_bytes>44);
        meeting_workspace::validate_wav(std::path::Path::new(new.audio_path.as_deref().unwrap())).unwrap();
        let saved:Vec<CompanionV1HostSession>=serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(saved.iter().find(|r|r.id=="old-meeting").unwrap().title,"录音时整理旧会议");
        assert!(saved.iter().find(|r|r.id=="new-recording").unwrap().audio_stored);
        println!("synthetic concurrent capture and edit evidence: {}",root.display());
    }

    #[test]
    fn edit_saved_meeting_while_another_recording_continues() {
        let root=std::env::temp_dir().join(format!("companion-edit-other-recording-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();let path=root.join("sessions.json");
        let prior=std::env::var_os("COMPANION_TYPE_STATE_PATH");std::env::set_var("COMPANION_TYPE_STATE_PATH",&path);
        let mut snapshot=apply_fixture_control(fixture_snapshot(),
            recovery_request(CompanionV1ControlAction::MeetingLoadDemo,"saved-before-recording",false)).unwrap();
        let mut active=snapshot.host.sessions[0].clone();active.id="separate-active-recording".into();active.status="recording".into();
        active.transcript_text="正在记录的前缀".into();active.transcript_final=false;
        snapshot.host.sessions.push(active.clone());snapshot.host.active_session_id=Some(active.id.clone());
        snapshot.meeting.active=true;snapshot.device.recording=true;
        persistence::save_sessions_to(&path,&snapshot.host.sessions).unwrap();
        let backend=FixtureCompanionBackend::new();*backend.snapshot.lock().unwrap()=snapshot;
        let request=meeting_workspace::MeetingEditRequest {session_id:"saved-before-recording".into(),title:Some("已整理的旧会议".into()),
            expected_title:Some(active.title.clone()),meeting_mode:None,markdown:None,expected_markdown:None,
            create_manual:None,restore_history:None,transcript_review:None};
        let result=backend.save_meeting_edit(request).unwrap();
        assert_eq!(result.host.sessions[0].title,"已整理的旧会议");
        assert_eq!(serde_json::to_value(&result.host.sessions[1]).unwrap(),serde_json::to_value(&active).unwrap());
        let disk:Vec<CompanionV1HostSession>=serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(disk[0].title,"已整理的旧会议");assert_eq!(serde_json::to_value(&disk[1]).unwrap(),serde_json::to_value(&active).unwrap());
        assert!(result.meeting.active && result.device.recording);
        session_store::update_checked(&path,|rows|{rows[0].title="其他进程的新标题".into();Ok(())}).unwrap();
        let stale_request=meeting_workspace::MeetingEditRequest {session_id:"saved-before-recording".into(),title:Some("不应覆盖".into()),
            expected_title:Some("已整理的旧会议".into()),meeting_mode:None,markdown:None,expected_markdown:None,
            create_manual:None,restore_history:None,transcript_review:None};
        assert!(backend.save_meeting_edit(stale_request).is_err());
        let conflict_disk:Vec<CompanionV1HostSession>=serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(conflict_disk[0].title,"其他进程的新标题");
        assert_eq!(serde_json::to_value(&conflict_disk[1]).unwrap(),serde_json::to_value(&active).unwrap());
        let active_request=meeting_workspace::MeetingEditRequest {session_id:active.id.clone(),title:Some("不应修改".into()),
            expected_title:Some(active.title.clone()),meeting_mode:None,markdown:None,expected_markdown:None,
            create_manual:None,restore_history:None,transcript_review:None};
        assert!(backend.save_meeting_edit(active_request).is_err());
        let after:Vec<CompanionV1HostSession>=serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(serde_json::to_value(&after[1]).unwrap(),serde_json::to_value(&active).unwrap());
        if let Some(value)=prior{std::env::set_var("COMPANION_TYPE_STATE_PATH",value)}else{std::env::remove_var("COMPANION_TYPE_STATE_PATH")}
    }

    #[test]
    fn regenerating_minutes_keeps_saved_user_edits_and_prior_versions() {
        let snapshot = apply_fixture_control(fixture_snapshot(),
            recovery_request(CompanionV1ControlAction::MeetingLoadDemo, "history-test", false)).unwrap();
        let mut session = snapshot.host.sessions[0].clone();
        session.meeting_mode = "offlineStore".into();
        let mut original = minutes::rules_l0_minutes(&session, "first");
        original.source = "userEdited".into();
        original.markdown = "用户修改过的纪要和待办".into();
        session.minutes = Some(original.clone());
        session.minutes_by_mode.offline_store = Some(minutes_variant(&original, 0));
        refresh_minutes_products_for_mode(&mut session, "second", Some("offlineStore"), |input| {
            let mut result = minutes::rules_l0_minutes(input, "second");
            result.markdown = "第一次重新整理".into(); result
        });
        assert_eq!(session.minutes_by_mode.history.len(), 1);
        assert_eq!(session.minutes_by_mode.history[0].variant.markdown, "用户修改过的纪要和待办");
        assert_eq!(session.minutes_by_mode.history[0].variant.source, "userEdited");
        refresh_minutes_products_for_mode(&mut session, "third", Some("offlineStore"), |input| {
            let mut result = minutes::rules_l0_minutes(input, "third");
            result.markdown = "服务失败时的草稿".into(); result.llm_note = Some("service unavailable".into()); result
        });
        let saved = serde_json::to_vec(&session).unwrap();
        let reopened: CompanionV1HostSession = serde_json::from_slice(&saved).unwrap();
        assert_eq!(reopened.minutes_by_mode.history.len(), 2);
        assert_eq!(reopened.minutes_by_mode.history[0].variant.markdown, "用户修改过的纪要和待办");
        assert_eq!(reopened.minutes_by_mode.history[1].variant.markdown, "第一次重新整理");
        assert_eq!(reopened.minutes_by_mode.offline_store.unwrap().markdown, "服务失败时的草稿");
    }

    #[test]
    fn failed_template_generation_keeps_existing_minutes() {
        let old=std::env::var_os("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED");
        std::env::set_var("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED","0");
        let backend=FixtureCompanionBackend::new();let id="template-retain";
        let mut snapshot=apply_fixture_control(fixture_snapshot(),recovery_request(CompanionV1ControlAction::MeetingLoadDemo,id,false)).unwrap();
        let original=snapshot.host.sessions[0].minutes_by_mode.offline_store.as_ref().unwrap().markdown.clone();
        snapshot.host.selected_session_id=Some(id.into());*backend.snapshot.lock().unwrap()=snapshot;
        let mut request=recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes,id,false);
        request.meeting_mode=Some("offlineStore".into());
        request.minutes_template=Some(crate::companion_v1::MinutesTemplate{id:"interview".into(),name:String::new(),instructions:String::new()});
        let error=backend.apply_control(request).unwrap_err();
        assert!(error.contains("模板"),"{error}");
        let saved=backend.snapshot().unwrap();assert_eq!(saved.host.sessions[0].minutes_by_mode.offline_store.as_ref().unwrap().markdown,original);
        assert!(saved.host.sessions[0].minutes_by_mode.history.is_empty());
        if let Some(value)=old {std::env::set_var("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED",value)} else {std::env::remove_var("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED")}
    }

    #[test]
    fn explicit_selected_mode_regenerates_completed_minutes_without_replaying_peer_or_asr() {
        struct RestoreEnv(Vec<(&'static str, Option<std::ffi::OsString>)>);
        impl Drop for RestoreEnv { fn drop(&mut self) { for (name, value) in &self.0 {
            if let Some(value) = value { std::env::set_var(name, value); }
            else { std::env::remove_var(name); }
        } } }
        let _restore = RestoreEnv(["COMPANION_TYPE_MINUTES_COMMAND", "COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED"]
            .into_iter().map(|name| (name, std::env::var_os(name))).collect());
        std::env::remove_var("COMPANION_TYPE_MINUTES_COMMAND");
        std::env::set_var("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED", "0");
        let backend = FixtureCompanionBackend::new();
        let mut snapshot = apply_fixture_control(fixture_snapshot(),
            recovery_request(CompanionV1ControlAction::MeetingLoadDemo, "explicit-version", false)).unwrap();
        let session = &mut snapshot.host.sessions[0];
        let id = session.id.clone();
        session.transcript_final = true;
        session.minutes.as_mut().unwrap().quality = "final".into();
        session.minutes.as_mut().unwrap().llm_note = None;
        let mode = session.minutes_by_mode.offline_store.as_mut().unwrap();
        mode.status = "minutesReady".into(); mode.quality = "final".into();
        mode.source = "llm_deepseek".into(); mode.generated_at = Some("old-product".into());
        session.minutes_by_mode.online_live = session.minutes_by_mode.offline_store.clone();
        let old = serde_json::to_value(&session.minutes_by_mode).unwrap();
        let raw = session.transcript_text.clone(); let utterances = session.utterances.clone();
        *backend.snapshot.lock().unwrap() = snapshot;
        let mut automatic = recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes, &id, true);
        automatic.meeting_mode = Some("offlineStore".into());
        let cached = backend.apply_control(automatic).unwrap();
        assert_eq!(serde_json::to_value(&cached.host.sessions[0].minutes_by_mode).unwrap(), old);
        let cached = backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes, &id, false)).unwrap();
        assert_eq!(serde_json::to_value(&cached.host.sessions[0].minutes_by_mode).unwrap(), old);
        let peer = serde_json::to_value(&cached.host.sessions[0].minutes_by_mode.online_live).unwrap();
        let mut explicit = recovery_request(CompanionV1ControlAction::MeetingGenerateMinutes, &id, false);
        explicit.meeting_mode = Some("offlineStore".into());
        let generated = backend.apply_control(explicit).unwrap(); let session = &generated.host.sessions[0];
        assert_ne!(session.minutes_by_mode.offline_store.as_ref().unwrap().generated_at.as_deref(), Some("old-product"));
        assert_eq!(session.minutes_by_mode.offline_store.as_ref().unwrap().source, "rules_l0");
        assert_eq!(serde_json::to_value(&session.minutes_by_mode.online_live).unwrap(), peer);
        assert_eq!(session.transcript_text, raw); assert_eq!(session.utterances, utterances);
    }

    #[test]
    fn draft_minutes_do_not_block_an_explicit_upgrade_attempt() {
        let snapshot = apply_fixture_control(
            fixture_snapshot(),
            CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingLoadDemo,
                context_note_revision: None, ble_name: None,
                session_id: Some("draft-upgrade".to_string()),
                prompt_id: None,
                title: Some("Draft upgrade".to_string()),
                transcript_text: Some("决定：继续精修纪要。".to_string()),
                meeting_mode: Some("offlineStore".to_string()),
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: Some(2_000),
            },
        )
        .unwrap();
        let mut session = snapshot.host.sessions[0].clone();
        assert_eq!(session.minutes.as_ref().unwrap().quality, "draft");
        assert!(!session_has_final_minutes_product(&session));

        session.minutes.as_mut().unwrap().quality = "final".to_string();
        session.minutes.as_mut().unwrap().llm_note = None;
        session
            .minutes_by_mode
            .offline_store
            .as_mut()
            .unwrap()
            .quality = "final".to_string();
        assert!(session_has_final_minutes_product(&session));
    }

    #[test]
    fn physical_oobe_report_never_claims_unrecorded_board_audio_or_remote_services() {
        let report = ble_bridge::CompanionOobeProbeReport {
            device_id: "AA:BB:CC:DD:EE:FF".to_string(),
            service_count: 5,
            characteristic_count: 18,
            recordings_available: 2,
            identity: CompanionDeviceIdentity {
                firmware_version: Some(0x0001_010f),
                build_id: Some(0x2026_1004),
                board_id: Some(0x5742_4155),
                mcu_uid: Some("1032547698badcfe01234567".to_string()),
                ui_generation: Some(33),
                recording_capacity: None,
                recording: Some(false),
                imu_supported: Some(true),
                imu_online: Some(true),
                imu_sample_hz: Some(50),
                speaker_supported: Some(false),
                speaker_online: Some(false),
                speaker_volume: Some(0),
                speaker_find_supported: Some(false),
            },
            device_status_read: true,
            imu_status_read: true,
            speaker_status_read: true,
            missing_required_gatt: Vec::new(),
            recording_list_error: None,
            clock_sync_error: None,
            clock_sync_evidence: Some("UTC write/readback verified 02:03:04".to_string()),
        };
        let checks = oobe_checks_from_probe(&report);
        assert_eq!(
            checks.iter().find(|check| check.id == "firmware").unwrap().status,
            "pass"
        );
        assert_eq!(
            checks.iter().find(|check| check.id == "gatt").unwrap().status,
            "pass"
        );
        let microphone = checks
            .iter()
            .find(|check| check.id == "boardMicrophone")
            .unwrap();
        assert_eq!(microphone.status, "warn");
        assert!(microphone.message.contains("未启动麦克风实录"));
        let remote = checks
            .iter()
            .find(|check| check.id == "remoteServices")
            .unwrap();
        assert_eq!(remote.status, "warn");
        assert!(remote.message.contains("未调用"));
        assert_eq!(
            checks.iter().find(|check| check.id == "speaker").unwrap().status,
            "warn"
        );
        for id in ["display", "touch", "power"] {
            let check = checks.iter().find(|check| check.id == id).unwrap();
            assert_eq!(check.status, "warn");
            assert!(check.message.contains("未检查"));
        }

        let mut missing_recording_gatt = report;
        missing_recording_gatt.missing_required_gatt =
            vec!["recording_control(8f7a...)".to_string()];
        assert_eq!(
            oobe_checks_from_probe(&missing_recording_gatt)
                .iter()
                .find(|check| check.id == "boardMicrophone")
                .unwrap()
                .status,
            "fail"
        );
    }

    #[test]
    fn failed_oobe_connection_marks_unchecked_hardware_truthfully() {
        let checks = failed_oobe_checks("pairing denied");
        assert_eq!(
            checks.iter().find(|check| check.id == "bluetooth").unwrap().status,
            "fail"
        );
        assert_eq!(
            checks
                .iter()
                .find(|check| check.id == "boardMicrophone")
                .unwrap()
                .status,
            "warn"
        );
        assert!(checks
            .iter()
            .find(|check| check.id == "boardMicrophone")
            .unwrap()
            .message
            .contains("主机麦克风"));
        for id in ["display", "touch", "power"] {
            assert_eq!(
                checks.iter().find(|check| check.id == id).unwrap().status,
                "warn"
            );
        }
    }

    #[test]
    fn oobe_is_rejected_before_ble_side_effects_while_recording() {
        let mut snapshot = fixture_snapshot();
        assert!(!oobe_blocked_by_active_recording(&snapshot, false));
        assert!(oobe_blocked_by_active_recording(&snapshot, true));
        snapshot.meeting.active = true;
        assert!(oobe_blocked_by_active_recording(&snapshot, false));

        let backend = FixtureCompanionBackend::new();
        {
            let mut guard = backend.snapshot.lock().unwrap();
            guard.meeting.active = true;
            guard.meeting.status = "recording".to_string();
            guard.oobe.complete = false;
            guard.oobe.last_run_at = None;
        }
        let error = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::OobeRunChecks,
                "unused-oobe-target",
                false,
            ))
            .unwrap_err();
        assert!(error.contains("正在录音或在线转写"));
        let after = backend.snapshot().unwrap();
        assert!(!after.oobe.complete);
        assert!(after.oobe.last_run_at.is_none());
    }

    fn install_recovery_session(
        backend: &FixtureCompanionBackend,
        id: &str,
        audio_path: &std::path::Path,
    ) {
        let mut snapshot = fixture_snapshot();
        let request = CompanionV1ControlRequest { minutes_template: None, recording_source: None,
            action: CompanionV1ControlAction::DeviceSyncRecordings,
            context_note_revision: None, ble_name: None,
            session_id: Some(id.to_string()),
            prompt_id: None,
            title: Some(id.to_string()),
            transcript_text: None,
            meeting_mode: Some("offlineStore".to_string()),
            audio_path: Some(audio_path.to_string_lossy().to_string()),
            audio_bytes: Some(std::fs::metadata(audio_path).unwrap().len()),
            device_id: Some("test-device".to_string()),
            duration_ms: Some(1_000),
        };
        let session = synced_device_session(&snapshot, &request, "test");
        snapshot.host.sessions = vec![session];
        snapshot.host.selected_session_id = Some(id.to_string());
        *backend.snapshot.lock().unwrap() = snapshot;
    }

    #[test]
    fn recovery_explicit_missing_target_never_falls_back_to_selected_session() {
        let backend = FixtureCompanionBackend::new();
        let error = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::MeetingGenerateMinutes,
                "missing-session",
                true,
            ))
            .unwrap_err();
        assert!(error.contains("missing-session"));
    }

    #[test]
    fn product_long_recording_uses_one_wav_but_independent_duplicates_fail() {
        let root = std::env::temp_dir().join(format!("companion-logical-chunks-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let audio = root.join("long.wav");
        let pcm_bytes = 301 * 32_000u32;
        let mut wav = Vec::new();
        wav.extend_from_slice(b"RIFF"); wav.extend_from_slice(&(pcm_bytes + 36).to_le_bytes());
        wav.extend_from_slice(b"WAVEfmt "); wav.extend_from_slice(&16u32.to_le_bytes());
        wav.extend_from_slice(&1u16.to_le_bytes()); wav.extend_from_slice(&1u16.to_le_bytes());
        wav.extend_from_slice(&16_000u32.to_le_bytes()); wav.extend_from_slice(&32_000u32.to_le_bytes());
        wav.extend_from_slice(&2u16.to_le_bytes()); wav.extend_from_slice(&16u16.to_le_bytes());
        wav.extend_from_slice(b"data"); wav.extend_from_slice(&pcm_bytes.to_le_bytes());
        wav.resize(44 + pcm_bytes as usize, 0);
        std::fs::write(&audio, &wav).unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "long-logical", &audio);
        let original = {
            let mut snapshot = backend.snapshot.lock().unwrap();
            let session = &mut snapshot.host.sessions[0];
            session.duration_ms = 301_000;
            session.chunks = seal_companion_v1_session_chunks(session, "test", session.duration_ms, Some(session.audio_bytes));
            assert_eq!(session.chunks.len(), 2);
            assert_eq!(transcription_chunk_paths(session).unwrap(), vec![audio.to_string_lossy().into_owned()]);
            session.clone()
        };
        // Only the known timeline contract may collapse duplicate paths.
        for field in 0..4 {
            let mut altered = original.clone();
            match field {
                0 => altered.chunks[1].id.push_str("-independent"),
                1 => altered.chunks[1].status = "captured".into(),
                2 => altered.chunks[1].duration_ms += 1,
                _ => altered.chunks[1].bytes += 1,
            }
            let paths = transcription_chunk_paths(&altered).unwrap();
            assert_eq!(paths.len(), 2);
            assert!(CompanionTranscriptionManager::new().transcribe_session(Some(audio.to_str().unwrap()), &paths)
                .unwrap_err().contains("录音分段重复"));
        }
        for missing in [None, Some("device://not-pulled".to_string()), Some("host://not-recorded".to_string())] {
            let mut incomplete = original.clone();
            incomplete.chunks.push(original.chunks[0].clone());
            incomplete.chunks[1].path = missing;
            let paths = transcription_chunk_paths(&incomplete).unwrap();
            assert_eq!(paths.len(), 3);
            assert!(CompanionTranscriptionManager::new().transcribe_session(Some(audio.to_str().unwrap()), &paths)
                .unwrap_err().contains("第 2 / 3 段"));
        }
        let previous = std::env::var_os("COMPANION_TYPE_TRANSCRIPT_TEXT");
        std::env::set_var("COMPANION_TYPE_TRANSCRIPT_TEXT", "Software fixture for long recording metadata routing.");
        let result = backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingTranscribeAudio, "long-logical", false));
        if let Some(value) = previous { std::env::set_var("COMPANION_TYPE_TRANSCRIPT_TEXT", value); }
        else { std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT"); }
        let session = &result.unwrap().host.sessions[0];
        assert!(session.transcript_final);
        assert_eq!(session.chunks.len(), 2);
        assert_eq!(std::fs::read(&audio).unwrap(), wav);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn product_transcription_keeps_missing_segment_and_pauses_recovery() {
        let root = std::env::temp_dir().join(format!("companion-product-missing-segment-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let first = root.join("first.wav"); std::fs::write(&first, b"retained-audio-fixture").unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "missing-segment", &first);
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            let session = &mut snapshot.host.sessions[0];
            session.chunks = [first.clone(), root.join("missing.wav")].iter().enumerate().map(|(index,path)| {
                crate::companion_v1::CompanionV1AudioChunk { id: format!("segment-{index}"),
                    path: Some(path.to_string_lossy().into_owned()), started_at: None, stopped_at: None,
                    duration_ms: 1_000, bytes: 22, status: "captured".into() }
            }).collect();
        }
        let previous = std::env::var_os("COMPANION_TYPE_TRANSCRIPT_TEXT");
        std::env::set_var("COMPANION_TYPE_TRANSCRIPT_TEXT", "This fixture must not hide missing segments.");
        let result = backend.apply_control(recovery_request(CompanionV1ControlAction::MeetingTranscribeAudio, "missing-segment", false));
        if let Some(value) = previous { std::env::set_var("COMPANION_TYPE_TRANSCRIPT_TEXT", value); }
        else { std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT"); }
        let snapshot = result.unwrap(); let session = &snapshot.host.sessions[0];
        assert_eq!(session.chunks.len(), 2); assert!(!session.transcript_final);
        assert_eq!(session.recovery.stage, "paused");
        assert!(session.recovery.last_error.as_ref().unwrap().contains("第 2 / 2 段"));
        assert_eq!(std::fs::read(first).unwrap(), b"retained-audio-fixture");
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn interrupted_capture_automatic_request_waits_for_explicit_review() {
        let root = std::env::temp_dir().join(format!("companion-interrupted-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let wav = root.join("original.wav");
        std::fs::write(&wav, b"invalid original must never be submitted").unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "interrupted", &wav);
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            let s = &mut snapshot.host.sessions[0];
            s.capture_incomplete = true;
            s.recovery.attempt_count = 1;
        }
        let held = backend.apply_control(recovery_request(
            CompanionV1ControlAction::MeetingTranscribeAudio, "interrupted", true)).unwrap();
        let s = &held.host.sessions[0];
        assert_eq!(s.recovery.stage, "paused");
        assert_eq!(s.recovery.attempt_count, 1);
        assert_eq!(s.pending_reason.as_deref(), Some("capture_interrupted"));
        assert!(!s.recovery.capture_review_confirmed && !s.transcript_final);
        // A manual choice does not bypass original-file validation.
        assert!(backend.apply_control(recovery_request(
            CompanionV1ControlAction::MeetingTranscribeAudio, "interrupted", false)).is_err());
        assert!(!backend.snapshot().unwrap().host.sessions[0].recovery.capture_review_confirmed);
        // A stale automatic command cannot restore revoked recovery intent.
        backend.snapshot.lock().unwrap().host.sessions[0].recovery = Default::default();
        let revoked = backend.apply_control(recovery_request(
            CompanionV1ControlAction::MeetingTranscribeAudio, "interrupted", true)).unwrap();
        assert_eq!(revoked.host.sessions[0].recovery.intent, "none");
        assert!(!revoked.host.sessions[0].recovery.capture_review_confirmed);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn recovery_stale_automatic_request_cannot_bypass_persisted_backoff() {
        let root = std::env::temp_dir().join("companion-type-stale-recovery");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let wav = root.join("meeting.wav");
        std::fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "stale", &wav);
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            let session = &mut snapshot.host.sessions[0];
            session.recovery.stage = "retryBackoff".to_string();
            session.recovery.retry_stage = "transcription".to_string();
            session.recovery.attempt_count = 1;
            session.recovery.next_retry_at_unix_ms = Some(u64::MAX - 1);
        }
        let result = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::MeetingTranscribeAudio,
                "stale",
                true,
            ))
            .unwrap();
        assert_eq!(result.host.sessions[0].recovery.stage, "retryBackoff");
        assert_eq!(result.host.sessions[0].recovery.attempt_count, 1);
        assert!(!result.host.sessions[0].transcript_final);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn recovery_automatic_claim_rechecks_and_waits_for_an_active_recording() {
        let root = std::env::temp_dir().join("companion-type-active-recording-recovery");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let wav = root.join("meeting.wav");
        std::fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        std::fs::write(root.join("meeting.transcript.txt"), "must wait").unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "old-pending", &wav);
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            let mut recording = snapshot.host.sessions[0].clone();
            recording.id = "recording-now".to_string();
            recording.status = "recording".to_string();
            recording.recovery = CompanionV1MeetingRecovery::default();
            snapshot.host.sessions.push(recording);
            snapshot.host.active_session_id = Some("recording-now".to_string());
            snapshot.meeting.active = true;
        }
        let result = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::MeetingTranscribeAudio,
                "old-pending",
                true,
            ))
            .unwrap();
        let pending = result
            .host
            .sessions
            .iter()
            .find(|session| session.id == "old-pending")
            .unwrap();
        assert_eq!(pending.recovery.stage, "pendingTranscription");
        assert!(!pending.transcript_final);
        assert!(result.meeting.active);
        assert_eq!(result.host.active_session_id.as_deref(), Some("recording-now"));

        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            let pending = snapshot
                .host
                .sessions
                .iter_mut()
                .find(|session| session.id == "old-pending")
                .unwrap();
            pending.transcript_text = "already committed".to_string();
            pending.transcript_final = true;
            pending.recovery.stage = "paused".to_string();
            pending.recovery.retry_stage = "minutes".to_string();
        }
        let cached = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::MeetingTranscribeAudio,
                "old-pending",
                true,
            ))
            .unwrap();
        let pending = cached
            .host
            .sessions
            .iter()
            .find(|session| session.id == "old-pending")
            .unwrap();
        assert_eq!(pending.recovery.stage, "paused");
        assert!(cached.meeting.active);
        assert_eq!(cached.host.active_session_id.as_deref(), Some("recording-now"));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn recovery_automatic_claim_waits_for_device_button_recording_then_resumes() {
        let root = std::env::temp_dir().join("companion-type-device-recording-recovery");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let wav = root.join("meeting.wav");
        std::fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        std::fs::write(root.join("meeting.transcript.txt"), "resume after device stop").unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "device-busy-pending", &wav);
        backend.snapshot.lock().unwrap().device.recording = true;

        let waiting = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::MeetingTranscribeAudio,
                "device-busy-pending",
                true,
            ))
            .unwrap();
        assert_eq!(waiting.host.sessions[0].recovery.stage, "pendingTranscription");
        assert!(!waiting.host.sessions[0].transcript_final);

        backend.snapshot.lock().unwrap().device.recording = false;
        let resumed = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::MeetingTranscribeAudio,
                "device-busy-pending",
                true,
            ))
            .unwrap();
        assert!(resumed.host.sessions[0].transcript_final);
        assert_eq!(resumed.host.sessions[0].transcript_text, "resume after device stop");
        assert_eq!(resumed.host.sessions[0].recovery.stage, "pendingMinutes");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn recovery_automatic_processing_does_not_change_user_selected_session() {
        let root = std::env::temp_dir().join("companion-type-selection-recovery");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let wav = root.join("meeting.wav");
        std::fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        std::fs::write(
            root.join("meeting.transcript.txt"),
            "Decision: preserve selection.",
        )
        .unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "recover-me", &wav);
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            let mut other = snapshot.host.sessions[0].clone();
            other.id = "user-selected".to_string();
            other.recovery = CompanionV1MeetingRecovery::default();
            snapshot.host.sessions.push(other);
            snapshot.host.selected_session_id = Some("user-selected".to_string());
        }
        let result = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::MeetingTranscribeAudio,
                "recover-me",
                true,
            ))
            .unwrap();
        assert_eq!(result.host.selected_session_id.as_deref(), Some("user-selected"));
        let recovered = result
            .host
            .sessions
            .iter()
            .find(|session| session.id == "recover-me")
            .unwrap();
        assert!(recovered.transcript_final);
        assert_eq!(recovered.recovery.stage, "pendingMinutes");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn recovery_manual_retry_racing_startup_worker_is_single_flight_per_session() {
        let root = std::env::temp_dir().join("companion-type-single-flight-recovery");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let wav = root.join("meeting.wav");
        std::fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        std::fs::write(
            root.join("meeting.transcript.txt"),
            "Decision: invoke ASR once. Action: keep the durable result.",
        )
        .unwrap();
        let backend = Arc::new(FixtureCompanionBackend::new());
        install_recovery_session(&backend, "single-flight", &wav);
        let barrier = Arc::new(std::sync::Barrier::new(3));
        let mut threads = Vec::new();
        for automatic in [true, false] {
            let backend = Arc::clone(&backend);
            let barrier = Arc::clone(&barrier);
            threads.push(std::thread::spawn(move || {
                barrier.wait();
                backend.apply_control(recovery_request(
                    CompanionV1ControlAction::MeetingTranscribeAudio,
                    "single-flight",
                    automatic,
                ))
            }));
        }
        barrier.wait();
        for thread in threads {
            thread.join().unwrap().unwrap();
        }
        let result = backend.snapshot().unwrap();
        let session = &result.host.sessions[0];
        assert!(session.transcript_final);
        assert_eq!(session.recovery.stage, "pendingMinutes");
        assert_eq!(session.recovery.attempt_count, 0);
        assert_eq!(session.transcript_text.matches("invoke ASR once").count(), 1);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn recovery_stale_automatic_request_stops_after_privacy_revocation() {
        let root = std::env::temp_dir().join("companion-type-revoked-recovery");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let wav = root.join("meeting.wav");
        std::fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        std::fs::write(root.join("meeting.transcript.txt"), "must not be read").unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "revoked", &wav);
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            snapshot.host.sessions[0].recovery = CompanionV1MeetingRecovery::default();
        }
        let result = backend
            .apply_control(recovery_request(
                CompanionV1ControlAction::MeetingTranscribeAudio,
                "revoked",
                true,
            ))
            .unwrap();
        let session = &result.host.sessions[0];
        assert_eq!(session.recovery.intent, "none");
        assert!(session.transcript_text.is_empty());
        assert!(!session.transcript_final);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn recovery_imported_final_transcript_advances_to_minutes_only() {
        let root = std::env::temp_dir().join("companion-type-import-recovery");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let wav = root.join("meeting.wav");
        std::fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        let backend = FixtureCompanionBackend::new();
        install_recovery_session(&backend, "import-final", &wav);
        let mut request = recovery_request(
            CompanionV1ControlAction::MeetingImportTranscript,
            "import-final",
            false,
        );
        request.transcript_text = Some("Decision: imported final transcript.".to_string());
        let result = backend.apply_control(request).unwrap();
        let session = &result.host.sessions[0];
        assert!(session.transcript_final);
        assert_eq!(session.recovery.stage, "pendingMinutes");
        assert_eq!(session.recovery.retry_stage, "minutes");
        assert_eq!(session.recovery.attempt_count, 0);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn uncertain_meeting_start_retry_reuses_wire_identity_and_original_limit() {
        let mut pending = None;
        assert_eq!(
            reserve_pending_meeting_start(
                &mut pending,
                "meeting-retry-7",
                Some("wba-device-a"),
                60,
            )
            .unwrap(),
            60
        );
        /* A refreshed UI may submit a different duration, but an uncertain
         * retry must keep the original START bytes under the same request id. */
        assert_eq!(
            reserve_pending_meeting_start(
                &mut pending,
                "meeting-retry-7",
                Some("wba-device-a"),
                90,
            )
            .unwrap(),
            60
        );
        assert_eq!(pending.as_ref().unwrap().max_seconds, 60);
    }

    #[test]
    fn uncertain_meeting_start_cannot_move_to_another_session_or_device() {
        let mut pending = None;
        reserve_pending_meeting_start(&mut pending, "meeting-owner-a", Some("wba-device-a"), 60)
            .unwrap();
        assert!(reserve_pending_meeting_start(
            &mut pending,
            "meeting-owner-b",
            Some("wba-device-a"),
            60,
        )
        .unwrap_err()
        .contains("outcome is still unknown"));
        assert!(reserve_pending_meeting_start(
            &mut pending,
            "meeting-owner-a",
            Some("wba-device-b"),
            60,
        )
        .unwrap_err()
        .contains("bound to device"));
        assert_eq!(pending.as_ref().unwrap().session_id, "meeting-owner-a");
    }

    #[test]
    fn only_an_explicit_board_start_rejection_is_a_definitive_retry_end() {
        assert!(meeting_start_rejection_is_definitive(
            "board rejected V1 meeting command=1 request_id=42 error=2"
        ));
        assert!(!meeting_start_rejection_is_definitive(
            "meeting_status timeout command=1 request_id=42 expected_state=1"
        ));
        assert!(!meeting_start_rejection_is_definitive(
            "write V1 meeting_control command=1: device disconnected"
        ));
    }

    #[test]
    fn measured_wba_identity_updates_model_and_unknown_probe_fails_closed() {
        let mut snapshot = fixture_snapshot();
        snapshot.connected = true;
        snapshot.device.connected = true;
        let measured = CompanionDeviceIdentity {
            firmware_version: Some(0x0001_0101),
            build_id: Some(0x2026_1003),
            board_id: Some(0x5742_4155),
            mcu_uid: Some("1032547698badcfe01234567".to_string()),
            ui_generation: Some(33),
            recording_capacity: None,
            recording: Some(true),
            imu_supported: Some(true),
            imu_online: Some(true),
            imu_sample_hz: Some(52),
            speaker_supported: Some(true),
            speaker_online: Some(true),
            speaker_volume: Some(65),
            speaker_find_supported: None,
        };
        apply_device_identity(&mut snapshot, &measured);
        assert_eq!(snapshot.device.firmware_version, Some(0x0001_0101));
        assert_eq!(snapshot.device.mcu_uid, measured.mcu_uid);
        assert_eq!(snapshot.device.ui_generation, Some(33));
        assert_eq!(
            snapshot.device.hardware_revision.as_deref(),
            Some("COMPANION-WBA55-V1.1")
        );
        assert!(snapshot.imu.supported && snapshot.imu.online);
        assert!(snapshot.speaker.supported && snapshot.speaker.online);
        assert_eq!(snapshot.speaker.volume, 65);
        assert!(snapshot.device.recording);

        let unknown = CompanionDeviceIdentity {
            firmware_version: None,
            build_id: None,
            board_id: None,
            mcu_uid: None,
            ui_generation: None,
            recording_capacity: None,
            recording: None,
            imu_supported: None,
            imu_online: None,
            imu_sample_hz: None,
            speaker_supported: None,
            speaker_online: None,
            speaker_volume: None,
            speaker_find_supported: None,
        };
        apply_device_identity(&mut snapshot, &unknown);
        assert!(!snapshot.imu.supported && !snapshot.imu.online);
        assert!(!snapshot.speaker.supported && !snapshot.speaker.online);
        assert_eq!(snapshot.imu.sample_hz, 0);
        assert_eq!(snapshot.speaker.volume, 0);
        assert_eq!(snapshot.speaker.status, "unknown");
        assert!(snapshot.device.recording);
        assert!(snapshot.device.firmware_version.is_none());
        assert!(snapshot.device.build_id.is_none());
        assert!(snapshot.device.board_id.is_none());
        assert!(snapshot.device.hardware_revision.is_none());
        assert!(snapshot.device.mcu_uid.is_none());
        assert!(snapshot.device.ui_generation.is_none());
    }

    #[test]
    fn speaker_prompt_names_are_bounded_to_firmware_product_cues() {
        assert_eq!(speaker_prompt_id(None).unwrap(), 0);
        assert_eq!(speaker_prompt_id(Some("recordingStarted")).unwrap(), 1);
        assert_eq!(speaker_prompt_id(Some("recordingStopped")).unwrap(), 2);
        assert_eq!(speaker_prompt_id(Some("error")).unwrap(), 3);
        assert!(speaker_prompt_id(Some("spokenMinutes")).is_err());
    }

    #[test]
    fn active_recording_id_is_not_treated_as_already_pulled() {
        let mut snapshot = fixture_snapshot();
        let request = CompanionV1ControlRequest { minutes_template: None, recording_source: None,
            action: CompanionV1ControlAction::MeetingStart,
            context_note_revision: None, ble_name: None,
            session_id: Some("filter-regression".to_string()),
            prompt_id: None,
            title: None,
            transcript_text: None,
            meeting_mode: Some("offlineStore".to_string()),
            audio_path: Some("C:/recordings/filter-regression.wav".to_string()),
            audio_bytes: Some(12_345),
            device_id: None,
            duration_ms: Some(1_000),
        };
        let mut active =
            crate::companion_v1::synced_device_session(&snapshot, &request, "filter-regression");
        active.source_device_id = Some("AA:BB:CC:DD:EE:FF".to_string());
        active.device_recording_id = Some(901);
        active.device_total_length = None;
        active.device_sha256 = None;
        let mut verified = active.clone();
        verified.device_recording_id = Some(900);
        verified.device_total_length = Some(12_345);
        verified.device_sha256 = Some("a".repeat(64));
        verified.device_reclaimed = true;
        snapshot.host.sessions = vec![active, verified];

        assert_eq!(
            verified_device_recording_ids(&snapshot, Some("AA:BB:CC:DD:EE:FF")),
            vec![900]
        );
    }

    #[test]
    fn recording_identity_is_namespaced_by_source_device_and_legacy_never_suppresses_pull() {
        assert_eq!(
            device_recording_session_id(Some("AA:BB:CC:DD:EE:FF"), 42),
            "device-aabbccddeeff-recording-42"
        );
        assert_eq!(
            device_recording_session_id(Some("11:22:33:44:55:66"), 42),
            "device-112233445566-recording-42"
        );

        let mut snapshot = fixture_snapshot();
        let request = CompanionV1ControlRequest { minutes_template: None, recording_source: None,
            action: CompanionV1ControlAction::DeviceSyncRecordings,
            context_note_revision: None, ble_name: None,
            session_id: Some("device-recording-42".to_string()),
            prompt_id: None,
            title: None,
            transcript_text: None,
            meeting_mode: Some("offlineStore".to_string()),
            audio_path: Some("C:/legacy.wav".to_string()),
            audio_bytes: Some(42),
            device_id: None,
            duration_ms: Some(42),
        };
        let mut legacy = crate::companion_v1::synced_device_session(&snapshot, &request, "legacy");
        legacy.device_recording_id = Some(42);
        legacy.device_total_length = Some(42);
        legacy.device_sha256 = Some("a".repeat(64));
        legacy.source_device_id = None;
        let mut other_device = legacy.clone();
        other_device.id = "device-112233445566-recording-42".to_string();
        other_device.source_device_id = Some("11:22:33:44:55:66".to_string());
        other_device.device_reclaimed = true;
        snapshot.host.sessions = vec![legacy, other_device];
        assert!(verified_device_recording_ids(
            &snapshot,
            Some("AA:BB:CC:DD:EE:FF")
        )
        .is_empty());
        assert_eq!(
            verified_device_recording_ids(&snapshot, Some("11:22:33:44:55:66")),
            vec![42]
        );

        snapshot.device.device_id = Some("AA:BB:CC:DD:EE:FF".to_string());
        let implicit_target = effective_device_target(
            None,
            snapshot.device.device_id.as_deref(),
        );
        assert_eq!(implicit_target.as_deref(), Some("AA:BB:CC:DD:EE:FF"));
        assert!(verified_device_recording_ids(&snapshot, implicit_target.as_deref()).is_empty());

        let switched_target = effective_device_target(
            Some("11:22:33:44:55:66"),
            snapshot.device.device_id.as_deref(),
        );
        assert_eq!(switched_target.as_deref(), Some("11:22:33:44:55:66"));
        assert_eq!(
            verified_device_recording_ids(&snapshot, switched_target.as_deref()),
            vec![42]
        );

        assert_eq!(effective_device_target(None, None), None);
        assert!(verified_device_recording_ids(&snapshot, None).is_empty());
    }

    #[test]
    fn board_online_live_partial_replaces_durable_prefix_preview() {
        let backend = FixtureCompanionBackend::new();
        let session_id = "board-online-partial-reconcile-test";
        backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStart,
                context_note_revision: None, ble_name: None,
                session_id: Some(session_id.to_string()),
                prompt_id: None,
                title: Some("Board partial reconcile".to_string()),
                transcript_text: None,
                meeting_mode: Some("onlineLive".to_string()),
                audio_path: Some(format!("board://online/{session_id}")),
                audio_bytes: Some(0),
                device_id: None,
                duration_ms: Some(0),
            })
            .expect("start board session");
        backend
            .set_board_online_live_partial(session_id, "第一段耐久前缀")
            .expect("first partial");
        let snapshot = backend
            .set_board_online_live_partial(session_id, "第二段最新窗口")
            .expect("second partial");
        let session = snapshot
            .host
            .sessions
            .iter()
            .find(|session| session.id == session_id)
            .expect("session");
        assert_eq!(session.live_transcript_text, "第二段最新窗口");
        assert_eq!(session.transcript_text, "第二段最新窗口");
        assert!(!session.transcript_text.contains("第一段"));
    }

    #[test]
    fn durable_board_batch_creates_three_stable_sessions_and_exact_delete_preserves_neighbors() {
        let mut snapshot = fixture_snapshot();
        snapshot.host.sessions.clear();
        let make = |id: u32| CompanionSyncedRecording {
            recording_id: id,
            duration_ms: 45_000 + id,
            total_length: 90_000 + id,
            sha256: format!("{:064x}", id),
            recording_path: format!("C:/recordings/device-{id}.wav"),
            device_reclaimed: false, capture_incomplete: false,
        };
        let three = vec![make(41), make(42), make(43)];
        let expected_id = |id: u32| format!("device-recording-{id}-{:064x}", id);
        merge_synced_recordings(&mut snapshot, &three);
        assert_eq!(snapshot.host.sessions.len(), 3);
        assert_eq!(snapshot.device.recordings_available, 3);
        assert_eq!(
            snapshot.host.selected_session_id.as_deref(),
            Some(expected_id(43).as_str())
        );
        let identities = snapshot
            .host
            .sessions
            .iter()
            .map(|session| {
                (
                    session.device_recording_id.unwrap(),
                    session.device_sha256.clone().unwrap(),
                )
            })
            .collect::<std::collections::BTreeMap<_, _>>();
        assert_eq!(identities.len(), 3);

        // Reconnect updates id=42 in place; it must not duplicate or collapse the other ids.
        let mut replay = make(42);
        replay.recording_path = "C:/recordings/device-42-resumed.wav".to_string();
        merge_synced_recordings(&mut snapshot, &[replay]);
        assert_eq!(snapshot.host.sessions.len(), 3);
        assert_eq!(
            snapshot
                .host
                .sessions
                .iter()
                .find(|s| s.id == expected_id(42))
                .unwrap()
                .audio_path
                .as_deref(),
            Some("C:/recordings/device-42-resumed.wav")
        );

        // The reducer's selected delete removes exactly the requested middle session.
        let before_41 = identities.get(&41).cloned().unwrap();
        let before_43 = identities.get(&43).cloned().unwrap();
        let deleted = apply_fixture_control(
            snapshot,
            CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::PrivacyDeleteSession,
                context_note_revision: None, ble_name: None,
                session_id: Some(expected_id(42)),
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
        assert_eq!(deleted.host.sessions.len(), 2);
        assert!(deleted
            .host
            .sessions
            .iter()
            .all(|s| s.device_recording_id != Some(42)));
        assert_eq!(
            deleted
                .host
                .sessions
                .iter()
                .find(|s| s.device_recording_id == Some(41))
                .unwrap()
                .device_sha256
                .as_deref(),
            Some(before_41.as_str())
        );
        assert_eq!(
            deleted
                .host
                .sessions
                .iter()
                .find(|s| s.device_recording_id == Some(43))
                .unwrap()
                .device_sha256
                .as_deref(),
            Some(before_43.as_str())
        );
    }

    #[test]
    fn fixture_backend_exposes_type_style_service_boundaries() {
        let backend = FixtureCompanionBackend::new();
        let capabilities = backend.capabilities();
        assert_eq!(capabilities.backend_id, "companion-type.hybrid-host");
        assert_eq!(
            capabilities.services.recording.provider_id,
            "host-microphone-wav"
        );
        assert_eq!(
            capabilities.services.transcription.provider_id,
            "companion-type-transcription"
        );
        assert!(capabilities.services.minutes.supported);
        assert_eq!(
            capabilities.services.minutes.provider_id,
            "companion-type-minutes"
        );
    }

    #[test]
    fn mechanical_voice_session_transcribe_and_minutes() {
        let root = std::env::temp_dir().join("companion-type-mechanical-voice-accept");
        let _ = std::fs::create_dir_all(&root);
        let wav = root.join("mechanical-meeting.wav");
        // Minimal valid-ish RIFF header + silence payload for file existence.
        let mut bytes = Vec::new();
        bytes.extend_from_slice(b"RIFF");
        bytes.extend_from_slice(&(36_u32 + 3200).to_le_bytes());
        bytes.extend_from_slice(b"WAVE");
        bytes.extend_from_slice(b"fmt ");
        bytes.extend_from_slice(&16_u32.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes()); // PCM
        bytes.extend_from_slice(&1_u16.to_le_bytes()); // mono
        bytes.extend_from_slice(&16_000_u32.to_le_bytes());
        bytes.extend_from_slice(&(16_000_u32 * 2).to_le_bytes());
        bytes.extend_from_slice(&2_u16.to_le_bytes());
        bytes.extend_from_slice(&16_u16.to_le_bytes());
        bytes.extend_from_slice(b"data");
        bytes.extend_from_slice(&3200_u32.to_le_bytes());
        bytes.extend(std::iter::repeat(0u8).take(3200));
        std::fs::write(&wav, &bytes).unwrap();
        let sidecar = root.join("mechanical-meeting.transcript.txt");
        let spoken = [
            "Decision: Companion host owns long meeting recordings.",
            "Action owner: Chen due: Friday validates mechanical voice minutes.",
            "Question: is offline needs_transcription explicit?",
        ]
        .join("\n");
        std::fs::write(&sidecar, &spoken).unwrap();

        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
        std::env::remove_var("COMPANION_TYPE_MINUTES_COMMAND");
        std::env::remove_var("DEEPSEEK_API_KEY");
        std::env::remove_var("COMPANION_TYPE_DEFAULT_MEETING_MODE");

        let backend = FixtureCompanionBackend::new();
        let started = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStart,
                context_note_revision: None, ble_name: None,
                session_id: Some("mech-1".to_string()),
                prompt_id: None,
                title: Some("Mechanical voice acceptance".to_string()),
                transcript_text: None,
                meeting_mode: Some("offlineStore".to_string()),
                audio_path: Some(wav.to_string_lossy().to_string()),
                audio_bytes: Some(bytes.len() as u64),
                device_id: None,
                duration_ms: Some(1000),
            })
            .unwrap();
        assert_eq!(started.meeting.status, "recording");
        // This is a controlled local WAV, not a Companion device recording.
        // Keep the real device identity/STOP guard intact in the product.
        backend.snapshot.lock().unwrap().host.sessions[0].source = "controlledLocalAudioFixture".into();

        let stopped = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStop,
                context_note_revision: None, ble_name: None,
                session_id: Some("mech-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: Some(wav.to_string_lossy().to_string()),
                audio_bytes: Some(bytes.len() as u64),
                device_id: None,
                duration_ms: Some(1000),
            })
            .unwrap();
        let stopped_session = stopped.host.sessions.first().unwrap();
        assert_eq!(stopped_session.status, "captured");
        assert_eq!(
            stopped_session.pending_reason.as_deref(),
            Some("needs_transcription")
        );

        let transcribed = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingTranscribeAudio,
                context_note_revision: None, ble_name: None,
                session_id: Some("mech-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: Some(wav.to_string_lossy().to_string()),
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        let transcribed_session = transcribed.host.sessions.first().unwrap();
        assert_eq!(transcribed.meeting.status, "transcribed");
        assert!(transcribed_session.transcript_text.contains("Decision"));
        assert!(transcribed_session.pending_reason.is_none());

        let minutes = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingGenerateMinutes,
                context_note_revision: None, ble_name: None,
                session_id: Some("mech-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        let session = minutes.host.sessions.first().unwrap();
        assert_eq!(minutes.meeting.status, "minutesReady");
        let generated = session.minutes.as_ref().unwrap();
        assert_eq!(generated.source, "rules_l0");
        assert_eq!(generated.quality, "draft");
        assert!(!generated.decisions.is_empty());
        assert!(!generated.action_items.is_empty());
        assert!(session.export_markdown.contains("## Action Items"));
    }

    #[test]
    fn fixture_backend_keeps_state_between_controls() {
        let backend = FixtureCompanionBackend::new();
        let started = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStart,
                context_note_revision: None, ble_name: None,
                session_id: None,
                prompt_id: None,
                title: Some("Backend state chain".to_string()),
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(started.host.sessions.len(), 1);
        assert!(started.host.sessions[0].audio_path.is_some());

        let stopped = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
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
            })
            .unwrap();
        assert_eq!(stopped.host.sessions.len(), 1);
        assert!(stopped.host.sessions[0].duration_ms > 0);
        assert!(stopped.host.sessions[0].audio_path.is_some());
    }

    #[test]
    fn backend_transcribes_audio_with_companion_type_sidecar_provider() {
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");
        std::env::remove_var("DEEPSEEK_API_KEY");
        std::env::remove_var("COMPANION_TYPE_DEFAULT_MEETING_MODE");
        let root =
            std::env::temp_dir().join("companion-type-independent-transcription-backend-test");
        let _ = std::fs::create_dir_all(&root);
        let audio = root.join("meeting.wav");
        let sidecar = root.join("meeting.transcript.txt");
        let mut wav=denzic_host_audio_v1_core::wav::wav_header(3200).to_vec();
        wav.extend(vec![0u8; 3200]);
        std::fs::write(&audio, &wav).unwrap();
        std::fs::write(
            &sidecar,
            "Decision: Companion-Type owns the ASR boundary.\nAction: Maya validates independent minutes.",
        )
        .unwrap();

        let backend = FixtureCompanionBackend::new();
        let started = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStart,
                context_note_revision: None, ble_name: None,
                session_id: Some("sidecar-session".to_string()),
                prompt_id: None,
                title: Some("Independent ASR".to_string()),
                transcript_text: None,
                meeting_mode: Some("offlineStore".to_string()),
                audio_path: Some(audio.to_string_lossy().to_string()),
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(started.host.sessions[0].source, "deviceFlash");
        assert_eq!(
            started.host.sessions[0].audio_path.as_deref(),
            Some(audio.to_string_lossy().as_ref())
        );
        // The supplied WAV is a local controlled fixture, not device audio.
        backend.snapshot.lock().unwrap().host.sessions[0].source = "controlledLocalAudioFixture".into();

        let stopped = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStop,
                context_note_revision: None, ble_name: None,
                session_id: Some("sidecar-session".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: Some(90_000),
            })
            .unwrap();
        assert_eq!(stopped.host.sessions[0].status, "captured");

        let transcribed = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingTranscribeAudio,
                context_note_revision: None, ble_name: None,
                session_id: Some("sidecar-session".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(transcribed.meeting.status, "transcribed");
        assert!(transcribed.host.sessions[0]
            .transcript_text
            .contains("Companion-Type owns the ASR boundary"));
        assert!(transcribed
            .last_control
            .as_ref()
            .unwrap()
            .message
            .contains("companion-type-sidecar-transcript"));

        let minutes = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingGenerateMinutes,
                context_note_revision: None, ble_name: None,
                session_id: Some("sidecar-session".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(minutes.meeting.status, "minutesReady");
        assert_eq!(
            minutes.host.sessions[0]
                .minutes
                .as_ref()
                .unwrap()
                .decisions
                .len(),
            1
        );
        assert_eq!(
            minutes.host.sessions[0]
                .minutes
                .as_ref()
                .unwrap()
                .action_items
                .len(),
            1
        );
    }

    #[test]
    fn live_asr_mock_online_partials_before_stop() {
        std::env::set_var("COMPANION_TYPE_LIVE_ASR_MOCK", "1");
        std::env::set_var("COMPANION_TYPE_HOST_RECORDING_MODE", "synthetic");
        std::env::remove_var("COMPANION_TYPE_LIVE_ASR_OFF");
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");

        let backend = FixtureCompanionBackend::new();
        let started = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStart,
                context_note_revision: None, ble_name: None,
                session_id: Some("live-1".to_string()),
                prompt_id: None,
                title: Some("Live streaming mock".to_string()),
                transcript_text: None,
                meeting_mode: Some("onlineLive".to_string()),
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(started.meeting.status, "recording");
        assert!(
            started
                .last_control
                .as_ref()
                .map(|c| c.message.contains("liveAsr=mock-streaming")
                    || c.message.contains("liveAsr="))
                .unwrap_or(false),
            "start should report liveAsr mode: {:?}",
            started.last_control
        );

        // Wait for mock partials (3 steps × 180ms).
        std::thread::sleep(std::time::Duration::from_millis(700));
        let mid = backend.snapshot().unwrap();
        let mid_session = mid
            .host
            .sessions
            .iter()
            .find(|s| s.id == "live-1")
            .expect("session");
        assert!(
            !mid_session.live_transcript_text.trim().is_empty()
                || !mid_session.transcript_text.trim().is_empty(),
            "mid-meeting live text must appear before stop; live={:?} transcript={:?}",
            mid_session.live_transcript_text,
            mid_session.transcript_text
        );

        let stopped = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStop,
                context_note_revision: None, ble_name: None,
                session_id: Some("live-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: Some(1000),
            })
            .unwrap();
        let stopped_session = stopped
            .host
            .sessions
            .iter()
            .find(|s| s.id == "live-1")
            .expect("session");
        assert_eq!(stopped_session.status, "transcribed");
        assert!(stopped_session.pending_reason.is_none());
        assert!(
            stopped_session.transcript_text.contains("在线实时转写")
                || stopped_session.transcript_text.contains("会议开始"),
            "stop should seal live stream text: {}",
            stopped_session.transcript_text
        );
        std::env::remove_var("COMPANION_TYPE_LIVE_ASR_MOCK");
    }

    /// Product IPC closure: apply_control(MeetingStart -> Stop ->
    /// TranscribeAudio -> GenerateMinutes) end-to-end through the native
    /// DeepSeek path (no python, no COMPANION_TYPE_MINUTES_COMMAND). This is
    /// the packaged-build code path the UI exercises. Uses a sidecar
    /// transcript so it does not depend on real ASR. #[ignore]'d: needs
    /// DEEPSEEK_API_KEY + network.
    #[test]
    #[ignore = "requires DEEPSEEK_API_KEY + network; runs the product IPC minutes path"]
    fn product_minutes_path_native_deepseek_end_to_end() {
        if std::env::var("DEEPSEEK_API_KEY")
            .map(|v| v.trim().is_empty())
            .unwrap_or(true)
        {
            eprintln!("skipped: DEEPSEEK_API_KEY not set");
            return;
        }
        std::env::remove_var("COMPANION_TYPE_MINUTES_COMMAND");
        std::env::remove_var("COMPANION_TYPE_MINUTES_ARGS");
        std::env::remove_var("COMPANION_TYPE_TRANSCRIPT_TEXT");
        std::env::remove_var("COMPANION_TYPE_ASR_COMMAND");

        let root = std::env::temp_dir().join("companion-type-product-native-minutes");
        let _ = std::fs::create_dir_all(&root);
        let wav = root.join("product-native.wav");
        let mut bytes = Vec::new();
        bytes.extend_from_slice(b"RIFF");
        bytes.extend_from_slice(&(36_u32 + 3200).to_le_bytes());
        bytes.extend_from_slice(b"WAVE");
        bytes.extend_from_slice(b"fmt ");
        bytes.extend_from_slice(&16_u32.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes());
        bytes.extend_from_slice(&1_u16.to_le_bytes());
        bytes.extend_from_slice(&16_000_u32.to_le_bytes());
        bytes.extend_from_slice(&(16_000_u32 * 2).to_le_bytes());
        bytes.extend_from_slice(&2_u16.to_le_bytes());
        bytes.extend_from_slice(&16_u16.to_le_bytes());
        bytes.extend_from_slice(b"data");
        bytes.extend_from_slice(&3200_u32.to_le_bytes());
        bytes.extend(std::iter::repeat(0u8).take(3200));
        std::fs::write(&wav, &bytes).unwrap();
        let sidecar = root.join("product-native.transcript.txt");
        std::fs::write(
            &sidecar,
            "陈明：默认编码用 Opus 16 单声道，失败必须 fail closed 并提示重录。\n\
             Billy：录音区 14 兆连续，UI 两兆独立，不作录音缓冲。\n\
             决定：发版默认 codec 是 Opus 16，半率 IMA 仅调试开关且默认关闭。\n\
             行动：陈明周五前输出压缩同步说明；Billy 本周完成 5 分钟空中路径闭环。",
        )
        .unwrap();

        let backend = FixtureCompanionBackend::new();
        backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStart,
                context_note_revision: None, ble_name: None,
                session_id: Some("prod-native-1".to_string()),
                prompt_id: None,
                title: Some("产品纪要闭环".to_string()),
                transcript_text: None,
                meeting_mode: Some("offlineStore".to_string()),
                audio_path: Some(wav.to_string_lossy().to_string()),
                audio_bytes: Some(bytes.len() as u64),
                device_id: None,
                duration_ms: Some(1000),
            })
            .unwrap();
        backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStop,
                context_note_revision: None, ble_name: None,
                session_id: Some("prod-native-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: Some(wav.to_string_lossy().to_string()),
                audio_bytes: Some(bytes.len() as u64),
                device_id: None,
                duration_ms: Some(1000),
            })
            .unwrap();
        let transcribed = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingTranscribeAudio,
                context_note_revision: None, ble_name: None,
                session_id: Some("prod-native-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: Some(wav.to_string_lossy().to_string()),
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(transcribed.meeting.status, "transcribed");

        let minutes_snap = backend
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingGenerateMinutes,
                context_note_revision: None, ble_name: None,
                session_id: Some("prod-native-1".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();
        assert_eq!(minutes_snap.meeting.status, "minutesReady");
        let session = minutes_snap
            .host
            .sessions
            .iter()
            .find(|s| s.id == "prod-native-1")
            .expect("session present");
        let m = session.minutes.as_ref().expect("minutes generated");
        // The product path must have routed through native DeepSeek, not L0.
        assert_eq!(
            m.source, "llm_deepseek",
            "product path must use native deepseek; llm_note={:?}",
            m.llm_note
        );
        assert_eq!(m.quality, "final");
        assert!(
            m.llm_note.is_none(),
            "unexpected downgrade: {:?}",
            m.llm_note
        );
        assert!(!m.decisions.is_empty());
        assert!(session.export_markdown.contains("Opus"));
        // Echo must not carry a downgrade marker on the success path.
        let echo = minutes_snap.last_control.as_ref().expect("echo");
        assert!(
            !echo.message.contains("—"),
            "echo leaked downgrade note: {}",
            echo.message
        );
    }

    #[test]
    fn privacy_erase_all_is_local_only_and_refuses_to_interrupt_recording() {
        let backend = FixtureCompanionBackend::new();
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            snapshot.meeting.active = true;
            snapshot.meeting.status = "recording".to_string();
        }
        let request = CompanionV1ControlRequest { minutes_template: None, recording_source: None,
            action: CompanionV1ControlAction::PrivacyEraseAll,
            context_note_revision: None, ble_name: None,
            session_id: None,
            prompt_id: None,
            title: None,
            transcript_text: None,
            meeting_mode: None,
            audio_path: None,
            audio_bytes: None,
            device_id: Some("AA:BB:CC:DD:EE:FF".to_string()),
            duration_ms: None,
        };
        assert!(backend.apply_control(request.clone()).is_err());
        assert!(backend.snapshot().unwrap().meeting.active);
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            snapshot.meeting.active = false;
            snapshot.meeting.status = "idle".to_string();
        }
        let cleared = backend.apply_control(request).unwrap();
        assert!(cleared.host.sessions.is_empty());
        assert!(cleared
            .last_control
            .as_ref()
            .unwrap()
            .message
            .contains("device's local menu"));
    }

    #[test]
    fn exact_delete_rejects_stale_selection_and_wrong_source_device() {
        let backend = FixtureCompanionBackend::new();
        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            let request = CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::DeviceSyncRecordings,
                context_note_revision: None, ble_name: None,
                session_id: Some("owned-recording".to_string()),
                prompt_id: None,
                title: Some("owned".to_string()),
                transcript_text: None,
                meeting_mode: Some("offlineStore".to_string()),
                audio_path: Some("C:/missing.wav".to_string()),
                audio_bytes: Some(100),
                device_id: Some("AA:BB:CC:DD:EE:FF".to_string()),
                duration_ms: Some(1000),
            };
            let mut session = crate::companion_v1::synced_device_session(
                &snapshot,
                &request,
                "owned-recording",
            );
            session.device_recording_id = Some(7);
            session.device_total_length = Some(100);
            session.device_sha256 = Some("a".repeat(64));
            session.source_device_id = Some("AA:BB:CC:DD:EE:FF".to_string());
            snapshot.host.sessions = vec![session];
            snapshot.host.selected_session_id = Some("other-session".to_string());
            snapshot.device.device_id = Some("11:22:33:44:55:66".to_string());
        }
        let request = CompanionV1ControlRequest { minutes_template: None, recording_source: None,
            action: CompanionV1ControlAction::PrivacyDeleteSession,
            context_note_revision: None, ble_name: None,
            session_id: Some("owned-recording".to_string()),
            prompt_id: None,
            title: None,
            transcript_text: None,
            meeting_mode: None,
            audio_path: None,
            audio_bytes: None,
            device_id: Some("11:22:33:44:55:66".to_string()),
            duration_ms: None,
        };
        assert!(backend
            .apply_control(request.clone())
            .unwrap_err()
            .contains("no longer the selected"));
        backend.snapshot.lock().unwrap().host.selected_session_id =
            Some("owned-recording".to_string());
        assert!(backend
            .apply_control(request.clone())
            .unwrap_err()
            .contains("belongs to device"));
        assert_eq!(backend.snapshot().unwrap().host.sessions.len(), 1);

        {
            let mut snapshot = backend.snapshot.lock().unwrap();
            snapshot.host.sessions[0].device_reclaimed = true;
        }
        let mut reclaimed_request = request;
        reclaimed_request.device_id = Some("AA:BB:CC:DD:EE:FF".to_string());
        let deleted = backend.apply_control(reclaimed_request).unwrap();
        assert!(deleted.host.sessions.is_empty());
        assert!(deleted
            .last_control
            .as_ref()
            .unwrap()
            .message
            .contains("already reclaimed"));
    }
}
