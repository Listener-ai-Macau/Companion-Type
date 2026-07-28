//! Companion-Type session persistence.
//!
//! The backend state (`CompanionV1Snapshot`) is otherwise in-memory only:
//! closing the app used to wipe every meeting's transcript and minutes even
//! though the WAV files survived on disk. This module persists the host
//! sessions — the valuable user data (transcript, minutes, audio path, diarized
//! speaker tags, metadata) — to a JSON file so they survive restarts.
//!
//! Location resolution (first wins):
//!   1. `COMPANION_TYPE_STATE_PATH`  — full file path (also used by tests)
//!   2. `COMPANION_TYPE_STATE_DIR/sessions.json`
//!   3. `%APPDATA%\Companion Type\state\sessions.json`

use std::fs;
use std::path::{Path, PathBuf};

use crate::companion_v1::CompanionV1HostSession;

const STATE_FILE: &str = "sessions.json";

pub fn state_file_path() -> PathBuf {
    if let Ok(path) = std::env::var("COMPANION_TYPE_STATE_PATH") {
        return PathBuf::from(path);
    }
    if let Ok(dir) = std::env::var("COMPANION_TYPE_STATE_DIR") {
        return PathBuf::from(dir).join(STATE_FILE);
    }
    let appdata = std::env::var("APPDATA").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(appdata)
        .join("Companion Type")
        .join("state")
        .join(STATE_FILE)
}

/// Load persisted sessions from `path`. Returns `None` when the file is absent
/// or cannot be parsed (corrupt / schema drift) so the caller falls back to the
/// fixture default instead of crashing the app.
pub fn load_sessions_from(path: &Path) -> Option<Vec<CompanionV1HostSession>> {
    let bytes = fs::read(path).ok()?;
    match serde_json::from_slice::<Vec<CompanionV1HostSession>>(&bytes) {
        Ok(sessions) => Some(sessions),
        Err(err) => {
            eprintln!(
                "[persistence] failed to parse {}: {}; ignoring cached state",
                path.display(),
                err
            );
            None
        }
    }
}

/// Persist sessions atomically: write to a sibling temp file, then rename.
pub fn save_sessions_to(
    path: &Path,
    sessions: &[CompanionV1HostSession],
) -> Result<(), String> {
    if let Some(dir) = path.parent() {
        fs::create_dir_all(dir).map_err(|e| format!("create_dir_all {}: {e}", dir.display()))?;
    }
    let json =
        serde_json::to_string_pretty(sessions).map_err(|e| format!("serialize sessions: {e}"))?;
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, &json).map_err(|e| format!("write {}: {e}", tmp.display()))?;
    fs::rename(&tmp, path)
        .map_err(|e| format!("rename {} -> {}: {e}", tmp.display(), path.display()))?;
    Ok(())
}

/// Load the app's persisted sessions (resolved location). `None` = no cached
/// state; keep the fixture default.
pub fn load_sessions() -> Option<Vec<CompanionV1HostSession>> {
    // Under cargo test, do not touch the real user state dir unless a test
    // explicitly pins COMPANION_TYPE_STATE_PATH — otherwise every backend
    // integration test that calls apply_control would read/write the real
    // %APPDATA% state file (pollution + parallel races). Persistence unit
    // tests use load_sessions_from / save_sessions_to with explicit paths.
    if cfg!(test) && std::env::var("COMPANION_TYPE_STATE_PATH").is_err() {
        return None;
    }
    load_sessions_from(&state_file_path())
}

/// Save sessions to the resolved location. Best-effort: a write failure is
/// logged but never blocks a control action.
pub fn save_sessions(sessions: &[CompanionV1HostSession]) {
    if cfg!(test) && std::env::var("COMPANION_TYPE_STATE_PATH").is_err() {
        return;
    }
    let path = state_file_path();
    if let Err(err) = save_sessions_to(&path, sessions) {
        eprintln!("[persistence] failed to save {}: {}", path.display(), err);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::CompanionV1SessionRetention;

    fn sample_session(id: &str, text: &str) -> CompanionV1HostSession {
        CompanionV1HostSession {
            id: id.to_string(),
            title: format!("Meeting {id}"),
            source: "hostMicrophone".to_string(),
            status: "transcribed".to_string(),
            pending_reason: None,
            started_at: None,
            stopped_at: None,
            duration_ms: 5000,
            audio_path: Some(format!("C:/tmp/{id}.wav")),
            audio_bytes: 1000,
            chunks: vec![],
            transcript_text: text.to_string(),
            transcript_preview: text.to_string(),
            transcript_segments: 1,
            utterances: Vec::new(),
            minutes: None,
            export_markdown: String::new(),
            exported_at: None,
            retention: CompanionV1SessionRetention {
                audio_cached: true,
                transcript_cached: true,
                minutes_cached: false,
                consent_required: true,
                retention_label: "7 days local".to_string(),
                expires_at: None,
            },
        }
    }

    #[test]
    fn save_then_load_round_trips_sessions() {
        let dir = std::env::temp_dir().join("companion-type-persistence-roundtrip");
        let _ = fs::remove_dir_all(&dir);
        let path = dir.join("s.json");
        let sessions = vec![
            sample_session("s1", "决定：持久化。行动：陈明验证。"),
            sample_session("s2", "说话人1: 你好\n说话人2: 谢谢"),
        ];
        save_sessions_to(&path, &sessions).expect("save");
        let loaded = load_sessions_from(&path).expect("loaded");
        assert_eq!(loaded.len(), 2);
        assert_eq!(loaded[0].id, "s1");
        assert_eq!(loaded[0].transcript_text, "决定：持久化。行动：陈明验证。");
        assert_eq!(loaded[1].transcript_text, "说话人1: 你好\n说话人2: 谢谢");
        assert_eq!(loaded[0].retention.retention_label, "7 days local");
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn load_returns_none_when_missing() {
        let path = std::env::temp_dir().join("definitely-missing-companion-state.json");
        let _ = fs::remove_file(&path);
        assert!(load_sessions_from(&path).is_none());
    }

    #[test]
    fn load_returns_none_when_corrupt() {
        let dir = std::env::temp_dir().join("companion-type-persistence-corrupt");
        let _ = fs::remove_dir_all(&dir);
        let path = dir.join("s.json");
        fs::create_dir_all(&dir).unwrap();
        fs::write(&path, b"not valid json {{{").unwrap();
        assert!(load_sessions_from(&path).is_none());
        let _ = fs::remove_dir_all(&dir);
    }
}
