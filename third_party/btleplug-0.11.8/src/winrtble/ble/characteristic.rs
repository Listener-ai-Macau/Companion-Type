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

use super::{super::utils::to_descriptor_value, descriptor::BLEDescriptor};
use crate::{
    api::{Characteristic, WriteType},
    winrtble::utils,
    Error, Result,
};

use log::{debug, trace};
use std::{
    collections::HashMap,
    future::{Future, IntoFuture},
};
use uuid::Uuid;
use windows::core::{Ref, RuntimeType};
use windows::{
    Devices::Bluetooth::{
        BluetoothCacheMode,
        GenericAttributeProfile::{
            GattCharacteristic, GattClientCharacteristicConfigurationDescriptorValue,
            GattCommunicationStatus, GattValueChangedEventArgs, GattWriteOption,
        },
    },
    Foundation::TypedEventHandler,
    Storage::Streams::{DataReader, DataWriter},
};
use windows_future::{AsyncStatus, IAsyncOperation};

pub type NotifiyEventHandler = Box<dyn Fn(Vec<u8>) + Send>;

// IAsyncOperation is Send in the Windows bindings; holding it also keeps its
// cancellation interface alive without adding an unsafe Send for IAsyncInfo.
struct CancelPendingGatt<T: RuntimeType + 'static>(IAsyncOperation<T>);

impl<T: RuntimeType + 'static> Drop for CancelPendingGatt<T> {
    fn drop(&mut self) {
        // Dropping windows-future's adapter only drops COM references. The
        // already-started OS request can otherwise outlive a caller's timeout.
        if self
            .0
            .Status()
            .map_or(true, |status| status == AsyncStatus::Started)
        {
            if let Err(error) = self.0.Cancel() {
                debug!("GATT cancellation request failed: {error}");
            } else {
                debug!("GATT cancellation requested; completion is not confirmed");
            }
        }
    }
}

fn await_cancellable_gatt<T: RuntimeType + 'static>(
    operation: IAsyncOperation<T>,
) -> impl Future<Output = windows::core::Result<T>> {
    // Arm before returning a future: WinRT operations are hot-started, even if
    // the caller cancels before the first poll. Cancel is a request, not an ACK
    // or permission to reuse an unconfirmed connection/consume recording data.
    let guard = CancelPendingGatt(operation.clone());
    async move {
        let result = operation.into_future().await;
        drop(guard);
        result
    }
}

impl From<WriteType> for GattWriteOption {
    fn from(val: WriteType) -> Self {
        match val {
            WriteType::WithoutResponse => GattWriteOption::WriteWithoutResponse,
            WriteType::WithResponse => GattWriteOption::WriteWithResponse,
        }
    }
}

#[derive(Debug)]
pub struct BLECharacteristic {
    characteristic: GattCharacteristic,
    pub descriptors: HashMap<Uuid, BLEDescriptor>,
    notify_token: Option<i64>,
}

impl BLECharacteristic {
    pub fn new(
        characteristic: GattCharacteristic,
        descriptors: HashMap<Uuid, BLEDescriptor>,
    ) -> Self {
        BLECharacteristic {
            characteristic,
            descriptors,
            notify_token: None,
        }
    }

    pub async fn write_value(&self, data: &[u8], write_type: WriteType) -> Result<()> {
        let with_response = matches!(write_type, WriteType::WithResponse);
        let writer = DataWriter::new()?;
        writer.WriteBytes(data)?;
        let operation = self
            .characteristic
            .WriteValueWithOptionAsync(&writer.DetachBuffer()?, write_type.into())?;
        let result = if with_response {
            await_cancellable_gatt(operation).await?
        } else {
            // Keep the bulk write-without-response path unchanged.
            operation.into_future().await?
        };
        if result == GattCommunicationStatus::Success {
            Ok(())
        } else {
            Err(Error::Other(
                format!("Windows UWP threw error on write: {:?}", result).into(),
            ))
        }
    }

