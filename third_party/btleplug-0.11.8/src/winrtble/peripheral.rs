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

use super::{
    advertisement_data_type, ble::characteristic::BLECharacteristic,
    ble::descriptor::BLEDescriptor, ble::device::BLEDevice, ble::service::BLEService, utils,
};
use crate::{
    api::{
        bleuuid::{uuid_from_u16, uuid_from_u32},
        AddressType, BDAddr, CentralEvent, Characteristic, Descriptor, Peripheral as ApiPeripheral,
        PeripheralProperties, Service, ValueNotification, WriteType,
    },
    common::{adapter_manager::AdapterManager, util::notifications_stream_from_broadcast_receiver},
    Error, Result,
};
use async_trait::async_trait;
use dashmap::DashMap;
use futures::stream::{Stream, StreamExt};
use log::{trace, warn};
#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};
#[cfg(feature = "serde")]
use serde_cr as serde;
use std::{
    collections::{BTreeSet, HashMap, HashSet},
    convert::TryInto,
    fmt::{self, Debug, Display, Formatter},
    future::IntoFuture,
    pin::Pin,
    sync::atomic::{AtomicU64, Ordering},
    sync::{Arc, RwLock},
    time::Instant,
};
use tokio::sync::broadcast;
use uuid::Uuid;

use std::sync::Weak;
use windows::core::GUID;
use windows::Devices::Bluetooth::GenericAttributeProfile::GattCharacteristic;
use windows::Devices::Bluetooth::{
    Advertisement::*, BluetoothAddressType, BluetoothConnectionStatus, BluetoothLEDevice,
};

#[cfg_attr(
    feature = "serde",
    derive(Serialize, Deserialize),
    serde(crate = "serde_cr")
)]
#[derive(Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct PeripheralId(BDAddr);

impl Display for PeripheralId {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        Display::fmt(&self.0, f)
    }
}

/// Implementation of [api::Peripheral](crate::api::Peripheral).
#[derive(Clone)]
pub struct Peripheral {
    shared: Arc<Shared>,
}

struct Shared {
    device: tokio::sync::Mutex<Option<BLEDevice>>,
    adapter: Weak<AdapterManager<Peripheral>>,
    address: BDAddr,
    connection: ConnectionState,
    ble_services: DashMap<Uuid, BLEService>,
    notifications_channel: broadcast::Sender<(ValueNotification, Instant)>,

    // Mutable, advertised, state...
    address_type: RwLock<Option<AddressType>>,
    local_name: RwLock<Option<String>>,
    last_tx_power_level: RwLock<Option<i16>>, // XXX: would be nice to avoid lock here!
    last_rssi: RwLock<Option<i16>>,           // XXX: would be nice to avoid lock here!
    latest_manufacturer_data: RwLock<HashMap<u16, Vec<u8>>>,
    latest_service_data: RwLock<HashMap<Uuid, Vec<u8>>>,
    services: RwLock<HashSet<Uuid>>,
    class: RwLock<Option<u32>>,
}

/// Pack the attempt identity and connected bit into one atomic value. A
/// queued callback from a retired native object cannot change a newer link.
#[derive(Default)]
struct ConnectionState(AtomicU64);
impl ConnectionState {
    fn begin(&self) -> ConnectionAttempt<'_> {
        let old=self.0.fetch_update(Ordering::AcqRel,Ordering::Acquire,
            |current|Some(current.wrapping_add(2)&!1)).expect("generation update always has a value");
        let generation=old.wrapping_add(2)&!1;
        ConnectionAttempt {state:self,generation,committed:false}
    }
    fn connected(&self)->bool {self.0.load(Ordering::Acquire)&1!=0}
    fn publish(&self,generation:u64,connected:bool)->bool {
        self.0.fetch_update(Ordering::AcqRel,Ordering::Acquire,|current|
            (current&!1==generation).then_some(generation|u64::from(connected))).is_ok()
    }
    fn retire(&self,generation:u64) {
        let _=self.0.fetch_update(Ordering::AcqRel,Ordering::Acquire,|current|
            (current&!1==generation).then_some(generation.wrapping_add(2)&!1));
    }
}
struct ConnectionAttempt<'a> {
    state:&'a ConnectionState,
    generation:u64,
    committed:bool,
}
impl Drop for ConnectionAttempt<'_> {
    fn drop(&mut self) {if !self.committed {self.state.retire(self.generation);}}
}

