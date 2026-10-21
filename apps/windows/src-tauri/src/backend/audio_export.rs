//! Session-authorized original audio export, streamed into an atomic replacement.
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use sha2::{Digest, Sha256};
use crate::companion_v1::CompanionV1Snapshot;

pub fn source(snapshot: &CompanionV1Snapshot, session_id: &str) -> Result<(PathBuf, String), String> {
    let path = super::meeting_workspace::local_audio_path(snapshot, session_id)?;
    let session = snapshot.host.sessions.iter().find(|s| s.id == session_id).ok_or("这场会议已不存在")?;
    let title = super::export::safe_file_stem(&session.title, session_id);
    Ok((path, format!("{title}-original.wav")))
}

pub fn export(snapshot: &CompanionV1Snapshot, session_id: &str, destination: &Path) -> Result<u64, String> {
    let (input, _) = source(snapshot, session_id)?;
    // The native chooser authorizes an output location, never destruction of
    // this or another retained recording in the current library.
    if let Ok(target) = destination.canonicalize() {
        for session in &snapshot.host.sessions {
            for raw in session.audio_path.iter().chain(session.chunks.iter().filter_map(|c| c.path.as_ref())) {
                if Path::new(raw).canonicalize().is_ok_and(|p| p == target) {
                    return Err("请选择新的文件位置，不能覆盖会议库中的原始录音。".into());
                }
            }
        }
    }
    copy_atomic(&input, destination)
}

pub fn copy_atomic(source: &Path, destination: &Path) -> Result<u64, String> {
    super::meeting_workspace::validate_wav(source)?;
    if source.canonicalize().ok() == destination.canonicalize().ok() {
        return Err("不能用导出覆盖原音，请另选位置。".into());
    }
    let parent = destination.parent().filter(|p| !p.as_os_str().is_empty()).ok_or("请选择完整的保存路径")?;
    fs::create_dir_all(parent).map_err(|e| format!("无法创建保存目录：{e}"))?;
    let temporary = parent.join(format!(".companion-audio-{}.tmp", uuid::Uuid::new_v4()));
    let result = (|| {
        let mut input = File::open(source).map_err(|e| format!("无法读取原音：{e}"))?;
        let expected = input.metadata().map_err(|e| e.to_string())?.len();
        let mut output = OpenOptions::new().write(true).create_new(true).open(&temporary).map_err(|e| e.to_string())?;
        let mut buffer = [0u8; 65_536];
        let mut copied = 0u64;
        let mut hash = Sha256::new();
        loop {
            let count = input.read(&mut buffer).map_err(|e| format!("读取原音中断：{e}"))?;
            if count == 0 { break; }
            copied += count as u64;
            if copied > expected { return Err("原音在保存期间发生变化，请重试。".into()); }
            output.write_all(&buffer[..count]).map_err(|e| format!("保存原音失败：{e}"))?;
            hash.update(&buffer[..count]);
        }
        output.sync_all().map_err(|e| format!("原音尚未安全保存：{e}"))?;
        drop(output);
        if copied != expected { return Err("原音读取不完整，已有目标文件保持不变。".into()); }
        super::meeting_workspace::validate_wav(&temporary)?;
        // Catch a file replaced/modified while copying, before publishing it.
        let mut current = File::open(source).map_err(|e| e.to_string())?;
        let mut current_hash = Sha256::new();
        loop {
            let count = current.read(&mut buffer).map_err(|e| e.to_string())?;
            if count == 0 { break; }
            current_hash.update(&buffer[..count]);
        }
        if hash.finalize() != current_hash.finalize() { return Err("原音在保存期间发生变化，请重试。".into()); }
        super::export::replace_file(&temporary, destination)?;
        Ok(copied)
    })();
    if result.is_err() { let _ = fs::remove_file(&temporary); }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    fn wav() -> Vec<u8> {
        let mut b=Vec::new(); b.extend(b"RIFF"); b.extend(40u32.to_le_bytes()); b.extend(b"WAVEfmt ");
        b.extend(16u32.to_le_bytes()); b.extend(1u16.to_le_bytes()); b.extend(1u16.to_le_bytes());
        b.extend(16000u32.to_le_bytes()); b.extend(32000u32.to_le_bytes()); b.extend(2u16.to_le_bytes());
        b.extend(16u16.to_le_bytes()); b.extend(b"data"); b.extend(4u32.to_le_bytes()); b.extend([0u8;4]); b
    }
    #[test]
    fn exact_original_copy_and_failed_export_preserve_files() {
        let root=std::env::temp_dir().join(format!("companion-original-export-{}",uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap(); let input=root.join("source.wav"); let output=root.join("saved.wav");
        fs::write(&input,wav()).unwrap(); fs::write(&output,b"previous file").unwrap();
        assert_eq!(copy_atomic(&input,&output).unwrap(),48); assert_eq!(fs::read(&output).unwrap(),wav());
        assert!(copy_atomic(&input,&input).is_err()); assert_eq!(fs::read(&input).unwrap(),wav());
        fs::write(&input,b"truncated wav").unwrap(); assert!(copy_atomic(&input,&output).is_err());
        assert_eq!(fs::read(&output).unwrap(),wav());
        let mut malformed = wav(); malformed.extend(b"unindexed trailing data");
        fs::write(&input,malformed).unwrap(); assert!(copy_atomic(&input,&output).is_err());
        assert_eq!(fs::read(&output).unwrap(),wav());
        assert!(!fs::read_dir(&root).unwrap().any(|e| e.unwrap().path().extension().is_some_and(|e|e=="tmp")));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn export_is_bound_to_current_session_and_cannot_overwrite_other_recordings() {
        let root=std::env::temp_dir().join(format!("companion-session-export-{}",uuid::Uuid::new_v4()));
        fs::create_dir_all(&root).unwrap(); let input=root.join("source.wav"); let other=root.join("other.wav");
        let output=root.join("backup.wav"); fs::write(&input,wav()).unwrap(); fs::write(&other,wav()).unwrap();
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap();
        let mut session=snapshot.host.sessions[0].clone(); session.id="original".into();
        session.audio_path=Some(input.to_string_lossy().into()); session.audio_stored=true;
        session.retention.audio_cached=true; session.pending_reason=None; session.status="captured".into();
        session.transcript_text.clear(); session.minutes=None;
        let mut second=session.clone(); second.id="second".into(); second.audio_path=Some(other.to_string_lossy().into());
        snapshot.host.sessions=vec![session,second]; snapshot.meeting.active=false; snapshot.device.recording=false;
        assert!(export(&snapshot,"missing",&output).is_err()); assert!(!output.exists());
        assert!(export(&snapshot,"original",&other).is_err()); assert_eq!(fs::read(&other).unwrap(),wav());
        assert_eq!(export(&snapshot,"original",&output).unwrap(),48);
        snapshot.device.recording=true; assert!(export(&snapshot,"original",&output).is_err());
        assert_eq!(fs::read(&output).unwrap(),wav()); fs::remove_dir_all(root).unwrap();
    }
}
