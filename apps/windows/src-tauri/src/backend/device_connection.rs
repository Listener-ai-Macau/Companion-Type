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
    #[serde(default)]
    pub pairing_required: bool,
    pub last_connected_at: Option<String>,
}

impl Default for DeviceConnectionPreference {
    fn default() -> Self {
        Self {
            remembered_device_id: None,
            auto_reconnect_enabled: true,
            manual_disconnect: false,
            pairing_required: false,
            last_connected_at: None,
        }
    }
}

impl DeviceConnectionPreference {
    pub(crate) fn remember_confirmed_recorder_connect(&mut self,
        action: crate::companion_v1::CompanionV1ControlAction,
        snapshot: &crate::companion_v1::CompanionV1Snapshot, at: String) -> bool {
        use crate::companion_v1::CompanionV1ControlAction as Action;
        // Called only after recorder_control::apply completes its protected
        // identity/journal observation. STOP/PAUSE/recovery are not user Connect.
        if action != Action::DeviceConnect || snapshot.source != "firmware"
            || snapshot.device.mode != "windowsNative" || !snapshot.connected
            || !snapshot.device.connected
            || snapshot.last_control.as_ref().is_none_or(|c| !c.accepted || c.action != action) {
            return false;
        }
        self.remember_connected_probe("windows-native-connect", true,
            snapshot.device.device_id.as_deref(), at)
    }

    /// A completed user Connect clears their earlier Disconnect for a live
    /// recorder too. Discovery/configured/failed transports cannot do so.
    pub(crate) fn remember_connected_probe(&mut self, mode: &str, ready: bool,
        device_id: Option<&str>, at: String) -> bool {
        if !ready || !matches!(mode, "windows-native-connect"
            | "windows-native-connect-auto-upload" | "windows-native-connect-auto-upload-segmented") {
            return false;
        }
        device_id.is_some_and(|id| self.remember_native_success(id, at))
    }

    pub(crate) fn can_automatically_reconnect(&self) -> bool {
        self.auto_reconnect_enabled
            && !self.manual_disconnect
            && !self.pairing_required
            && self.remembered_device_id.as_deref().is_some_and(stable_device_id)
    }

    pub(crate) fn remember_native_success(&mut self, device_id: &str, at: String) -> bool {
        if !stable_device_id(device_id) {
            return false;
        }
        self.remembered_device_id = Some(device_id.trim().to_string());
        self.manual_disconnect = false;
        self.pairing_required = false;
        self.last_connected_at = Some(at);
        true
    }

    pub(crate) fn mark_manual_disconnect(&mut self) {
        self.manual_disconnect = self.remembered_device_id.is_some();
    }

    pub(crate) fn mark_pairing_required(&mut self, device_id:&str)->bool {
        if self.remembered_device_id.as_deref().is_none_or(|id|!same_device_id(id,device_id)) {return false;}
        self.pairing_required=true;true
    }

    /// A protected original-session recovery may resolve pairing without
    /// undoing the user's independent manual-disconnect/auto-connect choice.
    pub(crate) fn observe_confirmed_pairing(&mut self,snapshot:&crate::companion_v1::CompanionV1Snapshot)->bool {
        if !self.pairing_required || snapshot.source!="firmware" || snapshot.device.mode!="windowsNative"
            || !snapshot.connected || !snapshot.device.connected
            || snapshot.device.device_id.as_deref().is_none_or(|id|self.remembered_device_id.as_deref().is_none_or(|known|!same_device_id(known,id))) {
            return false;
        }
        self.pairing_required=false;true
    }