    pub async fn read_value(&self) -> Result<Vec<u8>> {
        let operation = self
            .characteristic
            .ReadValueWithCacheModeAsync(BluetoothCacheMode::Uncached)?;
        let result = await_cancellable_gatt(operation).await?;
        if result.Status()? == GattCommunicationStatus::Success {
            let value = result.Value()?;
            let reader = DataReader::FromBuffer(&value)?;
            let len = reader.UnconsumedBufferLength()? as usize;
            let mut input = vec![0u8; len];
            reader.ReadBytes(&mut input[0..len])?;
            Ok(input)
        } else {
            Err(Error::Other(
                format!("Windows UWP threw error on read: {:?}", result).into(),
            ))
        }
    }

    pub async fn subscribe(&mut self, on_value_changed: NotifiyEventHandler) -> Result<()> {
        {
            let value_handler = TypedEventHandler::new(
                move |_: Ref<GattCharacteristic>, args: Ref<GattValueChangedEventArgs>| {
                    if let Ok(args) = args.ok() {
                        let value = args.CharacteristicValue()?;
                        let reader = DataReader::FromBuffer(&value)?;
                        let len = reader.UnconsumedBufferLength()? as usize;
                        let mut input: Vec<u8> = vec![0u8; len];
                        reader.ReadBytes(&mut input[0..len])?;
                        trace!("changed {:?}", input);
                        on_value_changed(input);
                    }
                    Ok(())
                },
            );
            let token = self.characteristic.ValueChanged(&value_handler)?;
            self.notify_token = Some(token);
        }
        let config = to_descriptor_value(self.characteristic.CharacteristicProperties()?);
        if config == GattClientCharacteristicConfigurationDescriptorValue::None {
            return Err(Error::NotSupported("Can not subscribe to attribute".into()));
        }

        let operation = self
            .characteristic
            .WriteClientCharacteristicConfigurationDescriptorAsync(config)?;
        let status = await_cancellable_gatt(operation).await?;
        trace!("subscribe {:?}", status);
        if status == GattCommunicationStatus::Success {
            Ok(())
        } else {
            Err(Error::Other(
                format!("Windows UWP threw error on subscribe: {:?}", status).into(),
            ))
        }
    }

    pub async fn unsubscribe(&mut self) -> Result<()> {
        if let Some(token) = &self.notify_token {
            self.characteristic.RemoveValueChanged(*token)?;
        }
        self.notify_token = None;
        let config = GattClientCharacteristicConfigurationDescriptorValue::None;
        let operation = self
            .characteristic
            .WriteClientCharacteristicConfigurationDescriptorAsync(config)?;
        let status = await_cancellable_gatt(operation).await?;
        trace!("unsubscribe {:?}", status);
        if status == GattCommunicationStatus::Success {
            Ok(())
        } else {
            Err(Error::Other(
                format!("Windows UWP threw error on unsubscribe: {:?}", status).into(),
            ))
        }
    }

    pub fn uuid(&self) -> Uuid {
        utils::to_uuid(&self.characteristic.Uuid().unwrap())
    }

    pub fn to_characteristic(&self, service_uuid: Uuid) -> Characteristic {
        let uuid = self.uuid();
        let properties =
            utils::to_char_props(&self.characteristic.CharacteristicProperties().unwrap());
        let descriptors = self
            .descriptors
            .values()
            .map(|descriptor| descriptor.to_descriptor(service_uuid, uuid))
            .collect();
        Characteristic {
            uuid,
            service_uuid,
            descriptors,
            properties,
        }
    }
}

impl Drop for BLECharacteristic {
    fn drop(&mut self) {
        if let Some(token) = &self.notify_token {
            let result = self.characteristic.RemoveValueChanged(*token);
            if let Err(err) = result {
                debug!("Drop:remove_connection_status_changed {:?}", err);
            }
        }
    }
}

