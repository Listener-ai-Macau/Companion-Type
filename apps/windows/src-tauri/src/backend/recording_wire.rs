//! Versioned recording metadata. A V2 radio peer must negotiate its actual
//! UID and durable epoch before the transport can use this directory. The
//! receiver revalidates raw files and the library before an exact consume.
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};

const DESCRIPTOR_BYTES: usize = 112;
const PAGE_HEADER_BYTES: usize = 24;
const MAX_SEGMENTS: u32 = 1024;
const MAX_ENCODED: u32 = 64 * 1024 * 1024;
const SEALED: u8 = 1;
const LAST: u8 = 2;
const RECOVERED: u8 = 4;
pub(crate) const SOURCE_MIC_SAI: u8 = 1;
const GOLDEN: &str = include_str!("recording_wire/golden.json");

fn fail(reason: &str) -> String {
    format!("recording metadata: {reason}")
}
fn u16le(p: &[u8], at: usize) -> u16 {
    u16::from_le_bytes(p[at..at + 2].try_into().unwrap())
}
fn u32le(p: &[u8], at: usize) -> u32 {
    u32::from_le_bytes(p[at..at + 4].try_into().unwrap())
}
fn u64le(p: &[u8], at: usize) -> u64 {
    u64::from_le_bytes(p[at..at + 8].try_into().unwrap())
}

