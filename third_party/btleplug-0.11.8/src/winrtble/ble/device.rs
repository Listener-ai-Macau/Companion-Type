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

use crate::{api::{AddressType, BDAddr}, winrtble::utils, Error, Result};
use super::characteristic::await_cancellable_gatt;
use log::{debug, trace};
use std::future::IntoFuture;
use uuid::Uuid;
use windows::{
    core::Ref,
    Devices::Bluetooth::{
        BluetoothAddressType, BluetoothCacheMode, BluetoothConnectionStatus, BluetoothLEDevice,
        GenericAttributeProfile::{
            GattCharacteristic, GattCommunicationStatus, GattDescriptor, GattDeviceService,
            GattDeviceServicesResult, GattOpenStatus, GattSharingMode,
        },
    },
    Devices::Enumeration::DeviceAccessStatus,
    Foundation::TypedEventHandler,
};

pub type ConnectedEventHandler = Box<dyn Fn(bool) + Send>;

pub struct BLEDevice {
    device: BluetoothLEDevice,
    connection_token: i64,
    services: Vec<GattDeviceService>,
}

fn require_discovery_success(
    status: GattCommunicationStatus, operation: &str, service: Uuid, protocol_error: Option<u8>,
) -> Result<()> {
    if status == GattCommunicationStatus::Success { return Ok(()); }
    let label = match status {
        GattCommunicationStatus::Unreachable => "Unreachable",
        GattCommunicationStatus::ProtocolError => "ProtocolError",
        GattCommunicationStatus::AccessDenied => "AccessDenied",
        _ => "Unknown",
    };
    Err(Error::Other(format!(
        "{operation} service={service} status={label} ({status:?}) protocol_error={protocol_error:?}"
    ).into()))
}

fn require_root_discovery_success(status: GattCommunicationStatus, protocol_error: Option<u8>) -> Result<()> {
    if status == GattCommunicationStatus::Success { return Ok(()); }
    let detail=format!(
        "Windows BLE root service discovery failed: status={status:?} protocol_error={protocol_error:?}; no cached or empty-success service list"
    );
    eprintln!("BLE root_service_discovery {detail}");
    // Preserve btleplug's public error categories used by existing callers,
    // while recording the actual phase/status/ATT code instead of hiding it.
    if status==GattCommunicationStatus::AccessDenied {Err(Error::PermissionDenied)}
    else if status==GattCommunicationStatus::Unreachable {Err(Error::NotConnected)}
    else if status==GattCommunicationStatus::ProtocolError {Err(Error::NotSupported(detail))}
    else {Err(Error::Other(detail.into()))}
}

fn root_discovery_status(result: &GattDeviceServicesResult) -> Result<()> {
    let status=result.Status()?;
    let protocol_error=if status==GattCommunicationStatus::ProtocolError {
        result.ProtocolError().and_then(|value|value.Value()).ok()
    } else {None};
    require_root_discovery_success(status,protocol_error)
}

fn require_service_access(status: DeviceAccessStatus, service: Uuid) -> Result<()> {
    if status == DeviceAccessStatus::Allowed { return Ok(()); }
    let label = match status {
        DeviceAccessStatus::DeniedByUser => "DeniedByUser",
        DeviceAccessStatus::DeniedBySystem => "DeniedBySystem",
        DeviceAccessStatus::Unspecified => "Unspecified",
        _ => "Unknown",
    };
    Err(Error::Other(format!(
        "required_service_access service={service} access={label} ({status:?}); no characteristics or control command requested"
    ).into()))
}

fn require_shared_service(status: GattOpenStatus, mode: Option<GattSharingMode>, service: Uuid) -> Result<()> {
    if matches!(status, GattOpenStatus::Success|GattOpenStatus::AlreadyOpened)
        && mode==Some(GattSharingMode::SharedReadAndWrite) { return Ok(()); }
    let label=match status {
        GattOpenStatus::SharingViolation=>"SharingViolation",
        GattOpenStatus::AccessDenied=>"AccessDenied",
        GattOpenStatus::NotFound=>"NotFound",
        GattOpenStatus::AlreadyOpened=>"AlreadyOpenedIncompatibleMode",
        GattOpenStatus::Success=>"OpenedIncompatibleMode",
        GattOpenStatus::Unspecified=>"Unspecified",
        _=>"Unknown",
    };
    Err(Error::Other(format!(
        "shared_service_open service={service} status={label} ({status:?}) sharing={mode:?}; no exclusive fallback or control command"
    ).into()))
}