impl Peripheral {
    /// Acquire metadata for an exact, already-paired and connected Windows
    /// device. Connected peripherals need not advertise; a fresh adapter's
    /// advertisement registry cannot discover them. This performs no pairing,
    /// GATT operation or connection request. The normal connect/discovery path
    /// still owns its handles and validates the protected services afterwards.
    pub async fn from_connected_paired_address(address: BDAddr) -> Result<Self> {
        let device = BluetoothLEDevice::FromBluetoothAddressAsync(address.into())
            .map_err(|error| Error::Other(Box::new(error)))?
            .into_future().await.map_err(|error| Error::Other(Box::new(error)))?;
        if device.BluetoothAddress().map_err(|error| Error::Other(Box::new(error)))?
            != u64::from(address) {
            return Err(Error::DeviceNotFound);
        }
        if device.ConnectionStatus().map_err(|error| Error::Other(Box::new(error)))?
            != BluetoothConnectionStatus::Connected {
            return Err(Error::NotConnected);
        }
        let paired = device.DeviceInformation()
            .and_then(|information| information.Pairing())
            .and_then(|pairing| pairing.IsPaired())
            .map_err(|error| Error::Other(Box::new(error)))?;
        if !paired { return Err(Error::PermissionDenied); }
        let address_type = match device.BluetoothAddressType()
            .map_err(|error| Error::Other(Box::new(error)))? {
            BluetoothAddressType::Public => AddressType::Public,
            BluetoothAddressType::Random => AddressType::Random,
            _ => return Err(Error::NotSupported("Unknown Windows Bluetooth address type".into())),
        };
        let name = device.Name().map_err(|error| Error::Other(Box::new(error)))?.to_string();
        let peripheral = Self::new(Weak::new(), address);
        *peripheral.shared.address_type.write()? = Some(address_type);
        *peripheral.shared.local_name.write()? = Some(name);
        // Leave connected=false until connect() installs its own callbacks and
        // device handle. Drop only this borrowed COM reference: Close() could
        // invalidate another owner's live WinRT device/GATT objects.
        Ok(peripheral)
    }

    pub(crate) fn new(adapter: Weak<AdapterManager<Self>>, address: BDAddr) -> Self {
        let (broadcast_sender, _) =
            broadcast::channel(crate::common::util::WINDOWS_NOTIFICATION_CAPACITY);
        Peripheral {
            shared: Arc::new(Shared {
                adapter,
                device: tokio::sync::Mutex::new(None),
                address,
                connection: ConnectionState::default(),
                ble_services: DashMap::new(),
                notifications_channel: broadcast_sender,
                address_type: RwLock::new(None),
                local_name: RwLock::new(None),
                last_tx_power_level: RwLock::new(None),
                last_rssi: RwLock::new(None),
                latest_manufacturer_data: RwLock::new(HashMap::new()),
                latest_service_data: RwLock::new(HashMap::new()),
                services: RwLock::new(HashSet::new()),
                class: RwLock::new(None),
            }),
        }
    }

    /// Companion's exact-byte recording receiver must observe native queue lag,
    /// rather than having the ordinary notification trait silently discard it.
    /// Reuses the existing device, ValueChanged callbacks and CCCD subscriptions.
    pub fn checked_notifications(
        &self,
    ) -> Pin<Box<dyn Stream<Item = Result<(ValueNotification, Instant)>> + Send>> {
        crate::common::util::checked_notifications_stream_from_broadcast_receiver(
            self.shared.notifications_channel.subscribe(),
        )
    }

    /// Discover fresh services and characteristics for a caller that only uses
    /// characteristic reads/writes and WinRT CCCD subscriptions. Skips raw
    /// descriptor discovery, not encryption, live GATT discovery or access
    /// checks. The ordinary trait preserves full descriptor discovery.
    pub async fn discover_services_without_descriptors(&self) -> Result<()> {
        self.discover_services_impl(false).await
    }

