//! Recover registered interrupted meeting tracks without changing originals.
use std::fs::File;
use std::path::{Path, PathBuf};
use super::audio_artifacts::{self, MeetingCapturePart};
use super::host_interrupted_recovery::{self, RecoveredHostAudio};
use crate::companion_v1::{CompanionV1MeetingTrackPart, CompanionV1MeetingTracks};

pub(super) struct RecoveredMeeting {
    pub(super) tracks: CompanionV1MeetingTracks,
    pub(super) bytes: u64,
    pub(super) duration_ms: u64,
    // Keep both original leases and copy provenance until the session update
    // is durable. A failed update leaves every original and copy available.
    _sealed_leases: Vec<File>,
    _copies: Vec<RecoveredHostAudio>,
}

pub(super) fn verify_tracks(tracks: &CompanionV1MeetingTracks, expected_bytes: u64, expected_ms: u64) -> Result<(), String> {
    let mut bytes = 0u64; let mut durations = Vec::new();
    for parts in [&tracks.microphone, &tracks.system] {
        let mut samples = 0u64;
        for part in parts {
            if part.first_sample != samples || part.samples == 0 { return Err("会议音轨分段不连续，原文件保留。".into()); }
            let path = Path::new(&part.path);
            audio_artifacts::verify_sealed_meeting_part(path)?;
            super::meeting_workspace::validate_wav(path)?;
            let size = std::fs::metadata(path).map_err(|_| "会议音轨缺失，原文件保留。")?.len();
            if part.samples.checked_mul(2).and_then(|n| n.checked_add(44)) != Some(size) { return Err("会议音轨长度已变化，原文件保留。".into()); }
            samples = samples.checked_add(part.samples).ok_or("会议音轨长度无效")?;
            bytes = bytes.checked_add(size).ok_or("会议音轨长度无效")?;
        }
        durations.push(samples);
    }
    if durations.iter().all(|&n| n == 0) || bytes != expected_bytes
        || durations.into_iter().max().unwrap_or(0).saturating_mul(1_000) / 16_000 != expected_ms {
        return Err("会议音轨与保存记录不一致，原文件保留。".into());
    }
    Ok(())
}

/// This only opens paths recorded in the ownership manifest for `anchor`.
/// A partially written WAV is repaired to a new copy; its original is untouched.
#[allow(dead_code)]
pub(super) fn recover(anchor: &Path) -> Result<RecoveredMeeting, String> {
    let (mic, system) = audio_artifacts::meeting_capture_parts(anchor)?;
    if mic.is_empty() && system.is_empty() { return Err("没有找到已登记的会议音轨，原文件保留。".into()); }
    let mut leases = Vec::new();
    for part in mic.iter().chain(&system).filter(|part| part.sealed) {
        if let Some(lease) = audio_artifacts::usage(&part.path)? { leases.push(lease); }
    }
    // Recheck after taking leases so a concurrent supported deletion or
    // replacement cannot silently change the selected recording.
    if audio_artifacts::meeting_capture_parts(anchor)? != (mic.clone(), system.clone()) {
        return Err("会议音轨已变化，请重新载入；原文件保留。".into());
    }
    let mut copies = Vec::new();
    let (microphone, mic_samples, mic_bytes) = recover_track(mic, &mut copies)?;
    let (system, system_samples, system_bytes) = recover_track(system, &mut copies)?;
    if mic_samples == 0 && system_samples == 0 { return Err("没有可恢复的完整音频采样，原文件保留。".into()); }
    let duration_ms = mic_samples.max(system_samples).saturating_mul(1_000) / 16_000;
    Ok(RecoveredMeeting { tracks: CompanionV1MeetingTracks {
        root: anchor.to_string_lossy().into_owned(), state: "needsReview".into(), microphone, system,
        discontinuity: true, issue: Some("录音意外中断，已找回可用片段；结尾可能缺失。".into()),
    }, bytes: mic_bytes.saturating_add(system_bytes), duration_ms, _sealed_leases: leases, _copies: copies })
}

fn recover_track(parts: Vec<MeetingCapturePart>, copies: &mut Vec<RecoveredHostAudio>)
    -> Result<(Vec<CompanionV1MeetingTrackPart>, u64, u64), String> {
    let mut result = Vec::new(); let mut samples = 0u64; let mut bytes_total = 0u64;
    let count = parts.len();
    for (position, part) in parts.into_iter().enumerate() {
        if !part.sealed && position + 1 != count { return Err("会议音轨中间分段不完整，原文件保留。".into()); }
        let source_len = std::fs::metadata(&part.path).map_err(|_| "会议音轨缺失，原文件保留。")?.len();
        if source_len <= 45 && !part.sealed {
            // No complete 16-bit sample exists. Preserve the source; a lone
            // partial byte is not invented into a sample.
            continue;
        }
        let path: PathBuf = if part.sealed { part.path } else {
            let recovered = host_interrupted_recovery::recover_copy(&part.path)?;
            let path = recovered.path.clone(); copies.push(recovered); path
        };
        super::meeting_workspace::validate_wav(&path)?;
        let length = std::fs::metadata(&path).map_err(|_| "无法读取已恢复音轨。")?.len();
        let pcm = length.checked_sub(44).filter(|n| *n > 0 && n % 2 == 0).ok_or("恢复音轨长度无效")?;
        let part_samples = pcm / 2;
        result.push(CompanionV1MeetingTrackPart { path: path.to_string_lossy().into_owned(), first_sample: samples, samples: part_samples });
        samples = samples.checked_add(part_samples).ok_or("会议音轨长度无效")?;
        bytes_total = bytes_total.checked_add(length).ok_or("会议音轨长度无效")?;
    }
    Ok((result, samples, bytes_total))
}

