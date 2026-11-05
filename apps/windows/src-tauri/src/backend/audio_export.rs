//! Session-authorized original audio export, streamed into an atomic replacement.
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use sha2::{Digest, Sha256};
use crate::companion_v1::CompanionV1Snapshot;

#[derive(Debug,Clone,PartialEq,Eq)]
pub enum AudioSource { Single(PathBuf), Imported(PathBuf), Parts(Vec<(PathBuf,u64)>), Meeting { tracks: crate::companion_v1::CompanionV1MeetingTracks, bytes:u64, duration_ms:u64 } }
impl AudioSource {
    fn data_bytes(&self)->Result<u64,String> {
        match self { Self::Single(_) | Self::Imported(_)=>Ok(0), Self::Parts(parts)=>parts.iter().try_fold(0u64,|sum,(_,samples)|
            sum.checked_add(samples.checked_mul(2).ok_or("录音容量无效。")?).ok_or_else(||"录音容量无效。".into())),
            Self::Meeting{tracks,..} => [&tracks.microphone,&tracks.system].into_iter().map(|parts|parts.iter().fold(0u64,|sum,p|sum.saturating_add(p.samples))).max().unwrap_or(0).checked_mul(2).ok_or_else(||"录音容量无效。".into()) }
    }
    pub fn extension(&self)->Result<&'static str,String> {
        if let Self::Imported(path)=self {
            let extension=path.extension().and_then(|s|s.to_str()).unwrap_or("").to_ascii_lowercase();
            return match extension.as_str() {"wav"=>Ok("wav"),"mp3"=>Ok("mp3"),"m4a"=>Ok("m4a"),"mp4"=>Ok("mp4"),"aac"=>Ok("aac"),"flac"=>Ok("flac"),"ogg"=>Ok("ogg"),_=>Err("原文件格式不可用。".into())};
        }
        Ok(if self.data_bytes()? > u64::from(u32::MAX-36) {"zip"} else {"wav"})
    }
}

pub fn source(snapshot: &CompanionV1Snapshot, session_id: &str) -> Result<(AudioSource, String), String> {
    let session = snapshot.host.sessions.iter().find(|s| s.id == session_id).ok_or("这场会议已不存在")?;
    let title = super::export::safe_file_stem(&session.title, session_id);
    if session.source=="hostMeeting" {
        super::meeting_workspace::local_meeting_audio_tracks(snapshot, session_id)?;
        let tracks=session.meeting_tracks.clone().ok_or("会议音轨缺失。")?;
        let audio=AudioSource::Meeting{tracks,bytes:session.audio_bytes,duration_ms:session.duration_ms};
        let extension=audio.extension()?;
        return Ok((audio,format!("{title}-meeting.{extension}")));
    }
    if session.source=="importedAudio" {
        super::library_lifecycle::require_available(session)?;
        if !session.audio_stored || !session.retention.audio_cached {return Err("这场录音的本机音频已删除。".into());}
        let root=super::audio_storage::recording_root()?;
        let original=AudioSource::Imported(super::import_audio::verify_original(session,&root)?);
        let extension=original.extension()?;
        return Ok((original,format!("{title}-original.{extension}")));
    }
    let path = super::meeting_workspace::local_audio_path(snapshot, session_id)?;
    let audio=if let Some(parts)=super::host_segmented_capture::saved_parts(session)? {
        if parts[0].0!=path {return Err("这场录音的分段尚未完整，未导出。".into());}
        AudioSource::Parts(parts)
    } else if session.device_recording_key.is_some() && (session.chunks.iter()
        .any(|chunk|chunk.stopped_at.as_deref()==Some("verified-v2-session-part"))
        || path.file_name().and_then(|name|name.to_str()).is_some_and(|name|name.contains(".parts-"))) {
        let parts=super::recording_wire::receiver::Receiver::verified_audio_parts(session)?;
        if parts.is_empty() || parts[0].0.canonicalize().ok().as_ref()!=Some(&path) {return Err("这场录音的分段尚未完整，未导出。".into());}
        if parts.len()==1 {AudioSource::Single(parts[0].0.clone())} else {AudioSource::Parts(parts)}
    } else { AudioSource::Single(path) };
    let extension=audio.extension()?;
    Ok((audio, format!("{title}-original.{extension}")))
}

