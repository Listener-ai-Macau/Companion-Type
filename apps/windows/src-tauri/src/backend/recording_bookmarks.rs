//! User-authored points on the original audio timeline, independent of ASR.
use serde::{Deserialize, Serialize};
use crate::companion_v1::CompanionV1HostSession;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Bookmark {
    pub id: String,
    pub label: String,
    pub position_ms: u64,
    /// Playback/ASR timeline. Live capture keeps its original board position.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audio_position_ms: Option<u64>,
    pub created_at: String,
    pub origin: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_device_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub recording_id: Option<u32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_sha256: Option<String>,
    #[serde(default,skip_serializing_if="Option::is_none")]
    pub source_recording_key: Option<crate::companion_v1::CompanionV1RecordingKey>,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub enum Action { AddLive, AddAt, Rename, Delete }

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Request {
    pub session_id: String,
    pub bookmark_id: String,
    pub expected_revision: u64,
    pub action: Action,
    pub label: Option<String>,
    pub position_ms: Option<u64>,
}

/// Constructed by the native board reader/worker, never deserialized from IPC.
pub struct LiveStamp {
    pub(crate) session_id: String,
    pub(crate) device_id: String,
    pub(crate) recording_id: u32,
    pub(crate) position_ms: u64,
}

fn label(request: &Request) -> Result<String, String> {
    let value = request.label.as_deref().unwrap_or("重点").trim();
    if value.is_empty() || value.chars().count() > 120 || value.chars().any(char::is_control) {
        return Err("重点名称请填写1到120个字符，不含换行。".into());
    }
    Ok(value.into())
}

pub(crate) fn validate_request(session: &CompanionV1HostSession, request: &Request) -> Result<(), String> {
    if request.session_id != session.id || uuid::Uuid::parse_str(&request.bookmark_id).is_err() {
        return Err("重点所属会议或请求标识无效；未修改其他会议。".into());
    }
    if session.bookmarks.len() > 1024 { return Err("会议重点数据异常，请保留原文件后检查。".into()); }
    if request.action != Action::Delete { label(request)?; }
    if request.action == Action::AddLive && request.position_ms.is_some() {
        return Err("录音中重点的时间由设备取得，不能指定或估算。".into());
    }
    Ok(())
}

pub(crate) fn duplicate(session: &CompanionV1HostSession, request: &Request) -> Result<bool, String> {
    validate_request(session, request)?;
    let old = session.bookmarks.iter().find(|b| b.id == request.bookmark_id);
    if request.action == Action::Delete { return Ok(old.is_none()); }
    if request.action == Action::Rename { return Ok(old.is_some_and(|p| label(request).is_ok_and(|label| p.label == label))); }
    let Some(old) = old else { return Ok(false); };
    if old.label == label(request)? && match request.action {
        Action::AddLive => old.origin == "boardRecording",
        Action::AddAt => old.origin == "playback" && request.position_ms == Some(old.position_ms),
        _ => false,
    } { return Ok(true); }
    Err("这个重点请求已用于其他内容，请刷新后再操作。".into())
}

pub(crate) fn apply(session: &mut CompanionV1HostSession, request: &Request,
    stamp: Option<&LiveStamp>, playback_duration_ms: Option<u64>, now: &str) -> Result<bool, String> {
    if duplicate(session, request)? { return Ok(false); }
    if request.expected_revision != session.bookmark_revision {
        return Err("会议重点已变化；你的输入仍保留，请刷新后核对。".into());
    }
    let revision = session.bookmark_revision.checked_add(1).ok_or("重点版本已超出范围。")?;
    let mut next = session.bookmarks.clone();
    match request.action {
        Action::AddLive | Action::AddAt => {
            if next.len() >= 1024 { return Err("这场会议已有1024个重点，请整理后再添加。".into()); }
            let (position_ms, origin) = if request.action == Action::AddLive {
                let stamp = stamp.ok_or("尚未取得这场设备录音的实际时间，请重试。")?;
                if stamp.session_id != session.id || stamp.recording_id == 0
                    || session.device_recording_id != Some(stamp.recording_id)
                    || session.source_device_id.as_deref().is_none_or(|s| !super::device_connection::same_device_id(s, &stamp.device_id))
                    || stamp.position_ms == 0 {
                    return Err("设备录音身份或时间已变化；未将重点写入其他录音。".into());
                }
                (stamp.position_ms, "boardRecording")
            } else {
                let position = request.position_ms.ok_or("请选择原音中的实际时间点。")?;
                if session.status == "recording" || playback_duration_ms.is_none_or(|limit| position > limit) {
                    return Err("这个时间点不在已保存的原音中，请重新准备回听。".into());
                }
                (position, "playback")
            };
            next.push(Bookmark { id: request.bookmark_id.clone(), label: label(request)?, position_ms,
                audio_position_ms: (request.action == Action::AddAt).then_some(position_ms),
                created_at: now.into(), origin: origin.into(), source_device_id: session.source_device_id.clone(),
                recording_id: session.device_recording_id, source_sha256: session.device_sha256.clone(),source_recording_key:None });
            next.sort_by_key(|b| b.position_ms);
        }
        Action::Rename => {
            let point = next.iter_mut().find(|b| b.id == request.bookmark_id).ok_or("这个重点已不存在。")?;
            point.label = label(request)?;
        }
        Action::Delete => {
            let before = next.len();
            next.retain(|b| b.id != request.bookmark_id);
            if next.len() == before { return Err("这个重点已不存在，请刷新。".into()); }
        }
    }
    session.bookmarks = next;
    session.bookmark_revision = revision;
    Ok(true)
}

pub(crate) fn bind_received(session: &mut CompanionV1HostSession) {
    if !session.bookmarks.iter().any(|b| b.origin == "boardRecording" && b.audio_position_ms.is_none()) { return; }
    let timing = received_timing(session);
    for bookmark in &mut session.bookmarks {
        if bookmark.source_sha256.is_none() && bookmark.recording_id == session.device_recording_id
            && bookmark.source_device_id.as_deref().zip(session.source_device_id.as_deref())
                .is_some_and(|(a,b)| super::device_connection::same_device_id(a,b)) {
            bookmark.source_sha256 = session.device_sha256.clone();
        }
        if bookmark.origin == "boardRecording" && bookmark.source_sha256.is_some()
            && bookmark.source_sha256 == session.device_sha256
            && bookmark.recording_id == session.device_recording_id
            && bookmark.source_device_id.as_deref().zip(session.source_device_id.as_deref())
                .is_some_and(|(a,b)| super::device_connection::same_device_id(a,b)) {
            if let Some((capture_duration, skip)) = timing {
                if bookmark.position_ms <= capture_duration {
                    bookmark.audio_position_ms = Some(bookmark.position_ms.saturating_sub(skip));
                }
            }
        }
    }
}

pub(crate) enum CommitError { Conflict(String), Storage(String) }

pub(crate) fn commit(session: &mut CompanionV1HostSession, expected_revision:u64) -> Result<(),CommitError> {
    if cfg!(test) && std::env::var("COMPANION_TYPE_STATE_PATH").is_err() { return Ok(()); }
    commit_to(&super::persistence::state_file_path(), session, expected_revision)
}

fn commit_to(path: &std::path::Path, session:&mut CompanionV1HostSession, expected_revision:u64) -> Result<(),CommitError> {
    let mut conflict = None;
    let mut committed = None;
    let result = super::session_store::update_checked(path, |rows| {
        let fail = "磁盘中的会议重点或录音身份已变化；你的输入仍保留，请重新载入后核对。";
        let Some(row) = rows.iter_mut().find(|r| r.id == session.id) else {
            conflict=Some(fail.to_string()); return Err(fail.into());
        };
        if row.bookmark_revision != expected_revision
            || row.device_recording_id != session.device_recording_id
            || row.source_device_id != session.source_device_id {
            conflict=Some(fail.to_string()); return Err(fail.into());
        }
        row.bookmarks=session.bookmarks.clone(); row.bookmark_revision=session.bookmark_revision;
        row.exported_at=None;
        bind_received(row);
        committed=Some(row.bookmarks.clone());
        Ok(())
    });
    if let Some(error)=conflict { return Err(CommitError::Conflict(error)); }
    result.map_err(CommitError::Storage)?;
    if let Some(points)=committed { session.bookmarks=points; }
    Ok(())
}

/// Validate the sealed COP1 artifact without allocating a long recording.
/// The product decoder drops its first frame; other containers are deliberately
/// left unmapped until their decoder timing is known.
fn received_timing(session: &CompanionV1HostSession) -> Option<(u64,u64)> {
    use std::io::Read;
    use sha2::{Digest, Sha256};
    if !session.audio_stored || !session.retention.audio_cached { return None; }
    let path = std::path::Path::new(session.audio_path.as_deref()?);
    let playback = super::meeting_workspace::wav_duration_ms(path).ok()?;
    let mut file = std::fs::File::open(path.with_extension("opus")).ok()?;
    if session.device_total_length.is_some_and(|n| file.metadata().ok().is_none_or(|m| m.len() != u64::from(n))) { return None; }
    let mut head = [0u8;12]; file.read_exact(&mut head).ok()?;
    if &head[..4] != b"COP1" || head[4] != 1 || head[5] != 1 || head[7] != 0
        || ![10,20,40,60].contains(&head[6])
        || ![8000,12000,16000,24000,48000].contains(&u32::from_le_bytes(head[8..12].try_into().ok()?)) { return None; }
    let mut hash = Sha256::new(); hash.update(head);
    let mut frames = 0u64; let mut packet = [0u8;1275];
    loop {
        let mut size = [0u8;2];
        if file.read(&mut size[..1]).ok()? == 0 { break; }
        file.read_exact(&mut size[1..]).ok()?;
        let length = u16::from_le_bytes(size) as usize;
        if length == 0 || length > packet.len() { return None; }
        file.read_exact(&mut packet[..length]).ok()?;
        hash.update(size); hash.update(&packet[..length]);
        frames = frames.checked_add(1)?;
    }
    let skip = u64::from(head[6]);
    let capture = frames.checked_mul(skip)?;
    if frames < 2 || capture.checked_sub(skip)? != playback
        || format!("{:x}",hash.finalize()) != session.device_sha256.as_deref()? { return None; }
    Some((capture,skip))
}

pub(crate) mod live_queue;
pub(crate) mod device;
pub(crate) mod probe;

#[cfg(test)]
mod tests;
