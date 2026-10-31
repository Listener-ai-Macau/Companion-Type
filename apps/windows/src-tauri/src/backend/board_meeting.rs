//! Metadata for the real START/STOP route, separate from the fixture reducer.
use super::ble_bridge::CompanionSyncedRecording;
use crate::companion_v1::{
    CompanionV1ControlAction, CompanionV1ControlRequest, CompanionV1HostSession, CompanionV1Snapshot,
};

#[derive(Debug, Eq, PartialEq)]
pub(super) struct DeviceControlTarget {
    pub device_id: Option<String>,
    pub recording_id: Option<u32>,
}

/// START chooses a capture source. STOP belongs to the source already chosen,
/// even when the device has disconnected; it must never become a host capture.
pub(super) fn device_control_target(
    snapshot: &CompanionV1Snapshot,
    request: &CompanionV1ControlRequest,
) -> Result<Option<DeviceControlTarget>, String> {
    let has_audio_path = request.audio_path.as_deref().is_some_and(|path| !path.trim().is_empty());
    match request.action {
        CompanionV1ControlAction::MeetingStart => {
            return Ok((snapshot.connected && !has_audio_path).then(|| DeviceControlTarget {
                device_id: request.device_id.clone().or_else(|| snapshot.device.device_id.clone()),
                recording_id: None,
            }));
        }
        CompanionV1ControlAction::MeetingStop | CompanionV1ControlAction::MeetingFinalize => {}
        _ => return Ok(None),
    }
    let session_id = request.session_id.as_deref()
        .or(snapshot.host.active_session_id.as_deref())
        .or(snapshot.host.selected_session_id.as_deref())
        .ok_or("找不到要结束的原录音，未创建替代会议。")?;
    if snapshot.host.active_session_id.as_deref().is_some_and(|active| active != session_id) {
        return Err("另一场录音正在进行，未停止或修改它。".into());
    }
    let session = snapshot.host.sessions.iter().find(|session| session.id == session_id)
        .ok_or("找不到要结束的原录音，未创建替代会议。")?;
    if !matches!(session.source.as_str(), "boardDevice" | "deviceFlash") {
        return Ok(None);
    }
    if has_audio_path {
        return Err("这场录音来自 Companion，不能用本机文件替代设备原音。".into());
    }
    let device_id = session.source_device_id.as_deref()
        .filter(|id| super::device_connection::stable_device_id(id))
        .ok_or("原录音缺少设备身份，未向其他设备发送结束命令。")?;
    if !session.device_recording_id.is_some_and(|id| id != 0) {
        return Err("原录音缺少设备录音编号，未创建替代录音。".into());
    }
    if request.device_id.as_deref().is_some_and(|id|
        !super::device_connection::same_device_id(id, device_id))
        || snapshot.device.device_id.as_deref().is_some_and(|id|
            !super::device_connection::same_device_id(id, device_id))
    {
        return Err("所选设备与原录音来源不同，请连接原来的 Companion 后继续。".into());
    }
    Ok(Some(DeviceControlTarget {
        device_id: Some(device_id.into()), recording_id: session.device_recording_id,
    }))
}

fn capture_date(value: Option<&str>) -> Option<String> {
    value.filter(|value| chrono::DateTime::parse_from_rfc3339(value).is_ok()).map(str::to_owned)
}

/// Legacy phase labels are not dates. Preserve known observations and leave
/// unknown capture times empty, rather than inventing them from a later pull.
pub(super) fn retain_capture_dates(session: &mut CompanionV1HostSession) {
    session.started_at = capture_date(session.started_at.as_deref());
    session.stopped_at = capture_date(session.stopped_at.as_deref());
    let segmented = session.device_recording_key.is_some();
    for chunk in &mut session.chunks {
        chunk.started_at = capture_date(chunk.started_at.as_deref());
        // Segmented originals use these two values as provenance markers,
        // not capture dates. Removing them on reload makes the next ordinary
        // transcript/minutes save look like a lost device recording.
        let provenance = segmented && matches!((chunk.stopped_at.as_deref(), chunk.status.as_str()),
            (Some("verified-v2-segment"), "sealed" | "synced")
                | (Some("verified-v2-session"), "synced"));
        if !provenance { chunk.stopped_at = capture_date(chunk.stopped_at.as_deref()); }
    }
}