pub fn guard_destination(snapshot:&CompanionV1Snapshot,destination:&Path)->Result<(),String>{
    // The native chooser authorizes an output location, never destruction of
    // this or another retained recording in the current library.
    if let Ok(target) = destination.canonicalize() {
        for session in &snapshot.host.sessions {
            for raw in session.audio_path.iter().chain(session.chunks.iter().filter_map(|c| c.path.as_ref()))
                .chain(session.meeting_tracks.iter().flat_map(|t|t.microphone.iter().chain(&t.system).map(|p|&p.path))) {
                if Path::new(raw).canonicalize().is_ok_and(|p| p == target) {
                    return Err("请选择新的文件位置，不能覆盖会议库中的原始录音。".into());
                }
            }
        }
    }
    Ok(())
}

pub fn export(snapshot: &CompanionV1Snapshot, session_id: &str, destination: &Path) -> Result<u64, String> {
    let (input, _) = source(snapshot, session_id)?;
    guard_destination(snapshot,destination)?;
    copy_source_atomic(&input, destination)
}

pub fn copy_source_atomic(source:&AudioSource,destination:&Path)->Result<u64,String> {
    match source { AudioSource::Single(path)=>copy_atomic(path,destination),
        AudioSource::Imported(path)=>copy_atomic_inner(path,destination,false),
        AudioSource::Parts(parts)=>copy_parts_atomic(parts,destination),
        AudioSource::Meeting{tracks,bytes,duration_ms}=>copy_meeting_atomic(tracks,*bytes,*duration_ms,destination) }
}

fn copy_meeting_atomic(tracks:&crate::companion_v1::CompanionV1MeetingTracks, bytes:u64, duration_ms:u64, destination:&Path)->Result<u64,String> {
    let all=tracks.microphone.iter().chain(&tracks.system).collect::<Vec<_>>();
    let _leases=all.iter().map(|part|super::audio_artifacts::usage(Path::new(&part.path))).collect::<Result<Vec<_>,_>>()?;
    super::meeting_audio_recovery::verify_tracks(tracks,bytes,duration_ms)?;
    if let Ok(target)=destination.canonicalize() {
        if all.iter().any(|part|Path::new(&part.path).canonicalize().is_ok_and(|path|path==target)) {
            return Err("不能用导出覆盖原音，请另选位置。".into());
        }
    }
    let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).ok_or("请选择完整的保存路径")?;
    fs::create_dir_all(parent).map_err(|e|format!("无法创建保存目录：{e}"))?;
    let temporary=parent.join(format!(".companion-meeting-audio-{}.tmp",uuid::Uuid::new_v4()));
    let result=(||{
        let source=AudioSource::Meeting{tracks:tracks.clone(),bytes,duration_ms};
        let file=OpenOptions::new().write(true).create_new(true).open(&temporary).map_err(|e|e.to_string())?;
        let file=if source.extension()?=="zip" {
            let mut archive=zip::ZipWriter::new(file);
            for (label,parts) in [("microphone",&tracks.microphone),("computer",&tracks.system)] {
                for (index,part) in parts.iter().enumerate() {
                    archive.start_file(format!("{label}-{:05}.wav",index+1),zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored).large_file(true)).map_err(|e|e.to_string())?;
                    let mut input=File::open(&part.path).map_err(|e|e.to_string())?;
                    std::io::copy(&mut input,&mut archive).map_err(|e|e.to_string())?;
                }
            }
            archive.finish().map_err(|e|e.to_string())?
        } else {
            let mut output=file;let size=u32::try_from(source.data_bytes()?).map_err(|_|"录音容量超出WAV格式。")?;
            output.write_all(&denzic_host_audio_v1_core::wav::wav_header(size)).map_err(|e|e.to_string())?;
            let samples=super::meeting_audio_mix::mix(&tracks.microphone,&tracks.system,|values|{
                let mut block=Vec::with_capacity(values.len()*2);for sample in values {block.extend_from_slice(&sample.to_le_bytes());}
                output.write_all(&block).map_err(|e|e.to_string())
            })?;
            if samples.checked_mul(2)!=Some(u64::from(size)) {return Err("会议音轨长度已变化。".into());}
            output
        };
        file.sync_all().map_err(|e|e.to_string())?;drop(file);
        super::meeting_audio_recovery::verify_tracks(tracks,bytes,duration_ms)?;
        if source.extension()?=="wav" {super::meeting_workspace::validate_wav(&temporary)?;}
        let length=fs::metadata(&temporary).map_err(|e|e.to_string())?.len();
        super::export::replace_file(&temporary,destination)?;Ok(length)
    })();
    if result.is_err(){let _=fs::remove_file(&temporary);}result
}

