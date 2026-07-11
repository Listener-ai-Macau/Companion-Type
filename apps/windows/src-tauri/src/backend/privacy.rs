use std::path::{Path, PathBuf};

use crate::companion_v1::CompanionV1Snapshot;

#[derive(Clone, Debug, Default)]
pub struct PrivacyEraseReport {
    pub deleted_files: usize,
    pub skipped_files: usize,
}

#[derive(Clone, Debug)]
pub struct PrivacyManager {
    recording_root: PathBuf,
}

impl PrivacyManager {
    pub fn new() -> Self {
        Self {
            recording_root: recording_root(),
        }
    }

    pub fn erase_selected_audio(&self, snapshot: &CompanionV1Snapshot) -> PrivacyEraseReport {
        let mut report = PrivacyEraseReport::default();
        let selected_id = snapshot
            .host
            .selected_session_id
            .as_ref()
            .or(snapshot.host.active_session_id.as_ref());
        for session in &snapshot.host.sessions {
            if selected_id.is_some_and(|id| id != &session.id) {
                continue;
            }
            self.erase_session_audio(session.audio_path.as_deref(), &mut report);
            for chunk in &session.chunks {
                self.erase_session_audio(chunk.path.as_deref(), &mut report);
            }
        }
        report
    }

    pub fn erase_all_audio(&self, snapshot: &CompanionV1Snapshot) -> PrivacyEraseReport {
        let mut report = PrivacyEraseReport::default();
        for session in &snapshot.host.sessions {
            self.erase_session_audio(session.audio_path.as_deref(), &mut report);
            for chunk in &session.chunks {
                self.erase_session_audio(chunk.path.as_deref(), &mut report);
            }
        }
        report
    }

    fn erase_session_audio(&self, path: Option<&str>, report: &mut PrivacyEraseReport) {
        let Some(path) = path else {
            return;
        };
        let path = PathBuf::from(path);
        if !self.is_owned_recording_path(&path) {
            report.skipped_files += 1;
            return;
        }
        if path.exists() {
            match std::fs::remove_file(&path) {
                Ok(()) => report.deleted_files += 1,
                Err(_) => report.skipped_files += 1,
            }
        }
    }

    fn is_owned_recording_path(&self, path: &Path) -> bool {
        if !path.is_absolute() {
            return false;
        }
        let Ok(path) = path.canonicalize() else {
            return false;
        };
        let Ok(root) = self.recording_root.canonicalize() else {
            return false;
        };
        path.starts_with(root)
    }
}

impl Default for PrivacyManager {
    fn default() -> Self {
        Self::new()
    }
}

fn recording_root() -> PathBuf {
    std::env::var("COMPANION_TYPE_RECORDING_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::temp_dir()
                .join("companion-type")
                .join("recordings")
        })
}

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
                ble_name: None,
                session_id: Some("privacy-session".to_string()),
                prompt_id: None,
                title: Some("Privacy session".to_string()),
                transcript_text: None,
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
