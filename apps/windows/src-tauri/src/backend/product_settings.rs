//! Local product settings for Companion-Type (ASR / DeepSeek / meeting defaults).
//!
//! Stored under the user app-data directory. Secrets are never committed to the
//! repo; production secrets live in Windows Credential Manager and process env.

use std::fs;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

mod storage;
mod credentials;
pub use credentials::{CompanionProductSettingsPatch, CredentialBlocks, CredentialKind};
#[cfg(windows)]
mod windows_vault;
#[cfg(windows)]
mod storage_probe;

/// Explicit, isolated installed-binary check. Never reads the user's profile.
#[cfg(windows)]
pub fn verify_storage(output: &std::path::Path) -> Result<serde_json::Value, String> {
    storage_probe::run(output)
}

const LEGACY_PRODUCT_CREDENTIAL_TARGET: &str = "credentials.v1.chunk.0.com.listener.type";
const PRODUCT_CREDENTIAL_TARGET: &str = "Companion.Type.product-settings.secrets.v2";

#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
struct CompanionProductSecrets {
    volc_app_key: String,
    volc_access_key: String,
    openai_asr_api_key: String,
    deepseek_api_key: String,
}

impl CompanionProductSecrets {
    fn from_settings(settings: &CompanionProductSettings) -> Self {
        Self {
            volc_app_key: settings.volc_app_key.clone(),
            volc_access_key: settings.volc_access_key.clone(),
            openai_asr_api_key: settings.openai_asr_api_key.clone(),
            deepseek_api_key: settings.deepseek_api_key.clone(),
        }
    }

    fn is_empty(&self) -> bool {
        self.volc_app_key.is_empty()
            && self.volc_access_key.is_empty()
            && self.openai_asr_api_key.is_empty()
            && self.deepseek_api_key.is_empty()
    }

    fn apply_to(&self, settings: &mut CompanionProductSettings) {
        settings.volc_app_key = self.volc_app_key.clone();
        settings.volc_access_key = self.volc_access_key.clone();
        settings.openai_asr_api_key = self.openai_asr_api_key.clone();
        settings.deepseek_api_key = self.deepseek_api_key.clone();
    }
}