async fn open_shared_service(service: &GattDeviceService) -> Result<()> {
    let uuid=utils::to_uuid(&service.Uuid()?);
    let previous_access=service.DeviceAccessInformation().and_then(|info|info.CurrentStatus());
    let before=service.SharingMode();
    let access=await_cancellable_gatt(service.RequestAccessAsync()?).await?;
    require_service_access(access,uuid)?;
    // Implicit GetCharacteristics opens Exclusive on this Windows backend.
    // A previous client's live/retiring lease then blocks the next process
    // before ATT, despite Allowed access. All our discovery paths must open
    // shared explicitly, including the first client, not only a later retry.
    let opened=await_cancellable_gatt(service.OpenAsync(GattSharingMode::SharedReadAndWrite)?).await?;
    let after=service.SharingMode().ok();
    eprintln!("BLE shared_service_open service={uuid} previous_access={previous_access:?} access={access:?} before={before:?} opened={opened:?} after={after:?}");
    require_shared_service(opened,after,uuid)
}

impl BLEDevice {
    pub async fn new(
        address: BDAddr,
        address_type: Option<AddressType>,
        connection_status_changed: ConnectedEventHandler,
    ) -> Result<Self> {
        // Pairing and GATT must name the same native identity. In particular,
        // WBA static-random identities cannot lose their advertised type here.
        // Only genuinely unknown types use the SDK's untyped overload.
        let requested_type=address_type.map(|kind|match kind {
            AddressType::Public=>BluetoothAddressType::Public,
            AddressType::Random=>BluetoothAddressType::Random,
        });
        let async_op = match requested_type {
            Some(kind)=>BluetoothLEDevice::FromBluetoothAddressWithBluetoothAddressTypeAsync(address.into(),kind),
            None=>BluetoothLEDevice::FromBluetoothAddressAsync(address.into()),
        }
            .map_err(|_| Error::DeviceNotFound)?;
        let device = async_op
            .into_future()
            .await
            .map_err(|_| Error::DeviceNotFound)?;
        let actual_address=device.BluetoothAddress().map_err(|e|Error::Other(Box::new(e)))?;
        let actual_type=device.BluetoothAddressType().map_err(|e|Error::Other(Box::new(e)))?;
        if actual_address!=u64::from(address) || requested_type.is_some_and(|kind|kind!=actual_type) {
            return Err(Error::Other("native GATT identity differs from the advertised address/type; no alternate identity fallback".into()));
        }
        eprintln!("BLE native_gatt_identity address={address} requested_type={requested_type:?} actual_type={actual_type:?} matched=1");
        let connection_status_handler =
            TypedEventHandler::new(move |sender: Ref<BluetoothLEDevice>, _| {
                if let Ok(sender) = sender.ok() {
                    let is_connected = sender
                        .ConnectionStatus()
                        .ok()
                        .map_or(false, |v| v == BluetoothConnectionStatus::Connected);
                    connection_status_changed(is_connected);
                    trace!("state {:?}", sender.ConnectionStatus());
                }

                Ok(())
            });
        let connection_token = device
            .ConnectionStatusChanged(&connection_status_handler)
            .map_err(|_| Error::Other("Could not add connection status handler".into()))?;

        Ok(BLEDevice {
            device,
            connection_token,
            services: vec![],
        })
    }

    async fn get_gatt_services(
        &self,
        cache_mode: BluetoothCacheMode,
    ) -> Result<GattDeviceServicesResult> {
        let winrt_error = |e| Error::Other(format!("{:?}", e).into());
        let async_op = self
            .device
            .GetGattServicesWithCacheModeAsync(cache_mode)
            .map_err(winrt_error)?;
        let service_result = await_cancellable_gatt(async_op).await.map_err(winrt_error)?;
        Ok(service_result)
    }

    pub async fn connect(&self) -> Result<()> {
        if self.is_connected().await? {
            return Ok(());
        }

        let service_result = self.get_gatt_services(BluetoothCacheMode::Uncached).await?;
        root_discovery_status(&service_result)
    }

