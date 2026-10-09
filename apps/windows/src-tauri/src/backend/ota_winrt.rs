//! Companion OTA v1 host path: **WinRT dual-lane WWR** via platform
//! `denzic-ble-windows` — same shape as Listener 1.0.3, not btleplug threads.
//!
//! Copied from Listener-Type `windows_ble` dual-lane pipeline:
//! - `start_gatt_write_with_option_async` + dual pending queues
//! - joint drain of DATA + DATA_B
//! - `TransferOptions::dual_lane_bulk` window=400, inactive cold=64
//! - pipeline depth 32 (~16/lane)
//!
//! Chunk payload stays WB SAFE_ATT (caller passes ≤244).

#![cfg(windows)]

use std::time::{Duration, Instant};

use denzic_ble_windows::{
    open_ble_device_with_timeout, read_characteristic_bytes_with_timeout,
    start_gatt_write_with_option_async, wait_async_operation_with_cancel,
    write_gatt_value_status_with_timeout, write_gatt_value_with_timeout, BleCancel,
    ASYNC_POLL_INTERVAL_MS,
};
use windows::core::{GUID, HSTRING};
use windows::Devices::Bluetooth::GenericAttributeProfile::{
    GattCharacteristic, GattCharacteristicProperties, GattCommunicationStatus, GattDeviceService,
    GattSession, GattSessionStatus, GattWriteOption,
};
use windows::Devices::Bluetooth::{
    BluetoothCacheMode, BluetoothLEDevice, BluetoothLEPreferredConnectionParameters,
    BluetoothLEPreferredConnectionParametersRequest,
};
use windows::Devices::Enumeration::{DeviceAccessStatus, DeviceInformation};
use windows::Foundation::IAsyncOperation;

use super::ble_bridge::CompanionOtaBleReport;

const OTA_SERVICE_UUID: GUID = GUID::from_u128(denzic_ota_core::GATT_SERVICE_UUID_U128);
const OTA_CONTROL_UUID: GUID = GUID::from_u128(denzic_ota_core::GATT_CONTROL_UUID_U128);
const OTA_DATA_UUID: GUID = GUID::from_u128(denzic_ota_core::GATT_DATA_UUID_U128);
const OTA_DATA_B_UUID: GUID = GUID::from_u128(denzic_ota_core::GATT_DATA_B_UUID_U128);
const OTA_STATUS_UUID: GUID = GUID::from_u128(denzic_ota_core::GATT_STATUS_UUID_U128);

/// Listener-proven dual-lane host pipeline (windows_ble). Measured on WB:
/// depth 32 ~16.4 KB/s / 4 recoveries; depth 16 thrashed worse (~10 KB/s).
const WWR_PIPELINE_DEPTH: usize = 32;
const INACTIVE_LINK_WINDOW_CHUNKS: u16 = 64;
const WINDOW_CHUNKS: u16 = 400;
const DISCOVERY_TIMEOUT: Duration = Duration::from_secs(12);
const GATT_READY_TIMEOUT: Duration = Duration::from_secs(8);
const OTA_WRITE_TIMEOUT: Duration = Duration::from_secs(8);
const OTA_SYNC_WRITE_TIMEOUT: Duration = Duration::from_secs(30);
const OTA_FINISH_WRITE_TIMEOUT: Duration = Duration::from_secs(12);
const OTA_ABORT_WRITE_TIMEOUT: Duration = Duration::from_secs(2);
const STATUS_READ_TIMEOUT: Duration = Duration::from_secs(3);
const STATUS_POLL_INTERVAL: Duration = Duration::from_millis(8);
const PROGRESS_TIMEOUT: Duration = Duration::from_secs(120);

struct OpenOtaTarget {
    device_id: String,
    control: GattCharacteristic,
    data: GattCharacteristic,
    data_b: Option<GattCharacteristic>,
    status: GattCharacteristic,
    data_write_option: GattWriteOption,
    /// Keep device/service/session alive for the transfer.
    _service: GattDeviceService,
    _session: Option<GattSession>,
    _device: Option<BluetoothLEDevice>,
    /// WinRT keeps preferred CI only while this request object lives.
    _conn_pref_request: Option<BluetoothLEPreferredConnectionParametersRequest>,
}

struct CompanionOtaWinrtTransport<'a> {
    target: &'a OpenOtaTarget,
    pending_wwr: Vec<IAsyncOperation<GattCommunicationStatus>>,
    pending_wwr_b: Vec<IAsyncOperation<GattCommunicationStatus>>,
    status_error_started: Option<Instant>,
    wba_signed: bool,
}

