// btleplug Source Code File
//
// Copyright 2020 Nonpolynomial. All rights reserved.
//
// Licensed under the BSD 3-Clause license. See LICENSE file in the project root
// for full license information.

#[cfg(test)]
use crate::api::ValueNotification;
use futures::stream::{Stream, StreamExt};
use std::pin::Pin;
use tokio::sync::broadcast::Receiver;
use tokio_stream::wrappers::BroadcastStream;

pub const WINDOWS_NOTIFICATION_CAPACITY: usize = 512;

/// Keep overflow visible to consumers that must recover an exact byte stream.
/// The ordinary trait API remains source compatible for other BLE consumers.
pub fn checked_notifications_stream_from_broadcast_receiver<T: Clone + Send + 'static>(
    receiver: Receiver<T>,
) -> Pin<Box<dyn Stream<Item = crate::Result<T>> + Send>> {
    Box::pin(BroadcastStream::new(receiver).map(|value| {
        value.map_err(|error| crate::Error::RuntimeError(format!(
            "Windows BLE notification queue overflow: {error}; resume from the durable offset"
        )))
    }))
}

pub fn notifications_stream_from_broadcast_receiver<T: Clone + Send + 'static>(
    receiver: Receiver<T>,
) -> Pin<Box<dyn Stream<Item = T> + Send>> {
    Box::pin(BroadcastStream::new(receiver).filter_map(|x| async move { x.ok() }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::sync::broadcast;

    fn value(index: u32) -> ValueNotification {
        ValueNotification { uuid: uuid::Uuid::nil(), value: index.to_le_bytes().to_vec() }
    }

    #[tokio::test]
    async fn notification_queue_preserves_an_unpolled_64_packet_windows_burst() {
        let (sender, receiver) = broadcast::channel(WINDOWS_NOTIFICATION_CAPACITY);
        let mut stream = checked_notifications_stream_from_broadcast_receiver(receiver);
        // No reader runs during the entire callback burst. The upstream 16-item
        // ring dropped 48 values here before any downstream worker could help.
        for index in 0..64 { sender.send(value(index)).unwrap(); }
        for index in 0..64 {
            assert_eq!(stream.next().await.unwrap().unwrap().value, (index as u32).to_le_bytes());
        }
    }

    #[tokio::test]
    async fn notification_queue_reports_native_overflow_before_surviving_values() {
        let (sender, receiver) = broadcast::channel(WINDOWS_NOTIFICATION_CAPACITY);
        let mut stream = checked_notifications_stream_from_broadcast_receiver(receiver);
        for index in 0..WINDOWS_NOTIFICATION_CAPACITY as u32 + 1 { sender.send(value(index)).unwrap(); }
        assert!(stream.next().await.unwrap().unwrap_err().to_string().contains("queue overflow"));
        for index in 1..=WINDOWS_NOTIFICATION_CAPACITY {
            assert_eq!(stream.next().await.unwrap().unwrap().value, (index as u32).to_le_bytes());
        }
        drop(sender);
        assert!(stream.next().await.is_none());
    }

    #[tokio::test]
    async fn notification_queue_keeps_callback_time_across_a_delayed_drain() {
        let (sender, receiver) = broadcast::channel(WINDOWS_NOTIFICATION_CAPACITY);
        let mut stream = checked_notifications_stream_from_broadcast_receiver(receiver);
        let first = std::time::Instant::now();
        for index in 0..64 {
            sender.send((value(index), first + std::time::Duration::from_millis(index as u64))).unwrap();
        }
        for index in 0..64 {
            let (notification, received_at) = stream.next().await.unwrap().unwrap();
            assert_eq!(notification.value, (index as u32).to_le_bytes());
            assert_eq!(received_at, first + std::time::Duration::from_millis(index as u64));
        }
    }
}