    async fn is_connected(&self) -> Result<bool> {
        let winrt_error = |e| Error::Other(format!("{:?}", e).into());
        let status = self.device.ConnectionStatus().map_err(winrt_error)?;

        Ok(status == BluetoothConnectionStatus::Connected)
    }

    pub async fn get_characteristics(
        service: &GattDeviceService,
    ) -> Result<Vec<GattCharacteristic>> {
        open_shared_service(service).await?;
        let result = await_cancellable_gatt(service
            .GetCharacteristicsWithCacheModeAsync(BluetoothCacheMode::Uncached)?).await?;
        let status=result.Status()?;
        let protocol_error=if status==GattCommunicationStatus::ProtocolError {
            result.ProtocolError().and_then(|value|value.Value()).ok()
        } else {None};
        require_discovery_success(status,"get_characteristics",utils::to_uuid(&service.Uuid()?),protocol_error)?;
        Ok(result.Characteristics()?.into_iter().collect())
    }

    /// A bounded caller may refresh an incomplete required service on its
    /// existing connection. Never return stale services or an empty-success
    /// characteristic list when Windows actually returned a communication error.
    pub async fn discover_exact_service(&mut self, uuid: Uuid) -> Result<GattDeviceService> {
        let result = await_cancellable_gatt(self.device.GetGattServicesForUuidWithCacheModeAsync(
            utils::to_guid(&uuid), BluetoothCacheMode::Uncached,
        )?).await?;
        let status = result.Status()?;
        let protocol_error = if status == GattCommunicationStatus::ProtocolError {
            result.ProtocolError().and_then(|value| value.Value()).ok()
        } else { None };
        require_discovery_success(status, "discover_exact_service", uuid, protocol_error)?;
        let services: Vec<_> = result.Services()?.into_iter().collect();
        // Own fresh service handles until disconnect, including a failed
        // characteristic enumeration. Do not Close another live owner's object.
        self.services.extend(services.iter().cloned());
        if services.len() != 1 || utils::to_uuid(&services[0].Uuid()?) != uuid {
            return Err(Error::Other(format!(
                "discover_exact_service service={uuid} status=Success matching_count={}", services.len()
            ).into()));
        }
        Ok(services[0].clone())
    }

    pub async fn get_characteristics_strict(service: &GattDeviceService) -> Result<Vec<GattCharacteristic>> {
        let uuid = utils::to_uuid(&service.Uuid()?);
        let characteristics=Self::get_characteristics(service).await?;
        if characteristics.is_empty() {
            return Err(Error::Other(format!(
                "get_characteristics_strict service={uuid} status=Success characteristic_count=0"
            ).into()));
        }
        Ok(characteristics)
    }

    pub async fn get_characteristic_descriptors(
        characteristic: &GattCharacteristic,
    ) -> Result<Vec<GattDescriptor>> {
        let async_result = characteristic
            .GetDescriptorsWithCacheModeAsync(BluetoothCacheMode::Uncached)?
            .into_future()
            .await?;
        let status = async_result.Status();
        if status == Ok(GattCommunicationStatus::Success) {
            let results = async_result.Descriptors()?;
            debug!("descriptors {:?}", results.Size());
            Ok(results.into_iter().collect())
        } else {
            Err(Error::Other(
                format!(
                    "get_characteristic_descriptors for {:?} failed: {:?}",
                    characteristic, status
                )
                .into(),
            ))
        }
    }

    pub async fn discover_services(&mut self) -> Result<&[GattDeviceService]> {
        let winrt_error = |e| Error::Other(format!("{:?}", e).into());
        let service_result = self.get_gatt_services(BluetoothCacheMode::Uncached).await?;
        root_discovery_status(&service_result)?;
        {
            // We need to convert the IVectorView to a Vec, because IVectorView is not Send and so
            // can't be help past the await point below.
            let services: Vec<_> = service_result
                .Services()
                .map_err(winrt_error)?
                .into_iter()
                .collect();
            self.services = services;
            debug!("services {:?}", self.services.len());
        }
        Ok(self.services.as_slice())
    }
}