pub fn transfer_companion_ota_winrt(
    requested_device_id: Option<&str>,
    firmware: &[u8],
    chunk_bytes: u16,
    wba_manifest: Option<&[u8; 144]>,
) -> Result<CompanionOtaBleReport, String> {
    // Connection-params request is held on `target` for the whole transfer.
    let mut target = open_ota_target(requested_device_id)?;
    let manifest_char=open_write_char(&target._service,
        GUID::from_u128(super::firmware_ota::WBA_MANIFEST_UUID_U128),"WBA signed manifest").ok();
    match (wba_manifest, manifest_char.as_ref()) {
        (Some(wire),Some(characteristic)) => {
            // Attribute writes may be readable before the application handles
            // them. Require the device's distinct post-verification receipt,
            // never a readback of our own unverified 144-byte write.
            let mut receipt=[0u8;8];receipt[..4].copy_from_slice(b"WMA1");
            receipt[4..].copy_from_slice(&crc32fast::hash(&wire[..140]).to_le_bytes());
            write_gatt_value_with_timeout(characteristic,wire,GattWriteOption::WriteWithResponse,
                OTA_WRITE_TIMEOUT,"WBA signed manifest")?;
            let deadline=Instant::now()+OTA_WRITE_TIMEOUT;
            loop {
                let accepted=read_characteristic_bytes_with_timeout(characteristic,BluetoothCacheMode::Uncached,
                    "WBA manifest acceptance",STATUS_READ_TIMEOUT,&BleCancel::NONE)?;
                if accepted.as_slice()==receipt {break;}
                if Instant::now()>=deadline {return Err("WBA rejected the signed manifest (key, target, version or device busy); no payload was sent".into());}
                std::thread::sleep(Duration::from_millis(50));
            }
        }
        (Some(_),None)=>return Err("Selected device does not expose the WBA signed update service; no payload was sent".into()),
        (None,Some(_))=>return Err("A WBA device requires a signed WBA package; WB55 payload was not sent".into()),
        (None,None)=>{}
    }
    if target.data_b.is_some() {
        eprintln!("[companion-ota] dual-lane DATA+DATA_B available (platform dual-lane WinRT)");
    } else {
        eprintln!("[companion-ota] single-lane DATA only (no DATA_B on device)");
    }
    eprintln!("[companion-ota] host=WinRT/denzic-ble-windows (Listener-aligned dual WWR pipeline)");

    // Preferred CI only sticks while the Request object is kept alive on the
    // *same* BluetoothLEDevice as the GATT session. Python subprocess / separate
    // FromAddress open was the wrong path (params drop when process exits).
    if std::env::var("COMPANION_TYPE_SKIP_WINRT_CONN_PARAMS")
        .map(|v| {
            let t = v.trim();
            t == "1" || t.eq_ignore_ascii_case("true")
        })
        .unwrap_or(false)
    {
        eprintln!("[companion-ota] winrt_pref=skipped (COMPANION_TYPE_SKIP_WINRT_CONN_PARAMS)");
    } else if let Some(device) = target._device.as_ref() {
        match apply_throughput_optimized(device) {
            Ok(req) => {
                eprintln!(
                    "[companion-ota] winrt_pref=ThroughputOptimized held_on_device={}",
                    target.device_id
                );
                target._conn_pref_request = Some(req);
                // Let controller apply CI before blasting WWR.
                std::thread::sleep(Duration::from_millis(700));
            }
            Err(err) => {
                eprintln!(
                    "[companion-ota] winrt_pref=failed ({err}); continuing without preferred CI"
                );
            }
        }
    } else {
        eprintln!(
            "[companion-ota] winrt_pref=no_device_handle (open path lacked BluetoothLEDevice)"
        );
    }

    let pipeline = WWR_PIPELINE_DEPTH;
    eprintln!(
        "[companion-ota] wwr_pipeline_depth={pipeline} per_lane={} dual={}",
        (pipeline + 1) / 2,
        target.data_b.is_some()
    );

    let mut options = denzic_ota_core::TransferOptions::dual_lane_bulk(chunk_bytes);
    options.chunk_payload_bytes = chunk_bytes;
    options.window_chunks = if wba_manifest.is_some() {8} else {WINDOW_CHUNKS};
    options.inactive_link_window_chunks = Some(if wba_manifest.is_some() {8} else {INACTIVE_LINK_WINDOW_CHUNKS});
    options.prefer_dual_lane = wba_manifest.is_none();
    eprintln!(
        "[companion-ota] bulk options window_chunks={} prefer_dual_lane={} inactive_link={:?} chunk_payload={} dual_lane_available={}",
        options.window_chunks,
        options.prefer_dual_lane,
        options.inactive_link_window_chunks,
        options.chunk_payload_bytes,
        target.data_b.is_some()
    );

    let mut transport = CompanionOtaWinrtTransport {
        target: &target,
        pending_wwr: Vec::with_capacity(pipeline),
        pending_wwr_b: Vec::with_capacity(pipeline),
        status_error_started: None,
        wba_signed: wba_manifest.is_some(),
    };

    let report = denzic_ota_core::transfer(&mut transport, firmware, options, |_, _| {})
        .map_err(|e| e.to_string())?;
    if wba_manifest.is_some() {
        // FINISH means bytes arrived. WBA must additionally finish readback
        // verification and durably arm the resident installer before success.
        let deadline=Instant::now()+Duration::from_secs(120);
        loop {
            let bytes=read_characteristic_bytes_with_timeout(&target.status,BluetoothCacheMode::Uncached,
                "WBA staged-image verification",STATUS_READ_TIMEOUT,&BleCancel::NONE)?;
            let status=denzic_ota_core::parse_status(&bytes)?;
            if status.state==denzic_ota_core::STATE_ERROR {
                return Err(format!("WBA staged-image verification failed: {}",status.last_error));
            }
            if status.state==denzic_ota_core::STATE_COMPLETE && status.bytes_written as usize==firmware.len() {break;}
            if Instant::now()>=deadline {return Err("WBA timed out verifying the staged image; installation is not confirmed".into());}
            std::thread::sleep(Duration::from_millis(50));
        }
    }

    let total_ms = report.timings.total.as_secs_f64().max(0.001);
    let transport_ms = report.timings.transport_elapsed().as_secs_f64().max(0.001);
    let bulk_kb_s = (report.firmware_bytes as f64 / 1024.0) / total_ms;
    let transport_kb_s = (report.firmware_bytes as f64 / 1024.0) / transport_ms;
    eprintln!(
        "[companion-ota] bulk_kb_s={:.1} transport_kb_s={:.1} bytes={} data_writes={} status_reads={} dual={} active_link={} recovered_offsets={} elapsed_ms={:.0} transport_ms={:.0}",
        bulk_kb_s,
        transport_kb_s,
        report.firmware_bytes,
        report.data_writes,
        report.status_reads,
        target.data_b.is_some(),
        report.active_link_confirmed,
        report.recovered_offsets,
        total_ms * 1000.0,
        transport_ms * 1000.0
    );
    eprintln!(
        "firmware_ota_report bulk_kb_s={:.2} protocol_ms={:.0} wall_ms={:.0} bytes={} data_writes={} chunk_note=WB_SAFE_ATT_le_244 host=winrt_dual_wwr",
        bulk_kb_s,
        total_ms * 1000.0,
        total_ms * 1000.0,
        report.firmware_bytes,
        report.data_writes
    );

    Ok(CompanionOtaBleReport {
        device_id: target.device_id.clone(),
        transfer: report,
    })
}

