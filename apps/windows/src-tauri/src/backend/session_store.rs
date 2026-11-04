//! Durable session index storage. Recovery copies are never treated as audio evidence.
use std::collections::HashSet;
use std::fs::{self, File, OpenOptions};
use std::io::ErrorKind;
use std::path::{Path, PathBuf};
use sha2::{Digest, Sha256};
use crate::companion_v1::{CompanionV1HostSession, CompanionV1PersistenceState};

pub struct LoadedIndex {
    pub bytes: Option<Vec<u8>>,
    pub state: CompanionV1PersistenceState,
}

fn sibling(path: &Path, suffix: &str) -> PathBuf {
    let mut name = path.as_os_str().to_os_string();
    name.push(suffix);
    PathBuf::from(name)
}

fn lock(path: &Path) -> Result<File, String> {
    if let Some(parent) = path.parent().filter(|p| !p.as_os_str().is_empty()) {
        fs::create_dir_all(parent).map_err(|e| format!("create session directory: {e}"))?;
    }
    let file = OpenOptions::new().read(true).write(true).create(true).truncate(false)
        .open(sibling(path, ".lock")).map_err(|e| format!("open session lock: {e}"))?;
    file.try_lock().map_err(|e| format!("会议库正被另一进程使用，或无法取得写入锁：{e}"))?;
    Ok(file)
}

fn read_optional(path: &Path) -> Result<Option<Vec<u8>>, String> {
    match fs::read(path) {
        Ok(bytes) => Ok(Some(bytes)),
        Err(e) if e.kind() == ErrorKind::NotFound => Ok(None),
        Err(e) => Err(format!("read {}: {e}", path.display())),
    }
}

fn decode(bytes: &[u8]) -> Result<Vec<CompanionV1HostSession>, String> {
    let sessions: Vec<CompanionV1HostSession> = serde_json::from_slice(bytes)
        .map_err(|e| format!("会话索引格式损坏：{e}"))?;
    let mut ids = HashSet::new();
    if sessions.iter().any(|s| s.id.trim().is_empty() || !ids.insert(&s.id)) {
        return Err("会话索引包含空白或重复的会议标识".to_string());
    }
    Ok(sessions)
}

fn recovered(bytes: Vec<u8>, path: &Path, message: &str) -> LoadedIndex {
    LoadedIndex { bytes: Some(bytes), state: CompanionV1PersistenceState {
        status: "recovered".into(), message: Some(message.into()),
        recovery_path: Some(path.to_string_lossy().into_owned()),
    }}
}

fn load_locked(path: &Path) -> Result<LoadedIndex, String> {
    // A privacy checkpoint is committed before changing either ordinary copy.
    // A crash must finish the requested deletion, never restore its old backup.
    let pending = sibling(path, ".privacy-pending");
    if let Some(bytes) = read_optional(&pending)? {
        decode(&bytes)?;
        return Ok(recovered(bytes, &pending, "已恢复中断的隐私清理结果；请重试保存，完成本地提交。"));
    }
    let primary = read_optional(path)?;
    if let Some(bytes) = primary.as_ref().filter(|bytes| decode(bytes).is_ok()) {
        return Ok(LoadedIndex { bytes: Some(bytes.clone()), state: Default::default() });
    }
    let backup_path = sibling(path, ".bak");
    let backup = read_optional(&backup_path)?;
    if let Some(bytes) = backup.as_ref().filter(|bytes| decode(bytes).is_ok()) {
        return Ok(recovered(bytes.clone(), &backup_path,
            "会话索引无法读取，已载入上一份有效备份。最近一次变更可能缺失；原文件会保留，请重试保存。"));
    }
    if primary.is_some() || backup.is_some() {
        return Err("会话索引及备份均无法读取。原文件已保留，自动处理已暂停；修复文件后可重试恢复。".into());
    }
    Ok(LoadedIndex { bytes: None, state: Default::default() })
}

