//! Durable V2 segment consumer. No BLE action is performed here. The caller
//! must negotiate V2 and validate the actual UID. Every pathname is derived from validated
//! immutable metadata, never loaded as an arbitrary path from a receipt.
use super::{plan_group, Descriptor, GroupPlan, SessionKey, MAX_SEGMENTS};
use crate::backend::{audio_artifacts, cop1, export, session_store};
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
    #[serde(default, skip_serializing_if="Option::is_none")]
    timeline: Option<cop1::Timeline>,
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
enum OpenMode { Strict, LocalRepair, PrepareSync }
impl Receiver {
    /// Recover pending physical receipts even if the device directory is now
    /// empty (power loss after removal, before its successful reply). Enumerate
    /// only this format's exact manifest names; never adopt arbitrary audio.
    pub(crate) fn pending_initials(root: &Path, peer: &super::transport::Peer,
        device: &str) -> Result<Vec<Vec<u8>>, String> {
        let mut pending = Vec::new();
        for entry in fs::read_dir(root).map_err(|_| fail())? {
            let entry = entry.map_err(|_| fail())?;
            let name = entry.file_name();
            let Some(name) = name.to_str() else { continue; };
            let Some(hash) = name.strip_prefix(".board-session-").and_then(|s| s.strip_suffix(".json")) else { continue; };
            if hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) { continue; }
            let mut body = Vec::new();
            read_locked(&entry.path())?.take(MAX_RECEIPT + 1).read_to_end(&mut body).map_err(|_| fail())?;
            if body.len() as u64 > MAX_RECEIPT { return Err(fail()); }
            let receipt: Receipt = serde_json::from_slice(&body).map_err(|_| fail())?;
            if receipt.schema != 1 || receipt.segments.is_empty() || receipt.segments.len() > MAX_SEGMENTS as usize {
                return Err(fail());
            }
            let d = Descriptor::decode(&receipt.segments[0].wire)?;
            let expected = format!("{:x}", Sha256::digest(serde_json::to_vec(&d.key).map_err(|_| fail())?));
            if hash != expected { return Err(fail()); }
            if d.key.device_uid != peer.uid || d.key.format_epoch != peer.epoch { continue; }
            if receipt.device.as_deref().is_some_and(|id|
                !crate::backend::device_connection::same_device_id(id, device)) { continue; }
            if receipt.audio.is_none() || receipt.segments.iter().any(|s| !s.acked) {
                pending.push(d.encode()?);
            }
        }
        pending.sort_by_key(|p| super::u64le(p, 20));
        Ok(pending)
    }
    /// Reuse only durable, revalidated sealed originals after the device has
    /// consumed their directory entries. Never promote a growing prefix or
    /// infer a terminal segment from host state. The caller still needs the
    /// actual immutable terminal descriptor and a stable protected status.
    pub(crate) fn verified_received_catalogue(root:&Path,key:&SessionKey,device:&str)
        ->Result<Vec<Descriptor>,String> {
        let stem=format!("board-session-{:x}",Sha256::digest(serde_json::to_vec(key).map_err(|_|fail())?));
        let path=root.join(format!(".{stem}.json"));
        if !regular(&path)? {return Ok(Vec::new());}
        let mut body=Vec::new();read_locked(&path)?.take(MAX_RECEIPT+1).read_to_end(&mut body).map_err(|_|fail())?;
        if body.len() as u64>MAX_RECEIPT {return Err(fail());}
        let receipt:Receipt=serde_json::from_slice(&body).map_err(|_|fail())?;
        let first=receipt.segments.first().ok_or_else(fail)?;
        if Descriptor::decode(&first.wire)?.key!=*key {return Err(fail());}
        let receiver=Self::open(root,&first.wire)?;
        if receiver.receipt.device.as_deref().is_none_or(|old|
            !crate::backend::device_connection::same_device_id(old,device)) {return Err(fail());}
        Ok(receiver.receipt.segments.iter().zip(receiver.descriptors()?)
            .filter_map(|(saved,d)|saved.received.then_some(d)).collect())
    }
    pub(crate) fn session_id(&self) -> &str { &self.stem }
    pub(crate) fn has_segment(&mut self, wire: &[u8]) -> Result<bool, String> {
        let d = Descriptor::decode(wire)?;
        self.accept_metadata(wire)?;
        self.recover()?;
        Ok(self.receipt.segments.iter().any(|s| s.received &&
            super::u32le(&s.wire, 28) == d.segment_index))
    }
    pub(crate) fn open(root: &Path, initial_wire: &[u8]) -> Result<Self, String> {
        Self::open_inner(root,initial_wire,OpenMode::Strict)
    }
    // Only the indexed local-recovery entry may rebuild a missing derivative.
    // Ordinary verification/ACK admission remains strict and never writes WAV.
    fn open_for_local_repair(root: &Path, initial_wire: &[u8]) -> Result<Self,String> {
        Self::open_inner(root,initial_wire,OpenMode::LocalRepair)
    }
    fn open_inner(root: &Path, initial_wire: &[u8], mode:OpenMode) -> Result<Self,String> {
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
        match mode {
            OpenMode::Strict=>this.recover()?,
            OpenMode::LocalRepair=>{
                this.recover_originals()?;
                this.rebuild_missing_audio()?;
                this.recover()?;
            },
            // Only SyncRepair owns this unchecked value. Its public surface
            // has no publish/consume operations; finish revalidates all files.
            OpenMode::PrepareSync=>(),
        }
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
        let index = self.receipt.segments.iter()
            .position(|s| super::u32le(&s.wire,28)==d.segment_index).ok_or_else(fail)?;
        let path = self.payload_path(&d);
        if regular(&path)? {
            verify_file(read_locked(&path)?, &d)?;
        } else {
            // Intent (descriptor) is already durable before the body exists.
            if self.receipt.segments[index].received {
                audio_artifacts::restore_missing_original_pinned(
                    self._usage.as_ref(),&self.audio_path(),&path,u64::from(d.encoded_length),
                    &format!("{:x}",Sha256::digest(payload)),
                    || export::write_atomic(&path,payload).map(|_|()),
                )?;
            } else {
                audio_artifacts::generated_pinned(
                    self._usage.as_ref(), &self.audio_path(), &path,
                    audio_artifacts::Purpose::CompressedOriginal,
                    || export::write_atomic(&path, payload).map(|_| ()),
                )?;
            }
            verify_file(read_locked(&path)?, &d)?;
        }
        if !self.receipt.segments[index].received {
            self.receipt.segments[index].received = true;
            if let Err(e) = self.save() {
                self.receipt.segments[index].received = false;
                return Err(e);
            }
        }
        Ok(())
    }
    fn recover_originals(&mut self) -> Result<(), String> {
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
                return Err(if self.receipt.segments[index].acked {
                    "这份录音的本机原音不完整；设备已确认清理，可能无法补回。现有文件和恢复记录已保留。"
                } else {
                    "这份录音的本机原音不完整；请连接原设备补收。尚未确认清理缺失部分，现有文件和恢复记录已保留。"
                }.into());
            }
        }
        if changed {
            self.save()?;
        }
        Ok(())
    }
    fn recover(&mut self) -> Result<(), String> {
        self.recover_originals()?;
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
        let descriptors=self.descriptors()?;
        self.verify_audio_shape(a,&descriptors)?;
        let expected=a.bytes;
        let file = read_locked(&self.audio_path())?;
        if file.metadata().map_err(|_| fail())?.len() != expected {
            return Err(fail());
        }
        let (bytes, hash) = digest(file)?;
        if a.bytes != bytes || a.sha256 != hash {
            return Err(fail());
        }
        // A saved pause index must be derivable from the same immutable raw
        // originals. Never trust edited receipt timing or infer gaps from WAV.
        // Legacy originals only need the header check here; their established
        // raw verification remains in recover(), without another full scan.
        let mut files=Vec::with_capacity(descriptors.len());let mut schemas=Vec::new();
        for d in &descriptors {
            let mut file=read_locked(&self.payload_path(d))?;let mut header=[0;12];
            file.read_exact(&mut header).map_err(|_|fail())?;schemas.push(header[4]);
            file.seek(SeekFrom::Start(0)).map_err(|_|fail())?;files.push(file);
        }
        let timeline=if schemas.iter().all(|schema|*schema==1) {None} else {
            for (file,d) in files.iter_mut().zip(&descriptors) {
                let owned=file.try_clone().map_err(|_|fail())?;let _=verify_file(owned,d)?;
                file.seek(SeekFrom::Start(0)).map_err(|_|fail())?;
            }
            collect_timeline(&descriptors,&mut files)?
        };
        if a.timeline!=timeline {return Err("暂停时间轴与已保存原音不一致，原件已保留。".into());}
        Ok(())
    }
    fn verify_audio_shape(&self,a:&Audio,descriptors:&[Descriptor])->Result<(),String> {
        let plan = plan_group(&descriptors, &BTreeSet::new())?;
        let mut files=Vec::with_capacity(descriptors.len());
        for d in descriptors {files.push(verify_file(read_locked(&self.payload_path(d))?,d)?);}
        let timeline=collect_timeline(descriptors,&mut files)?;
        let samples=timeline.as_ref().map_or_else(||plan.sample_count.checked_sub(320).ok_or_else(fail),
            |t|Ok(t.playback_samples()))?;
        let expected = samples.checked_mul(2)
            .and_then(|b| b.checked_add(44))
            .ok_or_else(fail)?;
        if !plan.metadata_complete
            || expected > MAX_PCM_BYTES + 44
            || a.samples != samples
            || a.bytes != expected
            || a.timeline != timeline
        {
            return Err(fail());
        }
        Ok(())
    }
    fn rebuild_missing_audio(&mut self)->Result<(),String> {
        let Some(expected)=self.receipt.audio.clone() else{return Ok(())};
        if regular(&self.audio_path())? {return Ok(())};
        let descriptors=self.descriptors()?;
        self.verify_audio_shape(&expected,&descriptors)?;
        let mut files=Vec::with_capacity(descriptors.len());
        for d in &descriptors {files.push(verify_file(read_locked(&self.payload_path(d))?,d)?);}
        self.assemble_inner(&descriptors,&mut files,expected.samples,false,Some(&expected))?;
        Ok(())
    }
    fn verify_received_timeline(&self) -> Result<(),String> {
        let descriptors=self.descriptors()?.into_iter().zip(&self.receipt.segments)
            .filter(|(_,segment)|segment.received).map(|(d,_)|d).collect::<Vec<_>>();
        let mut files=Vec::new();let mut schemas=Vec::new();
        for d in &descriptors {
            let mut file=read_locked(&self.payload_path(d))?;let mut header=[0;12];
            file.read_exact(&mut header).map_err(|_|fail())?;schemas.push(header[4]);
            file.seek(SeekFrom::Start(0)).map_err(|_|fail())?;files.push(file);
        }
        if !schemas.iter().all(|schema|*schema==1) {collect_timeline(&descriptors,&mut files)?;}
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
        let descriptors = self.descriptors()?;
        // Lock the exact handles before verification and keep them through
        // decode: another process cannot substitute a body after its hash check.
        let mut files = Vec::with_capacity(descriptors.len());
        for d in &descriptors {
            files.push(verify_file(read_locked(&self.payload_path(d))?, d)?);
        }
        let source_timeline=collect_timeline(&descriptors,&mut files)?;
        let samples=source_timeline.as_ref().map_or_else(||plan.sample_count.checked_sub(320).ok_or_else(fail),
            |t|Ok(t.playback_samples()))?;
        if samples == 0 || samples > MAX_PCM_BYTES / 2 {
            return Err("录音超过当前WAV时长上限，原始分段已保留。".into());
        }
        let path = self.audio_path();
        if regular(&path)? {
            // A previous crash may have replaced the WAV before the receipt was
            // committed. Recompute a candidate then compare; never trust a name.
            return self.assemble_inner(&descriptors, &mut files, samples, true,None);
        }
        self.assemble_inner(&descriptors, &mut files, samples, false,None)
    }
    fn assemble_inner(
        &mut self,
        ds: &[Descriptor],
        files: &mut [File],
        samples: u64,
        existing: bool,
        expected:Option<&Audio>,
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
                let timeline=decode(ds, files, &temporary, samples)?;
                let (bytes, sha256) = digest(read_locked(&temporary)?)?;
                if expected.is_some_and(|saved| saved.bytes!=bytes || saved.sha256!=sha256 ||
                    saved.samples!=samples || saved.timeline!=timeline) {
                    return Err("重建回听与原保存校验不一致；原始分段和恢复记录均已保留，未替换文件。".into());
                }
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
                } else if let Some(saved)=expected {
                    audio_artifacts::restore_missing_recording_pinned(
                        self._usage.as_ref(),&output,saved.bytes,&saved.sha256,
                        || export::replace_file(&temporary,&output),
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
                    timeline,
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
        let previous=self.receipt.audio.replace(audio);
        if let Err(e) = self.save() {
            self.receipt.audio = previous;
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
struct HashedRead<'a> {file: &'a mut File,sha: Sha256,crc: crc32fast::Hasher,bytes:u64}
impl Read for HashedRead<'_> {
    fn read(&mut self, output:&mut [u8]) -> std::io::Result<usize> {
        let n=self.file.read(output)?;self.sha.update(&output[..n]);self.crc.update(&output[..n]);self.bytes+=n as u64;Ok(n)
    }
}
fn verify_file(mut file: File, d: &Descriptor) -> Result<File, String> {
    d.validate()?;
    if file.metadata().map_err(|_| fail())?.len() != u64::from(d.encoded_length) {
        return Err(fail());
    }
    let mut hashed=HashedRead{file:&mut file,sha:Sha256::new(),crc:crc32fast::Hasher::new(),bytes:0};
    let mut reader=cop1::Reader::new(&mut hashed,d.sample_offset,false)?;
    if reader.frame_ms!=20 || reader.source_rate!=16000 {return Err(fail());}
    while let Some(record)=reader.next()? {
        if let cop1::Record::Audio(packet)=record {if packet.len()>400 {return Err(fail());}}
    }
    let schema=reader.schema;let summary=reader.finish(d.flags&4!=0)?;drop(reader);
    if summary.frames * 320 != d.sample_count || summary.encoded_bytes!=u64::from(d.encoded_length)
        || (summary.ended_paused && d.flags&2==0 && !(schema>=4&&summary.codec_end.is_some()))
        || hashed.bytes!=u64::from(d.encoded_length)
        || hashed.crc.finalize() != d.content_crc32
        || hashed.sha.finalize().as_slice() != d.sha256
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
) -> Result<Option<cop1::Timeline>, String> {
    use denzic_host_audio_v1_core::{opus_decoder::MonoDecoder, wav::WavWriter};
    let mut decoder = MonoDecoder::new(16000)?;
    let mut wav = WavWriter::create(output).map_err(|e|export::local_write_error("创建录音回听文件",&e))?;
    let mut window=None;
    let mut schema=None;let mut timeline=None;
    for (d, file) in ds.iter().zip(files) {
        file.seek(SeekFrom::Start(0)).map_err(|_| fail())?;
        let mut reader=cop1::Reader::new(file,d.sample_offset,false)?;
        select_schema(&mut schema,&mut timeline,reader.schema)?;
        if window.is_none(){window=Some(cop1::SampleWindow::new(reader.schema,320)?);}
        while let Some(record)=reader.next()? {
            let packet=match record {
                cop1::Record::Audio(packet)=>packet,
                cop1::Record::Event(event)=>{if !window.as_ref().ok_or_else(fail)?.event_allowed(){return Err(fail());}
                    timeline.as_mut().ok_or_else(fail)?.push(event)?;continue;},
                cop1::Record::Boundary(b)=>{window.as_mut().ok_or_else(fail)?.observe(b)?;continue;},
            };
            let pcm = decoder.decode(&packet)?;
            if pcm.len() != 320 {
                return Err(fail());
            }
            let range=window.as_mut().ok_or_else(fail)?.packet(pcm.len())?;
            let pcm = pcm[range]
                .iter().copied()
                .flat_map(|v| v.clamp(-29900, 29900).to_le_bytes())
                .collect::<Vec<_>>();
            wav.append_bytes(&pcm).map_err(|e|export::local_write_error("写入录音回听文件",&e))?;
        }
        let summary=reader.finish(d.flags&4!=0)?;
        if let Some(timeline)=timeline.as_mut() {timeline.add_segment(&summary)?;}
    }
    let boundary=window.as_ref().ok_or_else(fail)?.finish(allow_incomplete_source_end(ds))?;
    if schema.is_some_and(|s|s>=4){timeline.as_mut().ok_or_else(fail)?.apply_boundary(boundary);}
    if boundary.written_samples != expected {
        return Err(fail());
    }
    wav.finalize().map_err(|e|export::local_write_error("完成录音回听文件",&e))?;
    drop(wav);
    OpenOptions::new()
        .write(true)
        .open(output)
        .and_then(|f| f.sync_all())
        .map_err(|e|export::local_write_error("提交录音回听文件",&e))?;
    Ok(timeline)
}

fn select_schema(schema:&mut Option<u8>,timeline:&mut Option<cop1::Timeline>,current:u8)->Result<(),String> {
    if schema.is_some_and(|old|old!=current) {return Err("同一录音的原音格式发生变化，原件已保留。".into());}
    if schema.is_none() {if matches!(current,2..=5) {*timeline=Some(cop1::Timeline::default());}*schema=Some(current);}
    Ok(())
}
fn collect_timeline(ds:&[Descriptor],files:&mut [File])->Result<Option<cop1::Timeline>,String> {
    let mut schema=None;let mut timeline=None;let mut window=None;
    for (d,file) in ds.iter().zip(files) {
        file.seek(SeekFrom::Start(0)).map_err(|_|fail())?;
        let mut reader=cop1::Reader::new(file,d.sample_offset,false)?;
        select_schema(&mut schema,&mut timeline,reader.schema)?;
        if window.is_none(){window=Some(cop1::SampleWindow::new(reader.schema,320)?);}
        while let Some(record)=reader.next()? {
            match record {
                cop1::Record::Audio(_)=>{window.as_mut().ok_or_else(fail)?.packet(320)?;},
                cop1::Record::Boundary(b)=>window.as_mut().ok_or_else(fail)?.observe(b)?,
                cop1::Record::Event(event)=>{if !window.as_ref().ok_or_else(fail)?.event_allowed(){return Err(fail());}
                    timeline.as_mut().ok_or_else(fail)?.push(event)?;},
            }
        }
        let summary=reader.finish(d.flags&4!=0)?;
        if let Some(timeline)=timeline.as_mut() {timeline.add_segment(&summary)?;}
    }
    if let Some(window)=window {let b=window.finish(allow_incomplete_source_end(ds))?;
        if schema.is_some_and(|s|s>=4){timeline.as_mut().ok_or_else(fail)?.apply_boundary(b);}}
    Ok(timeline)
}
fn allow_incomplete_source_end(ds:&[Descriptor])->bool {
    ds.last().is_none_or(|last|last.flags&2==0||last.flags&4!=0)
}

#[cfg(test)]
mod pause_tests;
#[cfg(test)]
mod device_bookmark_tests;
#[cfg(test)]
mod source_boundary_tests;

mod probe;
mod publish;
mod local;
mod resync;
pub(crate) use resync::SyncRepair;
mod live;
pub(crate) use live::LiveCursor;
pub(crate) use local::{LocalRestoreReport, restore_local_product,restore_local_session};
pub(crate) use probe::{phase, verify};

#[cfg(test)]
mod audio_profile_tests;
