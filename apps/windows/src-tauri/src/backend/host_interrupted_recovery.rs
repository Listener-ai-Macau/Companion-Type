//! Conservative copy-only recovery prototype for an interrupted host WAV.
//! The original remains untouched; callers must still commit an exact session
//! association before presenting the copy to the user.
use std::{fs::{self, File}, io::{Read, Write}, path::{Path, PathBuf}};
use sha2::{Digest, Sha256};
use super::audio_artifacts::{self};

pub(super) struct RecoveredHostAudio {
    pub path: PathBuf,
    pub bytes: u64,
    pub duration_ms: u64,
    _writer: audio_artifacts::WriterLease,
}

fn digest(path: &Path) -> Result<[u8; 32], String> {
    let mut input = File::open(path).map_err(|e| format!("原文件读取失败：{e}"))?;
    let mut hash = Sha256::new();
    let mut block = [0u8; 64 * 1024];
    loop {
        let n = input.read(&mut block).map_err(|e| format!("原文件读取失败：{e}"))?;
        if n == 0 { break; }
        hash.update(&block[..n]);
    }
    Ok(hash.finalize().into())
}

pub(super) fn recover_copy(source: &Path) -> Result<RecoveredHostAudio, String> {
    // This also rejects a live writer, unknown provenance and symlinks.
    let pinned = audio_artifacts::interrupted_host_writer(source)?;
    let metadata = fs::symlink_metadata(source).map_err(|_| "原录音无法读取。")?;
    let size = metadata.len();
    if !metadata.is_file() || metadata.file_type().is_symlink() || size <= 45
        || size > 512 * 1024 * 1024 {
        return Err("原录音长度无法安全恢复，文件保留。".into());
    }
    // A crash may leave just one byte of the last 16-bit PCM sample. Never
    // fabricate its missing half: copy only complete samples and retain the
    // original byte-for-byte, including that trailing byte.
    let partial_tail = (size - 44) % 2;
    let payload = u32::try_from(size - 44 - partial_tail).map_err(|_| "原录音过长，文件保留。")?;
    let mut input = File::open(source).map_err(|_| "原录音无法打开。")?;
    let mut header = [0u8; 44];
    input.read_exact(&mut header).map_err(|_| "原录音文件头不完整。")?;
    let placeholder = denzic_host_audio_v1_core::wav::wav_header(0);
    let complete = denzic_host_audio_v1_core::wav::wav_header(payload);
    // The writer replaces the zero-size header from the beginning with this
    // exact finalized header. A crash during write_all may leave a prefix of
    // the new header and a suffix of the placeholder. Accept only a prefix
    // matching this known transition and only with complete samples. With an
    // incomplete sample the writer's final byte count is not knowable, so the
    // earlier zero-header rule remains the sole safe match.
    let interrupted_backfill = partial_tail == 0 && (0..=header.len()).any(|cut| {
        header[..cut] == complete[..cut] && header[cut..] == placeholder[cut..]
    });
    // Older writers updated the header only after a whole callback. A disk-full
    // error can leave a valid shorter header followed by more complete samples.
    // The exclusive, recorded product ownership above is required before using
    // those bytes. Require complete samples and leave the original untouched;
    // the existing conservative odd-tail rule remains unchanged.
    let declared = u32::from_le_bytes(header[40..44].try_into().expect("fixed header"));
    let prior_complete_header = partial_tail == 0 && declared % 2 == 0 && declared < payload
        && header == denzic_host_audio_v1_core::wav::wav_header(declared);
    if header != placeholder && !interrupted_backfill && !prior_complete_header {
        return Err("原录音不是可确认的录音格式，文件保留。".into());
    }
    let before = digest(source)?;
    audio_artifacts::checkpoint_interrupted_host(&pinned, source, size, &before)?;
    let destination = source.parent().ok_or("原录音目录不可用。")?
        .join(format!("recovered-{}.wav", uuid::Uuid::new_v4().simple()));
    audio_artifacts::generated_crash_safe(&pinned, source, &destination, |output| {
        output.write_all(&denzic_host_audio_v1_core::wav::wav_header(payload))
            .map_err(|e| format!("不能写入恢复副本：{e}"))?;
        #[cfg(test)]
        if std::env::var_os("COMPANION_TEST_RECOVERY_CRASH_AFTER_HEADER").is_some() {
            output.write_all(&[7u8; 128]).unwrap();
            output.sync_all().unwrap();
            std::process::exit(0);
        }
        let mut streamed = Sha256::new();
        streamed.update(header);
        let mut copied = 0u64;
        let mut read_bytes = 0u64;
        let mut block = [0u8; 64 * 1024];
        loop {
            let n = input.read(&mut block).map_err(|e| format!("不能读取录音：{e}"))?;
            if n == 0 { break; }
            let complete = (u64::from(payload) - copied).min(n as u64) as usize;
            output.write_all(&block[..complete]).map_err(|e| format!("不能复制录音：{e}"))?;
            streamed.update(&block[..n]);
            copied += complete as u64;
            read_bytes += n as u64;
        }
        let copied_digest: [u8; 32] = streamed.finalize().into();
        if copied != u64::from(payload) || read_bytes != size - 44 || copied_digest != before || digest(source)? != before {
            return Err("原录音在恢复时发生变化，原文件保留。".into());
        }
        output.sync_all().map_err(|e| format!("不能保存恢复副本：{e}"))?;
        Ok(())
    })?;
    super::meeting_workspace::validate_wav(&destination)?;
    // Link both the raw original and the derivative to the retained meeting.
    // Explicit future privacy erasure reaches the exact two files together.
    audio_artifacts::attach_group(source, &destination)?;
    Ok(RecoveredHostAudio { path: destination, bytes: u64::from(payload) + 44, duration_ms: u64::from(payload) * 1000 / 32000, _writer: pinned })
}


