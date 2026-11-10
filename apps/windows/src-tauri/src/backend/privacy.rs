use std::collections::HashSet;
use std::path::PathBuf;

use crate::companion_v1::{
    CompanionV1ControlAction, CompanionV1ControlRequest, CompanionV1HostSession, CompanionV1Snapshot,
};

fn session_audio_paths(session: &CompanionV1HostSession) -> impl Iterator<Item = &str> {
    session.audio_path.iter().map(String::as_str)
        .chain(session.chunks.iter().filter_map(|chunk| chunk.path.as_deref()))
        .chain(session.meeting_tracks.iter().flat_map(|tracks|
            tracks.microphone.iter().chain(&tracks.system).map(|part| part.path.as_str())))
}

/// Include registered originals that were not yet written into the session
/// index when capture stopped unexpectedly. Only the selected recording is
/// checkpointed for deletion; retained sessions are used solely to protect it.
fn cleanup_audio_paths<'a>(sessions: impl Iterator<Item = &'a CompanionV1HostSession>,
    checkpoint: bool,documents:bool) -> Result<Vec<String>, String> {
    let mut paths = Vec::new();
    for session in sessions {
        if documents&&!session.document_context.is_empty(){paths.push(super::document_context::owner_path(session,&super::audio_storage::recording_root()?).to_string_lossy().into_owned());}
        if checkpoint && session.source=="importedAudio" && session.audio_stored {
            let original=super::import_audio::original_chunk(session)?;
            if let Some(_path)=original.path.as_deref().filter(|path|std::path::Path::new(path).exists()) {
                super::import_audio::verify_original(session,&super::audio_storage::recording_root()?)?;
            }
        }
        paths.extend(session_audio_paths(session).map(str::to_owned));
        let Some(tracks) = session.meeting_tracks.as_ref() else { continue; };
        if session.source != "hostMeeting" || !matches!(tracks.state.as_str(), "recording" | "needsReview") { continue; }
        let (mic, system) = super::audio_artifacts::meeting_capture_parts_for_cleanup(PathBuf::from(&tracks.root).as_path())?;
        for part in mic.into_iter().chain(system) {
            if checkpoint && !part.sealed {
                super::audio_artifacts::checkpoint_interrupted_meeting_for_cleanup(&part.path)?;
            }
            paths.push(part.path.to_string_lossy().into_owned());
        }
    }
    Ok(paths)
}

/// Validate before any file or device deletion. The UI confirmation carries
/// the selected ID; a stale or missing ID must never broaden the operation.
pub(super) fn validate_control(
    snapshot: &CompanionV1Snapshot,
    request: &CompanionV1ControlRequest,
    live_active: bool,
) -> Result<(), String> {
    if !matches!(
        request.action,
        CompanionV1ControlAction::PrivacyEraseAudio
            | CompanionV1ControlAction::PrivacyEraseTranscript
            | CompanionV1ControlAction::PrivacyDeleteSession
            | CompanionV1ControlAction::PrivacyEraseAll
    ) {
        return Ok(());
    }
    super::library_lifecycle::validate_privacy(snapshot,request)?;
    if snapshot.device.recording || super::oobe_blocked_by_active_recording(snapshot, live_active) {
        return Err("正在录音或在线转写，不能删除资料；请先停止并完成当前会议".into());
    }
    if request.action == CompanionV1ControlAction::PrivacyEraseAll {
        return Ok(());
    }
    let id = request
        .session_id
        .as_deref()
        .filter(|id| !id.trim().is_empty())
        .ok_or("privacy action requires an explicit sessionId")?;
    if snapshot.host.selected_session_id.as_deref() != Some(id)
        || !snapshot
            .host
            .sessions
            .iter()
            .any(|session| session.id == id)
    {
        return Err(
            "privacy target is no longer the selected session; refresh and confirm again".into(),
        );
    }
    Ok(())
}

fn path_key(path: &str) -> String {
    let path = PathBuf::from(path);
    let resolved = path.canonicalize().unwrap_or_else(|_| {
        path.parent()
            .and_then(|parent| parent.canonicalize().ok())
            .zip(path.file_name())
            .map(|(parent, name)| parent.join(name))
            .unwrap_or(path.clone())
    });
    let text = resolved.to_string_lossy().replace('/', "\\");
    let text = text.strip_prefix("\\\\?\\").unwrap_or(&text);
    if cfg!(windows) {
        text.to_ascii_lowercase()
    } else {
        text.into()
    }
}

