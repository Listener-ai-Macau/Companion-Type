//! Public file is the commit point; credential snapshots are immutable.
use super::{clear_persisted_secrets, CompanionProductSecrets, CompanionProductSettings, CredentialBlocks};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::{self, File, OpenOptions};
use std::io::Read;
use std::path::{Path, PathBuf};
use uuid::Uuid;

const FORMAT: u32 = 3;
const MAX_FILE_BYTES: u64 = 64 * 1024;

pub(super) trait Vault {
    fn read(&self, generation: Option<Uuid>) -> Result<Option<CompanionProductSecrets>, String>;
    fn write(&self, generation: Uuid, secrets: &CompanionProductSecrets) -> Result<(), String>;
    fn delete(&self, generation: Uuid) -> Result<(), String>;
    /// Only this product's legacy target; never the shared Denzic provider bundle.
    fn clear_legacy(&self, blocks: &CredentialBlocks) -> Result<(), String>;
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct ClearJournal {
    committed_body_sha256: String,
    previous_body_sha256: Option<String>,
    retired_generation: Option<Uuid>,
}

enum ClearState { None, Prepared, Committed(ClearJournal) }
fn digest(body: &[u8]) -> String { format!("{:x}", Sha256::digest(body)) }

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Record {
    #[serde(default)]
    settings_format_version: u32,
    #[serde(default)]
    credential_generation: Option<Uuid>,
    #[serde(flatten)]
    settings: CompanionProductSettings,
}

pub(super) struct Loaded {
    pub settings: CompanionProductSettings,
    pub warning: Option<String>,
    pub configured: bool,
    pub recovered: bool,
    generation: Option<Uuid>,
}

pub(super) struct Store<'a> {
    pub path: &'a Path,
    pub vault: Option<&'a dyn Vault>,
}

