//! Build independently readable WAV parts from one continuous source decoder.
//! The caller owns the new staging directory and must publish all parts and
//! their receipt together before exposing them as a completed recording.
use super::*;
use std::io::{Seek, SeekFrom, Write};

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct Part {
    pub path: PathBuf,
    pub first_sample: u64,
    pub samples: u64,
    pub bytes: u64,
    pub sha256: String,
}

struct OpenPart {
    file: File,
    path: PathBuf,
    first_sample: u64,
    pcm_bytes: u32,
}

struct PartWriter {
    root: PathBuf,
    max_pcm_bytes: u32,
    total_samples: u64,
    current: Option<OpenPart>,
    completed: Vec<Part>,
}

impl PartWriter {
    fn new(root: &Path, max_pcm_bytes: u32) -> Result<Self, String> {
        // RIFF has a 32-bit size including the 36 bytes after its size field.
        // Each split is internal; it is not a limit on the full recording.
        if max_pcm_bytes < 2 || max_pcm_bytes % 2 != 0 || max_pcm_bytes > u32::MAX - 36 {
            return Err("音频分段大小无效。".into());
        }
        fs::create_dir(root).map_err(|e| export::local_write_error("创建录音分段目录", &e))?;
        Ok(Self { root: root.into(), max_pcm_bytes, total_samples: 0, current: None, completed: Vec::new() })
    }

    fn open_next(&mut self) -> Result<(), String> {
        let path = self.root.join(format!("part-{:08}.wav", self.completed.len()));
        let mut file = OpenOptions::new().write(true).read(true).create_new(true).open(&path)
            .map_err(|e| export::local_write_error("创建录音分段", &e))?;
        file.write_all(&denzic_host_audio_v1_core::wav::wav_header(0))
            .map_err(|e| export::local_write_error("写入录音分段", &e))?;
        self.current = Some(OpenPart { file, path, first_sample: self.total_samples, pcm_bytes: 0 });
        Ok(())
    }

    fn append(&mut self, mut pcm: &[u8]) -> Result<(), String> {
        if pcm.len() % 2 != 0 { return Err("录音分段不是完整采样。".into()); }
        while !pcm.is_empty() {
            if self.current.is_none() { self.open_next()?; }
            let current = self.current.as_mut().ok_or_else(fail)?;
            let available = (self.max_pcm_bytes - current.pcm_bytes) as usize;
            let count = available.min(pcm.len());
            current.file.write_all(&pcm[..count])
                .map_err(|e| export::local_write_error("写入录音分段", &e))?;
            current.pcm_bytes += count as u32;
            self.total_samples = self.total_samples.checked_add((count / 2) as u64).ok_or_else(fail)?;
            pcm = &pcm[count..];
            if current.pcm_bytes == self.max_pcm_bytes { self.finish_current()?; }
        }
        Ok(())
    }

    fn finish_current(&mut self) -> Result<(), String> {
        let Some(mut current) = self.current.take() else { return Ok(()); };
        current.file.seek(SeekFrom::Start(0))
            .and_then(|_| current.file.write_all(&denzic_host_audio_v1_core::wav::wav_header(current.pcm_bytes)))
            .and_then(|_| current.file.sync_all())
            .map_err(|e| export::local_write_error("保存录音分段", &e))?;
        drop(current.file);
        let (bytes, sha256) = digest(read_locked(&current.path)?)?;
        if bytes != u64::from(current.pcm_bytes) + 44 { return Err(fail()); }
        self.completed.push(Part { path: current.path, first_sample: current.first_sample,
            samples: u64::from(current.pcm_bytes / 2), bytes, sha256 });
        Ok(())
    }

    fn finish(mut self, expected: u64) -> Result<Vec<Part>, String> {
        self.finish_current()?;
        if self.total_samples != expected || self.completed.is_empty() { return Err(fail()); }
        Ok(self.completed)
    }
}

