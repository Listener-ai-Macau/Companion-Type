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

#[cfg(test)]
use std::fs;
use std::path::{Path, PathBuf};

use crate::companion_v1::{CompanionV1HostSession, CompanionV1MinutesVariant, CompanionV1PersistenceState, CompanionV1Snapshot};

const STATE_FILE: &str = "sessions.json";

fn recovery_audio_is_owned(session: &CompanionV1HostSession) -> bool {
    let Some(path) = session.audio_path.as_deref() else {
        return false;
    };
    if path.starts_with("board://") || path.starts_with("device://") || path.starts_with("host://") {
        return false;
    }
    let path = Path::new(path);
    let is_wav = path
        .extension()
        .and_then(|value| value.to_str())
        .is_some_and(|value| value.eq_ignore_ascii_case("wav"));
    if !is_wav || !path.is_file() || !session.audio_stored || !session.retention.audio_cached {
        return false;
    }
    let known_product_source = matches!(
        session.source.as_str(),
        "deviceFlash" | "boardDevice" | "hostMicrophone"
    );
    let chunk_owns_path = session.chunks.iter().any(|chunk| {
        chunk.path.as_deref() == session.audio_path.as_deref()
            && matches!(chunk.status.as_str(), "sealed" | "synced")
    });
    known_product_source && (chunk_owns_path || session.device_recording_id.is_some())
}

