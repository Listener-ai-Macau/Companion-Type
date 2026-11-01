//! Rolling WAV output for long local recordings. This writer is not yet wired
//! to capture: persistence, recovery, playback and export must move together.
use std::fs::{File, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, atomic::{AtomicBool,Ordering}, mpsc::{self,SyncSender,TrySendError}};
use std::thread::{self,JoinHandle};

// RIFF's length includes the extra 36 bytes, and PCM samples are two bytes.
const MAX_PCM_BYTES: u32 = (u32::MAX - 36) & !1;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct HostAudioPart {
    pub path: PathBuf,
    pub samples: u64,
}

/// Store one physical part per entry, preserving the continuous sample axis.
pub(super) fn session_chunks(session_id: &str, parts: &[HostAudioPart]) -> Result<Vec<crate::companion_v1::CompanionV1AudioChunk>, String> {
    if parts.len()<2 {return Err("录音分段不完整。".into());}
    parts.iter().enumerate().map(|(index,part)| {
        let bytes=part.samples.checked_mul(2).and_then(|n|n.checked_add(44)).ok_or("录音容量无效。")?;
        if part.samples==0 || bytes>u64::from(MAX_PCM_BYTES)+44 {return Err("录音分段容量无效。".into());}
        Ok(crate::companion_v1::CompanionV1AudioChunk {
            id:format!("{session_id}-host-part-{index:08}"),path:Some(part.path.to_str().ok_or("录音路径无效。")?.into()),
            started_at:None,stopped_at:None,duration_ms:part.samples/16,bytes,status:"sealed".into(),
        })
    }).collect()
}

/// Validate every declared host part before playback, ASR, export or backup.
/// Legacy single-file host and device sessions use their existing paths.
pub(crate) fn saved_parts(row:&crate::companion_v1::CompanionV1HostSession)->Result<Option<Vec<(PathBuf,u64)>>,String> {
    let prefix=format!("{}-host-part-",row.id);
    if !row.chunks.iter().any(|c|c.id.starts_with(&prefix)) {return Ok(None);}
    if !matches!(row.source.as_str(),"hostMicrophone" | "importedAudio") || row.device_recording_key.is_some() || !row.audio_stored || row.chunks.len()<2 {
        return Err("录音分段尚未完整保存。".into());
    }
    let primary=Path::new(row.audio_path.as_deref().ok_or("录音路径缺失。")?).canonicalize().map_err(|_|"录音文件缺失。")?;
    let root=primary.parent().ok_or("录音目录不可用。")?;
    let mut parts=Vec::new();let mut samples=0u64;let mut total_bytes=0u64;
    for (index,chunk) in row.chunks.iter().enumerate() {
        if chunk.id!=format!("{}-host-part-{index:08}",row.id) || chunk.status!="sealed" {
            return Err("录音分段不完整。".into());
        }
        let path=Path::new(chunk.path.as_deref().ok_or("录音分段缺失。")?).canonicalize().map_err(|_|"录音分段缺失。")?;
        if path.parent()!=Some(root) || (index==0 && path!=primary) || parts.iter().any(|(old,_)|old==&path) {
            return Err("录音分段路径无效。".into());
        }
        let pcm=chunk.bytes.checked_sub(44).ok_or("录音分段容量无效。")?;
        if pcm==0 || pcm%2!=0 || pcm>u64::from(MAX_PCM_BYTES) || chunk.duration_ms!=pcm/32 {
            return Err("录音分段时长无效。".into());
        }
        let mut input=File::open(&path).map_err(|_|"录音分段无法读取。")?;
        if input.metadata().map_err(|_|"录音分段无法读取。")?.len()!=chunk.bytes {return Err("录音分段不完整。".into());}
        let mut header=[0u8;44];input.read_exact(&mut header).map_err(|_|"录音分段不完整。")?;
        if header!=denzic_host_audio_v1_core::wav::wav_header(pcm as u32) {return Err("录音分段格式无效。".into());}
        samples=samples.checked_add(pcm/2).ok_or("录音时长无效。")?;
        total_bytes=total_bytes.checked_add(chunk.bytes).ok_or("录音容量无效。")?;
        parts.push((path,pcm/2));
    }
    if row.duration_ms!=samples/16 || row.audio_bytes!=total_bytes {return Err("录音分段时长不完整。".into());}
    Ok(Some(parts))
}

