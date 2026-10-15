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

use crate::{api::BDAddr, winrtble::utils, Error, Result};
use super::characteristic::await_cancellable_gatt;
use log::{debug, trace};
use std::future::IntoFuture;
use uuid::Uuid;
use windows::{
    core::Ref,
    Devices::Bluetooth::{
        BluetoothCacheMode, BluetoothConnectionStatus, BluetoothLEDevice,
        GenericAttributeProfile::{
            GattCharacteristic, GattCommunicationStatus, GattDescriptor, GattDeviceService,
            GattDeviceServicesResult,
        },
    },
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

impl BLEDevice {
    pub async fn new(
        address: BDAddr,
        connection_status_changed: ConnectedEventHandler,
    ) -> Result<Self> {
        let async_op = BluetoothLEDevice::FromBluetoothAddressAsync(address.into())
            .map_err(|_| Error::DeviceNotFound)?;
        let device = async_op
            .into_future()
            .await
            .map_err(|_| Error::DeviceNotFound)?;
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
        let service_result = async_op.into_future().await.map_err(winrt_error)?;
        Ok(service_result)
    }

    pub async fn connect(&self) -> Result<()> {
        if self.is_connected().await? {
            return Ok(());
        }

        let service_result = self.get_gatt_services(BluetoothCacheMode::Uncached).await?;
        let status = service_result.Status().map_err(|_| Error::DeviceNotFound)?;
        utils::to_error(status)
    }

    async fn is_connected(&self) -> Result<bool> {
        let winrt_error = |e| Error::Other(format!("{:?}", e).into());
        let status = self.device.ConnectionStatus().map_err(winrt_error)?;

        Ok(status == BluetoothConnectionStatus::Connected)
    }

    pub async fn get_characteristics(
        service: &GattDeviceService,
    ) -> Result<Vec<GattCharacteristic>> {
        let async_result = service
            .GetCharacteristicsWithCacheModeAsync(BluetoothCacheMode::Uncached)?
            .into_future()
            .await?;

        match async_result.Status() {
            Ok(GattCommunicationStatus::Success) => {
                let results = async_result.Characteristics()?;
                debug!("characteristics {:?}", results.Size());
                Ok(results.into_iter().collect())
            }
            Ok(GattCommunicationStatus::ProtocolError) => Err(Error::Other(
                format!(
                    "get_characteristics for {:?} encountered a protocol error",
                    service
                )
                .into(),
            )),
            Ok(status) => {
                debug!("characteristic read failed due to {:?}", status);
                Ok(vec![])
            }
            Err(e) => Err(Error::Other(
                format!("get_characteristics for {:?} failed: {:?}", service, e).into(),
            )),
        }
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
        let result = await_cancellable_gatt(service.GetCharacteristicsWithCacheModeAsync(
            BluetoothCacheMode::Uncached,
        )?).await?;
        let status = result.Status()?;
        let protocol_error = if status == GattCommunicationStatus::ProtocolError {
            result.ProtocolError().and_then(|value| value.Value()).ok()
        } else { None };
        require_discovery_success(status, "get_characteristics_strict", uuid, protocol_error)?;
        let characteristics: Vec<_> = result.Characteristics()?.into_iter().collect();
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
        let status = service_result.Status().map_err(winrt_error)?;
        if status == GattCommunicationStatus::Success {
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

        self.services.iter().for_each(|service| {
            if let Err(err) = service.Close() {
                debug!("Drop:remove_gatt_Service {:?}", err);
            }
        });

        let result = self.device.Close();
        if let Err(err) = result {
            debug!("Drop:close {:?}", err);
        }
    }
}

#[cfg(test)]
mod discovery_tests {
    use super::*;

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
}