/// Reconcile a persisted recovery checkpoint after a process restart. This is
/// deliberately conservative: only an already-armed product session can be
/// queued, and an arbitrary/legacy WAV never gains recovery intent here.
pub(crate) fn reconcile_session_recovery(session: &mut CompanionV1HostSession) {
    if session.recovery.intent != "processMeeting" {
        return;
    }
    if session.recovery.max_attempts == 0 {
        session.recovery.max_attempts = 3;
    }
    let requested_minutes = if session.recovery.requested_meeting_mode == "onlineLive" {
        session.minutes_by_mode.online_live.as_ref()
    } else {
        session.minutes_by_mode.offline_store.as_ref()
    };
    let requested_minutes_ready = requested_minutes.is_some_and(|minutes| {
        minutes.status == "minutesReady" && !minutes.markdown.trim().is_empty()
            && minutes.processing.as_ref().is_none_or(|p| p.is_complete())
            && super::transcript_review::minutes_current(session, minutes.source_review_revision)
    });
    // A committed, mode-specific product always wins over a stale in-flight
    // checkpoint left by a crash after the final local save.
    if session.status == "minutesReady"
        && !super::session_has_pending_dual_minutes(session)
        && session.minutes.as_ref().is_some_and(|minutes| !minutes.markdown.trim().is_empty()
            && minutes.processing.as_ref().is_none_or(|p| p.is_complete())
            && super::transcript_review::minutes_current(session, minutes.source_review_revision))
        && requested_minutes_ready
    {
        session.recovery.stage = "complete".to_string();
        session.recovery.retry_stage.clear();
        session.recovery.next_retry_at_unix_ms = None;
        session.recovery.last_error = None;
        session.pending_reason = None;
        return;
    }
    if session.recovery.requested_meeting_mode != session.meeting_mode
        || !matches!(session.meeting_mode.as_str(), "offlineStore" | "onlineLive")
    {
        session.recovery.stage = "paused".to_string();
        session.recovery.next_retry_at_unix_ms = None;
        session.recovery.last_error = Some("meeting mode changed after capture".to_string());
        session.pending_reason = Some("recovery_paused".to_string());
        return;
    }
    if super::interrupted_capture::hold(session) { return; }
    // An attempt is durably consumed before remote work. If the process died
    // while it was in flight, resume that exact stage through backoff instead
    // of silently resetting the budget.
    if matches!(session.recovery.stage.as_str(), "transcribing" | "generatingMinutes") {
        session.recovery.retry_stage = if session.recovery.stage == "generatingMinutes" {
            "minutes"
        } else {
            "transcription"
        }
        .to_string();
        if session.recovery.attempt_count >= session.recovery.max_attempts {
            session.recovery.stage = "paused".to_string();
            session.recovery.next_retry_at_unix_ms = None;
            session.pending_reason = Some("recovery_paused".to_string());
        } else {
            session.recovery.stage = "retryBackoff".to_string();
            session.recovery.next_retry_at_unix_ms = None;
            session.pending_reason = Some("recovery_retry_wait".to_string());
        }
        return;
    }
    if session.recovery.attempt_count >= session.recovery.max_attempts {
        session.recovery.stage = "paused".to_string();
        session.recovery.next_retry_at_unix_ms = None;
        session.pending_reason = Some("recovery_paused".to_string());
        return;
    }
    // Preserve a durable failure decision across restarts. In particular, a
    // final transcript must not revive exhausted/paused minutes generation.
    if session.recovery.stage == "paused" {
        session.recovery.next_retry_at_unix_ms = None;
        let awaiting_device_audio = session.pending_reason.as_deref() == Some("needs_device_sync")
            && matches!(session.source.as_str(), "boardDevice" | "deviceFlash")
            && session.device_recording_id.is_some_and(|id| id != 0)
            && !session.audio_stored && !session.device_reclaimed;
        // Pausing ASR while the original audio is still on the board must
        // retain the actionable sync state. This does not resume cloud work.
        if session.pending_reason.as_deref() != Some("no_speech_detected") && !awaiting_device_audio {
            session.pending_reason = Some("recovery_paused".to_string());
        }
        return;
    }
    if session.recovery.stage == "retryBackoff" {
        if session.recovery.retry_stage.is_empty() {
            session.recovery.retry_stage = if session.transcript_final {
                "minutes"
            } else {
                "transcription"
            }
            .to_string();
        }
        session.pending_reason = Some("recovery_retry_wait".to_string());
        return;
    }
    if session.transcript_final && !session.transcript_text.trim().is_empty() {
        session.recovery.stage = "pendingMinutes".to_string();
        session.recovery.retry_stage = "minutes".to_string();
        session.recovery.next_retry_at_unix_ms = None;
        session.pending_reason = None;
        return;
    }
    if !recovery_audio_is_owned(session) {
        session.recovery.stage = "paused".to_string();
        session.recovery.next_retry_at_unix_ms = None;
        session.recovery.last_error = Some(
            "captured audio is missing, virtual, or not owned by this product session".to_string(),
        );
        session.pending_reason = Some(if session
            .audio_path
            .as_deref()
            .is_some_and(|path| path.starts_with("board://") || path.starts_with("device://"))
        {
            "needs_device_sync".to_string()
        } else {
            "recovery_paused".to_string()
        });
        return;
    }
    session.recovery.stage = "pendingTranscription".to_string();
    session.recovery.retry_stage = "transcription".to_string();
    session.recovery.next_retry_at_unix_ms = None;
    session.pending_reason = Some("needs_transcription".to_string());
}

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

/// Load the valid primary or recovery copy. Callers must distinguish unavailable
/// storage from an empty library with `load_sessions_with_status` before editing.
pub fn load_sessions_from(path: &Path) -> Option<Vec<CompanionV1HostSession>> {
    let loaded = super::session_store::load(path);
    migrate_sessions(loaded.bytes?)
}

