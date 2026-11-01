//! Recompute only acoustic labels on the exact saved source. No ASR/LLM,
//! supplied waveform, transcript text or expected speaker count is accepted.
use crate::companion_v1::{CompanionV1HostSession,CompanionV1Snapshot};

#[derive(serde::Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct Request { pub session_id:String }

pub(super) fn prepare(snapshot:&CompanionV1Snapshot,id:&str)->Result<CompanionV1HostSession,String> {
    let row=snapshot.host.sessions.iter().find(|s|s.id==id).ok_or("这场录音已不存在。")?;
    if !row.transcript_final || row.utterances.is_empty() || row.capture_incomplete {
        return Err("请先收齐原音并完成带时间轴的转写，再重新区分说话人。".into());
    }
    if row.utterances.iter().any(|u|u.approximate_timing) {
        return Err("本地转写提供的是整段近似位置，无法据此区分说话人；原音和文字已保留。".into());
    }
    if super::transcript_review::active_revision(row).is_some() || super::transcript_review::review_is_stale(row)
        || row.minutes.as_ref().is_some_and(|m|m.source=="userEdited")
        || [&row.minutes_by_mode.offline_store,&row.minutes_by_mode.online_live].into_iter().flatten().any(|m|m.source=="userEdited") {
        return Err("这场会议已有人工修订，重新分组可能改变归属；已保留修订，未自动覆盖。".into());
    }
    super::meeting_workspace::local_audio_path(snapshot,id)?;
    Ok(row.clone())
}

pub(super) fn apply(row:&mut CompanionV1HostSession,labels:super::transcription::CompanionTranscript)->Result<bool,String> {
    if labels.utterances.len()!=row.utterances.len() || labels.utterances.iter().zip(&row.utterances)
        .any(|(new,old)|new.text!=old.text || new.start_ms!=old.start_ms || new.end_ms!=old.end_ms || new.approximate_timing!=old.approximate_timing) {
        return Err("本地分组结果改变了原文字或时间轴，未保存。".into());
    }
    if labels.utterances==row.utterances {return Ok(false);}
    if !labels.utterances.iter().any(|u|u.speaker.is_some()) {return Err("没有取得有效声纹，保留原分组。".into());}
    row.utterances=labels.utterances;row.transcript_text=labels.text;
    row.live_transcript_text=row.transcript_text.clone();row.transcript_preview=row.transcript_text.chars().take(120).collect();
    row.transcript_segments=row.utterances.len();row.transcript_final=true;
    let mut has_minutes=false;
    for variant in [&mut row.minutes_by_mode.offline_store,&mut row.minutes_by_mode.online_live].into_iter().flatten() {
        // Keep every existing document; its speaker source changed, so it is a
        // retained draft until an explicit regeneration for that mode.
        variant.quality="draft".into();variant.status="transcribed".into();has_minutes=true;
    }
    if let Some(minutes)=row.minutes.as_mut() {
        minutes.quality="draft".into();
        minutes.llm_note=Some("说话人已在本机重新区分；这里保留的是之前的纪要，可按需重新生成。".into());has_minutes=true;
    }
    row.status="transcribed".into();row.pending_reason=has_minutes.then(||"minutes_source_changed".into());
    row.recovery=Default::default();row.exported_at=None;row.export_markdown.clear();
    Ok(true)
}

#[cfg(test)] mod tests {
    use super::*;
    #[test] fn coarse_asr_windows_are_not_treated_as_single_speakers() {
        let mut s=crate::companion_v1::fixture_snapshot();
        let r=crate::companion_v1::CompanionV1ControlRequest { recording_source: None,action:crate::companion_v1::CompanionV1ControlAction::MeetingLoadDemo,
            session_id:Some("coarse-speakers".into()),context_note_revision:None,ble_name:None,prompt_id:None,title:None,transcript_text:Some("大家讨论。".into()),meeting_mode:None,audio_path:None,audio_bytes:None,device_id:None,duration_ms:None};
        s=crate::companion_v1::apply_fixture_control(s,r).unwrap();
        s.host.sessions[0].utterances=vec![crate::companion_v1::CompanionV1UtteranceSegment{text:"大家讨论。".into(),start_ms:0,end_ms:16000,speaker:None,approximate_timing:true}];
        s.host.sessions[0].transcript_final=true;
        assert!(prepare(&s,"coarse-speakers").unwrap_err().contains("近似位置"));
    }
    #[test] fn local_labels_cannot_rewrite_words_and_keep_both_old_documents() {
        let mut s=crate::companion_v1::fixture_snapshot();
        let mut r=crate::companion_v1::CompanionV1ControlRequest { recording_source: None,action:crate::companion_v1::CompanionV1ControlAction::MeetingLoadDemo,
            session_id:Some("local-speakers".into()),context_note_revision: None, ble_name:None,prompt_id:None,title:None,transcript_text:Some("原句。".into()),meeting_mode:None,audio_path:None,audio_bytes:None,device_id:None,duration_ms:None};
        s=crate::companion_v1::apply_fixture_control(s,r.clone()).unwrap();
        r.action=crate::companion_v1::CompanionV1ControlAction::MeetingGenerateMinutes;
        r.meeting_mode=Some("onlineLive".into());s=crate::companion_v1::apply_fixture_control(s,r).unwrap();
        let row=&mut s.host.sessions[0];row.utterances=vec![crate::companion_v1::CompanionV1UtteranceSegment{text:"原句。".into(),start_ms:0,end_ms:2000,speaker:Some(0),approximate_timing:false}];
        let old=row.minutes_by_mode.clone();let original=row.clone();
        let make=|word:&str|super::super::transcription::CompanionTranscript {text:format!("说话人2: {word}"),provider_id:"local".into(),mode:"local".into(),evidence_path:None,
            utterances:vec![crate::companion_v1::CompanionV1UtteranceSegment{text:word.into(),start_ms:0,end_ms:2000,speaker:Some(1),approximate_timing:false}]};
        assert!(apply(row,make("改了原句")).is_err());assert_eq!(row.utterances,original.utterances);
        assert!(apply(row,make("原句。")).unwrap());
        for (before,after) in [(&old.offline_store,&row.minutes_by_mode.offline_store),(&old.online_live,&row.minutes_by_mode.online_live)] {
            if let Some(before)=before {let after=after.as_ref().unwrap();assert_eq!(after.markdown,before.markdown);assert_eq!(after.quality,"draft");}
        }
        assert_eq!(row.audio_path,original.audio_path);assert_eq!(row.device_recording_key,original.device_recording_key);
        assert_eq!(row.recovery.intent,"none");assert_eq!(row.pending_reason.as_deref(),Some("minutes_source_changed"));
        row.minutes.as_mut().unwrap().source="userEdited".into();
        assert!(prepare(&s,"local-speakers").unwrap_err().contains("人工修订"));
    }
}