impl Store<'_> {
    fn side(&self, suffix: &str) -> PathBuf {
        let mut name = self.path.as_os_str().to_os_string();
        name.push(suffix);
        PathBuf::from(name)
    }

    fn record(&self, path: &Path) -> Result<Option<Loaded>, String> {
        let mut file = match File::open(path) {
            Ok(file) => file,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(_) => return Err("无法读取设置文件；原文件已保留。".into()),
        };
        let mut raw = Vec::new();
        Read::by_ref(&mut file)
            .take(MAX_FILE_BYTES + 1)
            .read_to_end(&mut raw)
            .map_err(|_| "无法完整读取设置文件；原文件已保留。")?;
        if raw.len() as u64 > MAX_FILE_BYTES {
            return Err("设置文件过大；原文件已保留。".into());
        }
        let record: Record =
            serde_json::from_slice(&raw).map_err(|_| "设置文件损坏；原文件已保留。")?;
        if !matches!(record.settings_format_version, 0 | 2 | FORMAT) {
            return Err("设置来自更新版本，当前软件不能覆盖它。".into());
        }
        let mut settings = record.settings;
        match (
            self.vault,
            record.settings_format_version,
            record.credential_generation,
        ) {
            (Some(vault), 2 | FORMAT, Some(generation)) => {
                let secrets = vault
                    .read(Some(generation))?
                    .ok_or("设置对应的安全凭据不可用；不能用旧凭据替代。")?;
                secrets.apply_to(&mut settings);
            }
            (Some(_), 2 | FORMAT, None) => return Err("设置缺少安全凭据身份；原文件已保留。".into()),
            (Some(vault), 0, None) => {
                if let Some(secrets) = vault.read(None)? {
                    // Explicit legacy JSON values take precedence during migration.
                    if settings.volc_app_key.is_empty() {
                        settings.volc_app_key = secrets.volc_app_key;
                    }
                    if settings.volc_access_key.is_empty() {
                        settings.volc_access_key = secrets.volc_access_key;
                    }
                    if settings.openai_asr_api_key.is_empty() {
                        settings.openai_asr_api_key = secrets.openai_asr_api_key;
                    }
                    if settings.deepseek_api_key.is_empty() {
                        settings.deepseek_api_key = secrets.deepseek_api_key;
                    }
                }
            }
            (None, _, Some(_)) => return Err("这份设置需要原系统的安全凭据；不能覆盖。".into()),
            (_, 0, Some(_)) => return Err("设置格式与凭据身份不一致。".into()),
            _ => {}
        }
        Ok(Some(Loaded {
            settings,
            warning: None,
            configured: true,
            recovered: false,
            generation: record.credential_generation,
        }))
    }

    pub fn load(&self) -> Result<Loaded, String> {
        // Existing stores share the writer's OS lock. No lock file is created
        // by a read-only invocation or by a brand-new profile.
        let lock = match File::open(self.side(".lock")) {
            Ok(file) => {
                file.try_lock_shared()
                    .map_err(|_| "正在保存设置，请稍后重试。")?;
                Some(file)
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
            Err(_) => return Err("无法安全读取设置，请稍后重试。".into()),
        };
        let result = self.load_unlocked();
        drop(lock);
        result
    }

    fn load_unlocked(&self) -> Result<Loaded, String> {
        match self.clear_state()? {
            ClearState::Committed(_) => {
                // Do not fall back to a pre-clear backup while cleanup is pending.
                let mut loaded = self.record(self.path)?.ok_or("清空密钥后的设置不可用；不能恢复旧凭据。")?;
                loaded.warning = Some("密钥已停止使用，但旧凭据清理尚未完成；请再次保存设置重试。".into());
                return Ok(loaded);
            }
            ClearState::None | ClearState::Prepared => {}
        }
        match self.record(self.path) {
            Ok(Some(settings)) => Ok(settings),
            Ok(None) => match self.record(&self.side(".bak"))? {
                Some(mut settings) => {
                    settings.recovered = true;
                    settings.warning = Some(
                        "设置文件缺失，正在使用上次保存的备份。再次保存会恢复设置文件。".into(),
                    );
                    Ok(settings)
                }
                None => {
                    let mut settings = CompanionProductSettings::default();
                    if let Some(vault) = self.vault {
                        if let Some(secrets) = vault.read(None)? {
                            secrets.apply_to(&mut settings);
                        }
                    }
                    Ok(Loaded {
                        settings,
                        warning: None,
                        configured: false,
                        recovered: false,
                        generation: None,
                    })
                }
            },
            Err(error) => {
                // Never downgrade a future format or resurrect missing/revoked credentials.
                if !error.starts_with("设置文件损坏") && !error.starts_with("设置文件过大")
                {
                    return Err(error);
                }
                match self.record(&self.side(".bak")) {
                    Ok(Some(mut settings)) => {
                        settings.recovered = true;
                        settings.warning = Some(
                            "设置文件损坏，正在使用上次保存的备份。保存时会保留损坏原件。".into(),
                        );
                        Ok(settings)
                    }
                    _ => {
                        Err("设置文件损坏且没有有效备份；原文件已保留，请先恢复或修复设置。".into())
                    }
                }
            }
        }
    }

    fn encode(
        &self,
        settings: &CompanionProductSettings,
        generation: Option<Uuid>,
    ) -> Result<Vec<u8>, String> {
        let mut persisted = settings.clone();
        if self.vault.is_some() {
            clear_persisted_secrets(&mut persisted);
        }
        let body = serde_json::to_vec_pretty(&Record {
            settings_format_version: FORMAT,
            credential_generation: generation,
            settings: persisted,
        })
        .map_err(|_| "无法编码设置；原配置未覆盖。")?;
        if body.len() as u64 > MAX_FILE_BYTES {
            return Err("设置内容过大，未保存。".into());
        }
        Ok(body)
    }

    fn snapshot(
        &self,
        settings: &CompanionProductSettings,
    ) -> Result<(Option<Uuid>, Vec<u8>), String> {
        let generation = self.vault.map(|_| Uuid::new_v4());
        let body = self.encode(settings, generation)?;
        if let (Some(vault), Some(generation)) = (self.vault, generation) {
            // Track only generations owned by this transaction; never enumerate
            // the user's vault. The journal survives either publication failing.
            self.track_pending(generation)?;
            vault.write(
                generation,
                &CompanionProductSecrets::from_settings(settings),
            )?;
        }
        Ok((generation, body))
    }

    fn pending_generations(&self) -> Result<Vec<Uuid>, String> {
        let pending = self.side(".pending");
        let raw = match fs::read_to_string(&pending) {
            Ok(raw) => raw,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
            Err(_) => return Err("上次设置保存尚未恢复；请稍后重试。".into()),
        };
        let generations: Vec<Uuid> =
            serde_json::from_str(&raw).map_err(|_| "设置恢复记录损坏；原配置未覆盖。")?;
        if generations.len() > 2 {
            return Err("设置恢复记录无效；原配置未覆盖。".into());
        }
        Ok(generations)
    }

    fn track_pending(&self, generation: Uuid) -> Result<(), String> {
        let mut generations = self.pending_generations()?;
        if !generations.contains(&generation) {
            generations.push(generation);
        }
        if generations.len() > 2 {
            return Err("上次设置保存尚未恢复，未覆盖原配置。".into());
        }
        let body =
            serde_json::to_vec(&generations).map_err(|_| "无法记录设置保存状态，未覆盖原配置。")?;
        atomic_write(&self.side(".pending"), &body)
    }

    fn settle_pending(&self, active: Option<Uuid>, backup: Option<Uuid>) -> Result<(), String> {
        for generation in self.pending_generations()? {
            if Some(generation) != active && Some(generation) != backup {
                if let Some(vault) = self.vault {
                    vault.delete(generation)?;
                }
            }
        }
        match fs::remove_file(self.side(".pending")) {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(_) => Err("无法完成上次设置保存的清理，请稍后重试。".into()),
        }
    }

    pub fn update(
        &self,
        merge: impl FnOnce(CompanionProductSettings) -> CompanionProductSettings,
    ) -> Result<CompanionProductSettings, String> {
        self.update_after_commit(merge, |_| {})
    }

    pub fn update_after_commit(
        &self,
        merge: impl FnOnce(CompanionProductSettings) -> CompanionProductSettings,
        after_commit: impl FnOnce(&CompanionProductSettings),
    ) -> Result<CompanionProductSettings, String> {
        if let Some(parent) = self.path.parent().filter(|p| !p.as_os_str().is_empty()) {
            fs::create_dir_all(parent).map_err(|_| "无法创建设置目录，未保存。")?;
        }
        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(self.side(".lock"))
            .map_err(|_| "无法锁定设置文件，未保存。")?;
        lock.try_lock()
            .map_err(|_| "另一项设置保存正在进行，请稍后重试。")?;
        match self.clear_state()? {
            ClearState::Committed(journal) => self.finish_clear(&journal)?,
            ClearState::Prepared => fs::remove_file(self.side(".credential-clear"))
                .map_err(|_| "无法恢复上次密钥清理，请稍后重试。")?,
            ClearState::None => {}
        }
        let previous = self.load_unlocked()?; // Corrupt/future files cannot become defaults and be overwritten.
        if previous.recovered {
            if self.path.exists() {
                self.preserve_corrupt(self.path)?;
            }
            // Repair only during an explicit save, after preserving the bad file.
            // Restore the already-validated old pair before creating any new
            // snapshot, so a failed save still has a usable old configuration.
            let backup =
                fs::read(self.side(".bak")).map_err(|_| "无法恢复有效设置备份，未保存。")?;
            atomic_write(self.path, &backup)?;
        }
        // Reclaim a previous interrupted save before starting a new one.
        let old_backup_generation = match self.record(&self.side(".bak")) {
            Ok(record) => record.and_then(|r| r.generation),
            Err(_) => {
                self.preserve_corrupt(&self.side(".bak"))?;
                None
            }
        };
        self.settle_pending(previous.generation, old_backup_generation)?;
        if let Some(retired) = old_backup_generation.filter(|id| Some(*id) != previous.generation) {
            self.track_pending(retired)?;
        }
        let old_generation;
        if let Some(generation) = previous.generation {
            old_generation = Some(generation);
            atomic_write(
                &self.side(".bak"),
                &self.encode(&previous.settings, old_generation)?,
            )?;
        } else {
            let (generation, body) = self.snapshot(&previous.settings)?;
            old_generation = generation;
            atomic_write(&self.side(".bak"), &body)?;
        }
        self.settle_pending(previous.generation, old_generation)?;
        let settings = merge(previous.settings);
        let (generation, body) = self.snapshot(&settings)?;
        let clear = if settings.credential_blocks.any() {
            let previous_body_sha256 = match fs::read(self.path) {
                Ok(bytes) => Some(digest(&bytes)),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
                Err(_) => return Err("无法确认清空前的配置，未保存。".into()),
            };
            let journal = ClearJournal { committed_body_sha256: digest(&body), previous_body_sha256,
                retired_generation: old_generation };
            let encoded = serde_json::to_vec(&journal).map_err(|_| "无法记录密钥清理状态，未保存。")?;
            atomic_write(&self.side(".credential-clear"), &encoded)?;
            Some(journal)
        } else { None };
        atomic_write(self.path, &body)?; // Sole publication/commit point.
        let published = self
            .record(self.path)?
            .ok_or("设置保存结果无法确认，请重新加载。")?;
        if published.settings != settings || published.generation != generation {
            return Err("设置保存结果无法确认，请重新加载。".into());
        }
        // Commit succeeded. Cleanup failure must not misreport it as an aborted
        // save or remove a snapshot referenced by either public file.
        if let Some(journal) = clear {
            // A cleanup failure is a committed save with a visible warning and
            // durable retry record, never a false claim that the old key survived.
            let _ = self.finish_clear(&journal);
        } else {
            let _ = self.settle_pending(generation, old_generation);
        }
        // Keep the writer lock until the process has adopted this committed
        // configuration. A later save cannot apply ahead of an earlier one.
        after_commit(&settings);
        Ok(settings)
    }

    fn clear_state(&self) -> Result<ClearState, String> {
        let file = match File::open(self.side(".credential-clear")) {
            Ok(file) => file,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(ClearState::None),
            Err(_) => return Err("无法读取密钥清理记录；不能恢复旧凭据。".into()),
        };
        let mut raw = Vec::new();
        file.take(4097).read_to_end(&mut raw).map_err(|_| "无法读取密钥清理记录；不能恢复旧凭据。")?;
        if raw.len() > 4096 { return Err("密钥清理记录无效；不能恢复旧凭据。".into()); }
        let journal: ClearJournal = serde_json::from_slice(&raw)
            .map_err(|_| "密钥清理记录损坏；不能恢复旧凭据。")?;
        let valid_hash = |s: &str| s.len() == 64 && s.bytes().all(|b| b.is_ascii_hexdigit());
        if !valid_hash(&journal.committed_body_sha256)
            || journal.previous_body_sha256.as_deref().is_some_and(|s| !valid_hash(s)) {
            return Err("密钥清理记录无效；不能恢复旧凭据。".into());
        }
        let mut body = Vec::new();
        let actual = match File::open(self.path) {
            Ok(file) => {
                file.take(MAX_FILE_BYTES + 1).read_to_end(&mut body)
                    .map_err(|_| "无法确认密钥清理状态；不能恢复旧凭据。")?;
                Some(digest(&body))
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => None,
            Err(_) => return Err("无法确认密钥清理状态；不能恢复旧凭据。".into()),
        };
        if actual.as_deref() == Some(journal.committed_body_sha256.as_str()) {
            Ok(ClearState::Committed(journal))
        } else if actual == journal.previous_body_sha256 {
            Ok(ClearState::Prepared)
        } else {
            Err("密钥清理状态尚未确认；不能从旧备份恢复凭据，请保留文件并修复设置。".into())
        }
    }

    fn finish_clear(&self, journal: &ClearJournal) -> Result<(), String> {
        let body = fs::read(self.path).map_err(|_| "无法完成旧凭据清理，请再次保存重试。")?;
        if digest(&body) != journal.committed_body_sha256 {
            return Err("密钥清理身份不匹配；不能恢复旧凭据。".into());
        }
        let current = self.record(self.path)?.ok_or("密钥清理后的配置不可用。")?;
        if !current.settings.credential_blocks.any() {
            return Err("密钥清理记录与配置不一致。".into());
        }
        // Both recovery files reference the cleared bundle before revocation.
        // If a crash interrupts this, the journal blocks old backup recovery.
        atomic_write(&self.side(".bak"), &body)?;
        if let Some(vault) = self.vault {
            vault.clear_legacy(&current.settings.credential_blocks)?;
            if let Some(retired) = journal.retired_generation.filter(|id| Some(*id) != current.generation) {
                vault.delete(retired)?;
            }
        }
        self.settle_pending(current.generation, current.generation)?;
        fs::remove_file(self.side(".credential-clear"))
            .map_err(|_| "无法完成密钥清理记录的删除，请再次保存重试。".into())
    }

    fn preserve_corrupt(&self, source: &Path) -> Result<(), String> {
        let quarantine = self.side(&format!(".corrupt-{}", Uuid::new_v4()));
        let result = (|| {
            let mut input = File::open(source).map_err(|_| "无法保留损坏的设置原件，未保存。")?;
            let mut output = OpenOptions::new()
                .create_new(true)
                .write(true)
                .open(&quarantine)
                .map_err(|_| "无法保留损坏的设置原件，未保存。")?;
            std::io::copy(&mut input, &mut output)
                .and_then(|_| output.sync_all())
                .map_err(|_| "无法完整保留损坏的设置原件，未保存。")?;
            Ok(())
        })();
        if result.is_err() {
            let _ = fs::remove_file(quarantine);
        }
        result
    }
}

fn atomic_write(destination: &Path, bytes: &[u8]) -> Result<(), String> {
    super::super::export::write_atomic(destination, bytes).map(|_| ())
        .map_err(|_| "设置原子保存失败，原文件未覆盖。".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        cell::{Cell, RefCell},
        collections::HashMap,
    };

    #[derive(Default)]
    struct MemoryVault {
        entries: RefCell<HashMap<Option<Uuid>, CompanionProductSecrets>>,
        fail_write: Cell<bool>,
        fail_delete: Cell<bool>,
    }
    impl Vault for MemoryVault {
        fn read(&self, id: Option<Uuid>) -> Result<Option<CompanionProductSecrets>, String> {
            Ok(self.entries.borrow().get(&id).cloned())
        }
        fn write(&self, id: Uuid, secrets: &CompanionProductSecrets) -> Result<(), String> {
            if self.fail_write.get() {
                return Err("injected vault write failure".into());
            }
            assert!(self
                .entries
                .borrow_mut()
                .insert(Some(id), secrets.clone())
                .is_none());
            Ok(())
        }
        fn delete(&self, id: Uuid) -> Result<(), String> {
            if self.fail_delete.get() { return Err("injected vault delete failure".into()); }
            self.entries.borrow_mut().remove(&Some(id));
            Ok(())
        }
        fn clear_legacy(&self, blocks: &CredentialBlocks) -> Result<(), String> {
            if let Some(secrets) = self.entries.borrow_mut().get_mut(&None) {
                if blocks.volc_app_key { secrets.volc_app_key.clear(); }
                if blocks.volc_access_key { secrets.volc_access_key.clear(); }
                if blocks.openai_asr_api_key { secrets.openai_asr_api_key.clear(); }
                if blocks.deepseek_api_key { secrets.deepseek_api_key.clear(); }
            }
            Ok(())
        }
    }
    struct Profile(PathBuf);
    impl Profile {
        fn new() -> Self {
            let path =
                std::env::temp_dir().join(format!("companion-settings-storage-{}", Uuid::new_v4()));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
        fn path(&self) -> PathBuf {
            self.0.join("settings.json")
        }
    }
    impl Drop for Profile {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn clear_patch(kind: super::super::CredentialKind) -> super::super::CompanionProductSettingsPatch {
        super::super::CompanionProductSettingsPatch { settings: CompanionProductSettings::default(), clear_credentials: vec![kind] }
    }

    #[test]
    fn clear_revokes_current_backup_and_product_legacy_but_keeps_other_keys() {
        let profile = Profile::new(); let path = profile.path(); let vault = MemoryVault::default();
        let store = Store { path: &path, vault: Some(&vault) };
        store.update(|mut s| { s.deepseek_api_key = "remove-private".into(); s.openai_asr_api_key = "keep-private".into(); s }).unwrap();
        let retired = store.load().unwrap().generation.unwrap();
        vault.entries.borrow_mut().insert(None, CompanionProductSecrets {
            deepseek_api_key: "legacy-private".into(), openai_asr_api_key: "other-legacy-private".into(), ..Default::default() });
        let patch = clear_patch(super::super::CredentialKind::DeepseekApiKey);
        patch.validate().unwrap();
        let cleared = store.update(|s| patch.merge(s)).unwrap();
        assert!(cleared.deepseek_api_key.is_empty() && cleared.credential_blocks.deepseek_api_key);
        assert_eq!(cleared.openai_asr_api_key, "keep-private");
        assert!(!vault.entries.borrow().contains_key(&Some(retired)));
        let legacy = vault.entries.borrow().get(&None).unwrap().clone();
        assert!(legacy.deepseek_api_key.is_empty()); assert_eq!(legacy.openai_asr_api_key, "other-legacy-private");
        assert_eq!(store.record(&store.side(".bak")).unwrap().unwrap().settings, cleared);
        assert!(!store.side(".credential-clear").exists());
        fs::write(&path, b"{broken after clear").unwrap();
        assert_eq!(store.load().unwrap().settings, cleared, "backup recovery cannot resurrect a cleared key");
    }

    #[test]
    fn failed_clear_vault_write_leaves_active_settings_and_callback_unchanged() {
        let profile = Profile::new(); let path = profile.path(); let vault = MemoryVault::default();
        let store = Store { path: &path, vault: Some(&vault) };
        let old = store.update(|mut s| { s.deepseek_api_key = "old-private".into(); s }).unwrap();
        let original = fs::read(&path).unwrap(); let adopted = Cell::new(false);
        vault.fail_write.set(true);
        assert!(store.update_after_commit(|s| clear_patch(super::super::CredentialKind::DeepseekApiKey).merge(s), |_| adopted.set(true)).is_err());
        assert!(!adopted.get()); assert_eq!(store.load().unwrap().settings, old); assert_eq!(fs::read(&path).unwrap(), original);
        vault.fail_write.set(false);
        let clear = store.update(|s| clear_patch(super::super::CredentialKind::DeepseekApiKey).merge(s)).unwrap();
        assert!(clear.deepseek_api_key.is_empty());
    }

    #[test]
    fn committed_clear_cleanup_failure_is_visible_retryable_and_fail_closed() {
        let profile = Profile::new(); let path = profile.path(); let vault = MemoryVault::default();
        let store = Store { path: &path, vault: Some(&vault) };
        store.update(|mut s| { s.deepseek_api_key = "old-private".into(); s }).unwrap();
        fs::copy(&path, store.side(".bak")).unwrap();
        vault.fail_delete.set(true);
        let adopted = Cell::new(false);
        let cleared = store.update_after_commit(|s| clear_patch(super::super::CredentialKind::DeepseekApiKey).merge(s), |_| adopted.set(true)).unwrap();
        assert!(adopted.get()); assert!(store.side(".credential-clear").exists());
        assert!(store.load().unwrap().warning.is_some());
        let committed = fs::read(&path).unwrap();
        fs::write(&path, b"{interrupted cleanup").unwrap();
        assert!(store.load().is_err()); assert!(store.update(|s| s).is_err());
        fs::write(&path, &committed).unwrap(); vault.fail_delete.set(false);
        store.update(|s| s).unwrap();
        assert_eq!(store.load().unwrap().settings, cleared);
        assert!(store.load().unwrap().warning.is_none());
        assert!(!store.side(".credential-clear").exists());
    }

    #[test]
    fn format_two_profiles_load_and_new_clear_profiles_refuse_old_readers() {
        let profile = Profile::new(); let path = profile.path(); let vault = MemoryVault::default();
        let store = Store { path: &path, vault: Some(&vault) };
        let old = store.update(|mut s| { s.deepseek_api_key = "old-private".into(); s }).unwrap();
        let mut record: serde_json::Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        record["settingsFormatVersion"] = serde_json::json!(2); record.as_object_mut().unwrap().remove("credentialBlocks");
        fs::write(&path, serde_json::to_vec(&record).unwrap()).unwrap();
        assert_eq!(store.load().unwrap().settings, old);
        store.update(|s| clear_patch(super::super::CredentialKind::DeepseekApiKey).merge(s)).unwrap();
        assert_eq!(serde_json::from_slice::<serde_json::Value>(&fs::read(&path).unwrap()).unwrap()["settingsFormatVersion"], 3);
    }

    #[test]
    fn vault_failure_keeps_public_file_and_old_secret_together() {
        let profile = Profile::new();
        let path = profile.path();
        let vault = MemoryVault::default();
        let store = Store {
            path: &path,
            vault: Some(&vault),
        };
        store
            .update(|mut settings| {
                settings.deepseek_api_key = "old-private".into();
                settings
            })
            .unwrap();
        let original = fs::read(&path).unwrap();
        vault.fail_write.set(true);
        assert!(store
            .update(|mut settings| {
                settings.deepseek_model = "new-model".into();
                settings.deepseek_api_key = "new-private".into();
                settings
            })
            .is_err());
        assert_eq!(fs::read(&path).unwrap(), original);
        let reloaded = store.load().unwrap().settings;
        assert_eq!(reloaded.deepseek_api_key, "old-private");
        assert_eq!(
            reloaded.deepseek_model,
            CompanionProductSettings::default().deepseek_model
        );
        vault.fail_write.set(false);
        store
            .update(|mut settings| {
                settings.ble_compress = true;
                settings
            })
            .unwrap();
        assert_eq!(vault.entries.borrow().len(), 2);
        for file in [&path, &store.side(".bak")] {
            assert!(!fs::read_to_string(file).unwrap().contains("private"));
        }
    }

    #[test]
    fn uncommitted_vault_snapshot_is_not_used_after_restart() {
        let profile = Profile::new();
        let path = profile.path();
        let vault = MemoryVault::default();
        let store = Store {
            path: &path,
            vault: Some(&vault),
        };
        let old = store
            .update(|mut settings| {
                settings.openai_asr_api_key = "old-private".into();
                settings
            })
            .unwrap();
        let mut new = old.clone();
        new.openai_asr_api_key = "uncommitted-private".into();
        let (orphan, _) = store.snapshot(&new).unwrap();
        let restarted = Store {
            path: &path,
            vault: Some(&vault),
        };
        assert_eq!(restarted.load().unwrap().settings, old);
        assert!(
            store.side(".pending").exists(),
            "reading must not write or delete a recovery journal"
        );
        restarted
            .update(|mut settings| {
                settings.ble_compress = true;
                settings
            })
            .unwrap();
        assert!(!vault.entries.borrow().contains_key(&orphan));
        assert!(!store.side(".pending").exists());
    }

    #[test]
    fn damaged_file_recovers_backup_only_on_explicit_save_and_preserves_original() {
        let profile = Profile::new();
        let path = profile.path();
        let vault = MemoryVault::default();
        let store = Store {
            path: &path,
            vault: Some(&vault),
        };
        let old = store
            .update(|mut s| {
                s.deepseek_api_key = "backup-private".into();
                s
            })
            .unwrap();
        store
            .update(|mut s| {
                s.default_meeting_mode = "onlineLive".into();
                s
            })
            .unwrap();
        let bad = b"{interrupted settings";
        fs::write(&path, bad).unwrap();
        let reloaded = store.load().unwrap();
        assert!(reloaded.recovered && reloaded.warning.is_some());
        assert_eq!(reloaded.settings, old);
        assert_eq!(
            fs::read(&path).unwrap(),
            bad,
            "read-only recovery cannot overwrite the damaged file"
        );
        store
            .update(|mut s| {
                s.ble_compress = true;
                s
            })
            .unwrap();
        let files: Vec<_> = fs::read_dir(&profile.0)
            .unwrap()
            .map(|e| e.unwrap().path())
            .filter(|p| {
                p.file_name()
                    .unwrap()
                    .to_string_lossy()
                    .contains(".corrupt-")
            })
            .collect();
        assert_eq!(files.len(), 1);
        assert_eq!(fs::read(&files[0]).unwrap(), bad);
        let saved = store.load().unwrap();
        assert!(!saved.recovered);
        assert!(saved.settings.ble_compress);
        assert_eq!(saved.settings.deepseek_api_key, old.deepseek_api_key);
    }

    #[test]
    fn legacy_backup_migration_preserves_existing_key_and_removes_plaintext_from_both_files() {
        let profile = Profile::new();
        let path = profile.path();
        let vault = MemoryVault::default();
        let store = Store {
            path: &path,
            vault: Some(&vault),
        };
        let mut legacy = CompanionProductSettings::default();
        legacy.volc_app_key = "legacy-private".into();
        fs::write(store.side(".bak"), serde_json::to_vec(&legacy).unwrap()).unwrap();
        fs::write(&path, b"{broken").unwrap();
        let saved = store
            .update(|mut s| {
                s.ble_compress = true;
                s
            })
            .unwrap();
        assert_eq!(saved.volc_app_key, legacy.volc_app_key);
        for file in [&path, &store.side(".bak")] {
            let content = fs::read_to_string(file).unwrap();
            assert!(!content.contains("legacy-private"));
            assert_eq!(
                serde_json::from_str::<Record>(&content)
                    .unwrap()
                    .settings_format_version,
                FORMAT
            );
        }
    }

    #[test]
    fn missing_current_credential_does_not_resurrect_backup_or_legacy_keys() {
        let profile = Profile::new();
        let path = profile.path();
        let vault = MemoryVault::default();
        let store = Store {
            path: &path,
            vault: Some(&vault),
        };
        store
            .update(|mut s| {
                s.deepseek_api_key = "old-private".into();
                s
            })
            .unwrap();
        store
            .update(|mut s| {
                s.deepseek_api_key = "current-private".into();
                s
            })
            .unwrap();
        let original = fs::read(&path).unwrap();
        let current: Record = serde_json::from_slice(&original).unwrap();
        vault
            .entries
            .borrow_mut()
            .remove(&current.credential_generation);
        vault.entries.borrow_mut().insert(
            None,
            CompanionProductSecrets {
                deepseek_api_key: "legacy-private".into(),
                ..Default::default()
            },
        );
        assert!(store.load().err().unwrap().contains("凭据不可用"));
        assert!(store.update(|s| s).is_err());
        assert_eq!(fs::read(&path).unwrap(), original);
    }

    #[test]
    fn corrupt_unbacked_future_and_oversized_profiles_cannot_be_overwritten_with_defaults() {
        let profile = Profile::new();
        let path = profile.path();
        let store = Store {
            path: &path,
            vault: None,
        };
        let mut future = serde_json::to_value(CompanionProductSettings::default()).unwrap();
        future["settingsFormatVersion"] = serde_json::json!(99);
        for bad in [
            b"{broken".to_vec(),
            serde_json::to_vec(&future).unwrap(),
            vec![b'X'; MAX_FILE_BYTES as usize + 1],
        ] {
            fs::write(&path, &bad).unwrap();
            assert!(store.load().is_err());
            assert!(store.update(|s| s).is_err());
            assert_eq!(fs::read(&path).unwrap(), bad);
            assert!(!store.side(".bak").exists());
        }
    }

    #[test]
    fn lock_conflict_prevents_read_modify_write_and_later_patch_preserves_previous_changes() {
        let profile = Profile::new();
        let path = profile.path();
        let store = Store {
            path: &path,
            vault: None,
        };
        store
            .update(|mut s| {
                s.deepseek_api_key = "retained-private".into();
                s.default_meeting_mode = "onlineLive".into();
                s
            })
            .unwrap();
        let original = fs::read(&path).unwrap();
        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .open(store.side(".lock"))
            .unwrap();
        lock.try_lock().unwrap();
        assert!(store.load().is_err());
        assert!(store
            .update(|_| panic!("merge must not run without the writer lock"))
            .is_err());
        assert_eq!(fs::read(&path).unwrap(), original);
        drop(lock);
        let saved = store
            .update(|mut s| {
                s.ble_compress = true;
                s
            })
            .unwrap();
        assert_eq!(saved.default_meeting_mode, "onlineLive");
        assert_eq!(saved.deepseek_api_key, "retained-private");
    }

    #[test]
    fn post_commit_application_holds_the_writer_lock_and_never_runs_on_a_failed_save() {
        let profile = Profile::new();
        let path = profile.path();
        let store = Store {
            path: &path,
            vault: None,
        };
        let applied = Cell::new(false);
        store
            .update_after_commit(
                |mut s| {
                    s.ble_compress = true;
                    s
                },
                |settings| {
                    assert!(settings.ble_compress);
                    let persisted: Record =
                        serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
                    assert!(persisted.settings.ble_compress, "apply follows publication");
                    assert!(store
                        .update(|_| panic!("another merge cannot interleave application"))
                        .is_err());
                    applied.set(true);
                },
            )
            .unwrap();
        assert!(applied.get());
        applied.set(false);
        let mut future = serde_json::to_value(CompanionProductSettings::default()).unwrap();
        future["settingsFormatVersion"] = serde_json::json!(99);
        fs::write(&path, serde_json::to_vec(&future).unwrap()).unwrap();
        assert!(store
            .update_after_commit(|s| s, |_| applied.set(true))
            .is_err());
        assert!(!applied.get());
    }

    #[cfg(windows)]
    #[test]
    fn windows_destination_without_delete_sharing_rejects_replace_but_keeps_old_configuration() {
        use std::os::windows::fs::OpenOptionsExt;
        let profile = Profile::new();
        let path = profile.path();
        let vault = MemoryVault::default();
        let store = Store {
            path: &path,
            vault: Some(&vault),
        };
        let old = store
            .update(|mut s| {
                s.deepseek_api_key = "old-private".into();
                s
            })
            .unwrap();
        let original = fs::read(&path).unwrap();
        let held = OpenOptions::new()
            .read(true)
            .share_mode(1 | 2)
            .open(&path)
            .unwrap();
        assert!(store
            .update(|mut s| {
                s.deepseek_api_key = "new-private".into();
                s.ble_compress = true;
                s
            })
            .is_err());
        assert_eq!(fs::read(&path).unwrap(), original);
        assert_eq!(store.load().unwrap().settings, old);
        drop(held);
        store
            .update(|mut s| {
                s.ble_compress = true;
                s
            })
            .unwrap();
        assert_eq!(
            vault.entries.borrow().len(),
            2,
            "retry must reclaim the failed save's snapshot"
        );
    }
}
