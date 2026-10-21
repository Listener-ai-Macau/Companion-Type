//! Drain the Windows notification stream independently of validation and disk IO.
//! The pinned Windows dependency exposes native queue lag instead of hiding it.
//! Waiting for storage in the pull future must not leave that receiver unpolled.

use std::{
    pin::Pin,
    sync::{atomic::{AtomicUsize, Ordering}, Arc, Mutex},
    task::{Context, Poll},
    thread::JoinHandle,
    time::Instant,
};

use btleplug::api::ValueNotification;
use futures::{future::{AbortHandle, Abortable}, Stream, StreamExt};
use tokio::sync::mpsc;

use super::{RECORDING_CHUNK_PULL_UUID, RECORDING_CHUNK_PULL_B_UUID};

const QUEUE_PACKETS: usize = 512;
const MAX_VALUE_BYTES: usize = 512;

pub(super) struct ReceivedNotification {
    pub notification: ValueNotification,
    pub received_at: Instant,
}

#[derive(Default)]
struct Stats {
    accepted: AtomicUsize,
    high_water: AtomicUsize,
}

pub(super) struct NotificationReceiver {
    receiver: mpsc::Receiver<ReceivedNotification>,
    failure: Arc<Mutex<Option<String>>>,
    stats: Arc<Stats>,
    abort: AbortHandle,
    worker: Option<JoinHandle<()>>,
}

impl NotificationReceiver {
    pub fn start(mut input: Pin<Box<dyn Stream<Item = Result<ReceivedNotification, String>> + Send>>) -> Result<Self, String> {
        let (sender, receiver) = mpsc::channel(QUEUE_PACKETS);
        let failure = Arc::new(Mutex::new(None));
        let worker_failure = failure.clone();
        let stats = Arc::new(Stats::default());
        let worker_stats = stats.clone();
        let (abort, registration) = AbortHandle::new_pair();
        // Native BLE is driven by a current-thread runtime. A task on that same
        // runtime cannot drain notifications while its caller blocks. This
        // stream only waits on btleplug's broadcast receiver, not WinRT calls;
        // its waker works on an independent executor without a second radio,
        // GATT subscription, connection or throughput preference.
        let worker = std::thread::Builder::new().name("companion-recording-rx".into())
            .spawn(move || {
                let receive = async move {
                    while let Some(notification) = input.next().await {
                        let ReceivedNotification { notification, received_at } = match notification {
                            Ok(value) => value,
                            Err(error) => {
                                *worker_failure.lock().unwrap_or_else(|e| e.into_inner()) = Some(error);
                                return;
                            },
                        };
                        if notification.uuid != RECORDING_CHUNK_PULL_UUID
                            && notification.uuid != RECORDING_CHUNK_PULL_B_UUID { continue; }
                        if notification.value.len() > MAX_VALUE_BYTES {
                            *worker_failure.lock().unwrap_or_else(|e| e.into_inner()) =
                                Some("recording notification exceeds the GATT value limit".into());
                            return;
                        }
                        match sender.try_send(ReceivedNotification { notification, received_at }) {
                            Ok(()) => {
                                worker_stats.accepted.fetch_add(1, Ordering::Release);
                                worker_stats.high_water.fetch_max(QUEUE_PACKETS - sender.capacity(), Ordering::Relaxed);
                            },
                            Err(mpsc::error::TrySendError::Full(_)) => {
                                // Never hide a second overflow or grow without
                                // bound. Drain the accepted prefix, then fail
                                // so the existing durable-offset retry can run.
                                *worker_failure.lock().unwrap_or_else(|e| e.into_inner()) = Some(
                                    "recording receive queue overflow; original recording not consumed".into());
                                return;
                            },
                            Err(mpsc::error::TrySendError::Closed(_)) => return,
                        }
                    }
                    *worker_failure.lock().unwrap_or_else(|e| e.into_inner()) =
                        Some("recording notification stream ended".into());
                };
                let _ = futures::executor::block_on(Abortable::new(receive, registration));
            }).map_err(|e| format!("start recording notification receiver: {e}"))?;
        Ok(Self { receiver, failure, stats, abort, worker: Some(worker) })
    }

    pub fn close(&mut self) {
        self.receiver.close();
        self.abort.abort();
        if let Some(worker) = self.worker.take() {
            if worker.join().is_err() {
                *self.failure.lock().unwrap_or_else(|e| e.into_inner()) =
                    Some("recording notification receiver failed".into());
            }
            eprintln!("recording receive_queue accepted={} high_water={} capacity={} receiver_joined=1",
                self.stats.accepted.load(Ordering::Relaxed), self.stats.high_water.load(Ordering::Relaxed), QUEUE_PACKETS);
        }
    }
}

impl Stream for NotificationReceiver {
    type Item = Result<ReceivedNotification, String>;

    fn poll_next(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Option<Self::Item>> {
        match self.receiver.poll_recv(cx) {
            Poll::Ready(Some(value)) => Poll::Ready(Some(Ok(value))),
            Poll::Ready(None) => Poll::Ready(self.failure.lock().unwrap_or_else(|e| e.into_inner()).take().map(Err)),
            Poll::Pending => Poll::Pending,
        }
    }
}

impl Drop for NotificationReceiver {
    fn drop(&mut self) { self.close(); }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{sync::atomic::AtomicBool, time::Duration};

    fn packet(index: u32) -> ValueNotification {
        ValueNotification {
            uuid: if index % 2 == 0 { RECORDING_CHUNK_PULL_UUID } else { RECORDING_CHUNK_PULL_B_UUID },
            value: index.to_le_bytes().to_vec(),
        }
    }