fn copy_parts_atomic(parts:&[(PathBuf,u64)],destination:&Path)->Result<u64,String> {
    let source=AudioSource::Parts(parts.to_vec());
    let zip=source.extension()?=="zip";
    copy_parts_as(parts,destination,zip)
}

fn copy_parts_as(parts:&[(PathBuf,u64)],destination:&Path,zip:bool)->Result<u64,String> {
    let source=AudioSource::Parts(parts.to_vec());
    if parts.len()<2 {return Err("录音分段不完整。".into());}
    if let Ok(target)=destination.canonicalize() {
        if parts.iter().any(|(part,_)|part.canonicalize().is_ok_and(|path|path==target)) {
            return Err("不能用导出覆盖原音，请另选位置。".into());
        }
    }
    let parent=destination.parent().filter(|p|!p.as_os_str().is_empty()).ok_or("请选择完整的保存路径")?;
    fs::create_dir_all(parent).map_err(|e|format!("无法创建保存目录：{e}"))?;
    let temporary=parent.join(format!(".companion-audio-{}.tmp",uuid::Uuid::new_v4()));
    let result=(|| {
        let file=OpenOptions::new().write(true).create_new(true).open(&temporary).map_err(|e|e.to_string())?;
        let (mut archive,mut output)=if zip {(Some(zip::ZipWriter::new(file)),None)} else {(None,Some(file))};
        if let Some(out)=output.as_mut() {
            let pcm=u32::try_from(source.data_bytes()?).map_err(|_|"录音容量超出WAV格式。")?;
            out.write_all(&denzic_host_audio_v1_core::wav::wav_header(pcm)).map_err(|e|e.to_string())?;
        }
        let mut buffer=[0u8;65_536];
        for (index,(path,samples)) in parts.iter().enumerate() {
            super::meeting_workspace::validate_wav(path)?;
            let expected=samples.checked_mul(2).and_then(|n|n.checked_add(44)).ok_or("录音容量无效。")?;
            let mut input=File::open(path).map_err(|e|format!("无法读取原音：{e}"))?;
            if input.metadata().map_err(|e|e.to_string())?.len()!=expected {return Err("录音分段已变化，请重试。".into());}
            let mut header=[0u8;44];input.read_exact(&mut header).map_err(|e|e.to_string())?;
            let pcm=u32::try_from(samples.checked_mul(2).ok_or("录音容量无效。")?).map_err(|_|"录音容量无效。")?;
            if header!=denzic_host_audio_v1_core::wav::wav_header(pcm) {return Err("录音分段格式无效。".into());}
            let mut hash=Sha256::new();hash.update(header);
            if let Some(writer)=archive.as_mut() {
                let options=zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored).large_file(true);
                writer.start_file(format!("录音-{:05}.wav",index+1),options).map_err(|e|e.to_string())?;
                writer.write_all(&header).map_err(|e|e.to_string())?;
            }
            let mut copied=44u64;
            loop {let n=input.read(&mut buffer).map_err(|e|e.to_string())?;if n==0{break;}
                copied=copied.checked_add(n as u64).ok_or("录音容量无效。")?;if copied>expected{return Err("录音分段已变化，请重试。".into());}
                hash.update(&buffer[..n]);
                if let Some(writer)=archive.as_mut(){writer.write_all(&buffer[..n]).map_err(|e|e.to_string())?;}
                else {output.as_mut().ok_or("无法保存录音。")?.write_all(&buffer[..n]).map_err(|e|e.to_string())?;}
            }
            if copied!=expected{return Err("录音分段读取不完整。".into());}
            let mut current=File::open(path).map_err(|e|e.to_string())?;let mut current_hash=Sha256::new();
            loop {let n=current.read(&mut buffer).map_err(|e|e.to_string())?;if n==0{break;}current_hash.update(&buffer[..n]);}
            if hash.finalize()!=current_hash.finalize(){return Err("录音在保存期间发生变化，请重试。".into());}
        }
        let file=if let Some(writer)=archive {writer.finish().map_err(|e|e.to_string())?} else {output.take().ok_or("无法保存录音。")?};
        file.sync_all().map_err(|e|e.to_string())?;drop(file);
        if !zip {super::meeting_workspace::validate_wav(&temporary)?;}
        let bytes=fs::metadata(&temporary).map_err(|e|e.to_string())?.len();
        super::export::replace_file(&temporary,destination)?;Ok(bytes)
    })();
    if result.is_err(){let _=fs::remove_file(&temporary);}result
}