#[cfg(test)]
mod cancellation_tests {
    use super::*;
    use std::{
        pin::pin,
        sync::{
            atomic::{AtomicUsize, Ordering},
            Arc,
        },
        task::{Context, Poll},
    };
    use windows::core::{implement, HRESULT};
    use windows_future::{
        AsyncOperationCompletedHandler, IAsyncInfo, IAsyncInfo_Impl, IAsyncOperation_Impl,
    };

    #[implement(IAsyncOperation<GattCommunicationStatus>, IAsyncInfo)]
    struct ControlledGatt {
        status: AsyncStatus,
        cancel_count: Arc<AtomicUsize>,
    }

    impl IAsyncInfo_Impl for ControlledGatt_Impl {
        fn Id(&self) -> windows::core::Result<u32> {
            Ok(1)
        }
        fn Status(&self) -> windows::core::Result<AsyncStatus> {
            Ok(self.status)
        }
        fn ErrorCode(&self) -> windows::core::Result<HRESULT> {
            Ok(HRESULT(0))
        }
        fn Cancel(&self) -> windows::core::Result<()> {
            self.cancel_count.fetch_add(1, Ordering::SeqCst);
            Ok(())
        }
        fn Close(&self) -> windows::core::Result<()> {
            Ok(())
        }
    }

    impl IAsyncOperation_Impl<GattCommunicationStatus> for ControlledGatt_Impl {
        fn SetCompleted(
            &self,
            _: Ref<AsyncOperationCompletedHandler<GattCommunicationStatus>>,
        ) -> windows::core::Result<()> {
            Ok(())
        }
        fn Completed(
            &self,
        ) -> windows::core::Result<AsyncOperationCompletedHandler<GattCommunicationStatus>>
        {
            Err(windows::core::Error::from_hresult(HRESULT(
                0x80004005u32 as i32,
            )))
        }
        fn GetResults(&self) -> windows::core::Result<GattCommunicationStatus> {
            if self.status == AsyncStatus::Completed {
                Ok(GattCommunicationStatus::Success)
            } else {
                Err(windows::core::Error::from_hresult(HRESULT(
                    0x80004005u32 as i32,
                )))
            }
        }
    }

    fn operation(
        status: AsyncStatus,
        count: &Arc<AtomicUsize>,
    ) -> IAsyncOperation<GattCommunicationStatus> {
        ControlledGatt {
            status,
            cancel_count: count.clone(),
        }
        .into()
    }

    #[test]
    fn cancelled_gatt_wait_requests_native_cancel_even_before_first_poll() {
        let count = Arc::new(AtomicUsize::new(0));
        drop(await_cancellable_gatt(operation(
            AsyncStatus::Started,
            &count,
        )));
        assert_eq!(count.load(Ordering::SeqCst), 1);
        let count = Arc::new(AtomicUsize::new(0));
        {
            let mut future = pin!(await_cancellable_gatt(operation(
                AsyncStatus::Started,
                &count
            )));
            let mut context = Context::from_waker(futures::task::noop_waker_ref());
            assert!(matches!(future.as_mut().poll(&mut context), Poll::Pending));
            assert_eq!(count.load(Ordering::SeqCst), 0);
        }
        assert_eq!(count.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn finished_gatt_wait_preserves_native_result_without_cancelling() {
        for status in [
            AsyncStatus::Completed,
            AsyncStatus::Error,
            AsyncStatus::Canceled,
        ] {
            let count = Arc::new(AtomicUsize::new(0));
            let mut future = pin!(await_cancellable_gatt(operation(status, &count)));
            let mut context = Context::from_waker(futures::task::noop_waker_ref());
            let result = future.as_mut().poll(&mut context);
            match (status == AsyncStatus::Completed, result) {
                (true, Poll::Ready(Ok(GattCommunicationStatus::Success)))
                | (false, Poll::Ready(Err(_))) => {}
                (_, result) => panic!("native result changed: {result:?}"),
            }
            drop(future);
            assert_eq!(count.load(Ordering::SeqCst), 0);
        }
    }
}