    fn observed(notification: ValueNotification) -> ReceivedNotification {
        ReceivedNotification { notification, received_at: Instant::now() }
    }

    // Same 16-item broadcast and ignored lag used by locked btleplug 0.11.8.
    fn small_broadcast() -> (tokio::sync::broadcast::Sender<ValueNotification>,
        Pin<Box<dyn Stream<Item = ValueNotification> + Send>>) {
        let (sender, receiver) = tokio::sync::broadcast::channel(16);
        let stream = futures::stream::unfold(receiver, |mut receiver| async move {
            loop {
                match receiver.recv().await {
                    Ok(value) => return Some((value, receiver)),
                    Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => continue,
                    Err(tokio::sync::broadcast::error::RecvError::Closed) => return None,
                }
            }
        });
        (sender, Box::pin(stream))
    }

    #[tokio::test]
    async fn blocked_product_thread_does_not_lose_the_small_broadcast_or_arrival_times() {
        let (old_sender, mut old_input) = small_broadcast();
        for index in 0..64 { old_sender.send(packet(index)).unwrap(); }
        // Reproduce the unpolled receiver: the first 48 notifications disappear.
        assert_eq!(old_input.next().await.unwrap().value, 48u32.to_le_bytes());

        let (sender, input) = small_broadcast();
        let mut receiver = NotificationReceiver::start(Box::pin(input.map(|value| Ok(observed(value))))).unwrap();
        let stats = receiver.stats.clone();
        let producer = std::thread::spawn(move || {
            for index in 0..64 {
                sender.send(packet(index)).unwrap();
                if index % 8 == 7 {
                    let deadline = Instant::now() + Duration::from_secs(2);
                    while stats.accepted.load(Ordering::Acquire) < index as usize + 1 {
                        assert!(Instant::now() < deadline, "independent receiver was blocked");
                        std::thread::sleep(Duration::from_millis(1));
                    }
                }
            }
            sender
        });
        // Deliberately block the current-thread async runtime like synchronous
        // work or a stalled caller. A task on this runtime would deadlock here.
        let _sender = producer.join().unwrap();
        let consumer_started = Instant::now();
        for index in 0..64 {
            let received = receiver.next().await.unwrap().unwrap();
            assert_eq!(received.notification.value, (index as u32).to_le_bytes());
            assert!(received.received_at <= consumer_started);
        }
        receiver.close();
        assert!(receiver.worker.is_none());
    }

    #[tokio::test]
    async fn queue_overflow_is_bounded_and_reported_after_the_ordered_prefix() {
        let input = Box::pin(futures::stream::iter((0..QUEUE_PACKETS as u32 + 1).map(|n| Ok(observed(packet(n))))));
        let mut receiver = NotificationReceiver::start(input).unwrap();
        let deadline = Instant::now() + Duration::from_secs(2);
        while !receiver.worker.as_ref().unwrap().is_finished() {
            assert!(Instant::now() < deadline);
            std::thread::sleep(Duration::from_millis(1));
        }
        assert_eq!(receiver.stats.accepted.load(Ordering::Acquire), QUEUE_PACKETS);
        assert_eq!(receiver.stats.high_water.load(Ordering::Relaxed), QUEUE_PACKETS);
        for index in 0..QUEUE_PACKETS {
            assert_eq!(receiver.next().await.unwrap().unwrap().notification.value, (index as u32).to_le_bytes());
        }
        assert!(receiver.next().await.unwrap().err().unwrap().contains("queue overflow"));
        assert!(receiver.next().await.is_none());
    }

    #[test]
    fn cancellation_joins_an_idle_receiver_and_drops_its_upstream_subscription() {
        struct Idle(Arc<AtomicBool>);
        impl Stream for Idle {
            type Item = Result<ReceivedNotification, String>;
            fn poll_next(self: Pin<&mut Self>, _: &mut Context<'_>) -> Poll<Option<Self::Item>> { Poll::Pending }
        }
        impl Drop for Idle {
            fn drop(&mut self) { self.0.store(true, Ordering::Release); }
        }
        let dropped = Arc::new(AtomicBool::new(false));
        let mut receiver = NotificationReceiver::start(Box::pin(Idle(dropped.clone()))).unwrap();
        receiver.close();
        assert!(dropped.load(Ordering::Acquire));
        assert!(receiver.worker.is_none());
    }

    #[tokio::test]
    async fn native_lag_is_an_explicit_failure_after_the_received_prefix() {
        let input = futures::stream::iter([
            Ok(observed(packet(0))), Ok(observed(packet(1))), Err("native queue overflow; resume required".into()),
            Ok(observed(packet(3))),
        ]);
        let mut receiver = NotificationReceiver::start(Box::pin(input)).unwrap();
        for index in 0..2 {
            assert_eq!(receiver.next().await.unwrap().unwrap().notification.value, (index as u32).to_le_bytes());
        }
        assert!(receiver.next().await.unwrap().err().unwrap().contains("native queue overflow"));
        assert!(receiver.next().await.is_none());
        receiver.close();
    }

    #[tokio::test]
    async fn receiver_keeps_native_callback_time_instead_of_retiming_queued_data() {
        let received_at = Instant::now() - Duration::from_secs(1);
        let input = futures::stream::iter([Ok(ReceivedNotification { notification: packet(0), received_at })]);
        let mut receiver = NotificationReceiver::start(Box::pin(input)).unwrap();
        assert_eq!(receiver.next().await.unwrap().unwrap().received_at, received_at);
        receiver.close();
    }
}
