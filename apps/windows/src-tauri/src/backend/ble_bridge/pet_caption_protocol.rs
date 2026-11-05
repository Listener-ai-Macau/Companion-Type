//! Known PCS1 wire revisions only. Firmware build numbers never grant support.
//! v0: original immediate BEGIN; v1: admission reasons; v2: reserved BEGIN.
pub(super) fn parse(value: &[u8]) -> Result<(u8, u32, u32), String> {
    if value.len() != 16 || &value[..4] != b"PCS1" {
        return Err("这块固件还不支持宠物聊天字幕，请先安装匹配的联合固件。".into());
    }
    let revision = value[7] >> 4;
    if revision > 2 || value[7] & 0x0c != 0 {
        return Err("当前字幕协议版本不受支持；回复已保留，请更新匹配的 Companion Type 与固件。".into());
    }
    // v0 had no gate/surface extension. State6 was introduced with v2 op5.
    // Invalid states/row counts must not become support or a visible receipt.
    if (revision == 0 && (value[5] != 0 || value[7] != 0))
        || value[4] > if revision == 2 { 6 } else { 5 }
        || value[6] > 13
    {
        return Err("字幕状态无法核对；回复已保留，请重新读取设备状态。".into());
    }
    Ok((value[4], u32::from_le_bytes(value[8..12].try_into().unwrap()),
        u32::from_le_bytes(value[12..16].try_into().unwrap())))
}

pub(super) fn begin_operation(value: &[u8]) -> Result<u8, String> {
    parse(value)?;
    // Never treat an unknown extension as a request to downgrade the protocol.
    Ok(if value[7] >> 4 == 2 { 5 } else { 1 })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn wire(revision: u8, state: u8) -> [u8; 16] {
        let mut value = [0u8; 16];value[..4].copy_from_slice(b"PCS1");
        value[4] = state;value[7] = revision << 4;
        value[8..12].copy_from_slice(&17u32.to_le_bytes());
        value[12..16].copy_from_slice(&23u32.to_le_bytes());value
    }
    #[test]
    fn known_legacy_and_reserved_begin_keep_their_wire_contract() {
        for revision in 0..=2 {
            let mut value = wire(revision, 3);value[6] = 13;
            assert_eq!(parse(&value).unwrap(), (3, 17, 23));
            assert_eq!(begin_operation(&value).unwrap(), if revision == 2 { 5 } else { 1 });
        }
        assert!(parse(&wire(2, 6)).is_ok());
        assert!(parse(&wire(1, 6)).is_err());
        assert!(parse(&wire(0, 6)).is_err());
    }
    #[test]
    fn unsupported_revision_and_reserved_bits_never_choose_a_command() {
        for byte in 0u8..=255 {
            let mut value = wire(0, 0);value[7] = byte;
            let accepted = byte == 0 || matches!(byte, 0x10..=0x13 | 0x20..=0x23);
            assert_eq!(begin_operation(&value).is_ok(), accepted, "byte7={byte:#x}");
        }
    }
    #[test]
    fn malformed_receipts_cannot_confirm_capability_or_visible_success() {
        let valid = wire(2, 3);
        for size in 0..16 {assert!(parse(&valid[..size]).is_err());}
        let mut oversized = valid.to_vec();oversized.push(0);assert!(parse(&oversized).is_err());
        let mut wrong_magic = valid;wrong_magic[3] = b'2';assert!(parse(&wrong_magic).is_err());
        for state in 7..=255 {assert!(parse(&wire(2, state)).is_err());}
        let mut invalid_rows = valid;invalid_rows[6] = 14;assert!(parse(&invalid_rows).is_err());
        let mut legacy = wire(0, 0);legacy[5] = 1;assert!(parse(&legacy).is_err());
    }
}
