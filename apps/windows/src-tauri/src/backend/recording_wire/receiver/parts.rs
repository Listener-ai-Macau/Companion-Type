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

/// Durable, path-independent description of one continuous decoded recording.
/// Filenames are derived from the owning directory and order, never read from
/// a receipt. Old single-WAV receipts remain unchanged.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(super) struct PartRecord {
    first_sample: u64,
    samples: u64,
    bytes: u64,
    sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(super) struct PartManifest {
    total_samples: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    file_prefix: Option<String>,
    parts: Vec<PartRecord>,
}

fn part_path(root: &Path, prefix: Option<&str>, index: usize) -> Result<PathBuf, String> {
    let name = if let Some(prefix) = prefix {
        let rest = prefix.strip_prefix("board-session-").ok_or_else(fail)?;
        let (session, generation) = rest.split_once(".parts-").ok_or_else(fail)?;
        if session.len() != 64 || generation.len() != 32
            || !session.bytes().chain(generation.bytes()).all(|b| b.is_ascii_hexdigit()) {
            return Err(fail());
        }
        format!("{prefix}-part-{index:08}.wav")
    } else {
        format!("part-{index:08}.wav")
    };
    Ok(root.join(name))
}

impl PartManifest {
    fn from_parts(root: &Path, prefix: Option<String>, parts: &[Part], total_samples: u64) -> Result<Self, String> {
        let records = parts.iter().enumerate().map(|(index, part)| {
            if part.path != part_path(root, prefix.as_deref(), index)? { return Err(fail()); }
            Ok(PartRecord { first_sample: part.first_sample, samples: part.samples,
                bytes: part.bytes, sha256: part.sha256.clone() })
        }).collect::<Result<Vec<_>, String>>()?;
        let manifest = Self { total_samples, file_prefix: prefix, parts: records };
        // PartWriter has already synced and hashed each newly written file.
        // Check the sample layout here; rehash only when reopening it later.
        manifest.paths(root)?;
        Ok(manifest)
    }

    fn paths(&self, root: &Path) -> Result<Vec<PathBuf>, String> {
        let metadata = fs::symlink_metadata(root).map_err(|_| fail())?;
        if !metadata.is_dir() || metadata.file_type().is_symlink() || self.parts.is_empty() {
            return Err(fail());
        }
        let mut next = 0u64;
        let mut paths = Vec::with_capacity(self.parts.len());
        for (index, part) in self.parts.iter().enumerate() {
            let pcm = part.samples.checked_mul(2).ok_or_else(fail)?;
            let pcm32 = u32::try_from(pcm).map_err(|_| fail())?;
            if part.samples == 0 || part.first_sample != next || pcm32 > u32::MAX - 36
                || part.bytes != pcm.checked_add(44).ok_or_else(fail)? {
                return Err(fail());
            }
            next = next.checked_add(part.samples).ok_or_else(fail)?;
            paths.push(part_path(root, self.file_prefix.as_deref(), index)?);
        }
        if next != self.total_samples { return Err(fail()); }
        Ok(paths)
    }

    /// Return all exact files in recording order after checking the saved
    /// sample axis, WAV headers and content. A missing middle file is never a
    /// shorter successful recording.
    pub(super) fn verify(&self, root: &Path) -> Result<Vec<PathBuf>, String> {
        let paths = self.paths(root)?;
        for (part, path) in self.parts.iter().zip(&paths) {
            let pcm32 = u32::try_from(part.samples.checked_mul(2).ok_or_else(fail)?).map_err(|_| fail())?;
            let mut file = read_locked(path)?;
            if file.metadata().map_err(|_| fail())?.len() != part.bytes { return Err(fail()); }
            let mut header = [0u8; 44];
            file.read_exact(&mut header).map_err(|_| fail())?;
            if header != denzic_host_audio_v1_core::wav::wav_header(pcm32) { return Err(fail()); }
            file.seek(SeekFrom::Start(0)).map_err(|_| fail())?;
            if digest(file)? != (part.bytes, part.sha256.clone()) { return Err(fail()); }
        }
        Ok(paths)
    }

