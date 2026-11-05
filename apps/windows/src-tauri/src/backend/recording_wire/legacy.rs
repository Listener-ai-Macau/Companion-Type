// Portable V1 decoder, also compiled by the C producer / Rust consumer harness.
use std::collections::BTreeSet;
const MAX_ENCODED: u32 = 64 * 1024 * 1024;
fn fail(reason: &str) -> String {
    format!("recording metadata: {reason}")
}
fn u16le(p: &[u8], at: usize) -> u16 {
    u16::from_le_bytes(p[at..at + 2].try_into().unwrap())
}
fn u32le(p: &[u8], at: usize) -> u32 {
    u32::from_le_bytes(p[at..at + 4].try_into().unwrap())
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct LegacyEntry {
    pub capture_incomplete: bool,
    pub recording_id: u32,
    pub started_unix_s: u32,
    pub duration_ms: u32,
    pub codec: u8,
    pub sync_state: u8,
    pub source_mode: u8,
    pub total_length: u32,
    pub sha256_prefix: [u8; 8],
    pub content_crc32: u32,
}

pub(crate) fn decode_v1(p: &[u8]) -> Result<Vec<LegacyEntry>, String> {
    if p.len() < 4 || p[0] != 1 {
        return Err(fail("unsupported V1 directory schema/header"));
    }
    let count = p[1] as usize;
    let size = u16le(p, 2) as usize;
    // Current WBA journal has seven entries; the legacy WB adapter has one.
    if count > 7
        || (count == 0 && size != 0 && size != 32)
        || (count > 0 && size != 32)
        || p.len() != 4 + count * size
    {
        return Err(fail(
            "directory count, entry size or exact length is invalid",
        ));
    }
    let mut ids = BTreeSet::new();
    let mut out = Vec::with_capacity(count);
    for row in p[4..].chunks_exact(32) {
        let id = u32le(row, 0);
        let length = u32le(row, 16);
        if id == 0
            || !ids.insert(id)
            || !matches!(row[12], 1..=3)
            || row[13] > 2
            || row[14] > 2
            || row[15] & !1 != 0
            || length == 0
            || length > MAX_ENCODED
        {
            return Err(fail("invalid or duplicate V1 recording identity/state"));
        }
        out.push(LegacyEntry {
            capture_incomplete: row[15] & 1 != 0,
            recording_id: id,
            started_unix_s: u32le(row, 4),
            duration_ms: u32le(row, 8),
            codec: row[12],
            sync_state: row[13],
            source_mode: row[14],
            total_length: length,
            sha256_prefix: row[20..28].try_into().unwrap(),
            content_crc32: u32le(row, 28),
        });
    }
    Ok(out)
}
