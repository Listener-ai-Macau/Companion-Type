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

use super::{ble::watcher::BLEWatcher, peripheral::Peripheral, peripheral::PeripheralId};
use crate::{
    api::{BDAddr, Central, CentralEvent, CentralState, ScanFilter},
    common::adapter_manager::AdapterManager,
    Error, Result,
};
use async_trait::async_trait;
use futures::stream::Stream;
use std::convert::TryInto;
use std::fmt::{self, Debug, Formatter};
use std::pin::Pin;
use std::sync::{Arc, Mutex};
use windows::{
    core::Ref,
    Devices::Radios::{Radio, RadioState},
    Foundation::TypedEventHandler,
};

/// Implementation of [api::Central](crate::api::Central).
#[derive(Clone)]
pub struct Adapter {
    watcher: Arc<Mutex<BLEWatcher>>,
    manager: Arc<AdapterManager<Peripheral>>,
    radio: Radio,
    // Clones share one registration; dropping a temporary Adapter must not
    // unsubscribe another live owner.
    _radio_state_subscription: Option<Arc<RadioStateSubscription>>,
}

struct RadioStateSubscription {
    radio: Radio,
    token: i64,
}

impl Drop for RadioStateSubscription {
    fn drop(&mut self) {
        if let Err(err) = self.radio.RemoveStateChanged(self.token) {
            log::warn!("radio state subscription cleanup failed: {}", err);
        }
    }
}

// https://github.com/microsoft/windows-rs/blob/master/crates/libs/windows/src/Windows/Devices/Radios/mod.rs
fn get_central_state(radio: &Radio) -> CentralState {
    let state = radio.State().unwrap_or(RadioState::Unknown);
    match state {
        RadioState::On => CentralState::PoweredOn,
        RadioState::Off => CentralState::PoweredOff,
        _ => CentralState::Unknown,
    }
}

impl Adapter {
    pub(crate) fn new(radio: Radio) -> Result<Self> {
        let watcher = Arc::new(Mutex::new(BLEWatcher::new()?));
        let manager = Arc::new(AdapterManager::default());

        // The event source owns this callback. Capturing the Radio itself would
        // create a COM reference cycle and keep its manager alive after cancel.
        let manager_weak = Arc::downgrade(&manager);
        let handler = TypedEventHandler::new(move |sender: Ref<Radio>, _args| {
            if let (Some(manager), Ok(radio)) = (manager_weak.upgrade(), sender.ok()) {
                let state = get_central_state(radio);
                manager.emit(CentralEvent::StateUpdate(state.into()));
            }
            Ok(())
        });
        let subscription = match radio.StateChanged(&handler) {
            Ok(token) => Some(Arc::new(RadioStateSubscription {
                radio: radio.clone(),
                token,
            })),
            Err(err) => {
                eprintln!("radio.StateChanged error: {}", err);
                None
            }
        };

        Ok(Adapter {
            watcher,
            manager,
            radio,
            _radio_state_subscription: subscription,
        })
    }
}

impl Debug for Adapter {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        f.debug_struct("Adapter")
            .field("manager", &self.manager)
            .finish()
    }
}

#[async_trait]
impl Central for Adapter {
    type Peripheral = Peripheral;

    async fn events(&self) -> Result<Pin<Box<dyn Stream<Item = CentralEvent> + Send>>> {
        Ok(self.manager.event_stream())
    }

    async fn start_scan(&self, filter: ScanFilter) -> Result<()> {
        let mut watcher = self.watcher.lock().map_err(Into::<Error>::into)?;
        let manager = self.manager.clone();
        watcher.start(
            filter,
            Box::new(move |args| {
                let bluetooth_address = args.BluetoothAddress()?;
                let address: BDAddr = bluetooth_address.try_into().unwrap();
                if let Some(mut entry) = manager.peripheral_mut(&address.into()) {
                    entry.value_mut().update_properties(args);
                    manager.emit(CentralEvent::DeviceUpdated(address.into()));
                } else {
                    let peripheral = Peripheral::new(Arc::downgrade(&manager), address);
                    peripheral.update_properties(args);
                    manager.add_peripheral(peripheral);
                    manager.emit(CentralEvent::DeviceDiscovered(address.into()));
                }
                Ok(())
            }),
        )
    }

    async fn stop_scan(&self) -> Result<()> {
        let mut watcher = self.watcher.lock().map_err(Into::<Error>::into)?;
        watcher.stop()?;
        Ok(())
    }

    async fn peripherals(&self) -> Result<Vec<Peripheral>> {
        Ok(self.manager.peripherals())
    }

    async fn peripheral(&self, id: &PeripheralId) -> Result<Peripheral> {
        self.manager.peripheral(id).ok_or(Error::DeviceNotFound)
    }

    async fn add_peripheral(&self, _address: &PeripheralId) -> Result<Peripheral> {
        Err(Error::NotSupported(
            "Can't add a Peripheral from a BDAddr".to_string(),
        ))
    }

    async fn adapter_info(&self) -> Result<String> {
        // TODO: Get information about the adapter.
        Ok("WinRT".to_string())
    }

    async fn adapter_state(&self) -> Result<CentralState> {
        Ok(get_central_state(&self.radio))
    }
}
