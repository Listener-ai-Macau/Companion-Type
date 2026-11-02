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

struct RepeatedLinkLoss {
    root: PathBuf,
    source: Source,
    body: Vec<u8>,
    starts: Vec<usize>,
    attempted_ends: Vec<usize>,
}
impl Attempt for RepeatedLinkLoss {
    fn receive(&mut self) -> BoxFuture<'_, Result<Vec<u8>, String>> {
        Box::pin(async move {
            let (mut cursor, mut saved) = ReceiveCursor::open(&self.root, self.source.clone()).await?;
            let offset = saved.len();
            self.starts.push(offset);
            assert_eq!(saved, self.body[..offset]);
            let end = if self.starts.len() <= 3 { (offset + 55_000).min(self.body.len()) }
                else { self.body.len() };
            self.attempted_ends.push(end);
            for packet in self.body[offset..end].chunks(224) { cursor.append(packet).await?; }
            if self.starts.len() <= 3 {
                return Err("BLE session disconnected: GattSessionStatus(0); original recording retained".into());
            }
            saved.extend_from_slice(&self.body[offset..end]);
            cursor.finish(saved.len(), Sha256::digest(&saved).into(), crc32fast::hash(&saved)).await?;
            Ok(saved)
        })
    }
}

#[tokio::test]
async fn repeated_link_losses_resume_same_durable_recording_without_gaps_or_duplicates() {
    let root = std::env::temp_dir().join(format!("companion-repeated-link-loss-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    let body: Vec<u8> = (0..180_000).map(|n| (n % 239) as u8).collect();
    let digest = Sha256::digest(&body);
    let mut prefix = [0; 8]; prefix.copy_from_slice(&digest[..8]);
    let source = Source { device: "same-sealed-device".into(), recording_id: 81, codec: 3,
        source_mode: 1, duration_ms: 90_000, total_length: body.len() as u32,
        sha256_prefix: prefix, content_crc32: crc32fast::hash(&body) };
    let mut port = RepeatedLinkLoss { root: root.clone(), source: source.clone(), body: body.clone(),
        starts: vec![], attempted_ends: vec![] };
    for _ in 0..3 {
        let error = receive(&mut port, true, 81).await.unwrap_err();
        assert!(error.contains("BLE session disconnected"));
    }
    assert_eq!(receive(&mut port, true, 81).await.unwrap(), body);
    assert_eq!(port.starts.len(), 4);
    for index in 1..port.starts.len() {
        assert!(port.starts[index] > port.starts[index - 1], "the verified prefix must advance");
        assert!(port.starts[index] <= port.attempted_ends[index - 1], "never skip unwritten bytes");
    }
    let (cursor, persisted) = Cursor::open(&root, source).unwrap();
    assert_eq!(persisted, body);
    drop(cursor);
    // Retain the small isolated fixture under the caller's E: test directory.
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
        "recording notification stream ended", "write recording_chunk_pull start timed out",
        "BLE session disconnected: GattSessionStatus(0); original recording retained"] {
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
        "BLE session disconnected: GattSessionStatus(0); original recording retained",
        "recording notification stream ended", "recording chunk notify timeout at offset=4",
        "recording transfer stalled after 3 resume requests at offset=4; original recording not consumed",
        NATIVE_OVERRUN, RECEIVER_OVERRUN,
        "sealed stream release failed before reclaim: native first lane release failed",
        "sealed stream release failed before reclaim: recording lane 1 release timed out"] {
        assert!(retire_connection(error), "{error}");
    }
    for error in ["recording packet CRC mismatch", "final SHA mismatch", "unsupported recording codec: 9",
        "recording receive queue overflow in a recording title", super::super::super::recording_sync::PAUSED] {
        assert!(!retire_connection(error), "{error}");
    }
}

#[tokio::test]
async fn lost_transport_releases_maintenance_before_blocked_native_cleanup() {
    use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
    let maintained=Arc::new(AtomicBool::new(true));
    let retire=maintained.clone();let during_cleanup=maintained.clone();
    let (entered,ready)=tokio::sync::oneshot::channel();
    let (release,wait)=tokio::sync::oneshot::channel();
    let original="recording transfer stalled after 3 resume requests at offset=1695577; original recording not consumed";
    let task=tokio::spawn(async move {
        quiesce_failed_attempt(original,move |cause| {
            assert_eq!(cause,original);retire.store(false,Ordering::SeqCst);
        },async move {
            assert!(!during_cleanup.load(Ordering::SeqCst));
            entered.send(()).unwrap();wait.await.unwrap();
            Err("sealed stream release failed before reclaim: native lane timed out".into())
        }).await
    });
    ready.await.unwrap();assert!(!maintained.load(Ordering::SeqCst));
    assert!(!task.is_finished(),"owned cleanup must still be awaited");
    release.send(()).unwrap();let cleanup=task.await.unwrap();
    let error=super::super::pull_session::finish_receive::<Vec<u8>>(Err(original.into()),cleanup).unwrap_err();
    assert!(error.starts_with(original));assert!(error.contains(super::super::pull_session::RETIRED_CLEANUP));
}

#[tokio::test]
async fn same_link_recovery_pause_and_bad_file_keep_maintenance() {
    for error in [NATIVE_OVERRUN,RECEIVER_OVERRUN,
        super::super::super::recording_sync::PAUSED,"recording packet CRC mismatch","final SHA mismatch"] {
        let mut retired=false;let mut cleaned=false;
        quiesce_failed_attempt(error,|_|retired=true,async {cleaned=true;Ok(())}).await.unwrap();
        assert!(!retired,"{error}");assert!(cleaned);
    }
}

#[tokio::test]
async fn explicit_native_loss_also_releases_before_cleanup() {
    for error in ["BLE session disconnected: GattSessionStatus(0); original recording retained",
        "recording chunk notify timeout at offset=4","resume write timed out"] {
        use std::cell::Cell;
        let retired=Cell::new(false);
        quiesce_failed_attempt(error,|cause|{assert_eq!(cause,error);retired.set(true)},async {
            assert!(retired.get());Ok(())
        }).await.unwrap();
    }
}