/// Attach one verified copy only to the exact saved session the user selected.
/// This does not start transcription or erase the unfinished original.
pub(super) fn recover_session_at(state_path: &Path, id: &str, expected: &(String, String)) -> Result<(), String> {
    recover_session_with(state_path, id, expected, || Ok(()))
}

pub(super) fn recover_session_with(state_path: &Path, id: &str, expected: &(String, String),
    after_copy: impl FnOnce() -> Result<(), String>) -> Result<(), String> {
    let loaded = super::session_store::load(state_path);
    if loaded.state.status != "ready" { return Err("会议库尚未恢复，原录音保留。".into()); }
    let bytes = loaded.bytes.ok_or("会议记录不存在，原录音保留。")?;
    let rows: Vec<crate::companion_v1::CompanionV1HostSession> =
        serde_json::from_slice(&bytes).map_err(|_| "会议记录无法读取，原录音保留。")?;
    let old = rows.iter().find(|row| row.id == id).ok_or("原会议已不存在，未恢复录音。")?;
    if old.source != "hostMicrophone" || old.audio_stored || old.organization.trashed_at.is_some()
        || old.recorder_control.is_some() {
        return Err("这条记录不符合本机中断恢复条件，原文件保留。".into());
    }
    let original = old.audio_path.as_deref().map(Path::new).filter(|p| p.is_absolute())
        .ok_or("没有可确认的本机原录音路径。")?.to_owned();
    let source_key = audio_artifacts::reference_key(&original)?;
    if rows.iter().filter(|row| row.audio_path.as_deref().is_some_and(|p| {
        audio_artifacts::reference_key(Path::new(p)).is_ok_and(|key| key == source_key)
    })).count() != 1 {
        return Err("原录音被多个记录引用，未自动恢复或替换。".into());
    }
    if old.chunks.iter().any(|chunk| chunk.path.as_deref().is_some_and(|p| {
        audio_artifacts::reference_key(Path::new(p)).map_or(true, |key| key != source_key)
    })) {
        return Err("这条录音还关联其他片段，未覆盖已有记录。".into());
    }
    let authorization = super::session_store::privacy_authorization(old)?;
    if &authorization != expected { return Err("原会议已变化，请刷新后再确认恢复；原文件保留。".into()); }
    let copy = recover_copy(&original)?;
    after_copy()?;
    let copy_path = copy.path.to_str().ok_or("恢复副本路径无法保存。")?.to_string();
    let timestamp = super::observation_timestamp();
    super::session_store::update_checked(state_path, |current| {
        let row = current.iter_mut().find(|row| row.id == id).ok_or("原会议已移除；原文件与恢复副本保留。")?;
        if row.source != "hostMicrophone" || row.audio_stored || row.organization.trashed_at.is_some()
            || row.recorder_control.is_some() || super::session_store::privacy_authorization(row)? != authorization {
            return Err("原会议在恢复期间发生变化；原文件与恢复副本保留。".into());
        }
        row.audio_path = Some(copy_path.clone());
        row.audio_bytes = copy.bytes;
        row.duration_ms = copy.duration_ms;
        row.audio_stored = true;
        row.retention.audio_cached = true;
        row.capture_incomplete = true;
        if row.status == "recording" { row.status = "captured".into(); }
        row.chunks = crate::companion_v1::seal_companion_v1_session_chunks(row, &timestamp, copy.duration_ms, Some(copy.bytes));
        super::interrupted_capture::hold(row);
        Ok(())
    })?;
    Ok(())
}
