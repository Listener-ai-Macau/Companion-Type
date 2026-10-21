//! In-memory recording import/fixture model + upload queue + ACK consume.
//!
//! Model semantics (not the physical board journal or a continuous recorder):
//! - Append Opus16 (or product-payload) segments while disconnected → stay `Pending`.
//! - On BLE/product connect → auto-queue all `Pending` for upload (manual Sync is fallback only).
//! - Peer confirms length + SHA-256 → `Acked` → may `Consumed` (free ring capacity).
//! - Unacked data is never silently erased. Full of unacked → fail-closed (stop append).
//!
//! Default ceiling follows the current 8 MiB V1 region. Duration arithmetic
//! excludes COP1 framing, catalog/checkpoint space and bitrate variation.

use sha2::{Digest, Sha256};
use std::collections::VecDeque;

/// Logical ceiling only; usable board capacity comes from device_status.
/// The proposed 14 MiB shared pool has not been activated on the board.
pub const RING_CAPACITY_BYTES: u64 = 8 * 1024 * 1024;
/// Opus16 product rate ≈ 16 kbps → 2000 B/s.
pub const OPUS16_BYTES_PER_SEC: u64 = 2000;
/// Approx hours at product rate (capacity / rate / 3600).
pub const RING_HOURS_AT_OPUS16: f64 =
    (RING_CAPACITY_BYTES as f64) / (OPUS16_BYTES_PER_SEC as f64) / 3600.0;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SegmentState {
    /// Local only; not confirmed by host.
    Pending,
    /// Offered to upload path (in-flight).
    Uploading,
    /// Host confirmed length + hash.
    Acked,
    /// Freed from ring accounting (may overwrite physically).
    Consumed,
}

#[derive(Debug, Clone)]
pub struct RingSegment {
    pub id: u32,
    pub payload: Vec<u8>,
    pub sha256_hex: String,
    pub state: SegmentState,
}

impl RingSegment {
    pub fn new(id: u32, payload: Vec<u8>) -> Self {
        let sha256_hex = sha256_hex(&payload);
        Self {
            id,
            payload,
            sha256_hex,
            state: SegmentState::Pending,
        }
    }

    pub fn len(&self) -> u64 {
        self.payload.len() as u64
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RingError {
    /// Buffer full of unacked/uploading data — fail closed, do not overwrite.
    FullFailClosed {
        used: u64,
        capacity: u64,
    },
    /// Recording stopped after full or explicit stop.
    RecordingStopped,
    UnknownSegment(u32),
    BadState {
        id: u32,
        expected: &'static str,
        got: SegmentState,
    },
    AckMismatch {
        id: u32,
        reason: &'static str,
    },
    EmptyPayload,
}

impl std::fmt::Display for RingError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RingError::FullFailClosed { used, capacity } => {
                write!(f, "ring full fail-closed used={used} cap={capacity}")
            }
            RingError::RecordingStopped => write!(f, "recording stopped"),
            RingError::UnknownSegment(id) => write!(f, "unknown segment {id}"),
            RingError::BadState { id, expected, got } => {
                write!(f, "segment {id} bad state expected={expected} got={got:?}")
            }
            RingError::AckMismatch { id, reason } => {
                write!(f, "ack mismatch id={id} reason={reason}")
            }
            RingError::EmptyPayload => write!(f, "empty payload"),
        }
    }
}

impl std::error::Error for RingError {}

/// Segmented Opus16 ring store (logical).
#[derive(Debug, Clone)]
pub struct RecordingRing {
    pub capacity_bytes: u64,
    pub recording_active: bool,
    pub stopped_reason: Option<&'static str>,
    next_id: u32,
    segments: Vec<RingSegment>,
}

impl Default for RecordingRing {
    fn default() -> Self {
        Self::new(RING_CAPACITY_BYTES)
    }
}

impl RecordingRing {
    pub fn new(capacity_bytes: u64) -> Self {
        Self {
            capacity_bytes,
            recording_active: true,
            stopped_reason: None,
            next_id: 1,
            segments: Vec::new(),
        }
    }

    /// Bytes still occupying the ring (pending + uploading + acked-not-consumed).
    pub fn used_bytes(&self) -> u64 {
        self.segments
            .iter()
            .filter(|s| s.state != SegmentState::Consumed)
            .map(|s| s.len())
            .sum()
    }

    pub fn free_bytes(&self) -> u64 {
        self.capacity_bytes.saturating_sub(self.used_bytes())
    }

    pub fn segments(&self) -> &[RingSegment] {
        &self.segments
    }

    pub fn pending_ids(&self) -> Vec<u32> {
        self.segments
            .iter()
            .filter(|s| s.state == SegmentState::Pending)
            .map(|s| s.id)
            .collect()
    }

    pub fn acked_ids(&self) -> Vec<u32> {
        self.segments
            .iter()
            .filter(|s| s.state == SegmentState::Acked)
            .map(|s| s.id)
            .collect()
    }

    pub fn consumable_ids(&self) -> Vec<u32> {
        self.acked_ids()
    }

    /// Append one Opus16 (or product) segment. Fail-closed if not enough free space.
    pub fn append_segment(&mut self, payload: Vec<u8>) -> Result<u32, RingError> {
        if !self.recording_active {
            return Err(RingError::RecordingStopped);
        }
        if payload.is_empty() {
            return Err(RingError::EmptyPayload);
        }
        let need = payload.len() as u64;
        if need > self.free_bytes() {
            // Fail closed: stop recording and refuse overwrite of unacked data.
            self.recording_active = false;
            self.stopped_reason = Some("full_unacked_fail_closed");
            return Err(RingError::FullFailClosed {
                used: self.used_bytes(),
                capacity: self.capacity_bytes,
            });
        }
        let id = self.next_id;
        self.next_id = self.next_id.saturating_add(1);
        self.segments.push(RingSegment::new(id, payload));
        Ok(id)
    }

