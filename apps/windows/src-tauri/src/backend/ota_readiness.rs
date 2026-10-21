//! Existing Companion 0x7001 readiness, separate from platform DOV1 receipts.
//! It explains a device refusal; it cannot authorize an image or waive a gate.

pub(super) const SERVICE_UUID: u128 = 0x8f7a00077b7d4f3d9d6f6c2d1b7c0000;
pub(super) const CHARACTERISTIC_UUID: u128 = 0x8f7a70017b7d4f3d9d6f6c2d1b7c0000;
const STORAGE_UNAVAILABLE: u16 = 1;
const BUSY: u16 = 2;
const POWER_UNKNOWN: u16 = 4;
const POWER_LOW: u16 = 8;
const CHARGER_FAULT: u16 = 16;
const KNOWN_BLOCKERS: u16 = STORAGE_UNAVAILABLE | BUSY | POWER_UNKNOWN | POWER_LOW | CHARGER_FAULT;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) struct Readiness {
    pub blockers: u16,
    pub battery_percent: Option<u8>,
    pub minimum_required_mv: u16,
}

impl Readiness {
    pub fn parse(bytes: &[u8]) -> Result<Self, String> {
        // Packed companion_gatt_ota_readiness_v1_t is exactly24 bytes.
        // The128-byte characteristic capacity is not its current wire length.
        if bytes.len() != 24 || bytes[0] != 1 || bytes[1] > 1
            || (bytes[3] > 100 && bytes[3] != 255) {
            return Err("无法确认设备升级条件：设备状态格式无效，尚未发送固件。".into());
        }
        let blockers = u16::from_le_bytes([bytes[6], bytes[7]]);
        if blockers & !KNOWN_BLOCKERS != 0 || (bytes[1] == 1) != (blockers == 0) {
            return Err("无法确认设备升级条件：设备状态尚未就绪或不一致，尚未发送固件。".into());
        }
        Ok(Self { blockers, battery_percent: (bytes[3] != 255).then_some(bytes[3]),
            minimum_required_mv: u16::from_le_bytes([bytes[4], bytes[5]]) })
    }

    pub fn blocker_message(self) -> Option<String> {
        let mut reasons = Vec::new();
        if self.blockers & STORAGE_UNAVAILABLE != 0 { reasons.push("设备升级存储尚未就绪".to_owned()); }
        if self.blockers & BUSY != 0 { reasons.push("设备正在录音、播放或处理升级存储".to_owned()); }
        if self.blockers & POWER_UNKNOWN != 0 { reasons.push("设备尚未确认可用于升级的电池电压或外接供电".to_owned()); }
        if self.blockers & POWER_LOW != 0 {
            let charge = self.battery_percent.map(|v| format!("（当前{v}%）")).unwrap_or_default();
            let threshold = if self.minimum_required_mv != 0 { format!("，升级要求至少{}mV", self.minimum_required_mv) } else { String::new() };
            reasons.push(format!("电池电量或电压不足{charge}{threshold}"));
        }
        if self.blockers & CHARGER_FAULT != 0 { reasons.push("设备报告充电故障".to_owned()); }
        (!reasons.is_empty()).then(|| format!("暂时无法升级：{}。尚未发送固件内容。", reasons.join("；")))
    }

    pub fn check_preflight(self) -> Result<(), String> {
        // BUSY also names a retained interrupted upgrade. Do not block that
        // same-image resume based on a public summary/prefix; let the existing
        // full signed-manifest gate match its exact transaction. Recording,
        // playback and other conflicts remain enforced by the device there.
        if self.blockers & !BUSY != 0 {
            return Err(self.blocker_message().expect("non-busy blocker has a reason"));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn wire(blockers: u16, percent: u8) -> Vec<u8> {
        let mut b = vec![0u8; 24]; b[0] = 1; b[1] = u8::from(blockers == 0); b[3] = percent;
        b[4..6].copy_from_slice(&3600u16.to_le_bytes()); b[6..8].copy_from_slice(&blockers.to_le_bytes()); b
    }
    #[test]
    fn actual_unknown_power_is_a_specific_refusal_without_fake_percent() {
        let r = Readiness::parse(&wire(4, 255)).unwrap();
        assert_eq!(r.battery_percent, None);
        let error = r.check_preflight().unwrap_err();
        assert!(error.contains("电池电压或外接供电"));
        assert!(!error.contains("255%"));
    }
    #[test]
    fn known_cell_and_charger_failures_retain_all_reasons() {
        let error = Readiness::parse(&wire(STORAGE_UNAVAILABLE | POWER_LOW | CHARGER_FAULT, 18)).unwrap()
            .check_preflight().unwrap_err();
        for reason in ["升级存储", "18%", "3600mV", "充电故障"] { assert!(error.contains(reason)); }
    }
    #[test]
    fn active_transaction_still_reaches_full_manifest_validation() {
        // An interrupted OTA is BUSY. Prefix/size/claimed version cannot
        // authorize resume, and this check must not prematurely forbid it.
        let mut b = wire(BUSY, 255); b[8..24].fill(0xab);
        let r = Readiness::parse(&b).unwrap();
        assert!(r.check_preflight().is_ok());
        assert!(r.blocker_message().unwrap().contains("录音、播放或处理升级存储"));
        assert!(Readiness::parse(&wire(BUSY | POWER_UNKNOWN, 255)).unwrap().check_preflight().is_err());
    }
    #[test]
    fn malformed_initial_unknown_and_contradictory_values_never_proceed() {
        let valid = wire(0, 255);
        for len in [0, 8, 23, 25, 128] { let mut b = valid.clone(); b.resize(len, 0); assert!(Readiness::parse(&b).is_err()); }
        for (index, value) in [(0, 2), (1, 2), (3, 101), (7, 0xff)] {
            let mut b = valid.clone(); b[index] = value; assert!(Readiness::parse(&b).is_err());
        }
        let mut b = wire(POWER_LOW, 40); b[1] = 1; assert!(Readiness::parse(&b).is_err());
        let mut b = valid.clone(); b[1] = 0; assert!(Readiness::parse(&b).is_err());
    }
    #[test]
    fn ready_power_is_only_permission_to_ask_device_to_validate_image() {
        let r = Readiness::parse(&wire(0, 100)).unwrap();
        assert!(r.check_preflight().is_ok()); assert_eq!(r.blocker_message(), None);
    }
}
