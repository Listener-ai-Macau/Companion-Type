//! Durable V2 segment consumer. No BLE action is performed here. The current
//! production radio is V1; this receiver can be connected only after negotiated
//! V2 and actual device UID validation. Every pathname is derived from validated
//! immutable metadata, never loaded as an arbitrary path from a receipt.
use super::{plan_group, Descriptor, GroupPlan, MAX_SEGMENTS};
use crate::backend::{audio_artifacts, export, session_store};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeSet,
    fs::{self, File, OpenOptions},
    io::{Read, Seek, SeekFrom},
    path::{Path, PathBuf},
};

const MAX_RECEIPT: u64 = 2 * 1024 * 1024;
const ACK_BYTES: usize = 84;
const MAX_PCM_BYTES: u64 = 1024 * 1024 * 1024;
fn fail() -> String {
    "分段录音的恢复记录或文件不可用，原件已保留；请解除占用或重新同步缺失的段。".into()
}
fn regular(path: &Path) -> Result<bool, String> {
    match fs::symlink_metadata(path) {
        Ok(m) if m.is_file() && !m.file_type().is_symlink() => Ok(true),
        Ok(_) => Err(fail()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err(fail()),
    }
}
fn read_locked(path: &Path) -> Result<File, String> {
    if !regular(path)? {
        return Err(fail());
    }
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        options.share_mode(1); // Deny concurrent write/delete, including other processes.
    }
    options.open(path).map_err(|_| fail())
}
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Segment {
    wire: Vec<u8>,
    received: bool,
    acked: bool,
}
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Audio {
    bytes: u64,
    sha256: String,
    samples: u64,
}
#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Receipt {
    schema: u32,
    segments: Vec<Segment>,
    audio: Option<Audio>,
    device: Option<String>,
}