#[derive(Clone, Debug, Default)]
pub struct PrivacyEraseReport {
    pub deleted_files: usize,
    pub skipped_files: usize,
    /// Still referenced by a different retained meeting. Keep that file and
    /// report the distinction rather than silently removing another's audio.
    pub shared_files: usize,
    /// Owned audio or its migration ledger could not be removed. Callers must
    /// keep the session pointer and retry instead of committing a false erase.
    pub failed_files: usize,
    /// Cache-shaped files with an unprovable legacy identity were preserved.
    pub unverified_cache_files: usize,
}

/// Publish structured counts, never infer cleanup success from the legacy message.
pub(super) fn cleanup_summary(action: CompanionV1ControlAction, report: &PrivacyEraseReport,
    completed_at: String) -> Option<crate::companion_v1::CompanionV1PrivacyCleanup> {
    if report.failed_files != 0 { return None; }
    let operation = match action {
        CompanionV1ControlAction::PrivacyEraseAudio => "audio",
        CompanionV1ControlAction::PrivacyEraseTranscript => "text",
        CompanionV1ControlAction::PrivacyDeleteSession => "session",
        CompanionV1ControlAction::PrivacyEraseAll => "allMeetings",
        _ => return None,
    };
    Some(crate::companion_v1::CompanionV1PrivacyCleanup {
        operation, completed_at, deleted_files: report.deleted_files,
        skipped_files: report.skipped_files, shared_files: report.shared_files,
        unverified_cache_files: report.unverified_cache_files, index_saved: false,
    })
}

#[cfg(test)]
mod summary_tests {
    use super::*;
    #[test]
    fn structured_cleanup_preserves_retained_counts_and_requires_actual_privacy_action() {
        let r = PrivacyEraseReport { deleted_files: 2, skipped_files: 3,
            shared_files: 4, failed_files: 0, unverified_cache_files: 5 };
        let s = cleanup_summary(CompanionV1ControlAction::PrivacyEraseAll, &r, "time".into()).unwrap();
        assert_eq!((s.deleted_files,s.skipped_files,s.shared_files,s.unverified_cache_files),(2,3,4,5));
        assert_eq!(s.operation,"allMeetings");assert!(!s.index_saved);
        assert!(cleanup_summary(CompanionV1ControlAction::DeviceDisconnect,&r,"time".into()).is_none());
        let failed=PrivacyEraseReport { failed_files: 1, ..r };
        assert!(cleanup_summary(CompanionV1ControlAction::PrivacyEraseAll,&failed,"time".into()).is_none());
    }
}

#[derive(Clone, Debug)]
pub struct PrivacyManager {
    recording_root: Option<PathBuf>,
    // Only the controlled private probe supplies this; production uses the
    // existing migration root. No IPC or product setting changes its value.
    legacy_root_override: Option<PathBuf>,
    cache_root: Option<PathBuf>,
    minutes_cache_root: Option<PathBuf>,
}

impl PrivacyManager {
    #[cfg(test)]
    pub(in crate::backend) fn for_handoff_test(root: PathBuf, legacy: PathBuf) -> Self {
        Self { recording_root: Some(root), legacy_root_override: Some(legacy), cache_root: None, minutes_cache_root: None }
    }

    #[cfg(test)]
    pub(in crate::backend) fn with_minutes_cache(root: PathBuf) -> Self {
        Self { recording_root: None, legacy_root_override: None, cache_root: None, minutes_cache_root: Some(root) }
    }

    pub fn new() -> Self {
        Self {
            recording_root: super::audio_storage::recording_root().ok(),
            legacy_root_override: None,
            cache_root: Some(super::transcription::asr_chunk_cache_root()),
            minutes_cache_root: super::minutes::long_meeting::cache_root(),
        }
    }

