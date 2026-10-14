//! A notification lease reused by prefixes and retained backlog entries.
//! Completed receive streams are released before a physical consume command.

use std::time::Duration;

use btleplug::{api::{CharPropFlags, Characteristic, Peripheral as _}, platform::Peripheral};
use futures::future::BoxFuture;
use tokio::time::timeout;

use super::{find_characteristic, RECORDING_CHUNK_PULL_UUID, RECORDING_CHUNK_PULL_B_UUID};
use super::pull_receiver::{NotificationReceiver, ReceivedNotification};

pub(super) trait SubscriptionPort: Clone + Send + Sync + 'static {
    fn subscribe(&self, lane: usize) -> BoxFuture<'_, Result<(), String>>;
    fn unsubscribe(&self, lane: usize) -> BoxFuture<'_, Result<(), String>>;
}

#[derive(Clone)]
pub(super) struct NativeSubscriptions {
    pub(super) peripheral: Peripheral,
    pub(super) lanes: Vec<Characteristic>,
}
impl SubscriptionPort for NativeSubscriptions {
    fn subscribe(&self, lane: usize) -> BoxFuture<'_, Result<(), String>> {
        Box::pin(async move {
            self.peripheral.subscribe(&self.lanes[lane]).await
                .map_err(|e| format!("subscribe recording lane {}: {e}", lane + 1))
        })
    }
    fn unsubscribe(&self, lane: usize) -> BoxFuture<'_, Result<(), String>> {
        Box::pin(async move {
            self.peripheral.unsubscribe(&self.lanes[lane]).await
                .map_err(|e| format!("unsubscribe recording lane {}: {e}", lane + 1))
        })
    }
}

pub(super) struct SubscriptionLease<P: SubscriptionPort> {
    port: P,
    active: [bool; 2],
    cleanup_timeout: Duration,
}
impl<P: SubscriptionPort> SubscriptionLease<P> {
    pub(super) async fn open(port: P, lanes: usize, read_timeout: Duration) -> Result<Self, String> {
        let mut lease = Self { port, active: [false; 2], cleanup_timeout: read_timeout.min(Duration::from_secs(1)) };
        for lane in 0..lanes {
            // A timed-out/cancelled CCCD write may still have reached Windows.
            // Record intent before awaiting so its cleanup is never skipped.
            lease.active[lane] = true;
            let result = timeout(read_timeout, lease.port.subscribe(lane)).await
                .map_err(|_| format!("subscribe recording lane {} timed out", lane + 1))
                .and_then(|r| r);
            if let Err(error) = result {
                lease.close().await;
                return Err(error);
            }
        }
        Ok(lease)
    }

    async fn close(&mut self) {
        for lane in 0..self.active.len() {
            if self.active[lane] {
                cleanup_lane(&self.port, lane, self.cleanup_timeout).await;
                self.active[lane] = false;
            }
        }
    }

    pub(super) async fn quiesce_for_control(&mut self) -> Result<(), String> {
        let mut failures = Vec::new();
        for lane in 0..self.active.len() {
            if !self.active[lane] { continue; }
            let result = timeout(self.cleanup_timeout, self.port.unsubscribe(lane)).await;
            // Every owned lane gets one bounded close attempt even if another
            // fails. A failed close retires the connection; it cannot authorize
            // an exact consume or trigger a second cleanup from Drop.
            self.active[lane] = false;
            match result {
                Ok(Ok(())) => {},
                Ok(Err(error)) => failures.push(error),
                Err(_) => failures.push(format!("recording lane {} release timed out", lane + 1)),
            }
        }
        if failures.is_empty() { Ok(()) }
        else { Err(format!("sealed stream release failed before reclaim: {}", failures.join("; "))) }
    }
}
async fn cleanup_lane<P: SubscriptionPort>(port: &P, lane: usize, deadline: Duration) {
    match timeout(deadline, port.unsubscribe(lane)).await {
        Ok(Ok(())) => {},
        Ok(Err(e)) => eprintln!("recording session cleanup: {e}"),
        Err(_) => eprintln!("recording session cleanup lane {} timed out", lane + 1),
    }
}
impl<P: SubscriptionPort> Drop for SubscriptionLease<P> {
    fn drop(&mut self) {
        if !self.active.iter().any(|v| *v) { return; }
        let active = std::mem::replace(&mut self.active, [false; 2]);
        let port = self.port.clone();
        let deadline = self.cleanup_timeout;
        // Normal exits await close. A cancelled async operation still schedules
        // bounded cleanup; no blocking wait or permanent parameter override.
        if let Ok(runtime) = tokio::runtime::Handle::try_current() {
            runtime.spawn(async move {
                for (lane, active) in active.into_iter().enumerate() {
                    if active { cleanup_lane(&port, lane, deadline).await; }
                }
            });
        } else {
            eprintln!("recording session cleanup requires the BLE runtime; connection owner must disconnect");
        }
    }
}

