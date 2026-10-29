//! Explicit provenance for newly generated audio. Unknown files are never
//! discovered by scanning, and imports/exports are never adopted implicitly.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeSet,
    fs::{self, File, OpenOptions},
    io::Read,
    path::{Path, PathBuf},
};

const MANIFEST: &str = ".audio-artifacts.json";
const MAX_BYTES: u64 = 8 * 1024 * 1024;
const MAX_FILES: usize = 16_384;

#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub(crate) enum Purpose {
    Recording,
    CompressedOriginal,
    LivePrefix,
    LiveWindow,
    DecodeTemporary,
    AsrTemporary,
    TransferCursor,
    SessionReceipt,
}
impl Purpose {
    fn accepts(self, path: &Path) -> bool {
        let ext = path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or_default();
        match self {
            Self::CompressedOriginal => ext.eq_ignore_ascii_case("opus"),
            Self::LivePrefix => ext.eq_ignore_ascii_case("cop1"),
            Self::TransferCursor => ext.eq_ignore_ascii_case("part"),
            Self::SessionReceipt => ext.eq_ignore_ascii_case("json"),
            _ => ext.eq_ignore_ascii_case("wav"),
        }
    }
    fn temporary(self) -> bool {
        matches!(self, Self::DecodeTemporary | Self::AsrTemporary)
    }
}
#[derive(Clone, Copy, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
enum Phase {
    Prepared,
    Sealed,
    Interrupted,
    Deleting,
    Gone,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Identity {
    bytes: u64,
    sha256: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Artifact {
    // A single component relative to the recording root, never an arbitrary
    // deletion path supplied by IPC or a sidecar document.
    file: String,
    sources: BTreeSet<String>,
    purpose: Purpose,
    phase: Phase,
    identity: Option<Identity>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Manifest {
    schema: u32,
    files: Vec<Artifact>,
}
impl Default for Manifest {
    fn default() -> Self {
        Self {
            schema: 1,
            files: Vec::new(),
        }
    }
}

fn fail() -> String {
    "录音文件归属记录不可用，已有文件保留；请解除占用或恢复记录后重试。".into()
}
fn component(name: &str) -> bool {
    !name.is_empty()
        && !matches!(name, "." | "..")
        && !name.contains(['/', '\\', ':', '\0'])
        && !name.starts_with(".audio-artifact")
        && Path::new(name).file_name() == Some(std::ffi::OsStr::new(name))
}
pub(super) fn reference_key(path: &Path) -> Result<String, String> {
    let path = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir().map_err(|_| fail())?.join(path)
    };
    // Resolve existing source aliases so a retained meeting using a symlink
    // protects the same physical recording. For a missing file, resolve only
    // the existing parent so deletion can retry after an earlier removal.
    let resolved = match path.canonicalize() {
        Ok(path) => path,
        Err(_) => path
            .parent()
            .ok_or_else(fail)?
            .canonicalize()
            .map_err(|_| fail())?
            .join(path.file_name().ok_or_else(fail)?),
    };
    let text = resolved.to_str().ok_or_else(fail)?.replace('/', "\\");
    let text = text.strip_prefix(r"\\?\").unwrap_or(&text);
    Ok(if cfg!(windows) {
        text.to_lowercase()
    } else {
        text.into()
    })
}
// Unlike recording_root(), this does not create a real profile directory when
// a decoder or diagnostic is writing a file outside the managed root.
fn managed_root(path: &Path) -> Option<PathBuf> {
    let expected = std::env::var_os("COMPANION_TYPE_RECORDING_DIR")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("LOCALAPPDATA")
                .map(|p| PathBuf::from(p).join("Companion Type").join("recordings"))
        })?;
    let expected = expected.canonicalize().ok()?;
    let parent = path.parent()?.canonicalize().ok()?;
    if reference_key(&parent.join("root-marker")).ok()?
        == reference_key(&expected.join("root-marker")).ok()?
    {
        Some(expected)
    } else {
        None
    }
}
pub(crate) fn is_managed(path: &Path) -> bool {
    managed_root(path).is_some()
}
fn no_link(path: &Path) -> Result<(), String> {
    match fs::symlink_metadata(path) {
        Ok(m) if m.file_type().is_symlink() || !m.is_file() => Err(fail()),
        Ok(_) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(_) => Err(fail()),
    }
}
fn load(root: &Path) -> Result<Manifest, String> {
    let path = root.join(MANIFEST);
    no_link(&path)?;
    let mut file = match File::open(&path) {
        Ok(f) => f,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Manifest::default()),
        Err(_) => return Err(fail()),
    };
    let mut bytes = Vec::new();
    file.by_ref()
        .take(MAX_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| fail())?;
    if bytes.len() as u64 > MAX_BYTES {
        return Err(fail());
    }
    let data: Manifest = serde_json::from_slice(&bytes).map_err(|_| fail())?;
    if data.schema != 1 || data.files.len() > MAX_FILES {
        return Err(fail());
    }
    let mut names = BTreeSet::new();
    for item in &data.files {
        if !component(&item.file)
            || !item.purpose.accepts(Path::new(&item.file))
            || !names.insert(item.file.to_lowercase())
            || item.sources.is_empty()
            || item.sources.len() > 1024
            || item.sources.iter().any(|s| s.is_empty())
            || item.identity.as_ref().is_some_and(|i| {
                i.sha256.len() != 64 || !i.sha256.bytes().all(|b| b.is_ascii_hexdigit())
            })
            || matches!(item.phase, Phase::Sealed | Phase::Interrupted) && item.identity.is_none()
        {
            return Err(fail());
        }
    }
    Ok(data)
}
fn save(root: &Path, data: &Manifest) -> Result<(), String> {
    let mut bounded = data.clone();
    // Keep recent diagnostics, all live/delete-pending records, and every
    // retired bridge required to reach a live descendant. Completed scratch
    // work must not exhaust the manifest after weeks of normal ASR use.
    let mut keep = bounded
        .files
        .iter()
        .enumerate()
        .filter(|(_, i)| i.phase != Phase::Gone)
        .map(|(n, _)| n)
        .collect::<BTreeSet<_>>();
    // An explicit recording deletion can finish before its session index is
    // checkpointed. Its path authority must outlive scratch-history pruning,
    // or the legacy fallback could later mistake a replacement for old audio.
    for (n, item) in bounded.files.iter().enumerate() {
        if item.phase == Phase::Gone && !item.purpose.temporary()
            && item.sources.contains(&reference_key(&root.join(&item.file))?) {
            keep.insert(n);
        }
    }
    keep.extend(
        bounded
            .files
            .iter()
            .enumerate()
            .rev()
            .filter(|(_, i)| i.phase == Phase::Gone)
            .take(256)
            .map(|(n, _)| n),
    );
    let names = bounded
        .files
        .iter()
        .map(|i| reference_key(&root.join(&i.file)))
        .collect::<Result<Vec<_>, _>>()?;
    loop {
        let before = keep.len();
        let sources = keep
            .iter()
            .flat_map(|&n| bounded.files[n].sources.iter().cloned())
            .collect::<BTreeSet<_>>();
        for (n, key) in names.iter().enumerate() {
            if sources.contains(key) {
                keep.insert(n);
            }
        }
        if keep.len() == before {
            break;
        }
    }
    bounded.files = bounded
        .files
        .into_iter()
        .enumerate()
        .filter(|(n, _)| keep.contains(n))
        .map(|(_, i)| i)
        .collect();
    let bytes = serde_json::to_vec(&bounded).map_err(|_| fail())?;
    if bytes.len() as u64 > MAX_BYTES || bounded.files.len() > MAX_FILES {
        return Err(fail());
    }
    super::export::write_atomic(&root.join(MANIFEST), &bytes)
        .map(|_| ())
}
fn lock(root: &Path) -> Result<File, String> {
    let path = root.join(".audio-artifacts.lock");
    no_link(&path)?;
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(|_| fail())?;
    file.try_lock().map_err(|_| fail())?;
    Ok(file)
}
fn lease(root: &Path, leaf: &str) -> Result<File, String> {
    reference_lease(root, &reference_key(&root.join(leaf))?, false)
}
fn reference_lease(root: &Path, reference: &str, shared: bool) -> Result<File, String> {
    let directory = root.join(".audio-artifact-locks");
    match fs::symlink_metadata(&directory) {
        Ok(m) if m.file_type().is_symlink() || !m.is_dir() => return Err(fail()),
        Ok(_) => {}
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => match fs::create_dir(&directory) {
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {}
            Err(_) => return Err(fail()),
        },
        Err(_) => return Err(fail()),
    }
    // Recheck after a concurrent create, including reparse/symlink redirection.
    if directory.canonicalize().map_err(|_| fail())? != root.join(".audio-artifact-locks") {
        return Err(fail());
    }
    let key = format!("{:x}", Sha256::digest(reference.as_bytes()));
    let path = directory.join(key);
    no_link(&path)?;
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(|_| fail())?;
    if shared {
        file.try_lock_shared()
    } else {
        file.try_lock()
    }
    .map_err(|_| "录音文件仍被另一项录音、转写或清理使用，请稍后重试。".to_string())?;
    Ok(file)
}
fn fingerprint(path: &Path) -> Result<Option<Identity>, String> {
    no_link(path)?;
    let mut file = match File::open(path) {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err(fail()),
    };
    let before = file.metadata().map_err(|_| fail())?;
    let mut hasher = Sha256::new();
    let mut total = 0u64;
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let n = file.read(&mut buffer).map_err(|_| fail())?;
        if n == 0 {
            break;
        }
        total += n as u64;
        hasher.update(&buffer[..n]);
    }
    let after = file.metadata().map_err(|_| fail())?;
    if !before.is_file()
        || before.len() != total
        || after.len() != total
        || before.modified().ok() != after.modified().ok()
    {
        return Err(fail());
    }
    Ok(Some(Identity {
        bytes: total,
        sha256: format!("{:x}", hasher.finalize()),
    }))
}

