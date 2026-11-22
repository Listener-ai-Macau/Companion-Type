//! A small write-ahead journal for cache bodies. It contains hashes and owners,
//! never transcript text, credentials or speaker features. Unknown files stay.
use super::*;
use std::{
    collections::BTreeSet,
    fs::{File, OpenOptions},
};

const JOURNAL: &str = ".cache-owners.json";
const MAX_JOURNAL_BYTES: u64 = 8 * 1024 * 1024;
const MAX_RECORDS: usize = 16_384;
#[derive(Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
enum Phase {
    Prepared,
    Ready,
    Deleting,
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Record {
    file: String,
    bytes: u64,
    sha256: String,
    sources: BTreeSet<String>,
    sessions: BTreeSet<String>,
    phase: Phase,
}
#[derive(Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Journal {
    version: u32,
    records: Vec<Record>,
}
fn fail() -> String {
    "转写缓存归属或清理记录不可用，会议记录保留；请解除占用或恢复记录后重试。".into()
}
fn no_link(path: &Path) -> Result<(), String> {
    match fs::symlink_metadata(path) {
        Ok(m) if !m.is_file() || m.file_type().is_symlink() => Err(fail()),
        Ok(_) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(_) => Err(fail()),
    }
}
fn cache_leaf(name: &str) -> bool {
    name.starts_with("v2-") && super::is_cache_name(name) && !name.contains(['/', '\\', ':', '\0'])
}
fn read_bytes(path: &Path, limit: u64) -> Result<Option<Vec<u8>>, String> {
    no_link(path)?;
    let file = match File::open(path) {
        Ok(f) => f,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err(fail()),
    };
    let mut bytes = Vec::new();
    file.take(limit + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| fail())?;
    if bytes.len() as u64 > limit {
        return Err(fail());
    }
    Ok(Some(bytes))
}
fn load_journal(root: &Path) -> Result<Journal, String> {
    let Some(bytes) = read_bytes(&root.join(JOURNAL), MAX_JOURNAL_BYTES)? else {
        return Ok(Journal {
            version: 1,
            records: vec![],
        });
    };
    let data: Journal = serde_json::from_slice(&bytes).map_err(|_| fail())?;
    let mut names = BTreeSet::new();
    if data.version != 1 || data.records.len() > MAX_RECORDS {
        return Err(fail());
    }
    for r in &data.records {
        if !cache_leaf(&r.file)
            || !names.insert(&r.file)
            || r.bytes > MAX_ENTRY_BYTES
            || r.sha256.len() != 64
            || !r.sha256.bytes().all(|b| b.is_ascii_hexdigit())
            || r.sources.is_empty()
            || r.sources.len() > 1024
            || r.sessions.len() > 1024
            || r.sources
                .iter()
                .chain(r.sessions.iter())
                .any(|s| s.is_empty() || s.len() > 32_768)
        {
            return Err(fail());
        }
    }
    Ok(data)
}
fn save(root: &Path, data: &Journal) -> Result<(), String> {
    let bytes = serde_json::to_vec(data).map_err(|_| fail())?;
    if bytes.len() as u64 > MAX_JOURNAL_BYTES || data.records.len() > MAX_RECORDS {
        return Err(fail());
    }
    super::super::super::export::write_atomic(&root.join(JOURNAL), &bytes)
        .map(|_| ())
        .map_err(|_| fail())
}
fn open_journal_lock(root: &Path) -> Result<File, String> {
    let m = fs::symlink_metadata(root).map_err(|_| fail())?;
    if !m.is_dir() || m.file_type().is_symlink() {
        return Err(fail());
    }
    let path = root.join(".cache-owners.lock");
    no_link(&path)?;
    OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .open(path)
        .map_err(|_| fail())
}