pub(super) fn observe_online_times(
    session: &mut CompanionV1HostSession,
    device_id: &str,
    recording_id: u32,
    start_ack_at: &str,
    stop_ack_at: &str,
) -> Result<(), String> {
    let start = chrono::DateTime::parse_from_rfc3339(start_ack_at)
        .map_err(|_| "尚未取得在线录音的实际开始确认时间。")?;
    let stop = chrono::DateTime::parse_from_rfc3339(stop_ack_at)
        .map_err(|_| "尚未取得在线录音的实际停止确认时间。")?;
    if stop < start || recording_id == 0 || device_id.trim().is_empty()
        || session.device_recording_id.is_some_and(|id| id != recording_id)
        || session.source_device_id.as_deref().is_some_and(|id|
            !super::device_connection::same_device_id(id, device_id))
    {
        return Err("在线录音的时间或设备身份不一致，未修改会议。".into());
    }
    session.started_at = Some(start_ack_at.into());
    session.stopped_at = Some(stop_ack_at.into());
    Ok(())
}

pub(super) fn observe_start(
    session: &mut CompanionV1HostSession,
    prior: Option<&CompanionV1HostSession>,
    observed: &str,
) {
    session.started_at = prior
        .and_then(|s| s.started_at.clone())
        .filter(|v| chrono::DateTime::parse_from_rfc3339(v).is_ok())
        .or_else(|| Some(observed.into()));
    for chunk in &mut session.chunks {
        chunk.started_at = session.started_at.clone();
    }
}

/// A real STOP acknowledgement is kept even when the user pauses its pull.
/// No local audio or reclaim identity exists until the sealed file is verified.
pub(super) fn pending_sync(
    session: &mut CompanionV1HostSession,
    recording_id: u32,
    duration_ms: u32,
    observed_stop: &str,
) -> Result<(), String> {
    if recording_id == 0 || session.device_recording_id.is_some_and(|id| id != recording_id)
        || session.device_sha256.is_some() || session.device_reclaimed
        || capture_date(Some(observed_stop)).is_none()
    {
        return Err("设备停止结果与这场录音身份或时间不一致，未修改会议。".into());
    }
    retain_capture_dates(session);
    session.stopped_at = Some(observed_stop.into());
    session.device_recording_id = Some(recording_id);
    session.duration_ms = u64::from(duration_ms);
    session.audio_path = None;
    session.audio_bytes = 0;
    session.audio_stored = false;
    session.retention.audio_cached = false;
    session.device_total_length = None;
    session.device_sha256 = None;
    session.device_reclaimed = false;
    session.chunks.clear();
    session.status = "captured".into();
    session.pending_reason = Some("needs_device_sync".into());
    super::arm_meeting_recovery(session);
    session.recovery.stage = "paused".into();
    session.recovery.next_retry_at_unix_ms = None;
    session.recovery.last_error = None;
    Ok(())
}