fn clear_persisted_secrets(settings: &mut CompanionProductSettings) {
    settings.volc_app_key.clear();
    settings.volc_access_key.clear();
    settings.openai_asr_api_key.clear();
    settings.deepseek_api_key.clear();
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct CompanionProductSettings {
    /// offlineStore | onlineLive
    pub default_meeting_mode: String,
    /// volcengine | openai-compatible | auto
    pub asr_provider: String,
    pub volc_app_key: String,
    pub volc_access_key: String,
    pub volc_resource_id: String,
    pub openai_asr_endpoint: String,
    pub openai_asr_api_key: String,
    pub openai_asr_model: String,
    pub deepseek_api_key: String,
    pub deepseek_base_url: String,
    pub deepseek_model: String,
    /// When true, Generate Minutes uses deepseek_minutes_polish.py if key set.
    pub deepseek_minutes_enabled: bool,
    /// Opt-in BLE IMA compress pull (COMPANION_TYPE_BLE_COMPRESS).
    pub ble_compress: bool,
    /// Persisted suppression of environment/legacy fallback after explicit clearing.
    #[serde(default)]
    pub credential_blocks: CredentialBlocks,
}

impl Default for CompanionProductSettings {
    fn default() -> Self {
        Self {
            default_meeting_mode: "offlineStore".to_string(),
            asr_provider: "volcengine".to_string(),
            volc_app_key: String::new(),
            volc_access_key: String::new(),
            volc_resource_id: "volc.bigasr.sauc.duration".to_string(),
            openai_asr_endpoint: "https://api.openai.com/v1/audio/transcriptions".to_string(),
            openai_asr_api_key: String::new(),
            openai_asr_model: "gpt-4o-transcribe".to_string(),
            deepseek_api_key: String::new(),
            deepseek_base_url: "https://api.deepseek.com/v1".to_string(),
            deepseek_model: "deepseek-v4-flash".to_string(),
            deepseek_minutes_enabled: true,
            ble_compress: false,
            credential_blocks: CredentialBlocks::default(),
        }
    }
}

/// Redacted view for UI (never echo full secrets back after save if desired).
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionProductSettingsPublic {
    pub default_meeting_mode: String,
    pub asr_provider: String,
    pub volc_app_key_set: bool,
    pub volc_access_key_set: bool,
    pub volc_resource_id: String,
    pub openai_asr_endpoint: String,
    pub openai_asr_api_key_set: bool,
    pub openai_asr_model: String,
    pub deepseek_api_key_set: bool,
    pub deepseek_base_url: String,
    pub deepseek_model: String,
    pub deepseek_minutes_enabled: bool,
    pub ble_compress: bool,
    pub settings_path: String,
    pub storage_warning: Option<String>,
    pub storage_save_blocked: bool,
}

impl CompanionProductSettings {
    /// Match the configuration used by providers without returning credentials.
    /// Environment / legacy-vault credentials are process-local and must never
    /// be copied into the settings file just to make readiness visible in the UI.
    pub fn to_effective_public(&self, path: &str) -> CompanionProductSettingsPublic {
        self.public_with_environment(path, |key| std::env::var(key).ok())
    }

    fn public_with_environment(
        &self,
        path: &str,
        read: impl Fn(&str) -> Option<String>,
    ) -> CompanionProductSettingsPublic {
        let value = |key: &str| read(key).filter(|value| !value.trim().is_empty());
        let mut public = self.to_public(path);
        if let Some(provider) = value("COMPANION_TYPE_ASR_PROVIDER") {
            public.asr_provider = match provider.to_ascii_lowercase().as_str() {
                "openai" => "openai-compatible".to_string(),
                _ => provider.to_ascii_lowercase(),
            };
        }
        public.volc_app_key_set |= !self.credential_blocks.volc_app_key && value("COMPANION_TYPE_VOLC_APP_KEY").is_some();
        public.volc_access_key_set |= !self.credential_blocks.volc_access_key && value("COMPANION_TYPE_VOLC_ACCESS_KEY").is_some();
        public.openai_asr_api_key_set |= !self.credential_blocks.openai_asr_api_key && (value("COMPANION_TYPE_ASR_API_KEY").is_some()
            || value("OPENAI_API_KEY").is_some());
        public.deepseek_api_key_set |= !self.credential_blocks.deepseek_api_key && value("DEEPSEEK_API_KEY").is_some();
        if let Some(enabled) = value("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED") {
            public.deepseek_minutes_enabled = enabled != "0";
        }
        if let Some(compress) = value("COMPANION_TYPE_BLE_COMPRESS") {
            public.ble_compress = compress == "1";
        }
        for (key, target) in [
            ("COMPANION_TYPE_VOLC_RESOURCE_ID", &mut public.volc_resource_id),
            ("COMPANION_TYPE_ASR_ENDPOINT", &mut public.openai_asr_endpoint),
            ("COMPANION_TYPE_ASR_MODEL", &mut public.openai_asr_model),
            ("DEEPSEEK_BASE_URL", &mut public.deepseek_base_url),
            ("DEEPSEEK_MODEL", &mut public.deepseek_model),
            ("COMPANION_TYPE_DEFAULT_MEETING_MODE", &mut public.default_meeting_mode),
        ] {
            if let Some(configured) = value(key) { *target = configured; }
        }
        public
    }

    pub fn to_public(&self, path: &str) -> CompanionProductSettingsPublic {
        CompanionProductSettingsPublic {
            default_meeting_mode: self.default_meeting_mode.clone(),
            asr_provider: self.asr_provider.clone(),
            volc_app_key_set: !self.credential_blocks.volc_app_key && !self.volc_app_key.trim().is_empty(),
            volc_access_key_set: !self.credential_blocks.volc_access_key && !self.volc_access_key.trim().is_empty(),
            volc_resource_id: self.volc_resource_id.clone(),
            openai_asr_endpoint: self.openai_asr_endpoint.clone(),
            openai_asr_api_key_set: !self.credential_blocks.openai_asr_api_key && !self.openai_asr_api_key.trim().is_empty(),
            openai_asr_model: self.openai_asr_model.clone(),
            deepseek_api_key_set: !self.credential_blocks.deepseek_api_key && !self.deepseek_api_key.trim().is_empty(),
            deepseek_base_url: self.deepseek_base_url.clone(),
            deepseek_model: self.deepseek_model.clone(),
            deepseek_minutes_enabled: self.deepseek_minutes_enabled,
            ble_compress: self.ble_compress,
            settings_path: path.to_string(),
            storage_warning: None,
            storage_save_blocked: false,
        }
    }
}

pub fn settings_path() -> PathBuf {
    if let Ok(override_path) = std::env::var("COMPANION_TYPE_PRODUCT_SETTINGS_PATH") {
        return PathBuf::from(override_path);
    }
    let base = std::env::var_os("APPDATA")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(PathBuf::from))
        .unwrap_or_else(|| PathBuf::from("."));
    base.join("Companion Type").join("product-settings.json")
}