    pub fn erase_selected_audio(&self, snapshot: &CompanionV1Snapshot) -> PrivacyEraseReport {
        self.erase_selected(snapshot,false)
    }
    pub fn erase_selected_recording(&self,snapshot:&CompanionV1Snapshot)->PrivacyEraseReport{
        self.erase_selected(snapshot,true)
    }
    fn erase_selected(&self,snapshot:&CompanionV1Snapshot,documents:bool)->PrivacyEraseReport{
        let mut report = PrivacyEraseReport::default();
        let mut seen = HashSet::new();
        let Some(selected_id) = snapshot.host.selected_session_id.as_ref().filter(|id| {
            snapshot
                .host
                .sessions
                .iter()
                .any(|session| &session.id == *id)
        }) else {
            report.failed_files = 1;
            return report;
        };
        let retained_paths = match cleanup_audio_paths(snapshot.host.sessions.iter().filter(|s| &s.id != selected_id), false,true) {
            Ok(paths) => paths, Err(_) => { report.failed_files += 1; return report; }
        };
        let sources = match cleanup_audio_paths(snapshot.host.sessions.iter().filter(|s| &s.id == selected_id), true,documents) {
            Ok(paths) => paths, Err(_) => { report.failed_files += 1; return report; }
        };
        if !self.erase_cache(snapshot, false, &sources, &retained_paths, &mut report) { return report; }
        let Some(handled) = self.erase_generated(&sources, &retained_paths, &mut seen, &mut report) else { return report; };
        let protected: HashSet<_> = retained_paths.iter().map(|path| path_key(path)).collect();
        for path in &sources {
            self.erase_session_audio_once(
                Some(path),
                &mut seen,
                &protected,
                &handled,
                &mut report,
            );
        }
        report
    }

    pub fn erase_all_audio(&self, snapshot: &CompanionV1Snapshot) -> PrivacyEraseReport {
        let mut report = PrivacyEraseReport::default();
        let mut seen = HashSet::new();
        let protected = HashSet::new();
        let sources = match cleanup_audio_paths(snapshot.host.sessions.iter(), true,true) {
            Ok(paths) => paths, Err(_) => { report.failed_files += 1; return report; }
        };
        if !self.erase_cache(snapshot, true, &sources, &[], &mut report) { return report; }
        let Some(handled) = self.erase_generated(&sources, &[], &mut seen, &mut report) else { return report; };
        for path in &sources {
            self.erase_session_audio_once(
                Some(path),
                &mut seen,
                &protected,
                &handled,
                &mut report,
            );
        }
        report
    }

    pub fn erase_selected_transcript(&self, snapshot: &CompanionV1Snapshot) -> PrivacyEraseReport {
        let mut report = PrivacyEraseReport::default();
        let Some(id) = snapshot.host.selected_session_id.as_ref().filter(|id| snapshot.host.sessions.iter().any(|s| &s.id == *id)) else { report.failed_files = 1; return report; };
        let paths = |selected: bool| snapshot.host.sessions.iter().filter(|s| (&s.id == id) == selected)
            .flat_map(session_audio_paths).map(str::to_owned).collect::<Vec<_>>();
        self.erase_cache(snapshot, false, &paths(true), &paths(false), &mut report);
        report
    }

    fn erase_cache(&self, snapshot: &CompanionV1Snapshot, all: bool, sources: &[String], retained: &[String], report: &mut PrivacyEraseReport) -> bool {
        let sessions: Vec<String> = snapshot.host.sessions.iter().filter(|s| all || snapshot.host.selected_session_id.as_ref() == Some(&s.id)).map(|s| s.id.clone()).collect();
        if let Some(root) = self.minutes_cache_root.as_ref() {
            match super::minutes::long_meeting::erase(root, &sessions, all) {
                Ok((deleted, unknown)) => { report.deleted_files += deleted; report.unverified_cache_files += unknown; },
                Err(_) => { report.failed_files += 1; return false; },
            }
        }
        let Some(root) = self.cache_root.as_ref() else { return true; };
        if !root.exists() { return true; }
        let protected = snapshot.host.sessions.iter().filter(|s| !all && snapshot.host.selected_session_id.as_ref() != Some(&s.id)).map(|s| s.id.clone()).collect();
        let guard = super::audio_artifacts::exclusive_sources(sources);
        if guard.is_err() { report.failed_files += 1; return false; }
        let session_set = sessions.into_iter().collect();
        match super::transcription::erase_cache(root, &session_set, sources, &protected, retained, all) {
            Ok(cache) => { report.deleted_files += cache.deleted; report.shared_files += cache.shared; report.unverified_cache_files += cache.unknown; true },
            Err(_) => { report.failed_files += 1; false },
        }
    }

    fn erase_generated(&self, sources: &[String], retained: &[String], seen: &mut HashSet<String>, report: &mut PrivacyEraseReport) -> Option<HashSet<String>> {
        let Some(root) = self.recording_root.as_ref() else { report.failed_files += 1; return None; };
        match super::audio_artifacts::erase(root, sources, retained) {
            Ok(generated) => {
                report.deleted_files += generated.deleted; report.shared_files += generated.shared;
                report.skipped_files += generated.unverified_empty;
                // A shared generated primary must also be protected from the
                // conservative legacy/index-only fallback below.
                seen.extend(generated.retained_paths.iter().map(|p| path_key(&p.to_string_lossy())));
                Some(generated.handled_paths.iter().map(|p| path_key(&p.to_string_lossy())).collect())
            }, Err(_) => { report.failed_files += 1; None },
        }
    }