fn open_ota_target(requested_device_id: Option<&str>) -> Result<OpenOtaTarget, String> {
    if let Some(id) = requested_device_id.map(str::trim).filter(|s| !s.is_empty()) {
        if let Ok(addr) = parse_ble_address(id) {
            // Explicit address: do not fall through to service-index (UUID crumbs /
            // wrong radio). Prefer the radio the operator named.
            return open_ota_target_for_address(addr, id)
                .map_err(|err| format!("OTA open by address {id} failed: {err}"));
        }
    }
    open_ota_target_from_service_index(requested_device_id)
}

fn open_ota_target_from_service_index(
    requested_device_id: Option<&str>,
) -> Result<OpenOtaTarget, String> {
    let selector = GattDeviceService::GetDeviceSelectorFromUuid(OTA_SERVICE_UUID)
        .map_err(|e| format!("OTA service selector failed: {e}"))?;
    let cancel = BleCancel::NONE;
    let op = DeviceInformation::FindAllAsyncAqsFilter(&selector)
        .map_err(|e| format!("OTA service discovery failed: {e}"))?;
    let devices =
        wait_async_operation_with_cancel(op, DISCOVERY_TIMEOUT, "OTA service discovery", &cancel)?;
    let count = devices
        .Size()
        .map_err(|e| format!("OTA service collection size failed: {e}"))?;
    if count == 0 {
        return Err(
            "Companion OTA service not found in Windows index (is the board in OTA/loader mode?)"
                .to_string(),
        );
    }
    let want = requested_device_id
        .map(|s| s.trim().to_ascii_uppercase().replace('-', ":"))
        .filter(|s| !s.is_empty());
    let mut last_err = None;
    for i in 0..count {
        let info = match devices.GetAt(i) {
            Ok(v) => v,
            Err(e) => {
                last_err = Some(format!("OTA service info[{i}]: {e}"));
                continue;
            }
        };
        let name = info.Name().map(|n| n.to_string()).unwrap_or_default();
        let id = match info.Id() {
            Ok(id) => id.to_string(),
            Err(e) => {
                last_err = Some(format!("OTA service id[{i}]: {e}"));
                continue;
            }
        };
        let addr_from_id = parse_bluetooth_address_from_device_id(&id);
        let addr_str = addr_from_id
            .map(format_ble_address)
            .unwrap_or_else(|| id.clone());
        if let Some(ref want) = want {
            let cand = addr_str.to_ascii_uppercase();
            if !cand.contains(want)
                && !want.contains(&cand)
                && !id.to_ascii_uppercase().contains(want)
            {
                continue;
            }
        } else {
            // Prefer companion-named endpoints when not requesting a specific address.
            let lower = name.to_ascii_lowercase();
            if !lower.is_empty()
                && !lower.contains("companion")
                && !lower.contains("ota")
                && count > 1
            {
                // still try later if nothing else works
            }
        }
        match open_ota_target_for_service_id(&id, &addr_str) {
            Ok(t) => {
                eprintln!(
                    "[companion-ota] selected WinRT OTA endpoint name={name} id_tail={}",
                    &id[id.len().saturating_sub(24)..]
                );
                return Ok(t);
            }
            Err(e) => last_err = Some(format!("{name}: {e}")),
        }
        if let Some(addr) = addr_from_id {
            match open_ota_target_for_address(addr, &addr_str) {
                Ok(t) => return Ok(t),
                Err(e) => last_err = Some(format!("{addr_str}: {e}")),
            }
        }
    }
    // Second pass: any service
    for i in 0..count {
        let info = devices.GetAt(i).map_err(|e| e.to_string())?;
        let id = info.Id().map_err(|e| e.to_string())?.to_string();
        let addr_str = parse_bluetooth_address_from_device_id(&id)
            .map(format_ble_address)
            .unwrap_or_else(|| id.clone());
        if let Ok(t) = open_ota_target_for_service_id(&id, &addr_str) {
            return Ok(t);
        }
    }
    Err(last_err.unwrap_or_else(|| "No writable Companion OTA service found".to_string()))
}

