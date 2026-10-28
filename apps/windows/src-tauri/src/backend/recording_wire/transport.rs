//! Negotiated product V2 transport. CRC protects framing, never pairing.
//! The caller uses protected GATT writes/notifications and retires this peer
//! at disconnection. An unsolicited V2 directory cannot silently enable it.
use super::{fail, u16le, u32le, u64le, Catalog, Descriptor, Page};

const STATUS_PREFIX: usize = 84; // Existing status + CCP1 capacity, unchanged.
const CAP_BYTES: usize = 32;
const REQUIRED_CAPS: u32 = 7; // sealed pull, exact physical consume, continuous
pub(crate) const STALE_SNAPSHOT: u32 = 8; // comp_segment_result_t

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Peer {
    pub(crate) uid: [u8; 12],
    pub(crate) epoch: u64,
    pub(crate) capacity: u16,
    pub(crate) max_value_bytes: u16,
    pub(crate) logical_control: bool,
    pub(crate) growing_tail: bool,
    pub(crate) batch_interval: bool,
    pub(crate) pause_control: bool,
}
impl Peer {
    pub(crate) fn from_status(status: &[u8]) -> Result<Option<Self>, String> {
        if status.len() < STATUS_PREFIX + 4 || &status[STATUS_PREFIX..STATUS_PREFIX + 4] != b"CRV2" {
            return Ok(None);
        }
        if status.len() != STATUS_PREFIX + CAP_BYTES || status[0] != 1
            || u32le(status, 12) != 0x5742_4155 {
            return Err(fail("invalid V2 capability status"));
        }
        let p = &status[STATUS_PREFIX..];
        let uid: [u8; 12] = status[20..32].try_into().unwrap();
        let epoch = u64le(p, 12);
        let capacity = u16le(p, 20);
        if u16le(p, 4) != 2 || usize::from(u16le(p, 6)) != CAP_BYTES
            || u32le(p, 8) & REQUIRED_CAPS != REQUIRED_CAPS || u32le(p, 8) & !1023 != 0 || epoch == 0
            || (u32le(p,8)&512!=0 && u32le(p,8)&256==0)
            || (u32le(p,8)&256!=0 && u32le(p,8)&192!=192)
            || (u32le(p,8)&128!=0 && u32le(p,8)&88!=88)
            || (u32le(p,8)&64!=0 && u32le(p,8)&24!=24)
            || capacity == 0 || capacity > 64 || u16le(p, 22) != 1024
            || !(248..=509).contains(&u16le(p, 24)) || u16le(p, 26) != 0
            || uid == [0; 12] || uid == [255; 12]
            || crc32fast::hash(&p[..28]) != u32le(p, 28) {
            return Err(fail("unsupported or corrupt V2 capability"));
        }
        Ok(Some(Self { uid, epoch, capacity, max_value_bytes: u16le(p,24), logical_control: u32le(p,8) & 8 != 0,
            growing_tail: u32le(p,8) & 16 != 0, batch_interval: u32le(p,8) & 32 != 0,
            pause_control: u32le(p,8) & 64 != 0 }))
    }
    pub(crate) fn validate(&self, d: &Descriptor) -> Result<(), String> {
        d.validate()?;
        if d.key.device_uid != self.uid || d.key.format_epoch != self.epoch {
            return Err(fail("directory changed recorder UID or format epoch"));
        }
        Ok(())
    }
    pub(crate) fn negotiate(&self, nonce: u32) -> Result<[u8; 32], String> {
        if nonce == 0 { return Err(fail("zero negotiation nonce")); }
        let mut p = [0; 32];
        p[0] = 2; p[1] = 0x22;
        p[4..8].copy_from_slice(&nonce.to_le_bytes());
        p[8..20].copy_from_slice(&self.uid);
        p[20..28].copy_from_slice(&self.epoch.to_le_bytes());
        let crc = crc32fast::hash(&p[..28]);
        p[28..32].copy_from_slice(&crc.to_le_bytes());
        Ok(p)
    }
    pub(crate) fn negotiate_capacity(&self, nonce:u32, mtu:u16, preferred:u16) -> Result<[u8;32],String> {
        // 219+ATT3+L2CAP4 fits the observed encrypted 2M/965us 226-byte
        // controller budget. Explicit comparison profile only: default509
        // and actual peer/MTU bounds stay unchanged; no codec or wire change.
        if ![219,244,495,509].contains(&preferred) {return Err(fail("invalid recording packet profile"));}
        let mut p=self.negotiate(nonce)?;
        if self.max_value_bytes>248 {
            let capacity=preferred.min(self.max_value_bytes).min(mtu.saturating_sub(3));
            if capacity<136 {return Err(fail("actual MTU cannot carry V2 recording"));}
            p[2..4].copy_from_slice(&capacity.to_le_bytes());
            let crc=crc32fast::hash(&p[..28]);p[28..32].copy_from_slice(&crc.to_le_bytes());
        }
        Ok(p)
    }
    pub(crate) fn pull(&self, d: &Descriptor, offset: u32, flags: u8) -> Result<Vec<u8>, String> {
        self.validate(d)?;
        if offset >= d.encoded_length || flags & !4 != 0 {
            return Err(fail("invalid V2 pull offset or flags"));
        }
        let mut p = vec![0; 32];
        p[0] = 2; p[1] = 0x21; p[2] = flags;
        p[4..8].copy_from_slice(&d.recording_id.to_le_bytes());
        p[8..16].copy_from_slice(&self.epoch.to_le_bytes());
        p[16..24].copy_from_slice(&d.key.session_id.to_le_bytes());
        p[24..28].copy_from_slice(&d.segment_index.to_le_bytes());
        p[28..32].copy_from_slice(&offset.to_le_bytes());
        Ok(p)
    }

