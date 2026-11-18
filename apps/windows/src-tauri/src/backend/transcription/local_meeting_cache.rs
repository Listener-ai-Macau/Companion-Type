//! Owned scratch space for local meeting audio, words and speaker features.
//! Ownership is durable before the producer starts. Python records write intent
//! before opening a generated file; deletion refuses unknown files and links.
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeSet,
    fs::{self, File, OpenOptions},
    io::Read,
    path::{Path, PathBuf},
};

const ERROR: &str = "本机识别缓存正在使用或归属无法核实，原录音和会议保留；请稍后重试。";
const INDEX: &str = ".local-meeting-owners.json";
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Entry {
    id: String,
    owner: String,
    key: String,
    marker: String,
    deleting: Option<Vec<Body>>,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Body {
    path: String,
    bytes: u64,
    sha256: String,
}
#[derive(Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Journal {
    entries: Vec<Entry>,
}
pub(super) struct Lease {
    pub root: PathBuf,
    _lease: File,
}

fn err() -> String {
    ERROR.into()
}
fn safe(path: &Path, dir: bool) -> Result<(), String> {
    let m = fs::symlink_metadata(path).map_err(|_| err())?;
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if m.file_attributes() & 0x400 != 0 {
            return Err(err());
        }
    }
    if m.file_type().is_symlink() || if dir { !m.is_dir() } else { !m.is_file() } {
        return Err(err());
    }
    Ok(())
}
fn base(root: &Path) -> PathBuf {
    root.join("local-meeting")
}
fn setup(root: &Path) -> Result<(), String> {
    fs::create_dir_all(root).map_err(|_| err())?;
    safe(root, true)
}
fn lock(path: &Path) -> Result<File, String> {
    if path.exists() {
        safe(path, false)?;
    }
    let f = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(|_| err())?;
    f.try_lock().map_err(|_| err())?;
    Ok(f)
}
fn load(root: &Path) -> Result<Journal, String> {
    let p = root.join(INDEX);
    if !p.exists() {
        return Ok(Journal::default());
    }
    safe(&p, false)?;
    if fs::metadata(&p).map_err(|_| err())?.len() > 8 * 1024 * 1024 {
        return Err(err());
    }
    let j: Journal =
        serde_json::from_slice(&fs::read(&p).map_err(|_| err())?).map_err(|_| err())?;
    let mut ids = BTreeSet::new();
    for e in &j.entries {
        if uuid::Uuid::parse_str(&e.id).is_err()
            || !ids.insert(e.id.clone())
            || e.owner.is_empty()
            || e.owner.len() > 4096
            || e.marker.len() != 36
            || e.key.is_empty()
        {
            return Err(err());
        }
    }
    Ok(j)
}
fn save(root: &Path, j: &Journal) -> Result<(), String> {
    super::super::export::write_atomic(
        &root.join(INDEX),
        &serde_json::to_vec(j).map_err(|_| err())?,
    )
    .map(|_| ())
    .map_err(|_| err())
}
fn verify(root: &Path, e: &Entry) -> Result<(), String> {
    safe(root, true)?;
    let marker = root.join(".owner");
    safe(&marker, false)?;
    if fs::read_to_string(marker).map_err(|_| err())? != e.marker {
        return Err(err());
    }
    Ok(())
}
fn acquire(root: &Path, e: &Entry) -> Result<Lease, String> {
    let lease = lock(&root.join(format!(".job-{}.lock", e.id)))?;
    let job = root.join(&e.id);
    if !job.exists() {
        fs::create_dir(&job).map_err(|_| err())?;
    }
    safe(&job, true)?;
    let path = job.join(".owner");
    // Recover an intent written before the empty directory was initialized.
    // Never adopt an unmarked directory that already contains data.
    if !path.exists() && fs::read_dir(&job).map_err(|_| err())?.next().is_none() {
        use std::io::Write;
        let mut marker = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&path)
            .map_err(|_| err())?;
        marker.write_all(e.marker.as_bytes()).map_err(|_| err())?;
        marker.sync_all().map_err(|_| err())?;
    }
    verify(&job, e)?;
    Ok(Lease {
        root: job,
        _lease: lease,
    })
}
pub(super) fn reserve(cache_root: &Path, owner: &str, key: &str) -> Result<Lease, String> {
    if owner.is_empty() || owner.len() > 4096 {
        return Err(err());
    }
    setup(cache_root)?;
    let root = base(cache_root);
    setup(&root)?;
    let _index = lock(&root.join(".owners.lock"))?;
    let mut j = load(&root)?;
    if let Some(e) = j
        .entries
        .iter()
        .find(|e| e.owner == owner && e.key == key && e.deleting.is_none())
    {
        return acquire(&root, e);
    }
    let e = Entry {
        id: uuid::Uuid::new_v4().to_string(),
        owner: owner.into(),
        key: key.into(),
        marker: uuid::Uuid::new_v4().to_string(),
        deleting: None,
    };
    // Write intent before creating the namespace, and never reuse a foreign dir.
    j.entries.push(e.clone());
    save(&root, &j)?;
    acquire(&root, &e)
}
fn relative(root: &Path, name: &str) -> Result<PathBuf, String> {
    let p = Path::new(name);
    if name.is_empty()
        || name.contains(['\\', ':', '\0'])
        || p.components()
            .any(|c| !matches!(c, std::path::Component::Normal(_)))
    {
        return Err(err());
    }
    let mut out = root.to_path_buf();
    let parts = p.components().collect::<Vec<_>>();
    for (i, c) in parts.iter().enumerate() {
        out.push(c.as_os_str());
        if out.exists() {
            safe(&out, i + 1 < parts.len())?;
        }
    }
    Ok(out)
}
fn digest(path: &Path) -> Result<Body, String> {
    safe(path, false)?;
    let mut f = File::open(path).map_err(|_| err())?;
    let bytes = f.metadata().map_err(|_| err())?.len();
    let mut h = Sha256::new();
    let mut b = [0u8; 65536];
    loop {
        let n = f.read(&mut b).map_err(|_| err())?;
        if n == 0 {
            break;
        }
        h.update(&b[..n]);
    }
    Ok(Body {
        path: String::new(),
        bytes,
        sha256: format!("{:x}", h.finalize()),
    })
}
fn inventory(root: &Path) -> Result<Vec<Body>, String> {
    let audit = root.join(".artifact-writes.jsonl");
    let mut known = BTreeSet::from([
        ".owner".to_string(),
        "input.json".into(),
        "audio.pcm".into(),
        "sealed.json".into(),
        ".artifact-writes.jsonl".into(),
        ".artifact-writes.lock".into(),
    ]);
    if audit.exists() {
        safe(&audit, false)?;
        if fs::metadata(&audit).map_err(|_| err())?.len() > 32 * 1024 * 1024 {
            return Err(err());
        }
        for line in fs::read_to_string(audit).map_err(|_| err())?.lines() {
            let name: String = serde_json::from_str(line).map_err(|_| err())?;
            relative(root, &name)?;
            known.insert(name);
        }
    }
    fn visit(
        root: &Path,
        dir: &Path,
        known: &BTreeSet<String>,
        out: &mut Vec<Body>,
    ) -> Result<(), String> {
        safe(dir, true)?;
        for e in fs::read_dir(dir).map_err(|_| err())? {
            let p = e.map_err(|_| err())?.path();
            let m = fs::symlink_metadata(&p).map_err(|_| err())?;
            if m.is_dir() {
                safe(&p, true)?;
                visit(root, &p, known, out)?;
            } else {
                safe(&p, false)?;
                let name = p
                    .strip_prefix(root)
                    .map_err(|_| err())?
                    .to_str()
                    .ok_or_else(err)?
                    .replace('\\', "/");
                if !known.contains(&name) {
                    return Err(err());
                }
                let mut b = digest(&p)?;
                b.path = name;
                out.push(b);
            }
        }
        Ok(())
    }
    let mut out = Vec::new();
    visit(root, root, &known, &mut out)?;
    Ok(out)
}
fn remove_empty(root: &Path) -> Result<(), String> {
    safe(root, true)?;
    for e in fs::read_dir(root).map_err(|_| err())? {
        let p = e.map_err(|_| err())?.path();
        safe(&p, true)?;
        remove_empty(&p)?;
    }
    fs::remove_dir(root).map_err(|_| err())
}
pub(super) fn erase(
    cache_root: &Path,
    sessions: &BTreeSet<String>,
    retained: &BTreeSet<String>,
    all: bool,
) -> Result<super::chunk_cache::ownership::Erase, String> {
    let root = base(cache_root);
    if !root.exists() {
        return Ok(Default::default());
    }
    safe(&root, true)?;
    let _index = lock(&root.join(".owners.lock"))?;
    let mut j = load(&root)?;
    let mut report = super::chunk_cache::ownership::Erase::default();
    let mut chosen = Vec::new();
    let mut leases = Vec::new();
    for (i, e) in j.entries.iter_mut().enumerate() {
        if !all && !sessions.contains(&e.owner) {
            continue;
        }
        if !all && retained.contains(&e.owner) {
            report.shared += 1;
            continue;
        }
        let lease = lock(&root.join(format!(".job-{}.lock", e.id)))?;
        leases.push(lease);
        let job = root.join(&e.id);
        if !job.exists() {
            if e.deleting.is_some() {
                chosen.push(i);
                continue;
            }
            return Err(err());
        }
        if e.deleting.is_none() {
            verify(&job, e)?;
            e.deleting = Some(inventory(&job)?);
        }
        chosen.push(i);
    }
    save(&root, &j)?;
    for &i in &chosen {
        let e = &j.entries[i];
        let job = root.join(&e.id);
        if !job.exists() {
            continue;
        }
        // Every unlink has a durable path, length and content identity. A
        // replaced body or an unknown new file is preserved and blocks success.
        for b in e.deleting.as_ref().ok_or_else(err)? {
            let p = relative(&job, &b.path)?;
            if !p.exists() {
                continue;
            }
            let actual = digest(&p)?;
            if actual.bytes != b.bytes || actual.sha256 != b.sha256 {
                return Err(err());
            }
        }
        for b in e.deleting.as_ref().ok_or_else(err)? {
            let p = relative(&job, &b.path)?;
            if p.exists() {
                fs::remove_file(p).map_err(|_| err())?;
                report.deleted += 1;
            }
        }
        remove_empty(&job)?;
    }
    let ids = chosen
        .iter()
        .map(|i| j.entries[*i].id.clone())
        .collect::<BTreeSet<_>>();
    j.entries.retain(|e| !ids.contains(&e.id));
    save(&root, &j)?;
    drop(leases);
    for id in ids {
        fs::remove_file(root.join(format!(".job-{id}.lock"))).map_err(|_| err())?;
    }
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn retries_the_same_empty_namespace_after_ownership_intent() {
        let root =
            std::env::temp_dir().join(format!("companion-local-meeting-{}", uuid::Uuid::new_v4()));
        let owned = base(&root);
        setup(&owned).unwrap();
        let entry = Entry {
            id: uuid::Uuid::new_v4().to_string(),
            owner: "session".into(),
            key: "full".into(),
            marker: uuid::Uuid::new_v4().to_string(),
            deleting: None,
        };
        save(
            &owned,
            &Journal {
                entries: vec![entry.clone()],
            },
        )
        .unwrap();
        let first = reserve(&root, "session", "full").unwrap();
        assert_eq!(first.root, owned.join(&entry.id));
        assert_eq!(
            fs::read_to_string(first.root.join(".owner")).unwrap(),
            entry.marker
        );
        drop(first);
        assert_eq!(
            reserve(&root, "session", "full").unwrap().root,
            owned.join(&entry.id)
        );
    }

    #[test]
    fn selected_owner_erase_keeps_other_and_refuses_busy_or_foreign_files() {
        let root =
            std::env::temp_dir().join(format!("companion-local-meeting-{}", uuid::Uuid::new_v4()));
        let a = reserve(&root, "a", "full").unwrap();
        let ap = a.root.clone();
        fs::write(ap.join("audio.pcm"), b"private-a").unwrap();
        assert!(erase(
            &root,
            &BTreeSet::from(["a".into()]),
            &BTreeSet::new(),
            false
        )
        .is_err());
        drop(a);
        let b = reserve(&root, "b", "stream-b").unwrap();
        let bp = b.root.clone();
        fs::write(bp.join("audio.pcm"), b"private-b").unwrap();
        drop(b);
        fs::write(ap.join("foreign.json"), b"unowned").unwrap();
        assert!(erase(
            &root,
            &BTreeSet::from(["a".into()]),
            &BTreeSet::new(),
            false
        )
        .is_err());
        assert_eq!(fs::read(ap.join("foreign.json")).unwrap(), b"unowned");
        assert!(ap.join("audio.pcm").exists());
        fs::remove_file(ap.join("foreign.json")).unwrap();
        erase(
            &root,
            &BTreeSet::from(["a".into()]),
            &BTreeSet::from(["b".into()]),
            false,
        )
        .unwrap();
        assert!(!ap.exists());
        assert_eq!(fs::read(bp.join("audio.pcm")).unwrap(), b"private-b");
        erase(&root, &BTreeSet::new(), &BTreeSet::new(), true).unwrap();
        assert!(!bp.exists());
        // Keep the isolated probe directory/journal as verification evidence.
    }
    #[test]
    fn replaced_marker_and_parent_path_are_never_adopted() {
        let root =
            std::env::temp_dir().join(format!("companion-local-meeting-{}", uuid::Uuid::new_v4()));
        let a = reserve(&root, "a", "full").unwrap();
        let p = a.root.clone();
        drop(a);
        fs::write(p.join(".owner"), b"replaced").unwrap();
        assert!(reserve(&root, "a", "full").is_err());
        assert!(erase(&root, &BTreeSet::new(), &BTreeSet::new(), true).is_err());
        assert!(relative(&p, "../original.wav").is_err());
    }
}