pub fn copy_atomic(source: &Path, destination: &Path) -> Result<u64, String> {
    copy_atomic_inner(source,destination,true)
}
fn copy_atomic_inner(source: &Path, destination: &Path, validate_wav:bool) -> Result<u64, String> {
    if validate_wav { super::meeting_workspace::validate_wav(source)?; }
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
        if validate_wav {super::meeting_workspace::validate_wav(&temporary)?;}
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

    #[test]
    fn segmented_export_writes_every_part_and_zip_fallback_preserves_each_wav() {
        let root=std::env::temp_dir().join(format!("companion-segmented-export-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();let first=root.join("first.wav");let second=root.join("second.wav");
        let one=wav();let mut two=wav();two[44..].copy_from_slice(&[1,2,3,4]);
        fs::write(&first,&one).unwrap();fs::write(&second,&two).unwrap();
        let parts=vec![(first.clone(),2),(second.clone(),2)];let output=root.join("all.wav");
        copy_parts_atomic(&parts,&output).unwrap();let got=fs::read(&output).unwrap();
        assert_eq!(got.len(),52);assert_eq!(&got[..44],&denzic_host_audio_v1_core::wav::wav_header(8));
        assert_eq!(&got[44..],&[0,0,0,0,1,2,3,4]);
        let archive=root.join("all.zip");copy_parts_as(&parts,&archive,true).unwrap();
        let mut zip=zip::ZipArchive::new(File::open(&archive).unwrap()).unwrap();assert_eq!(zip.len(),2);
        for (index,expected) in [one.clone(),two.clone()].iter().enumerate() {let mut data=Vec::new();
            zip.by_index(index).unwrap().read_to_end(&mut data).unwrap();assert_eq!(&data,expected);}
        assert_eq!(AudioSource::Parts(vec![(first.clone(),u64::from(u32::MAX)/2)]).extension().unwrap(),"zip");
        fs::write(&second,b"bad").unwrap();assert!(copy_parts_atomic(&parts,&output).is_err());assert_eq!(fs::read(&output).unwrap(),got);
        assert_eq!(fs::read(&first).unwrap(),one);fs::remove_dir_all(root).unwrap();
    }
}