    pub(super) fn owned_paths(&self, root: &Path, source: &Path) -> Result<Vec<PathBuf>, String> {
        let stem = source.file_stem().and_then(|name| name.to_str()).ok_or_else(fail)?;
        if source.parent() != Some(root) || self.file_prefix.as_deref()
            .is_none_or(|prefix| !prefix.starts_with(&format!("{stem}.parts-"))) {
            return Err(fail());
        }
        self.paths(root)
    }

    pub(super) fn verify_owned(&self, root: &Path, source: &Path) -> Result<Vec<PathBuf>, String> {
        self.owned_paths(root, source)?;
        self.verify(root)
    }

    pub(super) fn total_samples(&self) -> u64 { self.total_samples }

    pub(super) fn owned_details(&self, root: &Path, source: &Path) -> Result<Vec<(PathBuf, u64, u64, u64)>, String> {
        let paths = self.owned_paths(root, source)?;
        Ok(paths.into_iter().zip(&self.parts).map(|(path, part)|
            (path, part.first_sample, part.samples, part.bytes)).collect())
    }

    fn missing_owned(&self,root:&Path,source:&Path)->Result<(Vec<PathBuf>,Vec<bool>),String> {
        let paths=self.owned_paths(root,source)?;
        let mut missing=Vec::with_capacity(paths.len());
        for (part,path) in self.parts.iter().zip(&paths) {
            if !regular(path)? {missing.push(true);continue;}
            let mut file=read_locked(path)?;let mut header=[0u8;44];
            file.read_exact(&mut header).map_err(|_|fail())?;
            let pcm=u32::try_from(part.samples.checked_mul(2).ok_or_else(fail)?).map_err(|_|fail())?;
            file.seek(SeekFrom::Start(0)).map_err(|_|fail())?;
            if header!=denzic_host_audio_v1_core::wav::wav_header(pcm)
                || digest(file)?!=(part.bytes,part.sha256.clone()) {
                return Err("录音分段内容已损坏；现有文件和原始录音已保留。".into());
            }
            missing.push(false);
        }
        Ok((paths,missing))
    }
}

struct RestoreFile {
    file:Option<File>, lease:Option<audio_artifacts::WriteLease>, temporary:PathBuf,
}
impl Drop for RestoreFile {
    fn drop(&mut self) {
        drop(self.file.take());drop(self.lease.take());
        if regular(&self.temporary).unwrap_or(false) {
            if audio_artifacts::is_managed(&self.temporary) {let _=audio_artifacts::remove_temporary(&self.temporary);}
            else {let _=fs::remove_file(&self.temporary);}
        }
    }
}

/// Decode once across the entire meeting, writing only parts that are absent.
struct RestoreSink<'a> {
    root:&'a Path,source:&'a Path,pinned:Option<&'a audio_artifacts::WriterLease>,
    manifest:&'a PartManifest,paths:Vec<PathBuf>,missing:Vec<bool>,index:usize,written:u64,current:Option<RestoreFile>,
}
impl RestoreSink<'_> {
    fn append(&mut self,mut pcm:&[u8])->Result<(),String> {
        while !pcm.is_empty() {
            let part=self.manifest.parts.get(self.index).ok_or_else(fail)?;
            if self.written==0 && self.missing[self.index] {
                let temporary=self.root.join(format!(".companion-segments-{}.wav",uuid::Uuid::new_v4().simple()));
                let lease=audio_artifacts::WriteLease::begin_pinned(self.source,&temporary,audio_artifacts::Purpose::DecodeTemporary,self.pinned)?;
                let file=OpenOptions::new().write(true).create_new(true).open(&temporary).map_err(|_|fail())?;
                let pcm_bytes=u32::try_from(part.samples.checked_mul(2).ok_or_else(fail)?).map_err(|_|fail())?;
                self.current=Some(RestoreFile{file:Some(file),lease,temporary});
                self.current.as_mut().ok_or_else(fail)?.file.as_mut().ok_or_else(fail)?
                    .write_all(&denzic_host_audio_v1_core::wav::wav_header(pcm_bytes)).map_err(|_|fail())?;
            }
            let remaining=part.samples.checked_mul(2).and_then(|v|v.checked_sub(self.written)).ok_or_else(fail)?;
            let count=usize::try_from(remaining.min(pcm.len() as u64)).map_err(|_|fail())?;
            if let Some(current)=self.current.as_mut(){current.file.as_mut().ok_or_else(fail)?.write_all(&pcm[..count]).map_err(|_|fail())?;}
            self.written+=count as u64;pcm=&pcm[count..];
            if self.written==part.samples*2 {self.finish_part()?;}
        }
        Ok(())
    }
    fn finish_part(&mut self)->Result<(),String> {
        let part=self.manifest.parts.get(self.index).ok_or_else(fail)?;
        if let Some(mut current)=self.current.take() {
            let file=current.file.take().ok_or_else(fail)?;file.sync_all().map_err(|_|fail())?;drop(file);
            let identity=if let Some(lease)=current.lease.take(){lease.finish_with_identity()?}else{digest(read_locked(&current.temporary)?)?};
            if identity!=(part.bytes,part.sha256.clone()) {return Err("重建的录音与原保存记录不一致；原始录音已保留。".into());}
            audio_artifacts::restore_missing_part_pinned(self.pinned,self.source,&self.paths[self.index],part.bytes,&part.sha256,
                ||export::replace_file(&current.temporary,&self.paths[self.index]))?;
            if audio_artifacts::is_managed(&current.temporary) {let _=audio_artifacts::remove_temporary(&current.temporary);}
        }
        self.index+=1;self.written=0;Ok(())
    }
}

