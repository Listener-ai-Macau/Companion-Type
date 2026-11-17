//! Real Win32 file replacement and credential checks in a fresh isolated folder.
use super::{
    storage::{Store, Vault},
    windows_vault::WindowsVault,
    CompanionProductSecrets, CompanionProductSettings,
};
use std::os::windows::fs::OpenOptionsExt;
use std::{
    cell::{Cell, RefCell},
    fs::{self, OpenOptions},
    path::{Path, PathBuf},
};
use uuid::Uuid;

struct ProbeVault {
    vault: WindowsVault,
    owned: RefCell<Vec<Uuid>>,
    cleaned: Cell<bool>,
}
impl Vault for ProbeVault {
    fn read(&self, id: Option<Uuid>) -> Result<Option<CompanionProductSecrets>, String> {
        self.vault.read(id)
    }
    fn write(&self, id: Uuid, secrets: &CompanionProductSecrets) -> Result<(), String> {
        self.vault.write(id, secrets)?;
        self.owned.borrow_mut().push(id);
        Ok(())
    }
    fn delete(&self, id: Uuid) -> Result<(), String> {
        self.vault.delete(id)
    }
    fn clear_legacy(&self, blocks: &super::CredentialBlocks) -> Result<(), String> {
        self.vault.clear_legacy(blocks)
    }
}
impl ProbeVault {
    fn cleanup(&self) -> Result<(), String> {
        for id in self.owned.borrow().iter() {
            self.vault.delete(*id)?;
        }
        self.vault.delete_legacy()?;
        self.cleaned.set(true);
        Ok(())
    }
}
impl Drop for ProbeVault {
    fn drop(&mut self) {
        if !self.cleaned.get() {
            let _ = self.cleanup();
        }
    }
}
fn side(path: &Path, suffix: &str) -> PathBuf {
    let mut name = path.as_os_str().to_os_string();
    name.push(suffix);
    PathBuf::from(name)
}
fn ensure(condition: bool, check: &str) -> Result<(), String> {
    if condition {
        Ok(())
    } else {
        Err(format!("isolated settings check failed: {check}"))
    }
}
fn io<T>(result: std::io::Result<T>) -> Result<T, String> {
    result.map_err(|_| "isolated settings check file operation failed".into())
}

