//! Transcribe independent meeting tracks before combining their text.
//! This is not wired into sessions or the UI yet.
use std::collections::{BTreeMap, HashSet};
use std::path::Path;
use super::transcription::{self, CompanionTranscript, CompanionTranscriptionManager};

pub(super) struct TrackTranscription {
    pub(super) transcript: CompanionTranscript,
    /// Non-empty means a source could not be transcribed; the caller must
    /// display this and retain a retry route instead of calling it complete.
    pub(super) warnings: Vec<String>,
}

/// Submit each track independently to the user's configured provider. Cache
/// ownership is attached to the same session even when one track fails.
#[allow(dead_code)]
pub(super) fn transcribe_tracks(manager: &CompanionTranscriptionManager, session: &str,
    microphone: &[String], system: &[String]) -> Result<TrackTranscription, String> {
    if microphone.is_empty() && system.is_empty() { return Err("会议音轨不完整，原录音保留。".into()); }
    let mut seen = HashSet::new();
    for path in microphone.iter().chain(system) {
        let identity = std::fs::canonicalize(path).map_err(|_| "会议音轨缺失，原录音保留。")?;
        if !seen.insert(identity) { return Err("会议音轨重复，未提交转写。".into()); }
    }
    let mut all = microphone.to_vec(); all.extend_from_slice(system);
    let mic = if microphone.is_empty() { Ok(None) } else { transcribe_track(manager, microphone) };
    let output = if system.is_empty() { Ok(None) } else { transcribe_track(manager, system) };
    let result = combine_results(mic, output);
    if transcription::bind_cache_session(session, &all).is_err() {
        eprintln!("[transcription] meeting-track cache session binding pending");
    }
    result
}

fn combine_results(microphone: Result<Option<CompanionTranscript>, String>,
    system: Result<Option<CompanionTranscript>, String>) -> Result<TrackTranscription, String> {
    let mut warnings = Vec::new();
    let mut extract = |label: &str, result: Result<Option<CompanionTranscript>, String>| match result {
        Ok(track) => track,
        Err(error) => { warnings.push(format!("{label}未完成转写：{error}；原音保留，可重试。")); None }
    };
    let mic = extract("麦克风", microphone);
    let output = extract("电脑声音", system);
    if mic.is_none() && output.is_none() && !warnings.is_empty() { return Err(warnings.join(" ")); }
    Ok(TrackTranscription { transcript: combine(mic, output)?, warnings })
}

fn transcribe_track(manager: &CompanionTranscriptionManager, paths: &[String]) -> Result<Option<CompanionTranscript>, String> {
    match manager.transcribe_session(None, paths) {
        Ok(result) => Ok(Some(result)),
        Err(error) if error == transcription::LOCAL_NO_SPEECH => {
            // Only exact digital silence can be omitted. Quiet speech or a
            // provider failure must remain visible and retryable.
            for path in paths {
                if !transcription::wav_is_digital_silence(Path::new(path))? { return Err(error); }
            }
            Ok(None)
        }
        Err(error) => Err(error),
    }
}

fn compact(text: &str) -> String { text.chars().filter(|c| !c.is_whitespace()).collect() }