mod legacy;
pub(crate) use legacy::decode_v1;
pub(crate) mod receiver;
pub(crate) mod transport;
pub(crate) mod control;
pub(crate) mod tail;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct SessionKey {
    pub(crate) device_uid: [u8; 12],
    pub(crate) format_epoch: u64,
    pub(crate) session_id: u64,
}
impl SessionKey {
    pub(crate) fn public_key(&self) -> crate::companion_v1::CompanionV1RecordingKey {
        crate::companion_v1::CompanionV1RecordingKey {
            device_uid: self.device_uid.iter().map(|b| format!("{b:02x}")).collect(),
            format_epoch: format!("{:016x}", self.format_epoch),
            session_id: format!("{:016x}", self.session_id),
        }
    }
    pub(crate) fn from_public(key: &crate::companion_v1::CompanionV1RecordingKey) -> Result<Self, String> {
        let valid = |s: &str, n| s.len() == n && s.bytes().all(|b| b.is_ascii_hexdigit());
        if !valid(&key.device_uid, 24) || !valid(&key.format_epoch, 16) || !valid(&key.session_id, 16) {
            return Err(fail("invalid persisted logical recorder key"));
        }
        let mut uid = [0; 12];
        for (i, b) in uid.iter_mut().enumerate() {
            *b = u8::from_str_radix(&key.device_uid[i*2..i*2+2],16).map_err(|_| fail("invalid UID"))?;
        }
        let epoch = u64::from_str_radix(&key.format_epoch,16).map_err(|_| fail("invalid epoch"))?;
        let session = u64::from_str_radix(&key.session_id,16).map_err(|_| fail("invalid session"))?;
        if uid == [0;12] || uid == [255;12] || epoch == 0 || session == 0 {
            return Err(fail("empty persisted logical recorder key"));
        }
        Ok(Self { device_uid: uid, format_epoch: epoch, session_id: session })
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Descriptor {
    pub(crate) key: SessionKey,
    pub(crate) recording_id: u32,
    pub(crate) segment_index: u32,
    pub(crate) sample_offset: u64,
    pub(crate) sample_count: u64,
    pub(crate) encoded_length: u32,
    pub(crate) content_crc32: u32,
    pub(crate) sha256: [u8; 32],
    pub(crate) total_segments: u32,
    pub(crate) flags: u8,
    pub(crate) codec: u8,
    pub(crate) source_mode: u8,
    pub(crate) sync_state: u8,
}
impl Descriptor {
    fn validate(&self) -> Result<(), String> {
        if self.recording_id == 0
            || self.key.format_epoch == 0
            || self.key.session_id == 0
            || self.segment_index >= MAX_SEGMENTS
            || self.codec != 3
            || self.source_mode > 2
            || self.sync_state > 2
            || self.flags & !7 != 0
            || self.flags & SEALED == 0
            || !(15..=MAX_ENCODED).contains(&self.encoded_length)
            || self.sample_count == 0
            || self.sample_count % 320 != 0
            || self.sample_offset % 320 != 0
            || self.sample_offset.checked_add(self.sample_count).is_none()
            || self.sample_count / 320 > u64::from((self.encoded_length - 12) / 3)
            || self.key.device_uid == [0; 12]
            || self.key.device_uid == [255; 12]
            || self.sha256 == [0; 32]
            || if self.flags & LAST != 0 {
                self.total_segments != self.segment_index + 1
            } else {
                self.total_segments != 0
            }
        {
            return Err(fail("invalid sealed V2 descriptor"));
        }
        Ok(())
    }
    pub(crate) fn decode(p: &[u8]) -> Result<Self, String> {
        if p.len() != DESCRIPTOR_BYTES
            || &p[..4] != b"CRS2"
            || u16le(p, 4) != 2
            || u16le(p, 6) != DESCRIPTOR_BYTES as u16
            || crc32fast::hash(&p[..108]) != u32le(p, 108)
        {
            return Err(fail("V2 descriptor schema/length/CRC mismatch"));
        }
        let d = Self {
            recording_id: u32le(p, 8),
            key: SessionKey {
                format_epoch: u64le(p, 12),
                session_id: u64le(p, 20),
                device_uid: p[96..108].try_into().unwrap(),
            },
            segment_index: u32le(p, 28),
            sample_offset: u64le(p, 32),
            sample_count: u64le(p, 40),
            encoded_length: u32le(p, 48),
            content_crc32: u32le(p, 52),
            sha256: p[56..88].try_into().unwrap(),
            total_segments: u32le(p, 88),
            flags: p[92],
            codec: p[93],
            source_mode: p[94],
            sync_state: p[95],
        };
        d.validate()?;
        Ok(d)
    }
    pub(crate) fn encode(&self) -> Result<Vec<u8>, String> {
        self.validate()?;
        let mut p = vec![0; DESCRIPTOR_BYTES];
        p[..4].copy_from_slice(b"CRS2");
        p[4..6].copy_from_slice(&2u16.to_le_bytes());
        p[6..8].copy_from_slice(&(DESCRIPTOR_BYTES as u16).to_le_bytes());
        for (at, n) in [
            (8, self.recording_id),
            (28, self.segment_index),
            (48, self.encoded_length),
            (52, self.content_crc32),
            (88, self.total_segments),
        ] {
            p[at..at + 4].copy_from_slice(&n.to_le_bytes());
        }
        for (at, n) in [
            (12, self.key.format_epoch),
            (20, self.key.session_id),
            (32, self.sample_offset),
            (40, self.sample_count),
        ] {
            p[at..at + 8].copy_from_slice(&n.to_le_bytes());
        }
        p[56..88].copy_from_slice(&self.sha256);
        p[92] = self.flags;
        p[93] = self.codec;
        p[94] = self.source_mode;
        p[95] = self.sync_state;
        p[96..108].copy_from_slice(&self.key.device_uid);
        let crc = crc32fast::hash(&p[..108]);
        p[108..].copy_from_slice(&crc.to_le_bytes());
        Ok(p)
    }
    // Sync state may legitimately advance without changing the immutable segment.
    fn same_content(&self, other: &Self) -> bool {
        let mut copy = other.clone();
        copy.sync_state = self.sync_state;
        *self == copy
    }
    pub(crate) fn verify_payload(&self, payload: &[u8]) -> Result<(), String> {
        self.validate()?;
        if payload.len() != self.encoded_length as usize
            || crc32fast::hash(payload) != self.content_crc32
            || Sha256::digest(payload).as_slice() != self.sha256
        {
            return Err(fail("segment payload length/CRC/SHA mismatch"));
        }
        let mut reader=super::cop1::Reader::new(payload,self.sample_offset,false)?;
        if reader.frame_ms!=20 || reader.source_rate!=16000 {
            return Err(fail("V2 requires mono 16 kHz / 20 ms COP1"));
        }
        while let Some(record)=reader.next()? {
            if let super::cop1::Record::Audio(packet)=record {
                if packet.len()>400 {return Err(fail("invalid complete COP1 packet"));}
            }
        }
        let summary=reader.finish(self.flags & RECOVERED!=0)?;
        if summary.frames * 320 != self.sample_count || summary.encoded_bytes!=u64::from(self.encoded_length)
            || (summary.ended_paused && self.flags & LAST==0) {
            return Err(fail("segment frame count disagrees with sample count"));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct Page {
    snapshot: u32,
    nonce: u32,
    start: u32,
    total: u32,
    entries: Vec<Descriptor>,
}
impl Page {
    fn decode(p: &[u8]) -> Result<Self, String> {
        if p.len() < PAGE_HEADER_BYTES
            || p[0] != 2
            || p[1] > 2
            || u16le(p, 2) != DESCRIPTOR_BYTES as u16
            || p.len() != PAGE_HEADER_BYTES + usize::from(p[1]) * DESCRIPTOR_BYTES
        {
            return Err(fail("invalid V2 page framing"));
        }
        let mut crc = crc32fast::Hasher::new();
        crc.update(&p[..20]);
        crc.update(&p[24..]);
        if crc.finalize() != u32le(p, 20) {
            return Err(fail("V2 page CRC mismatch"));
        }
        let page = Self {
            snapshot: u32le(p, 4),
            start: u32le(p, 8),
            total: u32le(p, 12),
            nonce: u32le(p, 16),
            entries: p[24..]
                .chunks_exact(DESCRIPTOR_BYTES)
                .map(Descriptor::decode)
                .collect::<Result<_, _>>()?,
        };
        if page.snapshot == 0
            || page.nonce == 0
            || page.total > MAX_SEGMENTS
            || page.start > page.total
            || page.entries.len() as u32 > page.total - page.start
            || (page.total != 0 && page.entries.is_empty())
        {
            return Err(fail("invalid V2 page snapshot/cursor"));
        }
        Ok(page)
    }
    fn encode(&self) -> Result<Vec<u8>, String> {
        if self.entries.len() > 2 {
            return Err(fail("too many page entries"));
        }
        let mut p = vec![0; 24];
        p[0] = 2;
        p[1] = self.entries.len() as u8;
        p[2..4].copy_from_slice(&(DESCRIPTOR_BYTES as u16).to_le_bytes());
        for (at, n) in [
            (4, self.snapshot),
            (8, self.start),
            (12, self.total),
            (16, self.nonce),
        ] {
            p[at..at + 4].copy_from_slice(&n.to_le_bytes());
        }
        for d in &self.entries {
            p.extend(d.encode()?);
        }
        let mut crc = crc32fast::Hasher::new();
        crc.update(&p[..20]);
        crc.update(&p[24..]);
        p[20..24].copy_from_slice(&crc.finalize().to_le_bytes());
        Self::decode(&p)?;
        Ok(p)
    }
}

struct Catalog {
    nonce: u32,
    identity: Option<(u32, u32)>,
    entries: Vec<Descriptor>,
    pages: BTreeMap<u32, Page>,
}
impl Catalog {
    fn new(nonce: u32) -> Result<Self, String> {
        if nonce == 0 {
            return Err(fail("zero catalog request nonce"));
        }
        Ok(Self {
            nonce,
            identity: None,
            entries: Vec::new(),
            pages: BTreeMap::new(),
        })
    }
    fn accept(&mut self, page: Page) -> Result<(), String> {
        // Keep the invariant even for callers that construct an in-memory Page.
        Page::decode(&page.encode()?)?;
        if page.nonce != self.nonce {
            return Err(fail("catalog nonce does not match request"));
        }
        let identity = (page.snapshot, page.total);
        if self.identity.is_some_and(|old| old != identity) {
            return Err(fail("catalog changed; restart the snapshot"));
        }
        if let Some(old) = self.pages.get(&page.start) {
            return if *old == page {
                Ok(())
            } else {
                Err(fail("conflicting catalog page replay"))
            };
        }
        if page.start != self.entries.len() as u32 {
            return Err(fail("missing or out-of-order catalog page"));
        }
        let mut ids: BTreeSet<_> = self
            .entries
            .iter()
            .map(|d| (d.key.device_uid, d.key.format_epoch, d.recording_id))
            .collect();
        for d in &page.entries {
            if !ids.insert((d.key.device_uid, d.key.format_epoch, d.recording_id)) {
                return Err(fail("duplicate physical recording in catalog"));
            }
        }
        self.identity = Some(identity);
        self.entries.extend(page.entries.clone());
        self.pages.insert(page.start, page);
        Ok(())
    }
    fn finished(&self) -> bool {
        self.identity
            .is_some_and(|(_, total)| self.entries.len() == total as usize)
    }
}

#[derive(Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct GroupPlan {
    key: SessionKey,
    known_segments: u32,
    expected_segments: Option<u32>,
    missing_segments: Vec<u32>,
    verified_segments: u32,
    sample_count: u64,
    metadata_complete: bool,
    pub(crate) payloads_complete: bool,
    capture_incomplete: bool,
    capture_complete: bool,
}
impl GroupPlan {
    /// A complete sealed catalogue has no growing tail to free space for.
    /// Limited/background slices still reclaim each durable segment promptly.
    pub(crate) fn may_batch_reclaim(&self, segment_limit: Option<usize>) -> bool {
        segment_limit.is_none() && self.metadata_complete
    }
}
fn plan_group(items: &[Descriptor], verified: &BTreeSet<u32>) -> Result<GroupPlan, String> {
    let first = items.first().ok_or_else(|| fail("empty session group"))?;
    let mut segments = BTreeMap::<u32, &Descriptor>::new();
    let mut ids = BTreeMap::new();
    let mut expected = None;
    for d in items {
        d.validate()?;
        if d.key != first.key || d.source_mode != first.source_mode {
            return Err(fail("mixed device/epoch/session or meeting mode"));
        }
        if let Some(old) = segments.insert(d.segment_index, d) {
            if !old.same_content(d) {
                return Err(fail("conflicting segment index/content"));
            }
        }
        if let Some(old) = ids.insert(d.recording_id, d.segment_index) {
            if old != d.segment_index {
                return Err(fail("one physical recording assigned to multiple segments"));
            }
        }
        if d.flags & LAST != 0 {
            if expected.is_some_and(|n| n != d.total_segments) {
                return Err(fail("conflicting terminal segment count"));
            }
            expected = Some(d.total_segments);
        }
    }
    if expected.is_some_and(|n| segments.keys().any(|index| *index >= n)) {
        return Err(fail("segment exists after terminal segment"));
    }
    let end = expected.unwrap_or_else(|| segments.keys().next_back().unwrap() + 1);
    let missing: Vec<_> = (0..end).filter(|n| !segments.contains_key(n)).collect();
    let mut previous: Option<&Descriptor> = None;
    let mut samples = 0u64;
    for d in segments.values() {
        if d.segment_index == 0 && d.sample_offset != 0 {
            return Err(fail("first segment has a nonzero sample offset"));
        }
        if let Some(p) = previous {
            let previous_end = p.sample_offset + p.sample_count;
            if d.sample_offset < previous_end
                || (d.segment_index == p.segment_index + 1 && d.sample_offset != previous_end)
            {
                return Err(fail(
                    "overlapping segments or sample gap between adjacent segments",
                ));
            }
        }
        samples = samples
            .checked_add(d.sample_count)
            .ok_or_else(|| fail("group sample overflow"))?;
        previous = Some(d);
    }
    let metadata_complete = expected.is_some() && missing.is_empty();
    let count = segments
        .values()
        .filter(|d| verified.contains(&d.recording_id))
        .count() as u32;
    let recovered = segments.values().any(|d| d.flags & RECOVERED != 0);
    Ok(GroupPlan {
        key: first.key.clone(),
        known_segments: segments.len() as u32,
        expected_segments: expected,
        missing_segments: missing,
        verified_segments: count,
        sample_count: samples,
        metadata_complete,
        payloads_complete: metadata_complete && count == segments.len() as u32,
        capture_incomplete: recovered,
        capture_complete: metadata_complete && count == segments.len() as u32 && !recovered,
    })
}

fn unhex(s: &str) -> Result<Vec<u8>, String> {
    if s.len() % 2 != 0 {
        return Err(fail("bad golden hex"));
    }
    s.as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            std::str::from_utf8(pair)
                .ok()
                .and_then(|s| u8::from_str_radix(s, 16).ok())
                .ok_or_else(|| fail("bad golden hex"))
        })
        .collect()
}

fn exercise() -> Result<serde_json::Value, String> {
    let golden: serde_json::Value =
        serde_json::from_str(GOLDEN).map_err(|_| fail("bad golden fixture"))?;
    let hex = |key: &str| unhex(golden[key].as_str().ok_or_else(|| fail("missing golden"))?);
    let legacy = hex("v1Hex")?;
    let payload = hex("payloadHex")?;
    let descriptors: Vec<_> = golden["descriptorsHex"]
        .as_array()
        .ok_or_else(|| fail("missing descriptors"))?
        .iter()
        .map(|v| unhex(v.as_str().unwrap()).and_then(|b| Descriptor::decode(&b)))
        .collect::<Result<_, _>>()?;
    let pages: Vec<_> = golden["pagesHex"]
        .as_array()
        .ok_or_else(|| fail("missing pages"))?
        .iter()
        .map(|v| unhex(v.as_str().unwrap()).and_then(|b| Page::decode(&b)))
        .collect::<Result<_, _>>()?;
    let mut checks = Vec::new();
    macro_rules! check {
        ($name:expr,$ok:expr) => {
            if !$ok {
                return Err(fail($name));
            }
            checks.push($name);
        };
    }
    let entries = decode_v1(&legacy)?;
    check!(
        "legacy-unix-time-preserved",
        entries.len() == 1
            && entries[0].started_unix_s == 1_791_234_567
            && entries[0].recording_id == 41
    );
    check!(
        "empty-legacy-directory",
        decode_v1(&[1, 0, 0, 0])?.is_empty() && decode_v1(&[1, 0, 32, 0])?.is_empty()
    );
    check!(
        "legacy-truncation-refused",
        decode_v1(&legacy[..legacy.len() - 1]).is_err()
    );
    let mut bad = legacy.clone();
    bad.push(0);
    check!("legacy-trailing-bytes-refused", decode_v1(&bad).is_err());
    bad = legacy.clone();
    bad[2] = 64;
    check!("legacy-extension-not-guessed", decode_v1(&bad).is_err());
    bad = legacy.clone();
    bad[1] = 2;
    bad.extend_from_slice(&legacy[4..]);
    check!("duplicate-recording-id-refused", decode_v1(&bad).is_err());
    bad = legacy.clone();
    bad[19] = 2;
    check!("legacy-unknown-flags-refused", decode_v1(&bad).is_err());
    bad = legacy.clone();
    bad[19] = 1;
    check!(
        "legacy-recovery-flag",
        decode_v1(&bad)?[0].capture_incomplete
    );
    check!(
        "v2-cannot-enter-v1-without-capability",
        decode_v1(&unhex(golden["pagesHex"][0].as_str().unwrap())?).is_err()
    );
    for (i, d) in descriptors.iter().enumerate() {
        check!(
            "c-rust-descriptor-byte-parity",
            d.encode()? == unhex(golden["descriptorsHex"][i].as_str().unwrap())?
        );
        d.verify_payload(&payload)?;
    }
    for (i, p) in pages.iter().enumerate() {
        check!(
            "c-rust-page-byte-parity",
            p.encode()? == unhex(golden["pagesHex"][i].as_str().unwrap())?
        );
    }
    bad = descriptors[0].encode()?;
    bad[60] ^= 1;
    check!(
        "descriptor-crc-refuses-tampering",
        Descriptor::decode(&bad).is_err()
    );
    bad = pages[0].encode()?;
    bad[4] ^= 1;
    check!("page-crc-binds-header", Page::decode(&bad).is_err());
    let mut invalid = descriptors[0].clone();
    invalid.key.format_epoch = 0;
    check!("missing-format-epoch-refused", invalid.encode().is_err());
    invalid = descriptors[0].clone();
    invalid.flags = 0;
    check!("unsealed-segment-refused", invalid.encode().is_err());
    invalid = descriptors[2].clone();
    invalid.total_segments = 4;
    check!("terminal-count-must-match-index", invalid.encode().is_err());
    invalid = descriptors[0].clone();
    invalid.sample_offset = u64::MAX - 255;
    check!("sample-offset-overflow-refused", invalid.encode().is_err());
    let mut catalog = Catalog::new(pages[0].nonce)?;
    catalog.accept(pages[0].clone())?;
    check!("partial-catalog-not-complete", !catalog.finished());
    catalog.accept(pages[0].clone())?;
    check!(
        "identical-page-replay-idempotent",
        catalog.entries.len() == 2
    );
    let mut changed = pages[1].clone();
    changed.snapshot += 1;
    check!(
        "snapshot-change-refused",
        catalog.accept(changed).is_err() && catalog.entries.len() == 2
    );
    changed = pages[1].clone();
    changed.nonce += 1;
    check!(
        "cross-request-page-refused",
        catalog.accept(changed).is_err()
    );
    let mut empty = Catalog::new(pages[0].nonce)?;
    check!(
        "missing-first-page-refused",
        empty.accept(pages[1].clone()).is_err()
    );
    catalog.accept(pages[1].clone())?;
    check!("all-catalog-pages-complete", catalog.finished());
    let verified: BTreeSet<_> = descriptors.iter().map(|d| d.recording_id).collect();
    let mut shuffled = vec![
        descriptors[2].clone(),
        descriptors[0].clone(),
        descriptors[1].clone(),
        descriptors[1].clone(),
    ];
    let plan = plan_group(&shuffled, &verified)?;
    check!(
        "out-of-order-and-repeat-group",
        plan.known_segments == 3
            && plan.metadata_complete
            && plan.payloads_complete
            && plan.sample_count == 960
    );
    check!(
        "metadata-only-cannot-imply-payload-complete",
        !plan_group(&shuffled, &BTreeSet::new())?.payloads_complete
    );
    let missing = plan_group(&[descriptors[0].clone(), descriptors[2].clone()], &verified)?;
    check!(
        "missing-middle-explicit",
        missing.missing_segments == [1] && !missing.payloads_complete
    );
    let missing = plan_group(&descriptors[1..], &verified)?;
    check!(
        "missing-first-explicit",
        missing.missing_segments == [0] && !missing.metadata_complete
    );
    check!(
        "unsealed-session-tail-remains-open",
        plan_group(&descriptors[..2], &verified)?
            .expected_segments
            .is_none()
    );
    shuffled[0].flags |= RECOVERED;
    let recovered = plan_group(&shuffled, &verified)?;
    check!(
        "recovered-capture-never-full-acceptance",
        recovered.payloads_complete && recovered.capture_incomplete && !recovered.capture_complete
    );
    shuffled = descriptors.clone();
    shuffled[1].sample_offset = 0;
    check!("overlap-refused", plan_group(&shuffled, &verified).is_err());
    shuffled = descriptors.clone();
    shuffled[1].sample_offset += 320;
    check!(
        "adjacent-sample-gap-refused",
        plan_group(&shuffled, &verified).is_err()
    );
    shuffled = descriptors.clone();
    shuffled[1].key.device_uid[0] ^= 1;
    check!(
        "different-device-refused",
        plan_group(&shuffled, &verified).is_err()
    );
    shuffled = descriptors.clone();
    shuffled[1].key.format_epoch += 1;
    check!(
        "same-id-new-format-epoch-isolated",
        plan_group(&shuffled, &verified).is_err()
    );
    shuffled = descriptors.clone();
    shuffled[1].key.session_id += 1;
    check!(
        "different-session-refused",
        plan_group(&shuffled, &verified).is_err()
    );
    shuffled = descriptors.clone();
    let mut conflict = descriptors[1].clone();
    conflict.sha256[0] ^= 1;
    shuffled.push(conflict);
    check!(
        "conflicting-segment-refused",
        plan_group(&shuffled, &verified).is_err()
    );
    shuffled = descriptors.clone();
    shuffled[1].recording_id = descriptors[0].recording_id;
    check!(
        "physical-id-cannot-cover-two-segments",
        plan_group(&shuffled, &verified).is_err()
    );
    bad = payload.clone();
    bad[14] ^= 1;
    check!(
        "payload-identity-mismatch-refused",
        descriptors[0].verify_payload(&bad).is_err()
    );
    invalid = descriptors[0].clone();
    invalid.sample_count = 640;
    check!("impossible-frame-count-refused", invalid.encode().is_err());
    bad = payload.clone();
    bad[12] = 2;
    invalid = descriptors[0].clone();
    invalid.content_crc32 = crc32fast::hash(&bad);
    invalid.sha256 = Sha256::digest(&bad).into();
    check!(
        "hashed-but-truncated-opus-packet-refused",
        invalid.verify_payload(&bad).is_err()
    );
    bad = payload.clone();
    bad[6] = 10;
    invalid.content_crc32 = crc32fast::hash(&bad);
    invalid.sha256 = Sha256::digest(&bad).into();
    check!(
        "hashed-but-wrong-cop1-format-refused",
        invalid.verify_payload(&bad).is_err()
    );
    bad = payload.clone();
    bad.extend_from_slice(&payload[12..]);
    invalid = descriptors[0].clone();
    invalid.encoded_length = bad.len() as u32;
    invalid.content_crc32 = crc32fast::hash(&bad);
    invalid.sha256 = Sha256::digest(&bad).into();
    check!(
        "hashed-payload-still-needs-exact-frame-count",
        invalid.verify_payload(&bad).is_err()
    );
    let empty_page = Page {
        snapshot: 9,
        nonce: 17,
        start: 0,
        total: 0,
        entries: Vec::new(),
    };
    let mut empty_catalog = Catalog::new(17)?;
    empty_catalog.accept(Page::decode(&empty_page.encode()?)?)?;
    check!(
        "empty-catalog-is-not-a-complete-recording",
        empty_catalog.finished() && plan_group(&empty_catalog.entries, &verified).is_err()
    );
    let mut different = descriptors[0].clone();
    different.sync_state = 2;
    check!(
        "transfer-state-does-not-change-segment-content",
        plan_group(&[descriptors[0].clone(), different], &verified)?.known_segments == 1
    );
    Ok(
        serde_json::json!({"schema":"companion.recording-wire.contract.v2","result":"PASS_SOFTWARE_CONTRACT_ONLY", "checks":checks,
        "goldenSha256":format!("{:x}",Sha256::digest(GOLDEN.as_bytes())),"completeFixturePlan":plan,"recoveredFixturePlan":recovered,
        "fixtureSource":"synthetic-contract-only","radioV2Enabled":false,"journalV2Enabled":false,"ackOrEraseExecuted":false,
        "hardwareAcceptance":"NOT_RUN","fullChainAcceptance":"NOT_RUN"}),
    )
}
pub(crate) fn verify(output: &Path) -> Result<serde_json::Value, String> {
    // Refuse an existing directory before writing anything or opening app state.
    fs::create_dir(output).map_err(|_| fail("probe requires a fresh output folder"))?;
    let report = exercise()?;
    fs::write(
        output.join("result.json"),
        serde_json::to_vec_pretty(&report).map_err(|_| fail("serialize probe"))?,
    )
    .map_err(|_| fail("write probe receipt"))?;
    Ok(report)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn c_rust_wire_and_group_contract() {
        exercise().unwrap();
    }
    #[test]
    fn every_truncated_descriptor_and_page_is_refused() {
        let fixture: serde_json::Value = serde_json::from_str(GOLDEN).unwrap();
        let d = unhex(fixture["descriptorsHex"][0].as_str().unwrap()).unwrap();
        for n in 0..d.len() {
            assert!(Descriptor::decode(&d[..n]).is_err(), "descriptor {n}");
        }
        let p = unhex(fixture["pagesHex"][0].as_str().unwrap()).unwrap();
        for n in 0..p.len() {
            assert!(Page::decode(&p[..n]).is_err(), "page {n}");
        }
    }
}