    /// Refresh one incomplete required service on this same connection. This
    /// does not pair, reconnect, reuse stale cache or relax protected access.
    /// Replace its native characteristic map only after fresh enumeration has
    /// succeeded. WinRT subscribe() still writes the normal protected CCCD.
    pub async fn refresh_service_without_descriptors(&self, uuid: Uuid) -> Result<()> {
        let mut device = self.shared.device.lock().await;
        let device = device.as_mut().ok_or(Error::NotConnected)?;
        let service = device.discover_exact_service(uuid).await?;
        let native = BLEDevice::get_characteristics_strict(&service).await?;
        let mut characteristics = HashMap::new();
        for characteristic in native {
            let actual_uuid = utils::to_uuid(&characteristic.Uuid()?);
            // Ambiguous duplicates are not a usable protected control channel.
            if characteristics.contains_key(&actual_uuid) {
                return Err(Error::Other(format!(
                    "refresh_service service={uuid} duplicate_characteristic={actual_uuid}"
                ).into()));
            }
            characteristics.insert(actual_uuid, BLECharacteristic::new(characteristic, HashMap::new()));
        }
        self.shared.ble_services.insert(uuid, BLEService { uuid, characteristics });
        Ok(())
    }

    async fn discover_services_impl(&self, include_descriptors: bool) -> Result<()> {
        let mut device = self.shared.device.lock().await;
        if let Some(ref mut device) = *device {
            let gatt_services = device.discover_services().await?;
            for service in gatt_services {
                let uuid = utils::to_uuid(&service.Uuid().unwrap());
                if !self.shared.ble_services.contains_key(&uuid) {
                    match BLEDevice::get_characteristics(service).await {
                        Ok(characteristics) => {
                            let characteristics = characteristics
                                .into_iter()
                                .fold(
                                    // Only consider the first characteristic of each UUID
                                    // This "should" be unique, but of course it's not enforced
                                    HashMap::<GUID, GattCharacteristic>::new(),
                                    |mut map, gatt_characteristic| {
                                        let uuid = gatt_characteristic.Uuid().unwrap_or_default();
                                        if !map.contains_key(&uuid) {
                                            map.insert(uuid, gatt_characteristic);
                                        }
                                        map
                                    },
                                )
                                .into_iter()
                                .map(|(_, characteristic)| async {
                                    let c = characteristic.clone();
                                    (
                                        characteristic,
                                        if include_descriptors {
                                            BLEDevice::get_characteristic_descriptors(&c)
                                                .await
                                                .unwrap_or(Vec::new())
                                        } else {
                                            Vec::new()
                                        }
                                            .into_iter()
                                            .map(|descriptor| {
                                                let descriptor = BLEDescriptor::new(descriptor);
                                                (descriptor.uuid(), descriptor)
                                            })
                                            .collect(),
                                    )
                                });

                            let characteristics = futures::future::join_all(characteristics)
                                .await
                                .into_iter()
                                .map(|(characteristic, descriptors)| {
                                    let characteristic =
                                        BLECharacteristic::new(characteristic, descriptors);
                                    (characteristic.uuid(), characteristic)
                                })
                                .collect();

                            self.shared.ble_services.insert(
                                uuid,
                                BLEService {
                                    uuid,
                                    characteristics,
                                },
                            );
                        }
                        Err(e) => {
                            warn!("get_characteristics_async {:?}", e);
                        }
                    }
                }
            }
            return Ok(());
        }
        Err(Error::NotConnected)
    }

    // TODO: see if the other backends can also be similarly decoupled from PeripheralProperties
    // so it can potentially be replaced by individial state getters
    fn derive_properties(&self) -> PeripheralProperties {
        PeripheralProperties {
            address: self.address(),
            address_type: *self.shared.address_type.read().unwrap(),
            local_name: self.shared.local_name.read().unwrap().clone(),
            tx_power_level: *self.shared.last_tx_power_level.read().unwrap(),
            rssi: *self.shared.last_rssi.read().unwrap(),
            manufacturer_data: self.shared.latest_manufacturer_data.read().unwrap().clone(),
            service_data: self.shared.latest_service_data.read().unwrap().clone(),
            services: self
                .shared
                .services
                .read()
                .unwrap()
                .iter()
                .copied()
                .collect(),
            class: *self.shared.class.read().unwrap(),
        }
    }