    pub(crate) fn interval_request(&self, nonce: u32, begin: bool) -> Result<[u8;32], String> {
        if !self.batch_interval {return Err(fail("peer has no batch interval capability"));}
        let mut p=self.negotiate(nonce)?;
        p[1]=0x25;p[2]=u8::from(begin);
        let crc=crc32fast::hash(&p[..28]);p[28..32].copy_from_slice(&crc.to_le_bytes());
        Ok(p)
    }
}

pub(crate) struct Directory {
    peer: Peer,
    catalog: Catalog,
}
impl Directory {
    pub(crate) fn new(peer: &Peer, nonce: u32) -> Result<Self, String> {
        Ok(Self { peer: peer.clone(), catalog: Catalog::new(nonce)? })
    }
    pub(crate) fn request(&self) -> [u8; 16] {
        let mut p = [0; 16]; p[0] = 2; p[1] = 0x20;
        p[4..8].copy_from_slice(&self.catalog.identity.map(|(s, _)| s).unwrap_or(0).to_le_bytes());
        p[8..12].copy_from_slice(&self.catalog.nonce.to_le_bytes());
        p[12..16].copy_from_slice(&(self.catalog.entries.len() as u32).to_le_bytes());
        p
    }
    /// Ignore old callbacks by nonce. A matching invalid page is terminal;
    /// matching STALE starts a new snapshot with a new nonce, never mixes pages.
    pub(crate) fn accept(&mut self, payload: &[u8]) -> Result<bool, String> {
        if payload.len() >= 16 && &payload[..4] == b"CRE2" {
            if u32le(payload, 8) != self.catalog.nonce { return Ok(false); }
            if payload.len() != 16 || u16le(payload, 4) != 2 || u16le(payload, 6) != 16 {
                return Err(fail("invalid V2 directory error"));
            }
            return Err(if u32le(payload, 12) == STALE_SNAPSHOT {
                "录音目录正在更新，请重新取得同一快照。".into()
            } else { fail("device refused V2 directory") });
        }
        if payload.len() < 20 || payload[0] != 2 { return Ok(false); }
        if u32le(payload, 16) != self.catalog.nonce { return Ok(false); }
        let page = Page::decode(payload)?;
        if page.total > u32::from(self.peer.capacity) {
            return Err(fail("directory exceeds actual device capacity"));
        }
        for d in &page.entries { self.peer.validate(d)?; }
        let previous = self.catalog.entries.len();
        self.catalog.accept(page)?;
        Ok(self.catalog.finished() || self.catalog.entries.len() > previous)
    }
    pub(crate) fn finished(&self) -> bool { self.catalog.finished() }
    pub(crate) fn generation(&self) -> Option<u32> { self.catalog.identity.map(|(s, _)| s) }
    pub(crate) fn entries(self) -> Vec<Descriptor> { self.catalog.entries }
}

