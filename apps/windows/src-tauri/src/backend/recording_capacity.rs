//! Read the optional WBA capacity tail. Never substitute a host ring estimate.
use crate::companion_v1::CompanionV1RecordingCapacity;

pub(super) fn parse(payload: &[u8]) -> Option<CompanionV1RecordingCapacity> {
    if payload.len() < 84 || payload[0] != 1
        || u32::from_le_bytes(payload[12..16].try_into().ok()?) != 0x5742_4155
        || &payload[36..40] != b"CCP1" || !matches!(payload[40], 1 | 3)
        || payload[41] & 1 == 0 || payload[41] & !7 != 0
    { return None; }
    let word = |offset| u32::from_le_bytes(payload[offset..offset+4].try_into().unwrap());
    let c = CompanionV1RecordingCapacity {
        layout_version: payload[40], busy: payload[41] & 2 != 0,
        confirmed_discard_supported: payload[41] & 4 != 0,
        used_entries: payload[42], max_entries: payload[43],
        catalog_generation: word(44), data_bytes: word(48), free_bytes: word(52),
        largest_free_extent: word(56), protected_bytes: word(60), consumed_bytes: word(64),
        bytes_per_second: word(68), reserve_headroom: word(72), local_limit_seconds: word(76),
        unsynced_entries: payload[80], writing_entries: payload[81], consumed_entries: payload[82],
    };
    if c.max_entries != 7 || c.used_entries > c.max_entries
        || c.data_bytes == 0 || c.data_bytes > 16 * 1024 * 1024 || c.data_bytes % 4096 != 0
        || [c.free_bytes,c.largest_free_extent,c.protected_bytes,c.consumed_bytes]
            .iter().any(|n| *n > c.data_bytes || *n % 4096 != 0)
        || c.free_bytes.checked_add(c.protected_bytes)?.checked_add(c.consumed_bytes)? != c.data_bytes
        || c.largest_free_extent > c.free_bytes
        || c.bytes_per_second != 2100 || !matches!(c.reserve_headroom, 4096 | 4108)
        || ![0,900,1800,3600].contains(&c.local_limit_seconds)
        || c.protected_bytes + c.consumed_bytes < u32::from(c.used_entries) * 4096
        || (c.used_entries == 0 && c.free_bytes != c.data_bytes)
        || u16::from(c.unsynced_entries)+u16::from(c.writing_entries)+u16::from(c.consumed_entries)!=u16::from(c.used_entries)
        || c.protected_bytes < (u32::from(c.unsynced_entries)+u32::from(c.writing_entries))*4096
        || c.consumed_bytes < u32::from(c.consumed_entries)*4096
        || payload[83]!=0
    { return None; }
    Some(c)
}

pub(super) fn check(c: &CompanionV1RecordingCapacity, seconds: u16) -> Result<(),String> {
    if c.busy { return Err("recording preflight: 设备正在录音、回收或升级，请等待结束后重试".into()); }
    if c.used_entries >= c.max_entries {
        return Err("recording preflight: 设备录音目录已满，请先同步并回收录音".into());
    }
    let wanted = (u64::from(seconds) * u64::from(c.bytes_per_second)
        + u64::from(c.reserve_headroom) + 4095) / 4096 * 4096;
    if wanted > u64::from(c.largest_free_extent) {
        return Err(format!("recording preflight: 设备连续可用空间不足以录制完整的 {} 秒；约可录 {} 秒，请先同步录音或缩短时长。未开始录音，也未覆盖旧录音",seconds,available_seconds(c)));
    }
    Ok(())
}

pub(super) fn available_seconds(c: &CompanionV1RecordingCapacity) -> u32 {
    if c.used_entries >= c.max_entries { return 0; }
    c.largest_free_extent.saturating_sub(c.reserve_headroom) / c.bytes_per_second
}

#[cfg(test)]
mod tests {
    use super::*;
    fn empty_wire() -> Vec<u8> {
        let mut p=vec![0;84];p[0]=1;p[12..16].copy_from_slice(&0x5742_4155u32.to_le_bytes());
        p[36..40].copy_from_slice(b"CCP1");p[40]=1;p[41]=1;p[43]=7;
        for (at,n) in [(48,8u32*1024*1024-8192),(52,8*1024*1024-8192),
            (56,8*1024*1024-8192),(68,2100),(72,4096),(76,1800)] {
            p[at..at+4].copy_from_slice(&n.to_le_bytes());
        } p
    }
    #[test]
    fn actual_geometry_legacy_and_malformed_are_distinct() {
        let p=empty_wire();let c=parse(&p).unwrap();
        assert_eq!(c.data_bytes,8*1024*1024-8192);assert_eq!(available_seconds(&c),3988);
        assert!(check(&c,3988).is_ok());assert!(check(&c,3989).is_err());
        assert!(parse(&p[..36]).is_none());assert!(parse(&p[..79]).is_none());
        for at in [0,12,36,40,41,43,48,52,56,68,72,76,80,81,82,83] {
            let mut broken=p.clone();broken[at]=255;assert!(parse(&broken).is_none(),"offset {at}");
        }
    }
    #[test]
    fn layout_three_exposes_shared_capacity_and_two_hour_budget() {
        let mut p=empty_wire();p[40]=3;
        for at in [48,52,56] {p[at..at+4].copy_from_slice(&0xEE0000u32.to_le_bytes());}
        let c=parse(&p).unwrap();assert_eq!(c.layout_version,3);
        assert!(check(&c,7200).is_ok());assert!(available_seconds(&c)>7200);
        // Current WBA also reserves the 12-byte COP1 header. Accept its real
        // capacity frame without dropping support for the older 4096 value.
        for at in [48,52,56] {p[at..at+4].copy_from_slice(&0xEFC000u32.to_le_bytes());}
        p[72..76].copy_from_slice(&4108u32.to_le_bytes());
        let current=parse(&p).unwrap();assert_eq!(current.reserve_headroom,4108);
        assert!(check(&current,7200).is_ok());
        p[72..76].copy_from_slice(&4109u32.to_le_bytes());assert!(parse(&p).is_none());
        p[72..76].copy_from_slice(&4108u32.to_le_bytes());
        p[40]=2;assert!(parse(&p).is_none());p[40]=4;assert!(parse(&p).is_none());
    }
    #[test]
    fn fragmentation_directory_and_reclaim_do_not_advertise_free_capacity() {
        let mut c=parse(&empty_wire()).unwrap();c.used_entries=3;c.protected_bytes=16384;
        c.consumed_bytes=8192;c.data_bytes=57344;c.free_bytes=32768;c.largest_free_extent=24576;
        assert!(check(&c,9).is_ok());assert!(check(&c,10).is_err());
        c.busy=true;assert!(check(&c,1).is_err());c.busy=false;c.used_entries=7;
        assert_eq!(available_seconds(&c),0);assert!(check(&c,1).is_err());
    }
    #[test]
    #[ignore = "requires current real C product fixture; host-only cross-language evidence"]
    fn firmware_wire_fixture() {
        let p=std::fs::read(std::env::var("COMPANION_CAPACITY_FIXTURE").unwrap()).unwrap();
        let c=parse(&p).unwrap();assert_eq!(p.len(),84);
        assert_eq!(c.data_bytes,8*1024*1024-8192);assert_eq!(c.used_entries,0);
        assert_eq!(c.free_bytes,c.data_bytes);assert_eq!(c.local_limit_seconds,1800);
        assert!(check(&c,1800).is_ok());assert!(check(&c,7200).is_err());
    }
}
