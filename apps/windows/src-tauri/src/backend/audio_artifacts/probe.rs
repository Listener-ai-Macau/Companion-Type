//! Isolated real filesystem/decoder/coordinator checks, never real recordings.
use super::super::{CompanionBackend, FixtureCompanionBackend};
use super::*;
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
fn session(id: &str, audio: &Path) -> CompanionV1HostSession {
    let mut s = synced_device_session(
        &fixture_snapshot(),
        &request(Action::DeviceSyncRecordings, Some(id)),
        "controlled",
    );
    s.id = id.into();
    s.source = "controlledArtifactsFixture".into();
    s.status = "captured".into();
    s.audio_path = Some(audio.to_string_lossy().into_owned());
    s.audio_bytes = 44;
    s.audio_stored = true;
    s.retention.audio_cached = true;
    s.chunks.clear();
    s.device_recording_id = None;
    s.device_total_length = None;
    s.device_sha256 = None;
    s.source_device_id = None;
    s.device_reclaimed = false;
    s.recovery = Default::default();
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
fn put(source: &Path, path: &Path, purpose: Purpose, bytes: &[u8]) -> Result<(), String> {
    generated(source, path, purpose, || {
        super::super::export::write_atomic(path, bytes).map(|_| ())
    })
}
fn wav(pcm: &[u8]) -> Vec<u8> {
    let mut b = Vec::new();
    b.extend_from_slice(b"RIFF");
    b.extend_from_slice(&(36 + pcm.len() as u32).to_le_bytes());
    b.extend_from_slice(b"WAVEfmt ");
    b.extend_from_slice(&16u32.to_le_bytes());
    b.extend_from_slice(&1u16.to_le_bytes());
    b.extend_from_slice(&1u16.to_le_bytes());
    b.extend_from_slice(&16000u32.to_le_bytes());
    b.extend_from_slice(&32000u32.to_le_bytes());
    b.extend_from_slice(&2u16.to_le_bytes());
    b.extend_from_slice(&16u16.to_le_bytes());
    b.extend_from_slice(b"data");
    b.extend_from_slice(&(pcm.len() as u32).to_le_bytes());
    b.extend_from_slice(pcm);
    b
}
pub(crate) fn verify(output: &Path) -> Result<Value, String> {
    #[cfg(not(windows))]
    return Err("Windows audio artifact probe unavailable".into());
    fs::create_dir(output)
        .map_err(|_| "Audio artifacts probe requires a fresh, creatable output folder")?;
    let output = output.canonicalize().map_err(|_| fail())?;
    let root = output.join("recordings");
    let state = output.join("state");
    fs::create_dir(&root).map_err(|_| fail())?;
    fs::create_dir(&state).map_err(|_| fail())?;
    let index = state.join("sessions.json");
    let settings = state.join("settings.json");
    let _env = Environment::set(&[
        ("COMPANION_TYPE_RECORDING_DIR", root.as_os_str()),
        ("COMPANION_TYPE_STATE_DIR", state.as_os_str()),
        ("COMPANION_TYPE_STATE_PATH", index.as_os_str()),
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
    let mut checks = Vec::new();
    let mut check = |name: &str, ok: bool| -> Result<(), String> {
        if !ok {
            return Err(format!("Audio artifacts probe failed: {name}"));
        }
        checks.push(json!({"name":name,"passed":true}));
        Ok(())
    };
    let primary = root.join("会议 🐾.wav");
    let raw = primary.with_extension("opus");
    let mut cop = b"COP1\x01\x01\x14\x00".to_vec();
    cop.extend_from_slice(&16000u32.to_le_bytes());
    for _ in 0..3 {
        cop.extend_from_slice(&[3, 0, 0xf8, 0xff, 0xfe]);
    }
    let mut prepared = false;
    generated(&primary, &raw, Purpose::CompressedOriginal, || {
        prepared = load(&root)?.files.iter().any(|i| {
            i.file == raw.file_name().unwrap().to_str().unwrap()
                && i.phase == Phase::Prepared
                && i.identity.is_none()
        }) && !raw.exists();
        super::super::export::write_atomic(&raw, &cop).map(|_| ())
    })?;
    check("ownership_intent_precedes_file_creation", prepared)?;
    check(
        "compressed_original_has_exact_sealed_identity",
        load(&root)?.files.iter().any(|i| {
            i.purpose == Purpose::CompressedOriginal
                && i.phase == Phase::Sealed
                && i.identity == fingerprint(&raw).unwrap()
        }),
    )?;
    super::super::audio_decode::decode_recording(&raw, &primary, false)?;
    check(
        "real_native_COP1_decoder_registers_primary",
        fs::read(&primary).map_err(|_| fail())?.starts_with(b"RIFF")
            && load(&root)?.files.iter().any(|i| {
                i.file == primary.file_name().unwrap().to_str().unwrap() && i.phase == Phase::Sealed
            }),
    )?;
    check(
        "native_decoder_temporary_is_retired_after_atomic_move",
        load(&root)?
            .files
            .iter()
            .any(|i| i.purpose == Purpose::DecodeTemporary && i.phase == Phase::Gone),
    )?;
    let original = fs::read(&primary).map_err(|_| fail())?;
    let cursor = root.join(".device-recording-42-complete.part");
    fs::write(&cursor, &cop).map_err(|_| fail())?;
    let cursor_identity = fingerprint(&cursor)?.ok_or_else(fail)?;
    check(
        "cursor_adoption_rejects_wrong_full_byte_identity",
        verified_cursor(&primary, &cursor, cop.len() as u64, &"0".repeat(64)).is_err()
            && cursor.is_file(),
    )?;
    verified_cursor(
        &primary,
        &cursor,
        cursor_identity.bytes,
        &cursor_identity.sha256,
    )?;
    check(
        "verified_complete_transfer_cursor_has_recorded_owner",
        load(&root)?.files.iter().any(|i| {
            i.purpose == Purpose::TransferCursor
                && i.phase == Phase::Sealed
                && i.sources.contains(&reference_key(&primary).unwrap())
        }),
    )?;
    let bad = root.join("invalid.cop1");
    fs::write(&bad, b"COP1-invalid").map_err(|_| fail())?;
    check(
        "decode_failure_keeps_original_recording",
        super::super::audio_decode::decode_recording(&bad, &primary, false).is_err()
            && fs::read(&primary).ok().as_ref() == Some(&original),
    )?;
    let unknown = root.join("looks-like-recording.opus");
    fs::write(&unknown, b"unknown-user-file").map_err(|_| fail())?;
    let outside = output.join("imported.wav");
    fs::write(&outside, wav(&[1; 96_000])).map_err(|_| fail())?;
    check(
        "unknown_existing_file_cannot_be_adopted_or_replaced",
        put(
            &primary,
            &unknown,
            Purpose::CompressedOriginal,
            b"replacement",
        )
        .is_err()
            && fs::read(&unknown).ok().as_deref() == Some(b"unknown-user-file"),
    )?;
    let external = output.join("external-export.wav");
    put(&primary, &external, Purpose::Recording, b"external")?;
    check(
        "imports_and_exports_are_not_implicitly_registered",
        !load(&root)?
            .files
            .iter()
            .any(|i| i.file == "external-export.wav"),
    )?;
    check(
        "temporary_deletion_rejects_unmanaged_file",
        remove_temporary(&external).is_err() && external.is_file(),
    )?;
    let chunks = super::super::transcription::split_long_wav_into_chunks(&outside, 1)?;
    check(
        "long_ASR_chunks_are_created_in_managed_root",
        chunks.len() == 3 && chunks.iter().all(|p| p.parent() == Some(root.as_path())),
    )?;
    check(
        "ASR_chunks_have_source_and_purpose",
        load(&root)?
            .files
            .iter()
            .filter(|i| {
                i.purpose == Purpose::AsrTemporary
                    && i.phase == Phase::Sealed
                    && i.sources.contains(&reference_key(&outside).unwrap())
            })
            .count()
            == 3,
    )?;
    let merged = chunks
        .iter()
        .map(|p| super::super::diarization::read_pcm16k_mono_wav(p))
        .collect::<Result<Vec<_>, _>>()?
        .concat();
    check(
        "split_coverage_preserves_exact_original_PCM",
        merged == vec![1; 96_000],
    )?;
    let import_usage = usage(&outside)?.ok_or_else(fail)?;
    let simultaneous_reader = usage(&outside)?;
    check(
        "shared_consumption_leases_allow_multiple_readers",
        simultaneous_reader.is_some(),
    )?;
    check(
        "external_source_usage_protects_its_generated_ASR_chunks",
        erase(&root, &[outside.to_string_lossy().into_owned()], &[]).is_err()
            && chunks.iter().all(|p| p.is_file()),
    )?;
    drop(import_usage);
    drop(simultaneous_reader);
    for p in &chunks {
        remove_temporary(p)?;
    }
    check(
        "normal_ASR_cleanup_retires_only_owned_chunks",
        chunks.iter().all(|p| !p.exists()) && outside.is_file() && primary.is_file(),
    )?;
    let long_input = output.join(format!("{}.wav", "长".repeat(235)));
    fs::write(&long_input, wav(&[2; 70_000])).map_err(|_| fail())?;
    let long_chunks = super::super::transcription::split_long_wav_into_chunks(&long_input, 1)?;
    check(
        "long_import_filename_does_not_expand_temporary_names",
        long_chunks.len() == 3
            && long_chunks
                .iter()
                .all(|p| p.file_name().unwrap().to_string_lossy().len() < 100),
    )?;
    // These unfinished chunks will be erased through their exact external
    // source reference. The imported source itself must remain untouched.
    let import_delete = erase(&root, &[long_input.to_string_lossy().into_owned()], &[])?;
    check(
        "explicit_import_cleanup_deletes_only_generated_chunks",
        import_delete.deleted == 3
            && long_chunks.iter().all(|p| !p.exists())
            && long_input.is_file(),
    )?;
    let live = root.join("live-prefix.wav");
    let live_raw = live.with_extension("cop1");
    let pcm = (0..40 * 16_000)
        .flat_map(|i| (i as i16).to_le_bytes())
        .collect::<Vec<_>>();
    put(&live, &live_raw, Purpose::LivePrefix, b"controlled-prefix")?;
    put(&live, &live, Purpose::Recording, &wav(&pcm))?;
    let window = super::super::ble_bridge::board_live_consumer_window(&live, 40_000)?;
    check(
        "live_window_uses_exact_last_30_seconds_of_native_PCM",
        super::super::diarization::read_pcm16k_mono_wav(&window)? == pcm[pcm.len() - 30 * 32_000..],
    )?;
    check(
        "live_window_has_recorded_provenance",
        load(&root)?
            .files
            .iter()
            .any(|i| i.purpose == Purpose::LiveWindow && i.phase == Phase::Sealed),
    )?;
    check(
        "short_live_window_reuses_original_without_extra_file",
        super::super::ble_bridge::board_live_consumer_window(&live, 30_000)? == live,
    )?;
    attach_group(&live, &primary)?;
    check(
        "prefix_group_including_raw_and_window_links_to_final",
        load(&root)?
            .files
            .iter()
            .filter(|i| matches!(i.purpose, Purpose::LivePrefix | Purpose::LiveWindow))
            .all(|i| i.sources.contains(&reference_key(&primary).unwrap())),
    )?;
    let backend = FixtureCompanionBackend::new();
    let seeded = snapshot(vec![session("first", &primary)], "first");
    *backend.snapshot.lock().map_err(|_| fail())? = seeded.clone();
    let held = usage(&live)?.ok_or_else(fail)?;
    check(
        "active_audio_usage_blocks_entire_cleanup_preflight",
        backend
            .apply_control(request(Action::PrivacyEraseAudio, Some("first")))
            .is_err()
            && primary.is_file()
            && raw.is_file()
            && window.is_file(),
    )?;
    drop(held);
    let intent = root.join(MANIFEST);
    let before = fs::read(&intent).map_err(|_| fail())?;
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        let held = OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(&intent)
            .map_err(|_| fail())?;
        let new_file = root.join("not-published.wav");
        let mut ran = false;
        check(
            "occupied_manifest_stops_writer_before_payload_creation",
            generated(&new_file, &new_file, Purpose::Recording, || {
                ran = true;
                fs::write(&new_file, b"new").map_err(|_| fail())
            })
            .is_err()
                && !ran
                && !new_file.exists(),
        )?;
        check(
            "occupied_manifest_stops_deletion_before_first_file",
            backend
                .apply_control(request(Action::PrivacyEraseAudio, Some("first")))
                .is_err()
                && primary.is_file()
                && raw.is_file()
                && fs::read(&intent).ok().as_ref() == Some(&before),
        )?;
        drop(held);
        let held = OpenOptions::new()
            .read(true)
            .share_mode(1 | 2)
            .open(&raw)
            .map_err(|_| fail())?;
        check(
            "occupied_payload_reports_failure_and_retains_session",
            backend
                .apply_control(request(Action::PrivacyEraseAudio, Some("first")))
                .is_err()
                && backend.snapshot()?.host.sessions[0].audio_path
                    == seeded.host.sessions[0].audio_path
                && raw.is_file(),
        )?;
        drop(held);
    }
    let erased = backend.apply_control(request(Action::PrivacyEraseAudio, Some("first")))?;
    check(
        "retry_removes_raw_live_prefix_window_cursor_and_primary",
        !primary.exists()
            && !raw.exists()
            && !live.exists()
            && !live_raw.exists()
            && !window.exists()
            && !cursor.exists(),
    )?;
    check(
        "successful_delete_commits_audio_retention_and_index",
        !erased.host.sessions[0].audio_stored
            && !erased.host.sessions[0].retention.audio_cached
            && erased.host.sessions[0].audio_path.is_none(),
    )?;
    check(
        "delete_preserves_unknown_imports_and_exports",
        unknown.is_file()
            && external.is_file()
            && outside.is_file()
            && long_input.is_file()
            && bad.is_file(),
    )?;
    check(
        "deletion_retries_are_idempotent",
        erase(&root, &[primary.to_string_lossy().into_owned()], &[])?.deleted == 0,
    )?;
    let first = root.join("owner-a.wav");
    let second = root.join("owner-b.wav");
    let shared = root.join("shared-prefix.cop1");
    put(&first, &first, Purpose::Recording, &wav(&[0; 3200]))?;
    put(&second, &second, Purpose::Recording, &wav(&[1; 3200]))?;
    put(&first, &shared, Purpose::LivePrefix, b"shared")?;
    attach_group(&shared, &second)?;
    *backend.snapshot.lock().map_err(|_| fail())? =
        snapshot(vec![session("a", &first), session("b", &second)], "a");
    let a = backend.apply_control(request(Action::PrivacyDeleteSession, Some("a")))?;
    check(
        "selected_delete_preserves_other_owner_shared_artifact",
        !first.exists() && shared.is_file() && second.is_file() && a.host.sessions.len() == 1,
    )?;
    *backend.snapshot.lock().map_err(|_| fail())? = snapshot(vec![session("b", &second)], "b");
    backend.apply_control(request(Action::PrivacyDeleteSession, Some("b")))?;
    check(
        "last_owner_delete_consumes_shared_artifact",
        !shared.exists() && !second.exists() && backend.snapshot()?.host.sessions.is_empty(),
    )?;
    let corrupt = root.join("guarded.wav");
    put(&corrupt, &corrupt, Purpose::Recording, &wav(&[0; 3200]))?;
    let safe = fs::read(&intent).map_err(|_| fail())?;
    let bytes = fs::read(&corrupt).map_err(|_| fail())?;
    *backend.snapshot.lock().map_err(|_| fail())? =
        snapshot(vec![session("guarded", &corrupt)], "guarded");
    fs::write(&intent, b"{broken").map_err(|_| fail())?;
    check(
        "damaged_manifest_fails_closed_without_deleting_audio",
        backend
            .apply_control(request(Action::PrivacyEraseAudio, Some("guarded")))
            .is_err()
            && fs::read(&corrupt).ok().as_ref() == Some(&bytes),
    )?;
    fs::write(&intent, &safe).map_err(|_| fail())?;
    let mut malicious = load(&root)?;
    malicious.files[0].file = "../external-export.wav".into();
    save(&root, &malicious)?;
    check(
        "manifest_traversal_is_rejected_and_external_file_retained",
        backend
            .apply_control(request(Action::PrivacyEraseAudio, Some("guarded")))
            .is_err()
            && external.is_file()
            && corrupt.is_file(),
    )?;
    fs::write(&intent, &safe).map_err(|_| fail())?;
    fs::write(&corrupt, b"replaced-by-user").map_err(|_| fail())?;
    check(
        "changed_payload_is_not_deleted_as_original",
        backend
            .apply_control(request(Action::PrivacyEraseAudio, Some("guarded")))
            .is_err()
            && fs::read(&corrupt).ok().as_deref() == Some(b"replaced-by-user"),
    )?;
    fs::write(&corrupt, &bytes).map_err(|_| fail())?;
    let mut interrupted = load(&root)?;
    for i in &mut interrupted.files {
        if i.file == "guarded.wav" {
            i.phase = Phase::Deleting;
        }
    }
    save(&root, &interrupted)?;
    fs::remove_file(&corrupt).map_err(|_| fail())?;
    let recovered = backend.apply_control(request(Action::PrivacyEraseAudio, Some("guarded")))?;
    check(
        "persisted_delete_intent_recovers_with_primary_already_gone",
        !recovered.host.sessions[0].audio_stored
            && load(&root)?
                .files
                .iter()
                .any(|i| i.file == "guarded.wav" && i.phase == Phase::Gone),
    )?;
    let partial = root.join("interrupted.wav");
    let failed: Result<(), String> = generated(&partial, &partial, Purpose::Recording, || {
        fs::write(&partial, b"partial-owned").map_err(|_| fail())?;
        Err("controlled writer failure".into())
    });
    check(
        "writer_error_preserves_exact_interrupted_identity",
        failed.is_err()
            && load(&root)?.files.iter().any(|i| {
                i.file == "interrupted.wav"
                    && i.phase == Phase::Interrupted
                    && i.identity == fingerprint(&partial).unwrap()
            }),
    )?;
    erase(&root, &[partial.to_string_lossy().into_owned()], &[])?;
    check(
        "interrupted_writer_payload_can_be_explicitly_deleted",
        !partial.exists(),
    )?;
    let host = super::super::host_recording::HostRecordingManager::new();
    let _host_env = Environment::set(&[(
        "COMPANION_TYPE_HOST_RECORDING_MODE",
        std::ffi::OsStr::new("synthetic"),
    )]);
    let started = host.start("../../untrusted-session-id", "controlled")?;
    check(
        "host_filename_cannot_escape_root_through_session_ID",
        started.path.parent() == Some(root.as_path())
            && !started
                .path
                .to_string_lossy()
                .contains("untrusted-session-id"),
    )?;
    check(
        "host_recording_lease_prevents_foreign_cleanup",
        erase(&root, &[started.path.to_string_lossy().into_owned()], &[]).is_err(),
    )?;
    let stopped = host
        .stop(Some("../../untrusted-session-id"))?
        .ok_or_else(fail)?;
    check(
        "host_stop_seals_recording_without_using_real_microphone",
        stopped.bytes > 44
            && stopped.mode == "synthetic"
            && load(&root)?
                .files
                .iter()
                .any(|i| root.join(&i.file) == stopped.path && i.phase == Phase::Sealed),
    )?;
    erase(&root, &[stopped.path.to_string_lossy().into_owned()], &[])?;
    check(
        "completed_host_recording_can_be_explicitly_deleted",
        !stopped.path.exists(),
    )?;
    let pending = root.join("unsealed-process-interruption.wav");
    let mut pending_data = load(&root)?;
    pending_data.files.push(Artifact {
        file: "unsealed-process-interruption.wav".into(),
        sources: BTreeSet::from([reference_key(&pending)?]),
        purpose: Purpose::Recording,
        phase: Phase::Prepared,
        identity: None,
    });
    save(&root, &pending_data)?;
    fs::write(&pending, b"unsealed-controlled").map_err(|_| fail())?;
    check(
        "unsealed_crash_file_is_preserved_without_guessing_identity",
        erase(&root, &[pending.to_string_lossy().into_owned()], &[]).is_err() && pending.is_file(),
    )?;
    // Restore only this controlled fixture's known identity; production has
    // no implicit repair/adoption of an unsealed crash payload.
    let mut restored = load(&root)?;
    let item = restored
        .files
        .iter_mut()
        .find(|i| i.file == "unsealed-process-interruption.wav")
        .ok_or_else(fail)?;
    item.phase = Phase::Interrupted;
    item.identity = fingerprint(&pending)?;
    save(&root, &restored)?;
    erase(&root, &[pending.to_string_lossy().into_owned()], &[])?;
    let bridge = root.join("retired-bridge.wav");
    let child = root.join("live-descendant.wav");
    put(&bridge, &child, Purpose::AsrTemporary, b"live-descendant")?;
    let mut history = load(&root)?;
    history.files.push(Artifact {
        file: "retired-bridge.wav".into(),
        sources: BTreeSet::from([reference_key(&bridge)?]),
        purpose: Purpose::Recording,
        phase: Phase::Gone,
        identity: None,
    });
    for n in 0..600 {
        let name = format!("retired-{n}.wav");
        history.files.push(Artifact {
            sources: BTreeSet::from([reference_key(&root.join(&name))?]),
            file: name,
            purpose: Purpose::AsrTemporary,
            phase: Phase::Gone,
            identity: None,
        });
    }
    save(&root, &history)?;
    let compacted = load(&root)?;
    check(
        "retired_scratch_history_is_bounded",
        compacted
            .files
            .iter()
            .filter(|i| i.phase == Phase::Gone)
            .count()
            == 257,
    )?;
    check(
        "compaction_retains_bridge_to_live_descendant",
        compacted
            .files
            .iter()
            .any(|i| i.file == "retired-bridge.wav")
            && compacted
                .files
                .iter()
                .any(|i| i.file == "live-descendant.wav"),
    )?;
    erase(&root, &[bridge.to_string_lossy().into_owned()], &[])?;
    check(
        "compacted_manifest_still_deletes_exact_live_descendant",
        !child.exists(),
    )?;
    let all_a = root.join("delete-all-a.wav");
    let all_b = root.join("delete-all-b.wav");
    let all_raw = all_a.with_extension("opus");
    put(&all_a, &all_a, Purpose::Recording, &wav(&[0; 3200]))?;
    put(&all_b, &all_b, Purpose::Recording, &wav(&[1; 3200]))?;
    put(&all_a, &all_raw, Purpose::CompressedOriginal, b"all-raw")?;
    *backend.snapshot.lock().map_err(|_| fail())? = snapshot(
        vec![session("all-a", &all_a), session("all-b", &all_b)],
        "all-a",
    );
    backend.apply_control(request(Action::PrivacyEraseAll, None))?;
    check(
        "erase_all_consumes_generated_raw_and_recordings",
        !all_a.exists()
            && !all_b.exists()
            && !all_raw.exists()
            && backend.snapshot()?.host.sessions.is_empty(),
    )?;
    let main: Value =
        serde_json::from_slice(&fs::read(&index).map_err(|_| fail())?).map_err(|_| fail())?;
    let backup: Value = serde_json::from_slice(
        &fs::read(index.with_file_name("sessions.json.bak")).map_err(|_| fail())?,
    )
    .map_err(|_| fail())?;
    check(
        "erase_all_commits_empty_primary_and_recovery_indexes",
        main.as_array().is_some_and(Vec::is_empty) && backup.as_array().is_some_and(Vec::is_empty),
    )?;
    let report = json!({"schema":"companion.type.audio_artifacts_probe.v1","result":"PASS_LOCAL_AUDIO_ARTIFACTS_ONLY","checks":checks,
        "realUserProfileAccess":false,"deviceAccess":false,"networkAccess":false,"realMicrophoneAccess":false,
        "nativeGui":"NOT_RUN","trueAsrAcceptance":"NOT_RUN","hardwareAcceptance":"NOT_RUN","fullChainAcceptance":"NOT_RUN","physicalPowerLossAcceptance":"NOT_RUN",
        "crossProcessScenario":"NOT_RUN","scope":"New managed recordings, COP1/Opus, native live windows, decode and ASR chunks; explicit reference graph, OS lease exclusion, fingerprint validation and deletion-intent retry",
        "allArtifactLedgerComplete":false,"asrCachePrivacyDeletionComplete":false,"legacyUntrackedCleanup":"NOT_IMPLEMENTED"});
    fs::write(
        output.join("result.json"),
        serde_json::to_vec_pretty(&report).map_err(|_| fail())?,
    )
    .map_err(|_| fail())?;
    Ok(report)
}
#[cfg(all(test, windows))]
mod tests {
    use super::*;

    #[test]
    fn privacy_retry_preserves_same_path_replacement_after_owned_file_is_gone() {
        let root=std::env::temp_dir().join(format!("companion-privacy-gone-retry-{}",uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap();
        let state=root.join("sessions.json");
        let _env=Environment::set(&[("COMPANION_TYPE_RECORDING_DIR",root.as_os_str()),("COMPANION_TYPE_STATE_PATH",state.as_os_str())]);
        let source=root.join("owned.wav");
        put(&source,&source,Purpose::Recording,b"original owned audio").unwrap();
        let original=snapshot(vec![session("original",&source)],"original");
        // The previous attempt completed generated-file deletion, but the
        // library checkpoint/legacy cleanup still needs an ordinary retry.
        erase(&root,&[source.to_string_lossy().into_owned()],&[]).unwrap();
        assert!(!source.exists());
        fs::write(&source,b"different user replacement").unwrap();
        let before=fs::read(&source).unwrap();
        let backend=FixtureCompanionBackend::new();
        *backend.snapshot.lock().unwrap()=original;
        let result=backend.apply_control(request(Action::PrivacyEraseAudio,Some("original"))).unwrap();
        assert_eq!(fs::read(&source).ok(),Some(before),"legacy fallback must not delete a new file at a completed managed path");
        assert!(!result.host.sessions[0].audio_stored);
        assert!(result.last_control.unwrap().message.contains("1 skipped"));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn privacy_legacy_copy_still_cleans_after_generated_primary_already_deleted() {
        let root=std::env::temp_dir().join(format!("companion-privacy-legacy-handoff-{}",uuid::Uuid::new_v4()));
        let old=root.join("legacy");let current=root.join("current");
        fs::create_dir_all(&old).unwrap();fs::create_dir_all(&current).unwrap();
        let state=root.join("sessions.json");
        let _env=Environment::set(&[("COMPANION_TYPE_RECORDING_DIR",current.as_os_str()),("COMPANION_TYPE_STATE_PATH",state.as_os_str())]);
        let original=old.join("old.wav");
        fs::write(&original,wav(&[0,0,1,0])).unwrap();
        let mut seeded=session("legacy",&original);
        seeded.source="hostMicrophone".into();
        seeded.audio_bytes=fs::metadata(&original).unwrap().len();
        seeded.chunks=vec![crate::companion_v1::CompanionV1AudioChunk {
            id:"legacy-sealed".into(),path:Some(original.to_string_lossy().into_owned()),
            started_at:None,stopped_at:None,duration_ms:1,bytes:seeded.audio_bytes,status:"sealed".into(),
        }];
        let (migrated,_)=super::super::super::audio_storage::migrate_legacy_sessions(&[seeded],&current,&old).unwrap();
        let source=PathBuf::from(migrated[0].audio_path.as_ref().unwrap());
        assert_eq!(source.parent().unwrap(),current.canonicalize().unwrap());
        // Adopt only this exact migrated primary in the test's existing ledger.
        let identity=fingerprint(&source).unwrap().unwrap();
        let mut data=load(&current).unwrap();
        data.files.push(Artifact{file:source.file_name().unwrap().to_string_lossy().into_owned(),sources:BTreeSet::from([reference_key(&source).unwrap()]),purpose:Purpose::Recording,phase:Phase::Sealed,identity:Some(identity)});
        save(&current,&data).unwrap();
        erase(&current,&[source.to_string_lossy().into_owned()],&[]).unwrap();
        assert!(!source.exists()&&original.exists());
        fs::write(&source,b"new unrelated current file").unwrap();
        let manager=super::super::super::privacy::PrivacyManager::for_handoff_test(current.clone(),old.clone());
        let report=manager.erase_selected_audio(&snapshot(migrated,"legacy"));
        assert_eq!(report.failed_files,0);
        assert!(!original.exists(),"the exact fingerprinted legacy copy still must be cleaned");
        assert_eq!(fs::read(&source).ok().as_deref(),Some(b"new unrelated current file".as_slice()));
        assert_eq!(report.skipped_files,1);
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn native_audio_artifacts_guard_generated_files_ownership_and_cleanup_retry() {
        let output =
            std::env::temp_dir().join(format!("companion-artifact-probe-{}", uuid::Uuid::new_v4()));
        let report = super::verify(&output).unwrap();
        assert!(report["checks"].as_array().unwrap().len() >= 35);
        assert!(super::verify(&output).unwrap_err().contains("fresh"));
        // The native probe keeps its isolated evidence, like the existing
        // deletion/settings probes. It never touches other Temp directories.
    }
}