fn migrate_sessions(bytes: Vec<u8>) -> Option<Vec<CompanionV1HostSession>> {
    match serde_json::from_slice::<Vec<CompanionV1HostSession>>(&bytes) {
        Ok(mut sessions) => {
            // Backward-compatible one-time migration. Older state has one
            // `minutes` value; retain it and also expose it through the mode
            // it was generated under. A later second route can coexist.
            for session in &mut sessions {
                if matches!(session.source.as_str(), "deviceFlash" | "boardDevice" | "hostMicrophone") {
                    // Old phase labels are not capture dates. Loading must
                    // not replace an unknown original date with today's time.
                    super::board_meeting::retain_capture_dates(session);
                }
                // The host worker cannot survive process exit; the board may
                // still be recording. Recover the row into an actionable state
                // without inventing a stop time or treating a host:// target
                // path as audio already received from the device.
                if session.status == "recording" && session.recorder_control.is_some() {
                    // The physical recorder outlives this host process.
                    // Preserve its exact pending intent/key and require an
                    // actual CMS3 observation; restart cannot invent STOP.
                    session.recorder_control_uncertain=true;
                    session.pending_reason=Some("device_control_pending".into());
                } else if session.status == "recording" {
                    let needs_device_sync = (matches!(
                        session.source.as_str(), "deviceFlash" | "boardDevice"
                    ) && session.device_recording_id.is_some_and(|id| id != 0)
                        && !session.audio_stored)
                        || session
                            .audio_path
                            .as_deref()
                            .is_some_and(|path| path.starts_with("board://"));
                    session.status = "captured".to_string();
                    session.pending_reason = Some(
                        if needs_device_sync {
                            "needs_device_sync".to_string()
                        } else {
                            "needs_transcription".to_string()
                        },
                    );
                }
                if let Some(minutes) = session.minutes.as_ref() {
                    let variant = CompanionV1MinutesVariant {
                        processing: minutes.processing.clone(),
                        source_review_revision: minutes.source_review_revision,
                        status: "minutesReady".to_string(),
                        markdown: minutes.markdown.clone(),
                        source: minutes.source.clone(),
                        quality: minutes.quality.clone(),
                        generated_at: Some(minutes.generated_at.clone()),
                        partial_count: 0,
                    };
                    if session.meeting_mode == "onlineLive" {
                        if session.minutes_by_mode.online_live.is_none() {
                            session.minutes_by_mode.online_live = Some(variant);
                        }
                    } else if session.minutes_by_mode.offline_store.is_none() {
                        session.minutes_by_mode.offline_store = Some(variant);
                    }
                }
                // Pre-recovery-schema sessions had no transcriptFinal field.
                // Only migrate records whose old state already proved a final
                // transcript. Captured/recording rows and armed recovery rows
                // may contain onlineLive prefixes and must remain non-final.
                if session.recovery.intent == "none"
                    && !session.transcript_final
                    && matches!(session.status.as_str(), "transcribed" | "minutesReady")
                    && !session.transcript_text.trim().is_empty()
                {
                    session.transcript_final = true;
                }
                reconcile_session_recovery(session);
            }
            Some(sessions)
        }
        Err(_) => None,
    }
}

fn commit_audio_migration(
    path: &Path,
    before: &[CompanionV1HostSession],
    after: &[CompanionV1HostSession],
) -> Result<Vec<CompanionV1HostSession>, String> {
    let mut conflict = None;
    super::session_store::update(path, |stored| {
        let mut candidate = stored.clone();
        for migrated in after {
            let Some(original) = before.iter().find(|session| session.id == migrated.id) else { continue; };
            if original.audio_path == migrated.audio_path { continue; }
            let Some(current) = candidate.iter_mut().find(|session| session.id == migrated.id) else {
                conflict = Some(format!("meeting {} changed while audio was being migrated", migrated.id));
                break;
            };
            if current.audio_path != original.audio_path && current.audio_path != migrated.audio_path {
                conflict = Some(format!("meeting {} audio changed while it was being migrated", migrated.id));
                break;
            }
            if current.source != original.source
                || current.audio_bytes != original.audio_bytes
                || current.audio_stored != original.audio_stored
                || current.retention.audio_cached != original.retention.audio_cached
                || current.device_recording_id != original.device_recording_id
                || current.source_device_id != original.source_device_id {
                conflict = Some(format!("meeting {} identity changed while audio was being migrated", migrated.id));
                break;
            }
            if current.audio_path == original.audio_path {
                current.audio_path = migrated.audio_path.clone();
                for chunk in &mut current.chunks {
                    let same = match (chunk.path.as_deref(), original.audio_path.as_deref()) {
                        (Some(left), Some(right)) if left == right => true,
                        (Some(left), Some(right)) => Path::new(left).canonicalize().ok()
                            .zip(Path::new(right).canonicalize().ok())
                            .is_some_and(|(left, right)| left == right),
                        _ => false,
                    };
                    if same { chunk.path = migrated.audio_path.clone(); }
                }
            }
        }
        if conflict.is_none() { *stored = candidate; }
    })?;
    if let Some(error) = conflict { return Err(error); }
    // Return the locked commit rather than the older startup snapshot, so a
    // concurrent new meeting or edit is never hidden in memory.
    let loaded = super::session_store::load(path);
    if loaded.state.status == "blocked" {
        return Err(loaded.state.message.unwrap_or_else(|| "meeting index reload failed".into()));
    }
    migrate_sessions(loaded.bytes.ok_or("meeting index disappeared after audio migration")?)
        .ok_or_else(|| "meeting index became unreadable after audio migration".into())
}

