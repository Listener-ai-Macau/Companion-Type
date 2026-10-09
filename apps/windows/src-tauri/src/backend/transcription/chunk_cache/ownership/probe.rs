//! Controlled local bodies and PCM only; no provider, user profile or device.
use super::*;
use crate::backend::{
    audio_artifacts as audio, persistence, CompanionBackend, FixtureCompanionBackend,
};
use crate::companion_v1::{
    fixture_snapshot, synced_device_session, CompanionV1ControlAction as Action,
    CompanionV1ControlRequest, CompanionV1HostSession, CompanionV1Snapshot,
};
use serde_json::{json, Value};
struct Environment(Vec<(&'static str, Option<std::ffi::OsString>)>);
impl Environment {
    fn set(values: &[(&'static str, &std::ffi::OsStr)]) -> Self {
        Self(
            values
                .iter()
                .map(|(k, v)| {
                    let old = std::env::var_os(k);
                    std::env::set_var(k, v);
                    (*k, old)
                })
                .collect(),
        )
    }
}
impl Drop for Environment {
    fn drop(&mut self) {
        for (k, v) in &self.0 {
            if let Some(v) = v {
                std::env::set_var(k, v)
            } else {
                std::env::remove_var(k)
            }
        }
    }
}
fn request(action: Action, id: Option<&str>) -> CompanionV1ControlRequest {
    serde_json::from_value(json!({"action":action,"sessionId":id})).unwrap()
}
fn session(id: &str, path: &Path) -> CompanionV1HostSession {
    let mut s = synced_device_session(
        &fixture_snapshot(),
        &request(Action::DeviceSyncRecordings, Some(id)),
        "controlled",
    );
    s.id = id.into();
    s.source = "controlledCachePrivacyFixture".into();
    s.audio_path = Some(path.to_string_lossy().into_owned());
    s.chunks.clear();
    s.device_recording_id = None;
    s.device_total_length = None;
    s.device_sha256 = None;
    s.source_device_id = None;
    s.transcript_text = "Controlled final transcript".into();
    s.transcript_final = true;
    s.retention.transcript_cached = true;
    s
}
fn snapshot(sessions: Vec<CompanionV1HostSession>, id: &str) -> CompanionV1Snapshot {
    let mut s = fixture_snapshot();
    s.host.sessions = sessions;
    s.host.selected_session_id = Some(id.into());
    s.host.active_session_id = None;
    s.host.persistence = Default::default();
    s.device.recording = false;
    s.meeting.active = false;
    s
}
fn put_wav(path: &Path, pcm: &[u8]) -> Result<(), String> {
    let mut bytes = Vec::new();
    bytes.extend(b"RIFF");
    bytes.extend(&(36 + pcm.len() as u32).to_le_bytes());
    bytes.extend(b"WAVEfmt ");
    bytes.extend(&16u32.to_le_bytes());
    bytes.extend(&1u16.to_le_bytes());
    bytes.extend(&1u16.to_le_bytes());
    bytes.extend(&16000u32.to_le_bytes());
    bytes.extend(&32000u32.to_le_bytes());
    bytes.extend(&2u16.to_le_bytes());
    bytes.extend(&16u16.to_le_bytes());
    bytes.extend(b"data");
    bytes.extend(&(pcm.len() as u32).to_le_bytes());
    bytes.extend(pcm);
    fs::write(path, bytes).map_err(|_| fail())
}
pub(crate) fn verify(output: &Path) -> Result<Value, String> {
    fs::create_dir(output)
        .map_err(|_| "Cache privacy probe requires a fresh, creatable output folder")?;
    let output = output.canonicalize().map_err(|_| fail())?;
    let recordings = output.join("recordings");
    let root = output.join("cache");
    let state = output.join("state");
    for dir in [&recordings, &state] {
        fs::create_dir(dir).map_err(|_| fail())?;
    }
    let index = state.join("sessions.json");
    let settings = state.join("settings.json");
    let _environment = Environment::set(&[
        ("COMPANION_TYPE_RECORDING_DIR", recordings.as_os_str()),
        ("COMPANION_TYPE_ASR_CACHE_DIR", root.as_os_str()),
        ("COMPANION_TYPE_STATE_PATH", index.as_os_str()),
        ("COMPANION_TYPE_STATE_DIR", state.as_os_str()),
        ("COMPANION_TYPE_PRODUCT_SETTINGS_PATH", settings.as_os_str()),
        ("LOCALAPPDATA", state.as_os_str()),
        (
            "COMPANION_TYPE_BLE_NATIVE_DISABLED",
            std::ffi::OsStr::new("1"),
        ),
        (
            "COMPANION_TYPE_DISABLE_AUTO_RECOVERY",
            std::ffi::OsStr::new("1"),
        ),
    ]);
    let mut checks = Vec::new();
    let mut check = |name: &str, passed: bool| -> Result<(), String> {
        checks.push(json!({"name":name,"passed":passed}));
        if passed {
            Ok(())
        } else {
            Err(format!("Cache privacy check failed: {name}"))
        }
    };
    let pcm = vec![0x31; 32_000];
    let a = recordings.join("a.wav");
    let b = recordings.join("b.wav");
    put_wav(&a, &pcm)?;
    put_wav(&b, &pcm)?;
    let key = Key::new(
        &pcm,
        Profile::from_configuration(
            &json!({"provider":"controlled", "model":"controlled", "language":"auto"}),
        )?,
    )?;
    let path = key.path(&root)?;
    let calls = std::cell::Cell::new(0);
    let provider = || {
        calls.set(calls.get() + 1);
        Ok(("Controlled provider final".into(), vec![]))
    };
    let first = resolve(&root, &key, &a, provider)?;
    let second = resolve(&root, &key, &b, provider)?;
    check(
        "shared_pcm_hit_adds_both_source_owners",
        first == second
            && calls.get() == 1
            && load_journal(&root)?.records[0]
                .sources
                .contains(&audio::reference_key(&b)?),
    )?;
    bind_session(&root, "a", &audio::source_references(&a)?)?;
    bind_session(&root, "b", &audio::source_references(&b)?)?;
    check(
        "same_cache_has_two_explicit_session_owners",
        load_journal(&root)?.records[0].sessions.len() == 2,
    )?;
    let journal = fs::read_to_string(root.join(JOURNAL)).map_err(|_| fail())?;
    check(
        "journal_contains_no_body_or_embeddings",
        !journal.contains(&first.0) && !journal.contains("embedding"),
    )?;
    let backend = FixtureCompanionBackend::new();
    let initial = snapshot(vec![session("a", &a), session("b", &b)], "a");
    *backend.snapshot.lock().map_err(|_| fail())? = initial.clone();
    check(
        "stale_session_target_rejected_before_cache_effects",
        backend
            .apply_control(request(Action::PrivacyEraseTranscript, Some("b")))
            .is_err()
            && path.is_file(),
    )?;
    let other = serde_json::to_value(&initial.host.sessions[1]).unwrap();
    let cleared = backend.apply_control(request(Action::PrivacyEraseTranscript, Some("a")))?;
    check(
        "clear_transcript_preserves_shared_cache_and_other_meeting",
        path.is_file() && serde_json::to_value(&cleared.host.sessions[1]).unwrap() == other,
    )?;
    check(
        "clear_transcript_releases_only_selected_session",
        load_journal(&root)?.records[0].sessions == BTreeSet::from(["b".into()]),
    )?;
    check(
        "clear_transcript_keeps_original_audio",
        a.is_file() && b.is_file() && cleared.host.sessions[0].transcript_text.is_empty(),
    )?;
    let mut selected = cleared;
    selected.host.selected_session_id = Some("b".into());
    *backend.snapshot.lock().map_err(|_| fail())? = selected;
    backend.apply_control(request(Action::PrivacyEraseTranscript, Some("b")))?;
    check(
        "last_transcript_owner_removes_cache_body",
        !path.exists() && load_journal(&root)?.records.is_empty(),
    )?;
    check(
        "cleared_cache_does_not_silently_resurrect",
        super::super::load(&root, &key).is_none(),
    )?;
    check(
        "explicit_new_transcription_can_repopulate",
        resolve(&root, &key, &a, provider)? == first && calls.get() == 2,
    )?;
    bind_session(&root, "a", &audio::source_references(&a)?)?;
    // Protect the index until native Windows DELETE sharing permits removal.
    #[cfg(windows)]
    let occupied = {
        use std::os::windows::fs::OpenOptionsExt;
        OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(&path)
            .map_err(|_| fail())?
    };
    *backend.snapshot.lock().map_err(|_| fail())? = snapshot(vec![session("a", &a)], "a");
    #[cfg(windows)]
    {
        check(
            "occupied_cache_blocks_transcript_index_commit",
            backend
                .apply_control(request(Action::PrivacyEraseTranscript, Some("a")))
                .is_err()
                && !backend.snapshot()?.host.sessions[0]
                    .transcript_text
                    .is_empty(),
        )?;
        check(
            "occupied_cache_leaves_durable_delete_intent",
            load_journal(&root)?.records[0].phase == Phase::Deleting,
        )?;
        let before = calls.get();
        resolve(&root, &key, &a, provider)?;
        check(
            "pending_delete_cannot_become_cache_hit_or_republish",
            calls.get() == before + 1 && load_journal(&root)?.records[0].phase == Phase::Deleting,
        )?;
        drop(occupied);
    }
    // Load a fresh coordinator from disk: no volatile owner state is needed.
    let mut durable = backend.snapshot()?;
    persistence::save_snapshot(&mut durable)?;
    drop(backend);
    let restarted = FixtureCompanionBackend::new();
    restarted.apply_control(request(Action::MeetingSelectSession, Some("a")))?;
    restarted.apply_control(request(Action::PrivacyEraseTranscript, Some("a")))?;
    check(
        "fresh_coordinator_retries_durable_cache_delete",
        !path.exists()
            && restarted.snapshot()?.host.sessions[0]
                .transcript_text
                .is_empty(),
    )?;
    check(
        "primary_and_backup_transcript_are_cleared",
        [index.clone(), index.with_file_name("sessions.json.bak")]
            .iter()
            .all(|p| {
                fs::read_to_string(p)
                    .map(|s| !s.contains("Controlled final transcript"))
                    .unwrap_or(false)
            }),
    )?;
    // A surviving session ID still owns its cache after audio is missing.
    resolve(&root, &key, &a, provider)?;
    bind_session(&root, "a", &audio::source_references(&a)?)?;
    fs::remove_file(&a).map_err(|_| fail())?;
    let mut without_audio = snapshot(vec![session("a", &a)], "a");
    without_audio.host.sessions[0].audio_path = None;
    *restarted.snapshot.lock().map_err(|_| fail())? = without_audio;
    restarted.apply_control(request(Action::PrivacyEraseTranscript, Some("a")))?;
    check(
        "session_owner_survives_absent_audio_pointer",
        !path.exists(),
    )?;
    put_wav(&a, &pcm)?;
    // Cache ancestry survives removal of the ASR scratch file.
    let scratch = recordings.join(".companion-asr-owned.wav");
    audio::generated(&a, &scratch, audio::Purpose::AsrTemporary, || {
        put_wav(&scratch, &pcm)
    })?;
    resolve(&root, &key, &scratch, provider)?;
    check(
        "scratch_cache_captures_original_ancestry",
        load_journal(&root)?.records[0]
            .sources
            .contains(&audio::reference_key(&a)?),
    )?;
    audio::remove_temporary(&scratch)?;
    bind_session(&root, "a", &audio::source_references(&a)?)?;
    *restarted.snapshot.lock().map_err(|_| fail())? = snapshot(vec![session("a", &a)], "a");
    restarted.apply_control(request(Action::PrivacyEraseTranscript, Some("a")))?;
    check("scratch_removal_does_not_orphan_cache", !path.exists())?;
    let prefix = recordings.join("prefix.wav");
    audio::generated(&prefix, &prefix, audio::Purpose::Recording, || {
        put_wav(&prefix, &pcm)
    })?;
    resolve(&root, &key, &prefix, provider)?;
    audio::attach_group(&prefix, &a)?;
    bind_session(&root, "a", &audio::source_references(&a)?)?;
    check(
        "final_recording_adopts_live_prefix_cache",
        load_journal(&root)?.records[0].sessions.contains("a"),
    )?;
    // Protect a source held by another ASR consumer before any cache effects.
    let usage = audio::usage(&a)?;
    let before = fs::read(&path).map_err(|_| fail())?;
    check(
        "active_asr_lease_blocks_privacy_cache_effects",
        restarted
            .apply_control(request(Action::PrivacyEraseTranscript, Some("a")))
            .is_err()
            && fs::read(&path).map_err(|_| fail())? == before,
    )?;
    drop(usage);
    restarted.apply_control(request(Action::PrivacyEraseTranscript, Some("a")))?;
    check("released_asr_lease_allows_delete_retry", !path.exists())?;
    // Strict legacy V2 adoption. The previous processing profile is obsolete,
    // but its body remains private data and must not merely be a cache miss.
    let mut old = key.clone();
    old.profile.processing_version = "pcm16k-mono-s16le-volc-final-v2".into();
    super::super::store(&root, &old, "Old V2 final body", &[])?;
    let old_path = old.path(&root)?;
    *restarted.snapshot.lock().map_err(|_| fail())? = snapshot(vec![session("a", &a)], "a");
    restarted.apply_control(request(Action::PrivacyEraseTranscript, Some("a")))?;
    check(
        "verified_old_v2_is_removed_by_exact_pcm_identity",
        !old_path.exists(),
    )?;
    super::super::store(&root, &old, "Old V2 final body", &[])?;
    *restarted.snapshot.lock().map_err(|_| fail())? =
        snapshot(vec![session("a", &a), session("b", &b)], "a");
    restarted.apply_control(request(Action::PrivacyEraseTranscript, Some("a")))?;
    check("unbound_legacy_shared_pcm_is_preserved", old_path.is_file())?;
    let unknown = root.join(format!("{:064x}.json", 8));
    fs::write(
        &unknown,
        b"{\"schema\":\"companion-type.asr-chunk-cache.v1\",\"embedding\":[1,2]}",
    )
    .map_err(|_| fail())?;
    let unrelated = root.join("user-export.json");
    fs::write(&unrelated, b"user-owned").map_err(|_| fail())?;
    let outside = output.join("external-original.wav");
    put_wav(&outside, &pcm)?;
    let all = restarted.apply_control(request(Action::PrivacyEraseAll, None))?;
    check("erase_all_removes_verified_v2_body", !old_path.exists())?;
    check(
        "unprovable_v1_embedding_and_user_exports_preserved",
        unknown.is_file() && unrelated.is_file() && outside.is_file(),
    )?;
    check(
        "erase_all_reports_unverified_legacy_files",
        all.last_control
            .as_ref()
            .is_some_and(|c| c.message.contains("1 unverified legacy cache")),
    )?;
    put_wav(&a, &pcm)?;
    resolve(&root, &key, &a, provider)?;
    bind_session(&root, "a", &audio::source_references(&a)?)?;
    *restarted.snapshot.lock().map_err(|_| fail())? = snapshot(vec![session("a", &a)], "a");
    fs::write(&path, b"changed").map_err(|_| fail())?;
    check(
        "changed_owned_body_blocks_erase_without_index_commit",
        restarted
            .apply_control(request(Action::PrivacyEraseTranscript, Some("a")))
            .is_err()
            && fs::read(&path).map_err(|_| fail())? == b"changed",
    )?;
    let before = calls.get();
    resolve(&root, &key, &a, provider)?;
    check(
        "explicit_asr_repair_updates_body_identity",
        calls.get() == before + 1 && inspect(&path).is_some(),
    )?;
    let saved = fs::read(root.join(JOURNAL)).map_err(|_| fail())?;
    fs::write(root.join(JOURNAL), b"{interrupted").map_err(|_| fail())?;
    check(
        "corrupt_journal_preserves_cache_and_meeting",
        restarted
            .apply_control(request(Action::PrivacyEraseTranscript, Some("a")))
            .is_err()
            && path.is_file(),
    )?;
    let before = calls.get();
    let paid = resolve(&root, &key, &a, provider)?;
    check(
        "journal_fault_preserves_paid_result_without_publish",
        paid == first
            && calls.get() == before + 1
            && fs::read(root.join(JOURNAL)).map_err(|_| fail())? == b"{interrupted",
    )?;
    fs::write(root.join(JOURNAL), &saved).map_err(|_| fail())?;
    let mut traversal: Value = serde_json::from_slice(&saved).map_err(|_| fail())?;
    traversal["records"][0]["file"] = json!("../user-export.json");
    fs::write(root.join(JOURNAL), serde_json::to_vec(&traversal).unwrap()).map_err(|_| fail())?;
    check(
        "journal_traversal_cannot_delete_outside_cache",
        restarted
            .apply_control(request(Action::PrivacyEraseTranscript, Some("a")))
            .is_err()
            && outside.is_file()
            && unrelated.is_file(),
    )?;
    fs::write(root.join(JOURNAL), &saved).map_err(|_| fail())?;
    let journal_lock = lock(&root)?;
    check(
        "native_journal_lock_blocks_competing_privacy",
        restarted
            .apply_control(request(Action::PrivacyEraseTranscript, Some("a")))
            .is_err()
            && path.is_file(),
    )?;
    drop(journal_lock);
    restarted.apply_control(request(Action::PrivacyDeleteSession, Some("a")))?;
    check(
        "delete_session_removes_bound_cache_and_index",
        !path.exists() && restarted.snapshot()?.host.sessions.is_empty(),
    )?;
    let report = json!({"schema":"companion.type.local_cache_privacy_probe.v1","result":"PASS_LOCAL_CACHE_PRIVACY_ONLY","checks":checks,
        "realUserProfileAccess":false,"networkAccess":false,"deviceAccess":false,"realMicrophoneAccess":false,
        "legacyV1EmbeddingDeletion":"NOT_IMPLEMENTED_UNPROVEN_IDENTITY","allHistoricalPrivacyEraseComplete":false,
        "crossProcessAcceptance":"NOT_RUN","realProcessRestartAcceptance":"NOT_RUN","physicalPowerLossAcceptance":"NOT_RUN",
        "nativeGui":"NOT_RUN","trueAsrAcceptance":"NOT_RUN","hardwareAcceptance":"NOT_RUN","fullChainAcceptance":"NOT_RUN"});
    fs::write(
        output.join("result.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .map_err(|_| fail())?;
    Ok(report)
}