pub(super) fn run(output: &Path) -> Result<serde_json::Value, String> {
    // Refuse an existing folder: no user files, configuration, credentials,
    // microphone, BLE, service request, or ST-Link access is part of this probe.
    fs::create_dir(output)
        .map_err(|_| "settings check requires a new empty output folder".to_string())?;
    let vault = ProbeVault {
        vault: WindowsVault {
            base: format!("Companion.Type.settings-probe.{}", Uuid::new_v4()),
        },
        owned: RefCell::new(Vec::new()),
        cleaned: Cell::new(false),
    };
    let result = (|| {
        let path = output.join("settings.json");
        let store = Store {
            path: &path,
            vault: Some(&vault),
        };
        ensure(
            !store.load()?.configured && !path.exists(),
            "new profile read-only",
        )?;
        let old = store.update(|mut s| {
            s.openai_asr_api_key = "probe-private-old".into();
            s.asr_provider = "openai-compatible".into();
            s.default_meeting_mode = "onlineLive".into();
            s
        })?;
        ensure(store.load()?.settings == old, "credential/file round trip")?;
        let original = io(fs::read(&path))?;
        let held = io(OpenOptions::new().read(true).share_mode(1 | 2).open(&path))?;
        ensure(
            store
                .update(|mut s| {
                    s.openai_asr_api_key = "probe-private-new".into();
                    s.openai_asr_model = "probe-new-model".into();
                    s
                })
                .is_err(),
            "occupied destination rejects publication",
        )?;
        ensure(
            io(fs::read(&path))? == original && store.load()?.settings == old,
            "failed publication retains old pair",
        )?;
        drop(held);
        let new = store.update(|mut s| {
            s.openai_asr_api_key = "probe-private-new".into();
            s.openai_asr_model = "probe-new-model".into();
            s
        })?;
        ensure(
            store.load()?.settings == new && !side(&path, ".pending").exists(),
            "retry publishes complete new pair",
        )?;
        for file in [&path, &side(&path, ".bak")] {
            ensure(
                !io(fs::read_to_string(file))?.contains("probe-private"),
                "public and backup files contain no key values",
            )?;
        }
        let lock = io(OpenOptions::new()
            .read(true)
            .write(true)
            .open(side(&path, ".lock")))?;
        lock.try_lock()
            .map_err(|_| "isolated settings check lock acquisition failed")?;
        ensure(
            store.load().is_err() && store.update(|s| s).is_err(),
            "OS writer lock excludes concurrent access",
        )?;
        drop(lock);
        let displaced = output.join("displaced.json");
        io(fs::rename(&path, &displaced))?;
        let recovered = store.load()?;
        ensure(
            recovered.recovered
                && recovered.warning.is_some()
                && recovered.settings == old
                && !path.exists(),
            "missing file uses backup without writing",
        )?;
        io(fs::rename(displaced, &path))?;
        let bad = b"{interrupted settings";
        io(fs::write(&path, bad))?;
        let recovered = store.load()?;
        ensure(
            recovered.recovered
                && recovered.warning.is_some()
                && recovered.settings == old
                && io(fs::read(&path))? == bad,
            "damaged file uses valid backup without writing",
        )?;
        let repaired = store.update(|mut s| {
            s.ble_compress = true;
            s
        })?;
        ensure(
            repaired.openai_asr_api_key == old.openai_asr_api_key
                && repaired.ble_compress
                && !store.load()?.recovered,
            "explicit save repairs old valid configuration",
        )?;
        let quarantined: Vec<_> = io(fs::read_dir(output))?
            .filter_map(Result::ok)
            .map(|e| e.path())
            .filter(|p| {
                p.file_name()
                    .is_some_and(|s| s.to_string_lossy().contains(".corrupt-"))
            })
            .collect();
        ensure(
            quarantined.len() == 1 && io(fs::read(&quarantined[0]))? == bad,
            "exact damaged original retained",
        )?;
        let invalid = output.join("invalid.json");
        let invalid_store = Store {
            path: &invalid,
            vault: Some(&vault),
        };
        io(fs::write(&invalid, bad))?;
        ensure(
            invalid_store.load().is_err()
                && invalid_store.update(|s| s).is_err()
                && io(fs::read(&invalid))? == bad,
            "no backup cannot become defaults",
        )?;
        let mut future = serde_json::to_value(CompanionProductSettings::default())
            .map_err(|_| "probe encoding failed")?;
        future["settingsFormatVersion"] = serde_json::json!(99);
        let future = serde_json::to_vec(&future).map_err(|_| "probe encoding failed")?;
        io(fs::write(&invalid, &future))?;
        ensure(
            invalid_store.load().is_err()
                && invalid_store.update(|s| s).is_err()
                && io(fs::read(&invalid))? == future,
            "future format cannot be downgraded",
        )?;
        let published = io(fs::read(&path))?;
        let record: serde_json::Value =
            serde_json::from_slice(&published).map_err(|_| "probe publication decode failed")?;
        let id = record
            .get("credentialGeneration")
            .and_then(|v| v.as_str())
            .and_then(|v| Uuid::parse_str(v).ok())
            .ok_or("probe missing credential reference")?;
        vault.delete(id)?;
        ensure(
            store.load().is_err()
                && store.update(|s| s).is_err()
                && io(fs::read(&path))? == published,
            "missing current credential cannot resurrect backup",
        )?;
        let credential_checks = clear_checks(output, &vault)?;
        Ok(serde_json::json!({
            "result": "PASS_WINDOWS_SETTINGS_STORAGE_ONLY",
            "checks": ["readOnlyNewProfile", "nativeCredentialRoundTrip", "occupiedFileRetainsOldPair", "retryCommit",
                "noKeysInPublicOrBackup", "writerLock", "missingFileBackup", "damagedFileBackup",
                "explicitRepairPreservesOriginal", "unbackedCorruptProtected", "futureFormatProtected", "missingCredentialProtected"],
            "credentialClearChecks": credential_checks,
            "realUserProfileAccess": false, "deviceAccess": false, "networkAccess": false,
            "nativeGui": "NOT_RUN", "hardwareAcceptance": "NOT_RUN", "fullChainAcceptance": "NOT_RUN"
        }))
    })();
    vault.cleanup()?;
    result.map(|mut report| {
        report["testCredentialsRemoved"] = serde_json::json!(true);
        report
    })
}