    pub(crate) fn update_properties(&self, args: &BluetoothLEAdvertisementReceivedEventArgs) {
        let advertisement = args.Advertisement().unwrap();

        // Advertisements are cumulative: set/replace data only if it's set
        if let Ok(name) = advertisement.LocalName() {
            if !name.is_empty() {
                // XXX: we could probably also assume that we've seen the
                // advertisement before and speculatively take a read lock
                // to confirm that the name hasn't changed...

                let mut local_name_guard = self.shared.local_name.write().unwrap();
                *local_name_guard = Some(name.to_string());
            }
        }
        if let Ok(manufacturer_data) = advertisement.ManufacturerData() {
            if manufacturer_data.Size().unwrap() > 0 {
                let mut manufacturer_data_guard =
                    self.shared.latest_manufacturer_data.write().unwrap();
                *manufacturer_data_guard = manufacturer_data
                    .into_iter()
                    .map(|d| {
                        let manufacturer_id = d.CompanyId().unwrap();
                        let data = utils::to_vec(&d.Data().unwrap());

                        (manufacturer_id, data)
                    })
                    .collect();

                // Emit event of newly received advertisement
                self.emit_event(CentralEvent::ManufacturerDataAdvertisement {
                    id: self.shared.address.into(),
                    manufacturer_data: manufacturer_data_guard.clone(),
                });
            }
        }

        // The Windows Runtime API (as of 19041) does not directly expose Service Data as a friendly API (like Manufacturer Data above)
        // Instead they provide data sections for access to raw advertising data. That is processed here.
        if let Ok(data_sections) = advertisement.DataSections() {
            // See if we have any advertised service data before taking a lock to update...
            let mut found_service_data = false;
            for section in &data_sections {
                match section.DataType().unwrap() {
                    advertisement_data_type::SERVICE_DATA_16_BIT_UUID
                    | advertisement_data_type::SERVICE_DATA_32_BIT_UUID
                    | advertisement_data_type::SERVICE_DATA_128_BIT_UUID => {
                        found_service_data = true;
                        break;
                    }
                    _ => {}
                }
            }
            if found_service_data {
                let mut service_data_guard = self.shared.latest_service_data.write().unwrap();

                *service_data_guard = data_sections
                    .into_iter()
                    .filter_map(|d| {
                        let data = utils::to_vec(&d.Data().unwrap());

                        match d.DataType().unwrap() {
                            advertisement_data_type::SERVICE_DATA_16_BIT_UUID => {
                                let (uuid, data) = data.split_at(2);
                                let uuid =
                                    uuid_from_u16(u16::from_le_bytes(uuid.try_into().unwrap()));
                                Some((uuid, data.to_owned()))
                            }
                            advertisement_data_type::SERVICE_DATA_32_BIT_UUID => {
                                let (uuid, data) = data.split_at(4);
                                let uuid =
                                    uuid_from_u32(u32::from_le_bytes(uuid.try_into().unwrap()));
                                Some((uuid, data.to_owned()))
                            }
                            advertisement_data_type::SERVICE_DATA_128_BIT_UUID => {
                                let (uuid, data) = data.split_at(16);
                                let uuid = Uuid::from_slice(uuid).unwrap();
                                Some((uuid, data.to_owned()))
                            }
                            _ => None,
                        }
                    })
                    .collect();

                // Emit event of newly received advertisement
                self.emit_event(CentralEvent::ServiceDataAdvertisement {
                    id: self.shared.address.into(),
                    service_data: service_data_guard.clone(),
                });
            }
        }

        if let Ok(services) = advertisement.ServiceUuids() {
            let mut found_new_service = false;

            // Limited scope for read-only lock...
            {
                let services_guard_ro = self.shared.services.read().unwrap();

                // In all likelihood we've already seen all the advertised services before so lets
                // check to see if we can avoid taking the write lock and emitting an event...
                for uuid in &services {
                    if !services_guard_ro.contains(&utils::to_uuid(&uuid)) {
                        found_new_service = true;
                        break;
                    }
                }
            }

            if found_new_service {
                let mut services_guard = self.shared.services.write().unwrap();

                // ServicesUuids combines all the 16, 32 and 128 bit, 'complete' and 'incomplete'
                // service IDs that may be part of this advertisement into one single list with
                // a consistent (128bit) format. Considering that we don't practically know
                // whether the aggregate list is ever complete we always union the IDs with the
                // IDs already tracked.
                for uuid in services {
                    services_guard.insert(utils::to_uuid(&uuid));
                }

                self.emit_event(CentralEvent::ServicesAdvertisement {
                    id: self.shared.address.into(),
                    services: services_guard.iter().copied().collect(),
                });
            }
        }

        if let Ok(address_type) = args.BluetoothAddressType() {
            let mut address_type_guard = self.shared.address_type.write().unwrap();
            *address_type_guard = match address_type {
                BluetoothAddressType::Public => Some(AddressType::Public),
                BluetoothAddressType::Random => Some(AddressType::Random),
                _ => None,
            };
        }

        if let Ok(tx_reference) = args.TransmitPowerLevelInDBm() {
            // IReference is (ironically) a crazy foot gun in Rust since it very easily
            // panics if you look at it wrong. Calling GetInt16(), IsNumericScalar() or Type()
            // all panic here without returning a Result as documented.
            // Value() is apparently the _right_ way to extract something from an IReference<T>...
            if let Ok(tx) = tx_reference.Value() {
                let mut tx_power_level_guard = self.shared.last_tx_power_level.write().unwrap();
                *tx_power_level_guard = Some(tx);
            }
        }
        if let Ok(rssi) = args.RawSignalStrengthInDBm() {
            let mut rssi_guard = self.shared.last_rssi.write().unwrap();
            *rssi_guard = Some(rssi);
        }
    }