pub fn load(path: &Path) -> LoadedIndex {
    let result = (|| { let _lock = lock(path)?; load_locked(path) })();
    result.unwrap_or_else(|error| LoadedIndex {
        bytes: None,
        state: CompanionV1PersistenceState { status: "blocked".into(), message: Some(error),
            recovery_path: Some(path.to_string_lossy().into_owned()) },
    })
}

fn removes_private_data(old: &[CompanionV1HostSession], new: &[CompanionV1HostSession]) -> bool {
    old.iter().any(|before| {
        let Some(after) = new.iter().find(|after| after.id == before.id) else { return true; };
        (!before.transcript_text.is_empty() && after.transcript_text.is_empty())
            || before.meeting_notes.iter().any(|note| !after.meeting_notes.iter().any(|n| n.id == note.id && n.text == note.text))
            || (!before.live_transcript_text.is_empty() && after.live_transcript_text.is_empty())
            || (before.minutes.is_some() && after.minutes.is_none())
            || (before.minutes_by_mode.offline_store.is_some() && after.minutes_by_mode.offline_store.is_none())
            || (before.minutes_by_mode.online_live.is_some() && after.minutes_by_mode.online_live.is_none())
            || (before.retention.audio_cached && !after.retention.audio_cached)
            || (before.retention.transcript_cached && !after.retention.transcript_cached)
            || (!before.calendar_copies.is_empty() && after.calendar_copies.is_empty())
            || (before.retention.minutes_cached && !after.retention.minutes_cached)
    })
}

fn preserve_corrupt(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let destination = sibling(path, &format!(".corrupt-{:x}", Sha256::digest(bytes)));
    if let Some(existing) = read_optional(&destination)? {
        if existing != bytes { return Err("损坏索引保留文件冲突；拒绝覆盖".into()); }
        return Ok(());
    }
    super::export::write_atomic(&destination, bytes).map(|_| ())
}

fn clear_corrupt_copies(path: &Path) -> Result<(), String> {
    let parent = path.parent().ok_or("session path has no parent")?;
    let prefix = format!("{}.corrupt-", path.file_name().ok_or("session path has no filename")?.to_string_lossy());
    for entry in fs::read_dir(parent).map_err(|e| format!("list recovery copies: {e}"))? {
        let entry = entry.map_err(|e| format!("read recovery entry: {e}"))?;
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if let Some(hash) = name.strip_prefix(&prefix) {
            if hash.len() == 64 && hash.bytes().all(|c| c.is_ascii_hexdigit()) {
                fs::remove_file(entry.path()).map_err(|e| format!("清除旧的损坏索引副本失败：{e}"))?;
            }
        }
    }
    Ok(())
}

fn save_with(
    path: &Path, sessions: &[CompanionV1HostSession],
    write: impl FnMut(&Path, &[u8]) -> Result<(), String>,
) -> Result<(), String> {
    let _lock = lock(path)?;
    save_locked(path, sessions, write)
}