pub(super) fn restore_missing_owned(ds:&[Descriptor],files:&mut[File],root:&Path,source:&Path,
    pinned:Option<&audio_artifacts::WriterLease>,manifest:&PartManifest,expected_timeline:&Option<cop1::Timeline>)->Result<bool,String> {
    let (paths,missing)=manifest.missing_owned(root,source)?;
    if !missing.iter().any(|value|*value){return Ok(false);}
    let mut sink=RestoreSink{root,source,pinned,manifest,paths,missing,index:0,written:0,current:None};
    let timeline=decode_pcm(ds,files,manifest.total_samples,false,|pcm|sink.append(pcm))?;
    if sink.index!=manifest.parts.len() || sink.written!=0 || &timeline!=expected_timeline{return Err(fail());}
    Ok(true)
}

struct OpenPart {
    file: File,
    path: PathBuf,
    first_sample: u64,
    pcm_bytes: u32,
    lease: Option<audio_artifacts::WriteLease>,
}

struct OwnedParts<'a> {
    source: &'a Path,
    pinned: Option<&'a audio_artifacts::WriterLease>,
    prefix: String,
}

struct PartWriter<'a> {
    root: PathBuf,
    owned: Option<OwnedParts<'a>>,
    max_pcm_bytes: u32,
    total_samples: u64,
    current: Option<OpenPart>,
    completed: Vec<Part>,
}

impl<'a> PartWriter<'a> {
    fn new(root: &Path, max_pcm_bytes: u32) -> Result<Self, String> {
        // RIFF has a 32-bit size including the 36 bytes after its size field.
        // Each split is internal; it is not a limit on the full recording.
        if max_pcm_bytes < 2 || max_pcm_bytes % 2 != 0 || max_pcm_bytes > u32::MAX - 36 {
            return Err("音频分段大小无效。".into());
        }
        fs::create_dir(root).map_err(|e| export::local_write_error("创建录音分段目录", &e))?;
        Ok(Self { root: root.into(), owned: None, max_pcm_bytes, total_samples: 0, current: None, completed: Vec::new() })
    }

    fn new_owned(root: &Path, source: &'a Path, pinned: Option<&'a audio_artifacts::WriterLease>,
        max_pcm_bytes: u32) -> Result<Self, String> {
        if max_pcm_bytes < 2 || max_pcm_bytes % 2 != 0 || max_pcm_bytes > u32::MAX - 36
            || source.parent() != Some(root) {
            return Err(fail());
        }
        let stem = source.file_stem().and_then(|name| name.to_str()).ok_or_else(fail)?;
        let prefix = format!("{stem}.parts-{}", uuid::Uuid::new_v4().simple());
        // Check the derived name now; no receipt can direct writing elsewhere.
        part_path(root, Some(&prefix), 0)?;
        Ok(Self { root: root.into(), owned: Some(OwnedParts { source, pinned, prefix }),
            max_pcm_bytes, total_samples: 0, current: None, completed: Vec::new() })
    }

