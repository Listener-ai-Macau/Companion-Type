//! Human review overlays the immutable ASR result. Audio, ASR text, speaker ids
//! and timing remain available for audit and for a later transcription retry.
use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};
use crate::companion_v1::{CompanionV1HostSession, CompanionV1UtteranceSegment};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SpeakerName {
    pub speaker: usize,
    pub name: String,
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct UtteranceEdit {
    pub index: usize,
    pub text: String,
    /// A human attribution for this utterance, independent of the ASR cluster.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub speaker_name: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TranscriptReview {
    pub revision: u64,
    pub edited_at: String,
    pub source_transcript_text: String,
    pub source_utterances: Vec<CompanionV1UtteranceSegment>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    #[serde(default)]
    pub utterance_edits: Vec<UtteranceEdit>,
    #[serde(default)]
    pub speaker_names: Vec<SpeakerName>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct TranscriptReviewEdit {
    pub expected_transcript_text: String,
    pub expected_utterances: Vec<CompanionV1UtteranceSegment>,
    pub expected_revision: u64,
    #[serde(default)]
    pub restore_original: bool,
    pub text: Option<String>,
    #[serde(default)]
    pub utterance_edits: Vec<UtteranceEdit>,
    #[serde(default)]
    pub speaker_names: Vec<SpeakerName>,
}

pub fn review_is_stale(session: &CompanionV1HostSession) -> bool {
    session.transcript_review.as_ref().is_some_and(|review| {
        has_changes(review) && (review.source_transcript_text != session.transcript_text
            || review.source_utterances != session.utterances)
    })
}

pub fn final_transcript_available(session: &CompanionV1HostSession) -> bool {
    !session.transcript_text.trim().is_empty() && (session.transcript_final
        || (session.recovery.intent == "none" && matches!(session.status.as_str(), "transcribed" | "minutesReady")))
}

fn has_changes(review: &TranscriptReview) -> bool {
    review.text.is_some() || !review.utterance_edits.is_empty() || !review.speaker_names.is_empty()
}

pub fn active_revision(session: &CompanionV1HostSession) -> Option<u64> {
    session.transcript_review.as_ref()
        .filter(|review| !review_is_stale(session) && has_changes(review))
        .map(|review| review.revision)
}

pub fn minutes_current(session: &CompanionV1HostSession, source_revision: Option<u64>) -> bool {
    !review_is_stale(session) && active_revision(session) == source_revision
}

fn active_review(session: &CompanionV1HostSession) -> Option<&TranscriptReview> {
    session.transcript_review.as_ref().filter(|_| active_revision(session).is_some())
}

pub fn speaker_label(session: &CompanionV1HostSession, index: usize) -> Option<String> {
    let utterance = session.utterances.get(index)?;
    let review = active_review(session);
    if let Some(name) = review.and_then(|r| r.utterance_edits.iter().find(|e| e.index == index))
        .and_then(|edit| edit.speaker_name.as_ref()) {
        return Some(name.clone());
    }
    if let Some(name) = review.and_then(|r| r.speaker_names.iter().find(|n| Some(n.speaker) == utterance.speaker)) {
        return Some(name.name.clone());
    }
    utterance.speaker.map(|speaker| format!("说话人{}", speaker + 1))
}

pub fn effective_utterances(session: &CompanionV1HostSession) -> Vec<CompanionV1UtteranceSegment> {
    let mut utterances = session.utterances.clone();
    if let Some(review) = active_review(session) {
        for edit in &review.utterance_edits {
            if let Some(utterance) = utterances.get_mut(edit.index) { utterance.text = edit.text.clone(); }
        }
    }
    utterances
}

pub fn effective_text(session: &CompanionV1HostSession) -> String {
    let Some(review) = active_review(session) else { return session.transcript_text.clone(); };
    if let Some(text) = &review.text { return text.clone(); }
    effective_utterances(session).iter().enumerate().map(|(index, utterance)| {
        if let Some(label) = speaker_label(session, index) { format!("{label}: {}", utterance.text) }
        else { utterance.text.clone() }
    }).collect::<Vec<_>>().join("\n")
}

pub fn minutes_input(session: &CompanionV1HostSession) -> CompanionV1HostSession {
    let mut input = session.clone();
    // User context is retained locally/exported explicitly, never silently
    // sent as ASR evidence to native or external minutes providers.
    input.meeting_notes.clear();
    input.transcript_text = effective_text(session);
    input.utterances = effective_utterances(session);
    if active_revision(session).is_none() { input.transcript_review = None; }
    input
}

fn valid_text(text: &str) -> bool {
    !text.trim().is_empty() && text.len() <= 200_000
        && !text.chars().any(|c| c.is_control() && c != '\n' && c != '\r' && c != '\t')
}

fn checked_name(name: &str) -> Result<String, String> {
    let name = name.trim();
    if name.is_empty() || name.chars().count() > 32 || name.chars().any(char::is_control) {
        return Err("说话人名称请填写 1 到 32 个字符，不含换行。".into());
    }
    Ok(name.into())
}

/// Pure validation: the caller commits this together with any title/minutes edit.
pub fn prepare_review(session: &CompanionV1HostSession, edit: &TranscriptReviewEdit, now: &str) -> Result<TranscriptReview, String> {
    if session.transcript_text != edit.expected_transcript_text || session.utterances != edit.expected_utterances
        || session.transcript_review.as_ref().map_or(0, |r| r.revision) != edit.expected_revision {
        return Err("转写已在后台变化。你的草稿仍保留，请重新载入后核对，避免覆盖新内容。".into());
    }
    if !final_transcript_available(session) {
        return Err("转写尚未完成，请等最终文字保存后再修订。".into());
    }
    let revision = edit.expected_revision.checked_add(1).ok_or("修订编号已达上限，无法保存。")?;
    let mut result = TranscriptReview {
        revision, edited_at: now.into(), source_transcript_text: session.transcript_text.clone(),
        source_utterances: session.utterances.clone(), text: None, utterance_edits: vec![], speaker_names: vec![],
    };
    if edit.restore_original {
        if edit.text.is_some() || !edit.utterance_edits.is_empty() || !edit.speaker_names.is_empty() {
            return Err("恢复原始转写不能同时提交其他文字修改。".into());
        }
        return Ok(result);
    }
    if let Some(text) = &edit.text {
        if !session.utterances.is_empty() { return Err("这份转写有时间轴，请逐段修订以保留回听位置。".into()); }
        if !valid_text(text) { return Err("转写不能为空，且不能超过 200 KB 或包含非法控制字符。".into()); }
        if text.trim() != session.transcript_text.trim() { result.text = Some(text.trim().into()); }
    }
    let mut indices = BTreeSet::new();
    let mut total_bytes = 0usize;
    for item in &edit.utterance_edits {
        let source = session.utterances.get(item.index).ok_or("修订片段已不存在，请重新载入。")?;
        if !indices.insert(item.index) { return Err("同一转写片段不能重复修订。".into()); }
        if !valid_text(&item.text) { return Err("每段转写不能为空，且不能包含非法控制字符。".into()); }
        total_bytes = total_bytes.saturating_add(item.text.len());
        if total_bytes > 200_000 { return Err("修订文字总量不能超过 200 KB。".into()); }
        let speaker_name = item.speaker_name.as_deref().map(checked_name).transpose()?;
        if item.text.trim() != source.text.trim() || speaker_name.is_some() {
            result.utterance_edits.push(UtteranceEdit { index: item.index, text: item.text.trim().into(), speaker_name });
        }
    }
    let known_speakers = session.utterances.iter().filter_map(|u| u.speaker).collect::<BTreeSet<_>>();
    let mut named = BTreeSet::new();
    for item in &edit.speaker_names {
        if !known_speakers.contains(&item.speaker) || !named.insert(item.speaker) {
            return Err("说话人编号不存在或重复，请重新载入。".into());
        }
        result.speaker_names.push(SpeakerName { speaker: item.speaker, name: checked_name(&item.name)? });
    }
    result.utterance_edits.sort_by_key(|e| e.index);
    result.speaker_names.sort_by_key(|e| e.speaker);
    if let Some(current) = session.transcript_review.as_ref().filter(|_| !review_is_stale(session)) {
        if current.source_transcript_text == result.source_transcript_text && current.source_utterances == result.source_utterances
            && current.text == result.text && current.utterance_edits == result.utterance_edits
            && current.speaker_names == result.speaker_names {
            return Ok(current.clone());
        }
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{apply_fixture_control, fixture_snapshot};

    fn sample() -> CompanionV1HostSession {
        let request = serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
        let mut session = apply_fixture_control(fixture_snapshot(), request).unwrap().host.sessions.remove(0);
        session.transcript_final = true;
        session.utterances = vec![
            CompanionV1UtteranceSegment { text: "周四王交录音。".into(), start_ms: 1250, end_ms: 3200, speaker: Some(0) },
            CompanionV1UtteranceSegment { text: "周五陈校对。".into(), start_ms: 7000, end_ms: 9000, speaker: Some(0) },
        ];
        session
    }
    pub(super) fn request(session: &CompanionV1HostSession) -> TranscriptReviewEdit {
        TranscriptReviewEdit { expected_transcript_text: session.transcript_text.clone(),
            expected_utterances: session.utterances.clone(), expected_revision: session.transcript_review.as_ref().map_or(0, |r| r.revision),
            restore_original: false, text: None,
            utterance_edits: vec![UtteranceEdit { index: 1, text: "周四陈校对。".into(), speaker_name: Some("小陈".into()) }],
            speaker_names: vec![SpeakerName { speaker: 0, name: "小王".into() }],
        }
    }
    #[test]
    fn review_preserves_raw_audio_asr_ids_and_timing_and_survives_restart() {
        let mut session = sample(); let before = session.clone();
        session.transcript_review = Some(prepare_review(&session, &request(&session), "now").unwrap());
        assert_eq!(session.transcript_text, before.transcript_text);
        assert_eq!(session.utterances, before.utterances);
        assert_eq!(session.audio_path, before.audio_path);
        assert_eq!(effective_text(&session), "小王: 周四王交录音。\n小陈: 周四陈校对。");
        let effective = effective_utterances(&session);
        assert_eq!((effective[1].start_ms, effective[1].end_ms, effective[1].speaker), (7000,9000,Some(0)));
        assert!(!minutes_current(&session, None)); assert!(minutes_current(&session, Some(1)));
        let restored: CompanionV1HostSession = serde_json::from_str(&serde_json::to_string(&session).unwrap()).unwrap();
        assert_eq!(effective_text(&restored), effective_text(&session));
        let mut legacy = serde_json::to_value(&before).unwrap(); legacy.as_object_mut().unwrap().remove("transcriptReview");
        assert!(serde_json::from_value::<CompanionV1HostSession>(legacy).unwrap().transcript_review.is_none());
    }
    #[test]
    fn changed_asr_keeps_review_for_recovery_but_never_applies_old_indices() {
        let mut session = sample();
        session.transcript_review = Some(prepare_review(&session, &request(&session), "now").unwrap());
        let saved = serde_json::to_value(&session.transcript_review).unwrap();
        session.utterances.swap(0,1);
        assert!(review_is_stale(&session)); assert_eq!(effective_text(&session), session.transcript_text);
        assert_eq!(serde_json::to_value(&session.transcript_review).unwrap(), saved);
        assert!(!minutes_current(&session, None)); assert!(!minutes_current(&session, Some(1)));
    }
    #[test]
    fn invalid_or_stale_edits_and_restore_aba_are_rejected() {
        let mut session = sample(); let old = request(&session);
        for case in ["textOnTimed", "empty", "index", "duplicate", "name", "speaker", "source", "revision", "live", "restore"] {
            let mut input = request(&session); let mut s = session.clone();
            match case {
                "textOnTimed" => input.text = Some("new".into()),
                "empty" => input.utterance_edits[0].text = " ".into(),
                "index" => input.utterance_edits[0].index = 50,
                "duplicate" => input.utterance_edits.push(input.utterance_edits[0].clone()),
                "name" => input.speaker_names[0].name = "a\nb".into(),
                "speaker" => input.speaker_names[0].speaker = 99,
                "source" => input.expected_utterances[0].end_ms += 1,
                "revision" => input.expected_revision = 1,
                "live" => { s.transcript_final = false; s.status = "captured".into(); },
                "restore" => input.restore_original = true,
                _ => unreachable!(),
            }
            assert!(prepare_review(&s,&input,"now").is_err(), "{case}");
        }
        session.transcript_review = Some(prepare_review(&session,&old,"now").unwrap());
        let mut restore = request(&session); restore.restore_original = true; restore.utterance_edits.clear(); restore.speaker_names.clear();
        session.transcript_review = Some(prepare_review(&session,&restore,"later").unwrap());
        assert_eq!(session.transcript_review.as_ref().unwrap().revision, 2);
        assert_eq!(effective_text(&session), session.transcript_text); assert!(active_revision(&session).is_none());
        assert!(prepare_review(&session,&old,"stale").is_err());
        session.transcript_text.push_str("重新识别。");
        assert!(!review_is_stale(&session), "a cleared review has no old correction to apply");
        assert_eq!(effective_text(&session),session.transcript_text);
    }

    #[test]
    fn exports_use_reviewed_words_and_names_but_keep_original_source_and_subtitle_times() {
        use super::super::export::{prepare_meeting_export, MeetingExportFormat};
        let mut session = sample();
        session.transcript_review = Some(prepare_review(&session,&request(&session),"now").unwrap());
        let srt = prepare_meeting_export(&session,"offlineStore",MeetingExportFormat::Srt).unwrap();
        let srt = String::from_utf8(srt.bytes).unwrap();
        assert!(srt.contains("00:00:07,000 --> 00:00:09,000\n小陈: 周四陈校对。"));
        let json = prepare_meeting_export(&session,"offlineStore",MeetingExportFormat::Json).unwrap();
        let json: serde_json::Value = serde_json::from_slice(&json.bytes).unwrap();
        assert_eq!(json["originalTranscriptText"],session.transcript_text);
        assert_eq!(json["originalUtterances"][1]["text"],"周五陈校对。");
        assert_eq!(json["utterances"][1]["text"],"周四陈校对。");
        assert_eq!(json["speakerLabels"][1],"小陈");
        assert_eq!(json["minutesCurrent"],false);
        let text = prepare_meeting_export(&session,"offlineStore",MeetingExportFormat::Txt).unwrap();
        assert!(String::from_utf8(text.bytes).unwrap().contains("人工修订转写"));
        session.utterances.clear();
        assert!(prepare_meeting_export(&session,"offlineStore",MeetingExportFormat::Srt).is_err(), "plain text never invents a timeline");
    }

    #[test]
    fn privacy_erases_reviewed_and_original_text_and_releases_all_minutes_sources() {
        let mut session = sample();
        session.audio_path = Some("original-retained.wav".into());
        session.transcript_review = Some(prepare_review(&session,&request(&session),"now").unwrap());
        let id = session.id.clone();
        let mut snapshot = fixture_snapshot(); snapshot.host.sessions = vec![session]; snapshot.host.selected_session_id = Some(id.clone());
        let request = serde_json::from_value(serde_json::json!({"action":"privacyEraseTranscript","sessionId":id})).unwrap();
        let erased = apply_fixture_control(snapshot,request).unwrap(); let session = &erased.host.sessions[0];
        assert!(session.transcript_review.is_none()); assert!(session.transcript_text.is_empty());
        assert!(session.utterances.is_empty()); assert!(session.minutes.is_none());
        assert!(session.minutes_by_mode.offline_store.is_none() && session.minutes_by_mode.online_live.is_none());
        assert!(session.audio_path.is_some(), "erasing text does not silently erase the original recording");
    }
}