impl Drop for BLEDevice {
    fn drop(&mut self) {
        let result = self
            .device
            .RemoveConnectionStatusChanged(self.connection_token);
        if let Err(err) = result {
            debug!("Drop:remove_connection_status_changed {:?}", err);
        }

        // Match Companion's pairing/parameter references and Listener: detach
        // our callback, then release the COM fields normally. Explicit Close
        // can invalidate another live wrapper or an in-flight native request.
        // Peripheral disconnect clears its characteristic/service cache too.
    }
}

#[cfg(test)]
mod discovery_tests {
    use super::*;

    #[test]
    fn root_service_failure_preserves_native_category_and_cannot_return_stale_success() {
        assert!(require_root_discovery_success(GattCommunicationStatus::Success,None).is_ok());
        for(status,protocol)in[(GattCommunicationStatus::Unreachable,None),
            (GattCommunicationStatus::AccessDenied,None),(GattCommunicationStatus::ProtocolError,Some(5)),
            (GattCommunicationStatus(77),None)] {
            let error=require_root_discovery_success(status,protocol).unwrap_err();
            match status {
                GattCommunicationStatus::Unreachable=>assert!(matches!(error,Error::NotConnected)),
                GattCommunicationStatus::AccessDenied=>assert!(matches!(error,Error::PermissionDenied)),
                _=>{
                    let error=error.to_string();
                    assert!(error.contains(&format!("status={status:?}")));
                    assert!(error.contains(&format!("protocol_error={protocol:?}")));
                    assert!(error.contains("no cached or empty-success service list"));
                }
            }
        }
    }

    #[test]
    fn required_discovery_never_converts_native_failure_to_empty_success() {
        let uuid=Uuid::from_u128(0x8f7a00087b7d4f3d9d6f6c2d1b7c0000);
        assert!(require_discovery_success(GattCommunicationStatus::Success,"services",uuid,None).is_ok());
        for (status,label,code) in [
            (GattCommunicationStatus::Unreachable,"Unreachable",None),
            (GattCommunicationStatus::AccessDenied,"AccessDenied",None),
            (GattCommunicationStatus::ProtocolError,"ProtocolError",Some(5)),
            (GattCommunicationStatus(77),"Unknown",None),
        ] {
            let error=require_discovery_success(status,"characteristics",uuid,code).unwrap_err().to_string();
            assert!(error.contains(label) && error.contains(&uuid.to_string()));
            if code.is_some() { assert!(error.contains("Some(5)")); }
        }
    }

    #[test]
    fn required_service_access_only_allows_an_explicit_allowed_result() {
        let uuid=Uuid::from_u128(0x8f7a00087b7d4f3d9d6f6c2d1b7c0000);
        assert!(require_service_access(DeviceAccessStatus::Allowed,uuid).is_ok());
        for (status,label) in [
            (DeviceAccessStatus::DeniedByUser,"DeniedByUser"),
            (DeviceAccessStatus::DeniedBySystem,"DeniedBySystem"),
            (DeviceAccessStatus::Unspecified,"Unspecified"),
            (DeviceAccessStatus(77),"Unknown"),
        ] {
            let error=require_service_access(status,uuid).unwrap_err().to_string();
            assert!(error.contains(label) && error.contains("no characteristics or control command requested"));
        }
    }

    #[test]
    fn shared_service_open_requires_real_shared_read_write_and_respects_denial() {
        let uuid=Uuid::from_u128(0x8f7a00087b7d4f3d9d6f6c2d1b7c0000);
        for status in [GattOpenStatus::Success,GattOpenStatus::AlreadyOpened] {
            assert!(require_shared_service(status,Some(GattSharingMode::SharedReadAndWrite),uuid).is_ok());
            for mode in [None,Some(GattSharingMode::Exclusive),Some(GattSharingMode::SharedReadOnly),Some(GattSharingMode::Unspecified)] {
                assert!(require_shared_service(status,mode,uuid).is_err());
            }
        }
        for status in [GattOpenStatus::SharingViolation,GattOpenStatus::AccessDenied,GattOpenStatus::NotFound,GattOpenStatus::Unspecified,GattOpenStatus(77)] {
            let error=require_shared_service(status,Some(GattSharingMode::SharedReadAndWrite),uuid).unwrap_err().to_string();
            assert!(error.contains("no exclusive fallback or control command"));
        }
    }
}