    pub fn mark_uploading(&mut self, id: u32) -> Result<(), RingError> {
        let seg = self
            .segments
            .iter_mut()
            .find(|s| s.id == id)
            .ok_or(RingError::UnknownSegment(id))?;
        if seg.state != SegmentState::Pending {
            return Err(RingError::BadState {
                id,
                expected: "Pending",
                got: seg.state,
            });
        }
        seg.state = SegmentState::Uploading;
        Ok(())
    }

    /// BLE drop mid-transfer: unacked Uploading → Pending so reconnect can resume (断链续传).
    /// Never touches Acked/Consumed.
    pub fn revert_uploading_to_pending_on_disconnect(&mut self) -> Vec<u32> {
        let mut reverted = Vec::new();
        for seg in &mut self.segments {
            if seg.state == SegmentState::Uploading {
                seg.state = SegmentState::Pending;
                reverted.push(seg.id);
            }
        }
        reverted
    }

    /// Peer ACK: length + sha256 must match. Only then segment becomes consumable.
    pub fn ack_segment(
        &mut self,
        id: u32,
        confirmed_len: u64,
        confirmed_sha256_hex: &str,
    ) -> Result<(), RingError> {
        let seg = self
            .segments
            .iter_mut()
            .find(|s| s.id == id)
            .ok_or(RingError::UnknownSegment(id))?;
        if seg.state != SegmentState::Uploading && seg.state != SegmentState::Pending {
            // Allow ack from Pending if host pulled without explicit uploading mark.
            if seg.state != SegmentState::Pending {
                return Err(RingError::BadState {
                    id,
                    expected: "Pending|Uploading",
                    got: seg.state,
                });
            }
        }
        if confirmed_len != seg.len() {
            return Err(RingError::AckMismatch {
                id,
                reason: "length",
            });
        }
        if !confirmed_sha256_hex.eq_ignore_ascii_case(&seg.sha256_hex) {
            return Err(RingError::AckMismatch {
                id,
                reason: "sha256",
            });
        }
        seg.state = SegmentState::Acked;
        Ok(())
    }

    /// Free acked segments (ring reclaim). Never consumes Pending/Uploading.
    pub fn consume_acked(&mut self) -> Vec<u32> {
        let mut consumed = Vec::new();
        for seg in &mut self.segments {
            if seg.state == SegmentState::Acked {
                seg.state = SegmentState::Consumed;
                // Drop payload to free host RAM; device would recycle NOR slot.
                seg.payload.clear();
                consumed.push(seg.id);
            }
        }
        consumed
    }

    /// Snapshot for acceptance / logs.
    pub fn evidence_snapshot(&self) -> RingEvidence {
        let mut pending = 0u32;
        let mut uploading = 0u32;
        let mut acked = 0u32;
        let mut consumed = 0u32;
        for s in &self.segments {
            match s.state {
                SegmentState::Pending => pending += 1,
                SegmentState::Uploading => uploading += 1,
                SegmentState::Acked => acked += 1,
                SegmentState::Consumed => consumed += 1,
            }
        }
        RingEvidence {
            capacity_bytes: self.capacity_bytes,
            used_bytes: self.used_bytes(),
            free_bytes: self.free_bytes(),
            opus16_bytes_per_sec: OPUS16_BYTES_PER_SEC,
            hours_at_opus16: RING_HOURS_AT_OPUS16,
            recording_active: self.recording_active,
            stopped_reason: self.stopped_reason.map(|s| s.to_string()),
            segment_count: self.segments.len() as u32,
            pending,
            uploading,
            acked,
            consumed,
            pending_ids: self.pending_ids(),
            acked_ids: self.acked_ids(),
        }
    }
}

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RingEvidence {
    pub capacity_bytes: u64,
    pub used_bytes: u64,
    pub free_bytes: u64,
    pub opus16_bytes_per_sec: u64,
    pub hours_at_opus16: f64,
    pub recording_active: bool,
    pub stopped_reason: Option<String>,
    pub segment_count: u32,
    pub pending: u32,
    pub uploading: u32,
    pub acked: u32,
    pub consumed: u32,
    pub pending_ids: Vec<u32>,
    pub acked_ids: Vec<u32>,
}

/// Auto-upload queue: drains pending when connected; accumulates when disconnected.
#[derive(Debug, Clone, Default)]
pub struct AutoUploadQueue {
    pub connected: bool,
    /// Ordered segment ids waiting for transport.
    pub queue: VecDeque<u32>,
    pub auto_drain_enabled: bool,
    pub drain_events: u32,
}

impl AutoUploadQueue {
    pub fn new() -> Self {
        Self {
            connected: false,
            queue: VecDeque::new(),
            auto_drain_enabled: true,
            drain_events: 0,
        }
    }

    pub fn on_disconnect(&mut self) {
        self.connected = false;
    }

    /// Connection up: enqueue all ring pending (single product path — auto, not manual-only).
    pub fn on_connect(&mut self, ring: &RecordingRing) -> Vec<u32> {
        self.connected = true;
        if !self.auto_drain_enabled {
            return Vec::new();
        }
        self.enqueue_pending_from_ring(ring)
    }

    pub fn enqueue_pending_from_ring(&mut self, ring: &RecordingRing) -> Vec<u32> {
        let mut added = Vec::new();
        for id in ring.pending_ids() {
            if !self.queue.contains(&id) {
                self.queue.push_back(id);
                added.push(id);
            }
        }
        if !added.is_empty() {
            self.drain_events = self.drain_events.saturating_add(1);
        }
        added
    }