    fn erase_session_audio_once(
        &self,
        path: Option<&str>,
        seen: &mut HashSet<String>,
        protected: &HashSet<String>,
        handled: &HashSet<String>,
        report: &mut PrivacyEraseReport,
    ) {
        let Some(path) = path else {
            return;
        };
        let key = path_key(path);
        if !seen.insert(key.clone()) {
            return;
        }
        if protected.contains(&key) {
            report.shared_files += 1;
            return;
        }
        self.erase_session_audio(Some(path), protected, handled, report);
    }

    fn erase_session_audio(
        &self,
        path: Option<&str>,
        protected: &HashSet<String>,
        handled: &HashSet<String>,
        report: &mut PrivacyEraseReport,
    ) {
        let Some(path) = path else {
            return;
        };
        let path = PathBuf::from(path);
        let Some(root) = self.recording_root.as_ref() else {
            report.failed_files += 1;
            return;
        };
        if !super::audio_storage::owned_recording_reference(&path, root) {
            report.skipped_files += 1;
            return;
        }
        match std::fs::metadata(&path) {
            Ok(_) => {}
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(_) => {
                report.failed_files += 1;
                return;
            }
        }
        let targets = match self.legacy_root_override.as_deref().map_or_else(
            || super::audio_storage::privacy_delete_targets(&path, root),
            |legacy| super::audio_storage::privacy_delete_targets_with_legacy(&path, root, legacy),
        ) {
            Ok(targets) => targets,
            Err(_) => {
                report.failed_files += 1;
                return;
            }
        };
        let current = targets.last().cloned();
        let mut complete = true;
        for target in targets {
            let target_key = path_key(&target.to_string_lossy());
            if handled.contains(&target_key) {
                // Generated cleanup has already handled this original. A new
                // file at its pathname is not the user's requested recording.
                // Keep legacy copies below eligible by their exact ledger SHA.
                if target.exists() { report.skipped_files += 1; }
                continue;
            }
            if protected.contains(&target_key) {
                report.shared_files += 1;
                continue;
            }
            match std::fs::remove_file(&target) {
                Ok(()) => report.deleted_files += 1,
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                Err(_) => {
                    report.failed_files += 1;
                    complete = false;
                    break;
                }
            }
        }
        if complete {
            if let Some(current) = current {
                if super::audio_storage::forget_deleted_migration(&current, root).is_err() {
                    report.failed_files += 1;
                }
            }
        }
    }
}

impl Default for PrivacyManager {
    fn default() -> Self {
        Self::new()
    }
}