/// Commit through synchronized replacement and a validated recovery copy.
pub fn save_sessions_to(path: &Path, sessions: &[CompanionV1HostSession]) -> Result<(), String> {
    super::session_store::save(path, sessions)
}

pub fn load_sessions_with_status() -> (Option<Vec<CompanionV1HostSession>>, CompanionV1PersistenceState) {
    if cfg!(test) && std::env::var("COMPANION_TYPE_STATE_PATH").is_err() {
        return (None, Default::default());
    }
    let state_path = state_file_path();
    let loaded = super::session_store::load(&state_path);
    let Some(sessions) = loaded.bytes.and_then(migrate_sessions) else {
        return (None, loaded.state);
    };
    // Real startup migrates only already-indexed product WAVs. Tests and
    // intentionally isolated deployments use COMPANION_TYPE_RECORDING_DIR and
    // call the parameterized helper directly instead of touching a user profile.
    if !cfg!(test) && !super::audio_storage::has_recording_dir_override() {
        match super::audio_storage::migrate_production_sessions(&sessions) {
            Ok((migrated, outcome)) if outcome.migrated != 0 || outcome.ledger_backed != 0 => {
                // `update` finishes by writing the same committed index to its
                // fallback. A single ordinary save intentionally leaves the
                // previous index in .bak, which could still point at Temp.
                return match commit_audio_migration(&state_path, &sessions, &migrated) {
                    Ok(committed) => (Some(committed), Default::default()),
                    Err(error) => (Some(sessions), CompanionV1PersistenceState {
                        status: "blocked".into(),
                        message: Some(format!(
                            "旧录音已安全复制，但会议索引尚未提交；原路径和副本均已保留，请重试恢复：{error}"
                        )),
                        recovery_path: Some(state_path.to_string_lossy().into_owned()),
                    }),
                };
            }
            Ok(_) => {}
            Err(error) => {
                return (Some(sessions), CompanionV1PersistenceState {
                    status: "blocked".into(),
                    message: Some(format!("旧录音迁移未完成，会议库处理已暂停；原文件和索引保持不变：{error}")),
                    recovery_path: Some(state_path.to_string_lossy().into_owned()),
                });
            }
        }
    }
    (Some(sessions), loaded.state)
}

/// Read the persisted library for explicit repair tools. `None` means missing
/// or unavailable data; it must never be interpreted as permission to replace it.
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

/// Preserve real in-memory state on disk failure (a stopped recorder must stay
/// stopped) while preventing further processing from pretending it is durable.
pub fn save_snapshot(snapshot: &mut CompanionV1Snapshot) -> Result<(), String> {
    if snapshot.host.persistence.status == "blocked" {
        return Err("会议库尚未恢复，已暂停保存；请先重试恢复".into());
    }
    let result = save_sessions_checked(&snapshot.host.sessions);
    match &result {
        Ok(()) => snapshot.host.persistence = Default::default(),
        Err(error) => {
            snapshot.host.persistence = CompanionV1PersistenceState {
                status: "unsaved".into(),
                message: Some(format!("最新会议内容尚未保存，请保留当前窗口。修复磁盘空间或目录访问后，点击重试保存。详情：{error}")),
                recovery_path: Some(state_file_path().to_string_lossy().into_owned()),
            };
            if let Some(echo) = snapshot.last_control.as_mut() {
                echo.accepted = false;
                echo.message = "操作已执行，但最新内容尚未保存；请保留窗口并重试保存。".into();
            }
        }
    }
    result
}

