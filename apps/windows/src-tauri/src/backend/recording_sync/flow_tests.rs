//! Local state/receipt tests; these are not real board or cloud acceptance.
use super::*;
const DEVICE: &str = "AA:BB:CC:DD:EE:07";
const START: &str = "2026-10-08T01:00:00.000Z";
const STOP: &str = "2026-10-08T01:00:45.000Z";

fn recording() -> CompanionV1Snapshot {
    let mut snapshot = apply_control_at(fixture_snapshot(), serde_json::from_value(serde_json::json!({
        "action":"meetingStart", "sessionId":"paused-original", "meetingMode":"onlineLive",
        "title":"保留用户标题", "audioPath":"board://pending/paused-original"
    })).unwrap(), START).unwrap();
    snapshot.device.device_id = Some(DEVICE.into());
    let session = selected_session_mut(&mut snapshot).unwrap();
    session.device_recording_id = Some(7);
    session.source_device_id = Some(DEVICE.into());
    session.live_transcript_text = "已经收到的实时转写。".into();
    snapshot
}

fn paused_report() -> BoardOnlineLiveReport {
    BoardOnlineLiveReport {
        capture_incomplete: false, sync_paused: true, sealed_duration_ms: 45_000,
        device_id: DEVICE.into(), recording_id: 7, start_ack_at: START.into(), stop_ack_at: STOP.into(),
        partials: vec![], partial_errors: vec![], disconnect_resume: false, disconnect_offset: 0,
        final_recording_path: String::new(), final_total_length: 0, final_sha256: String::new(),
        device_reclaimed: false,
    }
}

#[test]
fn empty_sync_pause_keeps_library_capture_selection_and_recording_counters() {
    let mut snapshot = recording();
    snapshot.device.recordings_available = 4;
    let before = serde_json::json!({ "host":snapshot.host, "meeting":snapshot.meeting,
        "available":snapshot.device.recordings_available, "lastSync":snapshot.device.last_sync_at });
    let operation = CompanionBleOperation {
        provider_id: "companion-type-windows-ble".into(), mode: "windows-native-recording-pull".into(),
        ready: true, sync_paused: true, device_id: Some(DEVICE.into()), recording_path: None,
        recordings: vec![], device_identity: None, message: recording_sync::PAUSED.into(),
    };
    observe_empty_sync_pause(&mut snapshot, &operation);
    assert_eq!(before, serde_json::json!({ "host":snapshot.host, "meeting":snapshot.meeting,
        "available":snapshot.device.recordings_available, "lastSync":snapshot.device.last_sync_at }));
    let echo = snapshot.last_control.as_ref().unwrap();
    assert!(echo.accepted);
    assert_eq!(echo.action, CompanionV1ControlAction::DeviceSyncRecordings);
    assert!(echo.payload_hex.is_empty());
    assert!(echo.message.contains("暂停"));
}

#[test]
fn paused_real_stop_overrides_fixture_audio_and_survives_session_reload() {
    let mut stopped = apply_control_at(recording(), serde_json::from_value(serde_json::json!({
        "action":"meetingStop", "sessionId":"paused-original", "durationMs":45_000, "audioBytes":0
    })).unwrap(), STOP).unwrap();
    let session = selected_session_mut(&mut stopped).unwrap();
    assert!(session.audio_stored, "the fixture reducer is not evidence of receipt");
    board_meeting::pending_sync(session, 7, 45_000, STOP).unwrap();
    let stored = serde_json::to_vec(session).unwrap();
    let reloaded: CompanionV1HostSession = serde_json::from_slice(&stored).unwrap();
    assert_eq!(reloaded.device_recording_id, Some(7));
    assert_eq!(reloaded.stopped_at.as_deref(), Some(STOP));
    assert_eq!(reloaded.started_at.as_deref(), Some(START));
    assert_eq!(reloaded.duration_ms, 45_000);
    assert_eq!(reloaded.pending_reason.as_deref(), Some("needs_device_sync"));
    assert!(!reloaded.audio_stored && !reloaded.retention.audio_cached && !reloaded.device_reclaimed);
    assert!(reloaded.audio_path.is_none() && reloaded.device_sha256.is_none());
    assert!(reloaded.chunks.is_empty());
    assert_eq!(reloaded.recovery.stage, "paused");
    assert!(reloaded.recovery.next_retry_at_unix_ms.is_none());
}