fn open_ota_target_for_address(
    address: u64,
    device_id_label: &str,
) -> Result<OpenOtaTarget, String> {
    let cancel = BleCancel::NONE;
    let device = open_ble_device_with_timeout(address, DISCOVERY_TIMEOUT, false, &cancel)?;
    // Always label with the radio address from the open handle (not service-id UUID crumbs).
    let label = device
        .BluetoothAddress()
        .ok()
        .map(format_ble_address)
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| device_id_label.to_string());
    let services_op = device
        .GetGattServicesForUuidWithCacheModeAsync(OTA_SERVICE_UUID, BluetoothCacheMode::Uncached)
        .map_err(|e| format!("OTA GetGattServices failed: {e}"))?;
    let services_result =
        wait_async_operation_with_cancel(services_op, DISCOVERY_TIMEOUT, "OTA services", &cancel)?;
    let status = services_result
        .Status()
        .map_err(|e| format!("OTA services status: {e}"))?;
    if status != GattCommunicationStatus::Success {
        let _ = device.Close();
        return Err(format!("OTA services status={status:?}"));
    }
    let services = services_result
        .Services()
        .map_err(|e| format!("OTA services list: {e}"))?;
    if services.Size().unwrap_or(0) == 0 {
        let _ = device.Close();
        return Err("OTA service not present on device".to_string());
    }
    let service = services.GetAt(0).map_err(|e| format!("OTA service: {e}"))?;
    open_chars_from_service(service, Some(device), &label)
}

fn open_ota_target_for_service_id(
    service_id: &str,
    device_id_label: &str,
) -> Result<OpenOtaTarget, String> {
    let cancel = BleCancel::NONE;
    let op = GattDeviceService::FromIdAsync(&windows::core::HSTRING::from(service_id))
        .map_err(|e| format!("OTA FromIdAsync failed: {e}"))?;
    let service =
        wait_async_operation_with_cancel(op, DISCOVERY_TIMEOUT, "OTA service from id", &cancel)?;
    open_chars_from_service(service, None, device_id_label)
}

fn open_chars_from_service(
    service: GattDeviceService,
    device: Option<BluetoothLEDevice>,
    device_id_label: &str,
) -> Result<OpenOtaTarget, String> {
    let cancel = BleCancel::NONE;
    if let Ok(op) = service.RequestAccessAsync() {
        if let Ok(access) =
            wait_async_operation_with_cancel(op, DISCOVERY_TIMEOUT, "OTA access", &cancel)
        {
            if access != DeviceAccessStatus::Allowed && access != DeviceAccessStatus::Unspecified {
                return Err(format!("OTA service access denied: {access:?}"));
            }
        }
    }
    // Prefer an explicit device handle; otherwise reopen from the service DeviceId
    // so ThroughputOptimized can be held for the transfer lifetime.
    let device = match device {
        Some(d) => Some(d),
        None => reopen_device_from_service(&service),
    };
    let resolved_id = device
        .as_ref()
        .and_then(|d| d.BluetoothAddress().ok())
        .map(format_ble_address)
        .filter(|s| !s.is_empty() && !looks_like_uuid_crumb(s))
        .or_else(|| {
            let candidate = device_id_label.to_string();
            if looks_like_uuid_crumb(&candidate) {
                None
            } else {
                Some(candidate)
            }
        })
        .unwrap_or_else(|| device_id_label.to_string());
    let session = prepare_gatt_session(&service)?;
    let control = open_write_char(&service, OTA_CONTROL_UUID, "control")?;
    let data = open_write_char(&service, OTA_DATA_UUID, "data")?;
    let data_b = open_write_char(&service, OTA_DATA_B_UUID, "data_b").ok();
    let status = open_read_char(&service, OTA_STATUS_UUID, "status")?;
    let props = data
        .CharacteristicProperties()
        .map_err(|e| format!("data properties: {e}"))?;
    let data_write_option = if props.contains(GattCharacteristicProperties::WriteWithoutResponse) {
        GattWriteOption::WriteWithoutResponse
    } else if props.contains(GattCharacteristicProperties::Write) {
        GattWriteOption::WriteWithResponse
    } else {
        return Err("OTA data characteristic is not writable".to_string());
    };
    Ok(OpenOtaTarget {
        device_id: resolved_id,
        control,
        data,
        data_b,
        status,
        data_write_option,
        _service: service,
        _session: session,
        _device: device,
        _conn_pref_request: None,
    })
}

