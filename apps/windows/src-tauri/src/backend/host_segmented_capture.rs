//! Rolling WAV output for long local recordings. This writer is not yet wired
//! to capture: persistence, recovery, playback and export must move together.
use std::fs::{File, OpenOptions};
use std::io::{self, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

// RIFF's length includes the extra 36 bytes, and PCM samples are two bytes.
const MAX_PCM_BYTES: u32 = (u32::MAX - 36) & !1;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct HostAudioPart {
    pub path: PathBuf,
    pub samples: u64,
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
}