/// Only interleave utterances if they preserve all of each provider's text.
/// If timings or text coverage are incomplete, retain full text grouped by
/// source rather than inventing a chronological order or dropping words.
fn combine(microphone: Option<CompanionTranscript>, system: Option<CompanionTranscript>) -> Result<CompanionTranscript, String> {
    let tracks = [("麦克风", microphone), ("电脑声音", system)].into_iter()
        .filter_map(|(label, track)| track.map(|track| (label, track))).collect::<Vec<_>>();
    if tracks.is_empty() { return Err(transcription::LOCAL_NO_SPEECH.into()); }
    let timed = tracks.iter().all(|(_, t)| !t.utterances.is_empty()
        && t.utterances.iter().all(|u| !u.approximate_timing && u.end_ms >= u.start_ms)
        && compact(&t.text) == compact(&t.utterances.iter().map(|u| u.text.as_str()).collect::<Vec<_>>().join("")));
    let mut utterances = Vec::new();
    let mut speaker_ids = BTreeMap::new();
    if timed {
        for (track_index, (label, track)) in tracks.iter().enumerate() {
            for row in &track.utterances {
                let mut row = row.clone();
                row.text = format!("【{label}】{}", row.text);
                if let Some(original) = row.speaker {
                    let next = speaker_ids.len();
                    row.speaker = Some(*speaker_ids.entry((track_index, original)).or_insert(next));
                }
                utterances.push(row);
            }
        }
        utterances.sort_by_key(|row| (row.start_ms, row.end_ms));
    }
    let text = if timed {
        utterances.iter().map(|u| u.text.as_str()).collect::<Vec<_>>().join("\n")
    } else {
        tracks.iter().map(|(label, t)| format!("【{label}】\n{}", t.text)).collect::<Vec<_>>().join("\n\n")
    };
    let providers = tracks.iter().map(|(_, t)| t.provider_id.as_str()).collect::<Vec<_>>().join("+");
    Ok(CompanionTranscript { text, provider_id: format!("meeting-tracks:{providers}"),
        mode: if timed { "aligned-tracks" } else { "source-grouped-tracks" }.into(),
        evidence_path: None, utterances })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::CompanionV1UtteranceSegment;
    fn row(text: &str, start: u64, end: u64, speaker: Option<usize>) -> CompanionV1UtteranceSegment {
        CompanionV1UtteranceSegment { text: text.into(), start_ms: start, end_ms: end, speaker, approximate_timing: false }
    }
    fn transcript(text: &str, rows: Vec<CompanionV1UtteranceSegment>) -> CompanionTranscript {
        CompanionTranscript { text: text.into(), provider_id: "test".into(), mode: "test".into(), evidence_path: None, utterances: rows }
    }
    #[test]
    fn sources_are_interleaved_and_speaker_ids_remain_separate() {
        let mic=transcript("本地",vec![row("本地",2000,3000,Some(0))]);
        let system=transcript("远端甲远端乙",vec![row("远端甲",0,1000,Some(0)),row("远端乙",4000,5000,Some(1))]);
        let merged=combine(Some(mic),Some(system)).unwrap();
        assert_eq!(merged.mode,"aligned-tracks");
        assert_eq!(merged.utterances.iter().map(|r|r.start_ms).collect::<Vec<_>>(),[0,2000,4000]);
        assert_ne!(merged.utterances[0].speaker,merged.utterances[1].speaker);
        assert!(merged.text.contains("【电脑声音】远端甲") && merged.text.contains("【麦克风】本地"));
    }
    #[test]
    fn missing_timing_or_words_keeps_full_text_grouped_by_source() {
        let mic=transcript("完整本地文字",vec![row("本地",1,2,None)]);
        let system=transcript("完整电脑文字",vec![]);
        let merged=combine(Some(mic),Some(system)).unwrap();
        assert_eq!(merged.mode,"source-grouped-tracks"); assert!(merged.utterances.is_empty());
        assert!(merged.text.contains("完整本地文字") && merged.text.contains("完整电脑文字"));
    }
    #[test]
    fn silent_track_does_not_discard_other_track() {
        let merged=combine(None,Some(transcript("远端",vec![]))).unwrap();
        assert!(merged.text.contains("远端")); assert!(combine(None,None).is_err());
    }
    #[test]
    fn failed_track_keeps_other_text_and_reports_retry() {
        let remote = transcript("远端会议",vec![]);
        let partial = combine_results(Err("没有听清".into()),Ok(Some(remote))).unwrap();
        assert!(partial.transcript.text.contains("远端会议"));
        assert_eq!(partial.warnings.len(),1); assert!(partial.warnings[0].contains("可重试"));
        assert!(combine_results(Err("麦克风错误".into()),Err("电脑声音错误".into())).is_err());
    }
    #[test]
    fn approximate_chunk_timing_does_not_pretend_to_order_speakers() {
        let mut approximate = row("电脑内容",0,20_000,Some(0));
        approximate.approximate_timing = true;
        let result = combine(Some(transcript("本地",vec![row("本地",1000,2000,Some(0))])),
            Some(transcript("电脑内容",vec![approximate]))).unwrap();
        assert_eq!(result.mode,"source-grouped-tracks");
        assert!(result.utterances.is_empty());
        assert!(result.text.contains("电脑内容") && result.text.contains("本地"));
    }

    #[test]
    #[ignore = "explicit public WAVs and local model are required"]
    fn public_two_track_recordings_use_the_real_local_provider() {
        assert!(transcription::local_provider_selected());
        let mic = std::env::var("COMPANION_TEST_PUBLIC_MIC_WAV").unwrap();
        let system = std::env::var("COMPANION_TEST_PUBLIC_SYSTEM_WAV").unwrap();
        let result = transcribe_tracks(&CompanionTranscriptionManager::new(), "public-two-track-test", &[mic], &[system]).unwrap();
        assert!(result.warnings.is_empty(), "{:?}", result.warnings);
        assert!(result.transcript.text.contains("【麦克风】"));
        assert!(result.transcript.text.contains("【电脑声音】"));
        assert!(result.transcript.text.chars().count() > 20);
        eprintln!("public tracks transcribed locally; mode={}, chars={}", result.transcript.mode, result.transcript.text.chars().count());
    }
}