fn save_locked(
    path: &Path, sessions: &[CompanionV1HostSession],
    mut write: impl FnMut(&Path, &[u8]) -> Result<(), String>,
) -> Result<(), String> {
    let json = serde_json::to_vec_pretty(sessions).map_err(|e| format!("serialize sessions: {e}"))?;
    decode(&json)?;
    let backup_path = sibling(path, ".bak");
    let pending_path = sibling(path, ".privacy-pending");
    // Complete any interrupted privacy transaction before accepting later edits.
    // This prevents a stale deletion checkpoint from hiding a newer meeting.
    if let Some(pending) = read_optional(&pending_path)? {
        let sanitized = decode(&pending)?;
        if removes_private_data(sessions, &sanitized) {
            return Err("待保存内容早于中断的隐私清理；请重新打开应用载入清理结果，拒绝恢复已删除内容".into());
        }
        write(&backup_path, &pending)?;
        write(path, &pending)?;
        clear_corrupt_copies(path)?;
        fs::remove_file(&pending_path).map_err(|e| format!("finish privacy checkpoint: {e}"))?;
    }
    let primary = read_optional(path)?;
    let backup = read_optional(&backup_path)?;
    let previous = match primary.as_deref() {
        Some(bytes) if decode(bytes).is_ok() => Some(bytes),
        Some(bytes) => {
            if !backup.as_deref().is_some_and(|b| decode(b).is_ok()) {
                return Err("索引和备份均损坏，拒绝覆盖原数据；请先恢复会议库".into());
            }
            preserve_corrupt(path, bytes)?;
            backup.as_deref()
        }
        None => {
            if backup.as_deref().is_some_and(|b| decode(b).is_err()) {
                return Err("仅剩的备份已损坏，拒绝建立空索引覆盖恢复线索".into());
            }
            backup.as_deref()
        }
    };
    let privacy_change = previous.map(decode).transpose()?.as_deref()
        .is_some_and(|before| removes_private_data(before, sessions));
    if let Some(before) = previous.map(decode).transpose()? {
        for row in &before {
            if sessions.iter().find(|s|s.id==row.id).is_some_and(|next|
                next.calendar_copy_epoch<row.calendar_copy_epoch ||
                next.calendar_copy_revision<row.calendar_copy_revision ||
                next.calendar_copy_revision==row.calendar_copy_revision&&
                    (next.calendar_copies!=row.calendar_copies||next.calendar_slot_copies!=row.calendar_slot_copies)){
                return Err("磁盘中的日历副本说明已变化；拒绝用旧窗口覆盖，请重新载入后核对。".into());
            }
            if row.organization.protected && !sessions.iter().any(|s|s.id==row.id){
                return Err("磁盘中的受保护录音不能从资料库移除；请先明确解除保护。".into());
            }
            if sessions.iter().find(|s|s.id==row.id).is_some_and(|next|
                next.organization.revision<row.organization.revision||
                next.organization.revision==row.organization.revision&&next.organization!=row.organization){
                return Err("磁盘中的录音分类已变化；拒绝用旧窗口覆盖，请重新载入后核对。".into());
            }
            if sessions.iter().find(|s| s.id == row.id).is_some_and(|next|
                next.note_revision < row.note_revision || (next.note_revision == row.note_revision && next.meeting_notes != row.meeting_notes)) {
                return Err("磁盘中的会议备注已变化；拒绝用旧窗口覆盖，请重新载入后核对。".into());
            }
        }
    }
    if privacy_change {
        write(&pending_path, &json)?;
        write(&backup_path, &json)?;
        write(path, &json)?;
        clear_corrupt_copies(path)?;
        fs::remove_file(&pending_path).map_err(|e| format!("finish privacy checkpoint: {e}"))?;
    } else {
        // Validate before rotating: a damaged primary must never replace a good backup.
        write(&backup_path, previous.unwrap_or(&json))?;
        write(path, &json)?;
    }
    Ok(())
}

/// Bind a confirmed privacy action to the recording data visible when the
/// action began. Reclaimed status may change during cleanup; ownership and
/// contents must not be substituted by a later write.
pub(crate) fn privacy_authorization(row: &CompanionV1HostSession) -> Result<(String, String), String> {
    let mut value=serde_json::json!({
        "audioStored":row.audio_stored,"audioCached":row.retention.audio_cached,
        "audioPath":row.audio_path,"audioBytes":row.audio_bytes,"chunks":row.chunks,
        "deviceKey":row.device_recording_key,"deviceLength":row.device_total_length,
        "deviceHash":row.device_sha256,"transcript":row.transcript_text,
        "liveTranscript":row.live_transcript_text,"notes":row.meeting_notes,
        "minutes":row.minutes,"minutesByMode":row.minutes_by_mode,"organization":row.organization
    });
    // Preserve the historical authorization digest for ordinary sessions.
    if let Some(tracks) = &row.meeting_tracks {
        value.as_object_mut().unwrap().insert("meetingTracks".into(),
            serde_json::to_value(tracks).map_err(|e| format!("核对录音音轨失败：{e}"))?);
    }
    let bytes=serde_json::to_vec(&value).map_err(|e|format!("核对录音清理身份失败：{e}"))?;
    Ok((row.id.clone(),format!("{:x}",Sha256::digest(bytes))))
}