pub(super) struct RollingHostWav {
    anchor: PathBuf,
    file: File,
    current_bytes: u32,
    limit: u32,
    completed: Vec<HostAudioPart>,
}

/// Own every continuation before its first sample. Hold all leases through
/// capture so a long part is not hashed synchronously on the audio callback.
struct HostPartLeases {
    anchor: PathBuf,
    leases: Vec<super::audio_artifacts::WriteLease>,
}
impl HostPartLeases {
    fn new(anchor: &Path) -> Self { Self { anchor: anchor.to_owned(), leases: Vec::new() } }
    fn prepare(&mut self, next: &Path) -> io::Result<()> {
        use super::audio_artifacts::{self, Purpose, WriteLease};
        let lease=WriteLease::begin(next,next,Purpose::Recording).map_err(io::Error::other)?;
        audio_artifacts::attach_group(next,&self.anchor).map_err(io::Error::other)?;
        if let Some(lease)=lease {self.leases.push(lease);}
        Ok(())
    }
    fn finish(self) -> Result<(),String> {
        for lease in self.leases {lease.finish()?;}
        Ok(())
    }
}

/// The sound callback only queues samples. File rotation, flushes and
/// provenance checkpoints run on a separate writer thread.
#[derive(Clone)]
pub(super) struct CaptureQueue {
    sender: SyncSender<Vec<i16>>,
    failed: Arc<AtomicBool>,
    error: Arc<Mutex<Option<String>>>,
}
impl CaptureQueue {
    pub fn push(&self, samples: Vec<i16>) {
        if self.failed.load(Ordering::Acquire) {return;}
        match self.sender.try_send(samples) {
            Ok(()) => {},
            Err(TrySendError::Full(_)) => self.fail("录音保存速度跟不上采集，已保留此前音频。"),
            Err(TrySendError::Disconnected(_)) => self.fail("录音保存线程已中断，已保留此前音频。"),
        }
    }
    fn fail(&self, message:&str) {
        self.failed.store(true,Ordering::Release);
        if let Ok(mut error)=self.error.lock() {if error.is_none(){*error=Some(message.into());}}
    }
}