/// Bind the recovered files only to the same unchanged session. Copies and
/// originals remain available if the index update fails or races another edit.
#[allow(dead_code)]
pub(super) fn recover_session_at(state_path: &Path, id: &str, expected: &(String, String)) -> Result<(), String> {
    recover_session_with(state_path, id, expected, || Ok(()))
}

fn recover_session_with(state_path: &Path, id: &str, expected: &(String, String),
    after_copy: impl FnOnce() -> Result<(), String>) -> Result<(), String> {
    let loaded = super::session_store::load(state_path);
    if loaded.state.status != "ready" { return Err("会议库尚未恢复，原录音保留。".into()); }
    let bytes = loaded.bytes.ok_or("会议记录不存在，原录音保留。")?;
    let rows: Vec<crate::companion_v1::CompanionV1HostSession> = serde_json::from_slice(&bytes).map_err(|_| "会议记录无法读取，原录音保留。")?;
    let old = rows.iter().find(|row| row.id == id).ok_or("会议记录不存在，原录音保留。")?;
    if old.source != "hostMeeting" || old.audio_stored || old.organization.trashed_at.is_some() || old.recorder_control.is_some() {
        return Err("这条会议当前不需要恢复双音轨，原文件保留。".into());
    }
    let anchor = old.meeting_tracks.as_ref().map(|tracks| PathBuf::from(&tracks.root)).ok_or("会议缺少原音轨位置，原文件保留。")?;
    let authorization = super::session_store::privacy_authorization(old)?;
    if &authorization != expected { return Err("原会议已变化，请刷新后重试；原文件保留。".into()); }
    let recovered = recover(&anchor)?;
    after_copy()?;
    super::session_store::update_checked(state_path, |current| {
        let row = current.iter_mut().find(|row| row.id == id).ok_or("原会议已移除，原文件与副本保留。")?;
        if row.source != "hostMeeting" || row.audio_stored || row.organization.trashed_at.is_some()
            || row.recorder_control.is_some() || super::session_store::privacy_authorization(row)? != authorization {
            return Err("原会议在恢复期间发生变化，原文件与副本保留。".into());
        }
        row.meeting_tracks = Some(recovered.tracks.clone());
        row.audio_bytes = recovered.bytes; row.duration_ms = recovered.duration_ms;
        row.audio_stored = true; row.retention.audio_cached = true; row.capture_incomplete = true;
        row.status = "captured".into();
        super::interrupted_capture::hold(row);
        Ok(())
    })?;
    Ok(())
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;
    use std::io::Write;
    use super::super::meeting_audio_tracks::TrackWriter;

    #[test]
    #[ignore = "changes recording-directory environment; run in isolation"]
    fn registered_partial_track_recovers_copy_and_binds_original_session() {
        let root = std::env::temp_dir().join(format!("meeting-recover-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let previous = std::env::var_os("COMPANION_TYPE_RECORDING_DIR");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
        let anchor = root.join("meeting-exact");
        let mut mic = TrackWriter::create_flat(&root, "meeting-exact-mic", 10).unwrap();
        mic.append(&[1,2,3]).unwrap(); let original_mic = mic.finish().unwrap()[0].path.clone();
        let original_system = root.join("meeting-exact-system-00000000.wav");
        let lease = audio_artifacts::WriteLease::begin(&original_system, &original_system, audio_artifacts::Purpose::Recording).unwrap().unwrap();
        let mut file = std::fs::OpenOptions::new().write(true).create_new(true).open(&original_system).unwrap();
        file.write_all(&denzic_host_audio_v1_core::wav::wav_header(0)).unwrap();
        file.write_all(&[4,0,5,0,6,0]).unwrap(); file.sync_all().unwrap(); drop(file); drop(lease);
        let before = std::fs::read(&original_system).unwrap();
        let request = serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap();
        let mut row = crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(), request).unwrap().host.sessions.remove(0);
        row.id = "meeting-recovery".into(); row.source = "hostMeeting".into(); row.status = "captured".into();
        row.audio_stored = false; row.retention.audio_cached = false; row.audio_path = None; row.chunks.clear();
        row.meeting_tracks = Some(CompanionV1MeetingTracks { root: anchor.to_string_lossy().into_owned(), state: "recording".into(),
            microphone: vec![], system: vec![], discontinuity: false, issue: None });
        let state = root.join("sessions.json"); super::super::session_store::save(&state, &[row.clone()]).unwrap();
        let expected = super::super::session_store::privacy_authorization(&row).unwrap();
        recover_session_at(&state, &row.id, &expected).unwrap();
        let saved: Vec<crate::companion_v1::CompanionV1HostSession> = serde_json::from_slice(&std::fs::read(&state).unwrap()).unwrap();
        let saved = &saved[0]; let tracks = saved.meeting_tracks.as_ref().unwrap();
        assert!(saved.audio_stored && saved.capture_incomplete); assert_eq!(tracks.state,"needsReview");
        assert_eq!(Path::new(&tracks.microphone[0].path).canonicalize().unwrap(), original_mic.canonicalize().unwrap());
        assert_ne!(Path::new(&tracks.system[0].path).canonicalize().unwrap(), original_system.canonicalize().unwrap());
        assert_eq!(std::fs::read(&original_system).unwrap(), before);
        verify_tracks(tracks, saved.audio_bytes, saved.duration_ms).unwrap();
        if let Some(value) = previous { std::env::set_var("COMPANION_TYPE_RECORDING_DIR", value); }
        else { std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); }
        std::fs::remove_dir_all(root).unwrap();
    }
}