    fn emit_event(&self, event: CentralEvent) {
        if let Some(manager) = self.shared.adapter.upgrade() {
            manager.emit(event);
        } else {
            trace!("Could not emit an event. AdapterManager has been dropped");
        }
    }
}

impl Display for Peripheral {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        let connected = if self.shared.connection.connected() {
            " connected"
        } else {
            ""
        };
        write!(
            f,
            "{} {}{}",
            self.shared.address,
            self.shared
                .local_name
                .read()
                .unwrap()
                .clone()
                .unwrap_or_else(|| "(unknown)".to_string()),
            connected
        )
    }
}

impl Debug for Peripheral {
    fn fmt(&self, f: &mut Formatter) -> fmt::Result {
        let connected = if self.shared.connection.connected() {
            " connected"
        } else {
            ""
        };
        let properties = self.derive_properties();
        write!(
            f,
            "{} properties: {:?}, services: {:?} {}",
            self.shared.address, properties, self.shared.ble_services, connected
        )
    }
}

#[async_trait]
impl ApiPeripheral for Peripheral {
    fn id(&self) -> PeripheralId {
        PeripheralId(self.shared.address)
    }

    /// Returns the address of the peripheral.
    fn address(&self) -> BDAddr {
        self.shared.address
    }

    /// Returns the set of properties associated with the peripheral. These may be updated over time
    /// as additional advertising reports are received.
    async fn properties(&self) -> Result<Option<PeripheralProperties>> {
        Ok(Some(self.derive_properties()))
    }

    fn services(&self) -> BTreeSet<Service> {
        self.shared
            .ble_services
            .iter()
            .map(|item| item.value().to_service())
            .collect()
    }

    /// Returns true iff we are currently connected to the device.
    async fn is_connected(&self) -> Result<bool> {
        Ok(self.shared.connection.connected())
    }