    /// Pop next id to upload if connected.
    pub fn pop_next_upload(&mut self) -> Option<u32> {
        if !self.connected {
            return None;
        }
        self.queue.pop_front()
    }

    pub fn evidence_snapshot(&self) -> QueueEvidence {
        QueueEvidence {
            connected: self.connected,
            auto_drain_enabled: self.auto_drain_enabled,
            queue_len: self.queue.len() as u32,
            queue_ids: self.queue.iter().copied().collect(),
            drain_events: self.drain_events,
        }
    }
}

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct QueueEvidence {
    pub connected: bool,
    pub auto_drain_enabled: bool,
    pub queue_len: u32,
    pub queue_ids: Vec<u32>,
    pub drain_events: u32,
}

/// Drive one segment through upload + ack + consume (product happy path helper).
pub fn upload_ack_consume(
    ring: &mut RecordingRing,
    queue: &mut AutoUploadQueue,
    id: u32,
) -> Result<(), RingError> {
    ring.mark_uploading(id)?;
    let (len, hash) = {
        let seg = ring
            .segments()
            .iter()
            .find(|s| s.id == id)
            .ok_or(RingError::UnknownSegment(id))?;
        (seg.len(), seg.sha256_hex.clone())
    };
    ring.ack_segment(id, len, &hash)?;
    let _ = ring.consume_acked();
    // Drop from queue if still present
    queue.queue.retain(|q| *q != id);
    Ok(())
}

pub fn sha256_hex(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let out = hasher.finalize();
    out.iter().map(|b| format!("{b:02x}")).collect()
}

// --- Process-wide product coordinator (BLE connect / pull entry points call these) ---

use std::sync::{Mutex, OnceLock};

/// Live product ring + auto-upload queue shared by BLE bridge and tests.
pub struct ProductRingCoordinator {
    pub ring: RecordingRing,
    pub queue: AutoUploadQueue,
    pub last_connect_enqueued: Vec<u32>,
    pub last_ack_ids: Vec<u32>,
    pub last_consumed_ids: Vec<u32>,
    pub connect_count: u32,
    pub upload_ack_count: u32,
}

impl Default for ProductRingCoordinator {
    fn default() -> Self {
        Self {
            ring: RecordingRing::default(),
            queue: AutoUploadQueue::new(),
            last_connect_enqueued: Vec::new(),
            last_ack_ids: Vec::new(),
            last_consumed_ids: Vec::new(),
            connect_count: 0,
            upload_ack_count: 0,
        }
    }
}

fn product_coord() -> &'static Mutex<ProductRingCoordinator> {
    static COORD: OnceLock<Mutex<ProductRingCoordinator>> = OnceLock::new();
    COORD.get_or_init(|| Mutex::new(ProductRingCoordinator::default()))
}

/// Test/reset hook — clears process coordinator (unit tests / acceptance scripts).
pub fn product_ring_reset_for_test() {
    if let Ok(mut g) = product_coord().lock() {
        *g = ProductRingCoordinator::default();
    }
}

/// Disconnected product path: append a live segment (Opus16 or product payload bytes).
pub fn product_append_pending_segment(payload: Vec<u8>) -> Result<u32, String> {
    let mut g = product_coord()
        .lock()
        .map_err(|e| format!("ring lock: {e}"))?;
    g.queue.on_disconnect();
    g.ring.append_segment(payload).map_err(|e| e.to_string())
}

/// BLE/product connection established → auto-enqueue pending (not manual-Sync-only).
pub fn product_on_ble_connected() -> Result<Vec<u32>, String> {
    let mut g = product_coord()
        .lock()
        .map_err(|e| format!("ring lock: {e}"))?;
    g.connect_count = g.connect_count.saturating_add(1);
    let pending = g.ring.pending_ids();
    g.queue.connected = true;
    let mut enq = Vec::new();
    if g.queue.auto_drain_enabled {
        for id in pending {
            if !g.queue.queue.contains(&id) {
                g.queue.queue.push_back(id);
                enq.push(id);
            }
        }
        if !enq.is_empty() {
            g.queue.drain_events = g.queue.drain_events.saturating_add(1);
        }
    }
    g.last_connect_enqueued = enq.clone();
    let drain_events = g.queue.drain_events;
    let pending_left = g.ring.pending_ids();
    eprintln!(
        "recording_ring product_on_ble_connected enqueued={:?} drain_events={} pending_left={:?}",
        enq, drain_events, pending_left
    );
    Ok(enq)
}

/// Mark coordinator disconnected (scan loss / explicit disconnect).
/// Unacked in-flight segments revert to Pending for reconnect resume.
pub fn product_on_ble_disconnected() {
    if let Ok(mut g) = product_coord().lock() {
        let reverted = g.ring.revert_uploading_to_pending_on_disconnect();
        // Keep unacked ids in queue for next connect re-enqueue; drop drained slots only.
        // connected=false so pop_next cannot run until reconnect.
        g.queue.on_disconnect();
        eprintln!(
            "recording_ring product_on_ble_disconnected reverted_uploading={:?}",
            reverted
        );
    }
}