fn reopen_device_from_service(service: &GattDeviceService) -> Option<BluetoothLEDevice> {
    let device_id = service.DeviceId().ok()?.to_string();
    if device_id.is_empty() {
        return None;
    }
    let cancel = BleCancel::NONE;
    let op = BluetoothLEDevice::FromIdAsync(&HSTRING::from(device_id.as_str())).ok()?;
    wait_async_operation_with_cancel(op, DISCOVERY_TIMEOUT, "OTA device from service", &cancel).ok()
}

fn apply_throughput_optimized(
    device: &BluetoothLEDevice,
) -> Result<BluetoothLEPreferredConnectionParametersRequest, String> {
    let preferred = BluetoothLEPreferredConnectionParameters::ThroughputOptimized()
        .map_err(|e| format!("ThroughputOptimized factory: {e}"))?;
    device
        .RequestPreferredConnectionParameters(&preferred)
        .map_err(|e| format!("RequestPreferredConnectionParameters: {e}"))
}

fn prepare_gatt_session(service: &GattDeviceService) -> Result<Option<GattSession>, String> {
    let session = match service.Session() {
        Ok(s) => s,
        Err(_) => return Ok(None),
    };
    let deadline = Instant::now() + GATT_READY_TIMEOUT;
    while Instant::now() < deadline {
        if let Ok(status) = session.SessionStatus() {
            if status == GattSessionStatus::Active {
                let _ = session.SetMaintainConnection(true);
                return Ok(Some(session));
            }
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    // Best-effort: continue without active session flag.
    let _ = session.SetMaintainConnection(true);
    Ok(Some(session))
}

fn open_write_char(
    service: &GattDeviceService,
    uuid: GUID,
    label: &str,
) -> Result<GattCharacteristic, String> {
    let cancel = BleCancel::NONE;
    let op = service
        .GetCharacteristicsForUuidWithCacheModeAsync(uuid, BluetoothCacheMode::Uncached)
        .map_err(|e| format!("OTA {label} discovery failed: {e}"))?;
    let result =
        wait_async_operation_with_cancel(op, DISCOVERY_TIMEOUT, &format!("OTA {label}"), &cancel)?;
    let status = result
        .Status()
        .map_err(|e| format!("OTA {label} status: {e}"))?;
    if status != GattCommunicationStatus::Success {
        return Err(format!("OTA {label} discovery status={status:?}"));
    }
    let chars = result
        .Characteristics()
        .map_err(|e| format!("OTA {label} list: {e}"))?;
    if chars.Size().unwrap_or(0) == 0 {
        return Err(format!("OTA {label} characteristic missing"));
    }
    let ch = chars
        .GetAt(0)
        .map_err(|e| format!("OTA {label} get: {e}"))?;
    let props = ch
        .CharacteristicProperties()
        .map_err(|e| format!("OTA {label} props: {e}"))?;
    if !props.contains(GattCharacteristicProperties::Write)
        && !props.contains(GattCharacteristicProperties::WriteWithoutResponse)
    {
        return Err(format!("OTA {label} not writable"));
    }
    Ok(ch)
}

fn open_read_char(
    service: &GattDeviceService,
    uuid: GUID,
    label: &str,
) -> Result<GattCharacteristic, String> {
    let cancel = BleCancel::NONE;
    let op = service
        .GetCharacteristicsForUuidWithCacheModeAsync(uuid, BluetoothCacheMode::Uncached)
        .map_err(|e| format!("OTA {label} discovery failed: {e}"))?;
    let result =
        wait_async_operation_with_cancel(op, DISCOVERY_TIMEOUT, &format!("OTA {label}"), &cancel)?;
    let status = result
        .Status()
        .map_err(|e| format!("OTA {label} status: {e}"))?;
    if status != GattCommunicationStatus::Success {
        return Err(format!("OTA {label} discovery status={status:?}"));
    }
    let chars = result
        .Characteristics()
        .map_err(|e| format!("OTA {label} list: {e}"))?;
    if chars.Size().unwrap_or(0) == 0 {
        return Err(format!("OTA {label} characteristic missing"));
    }
    chars.GetAt(0).map_err(|e| format!("OTA {label} get: {e}"))
}

impl CompanionOtaWinrtTransport<'_> {
    fn cancel_pending_wwr(&mut self) {
        for pending in [&mut self.pending_wwr, &mut self.pending_wwr_b] {
            for operation in pending.drain(..) {
                let _ = operation.Cancel();
                let _ = operation.Close();
            }
        }
    }

    fn flush_pending_wwr(&mut self) -> Result<(), String> {
        self.drain_pending_wwr_until(0, 0)
    }

    fn drain_pending_wwr_until(&mut self, max_a: usize, max_b: usize) -> Result<(), String> {
        if self.pending_wwr.len() <= max_a && self.pending_wwr_b.len() <= max_b {
            return Ok(());
        }
        let deadline = Instant::now() + OTA_WRITE_TIMEOUT;
        while self.pending_wwr.len() > max_a || self.pending_wwr_b.len() > max_b {
            let mut progressed = false;
            for (pending, label) in [
                (&mut self.pending_wwr, "Companion OTA data pipeline"),
                (&mut self.pending_wwr_b, "Companion OTA data_b pipeline"),
            ] {
                let mut index = 0usize;
                while index < pending.len() {
                    let operation = &pending[index];
                    match operation
                        .Status()
                        .map_err(|err| format!("BLE {label} async status failed: {err}"))?
                    {
                        windows::Foundation::AsyncStatus::Completed => {
                            let operation = pending.remove(index);
                            let status = operation
                                .GetResults()
                                .map_err(|err| format!("BLE {label} write result failed: {err}"))?;
                            let _ = operation.Close();
                            if status != GattCommunicationStatus::Success {
                                return Err(format!(
                                    "BLE {label} write returned status={status:?}"
                                ));
                            }
                            progressed = true;
                        }
                        windows::Foundation::AsyncStatus::Error => {
                            let code = operation.ErrorCode().ok();
                            let _ = operation.Close();
                            pending.remove(index);
                            return Err(format!("BLE {label} write async error: {code:?}"));
                        }
                        windows::Foundation::AsyncStatus::Canceled => {
                            let _ = operation.Close();
                            pending.remove(index);
                            return Err(format!("BLE {label} write async canceled"));
                        }
                        windows::Foundation::AsyncStatus::Started => {
                            index += 1;
                        }
                        status => {
                            let _ = operation.Close();
                            pending.remove(index);
                            return Err(format!("BLE {label} unknown async status={status:?}"));
                        }
                    }
                }
            }
            if self.pending_wwr.len() <= max_a && self.pending_wwr_b.len() <= max_b {
                break;
            }
            if Instant::now() >= deadline {
                self.cancel_pending_wwr();
                return Err(format!(
                    "OTA transfer progress stalled for {} ms while draining the BLE data pipeline",
                    OTA_WRITE_TIMEOUT.as_millis()
                ));
            }
            if !progressed {
                std::thread::sleep(Duration::from_millis(ASYNC_POLL_INTERVAL_MS));
            }
        }
        Ok(())
    }

    fn enqueue_wwr_data_write(&mut self, packet: &[u8], lane_b: bool) -> Result<(), String> {
        let dual = self.target.data_b.is_some();
        let depth_per_lane = if dual {
            (WWR_PIPELINE_DEPTH + 1) / 2
        } else {
            WWR_PIPELINE_DEPTH
        };

        if lane_b {
            let characteristic = self.target.data_b.as_ref().ok_or_else(|| {
                "Companion OTA data_b lane requested but characteristic missing".to_string()
            })?;
            let operation = start_gatt_write_with_option_async(
                characteristic,
                packet,
                GattWriteOption::WriteWithoutResponse,
                "Companion OTA data_b",
            )?;
            self.pending_wwr_b.push(operation);
        } else {
            let operation = start_gatt_write_with_option_async(
                &self.target.data,
                packet,
                GattWriteOption::WriteWithoutResponse,
                "Companion OTA data",
            )?;
            self.pending_wwr.push(operation);
        }

        let max_a = depth_per_lane.saturating_sub(1);
        let max_b = if dual {
            depth_per_lane.saturating_sub(1)
        } else {
            0
        };
        let total = self.pending_wwr.len() + self.pending_wwr_b.len();
        if self.pending_wwr.len() > max_a
            || self.pending_wwr_b.len() > max_b
            || total >= WWR_PIPELINE_DEPTH
        {
            self.drain_pending_wwr_until(max_a, max_b)?;
        }
        Ok(())
    }
}

impl denzic_ota_core::OtaV1Transport for CompanionOtaWinrtTransport<'_> {
    fn write_control(
        &mut self,
        packet: &[u8; denzic_ota_core::CONTROL_BYTES],
    ) -> Result<(), String> {
        if packet[4] == denzic_ota_core::OP_ABORT {
            self.cancel_pending_wwr();
            return write_gatt_value_with_timeout(
                &self.target.control,
                packet,
                GattWriteOption::WriteWithResponse,
                OTA_ABORT_WRITE_TIMEOUT,
                "Companion OTA abort",
            )
            .map(|_| ());
        }
        self.flush_pending_wwr()?;
        let is_sync = packet[4] == denzic_ota_core::OP_SYNC;
        let is_begin = packet[4] == denzic_ota_core::OP_BEGIN;
        // WB flash lags host WWR completion. A short settle after drain cuts
        // ERROR_OFFSET_MISMATCH recoveries (window-halving thrash) more than it
        // costs in wall time — measured thrash was the bulk gate killer.
        if is_sync {
            std::thread::sleep(Duration::from_millis(25));
        }
        let label = match packet[4] {
            denzic_ota_core::OP_BEGIN => "Companion OTA begin",
            denzic_ota_core::OP_SYNC => "Companion OTA sync",
            denzic_ota_core::OP_ABORT => "Companion OTA abort",
            _ => "Companion OTA control",
        };
        // SYNC: status-style write (Listener); BEGIN/FINISH: full write-result path.
        let write_timeout = if is_sync {
            OTA_SYNC_WRITE_TIMEOUT
        } else {
            OTA_WRITE_TIMEOUT
        };
        let retries = if is_begin { 5 } else { 3 };
        let delay_ms = if is_begin {
            800
        } else if is_sync {
            200
        } else {
            400
        };
        for attempt in 0..=retries {
            let result = if is_sync {
                write_gatt_value_status_with_timeout(
                    &self.target.control,
                    packet,
                    GattWriteOption::WriteWithResponse,
                    write_timeout,
                    label,
                )
            } else {
                write_gatt_value_with_timeout(
                    &self.target.control,
                    packet,
                    GattWriteOption::WriteWithResponse,
                    write_timeout,
                    label,
                )
            };
            match result {
                Ok(_) => return Ok(()),
                Err(err) if attempt < retries => {
                    let lower = err.to_ascii_lowercase();
                    let retryable = lower.contains("timeout")
                        || lower.contains("timed out")
                        || lower.contains("authentication")
                        || lower.contains("protocol_error")
                        || lower.contains("cancel");
                    if !retryable {
                        return Err(err);
                    }
                    let _ = self.flush_pending_wwr();
                    std::thread::sleep(Duration::from_millis(delay_ms));
                }
                Err(err) => return Err(err),
            }
        }
        Err("Companion OTA control write failed after retries".to_string())
    }

    fn dual_lane_available(&self) -> bool {
        self.target.data_b.is_some()
    }

    fn write_data(&mut self, packet: &[u8]) -> Result<(), String> {
        if self.target.data_write_option == GattWriteOption::WriteWithoutResponse {
            match self.enqueue_wwr_data_write(packet, false) {
                Ok(()) => return Ok(()),
                Err(e) => {
                    if e.contains("stalled") {
                        return Err(e);
                    }
                    let _ = self.flush_pending_wwr();
                }
            }
        } else {
            self.flush_pending_wwr()?;
        }
        write_gatt_value_with_timeout(
            &self.target.data,
            packet,
            self.target.data_write_option,
            OTA_WRITE_TIMEOUT,
            "Companion OTA data",
        )
        .map(|_| ())
    }

    fn write_data_b(&mut self, packet: &[u8]) -> Result<(), String> {
        if self.target.data_write_option == GattWriteOption::WriteWithoutResponse {
            match self.enqueue_wwr_data_write(packet, true) {
                Ok(()) => return Ok(()),
                Err(e) => {
                    if e.contains("stalled") {
                        return Err(e);
                    }
                    let _ = self.flush_pending_wwr();
                }
            }
        } else {
            self.flush_pending_wwr()?;
        }
        let ch = self
            .target
            .data_b
            .as_ref()
            .ok_or_else(|| "Companion OTA data_b missing".to_string())?;
        write_gatt_value_with_timeout(
            ch,
            packet,
            self.target.data_write_option,
            OTA_WRITE_TIMEOUT,
            "Companion OTA data_b",
        )
        .map(|_| ())
    }

    fn read_status(&mut self) -> Result<Vec<u8>, String> {
        let timeout = self
            .status_error_started
            .map(|started| {
                PROGRESS_TIMEOUT
                    .saturating_sub(started.elapsed())
                    .min(STATUS_READ_TIMEOUT)
            })
            .unwrap_or(STATUS_READ_TIMEOUT);
        if timeout.is_zero() {
            return Err(format!(
                "OTA status progress stalled for {} ms",
                PROGRESS_TIMEOUT.as_millis()
            ));
        }
        let cancel = BleCancel::NONE;
        let result = self.flush_pending_wwr().and_then(|_| {
            read_characteristic_bytes_with_timeout(
                &self.target.status,
                BluetoothCacheMode::Uncached,
                "Companion OTA status",
                timeout,
                &cancel,
            )
        });
        match result {
            Ok(bytes) => {
                self.status_error_started = None;
                Ok(bytes)
            }
            Err(error) => {
                let started = *self.status_error_started.get_or_insert_with(Instant::now);
                if started.elapsed() >= PROGRESS_TIMEOUT {
                    Err(format!(
                        "OTA status progress stalled for {} ms: {error}",
                        PROGRESS_TIMEOUT.as_millis()
                    ))
                } else {
                    Err(error)
                }
            }
        }
    }

    fn status_retry_wait(&mut self, _attempt: u8) {
        std::thread::sleep(STATUS_POLL_INTERVAL);
    }

    fn write_finish(
        &mut self,
        packet: &[u8; denzic_ota_core::CONTROL_BYTES],
    ) -> Result<(), String> {
        self.flush_pending_wwr()?;
        for attempt in 0..5 {
            match write_gatt_value_with_timeout(
                &self.target.control,
                packet,
                GattWriteOption::WriteWithResponse,
                OTA_FINISH_WRITE_TIMEOUT,
                "Companion OTA finish",
            ) {
                Ok(_) => return Ok(()),
                Err(err) => {
                    let lower = err.to_ascii_lowercase();
                    // Device may reboot on FINISH before ATT completes.
                    if !self.wba_signed && (lower.contains("disconnect")
                        || lower.contains("not connected")
                        || lower.contains("removed")
                        || lower.contains("object closed"))
                    {
                        return Ok(());
                    }
                    if attempt + 1 >= 5 {
                        return Err(err);
                    }
                    std::thread::sleep(Duration::from_millis(500));
                }
            }
        }
        Ok(())
    }
}