    pub(crate) fn set_auto_reconnect(&mut self, enabled: bool) {
        self.auto_reconnect_enabled = enabled;
        if enabled {
            // Turning the preference back on is an explicit request to resume.
            self.manual_disconnect = false;
            self.pairing_required = false;
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
    fn pairing_pause_is_exact_durable_and_does_not_change_user_opt_in() {
        let mut preference=DeviceConnectionPreference::default();
        preference.remember_native_success("C8:92:FF:DD:3B:CA","before".into());
        assert!(!preference.mark_pairing_required("AA:BB:CC:DD:EE:FF"));
        assert!(preference.can_automatically_reconnect());
        assert!(preference.mark_pairing_required("c8-92-ff-dd-3b-ca"));
        assert!(preference.auto_reconnect_enabled && !preference.manual_disconnect);
        assert!(!preference.can_automatically_reconnect());
        let path=std::env::temp_dir().join(format!("companion-pairing-pause-{}.json",uuid::Uuid::new_v4()));
        save_to(&path,&preference).unwrap();
        let mut restarted=load_from(&path).unwrap();assert_eq!(restarted,preference);
        let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.device.connected=false;
        super::super::apply_connection_preference(&mut snapshot,&restarted);
        assert_eq!(snapshot.device.connection_phase,"pairingRequired");
        restarted.set_auto_reconnect(true);
        assert!(restarted.can_automatically_reconnect());
        super::super::apply_connection_preference(&mut snapshot,&restarted);
        assert_eq!(snapshot.device.connection_phase,"offline");
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn protected_recovery_resolves_pairing_without_reversing_manual_disconnect() {
        let mut p=DeviceConnectionPreference::default();p.remember_native_success("C8:92:FF:DD:3B:CA","old".into());
        p.mark_pairing_required("C8:92:FF:DD:3B:CA");p.set_auto_reconnect(false);p.mark_manual_disconnect();
        let mut s=crate::companion_v1::fixture_snapshot();s.source="firmware";s.connected=true;s.device.connected=true;
        s.device.mode="windowsNative".into();s.device.device_id=Some("AA:BB:CC:DD:EE:FF".into());
        assert!(!p.observe_confirmed_pairing(&s));assert!(p.pairing_required);
        s.device.device_id=Some("C8:92:FF:DD:3B:CA".into());s.device.connected=false;assert!(!p.observe_confirmed_pairing(&s));
        s.device.connected=true;assert!(p.observe_confirmed_pairing(&s));
        assert!(!p.pairing_required && p.manual_disconnect && !p.auto_reconnect_enabled);
        assert!(!p.can_automatically_reconnect());
    }

    #[test]
    fn legacy_preference_without_pause_field_keeps_its_original_choices() {
        let old=br#"{"rememberedDeviceId":"C8:92:FF:DD:3B:CA","autoReconnectEnabled":false,"manualDisconnect":true,"lastConnectedAt":null}"#;
        let preference:DeviceConnectionPreference=serde_json::from_slice(old).unwrap();
        assert!(!preference.pairing_required && !preference.auto_reconnect_enabled && preference.manual_disconnect);
    }

    #[test]
    fn protected_recorder_connect_retires_disconnect_but_other_controls_or_failed_observations_do_not() {
        use crate::companion_v1::{fixture_snapshot, CompanionV1ControlAction as Action,
            CompanionV1ControlEcho, COMPANION_V1_GATT_BOUNDARY};
        let mut original = DeviceConnectionPreference::default();
        original.remember_native_success("C8:92:FF:DD:3B:CA", "before".into());
        original.set_auto_reconnect(false);
        original.mark_manual_disconnect();
        let mut snapshot = fixture_snapshot();
        snapshot.source = "firmware".into();
        snapshot.connected = true;
        snapshot.device.connected = true;
        snapshot.device.mode = "windowsNative".into();
        snapshot.device.device_id = original.remembered_device_id.clone();
        snapshot.last_control = Some(CompanionV1ControlEcho { action: Action::DeviceConnect,
            characteristic_uuid: COMPANION_V1_GATT_BOUNDARY.meeting_control_uuid,
            payload_hex: String::new(), accepted: true, message: "protected original confirmed".into() });
        let mut preference = original.clone();
        assert!(preference.remember_confirmed_recorder_connect(Action::DeviceConnect, &snapshot, "after".into()));
        assert!(!preference.manual_disconnect);
        assert!(!preference.auto_reconnect_enabled);
        for action in [Action::MeetingRecoverControl, Action::MeetingStop, Action::MeetingPause,
            Action::MeetingResume, Action::DeviceDisconnect] {
            let mut preference = original.clone();
            assert!(!preference.remember_confirmed_recorder_connect(action, &snapshot, "invalid".into()));
            assert_eq!(preference, original);
        }
        for field in ["disconnected", "wrong_mode", "wrong_source", "unaccepted", "missing_echo", "unstable"] {
            let mut candidate = snapshot.clone();
            match field {
                "disconnected" => candidate.device.connected = false,
                "wrong_mode" => candidate.device.mode = "configured".into(),
                "wrong_source" => candidate.source = "fixture".into(),
                "unaccepted" => candidate.last_control.as_mut().unwrap().accepted = false,
                "missing_echo" => candidate.last_control = None,
                _ => candidate.device.device_id = Some("companion".into()),
            }
            let mut preference = original.clone();
            assert!(!preference.remember_confirmed_recorder_connect(Action::DeviceConnect, &candidate, "invalid".into()), "{field}");
            assert_eq!(preference, original);
        }
    }

    #[test]
    fn live_original_reconnect_clears_the_actual_manual_disconnect_without_enabling_auto_reconnect() {
        let mut preference = DeviceConnectionPreference::default();
        preference.remember_native_success("C8:92:FF:DD:3B:CA", "before".into());
        preference.set_auto_reconnect(false);
        preference.mark_manual_disconnect();
        assert!(preference.manual_disconnect);
        assert!(preference.remember_connected_probe("windows-native-connect", true,
            Some("C8:92:FF:DD:3B:CA"), "after".into()));
        assert!(!preference.manual_disconnect, "explicit live Connect must allow the bounded follower again");
        assert!(!preference.auto_reconnect_enabled, "user's auto-reconnect setting is independent");
        assert_eq!(preference.last_connected_at.as_deref(), Some("after"));
    }

    #[test]
    fn no_successful_native_probe_never_clears_manual_disconnect() {
        let mut preference = DeviceConnectionPreference::default();
        preference.remember_native_success("C8:92:FF:DD:3B:CA", "before".into());
        preference.mark_manual_disconnect();
        let original = preference.clone();
        for (mode, ready, id) in [("windows-native-connect", false, Some("C8:92:FF:DD:3B:CA")),
            ("windows-native-scan", true, Some("C8:92:FF:DD:3B:CA")),
            ("configured-native", true, Some("C8:92:FF:DD:3B:CA")),
            ("windows-native-connect", true, None), ("windows-native-connect", true, Some("companion"))] {
            assert!(!preference.remember_connected_probe(mode, ready, id, "invalid".into()));
            assert_eq!(preference, original);
        }
        for mode in ["windows-native-connect-auto-upload", "windows-native-connect-auto-upload-segmented"] {
            let mut successful = original.clone();
            assert!(successful.remember_connected_probe(mode, true, Some("C8:92:FF:DD:3B:CA"), "valid".into()));
            assert!(!successful.manual_disconnect);
        }
    }

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
