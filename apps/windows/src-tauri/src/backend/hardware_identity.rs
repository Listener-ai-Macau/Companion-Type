//! Explicit physical acceptance identity, independent of historical test builds.
use std::{fs, path::Path};
use serde::{Deserialize, Serialize};
use crate::companion_v1::CompanionV1DeviceTransportState;

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(crate) struct ExpectedIdentity {
    pub schema: String,
    pub firmware_version: u32,
    pub build_id: u32,
    pub board_id: u32,
    pub hardware_revision: String,
    pub mcu_uid: String,
    pub ui_generation: u32,
}

impl ExpectedIdentity {
    fn validate(mut self) -> Result<Self, String> {
        if self.schema != "companion.hardware.expected_identity.v1"
            || self.firmware_version == 0 || self.build_id == 0 || self.board_id == 0
            || self.ui_generation == 0 || self.hardware_revision.trim().is_empty()
            || self.mcu_uid.len() != 24 || !self.mcu_uid.bytes().all(|b| b.is_ascii_hexdigit())
            || self.mcu_uid.bytes().all(|b| b == b'0') {
            return Err("expected hardware identity requires explicit firmware/build/board/revision/96-bit UID/UI".into());
        }
        self.mcu_uid.make_ascii_lowercase();
        Ok(self)
    }

    pub(crate) fn load(path: &Path) -> Result<Self, String> {
        let bytes = fs::read(path).map_err(|e| format!("read expected identity {}: {e}", path.display()))?;
        if bytes.len() > 4096 { return Err("expected hardware identity exceeds 4096 bytes".into()); }
        serde_json::from_slice::<Self>(&bytes)
            .map_err(|e| format!("invalid expected hardware identity: {e}"))?.validate()
    }

    pub(crate) fn matches(&self, actual: &CompanionV1DeviceTransportState) -> bool {
        actual.firmware_version == Some(self.firmware_version)
            && actual.build_id == Some(self.build_id)
            && actual.board_id == Some(self.board_id)
            && actual.hardware_revision.as_deref() == Some(self.hardware_revision.as_str())
            && actual.mcu_uid.as_deref().is_some_and(|uid| uid.eq_ignore_ascii_case(&self.mcu_uid))
            && actual.ui_generation == Some(self.ui_generation)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn expected() -> ExpectedIdentity {
        serde_json::from_value(serde_json::json!({
            "schema":"companion.hardware.expected_identity.v1",
            "firmwareVersion":0x10128,"buildId":0x20261004,"boardId":0x57424155,
            "hardwareRevision":"COMPANION-WBA55-V1.1",
            "mcuUid":"180010000d50335754363720","uiGeneration":58
        })).unwrap()
    }
    fn actual() -> CompanionV1DeviceTransportState {
        let e=expected();let mut d=crate::companion_v1::fixture_snapshot().device;
        d.firmware_version=Some(e.firmware_version);d.build_id=Some(e.build_id);
        d.board_id=Some(e.board_id);d.hardware_revision=Some(e.hardware_revision);
        d.mcu_uid=Some(e.mcu_uid);d.ui_generation=Some(e.ui_generation);d
    }
    #[test]
    fn physical_identity_matches_all_fields() {
        let e=expected().validate().unwrap();assert!(e.matches(&actual()));
        for field in 0..6 {
            let mut d=actual();
            match field {
                0=>d.firmware_version=Some(0x10114),1=>d.build_id=None,
                2=>d.board_id=Some(0),3=>d.hardware_revision=Some("other".into()),
                4=>d.mcu_uid=Some("180010000d50335754363721".into()),_=>d.ui_generation=Some(38),
            }
            assert!(!e.matches(&d),"field {field} was not bound");
        }
    }
    #[test]
    fn invalid_identity_cannot_relax_checks() {
        for uid in ["", "000000000000000000000000", "180010000d5033575436372g"] {
            let mut e=expected();e.mcu_uid=uid.into();assert!(e.validate().is_err());
        }
        let mut e=expected();e.ui_generation=0;assert!(e.validate().is_err());
        let mut e=expected();e.schema="fixture".into();assert!(e.validate().is_err());
        let mut value=serde_json::to_value(expected()).unwrap();value["ignoreUid"]=true.into();
        assert!(serde_json::from_value::<ExpectedIdentity>(value).is_err());
    }
}