pub(crate) struct Receiver {
    root: PathBuf,
    stem: String,
    receipt: Receipt,
    _lock: File,
    _usage: Option<audio_artifacts::WriterLease>,
    ready: bool,
}
impl Receiver {
    pub(crate) fn open(root: &Path, initial_wire: &[u8]) -> Result<Self, String> {
        let initial = Descriptor::decode(initial_wire)?;
        let root = root.canonicalize().map_err(|_| fail())?;
        let stem = format!(
            "board-session-{:x}",
            Sha256::digest(serde_json::to_vec(&initial.key).map_err(|_| fail())?)
        );
        let lock_path = root.join(format!(".{stem}.lock"));
        regular(&lock_path)?;
        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(lock_path)
            .map_err(|_| fail())?;
        lock.try_lock().map_err(|_| fail())?;
        let path = root.join(format!(".{stem}.json"));
        let receipt = if regular(&path)? {
            let mut bytes = vec![];
            read_locked(&path)?
                .take(MAX_RECEIPT + 1)
                .read_to_end(&mut bytes)
                .map_err(|_| fail())?;
            if bytes.len() as u64 > MAX_RECEIPT {
                return Err(fail());
            }
            let r: Receipt = serde_json::from_slice(&bytes).map_err(|_| fail())?;
            if r.schema != 1 || r.segments.is_empty() || r.segments.len() > MAX_SEGMENTS as usize {
                return Err(fail());
            }
            r
        } else {
            Receipt {
                schema: 1,
                segments: vec![Segment {
                    wire: initial.encode()?,
                    received: false,
                    acked: false,
                }],
                audio: None,
                device: None,
            }
        };
        let final_path = root.join(format!("{stem}.wav"));
        let usage = audio_artifacts::writer(&final_path)?;
        let mut this = Self {
            root,
            stem,
            receipt,
            _lock: lock,
            _usage: usage,
            ready: true,
        };
        let descriptors = this.descriptors()?;
        if descriptors.iter().any(|d| d.key != initial.key)
            || descriptors
                .windows(2)
                .any(|pair| pair[0].segment_index >= pair[1].segment_index)
            || this.receipt.segments.iter().any(|s| s.acked && !s.received)
            || this.receipt.audio.is_some() && !this.receipt.segments.iter().all(|s| s.received)
            || this
                .receipt
                .device
                .as_deref()
                .is_some_and(|id| !crate::backend::device_connection::stable_device_id(id))
        {
            return Err(fail());
        }
        plan_group(&descriptors, &BTreeSet::new())?;
        if !regular(&path)? {
            this.save()?;
        }
        this.accept_metadata(initial_wire)?;
        this.recover()?;
        Ok(this)
    }
    fn descriptors(&self) -> Result<Vec<Descriptor>, String> {
        if !self.ready {
            return Err("分段录音提交尚未确认，请关闭收录任务后重新恢复；原件已保留。".into());
        }
        self.receipt
            .segments
            .iter()
            .map(|s| Descriptor::decode(&s.wire))
            .collect()
    }
    fn receipt_path(&self) -> PathBuf {
        self.root.join(format!(".{}.json", self.stem))
    }
    pub(crate) fn audio_path(&self) -> PathBuf {
        self.root.join(format!("{}.wav", self.stem))
    }
    fn payload_path(&self, d: &Descriptor) -> PathBuf {
        let digest = format!("{:x}", Sha256::digest(&d.sha256));
        self.root.join(format!(
            "{}-{:04}-{}-{}.opus",
            self.stem,
            d.segment_index,
            d.recording_id,
            &digest[..16]
        ))
    }
    fn chunk_id(d: &Descriptor) -> String {
        format!(
            "segment-{}-{}-{}",
            d.segment_index,
            d.recording_id,
            d.sha256
                .iter()
                .map(|n| format!("{n:02x}"))
                .collect::<String>()
        )
    }
    fn save(&mut self) -> Result<(), String> {
        if !self.ready {
            return Err(fail());
        }
        let bytes = serde_json::to_vec(&self.receipt).map_err(|_| fail())?;
        if bytes.len() as u64 > MAX_RECEIPT {
            return Err(fail());
        }
        let result = audio_artifacts::generated_pinned(
            self._usage.as_ref(),
            &self.audio_path(),
            &self.receipt_path(),
            audio_artifacts::Purpose::SessionReceipt,
            || export::write_atomic(&self.receipt_path(), &bytes).map(|_| ()),
        );
        if result.is_err() {
            self.ready = false;
        }
        result
    }
    pub(crate) fn accept_metadata(&mut self, wire: &[u8]) -> Result<(), String> {
        let descriptor = Descriptor::decode(wire)?;
        let descriptors = self.descriptors()?;
        if descriptors[0].key != descriptor.key {
            return Err(fail());
        }
        if let Some(old) = descriptors
            .iter()
            .find(|d| d.segment_index == descriptor.segment_index)
        {
            // Sync state is mutable on the device. It cannot rewrite content or
            // retroactively grant an ACK in the host journal.
            if !old.same_content(&descriptor) {
                return Err(fail());
            }
            return Ok(());
        }
        if self.receipt.audio.is_some() || descriptors.len() >= MAX_SEGMENTS as usize {
            return Err(fail());
        }
        let mut all = descriptors;
        all.push(descriptor.clone());
        plan_group(&all, &BTreeSet::new())?;
        let before = self.receipt.clone();
        self.receipt.segments.push(Segment {
            wire: descriptor.encode()?,
            received: false,
            acked: false,
        });
        self.receipt
            .segments
            .sort_by_key(|s| super::u32le(&s.wire, 28));
        if let Err(e) = self.save() {
            self.receipt = before;
            return Err(e);
        }
        Ok(())
    }
    pub(crate) fn accept_segment(&mut self, wire: &[u8], payload: &[u8]) -> Result<(), String> {
        let d = Descriptor::decode(wire)?;
        d.verify_payload(payload)?;
        self.accept_metadata(wire)?;
        let path = self.payload_path(&d);
        if regular(&path)? {
            verify_file(read_locked(&path)?, &d)?;
        } else {
            // Intent (descriptor) is already durable before the body exists.
            audio_artifacts::generated_pinned(
                self._usage.as_ref(),
                &self.audio_path(),
                &path,
                audio_artifacts::Purpose::CompressedOriginal,
                || export::write_atomic(&path, payload).map(|_| ()),
            )?;
            verify_file(read_locked(&path)?, &d)?;
        }
        let index = self
            .receipt
            .segments
            .iter()
            .position(|s| super::u32le(&s.wire, 28) == d.segment_index)
            .ok_or_else(fail)?;
        if !self.receipt.segments[index].received {
            self.receipt.segments[index].received = true;
            if let Err(e) = self.save() {
                self.receipt.segments[index].received = false;
                return Err(e);
            }
        }
        Ok(())
    }
    fn recover(&mut self) -> Result<(), String> {
        let mut changed = false;
        for (index, d) in self.descriptors()?.iter().enumerate() {
            let path = self.payload_path(d);
            if regular(&path)? {
                verify_file(read_locked(&path)?, d)?;
                if !self.receipt.segments[index].received {
                    self.receipt.segments[index].received = true;
                    changed = true;
                }
            } else if self.receipt.segments[index].received || self.receipt.segments[index].acked {
                return Err(fail());
            }
        }
        if changed {
            self.save()?;
        }
        if let Some(audio) = &self.receipt.audio {
            self.verify_audio(audio)?;
        }
        Ok(())
    }
    pub(crate) fn plan(&mut self) -> Result<GroupPlan, String> {
        self.recover()?;
        let descriptors = self.descriptors()?;
        let ids = self
            .receipt
            .segments
            .iter()
            .filter(|s| s.received)
            .map(|s| super::u32le(&s.wire, 8))
            .collect();
        plan_group(&descriptors, &ids)
    }
    fn verify_audio(&self, a: &Audio) -> Result<(), String> {
        let plan = plan_group(&self.descriptors()?, &BTreeSet::new())?;
        let expected = plan
            .sample_count
            .checked_sub(320)
            .and_then(|s| s.checked_mul(2))
            .and_then(|b| b.checked_add(44))
            .ok_or_else(fail)?;
        if !plan.metadata_complete
            || expected > MAX_PCM_BYTES + 44
            || a.samples != plan.sample_count - 320
            || a.bytes != expected
        {
            return Err(fail());
        }
        let file = read_locked(&self.audio_path())?;
        if file.metadata().map_err(|_| fail())?.len() != expected {
            return Err(fail());
        }
        let (bytes, hash) = digest(file)?;
        if a.bytes != bytes || a.sha256 != hash {
            return Err(fail());
        }
        Ok(())
    }
    pub(crate) fn assemble(&mut self) -> Result<PathBuf, String> {
        let plan = self.plan()?;
        if !plan.payloads_complete {
            return Err("录音尚有缺段，已收齐的原音保留，等待继续同步。".into());
        }
        if let Some(a) = &self.receipt.audio {
            self.verify_audio(a)?;
            return Ok(self.audio_path());
        }
        let samples = plan.sample_count.checked_sub(320).ok_or_else(fail)?;
        if samples == 0 || samples > MAX_PCM_BYTES / 2 {
            return Err("录音超过当前WAV时长上限，原始分段已保留。".into());
        }
        let descriptors = self.descriptors()?;
        // Lock the exact handles before verification and keep them through
        // decode: another process cannot substitute a body after its hash check.
        let mut files = Vec::with_capacity(descriptors.len());
        for d in &descriptors {
            files.push(verify_file(read_locked(&self.payload_path(d))?, d)?);
        }
        let path = self.audio_path();
        if regular(&path)? {
            // A previous crash may have replaced the WAV before the receipt was
            // committed. Recompute a candidate then compare; never trust a name.
            return self.assemble_inner(&descriptors, &mut files, samples, true);
        }
        self.assemble_inner(&descriptors, &mut files, samples, false)
    }
    fn assemble_inner(
        &mut self,
        ds: &[Descriptor],
        files: &mut [File],
        samples: u64,
        existing: bool,
    ) -> Result<PathBuf, String> {
        let output = self.audio_path();
        let temporary = self.root.join(format!(
            ".companion-segments-{}.wav",
            uuid::Uuid::new_v4().simple()
        ));
        let result = audio_artifacts::generated_pinned(
            self._usage.as_ref(),
            &output,
            &temporary,
            audio_artifacts::Purpose::DecodeTemporary,
            || {
                decode(ds, files, &temporary, samples)?;
                let (bytes, sha256) = digest(read_locked(&temporary)?)?;
                if existing {
                    audio_artifacts::generated_pinned(
                        self._usage.as_ref(),
                        &output,
                        &output,
                        audio_artifacts::Purpose::Recording,
                        || {
                            let actual = digest(read_locked(&output)?)?;
                            if actual != (bytes, sha256.clone()) {
                                return Err(fail());
                            }
                            Ok(())
                        },
                    )?;
                } else {
                    audio_artifacts::generated_pinned(
                        self._usage.as_ref(),
                        &output,
                        &output,
                        audio_artifacts::Purpose::Recording,
                        || export::replace_file(&temporary, &output),
                    )?;
                }
                Ok(Audio {
                    bytes,
                    sha256,
                    samples,
                })
            },
        );
        if regular(&temporary).unwrap_or(false) {
            if audio_artifacts::is_managed(&temporary) {
                let _ = audio_artifacts::remove_temporary(&temporary);
            } else {
                let _ = fs::remove_file(&temporary);
            }
        }
        let audio = result?;
        self.receipt.audio = Some(audio);
        if let Err(e) = self.save() {
            self.receipt.audio = None;
            return Err(e);
        }
        Ok(output)
    }
}

