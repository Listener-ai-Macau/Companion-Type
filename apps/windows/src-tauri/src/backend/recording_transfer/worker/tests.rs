use super::*;
use sha2::{Digest, Sha256};
use std::{fs, io::{BufWriter, Seek, SeekFrom}, path::PathBuf};

fn fixture() -> (PathBuf, Source, Vec<u8>) {
    let root = std::env::temp_dir().join(format!("companion-receive-worker-{}", uuid::Uuid::new_v4().simple()));
    fs::create_dir(&root).unwrap();
    let body: Vec<u8> = (0..180_000).map(|n| (n % 239) as u8).collect();
    let digest = Sha256::digest(&body);
    let mut prefix = [0u8; 8];
    prefix.copy_from_slice(&digest[..8]);
    let source = Source { device: "bounded-store-fixture".into(), recording_id: 81,
        codec: 3, source_mode: 1, duration_ms: 90_000, total_length: body.len() as u32,
        sha256_prefix: prefix, content_crc32: crc32fast::hash(&body) };
    (root, source, body)
}

async fn pause(cursor: &ReceiveCursor) -> std::sync::mpsc::Sender<()> {
    let (resume, blocked) = std::sync::mpsc::channel();
    let (entered, response) = oneshot::channel();
    cursor.sender.as_ref().unwrap().send(Command::Pause(blocked, entered)).await.unwrap();
    response.await.unwrap();
    resume
}

#[tokio::test]
async fn stalled_disk_allows_receive_progress_but_queue_stays_bounded() {
    use futures::FutureExt;
    let (root, source, body) = fixture();
    let (mut cursor, prefix) = ReceiveCursor::open(&root, source.clone()).await.unwrap();
    assert!(prefix.is_empty());
    let resume = pause(&cursor).await;
    let capacity = BATCH_BYTES * QUEUED_BATCHES;
    // The actual IO worker is held; 32 KiB can still be received/validated.
    for packet in body[..capacity].chunks(224) { cursor.append(packet).await.unwrap(); }
    assert_eq!(cursor.sender.as_ref().unwrap().capacity(), 0);
    assert!(Cursor::open(&root, source.clone()).is_err(), "worker retains exclusive file ownership");
    let receipt_path = root.join(format!(".device-recording-{}.json", source.key().unwrap()));
    let receipt: super::super::Receipt = serde_json::from_slice(&fs::read(&receipt_path).unwrap()).unwrap();
    assert_eq!(receipt.bytes, 0, "queued data must not count as durable");
    let mut full = Box::pin(cursor.append(&body[capacity..capacity+BATCH_BYTES]));
    assert!(full.as_mut().now_or_never().is_none(), "full queue must backpressure, not grow/drop");
    resume.send(()).unwrap();
    full.await.unwrap();
    for packet in body[capacity+BATCH_BYTES..].chunks(224) { cursor.append(packet).await.unwrap(); }
    cursor.finish(body.len(), Sha256::digest(&body).into(), crc32fast::hash(&body)).await.unwrap();
    assert!(cursor.worker.is_none());
    drop(cursor);
    let (cursor, recovered) = Cursor::open(&root, source.clone()).unwrap();
    assert_eq!(recovered, body);
    drop(cursor);
    super::super::release(&root, source).unwrap();
}

#[tokio::test]
async fn worker_write_failure_preserves_durable_prefix_and_refuses_finish() {
    let (root, source, body) = fixture();
    let (mut original, _) = Cursor::open(&root, source.clone()).unwrap();
    original.append(&body[..4_321]).unwrap();
    original.checkpoint().unwrap();
    let receipt = fs::read(&original.receipt_path).unwrap();
    let mut read_only = fs::File::open(&original.path).unwrap();
    read_only.seek(SeekFrom::Start(4_321)).unwrap();
    original.file = Some(BufWriter::with_capacity(super::super::CHECKPOINT_BYTES as usize, read_only));
    let mut cursor = ReceiveCursor::start(original).unwrap();
    let result = async {
        for packet in body[4_321..].chunks(224) { cursor.append(packet).await?; }
        cursor.finish(body.len(), Sha256::digest(&body).into(), crc32fast::hash(&body)).await
    }.await;
    assert!(result.is_err());
    drop(cursor);
    let (cursor, recovered) = Cursor::open(&root, source.clone()).unwrap();
    assert_eq!(recovered, body[..4_321]);
    assert_eq!(fs::read(&cursor.receipt_path).unwrap(), receipt);
    drop(cursor);
    assert!(super::super::release(&root, source).is_err());
}

#[tokio::test]
async fn cancelled_receive_closes_worker_before_retry_and_wrong_digest_is_rejected() {
    let (root, source, body) = fixture();
    let (mut cursor, _) = ReceiveCursor::open(&root, source.clone()).await.unwrap();
    for packet in body[..80_000].chunks(224) { cursor.append(packet).await.unwrap(); }
    drop(cursor);
    let (mut cursor, prefix) = ReceiveCursor::open(&root, source.clone()).await.unwrap();
    let length = 80_000 / BATCH_BYTES * BATCH_BYTES;
    assert_eq!(prefix, body[..length]);
    for packet in body[length..].chunks(224) { cursor.append(packet).await.unwrap(); }
    let mut wrong: [u8; 32] = Sha256::digest(&body).into();
    wrong[31] ^= 1;
    assert!(cursor.finish(body.len(), wrong, crc32fast::hash(&body)).await.is_err());
    drop(cursor);
    // Failed finishing never authorizes device consumption. Actual valid
    // bytes remain resumable and can pass the original synchronous validator.
    let (mut cursor, complete) = Cursor::open(&root, source.clone()).unwrap();
    assert_eq!(complete, body);
    cursor.finish(&complete).unwrap();
    drop(cursor);
    super::super::release(&root, source).unwrap();
}
