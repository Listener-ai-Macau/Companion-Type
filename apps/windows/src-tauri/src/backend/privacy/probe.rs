//! Controlled production coordinator/filesystem checks. No actual recordings,
//! user state, service calls or device commands are used.
use super::super::{audio_storage, persistence, CompanionBackend, FixtureCompanionBackend};
use crate::companion_v1::{
    fixture_snapshot, synced_device_session, CompanionV1ControlAction as Action,
    CompanionV1ControlRequest, CompanionV1HostSession, CompanionV1Snapshot,
};
use serde_json::{json, Value};
use std::{
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
};

struct Environment(Vec<(String, Option<OsString>)>);
impl Environment {
    fn set(values: &[(&str, &std::ffi::OsStr)]) -> Self {
        let previous = values
            .iter()
            .map(|(name, value)| {
                let old = std::env::var_os(name);
                std::env::set_var(name, value);
                ((*name).to_string(), old)
            })
            .collect();
        Self(previous)
    }
}
impl Drop for Environment {
    fn drop(&mut self) {
        for (name, value) in &self.0 {
            if let Some(value) = value {
                std::env::set_var(name, value);
            } else {
                std::env::remove_var(name);
            }
        }
    }
}
fn request(action: Action, id: Option<&str>) -> Result<CompanionV1ControlRequest, String> {
    serde_json::from_value(json!({"action":action,"sessionId":id}))
        .map_err(|_| "Cannot create privacy request".into())
}
fn session(id: &str, audio: &Path) -> Result<CompanionV1HostSession, String> {
    let mut value = synced_device_session(
        &fixture_snapshot(),
        &request(Action::DeviceSyncRecordings, Some(id))?,
        "controlled",
    );
    value.id = id.into();
    value.source = "controlledPrivacyFixture".into();
    value.status = "captured".into();
    value.audio_path = Some(audio.to_string_lossy().into_owned());
    value.audio_bytes = 46;
    value.audio_stored = true;
    value.retention.audio_cached = true;
    value.device_recording_id = None;
    value.device_total_length = None;
    value.device_sha256 = None;
    value.source_device_id = None;
    value.device_reclaimed = false;
    value.chunks.clear();
    value.transcript_text = "Controlled source fact".into();
    value.transcript_final = true;
    value.retention.transcript_cached = true;
    value.recovery = Default::default();
    Ok(value)
}
fn snapshot(sessions: Vec<CompanionV1HostSession>, selected: Option<&str>) -> CompanionV1Snapshot {
    let mut value = fixture_snapshot();
    value.source = "fixture";
    value.host.sessions = sessions;
    value.host.selected_session_id = selected.map(str::to_string);
    value.host.active_session_id = None;
    value.host.persistence = Default::default();
    value.device.recording = false;
    value.meeting.active = false;
    value
}
fn install_snapshot(backend: &FixtureCompanionBackend, snapshot: CompanionV1Snapshot) -> Result<(),String> {
    // The real coordinator validates the durable library before deleting.
    // Prepare both authorities; a cache-only row can fail for the wrong reason.
    super::super::session_store::save(&persistence::state_file_path(), &snapshot.host.sessions)?;
    *backend.snapshot.lock().map_err(|_|"Cannot seed controlled cache")? = snapshot;
    Ok(())
}
fn write_wav(path: &Path) -> Result<(), String> {
    let mut bytes = vec![0u8; 46];
    bytes[0..4].copy_from_slice(b"RIFF");
    bytes[4..8].copy_from_slice(&38u32.to_le_bytes());
    bytes[8..12].copy_from_slice(b"WAVE");
    bytes[12..16].copy_from_slice(b"fmt ");
    bytes[16..20].copy_from_slice(&16u32.to_le_bytes());
    bytes[20..22].copy_from_slice(&1u16.to_le_bytes());
    bytes[22..24].copy_from_slice(&1u16.to_le_bytes());
    bytes[24..28].copy_from_slice(&16000u32.to_le_bytes());
    bytes[28..32].copy_from_slice(&32000u32.to_le_bytes());
    bytes[32..34].copy_from_slice(&2u16.to_le_bytes());
    bytes[34..36].copy_from_slice(&16u16.to_le_bytes());
    bytes[36..40].copy_from_slice(b"data");
    bytes[40..44].copy_from_slice(&2u32.to_le_bytes());
    fs::write(path, bytes).map_err(|_| "Cannot create controlled WAV".into())
}
fn equal<T: serde::Serialize>(a: &T, b: &T) -> bool {
    serde_json::to_value(a).ok() == serde_json::to_value(b).ok()
}

