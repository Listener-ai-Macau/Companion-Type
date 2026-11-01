//! Keep a recovered original playable without submitting an incomplete meeting
//! automatically. Explicitly processing the saved fragment is independent of
//! device consumption and never clears its permanent interruption marker.
use crate::companion_v1::{CompanionV1HostSession, CompanionV1MeetingRecovery};

pub(super) fn needs_review(session: &CompanionV1HostSession) -> bool {
    session.capture_incomplete && !session.recovery.capture_review_confirmed
}

pub(super) fn hold(session: &mut CompanionV1HostSession) -> bool {
    if !needs_review(session) || !session.audio_stored || session.status == "recording"
        || session.recovery.stage == "complete" {
        return false;
    }
    if session.recovery.intent != "processMeeting" {
        session.recovery = CompanionV1MeetingRecovery::armed(&session.meeting_mode);
    }
    session.recovery.stage = "paused".into();
    session.recovery.next_retry_at_unix_ms = None;
    session.recovery.last_error = Some(if session.source == "hostMeeting" {
        format!("会议录音曾意外中断，已找回约{}秒的音轨；确认后可整理已保存的片段。", session.duration_ms / 1000)
    } else { format!(
        "录音曾意外中断，已保存{}秒。可以回听或导出；选择整理已保存的片段后才继续转写和纪要。",
        session.duration_ms / 1000) });
    session.pending_reason = Some("capture_interrupted".into());
    true
}

/// Called only by an explicit manual transcribe/minutes request after the
/// target session has been resolved. Automatic workers cannot call this path.
pub(super) fn confirm(session: &mut CompanionV1HostSession) -> Result<(), String> {
    if !needs_review(session) { return Ok(()); }
    if session.status == "recording" || !session.audio_stored || !session.retention.audio_cached {
        return Err("中断录音尚未收齐到本机，请先同步原设备；没有重新开录或提交转写。".into());
    }
    if session.device_recording_key.is_some() {
        super::recording_wire::receiver::Receiver::verify_saved_row(session)?;
    } else if super::host_segmented_capture::saved_parts(session)?.is_some() {
        // All parts and the total continuous sample axis were validated.
    } else if session.source == "hostMeeting" {
        let tracks = session.meeting_tracks.as_ref().ok_or("中断会议缺少音轨记录，原文件保留。")?;
        super::meeting_audio_recovery::verify_tracks(tracks, session.audio_bytes, session.duration_ms)?;
    } else {
        let path = session.audio_path.as_deref().map(std::path::Path::new)
            .filter(|p| p.is_absolute()).ok_or("中断录音缺少真实本机原音。")?;
        let meta = std::fs::symlink_metadata(path).map_err(|_| "中断录音原件已移动或删除。")?;
        if !meta.is_file() || meta.file_type().is_symlink() || meta.len() != session.audio_bytes
            || super::meeting_workspace::wav_duration_ms(path)? != session.duration_ms {
            return Err("中断录音的原件与保存记录不一致，未提交转写。".into());
        }
    }
    if session.recovery.intent != "processMeeting" {
        session.recovery = CompanionV1MeetingRecovery::armed(&session.meeting_mode);
    }
    session.recovery.capture_review_confirmed = true;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn manual_processing_keeps_interruption_warning_without_auto_submitting_normal_audio() {
        let mut s=original();s.processing_policy=crate::companion_v1::CompanionV1ProcessingPolicy::Manual;
        s.recovery=Default::default();super::super::arm_meeting_recovery(&mut s);
        assert_eq!(s.recovery.stage,"paused");assert_eq!(s.pending_reason.as_deref(),Some("capture_interrupted"));
        assert!(s.recovery.next_retry_at_unix_ms.is_none());assert!(s.capture_incomplete);
        let mut normal=original();normal.capture_incomplete=false;normal.processing_policy=s.processing_policy;
        normal.recovery=Default::default();super::super::arm_meeting_recovery(&mut normal);
        assert_eq!(normal.recovery.stage,"idle");assert_ne!(normal.recovery.intent,"processMeeting");
        let mut pet=s;pet.recovery.intent=super::super::pet_chat::CAPTURE_INTENT.into();
        super::super::arm_meeting_recovery(&mut pet);assert_eq!(pet.recovery.intent,super::super::pet_chat::CAPTURE_INTENT);
    }
    fn original() -> CompanionV1HostSession {
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingStart,Some("interrupted".into()))).unwrap();
        let mut s=snapshot.host.sessions.remove(0);
        s.status="captured".into();s.capture_incomplete=true;s.duration_ms=27000;
        s.audio_stored=true;s.audio_bytes=864044;s.recovery=CompanionV1MeetingRecovery::armed("offlineStore");
        s
    }
    #[test]
    fn interrupted_capture_waits_without_spending_retries_and_survives_restart() {
        let mut s=original();s.recovery.attempt_count=1;s.recovery.stage="retryBackoff".into();
        s.recovery.next_retry_at_unix_ms=Some(1);
        assert!(hold(&mut s));assert_eq!(s.recovery.attempt_count,1);
        assert_eq!(s.pending_reason.as_deref(),Some("capture_interrupted"));
        assert!(s.recovery.last_error.as_deref().unwrap().contains("27秒"));
        assert!(s.recovery.next_retry_at_unix_ms.is_none());
        let mut reopened:CompanionV1HostSession=serde_json::from_slice(&serde_json::to_vec(&s).unwrap()).unwrap();
        super::super::persistence::reconcile_session_recovery(&mut reopened);
        assert_eq!(reopened.recovery.stage,"paused");assert!(needs_review(&reopened));
        assert!(reopened.capture_incomplete&&reopened.audio_stored);
        // Explicit choice persists; future sync/restart cannot clear it or
        // silently present the interrupted source as a complete capture.
        reopened.recovery.capture_review_confirmed=true;
        assert!(!hold(&mut reopened));assert!(reopened.capture_incomplete);
    }
    #[test]
    fn unreceived_or_missing_original_cannot_be_confirmed() {
        let mut s=original();s.audio_stored=false;assert!(confirm(&mut s).is_err());
        s.audio_stored=true;s.audio_path=Some("host://declared.wav".into());
        assert!(confirm(&mut s).is_err());assert!(!s.recovery.capture_review_confirmed);
    }
}