fn clear_checks(output: &Path, vault: &ProbeVault) -> Result<Vec<&'static str>, String> {
    use super::{CompanionProductSettingsPatch, CredentialKind, apply_to_process_env};
    let names = ["COMPANION_TYPE_PRODUCT_SETTINGS_PATH", "COMPANION_TYPE_ASR_PROVIDER", "COMPANION_TYPE_ASR_API_KEY",
        "OPENAI_API_KEY", "COMPANION_TYPE_VOLC_APP_KEY", "COMPANION_TYPE_VOLC_ACCESS_KEY", "COMPANION_TYPE_VOLC_RESOURCE_ID",
        "COMPANION_TYPE_ASR_ENDPOINT", "COMPANION_TYPE_ASR_MODEL", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
        "COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED", "COMPANION_TYPE_BLE_COMPRESS", "COMPANION_TYPE_DEFAULT_MEETING_MODE", "COMPANION_TYPE_MINUTES_PROVIDER"];
    struct Environment(Vec<(&'static str, Option<std::ffi::OsString>)>);
    impl Drop for Environment { fn drop(&mut self) { for (key, value) in &self.0 {
        match value { Some(value) => std::env::set_var(key, value), None => std::env::remove_var(key) }
    } } }
    let _restore = Environment(names.iter().map(|key| (*key, std::env::var_os(key))).collect());
    for key in names { std::env::remove_var(key); }
    let mut checks = Vec::new();
    let mut check = |condition: bool, name: &'static str| -> Result<(), String> {
        ensure(condition, name)?; checks.push(name); Ok(())
    };
    let path = output.join("clear.json"); let store = Store { path: &path, vault: Some(vault) };
    let old = store.update(|mut s| {
        s.volc_app_key = "probe-private-app".into(); s.volc_access_key = "probe-private-access".into();
        s.openai_asr_api_key = "probe-private-asr".into(); s.deepseek_api_key = "probe-private-minutes".into(); s
    })?;
    apply_to_process_env(&old);
    let blank = CompanionProductSettingsPatch { settings: CompanionProductSettings::default(), clear_credentials: vec![] };
    let unchanged = store.update(|s| blank.merge(s))?;
    check(unchanged == old, "blankKeepsAllCredentials")?;
    let mut conflict = CompanionProductSettings::default(); conflict.deepseek_api_key = "probe-private-new".into();
    check(CompanionProductSettingsPatch { settings: conflict, clear_credentials: vec![CredentialKind::DeepseekApiKey] }.validate().is_err(), "clearReplaceConflictRejected")?;
    check(CompanionProductSettingsPatch { settings: CompanionProductSettings::default(), clear_credentials: vec![CredentialKind::DeepseekApiKey, CredentialKind::DeepseekApiKey] }.validate().is_err(), "duplicateClearRejected")?;
    let request = || CompanionProductSettingsPatch { settings: CompanionProductSettings::default(), clear_credentials: vec![CredentialKind::DeepseekApiKey] };
    let original = io(fs::read(&path))?;
    let occupied = io(OpenOptions::new().read(true).share_mode(1 | 2).open(&path))?;
    check(store.update_after_commit(|s| request().merge(s), apply_to_process_env).is_err(), "occupiedClearSaveFails")?;
    check(io(fs::read(&path))? == original && store.load()?.settings == old, "failedClearKeepsOldFileVaultPair")?;
    check(std::env::var("DEEPSEEK_API_KEY").ok().as_deref() == Some("probe-private-minutes"), "failedClearKeepsRuntimeKey")?;
    drop(occupied);
    // A production-owned legacy target is represented by this unique probe target.
    vault.vault.write_legacy(&CompanionProductSecrets::from_settings(&old))?;
    let retired: serde_json::Value = serde_json::from_slice(&original).map_err(|_| "probe encoding failed")?;
    let retired = Uuid::parse_str(retired["credentialGeneration"].as_str().ok_or("probe generation missing")?).map_err(|_| "probe generation invalid")?;
    let mut held_backup = None;
    let cleared = store.update_after_commit(|s| {
        // Backup publication happens before the merge; holding it here exercises
        // the post-commit failure, using real Windows sharing permissions.
        held_backup = Some(OpenOptions::new().read(true).share_mode(1 | 2).open(side(&path, ".bak")).expect("probe backup open"));
        request().merge(s)
    }, apply_to_process_env)?;
    check(cleared.deepseek_api_key.is_empty() && cleared.credential_blocks.deepseek_api_key, "committedClearStopsCredential")?;
    check(std::env::var_os("DEEPSEEK_API_KEY").is_none(), "committedClearRemovesProcessKey")?;
    check(store.load()?.warning.is_some() && side(&path, ".credential-clear").exists(), "postCommitCleanupWarningAndJournal")?;
    let committed = io(fs::read(&path))?;
    io(fs::write(&path, b"{interrupted clear cleanup"))?;
    check(store.load().is_err() && store.update(|s| s).is_err(), "pendingClearCannotRestoreOldBackup")?;
    std::env::set_var("COMPANION_TYPE_PRODUCT_SETTINGS_PATH", &path);
    for key in ["COMPANION_TYPE_VOLC_APP_KEY", "COMPANION_TYPE_VOLC_ACCESS_KEY", "COMPANION_TYPE_ASR_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"] { std::env::set_var(key, "probe-private-inherited"); }
    super::load_and_apply();
    check(["COMPANION_TYPE_VOLC_APP_KEY", "COMPANION_TYPE_VOLC_ACCESS_KEY", "COMPANION_TYPE_ASR_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"].iter().all(|key| std::env::var_os(key).is_none()) && super::public_report().storage_save_blocked, "damagedPendingClearStartupFailsClosed")?;
    std::env::remove_var("COMPANION_TYPE_PRODUCT_SETTINGS_PATH");
    io(fs::write(&path, &committed))?; drop(held_backup);
    let retried = store.update_after_commit(|s| s, apply_to_process_env)?;
    check(retried == cleared && store.load()?.warning.is_none(), "cleanupRetryCompletesWithoutRestoringKey")?;
    check(!side(&path, ".credential-clear").exists() && !side(&path, ".pending").exists(), "clearJournalsSettled")?;
    check(vault.read(Some(retired))?.is_none(), "oldNativeCredentialGenerationRemoved")?;
    let legacy = vault.read(None)?.ok_or("probe legacy target missing")?;
    check(legacy.deepseek_api_key.is_empty() && legacy.openai_asr_api_key == old.openai_asr_api_key, "ownLegacyClearPreservesOtherKeys")?;
    check(cleared.volc_app_key == old.volc_app_key && cleared.volc_access_key == old.volc_access_key && cleared.openai_asr_api_key == old.openai_asr_api_key, "selectedClearPreservesOtherProviders")?;
    let reload = Store { path: &path, vault: Some(vault) }.load()?.settings;
    std::env::set_var("DEEPSEEK_API_KEY", "probe-private-inherited"); apply_to_process_env(&reload);
    check(std::env::var_os("DEEPSEEK_API_KEY").is_none() && !reload.to_effective_public("isolated").deepseek_api_key_set, "reloadSuppressesInheritedFallback")?;
    check(!serde_json::to_string(&reload.to_effective_public("isolated")).map_err(|_| "probe public encoding failed")?.contains("probe-private"), "publicReportNeverEchoesCredentials")?;
    io(fs::write(&path, b"{damaged after clear"))?;
    let recovered = store.load()?;
    check(recovered.recovered && recovered.settings == cleared, "clearedBackupRecoversWithoutKey")?;
    store.update(|s| s)?;
    let mut replacement = CompanionProductSettings::default(); replacement.deepseek_api_key = "probe-private-replacement".into();
    let replacement = CompanionProductSettingsPatch { settings: replacement, clear_credentials: vec![] };
    let replaced = store.update_after_commit(|s| replacement.merge(s), apply_to_process_env)?;
    check(!replaced.credential_blocks.deepseek_api_key && replaced.deepseek_api_key == "probe-private-replacement", "replacementReenablesSelectedProvider")?;
    check(std::env::var("DEEPSEEK_API_KEY").ok().as_deref() == Some("probe-private-replacement"), "replacementAppliesAfterCommit")?;
    let all = CompanionProductSettingsPatch { settings: CompanionProductSettings::default(), clear_credentials: vec![
        CredentialKind::VolcAppKey, CredentialKind::VolcAccessKey, CredentialKind::OpenaiAsrApiKey, CredentialKind::DeepseekApiKey] };
    all.validate()?;
    let empty = store.update_after_commit(|s| all.merge(s), apply_to_process_env)?;
    check(CompanionProductSecrets::from_settings(&empty).is_empty(), "allProvidersCanBeExplicitlyCleared")?;
    check(vault.read(None)?.is_none(), "emptyOwnLegacyTargetRemoved")?;
    check(["COMPANION_TYPE_VOLC_APP_KEY", "COMPANION_TYPE_VOLC_ACCESS_KEY", "COMPANION_TYPE_ASR_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"].iter().all(|key| std::env::var_os(key).is_none()), "allRuntimeAliasesCleared")?;
    // Reuse the startup routine with a fresh plain fixture profile, never the
    // user's production settings or any shared legacy credential target.
    let startup_path = output.join("restart.json"); io(fs::write(&startup_path, serde_json::to_vec(&empty).map_err(|_| "probe encoding failed")?))?;
    std::env::set_var("COMPANION_TYPE_PRODUCT_SETTINGS_PATH", &startup_path);
    for key in ["COMPANION_TYPE_VOLC_APP_KEY", "COMPANION_TYPE_VOLC_ACCESS_KEY", "COMPANION_TYPE_ASR_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"] { std::env::set_var(key, "probe-private-inherited"); }
    super::load_and_apply();
    let public = super::public_report();
    check(!public.volc_app_key_set && !public.volc_access_key_set && !public.openai_asr_api_key_set && !public.deepseek_api_key_set, "startupRoutineHonorsPersistedClear")?;
    Ok(checks)
}