pub(crate) fn verify(output: &Path) -> Result<Value, String> {
    #[cfg(not(windows))]
    return Err("Windows privacy file-sharing probe unavailable".into());
    fs::create_dir(output)
        .map_err(|_| "Privacy delete probe requires a fresh, creatable output folder")?;
    let output = output
        .canonicalize()
        .map_err(|_| "Cannot resolve privacy probe directory")?;
    let recordings = output.join("recordings");
    let state = output.join("state");
    fs::create_dir(&recordings).map_err(|_| "Cannot create controlled recording directory")?;
    fs::create_dir(&state).map_err(|_| "Cannot create controlled state directory")?;
    let index = state.join("sessions.json");
    let settings = state.join("settings.json");
    let _environment = Environment::set(&[
        ("COMPANION_TYPE_RECORDING_DIR", recordings.as_os_str()),
        ("COMPANION_TYPE_STATE_PATH", index.as_os_str()),
        ("COMPANION_TYPE_STATE_DIR", state.as_os_str()),
        ("COMPANION_TYPE_PRODUCT_SETTINGS_PATH", settings.as_os_str()),
        (
            "COMPANION_TYPE_BLE_NATIVE_DISABLED",
            std::ffi::OsStr::new("1"),
        ),
        (
            "COMPANION_TYPE_DISABLE_AUTO_RECOVERY",
            std::ffi::OsStr::new("1"),
        ),
    ]);
    let first = recordings.join("first.wav");
    let second = recordings.join("second.wav");
    write_wav(&first)?;
    write_wav(&second)?;
    let first_bytes = fs::read(&first).map_err(|_| "Cannot read controlled original")?;
    let sessions = vec![session("first", &first)?, session("second", &second)?];
    let single = [
        Action::PrivacyEraseAudio,
        Action::PrivacyEraseTranscript,
        Action::PrivacyDeleteSession,
    ];
    let actions = [
        Action::PrivacyEraseAudio,
        Action::PrivacyEraseTranscript,
        Action::PrivacyDeleteSession,
        Action::PrivacyEraseAll,
    ];
    let mut checks = Vec::new();
    let mut check = |name: &str, passed: bool| -> Result<(), String> {
        checks.push(json!({"name":name,"passed":passed}));
        if passed {
            Ok(())
        } else {
            Err(format!("Privacy delete probe failed: {name}"))
        }
    };
    let backend = FixtureCompanionBackend::new();
    for (case, selected, requested) in [
        ("missing_request", Some("first"), None),
        ("missing_selection", None, Some("first")),
        ("stale_confirmation", Some("second"), Some("first")),
        ("unknown_target", Some("missing"), Some("missing")),
    ] {
        for action in single {
            let before = snapshot(sessions.clone(), selected);
            install_snapshot(&backend, before.clone())?;
            let index_before=fs::read(&index).map_err(|_|"Cannot inspect seeded index")?;
            let result = backend.apply_control(request(action, requested)?);
            check(
                &format!("{case}_{action:?}_no_side_effects"),
                result.is_err()
                    && equal(&before, &backend.snapshot()?)
                    && fs::read(&first).ok().as_ref() == Some(&first_bytes)
                    && second.is_file()
                    && fs::read(&index).ok().as_ref()==Some(&index_before),
            )?;
        }
    }
    for state_name in ["host_recording", "device_recording", "meeting_active"] {
        for action in actions {
            let mut before = snapshot(sessions.clone(), Some("first"));
            match state_name {
                "host_recording" => before.host.sessions[0].status = "recording".into(),
                "device_recording" => before.device.recording = true,
                _ => before.meeting.active = true,
            }
            install_snapshot(&backend, before.clone())?;
            let index_before=fs::read(&index).map_err(|_|"Cannot inspect seeded index")?;
            let result = backend.apply_control(request(action, Some("first"))?);
            check(
                &format!("{state_name}_{action:?}_no_side_effects"),
                result.is_err()
                    && equal(&before, &backend.snapshot()?)
                    && first.is_file()
                    && fs::read(&index).ok().as_ref()==Some(&index_before),
            )?;
        }
    }
    for action in actions {
        check(
            &format!("live_asr_flag_{action:?}_refused"),
            super::validate_control(
                &snapshot(sessions.clone(), Some("first")),
                &request(action, Some("first"))?,
                true,
            )
            .is_err(),
        )?;
    }
    let no_selection =
        super::PrivacyManager::new().erase_selected_audio(&snapshot(sessions.clone(), None));
    check(
        "missing_selection_never_expands_file_scope",
        no_selection.failed_files != 0
            && no_selection.deleted_files == 0
            && first.is_file()
            && second.is_file(),
    )?;

    let transcript_audio=recordings.join("transcript-kept.wav");
    write_wav(&transcript_audio)?;
    let audio_before=fs::read(&transcript_audio).map_err(|_|"Cannot inspect transcript-case audio")?;
    let mut transcript_session=session("transcript-only",&transcript_audio)?;
    transcript_session.note_revision=1;
    transcript_session.meeting_notes.push(super::super::meeting_notes::Note {
        id:uuid::Uuid::new_v4().to_string(),text:"Controlled user note".into(),bookmark_id:None,
        image:None,created_at:"controlled".into(),updated_at:"controlled".into(),
    });
    install_snapshot(&backend, snapshot(vec![transcript_session],Some("transcript-only")))?;
    let text_erased=backend.apply_control(request(Action::PrivacyEraseTranscript,Some("transcript-only"))?)?;
    check("transcript_delete_keeps_exact_audio_bytes",
        fs::read(&transcript_audio).ok().as_ref()==Some(&audio_before)
            && text_erased.host.sessions[0].audio_stored
            && text_erased.host.sessions[0].audio_path.as_deref()==Some(transcript_audio.to_string_lossy().as_ref()))?;
    check("transcript_delete_clears_text_and_user_notes",
        text_erased.host.sessions[0].transcript_text.is_empty()
            && !text_erased.host.sessions[0].transcript_final
            && text_erased.host.sessions[0].meeting_notes.is_empty())?;
    let (text_reload,_)=persistence::load_sessions_with_status();
    check("transcript_delete_checkpoint_survives_reload",
        text_reload.as_ref().is_some_and(|rows|rows.len()==1&&equal(&rows[0],&text_erased.host.sessions[0])))?;

    let shared = recordings.join("shared.wav");
    write_wav(&shared)?;
    let unknown = recordings.join("unknown.opus");
    fs::write(&unknown, b"unknown file must remain")
        .map_err(|_| "Cannot create controlled unknown")?;
    let outside = output.join("user-export.wav");
    write_wav(&outside)?;
    let mut shared_sessions = vec![session("first", &shared)?, session("second", &shared)?];
    // Protect a retained chunk reference as well as its primary path.
    shared_sessions[1].audio_path = Some(second.to_string_lossy().into());
    let mut chunk = synced_device_session(
        &fixture_snapshot(),
        &request(Action::DeviceSyncRecordings, Some("chunk"))?,
        "controlled",
    )
    .chunks
    .remove(0);
    chunk.path = Some(shared.to_string_lossy().into());
    chunk.bytes = 46;
    chunk.status = "sealed".into();
    shared_sessions[1].chunks = vec![chunk];
    let retained = shared_sessions[1].clone();
    install_snapshot(&backend, snapshot(shared_sessions, Some("first")))?;
    let cleared = backend.apply_control(request(Action::PrivacyDeleteSession, Some("first"))?)?;
    check(
        "delete_one_meeting_preserves_anothers_chunk_audio",
        cleared.host.sessions.len() == 1
            && equal(&retained, &cleared.host.sessions[0])
            && shared.is_file()
            && second.is_file(),
    )?;
    check(
        "shared_reference_retention_reported",
        cleared
            .last_control
            .as_ref()
            .is_some_and(|echo| echo.message.contains("1 retained for other meetings")),
    )?;
    let (loaded, _) = persistence::load_sessions_with_status();
    check(
        "shared_reference_survives_reload",
        loaded
            .as_ref()
            .is_some_and(|value| value.len() == 1 && equal(&retained, &value[0])),
    )?;

    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        for action in [
            Action::PrivacyEraseAudio,
            Action::PrivacyDeleteSession,
            Action::PrivacyEraseAll,
        ] {
            let before = snapshot(vec![session("first", &first)?], Some("first"));
            install_snapshot(&backend, before.clone())?;
            let index_before=fs::read(&index).map_err(|_|"Cannot inspect seeded index")?;
            let held = fs::OpenOptions::new()
                .read(true)
                .share_mode(0)
                .open(&first)
                .map_err(|_| "Cannot hold controlled file")?;
            let failed = backend.apply_control(request(action, Some("first"))?);
            check(
                &format!("occupied_original_{action:?}_preserves_retry"),
                failed.is_err() && equal(&before, &backend.snapshot()?) && first.is_file()
                    && fs::read(&index).ok().as_ref()==Some(&index_before),
            )?;
            drop(held);
        }
    }
    let released_before=snapshot(vec![session("first", &first)?], Some("first"));
    install_snapshot(&backend, released_before.clone())?;
    let retried = backend.apply_control(request(Action::PrivacyEraseAudio, Some("first"))?)?;
    check(
        "released_original_retry_clears_pointer_only_after_delete",
        !first.exists()
            && !retried.host.sessions[0].audio_stored
            && !retried.host.sessions[0].retention.audio_cached
            && retried.host.sessions[0].audio_path.is_none()
            && retried.host.sessions[0].transcript_text==released_before.host.sessions[0].transcript_text
            && retried.host.sessions[0].transcript_final,
    )?;
    install_snapshot(&backend, snapshot(vec![session("outside", &outside)?], Some("outside")))?;
    let external = backend.apply_control(request(Action::PrivacyEraseAudio, Some("outside"))?)?;
    check(
        "user_owned_export_not_deleted",
        outside.is_file() && external.host.sessions[0].audio_path.is_none(),
    )?;
    install_snapshot(&backend, snapshot(
        vec![session("shared-1", &shared)?,session("shared-2", &shared)?,session("second", &second)?],
        Some("second")))?;
    let all = backend.apply_control(request(Action::PrivacyEraseAll, None)?)?;
    check(
        "delete_all_removes_shared_indexed_files",
        all.host.sessions.is_empty() && !shared.exists() && !second.exists(),
    )?;
    check(
        "unknown_and_user_export_remain",
        unknown.is_file() && outside.is_file(),
    )?;
    let primary: Vec<CompanionV1HostSession> =
        serde_json::from_slice(&fs::read(&index).map_err(|_| "Cannot read cleared index")?)
            .map_err(|_| "Cleared index invalid")?;
    let backup: Vec<CompanionV1HostSession> = serde_json::from_slice(
        &fs::read(index.with_file_name("sessions.json.bak"))
            .map_err(|_| "Cannot read cleared backup")?,
    )
    .map_err(|_| "Cleared backup invalid")?;
    check(
        "index_and_backup_cannot_restore_removed_meetings",
        primary.is_empty() && backup.is_empty(),
    )?;

    // Exercise actual ledger publication failure after all referenced WAVs
    // were already deleted, then retry with the absent primary pointer.
    let legacy = output.join("legacy");
    fs::create_dir(&legacy).map_err(|_| "Cannot create controlled legacy root")?;
    let old = legacy.join("legacy.wav");
    write_wav(&old)?;
    let mut original = session("legacy", &old)?;
    original.source = "hostMicrophone".into();
    let mut chunk = synced_device_session(
        &fixture_snapshot(),
        &request(Action::DeviceSyncRecordings, Some("old"))?,
        "controlled",
    )
    .chunks
    .remove(0);
    chunk.path = original.audio_path.clone();
    chunk.bytes = 46;
    chunk.status = "sealed".into();
    original.chunks = vec![chunk];
    let (migrated, _) = audio_storage::migrate_legacy_sessions(&[original], &recordings, &legacy)?;
    let migrated_path = PathBuf::from(
        migrated[0]
            .audio_path
            .as_deref()
            .ok_or("Missing migrated pointer")?,
    );
    let manager = super::PrivacyManager {
        minutes_cache_root: None,
        cache_root: None,
        recording_root: Some(recordings.clone()),
        legacy_root_override: Some(legacy),
    };
    let seeded = snapshot(migrated, Some("legacy"));
    let ledger = recordings.join(".legacy-audio-copies.json");
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        let held = fs::OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(&ledger)
            .map_err(|_| "Cannot hold controlled ledger")?;
        let failed = manager.erase_selected_audio(&seeded);
        check(
            "ledger_commit_failure_is_reported_after_file_removal",
            failed.failed_files != 0 && !old.exists() && !migrated_path.exists(),
        )?;
        drop(held);
    }
    let retry = manager.erase_selected_audio(&seeded);
    let ledger_value: Value =
        serde_json::from_slice(&fs::read(&ledger).map_err(|_| "Cannot inspect controlled ledger")?)
            .map_err(|_| "Controlled ledger invalid")?;
    check(
        "missing_primary_retry_finishes_migration_ledger",
        retry.failed_files == 0 && ledger_value["copies"].as_array().is_some_and(Vec::is_empty),
    )?;
    check(
        "ledger_retry_is_idempotent",
        manager.erase_selected_audio(&seeded).failed_files == 0,
    )?;
    let report = json!({"schema":"companion.type.privacy_delete_probe.v1","result":"PASS_LOCAL_PRIVACY_DELETE_SAFETY_ONLY","checks":checks,
        "realUserProfileAccess":false,"networkAccess":false,"deviceAccess":false,"guiAcceptance":"NOT_RUN","fullChainAcceptance":"NOT_RUN",
        "scope":"Explicit deletion target, active recording exclusion, shared indexed audio protection and migration retry only",
        "artifactLedgerComplete":false,"asrCachePrivacyDeletionComplete":false});
    fs::write(
        output.join("result.json"),
        serde_json::to_vec_pretty(&report).map_err(|_| "Cannot encode privacy report")?,
    )
    .map_err(|_| "Cannot save privacy report")?;
    Ok(report)
}

#[cfg(all(test, windows))]
mod tests {
    #[test]
    fn production_delete_guards_shared_files_and_occupied_ledger_retry() {
        let root =
            std::env::temp_dir().join(format!("companion-privacy-safety-{}", uuid::Uuid::new_v4()));
        let report = super::verify(&root).unwrap();
        assert!(report["checks"]
            .as_array()
            .unwrap()
            .iter()
            .all(|check| check["passed"] == true));
    }
}
