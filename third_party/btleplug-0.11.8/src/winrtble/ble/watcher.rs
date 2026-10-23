// btleplug Source Code File
//
// Copyright 2020 Nonpolynomial Labs LLC. All rights reserved.
//
// Licensed under the BSD 3-Clause license. See LICENSE file in the project root
// for full license information.
//
// Some portions of this file are taken and/or modified from Rumble
// (https://github.com/mwylde/rumble), using a dual MIT/Apache License under the
// following copyright:
//
// Copyright (c) 2014 The Rust Project Developers

use crate::{api::ScanFilter, Error, Result};
use windows::{core::Ref, Devices::Bluetooth::Advertisement::*, Foundation::TypedEventHandler};

pub type AdvertisementEventHandler =
    Box<dyn Fn(&BluetoothLEAdvertisementReceivedEventArgs) -> windows::core::Result<()> + Send>;

#[derive(Debug)]
pub struct BLEWatcher {
    watcher: BluetoothLEAdvertisementWatcher,
    received_token: Option<i64>,
    stop_required: bool,
}

impl From<windows::core::Error> for Error {
    fn from(err: windows::core::Error) -> Error {
        Error::Other(format!("{:?}", err).into())
    }
}

impl BLEWatcher {
    pub fn new() -> Result<Self> {
        let ad = BluetoothLEAdvertisementFilter::new()?;
        let watcher = BluetoothLEAdvertisementWatcher::Create(&ad)?;
        Ok(BLEWatcher {
            watcher,
            received_token: None,
            stop_required: false,
        })
    }

    pub fn start(
        &mut self,
        filter: ScanFilter,
        on_received: AdvertisementEventHandler,
    ) -> Result<()> {
        // Stop is asynchronous. Let the caller observe a pending stop instead of
        // restarting a watcher while Windows is still shutting it down.
        if self.watcher.Status()? == BluetoothLEAdvertisementWatcherStatus::Stopping {
            return Err(Error::Other(
                "Bluetooth advertisement watcher is still stopping".into(),
            ));
        }
        let ScanFilter { services } = filter;
        let ad = self.watcher.AdvertisementFilter()?.Advertisement()?;
        let ad_services = ad.ServiceUuids()?;
        ad_services.Clear()?;
        for service in services {
            ad_services.Append(windows::core::GUID::from(service.as_u128()))?;
        }
        self.watcher
            .SetScanningMode(BluetoothLEScanningMode::Active)?;
        let _ = self.watcher.SetAllowExtendedAdvertisements(true);
        let handler: TypedEventHandler<
            BluetoothLEAdvertisementWatcher,
            BluetoothLEAdvertisementReceivedEventArgs,
        > = TypedEventHandler::new(
            move |_sender, args: Ref<BluetoothLEAdvertisementReceivedEventArgs>| {
                if let Ok(args) = args.ok() {
                    on_received(args)?;
                }
                Ok(())
            },
        );

        // One owned callback, including repeated starts on the same adapter.
        self.remove_received()?;
        self.received_token = Some(self.watcher.Received(&handler)?);
        self.stop_required = true;
        if let Err(err) = self.watcher.Start() {
            if let Err(cleanup_err) = self.stop() {
                log::warn!(
                    "advertisement watcher start cleanup failed: {}",
                    cleanup_err
                );
            }
            return Err(err.into());
        }
        Ok(())
    }

    fn remove_received(&mut self) -> Result<()> {
        if let Some(token) = self.received_token {
            self.watcher.RemoveReceived(token)?;
            self.received_token = None;
        }
        Ok(())
    }

    pub fn stop(&mut self) -> Result<()> {
        let stopped = if self.stop_required {
            self.watcher.Stop().map_err(Error::from)
        } else {
            Ok(())
        };
        if stopped.is_ok() {
            self.stop_required = false;
        }
        // Revoke our callback even if Stop fails; retain a failed token so Drop
        // can attempt cleanup again. Other applications' watchers are untouched.
        let revoked = self.remove_received();
        stopped.and(revoked)
    }
}

impl Drop for BLEWatcher {
    fn drop(&mut self) {
        if let Err(err) = self.stop() {
            log::warn!("advertisement watcher cleanup failed: {}", err);
        }
    }
}
