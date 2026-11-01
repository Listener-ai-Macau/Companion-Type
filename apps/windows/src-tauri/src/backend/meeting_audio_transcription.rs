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
    let result = (|| {
        let mic = if microphone.is_empty() { Ok(None) } else { transcribe_track(manager, microphone) };
        super::meeting_processing_job::check_current()?;
        if mic.as_ref().err().is_some_and(|error| error==super::meeting_processing_job::TRANSCRIPTION_CANCELLED) {
            return Err(super::meeting_processing_job::TRANSCRIPTION_CANCELLED.into());
        }
        let output = if system.is_empty() { Ok(None) } else { transcribe_track(manager, system) };
        super::meeting_processing_job::check_current()?;
        if output.as_ref().err().is_some_and(|error| error==super::meeting_processing_job::TRANSCRIPTION_CANCELLED) {
            return Err(super::meeting_processing_job::TRANSCRIPTION_CANCELLED.into());
        }
        let mic_failed=mic.is_err();let output_failed=output.is_err();
        let mut combined=combine_results(mic,output)?;
        // Keep the successfully transcribed track useful. Persist exactly which
        // source failed, so the partial result remains visibly incomplete after
        // restarting and can be retried without inventing missing speech.
        for (failed, paths, label) in [(mic_failed,microphone,"麦克风（转写失败）"),
                                      (output_failed,system,"电脑声音（转写失败）")] {
            if !failed { continue; }
            let bytes=paths.iter().try_fold(0u64,|total,path| {
                let bytes=transcription::wav_pcm_bytes(Path::new(path))?;
                total.checked_add(bytes).ok_or_else(||"录音时间范围过大，原音保留。".to_string())
            })?;
            let end_ms=u64::try_from((bytes as u128*1000+31_999)/32_000)
                .map_err(|_|"录音时间范围过大，原音保留。")?;
            if end_ms==0 {return Err("未能确定失败音轨的时长，原音保留，请重试转写。".into());}
            transcription::push_unrecognized(&mut combined.transcript.unrecognized,0,end_ms,Some(label.into()));
        }
        combined.transcript.unrecognized.sort_by_key(|range|(range.start_ms,range.end_ms));
        Ok(combined)
    })();
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
            // A finished recognizer may return no words for nonzero audio.
            // Preserve other tracks and report the missing source range; do not
            // claim that background noise or quiet speech was silence.
            let mut bytes=0u64;let mut nonzero=false;
            for path in paths {
                let path=Path::new(path);
                if !transcription::wav_is_digital_silence(path)? { nonzero=true; }
                bytes=bytes.checked_add(transcription::wav_pcm_bytes(path)?).ok_or("录音时间范围过大。")?;
            }
            if !nonzero { return Ok(None); }
            let end_ms=u64::try_from((bytes as u128 * 1000 + 31_999) / 32_000).map_err(|_| "录音时间范围过大。")?;
            Ok(Some(CompanionTranscript { text:String::new(), provider_id:"companion-type-local-empty".into(),
                mode:"local-no-words".into(),evidence_path:None,utterances:vec![],
                unrecognized:vec![crate::companion_v1::CompanionV1UnrecognizedAudio{start_ms:0,end_ms,source:None}] }))
        }
        Err(error) => Err(error),
    }
}

fn compact(text: &str) -> String { text.chars().filter(|c| !c.is_whitespace()).collect() }