pub(super) struct CaptureArchive {
    queue: Option<CaptureQueue>,
    worker: Option<JoinHandle<ArchiveOutcome>>,
}
pub(super) struct ArchiveOutcome {
    pub parts: Vec<HostAudioPart>,
    pub error: Option<String>,
    pub ownership_confirmed: bool,
}
impl CaptureArchive {
    pub fn start(anchor:&Path)->io::Result<Self> { Self::start_with_limit(anchor,MAX_PCM_BYTES) }
    fn start_with_limit(anchor:&Path,limit:u32)->io::Result<Self> {
        let mut writer=RollingHostWav::create_with_limit(anchor,limit)?;
        let mut leases=HostPartLeases::new(anchor);
        let (sender,receiver)=mpsc::sync_channel::<Vec<i16>>(512);
        let failed=Arc::new(AtomicBool::new(false));let error=Arc::new(Mutex::new(None::<String>));
        let queue=CaptureQueue{sender,failed:Arc::clone(&failed),error:Arc::clone(&error)};
        let worker=thread::Builder::new().name("companion-host-audio-writer".into()).spawn(move|| {
            for samples in receiver {
                if let Err(e)=writer.append(&samples,|path|leases.prepare(path)) {
                    failed.store(true,Ordering::Release);
                    if let Ok(mut slot)=error.lock() {if slot.is_none(){*slot=Some(format!("录音写入失败：{e}"));}}
                    break;
                }
            }
            let parts=match writer.finish() {
                Ok(parts)=>parts,
                Err(e)=>{if let Ok(mut slot)=error.lock(){if slot.is_none(){*slot=Some(format!("录音保存失败：{e}"));}} Vec::new()}
            };
            let mut issue=error.lock().ok().and_then(|e|e.clone());
            let ownership_confirmed=if issue.is_none() {
                match leases.finish(){Ok(())=>true,Err(e)=>{issue=Some(format!("录音保存尚未确认：{e}"));false}}
            } else {drop(leases);false};
            ArchiveOutcome{parts,error:issue,ownership_confirmed}
        })?;
        Ok(Self{queue:Some(queue),worker:Some(worker)})
    }
    pub fn queue(&self)->CaptureQueue {self.queue.as_ref().expect("archive active").clone()}
    pub fn error(&self)->Option<String> {self.queue.as_ref()?.error.lock().ok().and_then(|error|error.clone())}
    /// Stop capture first so all callback-owned senders have been dropped.
    pub fn finish(mut self)->Result<ArchiveOutcome,String> {
        drop(self.queue.take());
        self.worker.take().ok_or("录音保存线程不可用。")?.join().map_err(|_|"录音保存线程异常退出，原音保留。".into())
    }
}

impl RollingHostWav {
    pub fn create(anchor: &Path) -> io::Result<Self> {
        Self::create_with_limit(anchor, MAX_PCM_BYTES)
    }

    fn create_with_limit(anchor: &Path, limit: u32) -> io::Result<Self> {
        if limit < 2 || limit > MAX_PCM_BYTES || limit % 2 != 0 {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid WAV part size"));
        }
        let file = Self::create_part(anchor)?;
        Ok(Self { anchor: anchor.to_path_buf(), file, current_bytes: 0, limit, completed: Vec::new() })
    }

    fn create_part(path: &Path) -> io::Result<File> {
        let mut file = OpenOptions::new().write(true).create_new(true).open(path)?;
        file.write_all(&denzic_host_audio_v1_core::wav::wav_header(0))?;
        Ok(file)
    }

    fn current_path(&self) -> io::Result<PathBuf> {
        if self.completed.is_empty() { return Ok(self.anchor.clone()); }
        let stem = self.anchor.file_stem().and_then(|s| s.to_str())
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid recording name"))?;
        Ok(self.anchor.with_file_name(format!("{stem}.host-part-{:08}.wav", self.completed.len())))
    }

    fn finish_current(&mut self) -> io::Result<HostAudioPart> {
        self.file.seek(SeekFrom::Start(0))?;
        self.file.write_all(&denzic_host_audio_v1_core::wav::wav_header(self.current_bytes))?;
        self.file.sync_data()?;
        Ok(HostAudioPart { path: self.current_path()?, samples: u64::from(self.current_bytes / 2) })
    }

    /// The caller must durably record `next` as belonging to the same session
    /// before returning. If checkpointing fails, no new file is opened.
    pub fn append(&mut self, samples: &[i16], mut checkpoint: impl FnMut(&Path) -> io::Result<()>) -> io::Result<()> {
        for sample in samples {
            if self.current_bytes == self.limit {
                let part = self.finish_current()?;
                let next_index = self.completed.len() + 1;
                let stem = self.anchor.file_stem().and_then(|s| s.to_str())
                    .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid recording name"))?;
                let next = self.anchor.with_file_name(format!("{stem}.host-part-{next_index:08}.wav"));
                checkpoint(&next)?;
                let file = Self::create_part(&next)?;
                self.completed.push(part);
                self.file = file;
                self.current_bytes = 0;
            }
            self.file.write_all(&sample.to_le_bytes())?;
            self.current_bytes += 2;
        }
        Ok(())
    }


