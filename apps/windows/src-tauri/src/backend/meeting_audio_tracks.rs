//! Independently playable pieces of one aligned meeting track.
//!
//! Both microphone and computer output use the same timeline but have their
//! own writer and directory. Splitting is a file-format detail, not a limit on
//! the meeting. The caller must persist its session-to-directory association
//! before starting capture and publish all parts before declaring completion.
use std::fs::{self, File, OpenOptions};
use std::io::{self, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

const HEADER: u64 = 44;
// A RIFF size includes 36 bytes in addition to the PCM data.
const MAX_PART_SAMPLES: u64 = (u32::MAX as u64 - 36) / 2;
const WRITE_BLOCK_SAMPLES: usize = 4096;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct TrackPart {
    pub(super) path: PathBuf,
    pub(super) first_sample: u64,
    pub(super) samples: u64,
}

struct OpenPart {
    file: File,
    path: PathBuf,
    first_sample: u64,
    samples: u64,
    artifact: Option<super::audio_artifacts::WriteLease>,
}

#[allow(dead_code)]
pub(super) struct TrackWriter {
    root: PathBuf,
    prefix: String,
    limit: u64,
    cursor: u64,
    current: Option<OpenPart>,
    complete: Vec<TrackPart>,
    failed: bool,
}

#[allow(dead_code)]
impl TrackWriter {
    /// `root` must not already exist; an unknown recording is never replaced.
    pub(super) fn create(root: &Path, limit: u64) -> io::Result<Self> {
        if limit == 0 || limit > MAX_PART_SAMPLES {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid WAV part size"));
        }
        fs::create_dir(root)?;
        Ok(Self { root: root.into(), prefix: "part".into(), limit, cursor: 0, current: None, complete: Vec::new(), failed: false })
    }

    /// Save directly under the existing managed recordings directory, using a
    /// unique session/source prefix. Existing privacy and ownership code only
    /// recognizes direct children of that directory.
    pub(super) fn create_flat(root: &Path, prefix: &str, limit: u64) -> io::Result<Self> {
        if limit == 0 || limit > MAX_PART_SAMPLES || prefix.is_empty() || prefix.len() > 128
            || !prefix.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_') {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid track name or part size"));
        }
        if !root.is_dir() { return Err(io::Error::new(io::ErrorKind::NotFound, "recording directory missing")); }
        Ok(Self { root: root.into(), prefix: prefix.into(), limit, cursor: 0, current: None, complete: Vec::new(), failed: false })
    }

    fn open_next(&mut self) -> io::Result<()> {
        let path = self.root.join(format!("{}-{:08}.wav", self.prefix, self.complete.len()));
        // Each file receives the same ownership and active-writer protection
        // as an ordinary host recording before any PCM can be written.
        let artifact = super::audio_artifacts::WriteLease::begin(&path, &path, super::audio_artifacts::Purpose::Recording)
            .map_err(io::Error::other)?;
        let mut file = OpenOptions::new().write(true).read(true).create_new(true).open(&path)?;
        file.write_all(&denzic_host_audio_v1_core::wav::wav_header(0))?;
        self.current = Some(OpenPart { file, path, first_sample: self.cursor, samples: 0, artifact });
        Ok(())
    }

    /// Stop after any write failure. A partially written sample/file stays on
    /// disk for recovery; retrying this writer could duplicate or corrupt it.
    pub(super) fn append(&mut self, mut samples: &[i16]) -> io::Result<()> {
        if self.failed { return Err(io::Error::other("track already failed; recover its saved files")); }
        let result = (|| {
            while !samples.is_empty() {
                if self.current.is_none() { self.open_next()?; }
                let part = self.current.as_mut().expect("opened above");
                let count = samples.len().min(WRITE_BLOCK_SAMPLES).min((self.limit - part.samples) as usize);
                let mut bytes = Vec::with_capacity(count * 2);
                for sample in &samples[..count] { bytes.extend_from_slice(&sample.to_le_bytes()); }
                part.file.write_all(&bytes)?;
                part.samples += count as u64;
                self.cursor = self.cursor.checked_add(count as u64).ok_or_else(|| io::Error::other("sample count overflow"))?;
                samples = &samples[count..];
                if part.samples == self.limit { self.finish_part()?; }
            }
            Ok(())
        })();
        if result.is_err() { self.failed = true; }
        result
    }

    fn finish_part(&mut self) -> io::Result<()> {
        let Some(mut part) = self.current.take() else { return Ok(()); };
        let bytes = u32::try_from(part.samples * 2).map_err(|_| io::Error::other("WAV part too large"))?;
        part.file.seek(SeekFrom::Start(0))?;
        part.file.write_all(&denzic_host_audio_v1_core::wav::wav_header(bytes))?;
        part.file.sync_all()?;
        if part.file.metadata()?.len() != HEADER + u64::from(bytes) {
            return Err(io::Error::other("WAV part length changed"));
        }
        if let Some(artifact) = part.artifact.take() { artifact.finish().map_err(io::Error::other)?; }
        self.complete.push(TrackPart { path: part.path, first_sample: part.first_sample, samples: part.samples });
        Ok(())
    }

    pub(super) fn finish(mut self) -> io::Result<Vec<TrackPart>> {
        if self.failed { return Err(io::Error::other("track write failed; recover its saved files")); }
        self.finish_part()?;
        Ok(std::mem::take(&mut self.complete))
    }
}

