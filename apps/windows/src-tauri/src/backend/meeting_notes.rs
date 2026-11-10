//! Local user context, separate from ASR and generated meeting facts.
use serde::{Deserialize, Serialize};
use crate::companion_v1::CompanionV1HostSession;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Note {
    pub id: String,
    pub text: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub bookmark_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub image: Option<super::meeting_note_images::Attachment>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub enum Action { Add, Edit, Delete }

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Request {
    pub session_id: String,
    pub note_id: String,
    pub expected_revision: u64,
    pub action: Action,
    pub text: Option<String>,
    pub bookmark_id: Option<String>,
}

pub(crate) fn normalize_text(text: &str) -> Result<String, String> {
    let text = text.replace("\r\n", "\n").replace('\r', "\n");
    let text = text.trim();
    if text.is_empty() || text.chars().count() > 4000
        || text.chars().any(|c| c.is_control() && c != '\n' && c != '\t') {
        return Err("备注请填写1到4000个字符，可换行；不能包含无效控制字符。".into());
    }
    Ok(text.into())
}

pub(crate) fn apply(session: &mut CompanionV1HostSession, request: &Request, now: &str) -> Result<bool, String> {
    super::library_lifecycle::require_available(session)?;
    if request.session_id != session.id || uuid::Uuid::parse_str(&request.note_id).is_err() {
        return Err("备注所属会议或请求标识无效；未修改其他会议。".into());
    }
    let old = session.meeting_notes.iter().find(|n| n.id == request.note_id);
    if request.action == Action::Delete {
        if request.text.is_some() || request.bookmark_id.is_some() { return Err("删除备注请求包含多余内容。".into()); }
        if old.is_none() { return Ok(false); }
    }
    let text = if request.action == Action::Delete { None } else {
        Some(normalize_text(request.text.as_deref().ok_or("请填写备注。")?)?)
    };
    if let Some(old) = old {
        if request.action != Action::Delete && Some(&old.text) == text.as_ref() && old.bookmark_id == request.bookmark_id {
            return Ok(false); // A lost reply can retry the exact UUID, even after a revision advances.
        }
        if request.action == Action::Add { return Err("这个备注请求已用于其他内容，请刷新后核对。".into()); }
    } else if request.action == Action::Edit { return Err("这条备注已不存在；输入仍保留。".into()); }
    if request.expected_revision != session.note_revision {
        return Err("会议备注已变化；你的输入仍保留，请刷新后核对。".into());
    }
    if request.action != Action::Delete && request.bookmark_id.as_ref().is_some_and(|id| !session.bookmarks.iter().any(|b| &b.id == id)) {
        return Err("所选重点已不存在，请重新选择；不会估算或移动录音时间。".into());
    }
    let revision = session.note_revision.checked_add(1).ok_or("备注版本已超出范围。")?;
    let mut next = session.meeting_notes.clone();
    match request.action {
        Action::Add => {
            if next.len() >= 128 { return Err("这场会议已有128条备注，请整理后再添加。".into()); }
            next.push(Note { id: request.note_id.clone(), text: text.unwrap(), bookmark_id: request.bookmark_id.clone(),
                image: None, created_at: now.into(), updated_at: now.into() });
        }
        Action::Edit => {
            let note = next.iter_mut().find(|n| n.id == request.note_id).unwrap();
            note.text = text.unwrap(); note.bookmark_id = request.bookmark_id.clone(); note.updated_at = now.into();
        }
        Action::Delete => next.retain(|n| n.id != request.note_id),
    }
    if next.iter().map(|n| n.text.len()).sum::<usize>() > 200_000 { return Err("这场会议的备注已达到200KB，请整理后再添加。".into()); }
    session.meeting_notes = next; session.note_revision = revision; session.exported_at = None;
    Ok(true)
}

/// Reapply against the locked disk row. Only note fields change, so a newer
/// transport/ASR result is retained. A committed write with a lost reply is retryable.
pub(crate) fn commit(session: &mut CompanionV1HostSession, request: &Request, now: &str) -> Result<(), String> {
    if cfg!(test) && std::env::var("COMPANION_TYPE_STATE_PATH").is_err() { apply(session, request, now)?; return Ok(()); }
    commit_to(&super::persistence::state_file_path(), session, request, now)
}

fn commit_to(path: &std::path::Path, session: &mut CompanionV1HostSession, request: &Request, now: &str) -> Result<(), String> {
    let mut saved = None;
    super::session_store::update_checked(path, |rows| {
        let row = rows.iter_mut().find(|r| r.id == session.id).ok_or("会议已在磁盘中删除；备注输入仍保留。")?;
        if row.device_recording_id != session.device_recording_id || row.source_device_id != session.source_device_id {
            return Err("这场会议的录音归属已变化；未保存到其他录音。".into());
        }
        apply(row, request, now)?;
        saved = Some((row.note_revision, row.meeting_notes.clone()));
        Ok(())
    })?;
    if let Some((revision, notes)) = saved { session.note_revision = revision; session.meeting_notes = notes; session.exported_at = None; }
    Ok(())
}

pub(crate) fn render(session: &CompanionV1HostSession) -> String {
    if session.meeting_notes.is_empty() { return String::new(); }
    let mut text = "\n\n## 用户备注\n\n以下内容由用户补充，未作为原始识别或自动纪要事实。\n".to_string();
    for note in &session.meeting_notes {
        let anchor = note.bookmark_id.as_ref().map(|id| {
            session.bookmarks.iter().find(|b| &b.id == id).map_or_else(|| " · 原重点已删除".to_string(), |point| {
                let belongs = point.source_sha256.as_deref().is_none_or(|sha| Some(sha) == session.device_sha256.as_deref())
                    && (point.origin != "boardRecording" || (point.recording_id == session.device_recording_id
                        && point.source_device_id.as_deref().zip(session.source_device_id.as_deref())
                            .is_some_and(|(a,b)| super::device_connection::same_device_id(a,b))));
                let mapped = point.audio_position_ms.filter(|_| belongs && session.audio_stored && session.retention.audio_cached);
                let position = mapped.unwrap_or(point.position_ms);
                format!(" · 关联重点 {} {:02}:{:02}{}", point.label, position / 60000, position / 1000 % 60,
                    if mapped.is_none() { "（原标记位置，回听映射未确认）" } else { "" })
            })
        }).unwrap_or_default();
        text.push_str(&format!("\n用户补充{}：\n", anchor));
        // Quote all lines, including Markdown-looking user text; never create
        // an Action Items heading or task in the generated document.
        for line in note.text.lines() { text.push_str("> "); text.push_str(line); text.push('\n'); }
        if let Some(image)=&note.image {text.push_str(&format!("> 图片：{}（原图见图文ZIP；文字格式不嵌入原图）\n",image.name.replace(['\r','\n']," ")));}
    }
    text
}

#[cfg(test)]
mod tests;