/// Check and write under one lock; a privacy authorization applies only to
/// the exact recording contents visible before the user-requested operation.
pub(crate) fn save_snapshot_checked(path: &Path, sessions: &[CompanionV1HostSession],
    allowed_removals: &[(String,String)], allowed_audio_clear: &[(String,String)]) -> Result<(), String> {
    let _lock = lock(path)?;
    let loaded = load_locked(path)?;
    if let Some(bytes) = loaded.bytes {
        let before = decode(&bytes)?;
        for old in &before {
            let next=sessions.iter().find(|row| row.id == old.id);
            if next.is_none() {
                let authorized=privacy_authorization(old)?;
                if !allowed_removals.contains(&authorized) {
                    return Err("磁盘中有新的或已变化的录音；未覆盖资料，请重新载入后重试。".into());
                }
            }
            if let Some(next) = next {
                let had_audio = old.audio_stored || old.retention.audio_cached;
                let loses_audio = (old.audio_stored && !next.audio_stored)
                    || (old.retention.audio_cached && !next.retention.audio_cached)
                    || (had_audio && old.audio_path.is_some() && next.audio_path.is_none());
                if loses_audio && !allowed_audio_clear.contains(&privacy_authorization(old)?) {
                    return Err("这条录音的原音已在磁盘更新；未覆盖资料，请重新载入后重试。".into());
                }
                let loses_track_data = old.meeting_tracks.as_ref().is_some_and(|previous| {
                    next.meeting_tracks.as_ref().is_none_or(|updated| {
                        previous.root != updated.root
                            || previous.microphone.iter().any(|part| !updated.microphone.contains(part))
                            || previous.system.iter().any(|part| !updated.system.contains(part))
                    })
                });
                if loses_track_data && !allowed_audio_clear.contains(&privacy_authorization(old)?) {
                    return Err("磁盘中的会议音轨已更新；未覆盖原音，请重新载入后重试。".into());
                }
                // The receiver may publish another sealed raw segment without
                // producing a final WAV. A stale same-row snapshot must not
                // erase or alter those exact durable source references.
                let mut has_segment = false;
                let loses_segment = old.chunks.iter().filter(|chunk|
                    chunk.stopped_at.as_deref() == Some("verified-v2-segment")).any(|chunk| {
                        has_segment = true;
                        !next.chunks.iter().any(|candidate| candidate.id == chunk.id
                            && candidate.path == chunk.path && candidate.bytes == chunk.bytes
                            && candidate.duration_ms == chunk.duration_ms
                            && candidate.stopped_at == chunk.stopped_at
                            && matches!(candidate.status.as_str(), "sealed" | "synced"))
                    });
                if (loses_segment || (has_segment && old.device_recording_key != next.device_recording_key))
                    && !allowed_audio_clear.contains(&privacy_authorization(old)?) {
                    return Err("磁盘中的录音分段已更新；未覆盖原音，请重新载入后重试。".into());
                }
            }
        }
    }
    save_locked(path, sessions, |destination, bytes| super::export::write_atomic(destination, bytes).map(|_| ()))
}

pub fn save(path: &Path, sessions: &[CompanionV1HostSession]) -> Result<(), String> {
    save_with(path, sessions, |destination, bytes| super::export::write_atomic(destination, bytes).map(|_| ()))
}

/// The transport commits its verified recording before acknowledging deletion
/// on the device. Hold one lock across read/merge/write so a backlog never loses
/// earlier successful pulls if a later transfer or UI update is interrupted.
pub fn update(path: &Path, edit: impl FnOnce(&mut Vec<CompanionV1HostSession>)) -> Result<(), String> {
    update_checked(path, |sessions| { edit(sessions); Ok(()) })
}