    fn open_next(&mut self) -> Result<(), String> {
        let path = part_path(&self.root, self.owned.as_ref().map(|owned| owned.prefix.as_str()), self.completed.len())?;
        let lease = if let Some(owned) = &self.owned {
            audio_artifacts::WriteLease::begin_pinned(owned.source, &path,
                audio_artifacts::Purpose::Recording, owned.pinned)?
        } else { None };
        let mut file = OpenOptions::new().write(true).read(true).create_new(true).open(&path)
            .map_err(|e| export::local_write_error("创建录音分段", &e))?;
        file.write_all(&denzic_host_audio_v1_core::wav::wav_header(0))
            .map_err(|e| export::local_write_error("写入录音分段", &e))?;
        self.current = Some(OpenPart { file, path, first_sample: self.total_samples, pcm_bytes: 0, lease });
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
        let (bytes, sha256) = if let Some(lease) = current.lease {
            lease.finish_with_identity()?
        } else {
            digest(read_locked(&current.path)?)?
        };
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

#[allow(dead_code)]
pub(super) fn decode_to_manifest(ds: &[Descriptor], files: &mut [File], root: &Path,
    samples: u64, legacy_limited: bool, max_pcm_bytes: u32,
) -> Result<(PartManifest, Option<cop1::Timeline>), String> {
    let (parts, timeline) = decode_to_parts(ds, files, root, samples, legacy_limited, max_pcm_bytes)?;
    Ok((PartManifest::from_parts(root, None, &parts, samples)?, timeline))
}

/// Create flat, owned parts tied to the same recording as the compressed
/// originals. A unique generation keeps an interrupted attempt separate.
#[allow(dead_code)]
pub(super) fn decode_to_owned_manifest(ds: &[Descriptor], files: &mut [File], root: &Path,
    source: &Path, pinned: Option<&audio_artifacts::WriterLease>, samples: u64,
    legacy_limited: bool, max_pcm_bytes: u32,
) -> Result<(PartManifest, Option<cop1::Timeline>), String> {
    let mut output = PartWriter::new_owned(root, source, pinned, max_pcm_bytes)?;
    let prefix = output.owned.as_ref().map(|owned| owned.prefix.clone());
    let timeline = decode_pcm(ds, files, samples, legacy_limited, |pcm| output.append(pcm))?;
    let parts = output.finish(samples)?;
    Ok((PartManifest::from_parts(root, prefix, &parts, samples)?, timeline))
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
        let (manifest,timeline)=decode_to_manifest(&descriptors,&mut files,&dir,audio.samples,false,1000).unwrap();
        assert!(manifest.parts.len()>2); assert_eq!(timeline,audio.timeline);
        let saved=serde_json::to_vec(&manifest).unwrap();
        let reopened:PartManifest=serde_json::from_slice(&saved).unwrap();
        let paths=reopened.verify(&dir).unwrap();
        let mut decoded=Vec::new(); let mut samples=0;
        for (part,path) in reopened.parts.iter().zip(&paths) {
            assert_eq!(part.first_sample,samples);
            crate::backend::meeting_workspace::validate_wav(path).unwrap();
            let bytes=fs::read(path).unwrap();
            assert_eq!(bytes.len() as u64,part.bytes);
            assert_eq!(format!("{:x}",Sha256::digest(&bytes)),part.sha256);
            assert_eq!(part.samples*2,bytes.len() as u64-44);
            decoded.extend_from_slice(&bytes[44..]); samples+=part.samples;
        }
        assert_eq!(samples,audio.samples); assert_eq!(decoded,wav[44..]);
        let first=fs::read(&paths[0]).unwrap();
        let middle=fs::read(&paths[1]).unwrap();
        fs::remove_file(&paths[1]).unwrap();
        assert!(reopened.verify(&dir).is_err(), "a missing middle file must not become a shorter recording");
        fs::write(&paths[1],&middle).unwrap();
        let mut corrupt=middle.clone(); *corrupt.last_mut().unwrap()^=1; fs::write(&paths[1],&corrupt).unwrap();
        assert!(reopened.verify(&dir).is_err(), "changed audio must not match the saved receipt");
        fs::write(&paths[1],&middle).unwrap();
        let mut wrong_axis=reopened.clone(); wrong_axis.parts[1].first_sample+=1;
        assert!(wrong_axis.verify(&dir).is_err(), "a gap in the saved sample axis must be rejected");
        assert_eq!(reopened.verify(&dir).unwrap(),paths);
        assert!(decode_to_parts(&descriptors,&mut files,&dir,audio.samples,false,1000).is_err());
        assert_eq!(fs::read(&paths[0]).unwrap(),first,"existing output must never be replaced");
        drop(files);drop(receiver);fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn missing_middle_parts_are_restored_from_owned_originals_in_one_pass() {
        let parent=std::env::temp_dir();let requested=parent.join(format!("companion-parts-recovery-{}",uuid::Uuid::new_v4()));
        assert_eq!(requested.parent(),Some(parent.as_path()));fs::create_dir(&requested).unwrap();let root=fs::canonicalize(&requested).unwrap();
        assert!(root.starts_with(fs::canonicalize(&parent).unwrap()));
        let previous=std::env::var_os("COMPANION_TYPE_RECORDING_DIR");std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&root);
        let index=root.join("sessions.json");let source=super::super::source_boundary_tests::fixture();let first=source[0].0.encode().unwrap();
        let mut receiver=Receiver::open(&root,&first).unwrap();
        for (descriptor,payload) in &source {receiver.accept_segment(&descriptor.encode().unwrap(),payload).unwrap();}
        let originals=source.iter().map(|(d,_)|receiver.payload_path(d)).collect::<Vec<_>>();
        receiver.publish(&index,"C8:ED:45:EB:95:B4").unwrap();
        let paths=receiver.assemble_parts_with_limit(1000).unwrap();assert!(paths.len()>3);
        let receipt=fs::read(receiver.receipt_path()).unwrap();drop(receiver);
        assert!(!crate::backend::persistence::load_sessions_from(&index).unwrap()[0].audio_stored);
        let after_interruption=super::super::local::restore_local(&root,&index).unwrap();
        assert_eq!(after_interruption.restored.len(),1);assert!(after_interruption.failures.is_empty());
        assert!(crate::backend::persistence::load_sessions_from(&index).unwrap()[0].audio_stored);
        let expected=paths.iter().map(|path|fs::read(path).unwrap()).collect::<Vec<_>>();
        let unrelated=root.join("unrelated.wav");fs::write(&unrelated,b"not a generated file").unwrap();
        fs::remove_file(&paths[1]).unwrap();fs::remove_file(&paths[2]).unwrap();
        let report=super::super::local::restore_local(&root,&index).unwrap();assert_eq!(report.restored.len(),1);
        assert!(report.failures.is_empty());for (path,bytes) in paths.iter().zip(&expected){assert_eq!(&fs::read(path).unwrap(),bytes);}
        assert_eq!(fs::read(&unrelated).unwrap(),b"not a generated file");
        assert_eq!(fs::read(root.join(format!(".{}.json",crate::backend::persistence::load_sessions_from(&index).unwrap()[0].id))).unwrap(),receipt);
        let again=super::super::local::restore_local(&root,&index).unwrap();assert!(again.restored.is_empty()&&again.failures.is_empty());
        fs::remove_file(&paths[1]).unwrap();fs::remove_file(&originals[0]).unwrap();
        let failed=super::super::local::restore_local(&root,&index).unwrap();assert_eq!(failed.failures.len(),1);
        assert!(!paths[1].exists());assert_eq!(fs::read(&paths[2]).unwrap(),expected[2]);
        assert_eq!(fs::read(&unrelated).unwrap(),b"not a generated file");
        match previous {Some(value)=>std::env::set_var("COMPANION_TYPE_RECORDING_DIR",value),None=>std::env::remove_var("COMPANION_TYPE_RECORDING_DIR")};
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn published_parts_reopen_and_transcribe_as_one_complete_recording() {
        let parent=std::env::temp_dir();
        let requested=parent.join(format!("companion-parts-published-{}",uuid::Uuid::new_v4()));
        assert_eq!(requested.parent(),Some(parent.as_path())); fs::create_dir(&requested).unwrap();
        let root=fs::canonicalize(&requested).unwrap();
        assert!(root.starts_with(fs::canonicalize(&parent).unwrap()));
        let index=root.join("sessions.json");
        let source=super::super::source_boundary_tests::fixture();
        let first=source[0].0.encode().unwrap();
        let mut receiver=Receiver::open(&root,&first).unwrap();
        for (descriptor,payload) in &source { receiver.accept_segment(&descriptor.encode().unwrap(),payload).unwrap(); }
        receiver.publish(&index,"C8:ED:45:EB:95:B4").unwrap();
        let pending=crate::backend::persistence::load_sessions_from(&index).unwrap();
        assert!(!pending[0].audio_stored);
        let paths=receiver.assemble_parts_with_limit(1000).unwrap();
        assert!(paths.len()>2);
        receiver.publish(&index,"C8:ED:45:EB:95:B4").unwrap();
        let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();
        assert_eq!(rows.len(),1); let row=&rows[0];
        assert!(row.audio_stored);
        assert_eq!(row.audio_path.as_deref(),paths[0].to_str());
        assert_eq!(receiver.ack_candidates(&index).unwrap().len(),source.len());
        drop(receiver);
        assert_eq!(Receiver::verified_audio_paths(row).unwrap(),paths);
        let playback_parts=Receiver::verified_audio_parts(row).unwrap();
        assert_eq!(playback_parts.iter().map(|(path,_)|path.clone()).collect::<Vec<_>>(),paths);
        assert_eq!(playback_parts.iter().map(|(_,samples)|samples).sum::<u64>(),row.duration_ms*16);
        assert_eq!(crate::backend::transcription_chunk_paths(row).unwrap(),
            paths.iter().map(|p|p.to_string_lossy().into_owned()).collect::<Vec<_>>());
        let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.host.sessions=vec![row.clone()];
        snapshot.meeting.active=false;snapshot.device.recording=false;
        let output=root.join("complete-export.wav");
        crate::backend::audio_export::export(&snapshot,&row.id,&output).unwrap();
        let exported=fs::read(&output).unwrap();
        let mut expected=Vec::new();for path in &paths {expected.extend_from_slice(&fs::read(path).unwrap()[44..]);}
        assert_eq!(&exported[44..],expected.as_slice());
        let request:crate::backend::library_export::Request=serde_json::from_value(serde_json::json!({
            "targets":[{"sessionId":row.id,"expectedRevision":row.organization.revision}],"format":"audio"})).unwrap();
        let report=crate::backend::library_export::save(&snapshot,&request,&root).unwrap();
        let folder=PathBuf::from(report.path);let manifest:serde_json::Value=serde_json::from_slice(&fs::read(folder.join("manifest.json")).unwrap()).unwrap();
        let exported_batch=fs::read(folder.join(manifest["entries"][0]["file"].as_str().unwrap())).unwrap();
        assert_eq!(exported_batch,exported,"batch export must include the same complete recording");
        let mut reopened=Receiver::open(&root,&first).unwrap();
        reopened.publish(&index,"C8:ED:45:EB:95:B4").unwrap();
        drop(reopened);
        let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();
        assert_eq!(Receiver::verified_audio_paths(&rows[0]).unwrap(),paths);
        let held=root.join("temporarily-missing.wav"); fs::rename(&paths[1],&held).unwrap();
        assert!(crate::backend::transcription_chunk_paths(&rows[0]).is_err());
        fs::rename(&held,&paths[1]).unwrap();
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn owned_parts_receipt_reopens_as_one_recording_and_detects_missing_middle() {
        let parent=std::env::temp_dir(); assert!(parent.is_absolute());
        let requested=parent.join(format!("companion-parts-receipt-{}",uuid::Uuid::new_v4()));
        assert_eq!(requested.parent(),Some(parent.as_path())); fs::create_dir(&requested).unwrap();
        let root=fs::canonicalize(&requested).unwrap();
        assert!(root.starts_with(fs::canonicalize(&parent).unwrap()));
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&root);
        let source=super::super::source_boundary_tests::fixture();
        let first=source[0].0.encode().unwrap();
        let mut receiver=Receiver::open(&root,&first).unwrap();
        for (descriptor,payload) in &source { receiver.accept_segment(&descriptor.encode().unwrap(),payload).unwrap(); }
        let raw=source.iter().map(|(descriptor,_)|receiver.payload_path(descriptor)).collect::<Vec<_>>();
        let paths=receiver.assemble_parts_with_limit(1000).unwrap();
        assert!(paths.len()>2 && paths.iter().all(|path|path.is_file()));
        assert!(receiver.receipt.audio.is_none() && receiver.receipt.parts_audio.is_some());
        assert!(receiver.assemble().is_err(), "a single-file caller must not silently receive only the first part");
        drop(receiver);
        let mut reopened=Receiver::open(&root,&first).unwrap();
        assert_eq!(reopened.assemble_parts_with_limit(1000).unwrap(),paths);
        drop(reopened);
        let held=root.join("temporarily-missing.wav"); fs::rename(&paths[1],&held).unwrap();
        assert!(Receiver::open(&root,&first).is_err(), "missing middle audio must not appear complete");
        assert!(raw.iter().all(|path|path.is_file()));
        fs::rename(&held,&paths[1]).unwrap();
        let reopened=Receiver::open(&root,&first).unwrap(); drop(reopened);
        let foreign=root.join("unrelated.wav"); fs::write(&foreign,b"other recording").unwrap();
        audio_artifacts::erase(&root,&[paths[0].to_string_lossy().into_owned()],&[]).unwrap();
        assert!(paths.iter().all(|path|!path.exists()));
        assert_eq!(fs::read(&foreign).unwrap(),b"other recording");
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn owned_parts_follow_recording_lifecycle_without_touching_other_files() {
        let parent=std::env::temp_dir(); assert!(parent.is_absolute());
        let root=parent.join(format!("companion-owned-parts-{}",uuid::Uuid::new_v4()));
        assert_eq!(root.parent(),Some(parent.as_path())); fs::create_dir(&root).unwrap();
        std::env::set_var("COMPANION_TYPE_RECORDING_DIR",&root);
        let source=super::super::source_boundary_tests::fixture();
        let mut receiver=Receiver::open(&root,&source[0].0.encode().unwrap()).unwrap();
        for (descriptor,payload) in &source { receiver.accept_segment(&descriptor.encode().unwrap(),payload).unwrap(); }
        let primary=receiver.assemble().unwrap();
        let expected=fs::read(&primary).unwrap();
        let descriptors=receiver.descriptors().unwrap();
        let mut files=descriptors.iter().map(|d|
            verify_file(read_locked(&receiver.payload_path(d)).unwrap(),d).unwrap()
        ).collect::<Vec<_>>();
        let audio=receiver.receipt.audio.as_ref().unwrap();
        let (manifest,timeline)=decode_to_owned_manifest(&descriptors,&mut files,&receiver.root,
            &primary,receiver._usage.as_ref(),audio.samples,false,1000).unwrap();
        assert_eq!(timeline,audio.timeline);
        let reopened:PartManifest=serde_json::from_slice(&serde_json::to_vec(&manifest).unwrap()).unwrap();
        let paths=reopened.verify_owned(&receiver.root,&primary).unwrap();
        assert!(paths.len()>2 && paths.iter().all(|path|path.parent()==Some(receiver.root.as_path())));
        let decoded=paths.iter().flat_map(|path|fs::read(path).unwrap()[44..].to_vec()).collect::<Vec<_>>();
        assert_eq!(decoded,expected[44..]);
        let foreign=receiver.root.join("unrelated.wav"); fs::write(&foreign,b"not part of this recording").unwrap();
        assert!(reopened.verify_owned(&receiver.root,&receiver.root.join("other.wav")).is_err());
        drop(files); drop(receiver);
        let report=audio_artifacts::erase(&root,&[primary.to_string_lossy().into_owned()],&[]).unwrap();
        assert!(report.deleted>=paths.len());
        assert!(paths.iter().all(|path|!path.exists()));
        assert_eq!(fs::read(&foreign).unwrap(),b"not part of this recording");
        std::env::remove_var("COMPANION_TYPE_RECORDING_DIR"); fs::remove_dir_all(root).unwrap();
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
