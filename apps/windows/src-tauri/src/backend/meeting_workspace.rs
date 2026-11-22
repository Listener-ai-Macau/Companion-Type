//! Local meeting review: optimistic edits and a narrowly authorized WAV source.
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path,PathBuf};
use serde::Deserialize;
use sha2::{Digest,Sha256};
use crate::companion_v1::{CompanionV1HostSession, CompanionV1MinutesVariant, CompanionV1Snapshot};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct MeetingEditRequest {
    pub session_id: String,
    pub title: Option<String>,
    pub expected_title: Option<String>,
    pub meeting_mode: Option<String>,
    pub markdown: Option<String>,
    pub expected_markdown: Option<String>,
    pub create_manual: Option<ManualMinutesCreate>,
    pub restore_history: Option<HistoryRestore>,
    pub transcript_review: Option<super::transcript_review::TranscriptReviewEdit>,
}

/// A previously saved version, identified against the currently visible history.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct HistoryRestore {
    pub index: usize,
    pub archived_at: String,
}

/// Explicit first document creation, bound to the material visible when the
/// user opened the draft. Absence is checked separately from editing a result.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ManualMinutesCreate {
    pub expected_transcript_text: String,
    pub expected_review_revision: Option<u64>,
    pub expected_note_revision: u64,
}

