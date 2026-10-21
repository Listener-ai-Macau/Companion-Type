//! Versioned, disposable cache of final provider results. Local speaker
//! embeddings are deliberately recomputed, never persisted in this cache.
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

use super::super::volcengine::Utterance;

const SCHEMA: &str = "companion-type.asr-chunk-cache.v2";
// Bump when the PCM interpretation or provider-result extraction changes.
const PROCESSING_VERSION: &str = "pcm16k-mono-s16le-volc-final-v3";
const MAX_ENTRY_BYTES: u64 = 4 * 1024 * 1024;
const MAX_ENTRIES: usize = 512;

fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Profile {
    provider: String,
    model: String,
    language: String,
    processing_version: String,
    // Includes endpoint, resource/account scope, hotwords, audio format and
    // every actual request option. No credentials or hotword text is stored.
    configuration_sha256: String,
}

impl Profile {
    pub(super) fn from_configuration(configuration: &Value) -> Result<Self, String> {
        let field = |name: &str| {
            configuration
                .get(name)
                .and_then(Value::as_str)
                .filter(|value| !value.trim().is_empty())
                .map(str::to_string)
                .ok_or_else(|| "ASR cache configuration is incomplete".to_string())
        };
        Ok(Self {
            provider: field("provider")?,
            model: field("model")?,
            language: field("language")?,
            processing_version: PROCESSING_VERSION.into(),
            configuration_sha256: digest(
                &serde_json::to_vec(configuration)
                    .map_err(|_| "ASR cache configuration cannot be encoded")?,
            ),
        })
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Key {
    schema: String,
    pcm_sha256: String,
    pcm_samples: u64,
    profile: Profile,
}

impl Key {
    pub(super) fn new(pcm: &[u8], profile: Profile) -> Result<Self, String> {
        if pcm.is_empty() || pcm.len() % 2 != 0 {
            return Err("ASR requires nonempty PCM16 audio".into());
        }
        Ok(Self {
            schema: SCHEMA.into(),
            pcm_sha256: digest(pcm),
            pcm_samples: (pcm.len() / 2) as u64,
            profile,
        })
    }

    fn path(&self, root: &Path) -> Result<PathBuf, String> {
        let bytes = serde_json::to_vec(self).map_err(|_| "ASR cache identity cannot be encoded")?;
        // A different name from v1 makes unsafe legacy reuse impossible.
        Ok(root.join(format!("v2-{}.json", digest(&bytes))))
    }

    fn valid_result(&self, text: &str, utterances: &[Utterance]) -> bool {
        let duration_ms = self.pcm_samples.saturating_mul(1000) / 16_000;
        !text.trim().is_empty()
            && utterances.iter().all(|utterance| {
                !utterance.text.trim().is_empty() && utterance.start_ms <= utterance.end_ms
                // Allow the provider's normal rounding at the audio boundary.
                && utterance.end_ms <= duration_ms.saturating_add(1000)
            })
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Entry {
    key: Key,
    text: String,
    utterances: Vec<Utterance>,
    result_sha256: String,
}

fn result_digest(text: &str, utterances: &[Utterance]) -> Result<String, String> {
    serde_json::to_vec(&(text, utterances))
        .map(|bytes| digest(&bytes))
        .map_err(|_| "ASR cache result cannot be encoded".into())
}

// Reading or removing a legacy V2 entry requires both its embedded identity
// and its exact content-addressed filename, never a filename pattern alone.
fn inspect(path: &Path) -> Option<(Entry, Vec<u8>)> {
    let metadata = fs::symlink_metadata(path).ok()?;
    if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() > MAX_ENTRY_BYTES
    {
        return None;
    }
    let mut bytes = Vec::new();
    fs::File::open(path)
        .ok()?
        .take(MAX_ENTRY_BYTES + 1)
        .read_to_end(&mut bytes)
        .ok()?;
    if bytes.len() as u64 > MAX_ENTRY_BYTES {
        return None;
    }
    let entry: Entry = serde_json::from_slice(&bytes).ok()?;
    if entry.key.schema != SCHEMA
        || entry.key.pcm_samples == 0
        || entry.key.pcm_sha256.len() != 64
        || !entry.key.pcm_sha256.bytes().all(|b| b.is_ascii_hexdigit())
        || !entry.key.valid_result(&entry.text, &entry.utterances)
        || result_digest(&entry.text, &entry.utterances).ok()? != entry.result_sha256
        || entry.key.path(path.parent()?).ok()?.file_name() != path.file_name()
    {
        return None;
    }
    Some((entry, bytes))
}

pub(super) fn load(root: &Path, key: &Key) -> Option<(String, Vec<Utterance>)> {
    let mut file = fs::File::open(key.path(root).ok()?).ok()?;
    let metadata = file.metadata().ok()?;
    if !metadata.is_file() || metadata.len() > MAX_ENTRY_BYTES {
        return None;
    }
    // The bounded read also covers a file growing after metadata was checked.
    let mut bytes = Vec::new();
    file.by_ref()
        .take(MAX_ENTRY_BYTES + 1)
        .read_to_end(&mut bytes)
        .ok()?;
    drop(file);
    if bytes.len() as u64 > MAX_ENTRY_BYTES {
        return None;
    }
    let entry: Entry = serde_json::from_slice(&bytes).ok()?;
    if entry.key != *key
        || !key.valid_result(&entry.text, &entry.utterances)
        || result_digest(&entry.text, &entry.utterances).ok()? != entry.result_sha256
    {
        return None;
    }
    Some((entry.text, entry.utterances))
}

pub(super) fn store(
    root: &Path,
    key: &Key,
    text: &str,
    utterances: &[Utterance],
) -> Result<(), String> {
    if !key.valid_result(text, utterances) {
        return Err("ASR final result is empty or has invalid timing".into());
    }
    if load(root, key).is_some() {
        return Ok(());
    }
    let entry = Entry {
        key: key.clone(),
        text: text.into(),
        utterances: utterances.to_vec(),
        result_sha256: result_digest(text, utterances)?,
    };
    let bytes = serde_json::to_vec(&entry).map_err(|_| "ASR cache result cannot be encoded")?;
    if bytes.len() as u64 > MAX_ENTRY_BYTES {
        return Err("ASR cache result exceeds the entry limit".into());
    }
    // Unique staging file + flush + atomic publish: simultaneous workers
    // cannot share a temp name or expose a half-written JSON entry.
    if let Err(error) = super::super::export::write_atomic(&key.path(root)?, &bytes) {
        // Another worker may have committed this identity while we staged it.
        // On Windows a simultaneous reader can prevent replacing that file;
        // its fully validated final result already fulfills the cache write.
        if load(root, key).is_none() {
            return Err(error);
        }
    }
    trim(root);
    Ok(())
}

pub(super) fn resolve<F>(
    root: &Path,
    key: &Key,
    provider: F,
) -> Result<(String, Vec<Utterance>), String>
where
    F: FnOnce() -> Result<(String, Vec<Utterance>), String>,
{
    if let Some(cached) = load(root, key) {
        return Ok(cached);
    }
    let (text, utterances) = provider()?;
    if !key.valid_result(&text, &utterances) {
        return Err("ASR final result is empty or has invalid timing".into());
    }
    if store(root, key, &text, &utterances).is_err() {
        // Optional cache I/O must not lose a successful, paid transcription.
        // Avoid exposing recording paths or provider response fragments.
        eprintln!("[transcription] chunk_cache write=unavailable");
    }
    Ok((text, utterances))
}

fn is_cache_name(name: &str) -> bool {
    let Some(stem) = name.strip_suffix(".json") else {
        return false;
    };
    let sha = stem.strip_prefix("v2-").unwrap_or(stem);
    sha.len() == 64 && sha.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn trim(root: &Path) {
    let Ok(entries) = fs::read_dir(root) else {
        return;
    };
    let mut entries = entries
        .filter_map(Result::ok)
        .filter_map(|entry| {
            if !is_cache_name(entry.file_name().to_str()?) {
                return None;
            }
            inspect(&entry.path())?;
            let metadata = entry.metadata().ok()?;
            if !metadata.is_file() {
                return None;
            }
            Some((metadata.modified().ok()?, entry.path()))
        })
        .collect::<Vec<_>>();
    entries.sort_by_key(|(modified, _)| *modified);
    let excess = entries.len().saturating_sub(MAX_ENTRIES);
    for (_, path) in entries.into_iter().take(excess) {
        let _ = fs::remove_file(path);
    }
}

mod probe;
pub(super) use probe::verify;
pub(super) mod ownership;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn isolated_filesystem_probe_covers_cache_recovery_and_isolation() {
        let dir =
            std::env::temp_dir().join(format!("companion-cache-probe-{}", uuid::Uuid::new_v4()));
        let report = verify(&dir).unwrap();
        assert_eq!(report["result"], "PASS_LOCAL_ASR_CACHE_ONLY");
        assert!(report["checks"].as_array().unwrap().len() >= 15);
        assert!(
            verify(&dir).is_err(),
            "Never reuse a supplied existing folder"
        );
        // Only this test's fresh UUID folder is removed.
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn parallel_publish_never_shares_staging_files_or_partial_results() {
        let dir =
            std::env::temp_dir().join(format!("companion-cache-parallel-{}", uuid::Uuid::new_v4()));
        fs::create_dir(&dir).unwrap();
        let key = Key::new(
            &[1, 2, 3, 4],
            Profile::from_configuration(&serde_json::json!({
                "provider": "test", "model": "test", "language": "auto",
            }))
            .unwrap(),
        )
        .unwrap();
        std::thread::scope(|scope| {
            for index in 0..8 {
                let root = &dir;
                let key = &key;
                scope.spawn(move || {
                    for _ in 0..8 {
                        store(root, key, &format!("Final {index}"), &[]).unwrap();
                        assert!(load(root, key).unwrap().0.starts_with("Final "));
                    }
                });
            }
        });
        assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn retention_preserves_unrelated_files_and_bounds_cache_entries() {
        let dir = std::env::temp_dir().join(format!(
            "companion-cache-retention-{}",
            uuid::Uuid::new_v4()
        ));
        fs::create_dir(&dir).unwrap();
        fs::write(dir.join("recording.json"), b"keep me").unwrap();
        for index in 0..MAX_ENTRIES + 3 {
            let key = Key::new(
                &index.to_le_bytes(),
                Profile::from_configuration(
                    &serde_json::json!({"provider":"test", "model":"test", "language":"auto"}),
                )
                .unwrap(),
            )
            .unwrap();
            let entry = Entry {
                key: key.clone(),
                text: "final".into(),
                utterances: vec![],
                result_sha256: result_digest("final", &[]).unwrap(),
            };
            fs::write(key.path(&dir).unwrap(), serde_json::to_vec(&entry).unwrap()).unwrap();
        }
        let unknown = dir.join(format!("{:064x}.json", 42));
        fs::write(&unknown, b"legacy-without-provable-identity").unwrap();
        trim(&dir);
        assert_eq!(fs::read(dir.join("recording.json")).unwrap(), b"keep me");
        assert_eq!(
            fs::read(&unknown).unwrap(),
            b"legacy-without-provable-identity"
        );
        assert_eq!(fs::read_dir(&dir).unwrap().count(), MAX_ENTRIES + 2);
        fs::remove_dir_all(dir).unwrap();
    }
}