/// Only interleave utterances if they preserve all of each provider's text.
/// If timings or text coverage are incomplete, retain full text grouped by
/// source rather than inventing a chronological order or dropping words.
fn combine(microphone: Option<CompanionTranscript>, system: Option<CompanionTranscript>) -> Result<CompanionTranscript, String> {
    let all_tracks = [("麦克风", microphone), ("电脑声音", system)].into_iter()
        .filter_map(|(label, track)| track.map(|track| (label, track))).collect::<Vec<_>>();
    let unrecognized = all_tracks.iter().flat_map(|(label, track)| track.unrecognized.iter().cloned().map(|mut range| {
        range.source=Some((*label).to_string());range
    })).collect();
    let tracks = all_tracks.into_iter().filter(|(_,track)| !track.text.trim().is_empty()).collect::<Vec<_>>();
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
        evidence_path: None, utterances, unrecognized })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::companion_v1::CompanionV1UtteranceSegment;
    fn row(text: &str, start: u64, end: u64, speaker: Option<usize>) -> CompanionV1UtteranceSegment {
        CompanionV1UtteranceSegment { text: text.into(), start_ms: start, end_ms: end, speaker, approximate_timing: false }
    }
    fn transcript(text: &str, rows: Vec<CompanionV1UtteranceSegment>) -> CompanionTranscript {
        CompanionTranscript { text: text.into(), provider_id: "test".into(), mode: "test".into(), evidence_path: None, utterances: rows, unrecognized: Vec::new() }
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
    fn no_words_in_one_track_preserves_other_track_and_reports_source() {
        let mut mic=transcript("",vec![]);
        mic.unrecognized.push(crate::companion_v1::CompanionV1UnrecognizedAudio{start_ms:0,end_ms:15000,source:None});
        let output=transcript("远端会议内容",vec![row("远端会议内容",2000,3000,Some(0))]);
        let merged=combine_results(Ok(Some(mic)),Ok(Some(output))).unwrap();
        assert!(merged.warnings.is_empty());
        assert!(merged.transcript.text.contains("远端会议内容"));
        assert_eq!(merged.transcript.unrecognized.len(),1);
        assert_eq!(merged.transcript.unrecognized[0].source.as_deref(),Some("麦克风"));
        assert_eq!(merged.transcript.unrecognized[0].end_ms,15000);
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
    fn failed_track_keeps_usable_transcript_and_persistent_missing_range() {
        let root=std::env::temp_dir().join(format!("companion-dual-partial-{}",uuid::Uuid::new_v4()));
        let audio_root=root.join("managed");std::fs::create_dir_all(&audio_root).unwrap();
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&audio_root);
        std::env::set_var("COMPANION_TYPE_ASR_CACHE_DIR",root.join("cache"));
        std::env::set_var("COMPANION_TYPE_ASR_PROVIDER","fixture");
        for key in ["COMPANION_TYPE_TRANSCRIPT_TEXT","COMPANION_TYPE_ASR_ENDPOINT","COMPANION_TYPE_ASR_API_KEY","COMPANION_TYPE_ASR_COMMAND"] {std::env::remove_var(key);}
        let mic=root.join("microphone.wav");let system=root.join("system.wav");
        let mut pcm=denzic_host_audio_v1_core::wav::wav_header(32_000).to_vec();pcm.resize(32_044,0);
        std::fs::write(&mic,&pcm).unwrap();std::fs::write(&system,&pcm).unwrap();
        std::fs::write(root.join("microphone.transcript.txt"),"").unwrap();
        std::fs::write(root.join("system.transcript.txt"),"明天讨论产品包装。").unwrap();
        let result=transcribe_tracks(&CompanionTranscriptionManager::new(),"dual-partial-fixture",
            &[mic.to_string_lossy().into_owned()],&[system.to_string_lossy().into_owned()]).unwrap();
        assert!(result.transcript.text.contains("明天讨论产品包装。"));
        assert_eq!(result.warnings.len(),1);
        assert_eq!(result.transcript.unrecognized.len(),1,"the failed source must remain marked after the warning is gone");
        assert_eq!((result.transcript.unrecognized[0].start_ms,result.transcript.unrecognized[0].end_ms),(0,1000));
        assert!(result.transcript.unrecognized[0].source.as_deref().unwrap().contains("转写失败"));
        std::fs::write(root.join("microphone.transcript.txt"),"请小王整理报价。").unwrap();
        let retried=transcribe_tracks(&CompanionTranscriptionManager::new(),"dual-partial-fixture",
            &[mic.to_string_lossy().into_owned()],&[system.to_string_lossy().into_owned()]).unwrap();
        assert!(retried.warnings.is_empty() && retried.transcript.unrecognized.is_empty());
        assert!(retried.transcript.text.contains("请小王整理报价") && retried.transcript.text.contains("明天讨论产品包装"));
        std::fs::write(root.join("microphone.transcript.txt"),"").unwrap();
        std::fs::write(root.join("system.transcript.txt"),"").unwrap();
        assert!(transcribe_tracks(&CompanionTranscriptionManager::new(),"dual-partial-fixture",
            &[mic.to_string_lossy().into_owned()],&[system.to_string_lossy().into_owned()]).is_err(),"two failed tracks must not be treated as usable");
        assert_eq!(std::fs::read(&mic).unwrap(),pcm);assert_eq!(std::fs::read(&system).unwrap(),pcm);
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