pub fn edit_session(session: &mut CompanionV1HostSession, request: &MeetingEditRequest, now: &str) -> Result<(), String> {
    super::library_lifecycle::require_available(session)?;
    if session.id != request.session_id { return Err("会议标识不匹配".into()); }
    if session.status == "recording" || matches!(session.recovery.stage.as_str(), "transcribing" | "generatingMinutes") {
        return Err("这场会议仍在处理，请等待完成后修改。".into());
    }
    if request.title.is_none() && request.markdown.is_none() && request.transcript_review.is_none() { return Err("没有要保存的修改".into()); }
    if let Some(title) = &request.title {
        if title.trim().is_empty() || title.trim().chars().count() > 120 || title.chars().any(char::is_control) {
            return Err("会议名称请填写 1 到 120 个字符，不含换行。".into());
        }
        if request.expected_title.as_deref() != Some(&session.title) {
            return Err("会议名称已在后台变化。你的草稿仍保留，请重新载入后核对。".into());
        }
    }
    if request.restore_history.is_some() && (request.markdown.is_none() || request.create_manual.is_some() || request.transcript_review.is_some()) {
        return Err("请选择一份历史纪要恢复。".into());
    }
    if request.create_manual.is_some() && request.markdown.is_none() {
        return Err("手写清单请求缺少内容，未保存。".into());
    }
    // Validate every changed field before applying any part of the edit.
    let updated_review = request.transcript_review.as_ref()
        .map(|edit| super::transcript_review::prepare_review(session, edit, now)).transpose()?;
    if updated_review.is_some() && request.markdown.is_some() {
        return Err("请先保存转写修订，再核对这版纪要。".into());
    }
    let updated_variant = if let Some(markdown) = &request.markdown {
        if markdown.trim().is_empty() || (request.restore_history.is_none() && markdown.len() > 200_000) || markdown.contains('\0') {
            return Err("纪要不能为空，且不能超过 200 KB。".into());
        }
        let mode = request.meeting_mode.as_deref().ok_or("请选择要修改的纪要版本")?;
        let variant = match mode {
            "offlineStore" => session.minutes_by_mode.offline_store.as_ref(),
            "onlineLive" => session.minutes_by_mode.online_live.as_ref(),
            _ => return Err("不支持的纪要版本".into()),
        }.cloned().or_else(|| {
            if session.meeting_mode != mode || session.minutes_by_mode.offline_store.is_some() || session.minutes_by_mode.online_live.is_some() { return None; }
            session.minutes.as_ref().map(|m| CompanionV1MinutesVariant {
                template: None, processing: m.processing.clone(),
                source_note_context: m.source_note_context.clone(), source_action_evidence: m.source_action_evidence.clone(), source_review_revision: m.source_review_revision,
                status: session.status.clone(), markdown: m.markdown.clone(), source: m.source.clone(),
                quality: m.quality.clone(), generated_at: Some(m.generated_at.clone()), partial_count: 0,
            })
        });
        let variant = if let Some(create) = &request.create_manual {
            if variant.is_some() || request.expected_markdown.as_deref() != Some("") {
                return Err("这版已有整理内容。你的手写草稿仍保留，请重新载入后核对，避免覆盖。".into());
            }
            if !super::transcript_review::final_transcript_available(session) || session.capture_incomplete
                || session.recorder_control_uncertain || session.recorder_control.is_some()
                || matches!(session.pending_reason.as_deref(), Some("needs_device_sync" | "needs_segments" | "needs_local_audio" | "device_control_pending" | "capture_interrupted")) {
                return Err("请先确认完整文字和录音状态，再创建清单；原内容已保留。".into());
            }
            if super::transcript_review::review_is_stale(session)
                || create.expected_transcript_text != super::transcript_review::effective_text(session)
                || create.expected_review_revision != super::transcript_review::active_revision(session)
                || create.expected_note_revision != session.note_revision {
                return Err("原话或补充已变化。手写草稿仍保留，请核对当前内容后重新创建。".into());
            }
            if super::action_export::parse_saved_actions(markdown).is_empty() {
                return Err("请填写至少一项待办，再保存手写清单。".into());
            }
            CompanionV1MinutesVariant {
                template: None, processing: None, source_review_revision: super::transcript_review::active_revision(session),
                source_note_context: Some(super::minutes_context::source(session)), source_action_evidence: None,
                status: "minutesReady".into(), markdown: String::new(), source: "userAuthored".into(),
                quality: "final".into(), generated_at: Some(now.into()), partial_count: 0,
            }
        } else { variant.ok_or("这个版本还没有纪要，请先生成内容或创建手写清单。")? };
        if request.expected_markdown.as_deref() != Some(variant.markdown.as_str()) {
            return Err("纪要已在后台变化。你的草稿仍保留，请重新载入后核对，避免覆盖新内容。".into());
        }
        let updated = if let Some(history) = &request.restore_history {
            let saved = session.minutes_by_mode.history.get(history.index)
                .filter(|item| item.mode == mode && item.archived_at == history.archived_at && item.variant.markdown == *markdown)
                .ok_or("历史纪要已变化，请刷新后重试。")?;
            saved.variant.clone()
        } else {
            let mut updated = variant.clone();
            updated.markdown = markdown.trim().to_string();
            // Editing prose keeps the cloud review boundary until a later final generation.
            if updated.source != "userAuthored"
                && !super::minutes::is_cloud_review_draft(&updated.source, &updated.quality, updated.processing.is_some()) {
                updated.source = "userEdited".into();
            }
            updated.source_review_revision = super::transcript_review::active_revision(session);
            updated.generated_at = Some(now.into());
            updated
        };
        let prior = request.restore_history.as_ref().filter(|_| variant.markdown != updated.markdown).map(|_| variant);
        Some((mode.to_string(), updated, prior))
    } else { None };
    if let Some(title) = &request.title { session.title = title.trim().to_string(); }
    if let Some(review) = updated_review {
        if let Some(previous) = session.transcript_review.replace(review) {
            let current = session.transcript_review.as_ref().expect("new transcript revision");
            if previous.revision != current.revision
                && super::transcript_review::has_changes(&previous)
                && (previous.text.is_some() || current.text.is_some()
                    || previous.source_transcript_text != session.transcript_text)
            {
                session.transcript_review_history.push(previous);
            }
        }
        session.recovery = Default::default();
        // Keep both minutes documents intact. Explicit regeneration is required
        // before either can be presented as based on the revised transcript.
        let outdated = [&session.minutes_by_mode.offline_store, &session.minutes_by_mode.online_live]
            .into_iter().flatten().any(|v| !super::transcript_review::minutes_current(session, v.source_review_revision))
            || session.minutes.as_ref().is_some_and(|m| !super::transcript_review::minutes_current(session, m.source_review_revision));
        session.pending_reason = outdated.then(|| "minutes_source_changed".into());
        if outdated { session.status = "transcribed".into(); }
    }
    if let Some((mode, variant, prior)) = updated_variant {
        if let Some(prior) = prior {
            session.minutes_by_mode.history.push(crate::companion_v1::CompanionV1MinutesHistory {
                mode: mode.clone(), archived_at: now.into(), variant: prior,
            });
        }
        if mode == session.meeting_mode {
            session.export_markdown = variant.markdown.clone();
            if session.minutes.is_none() && variant.source == "userAuthored" {
                // Keep the current-mode document envelope coherent with existing
                // library/export/recovery consumers, without inventing extracted facts.
                session.minutes = Some(crate::companion_v1::CompanionV1MeetingMinutes {
                    processing:None, source_review_revision:variant.source_review_revision,
                    source_note_context:variant.source_note_context.clone(), source_action_evidence:variant.source_action_evidence.clone(), generated_at:now.into(),
                    source:variant.source.clone(), quality:variant.quality.clone(), markdown:variant.markdown.clone(),
                    summary:vec![],decisions:vec![],action_items:vec![],questions:vec![],keywords:vec![],llm_note:None,
                });
            }
            if let Some(minutes) = &mut session.minutes {
                minutes.markdown = variant.markdown.clone(); minutes.source = variant.source.clone();
                minutes.generated_at = variant.generated_at.clone().unwrap_or_else(|| now.into());
                minutes.source_review_revision = variant.source_review_revision;
                minutes.source_note_context = variant.source_note_context.clone();
                minutes.source_action_evidence = variant.source_action_evidence.clone();
                minutes.quality = variant.quality.clone();
                minutes.processing = variant.processing.clone();
                // A freely edited document no longer proves the old structured
                // extraction. Never export stale action items as the new edit.
                minutes.summary.clear(); minutes.decisions.clear(); minutes.action_items.clear();
                minutes.questions.clear(); minutes.keywords.clear();
            }
        }
        if mode == "offlineStore" { session.minutes_by_mode.offline_store = Some(variant); }
        else { session.minutes_by_mode.online_live = Some(variant); }
        session.retention.minutes_cached = true;
        // Manual review takes ownership; an already queued retry must not
        // replace it later. A future explicit Generate can request a new result.
        session.recovery = Default::default();
        let outdated = [&session.minutes_by_mode.offline_store, &session.minutes_by_mode.online_live]
            .into_iter().flatten().any(|v| !super::transcript_review::minutes_current(session, v.source_review_revision));
        session.pending_reason = outdated.then(|| "minutes_source_changed".into());
        session.status = if outdated { "transcribed" } else { "minutesReady" }.into();
    }
    session.exported_at = None;
    Ok(())
}