mod probe;
pub(crate) use probe::verify as verify_privacy_delete;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{
        apply_fixture_control, fixture_snapshot, CompanionV1ControlAction,
        CompanionV1ControlRequest, CompanionV1MeetingTrackPart, CompanionV1MeetingTracks,
    };

    #[test]
    #[ignore = "changes recording-directory environment; run in isolation"]
    fn deleting_interrupted_meeting_finds_registered_parts_and_preserves_shared() {
        use std::io::Write;
        use super::super::audio_artifacts::{Purpose, WriteLease};
        use super::super::meeting_audio_tracks::TrackWriter;
        let root = std::env::temp_dir().join(format!("companion-interrupted-delete-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
        let legacy = root.join("legacy"); std::fs::create_dir_all(&legacy).unwrap();
        let anchor = root.join("meeting-owned");
        let mut writer = TrackWriter::create_flat(&root, "meeting-owned-mic", 10).unwrap();
        writer.append(&[1, 2, 3]).unwrap();
        let complete = writer.finish().unwrap()[0].path.clone();
        let partial = root.join("meeting-owned-system-00000000.wav");
        let lease = WriteLease::begin(&partial, &partial, Purpose::Recording).unwrap().unwrap();
        let mut file = std::fs::OpenOptions::new().write(true).create_new(true).open(&partial).unwrap();
        file.write_all(&denzic_host_audio_v1_core::wav::wav_header(0)).unwrap();
        file.write_all(&[4, 0, 5, 0]).unwrap(); file.sync_all().unwrap(); drop(file); drop(lease);
        let unknown = root.join("meeting-owned-mic-00000001.wav"); std::fs::write(&unknown, b"other").unwrap();
        let request: CompanionV1ControlRequest = serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
        let mut snapshot = apply_fixture_control(fixture_snapshot(), request).unwrap();
        let mut selected = snapshot.host.sessions.remove(0);
        selected.id = "selected-interrupted".into(); selected.source = "hostMeeting".into();
        selected.audio_path = None; selected.chunks.clear();
        selected.meeting_tracks = Some(CompanionV1MeetingTracks { root: anchor.to_string_lossy().into_owned(), state: "recording".into(),
            microphone: vec![], system: vec![], discontinuity: false, issue: None });
        let mut retained = selected.clone(); retained.id = "retained".into(); retained.source = "hostMicrophone".into();
        retained.meeting_tracks = None; retained.audio_path = Some(partial.to_string_lossy().into_owned());
        snapshot.host.selected_session_id = Some(selected.id.clone()); snapshot.host.sessions = vec![selected, retained];
        let manager = PrivacyManager::for_handoff_test(root.clone(), legacy);
        let report = manager.erase_selected_audio(&snapshot);
        assert_eq!(report.failed_files, 0); assert!(!complete.exists()); assert!(partial.exists()); assert!(unknown.exists());
        snapshot.host.sessions.pop();
        let retry = manager.erase_selected_audio(&snapshot);
        assert_eq!(retry.failed_files, 0); assert!(!partial.exists()); assert!(unknown.exists());
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn deleting_selected_meeting_tracks_preserves_shared_and_outside_files() {
        let root = std::env::temp_dir().join(format!("companion-tracks-privacy-{}", uuid::Uuid::new_v4()));
        let legacy = root.join("legacy"); std::fs::create_dir_all(&legacy).unwrap();
        let mic = root.join("meeting-mic-00000000.wav");
        let shared = root.join("meeting-system-00000000.wav");
        let outside = std::env::temp_dir().join(format!("companion-outside-{}.wav", uuid::Uuid::new_v4()));
        for path in [&mic, &shared, &outside] { std::fs::write(path, b"audio").unwrap(); }
        let request = serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
        let mut snapshot = apply_fixture_control(fixture_snapshot(), request).unwrap();
        let mut selected = snapshot.host.sessions.remove(0);
        selected.id = "selected-tracks".into(); selected.audio_path = None; selected.chunks.clear();
        let part = |path: &std::path::Path| CompanionV1MeetingTrackPart { path: path.to_string_lossy().into_owned(), first_sample: 0, samples: 1 };
        selected.meeting_tracks = Some(CompanionV1MeetingTracks { root: root.join("meeting").to_string_lossy().into_owned(), state: "captured".into(),
            microphone: vec![part(&mic), part(&outside)], system: vec![part(&shared)], discontinuity: false, issue: None });
        let mut retained = selected.clone(); retained.id = "other-meeting".into();
        retained.meeting_tracks.as_mut().unwrap().microphone.clear();
        snapshot.host.selected_session_id = Some(selected.id.clone());
        snapshot.host.sessions = vec![selected, retained];
        let report = PrivacyManager::for_handoff_test(root.clone(), legacy).erase_selected_audio(&snapshot);
        assert!(!mic.exists()); assert!(shared.exists()); assert!(outside.exists());
        assert!(report.shared_files > 0); assert!(report.skipped_files > 0);
        std::fs::remove_file(outside).unwrap(); std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn privacy_manager_deletes_only_owned_audio_cache() {
        let root = std::env::temp_dir().join("companion-type-privacy-test");
        let _ = std::fs::create_dir_all(&root);
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
        let owned = root.join("owned.wav");
        let outside = std::env::temp_dir().join("companion-type-privacy-outside.wav");
        std::fs::write(&owned, b"owned").unwrap();
        std::fs::write(&outside, b"outside").unwrap();

        let snapshot = apply_fixture_control(
            fixture_snapshot(),
            CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::DeviceSyncRecordings,
                context_note_revision: None, ble_name: None,
                session_id: Some("privacy-session".to_string()),
                prompt_id: None,
                title: Some("Privacy session".to_string()),
                transcript_text: None,
                meeting_mode: None,
                audio_path: Some(owned.to_string_lossy().to_string()),
                audio_bytes: Some(5),
                device_id: None,
                duration_ms: Some(1000),
            },
        )
        .unwrap();

        let report = PrivacyManager::new().erase_selected_audio(&snapshot);
        assert_eq!(report.deleted_files, 1);
        assert!(!owned.exists());
        assert!(outside.exists());
        let _ = std::fs::remove_file(outside);
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR");
    }
}