fn with_store<T>(operation: impl FnOnce(storage::Store<'_>) -> T) -> T {
    let path = settings_path();
    #[cfg(windows)]
    let vault = std::env::var_os("COMPANION_TYPE_PRODUCT_SETTINGS_PATH").is_none()
        .then(|| windows_vault::WindowsVault { base: product_credential_target() });
    operation(storage::Store { path: &path,
        #[cfg(windows)]
        vault: vault.as_ref().map(|vault| vault as &dyn storage::Vault),
        #[cfg(not(windows))]
        vault: None,
    })
}

pub fn try_load_settings() -> Result<CompanionProductSettings, String> {
    with_store(|store| store.load().map(|loaded| loaded.settings))
}

pub fn load_settings() -> CompanionProductSettings {
    try_load_settings().unwrap_or_else(|error| {
        eprintln!("[settings] {error}");
        CompanionProductSettings::default()
    })
}

/// Keep storage failures visible even when the settings panel is collapsed.
pub fn public_report() -> CompanionProductSettingsPublic {
    let path = settings_path();
    match with_store(|store| store.load()) {
        Ok(loaded) => {
            let mut public = loaded.settings.to_effective_public(&path.to_string_lossy());
            public.storage_warning = loaded.warning;
            public
        }
        Err(error) => {
            let mut public = CompanionProductSettings::default().to_public(&path.to_string_lossy());
            public.storage_warning = Some(error);
            public.storage_save_blocked = true;
            public
        }
    }
}

pub fn save_settings(settings: &CompanionProductSettings) -> Result<PathBuf, String> {
    with_store(|store| store.update(|_| settings.clone()))?;
    Ok(settings_path())
}

/// Merge non-empty fields from `patch` into current on-disk settings.
fn merge_settings(mut current: CompanionProductSettings, patch: CompanionProductSettings) -> CompanionProductSettings {
    if !patch.default_meeting_mode.trim().is_empty() {
        current.default_meeting_mode = patch.default_meeting_mode.trim().to_string();
    }
    if !patch.asr_provider.trim().is_empty() {
        current.asr_provider = patch.asr_provider.trim().to_string();
    }
    // Blank inputs retain existing secrets. Clear intent uses a separate typed list.
    if !patch.volc_app_key.is_empty() {
        current.volc_app_key = patch.volc_app_key;
    }
    if !patch.volc_access_key.is_empty() {
        current.volc_access_key = patch.volc_access_key;
    }
    if !patch.volc_resource_id.trim().is_empty() {
        current.volc_resource_id = patch.volc_resource_id.trim().to_string();
    }
    if !patch.openai_asr_endpoint.trim().is_empty() {
        current.openai_asr_endpoint = patch.openai_asr_endpoint.trim().to_string();
    }
    if !patch.openai_asr_api_key.is_empty() {
        current.openai_asr_api_key = patch.openai_asr_api_key;
    }
    if !patch.openai_asr_model.trim().is_empty() {
        current.openai_asr_model = patch.openai_asr_model.trim().to_string();
    }
    if !patch.deepseek_api_key.is_empty() {
        current.deepseek_api_key = patch.deepseek_api_key;
    }
    if !patch.deepseek_base_url.trim().is_empty() {
        current.deepseek_base_url = patch.deepseek_base_url.trim().to_string();
    }
    if !patch.deepseek_model.trim().is_empty() {
        current.deepseek_model = patch.deepseek_model.trim().to_string();
    }
    current.deepseek_minutes_enabled = patch.deepseek_minutes_enabled;
    current.ble_compress = patch.ble_compress;
    current
}

pub fn merge_and_save(patch: CompanionProductSettings) -> Result<CompanionProductSettings, String> {
    merge_patch_and_save(CompanionProductSettingsPatch { settings: patch, clear_credentials: Vec::new() })
}

pub fn merge_patch_and_save(patch: CompanionProductSettingsPatch) -> Result<CompanionProductSettings, String> {
    patch.validate()?;
    with_store(|store| store.update_after_commit(|current| patch.merge(current), apply_to_process_env))
}

pub fn apply_to_process_env(settings: &CompanionProductSettings) {
    for (blocked, names) in [
        (settings.credential_blocks.volc_app_key, &["COMPANION_TYPE_VOLC_APP_KEY"][..]),
        (settings.credential_blocks.volc_access_key, &["COMPANION_TYPE_VOLC_ACCESS_KEY"][..]),
        (settings.credential_blocks.openai_asr_api_key, &["COMPANION_TYPE_ASR_API_KEY", "OPENAI_API_KEY"][..]),
        (settings.credential_blocks.deepseek_api_key, &["DEEPSEEK_API_KEY"][..]),
    ] {
        if blocked { for name in names { std::env::remove_var(name); } }
    }
    set_env("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED",
        Some(if settings.deepseek_minutes_enabled { "1" } else { "0" }));
    set_env(
        "COMPANION_TYPE_ASR_PROVIDER",
        Some(settings.asr_provider.as_str()),
    );
    if !settings.credential_blocks.volc_app_key && !settings.volc_app_key.trim().is_empty() {
        set_env("COMPANION_TYPE_VOLC_APP_KEY", Some(&settings.volc_app_key));
    }
    if !settings.credential_blocks.volc_access_key && !settings.volc_access_key.trim().is_empty() {
        set_env(
            "COMPANION_TYPE_VOLC_ACCESS_KEY",
            Some(&settings.volc_access_key),
        );
    }
    if !settings.volc_resource_id.trim().is_empty() {
        set_env(
            "COMPANION_TYPE_VOLC_RESOURCE_ID",
            Some(&settings.volc_resource_id),
        );
    }
    if !settings.openai_asr_endpoint.trim().is_empty() {
        set_env(
            "COMPANION_TYPE_ASR_ENDPOINT",
            Some(&settings.openai_asr_endpoint),
        );
    }
    if !settings.credential_blocks.openai_asr_api_key && !settings.openai_asr_api_key.trim().is_empty() {
        set_env(
            "COMPANION_TYPE_ASR_API_KEY",
            Some(&settings.openai_asr_api_key),
        );
        set_env("OPENAI_API_KEY", Some(&settings.openai_asr_api_key));
    }
    if !settings.openai_asr_model.trim().is_empty() {
        set_env("COMPANION_TYPE_ASR_MODEL", Some(&settings.openai_asr_model));
    }
    // DeepSeek minutes take the native reqwest path (minutes::deepseek_native_minutes),
    // which reads DEEPSEEK_* env directly. We deliberately do NOT set
    // COMPANION_TYPE_MINUTES_COMMAND here: that would route through the python
    // helper with a relative tools/ path that only resolves when cwd is the
    // Type root and silently breaks in a packaged build. The external command
    // stays available as an explicit override for users who set the env var.
    if !settings.credential_blocks.deepseek_api_key && settings.deepseek_minutes_enabled && !settings.deepseek_api_key.trim().is_empty() {
        set_env("DEEPSEEK_API_KEY", Some(&settings.deepseek_api_key));
        set_env("DEEPSEEK_BASE_URL", Some(&settings.deepseek_base_url));
        set_env("DEEPSEEK_MODEL", Some(&settings.deepseek_model));
    }
    set_env(
        "COMPANION_TYPE_BLE_COMPRESS",
        Some(if settings.ble_compress { "1" } else { "0" }),
    );
    set_env(
        "COMPANION_TYPE_DEFAULT_MEETING_MODE",
        Some(&settings.default_meeting_mode),
    );
}

fn set_env(key: &str, value: Option<&str>) {
    match value {
        Some(v) if !v.is_empty() => std::env::set_var(key, v),
        _ => {}
    }
}

pub fn load_and_apply() -> CompanionProductSettings {
    let loaded = match with_store(|store| store.load()) {
        Ok(loaded) => loaded,
        Err(error) => {
            eprintln!("[settings] {error}");
            // An unreadable configured profile cannot establish whether a key
            // was explicitly cleared. Fail closed for built-in services in this
            // process; never edit the user's environment or import another vault.
            for key in ["COMPANION_TYPE_VOLC_APP_KEY", "COMPANION_TYPE_VOLC_ACCESS_KEY",
                "COMPANION_TYPE_ASR_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"] {
                std::env::remove_var(key);
            }
            set_env("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED", Some("0"));
            return CompanionProductSettings::default();
        }
    };
    let configured = loaded.configured;
    #[allow(unused_mut)]
    let mut settings = loaded.settings;
    #[cfg(windows)]
    if configured
        && !loaded.recovered
        && std::env::var_os("COMPANION_TYPE_PRODUCT_SETTINGS_PATH").is_none()
        && settings_file_contains_plaintext_secrets()
    {
        match with_store(|store| store.update(|latest| latest)) {
            Ok(migrated) => {
                settings = migrated;
                eprintln!("[settings] migrated provider secrets to Windows Credential Manager");
            }
            Err(err) => eprintln!("[settings] credential migration failed: {err}"),
        }
    }
    if configured {
        apply_to_process_env(&settings);
    } else {
        /* Defaults must not clobber an explicit launch environment. This is
         * important for service/CLI deployments whose secrets remain in the
         * OS vault and are injected only for the process. */
        if std::env::var_os("COMPANION_TYPE_ASR_PROVIDER").is_none() {
            set_env("COMPANION_TYPE_ASR_PROVIDER", Some(&settings.asr_provider));
        }
        if std::env::var_os("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED").is_none() {
            set_env("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED", Some("1"));
        }
        if std::env::var_os("COMPANION_TYPE_VOLC_RESOURCE_ID").is_none() {
            set_env(
                "COMPANION_TYPE_VOLC_RESOURCE_ID",
                Some(&settings.volc_resource_id),
            );
        }
        if std::env::var_os("COMPANION_TYPE_BLE_COMPRESS").is_none() {
            set_env("COMPANION_TYPE_BLE_COMPRESS", Some("0"));
        }
        if std::env::var_os("COMPANION_TYPE_DEFAULT_MEETING_MODE").is_none() {
            set_env(
                "COMPANION_TYPE_DEFAULT_MEETING_MODE",
                Some(&settings.default_meeting_mode),
            );
        }
    }
    if !settings.credential_blocks.volc_app_key && !settings.credential_blocks.volc_access_key {
        apply_legacy_product_vault_if_needed();
    }
    settings
}

#[cfg(windows)]
fn settings_file_contains_plaintext_secrets() -> bool {
    let Ok(raw) = fs::read_to_string(settings_path()) else {
        return false;
    };
    let Ok(root) = serde_json::from_str::<serde_json::Value>(&raw) else {
        return false;
    };
    [
        "volcAppKey",
        "volcAccessKey",
        "openaiAsrApiKey",
        "deepseekApiKey",
    ]
    .iter()
    .any(|field| {
        root.get(field)
            .and_then(serde_json::Value::as_str)
            .is_some_and(|value| !value.is_empty())
    })
}

#[cfg(all(windows, test))]
fn windows_write_product_credentials(secrets: &CompanionProductSecrets) -> Result<(), String> {
    windows_vault::WindowsVault { base: product_credential_target() }.write_legacy(secrets)
}

#[cfg(all(windows, test))]
fn windows_product_credentials() -> Option<CompanionProductSecrets> {
    use storage::Vault;
    windows_vault::WindowsVault { base: product_credential_target() }.read(None).ok().flatten()
}

#[cfg(windows)]
fn product_credential_target() -> String {
    if let Ok(target) = std::env::var("COMPANION_TYPE_PRODUCT_CREDENTIAL_TARGET") {
        if !target.trim().is_empty() {
            return target;
        }
    }
    PRODUCT_CREDENTIAL_TARGET.to_string()
}

#[cfg(all(windows, test))]
fn windows_delete_test_credentials() -> Result<(), String> {
    windows_vault::WindowsVault { base: product_credential_target() }.delete_legacy()
}

/// One-way compatibility bridge for an existing Denzic installation. Older
/// products stored the shared provider bundle in Windows Credential Manager.
/// Companion Type may read that same per-user secret into this process, but it
/// never copies the token into product-settings.json or prints it. Explicit
/// Companion settings/environment always win.
fn apply_legacy_product_vault_if_needed() {
    if !legacy_import_allowed(|key| std::env::var(key).ok()) {
        return;
    }
    #[cfg(windows)]
    if let Some((app_key, access_key, resource_id)) = windows_legacy_volc_credentials() {
        set_env("COMPANION_TYPE_ASR_PROVIDER", Some("volcengine"));
        set_env("COMPANION_TYPE_VOLC_APP_KEY", Some(&app_key));
        set_env("COMPANION_TYPE_VOLC_ACCESS_KEY", Some(&access_key));
        set_env("COMPANION_TYPE_VOLC_RESOURCE_ID", Some(&resource_id));
        eprintln!(
            "[settings] imported Volcengine provider from Windows Credential Manager target={} (secret not persisted)",
            LEGACY_PRODUCT_CREDENTIAL_TARGET
        );
    }
}

fn legacy_import_allowed(read: impl Fn(&str) -> Option<String>) -> bool {
    let present = |key: &str| read(key).is_some_and(|value| !value.trim().is_empty());
    // An explicit isolated settings path must not pull in the user's real vault.
    if present("COMPANION_TYPE_PRODUCT_SETTINGS_PATH")
        || present("COMPANION_TYPE_VOLC_APP_KEY")
        || present("COMPANION_TYPE_VOLC_ACCESS_KEY")
    {
        return false;
    }
    match read("COMPANION_TYPE_ASR_PROVIDER") {
        None => true,
        Some(provider) => matches!(provider.trim().to_ascii_lowercase().as_str(), "" | "auto" | "volcengine"),
    }
}

#[cfg(windows)]
fn windows_legacy_volc_credentials() -> Option<(String, String, String)> {
    use std::ffi::c_void;
    use std::ptr;

    #[repr(C)]
    struct FileTime {
        low: u32,
        high: u32,
    }
    #[repr(C)]
    struct CredentialW {
        flags: u32,
        credential_type: u32,
        target_name: *mut u16,
        comment: *mut u16,
        last_written: FileTime,
        credential_blob_size: u32,
        credential_blob: *mut u8,
        persist: u32,
        attribute_count: u32,
        attributes: *mut c_void,
        target_alias: *mut u16,
        user_name: *mut u16,
    }
    #[link(name = "Advapi32")]
    extern "system" {
        fn CredReadW(
            target: *const u16,
            credential_type: u32,
            flags: u32,
            credential: *mut *mut CredentialW,
        ) -> i32;
        fn CredFree(buffer: *mut c_void);
    }

    let target: Vec<u16> = LEGACY_PRODUCT_CREDENTIAL_TARGET
        .encode_utf16()
        .chain(std::iter::once(0))
        .collect();
    let mut raw: *mut CredentialW = ptr::null_mut();
    // CRED_TYPE_GENERIC = 1.
    if unsafe { CredReadW(target.as_ptr(), 1, 0, &mut raw) } == 0 || raw.is_null() {
        return None;
    }
    let bytes = unsafe {
        let credential = &*raw;
        if credential.credential_blob.is_null() || credential.credential_blob_size == 0 {
            CredFree(raw.cast());
            return None;
        }
        std::slice::from_raw_parts(
            credential.credential_blob,
            credential.credential_blob_size as usize,
        )
        .to_vec()
    };
    unsafe { CredFree(raw.cast()) };

    // The legacy bundle is UTF-16LE JSON. Decode without assuming aligned u16
    // storage because CredentialBlob is byte-aligned.
    let words: Vec<u16> = bytes
        .chunks_exact(2)
        .map(|pair| u16::from_le_bytes([pair[0], pair[1]]))
        .take_while(|word| *word != 0)
        .collect();
    let json = String::from_utf16(&words).ok()?;
    parse_legacy_volc_credentials(&json)
}

fn parse_legacy_volc_credentials(json: &str) -> Option<(String, String, String)> {
    let root: serde_json::Value = serde_json::from_str(json).ok()?;
    let provider = root.get("providers")?.get("asr")?.get("volcengine")?;
    let app_key = provider.get("appKey")?.as_str()?.trim().to_string();
    let access_key = provider.get("accessKey")?.as_str()?.trim().to_string();
    let resource_id = provider
        .get("resourceId")
        .and_then(serde_json::Value::as_str)
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .unwrap_or("volc.seedasr.sauc.duration")
        .to_string();
    if app_key.is_empty() || access_key.is_empty() {
        return None;
    }
    Some((app_key, access_key, resource_id))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn runtime_credentials_enable_ui_without_exposing_or_persisting_secrets() {
        let settings = CompanionProductSettings::default();
        let environment = std::collections::HashMap::from([
            ("COMPANION_TYPE_ASR_PROVIDER", "openai"),
            ("COMPANION_TYPE_ASR_API_KEY", "asr-private-test"),
            ("COMPANION_TYPE_ASR_ENDPOINT", "https://example.test/audio"),
            ("DEEPSEEK_API_KEY", "minutes-private-test"),
            ("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED", "0"),
        ]);
        let public = settings.public_with_environment("isolated.json", |key| environment.get(key).map(|v| v.to_string()));
        assert_eq!(public.asr_provider, "openai-compatible");
        assert_eq!(public.openai_asr_endpoint, "https://example.test/audio");
        assert!(public.openai_asr_api_key_set && public.deepseek_api_key_set);
        assert!(!public.deepseek_minutes_enabled);
        let json = serde_json::to_string(&public).unwrap();
        assert!(!json.contains("private-test"));
        assert!(settings.openai_asr_api_key.is_empty() && settings.deepseek_api_key.is_empty());
        let imported = settings.public_with_environment("product.json", |key| match key {
            "COMPANION_TYPE_VOLC_APP_KEY" | "COMPANION_TYPE_VOLC_ACCESS_KEY" => Some("vault-only".to_string()),
            _ => None,
        });
        assert!(imported.volc_app_key_set && imported.volc_access_key_set);
        assert!(!serde_json::to_string(&imported).unwrap().contains("vault-only"));
    }

    #[test]
    fn legacy_import_respects_explicit_provider_partial_keys_and_isolation() {
        for key_value in [
            ("COMPANION_TYPE_ASR_PROVIDER", "openai-compatible"),
            ("COMPANION_TYPE_PRODUCT_SETTINGS_PATH", "isolated.json"),
            ("COMPANION_TYPE_VOLC_APP_KEY", "explicit-app"),
            ("COMPANION_TYPE_VOLC_ACCESS_KEY", "explicit-access"),
        ] {
            assert!(!legacy_import_allowed(|key| (key == key_value.0).then(|| key_value.1.to_string())));
        }
        assert!(legacy_import_allowed(|_| None));
        assert!(legacy_import_allowed(|key| (key == "COMPANION_TYPE_ASR_PROVIDER").then(|| "volcengine".to_string())));
    }

    fn with_temp_settings_path<F: FnOnce()>(body: F) {
        use std::sync::Mutex;
        static LOCK: Mutex<()> = Mutex::new(());
        let _guard = LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let directory = std::env::temp_dir().join(format!("companion-type-settings-{stamp}"));
        fs::create_dir(&directory).unwrap();
        let path = directory.join("settings.json");
        std::env::set_var(
            "COMPANION_TYPE_PRODUCT_SETTINGS_PATH",
            path.to_string_lossy().to_string(),
        );
        body();
        let _ = fs::remove_dir_all(&directory);
        std::env::remove_var("COMPANION_TYPE_PRODUCT_SETTINGS_PATH");
        // Do not leave meeting-mode / keys pollution for other tests.
        for key in [
            "COMPANION_TYPE_DEFAULT_MEETING_MODE",
            "COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED",
            "COMPANION_TYPE_VOLC_APP_KEY",
            "COMPANION_TYPE_VOLC_ACCESS_KEY",
            "COMPANION_TYPE_BLE_COMPRESS",
            "DEEPSEEK_API_KEY",
            "COMPANION_TYPE_MINUTES_COMMAND",
            "COMPANION_TYPE_MINUTES_ARGS",
        ] {
            std::env::remove_var(key);
        }
    }

    #[test]
    fn save_load_round_trip_and_apply_env() {
        with_temp_settings_path(|| {
            let mut s = CompanionProductSettings::default();
            s.default_meeting_mode = "onlineLive".to_string();
            s.volc_app_key = "app-test".to_string();
            s.volc_access_key = "access-test".to_string();
            s.deepseek_api_key = "sk-test".to_string();
            s.ble_compress = true;
            save_settings(&s).expect("save");
            apply_to_process_env(&s);
            let loaded = load_settings();
            assert_eq!(loaded.default_meeting_mode, "onlineLive");
            assert_eq!(loaded.volc_app_key, "app-test");
            assert_eq!(loaded.deepseek_api_key, "sk-test");
            assert!(loaded.deepseek_minutes_enabled);
            assert!(loaded.ble_compress);
            assert_eq!(
                std::env::var("COMPANION_TYPE_VOLC_APP_KEY").unwrap(),
                "app-test"
            );
            assert_eq!(std::env::var("COMPANION_TYPE_BLE_COMPRESS").unwrap(), "1");
            // DEEPSEEK_API_KEY is intentionally exercised by the ignored
            // network/product-path tests.  Do not read it here: Rust tests
            // share one process environment and those tests clean the key in
            // parallel, which made this persistence test nondeterministic.
        });
    }

    #[test]
    fn merge_keeps_previous_secret_when_patch_empty() {
        with_temp_settings_path(|| {
            let mut base = CompanionProductSettings::default();
            base.deepseek_api_key = "keep-me".to_string();
            save_settings(&base).unwrap();
            let mut patch = CompanionProductSettings::default();
            patch.deepseek_api_key = String::new();
            patch.ble_compress = true;
            let merged = merge_and_save(patch).unwrap();
            assert_eq!(merged.deepseek_api_key, "keep-me");
            assert!(merged.ble_compress);
        });
    }

    #[test]
    fn public_report_distinguishes_backup_recovery_from_protected_unreadable_settings() {
        with_temp_settings_path(|| {
            let path = settings_path();
            let mut previous = CompanionProductSettings::default();
            previous.deepseek_api_key = "settings-private-test".into();
            save_settings(&previous).unwrap();
            previous.ble_compress = true; save_settings(&previous).unwrap();
            fs::write(&path, b"{bad").unwrap();
            let recovered = public_report();
            assert!(recovered.storage_warning.is_some() && !recovered.storage_save_blocked);
            assert!(recovered.deepseek_api_key_set);
            assert!(!serde_json::to_string(&recovered).unwrap().contains("settings-private-test"));
            let mut backup = path.as_os_str().to_os_string(); backup.push(".bak");
            fs::remove_file(PathBuf::from(backup)).unwrap();
            let protected = public_report();
            assert!(protected.storage_warning.is_some() && protected.storage_save_blocked);
            assert!(!protected.deepseek_api_key_set);
            assert!(merge_and_save(CompanionProductSettings::default()).is_err());
            assert_eq!(fs::read(&path).unwrap(), b"{bad");
        });
    }

    #[test]
    fn failed_save_cannot_apply_patch_to_the_active_process_configuration() {
        with_temp_settings_path(|| {
            let mut old = CompanionProductSettings::default(); old.deepseek_api_key = "process-private-test".into();
            save_settings(&old).unwrap(); apply_to_process_env(&old);
            let mut future = serde_json::to_value(&old).unwrap();
            future["settingsFormatVersion"] = serde_json::json!(99);
            fs::write(settings_path(), serde_json::to_vec(&future).unwrap()).unwrap();
            let mut patch = old; patch.deepseek_api_key = "uncommitted-private-test".into();
            assert!(merge_and_save(patch).is_err());
            assert_eq!(std::env::var("DEEPSEEK_API_KEY").unwrap(), "process-private-test");
        });
    }

    #[cfg(windows)]
    #[test]
    #[ignore = "writes and removes isolated native Credential Manager snapshots"]
    fn windows_storage_probe_isolates_native_credentials() {
        with_temp_settings_path(|| {
            let output = settings_path().parent().unwrap().join("native-probe");
            let report = verify_storage(&output).expect("isolated native storage probe");
            assert_eq!(report["result"], "PASS_WINDOWS_SETTINGS_STORAGE_ONLY");
            assert_eq!(report["checks"].as_array().unwrap().len(), 12);
            assert_eq!(report["testCredentialsRemoved"], true);
            assert_eq!(report["realUserProfileAccess"], false);
            assert!(!report.to_string().contains("probe-private"));
            assert!(verify_storage(&output).is_err(), "existing folders must be protected");
        });
    }

    #[test]
    fn disabling_minutes_keeps_the_key_but_updates_the_active_provider_switch() {
        with_temp_settings_path(|| {
            let mut settings = CompanionProductSettings::default();
            settings.deepseek_api_key = "unused-test-key".to_string();
            apply_to_process_env(&settings);
            settings.deepseek_minutes_enabled = false;
            apply_to_process_env(&settings);
            assert_eq!(std::env::var("COMPANION_TYPE_DEEPSEEK_MINUTES_ENABLED").unwrap(), "0");
            assert_eq!(std::env::var("DEEPSEEK_API_KEY").unwrap(), "unused-test-key");
        });
    }

    #[test]
    fn persisted_settings_copy_contains_no_secret_values() {
        let mut settings = CompanionProductSettings::default();
        settings.volc_app_key = "volc-app-secret".to_string();
        settings.volc_access_key = "volc-access-secret".to_string();
        settings.openai_asr_api_key = "openai-secret".to_string();
        settings.deepseek_api_key = "deepseek-secret".to_string();
        let secrets = CompanionProductSecrets::from_settings(&settings);
        assert!(!secrets.is_empty());
        clear_persisted_secrets(&mut settings);
        let json = serde_json::to_string(&settings).unwrap();
        for secret in [
            "volc-app-secret",
            "volc-access-secret",
            "openai-secret",
            "deepseek-secret",
        ] {
            assert!(!json.contains(secret));
        }
        assert_eq!(secrets.volc_access_key, "volc-access-secret");
    }

    #[cfg(windows)]
    #[test]
    fn plaintext_detector_only_flags_non_empty_secret_fields() {
        with_temp_settings_path(|| {
            let path = settings_path();
            fs::write(
                &path,
                r#"{"volcAppKey":"","volcAccessKey":"secret","openaiAsrApiKey":"","deepseekApiKey":""}"#,
            )
            .unwrap();
            assert!(settings_file_contains_plaintext_secrets());
            fs::write(
                &path,
                r#"{"volcAppKey":"","volcAccessKey":"","openaiAsrApiKey":"","deepseekApiKey":""}"#,
            )
            .unwrap();
            assert!(!settings_file_contains_plaintext_secrets());
        });
    }

    #[cfg(windows)]
    #[test]
    #[ignore = "writes and removes one unique current-user Credential Manager entry"]
    fn windows_credential_manager_round_trip_uses_utf16_json_bundle() {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let old_app_data = std::env::var_os("APPDATA");
        let isolated_app_data = std::env::temp_dir().join(format!("companion-vault-{stamp}"));
        std::env::set_var("APPDATA", &isolated_app_data);
        std::env::remove_var("COMPANION_TYPE_PRODUCT_SETTINGS_PATH");
        std::env::set_var(
            "COMPANION_TYPE_PRODUCT_CREDENTIAL_TARGET",
            format!("Companion.Type.test.{stamp}"),
        );
        let secrets = CompanionProductSecrets {
            volc_app_key: "app".to_string(),
            volc_access_key: "access".to_string(),
            openai_asr_api_key: "openai".to_string(),
            deepseek_api_key: "deepseek".to_string(),
        };
        assert!(windows_product_credentials().is_none());
        windows_write_product_credentials(&secrets).expect("write unique test credential");
        let loaded = windows_product_credentials().expect("read unique test credential");
        let loaded_without_settings_file = load_settings();
        let cleanup = windows_delete_test_credentials();
        std::env::remove_var("COMPANION_TYPE_PRODUCT_CREDENTIAL_TARGET");
        match old_app_data {
            Some(value) => std::env::set_var("APPDATA", value),
            None => std::env::remove_var("APPDATA"),
        }
        cleanup.expect("remove unique test credential");
        assert_eq!(loaded, secrets);
        assert_eq!(loaded_without_settings_file.deepseek_api_key, "deepseek");
        assert_eq!(loaded_without_settings_file.volc_access_key, "access");
    }

    #[test]
    fn legacy_vault_json_extracts_volc_without_echoing_other_fields() {
        let parsed = parse_legacy_volc_credentials(
            r#"{"providers":{"asr":{"volcengine":{"appKey":"281","accessKey":"secret","resourceId":"volc.seedasr.sauc.duration"}}},"unrelated":"ignore"}"#,
        )
        .expect("valid legacy credentials");
        assert_eq!(parsed.0, "281");
        assert_eq!(parsed.1, "secret");
        assert_eq!(parsed.2, "volc.seedasr.sauc.duration");
        assert!(parse_legacy_volc_credentials("{}").is_none());
    }
}