fn digest(mut file: File) -> Result<(u64, String), String> {
    let mut sha = Sha256::new();
    let mut bytes = 0u64;
    let mut block = [0; 8192];
    loop {
        let n = file.read(&mut block).map_err(|_| fail())?;
        if n == 0 {
            break;
        }
        sha.update(&block[..n]);
        bytes += n as u64;
    }
    Ok((bytes, format!("{:x}", sha.finalize())))
}
fn verify_file(mut file: File, d: &Descriptor) -> Result<File, String> {
    d.validate()?;
    if file.metadata().map_err(|_| fail())?.len() != u64::from(d.encoded_length) {
        return Err(fail());
    }
    let mut header = [0; 12];
    file.read_exact(&mut header).map_err(|_| fail())?;
    if header != *b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00" {
        return Err(fail());
    }
    let mut sha = Sha256::new();
    let mut crc = crc32fast::Hasher::new();
    sha.update(header);
    crc.update(&header);
    let mut at = 12u32;
    let mut frames = 0u64;
    let mut packet = [0; 400];
    while at < d.encoded_length {
        let mut prefix = [0; 2];
        file.read_exact(&mut prefix).map_err(|_| fail())?;
        let n = u16::from_le_bytes(prefix) as usize;
        if n == 0 || n > 400 || n as u32 + 2 > d.encoded_length - at {
            return Err(fail());
        }
        file.read_exact(&mut packet[..n]).map_err(|_| fail())?;
        sha.update(prefix);
        sha.update(&packet[..n]);
        crc.update(&prefix);
        crc.update(&packet[..n]);
        at += n as u32 + 2;
        frames += 1;
    }
    if frames * 320 != d.sample_count
        || crc.finalize() != d.content_crc32
        || sha.finalize().as_slice() != d.sha256
    {
        return Err(fail());
    }
    file.seek(SeekFrom::Start(0)).map_err(|_| fail())?;
    Ok(file)
}
fn decode(
    ds: &[Descriptor],
    files: &mut [File],
    output: &Path,
    expected: u64,
) -> Result<(), String> {
    use denzic_host_audio_v1_core::{opus_decoder::MonoDecoder, wav::WavWriter};
    let mut decoder = MonoDecoder::new(16000)?;
    let mut wav = WavWriter::create(output).map_err(|_| fail())?;
    let mut frames = 0u64;
    let mut packet = [0; 400];
    for (d, file) in ds.iter().zip(files) {
        file.seek(SeekFrom::Start(12)).map_err(|_| fail())?;
        let mut at = 12u32;
        while at < d.encoded_length {
            let mut size = [0; 2];
            file.read_exact(&mut size).map_err(|_| fail())?;
            let n = u16::from_le_bytes(size) as usize;
            if n == 0 || n > 400 || n as u32 + 2 > d.encoded_length - at {
                return Err(fail());
            }
            file.read_exact(&mut packet[..n]).map_err(|_| fail())?;
            let pcm = decoder.decode(&packet[..n])?;
            if pcm.len() != 320 {
                return Err(fail());
            }
            at += n as u32 + 2;
            frames += 1;
            if frames == 1 {
                continue;
            } // One established pre-skip for the whole session.
            let pcm = pcm
                .into_iter()
                .flat_map(|v| v.clamp(-29900, 29900).to_le_bytes())
                .collect::<Vec<_>>();
            wav.append_bytes(&pcm).map_err(|_| fail())?;
        }
    }
    if (frames - 1) * 320 != expected {
        return Err(fail());
    }
    wav.finalize().map_err(|_| fail())?;
    drop(wav);
    OpenOptions::new()
        .write(true)
        .open(output)
        .and_then(|f| f.sync_all())
        .map_err(|_| fail())
}

mod probe;
mod publish;
pub(crate) use probe::{phase, verify};