fn parse_ble_address(s: &str) -> Result<u64, String> {
    let hex: String = s
        .chars()
        .filter(|c| c.is_ascii_hexdigit())
        .collect::<String>()
        .to_ascii_lowercase();
    if hex.len() != 12 {
        return Err(format!("invalid BLE address: {s}"));
    }
    u64::from_str_radix(&hex, 16).map_err(|e| format!("invalid BLE address {s}: {e}"))
}

fn format_ble_address(addr: u64) -> String {
    format!(
        "{:02X}:{:02X}:{:02X}:{:02X}:{:02X}:{:02X}",
        (addr >> 40) & 0xff,
        (addr >> 32) & 0xff,
        (addr >> 24) & 0xff,
        (addr >> 16) & 0xff,
        (addr >> 8) & 0xff,
        addr & 0xff
    )
}

fn looks_like_uuid_crumb(address_label: &str) -> bool {
    // OTA service UUID ends with ...adfa64983b06 — never treat that as a MAC.
    let hex: String = address_label
        .chars()
        .filter(|c| c.is_ascii_hexdigit())
        .collect::<String>()
        .to_ascii_lowercase();
    hex == "adfa64983b06" || hex == "1b55f597f09c" || hex.ends_with("adfa64983b06")
}

fn parse_bluetooth_address_from_device_id(id: &str) -> Option<u64> {
    // Prefer colon-form MACs (…#BluetoothLE#00:80:e1:…) over bare 12-hex crumbs
    // that are often UUID fragments (…adfa64983b06…).
    let mut bare: Vec<u64> = Vec::new();
    for part in id.split(&['#', '_'][..]) {
        if part.contains(':') {
            // May be "00:80:E1:27:B8:EC" or longer with noise — try sliding windows.
            let chars: Vec<char> = part.chars().collect();
            if chars.len() >= 17 {
                for start in 0..=chars.len().saturating_sub(17) {
                    let slice: String = chars[start..start + 17].iter().collect();
                    if slice.chars().filter(|c| *c == ':').count() == 5 {
                        if let Ok(a) = parse_ble_address(&slice) {
                            if !looks_like_uuid_crumb(&slice) {
                                return Some(a);
                            }
                        }
                    }
                }
            }
            if let Ok(a) = parse_ble_address(part) {
                if !looks_like_uuid_crumb(part) {
                    return Some(a);
                }
            }
        }
        let hex: String = part.chars().filter(|c| c.is_ascii_hexdigit()).collect();
        if hex.len() == 12 {
            if let Ok(a) = u64::from_str_radix(&hex, 16) {
                let label = format_ble_address(a);
                if !looks_like_uuid_crumb(&label) {
                    bare.push(a);
                }
            }
        }
        // Compact address after UUID: "...3b06_0080e127b8ec"
        if hex.len() > 12 {
            if let Ok(a) = u64::from_str_radix(&hex[hex.len() - 12..], 16) {
                let label = format_ble_address(a);
                if !looks_like_uuid_crumb(&label) {
                    bare.push(a);
                }
            }
        }
    }
    bare.into_iter().next()
}
