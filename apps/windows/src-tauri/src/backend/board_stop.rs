//! Preserve the real device STOP before its potentially slow or failed pull.
use super::{ble_bridge::CompanionMeetingControlReport, board_meeting, device_connection};
use crate::companion_v1::{CompanionV1ControlAction, CompanionV1ControlEcho, CompanionV1Snapshot};

/// A retry cannot improve an already durably received and exactly reclaimed
/// recording. Do not write STOP again, reopen BLE, rerun ASR or replace edits.
/// Pending reclaim is deliberately excluded: a host file is not its ACK.
pub(super) fn completed_retry(
    snapshot: &mut CompanionV1Snapshot,
    session_id: &str,
) -> Result<bool, String> {
    let Some(session) = snapshot.host.sessions.iter().find(|session| session.id == session_id) else {
        return Ok(false);
    };
    if !matches!(session.source.as_str(), "boardDevice" | "deviceFlash")
        || !session.audio_stored || !session.retention.audio_cached || !session.device_reclaimed
        || session.status == "recording" || snapshot.meeting.active || snapshot.device.recording
        || snapshot.host.active_session_id.is_some()
    {
        return Ok(false);
    }
    if snapshot.host.persistence.status != "ready" {
        return Err("这场录音已结束，但会议库尚未保存；请先重试保存。".into());
    }
    if !session.device_recording_id.is_some_and(|id| id != 0)
        || !session.source_device_id.as_deref().is_some_and(device_connection::stable_device_id)
        || !session.device_total_length.is_some_and(|bytes| bytes > 0)
        || !session.device_sha256.as_deref().is_some_and(|sha|
            sha.len() == 64 && sha.bytes().all(|byte| byte.is_ascii_hexdigit()))
    {
        return Err("这场录音的已保存记录不完整，未重发停止或覆盖原会议。".into());
    }
    let unavailable = || "这场录音已结束，但本机原音已移动、损坏或与保存记录不一致；未重发停止或覆盖会议。".to_string();
    let path = session.audio_path.as_deref().map(std::path::Path::new)
        .filter(|path| path.is_absolute()).ok_or_else(unavailable)?;
    let metadata = std::fs::symlink_metadata(path).map_err(|_| unavailable())?;
    if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() != session.audio_bytes
        || super::meeting_workspace::wav_duration_ms(path).map_err(|_| unavailable())? != session.duration_ms
    {
        return Err(unavailable());
    }
    snapshot.updated_at = super::observation_timestamp();
    snapshot.last_control = Some(CompanionV1ControlEcho {
        action: CompanionV1ControlAction::MeetingStop,
        characteristic_uuid: crate::companion_v1::COMPANION_V1_HOST_DEVICE_CHANNEL,
        payload_hex: String::new(), accepted: true,
        message: "这场录音已结束，原音已保存；保留已有转写和纪要。".into(),
    });
    Ok(true)
}