    /// Efficient conversion of already-preserved imported audio; host capture retains its original write path.
    pub fn append_bulk(&mut self, samples: &[i16], mut checkpoint: impl FnMut(&Path) -> io::Result<()>) -> io::Result<()> {
        let mut remaining=samples;
        while !remaining.is_empty() {
            if self.current_bytes == self.limit {
                let part = self.finish_current()?;
                let next_index = self.completed.len() + 1;
                let stem = self.anchor.file_stem().and_then(|s| s.to_str())
                    .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid recording name"))?;
                let next = self.anchor.with_file_name(format!("{stem}.host-part-{next_index:08}.wav"));
                checkpoint(&next)?;
                let file = Self::create_part(&next)?;
                self.completed.push(part);
                self.file = file;
                self.current_bytes = 0;
            }
            let take=remaining.len().min(((self.limit-self.current_bytes)/2) as usize);
            let mut bytes=Vec::with_capacity(take*2);
            for sample in &remaining[..take] { bytes.extend_from_slice(&sample.to_le_bytes()); }
            self.file.write_all(&bytes)?;
            self.current_bytes+=u32::try_from(bytes.len()).map_err(|_|io::Error::other("audio segment too large"))?;
            remaining=&remaining[take..];
        }
        Ok(())
    }

    pub fn finish(mut self) -> io::Result<Vec<HostAudioPart>> {
        let part = self.finish_current()?;
        self.completed.push(part);
        Ok(self.completed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn root() -> PathBuf {
        let path=std::env::temp_dir().join(format!("companion-host-parts-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&path).unwrap(); path
    }
    #[test]
    fn imported_audio_bulk_writer_rotates_without_losing_samples() {
        let dir=root();let anchor=dir.join("import.wav");let mut writer=RollingHostWav::create_with_limit(&anchor,6).unwrap();
        let mut checkpoints=Vec::new();writer.append_bulk(&[1,2,3,4,5,6,7],|p|{checkpoints.push(p.to_owned());Ok(())}).unwrap();
        let parts=writer.finish().unwrap();assert_eq!(parts.iter().map(|p|p.samples).collect::<Vec<_>>(),vec![3,3,1]);
        assert_eq!(checkpoints.len(),2);let mut actual=Vec::new();
        for part in &parts {let bytes=std::fs::read(&part.path).unwrap();actual.extend(bytes[44..].chunks_exact(2).map(|c|i16::from_le_bytes([c[0],c[1]])));}
        assert_eq!(actual,vec![1,2,3,4,5,6,7]);std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn rolls_without_losing_samples_or_creating_an_empty_extra_part() {
        let dir=root(); let anchor=dir.join("meeting.wav");
        let mut writer=RollingHostWav::create_with_limit(&anchor, 6).unwrap();
        let mut checkpoints=Vec::new();
        writer.append(&[1,2,3,4,5,6,7], |p| {checkpoints.push(p.to_owned()); Ok(())}).unwrap();
        let parts=writer.finish().unwrap();
        assert_eq!(parts.iter().map(|p|p.samples).collect::<Vec<_>>(),vec![3,3,1]);
        assert_eq!(checkpoints, parts[1..].iter().map(|p|p.path.clone()).collect::<Vec<_>>());
        let mut recovered=Vec::new();
        for part in &parts {
            let data=std::fs::read(&part.path).unwrap();
            assert_eq!(&data[..44], &denzic_host_audio_v1_core::wav::wav_header((part.samples*2) as u32));
            recovered.extend(data[44..].chunks_exact(2).map(|s|i16::from_le_bytes([s[0],s[1]])));
        }
        assert_eq!(recovered,vec![1,2,3,4,5,6,7]);
        let exact=dir.join("exact.wav"); let mut w=RollingHostWav::create_with_limit(&exact,2).unwrap();
        w.append(&[7], |_| panic!("no split on exact boundary")).unwrap();
        assert_eq!(w.finish().unwrap().len(),1);
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn failed_checkpoint_or_existing_next_part_never_overwrites_existing_audio() {
        let dir=root(); let anchor=dir.join("meeting.wav");
        let mut w=RollingHostWav::create_with_limit(&anchor,2).unwrap();
        w.append(&[11], |_| Ok(())).unwrap();
        assert!(w.append(&[12], |_| Err(io::Error::other("checkpoint"))).is_err());
        let next=dir.join("meeting.host-part-00000001.wav"); assert!(!next.exists());
        std::fs::write(&next,b"existing audio").unwrap();
        assert!(w.append(&[12], |_| Ok(())).is_err());
        assert_eq!(std::fs::read(&next).unwrap(),b"existing audio");
        let parts=w.finish().unwrap(); assert_eq!(parts[0].samples,1);
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    #[ignore]
    fn abrupt_rolling_capture_child() {
        let Some(anchor)=std::env::var_os("COMPANION_ROLLING_TEST_ANCHOR") else {return};
        let anchor=PathBuf::from(anchor);
        let _lease=super::super::audio_artifacts::WriteLease::begin(
            &anchor,&anchor,super::super::audio_artifacts::Purpose::Recording).unwrap();
        let mut writer=RollingHostWav::create_with_limit(&anchor,6).unwrap();
        let mut parts=HostPartLeases::new(&anchor);
        writer.append(&[10,20,30,40,50],|p|parts.prepare(p)).unwrap();
        // The second WAV still has a placeholder header when the process dies.
        std::process::exit(0);
    }

    #[test]
    #[ignore]
    fn abrupt_queued_capture_child() {
        let Some(anchor)=std::env::var_os("COMPANION_ROLLING_TEST_ANCHOR") else {return};
        let anchor=PathBuf::from(anchor);
        let _lease=super::super::audio_artifacts::WriteLease::begin(
            &anchor,&anchor,super::super::audio_artifacts::Purpose::Recording).unwrap();
        let archive=CaptureArchive::start_with_limit(&anchor,6).unwrap();
        let queue=archive.queue();queue.push(vec![10,20,30,40,50]);
        let next=anchor.with_file_name("crashed.host-part-00000001.wav");
        let until=std::time::Instant::now()+std::time::Duration::from_secs(5);
        while std::fs::metadata(&next).map_or(true,|m|m.len()<48) {
            assert!(std::time::Instant::now()<until,"background writer did not finish the test samples");
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        // Simulate process death while the real archive worker owns its files.
        std::process::exit(0);
    }

    #[test]
    fn registered_parts_survive_process_exit_and_recover_in_order() {
        let dir=root();let anchor=dir.join("crashed.wav");
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::host_segmented_capture::tests::abrupt_rolling_capture_child","--ignored"])
            .env("COMPANION_ROLLING_TEST_ANCHOR",&anchor)
            .env("COMPANION_TYPE_RECORDING_DIR",&dir).output().unwrap();
        assert!(child.status.success(),"{}",String::from_utf8_lossy(&child.stderr));
        unsafe {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&dir)};
        let pinned=super::super::audio_artifacts::interrupted_host_writer(&anchor).unwrap();
        let paths=super::super::audio_artifacts::interrupted_host_parts(&pinned,&anchor).unwrap();
        assert_eq!(paths.len(),2);
        assert_eq!(paths[1].canonicalize().unwrap(),dir.join("crashed.host-part-00000001.wav").canonicalize().unwrap());
        drop(pinned);
        let originals=paths.iter().map(|p|std::fs::read(p).unwrap()).collect::<Vec<_>>();
        let mut recovered=Vec::new();
        for path in &paths {
            let copy=super::super::host_interrupted_recovery::recover_copy(path).unwrap();
            let bytes=std::fs::read(&copy.path).unwrap();
            recovered.extend(bytes[44..].chunks_exact(2).map(|s|i16::from_le_bytes([s[0],s[1]])));
        }
        assert_eq!(recovered,vec![10,20,30,40,50]);
        for (path,before) in paths.iter().zip(originals) {assert_eq!(std::fs::read(path).unwrap(),before);}
        unsafe {std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn missing_last_registered_file_is_allowed_but_missing_middle_is_not() {
        let dir=root();let anchor=dir.join("gap.wav");
        unsafe {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&dir)};
        let lease=super::super::audio_artifacts::WriteLease::begin(
            &anchor,&anchor,super::super::audio_artifacts::Purpose::Recording).unwrap();
        let mut data=denzic_host_audio_v1_core::wav::wav_header(2).to_vec();data.extend([1,2]);
        std::fs::write(&anchor,&data).unwrap();drop(lease);
        let mut leases=HostPartLeases::new(&anchor);
        let first=dir.join("gap.host-part-00000001.wav");leases.prepare(&first).unwrap();
        let pinned=super::super::audio_artifacts::interrupted_host_writer(&anchor).unwrap();
        let parts=super::super::audio_artifacts::interrupted_host_parts(&pinned,&anchor).unwrap();
        assert_eq!(parts.len(),1,"a crash before creating the next file keeps the earlier part");
        drop(pinned);
        let second=dir.join("gap.host-part-00000002.wav");leases.prepare(&second).unwrap();
        std::fs::write(&second,&data).unwrap();
        let pinned=super::super::audio_artifacts::interrupted_host_writer(&anchor).unwrap();
        assert!(super::super::audio_artifacts::interrupted_host_parts(&pinned,&anchor).is_err());
        drop(pinned);drop(leases);
        unsafe {std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn complete_host_parts_flow_through_transcription_export_and_backup() {
        let base=root();let dir=base.join("recordings");let restored_dir=base.join("restored");let backups=base.join("backups");
        for p in [&dir,&restored_dir,&backups] {std::fs::create_dir(p).unwrap();}
        let dir=dir.canonicalize().unwrap();let restored_dir=restored_dir.canonicalize().unwrap();
        unsafe {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&dir)};
        let anchor=dir.join("session.wav");let mut writer=RollingHostWav::create_with_limit(&anchor,6).unwrap();
        writer.append(&[10,20,30,40,50],|_|Ok(())).unwrap();let parts=writer.finish().unwrap();
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingStart,Some("parts-test".into()))).unwrap();
        snapshot.meeting.active=false;snapshot.device.recording=false;snapshot.host.persistence.status="ready".into();
        let row=&mut snapshot.host.sessions[0];row.id="parts-test".into();row.status="captured".into();row.source="hostMicrophone".into();
        row.audio_path=Some(anchor.to_string_lossy().into());row.audio_stored=true;row.retention.audio_cached=true;
        row.duration_ms=parts.iter().map(|p|p.samples).sum::<u64>()/16;
        row.audio_bytes=parts.iter().map(|p|p.samples*2+44).sum();row.chunks=session_chunks(&row.id,&parts).unwrap();
        let declared=saved_parts(row).unwrap().unwrap();assert_eq!(declared.len(),2);
        assert_eq!(super::super::transcription_chunk_paths(row).unwrap().len(),2);
        row.capture_incomplete=true;row.recovery.capture_review_confirmed=false;
        super::super::interrupted_capture::confirm(row).unwrap();
        assert!(row.recovery.capture_review_confirmed);
        let (source,_)=super::super::audio_export::source(&snapshot,"parts-test").unwrap();
        let export=base.join("complete.wav");super::super::audio_export::copy_source_atomic(&source,&export).unwrap();
        let bytes=std::fs::read(&export).unwrap();
        let values=bytes[44..].chunks_exact(2).map(|s|i16::from_le_bytes([s[0],s[1]])).collect::<Vec<_>>();
        assert_eq!(values,vec![10,20,30,40,50]);
        let report=super::super::library_backup::save(&snapshot,&dir,&backups).unwrap();
        unsafe {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&restored_dir)};
        let rows=super::super::library_backup::restore_files(Path::new(&report.path),&restored_dir).unwrap();
        assert_eq!(saved_parts(&rows[0]).unwrap().unwrap().len(),2);
        std::fs::remove_file(restored_dir.join(parts[1].path.file_name().unwrap())).unwrap();
        assert!(saved_parts(&rows[0]).is_err(),"missing later audio cannot become a shorter successful meeting");
        unsafe {std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};
        std::fs::remove_dir_all(base).unwrap();
    }

    #[test]
    fn queued_capture_rotates_and_reports_a_failed_continuation() {
        let dir=root();unsafe {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&dir)};
        let anchor=dir.join("queued.wav");
        let owner=super::super::audio_artifacts::WriteLease::begin(&anchor,&anchor,super::super::audio_artifacts::Purpose::Recording).unwrap();
        let archive=CaptureArchive::start_with_limit(&anchor,6).unwrap();let queue=archive.queue();
        queue.push(vec![1,2,3]);queue.push(vec![4,5]);drop(queue);
        let result=archive.finish().unwrap();assert!(result.error.is_none() && result.ownership_confirmed);
        assert_eq!(result.parts.iter().map(|p|p.samples).collect::<Vec<_>>(),vec![3,2]);
        if let Some(owner)=owner {owner.finish().unwrap();}
        let other=dir.join("failed.wav");let collision=dir.join("failed.host-part-00000001.wav");
        let owner=super::super::audio_artifacts::WriteLease::begin(&other,&other,super::super::audio_artifacts::Purpose::Recording).unwrap();
        std::fs::write(&collision,b"existing").unwrap();let archive=CaptureArchive::start_with_limit(&other,6).unwrap();
        let queue=archive.queue();queue.push(vec![10,20,30,40]);drop(queue);
        let result=archive.finish().unwrap();assert!(result.error.is_some() && !result.ownership_confirmed);
        assert_eq!(result.parts[0].samples,3);assert_eq!(std::fs::read(collision).unwrap(),b"existing");drop(owner);
        unsafe {std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn full_writer_queue_exposes_failure_instead_of_silently_discarding_audio() {
        let (sender,_receiver)=mpsc::sync_channel(0);
        let queue=CaptureQueue{sender,failed:Arc::new(AtomicBool::new(false)),error:Arc::new(Mutex::new(None))};
        queue.push(vec![1,2]);
        assert!(queue.failed.load(Ordering::Acquire));
        assert!(queue.error.lock().unwrap().as_deref().unwrap().contains("跟不上采集"));
    }

    #[test]
    fn crashed_parts_recover_as_one_session_and_remain_backupable() {
        let base=root();let dir=base.join("recordings");let target=base.join("target");let backups=base.join("backups");
        for p in [&dir,&target,&backups] {std::fs::create_dir(p).unwrap();}
        let dir=dir.canonicalize().unwrap();let target=target.canonicalize().unwrap();let anchor=dir.join("crashed.wav");
        let child=std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact","backend::host_segmented_capture::tests::abrupt_queued_capture_child","--ignored"])
            .env("COMPANION_ROLLING_TEST_ANCHOR",&anchor).env("COMPANION_TYPE_RECORDING_DIR",&dir).output().unwrap();
        assert!(child.status.success(),"{}",String::from_utf8_lossy(&child.stderr));
        unsafe {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&dir)};
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingStart,Some("crashed-parts".into()))).unwrap();
        let mut row=snapshot.host.sessions.remove(0);row.id="crashed-parts".into();row.source="hostMicrophone".into();
        row.status="recording".into();row.audio_path=Some(anchor.to_string_lossy().into());row.audio_stored=false;row.chunks.clear();
        let index=base.join("session.json");super::super::persistence::save_sessions_to(&index,&[row.clone()]).unwrap();
        let authorization=super::super::session_store::privacy_authorization(&row).unwrap();
        super::super::host_interrupted_recovery::recover_session_at(&index,&row.id,&authorization).unwrap();
        let row=super::super::persistence::load_sessions_from(&index).unwrap().remove(0);
        assert!(row.capture_incomplete && row.audio_stored);assert_eq!(saved_parts(&row).unwrap().unwrap().len(),2);
        assert_eq!(super::super::transcription_chunk_paths(&row).unwrap().len(),2);
        snapshot.host.sessions=vec![row];snapshot.meeting.active=false;snapshot.device.recording=false;snapshot.host.persistence.status="ready".into();
        let (source,_)=super::super::audio_export::source(&snapshot,"crashed-parts").unwrap();let output=base.join("recovered.wav");
        super::super::audio_export::copy_source_atomic(&source,&output).unwrap();
        let bytes=std::fs::read(output).unwrap();assert_eq!(bytes[44..].chunks_exact(2).map(|s|i16::from_le_bytes([s[0],s[1]])).collect::<Vec<_>>(),vec![10,20,30,40,50]);
        let backup=super::super::library_backup::save(&snapshot,&dir,&backups).unwrap();
        unsafe {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&target)};
        let restored=super::super::library_backup::restore_files(Path::new(&backup.path),&target).unwrap();
        assert_eq!(saved_parts(&restored[0]).unwrap().unwrap().len(),2);
        unsafe {std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};std::fs::remove_dir_all(base).unwrap();
    }

    #[test]
    fn sealed_first_part_and_empty_last_part_recover_without_losing_first() {
        let base=root();let dir=base.join("recordings");let backups=base.join("backups");
        std::fs::create_dir(&dir).unwrap();std::fs::create_dir(&backups).unwrap();let dir=dir.canonicalize().unwrap();
        unsafe {std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&dir)};
        let anchor=dir.join("sealed.wav");let first=super::super::audio_artifacts::WriteLease::begin(
            &anchor,&anchor,super::super::audio_artifacts::Purpose::Recording).unwrap();
        let mut bytes=denzic_host_audio_v1_core::wav::wav_header(6).to_vec();bytes.extend([1,0,2,0,3,0]);std::fs::write(&anchor,&bytes).unwrap();
        if let Some(first)=first {first.finish().unwrap();}
        let next=dir.join("sealed.host-part-00000001.wav");let mut leases=HostPartLeases::new(&anchor);leases.prepare(&next).unwrap();
        std::fs::write(&next,denzic_host_audio_v1_core::wav::wav_header(0)).unwrap();drop(leases);
        let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),
            crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingStart,Some("sealed-first".into()))).unwrap();
        let mut row=snapshot.host.sessions.remove(0);row.id="sealed-first".into();row.source="hostMicrophone".into();
        row.status="recording".into();row.audio_path=Some(anchor.to_string_lossy().into());row.audio_stored=false;row.chunks.clear();
        let state=base.join("session.json");super::super::persistence::save_sessions_to(&state,&[row.clone()]).unwrap();
        let expected=super::super::session_store::privacy_authorization(&row).unwrap();
        super::super::host_interrupted_recovery::recover_session_at(&state,&row.id,&expected).unwrap();
        let row=super::super::persistence::load_sessions_from(&state).unwrap().remove(0);
        assert!(row.audio_stored && row.capture_incomplete);assert_eq!(std::fs::read(row.audio_path.as_ref().unwrap()).unwrap(),bytes);
        snapshot.host.sessions=vec![row];snapshot.host.persistence.status="ready".into();snapshot.meeting.active=false;snapshot.device.recording=false;
        assert!(super::super::library_backup::save(&snapshot,&dir,&backups).is_ok());
        unsafe {std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};std::fs::remove_dir_all(base).unwrap();
    }
}