    /// Creates a connection to the device. This is a synchronous operation; if this method returns
    /// Ok there has been successful connection. Note that peripherals allow only one connection at
    /// a time. Operations that attempt to communicate with a device will fail until it is connected.
    async fn connect(&self) -> Result<()> {
        // Serialize native replacement with disconnect. Retire the callback
        // generation and old references BEFORE opening the new native object.
        let mut current=self.shared.device.lock().await;
        let mut attempt=self.shared.connection.begin();
        let generation=attempt.generation;
        self.shared.ble_services.clear();
        drop(current.take());
        let shared_clone = Arc::downgrade(&self.shared);
        let adapter_clone = self.shared.adapter.clone();
        let address = self.shared.address;
        let address_type = *self.shared.address_type.read()?;
        let device = BLEDevice::new(
            self.shared.address,
            address_type,
            Box::new(move |is_connected| {
                let Some(shared)=shared_clone.upgrade() else {return;};
                if !shared.connection.publish(generation,is_connected) {return;}

                if !is_connected {
                    if let Some(adapter) = adapter_clone.upgrade() {
                        adapter.emit(CentralEvent::DeviceDisconnected(address.into()));
                    }
                }
            }),
        )
        .await?;

        device.connect().await?;
        *current = Some(device);
        if !self.shared.connection.publish(generation,true) {return Err(Error::NotConnected);}
        attempt.committed=true;
        self.emit_event(CentralEvent::DeviceConnected(self.shared.address.into()));
        Ok(())
    }

    /// Terminates a connection to the device. This is a synchronous operation.
    async fn disconnect(&self) -> Result<()> {
        // We need to clear the services because if this device is re-connected,
        // the cached service objects will no longer be valid (they must be refreshed).
        let mut device = self.shared.device.lock().await;
        // Drop the uncommitted attempt immediately: its generation becomes
        // unusable before callbacks can run during resource teardown.
        drop(self.shared.connection.begin());
        self.shared.ble_services.clear();
        *device = None;
        self.emit_event(CentralEvent::DeviceDisconnected(self.shared.address.into()));
        Ok(())
    }

    /// Discovers all characteristics for the device. This is a synchronous operation.
    async fn discover_services(&self) -> Result<()> {
        self.discover_services_impl(true).await
    }

    /// Write some data to the characteristic. Returns an error if the write couldn't be send or (in
    /// the case of a write-with-response) if the device returns an error.
    async fn write(
        &self,
        characteristic: &Characteristic,
        data: &[u8],
        write_type: WriteType,
    ) -> Result<()> {
        let ble_service = &*self
            .shared
            .ble_services
            .get(&characteristic.service_uuid)
            .ok_or_else(|| Error::NotSupported("Service not found for write".into()))?;
        let ble_characteristic = ble_service
            .characteristics
            .get(&characteristic.uuid)
            .ok_or_else(|| Error::NotSupported("Characteristic not found for write".into()))?;
        ble_characteristic.write_value(data, write_type).await
    }

    /// Enables either notify or indicate (depending on support) for the specified characteristic.
    /// This is a synchronous call.
    async fn subscribe(&self, characteristic: &Characteristic) -> Result<()> {
        let ble_service = &mut *self
            .shared
            .ble_services
            .get_mut(&characteristic.service_uuid)
            .ok_or_else(|| Error::NotSupported("Service not found for subscribe".into()))?;
        let ble_characteristic = ble_service
            .characteristics
            .get_mut(&characteristic.uuid)
            .ok_or_else(|| Error::NotSupported("Characteristic not found for subscribe".into()))?;
        let notifications_sender = self.shared.notifications_channel.clone();
        let uuid = characteristic.uuid;
        ble_characteristic
            .subscribe(Box::new(move |value| {
                let received_at = Instant::now();
                let notification = ValueNotification { uuid, value };
                // Note: we ignore send errors here which may happen while there are no
                // receivers...
                let _ = notifications_sender.send((notification, received_at));
            }))
            .await
    }

    /// Disables either notify or indicate (depending on support) for the specified characteristic.
    /// This is a synchronous call.
    async fn unsubscribe(&self, characteristic: &Characteristic) -> Result<()> {
        let ble_service = &mut *self
            .shared
            .ble_services
            .get_mut(&characteristic.service_uuid)
            .ok_or_else(|| Error::NotSupported("Service not found for unsubscribe".into()))?;
        let ble_characteristic = ble_service
            .characteristics
            .get_mut(&characteristic.uuid)
            .ok_or_else(|| {
                Error::NotSupported("Characteristic not found for unsubscribe".into())
            })?;
        ble_characteristic.unsubscribe().await
    }