impl Drop for TrackWriter {
    fn drop(&mut self) {
        // Best effort only: an interrupted process or a previous partial write
        // still requires the caller's copy-based recovery path.
        if !self.failed { let _ = self.finish_part(); }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    static NEXT: AtomicU64 = AtomicU64::new(0);
    fn root() -> PathBuf {
        let path = std::env::temp_dir().join(format!("meeting-track-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir(&path).unwrap();
        path
    }
    fn pcm(part: &TrackPart) -> Vec<i16> {
        let bytes = fs::read(&part.path).unwrap();
        assert_eq!(&bytes[..4], b"RIFF");
        assert_eq!(u32::from_le_bytes(bytes[40..44].try_into().unwrap()) as u64, part.samples * 2);
        bytes[44..].chunks_exact(2).map(|x| i16::from_le_bytes([x[0], x[1]])).collect()
    }
    #[test]
    fn two_tracks_split_without_losing_order_or_alignment() {
        let root = root();
        let mut mic = TrackWriter::create(&root.join("mic"), 3).unwrap();
        let mut system = TrackWriter::create(&root.join("system"), 3).unwrap();
        mic.append(&[1, 2, 0, 0, 3, 4, 5]).unwrap();
        system.append(&[0, 0, 8, 9, 10, 0, 0]).unwrap();
        let a = mic.finish().unwrap(); let b = system.finish().unwrap();
        assert_eq!(a.iter().map(|p| p.first_sample).collect::<Vec<_>>(), [0, 3, 6]);
        assert_eq!(b.iter().map(|p| p.first_sample).collect::<Vec<_>>(), [0, 3, 6]);
        assert_eq!(a.iter().flat_map(pcm).collect::<Vec<_>>(), [1, 2, 0, 0, 3, 4, 5]);
        assert_eq!(b.iter().flat_map(pcm).collect::<Vec<_>>(), [0, 0, 8, 9, 10, 0, 0]);
        fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn existing_directory_and_invalid_part_size_are_never_replaced() {
        let root = root(); let existing = root.join("existing"); fs::create_dir(&existing).unwrap();
        fs::write(existing.join("old.wav"), b"keep").unwrap();
        assert!(TrackWriter::create(&existing, 3).is_err());
        assert!(TrackWriter::create(&root.join("bad"), MAX_PART_SAMPLES + 1).is_err());
        assert_eq!(fs::read(existing.join("old.wav")).unwrap(), b"keep");
        assert!(!root.join("bad").exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn timestamp_gaps_and_overlaps_are_saved_across_part_boundaries() {
        let root = root();
        let mut mic = TrackWriter::create(&root.join("mic"), 3).unwrap();
        let mut system = TrackWriter::create(&root.join("system"), 3).unwrap();
        let mut mt = super::super::meeting_audio_timeline::Timeline::new();
        let mut st = super::super::meeting_audio_timeline::Timeline::new();
        mt.append(0, &[1, 2, 3, 4], |s| mic.append(s)).unwrap();
        mt.append(3, &[4, 5], |s| mic.append(s)).unwrap();
        st.append(2, &[8, 9], |s| system.append(s)).unwrap();
        st.append(7, &[10], |s| system.append(s)).unwrap();
        mt.finish(10, |s| mic.append(s)).unwrap();
        st.finish(10, |s| system.append(s)).unwrap();
        assert_eq!(mic.finish().unwrap().iter().flat_map(pcm).collect::<Vec<_>>(), [1, 2, 3, 4, 5, 0, 0, 0, 0, 0]);
        assert_eq!(system.finish().unwrap().iter().flat_map(pcm).collect::<Vec<_>>(), [0, 0, 8, 9, 0, 0, 0, 10, 0, 0]);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn unexpected_existing_part_is_preserved_and_failure_is_terminal() {
        let root = root(); let dir = root.join("mic");
        let mut mic = TrackWriter::create(&dir, 3).unwrap();
        let path = dir.join("part-00000000.wav"); fs::write(&path, b"prior").unwrap();
        assert!(mic.append(&[1]).is_err());
        assert!(mic.append(&[1]).is_err());
        assert!(mic.finish().is_err());
        assert_eq!(fs::read(&path).unwrap(), b"prior");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn normal_drop_finalizes_part_when_startup_of_other_track_fails() {
        let root = root(); let dir = root.join("mic");
        let mut mic = TrackWriter::create(&dir, 10).unwrap();
        mic.append(&[11, 12]).unwrap(); drop(mic);
        let part = TrackPart { path: dir.join("part-00000000.wav"), first_sample: 0, samples: 2 };
        assert_eq!(pcm(&part), [11, 12]);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn managed_flat_tracks_keep_sources_separate_and_reject_unsafe_names() {
        let root = root();
        assert!(TrackWriter::create_flat(&root, "../escape", 3).is_err());
        let mut mic = TrackWriter::create_flat(&root, "unique-mic", 3).unwrap();
        let mut system = TrackWriter::create_flat(&root, "unique-system", 3).unwrap();
        mic.append(&[1, 2]).unwrap(); system.append(&[3, 4]).unwrap();
        let a = mic.finish().unwrap(); let b = system.finish().unwrap();
        assert_eq!(a[0].path.parent(), Some(root.as_path()));
        assert_eq!(b[0].path.parent(), Some(root.as_path()));
        assert_ne!(a[0].path, b[0].path); assert_eq!(pcm(&a[0]), [1, 2]); assert_eq!(pcm(&b[0]), [3, 4]);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    #[ignore = "changes the process recording directory; run in isolation"]
    fn managed_track_files_get_owned_and_can_be_cleaned() {
        let root = root();
        let old = std::env::var_os("COMPANION_TYPE_RECORDING_DIR");
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR", &root);
        let mut track = TrackWriter::create_flat(&root, "owned-mic", 2).unwrap();
        track.append(&[1,2,3]).unwrap();
        let parts = track.finish().unwrap();
        assert!(parts.iter().all(|p| super::super::audio_artifacts::is_managed(&p.path)));
        let sources = parts.iter().map(|p| p.path.to_string_lossy().into_owned()).collect::<Vec<_>>();
        let report = super::super::audio_artifacts::erase(&root, &sources, &[]).unwrap();
        assert_eq!(report.deleted, 2); assert!(parts.iter().all(|p| !p.path.exists()));
        if let Some(value) = old { std::env::set_var("COMPANION_TYPE_RECORDING_DIR", value); }
        else { std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); }
        fs::remove_dir_all(root).unwrap();
    }
}