pub(crate) struct WriteLease {
    root: PathBuf,
    leaf: String,
    _lease: Option<File>,
    finished: bool,
    purpose: Purpose,
}
impl WriteLease {
    pub(crate) fn begin(
        source: &Path,
        path: &Path,
        purpose: Purpose,
    ) -> Result<Option<Self>, String> {
        Self::begin_with(source,path,purpose,None)
    }
    fn begin_with(source:&Path,path:&Path,purpose:Purpose,pinned:Option<&WriterLease>) -> Result<Option<Self>,String> {
        let Some(root) = managed_root(path) else {
            return Ok(None);
        };
        if !purpose.accepts(path) {
            return Err(fail());
        }
        let leaf = path
            .file_name()
            .and_then(|n| n.to_str())
            .filter(|n| component(n))
            .ok_or_else(fail)?
            .to_string();
        let already_exclusive=if let Some(pinned)=pinned {
            if pinned.root!=root || pinned.source!=reference_key(source)? {return Err(fail());}
            pinned.source==reference_key(path)?
        } else {false};
        let file_lease=if already_exclusive {None} else {Some(lease(&root,&leaf)?)};
        let _lock = lock(&root)?;
        let mut data = load(&root)?;
        let source = reference_key(source)?;
        if let Some(item) = data.files.iter_mut().find(|i| i.file == leaf) {
            if item.purpose != purpose
                || matches!(item.phase, Phase::Deleting | Phase::Gone)
                || !item.sources.contains(&source)
                || fingerprint(path)? != item.identity
            {
                return Err(fail());
            }
            item.phase = Phase::Prepared;
        } else {
            match fs::symlink_metadata(path) {
                Ok(_) => return Err("目标录音文件已存在但没有生成归属记录，原文件已保留。".into()),
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                Err(_) => return Err(fail()),
            }
            data.files.push(Artifact {
                file: leaf.clone(),
                sources: BTreeSet::from([source]),
                purpose,
                phase: Phase::Prepared,
                identity: None,
            });
        }
        save(&root, &data)?;
        Ok(Some(Self {
            root,
            leaf,
            _lease: file_lease,
            finished: false,
            purpose,
        }))
    }
    fn checkpoint(&mut self, phase: Phase) -> Result<(), String> {
        if phase == Phase::Sealed && self.root.join(&self.leaf).exists() {
            OpenOptions::new()
                .write(true)
                .open(self.root.join(&self.leaf))
                .and_then(|f| f.sync_all())
                .map_err(|e|super::export::local_write_error("提交录音文件",&e))?;
        }
        let identity = fingerprint(&self.root.join(&self.leaf))?;
        if phase == Phase::Sealed && !self.purpose.temporary() && identity.is_none() {
            return Err(fail());
        }
        let _lock = lock(&self.root)?;
        let mut data = load(&self.root)?;
        let item = data
            .files
            .iter_mut()
            .find(|i| i.file == self.leaf)
            .ok_or_else(fail)?;
        item.phase = if identity.is_none() {
            Phase::Gone
        } else {
            phase
        };
        item.identity = identity;
        save(&self.root, &data)?;
        self.finished = true;
        Ok(())
    }
    pub(crate) fn finish(mut self) -> Result<(), String> {
        self.checkpoint(Phase::Sealed)
    }
}
impl Drop for WriteLease {
    fn drop(&mut self) {
        if !self.finished && self.checkpoint(Phase::Interrupted).is_err() {
            eprintln!("audio artifact checkpoint pending; original and ownership intent preserved");
        }
    }
}
pub(crate) fn generated<T>(
    source: &Path,
    path: &Path,
    purpose: Purpose,
    write: impl FnOnce() -> Result<T, String>,
) -> Result<T, String> {
    let guard = WriteLease::begin(source, path, purpose)?;
    let result = write();
    if result.is_ok() {
        if let Some(guard) = guard {
            guard.finish()?;
        }
    }
    result
}
/// A multi-file writer holds the logical source exclusively through all of its
/// writes. Its primary file uses that same capability rather than attempting
/// a conflicting second lock; secondary files still take their own leases.
pub(crate) struct WriterLease {root:PathBuf,source:String,_file:File}
pub(crate) fn writer(source:&Path)->Result<Option<WriterLease>,String> {
    let Some(root)=managed_root(source) else {return Ok(None);};
    let source=reference_key(source)?;
    let file=reference_lease(&root,&source,false)?;
    Ok(Some(WriterLease{root,source,_file:file}))
}
pub(crate) fn generated_pinned<T>(pinned:Option<&WriterLease>,source:&Path,path:&Path,purpose:Purpose,
    write:impl FnOnce()->Result<T,String>)->Result<T,String> {
    let guard=WriteLease::begin_with(source,path,purpose,pinned)?;
    let result=write();
    if result.is_ok() {if let Some(guard)=guard {guard.finish()?;}}
    result
}
/// Recreate one absent WAV from independently verified compressed originals.
/// The former sealed identity remains the authority throughout the atomic
/// replacement. Unlike a new generated file, this must not reset a tombstone
/// or adopt an unknown pathname. The callback only commits its prepared file;
/// it must not re-enter the artifact manifest while this lock is held.
pub(crate) fn restore_missing_recording_pinned<T>(pinned:Option<&WriterLease>,path:&Path,
    bytes:u64,sha256:&str,commit:impl FnOnce()->Result<T,String>)->Result<T,String> {
    restore_missing_pinned(pinned,path,path,Purpose::Recording,bytes,sha256,commit)
}
/// Do not create even a decode temporary if the exact saved recording has
/// been retired, lost its owner, or changed since the explicit inspection.
pub(crate) fn preflight_damaged_recording_pinned(pinned:Option<&WriterLease>,path:&Path,
    bytes:u64,sha256:&str,damaged_bytes:u64,damaged_sha256:&str)->Result<(),String> {
    let expected=Identity{bytes,sha256:sha256.to_owned()};
    let damaged=Identity{bytes:damaged_bytes,sha256:damaged_sha256.to_owned()};
    if damaged==expected || fingerprint(path)?!=Some(damaged) {return Err(fail())}
    let Some(root)=managed_root(path) else{return Ok(())};
    let pinned=pinned.ok_or_else(fail)?;let source=reference_key(path)?;
    if pinned.root!=root || pinned.source!=source {return Err(fail())}
    let leaf=path.file_name().and_then(|n|n.to_str()).filter(|n|component(n)).ok_or_else(fail)?;
    let _lock=lock(&root)?;let manifest=load(&root)?;
    let target=manifest.files.iter().find(|i|i.file==leaf).ok_or_else(fail)?;
    if target.purpose!=Purpose::Recording || target.phase!=Phase::Sealed ||
       !target.sources.contains(&source) || target.identity.as_ref()!=Some(&expected) {
        return Err("录音归属已失效，现有文件和原始分段均已保留。".into());
    }
    Ok(())
}
/// Restore a verified derivative while retaining the replaced preimage.
/// A durable, linked backup intent exists before Windows replacement begins;
/// interrupted or externally changed backup contents remain fail-closed.
pub(crate) fn restore_damaged_recording_pinned<T>(pinned:Option<&WriterLease>,path:&Path,
    bytes:u64,sha256:&str,damaged_bytes:u64,damaged_sha256:&str,backup:&Path,
    commit:impl FnOnce()->Result<T,String>)->Result<T,String> {
    let expected=Identity{bytes,sha256:sha256.to_owned()};
    let damaged=Identity{bytes:damaged_bytes,sha256:damaged_sha256.to_owned()};
    if damaged==expected || fingerprint(path)?!=Some(damaged.clone()) || fingerprint(backup)?.is_some() {return Err(fail())}
    let Some(root)=managed_root(path) else{return commit()};
    let pinned=pinned.ok_or_else(fail)?;let source=reference_key(path)?;
    if pinned.root!=root || pinned.source!=source || managed_root(backup)!=Some(root.clone()) {return Err(fail())}
    let leaf=path.file_name().and_then(|n|n.to_str()).filter(|n|component(n)).ok_or_else(fail)?;
    let backup_leaf=backup.file_name().and_then(|n|n.to_str()).filter(|n|component(n)).ok_or_else(fail)?;
    let _backup_lease=lease(&root,backup_leaf)?;
    let _lock=lock(&root)?;let mut manifest=load(&root)?;
    let target=manifest.files.iter().find(|i|i.file==leaf).ok_or_else(fail)?;
    if target.purpose!=Purpose::Recording || target.phase!=Phase::Sealed ||
        !target.sources.contains(&source) || target.identity.as_ref()!=Some(&expected) ||
        manifest.files.iter().any(|i|i.file.eq_ignore_ascii_case(backup_leaf)) ||
        fingerprint(path)?!=Some(damaged.clone()) || fingerprint(backup)?.is_some() {
        return Err("录音归属或备份校验不符，现有文件均已保留，未进行替换。".into());
    }
    // The expected preimage makes a crash with a completed backup safe for
    // privacy cleanup. A changed preimage never gets guessed on recovery.
    manifest.files.push(Artifact{file:backup_leaf.to_owned(),sources:BTreeSet::from([source]),
        purpose:Purpose::Recording,phase:Phase::Prepared,identity:Some(damaged)});
    save(&root,&manifest)?;
    let result=commit();
    let backup_identity=fingerprint(backup)?;
    let item=manifest.files.last_mut().ok_or_else(fail)?;
    if let Some(actual)=backup_identity {item.identity=Some(actual);item.phase=Phase::Sealed;}
    else {item.identity=None;item.phase=Phase::Gone;}
    let backup_sealed=item.phase==Phase::Sealed;
    save(&root,&manifest)?;
    let result=result?;
    if !backup_sealed || fingerprint(path)?!=Some(expected) {return Err(fail())}
    Ok(result)
}
pub(crate) fn restore_missing_original_pinned<T>(pinned:Option<&WriterLease>,source:&Path,path:&Path,
    bytes:u64,sha256:&str,commit:impl FnOnce()->Result<T,String>)->Result<T,String> {
    restore_missing_pinned(pinned,source,path,Purpose::CompressedOriginal,bytes,sha256,commit)
}
fn restore_missing_pinned<T>(pinned:Option<&WriterLease>,source:&Path,path:&Path,purpose:Purpose,
    bytes:u64,sha256:&str,commit:impl FnOnce()->Result<T,String>)->Result<T,String> {
    if fingerprint(path)?.is_some() {return Err(fail())};
    let Some(root)=managed_root(path) else{return commit()};
    let pinned=pinned.ok_or_else(fail)?;let source=reference_key(source)?;
    if pinned.root!=root||pinned.source!=source {return Err(fail())};
    let leaf=path.file_name().and_then(|n|n.to_str()).filter(|n|component(n)).ok_or_else(fail)?;
    let _file_lease=if source!=reference_key(path)? {Some(lease(&root,leaf)?)}else{None};
    let _lock=lock(&root)?;let manifest=load(&root)?;
    let item=manifest.files.iter().find(|i|i.file==leaf).ok_or_else(fail)?;
    let expected=Identity{bytes,sha256:sha256.to_owned()};
    if item.purpose!=purpose||item.phase!=Phase::Sealed||
        !item.sources.contains(&source)||item.identity.as_ref()!=Some(&expected)||fingerprint(path)?.is_some() {
        return Err("录音归属记录不允许重建；已清理或身份不符的文件不会自动恢复。".into());
    }
    let result=commit()?;
    if fingerprint(path)?!=Some(expected) {return Err(fail())};
    // No metadata transition is needed: before/after the atomic commit the
    // same previously sealed identity applies. A failed commit keeps that
    // proof retryable rather than changing an accidental absence into Gone.
    Ok(result)
}
// Holding this across consumption also protects siblings during deletion's
// all-file preflight. Every writer/deleter uses OS locks across processes.
pub(crate) fn usage(path: &Path) -> Result<Option<File>, String> {
    // Imports still own their generated ASR chunks even though the source
    // itself is external and must never be deleted. Lease the source reference.
    let root = super::audio_storage::recording_root()?;
    Ok(Some(reference_lease(&root, &reference_key(path)?, true)?))
}
/// Capture ancestry while scratch files still exist. Cache ownership must not
/// depend on a retired scratch bridge surviving manifest compaction.
pub(crate) fn source_references(path: &Path) -> Result<BTreeSet<String>, String> {
    let mut keys = BTreeSet::from([reference_key(path)?]);
    let Some(root) = managed_root(path) else {
        return Ok(keys);
    };
    let _lock = lock(&root)?;
    let data = load(&root)?;
    loop {
        let before = keys.len();
        for item in &data.files {
            if keys.contains(&reference_key(&root.join(&item.file))?) {
                keys.extend(item.sources.iter().cloned());
            }
        }
        if before == keys.len() {
            return Ok(keys);
        }
    }
}
pub(crate) fn exclusive_sources(paths: &[String]) -> Result<Vec<File>, String> {
    let root = super::audio_storage::recording_root()?;
    let keys = paths
        .iter()
        .map(|p| reference_key(Path::new(p)))
        .collect::<Result<BTreeSet<_>, _>>()?;
    keys.iter()
        .map(|key| reference_lease(&root, key, false))
        .collect()
}
fn reachable(root: &Path, data: &Manifest, sources: &[String]) -> Result<BTreeSet<String>, String> {
    let mut keys = sources
        .iter()
        .filter_map(|p| reference_key(Path::new(p)).ok())
        .collect::<BTreeSet<_>>();
    loop {
        let before = keys.len();
        for item in &data.files {
            if item.sources.iter().any(|s| keys.contains(s)) {
                keys.insert(reference_key(&root.join(&item.file))?);
            }
        }
        if before == keys.len() {
            return Ok(keys);
        }
    }
}
/// Attach explicitly generated prefix groups to the integrity-checked final
/// recording. Includes failed consumers, never an inferred basename sibling.
pub(crate) fn attach_group(anchor: &Path, owner: &Path) -> Result<(), String> {
    let Some(root) = managed_root(anchor) else {
        return Ok(());
    };
    let _lock = lock(&root)?;
    let mut data = load(&root)?;
    let keys = reachable(&root, &data, &[anchor.to_string_lossy().into_owned()])?;
    let owner = reference_key(owner)?;
    let mut changed = false;
    for item in &mut data.files {
        if keys.contains(&reference_key(&root.join(&item.file))?) && item.phase != Phase::Gone {
            if !item.sources.contains(&owner) && item.sources.len() >= 1024 {
                return Err(fail());
            }
            changed |= item.sources.insert(owner.clone());
        }
    }
    if changed {
        save(&root, &data)?;
    }
    drop(_lock);
    if super::transcription::attach_cache_sources(&keys, &owner).is_err() {
        eprintln!("ASR cache attachment pending; verified recording retained");
    }
    Ok(())
}
/// The existing resumable transfer creates its cursor before a WAV exists.
/// Claim only the exact cursor that this completed transfer verified, using
/// its full byte identity. Never adopt an inferred sibling or scan old files.
pub(crate) fn verified_cursor(
    owner: &Path,
    path: &Path,
    bytes: u64,
    sha256: &str,
) -> Result<(), String> {
    let root = managed_root(path).ok_or_else(fail)?;
    let leaf = path
        .file_name()
        .and_then(|n| n.to_str())
        .filter(|n| component(n) && n.starts_with(".device-recording-") && n.ends_with(".part"))
        .ok_or_else(fail)?;
    let _lease = lease(&root, leaf)?;
    let identity = fingerprint(path)?;
    let Some(identity) = identity else {
        return Ok(());
    };
    if identity.bytes != bytes || identity.sha256 != sha256 {
        return Err(fail());
    }
    let _lock = lock(&root)?;
    let mut data = load(&root)?;
    let key = reference_key(owner)?;
    if let Some(item) = data.files.iter_mut().find(|i| i.file == leaf) {
        if item.purpose != Purpose::TransferCursor
            || item.phase == Phase::Deleting
            || item.identity.as_ref().is_some_and(|i| i != &identity)
        {
            return Err(fail());
        }
        if !item.sources.contains(&key) && item.sources.len() >= 1024 {
            return Err(fail());
        }
        item.sources.insert(key);
        item.phase = Phase::Sealed;
        item.identity = Some(identity);
    } else {
        data.files.push(Artifact {
            file: leaf.into(),
            sources: BTreeSet::from([key]),
            purpose: Purpose::TransferCursor,
            phase: Phase::Sealed,
            identity: Some(identity),
        });
    }
    save(&root, &data)
}
#[derive(Default)]
pub(crate) struct Erase {
    pub deleted: usize,
    pub shared: usize,
    pub retained_paths: Vec<PathBuf>,
    /// The graph owns cleanup of these exact pathnames, including Gone entries.
    /// Legacy/index fallback may still clean verified old migration copies,
    /// but must never grant deletion authority to a replacement at this path.
    pub handled_paths: Vec<PathBuf>,
}
pub(crate) fn erase(
    root: &Path,
    sources: &[String],
    protected: &[String],
) -> Result<Erase, String> {
    erase_inner(root, sources, protected, false)
}
fn erase_inner(
    root: &Path,
    sources: &[String],
    protected: &[String],
    temporary_only: bool,
) -> Result<Erase, String> {
    let root = root.canonicalize().map_err(|_| fail())?;
    let _lock = lock(&root)?;
    let mut data = load(&root)?;
    let selected = reachable(&root, &data, sources)?;
    let retained = reachable(&root, &data, protected)?;
    let mut report = Erase::default();
    let mut candidates = Vec::new();
    let mut leases = Vec::new();
    let mut lease_keys = sources
        .iter()
        .filter_map(|p| reference_key(Path::new(p)).ok())
        .collect::<BTreeSet<_>>();
    let requested_roots = lease_keys.clone();
    let mut root_marker_changed = false;
    for (index, item) in data.files.iter_mut().enumerate() {
        let key = reference_key(&root.join(&item.file))?;
        if !selected.contains(&key) || temporary_only && !item.purpose.temporary() {
            continue;
        }
        report.handled_paths.push(root.join(&item.file));
        if requested_roots.contains(&key) && !item.purpose.temporary() {
            root_marker_changed |= item.sources.insert(key.clone());
        }
        if item.phase == Phase::Gone { continue; }
        if retained.contains(&key) {
            report.shared += 1;
            report.retained_paths.push(root.join(&item.file));
            continue;
        }
        lease_keys.insert(key);
        candidates.push(index);
    }
    if candidates.is_empty() {
        if root_marker_changed { save(&root, &data)?; }
        return Ok(report);
    }
    for key in lease_keys {
        leases.push(reference_lease(&root, &key, false)?);
    }
    for &index in &candidates {
        let item = &data.files[index];
        let actual = fingerprint(&root.join(&item.file))?;
        if actual.is_some() && (item.identity.is_none() || actual != item.identity) {
            return Err(fail());
        }
    }
    // A durable delete intention precedes the first physical deletion. A
    // failure preserves identities and can retry even when files are gone.
    for &index in &candidates {
        data.files[index].phase = Phase::Deleting;
    }
    save(&root, &data)?;
    for &index in &candidates {
        match fs::remove_file(root.join(&data.files[index].file)) {
            Ok(()) => report.deleted += 1,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(_) => return Err(fail()),
        }
        data.files[index].phase = Phase::Gone;
    }
    save(&root, &data)?;
    drop(leases);
    Ok(report)
}
pub(crate) fn remove_temporary(path: &Path) -> Result<(), String> {
    if let Some(root) = managed_root(path) {
        // Exact file selection (not its generated siblings).
        let _lock = lock(&root)?;
        let data = load(&root)?;
        let key = reference_key(path)?;
        if !data.files.iter().any(|i| {
            reference_key(&root.join(&i.file)).ok().as_ref() == Some(&key) && i.purpose.temporary()
        }) {
            return Err(fail());
        }
        drop(_lock);
        erase_inner(&root, &[path.to_string_lossy().into_owned()], &[], true)?;
        Ok(())
    } else {
        Err("临时音频不在受管录音目录，未删除。".into())
    }
}

mod probe;
pub(crate) use probe::verify;