/// Edit one saved row against the current disk index, without replacing an
/// unrelated recording that is being captured or synchronized concurrently.
pub(crate) fn commit_saved_row(session: &mut CompanionV1HostSession, request: &MeetingEditRequest, now: &str) -> Result<(), String> {
    if cfg!(test) && std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none() { return edit_session(session, request, now); }
    let mut saved=None;
    super::session_store::update_checked(&super::persistence::state_file_path(), |rows| {
        let row=rows.iter_mut().find(|row|row.id==session.id).ok_or("这场会议已不存在；未修改其他会议。")?;
        if row.source!=session.source || row.device_recording_id!=session.device_recording_id || row.source_device_id!=session.source_device_id {
            return Err("会议来源已变化，请刷新后再修改。".into());
        }
        edit_session(row,request,now)?;saved=Some(row.clone());Ok(())
    })?;
    if let Some(row)=saved { *session=row; }
    Ok(())
}

pub fn local_audio_path(snapshot: &CompanionV1Snapshot, session_id: &str) -> Result<PathBuf, String> {
    if snapshot.meeting.active || snapshot.device.recording || snapshot.host.sessions.iter().any(|s| s.status == "recording") {
        return Err("录音期间暂不回放，避免把扬声器声音再次录入。".into());
    }
    let session = snapshot.host.sessions.iter().find(|s| s.id == session_id).ok_or("找不到这场会议")?;
    super::library_lifecycle::require_available(session)?;
    if !session.audio_stored || !session.retention.audio_cached || session.pending_reason.as_deref() == Some("needs_device_sync") {
        return Err("这场录音尚未保存在电脑，或本机音频已删除。".into());
    }
    let raw = session.audio_path.as_deref().ok_or("这场会议没有本机音频")?;
    let input = PathBuf::from(raw);
    let lower = raw.to_ascii_lowercase();
    if !input.is_absolute() || lower.starts_with("\\\\?\\unc\\") || (raw.starts_with("\\\\") && !raw.starts_with("\\\\?\\")) {
        return Err("回听仅支持这场会议的本机录音文件。".into());
    }
    let path = input.canonicalize().map_err(|_| "录音文件已移动或删除，请重新同步来源设备。")?;
    // A local-looking junction must not grant access to a network share.
    if path.to_string_lossy().to_ascii_lowercase().starts_with("\\\\?\\unc\\") {
        return Err("回听仅支持这场会议的本机录音文件。".into());
    }
    if !path.extension().is_some_and(|ext| ext.eq_ignore_ascii_case("wav")) { return Err("回听需要已解码的 WAV 录音。".into()); }
    validate_wav(&path)?;
    Ok(path)
}

/// Authorized, time-aligned source files for direct two-track playback. The
/// browser receives only the paths belonging to this saved session; it does
/// not create another full-size recording on disk.
#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PreparedMeetingAudioPart {
    pub path: String,
    pub first_sample: u64,
    pub samples: u64,
}
#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PreparedMeetingAudioTracks {
    pub session_id: String,
    pub source_identity: String,
    pub microphone: Vec<PreparedMeetingAudioPart>,
    pub system: Vec<PreparedMeetingAudioPart>,
}

pub fn local_meeting_audio_tracks(snapshot: &CompanionV1Snapshot, session_id: &str) -> Result<PreparedMeetingAudioTracks, String> {
    if snapshot.meeting.active || snapshot.device.recording || snapshot.host.sessions.iter().any(|s| s.status == "recording") {
        return Err("录音期间暂不回放，避免把扬声器声音再次录入。".into());
    }
    let session = snapshot.host.sessions.iter().find(|s| s.id == session_id).ok_or("找不到这场会议")?;
    super::library_lifecycle::require_available(session)?;
    if session.source != "hostMeeting" || !session.audio_stored || !session.retention.audio_cached {
        return Err("这场会议的双音轨尚未保存在电脑。".into());
    }
    let tracks = session.meeting_tracks.as_ref().ok_or("这场会议没有保存双音轨。")?;
    let mut leases = Vec::new();
    for part in tracks.microphone.iter().chain(&tracks.system) {
        if let Some(lease) = super::audio_artifacts::usage(Path::new(&part.path))? { leases.push(lease); }
    }
    super::meeting_audio_recovery::verify_tracks(tracks, session.audio_bytes, session.duration_ms)?;
    let mut hash = Sha256::new();
    hash.update(b"Companion playback meeting tracks v1\0");
    hash.update((session_id.len() as u64).to_le_bytes()); hash.update(session_id.as_bytes());
    let mut collect = |source: u8, parts: &[crate::companion_v1::CompanionV1MeetingTrackPart]| -> Result<Vec<PreparedMeetingAudioPart>, String> {
        hash.update([source]); hash.update((parts.len() as u64).to_le_bytes());
        let mut result = Vec::with_capacity(parts.len());
        for part in parts {
            let path = Path::new(&part.path).canonicalize().map_err(|_| "会议音轨已移动或删除。")?;
            if path.to_string_lossy().to_ascii_lowercase().starts_with("\\\\?\\unc\\") {
                return Err("回听仅支持这场会议的本机录音文件。".into());
            }
            let (bytes, digest) = super::audio_storage::fingerprint(&path)?;
            hash.update(part.first_sample.to_le_bytes()); hash.update(part.samples.to_le_bytes());
            hash.update(bytes.to_le_bytes()); hash.update(digest.as_bytes());
            result.push(PreparedMeetingAudioPart { path: path.to_string_lossy().into_owned(),
                first_sample: part.first_sample, samples: part.samples });
        }
        Ok(result)
    };
    let microphone = collect(0, &tracks.microphone)?;
    let system = collect(1, &tracks.system)?;
    Ok(PreparedMeetingAudioTracks { session_id: session_id.to_owned(), source_identity: format!("{:x}", hash.finalize()), microphone, system })
}