    async fn read(&self, characteristic: &Characteristic) -> Result<Vec<u8>> {
        let ble_service = &*self
            .shared
            .ble_services
            .get(&characteristic.service_uuid)
            .ok_or_else(|| Error::NotSupported("Service not found for read".into()))?;
        let ble_characteristic = ble_service
            .characteristics
            .get(&characteristic.uuid)
            .ok_or_else(|| Error::NotSupported("Characteristic not found for read".into()))?;
        ble_characteristic.read_value().await
    }

    async fn notifications(&self) -> Result<Pin<Box<dyn Stream<Item = ValueNotification> + Send>>> {
        let receiver = self.shared.notifications_channel.subscribe();
        Ok(Box::pin(notifications_stream_from_broadcast_receiver(receiver)
            .map(|(notification, _)| notification)))
    }

    async fn write_descriptor(&self, descriptor: &Descriptor, data: &[u8]) -> Result<()> {
        let ble_service = &*self
            .shared
            .ble_services
            .get(&descriptor.service_uuid)
            .ok_or_else(|| Error::NotSupported("Service not found for write".into()))?;
        let ble_characteristic = ble_service
            .characteristics
            .get(&descriptor.characteristic_uuid)
            .ok_or_else(|| Error::NotSupported("Characteristic not found for write".into()))?;
        let ble_descriptor = ble_characteristic
            .descriptors
            .get(&descriptor.uuid)
            .ok_or_else(|| Error::NotSupported("Descriptor not found for write".into()))?;
        ble_descriptor.write_value(data).await
    }

    async fn read_descriptor(&self, descriptor: &Descriptor) -> Result<Vec<u8>> {
        let ble_service = &*self
            .shared
            .ble_services
            .get(&descriptor.service_uuid)
            .ok_or_else(|| Error::NotSupported("Service not found for read".into()))?;
        let ble_characteristic = ble_service
            .characteristics
            .get(&descriptor.characteristic_uuid)
            .ok_or_else(|| Error::NotSupported("Characteristic not found for read".into()))?;
        let ble_descriptor = ble_characteristic
            .descriptors
            .get(&descriptor.uuid)
            .ok_or_else(|| Error::NotSupported("Descriptor not found for write".into()))?;
        ble_descriptor.read_value().await
    }
}

impl From<BDAddr> for PeripheralId {
    fn from(address: BDAddr) -> Self {
        PeripheralId(address)
    }
}

#[cfg(test)]
mod connection_generation_tests {
    use super::*;

    #[test]
    fn r54_old_callback_cannot_disconnect_or_reconnect_a_new_native_owner() {
        let state=ConnectionState::default();
        let mut old=state.begin();let old_generation=old.generation;
        assert!(state.publish(old_generation,true));old.committed=true;drop(old);
        let mut fresh=state.begin();let generation=fresh.generation;
        assert!(state.publish(generation,true));fresh.committed=true;
        for callback in [false,true,false] {
            assert!(!state.publish(old_generation,callback));
            assert!(state.connected());
        }
        assert!(state.publish(generation,false));assert!(!state.connected());
        assert!(state.publish(generation,true));assert!(state.connected());
    }

    #[test]
    fn r54_cancelled_or_failed_open_retires_its_callbacks_without_poisoning_fresh_owner() {
        let state=ConnectionState::default();
        let abandoned=state.begin();let abandoned_generation=abandoned.generation;
        assert!(state.publish(abandoned_generation,true));drop(abandoned);
        assert!(!state.connected());assert!(!state.publish(abandoned_generation,true));
        let mut fresh=state.begin();let generation=fresh.generation;
        assert!(state.publish(generation,true));fresh.committed=true;drop(fresh);
        assert!(state.connected());
        state.retire(abandoned_generation);assert!(state.connected());
        drop(state.begin());assert!(!state.connected());
        assert!(!state.publish(generation,true),"explicit disconnect invalidates even a queued connected callback");
    }
}
