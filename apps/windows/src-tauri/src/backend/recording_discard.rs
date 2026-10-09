//! Separate, explicit user loss approval. This is never a host-copy ACK.
use crate::companion_v1::CompanionV1RecordingCapacity;
use serde::Serialize;
use std::time::Duration;

pub(super) const BYTES: usize = 84;
pub(super) const PREVIEW: u8 = 1;
pub(super) const CONFIRM: u8 = 2;
pub(super) const CANCEL: u8 = 3;
pub(super) const REFUSED: u16 = 1;
pub(super) const PENDING: u16 = 2;
pub(super) const COMPLETE: u16 = 4;
pub(super) const NO_CANDIDATE: u16 = 8;
pub(super) const CANCELLED: u16 = 16;

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct RecordingLossInfo {
    pub recording_id: u32,
    pub started_at_unix_seconds: u32,
    pub duration_ms: u32,
    pub encoded_bytes: u32,
    pub releasable_bytes: u32,
    pub available_after_seconds: u32,
    pub requested_seconds: u32,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct RecordingDiscardReport {
    pub status: String,
    pub recording: Option<RecordingLossInfo>,
    pub message: String,
}

pub(super) struct Offer {
    wire: [u8; BYTES],
    pub info: RecordingLossInfo,
}

fn word(p: &[u8], at: usize) -> u32 {
    u32::from_le_bytes(p[at..at + 4].try_into().unwrap())
}

pub(super) fn preview_request(id: u32, seconds: u16) -> [u8; BYTES] {
    let mut p = [0; BYTES];
    p[0] = 2; p[1] = PREVIEW;
    p[4..8].copy_from_slice(&id.to_le_bytes());
    p[76..80].copy_from_slice(&u32::from(seconds).to_le_bytes());
    p
}

pub(super) fn flags(p: &[u8], request: &[u8; BYTES]) -> Result<u16, String> {
    if p.len() != BYTES || p[0] != 2 || p[1] != request[1] || p[4..8] != request[4..8]
        || p[76..80] != request[76..80] {
        return Err("设备删除回执身份不匹配，请重新读取设备；不会根据这条回执回收其它录音。".into());
    }
    let flags = u16::from_le_bytes(p[2..4].try_into().unwrap());
    if ![0, REFUSED, PENDING, COMPLETE, NO_CANDIDATE, CANCELLED].contains(&flags) {
        return Err("设备删除回执状态未知，请重新读取设备。".into());
    }
    // Refusal may echo an invalid request, but success must match every byte.
    if request[1] != PREVIEW && flags != REFUSED && p[4..] != request[4..] {
        return Err("设备删除回执与已确认的录音不一致，请重新读取设备。".into());
    }
    Ok(flags)
}

pub(super) fn parse_offer(p: &[u8], request: &[u8; BYTES],
                         c: &CompanionV1RecordingCapacity) -> Result<Offer, String> {
    if flags(p, request)? != 0 || request[1] != PREVIEW || !c.confirmed_discard_supported
        || c.busy || c.writing_entries != 0 || c.consumed_entries != 0 || c.unsynced_entries == 0
        || c.bytes_per_second != 2100 || c.reserve_headroom != 4096
        || word(p, 8) == 0 || word(p, 12) == 0 || word(p, 12) > word(p, 68)
        || word(p, 48) != c.catalog_generation || word(p, 48) == 0
        || p[52..60].iter().all(|b| *b == 0) || word(p, 68) < 4096 || word(p, 68) % 4096 != 0
        || word(p, 68) > c.protected_bytes || word(p, 72) != 60_000
        || word(p, 80) % 4096 != 0 || word(p, 80) > c.data_bytes
        || word(p, 80) < c.largest_free_extent
        || u64::from(word(p, 80)) > u64::from(c.free_bytes) + u64::from(word(p, 68)) {
        return Err("设备未提供有效的单条录音删除候选，请同步录音或重新读取设备容量。".into());
    }
    Ok(Offer {
        wire: p.try_into().unwrap(),
        info: RecordingLossInfo {
            recording_id: word(p, 8), started_at_unix_seconds: word(p, 60),
            duration_ms: word(p, 64), encoded_bytes: word(p, 12), releasable_bytes: word(p, 68),
            available_after_seconds: word(p, 80).saturating_sub(c.reserve_headroom) / c.bytes_per_second,
            requested_seconds: word(p, 76),
        },
    })
}

impl Offer {
    pub(super) fn decision(&self, confirmed: bool, elapsed: Duration) -> Result<[u8; BYTES], String> {
        // Leave room for the native dialog closing and the BLE write. Firmware
        // remains authoritative at its 60s deadline, including clock wrap.
        if confirmed && elapsed >= Duration::from_secs(50) {
            return Err("这次删除确认已过期，请重新查看具体录音后再确认。未发送删除确认。".into());
        }
        let mut p = self.wire;
        p[1] = if confirmed { CONFIRM } else { CANCEL };
        p[2..4].fill(0);
        Ok(p)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> (Vec<u8>, [u8; BYTES], CompanionV1RecordingCapacity) {
        let c = CompanionV1RecordingCapacity {
            layout_version: 1, busy: false, confirmed_discard_supported: true,
            used_entries: 1, max_entries: 7, catalog_generation: 3,
            data_bytes: 57344, free_bytes: 53248, largest_free_extent: 53248,
            protected_bytes: 4096, consumed_bytes: 0, bytes_per_second: 2100,
            reserve_headroom: 4096, local_limit_seconds: 1800,
            unsynced_entries: 1, writing_entries: 0, consumed_entries: 0,
        };
        let request = preview_request(731, 60);
        let mut p = request.to_vec();
        p[16..48].fill(0xA5);
        for (at, n) in [(8, 1u32), (12, 8), (48, 3), (52, 0xDC000001), (56, 0xDC000002),
                       (60, 1700000000), (64, 20), (68, 4096), (72, 60000), (80, 57344)] {
            p[at..at + 4].copy_from_slice(&n.to_le_bytes());
        }
        (p, request, c)
    }
    #[test]
    fn loss_requires_fresh_user_decision_and_exact_completed_receipt() {
        let (p, request, c) = fixture();
        let offer = parse_offer(&p, &request, &c).unwrap();
        assert_eq!(offer.info.available_after_seconds, 25);
        assert_eq!(offer.decision(false, Duration::from_secs(120)).unwrap()[1], CANCEL);
        assert!(offer.decision(true, Duration::from_secs(50)).is_err());
        let confirmation = offer.decision(true, Duration::from_secs(49)).unwrap();
        assert_eq!(confirmation[1], CONFIRM);
        let mut completed = confirmation; completed[2] = COMPLETE as u8;
        assert_eq!(flags(&completed, &confirmation).unwrap(), COMPLETE);
        for at in 4..BYTES {
            let mut mutated = completed; mutated[at] ^= 1;
            assert!(flags(&mutated, &confirmation).is_err(), "identity byte {at}");
        }
        assert!(flags(&completed[..48], &confirmation).is_err());
        let mut legacy = completed; legacy[0] = 1;
        assert!(flags(&legacy, &confirmation).is_err());
    }
    #[test]
    fn unavailable_busy_and_invalid_candidates_never_reach_confirmation() {
        let (p, request, c) = fixture();
        for mode in 0..5 {
            let mut invalid = c.clone();
            match mode { 0 => invalid.confirmed_discard_supported = false, 1 => invalid.busy = true,
                2 => invalid.writing_entries = 1, 3 => invalid.consumed_entries = 1,
                _ => invalid.catalog_generation += 1 }
            assert!(parse_offer(&p, &request, &invalid).is_err());
        }
        let mut too_large = p.clone(); too_large[12..16].copy_from_slice(&4097u32.to_le_bytes());
        assert!(parse_offer(&too_large, &request, &c).is_err());
        for at in [0, 1, 2, 4, 48, 68, 72, 76, 80] {
            let mut invalid = p.clone(); invalid[at] ^= 128;
            assert!(parse_offer(&invalid, &request, &c).is_err(), "byte {at}");
        }
    }
    #[test]
    #[ignore = "requires current actual C link wire; simulated NOR, no physical acceptance"]
    fn real_c_offer_and_completed_receipt() {
        let dir = std::path::PathBuf::from(std::env::var("COMPANION_DISCARD_FIXTURE_DIR").unwrap());
        let p = std::fs::read(dir.join("discard-preview.bin")).unwrap();
        let completed = std::fs::read(dir.join("discard-completed.bin")).unwrap();
        let (_, request, c) = fixture();
        let offer = parse_offer(&p, &request, &c).unwrap();
        assert_eq!(offer.info.recording_id, 1);
        let confirmation = offer.decision(true, Duration::ZERO).unwrap();
        assert_eq!(flags(&completed, &confirmation).unwrap(), COMPLETE);
    }
}