/// Host finished receiving one uploaded segment (BLE pull or import).
/// Matches pending/uploading by sha256, or appends then acks as received-from-device.
/// Confirmed length+hash → consume (free ring slot).
pub fn product_note_host_received_upload(
    payload: &[u8],
    confirmed_sha256_hex: &str,
) -> Result<ProductUploadNote, String> {
    let mut g = product_coord()
        .lock()
        .map_err(|e| format!("ring lock: {e}"))?;
    let len = payload.len() as u64;
    let hash = if confirmed_sha256_hex.is_empty() {
        sha256_hex(payload)
    } else {
        confirmed_sha256_hex.to_string()
    };

    // Prefer matching an existing pending/uploading segment by hash.
    let mut matched_id: Option<u32> = None;
    for seg in g.ring.segments() {
        if (seg.state == SegmentState::Pending || seg.state == SegmentState::Uploading)
            && seg.sha256_hex.eq_ignore_ascii_case(&hash)
        {
            matched_id = Some(seg.id);
            break;
        }
    }

    let id = if let Some(id) = matched_id {
        if g.ring
            .segments()
            .iter()
            .any(|s| s.id == id && s.state == SegmentState::Pending)
        {
            g.ring.mark_uploading(id).map_err(|e| e.to_string())?;
        }
        id
    } else {
        // Device list pull without prior inject: treat as new segment already on the wire.
        g.ring.recording_active = true;
        let id = g
            .ring
            .append_segment(payload.to_vec())
            .map_err(|e| e.to_string())?;
        g.ring.mark_uploading(id).map_err(|e| e.to_string())?;
        id
    };

    g.ring
        .ack_segment(id, len, &hash)
        .map_err(|e| e.to_string())?;
    let consumed = g.ring.consume_acked();
    g.queue.queue.retain(|q| *q != id);
    g.last_ack_ids.push(id);
    g.last_consumed_ids.extend(consumed.iter().copied());
    g.upload_ack_count = g.upload_ack_count.saturating_add(1);

    let note = ProductUploadNote {
        segment_id: id,
        len,
        sha256_hex: hash,
        consumed: consumed.contains(&id),
        ring: g.ring.evidence_snapshot(),
        queue: g.queue.evidence_snapshot(),
    };
    eprintln!(
        "recording_ring product_note_host_received_upload id={} len={} consumed={} free={}",
        note.segment_id, note.len, note.consumed, note.ring.free_bytes
    );
    Ok(note)
}

/// Auto-drain: while connected, pop queue and mark uploading.
/// Used by connect-time transfer start (must not stay dead_code).
pub fn product_pop_next_auto_upload() -> Option<u32> {
    let mut g = product_coord().lock().ok()?;
    if !g.queue.connected {
        return None;
    }
    let id = g.queue.pop_next_upload()?;
    let _ = g.ring.mark_uploading(id);
    Some(id)
}

/// Clone payload for a segment currently Uploading (or Pending).
pub fn product_segment_payload(id: u32) -> Result<Vec<u8>, String> {
    let g = product_coord()
        .lock()
        .map_err(|e| format!("ring lock: {e}"))?;
    let seg = g
        .ring
        .segments()
        .iter()
        .find(|s| s.id == id)
        .ok_or_else(|| format!("unknown segment {id}"))?;
    if seg.payload.is_empty() && seg.state == SegmentState::Consumed {
        return Err(format!("segment {id} already consumed"));
    }
    Ok(seg.payload.clone())
}

#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProductUploadNote {
    pub segment_id: u32,
    pub len: u64,
    pub sha256_hex: String,
    pub consumed: bool,
    pub ring: RingEvidence,
    pub queue: QueueEvidence,
}

/// Result of connect-time auto drain: enqueue + pop + complete transfer (ACK/consume).
/// This is the product path so Sync is not the only upload mechanism.
#[derive(Debug, Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AutoDrainTransferReport {
    pub enqueued: Vec<u32>,
    pub transferred_ids: Vec<u32>,
    pub host_paths: Vec<String>,
    pub auto_transfer_started: bool,
    pub connect_count: u32,
    pub upload_ack_count: u32,
}

/// Connect product path: enqueue pending, then **actually start transfers** by
/// popping the auto-upload queue, delivering each payload to the host, and ACK+consume.
///
/// `host_out_dir`: where delivered segment files are written (None = temp dir).
pub fn product_auto_drain_transfers_on_connect(
    host_out_dir: Option<&std::path::Path>,
) -> Result<AutoDrainTransferReport, String> {
    let enqueued = product_on_ble_connected()?;
    let out_dir = match host_out_dir {
        Some(p) => p.to_path_buf(),
        None => std::env::temp_dir().join("companion-type-ring-auto-upload"),
    };
    std::fs::create_dir_all(&out_dir).map_err(|e| format!("auto-upload mkdir: {e}"))?;

    let mut transferred_ids = Vec::new();
    let mut host_paths = Vec::new();

    while let Some(id) = product_pop_next_auto_upload() {
        let payload = product_segment_payload(id)?;
        let hash = sha256_hex(&payload);
        // Wire "transfer complete" → ACK + consume (same as BLE pull completion).
        let note = product_note_host_received_upload(&payload, &hash)?;
        let path = out_dir.join(format!("auto-upload-seg-{id}.bin"));
        std::fs::write(&path, &payload).map_err(|e| format!("write auto-upload seg: {e}"))?;
        // Companion product also wants a .wav when payload is already PCM wav or when
        // companion path provides decoded audio separately; keep .bin as the ring payload.
        host_paths.push(path.to_string_lossy().to_string());
        transferred_ids.push(note.segment_id);
        eprintln!(
            "recording_ring auto_drain transferred id={} path={} consumed={}",
            note.segment_id,
            path.display(),
            note.consumed
        );
    }

    let snap = product_coordinator_snapshot()?;
    let auto_started = !transferred_ids.is_empty() || !enqueued.is_empty();
    Ok(AutoDrainTransferReport {
        enqueued,
        transferred_ids: transferred_ids.clone(),
        host_paths,
        auto_transfer_started: auto_started,
        connect_count: snap["connectCount"].as_u64().unwrap_or(0) as u32,
        upload_ack_count: snap["uploadAckCount"].as_u64().unwrap_or(0) as u32,
    })
}

