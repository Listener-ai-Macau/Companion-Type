use std::collections::HashSet;
use std::path::PathBuf;

use crate::companion_v1::{
    CompanionV1ControlAction, CompanionV1ControlRequest, CompanionV1Snapshot,
};

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
        let retained_paths: Vec<String> = snapshot.host.sessions.iter().filter(|s| &s.id != selected_id)
            .flat_map(|s| s.audio_path.iter().chain(s.chunks.iter().filter_map(|c| c.path.as_ref()))).cloned().collect();
        let sources: Vec<String> = snapshot.host.sessions.iter().filter(|s| &s.id == selected_id)
            .flat_map(|s| s.audio_path.iter().chain(s.chunks.iter().filter_map(|c| c.path.as_ref()))).cloned().collect();
        if !self.erase_cache(snapshot, false, &sources, &retained_paths, &mut report) { return report; }
        if !self.erase_generated(&sources, &retained_paths, &mut seen, &mut report) { return report; }
        let protected: HashSet<_> = snapshot
            .host
            .sessions
            .iter()
            .filter(|session| &session.id != selected_id)
            .flat_map(|session| {
                session.audio_path.iter().map(String::as_str).chain(
                    session
                        .chunks
                        .iter()
                        .filter_map(|chunk| chunk.path.as_deref()),
                )
            })
            .map(path_key)
            .collect();
        for session in &snapshot.host.sessions {
            if selected_id != &session.id {
                continue;
            }
            self.erase_session_audio_once(
                session.audio_path.as_deref(),
                &mut seen,
                &protected,
                &mut report,
            );
            for chunk in &session.chunks {
                self.erase_session_audio_once(
                    chunk.path.as_deref(),
                    &mut seen,
                    &protected,
                    &mut report,
                );
            }
        }
        report
    }

    pub fn erase_all_audio(&self, snapshot: &CompanionV1Snapshot) -> PrivacyEraseReport {
        let mut report = PrivacyEraseReport::default();
        let mut seen = HashSet::new();
        let protected = HashSet::new();
        let sources: Vec<String> = snapshot.host.sessions.iter()
            .flat_map(|s| s.audio_path.iter().chain(s.chunks.iter().filter_map(|c| c.path.as_ref()))).cloned().collect();
        if !self.erase_cache(snapshot, true, &sources, &[], &mut report) { return report; }
        if !self.erase_generated(&sources, &[], &mut seen, &mut report) { return report; }
        for session in &snapshot.host.sessions {
            self.erase_session_audio_once(
                session.audio_path.as_deref(),
                &mut seen,
                &protected,
                &mut report,
            );
            for chunk in &session.chunks {
                self.erase_session_audio_once(
                    chunk.path.as_deref(),
                    &mut seen,
                    &protected,
                    &mut report,
                );
            }
        }
        report
    }

    pub fn erase_selected_transcript(&self, snapshot: &CompanionV1Snapshot) -> PrivacyEraseReport {
        let mut report = PrivacyEraseReport::default();
        let Some(id) = snapshot.host.selected_session_id.as_ref().filter(|id| snapshot.host.sessions.iter().any(|s| &s.id == *id)) else { report.failed_files = 1; return report; };
        let paths = |selected: bool| snapshot.host.sessions.iter().filter(|s| (&s.id == id) == selected)
            .flat_map(|s| s.audio_path.iter().chain(s.chunks.iter().filter_map(|c| c.path.as_ref()))).cloned().collect::<Vec<_>>();
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

    fn erase_generated(&self, sources: &[String], retained: &[String], seen: &mut HashSet<String>, report: &mut PrivacyEraseReport) -> bool {
        let Some(root) = self.recording_root.as_ref() else { report.failed_files += 1; return false; };
        match super::audio_artifacts::erase(root, sources, retained) {
            Ok(generated) => {
                report.deleted_files += generated.deleted; report.shared_files += generated.shared;
                // A shared generated primary must also be protected from the
                // conservative legacy/index-only fallback below.
                seen.extend(generated.retained_paths.iter().map(|p| path_key(&p.to_string_lossy())));
                true
            }, Err(_) => { report.failed_files += 1; false },
        }
    }

    fn erase_session_audio_once(
        &self,
        path: Option<&str>,
        seen: &mut HashSet<String>,
        protected: &HashSet<String>,
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
        self.erase_session_audio(Some(path), protected, report);
    }

    fn erase_session_audio(
        &self,
        path: Option<&str>,
        protected: &HashSet<String>,
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
            if protected.contains(&path_key(&target.to_string_lossy())) {
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
        CompanionV1ControlRequest,
    };

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
            CompanionV1ControlRequest {
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