/// A rejected identity merge must leave both ordinary index copies unchanged.
pub(crate) fn update_checked(path: &Path, edit: impl FnOnce(&mut Vec<CompanionV1HostSession>)->Result<(),String>) -> Result<(), String> {
    let _lock = lock(path)?;
    let loaded = load_locked(path)?;
    let mut sessions = loaded.bytes.map(|bytes| decode(&bytes)).transpose()?.unwrap_or_default();
    edit(&mut sessions)?;
    save_locked(path, &sessions, |destination, bytes| super::export::write_atomic(destination, bytes).map(|_| ()))?;
    // An ACK makes the board copy reclaimable, so unlike ordinary UI edits
    // this recording must also exist in the fallback before returning success.
    let json = serde_json::to_vec_pretty(&sessions).map_err(|e| e.to_string())?;
    super::export::write_atomic(&sibling(path, ".bak"), &json).map(|_| ())
}

/// An explicit user-selected backup may repair an entirely unreadable index.
/// Preserve every bad copy first; a valid existing copy is always merged.
pub(crate) fn restore_backup(path:&Path,rows:&[CompanionV1HostSession])->Result<(),String>{
    let _lock=lock(path)?;
    let loaded=load_locked(path);
    let mut current=match loaded {
        Ok(loaded)=>loaded.bytes.map(|b|decode(&b)).transpose()?.unwrap_or_default(),
        Err(original)=>{
            let backup=sibling(path,".bak");let pending=sibling(path,".privacy-pending");
            let copies=[(path.to_path_buf(),read_optional(path)?),(backup.clone(),read_optional(&backup)?),(pending.clone(),read_optional(&pending)?)];
            if copies.iter().all(|(_,b)|b.is_none()) {return Err(original);}
            // A previous explicit restore can have written one valid copy
            // before a later write failed. Retry only that exact result;
            // otherwise never replace an independently valid local index.
            let desired=serde_json::to_vec(rows).map_err(|e|e.to_string())?;
            for (_,bytes) in &copies {
                if let Some(valid)=bytes.as_ref().and_then(|b|decode(b).ok()) {
                    if serde_json::to_vec(&valid).map_err(|e|e.to_string())?!=desired{return Err(original);}
                }
            }
            for (file,bytes) in &copies {if let Some(bytes)=bytes {if decode(bytes).is_err(){preserve_corrupt(file,bytes)?;}}}
            let json=serde_json::to_vec_pretty(rows).map_err(|e|e.to_string())?;decode(&json)?;
            super::export::write_atomic(&backup,&json)?;
            super::export::write_atomic(path,&json)?;
            if pending.exists(){fs::remove_file(&pending).map_err(|e|format!("恢复已保存，但旧清理记录仍需处理：{e}"))?;}
            return Ok(());
        }
    };
    let mut ids=current.iter().map(|r|r.id.clone()).collect::<HashSet<_>>();
    for row in rows {
        if ids.contains(&row.id){
            let old=current.iter().find(|r|r.id==row.id).ok_or("会议身份无效。")?;
            if serde_json::to_vec(old).map_err(|e|e.to_string())?!=serde_json::to_vec(row).map_err(|e|e.to_string())? {
                return Err(format!("本机已有不同版本的“{}”，未覆盖。",row.title));
            }
        }else{ids.insert(row.id.clone());current.push(row.clone());}
    }
    save_locked(path,&current,|destination,bytes|super::export::write_atomic(destination,bytes).map(|_|()))?;
    let json=serde_json::to_vec_pretty(&current).map_err(|e|e.to_string())?;
    super::export::write_atomic(&sibling(path,".bak"),&json).map(|_|())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stale_snapshot_cannot_remove_or_substitute_meeting_tracks() {
        use crate::companion_v1::{CompanionV1MeetingTrackPart, CompanionV1MeetingTracks};
        let path = workspace();
        let mut row = data("meeting-tracks").remove(0);
        row.meeting_tracks = Some(CompanionV1MeetingTracks {
            root: "owned-meeting".into(), state: "captured".into(),
            microphone: vec![CompanionV1MeetingTrackPart { path: "mic-1.wav".into(), first_sample: 0, samples: 20 }],
            system: vec![CompanionV1MeetingTrackPart { path: "system-1.wav".into(), first_sample: 0, samples: 20 }],
            discontinuity: false, issue: None,
        });
        save(&path, &[row.clone()]).unwrap();
        let before = fs::read(&path).unwrap();
        let mut stale = row.clone(); stale.meeting_tracks = None;
        assert!(save_snapshot_checked(&path, &[stale.clone()], &[], &[]).is_err());
        let mut altered = row.clone(); altered.meeting_tracks.as_mut().unwrap().system[0].path = "other.wav".into();
        assert!(save_snapshot_checked(&path, &[altered], &[], &[]).is_err());
        assert_eq!(fs::read(&path).unwrap(), before);
        save_snapshot_checked(&path, &[stale], &[], &[privacy_authorization(&row).unwrap()]).unwrap();
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }

    #[test]
    fn old_sessions_deserialize_without_meeting_tracks() {
        let row = data("legacy").remove(0);
        let mut value = serde_json::to_value(&row).unwrap();
        value.as_object_mut().unwrap().remove("meetingTracks");
        let loaded: CompanionV1HostSession = serde_json::from_value(value).unwrap();
        assert!(loaded.meeting_tracks.is_none());
        assert_eq!(privacy_authorization(&row).unwrap(), privacy_authorization(&loaded).unwrap());
    }

    #[test]
    fn stale_snapshot_preserves_same_recording_new_audio() {
        use crate::companion_v1::{apply_fixture_control,fixture_snapshot,CompanionV1ControlAction};
        let root=std::env::temp_dir().join(format!("companion-same-audio-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();let path=root.join("sessions.json");
        let snapshot=apply_fixture_control(fixture_snapshot(),crate::control_request(CompanionV1ControlAction::MeetingStart,Some("first".into()))).unwrap();
        let mut first=snapshot.host.sessions.into_iter().find(|s|s.id=="first").unwrap();
        first.audio_stored=false;first.audio_path=None;first.retention.audio_cached=false;
        save(&path,&[first.clone()]).unwrap();let stale=vec![first];
        update_checked(&path,|rows|{rows[0].audio_stored=true;rows[0].audio_path=Some("fictional-local.wav".into());rows[0].retention.audio_cached=true;Ok(())}).unwrap();
        let primary=std::fs::read(&path).unwrap();let backup=std::fs::read(root.join("sessions.json.bak")).unwrap();
        assert!(save_snapshot_checked(&path,&stale,&[],&[]).is_err(),"stale snapshot must not discard a newer saved audio reference");
        assert_eq!(std::fs::read(&path).unwrap(),primary);assert_eq!(std::fs::read(root.join("sessions.json.bak")).unwrap(),backup);
        let old_authorization=privacy_authorization(&stale[0]).unwrap();
        assert!(save_snapshot_checked(&path,&stale,&[],&[old_authorization]).is_err(), "old authorization must not cover newer audio");
        assert!(save_snapshot_checked(&path,&[],&[privacy_authorization(&stale[0]).unwrap()],&[]).is_err(), "old delete must not remove a newer recording");
        assert_eq!(std::fs::read(&path).unwrap(),primary);assert_eq!(std::fs::read(root.join("sessions.json.bak")).unwrap(),backup);
        // A new explicit cleanup of the currently observed content is permitted.
        let fresh=decode(&primary).unwrap();let fresh_authorization=privacy_authorization(&fresh[0]).unwrap();
        let mut cleared=fresh.clone();cleared[0].audio_stored=false;cleared[0].retention.audio_cached=false;cleared[0].audio_path=None;
        save_snapshot_checked(&path,&cleared,&[],&[fresh_authorization]).unwrap();
        let cleared=decode(&std::fs::read(&path).unwrap()).unwrap();
        assert!(!cleared[0].audio_stored && !cleared[0].retention.audio_cached);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn ui_snapshot_guard_rejects_unseen_recording_and_allows_exact_delete() {
        use crate::companion_v1::{apply_fixture_control,fixture_snapshot,CompanionV1ControlAction};
        let root=std::env::temp_dir().join(format!("companion-snapshot-guard-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();let path=root.join("sessions.json");
        let snapshot=apply_fixture_control(fixture_snapshot(),crate::control_request(CompanionV1ControlAction::MeetingStart,Some("first".into()))).unwrap();
        let first=snapshot.host.sessions.into_iter().find(|s|s.id=="first").unwrap();
        save(&path,&[first.clone()]).unwrap();let stale=vec![first.clone()];
        let mut newer=first.clone();newer.id="new-recording".into();
        update_checked(&path,|rows|{rows.push(newer);Ok(())}).unwrap();
        let before=std::fs::read(&path).unwrap();let backup=std::fs::read(root.join("sessions.json.bak")).unwrap();
        assert!(save_snapshot_checked(&path,&stale,&[],&[]).is_err());
        assert_eq!(std::fs::read(&path).unwrap(),before);assert_eq!(std::fs::read(root.join("sessions.json.bak")).unwrap(),backup);
        // Confirming deletion of "first" must not authorize deleting a newer row.
        assert!(save_snapshot_checked(&path,&[],&[privacy_authorization(&first).unwrap()],&[]).is_err());
        assert_eq!(std::fs::read(&path).unwrap(),before);
        let mut latest=decode(&before).unwrap();latest.retain(|row|row.id!="first");
        save_snapshot_checked(&path,&latest,&[privacy_authorization(&first).unwrap()],&[]).unwrap();
        let saved=decode(&std::fs::read(&path).unwrap()).unwrap();
        assert_eq!(saved.len(),1);assert_eq!(saved[0].id,"new-recording");
        std::fs::remove_dir_all(root).unwrap();
    }
    fn workspace() -> PathBuf {
        let path = std::env::temp_dir().join(format!("companion-store-{}", uuid::Uuid::new_v4()));
        fs::create_dir_all(&path).unwrap(); path.join("sessions.json")
    }
    fn data(id: &str) -> Vec<CompanionV1HostSession> {
        let request = serde_json::from_value(serde_json::json!({"action": "meetingLoadDemo"})).unwrap();
        let mut data = crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(), request).unwrap().host.sessions;
        data.truncate(1); data[0].id = id.into(); data
    }
    fn write(path: &Path, bytes: &[u8]) -> Result<(), String> { super::super::export::write_atomic(path, bytes).map(|_| ()) }
    #[test]
    fn corrupt_primary_recovers_good_backup_and_preserves_original_bytes() {
        let path = workspace(); let first = data("kept");
        save(&path, &first).unwrap();
        fs::write(&path, b"[{torn").unwrap();
        let report = load(&path);
        assert_eq!(report.state.status, "recovered");
        assert_eq!(decode(&report.bytes.unwrap()).unwrap()[0].id, "kept");
        save(&path, &first).unwrap();
        assert_eq!(load(&path).state.status, "ready");
        let copies: Vec<_> = fs::read_dir(path.parent().unwrap()).unwrap().flatten()
            .filter(|p| p.file_name().to_string_lossy().contains(".corrupt-")).collect();
        assert_eq!(copies.len(), 1); assert_eq!(fs::read(copies[0].path()).unwrap(), b"[{torn");
    }
    #[test]
    fn unreadable_and_invalid_indexes_never_become_an_empty_success() {
        let path = workspace(); fs::write(&path, b"broken").unwrap();
        assert_eq!(load(&path).state.status, "blocked");
        assert!(save(&path, &[]).is_err()); assert_eq!(fs::read(&path).unwrap(), b"broken");
        let duplicate = [data("same")[0].clone(), data("same")[0].clone()];
        assert!(save(&workspace(), &duplicate).is_err());
    }
    #[test]
    fn failed_replacement_keeps_committed_index_and_valid_backup() {
        let path = workspace(); let old = data("old"); save(&path, &old).unwrap();
        let mut new = old.clone(); new[0].title = "new title".into();
        let error = save_with(&path, &new, |dest, bytes| {
            if dest == path { Err("injected disk-full before replace".into()) } else { write(dest, bytes) }
        });
        assert!(error.is_err());
        assert_eq!(decode(&fs::read(&path).unwrap()).unwrap()[0].title, old[0].title);
        assert_eq!(decode(&fs::read(sibling(&path, ".bak")).unwrap()).unwrap()[0].title, old[0].title);
    }
    #[test]
    fn privacy_deletion_cannot_reappear_from_backup_at_any_write_boundary() {
        for fail_at in 1..=4 {
            let path = workspace(); save(&path, &data("private")).unwrap();
            let mut calls = 0;
            let result = save_with(&path, &[], |dest, bytes| {
                calls += 1;
                if calls == fail_at { return Err("injected process interruption".into()); }
                write(dest, bytes)
            });
            let loaded = load(&path);
            let sessions = decode(&loaded.bytes.unwrap()).unwrap();
            if fail_at == 1 { assert!(result.is_err()); assert_eq!(sessions.len(), 1); }
            else {
                assert!(sessions.is_empty(), "deletion must survive once its intent committed");
                save(&path, &[]).unwrap();
                fs::write(&path, b"torn after deletion").unwrap();
                assert!(decode(&load(&path).bytes.unwrap()).unwrap().is_empty());
            }
        }
    }
    #[test]
    fn selective_deletion_retains_other_meetings_and_future_saves() {
        let path = workspace(); let mut sessions = data("delete"); sessions.extend(data("keep"));
        save(&path, &sessions).unwrap(); sessions.remove(0); save(&path, &sessions).unwrap();
        sessions.extend(data("later")); save(&path, &sessions).unwrap();
        assert!(!sibling(&path, ".privacy-pending").exists());
        let restored = decode(&load(&path).bytes.unwrap()).unwrap();
        assert_eq!(restored.iter().map(|s| s.id.as_str()).collect::<Vec<_>>(), vec!["keep", "later"]);
    }
    #[test]
    fn another_process_lock_refuses_write_and_keeps_index() {
        let path = workspace(); save(&path, &data("kept")).unwrap();
        let _held = lock(&path).unwrap();
        assert!(save(&path, &[]).is_err());
        assert_eq!(load(&path).state.status, "blocked");
        assert_eq!(decode(&fs::read(&path).unwrap()).unwrap()[0].id, "kept");
    }

    #[test]
    fn interrupted_privacy_checkpoint_rejects_stale_memory_and_removes_corrupt_copies() {
        let path = workspace(); let old = data("private"); save(&path, &old).unwrap();
        preserve_corrupt(&path, b"private partial JSON").unwrap();
        let result = save_with(&path, &[], |dest, bytes| {
            if dest == path { Err("injected interruption".into()) } else { write(dest, bytes) }
        });
        assert!(result.is_err());
        assert!(save(&path, &old).is_err(), "stale caller cannot resurrect a committed deletion");
        assert!(decode(&load(&path).bytes.unwrap()).unwrap().is_empty());
        save(&path, &[]).unwrap();
        assert!(!fs::read_dir(path.parent().unwrap()).unwrap().flatten()
            .any(|entry| entry.file_name().to_string_lossy().contains(".corrupt-")));
    }
}