pub(crate) fn receipt_matches(expected: &[u8], payload: &[u8], peer: &Peer) -> Result<bool, String> {
    let valid = |p: &[u8]| p.len() == 84 && &p[..8] == b"CRA2\x02\x00\x54\x00"
        && p[8..20] == peer.uid && u64le(p, 20) == peer.epoch
        && crc32fast::hash(&p[..80]) == u32le(p, 80);
    if !valid(expected) { return Err(fail("consume does not belong to negotiated recorder")); }
    if payload == expected { return Ok(true); }
    if payload.len() >= 8 && &payload[..4] == b"CRA2" {
        if !valid(payload) { return Err(fail("invalid physical consume receipt")); }
        // A different complete receipt cannot confirm this request.
    }
    Ok(false)
}

/// Await one complete protected WBA recording capability publication inside
/// the existing probe budget. A base identity is not a negative capability:
/// WBA may publish it before its CRV2 suffix after encryption. Transport
/// failures, corrupt complete values and identity changes are terminal.
pub(crate) async fn read_published_status<F, Fut>(read: F) -> Result<Vec<u8>, String>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<Vec<u8>, String>>,
{
    read_status_publication(read, false).await
}

/// Protocol selection must not interpret an incomplete WBA publication as V1.
/// Non-WBA legacy status keeps its existing schema1/20B path; once a WBA UID
/// was observed in this read sequence, even that fallback is forbidden.
pub(crate) async fn read_protocol_status<F, Fut>(read: F) -> Result<Vec<u8>, String>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<Vec<u8>, String>>,
{
    read_status_publication(read, true).await
}

async fn read_status_publication<F, Fut>(mut read: F, allow_legacy: bool) -> Result<Vec<u8>, String>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<Vec<u8>, String>>,
{
    tokio::time::timeout(std::time::Duration::from_millis(2500), async {
        let mut uid = None;
        loop {
            let status = read().await?;
            if status.first().is_some_and(|schema| *schema != 0 && *schema != 1) {
                return Err(fail("unsupported recording status schema"));
            }
            if allow_legacy && status.first() == Some(&1) && status.len() >= 20
                && u32le(&status, 12) != 0x5742_4155
            {
                if uid.is_some() {
                    return Err(fail("recorder board changed during capability publication"));
                }
                return Ok(status);
            }
            if status.first() == Some(&1) && status.len() >= 36 {
                if u32le(&status, 12) != 0x5742_4155 {
                    return Err(fail("recording control requires WBA capability status"));
                }
                let observed: [u8; 12] = status[20..32].try_into().unwrap();
                if observed == [0; 12] || observed == [255; 12] {
                    return Err(fail("invalid recording status UID"));
                }
                if uid.is_some_and(|prior| prior != observed) {
                    return Err(fail("recorder UID changed during capability publication"));
                }
                uid = Some(observed);
                if status.len() >= STATUS_PREFIX + CAP_BYTES {
                    Peer::from_status(&status)?
                        .ok_or_else(|| fail("complete recording status lacks V2 capability"))?;
                    return Ok(status);
                }
            }
            // Only incomplete publications are retried, on this same peer.
            // No reconnect, clock write, START or capability synthesis.
            tokio::time::sleep(std::time::Duration::from_millis(120)).await;
        }
    })
    .await
    .map_err(|_| "设备录音能力尚未完整发布；未发送录音控制，请稍后重连。".to_string())?
}

#[cfg(test)]
mod tests;