/// Replace host:// declarations with the verified file before ASR sees them.
/// Dates are host observations of actual ACKs, not inferred sample timestamps.
pub(super) fn attach_recording(
    session: &mut CompanionV1HostSession,
    recording: &CompanionSyncedRecording,
    observed_stop: &str,
) -> Result<(), String> {
    if session.device_recording_id != Some(recording.recording_id)
        || session
            .device_sha256
            .as_deref()
            .is_some_and(|sha| sha != recording.sha256)
    {
        return Err("设备停止结果与这场录音身份不一致，未覆盖其他录音。".into());
    }
    let path = std::path::Path::new(&recording.recording_path);
    if !path.is_absolute() {
        return Err("设备录音尚未取得真实本机路径。".into());
    }
    let duration = super::meeting_workspace::wav_duration_ms(path)?;
    let bytes = std::fs::metadata(path)
        .map_err(|_| "设备原音已移动或删除，未声明收齐。")?
        .len();
    session.audio_path = Some(recording.recording_path.clone());
    session.audio_bytes = bytes;
    session.duration_ms = duration;
    session.audio_stored = true;
    session.retention.audio_cached = true;
    session.device_total_length = Some(recording.total_length);
    session.device_sha256 = Some(recording.sha256.clone());
    session.device_reclaimed = recording.device_reclaimed;
    session.capture_incomplete = recording.capture_incomplete;
    retain_capture_dates(session);
    session.stopped_at = Some(observed_stop.into());
    session.chunks = vec![super::audio_chunk(
        format!("{}-board-received", session.id),
        session.audio_path.clone(),
        session.started_at.clone(),
        session.stopped_at.clone(),
        duration,
        bytes,
        "synced",
    )];
    super::recording_bookmarks::bind_received(session);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{apply_control_at, apply_fixture_control, fixture_snapshot};

    fn route_snapshot(source: &str) -> CompanionV1Snapshot {
        let mut snapshot = fixture_snapshot();
        let mut session = pending_online();
        session.source = source.into();
        session.source_device_id = Some("C8:92:FF:DD:3B:CA".into());
        session.device_recording_id = Some(18);
        snapshot.host.active_session_id = Some(session.id.clone());
        snapshot.host.selected_session_id = Some(session.id.clone());
        snapshot.host.sessions = vec![session];
        snapshot.connected = false;
        snapshot.device.connected = false;
        snapshot.device.device_id = None;
        snapshot
    }

    fn route_request(action: &str) -> CompanionV1ControlRequest {
        serde_json::from_value(serde_json::json!({ "action": action })).unwrap()
    }

    #[test]
    fn control_route_original_device_survives_disconnection_and_selection_fallback() {
        for source in ["boardDevice", "deviceFlash"] {
            for action in ["meetingStop", "meetingFinalize"] {
                let mut snapshot = route_snapshot(source);
                let mut request = route_request(action);
                for selection in ["explicit", "active", "selected"] {
                    request.session_id = (selection == "explicit").then(|| "online-clock".into());
                    if selection == "selected" { snapshot.host.active_session_id = None; }
                    // Equivalent native address formatting does not select a different device.
                    request.device_id = Some("c8-92-ff-dd-3b-ca".into());
                    assert_eq!(device_control_target(&snapshot, &request).unwrap(),
                        Some(DeviceControlTarget { device_id: Some("C8:92:FF:DD:3B:CA".into()), recording_id: Some(18) }),
                        "{source}/{action}/{selection}");
                }
            }
        }
    }

    #[test]
    fn control_route_ambiguous_or_changed_original_is_rejected_before_device_io() {
        for failure in ["no_session", "unknown_session", "another_active", "missing_device",
            "invalid_device", "missing_recording", "zero_recording", "override_audio",
            "requested_other_device", "selected_other_device"] {
            for action in ["meetingStop", "meetingFinalize"] {
                let mut snapshot = route_snapshot("boardDevice");
                let mut request = route_request(action);
                request.session_id = Some("online-clock".into());
                match failure {
                    "no_session" => {
                        request.session_id = None;
                        snapshot.host.active_session_id = None;
                        snapshot.host.selected_session_id = None;
                    }
                    "unknown_session" => {
                        snapshot.host.active_session_id = None;
                        request.session_id = Some("missing".into());
                    }
                    "another_active" => snapshot.host.active_session_id = Some("another".into()),
                    "missing_device" => snapshot.host.sessions[0].source_device_id = None,
                    "invalid_device" => snapshot.host.sessions[0].source_device_id = Some("Companion".into()),
                    "missing_recording" => snapshot.host.sessions[0].device_recording_id = None,
                    "zero_recording" => snapshot.host.sessions[0].device_recording_id = Some(0),
                    "override_audio" => request.audio_path = Some("C:/replacement.wav".into()),
                    "requested_other_device" => request.device_id = Some("C8:92:FF:DD:3B:CB".into()),
                    "selected_other_device" => {
                        snapshot.connected = true;
                        snapshot.device.device_id = Some("C8:92:FF:DD:3B:CB".into());
                    }
                    _ => unreachable!(),
                }
                let before = serde_json::to_value(&snapshot).unwrap();
                assert!(device_control_target(&snapshot, &request).is_err(), "{failure}/{action}");
                assert_eq!(serde_json::to_value(&snapshot).unwrap(), before);
            }
        }
    }

    #[test]
    fn control_route_host_stop_stays_local_and_start_keeps_existing_source_selection() {
        let mut snapshot = route_snapshot("hostMicrophone");
        snapshot.connected = true;
        snapshot.device.connected = true;
        snapshot.device.device_id = Some("C8:92:FF:DD:3B:CA".into());
        for action in ["meetingStop", "meetingFinalize", "deviceSyncRecordings"] {
            assert_eq!(device_control_target(&snapshot, &route_request(action)).unwrap(), None);
        }
        let mut start = route_request("meetingStart");
        assert_eq!(device_control_target(&snapshot, &start).unwrap(),
            Some(DeviceControlTarget { device_id: snapshot.device.device_id.clone(), recording_id: None }));
        start.audio_path = Some("C:/existing.wav".into());
        assert_eq!(device_control_target(&snapshot, &start).unwrap(), None);
        start.audio_path = Some("  ".into());
        assert!(device_control_target(&snapshot, &start).unwrap().is_some());
        snapshot.connected = false;
        assert_eq!(device_control_target(&snapshot, &start).unwrap(), None);
    }

    #[test]
    fn control_route_disconnected_board_stop_never_fabricates_host_audio() {
        use super::super::{CompanionBackend, FixtureCompanionBackend};
        struct Restore {
            values: Vec<(&'static str, Option<std::ffi::OsString>)>,
            root: std::path::PathBuf,
        }
        impl Drop for Restore {
            fn drop(&mut self) {
                for (name, value) in &self.values {
                    if let Some(value) = value { std::env::set_var(name, value); }
                    else { std::env::remove_var(name); }
                }
                for name in ["sessions.json", "sessions.json.lock", "sessions.json.bak"] {
                    let _ = std::fs::remove_file(self.root.join(name));
                }
                let _ = std::fs::remove_dir(&self.root);
            }
        }
        let root = std::env::temp_dir().join(format!("companion-stop-route-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let state_path = root.join("sessions.json");
        let _restore = Restore { values: ["COMPANION_TYPE_STATE_PATH", "COMPANION_TYPE_BLE_NATIVE_DISABLED"]
            .into_iter().map(|name| (name, std::env::var_os(name))).collect(), root };
        std::env::set_var("COMPANION_TYPE_STATE_PATH", &state_path);
        // Reach the real production coordinator while guaranteeing no radio
        // connection, microphone, pairing, or external service can be used.
        std::env::set_var("COMPANION_TYPE_BLE_NATIVE_DISABLED", "1");
        for source in ["boardDevice", "deviceFlash"] {
            let backend = FixtureCompanionBackend::new();
            let mut original = apply_control_at(fixture_snapshot(), serde_json::from_value(serde_json::json!({
                "action":"meetingStart", "sessionId":"original-disconnected", "meetingMode":"offlineStore",
                "audioPath":"board://pending/original-disconnected", "title":"原来的板端录音"
            })).unwrap(), "2026-10-08T08:00:00.000Z").unwrap();
            original.connected = false;
            original.device.connected = false;
            original.device.device_id = None;
            original.device.recording = true;
            original.host.persistence.status = "ready".into();
            let session = &mut original.host.sessions[0];
            session.source = source.into();
            session.source_device_id = Some("C8:92:FF:DD:3B:CA".into());
            session.device_recording_id = Some(18);
            session.audio_stored = false;
            session.audio_bytes = 0;
            session.retention.audio_cached = false;
            *backend.snapshot.lock().unwrap() = original.clone();
            let request = serde_json::from_value(serde_json::json!({
                "action":"meetingStop", "sessionId":"original-disconnected"
            })).unwrap();
            let result = backend.apply_control(request);
            assert!(result.is_err(), "{source}: disconnected real board STOP must not fabricate host audio");
            assert!(result.unwrap_err().contains("native Windows BLE"));
            assert_eq!(serde_json::to_value(backend.snapshot().unwrap()).unwrap(),
                serde_json::to_value(&original).unwrap());
            assert!(!state_path.exists(), "a rejected device STOP cannot commit a synthetic host receipt");
        }
    }

    fn pending_online() -> CompanionV1HostSession {
        apply_control_at(fixture_snapshot(), serde_json::from_value(serde_json::json!({
            "action":"meetingStart", "sessionId":"online-clock", "meetingMode":"onlineLive",
            "audioPath":"board://pending/online-clock"
        })).unwrap(), "2026-10-07T01:00:00.000Z").unwrap().host.sessions.remove(0)
    }

    #[test]
    fn online_observations_survive_pending_asr_generation_and_later_pull() {
        let mut session = pending_online();
        let start = "2026-10-07T01:02:03.123Z";
        let stop = "2026-10-07T01:03:12.789Z";
        session.started_at = None; // pending UI state has no acknowledged START
        observe_online_times(&mut session, "C8:92:FF:DD:3B:CA", 38, start, stop).unwrap();
        session.device_recording_id = Some(38);
        session.source_device_id = Some("C8:92:FF:DD:3B:CA".into());
        session.status = "captured".into();
        session.pending_reason = Some("needs_transcription".into());
        session.transcript_text = "原音的实际转写。".into();
        session.transcript_final = true;
        let mut snapshot = fixture_snapshot();
        snapshot.host.selected_session_id = Some(session.id.clone());
        snapshot.host.sessions = vec![session];
        let generated = "2026-10-07T02:00:00.000Z";
        let snapshot = apply_control_at(snapshot, serde_json::from_value(serde_json::json!({
            "action":"meetingGenerateMinutes", "sessionId":"online-clock"
        })).unwrap(), generated).unwrap();
        let mut saved = snapshot.host.sessions[0].clone();
        assert_eq!(snapshot.updated_at, generated);
        assert_eq!(saved.minutes.as_ref().unwrap().generated_at, generated);
        assert_eq!(saved.started_at.as_deref(), Some(start));
        assert_eq!(saved.stopped_at.as_deref(), Some(stop));
        retain_capture_dates(&mut saved);
        assert_eq!(saved.stopped_at.as_deref(), Some(stop));
        let stored = serde_json::to_vec(&saved).unwrap();
        let reloaded: CompanionV1HostSession = serde_json::from_slice(&stored).unwrap();
        assert_eq!(reloaded.started_at, saved.started_at);
        assert_eq!(reloaded.stopped_at, saved.stopped_at);

        saved.started_at = Some("fixture".into());
        saved.stopped_at = Some("board-online-live-pending-asr".into());
        retain_capture_dates(&mut saved);
        assert!(saved.started_at.is_none() && saved.stopped_at.is_none());
        assert_eq!(saved.transcript_text, reloaded.transcript_text);
    }

    #[test]
    fn invalid_online_observations_do_not_rewrite_the_original_meeting() {
        for failure in ["missing", "reverse", "different_recording", "different_device", "zero"] {
            let mut session = pending_online();
            session.device_recording_id = Some(38);
            session.source_device_id = Some("C8:92:FF:DD:3B:CA".into());
            let start = "2026-10-07T01:02:03.123Z";
            let mut stop = "2026-10-07T01:03:12.789Z";
            let mut id = 38;
            let mut device = "C8:92:FF:DD:3B:CA";
            match failure {
                "missing" => stop = "board-online-live-final",
                "reverse" => stop = "2026-10-07T00:00:00.000Z",
                "different_recording" => id = 39,
                "different_device" => device = "C8:92:FF:DD:3B:CB",
                "zero" => id = 0,
                _ => unreachable!(),
            }
            let before = serde_json::to_value(&session).unwrap();
            assert!(observe_online_times(&mut session, device, id, start, stop).is_err(), "{failure}");
            assert_eq!(serde_json::to_value(&session).unwrap(), before, "{failure}");
        }
    }

    fn source() -> (
        CompanionV1HostSession,
        CompanionSyncedRecording,
        std::path::PathBuf,
    ) {
        let mut session = apply_fixture_control(
            fixture_snapshot(),
            serde_json::from_value(
                serde_json::json!({"action":"meetingStart","sessionId":"board-direct"}),
            )
            .unwrap(),
        )
        .unwrap()
        .host
        .sessions
        .remove(0);
        session.source = "boardDevice".into();
        session.device_recording_id = Some(29);
        let root =
            std::env::temp_dir().join(format!("companion-board-direct-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("verified.wav");
        let size = 96000u32;
        let mut wav = b"RIFF".to_vec();
        wav.extend_from_slice(&(size + 36).to_le_bytes());
        wav.extend_from_slice(b"WAVEfmt \x10\0\0\0\x01\0\x01\0");
        wav.extend_from_slice(&16000u32.to_le_bytes());
        wav.extend_from_slice(&32000u32.to_le_bytes());
        wav.extend_from_slice(b"\x02\0\x10\0data");
        wav.extend_from_slice(&size.to_le_bytes());
        wav.resize(44 + size as usize, 0);
        std::fs::write(&path, wav).unwrap();
        let recording = CompanionSyncedRecording {
            recording_id: 29,
            duration_ms: 3020,
            total_length: 6300,
            sha256: "a".repeat(64),
            recording_path: path.to_string_lossy().into(),
            device_reclaimed: true,
            capture_incomplete: false,
        };
        (session, recording, root)
    }
    #[test]
    fn direct_stop_declares_actual_wav_before_asr_and_keeps_first_start_ack_on_retry() {
        let (mut s, recording, _) = source();
        let first = "2026-10-07T01:02:03.123Z";
        observe_start(&mut s, None, first);
        let prior = s.clone();
        s.started_at = Some("fixture".into());
        observe_start(&mut s, Some(&prior), "2026-10-07T01:02:08.456Z");
        assert_eq!(s.started_at.as_deref(), Some(first));
        attach_recording(&mut s, &recording, "2026-10-07T01:02:12.789Z").unwrap();
        assert_eq!(s.duration_ms, 3000);
        assert_eq!(s.audio_bytes, 96044);
        assert_eq!(s.chunks.len(), 1);
        assert_eq!(s.chunks[0].path, s.audio_path);
        assert_eq!(s.chunks[0].duration_ms, 3000);
        assert_eq!(
            super::super::transcription_chunk_paths(&s).unwrap(),
            vec![recording.recording_path.clone()]
        );
        assert!(std::path::Path::new(s.chunks[0].path.as_ref().unwrap()).is_file());
        assert!(chrono::DateTime::parse_from_rfc3339(s.started_at.as_ref().unwrap()).is_ok());
        assert!(chrono::DateTime::parse_from_rfc3339(s.stopped_at.as_ref().unwrap()).is_ok());
        assert!(!s.transcript_final);
        assert_eq!(s.device_sha256.as_deref(), Some(recording.sha256.as_str()));
    }
    #[test]
    fn wrong_id_changed_hash_placeholder_and_corrupt_wav_do_not_mutate_or_claim_audio() {
        for failure in ["id", "hash", "placeholder", "missing", "corrupt"] {
            let (mut s, mut recording, root) = source();
            match failure {
                "id" => recording.recording_id = 33,
                "hash" => s.device_sha256 = Some("b".repeat(64)),
                "placeholder" => recording.recording_path = "host://unrecorded.wav".into(),
                "missing" => {
                    recording.recording_path = root.join("missing.wav").to_string_lossy().into()
                }
                "corrupt" => {
                    std::fs::write(&recording.recording_path, b"bad").unwrap();
                }
                _ => {}
            }
            let before = serde_json::to_value(&s).unwrap();
            assert!(
                attach_recording(&mut s, &recording, "actual-ack").is_err(),
                "{failure}"
            );
            assert_eq!(serde_json::to_value(s).unwrap(), before, "{failure}");
        }
    }
}