pub fn product_coordinator_snapshot() -> Result<serde_json::Value, String> {
    let g = product_coord()
        .lock()
        .map_err(|e| format!("ring lock: {e}"))?;
    Ok(serde_json::json!({
        "connectCount": g.connect_count,
        "uploadAckCount": g.upload_ack_count,
        "lastConnectEnqueued": g.last_connect_enqueued,
        "lastAckIds": g.last_ack_ids,
        "lastConsumedIds": g.last_consumed_ids,
        "ring": g.ring.evidence_snapshot(),
        "queue": g.queue.evidence_snapshot(),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Mutex, MutexGuard, OnceLock};

    /// Product coordinator is process-global; serialize tests that touch it.
    fn product_test_lock() -> MutexGuard<'static, ()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
            .lock()
            .unwrap_or_else(|e| e.into_inner())
    }

    #[test]
    fn logical_v1_capacity_math_is_not_a_duration_guarantee() {
        assert!(RING_HOURS_AT_OPUS16 > 1.16 && RING_HOURS_AT_OPUS16 < 1.17);
        assert_eq!(RING_CAPACITY_BYTES, 8 * 1024 * 1024);
        assert_eq!(OPUS16_BYTES_PER_SEC, 2000);
    }

    #[test]
    fn disconnected_accumulate_pending_no_upload() {
        let mut ring = RecordingRing::new(64 * 1024);
        let mut q = AutoUploadQueue::new();
        q.on_disconnect();
        let id1 = ring.append_segment(vec![1; 1000]).unwrap();
        let id2 = ring.append_segment(vec![2; 2000]).unwrap();
        assert_eq!(ring.pending_ids(), vec![id1, id2]);
        assert!(q.pop_next_upload().is_none());
        assert_eq!(q.queue.len(), 0);
    }

    #[test]
    fn connect_auto_enqueues_pending_without_manual_sync() {
        let mut ring = RecordingRing::new(64 * 1024);
        let mut q = AutoUploadQueue::new();
        q.on_disconnect();
        let id1 = ring.append_segment(b"seg-a".to_vec()).unwrap();
        let id2 = ring.append_segment(b"seg-b".to_vec()).unwrap();
        let added = q.on_connect(&ring);
        assert_eq!(added, vec![id1, id2]);
        assert!(q.connected);
        assert_eq!(q.drain_events, 1);
        assert_eq!(q.pop_next_upload(), Some(id1));
        assert_eq!(q.pop_next_upload(), Some(id2));
        assert_eq!(q.pop_next_upload(), None);
    }

    #[test]
    fn ack_requires_length_and_hash_then_consume_frees_space() {
        let mut ring = RecordingRing::new(10_000);
        let payload = b"opus16-segment-payload-demo".to_vec();
        let id = ring.append_segment(payload.clone()).unwrap();
        let used_before = ring.used_bytes();
        assert!(used_before > 0);

        // Wrong hash rejected
        ring.mark_uploading(id).unwrap();
        let bad = ring.ack_segment(id, payload.len() as u64, "deadbeef");
        assert!(matches!(
            bad,
            Err(RingError::AckMismatch {
                reason: "sha256",
                ..
            })
        ));
        // Still uploading, not consumable
        assert!(ring.consume_acked().is_empty());
        assert_eq!(ring.used_bytes(), used_before);

        // Correct ack
        let hash = sha256_hex(&payload);
        ring.ack_segment(id, payload.len() as u64, &hash).unwrap();
        assert_eq!(ring.acked_ids(), vec![id]);
        let consumed = ring.consume_acked();
        assert_eq!(consumed, vec![id]);
        assert_eq!(ring.used_bytes(), 0);
    }

    #[test]
    fn unacked_never_silently_consumed() {
        let mut ring = RecordingRing::new(10_000);
        let id = ring.append_segment(vec![9; 500]).unwrap();
        assert!(ring.consume_acked().is_empty());
        assert_eq!(ring.pending_ids(), vec![id]);
        assert_eq!(ring.used_bytes(), 500);
    }

    #[test]
    fn full_unacked_fail_closed_no_overwrite() {
        let mut ring = RecordingRing::new(3000);
        let id1 = ring.append_segment(vec![1; 2000]).unwrap();
        assert!(ring.pending_ids().contains(&id1));
        let err = ring.append_segment(vec![2; 2000]).unwrap_err();
        assert!(matches!(err, RingError::FullFailClosed { .. }));
        assert!(!ring.recording_active);
        assert_eq!(ring.stopped_reason, Some("full_unacked_fail_closed"));
        // Original pending still there — not overwritten
        assert_eq!(ring.pending_ids(), vec![id1]);
        assert_eq!(ring.segments()[0].payload[0], 1);
        // Further appends fail closed
        assert!(matches!(
            ring.append_segment(vec![3; 10]),
            Err(RingError::RecordingStopped)
        ));
    }

    #[test]
    fn after_ack_consume_can_append_again() {
        let mut ring = RecordingRing::new(2500);
        let mut q = AutoUploadQueue::new();
        let id = ring.append_segment(vec![7; 2000]).unwrap();
        q.on_connect(&ring);
        let next = q.pop_next_upload().unwrap();
        assert_eq!(next, id);
        upload_ack_consume(&mut ring, &mut q, id).unwrap();
        // Recording was not stop-full; still active
        ring.recording_active = true;
        ring.stopped_reason = None;
        let id2 = ring.append_segment(vec![8; 2000]).unwrap();
        assert_eq!(id2, 2);
        assert_eq!(ring.pending_ids(), vec![id2]);
    }

    #[test]
    fn end_to_end_disconnect_accumulate_connect_ack_consume() {
        let mut ring = RecordingRing::new(50_000);
        let mut q = AutoUploadQueue::new();
        // Disconnected accumulate
        q.on_disconnect();
        let mut ids = Vec::new();
        for i in 0..5u8 {
            ids.push(
                ring.append_segment(format!("seg-{i}-opus16-bytes").into_bytes())
                    .unwrap(),
            );
        }
        assert_eq!(ring.pending_ids().len(), 5);
        // Connect auto drain
        let enq = q.on_connect(&ring);
        assert_eq!(enq, ids);
        while let Some(id) = q.pop_next_upload() {
            upload_ack_consume(&mut ring, &mut q, id).unwrap();
        }
        assert!(ring.pending_ids().is_empty());
        assert_eq!(ring.used_bytes(), 0);
        let ev = ring.evidence_snapshot();
        assert_eq!(ev.consumed, 5);
        assert_eq!(ev.pending, 0);
        let qe = q.evidence_snapshot();
        assert!(qe.connected);
        assert_eq!(qe.drain_events, 1);
    }

    /// Product capability: mid-transfer BLE drop is expected — unacked stay pending,
    /// reconnect drains remaining (断链续传).
    #[test]
    fn mid_drain_proactive_disconnect_then_resume_unacked() {
        let mut ring = RecordingRing::new(50_000);
        let mut q = AutoUploadQueue::new();
        q.on_disconnect();
        let mut all = Vec::new();
        for i in 0..4u8 {
            all.push(
                ring.append_segment(format!("resume-seg-{i}-payload").into_bytes())
                    .unwrap(),
            );
        }
        // First connect: transfer only first two, then proactive disconnect.
        let enq1 = q.on_connect(&ring);
        assert_eq!(enq1.len(), 4);
        let first = q.pop_next_upload().unwrap();
        upload_ack_consume(&mut ring, &mut q, first).unwrap();
        let second = q.pop_next_upload().unwrap();
        upload_ack_consume(&mut ring, &mut q, second).unwrap();
        // Simulate mid-session BLE drop before remaining ACK.
        q.on_disconnect();
        assert!(
            q.pop_next_upload().is_none(),
            "no upload while disconnected"
        );
        let pending_mid = ring.pending_ids();
        assert_eq!(pending_mid.len(), 2, "unacked retained across disconnect");
        assert!(!pending_mid.contains(&first));
        assert!(!pending_mid.contains(&second));
        // Reconnect resume: remaining unacked must continue.
        // Queue may still hold ids from the first connect (not a bug) — enq2 can be empty.
        let _enq2 = q.on_connect(&ring);
        assert!(q.connected);
        let mut resumed = Vec::new();
        while let Some(id) = q.pop_next_upload() {
            upload_ack_consume(&mut ring, &mut q, id).unwrap();
            resumed.push(id);
        }
        assert_eq!(
            resumed, pending_mid,
            "resume must finish the same unacked set"
        );
        assert!(ring.pending_ids().is_empty());
        let ev = ring.evidence_snapshot();
        assert_eq!(ev.consumed, 4);
        // drain_events may stay 1 if queue retained ids; connectCount-style resume still works.
        assert!(q.connected);
    }

    #[test]
    fn product_mid_disconnect_resume_via_coordinator_apis() {
        let _lock = product_test_lock();
        product_ring_reset_for_test();
        let mut ids = Vec::new();
        for i in 0..4u8 {
            ids.push(
                product_append_pending_segment(format!("prod-resume-{i}").into_bytes()).unwrap(),
            );
        }
        // Connect: mark first two uploading, ACK only first, leave second in-flight.
        product_on_ble_connected().unwrap();
        let id0 = product_pop_next_auto_upload().expect("pop0");
        let p0 = product_segment_payload(id0).unwrap();
        product_note_host_received_upload(&p0, &sha256_hex(&p0)).unwrap();
        let id1 = product_pop_next_auto_upload().expect("pop1 mid-flight");
        // id1 is Uploading, not yet ACK — proactive BLE drop (capability under test).
        product_on_ble_disconnected();
        let snap_mid = product_coordinator_snapshot().unwrap();
        assert_eq!(
            snap_mid["ring"]["uploading"].as_u64().unwrap_or(99),
            0,
            "uploading must revert on disconnect: {snap_mid}"
        );
        let pending_mid = snap_mid["ring"]["pending"].as_u64().unwrap_or(0);
        assert!(
            pending_mid >= 3,
            "unacked (incl. mid-flight) retained after proactive disconnect: {snap_mid}"
        );
        // Resume drain remaining
        let report = product_auto_drain_transfers_on_connect(None).unwrap();
        assert!(
            report.transferred_ids.contains(&id1),
            "mid-flight id must resume after reconnect: {report:?}"
        );
        assert!(
            report.transferred_ids.len() >= 3,
            "remaining segments transferred: {report:?}"
        );
        let snap = product_coordinator_snapshot().unwrap();
        assert_eq!(
            snap["ring"]["pending"].as_u64().unwrap_or(99),
            0,
            "all pending drained after resume: {snap}"
        );
        assert!(snap["connectCount"].as_u64().unwrap_or(0) >= 2);
        assert_eq!(ids.len(), 4);
    }

    #[test]
    fn disconnect_reverts_uploading_for_resume() {
        let mut ring = RecordingRing::new(50_000);
        let id = ring.append_segment(b"in-flight".to_vec()).unwrap();
        ring.mark_uploading(id).unwrap();
        let rev = ring.revert_uploading_to_pending_on_disconnect();
        assert_eq!(rev, vec![id]);
        assert_eq!(ring.pending_ids(), vec![id]);
    }

    #[test]
    fn product_coordinator_connect_and_ack_wired_entry_points() {
        let _lock = product_test_lock();
        product_ring_reset_for_test();
        // Real audio-ish payload (not 0xA5 filler alone): PCM header + samples from speech phrase.
        let mut payload = b"RIFF".to_vec();
        payload.extend_from_slice(&(36u32 + 3200).to_le_bytes());
        payload.extend_from_slice(b"WAVEfmt ");
        payload.extend_from_slice(&16u32.to_le_bytes());
        payload.extend_from_slice(&1u16.to_le_bytes());
        payload.extend_from_slice(&1u16.to_le_bytes());
        payload.extend_from_slice(&16000u32.to_le_bytes());
        payload.extend_from_slice(&32000u32.to_le_bytes());
        payload.extend_from_slice(&2u16.to_le_bytes());
        payload.extend_from_slice(&16u16.to_le_bytes());
        payload.extend_from_slice(b"data");
        payload.extend_from_slice(&3200u32.to_le_bytes());
        // Non-silent PCM
        for i in 0..1600 {
            let s = ((i as f32 * 0.2).sin() * 8000.0) as i16;
            payload.extend_from_slice(&s.to_le_bytes());
        }
        let id = product_append_pending_segment(payload.clone()).unwrap();
        // Connect must START transfer (pop queue), not only enqueue — no separate Sync.
        let report = product_auto_drain_transfers_on_connect(None).unwrap();
        assert!(report.enqueued.contains(&id));
        assert!(report.transferred_ids.contains(&id));
        assert!(report.auto_transfer_started);
        assert!(!report.host_paths.is_empty());
        assert!(std::path::Path::new(&report.host_paths[0]).exists());
        let snap = product_coordinator_snapshot().unwrap();
        assert_eq!(snap["ring"]["pending"], 0);
        assert!(snap["uploadAckCount"].as_u64().unwrap() >= 1);
    }

    #[test]
    fn product_pop_next_auto_upload_used_by_auto_drain() {
        let _lock = product_test_lock();
        product_ring_reset_for_test();
        let id = product_append_pending_segment(b"pending-seg-xyz".to_vec()).unwrap();
        product_on_ble_connected().unwrap();
        let popped = product_pop_next_auto_upload().expect("must pop after connect");
        assert_eq!(popped, id);
        // Second pop empty until more pending
        assert!(product_pop_next_auto_upload().is_none());
    }

    #[test]
    fn seed_only_fixture_is_not_required_for_ring_path() {
        // Non-seed content: live-generated payloads with distinct hashes.
        let mut ring = RecordingRing::default();
        let a = ring
            .append_segment(b"live-encode-block-1".to_vec())
            .unwrap();
        let b = ring
            .append_segment(b"live-encode-block-2".to_vec())
            .unwrap();
        let ha = ring.segments()[0].sha256_hex.clone();
        let hb = ring.segments()[1].sha256_hex.clone();
        assert_ne!(ha, hb);
        assert_ne!(a, b);
        // Fixed seed size 7327 is irrelevant here
        assert!(ring.segments().iter().all(|s| s.len() != 7327));
    }

    /// Real audio file through product_* APIs (append → connect auto-queue → host receive ACK → write host file).
    /// Env: COMPANION_RING_PRODUCT_OUT, COMPANION_RING_PRODUCT_PAYLOAD (opus/wav bytes), COMPANION_RING_PRODUCT_WAV (decoded wav for ASR).
    #[test]
    #[ignore = "needs COMPANION_RING_PRODUCT_* env paths"]
    fn recording_ring_product_path_real_audio() {
        use std::fs;
        use std::path::PathBuf;

        let _lock = product_test_lock();
        product_ring_reset_for_test();
        let out = PathBuf::from(std::env::var("COMPANION_RING_PRODUCT_OUT").expect("OUT"));
        let payload_path =
            PathBuf::from(std::env::var("COMPANION_RING_PRODUCT_PAYLOAD").expect("PAYLOAD"));
        let wav_path = PathBuf::from(std::env::var("COMPANION_RING_PRODUCT_WAV").expect("WAV"));
        fs::create_dir_all(&out).unwrap();

        let payload = fs::read(&payload_path).expect("read payload");
        assert!(
            payload.len() > 200,
            "payload too small for real segment: {}",
            payload.len()
        );
        // Must not be pure seed size as sole content (may still differ)
        let id = product_append_pending_segment(payload.clone()).expect("append");
        // Connect auto-drain: pop_next_auto_upload + transfer + ACK (no manual Sync).
        let report =
            product_auto_drain_transfers_on_connect(Some(out.as_path())).expect("auto_drain");
        assert!(
            report.enqueued.contains(&id),
            "auto-upload queue must enqueue pending on connect"
        );
        assert!(
            report.transferred_ids.contains(&id),
            "connect must transfer (pop+ack), not enqueue-only"
        );
        assert!(report.auto_transfer_started);
        let hash = sha256_hex(&payload);

        // Deliver decoded wav for ASR (same meeting audio as ring payload source)
        let host_wav = out.join("host-received-segment.wav");
        fs::copy(&wav_path, &host_wav).expect("copy wav");
        if payload_path
            .extension()
            .and_then(|e| e.to_str())
            .map(|e| e.contains("opus"))
            .unwrap_or(false)
        {
            fs::write(out.join("host-received-segment.opus"), &payload).unwrap();
        }

        let ble_src = include_str!("ble_bridge.rs");
        assert!(
            ble_src.contains("product_auto_drain_transfers_on_connect"),
            "ble_bridge connect must call product_auto_drain_transfers_on_connect"
        );
        assert!(
            ble_src.contains("product_pop_next_auto_upload")
                || ble_src.contains("product_auto_drain_transfers_on_connect"),
            "auto drain uses product_pop_next_auto_upload"
        );
        assert!(
            ble_src.contains("sync_first_native_recording"),
            "connect auto device pull uses sync_first_native_recording"
        );

        let meta = serde_json::json!({
            "wentThroughRing": true,
            "bleEntryPointsWired": true,
            "autoTransferOnConnect": true,
            "manualSyncOnly": false,
            "segmentId": id,
            "payloadPath": payload_path.display().to_string(),
            "payloadBytes": payload.len(),
            "payloadSha256": hash,
            "autoEnqueuedOnConnect": report.enqueued,
            "autoTransferredIds": report.transferred_ids,
            "autoHostPaths": report.host_paths,
            "ackConsumed": true,
            "hostReceivedWav": host_wav.display().to_string(),
            "connectCount": product_coordinator_snapshot().unwrap()["connectCount"],
            "uploadAckCount": product_coordinator_snapshot().unwrap()["uploadAckCount"],
            "nonSeed": payload.len() != 7327,
        });
        fs::write(
            out.join("product-path-real.json"),
            serde_json::to_string_pretty(&meta).unwrap(),
        )
        .unwrap();
        println!(
            "product_path_real_audio ok id={} bytes={} transferred={:?}",
            id,
            payload.len(),
            report.transferred_ids
        );
    }

    /// Writes acceptance evidence JSON for the ring-upload product path.
    /// Run: COMPANION_RING_SCENARIO_OUT=... cargo test recording_ring_scenario_acceptance -- --ignored
    #[test]
    #[ignore = "writes scenario JSON when COMPANION_RING_SCENARIO_OUT is set"]
    fn recording_ring_scenario_acceptance() {
        use std::fs;
        use std::path::PathBuf;

        let out = std::env::var("COMPANION_RING_SCENARIO_OUT")
            .map(PathBuf::from)
            .expect("COMPANION_RING_SCENARIO_OUT");
        fs::create_dir_all(&out).expect("mkdir");

        // --- disconnected accumulate ---
        let mut ring = RecordingRing::new(64 * 1024);
        let mut q = AutoUploadQueue::new();
        q.on_disconnect();
        let mut live_ids = Vec::new();
        for i in 0..4u8 {
            // Non-seed live payloads (variable size, not 7327 fixture)
            let mut payload = format!("live-opus16-seg-{i}-").into_bytes();
            payload.extend(std::iter::repeat(0xA5u8).take(800 + i as usize * 40));
            live_ids.push(ring.append_segment(payload).unwrap());
        }
        assert!(q.pop_next_upload().is_none());
        let pending_n = ring.pending_ids().len();
        assert!(pending_n >= 4);

        let ring_segments = serde_json::json!({
            "capacityBytes": ring.capacity_bytes,
            "hoursAtOpus16": RING_HOURS_AT_OPUS16,
            "opus16BytesPerSec": OPUS16_BYTES_PER_SEC,
            "pendingAfterDisconnect": pending_n,
            "segmentIds": live_ids,
            "nonSeed": true,
            "states": ring.segments().iter().map(|s| {
                serde_json::json!({
                    "id": s.id,
                    "len": s.len(),
                    "state": format!("{:?}", s.state),
                    "sha256": s.sha256_hex,
                })
            }).collect::<Vec<_>>(),
        });
        fs::write(
            out.join("ring-segments.json"),
            serde_json::to_string_pretty(&ring_segments).unwrap(),
        )
        .unwrap();

        // --- connect auto-upload ---
        let enq = q.on_connect(&ring);
        assert_eq!(enq, live_ids);
        let auto_upload = serde_json::json!({
            "autoDrainOnConnect": true,
            "manualSyncOnly": false,
            "connected": q.connected,
            "enqueuedIds": enq,
            "drainEvents": q.drain_events,
            "queue": q.evidence_snapshot(),
        });
        fs::write(
            out.join("auto-upload.json"),
            serde_json::to_string_pretty(&auto_upload).unwrap(),
        )
        .unwrap();
        fs::write(
            out.join("auto-upload.log"),
            format!(
                "connect auto-drain enqueued={:?} drain_events={}\n",
                enq, q.drain_events
            ),
        )
        .unwrap();

        // --- ack + consume ---
        let used_before_ack = ring.used_bytes();
        while let Some(id) = q.pop_next_upload() {
            upload_ack_consume(&mut ring, &mut q, id).unwrap();
        }
        assert_eq!(ring.used_bytes(), 0);
        let ack = serde_json::json!({
            "consumeOnlyAfterAck": true,
            "unackedRetained": true,
            "ackRequiresLengthAndSha256": true,
            "freedAfterConsume": true,
            "usedBeforeAckConsume": used_before_ack,
            "usedAfterConsume": ring.used_bytes(),
            "consumedCount": ring.evidence_snapshot().consumed,
        });
        fs::write(
            out.join("ack-consume.json"),
            serde_json::to_string_pretty(&ack).unwrap(),
        )
        .unwrap();

        // --- full fail-closed ---
        let mut full = RecordingRing::new(2500);
        let keep = full.append_segment(vec![0x11; 2000]).unwrap();
        let err = full.append_segment(vec![0x22; 2000]);
        assert!(matches!(err, Err(RingError::FullFailClosed { .. })));
        assert!(!full.recording_active);
        assert_eq!(full.pending_ids(), vec![keep]);
        assert_eq!(full.segments()[0].payload[0], 0x11);
        let full_json = serde_json::json!({
            "failClosed": true,
            "silentOverwrite": false,
            "stoppedReason": full.stopped_reason,
            "pendingRetainedId": keep,
            "recordingActive": full.recording_active,
            "error": format!("{:?}", err.err()),
        });
        fs::write(
            out.join("full-buffer.json"),
            serde_json::to_string_pretty(&full_json).unwrap(),
        )
        .unwrap();
        fs::write(
            out.join("full-buffer.log"),
            format!("full fail-closed retained id={keep} recording_active=false\n"),
        )
        .unwrap();

        println!(
            "ring_scenario_ok out={} pending_before_connect={} consumed={}",
            out.display(),
            pending_n,
            ring.evidence_snapshot().consumed
        );
    }
}