pub(super) fn observe(
    snapshot: &mut CompanionV1Snapshot,
    session_id: &str,
    report: &CompanionMeetingControlReport,
    observed_at: &str,
) -> Result<(), String> {
    let stopped = chrono::DateTime::parse_from_rfc3339(observed_at)
        .map_err(|_| "设备停止确认缺少有效时间，未修改会议。")?;
    if report.state != 2 || report.last_error != 0 || report.meeting_id == 0
        || snapshot.host.active_session_id.as_deref().is_some_and(|id| id != session_id)
        || snapshot.device.device_id.as_deref().is_some_and(|id|
            !device_connection::same_device_id(id, &report.device_id))
    {
        return Err("设备停止确认与当前录音不一致，未修改会议。".into());
    }
    let index = snapshot.host.sessions.iter().position(|session| session.id == session_id)
        .ok_or("设备停止确认找不到原会议，未创建替代录音。")?;
    let session = &snapshot.host.sessions[index];
    if !matches!(session.source.as_str(), "boardDevice" | "deviceFlash")
        || session.device_recording_id != Some(report.meeting_id)
        || !session.source_device_id.as_deref().is_some_and(|id|
            device_connection::same_device_id(id, &report.device_id))
        || session.started_at.as_deref().and_then(|value|
            chrono::DateTime::parse_from_rfc3339(value).ok()).is_some_and(|started| stopped < started)
    {
        return Err("设备停止确认与原会议身份或开始时间不一致，未覆盖录音。".into());
    }

    let mut pending = session.clone();
    if !pending.audio_stored {
        // The device ACK confirms capture, not receipt, transcription or reclaim.
        let first_stop = pending.stopped_at.clone().filter(|value|
            chrono::DateTime::parse_from_rfc3339(value).is_ok());
        board_meeting::pending_sync(&mut pending, report.meeting_id, report.duration_ms,
            first_stop.as_deref().unwrap_or(observed_at))?;
    } else {
        // An idempotent STOP must not erase an already received file or its
        // exact reclaim receipt while reconnecting the same meeting.
        board_meeting::retain_capture_dates(&mut pending);
        if pending.stopped_at.is_none() { pending.stopped_at = Some(observed_at.into()); }
    }
    snapshot.meeting.duration_ms = pending.duration_ms;
    snapshot.meeting.status = pending.status.clone();
    snapshot.host.sessions[index] = pending;
    snapshot.host.active_session_id = None;
    snapshot.meeting.active = false;
    snapshot.device.recording = false;
    snapshot.updated_at = observed_at.into();
    snapshot.last_control = Some(CompanionV1ControlEcho {
        action: CompanionV1ControlAction::MeetingStop,
        characteristic_uuid: crate::companion_v1::COMPANION_V1_HOST_DEVICE_CHANNEL,
        payload_hex: String::new(), accepted: true,
        message: "设备已停止录音，正在同步原音；传输中断后可继续同步这场会议。".into(),
    });
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{apply_control_at, fixture_snapshot};
    const DEVICE: &str = "C8:92:FF:DD:3B:CA";
    const START: &str = "2026-10-08T07:06:55.130Z";
    const STOP: &str = "2026-10-08T07:11:55.550Z";

    #[test]
    fn completed_retry_actual_coordinator_keeps_saved_original_without_device_or_cloud() {
        use super::super::{CompanionBackend, FixtureCompanionBackend};
        struct Restore {
            state: Option<std::ffi::OsString>,
            disabled: Option<std::ffi::OsString>,
            root: std::path::PathBuf,
        }
        impl Drop for Restore {
            fn drop(&mut self) {
                for (name, value) in [("COMPANION_TYPE_STATE_PATH", &self.state),
                    ("COMPANION_TYPE_BLE_NATIVE_DISABLED", &self.disabled)] {
                    if let Some(value) = value { std::env::set_var(name, value); }
                    else { std::env::remove_var(name); }
                }
                for name in ["original.wav", "sessions.json", "sessions.json.lock", "sessions.json.bak"] {
                    let _ = std::fs::remove_file(self.root.join(name));
                }
                let _ = std::fs::remove_dir(&self.root);
            }
        }
        let root = std::env::temp_dir().join(format!("companion-stop-received-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let _restore = Restore {
            state: std::env::var_os("COMPANION_TYPE_STATE_PATH"),
            disabled: std::env::var_os("COMPANION_TYPE_BLE_NATIVE_DISABLED"), root: root.clone(),
        };
        let state_path = root.join("sessions.json");
        std::env::set_var("COMPANION_TYPE_STATE_PATH", &state_path);
        std::env::set_var("COMPANION_TYPE_BLE_NATIVE_DISABLED", "1");
        let backend = FixtureCompanionBackend::new();
        let (mut snapshot, report) = recording();
        observe(&mut snapshot, "original", &report, STOP).unwrap();
        let wav = root.join("original.wav");
        let data_size = 32_000u32;
        let mut bytes = b"RIFF".to_vec();
        bytes.extend_from_slice(&(data_size + 36).to_le_bytes());
        bytes.extend_from_slice(b"WAVEfmt \x10\0\0\0\x01\0\x01\0");
        bytes.extend_from_slice(&16_000u32.to_le_bytes());
        bytes.extend_from_slice(&32_000u32.to_le_bytes());
        bytes.extend_from_slice(b"\x02\0\x10\0data");
        bytes.extend_from_slice(&data_size.to_le_bytes());
        bytes.resize(44 + data_size as usize, 0);
        std::fs::write(&wav, &bytes).unwrap();
        let received = super::super::ble_bridge::CompanionSyncedRecording {
            recording_id: 16, duration_ms: 1_020, total_length: 2_100, sha256: "ab".repeat(32),
            recording_path: wav.to_string_lossy().into(), device_reclaimed: true, capture_incomplete: false,
        };
        board_meeting::attach_recording(&mut snapshot.host.sessions[0], &received, STOP).unwrap();
        snapshot.host.sessions[0].transcript_text = "保留我已经改好的转写。".into();
        snapshot.host.sessions[0].transcript_final = true;
        snapshot.host.sessions[0].pending_reason = None;
        snapshot.host.persistence.status = "ready".into();
        snapshot.connected = false;
        snapshot.device.connected = false;
        super::super::persistence::save_sessions_to(&state_path, &snapshot.host.sessions).unwrap();
        let saved_index = std::fs::read(&state_path).unwrap();
        *backend.snapshot.lock().unwrap() = snapshot.clone();
        let stopped = backend.apply_control(serde_json::from_value(serde_json::json!({
            "action":"meetingStop", "sessionId":"original"
        })).unwrap());
        assert!(stopped.is_ok(), "already received and reclaimed STOP must succeed without native BLE: {:?}", stopped.err());
        let stopped = stopped.unwrap();
        assert_eq!(serde_json::to_value(&stopped.host.sessions).unwrap(),
            serde_json::to_value(&snapshot.host.sessions).unwrap());
        assert!(!stopped.meeting.active && !stopped.device.recording);
        assert_eq!(std::fs::read(&state_path).unwrap(), saved_index);
        assert_eq!(std::fs::read(&wav).unwrap(), bytes);
        for case in ["pending_consume", "no_local_audio", "privacy_erased", "device_still_recording",
            "missing_file", "changed_length", "changed_duration", "bad_hash", "missing_length",
            "unsaved_library", "another_active"] {
            let mut original = snapshot.clone();
            let session = &mut original.host.sessions[0];
            match case {
                "pending_consume" => session.device_reclaimed = false,
                "no_local_audio" => session.audio_stored = false,
                "privacy_erased" => session.retention.audio_cached = false,
                "device_still_recording" => original.device.recording = true,
                "missing_file" => session.audio_path = Some(root.join("missing.wav").to_string_lossy().into()),
                "changed_length" => session.audio_bytes += 1,
                "changed_duration" => session.duration_ms += 20,
                "bad_hash" => session.device_sha256 = Some("not-a-receipt".into()),
                "missing_length" => session.device_total_length = None,
                "unsaved_library" => original.host.persistence.status = "dirty".into(),
                "another_active" => {
                    original.host.active_session_id = Some("another-meeting".into());
                    original.meeting.active = true;
                }
                _ => unreachable!(),
            }
            *backend.snapshot.lock().unwrap() = original.clone();
            let error = backend.apply_control(serde_json::from_value(serde_json::json!({
                "action":"meetingStop", "sessionId":"original"
            })).unwrap()).expect_err(case);
            match case {
                "pending_consume" | "no_local_audio" | "privacy_erased" | "device_still_recording" =>
                    assert!(error.contains("native Windows BLE"), "{case}: {error}"),
                "missing_file" | "changed_length" | "changed_duration" =>
                    assert!(error.contains("本机原音"), "{case}: {error}"),
                "bad_hash" | "missing_length" => assert!(error.contains("记录不完整"), "{case}: {error}"),
                "unsaved_library" => assert!(error.contains("尚未保存"), "{case}: {error}"),
                "another_active" => assert!(error.contains("另一场录音"), "{case}: {error}"),
                _ => unreachable!(),
            }
            assert_eq!(serde_json::to_value(backend.snapshot().unwrap()).unwrap(),
                serde_json::to_value(&original).unwrap(), "{case}");
            assert_eq!(std::fs::read(&state_path).unwrap(), saved_index, "{case}");
            assert_eq!(std::fs::read(&wav).unwrap(), bytes, "{case}");
        }
    }

    fn recording() -> (CompanionV1Snapshot, CompanionMeetingControlReport) {
        let mut snapshot = apply_control_at(fixture_snapshot(), serde_json::from_value(serde_json::json!({
            "action":"meetingStart", "sessionId":"original", "meetingMode":"offlineStore",
            "title":"原会议", "audioPath":"host://original"
        })).unwrap(), START).unwrap();
        snapshot.device.device_id = Some(DEVICE.into());
        snapshot.device.recording = true;
        let session = &mut snapshot.host.sessions[0];
        session.source = "boardDevice".into();
        session.source_device_id = Some(DEVICE.into());
        session.device_recording_id = Some(16);
        session.audio_stored = false;
        session.retention.audio_cached = false;
        (snapshot, CompanionMeetingControlReport { device_id: DEVICE.into(), request_id: 42,
            state: 2, last_error: 0, meeting_id: 16, duration_ms: 300420, sync_state: 2 })
    }

    #[test]
    fn real_stop_survives_failed_pull_and_reload_without_fabricated_audio() {
        let (mut snapshot, report) = recording();
        observe(&mut snapshot, "original", &report, STOP).unwrap();
        // This checkpoint precedes receive, so a failed receive or process
        // exit cannot restore the original as an active microphone.
        let path = std::env::temp_dir().join(format!("companion-stop-{}-{}.json",
            std::process::id(), super::super::unix_time_ms()));
        super::super::persistence::save_sessions_to(&path, &snapshot.host.sessions).unwrap();
        let sessions = super::super::persistence::load_sessions_from(&path).unwrap();
        let session = &sessions[0];
        assert_eq!(session.id, "original");
        assert_eq!(session.title, "原会议");
        assert_eq!(session.device_recording_id, Some(16));
        assert_eq!(session.started_at.as_deref(), Some(START));
        assert_eq!(session.stopped_at.as_deref(), Some(STOP));
        assert_eq!(session.status, "captured");
        assert_eq!(session.pending_reason.as_deref(), Some("needs_device_sync"));
        assert_eq!(session.duration_ms, 300420);
        assert!(!session.audio_stored && !session.retention.audio_cached && !session.device_reclaimed);
        assert!(session.audio_path.is_none() && session.device_sha256.is_none());
        assert!(snapshot.host.active_session_id.is_none() && !snapshot.meeting.active && !snapshot.device.recording);
        let _ = std::fs::remove_file(&path);
        let _ = std::fs::remove_file(format!("{}.lock", path.display()));
    }

    #[test]
    fn unconfirmed_or_wrong_stop_cannot_end_the_original_or_another_meeting() {
        for failure in ["active", "device_error", "zero_id", "other_recording", "other_device",
            "other_active", "bad_time", "before_start", "missing_session"] {
            let (mut snapshot, mut report) = recording();
            let mut time = STOP;
            let mut id = "original";
            match failure {
                "active" => report.state = 1,
                "device_error" => report.last_error = 1,
                "zero_id" => report.meeting_id = 0,
                "other_recording" => report.meeting_id = 17,
                "other_device" => report.device_id = "C8:92:FF:DD:3B:CB".into(),
                "other_active" => snapshot.host.active_session_id = Some("another".into()),
                "bad_time" => time = "stopped",
                "before_start" => time = "2026-10-08T07:00:00.000Z",
                "missing_session" => id = "missing",
                _ => unreachable!(),
            }
            let before = serde_json::to_value(&snapshot).unwrap();
            assert!(observe(&mut snapshot, id, &report, time).is_err(), "{failure}");
            assert_eq!(serde_json::to_value(&snapshot).unwrap(), before, "{failure}");
        }
    }

    #[test]
    fn repeated_stop_keeps_received_audio_and_first_ack_for_reclaim_retry() {
        let (mut snapshot, report) = recording();
        observe(&mut snapshot, "original", &report, STOP).unwrap();
        let session = &mut snapshot.host.sessions[0];
        session.audio_path = Some("C:\\recordings\\original.wav".into());
        session.audio_bytes = 9613440;
        session.audio_stored = true;
        session.retention.audio_cached = true;
        session.device_total_length = Some(630894);
        session.device_sha256 = Some("ab".repeat(32));
        session.device_reclaimed = false;
        session.pending_reason = Some("needs_transcription".into());
        let before = serde_json::to_value(&session).unwrap();
        observe(&mut snapshot, "original", &report, "2026-10-08T07:12:55.550Z").unwrap();
        assert_eq!(serde_json::to_value(&snapshot.host.sessions[0]).unwrap(), before);
    }

    #[test]
    fn device_sync_checkpoint_does_not_resume_or_relabel_other_paused_work() {
        for failure in ["host_source", "missing_recording", "received", "reclaimed", "other_pause"] {
            let (mut snapshot, report) = recording();
            observe(&mut snapshot, "original", &report, STOP).unwrap();
            let session = &mut snapshot.host.sessions[0];
            match failure {
                "host_source" => session.source = "hostMicrophone".into(),
                "missing_recording" => session.device_recording_id = None,
                "received" => session.audio_stored = true,
                "reclaimed" => session.device_reclaimed = true,
                "other_pause" => session.pending_reason = Some("recovery_paused".into()),
                _ => unreachable!(),
            }
            super::super::persistence::reconcile_session_recovery(session);
            assert_eq!(session.pending_reason.as_deref(), Some("recovery_paused"), "{failure}");
            assert_eq!(session.recovery.stage, "paused", "{failure}");
            assert!(session.recovery.next_retry_at_unix_ms.is_none(), "{failure}");
        }
    }
}
