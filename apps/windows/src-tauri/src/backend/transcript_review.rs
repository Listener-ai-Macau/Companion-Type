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
    /// Review derived from a replacement ASR preview may have different gaps.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub unrecognized: Option<Vec<crate::companion_v1::CompanionV1UnrecognizedAudio>>,
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
    #[serde(default)]
    pub unrecognized: Option<Vec<crate::companion_v1::CompanionV1UnrecognizedAudio>>,
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

pub fn effective_unrecognized(session: &CompanionV1HostSession) -> &[crate::companion_v1::CompanionV1UnrecognizedAudio] {
    active_review(session).filter(|review| review.text.is_some())
        .and_then(|review| review.unrecognized.as_deref())
        .unwrap_or(&session.transcript_unrecognized)
}

pub fn speaker_label(session: &CompanionV1HostSession, index: usize) -> Option<String> {
    let utterance = session.utterances.get(index)?;
    active_review(session)
        .and_then(|review| confirmed_speaker_name(review, index, utterance.speaker))
        .map(str::to_owned)
        .or_else(|| utterance.speaker.map(|speaker| format!("说话人{}", speaker + 1)))
}

fn confirmed_speaker_name(review: &TranscriptReview, index: usize, speaker: Option<usize>) -> Option<&str> {
    review.utterance_edits.iter().find(|edit| edit.index == index)
        .and_then(|edit| edit.speaker_name.as_deref())
        .or_else(|| review.speaker_names.iter().find(|name| Some(name.speaker) == speaker)
            .map(|name| name.name.as_str()))
}