// This staging primitive is not yet connected to publication, playback or
// ASR: until those accept all parts, the existing single-WAV limit remains.
#[allow(dead_code)]
pub(super) fn decode_to_parts(ds: &[Descriptor], files: &mut [File], root: &Path,
    samples: u64, legacy_limited: bool, max_pcm_bytes: u32,
) -> Result<(Vec<Part>, Option<cop1::Timeline>), String> {
    let mut output = PartWriter::new(root, max_pcm_bytes)?;
    let timeline = decode_pcm(ds, files, samples, legacy_limited, |pcm| output.append(pcm))?;
    Ok((output.finish(samples)?, timeline))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn production_source_parts_are_independently_readable_and_exact() {
        let root=std::env::temp_dir().join(format!("companion-wav-parts-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();
        let source=super::super::source_boundary_tests::fixture();
        let mut receiver=Receiver::open(&root,&source[0].0.encode().unwrap()).unwrap();
        for (descriptor,payload) in &source { receiver.accept_segment(&descriptor.encode().unwrap(),payload).unwrap(); }
        let wav=fs::read(receiver.assemble().unwrap()).unwrap();
        let audio=receiver.receipt.audio.as_ref().unwrap().clone();
        let descriptors=receiver.descriptors().unwrap();
        let mut files=descriptors.iter().map(|d|
            verify_file(read_locked(&receiver.payload_path(d)).unwrap(),d).unwrap()
        ).collect::<Vec<_>>();
        let dir=root.join("new-parts");
        let (parts,timeline)=decode_to_parts(&descriptors,&mut files,&dir,audio.samples,false,1000).unwrap();
        assert!(parts.len()>2); assert_eq!(timeline,audio.timeline);
        let mut decoded=Vec::new(); let mut samples=0;
        for part in &parts {
            assert_eq!(part.first_sample,samples);
            crate::backend::meeting_workspace::validate_wav(&part.path).unwrap();
            let bytes=fs::read(&part.path).unwrap();
            assert_eq!(bytes.len() as u64,part.bytes);
            assert_eq!(format!("{:x}",Sha256::digest(&bytes)),part.sha256);
            assert_eq!(part.samples*2,bytes.len() as u64-44);
            decoded.extend_from_slice(&bytes[44..]); samples+=part.samples;
        }
        assert_eq!(samples,audio.samples); assert_eq!(decoded,wav[44..]);
        let first=fs::read(&parts[0].path).unwrap();
        assert!(decode_to_parts(&descriptors,&mut files,&dir,audio.samples,false,1000).is_err());
        assert_eq!(fs::read(&parts[0].path).unwrap(),first,"existing output must never be replaced");
        drop(files);drop(receiver);fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn exact_boundary_has_no_empty_trailing_part_and_invalid_size_creates_nothing() {
        let root=std::env::temp_dir().join(format!("companion-parts-boundary-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();
        let invalid=root.join("invalid");assert!(PartWriter::new(&invalid,3).is_err());assert!(!invalid.exists());
        let mut writer=PartWriter::new(&root.join("parts"),4).unwrap();
        writer.append(&[1,2,3,4]).unwrap();
        let parts=writer.finish(2).unwrap();
        assert_eq!(parts.len(),1);assert_eq!(parts[0].samples,2);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    #[ignore = "requires an explicitly selected locally saved board recording"]
    fn saved_device_recording_splits_without_changing_original() {
        let original=PathBuf::from(std::env::var_os("COMPANION_PARTS_REAL_ROOT").unwrap());
        let receipt_path=PathBuf::from(std::env::var_os("COMPANION_PARTS_REAL_RECEIPT").unwrap());
        let wav_path=PathBuf::from(std::env::var_os("COMPANION_PARTS_REAL_WAV").unwrap());
        let receipt_bytes=fs::read(&receipt_path).unwrap();
        let receipt:Receipt=serde_json::from_slice(&receipt_bytes).unwrap();
        let expected=receipt.audio.as_ref().unwrap().clone();
        let original_wav=fs::read(&wav_path).unwrap();
        assert_eq!(format!("{:x}",Sha256::digest(&original_wav)),expected.sha256);
        let root=std::env::temp_dir().join(format!("companion-real-parts-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&root).unwrap();
        let mut receiver=Receiver::open(&root,&receipt.segments[0].wire).unwrap();
        let mut originals=Vec::new();
        for segment in &receipt.segments {
            let descriptor=Descriptor::decode(&segment.wire).unwrap();
            let name=receiver.payload_path(&descriptor).file_name().unwrap().to_owned();
            let path=original.join(name);let bytes=fs::read(&path).unwrap();
            originals.push((path,format!("{:x}",Sha256::digest(&bytes))));
            receiver.accept_segment(&segment.wire,&bytes).unwrap();
        }
        assert_eq!(fs::read(receiver.assemble().unwrap()).unwrap(),original_wav);
        let descriptors=receiver.descriptors().unwrap();
        let mut files=descriptors.iter().map(|d|
            verify_file(read_locked(&receiver.payload_path(d)).unwrap(),d).unwrap()
        ).collect::<Vec<_>>();
        // Sixteen-second parts force multiple boundaries in the real sample.
        let (parts,timeline)=decode_to_parts(&descriptors,&mut files,&root.join("parts"),expected.samples,false,512000).unwrap();
        assert!(parts.len()>2);assert_eq!(timeline,expected.timeline);
        let mut joined=Vec::new();let mut samples=0;
        for part in &parts {
            assert_eq!(part.first_sample,samples);
            crate::backend::meeting_workspace::validate_wav(&part.path).unwrap();
            let bytes=fs::read(&part.path).unwrap();
            assert_eq!(format!("{:x}",Sha256::digest(&bytes)),part.sha256);
            joined.extend_from_slice(&bytes[44..]);samples+=part.samples;
        }
        assert_eq!(samples,expected.samples);assert_eq!(joined,original_wav[44..]);
        for (path,hash) in originals {assert_eq!(format!("{:x}",Sha256::digest(fs::read(path).unwrap())),hash);}
        assert_eq!(fs::read(&receipt_path).unwrap(),receipt_bytes);
        assert_eq!(format!("{:x}",Sha256::digest(fs::read(wav_path).unwrap())),expected.sha256);
        println!("board_audio_samples={samples} parts={}",parts.len());
        drop(files);drop(receiver);fs::remove_dir_all(root).unwrap();
    }
}