fn lock(root: &Path) -> Result<File, String> {
    let file = open_journal_lock(root)?;
    file.try_lock().map_err(|_| fail())?;
    Ok(file)
}
fn claim(
    data: &mut Journal,
    file: &str,
    bytes: &[u8],
    sources: &BTreeSet<String>,
    phase: Phase,
) -> Result<(), String> {
    if sources.is_empty() || sources.len() > 1024 {
        return Err(fail());
    }
    let r = if let Some(index) = data.records.iter().position(|r| r.file == file) {
        &mut data.records[index]
    } else {
        data.records.push(Record {
            file: file.into(),
            bytes: 0,
            sha256: String::new(),
            sources: BTreeSet::new(),
            sessions: BTreeSet::new(),
            phase,
        });
        data.records.last_mut().unwrap()
    };
    if r.phase == Phase::Deleting {
        return Err(fail());
    }
    r.sources.extend(sources.iter().cloned());
    if r.sources.len() > 1024 {
        return Err(fail());
    }
    r.bytes = bytes.len() as u64;
    r.sha256 = digest(bytes);
    r.phase = phase;
    Ok(())
}
fn hit(
    root: &Path,
    key: &Key,
    sources: &BTreeSet<String>,
) -> Result<Option<(String, Vec<Utterance>)>, String> {
    if !root.exists() {
        return Ok(None);
    }
    let _lock = super::super::super::audio_artifacts::wait_for_asr_journal(open_journal_lock(root)?)
        .map_err(|_| fail())?;
    let mut data = load_journal(root)?;
    let path = key.path(root)?;
    no_link(&path)?;
    let Some((entry, bytes)) = inspect(&path).filter(|(e, _)| e.key == *key) else {
        return Ok(None);
    };
    if data
        .records
        .iter()
        .find(|r| path.file_name().and_then(|n| n.to_str()) == Some(&r.file))
        .is_some_and(|r| r.bytes != bytes.len() as u64 || r.sha256 != digest(&bytes))
    {
        return Err(fail());
    }
    claim(
        &mut data,
        path.file_name().and_then(|s| s.to_str()).ok_or_else(fail)?,
        &bytes,
        sources,
        Phase::Ready,
    )?;
    save(root, &data)?;
    Ok(Some((entry.text, entry.utterances)))
}
fn publish(
    root: &Path,
    key: &Key,
    text: &str,
    utterances: &[Utterance],
    sources: &BTreeSet<String>,
) -> Result<(), String> {
    fs::create_dir_all(root).map_err(|_| fail())?;
    let _lock = super::super::super::audio_artifacts::wait_for_asr_journal(open_journal_lock(root)?)
        .map_err(|_| fail())?;
    let mut data = load_journal(root)?;
    let path = key.path(root)?;
    no_link(&path)?;
    if let Some((_, bytes)) = inspect(&path).filter(|(e, bytes)| {
        e.key == *key
            && !data
                .records
                .iter()
                .find(|r| path.file_name().and_then(|n| n.to_str()) == Some(&r.file))
                .is_some_and(|r| r.bytes != bytes.len() as u64 || r.sha256 != digest(bytes))
    }) {
        claim(
            &mut data,
            path.file_name().and_then(|s| s.to_str()).ok_or_else(fail)?,
            &bytes,
            sources,
            Phase::Ready,
        )?;
        return save(root, &data);
    }
    let entry = Entry {
        key: key.clone(),
        text: text.into(),
        utterances: utterances.to_vec(),
        result_sha256: result_digest(text, utterances)?,
    };
    let bytes = serde_json::to_vec(&entry).map_err(|_| fail())?;
    if bytes.len() as u64 > MAX_ENTRY_BYTES {
        return Err(fail());
    }
    let leaf = path.file_name().and_then(|s| s.to_str()).ok_or_else(fail)?;
    claim(&mut data, leaf, &bytes, sources, Phase::Prepared)?;
    save(root, &data)?; // Identity and owners reach disk before the body.
    super::super::super::export::write_atomic(&path, &bytes)?;
    claim(&mut data, leaf, &bytes, sources, Phase::Ready)?;
    save(root, &data)?;
    let protected = data.records.iter()
        .filter(|r| r.phase != Phase::Ready || !r.sources.is_disjoint(sources))
        .map(|r| r.file.clone())
        .collect();
    trim_except(root, &protected);
    // Retention may have removed bodies; don't retain their private path hints.
    data.records
        .retain(|r| r.phase == Phase::Deleting || root.join(&r.file).exists());
    save(root, &data)
}
/// Reuse a verified final result and bind it to the current audio source.
pub(in crate::backend::transcription) fn reuse(
    root: &Path,
    key: &Key,
    source: &Path,
) -> Option<(String, Vec<Utterance>)> {
    let sources = super::super::super::audio_artifacts::source_references(source).ok()?;
    hit(root, key, &sources).ok().flatten()
}

