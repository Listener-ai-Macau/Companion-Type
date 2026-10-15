//! Durable product-audio ownership and conservative legacy Temp migration.
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::companion_v1::CompanionV1HostSession;

const RECORDING_DIR_ENV: &str = "COMPANION_TYPE_RECORDING_DIR";
const LEDGER_FILE: &str = ".legacy-audio-copies.json";
const LOCK_FILE: &str = ".audio-storage.lock";

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct LegacyCopy {
    current_path: String,
    legacy_path: String,
    bytes: u64,
    sha256: String,
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct MigrationLedger {
    #[serde(default)]
    copies: Vec<LegacyCopy>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub(crate) struct MigrationOutcome {
    pub migrated: usize,
    /// Sessions backed by the migration ledger. Recommit these even when the
    /// primary already has the new path, because a prior crash may have left
    /// the fallback index pointing at cleanup-prone Temp.
    pub ledger_backed: usize,
}

pub(crate) fn has_recording_dir_override() -> bool {
    std::env::var_os(RECORDING_DIR_ENV).is_some()
}

/// The only directory where new product audio may be created. Production
/// fails closed when LocalAppData is unavailable; Temp is not durable enough
/// to be the sole copy after an exact board reclaim.
pub(crate) fn recording_root() -> Result<PathBuf, String> {
    let root = if let Some(path) = std::env::var_os(RECORDING_DIR_ENV) {
        PathBuf::from(path)
    } else {
        let local = std::env::var_os("LOCALAPPDATA")
            .filter(|value| !value.is_empty())
            .ok_or("LOCALAPPDATA is unavailable; refusing temporary recording storage")?;
        PathBuf::from(local).join("Companion Type").join("recordings")
    };
    if !root.is_absolute() {
        return Err(format!("recording directory must be absolute: {}", root.display()));
    }
    fs::create_dir_all(&root)
        .map_err(|error| format!("create durable recording directory {}: {error}", root.display()))?;
    root.canonicalize()
        .map_err(|error| format!("resolve durable recording directory {}: {error}", root.display()))
}

fn legacy_recording_root() -> Result<PathBuf, String> {
    let root = std::env::temp_dir().join("companion-type").join("recordings");
    if !root.is_absolute() { return Err("legacy recording root is not absolute".into()); }
    Ok(root.canonicalize().unwrap_or(root))
}

fn path_key(path: &Path) -> String {
    let text = path.to_string_lossy().replace('/', "\\");
    let text = text.strip_prefix("\\\\?\\").unwrap_or(&text);
    if cfg!(windows) { text.to_ascii_lowercase() } else { text.to_string() }
}

fn same_path(left: &Path, right: &Path) -> bool { path_key(left) == path_key(right) }

fn direct_child(path: &Path, root: &Path) -> bool {
    path.parent().is_some_and(|parent| same_path(parent, root)) && path.file_name().is_some()
}

pub(crate) fn owned_recording_reference(path: &Path, root: &Path) -> bool {
    if !path.is_absolute() { return false; }
    let Ok(root) = root.canonicalize() else { return false; };
    let Some(parent) = path.parent() else { return false; };
    let parent = parent.canonicalize().unwrap_or_else(|_| parent.to_path_buf());
    same_path(&parent, &root) && path.file_name().is_some()
}

fn path_text(path: &Path) -> String {
    path.to_string_lossy().into_owned()
}

fn fingerprint(path: &Path) -> Result<(u64, String), String> {
    let mut file = File::open(path).map_err(|error| format!("open audio {}: {error}", path.display()))?;
    let before = file.metadata().map_err(|error| format!("inspect audio {}: {error}", path.display()))?;
    if !before.is_file() { return Err(format!("audio is not a file: {}", path.display())); }
    let mut hasher = Sha256::new();
    let mut bytes = 0u64;
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let count = file.read(&mut buffer)
            .map_err(|error| format!("read audio {}: {error}", path.display()))?;
        if count == 0 { break; }
        hasher.update(&buffer[..count]);
        bytes = bytes.saturating_add(count as u64);
    }
    let after = file.metadata().map_err(|error| format!("recheck audio {}: {error}", path.display()))?;
    if before.len() != bytes || after.len() != bytes || before.modified().ok() != after.modified().ok() {
        return Err(format!("audio changed while it was verified: {}", path.display()));
    }
    Ok((bytes, format!("{:x}", hasher.finalize())))
}

fn load_ledger(root: &Path) -> Result<MigrationLedger, String> {
    let path = root.join(LEDGER_FILE);
    match fs::read(&path) {
        Ok(bytes) => serde_json::from_slice(&bytes)
            .map_err(|error| format!("legacy audio ledger is damaged at {}: {error}", path.display())),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(MigrationLedger::default()),
        Err(error) => Err(format!("read legacy audio ledger {}: {error}", path.display())),
    }
}

fn save_ledger(root: &Path, ledger: &MigrationLedger) -> Result<(), String> {
    let bytes = serde_json::to_vec_pretty(ledger)
        .map_err(|error| format!("serialize legacy audio ledger: {error}"))?;
    super::export::write_atomic(&root.join(LEDGER_FILE), &bytes).map(|_| ())
}

fn lock_storage(root: &Path) -> Result<File, String> {
    let file = OpenOptions::new().read(true).write(true).create(true).truncate(false)
        .open(root.join(LOCK_FILE)).map_err(|error| format!("open audio storage lock: {error}"))?;
    file.try_lock().map_err(|error| format!("audio storage is in use: {error}"))?;
    Ok(file)
}

fn product_owned_legacy_audio(session: &CompanionV1HostSession, source: &Path, bytes: u64) -> bool {
    if !session.audio_stored || !session.retention.audio_cached || session.audio_bytes != bytes {
        return false;
    }
    if !matches!(session.source.as_str(), "deviceFlash" | "boardDevice" | "hostMicrophone") {
        return false;
    }
    if session.device_recording_id.is_some() { return true; }
    let mut found = false;
    let mut declared_bytes = 0u64;
    for chunk in &session.chunks {
        let same_file = chunk.path.as_deref().and_then(|value| Path::new(value).canonicalize().ok())
            .is_some_and(|path| path == source);
        if same_file {
            if !matches!(chunk.status.as_str(), "sealed" | "synced") { return false; }
            found = true;
            declared_bytes = match declared_bytes.checked_add(chunk.bytes) {
                Some(value) => value,
                None => return false,
            };
        }
    }
    found && declared_bytes == bytes
}

fn product_owned_missing_legacy_audio(
    session: &CompanionV1HostSession, source: &Path, bytes: u64,
) -> bool {
    if !session.audio_stored || !session.retention.audio_cached || session.audio_bytes != bytes
        || !matches!(session.source.as_str(), "deviceFlash" | "boardDevice" | "hostMicrophone") {
        return false;
    }
    if session.device_recording_id.is_some() { return true; }
    let matching: Vec<_> = session.chunks.iter().filter(|chunk| {
        chunk.path.as_deref().is_some_and(|path| Path::new(path) == source)
    }).collect();
    !matching.is_empty()
        && matching.iter().all(|chunk| matches!(chunk.status.as_str(), "sealed" | "synced"))
        && matching.iter().try_fold(0u64, |total, chunk| total.checked_add(chunk.bytes)) == Some(bytes)
}

fn copy_verified(source: &Path, destination: &Path, expected: &(u64, String)) -> Result<(), String> {
    if destination.exists() {
        super::meeting_workspace::validate_wav(destination)?;
        if fingerprint(destination)? == *expected { return Ok(()); }
        return Err(format!("durable recording conflicts with different content: {}", destination.display()));
    }
    let temporary = destination.with_file_name(format!(
        ".{}.{}.migrating",
        destination.file_name().ok_or("recording destination has no filename")?.to_string_lossy(),
        Uuid::new_v4()
    ));
    let result = (|| {
        let mut input = File::open(source).map_err(|error| format!("open legacy audio: {error}"))?;
        let mut output = OpenOptions::new().write(true).create_new(true).open(&temporary)
            .map_err(|error| format!("create migration file {}: {error}", temporary.display()))?;
        std::io::copy(&mut input, &mut output)
            .map_err(|error| format!("copy legacy audio to {}: {error}", temporary.display()))?;
        output.flush().map_err(|error| format!("flush migrated audio: {error}"))?;
        output.sync_all().map_err(|error| format!("sync migrated audio: {error}"))?;
        drop(output);
        super::meeting_workspace::validate_wav(&temporary)?;
        if fingerprint(&temporary)? != *expected { return Err("migrated audio did not match its source".into()); }
        fs::rename(&temporary, destination)
            .map_err(|error| format!("commit migrated audio {}: {error}", destination.display()))
    })();
    if result.is_err() { let _ = fs::remove_file(&temporary); }
    result
}

/// Copy only indexed product WAVs that are direct children of the historical
/// owned Temp root. The source remains because an older index backup can refer
/// to it. The caller commits the returned sessions only after this succeeds.
pub(crate) fn migrate_legacy_sessions(
    sessions: &[CompanionV1HostSession], destination_root: &Path, legacy_root: &Path,
) -> Result<(Vec<CompanionV1HostSession>, MigrationOutcome), String> {
    let destination_root = destination_root.canonicalize()
        .map_err(|error| format!("resolve migration destination: {error}"))?;
    let legacy_root = legacy_root.canonicalize().unwrap_or_else(|_| legacy_root.to_path_buf());
    if !legacy_root.is_absolute() { return Err("legacy recording root must be absolute".into()); }
    let _lock = lock_storage(&destination_root)?;
    let mut ledger = load_ledger(&destination_root)?;
    let mut updated = sessions.to_vec();
    let mut outcome = MigrationOutcome::default();
    for session in &mut updated {
        let Some(raw) = session.audio_path.clone() else { continue; };
        let raw_source = PathBuf::from(&raw);
        if !raw_source.is_absolute() || raw_source.extension().is_none_or(|ext| !ext.eq_ignore_ascii_case("wav")) { continue; }
        let source_parent_owned = raw_source.parent().is_some_and(|parent| {
            let resolved = parent.canonicalize().unwrap_or_else(|_| parent.to_path_buf());
            same_path(&resolved, &legacy_root)
        });
        if !source_parent_owned { continue; }
        let source = match raw_source.canonicalize() {
            Ok(source) => source,
            Err(_) => {
                // The primary may be damaged and recovery may load an old
                // backup after Temp cleanup. Recover that exact pointer only
                // from a previously committed ledger entry and verified
                // durable bytes; basename alone never grants ownership.
                let Some(record) = ledger.copies.iter().find(|record| {
                    record.bytes == session.audio_bytes
                        && product_owned_missing_legacy_audio(session, &raw_source, record.bytes)
                        &&
                    Path::new(&record.legacy_path).file_name() == raw_source.file_name()
                        && Path::new(&record.legacy_path).parent().is_some_and(|parent| {
                            let resolved = parent.canonicalize().unwrap_or_else(|_| parent.to_path_buf());
                            same_path(&resolved, &legacy_root)
                        })
                }).cloned() else { continue; };
                let current = PathBuf::from(&record.current_path);
                let Ok(current) = current.canonicalize() else { continue; };
                if !direct_child(&current, &destination_root)
                    || fingerprint(&current)? != (record.bytes, record.sha256) {
                    continue;
                }
                session.audio_path = Some(path_text(&current));
                for chunk in &mut session.chunks {
                    if chunk.path.as_deref().is_some_and(|path| Path::new(path) == raw_source) {
                        chunk.path = session.audio_path.clone();
                    }
                }
                outcome.migrated += 1;
                continue;
            }
        };
        if !direct_child(&source, &legacy_root) { continue; }
        super::meeting_workspace::validate_wav(&source)?;
        let expected = fingerprint(&source)?;
        if !product_owned_legacy_audio(session, &source, expected.0) { continue; }
        let destination = destination_root.join(source.file_name().ok_or("legacy WAV has no filename")?);
        copy_verified(&source, &destination, &expected)?;
        let destination = destination.canonicalize()
            .map_err(|error| format!("resolve migrated audio: {error}"))?;
        let record = LegacyCopy { current_path: path_text(&destination), legacy_path: path_text(&source),
            bytes: expected.0, sha256: expected.1 };
        if !ledger.copies.contains(&record) {
            ledger.copies.push(record);
            save_ledger(&destination_root, &ledger)?;
        }
        session.audio_path = Some(path_text(&destination));
        for chunk in &mut session.chunks {
            if chunk.path.as_deref().and_then(|path| Path::new(path).canonicalize().ok())
                .is_some_and(|path| path == source) {
                chunk.path = session.audio_path.clone();
            }
        }
        outcome.migrated += 1;
    }
    for session in &updated {
        let Some(raw) = session.audio_path.as_deref() else { continue; };
        let Ok(current) = Path::new(raw).canonicalize() else { continue; };
        let Ok(identity) = fingerprint(&current) else { continue; };
        if ledger.copies.iter().any(|record| {
            Path::new(&record.current_path).canonicalize().ok().as_deref().is_some_and(|path| same_path(path, &current))
                && (record.bytes, record.sha256.clone()) == identity
        }) {
            outcome.ledger_backed += 1;
        }
    }
    Ok((updated, outcome))
}

pub(crate) fn migrate_production_sessions(
    sessions: &[CompanionV1HostSession],
) -> Result<(Vec<CompanionV1HostSession>, MigrationOutcome), String> {
    if has_recording_dir_override() { return Ok((sessions.to_vec(), MigrationOutcome::default())); }
    let root = recording_root()?;
    let legacy = match legacy_recording_root() {
        Ok(path) => path,
        Err(_) => return Ok((sessions.to_vec(), MigrationOutcome::default())),
    };
    migrate_legacy_sessions(sessions, &root, &legacy)
}

/// Return current owned audio plus only ledger-confirmed legacy copies whose
/// bytes still match. There is deliberately no directory scan or basename match.
pub(super) fn privacy_delete_targets_with_legacy(
    current: &Path, root: &Path, legacy_root: &Path,
) -> Result<Vec<PathBuf>, String> {
    let root = root.canonicalize().map_err(|error| format!("resolve recording root: {error}"))?;
    let legacy_root = legacy_root.canonicalize().unwrap_or_else(|_| legacy_root.to_path_buf());
    if !legacy_root.is_absolute() { return Err("legacy recording root must be absolute".into()); }
    // A prior delete may already have removed the primary before ledger
    // publication failed. Resolve its owned parent so retry can still finish.
    if !owned_recording_reference(current, &root) { return Err("recording is outside the owned root".into()); }
    let current = match current.canonicalize() {
        Ok(path) => {
            if !direct_child(&path, &root) { return Err("recording is outside the owned root".into()); }
            fingerprint(&path)?;
            path
        },
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => root.join(current.file_name().ok_or("recording has no filename")?),
        Err(error) => return Err(format!("resolve recording: {error}")),
    };
    if !direct_child(&current, &root) { return Err("recording is outside the owned root".into()); }
    let _lock = lock_storage(&root)?;
    let ledger = load_ledger(&root)?;
    let mut targets: Vec<PathBuf> = Vec::new();
    for copy in ledger.copies {
        if !same_path(Path::new(&copy.current_path), &current) { continue; }
        let legacy = match PathBuf::from(copy.legacy_path).canonicalize() {
            Ok(path) => path,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
            Err(error) => return Err(format!("resolve legacy audio: {error}")),
        };
        if direct_child(&legacy, &legacy_root)
            && fingerprint(&legacy)? == (copy.bytes, copy.sha256)
            && !targets.iter().any(|path| same_path(path, &legacy)) {
            targets.push(legacy);
        }
    }
    // Current is deliberately last. If an old-copy deletion fails, privacy.rs
    // leaves current intact so a retry can still resolve its migration ledger.
    targets.push(current);
    Ok(targets)
}

pub(crate) fn privacy_delete_targets(current: &Path, root: &Path) -> Result<Vec<PathBuf>, String> {
    match legacy_recording_root() {
        Ok(legacy) => privacy_delete_targets_with_legacy(current, root, &legacy),
        Err(_) => {
            let root = root.canonicalize().map_err(|error| format!("resolve recording root: {error}"))?;
            let current = current.canonicalize().map_err(|error| format!("resolve recording: {error}"))?;
            if !direct_child(&current, &root) { return Err("recording is outside the owned root".into()); }
            Ok(vec![current])
        }
    }
}

pub(crate) fn forget_deleted_migration(current: &Path, root: &Path) -> Result<(), String> {
    let root = root.canonicalize().map_err(|error| format!("resolve recording root: {error}"))?;
    let _lock = lock_storage(&root)?;
    let mut ledger = load_ledger(&root)?;
    let before = ledger.copies.len();
    ledger.copies.retain(|copy| !same_path(Path::new(&copy.current_path), current));
    if ledger.copies.len() != before { save_ledger(&root, &ledger)?; }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{CompanionV1AudioChunk, CompanionV1SessionRetention};

    fn write_wav(path: &Path, sample: u8) {
        let mut bytes = vec![0u8; 46];
        bytes[0..4].copy_from_slice(b"RIFF");
        bytes[4..8].copy_from_slice(&38u32.to_le_bytes());
        bytes[8..12].copy_from_slice(b"WAVE");
        bytes[12..16].copy_from_slice(b"fmt ");
        bytes[16..20].copy_from_slice(&16u32.to_le_bytes());
        bytes[20..22].copy_from_slice(&1u16.to_le_bytes());
        bytes[22..24].copy_from_slice(&1u16.to_le_bytes());
        bytes[24..28].copy_from_slice(&16_000u32.to_le_bytes());
        bytes[28..32].copy_from_slice(&32_000u32.to_le_bytes());
        bytes[32..34].copy_from_slice(&2u16.to_le_bytes());
        bytes[34..36].copy_from_slice(&16u16.to_le_bytes());
        bytes[36..40].copy_from_slice(b"data");
        bytes[40..44].copy_from_slice(&2u32.to_le_bytes());
        bytes[44] = sample;
        bytes[45] = sample;
        fs::write(path, bytes).unwrap();
    }

    fn product_session(path: &Path) -> CompanionV1HostSession {
        let bytes = fs::metadata(path).unwrap().len();
        CompanionV1HostSession { recorder_control: None, recorder_control_uncertain: false, device_recording_key: None, 
            transcript_review: None,
            bookmark_revision: 0, bookmarks: vec![],
            note_revision: 0, meeting_notes: vec![],
            id: "legacy-audio".into(), title: "Legacy audio".into(), source: "hostMicrophone".into(),
            status: "captured".into(), meeting_mode: "offlineStore".into(), pending_reason: None,
            started_at: None, stopped_at: None, duration_ms: 1, audio_path: Some(path_text(path)),
            audio_bytes: bytes, audio_stored: true, device_recording_id: None,
            device_total_length: None, device_sha256: None, device_reclaimed: false, capture_incomplete: false, source_device_id: None,
            chunks: vec![CompanionV1AudioChunk { id: "legacy-sealed".into(), path: Some(path_text(path)),
                started_at: None, stopped_at: None, duration_ms: 1, bytes, status: "sealed".into() }],
            transcript_text: String::new(), transcript_final: false, live_transcript_text: String::new(),
            transcript_preview: String::new(), transcript_segments: 0, utterances: vec![], minutes: None,
            minutes_by_mode: Default::default(), recovery: Default::default(), export_markdown: String::new(),
            exported_at: None, retention: CompanionV1SessionRetention { audio_cached: true,
                transcript_cached: false, minutes_cached: false, consent_required: true,
                retention_label: "local".into(), expires_at: None },
        }
    }

    fn roots(name: &str) -> (PathBuf, PathBuf) {
        let base = std::env::temp_dir().join(format!("companion-audio-{name}-{}", Uuid::new_v4()));
        let old = base.join("old");
        let new = base.join("new");
        fs::create_dir_all(&old).unwrap();
        fs::create_dir_all(&new).unwrap();
        (old, new)
    }

    #[test]
    fn migration_is_idempotent_and_retains_precise_old_copy() {
        let (old, new) = roots("idempotent");
        let source = old.join("meeting.wav");
        write_wav(&source, 7);
        let original = product_session(&source);
        let (first, outcome) = migrate_legacy_sessions(&[original], &new, &old).unwrap();
        assert_eq!(outcome.migrated, 1);
        assert!(source.exists(), "old index backup may still need this copy");
        let current = PathBuf::from(first[0].audio_path.as_ref().unwrap());
        assert!(current.exists());
        assert_eq!(first[0].chunks[0].path.as_deref(), first[0].audio_path.as_deref());
        let (second, second_outcome) = migrate_legacy_sessions(&first, &new, &old).unwrap();
        assert_eq!(second[0].audio_path, first[0].audio_path);
        assert_eq!(second_outcome.ledger_backed, 1, "restart must recommit the fallback index");
        let targets = privacy_delete_targets_with_legacy(&current, &new, &old).unwrap();
        assert_eq!(targets.len(), 2);
        assert!(targets.contains(&source.canonicalize().unwrap()));
        for target in targets { fs::remove_file(target).unwrap(); }
        assert!(!current.exists() && !source.exists(), "privacy deletion removes both exact copies");
    }

    #[test]
    fn old_backup_pointer_recovers_from_ledger_after_temp_cleanup() {
        let (old, new) = roots("backup-recovery");
        let source = old.join("meeting.wav");
        write_wav(&source, 7);
        let old_index_session = product_session(&source);
        let (first, _) = migrate_legacy_sessions(&[old_index_session.clone()], &new, &old).unwrap();
        fs::remove_file(&source).unwrap();
        fs::remove_dir(&old).unwrap();
        let (recovered, outcome) = migrate_legacy_sessions(&[old_index_session], &new, &old).unwrap();
        assert_eq!(outcome.migrated, 1);
        assert_eq!(outcome.ledger_backed, 1);
        assert_eq!(recovered[0].audio_path, first[0].audio_path);
        assert!(Path::new(recovered[0].audio_path.as_ref().unwrap()).exists());
    }

    #[test]
    fn migration_commit_keeps_primary_and_backup_on_durable_path() {
        let (old, new) = roots("index-commit");
        let source = old.join("meeting.wav");
        write_wav(&source, 7);
        let original = product_session(&source);
        let state = new.parent().unwrap().join("sessions.json");
        super::super::session_store::save(&state, &[original.clone()]).unwrap();
        let (migrated, _) = migrate_legacy_sessions(&[original], &new, &old).unwrap();
        super::super::session_store::update(&state, |sessions| *sessions = migrated.clone()).unwrap();
        let backup = PathBuf::from(format!("{}.bak", state.display()));
        for path in [&state, &backup] {
            let sessions: Vec<CompanionV1HostSession> = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
            assert_eq!(sessions[0].audio_path, migrated[0].audio_path);
        }
        fs::remove_file(&source).unwrap();
        fs::write(&state, b"damaged primary").unwrap();
        let recovered = super::super::session_store::load(&state);
        let sessions: Vec<CompanionV1HostSession> = serde_json::from_slice(&recovered.bytes.unwrap()).unwrap();
        assert_eq!(sessions[0].audio_path, migrated[0].audio_path);
    }

    #[test]
    fn logical_chunks_sharing_one_wav_are_owned_by_their_total_bytes() {
        let (old, new) = roots("logical-chunks");
        let source = old.join("long.wav");
        write_wav(&source, 7);
        let mut original = product_session(&source);
        original.chunks[0].bytes = 20;
        let mut second = original.chunks[0].clone();
        second.id = "legacy-sealed-2".into();
        second.bytes = original.audio_bytes - 20;
        original.chunks.push(second);
        let (migrated, outcome) = migrate_legacy_sessions(&[original], &new, &old).unwrap();
        assert_eq!(outcome.migrated, 1);
        assert_eq!(migrated[0].chunks.len(), 2);
        assert!(migrated[0].chunks.iter().all(|chunk| chunk.path == migrated[0].audio_path));
    }

    #[test]
    fn conflicting_destination_fails_without_mutating_pointer_or_source() {
        let (old, new) = roots("conflict");
        let source = old.join("meeting.wav");
        write_wav(&source, 7);
        write_wav(&new.join("meeting.wav"), 8);
        let original = product_session(&source);
        assert!(migrate_legacy_sessions(&[original.clone()], &new, &old).is_err());
        assert_eq!(original.audio_path.as_deref(), Some(path_text(&source).as_str()));
        assert!(source.exists());
    }

    #[test]
    fn nested_external_and_unowned_audio_are_not_migrated() {
        let (old, new) = roots("external");
        let nested = old.join("nested");
        fs::create_dir_all(&nested).unwrap();
        let nested_wav = nested.join("meeting.wav");
        write_wav(&nested_wav, 7);
        let original = product_session(&nested_wav);
        let (unchanged, outcome) = migrate_legacy_sessions(&[original.clone()], &new, &old).unwrap();
        assert_eq!(outcome.migrated, 0);
        assert_eq!(unchanged[0].audio_path, original.audio_path);

        let direct = old.join("unowned.wav");
        write_wav(&direct, 7);
        let mut unowned = product_session(&direct);
        unowned.source = "importedFile".into();
        let (unchanged, outcome) = migrate_legacy_sessions(&[unowned.clone()], &new, &old).unwrap();
        assert_eq!(outcome.migrated, 0);
        assert_eq!(unchanged[0].audio_path, unowned.audio_path);
    }

    #[test]
    fn privacy_never_deletes_same_name_legacy_file_after_content_changes() {
        let (old, new) = roots("privacy-content");
        let source = old.join("meeting.wav");
        write_wav(&source, 7);
        let (migrated, _) = migrate_legacy_sessions(&[product_session(&source)], &new, &old).unwrap();
        let current = PathBuf::from(migrated[0].audio_path.as_ref().unwrap());
        write_wav(&source, 9);
        let targets = privacy_delete_targets_with_legacy(&current, &new, &old).unwrap();
        assert_eq!(targets, vec![current.canonicalize().unwrap()]);
        fs::remove_file(&targets[0]).unwrap();
        assert!(source.exists(), "same basename with different bytes is not the migrated copy");
    }
}
