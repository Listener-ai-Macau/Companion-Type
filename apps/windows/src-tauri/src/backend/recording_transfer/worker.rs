//! Keep durable file IO off the BLE receive task. The bounded queue is only
//! staging memory: the existing Cursor remains the sole receipt/lock owner.
use super::{fail, Cursor, Source};
use std::{
    path::Path,
    sync::{atomic::{AtomicU64, Ordering}, Arc,Mutex},
    thread::JoinHandle,
    time::Instant,
};
use tokio::sync::{mpsc, oneshot};

const BATCH_BYTES: usize = 4 * 1024;
const QUEUED_BATCHES: usize = 8;

enum Command {
    Append(Vec<u8>),
    Checkpoint(oneshot::Sender<Result<(), String>>),
    Finish { length: usize, digest: [u8; 32], crc32: u32 },
    #[cfg(test)]
    Pause(std::sync::mpsc::Receiver<()>, oneshot::Sender<()>),
}

#[derive(Default)]
struct Timing {
    total_us: AtomicU64,
    peak_us: AtomicU64,
}

pub(crate) struct ReceiveCursor {
    sender: Option<mpsc::Sender<Command>>,
    complete: Option<oneshot::Receiver<Result<(), String>>>,
    worker: Option<JoinHandle<()>>,
    pending: Vec<u8>,
    accepted_bytes: u64,
    expected_bytes: u64,
    timing: Arc<Timing>,
    queue_wait_us: u64,
    failure:Arc<Mutex<Option<String>>>,
}

impl ReceiveCursor {
    pub(crate) async fn open(root: &Path, source: Source) -> Result<(Self, Vec<u8>), String> {
        let root = root.to_path_buf();
        let (cursor, prefix) = tokio::task::spawn_blocking(move || Cursor::open(&root, source))
            .await.map_err(|_| fail())??;
        Ok((Self::start(cursor)?, prefix))
    }

    fn start(mut cursor: Cursor) -> Result<Self, String> {
        let (sender, mut receiver) = mpsc::channel(QUEUED_BATCHES);
        let (done, complete) = oneshot::channel();
        let timing = Arc::new(Timing::default());
        let worker_timing = timing.clone();
        let failure=Arc::new(Mutex::new(None));let worker_failure=failure.clone();
        let accepted_bytes = cursor.bytes;
        let expected_bytes = u64::from(cursor.receipt.source.total_length);
        let worker = std::thread::Builder::new().name("companion-recording-store".into())
            .spawn(move || {
                let result = (|| {
                    while let Some(command) = receiver.blocking_recv() {
                        match command {
                            Command::Append(bytes) => {
                                let started = Instant::now();
                                let result = cursor.append(&bytes);
                                let us = micros(started);
                                worker_timing.total_us.fetch_add(us, Ordering::Relaxed);
                                worker_timing.peak_us.fetch_max(us, Ordering::Relaxed);
                                result?;
                            },
                            Command::Checkpoint(reply) => {
                                let result = cursor.checkpoint();
                                let _ = reply.send(result.clone());
                                result?;
                            },
                            Command::Finish { length, digest, crc32 } => {
                                return cursor.finish_received(length, digest, crc32);
                            },
                            #[cfg(test)]
                            Command::Pause(resume, entered) => {
                                let _ = entered.send(());
                                resume.recv().map_err(|_| fail())?;
                            },
                        }
                    }
                    // Cancellation/error retains only bytes actually written.
                    // Cursor::drop checkpoints the accepted queue prefix.
                    Ok(())
                })();
                if let Err(error)=&result {
                    // Publish the original failure BEFORE closing the command
                    // channel. A producer blocked on that queue must receive
                    // the real disk/checkpoint error, not a transport failure.
                    if let Ok(mut saved)=worker_failure.lock() {*saved=Some(error.clone());}
                    receiver.close();
                }
                drop(cursor);
                let _ = done.send(result);
            }).map_err(|_| fail())?;
        Ok(Self {
            sender: Some(sender), complete: Some(complete), worker: Some(worker),
            pending: Vec::with_capacity(BATCH_BYTES), accepted_bytes, expected_bytes,
            timing, queue_wait_us: 0,failure,
        })
    }

    pub(crate) async fn append(&mut self, mut bytes: &[u8]) -> Result<(), String> {
        if self.accepted_bytes.saturating_add(bytes.len() as u64) > self.expected_bytes {
            return Err(fail());
        }
        while !bytes.is_empty() {
            let length = bytes.len().min(BATCH_BYTES - self.pending.len());
            self.pending.extend_from_slice(&bytes[..length]);
            self.accepted_bytes += length as u64;
            bytes = &bytes[length..];
            if self.pending.len() == BATCH_BYTES { self.flush_pending().await?; }
        }
        Ok(())
    }

    async fn flush_pending(&mut self) -> Result<(), String> {
        if self.pending.is_empty() { return Ok(()); }
        let started = Instant::now();
        // Reserve before taking the batch: cancelling a blocked send cannot
        // discard a buffer while leaving this object usable with a gap.
        let permit = self.sender.as_ref().ok_or_else(||self.worker_error())?.reserve().await
            .map_err(|_|self.worker_error())?;
        self.queue_wait_us = self.queue_wait_us.saturating_add(micros(started));
        permit.send(Command::Append(std::mem::replace(&mut self.pending, Vec::with_capacity(BATCH_BYTES))));
        Ok(())
    }

    pub(crate) async fn checkpoint(&mut self) -> Result<(), String> {
        self.flush_pending().await?;
        let (reply, response) = oneshot::channel();
        self.sender.as_ref().ok_or_else(||self.worker_error())?.send(Command::Checkpoint(reply)).await
            .map_err(|_|self.worker_error())?;
        response.await.map_err(|_|self.worker_error())?
    }

    pub(crate) async fn finish(&mut self, length: usize, digest: [u8; 32], crc32: u32) -> Result<(), String> {
        if self.accepted_bytes != self.expected_bytes || length as u64 != self.expected_bytes {
            return Err(fail());
        }
        self.flush_pending().await?;
        self.sender.as_ref().ok_or_else(||self.worker_error())?
            .send(Command::Finish { length, digest, crc32 }).await.map_err(|_|self.worker_error())?;
        drop(self.sender.take());
        let result = self.complete.take().ok_or_else(||self.worker_error())?.await.map_err(|_|self.worker_error())?;
        self.join()?;
        result
    }

    // IO runs concurrently, so its duration must not be subtracted from the
    // receive wall clock. Queue wait is the part that blocks receive progress.
    pub(crate) fn timing(&self) -> (u64, u64, u64) {
        (self.timing.total_us.load(Ordering::Relaxed),
         self.timing.peak_us.load(Ordering::Relaxed), self.queue_wait_us)
    }

    fn join(&mut self) -> Result<(), String> {
        if let Some(worker) = self.worker.take() { worker.join().map_err(|_| fail())?; }
        Ok(())
    }
    fn worker_error(&self)->String {
        self.failure.lock().ok().and_then(|saved|saved.clone()).unwrap_or_else(fail)
    }
}

impl Drop for ReceiveCursor {
    fn drop(&mut self) {
        // Error/cancel cleanup drains the bounded queue and closes the file
        // lease before a retry. The <4 KiB unsent tail is replayed from the
        // unchanged board original; it never appears in a durable receipt.
        drop(self.sender.take());
        if self.join().is_err() { eprintln!("recording receive worker failed; durable cursor retained"); }
    }
}

fn micros(started: Instant) -> u64 { started.elapsed().as_micros().min(u128::from(u64::MAX)) as u64 }

#[cfg(test)]
mod tests;
