//! Multi-format transcript / minutes export.
//!
//! Markdown is rendered by `minutes::render_minutes_markdown`. This module
//! renders the other formats the dashboard can request via the
//! `MeetingExport{Txt,Json,Srt}` actions:
//!  - **txt**  : the plain (speaker-tagged) transcript text.
//!  - **json** : a structured dump (title, transcript, timed utterances, minutes).
//!  - **srt**  : subtitles from the diarization-aware utterance segments
//!               (requires per-utterance timing from the volcengine path).

use crate::companion_v1::{CompanionV1HostSession, CompanionV1MeetingMinutes, CompanionV1UtteranceSegment};

/// Plain-text export: the session title + transcript text (already carries
/// "说话人N:" speaker attribution when diarization ran).
pub fn render_txt(session: &CompanionV1HostSession) -> String {
    let title = if session.title.trim().is_empty() {
        "Companion meeting"
    } else {
        session.title.trim()
    };
    format!("# {title}\n\n{}", session.transcript_text)
}

/// Structured JSON export of the session. Minutes are included when present.
pub fn render_json(session: &CompanionV1HostSession) -> Result<String, String> {
    #[derive(serde::Serialize)]
    #[serde(rename_all = "camelCase")]
    struct Export<'a> {
        title: &'a str,
        generated_at: &'a str,
        duration_ms: u64,
        transcript_text: &'a str,
        utterances: &'a [CompanionV1UtteranceSegment],
        minutes: Option<&'a CompanionV1MeetingMinutes>,
    }
    let generated_at = session
        .minutes
        .as_ref()
        .map(|m| m.generated_at.as_str())
        .or(session.started_at.as_deref())
        .unwrap_or("");
    let payload = Export {
        title: &session.title,
        generated_at,
        duration_ms: session.duration_ms,
        transcript_text: &session.transcript_text,
        utterances: &session.utterances,
        minutes: session.minutes.as_ref(),
    };
    serde_json::to_string_pretty(&payload).map_err(|e| format!("serialize export json: {e}"))
}

/// SRT subtitle export from the timed utterance segments. Returns an empty
/// string when the session has no utterance timing (e.g. env-text / sidecar /
/// pre-diarization sessions); the caller falls back to markdown in that case.
pub fn render_srt(session: &CompanionV1HostSession) -> String {
    if session.utterances.is_empty() {
        return String::new();
    }
    let mut out = String::new();
    for (index, utt) in session.utterances.iter().enumerate() {
        let label = utt
            .speaker
            .map(|id| format!("说话人{}: ", id + 1))
            .unwrap_or_default();
        out.push_str(&format!("{}\n", index + 1));
        out.push_str(&format!("{} --> {}\n", srt_timestamp(utt.start_ms), srt_timestamp(utt.end_ms)));
        out.push_str(&format!("{}{}\n\n", label, utt.text));
    }
    out
}

/// Format milliseconds as an SRT timestamp: `HH:MM:SS,mmm`.
fn srt_timestamp(ms: u64) -> String {
    let millis = ms % 1000;
    let total_seconds = ms / 1000;
    let seconds = total_seconds % 60;
    let total_minutes = total_seconds / 60;
    let minutes = total_minutes % 60;
    let hours = total_minutes / 60;
    format!("{hours:02}:{minutes:02}:{seconds:02},{millis:03}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::{CompanionV1ActionItem, CompanionV1SessionRetention};

    fn session(
        transcript: &str,
        utterances: Vec<CompanionV1UtteranceSegment>,
        minutes: Option<CompanionV1MeetingMinutes>,
    ) -> CompanionV1HostSession {
        CompanionV1HostSession {
            id: "s1".into(),
            title: "Q3 Review".into(),
            source: "hostMicrophone".into(),
            status: "minutesReady".into(),
            pending_reason: None,
            started_at: Some("2026-07-28T10:00:00Z".into()),
            stopped_at: None,
            duration_ms: 5000,
            audio_path: None,
            audio_bytes: 0,
            chunks: vec![],
            transcript_text: transcript.into(),
            transcript_preview: transcript.into(),
            transcript_segments: 0,
            utterances,
            minutes,
            export_markdown: String::new(),
            exported_at: None,
            retention: CompanionV1SessionRetention {
                audio_cached: true,
                transcript_cached: true,
                minutes_cached: true,
                consent_required: true,
                retention_label: "7 days local".into(),
                expires_at: None,
            },
        }
    }

    fn minutes() -> CompanionV1MeetingMinutes {
        CompanionV1MeetingMinutes {
            generated_at: "2026-07-28T10:05:00Z".into(),
            source: "rules_l0".into(),
            quality: "draft".into(),
            summary: vec!["讨论了持久化".into()],
            decisions: vec!["决定：上线持久化".into()],
            action_items: vec![CompanionV1ActionItem {
                text: "陈明周五前验证".into(),
                owner: Some("陈明".into()),
                due: Some("周五".into()),
            }],
            questions: vec![],
            keywords: vec!["持久化".into()],
            markdown: "# Q3 Review".into(),
        }
    }

    #[test]
    fn render_txt_includes_title_and_speaker_tagged_transcript() {
        let s = session("说话人1: 你好\n说话人2: 谢谢", vec![], None);
        let out = render_txt(&s);
        assert!(out.contains("# Q3 Review"));
        assert!(out.contains("说话人1: 你好"));
    }

    #[test]
    fn render_json_includes_utterances_and_minutes() {
        let utts = vec![
            CompanionV1UtteranceSegment { text: "你好".into(), start_ms: 0, end_ms: 1500, speaker: Some(0) },
            CompanionV1UtteranceSegment { text: "谢谢".into(), start_ms: 1600, end_ms: 3000, speaker: Some(1) },
        ];
        let s = session("说话人1: 你好\n说话人2: 谢谢", utts, Some(minutes()));
        let out = render_json(&s).expect("json");
        assert!(out.contains("\"transcriptText\""));
        assert!(out.contains("\"utterances\""));
        assert!(out.contains("\"startMs\": 0"));
        assert!(out.contains("\"speaker\": 1"));
        assert!(out.contains("\"actionItems\""));
        assert!(out.contains("陈明周五前验证"));
    }

    #[test]
    fn render_srt_emits_timed_subtitles_with_speaker() {
        let utts = vec![
            CompanionV1UtteranceSegment { text: "你好".into(), start_ms: 0, end_ms: 1500, speaker: Some(0) },
            CompanionV1UtteranceSegment { text: "谢谢".into(), start_ms: 1_842_500, end_ms: 1_843_999, speaker: Some(1) },
        ];
        let s = session("irrelevant", utts, None);
        let out = render_srt(&s);
        assert!(out.contains("1\n00:00:00,000 --> 00:00:01,500\n说话人1: 你好\n\n"));
        // 1842500ms = 00:30:42,500 ; 1843999ms = 00:30:43,999
        assert!(out.contains("2\n00:30:42,500 --> 00:30:43,999\n说话人2: 谢谢"));
    }

    #[test]
    fn render_srt_empty_when_no_timing() {
        let s = session("plain text, no utterances", vec![], None);
        assert_eq!(render_srt(&s), "");
    }

    #[test]
    fn srt_timestamp_format() {
        assert_eq!(srt_timestamp(0), "00:00:00,000");
        assert_eq!(srt_timestamp(1500), "00:00:01,500");
        assert_eq!(srt_timestamp(3_661_001), "01:01:01,001");
    }
}
