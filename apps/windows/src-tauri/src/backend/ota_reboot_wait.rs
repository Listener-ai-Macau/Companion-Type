//! A restart availability hint, never an installed-version receipt.
//! Observe only our own passive watcher. Do not send GATT requests while Boot
//! is installing, and leave one ordinary verification budget if scanning is
//! unavailable or Windows does not deliver a matching advertisement.

use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use windows::Devices::Bluetooth::Advertisement::{
    BluetoothLEAdvertisementWatcher, BluetoothLEAdvertisementReceivedEventArgs,
    BluetoothLEAdvertisementWatcherStatus, BluetoothLEScanningMode,
};
use windows::Foundation::{EventRegistrationToken, TypedEventHandler};

pub(super) struct Observation {
    pub elapsed_ms: u128,
    pub fresh_advertisement: bool,
    pub fallback_reason: Option<String>,
}

struct WatchLease {
    watcher: BluetoothLEAdvertisementWatcher,
    token: Option<EventRegistrationToken>,
    stop_required: bool,
}
impl WatchLease {
    fn close(&mut self) -> Result<(), String> {
        let stop = if self.stop_required {
            self.watcher.Stop().map_err(|e| format!("restart watcher Stop: {e}"))
        } else { Ok(()) };
        if stop.is_ok() { self.stop_required = false; }
        let revoke = if let Some(token) = self.token {
            self.watcher.RemoveReceived(token)
                .map(|_| self.token = None)
                .map_err(|e| format!("restart watcher RemoveReceived: {e}"))
        } else { Ok(()) };
        stop.and(revoke)
    }
}
impl Drop for WatchLease {
    fn drop(&mut self) {
        if let Err(e) = self.close() { eprintln!("[companion-ota] restart_watcher_cleanup error={e}"); }
    }
}

pub(super) fn wait(address: u64, deadline: Instant) -> Result<Observation, String> {
    let started = Instant::now();
    // A discovery plus signed running-receipt check must still fit the original
    // installation deadline. No new fixed assumption about Boot duration.
    let observe_until = deadline.checked_sub(Duration::from_secs(20)).unwrap_or(deadline);
    let mut result = Observation { elapsed_ms: 0, fresh_advertisement: false, fallback_reason: None };
    let unix_ticks = SystemTime::now().duration_since(UNIX_EPOCH)
        .map_err(|e| format!("restart observation clock: {e}"))?.as_nanos() / 100;
    let earliest = i64::try_from(unix_ticks).map_err(|_| "restart timestamp overflow")?
        .checked_add(116_444_736_000_000_000).ok_or("restart timestamp overflow")?;
    let seen = Arc::new(AtomicBool::new(false));
    let observed = seen.clone();
    let watcher = match BluetoothLEAdvertisementWatcher::new() {
        Ok(w) => w,
        Err(e) => {
            result.fallback_reason = Some(format!("watcher unavailable: {e}"));
            return Ok(result);
        }
    };
    let mut lease = WatchLease { watcher, token: None, stop_required: false };
    let setup = (|| -> Result<(), String> {
        lease.watcher.SetScanningMode(BluetoothLEScanningMode::Passive).map_err(|e| e.to_string())?;
        let handler = TypedEventHandler::<BluetoothLEAdvertisementWatcher, BluetoothLEAdvertisementReceivedEventArgs>::new(move |_, args| {
            if let Some(args) = args.as_ref() {
                // A fresh packet is only permission to try GATT. The existing
                // protected UID, App/UI IDs and signed WSI3 remain mandatory.
                if args.BluetoothAddress().ok() == Some(address)
                    && args.IsConnectable().unwrap_or(false)
                    && args.Timestamp().is_ok_and(|t| t.UniversalTime >= earliest) {
                    observed.store(true, Ordering::Release);
                }
            }
            Ok(())
        });
        lease.token = Some(lease.watcher.Received(&handler).map_err(|e| e.to_string())?);
        lease.stop_required = true;
        lease.watcher.Start().map_err(|e| e.to_string())
    })();
    if let Err(e) = setup {
        result.fallback_reason = Some(format!("passive observation unavailable: {e}"));
    } else {
        loop {
            if seen.load(Ordering::Acquire) { result.fresh_advertisement = true; break; }
            if Instant::now() >= observe_until {
                result.fallback_reason = Some("no fresh advertisement; reserved ordinary verification budget".into());
                break;
            }
            match lease.watcher.Status() {
                Ok(BluetoothLEAdvertisementWatcherStatus::Aborted | BluetoothLEAdvertisementWatcherStatus::Stopped) => {
                    result.fallback_reason = Some("passive watcher stopped before restart observation".into());
                    break;
                }
                Err(e) => { result.fallback_reason = Some(format!("passive watcher status: {e}")); break; }
                _ => {}
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }
    lease.close()?;
    result.elapsed_ms = started.elapsed().as_millis();
    Ok(result)
}
