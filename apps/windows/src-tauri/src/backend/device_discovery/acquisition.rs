//! A finite scan demand during an explicit known-device connection. The paired
//! address path otherwise asks Windows to connect without active discovery.
use std::sync::{Arc,atomic::{AtomicU64,Ordering}};
use std::time::Instant;
use windows::Devices::Bluetooth::Advertisement::{BluetoothLEAdvertisementWatcher,
    BluetoothLEAdvertisementReceivedEventArgs,BluetoothLEScanningMode,BluetoothLEAdvertisementWatcherStatus};
use windows::Foundation::{EventRegistrationToken,TypedEventHandler};

pub(crate) struct Acquisition {
    watcher:BluetoothLEAdvertisementWatcher,
    token:Option<EventRegistrationToken>,
    started:Instant,
    first:Arc<AtomicU64>,
}
impl Acquisition {
    // None means observation was unavailable, not that the device was absent.
    pub(crate) fn target_observed(&self)->Option<bool> {
        (self.watcher.Status().ok()==Some(BluetoothLEAdvertisementWatcherStatus::Started))
            .then(||self.first.load(Ordering::Relaxed)!=0)
    }
    pub(crate) fn begin(address:&str)->Option<Self> {
        let compact=address.replace([':', '-'],"");
        if compact.len()!=12 {return None;}
        let address=u64::from_str_radix(&compact,16).ok()?;
        let watcher=match BluetoothLEAdvertisementWatcher::new() {
            Ok(w)=>w,Err(e)=>{eprintln!("BLE acquisition_scan started=0 error={e}");return None;}
        };
        let started=Instant::now();let first=Arc::new(AtomicU64::new(0));
        let mut lease=Self{watcher,token:None,started,first:first.clone()};
        let result=(||->windows::core::Result<()> {
            lease.watcher.SetScanningMode(BluetoothLEScanningMode::Active)?;
            let handler=TypedEventHandler::<BluetoothLEAdvertisementWatcher,BluetoothLEAdvertisementReceivedEventArgs>::new(move |_,args| {
                if args.as_ref().is_some_and(|a|a.BluetoothAddress().ok()==Some(address)) {
                    let elapsed=started.elapsed().as_micros().min(u128::from(u64::MAX)) as u64;
                    let _=first.compare_exchange(0,elapsed.max(1),Ordering::Relaxed,Ordering::Relaxed);
                }
                Ok(())
            });
            lease.token=Some(lease.watcher.Received(&handler)?);
            lease.watcher.Start()
        })();
        match result {
            Ok(())=>{eprintln!("BLE acquisition_scan started=1 scope=connection_setup fixed_wait_ms=0");Some(lease)}
            Err(e)=>{eprintln!("BLE acquisition_scan started=0 error={e}");None}
        }
    }
}
impl Drop for Acquisition {
    fn drop(&mut self) {
        let stop=self.watcher.Stop();
        let revoke=self.token.take().map(|t|self.watcher.RemoveReceived(t));
        eprintln!("BLE acquisition_scan ended=1 elapsed_us={} target_first_advertisement_us={} stopped={} handler_removed={}",
            self.started.elapsed().as_micros(),self.first.load(Ordering::Relaxed),stop.is_ok(),revoke.is_none_or(|r|r.is_ok()));
    }
}
