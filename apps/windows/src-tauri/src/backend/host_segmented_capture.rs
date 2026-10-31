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
}
