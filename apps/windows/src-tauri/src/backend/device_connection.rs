//! Durable, conservative device reconnection preference.
//!
//! Only a stable native Bluetooth address that completed a real GATT probe is
//! stored. Discovery results and configured/fixture transports never arm
//! automatic reconnect.

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

const FILE_NAME: &str = "device-connection.json";

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct DeviceConnectionPreference {
    pub remembered_device_id: Option<String>,
    pub auto_reconnect_enabled: bool,
    pub manual_disconnect: bool,
    pub last_connected_at: Option<String>,
}

impl Default for DeviceConnectionPreference {
    fn default() -> Self {
        Self {
            remembered_device_id: None,
            auto_reconnect_enabled: true,
            manual_disconnect: false,
            last_connected_at: None,
        }
    }
}

impl DeviceConnectionPreference {
    pub(crate) fn can_automatically_reconnect(&self) -> bool {
        self.auto_reconnect_enabled
            && !self.manual_disconnect
            && self.remembered_device_id.as_deref().is_some_and(stable_device_id)
    }

    pub(crate) fn remember_native_success(&mut self, device_id: &str, at: String) -> bool {
        if !stable_device_id(device_id) {
            return false;
        }
        self.remembered_device_id = Some(device_id.trim().to_string());
        self.manual_disconnect = false;
        self.last_connected_at = Some(at);
        true
    }

    pub(crate) fn mark_manual_disconnect(&mut self) {
        self.manual_disconnect = self.remembered_device_id.is_some();
    }

    pub(crate) fn set_auto_reconnect(&mut self, enabled: bool) {
        self.auto_reconnect_enabled = enabled;
        if enabled {
            // Turning the preference back on is an explicit request to resume.
            self.manual_disconnect = false;
        }
    }
}

pub(crate) fn stable_device_id(value: &str) -> bool {
    let normalized = value
        .chars()
        .filter(|character| character.is_ascii_hexdigit())
        .collect::<String>();
    normalized.len() == 12 && value.chars().all(|character| {
        character.is_ascii_hexdigit() || matches!(character, ':' | '-')
    })
}

pub(crate) fn same_device_id(left: &str, right: &str) -> bool {
    let normalize = |value: &str| {
        value
            .chars()
            .filter(|character| character.is_ascii_hexdigit())
            .flat_map(char::to_uppercase)
            .collect::<String>()
    };
    stable_device_id(left) && stable_device_id(right) && normalize(left) == normalize(right)
}

fn preference_path() -> PathBuf {
    super::persistence::state_file_path()
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join(FILE_NAME)
}

pub(crate) fn load() -> DeviceConnectionPreference {
    if cfg!(test) && std::env::var("COMPANION_TYPE_STATE_PATH").is_err() {
        return DeviceConnectionPreference::default();
    }
    load_from(&preference_path()).unwrap_or_default()
}

pub(crate) fn save(preference: &DeviceConnectionPreference) -> Result<(), String> {
    if cfg!(test) && std::env::var("COMPANION_TYPE_STATE_PATH").is_err() {
        return Ok(());
    }
    save_to(&preference_path(), preference)
}

pub(super) fn load_from(path: &Path) -> Option<DeviceConnectionPreference> {
    let bytes = fs::read(path).ok()?;
    let preference = serde_json::from_slice::<DeviceConnectionPreference>(&bytes).ok()?;
    if preference
        .remembered_device_id
        .as_deref()
        .is_some_and(|id| !stable_device_id(id))
    {
        return None;
    }
    Some(preference)
}

pub(super) fn save_to(path: &Path, preference: &DeviceConnectionPreference) -> Result<(), String> {
    let bytes = serde_json::to_vec_pretty(preference)
        .map_err(|error| format!("serialize device preference: {error}"))?;
    super::export::write_atomic(path, &bytes).map(|_| ())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_stable_native_address_can_arm_automatic_reconnect() {
        let mut preference = DeviceConnectionPreference::default();
        assert!(!preference.remember_native_success("companion", "now".to_string()));
        assert!(!preference.can_automatically_reconnect());
        assert!(preference.remember_native_success(
            "AA:BB:CC:DD:EE:FF",
            "2026-10-04T00:00:00Z".to_string()
        ));
        assert!(preference.can_automatically_reconnect());
        preference.mark_manual_disconnect();
        assert!(!preference.can_automatically_reconnect());
        preference.set_auto_reconnect(true);
        assert!(preference.can_automatically_reconnect());
        preference.set_auto_reconnect(false);
        assert!(!preference.can_automatically_reconnect());
    }

    #[test]
    fn corrupt_or_unstable_persisted_identity_fails_closed() {
        let path = std::env::temp_dir().join(format!(
            "companion-device-preference-{}-{}.json",
            std::process::id(),
            crate::backend::unix_time_ms()
        ));
        fs::write(
            &path,
            br#"{"rememberedDeviceId":"companion","autoReconnectEnabled":true,"manualDisconnect":false,"lastConnectedAt":null}"#,
        )
        .unwrap();
        assert!(load_from(&path).is_none());
        let _ = fs::remove_file(path);
    }


    #[test]
    fn address_comparison_ignores_only_native_address_separators_and_case() {
        assert!(same_device_id("aa:bb:cc:dd:ee:ff", "AA-BB-CC-DD-EE-FF"));
        assert!(!same_device_id("AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:00"));
        assert!(!same_device_id("companion", "companion"));
    }

    #[test]
    fn preference_save_atomically_replaces_an_existing_file() {
        let path = std::env::temp_dir().join(format!(
            "companion-device-preference-replace-{}-{}.json",
            std::process::id(),
            crate::backend::unix_time_ms()
        ));
        let mut preference = DeviceConnectionPreference::default();
        preference.remember_native_success("AA:BB:CC:DD:EE:FF", "first".to_string());
        save_to(&path, &preference).unwrap();
        preference.mark_manual_disconnect();
        save_to(&path, &preference).unwrap();
        assert!(load_from(&path).unwrap().manual_disconnect);
        let _ = fs::remove_file(path);
    }
}