pub(in crate::backend::transcription) fn resolve<F>(
    root: &Path,
    key: &Key,
    source: &Path,
    provider: F,
) -> Result<(String, Vec<Utterance>), String>
where
    F: FnOnce() -> Result<(String, Vec<Utterance>), String>,
{
    let sources = super::super::super::audio_artifacts::source_references(source);
    if let Ok(sources) = &sources {
        if let Ok(Some(cached)) = hit(root, key, sources) {
            return Ok(cached);
        }
    }
    let result = provider()?;
    if !key.valid_result(&result.0, &result.1) {
        return Err("ASR final result is empty or has invalid timing".into());
    }
    if sources
        .and_then(|s| publish(root, key, &result.0, &result.1, &s))
        .is_err()
    {
        eprintln!("[transcription] owned_chunk_cache write=unavailable");
    }
    Ok(result) // Optional cache faults never discard a paid final result.
}
pub(in crate::backend::transcription) fn bind_session(
    root: &Path,
    session: &str,
    sources: &BTreeSet<String>,
) -> Result<(), String> {
    if !root.exists() {
        return Ok(());
    }
    if session.is_empty() {
        return Err(fail());
    }
    let _lock = lock(root)?;
    let mut data = load_journal(root)?;
    for r in &mut data.records {
        if r.phase != Phase::Deleting && !r.sources.is_disjoint(sources) {
            r.sessions.insert(session.into());
            if r.sessions.len() > 1024 {
                return Err(fail());
            }
        }
    }
    save(root, &data)
}
pub(in crate::backend::transcription) fn attach(
    root: &Path,
    sources: &BTreeSet<String>,
    owner: &str,
) -> Result<(), String> {
    if !root.exists() {
        return Ok(());
    }
    let _lock = lock(root)?;
    let mut data = load_journal(root)?;
    for r in &mut data.records {
        if r.phase != Phase::Deleting && !r.sources.is_disjoint(sources) {
            r.sources.insert(owner.into());
            if r.sources.len() > 1024 {
                return Err(fail());
            }
        }
    }
    save(root, &data)
}

#[derive(Default)]
pub(crate) struct Erase {
    pub deleted: usize,
    pub shared: usize,
    pub unknown: usize,
}
fn source_keys(paths: &[String]) -> Result<BTreeSet<String>, String> {
    let mut keys = BTreeSet::new();
    for path in paths {
        keys.extend(super::super::super::audio_artifacts::source_references(
            Path::new(path),
        )?);
    }
    Ok(keys)
}
fn pcm_keys(paths: &[String]) -> BTreeSet<(String, u64)> {
    paths
        .iter()
        .filter_map(|p| super::super::super::diarization::read_pcm16k_mono_wav(Path::new(p)).ok())
        .map(|pcm| (digest(&pcm), (pcm.len() / 2) as u64))
        .collect()
}
/// All intent is committed before unlinking. A failed body or journal write
/// leaves exact identities retryable, even after the source WAV disappeared.
pub(crate) fn erase(
    root: &Path,
    sessions: &BTreeSet<String>,
    sources: &[String],
    retained_sessions: &BTreeSet<String>,
    retained: &[String],
    all: bool,
) -> Result<Erase, String> {
    if !root.exists() {
        return Ok(Erase::default());
    }
    let sources = source_keys(sources)?;
    let protected = source_keys(retained)?;
    let _lock = lock(root)?;
    let mut data = load_journal(root)?;
    let selected_pcm = pcm_keys(&sources.iter().cloned().collect::<Vec<_>>());
    let protected_pcm = pcm_keys(&protected.iter().cloned().collect::<Vec<_>>());
    let mut report = Erase::default();
    // Adopt old V2 bodies only when the schema, result digest and filename all
    // prove identity. Old V1/embedding or malformed JSON stays unclaimed.
    for entry in fs::read_dir(root).map_err(|_| fail())? {
        let entry = entry.map_err(|_| fail())?;
        let name = entry.file_name();
        let Some(name) = name.to_str() else {
            continue;
        };
        if !super::is_cache_name(name) || data.records.iter().any(|r| r.file == name) {
            continue;
        }
        let Some((old, bytes)) = inspect(&entry.path()) else {
            report.unknown += 1;
            continue;
        };
        let pcm_key = (old.key.pcm_sha256, old.key.pcm_samples);
        if !(all || selected_pcm.contains(&pcm_key)) {
            continue;
        }
        if protected_pcm.contains(&pcm_key) {
            report.shared += 1;
            continue;
        }
        // The validated legacy identity is durable before its deletion too.
        let owners = if sources.is_empty() {
            BTreeSet::from(["legacy-v2-verified".into()])
        } else {
            sources.clone()
        };
        claim(&mut data, name, &bytes, &owners, Phase::Ready)?;
    }
    let mut chosen = BTreeSet::new();
    for r in &mut data.records {
        if !(all || !r.sessions.is_disjoint(sessions) || !r.sources.is_disjoint(&sources)) {
            continue;
        }
        let shared = !all
            && if r.sessions.is_empty() {
                !r.sources.is_disjoint(&protected)
            } else {
                !r.sessions.is_disjoint(retained_sessions)
            };
        if shared && r.phase != Phase::Deleting {
            r.sessions.retain(|s| !sessions.contains(s));
            let keep_source = |source: &String| !sources.contains(source) || protected.contains(source);
            // Older entries can name a surviving session without a matching
            // path. Keep the journal readable without inventing a replacement
            // source for such entries.
            if r.sources.iter().any(keep_source) {
                r.sources.retain(keep_source);
            }
            report.shared += 1;
            continue;
        }
        if let Some(bytes) = read_bytes(&root.join(&r.file), MAX_ENTRY_BYTES)? {
            if bytes.len() as u64 != r.bytes || digest(&bytes) != r.sha256 {
                return Err(fail());
            }
        }
        chosen.insert(r.file.clone());
        r.phase = Phase::Deleting;
    }
    save(root, &data)?;
    for leaf in &chosen {
        match fs::remove_file(root.join(leaf)) {
            Ok(()) => report.deleted += 1,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(_) => return Err(fail()),
        }
    }
    data.records.retain(|r| !chosen.contains(&r.file));
    save(root, &data)?;
    Ok(report)
}

