use super::*;
use crate::backend::recording_transfer::{Cursor, ReceiveCursor, Source};
use sha2::{Digest, Sha256};
use std::path::PathBuf;

const NATIVE_OVERRUN: &str = "recording native receive: Runtime Error: Windows BLE notification queue overflow: channel lagged by 1; resume from the durable offset";
const RECEIVER_OVERRUN: &str = "recording receive queue overflow; original recording not consumed";

struct InterruptedFile {
    root: PathBuf,
    source: Source,
    body: Vec<u8>,
    starts: Vec<usize>,
}
impl Attempt for InterruptedFile {
    fn receive(&mut self) -> BoxFuture<'_, Result<Vec<u8>, String>> {
        Box::pin(async move {
            let (mut cursor, mut data) = ReceiveCursor::open(&self.root, self.source.clone()).await?;
            let offset = data.len();
            self.starts.push(offset);
            assert_eq!(data, self.body[..offset]);
            let end = if self.starts.len() == 1 { 80_000 } else { self.body.len() };
            for packet in self.body[offset..end].chunks(224) { cursor.append(packet).await?; }
            if self.starts.len() == 1 {
                // Like a failed native stream: dropping the real storage worker
                // drains its accepted batches, closes the lock and checkpoints.
                return Err(NATIVE_OVERRUN.into());
            }
            data.extend_from_slice(&self.body[offset..]);
            cursor.finish(data.len(), Sha256::digest(&data).into(), crc32fast::hash(&data)).await?;
            Ok(data)
        })
    }
}

#[tokio::test]
async fn native_overrun_reopens_the_real_durable_cursor_and_receives_only_missing_bytes() {
    let root = std::env::temp_dir().join(format!("companion-pull-recovery-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    let body: Vec<u8> = (0..180_000).map(|n| (n % 239) as u8).collect();
    let digest = Sha256::digest(&body);
    let mut prefix = [0; 8];
    prefix.copy_from_slice(&digest[..8]);
    let source = Source { device: "same-sealed-device".into(), recording_id: 81, codec: 3,
        source_mode: 1, duration_ms: 90_000, total_length: body.len() as u32,
        sha256_prefix: prefix, content_crc32: crc32fast::hash(&body) };
    let mut port = InterruptedFile { root: root.clone(), source: source.clone(), body: body.clone(), starts: vec![] };
    assert_eq!(receive(&mut port, true, 81).await.unwrap(), body);
    // The <4KiB unsent tail is replayed; an in-memory 80,000 offset would skip it.
    assert_eq!(port.starts, [0, 77_824]);
    let (cursor, persisted) = Cursor::open(&root, source).unwrap();
    assert_eq!(persisted, body);
    drop(cursor);
    std::fs::remove_dir_all(root).unwrap();
}

struct FailedPort { error: &'static str, attempts: usize }
impl Attempt for FailedPort {
    fn receive(&mut self) -> BoxFuture<'_, Result<Vec<u8>, String>> {
        Box::pin(async move { self.attempts += 1; Err(self.error.into()) })
    }
}

#[tokio::test]
async fn recurring_overrun_stops_after_three_receiver_restarts() {
    for error in [NATIVE_OVERRUN, RECEIVER_OVERRUN] {
        let mut port = FailedPort { error, attempts: 0 };
        assert_eq!(receive(&mut port, true, 81).await.unwrap_err(), error);
        assert_eq!(port.attempts, 4);
        assert!(retire_connection(error));
    }
}

#[tokio::test]
async fn pause_integrity_storage_and_link_errors_are_never_retried_as_queue_overruns() {
    for error in [super::super::super::recording_sync::PAUSED,
        "recording packet CRC mismatch at offset=0", "final SHA mismatch",
        "recording byte count mismatch", "录音续传记录不可用",
        "recording notification stream ended", "write recording_chunk_pull start timed out"] {
        let mut port = FailedPort { error, attempts: 0 };
        assert_eq!(receive(&mut port, true, 81).await.unwrap_err(), error);
        assert_eq!(port.attempts, 1);
    }
}

#[tokio::test]
async fn live_or_lossy_receive_cannot_replay_a_sealed_file_cursor() {
    let mut port = FailedPort { error: NATIVE_OVERRUN, attempts: 0 };
    assert!(receive(&mut port, false, 81).await.is_err());
    assert_eq!(port.attempts, 1);
}

#[test]
fn transport_failures_retire_the_connection_but_one_bad_recording_stays_isolated() {
    for error in ["resume write: HRESULT(0x80000013) 该对象已关闭。",
        "resume write: GattCommunicationStatus(1)", "not connected",
        "recording notification stream ended", "recording chunk notify timeout at offset=4",
        "recording transfer stalled after 3 resume requests at offset=4; original recording not consumed",
        NATIVE_OVERRUN, RECEIVER_OVERRUN] { assert!(retire_connection(error), "{error}"); }
    for error in ["recording packet CRC mismatch", "final SHA mismatch", "unsupported recording codec: 9",
        "recording receive queue overflow in a recording title", super::super::super::recording_sync::PAUSED] {
        assert!(!retire_connection(error), "{error}");
    }
}