/// A renderer may remember this opaque original identity, never a path or
/// caller-provided digest. Same bytes at a new path retain progress; another
/// session or a replaced same-length WAV never inherits it.
pub fn playback_identity(session_id:&str,path:&Path)->Result<String,String> {
    let (bytes,digest)=super::audio_storage::fingerprint(path)?;
    let mut hash=Sha256::new();hash.update(b"Companion playback original v1\0");
    hash.update((session_id.len() as u64).to_le_bytes());hash.update(session_id.as_bytes());
    hash.update(bytes.to_le_bytes());hash.update(digest.as_bytes());
    Ok(format!("{:x}",hash.finalize()))
}

/// One identity for the complete ordered recording, including every part.
pub fn playback_parts_identity(session_id:&str,parts:&[(PathBuf,u64)])->Result<String,String> {
    if parts.len()==1 { return playback_identity(session_id,&parts[0].0); }
    if parts.is_empty() { return Err("这场会议没有本机音频".into()); }
    let mut hash=Sha256::new(); hash.update(b"Companion playback parts v1\0");
    hash.update((session_id.len() as u64).to_le_bytes()); hash.update(session_id.as_bytes());
    for (path,samples) in parts {
        let (bytes,digest)=super::audio_storage::fingerprint(path)?;
        hash.update(samples.to_le_bytes()); hash.update(bytes.to_le_bytes()); hash.update(digest.as_bytes());
    }
    Ok(format!("{:x}",hash.finalize()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{apply_fixture_control, fixture_snapshot};
    use super::super::{export::{prepare_meeting_export, MeetingExportFormat}, persistence};

    #[test]
    #[ignore = "changes recording-directory environment; run in isolation"]
    fn saved_meeting_tracks_prepare_without_copy_and_detect_changed_source() {
        use crate::companion_v1::{CompanionV1MeetingTrackPart, CompanionV1MeetingTracks};
        use super::super::meeting_audio_tracks::TrackWriter;
        let root = std::env::temp_dir().join(format!("meeting-playback-source-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap(); std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
        let mut mic = TrackWriter::create_flat(&root, "source-mic", 2).unwrap(); mic.append(&[1,2,3]).unwrap();
        let mut system = TrackWriter::create_flat(&root, "source-system", 2).unwrap(); system.append(&[4,5,6]).unwrap();
        let convert = |parts: Vec<super::super::meeting_audio_tracks::TrackPart>| parts.into_iter().map(|part| CompanionV1MeetingTrackPart {
            path: part.path.to_string_lossy().into_owned(), first_sample: part.first_sample, samples: part.samples }).collect::<Vec<_>>();
        let microphone = convert(mic.finish().unwrap()); let system = convert(system.finish().unwrap());
        let bytes = microphone.iter().chain(&system).map(|part| 44 + part.samples * 2).sum();
        let request = serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
        let mut snapshot = apply_fixture_control(fixture_snapshot(), request).unwrap();
        let session = &mut snapshot.host.sessions[0]; session.id = "meeting-playback".into();
        session.source = "hostMeeting".into(); session.status = "captured".into(); session.audio_stored = true;
        session.retention.audio_cached = true; session.audio_bytes = bytes; session.duration_ms = 0;
        session.meeting_tracks = Some(CompanionV1MeetingTracks { root: root.join("source").to_string_lossy().into_owned(),
            state: "captured".into(), microphone, system, discontinuity: false, issue: None });
        let first = local_meeting_audio_tracks(&snapshot, "meeting-playback").unwrap();
        let second = local_meeting_audio_tracks(&snapshot, "meeting-playback").unwrap();
        assert_eq!(first.source_identity, second.source_identity);
        assert_eq!((first.microphone.len(), first.system.len()), (2, 2));
        assert_eq!(first.system[1].first_sample, 2);
        std::fs::write(&first.system[0].path, b"replaced").unwrap();
        assert!(local_meeting_audio_tracks(&snapshot, "meeting-playback").is_err());
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn playback_identity_binds_actual_content_and_session_but_not_path() {
        let root=std::env::temp_dir().join(format!("companion-playback-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let first=root.join("first.wav");let moved=root.join("moved.wav");
        std::fs::write(&first,b"same length original A").unwrap();
        let original=playback_identity("one",&first).unwrap();assert_eq!(original.len(),64);
        assert_ne!(original,playback_identity("two",&first).unwrap());
        std::fs::rename(&first,&moved).unwrap();assert_eq!(original,playback_identity("one",&moved).unwrap());
        std::fs::write(&moved,b"same length original B").unwrap();
        assert_ne!(original,playback_identity("one",&moved).unwrap());
        assert!(playback_identity("one",&first).is_err());std::fs::remove_dir_all(root).unwrap();
    }

    fn sample() -> CompanionV1HostSession {
        let request = serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
        let mut snapshot = apply_fixture_control(fixture_snapshot(), request).unwrap();
        snapshot.host.sessions.remove(0)
    }
    fn edit(session: &CompanionV1HostSession) -> MeetingEditRequest {
        MeetingEditRequest {
            create_manual: None, restore_history: None, transcript_review: None,
            session_id: session.id.clone(), title: Some("我的会议".into()), expected_title: Some(session.title.clone()),
            meeting_mode: Some("offlineStore".into()), markdown: Some("# 人工核对\n\n周五交付。".into()),
            expected_markdown: Some(session.minutes_by_mode.offline_store.as_ref().unwrap().markdown.clone()),
        }
    }

    #[test]
    fn restore_previous_minutes_preserves_current_and_original_source_revision() {
        let mut session=sample();
        let mut older=session.minutes_by_mode.offline_store.clone().unwrap();
        older.markdown="用户之前的纪要".into();older.source="userEdited".into();older.source_review_revision=Some(23);
        older.template=Some(crate::companion_v1::MinutesTemplate{id:"interview".into(),name:"访谈".into(),instructions:"访谈视角".into()});
        session.minutes_by_mode.history.push(crate::companion_v1::CompanionV1MinutesHistory {
            mode:"offlineStore".into(),archived_at:"earlier".into(),variant:older,
        });
        let current=session.minutes_by_mode.offline_store.as_ref().unwrap().markdown.clone();
        let mut request=edit(&session);request.title=None;request.expected_title=None;
        request.markdown=Some("用户之前的纪要".into());request.expected_markdown=Some(current.clone());
        request.restore_history=Some(HistoryRestore{index:0,archived_at:"wrong".into()});
        assert!(edit_session(&mut session,&request,"now").is_err());
        assert_eq!(session.minutes_by_mode.offline_store.as_ref().unwrap().markdown,current);
        request.restore_history=Some(HistoryRestore{index:0,archived_at:"earlier".into()});
        edit_session(&mut session,&request,"now").unwrap();
        let restored=session.minutes_by_mode.offline_store.as_ref().unwrap();
        assert_eq!(restored.markdown,"用户之前的纪要");assert_eq!(restored.source_review_revision,Some(23));
        assert_eq!(restored.template.as_ref().unwrap().name,"访谈");
        assert_eq!(session.minutes_by_mode.history.last().unwrap().variant.markdown,current);
        assert_eq!(session.status,"transcribed");
        let reopened:CompanionV1HostSession=serde_json::from_slice(&serde_json::to_vec(&session).unwrap()).unwrap();
        assert_eq!(reopened.minutes_by_mode.history.last().unwrap().variant.markdown,current);
        let restored=reopened.minutes_by_mode.offline_store.unwrap();
        assert_eq!(restored.source_review_revision,Some(23));assert_eq!(restored.template.unwrap().id,"interview");
    }

    #[test]
    fn edits_round_trip_preserve_other_mode_and_export_reviewed_text() {
        let mut session = sample();
        let mut live = session.minutes_by_mode.offline_store.clone().unwrap();
        live.markdown = "实时版本保留".into();
        session.minutes_by_mode.online_live = Some(live);
        session.recovery.intent = "processMeeting".into();
        session.recovery.stage = "retryBackoff".into();
        let request = edit(&session);
        edit_session(&mut session, &request, "12345").unwrap();
        assert_eq!(session.title, "我的会议");
        assert_eq!(session.recovery.intent, "none", "a queued retry cannot overwrite manual review");
        assert_eq!(session.minutes_by_mode.online_live.as_ref().unwrap().markdown, "实时版本保留");
        let edited = session.minutes_by_mode.offline_store.as_ref().unwrap();
        assert_eq!(edited.source, "userEdited");
        assert_eq!(edited.generated_at.as_deref(), Some("12345"));
        assert!(session.minutes.as_ref().unwrap().action_items.is_empty());
        assert!(session.minutes.as_ref().unwrap().summary.is_empty());
        let exported = prepare_meeting_export(&session, "offlineStore", MeetingExportFormat::Markdown).unwrap();
        assert!(String::from_utf8(exported.bytes).unwrap().ends_with(request.markdown.as_ref().unwrap()));
        assert!(exported.suggested_name.contains("我的会议"));
        let directory = std::env::temp_dir().join(format!("companion-reviewed-{}", uuid::Uuid::new_v4()));
        let path = directory.join("sessions.json");
        persistence::save_sessions_to(&path, &[session.clone()]).unwrap();
        let restored = persistence::load_sessions_from(&path).unwrap();
        assert_eq!(restored[0].title, session.title);
        assert_eq!(restored[0].minutes_by_mode.offline_store.as_ref().unwrap().markdown, edited.markdown);
        std::fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn stale_or_invalid_combined_edit_never_partially_renames() {
        for failure in ["staleBody", "staleTitle", "missingMode", "emptyBody", "unknownId", "recording", "inFlight", "oversize"] {
            let mut session = sample();
            let mut request = edit(&session);
            match failure {
                "staleBody" => request.expected_markdown = Some("旧版本".into()),
                "staleTitle" => request.expected_title = Some("旧标题".into()),
                "missingMode" => request.meeting_mode = None,
                "emptyBody" => request.markdown = Some(" \n ".into()),
                "unknownId" => request.session_id = "other".into(),
                "recording" => session.status = "recording".into(),
                "inFlight" => session.recovery.stage = "generatingMinutes".into(),
                "oversize" => request.markdown = Some("x".repeat(200_001)),
                _ => unreachable!(),
            }
            let before = serde_json::to_value(&session).unwrap();
            assert!(edit_session(&mut session, &request, "now").is_err(), "{failure}");
            assert_eq!(serde_json::to_value(&session).unwrap(), before, "{failure}");
        }
    }

    #[test]
    fn manually_editing_draft_does_not_certify_it_as_final() {
        let mut session = sample();
        let variant = session.minutes_by_mode.offline_store.as_mut().unwrap();
        variant.quality = "draft".into(); variant.status = "minutesDraft".into();
        let request = edit(&session);
        edit_session(&mut session, &request, "now").unwrap();
        assert_eq!(session.minutes_by_mode.offline_store.as_ref().unwrap().quality, "draft");
        let export = prepare_meeting_export(&session, "offlineStore", MeetingExportFormat::Markdown).unwrap();
        assert!(String::from_utf8(export.bytes).unwrap().starts_with("> 草稿"));
    }

    #[test]
    fn transcript_edit_is_atomic_and_old_minutes_are_retained_until_reviewed() {
        let mut session = sample(); session.transcript_final = true;
        session.utterances = vec![];
        let original = serde_json::to_value(&session).unwrap();
        let mut request = edit(&session); request.markdown = None;
        request.transcript_review = Some(super::super::transcript_review::TranscriptReviewEdit {
            expected_transcript_text: "stale".into(), expected_utterances: vec![], expected_revision: 0,
            restore_original: false, text: Some("owner 小王；周四交录音。".into()), utterance_edits: vec![], speaker_names: vec![], unrecognized: None,
        });
        assert!(edit_session(&mut session,&request,"now").is_err());
        assert_eq!(serde_json::to_value(&session).unwrap(), original, "invalid text edit cannot partly rename");
        request.transcript_review.as_mut().unwrap().expected_transcript_text = session.transcript_text.clone();
        let old_minutes = serde_json::to_value(&session.minutes_by_mode).unwrap();
        let raw = session.transcript_text.clone();
        edit_session(&mut session,&request,"now").unwrap();
        assert_eq!(session.transcript_text,raw);
        assert_eq!(serde_json::to_value(&session.minutes_by_mode).unwrap(),old_minutes);
        assert_eq!(session.recovery.intent,"none");
        assert_eq!(session.pending_reason.as_deref(),Some("minutes_source_changed"));
        let md = prepare_meeting_export(&session,"offlineStore",MeetingExportFormat::Markdown).unwrap();
        assert!(String::from_utf8(md.bytes).unwrap().starts_with("> 整理来源已变化"));
        assert!(prepare_meeting_export(&session,"offlineStore",MeetingExportFormat::Todo).is_err());
        let reviewed_body = session.minutes_by_mode.offline_store.as_ref().unwrap().markdown.clone();
        request.transcript_review = None; request.title = None;
        request.markdown = Some("## 行动项\n- [ ] 小王周四交录音".into()); request.expected_markdown = Some(reviewed_body);
        edit_session(&mut session,&request,"reviewed").unwrap();
        assert_eq!(session.minutes_by_mode.offline_store.as_ref().unwrap().source_review_revision,Some(1));
        assert!(prepare_meeting_export(&session,"offlineStore",MeetingExportFormat::Todo).is_ok());
    }

    #[test]
    fn adopted_transcript_preserves_original_peer_minutes_and_previous_revision() {
        use super::super::transcript_review::{self, TranscriptReviewEdit};
        let mut session = sample();
        session.transcript_final = true;
        let raw = session.transcript_text.clone();
        let mut request = edit(&session);
        request.title = None;
        request.markdown = None;
        request.transcript_review = Some(TranscriptReviewEdit {
            expected_transcript_text: raw.clone(), expected_utterances: session.utterances.clone(), expected_revision: 0,
            restore_original: false, text: Some("上一版人工核对的文字。".into()), utterance_edits: vec![],
            speaker_names: vec![], unrecognized: None,
        });
        edit_session(&mut session, &request, "previous").unwrap();
        let minutes = serde_json::to_value(&session.minutes_by_mode).unwrap();
        let payload = request.transcript_review.as_mut().unwrap();
        payload.expected_revision = 1;
        payload.text = Some("本次导入的最终文字。".into());
        edit_session(&mut session, &request, "adopted").unwrap();
        assert!(edit_session(&mut session, &request, "stale retry").is_err());
        let restored: CompanionV1HostSession = serde_json::from_slice(&serde_json::to_vec(&session).unwrap()).unwrap();
        assert_eq!(restored.transcript_text, raw);
        assert_eq!(serde_json::to_value(&restored.minutes_by_mode).unwrap(), minutes);
        assert_eq!(transcript_review::active_revision(&restored), Some(2));
        assert_eq!(transcript_review::effective_text(&restored), "本次导入的最终文字。");
        assert_eq!(restored.transcript_review_history.len(), 1);
        assert_eq!(restored.transcript_review_history[0].text.as_deref(), Some("上一版人工核对的文字。"));
        assert!(transcript_review::minutes_input(&restored).transcript_review_history.is_empty());
    }

    fn wav() -> Vec<u8> {
        let mut bytes = Vec::new();
        bytes.extend(b"RIFF"); bytes.extend(40u32.to_le_bytes()); bytes.extend(b"WAVEfmt ");
        bytes.extend(16u32.to_le_bytes()); bytes.extend(1u16.to_le_bytes()); bytes.extend(1u16.to_le_bytes());
        bytes.extend(16000u32.to_le_bytes()); bytes.extend(32000u32.to_le_bytes());
        bytes.extend(2u16.to_le_bytes()); bytes.extend(16u16.to_le_bytes());
        bytes.extend(b"data"); bytes.extend(4u32.to_le_bytes()); bytes.extend([0u8; 4]); bytes
    }

    #[test]
    fn playback_grants_only_current_retained_local_audio_and_rejects_broken_wav() {
        let directory = std::env::temp_dir().join(format!("companion-playback-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join("audio.wav");
        std::fs::write(&path, wav()).unwrap();
        let mut session = sample();
        session.audio_path = Some(path.to_string_lossy().into());
        session.audio_stored = true; session.retention.audio_cached = true;
        let id = session.id.clone();
        let mut snapshot = fixture_snapshot(); snapshot.host.sessions = vec![session];
        assert_eq!(local_audio_path(&snapshot, &id).unwrap(), path.canonicalize().unwrap());
        assert!(local_audio_path(&snapshot, "missing").is_err());
        snapshot.meeting.active = true;
        assert!(local_audio_path(&snapshot, &id).is_err());
        snapshot.meeting.active = false;
        snapshot.host.sessions[0].retention.audio_cached = false;
        assert!(local_audio_path(&snapshot, &id).is_err());
        snapshot.host.sessions[0].retention.audio_cached = true;
        snapshot.host.sessions[0].audio_path = Some("\\\\server\\share\\audio.wav".into());
        assert!(local_audio_path(&snapshot, &id).is_err());
        snapshot.host.sessions[0].audio_path = Some(path.to_string_lossy().into());
        for failure in ["truncated", "float", "hugeChunk", "unaligned"] {
            let mut bytes = wav();
            match failure {
                "truncated" => bytes.truncate(45),
                "float" => bytes[20] = 3,
                "hugeChunk" => bytes[40..44].copy_from_slice(&u32::MAX.to_le_bytes()),
                "unaligned" => bytes[40..44].copy_from_slice(&3u32.to_le_bytes()),
                _ => unreachable!(),
            }
            std::fs::write(&path, bytes).unwrap();
            assert!(local_audio_path(&snapshot, &id).is_err(), "{failure}");
        }
        std::fs::remove_dir_all(directory).unwrap();
    }
    fn without_minutes() -> CompanionV1HostSession {
        let mut s = sample(); s.minutes = None; s.minutes_by_mode = Default::default();
        s.status = "transcribed".into(); s.transcript_final = true; s.export_markdown.clear(); s
    }
    fn create(s: &CompanionV1HostSession) -> MeetingEditRequest {
        MeetingEditRequest {
            session_id:s.id.clone(), title:None,expected_title:None, meeting_mode:Some("offlineStore".into()),
            markdown:Some("## Action Items\n\n- [ ] 带上充电线\n- [ ] 确认车次 (due: 2026-10-29)".into()),
            expected_markdown:Some(String::new()),transcript_review:None,
            restore_history:None,create_manual:Some(ManualMinutesCreate {
                expected_transcript_text:super::super::transcript_review::effective_text(s),
                expected_review_revision:super::super::transcript_review::active_revision(s),expected_note_revision:s.note_revision,
            }),
        }
    }
    #[test]
    fn manual_first_checklist_roundtrip_and_exports_keep_authored_origin_and_originals() {
        let mut s=without_minutes();
        s.meeting_notes.push(super::super::meeting_notes::Note {kind:Default::default(),references:vec![],id:uuid::Uuid::new_v4().to_string(),text:"回程还未确认".into(),bookmark_id:None,image:None,created_at:"1".into(),updated_at:"1".into()});
        s.note_revision=1;
        let before=s.clone();let request=create(&s);
        edit_session(&mut s,&request,"1234").unwrap();
        let manual=s.minutes_by_mode.offline_store.as_ref().unwrap();
        assert_eq!(manual.source,"userAuthored");assert!(manual.processing.is_none());
        assert!(super::super::session_has_final_minutes_product(&s));
        assert_eq!(s.minutes.as_ref().unwrap().source,"userAuthored");
        assert_eq!(s.transcript_text,before.transcript_text);assert_eq!(s.transcript_final,before.transcript_final);
        assert_eq!(serde_json::to_value(&s.transcript_review).unwrap(),serde_json::to_value(&before.transcript_review).unwrap());
        assert_eq!(serde_json::to_value(&s.meeting_notes).unwrap(),serde_json::to_value(&before.meeting_notes).unwrap());
        assert_eq!(s.audio_path,before.audio_path);assert_eq!(s.capture_incomplete,before.capture_incomplete);
        let md=String::from_utf8(prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Markdown).unwrap().bytes).unwrap();
        assert!(md.starts_with("> 用户手写清单"));assert!(!md.contains("基于人工修订的转写生成"));
        let todo=String::from_utf8(prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Todo).unwrap().bytes).unwrap();assert!(todo.contains("带上充电线"));
        let ics=String::from_utf8(prepare_meeting_export(&s,"offlineStore",MeetingExportFormat::Ics).unwrap().bytes).unwrap();assert!(ics.contains("20261029"));
        let dir=std::env::temp_dir().join(format!("companion-manual-{}",uuid::Uuid::new_v4()));let file=dir.join("sessions.json");
        persistence::save_sessions_to(&file,&[s.clone()]).unwrap();let mut loaded=persistence::load_sessions_from(&file).unwrap().remove(0);
        assert_eq!(loaded.minutes_by_mode.offline_store.as_ref().unwrap().source,"userAuthored");
        let mut update=create(&loaded);update.create_manual=None;update.expected_markdown=Some(loaded.minutes_by_mode.offline_store.as_ref().unwrap().markdown.clone());
        update.markdown=Some(update.expected_markdown.as_ref().unwrap().replace("[ ] 带上","[x] 带上"));
        edit_session(&mut loaded,&update,"1235").unwrap();assert_eq!(loaded.minutes_by_mode.offline_store.as_ref().unwrap().source,"userAuthored");
        assert!(prepare_meeting_export(&loaded,"offlineStore",MeetingExportFormat::Todo).is_ok());
        loaded.note_revision+=1;assert!(prepare_meeting_export(&loaded,"offlineStore",MeetingExportFormat::Todo).is_err());
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn manual_create_conflicts_never_overwrite_documents_or_partially_rename() {
        for case in ["existing","legacy","newTranscript","newReview","newNote","incomplete","uncertain","pendingAudio","liveRecording","processing","missingText","emptyActions","missingAbsence","missingIntent"] {
            let mut s=without_minutes();let mut request=create(&s);
            request.title=Some("must not leak".into());request.expected_title=Some(s.title.clone());
            match case {
                "existing"=>s.minutes_by_mode.offline_store=sample().minutes_by_mode.offline_store,
                "legacy"=>s.minutes=sample().minutes,
                "newTranscript"=>s.transcript_text.push_str("已更新"),
                "newReview"=>request.create_manual.as_mut().unwrap().expected_review_revision=Some(99),
                "newNote"=>s.note_revision+=1,
                "incomplete"=>s.capture_incomplete=true,
                "uncertain"=>s.recorder_control_uncertain=true,
                "pendingAudio"=>s.pending_reason=Some("needs_device_sync".into()),
                "liveRecording"=>s.status="recording".into(),
                "processing"=>s.recovery.stage="generatingMinutes".into(),
                "missingText"=>{s.transcript_text.clear();s.transcript_final=false;},
                "emptyActions"=>request.markdown=Some("## Action Items\n".into()),
                "missingAbsence"=>request.expected_markdown=None,
                "missingIntent"=>request.create_manual=None,
                _=>unreachable!(),
            }
            let original=serde_json::to_value(&s).unwrap();assert!(edit_session(&mut s,&request,"now").is_err(),"{case}");
            assert_eq!(serde_json::to_value(&s).unwrap(),original,"{case}");
        }
        let mut s=without_minutes();let request=create(&s);edit_session(&mut s,&request,"1").unwrap();
        let saved=serde_json::to_value(&s).unwrap();assert!(edit_session(&mut s,&request,"2").is_err());assert_eq!(serde_json::to_value(&s).unwrap(),saved);
    }

    #[test]
    fn valid_long_wav_remains_playable_and_truncation_is_detected() {
        use std::io::Write;
        struct Scratch(std::path::PathBuf);
        impl Drop for Scratch {
            fn drop(&mut self) { let _ = std::fs::remove_file(&self.0); }
        }
        let path = std::env::temp_dir().join(format!("companion-long-wav-{}.wav", uuid::Uuid::new_v4()));
        let mut file = std::fs::OpenOptions::new().read(true).write(true).create_new(true).open(&path).unwrap();
        let scratch = Scratch(path);
        let pcm_bytes = 512u32 * 1024 * 1024;
        file.write_all(&denzic_host_audio_v1_core::wav::wav_header(pcm_bytes)).unwrap();
        file.set_len(u64::from(pcm_bytes) + 44).unwrap();
        drop(file);
        assert_eq!(super::wav_duration_ms(&scratch.0).unwrap(), u64::from(pcm_bytes) * 1000 / 32000);
        std::fs::OpenOptions::new().write(true).open(&scratch.0).unwrap()
            .set_len(u64::from(pcm_bytes) + 42).unwrap();
        assert!(super::wav_duration_ms(&scratch.0).is_err(), "a truncated original must still be detected");
    }
}

pub(super) fn validate_wav(path: &std::path::Path) -> Result<(), String> {
    wav_duration_ms(path).map(|_| ())
}

pub(crate) fn wav_duration_ms(path: &std::path::Path) -> Result<u64, String> {
    let mut duration_ms = None;
    let result = (|| -> std::io::Result<bool> {
        let mut file = File::open(path)?;
        let size = file.metadata()?.len();
        if size < 44 { return Ok(false); }
        let mut header = [0u8; 12]; file.read_exact(&mut header)?;
        if &header[..4] != b"RIFF" || &header[8..12] != b"WAVE" { return Ok(false); }
        let riff_end = u32::from_le_bytes(header[4..8].try_into().unwrap()) as u64 + 8;
        if riff_end != size || riff_end < 44 { return Ok(false); }
        let mut position = 12u64; let mut alignment = None; let mut byte_rate_value = None;
        let mut data_seen = false; let mut chunks = 0;
        while position + 8 <= riff_end && chunks < 1024 {
            chunks += 1;
            file.seek(SeekFrom::Start(position))?;
            let mut chunk = [0u8; 8]; file.read_exact(&mut chunk)?;
            let len = u32::from_le_bytes(chunk[4..8].try_into().unwrap()) as u64;
            if position + 8 + len > riff_end { return Ok(false); }
            if &chunk[..4] == b"fmt " {
                if len < 16 || alignment.is_some() { return Ok(false); }
                let mut fmt = [0u8; 16]; file.read_exact(&mut fmt)?;
                let channels = u16::from_le_bytes(fmt[2..4].try_into().unwrap());
                let rate = u32::from_le_bytes(fmt[4..8].try_into().unwrap());
                let byte_rate = u32::from_le_bytes(fmt[8..12].try_into().unwrap());
                let align = u16::from_le_bytes(fmt[12..14].try_into().unwrap());
                if u16::from_le_bytes(fmt[..2].try_into().unwrap()) != 1 || !(1..=2).contains(&channels)
                    || !(8_000..=96_000).contains(&rate) || align != channels * 2
                    || u16::from_le_bytes(fmt[14..16].try_into().unwrap()) != 16 || byte_rate != rate * u32::from(align) { return Ok(false); }
                alignment = Some(align as u64);
                byte_rate_value = Some(byte_rate as u64);
            }
            if &chunk[..4] == b"data" {
                if data_seen || !alignment.is_some_and(|align| len > 0 && len % align == 0) { return Ok(false); }
                data_seen = true;
                duration_ms = byte_rate_value.and_then(|rate| len.checked_mul(1000).map(|n| n / rate));
            }
            position += 8 + len + len % 2;
        }
        Ok(data_seen && position == riff_end)
    })();
    if result.unwrap_or(false) {
        duration_ms.ok_or_else(|| "未取得原音的实际时长。".into())
    } else { Err("录音文件不完整或格式暂不支持，无法回听；已有文字和纪要仍可查看。".into()) }

}