/// Persist a checkpoint and report failure to the caller. Tests without an
/// explicit state path stay isolated from the real user profile.
pub fn save_sessions_checked(sessions: &[CompanionV1HostSession]) -> Result<(), String> {
    if cfg!(test) && std::env::var("COMPANION_TYPE_STATE_PATH").is_err() {
        return Ok(());
    }
    save_sessions_to(&state_file_path(), sessions)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{
        CompanionV1AudioChunk, CompanionV1MeetingMinutes, CompanionV1MeetingRecovery,
        CompanionV1SessionRetention,
    };

    fn sample_session(id: &str, text: &str) -> CompanionV1HostSession {
        CompanionV1HostSession { processing_policy: Default::default(), recorder_control: None, recorder_control_uncertain: false, device_recording_key: None, 
            transcript_review: None,
            bookmark_revision: 0, bookmarks: vec![],
            note_revision: 0, meeting_notes: vec![],
            id: id.to_string(),
            title: format!("Meeting {id}"),
            source: "hostMicrophone".to_string(),
            meeting_mode: "offlineStore".to_string(),
            status: "transcribed".to_string(),
            pending_reason: None,
            started_at: None,
            stopped_at: None,
            duration_ms: 5000,
            audio_path: Some(format!("C:/tmp/{id}.wav")),
            audio_bytes: 1000,
            audio_stored: true,
            device_recording_id: None,
            device_total_length: None,
            device_sha256: None,
            device_reclaimed: false, capture_incomplete: false,
            source_device_id: None,
            chunks: vec![],
            transcript_text: text.to_string(),
            transcript_final: !text.trim().is_empty(),
            live_transcript_text: String::new(),
            transcript_preview: text.to_string(),
            transcript_segments: 1,
            utterances: Vec::new(),
            minutes: None,
            minutes_by_mode: Default::default(),
            recovery: Default::default(),
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

    fn armed_owned_session(id: &str) -> (CompanionV1HostSession, PathBuf) {
        let dir = std::env::temp_dir().join(format!("companion-type-recovery-{id}"));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let wav = dir.join(format!("{id}.wav"));
        fs::write(&wav, b"RIFF----WAVEfmt ").unwrap();
        let mut session = sample_session(id, "");
        session.status = "captured".to_string();
        session.audio_path = Some(wav.to_string_lossy().to_string());
        session.recovery = CompanionV1MeetingRecovery::armed("offlineStore");
        session.chunks = vec![CompanionV1AudioChunk {
            id: format!("{id}-sealed"),
            path: session.audio_path.clone(),
            started_at: None,
            stopped_at: Some("test".to_string()),
            duration_ms: 1_000,
            bytes: 16,
            status: "sealed".to_string(),
        }];
        (session, dir)
    }

    fn sample_minutes(markdown: &str) -> CompanionV1MeetingMinutes {
        CompanionV1MeetingMinutes {
            processing: None,
            source_review_revision: None,
            generated_at: "test".to_string(),
            source: "rules_l0".to_string(),
            quality: "draft".to_string(),
            summary: vec![],
            decisions: vec![],
            action_items: vec![],
            questions: vec![],
            keywords: vec![],
            markdown: markdown.to_string(),
            llm_note: None,
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
    fn legacy_minutes_migrate_to_their_original_mode() {
        let dir = std::env::temp_dir().join("companion-type-persistence-minutes-migration");
        let _ = fs::remove_dir_all(&dir);
        let path = dir.join("s.json");
        let mut session = sample_session("legacy", "决定：迁移双纪要状态。");
        session.minutes = Some(crate::companion_v1::CompanionV1MeetingMinutes {
            processing: None,
            source_review_revision: None,
            generated_at: "2026-08-14T00:00:00Z".to_string(),
            source: "rules_l0".to_string(),
            quality: "draft".to_string(),
            summary: vec!["迁移".to_string()],
            decisions: vec![],
            action_items: vec![],
            questions: vec![],
            keywords: vec![],
            markdown: "# legacy minutes".to_string(),
            llm_note: None,
        });
        save_sessions_to(&path, &[session]).expect("save");
        let loaded = load_sessions_from(&path).expect("load");
        assert_eq!(
            loaded[0]
                .minutes_by_mode
                .offline_store
                .as_ref()
                .map(|item| item.markdown.as_str()),
            Some("# legacy minutes")
        );
        assert!(loaded[0].minutes_by_mode.online_live.is_none());
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn restart_recovers_phantom_board_recording_to_sync_pending() {
        let dir = std::env::temp_dir().join("companion-type-persistence-recording-recovery");
        let _ = fs::remove_dir_all(&dir);
        let path = dir.join("s.json");
        let mut session = sample_session("board-live", "");
        session.status = "recording".to_string();
        session.audio_path = Some("board://online/board-live".to_string());
        session.stopped_at = None;
        save_sessions_to(&path, &[session]).expect("save");
        let loaded = load_sessions_from(&path).expect("load");
        assert_eq!(loaded[0].status, "captured");
        assert_eq!(
            loaded[0].pending_reason.as_deref(),
            Some("needs_device_sync")
        );
        assert!(loaded[0].stopped_at.is_none());
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn restart_recovers_unreceived_board_audio_with_host_target_path() {
        let dir = std::env::temp_dir().join(format!(
            "companion-type-board-target-recovery-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        let path = dir.join("s.json");
        let mut pending = sample_session("board-recording-17", "");
        pending.source = "boardDevice".to_string();
        pending.source_device_id = Some("C8:92:FF:DD:3B:CA".to_string());
        pending.device_recording_id = Some(17);
        pending.meeting_mode = "onlineLive".to_string();
        pending.status = "recording".to_string();
        pending.started_at = Some("2026-10-08T07:06:55.130Z".to_string());
        pending.audio_path = Some("host://companion-type/recordings/board-recording-17.wav".to_string());
        pending.audio_stored = false;
        pending.retention.audio_cached = false;
        pending.chunks.clear();
        save_sessions_to(&path, &[pending.clone()]).expect("save");

        let loaded = load_sessions_from(&path).expect("load");
        let recovered = &loaded[0];
        assert_eq!(recovered.status, "captured");
        assert_eq!(recovered.pending_reason.as_deref(), Some("needs_device_sync"));
        assert_eq!(recovered.id, pending.id);
        assert_eq!(recovered.title, pending.title);
        assert_eq!(recovered.meeting_mode, pending.meeting_mode);
        assert_eq!(recovered.started_at, pending.started_at);
        assert_eq!(recovered.device_recording_id, Some(17));
        assert!(recovered.stopped_at.is_none());
        assert!(!recovered.audio_stored);
        assert!(!recovered.device_reclaimed);
        assert!(recovered.device_sha256.is_none());
        assert!(recovered.chunks.is_empty());
        fs::remove_dir_all(&dir).expect("remove test state");
    }

    #[test]
    fn restart_keeps_received_audio_and_confirmed_stop_for_transcription() {
        let mut session = sample_session("received-board-audio", "");
        session.source = "boardDevice".to_string();
        session.device_recording_id = Some(17);
        session.status = "recording".to_string();
        session.stopped_at = Some("2026-10-08T07:12:25Z".to_string());
        let loaded = migrate_sessions(serde_json::to_vec(&vec![session]).unwrap()).unwrap();
        assert_eq!(loaded[0].pending_reason.as_deref(), Some("needs_transcription"));
        assert_eq!(loaded[0].stopped_at.as_deref(), Some("2026-10-08T07:12:25Z"));
        assert!(loaded[0].audio_stored);
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

    #[test]
    fn recovery_never_arms_an_unrelated_legacy_wav() {
        let (mut session, dir) = armed_owned_session("legacy-unarmed");
        session.recovery = CompanionV1MeetingRecovery::default();
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "idle");
        assert_eq!(session.recovery.intent, "none");
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_queues_only_an_armed_owned_product_wav() {
        let (mut session, dir) = armed_owned_session("armed-owned");
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "pendingTranscription");
        assert_eq!(session.recovery.retry_stage, "transcription");
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_restart_preserves_exhausted_minutes_failure_even_with_final_transcript() {
        let (mut session, dir) = armed_owned_session("minutes-exhausted");
        session.transcript_text = "final transcript".to_string();
        session.transcript_final = true;
        session.recovery.stage = "paused".to_string();
        session.recovery.retry_stage = "minutes".to_string();
        session.recovery.attempt_count = 3;
        session.recovery.max_attempts = 3;
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "paused");
        assert_eq!(session.recovery.retry_stage, "minutes");
        assert_eq!(session.pending_reason.as_deref(), Some("recovery_paused"));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_restart_preserves_minutes_backoff_instead_of_bypassing_it() {
        let (mut session, dir) = armed_owned_session("minutes-backoff");
        session.transcript_text = "final transcript".to_string();
        session.transcript_final = true;
        session.recovery.stage = "retryBackoff".to_string();
        session.recovery.retry_stage = "minutes".to_string();
        session.recovery.attempt_count = 1;
        session.recovery.next_retry_at_unix_ms = Some(u64::MAX - 1);
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "retryBackoff");
        assert_eq!(session.recovery.retry_stage, "minutes");
        assert_eq!(session.recovery.next_retry_at_unix_ms, Some(u64::MAX - 1));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_online_live_partial_is_not_promoted_to_final_minutes_input() {
        let (mut session, dir) = armed_owned_session("live-partial");
        session.meeting_mode = "onlineLive".to_string();
        session.recovery = CompanionV1MeetingRecovery::armed("onlineLive");
        session.transcript_text = "provisional prefix".to_string();
        session.live_transcript_text = session.transcript_text.clone();
        session.transcript_final = false;
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "pendingTranscription");
        assert_ne!(session.recovery.stage, "pendingMinutes");
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_in_flight_crash_keeps_consumed_attempt_and_exact_stage() {
        let (mut session, dir) = armed_owned_session("inflight-minutes");
        session.transcript_text = "final transcript".to_string();
        session.transcript_final = true;
        session.recovery.stage = "generatingMinutes".to_string();
        session.recovery.attempt_count = 2;
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "retryBackoff");
        assert_eq!(session.recovery.retry_stage, "minutes");
        assert_eq!(session.recovery.attempt_count, 2);

        session.recovery.stage = "generatingMinutes".to_string();
        session.recovery.attempt_count = 3;
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "paused");
        assert_eq!(session.recovery.attempt_count, 3);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_completed_mode_specific_minutes_win_over_stale_checkpoint() {
        let (mut session, dir) = armed_owned_session("completed");
        session.transcript_text = "final transcript".to_string();
        session.transcript_final = true;
        session.status = "minutesReady".to_string();
        session.minutes = Some(sample_minutes("# final"));
        session.minutes_by_mode.offline_store = Some(CompanionV1MinutesVariant {
            processing: None,
            source_review_revision: None,
            status: "minutesReady".to_string(),
            markdown: "# final".to_string(),
            source: "rules_l0".to_string(),
            quality: "draft".to_string(),
            generated_at: Some("test".to_string()),
            partial_count: 0,
        });
        session.recovery.stage = "generatingMinutes".to_string();
        session.recovery.attempt_count = 2;
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "complete");
        assert_eq!(session.recovery.attempt_count, 2);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_failed_minutes_draft_restarts_at_minutes_without_repeating_asr() {
        let (mut session, dir) = armed_owned_session("minutes-draft-retry");
        session.transcript_text = "durable final transcript".to_string();
        session.transcript_final = true;
        session.status = "transcribed".to_string();
        let mut draft = sample_minutes("# readable fallback draft");
        draft.llm_note = Some("temporary minutes service timeout".to_string());
        session.minutes = Some(draft);
        session.minutes_by_mode.offline_store = Some(CompanionV1MinutesVariant {
            processing: None,
            source_review_revision: None,
            status: "retryPending".to_string(),
            markdown: "# readable fallback draft".to_string(),
            source: "rules_l0".to_string(),
            quality: "draft".to_string(),
            generated_at: Some("test".to_string()),
            partial_count: 0,
        });
        session.recovery.stage = "retryBackoff".to_string();
        session.recovery.retry_stage = "minutes".to_string();
        session.recovery.attempt_count = 1;
        session.recovery.next_retry_at_unix_ms = Some(0);
        reconcile_session_recovery(&mut session);
        assert_eq!(session.recovery.stage, "retryBackoff");
        assert_eq!(session.recovery.retry_stage, "minutes");
        assert!(session.transcript_final);
        assert_eq!(session.recovery.attempt_count, 1);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_legacy_completed_transcript_migrates_final_but_captured_partial_does_not() {
        let dir = std::env::temp_dir().join("companion-type-legacy-transcript-final");
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("sessions.json");
        let completed = sample_session("legacy-complete", "legacy final text");
        let mut partial = sample_session("legacy-partial", "online prefix only");
        partial.status = "captured".to_string();
        partial.transcript_final = false;
        let mut value = serde_json::to_value(vec![completed, partial]).unwrap();
        for session in value.as_array_mut().unwrap() {
            session.as_object_mut().unwrap().remove("transcriptFinal");
        }
        fs::write(&path, serde_json::to_vec_pretty(&value).unwrap()).unwrap();
        let loaded = load_sessions_from(&path).unwrap();
        assert!(loaded[0].transcript_final);
        assert!(!loaded[1].transcript_final);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn recovery_revoked_intent_stays_revoked_after_restart() {
        let (mut session, dir) = armed_owned_session("privacy-revoked");
        session.recovery = CompanionV1MeetingRecovery::default();
        let path = dir.join("sessions.json");
        save_sessions_to(&path, &[session]).unwrap();
        let loaded = load_sessions_from(&path).unwrap();
        assert_eq!(loaded[0].recovery.intent, "none");
        assert_eq!(loaded[0].recovery.stage, "idle");
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn audio_migration_replays_only_paths_and_preserves_concurrent_rows() {
        let dir = std::env::temp_dir().join(format!("companion-audio-commit-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("sessions.json");
        let mut original = sample_session("migrate", "original");
        original.audio_path = Some("C:/Temp/companion-type/recordings/old.wav".into());
        let mut migrated = original.clone();
        migrated.audio_path = Some("C:/Users/test/AppData/Local/Companion Type/recordings/old.wav".into());
        save_sessions_to(&path, &[original.clone()]).unwrap();
        let mut concurrent = sample_session("new-meeting", "new");
        concurrent.title = "concurrent title".into();
        super::super::session_store::update(&path, |sessions| sessions.push(concurrent.clone())).unwrap();
        let committed = commit_audio_migration(&path, &[original], &[migrated]).unwrap();
        assert_eq!(committed.len(), 2);
        assert_eq!(committed.iter().find(|s| s.id == concurrent.id).unwrap().title, "concurrent title");
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn audio_migration_conflict_commits_none_of_a_multirow_candidate() {
        let dir = std::env::temp_dir().join(format!("companion-audio-conflict-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("sessions.json");
        let mut first = sample_session("first", "one");
        first.audio_path = Some("C:/Temp/companion-type/recordings/first.wav".into());
        let mut second = sample_session("second", "two");
        second.audio_path = Some("C:/Temp/companion-type/recordings/second.wav".into());
        save_sessions_to(&path, &[first.clone(), second.clone()]).unwrap();
        super::super::session_store::update(&path, |sessions| {
            sessions[1].retention.audio_cached = false;
        }).unwrap();
        let mut first_after = first.clone();
        first_after.audio_path = Some("C:/durable/first.wav".into());
        let mut second_after = second.clone();
        second_after.audio_path = Some("C:/durable/second.wav".into());
        assert!(commit_audio_migration(&path, &[first.clone(), second], &[first_after, second_after]).is_err());
        let stored = load_sessions_from(&path).unwrap();
        assert_eq!(stored[0].audio_path, first.audio_path, "earlier candidate mutation must not leak");
        assert!(!stored[1].retention.audio_cached, "concurrent privacy edit stays authoritative");
        let _ = fs::remove_dir_all(dir);
    }
}