mod probe;
pub(crate) use probe::verify;
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn concurrent_asr_windows_wait_for_cache_publication() {
        let dir = std::env::temp_dir().join(format!("companion-cache-parallel-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&dir).unwrap();
        let profile = Profile::from_configuration(&serde_json::json!({
            "provider":"test", "model":"test", "language":"zh"
        })).unwrap();
        let sources = BTreeSet::from(["same-recording".to_string()]);
        let occupied = lock(&dir).unwrap();
        let barrier = std::sync::Barrier::new(3);
        std::thread::scope(|scope| {
            let workers = [1_u32, 2].map(|value| {
                let key = Key::new(&value.to_le_bytes(), profile.clone()).unwrap();
                let dir = &dir;
                let sources = &sources;
                let barrier = &barrier;
                scope.spawn(move || {
                    barrier.wait();
                    publish(dir, &key, "完成", &[], sources).unwrap();
                    assert!(hit(dir, &key, sources).unwrap().is_some());
                })
            });
            barrier.wait();
            std::thread::sleep(std::time::Duration::from_millis(40));
            drop(occupied);
            for worker in workers {
                worker.join().unwrap();
            }
        });
        assert_eq!(load_journal(&dir).unwrap().records.len(), 2);
        for file in fs::read_dir(&dir).unwrap() {
            fs::remove_file(file.unwrap().path()).unwrap();
        }
        fs::remove_dir(dir).unwrap();
    }

    #[test]
    fn retention_preserves_all_windows_of_current_long_recording() {
        let dir = std::env::temp_dir().join(format!("companion-cache-long-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&dir).unwrap();
        let profile = Profile::from_configuration(&serde_json::json!({
            "provider":"test", "model":"test", "language":"zh"
        })).unwrap();
        let current = BTreeSet::from(["current-recording".to_string()]);
        let old = BTreeSet::from(["older-recording".to_string()]);
        let mut journal = Journal { version: 1, records: Vec::new() };
        let mut current_keys = Vec::new();
        // Seed an older recording, followed by more than the ordinary global
        // cache limit for the current recording. All entries have real V2
        // identity and the same ownership journal used by production.
        for index in 0u32..(MAX_ENTRIES as u32 + 5) {
            let key = Key::new(&index.to_le_bytes(), profile.clone()).unwrap();
            let entry = Entry { key: key.clone(), text: "完成".into(), utterances: vec![],
                result_sha256: result_digest("完成", &[]).unwrap() };
            let bytes = serde_json::to_vec(&entry).unwrap();
            let path = key.path(&dir).unwrap();
            fs::write(&path, &bytes).unwrap();
            let owners = if index < 3 { &old } else { &current };
            claim(&mut journal, path.file_name().unwrap().to_str().unwrap(), &bytes, owners, Phase::Ready).unwrap();
            if index >= 3 { current_keys.push(key); }
        }
        save(&dir, &journal).unwrap();
        let new_key = Key::new(&u32::MAX.to_le_bytes(), profile).unwrap();
        publish(&dir, &new_key, "完成", &[], &current).unwrap();
        for key in &current_keys {
            assert!(load(&dir, key).is_some(), "current recording lost a completed window");
        }
        assert!(hit(&dir, &current_keys[0], &current).unwrap().is_some());
        assert!(hit(&dir, &new_key, &current).unwrap().is_some());
        assert_eq!(load_journal(&dir).unwrap().records.len(), current_keys.len() + 1);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn isolated_native_cache_privacy_contract() {
        let dir =
            std::env::temp_dir().join(format!("companion-cache-privacy-{}", uuid::Uuid::new_v4()));
        let report = super::verify(&dir).unwrap();
        assert_eq!(report["result"], "PASS_LOCAL_CACHE_PRIVACY_ONLY");
        assert!(super::verify(&dir).is_err());
        // Keep the fresh fixture and report as evidence; never remove a caller path.
    }
}