#[test]
fn online_final_pull_pause_preserves_partial_text_then_exact_receipt_resumes_original_meeting() {
    let mut snapshot = recording();
    observe_paused_online_sync(&mut snapshot, "paused-original", &paused_report()).unwrap();
    assert!(!snapshot.meeting.active && snapshot.host.active_session_id.is_none());
    let session = selected_session(&snapshot).unwrap();
    assert_eq!(session.live_transcript_text, "已经收到的实时转写。");
    assert!(!session.audio_stored && !session.transcript_final);
    assert_eq!(session.pending_reason.as_deref(), Some("needs_device_sync"));
    assert!(verified_device_recording_ids(&snapshot, Some(DEVICE)).is_empty());
    // A later exact, verified transfer supplies the durable local artifact.
    let root = std::env::temp_dir().join(format!("companion-sync-flow-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    let path = root.join("received.wav");
    let mut wav = b"RIFF".to_vec();
    wav.extend(3236u32.to_le_bytes()); wav.extend(b"WAVEfmt ");
    wav.extend(16u32.to_le_bytes()); wav.extend(1u16.to_le_bytes()); wav.extend(1u16.to_le_bytes());
    wav.extend(16_000u32.to_le_bytes()); wav.extend(32_000u32.to_le_bytes());
    wav.extend(2u16.to_le_bytes()); wav.extend(16u16.to_le_bytes()); wav.extend(b"data");
    wav.extend(3200u32.to_le_bytes()); wav.resize(3244, 0);
    std::fs::write(&path, wav).unwrap();
    merge_synced_recordings(&mut snapshot, &[CompanionSyncedRecording {
        recording_id: 7, duration_ms: 45_000, total_length: 1024, sha256: "ab".repeat(32),
        recording_path: path.to_string_lossy().into(), device_reclaimed: false, capture_incomplete: false,
    }]);
    // The original meeting is durable before physical consume. A timed-out
    // consume must remain eligible after reload, without changing this audio
    // receipt or inventing a device ACK. Explicit retain policy still skips it.
    let serialized = serde_json::to_vec(&snapshot.host.sessions).unwrap();
    snapshot.host.sessions = serde_json::from_slice(&serialized).unwrap();
    assert!(verified_device_recording_ids_for_policy(&snapshot, Some(DEVICE), true).is_empty());
    assert_eq!(verified_device_recording_ids_for_policy(&snapshot, Some(DEVICE), false), vec![7]);
    assert!(selected_session(&snapshot).unwrap().audio_stored);
    assert!(!selected_session(&snapshot).unwrap().device_reclaimed);
    merge_synced_recordings(&mut snapshot, &[CompanionSyncedRecording {
        recording_id: 7, duration_ms: 45_000, total_length: 1024, sha256: "ab".repeat(32),
        recording_path: path.to_string_lossy().into(), device_reclaimed: true, capture_incomplete: false,
    }]);
    assert_eq!(snapshot.host.sessions.len(), 1);
    let received = selected_session(&snapshot).unwrap();
    assert_eq!(received.id, "paused-original");
    assert_eq!(received.title, "保留用户标题");
    assert_eq!(received.meeting_mode, "onlineLive");
    assert_eq!(received.started_at.as_deref(), Some(START));
    assert_eq!(received.stopped_at.as_deref(), Some(STOP));
    assert_eq!(received.live_transcript_text, "已经收到的实时转写。");
    assert!(received.audio_stored && received.device_reclaimed);
    assert_eq!(received.pending_reason.as_deref(), Some("needs_transcription"));
    assert_eq!(received.recovery.stage, "pendingTranscription");
    assert_eq!(verified_device_recording_ids(&snapshot, Some(DEVICE)), vec![7]);
}

#[test]
fn paused_stop_cannot_erase_verified_audio_or_change_a_different_device_recording() {
    let mut snapshot = recording();
    let before = serde_json::to_value(&snapshot).unwrap();
    let mut report = paused_report(); report.device_id = "11:22:33:44:55:66".into();
    assert!(observe_paused_online_sync(&mut snapshot, "paused-original", &report).is_err());
    assert_eq!(serde_json::to_value(&snapshot).unwrap(), before);
    let session = selected_session_mut(&mut snapshot).unwrap();
    session.audio_path = Some("C:/verified.wav".into()); session.audio_stored = true;
    session.device_sha256 = Some("ab".repeat(32)); session.device_reclaimed = true;
    let before = serde_json::to_value(&snapshot).unwrap();
    assert!(observe_paused_online_sync(&mut snapshot, "paused-original", &paused_report()).is_err());
    assert_eq!(serde_json::to_value(&snapshot).unwrap(), before);
}
