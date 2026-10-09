//! Durable, device-bound receive cursors. A filename alone is never a receipt.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs::{self, File, OpenOptions},
    io::{BufWriter, Read, Seek, SeekFrom, Write},
    path::{Path, PathBuf},
};

const MAX_RECORDING: u64 = 64 * 1024 * 1024;
const CHECKPOINT_BYTES: u64 = 64 * 1024;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(crate) struct Source {
    pub device: String,
    pub recording_id: u32,
    pub codec: u8,
    pub source_mode: u8,
    pub duration_ms: u32,
    pub total_length: u32,
    pub sha256_prefix: [u8; 8],
    pub content_crc32: u32,
}
impl Source {
    fn validate(&self) -> Result<(), String> {
        if self.device.is_empty()
            || self.device.len() > 256
            || self.device.contains('\0')
            || self.total_length == 0
            || u64::from(self.total_length) > MAX_RECORDING
        {
            return Err(fail());
        }
        Ok(())
    }
    fn key(&self) -> Result<String, String> {
        self.validate()?;
        Ok(format!(
            "{:x}",
            Sha256::digest(serde_json::to_vec(self).map_err(|_| fail())?)
        ))
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Receipt {
    schema: u32,
    source: Source,
    bytes: u64,
    sha256: String,
    releasing: bool,
}
fn fail() -> String {
    "录音续传记录不可用，原文件已保留；请检查文件占用或恢复记录后重试。".into()
}
fn no_link(path: &Path) -> Result<bool, String> {
    match fs::symlink_metadata(path) {
        Ok(m) if m.is_file() && !m.file_type().is_symlink() => Ok(true),
        Ok(_) => Err(fail()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(false),
        Err(_) => Err(fail()),
    }
}
pub(crate) fn path(root: &Path, source: &Source) -> Result<PathBuf, String> {
    Ok(root.join(format!(".device-recording-{}.part", source.key()?)))
}
pub(crate) struct Cursor {
    path: PathBuf,
    receipt_path: PathBuf,
    _lock: File,
    file: Option<BufWriter<File>>,
    receipt: Receipt,
    hasher: Sha256,
    bytes: u64,
}
impl Cursor {
    pub(crate) fn open(root: &Path, source: Source) -> Result<(Self, Vec<u8>), String> {
        // Canonical parents also allow long Windows paths without a registry change.
        let root = root.canonicalize().map_err(|_| fail())?;
        let key = source.key()?;
        let path = path(&root, &source)?;
        let receipt_path = root.join(format!(".device-recording-{key}.json"));
        let lock_path = root.join(format!(".device-recording-{key}.lock"));
        no_link(&lock_path)?;
        let lock = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .open(lock_path)
            .map_err(|_| fail())?;
        lock.try_lock().map_err(|_| fail())?;
        let mut body_exists = no_link(&path)?;
        let mut receipt = if no_link(&receipt_path)? {
            let f = File::open(&receipt_path).map_err(|_| fail())?;
            let mut bytes = Vec::new();
            f.take(4097).read_to_end(&mut bytes).map_err(|_| fail())?;
            if bytes.len() > 4096 {
                return Err(fail());
            }
            let r: Receipt = serde_json::from_slice(&bytes).map_err(|_| fail())?;
            if r.schema != 1
                || r.source != source
                || r.bytes > u64::from(source.total_length)
                || r.sha256.len() != 64
                || !r.sha256.bytes().all(|b| b.is_ascii_hexdigit())
            {
                return Err(fail());
            }
            r
        } else {
            if body_exists {
                return Err(fail());
            }
            let r = Receipt {
                schema: 1,
                source,
                bytes: 0,
                sha256: format!("{:x}", Sha256::digest([])),
                releasing: false,
            };
            // The ownership intent is durable before creating the audio body.
            save(&receipt_path, &r)?;
            r
        };
        if receipt.releasing {
            finish_release(&path, &receipt_path, &receipt)?;
            body_exists = false;
            receipt.bytes = 0;
            receipt.sha256 = format!("{:x}", Sha256::digest([]));
            receipt.releasing = false;
            save(&receipt_path, &receipt)?;
        }
        if !body_exists && receipt.bytes != 0 {
            return Err(fail());
        }
        let mut file = OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(!body_exists)
            .open(&path)
            .map_err(|_| fail())?;
        let len = file.metadata().map_err(|_| fail())?.len();
        if len < receipt.bytes || len > u64::from(receipt.source.total_length) {
            return Err(fail());
        }
        let mut data = Vec::with_capacity(receipt.source.total_length as usize);
        (&mut file)
            .take(receipt.bytes)
            .read_to_end(&mut data)
            .map_err(|_| fail())?;
        let mut hasher = Sha256::new();
        hasher.update(&data);
        if format!("{:x}", hasher.clone().finalize()) != receipt.sha256 {
            return Err(fail());
        }
        if receipt.bytes == u64::from(receipt.source.total_length)
            && (hasher.clone().finalize()[..8] != receipt.source.sha256_prefix
                || crc32fast::hash(&data) != receipt.source.content_crc32)
        {
            return Err(fail());
        }
        // Only the uncommitted tail of our own, validated file may be replayed.
        if len != receipt.bytes {
            file.set_len(receipt.bytes).map_err(|_| fail())?;
            file.sync_all().map_err(|_| fail())?;
        }
        file.seek(SeekFrom::Start(receipt.bytes))
            .map_err(|_| fail())?;
        let bytes = receipt.bytes;
        Ok((
            Self {
                path,
                receipt_path,
                _lock: lock,
                // Coalesce the 224-byte BLE payloads within the existing
                // checkpoint window; buffering never advances the receipt.
                file: Some(BufWriter::with_capacity(CHECKPOINT_BYTES as usize, file)),
                receipt,
                hasher,
                bytes,
            },
            data,
        ))
    }
    pub(crate) fn append(&mut self, bytes: &[u8]) -> Result<(), String> {
        if self.bytes + bytes.len() as u64 > u64::from(self.receipt.source.total_length) {
            return Err(fail());
        }
        self.file
            .as_mut()
            .ok_or_else(fail)?
            .write_all(bytes)
            .map_err(|_| fail())?;
        self.hasher.update(bytes);
        self.bytes += bytes.len() as u64;
        if self.bytes - self.receipt.bytes >= CHECKPOINT_BYTES {
            self.checkpoint()?;
        }
        Ok(())
    }
    pub(crate) fn checkpoint(&mut self) -> Result<(), String> {
        let file = self.file.as_mut().ok_or_else(fail)?;
        // A receipt may describe only audio that reached durable storage.
        // Flush the user-space batch before syncing and atomically saving it.
        file.flush().map_err(|_| fail())?;
        file.get_ref().sync_all().map_err(|_| fail())?;
        let mut next = self.receipt.clone();
        next.bytes = self.bytes;
        next.sha256 = format!("{:x}", self.hasher.clone().finalize());
        save(&self.receipt_path, &next)?;
        self.receipt = next;
        Ok(())
    }
    pub(crate) fn finish(&mut self, bytes: &[u8]) -> Result<(), String> {
        let digest: [u8; 32] = self.hasher.clone().finalize().into();
        self.finish_received(bytes.len(), digest, crc32fast::hash(bytes))
    }
    fn finish_received(&mut self, length: usize, digest: [u8; 32], crc32: u32) -> Result<(), String> {
        let written: [u8; 32] = self.hasher.clone().finalize().into();
        if self.bytes != u64::from(self.receipt.source.total_length)
            || length as u64 != self.bytes
            || written != digest
            || written[..8] != self.receipt.source.sha256_prefix
            || crc32 != self.receipt.source.content_crc32
        {
            return Err(fail());
        }
        self.checkpoint()
    }
}
impl Drop for Cursor {
    fn drop(&mut self) {
        if self.bytes != self.receipt.bytes && self.checkpoint().is_err() {
            eprintln!("recording transfer checkpoint pending; last durable cursor preserved");
        }
    }
}
fn save(path: &Path, receipt: &Receipt) -> Result<(), String> {
    super::export::write_atomic(path, &serde_json::to_vec(receipt).map_err(|_| fail())?).map(|_| ())
}
/// Called only after the WAV/library receipt, and (when enabled) exact device ACK.
pub(crate) fn release(root: &Path, source: Source) -> Result<(), String> {
    let key = source.key()?;
    let receipt_path = root
        .canonicalize()
        .map_err(|_| fail())?
        .join(format!(".device-recording-{key}.json"));
    if !no_link(&receipt_path)? {
        return Ok(());
    }
    // A retry may follow the deletion intent with an already absent body.
    if fs::metadata(&receipt_path).map_err(|_| fail())?.len() > 4096 {
        return Err(fail());
    }
    let mut receipt: Receipt =
        serde_json::from_slice(&fs::read(&receipt_path).map_err(|_| fail())?)
            .map_err(|_| fail())?;
    if receipt.releasing {
        let root = receipt_path.parent().ok_or_else(fail)?;
        let body = path(root, &source)?;
        let lock_path = root.join(format!(".device-recording-{key}.lock"));
        no_link(&lock_path)?;
        let lock = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .open(lock_path)
            .map_err(|_| fail())?;
        lock.try_lock().map_err(|_| fail())?;
        // Reread under the lease; another process may have just resumed it.
        if fs::metadata(&receipt_path).map_err(|_| fail())?.len() > 4096 {
            return Err(fail());
        }
        receipt = serde_json::from_slice(&fs::read(&receipt_path).map_err(|_| fail())?)
            .map_err(|_| fail())?;
        if receipt.schema != 1 || receipt.source != source || !receipt.releasing {
            return Err(fail());
        }
        finish_release(&body, &receipt_path, &receipt)?;
        return Ok(());
    }
    let (mut cursor, data) = Cursor::open(root, source)?;
    cursor.finish(&data)?;
    receipt = cursor.receipt.clone();
    receipt.releasing = true;
    save(&cursor.receipt_path, &receipt)?;
    // Close the body before unlinking on Windows while retaining the OS lease.
    drop(cursor.file.take());
    fs::remove_file(&cursor.path).map_err(|_| fail())?;
    fs::remove_file(&cursor.receipt_path).map_err(|_| fail())?;
    Ok(())
}

fn finish_release(body: &Path, receipt_path: &Path, receipt: &Receipt) -> Result<(), String> {
    receipt.source.validate()?;
    if receipt.schema != 1
        || !receipt.releasing
        || receipt.bytes != u64::from(receipt.source.total_length)
    {
        return Err(fail());
    }
    if no_link(body)? {
        if fs::metadata(body).map_err(|_| fail())?.len() != receipt.bytes {
            return Err(fail());
        }
        let data = fs::read(body).map_err(|_| fail())?;
        let digest = Sha256::digest(&data);
        if format!("{:x}", digest) != receipt.sha256
            || digest[..8] != receipt.source.sha256_prefix
            || crc32fast::hash(&data) != receipt.source.content_crc32
        {
            return Err(fail());
        }
        fs::remove_file(body).map_err(|_| fail())?;
    }
    fs::remove_file(receipt_path).map_err(|_| fail())?;
    Ok(())
}

pub(crate) mod groups;
mod worker;
pub(crate) use worker::ReceiveCursor;
mod probe;
pub(crate) use probe::verify;

#[cfg(test)]
mod tests;