pub(super) struct PullSession {
    pub chunk: Characteristic,
    pub dual_lane: bool,
    pub notifications: NotificationReceiver,
    lease: SubscriptionLease<NativeSubscriptions>,
}
impl PullSession {
    pub async fn open(peripheral: &Peripheral, characteristics: &std::collections::BTreeSet<Characteristic>, read_timeout: Duration)
        -> Result<Self, String>
    {
        let chunk = find_characteristic(characteristics, RECORDING_CHUNK_PULL_UUID)?;
        if !chunk.properties.intersects(CharPropFlags::WRITE | CharPropFlags::WRITE_WITHOUT_RESPONSE)
            || !chunk.properties.contains(CharPropFlags::NOTIFY) {
            return Err("recording_chunk_pull must support WRITE+NOTIFY".into());
        }
        let second = find_characteristic(characteristics, RECORDING_CHUNK_PULL_B_UUID).ok();
        if second.as_ref().is_some_and(|c| !c.properties.contains(CharPropFlags::NOTIFY)) {
            return Err("recording_chunk_pull_b (3004) present but not notifiable; dual-lane required".into());
        }
        // Register the receiver before either CCCD can enable notifications.
        #[cfg(not(windows))]
        let notifications = timeout(read_timeout, peripheral.notifications()).await
            .map_err(|_| "open BLE notification stream timed out".to_string())?
            .map_err(|e| format!("open BLE notification stream: {e}"))?;
        #[cfg(not(windows))]
        let notifications = Box::pin(futures::StreamExt::map(notifications, |notification|
            Ok(ReceivedNotification { notification, received_at: std::time::Instant::now() })));
        #[cfg(windows)]
        let notifications = Box::pin(futures::StreamExt::map(peripheral.checked_notifications(),
            |value| value.map(|(notification, received_at)| ReceivedNotification { notification, received_at })
                .map_err(|e| format!("recording native receive: {e}"))));
        let notifications = NotificationReceiver::start(notifications)?;
        let dual_lane = second.is_some();
        let mut lanes = vec![chunk.clone()];
        if let Some(second) = second { lanes.push(second); }
        let count = lanes.len();
        let lease = SubscriptionLease::open(NativeSubscriptions { peripheral: peripheral.clone(), lanes }, count, read_timeout).await?;
        eprintln!("recording pull session opened dual_lane={dual_lane} reused_until_connection_end=1");
        Ok(Self { chunk, dual_lane, notifications, lease })
    }

    pub async fn close(session: &mut Option<Self>) {
        if let Some(mut current) = session.take() {
            current.notifications.close();
            current.lease.close().await;
        }
    }

    pub async fn quiesce_for_control(session: &mut Option<Self>) -> Result<(), String> {
        let Some(mut current) = session.take() else { return Ok(()); };
        current.notifications.close();
        current.lease.quiesce_for_control().await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, Mutex};

    #[derive(Clone, Default)]
    struct Port {
        calls: Arc<Mutex<Vec<(bool, usize)>>>,
        fail_second: bool,
        pending_second: bool,
        fail_first_release: bool,
        pending_first_release: bool,
    }
    impl SubscriptionPort for Port {
        fn subscribe(&self, lane: usize) -> BoxFuture<'_, Result<(), String>> {
            Box::pin(async move {
                self.calls.lock().unwrap().push((true, lane));
                if lane == 1 && self.pending_second { futures::future::pending::<()>().await; }
                if lane == 1 && self.fail_second { Err("second lane failed".into()) } else { Ok(()) }
            })
        }
        fn unsubscribe(&self, lane: usize) -> BoxFuture<'_, Result<(), String>> {
            Box::pin(async move {
                self.calls.lock().unwrap().push((false, lane));
                if lane == 0 && self.pending_first_release { futures::future::pending::<()>().await; }
                if lane == 0 && self.fail_first_release { Err("native first lane release failed".into()) } else { Ok(()) }
            })
        }
    }

    #[tokio::test]
    async fn one_lease_keeps_both_lanes_until_explicit_connection_close() {
        let port = Port::default();
        let mut lease = SubscriptionLease::open(port.clone(), 2, Duration::from_secs(1)).await.unwrap();
        assert_eq!(*port.calls.lock().unwrap(), [(true, 0), (true, 1)]);
        // Several prefix/window consumers reuse the lease; none re-arm CCCD.
        assert_eq!(lease.active, [true, true]);
        lease.close().await;
        lease.close().await;
        drop(lease);
        assert_eq!(*port.calls.lock().unwrap(), [(true, 0), (true, 1), (false, 0), (false, 1)]);
    }

    #[tokio::test]
    async fn second_lane_failure_rolls_back_the_first_and_uncertain_second_write() {
        let port = Port { fail_second: true, ..Default::default() };
        assert!(SubscriptionLease::open(port.clone(), 2, Duration::from_secs(1)).await.is_err());
        assert_eq!(*port.calls.lock().unwrap(), [(true, 0), (true, 1), (false, 0), (false, 1)]);
    }

    #[tokio::test]
    async fn cancelled_open_cleans_already_subscribed_and_inflight_lanes() {
        let port = Port { pending_second: true, ..Default::default() };
        let worker_port = port.clone();
        let worker = tokio::spawn(async move { SubscriptionLease::open(worker_port, 2, Duration::from_secs(1)).await });
        while port.calls.lock().unwrap().len() < 2 { tokio::task::yield_now().await; }
        worker.abort();
        let _ = worker.await;
        timeout(Duration::from_secs(1), async {
            while port.calls.lock().unwrap().len() < 4 { tokio::task::yield_now().await; }
        }).await.unwrap();
        assert_eq!(*port.calls.lock().unwrap(), [(true, 0), (true, 1), (false, 0), (false, 1)]);
    }

    #[tokio::test]
    async fn control_handoff_requires_both_releases_and_failure_still_closes_other_lane() {
        for port in [Port::default(), Port { fail_first_release: true, ..Default::default() },
                     Port { pending_first_release: true, ..Default::default() }] {
            let success = !port.fail_first_release && !port.pending_first_release;
            let mut lease = SubscriptionLease::open(port.clone(), 2, Duration::from_millis(10)).await.unwrap();
            assert_eq!(lease.quiesce_for_control().await.is_ok(), success);
            drop(lease);
            assert_eq!(*port.calls.lock().unwrap(), [(true, 0), (true, 1), (false, 0), (false, 1)]);
        }
    }
}