pub fn effective_utterances(session: &CompanionV1HostSession) -> Vec<CompanionV1UtteranceSegment> {
    let mut utterances = session.utterances.clone();
    if let Some(review) = active_review(session) {
        // A whole-document alternative has no verified alignment to the old
        // ASR windows. Keep those windows in the original, not as new timing.
        if review.text.is_some() { return Vec::new(); }
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

fn without_automatic_speaker_labels(text: &str) -> String {
    text.split_inclusive('\n').map(|line| {
        let Some((label, speech)) = line.split_once([':', '：']) else { return line; };
        let Some(id) = label.strip_prefix("说话人") else { return line; };
        if matches!(id, "?" | "？") || (!id.is_empty() && id.bytes().all(|c| c.is_ascii_digit())) {
            speech.strip_prefix(' ').unwrap_or(speech)
        } else {
            line
        }
    }).collect()
}

pub fn minutes_input(session: &CompanionV1HostSession) -> CompanionV1HostSession {
    let mut input = session.clone();
    // User context is retained locally/exported explicitly, never silently
    // sent as ASR evidence to native or external minutes providers.
    input.meeting_notes.clear();
    input.utterances = effective_utterances(session);
    let review = active_review(session);
    if review.is_none() { input.transcript_review = None; }
    // The ASR cluster is useful for playback, but cannot identify a person in
    // a claim or task. Only an active human attribution travels with timed speech.
    input.transcript_text = if let Some(review) = review.filter(|review| review.text.is_none()) {
        input.utterances.iter().enumerate().map(|(index, row)| {
            match confirmed_speaker_name(review, index, row.speaker) {
                Some(name) => format!("{name}: {}", row.text),
                None => row.text.clone(),
            }
        }).collect::<Vec<_>>().join("\n")
    } else {
        let text = review.and_then(|review| review.text.as_deref()).unwrap_or(&session.transcript_text);
        // A legacy recording or whole-text re-transcription may carry these
        // reserved labels without carrying the ASR timing alongside them.
        let from_recording = !session.utterances.is_empty() || session.audio_stored
            || session.audio_path.is_some()
            || matches!(session.source.as_str(), "boardDevice" | "deviceFlash" | "hostMicrophone"
                | "hostMeeting" | "importedAudio" | "derivedAudio");
        if from_recording { without_automatic_speaker_labels(text) } else { text.to_owned() }
    };
    input
}

// Match the long-meeting source capacity. A successful long transcription must
// not become unusable merely because its review exceeds the former 200 KB cap.
const MAX_REVIEW_BYTES: usize = 2 * 1024 * 1024;
fn valid_text(text: &str) -> bool {
    !text.trim().is_empty() && text.len() <= MAX_REVIEW_BYTES
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
        source_utterances: session.utterances.clone(), text: None, utterance_edits: vec![], speaker_names: vec![], unrecognized: None,
    };
    if edit.restore_original {
        if edit.text.is_some() || !edit.utterance_edits.is_empty() || !edit.speaker_names.is_empty() {
            return Err("恢复原始转写不能同时提交其他文字修改。".into());
        }
        return Ok(result);
    }
    if let Some(text) = &edit.text {
        if !edit.utterance_edits.is_empty() || !edit.speaker_names.is_empty() {
            return Err("整篇替代文字不能同时修改旧时间轴或说话人。".into());
        }
        if !valid_text(text) { return Err("转写不能为空，且不能超过 2 MiB 或包含非法控制字符。".into()); }
        if text.trim() != session.transcript_text.trim() || edit.unrecognized.is_some() { result.text = Some(text.trim().into()); }
        if result.text.is_some() {
            result.unrecognized = edit.unrecognized.clone().or_else(|| session.transcript_review.as_ref()
                .filter(|_| !review_is_stale(session)).and_then(|review| review.unrecognized.clone()));
        }
    }
    let mut indices = BTreeSet::new();
    let mut total_bytes = 0usize;
    for item in &edit.utterance_edits {
        let source = session.utterances.get(item.index).ok_or("修订片段已不存在，请重新载入。")?;
        if !indices.insert(item.index) { return Err("同一转写片段不能重复修订。".into()); }
        if !valid_text(&item.text) { return Err("每段转写不能为空，且不能包含非法控制字符。".into()); }
        total_bytes = total_bytes.saturating_add(item.text.len());
        if total_bytes > MAX_REVIEW_BYTES { return Err("修订文字总量不能超过 2 MiB。".into()); }
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
            && current.speaker_names == result.speaker_names && current.unrecognized == result.unrecognized {
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
            CompanionV1UtteranceSegment { text: "周四王交录音。".into(), start_ms: 1250, end_ms: 3200, speaker: Some(0), approximate_timing: false },
            CompanionV1UtteranceSegment { text: "周五陈校对。".into(), start_ms: 7000, end_ms: 9000, speaker: Some(0), approximate_timing: false },
        ];
        session
    }
    pub(super) fn request(session: &CompanionV1HostSession) -> TranscriptReviewEdit {
        TranscriptReviewEdit { expected_transcript_text: session.transcript_text.clone(),
            expected_utterances: session.utterances.clone(), expected_revision: session.transcript_review.as_ref().map_or(0, |r| r.revision),
            restore_original: false, text: None,
            utterance_edits: vec![UtteranceEdit { index: 1, text: "周四陈校对。".into(), speaker_name: Some("小陈".into()) }],
            speaker_names: vec![SpeakerName { speaker: 0, name: "小王".into() }],
            unrecognized: None,
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
    fn alternate_transcription_keeps_original_and_does_not_borrow_old_timestamps() {
        let mut session=sample();let original=session.clone();
        let edit=TranscriptReviewEdit {expected_transcript_text:session.transcript_text.clone(),
            expected_utterances:session.utterances.clone(),expected_revision:0,restore_original:false,
            text:Some("重新识别的完整会议内容。".into()),utterance_edits:vec![],speaker_names:vec![],unrecognized:None};
        session.transcript_review=Some(prepare_review(&session,&edit,"now").unwrap());
        assert_eq!(session.transcript_text,original.transcript_text);
        assert_eq!(session.utterances,original.utterances);
        assert_eq!(session.audio_path,original.audio_path);
        assert_eq!(effective_text(&session),"重新识别的完整会议内容。");
        assert!(effective_utterances(&session).is_empty());
        assert!(super::super::export::prepare_meeting_export(&session,&session.meeting_mode,super::super::export::MeetingExportFormat::Srt).is_err());
        let exported:serde_json::Value=serde_json::from_str(&super::super::export::render_json(&session).unwrap()).unwrap();
        assert_eq!(exported["utterances"].as_array().unwrap().len(),0);
        assert_eq!(exported["speakerLabels"].as_array().unwrap().len(),0);
        assert_eq!(exported["originalUtterances"].as_array().unwrap().len(),original.utterances.len());
        let input=minutes_input(&session);assert_eq!(input.transcript_text,"重新识别的完整会议内容。");assert!(input.utterances.is_empty());
        assert!(!minutes_current(&session,None));
        let restored:CompanionV1HostSession=serde_json::from_str(&serde_json::to_string(&session).unwrap()).unwrap();
        assert_eq!(effective_text(&restored),effective_text(&session));
        assert_eq!(restored.transcript_text,original.transcript_text);
        let mut mixed=edit;mixed.utterance_edits.push(UtteranceEdit {index:0,text:"不应附着旧时间轴".into(),speaker_name:None});
        assert!(prepare_review(&original,&mixed,"now").is_err());
        let mut saved=original.clone();
        let prior_minutes=serde_json::to_value(&saved.minutes).unwrap();
        let prior_notes=serde_json::to_value(&saved.meeting_notes).unwrap();
        let request=super::super::meeting_workspace::MeetingEditRequest {session_id:saved.id.clone(),title:None,expected_title:None,
            meeting_mode:None,markdown:None,expected_markdown:None,create_manual:None,restore_history:None,transcript_review:Some(TranscriptReviewEdit {
                expected_transcript_text:saved.transcript_text.clone(),expected_utterances:saved.utterances.clone(),expected_revision:0,
                restore_original:false,text:Some("重新识别的完整会议内容。".into()),utterance_edits:vec![],speaker_names:vec![],unrecognized:None})};
        super::super::meeting_workspace::edit_session(&mut saved,&request,"now").unwrap();
        assert_eq!(serde_json::to_value(&saved.minutes).unwrap(),prior_minutes);
        assert_eq!(serde_json::to_value(&saved.meeting_notes).unwrap(),prior_notes);
        assert_eq!(saved.transcript_text,original.transcript_text);assert_eq!(saved.utterances,original.utterances);
        if saved.minutes.is_some() {assert_eq!(saved.pending_reason.as_deref(),Some("minutes_source_changed"));}
    }
    #[test]
    fn alternate_transcription_preserves_its_own_missing_audio_ranges() {
        let mut session=sample();
        session.transcript_unrecognized=vec![crate::companion_v1::CompanionV1UnrecognizedAudio{start_ms:1000,end_ms:2000,source:None}];
        let mut edit=request(&session);edit.utterance_edits.clear();edit.speaker_names.clear();edit.text=Some("新的结果".into());
        edit.unrecognized=Some(vec![crate::companion_v1::CompanionV1UnrecognizedAudio{start_ms:3000,end_ms:4000,source:None}]);
        session.transcript_review=Some(prepare_review(&session,&edit,"now").unwrap());
        assert_eq!(effective_unrecognized(&session)[0].start_ms,3000);
        let reopened:CompanionV1HostSession=serde_json::from_str(&serde_json::to_string(&session).unwrap()).unwrap();
        assert_eq!(effective_unrecognized(&reopened)[0].start_ms,3000);
        assert_eq!(reopened.transcript_unrecognized[0].start_ms,1000);
        assert!(super::super::export::render_json(&reopened).unwrap().contains("3000"));
        edit.expected_revision=1;edit.restore_original=true;edit.text=None;edit.unrecognized=None;
        session.transcript_review=Some(prepare_review(&session,&edit,"later").unwrap());
        assert_eq!(effective_unrecognized(&session)[0].start_ms,1000);
    }
    #[test]
    fn long_alternative_transcription_is_not_blocked_at_old_200kb_limit() {
        let mut session=sample();let original=session.clone();
        let text="会".repeat(77_000);assert!(text.len()>200_000 && text.len()<MAX_REVIEW_BYTES);
        let mut edit=TranscriptReviewEdit {expected_transcript_text:session.transcript_text.clone(),
            expected_utterances:session.utterances.clone(),expected_revision:0,restore_original:false,
            text:Some(text.clone()),utterance_edits:vec![],speaker_names:vec![],unrecognized:None};
        session.transcript_review=Some(prepare_review(&session,&edit,"now").unwrap());
        assert_eq!(effective_text(&session),text);assert_eq!(session.transcript_text,original.transcript_text);
        assert_eq!(session.utterances,original.utterances);assert!(effective_utterances(&session).is_empty());
        edit.text=Some("a".repeat(MAX_REVIEW_BYTES+1));
        assert!(prepare_review(&original,&edit,"now").unwrap_err().contains("2 MiB"));
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
    fn minutes_do_not_promote_asr_speaker_labels_to_identity() {
        let mut session = sample();
        session.source = "importedAudio".into();
        session.transcript_text = "说话人1: 周四王交录音。 周五陈校对。\r\n说话人？：我会上报。\n【电脑声音】保留来源。".into();
        let raw = session.transcript_text.clone();
        let original_rows = session.utterances.clone();
        let before = minutes_input(&session);
        assert_eq!(before.transcript_text, "周四王交录音。 周五陈校对。\r\n我会上报。\n【电脑声音】保留来源。");
        assert_eq!(before.utterances, original_rows);
        assert_eq!(effective_text(&session), raw);

        let mut edit = request(&session);
        edit.speaker_names.clear();
        session.transcript_review = Some(prepare_review(&session, &edit, "now").unwrap());
        let input = minutes_input(&session);
        assert_eq!(input.transcript_text, "周四王交录音。\n小陈: 周四陈校对。");
        assert_eq!(input.utterances[1].start_ms, original_rows[1].start_ms);
        assert_eq!(input.utterances[1].end_ms, original_rows[1].end_ms);
        assert_eq!(speaker_label(&session, 0).as_deref(), Some("说话人1"));
        assert_eq!(effective_text(&session), "说话人1: 周四王交录音。\n小陈: 周四陈校对。");

        let mut named = request(&session);
        named.speaker_names[0].name = "说话人1".into();
        session.transcript_review = Some(prepare_review(&session, &named, "later").unwrap());
        assert_eq!(minutes_input(&session).transcript_text, "说话人1: 周四王交录音。\n小陈: 周四陈校对。");
        session.utterances[0].end_ms -= 1;
        assert!(minutes_input(&session).transcript_review.is_none());
        assert_eq!(minutes_input(&session).transcript_text, before.transcript_text);
    }

    #[test]
    fn minutes_distinguish_audio_text_replacement_from_authored_transcript_labels() {
        let mut session = sample();
        let written = "说话人12：王负责核单。\n主持人: 现阶段不交货。\n事项：只核对 12 元。";
        session.utterances.clear();
        session.source = "importedTranscript".into();
        session.audio_stored = false;
        session.audio_path = None;
        session.transcript_text = written.into();
        assert_eq!(minutes_input(&session).transcript_text, written);

        session.source = "hostMeeting".into();
        let mut edit = request(&session);
        edit.speaker_names.clear();
        edit.utterance_edits.clear();
        edit.text = Some(written.into());
        session.transcript_review = Some(prepare_review(&session, &edit, "now").unwrap());
        assert_eq!(minutes_input(&session).transcript_text, "王负责核单。\n主持人: 现阶段不交货。\n事项：只核对 12 元。");
        assert_eq!(effective_text(&session), written);
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
        assert!(String::from_utf8(text.bytes).unwrap().contains("修订后的转写"));
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
