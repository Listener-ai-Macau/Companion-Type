//! Companion BLE bridge boundary.
//!
//! The Windows app owns a native BLE path here. Firmware Python tools remain
//! validation inventory, but app scan/connect/sync can use the OS BLE stack
//! directly through btleplug's Windows backend.

use std::fs::{create_dir_all, File};
use std::io::{Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::time::{Duration as StdDuration, SystemTime, UNIX_EPOCH};

use btleplug::api::{
    Central, CharPropFlags, Characteristic, Manager as _, Peripheral as _, ScanFilter, WriteType,
};
use btleplug::platform::{Manager, Peripheral};
use futures::StreamExt;
use serde::Serialize;
use sha2::{Digest, Sha256};
use tokio::time::{sleep, timeout};
use uuid::Uuid;

const COMPANION_DEVICE_NAME_FILTER: &str = "companion";
const RECORDING_SERVICE_UUID: Uuid = Uuid::from_u128(0x8f7a00037b7d4f3d9d6f6c2d1b7c0000);
const COMPANION_OTA_V1_SERVICE_UUID: Uuid = Uuid::from_u128(0x8f7a80077b7d4f3d9d6f6c2d1b7c0000);
const COMPANION_OTA_V1_CONTROL_UUID: Uuid = Uuid::from_u128(0x8f7a80027b7d4f3d9d6f6c2d1b7c0000);
const COMPANION_OTA_V1_DATA_UUID: Uuid = Uuid::from_u128(0x8f7a80047b7d4f3d9d6f6c2d1b7c0000);
const COMPANION_OTA_V1_STATUS_UUID: Uuid = Uuid::from_u128(0x8f7a80057b7d4f3d9d6f6c2d1b7c0000);
const RECORDING_LIST_UUID: Uuid = Uuid::from_u128(0x8f7a30027b7d4f3d9d6f6c2d1b7c0000);
const RECORDING_CHUNK_PULL_UUID: Uuid = Uuid::from_u128(0x8f7a30037b7d4f3d9d6f6c2d1b7c0000);
const RECORDING_CHUNK_FINAL_FLAG: u8 = 0x01;
const RECORDING_CHUNK_ERROR_FLAG: u8 = 0x80;
const RECORDING_LIST_ENTRY_BYTES: usize = 32;
const RECORDING_CHUNK_HEADER_BYTES: usize = 56;
const RECORDING_CODEC_PCM16_MONO: u8 = 1;
const RECORDING_SOURCE_MIC_SAI: u8 = 1;
const PCM_SAMPLE_RATE_HZ: u32 = 16_000;
const PCM_CHANNELS: u16 = 1;
const PCM_BITS_PER_SAMPLE: u16 = 16;

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionBleBridgeStatus {
    pub provider_id: String,
    pub mode: String,
    pub ready: bool,
    pub native_ready: bool,
    pub native_provider_id: String,
    pub firmware_repo: String,
    pub helpers: Vec<CompanionBleHelperStatus>,
    pub message: String,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionBleHelperStatus {
    pub name: String,
    pub path: String,
    pub exists: bool,
}

#[derive(Clone, Debug)]
pub struct CompanionBleOperation {
    pub provider_id: String,
    pub mode: String,
    pub ready: bool,
    pub device_id: Option<String>,
    pub recording_path: Option<String>,
    pub message: String,
}

#[derive(Debug)]
pub(crate) struct CompanionOtaBleReport {
    pub device_id: String,
    pub transfer: denzic_ota_core::TransferReport,
}

pub struct CompanionBleBridge {
    firmware_repo: PathBuf,
}

impl CompanionBleBridge {
    pub fn detect_default() -> Self {
        let firmware_repo = std::env::var("COMPANION_TYPE_FIRMWARE_REPO")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                    .join("..")
                    .join("..")
                    .join("..")
                    .join("Companion-Firmware")
            });
        Self { firmware_repo }
    }

    pub fn status(&self) -> CompanionBleBridgeStatus {
        let native_ready = native_ble_available();
        let helpers = [
            ("ble-real-bench", "tools/companion_ble_real_bench.py"),
            (
                "flash-recording-chain",
                "tools/companion_flash_recording_chain.py",
            ),
            (
                "button-recording-chain",
                "tools/companion_button_recording_chain.py",
            ),
        ]
        .into_iter()
        .map(|(name, relative)| {
            let path = self.firmware_repo.join(relative);
            CompanionBleHelperStatus {
                name: name.to_string(),
                path: path.to_string_lossy().to_string(),
                exists: path.exists(),
            }
        })
        .collect::<Vec<_>>();
        let helper_ready = helpers.iter().any(|helper| helper.exists);
        let ready = native_ready || helper_ready;
        let message = if native_ready {
            "Companion native Windows BLE provider is available; helper tools remain validation inventory."
        } else if helper_ready {
            "Companion BLE helper tools are available; native Windows BLE provider is disabled or unsupported on this host."
        } else {
            "Companion BLE boundary not ready; enable Windows BLE or set COMPANION_TYPE_FIRMWARE_REPO for validation helpers."
        };

        CompanionBleBridgeStatus {
            provider_id: "companion-type-ble-boundary".to_string(),
            mode: if native_ready {
                "windows-native-ready".to_string()
            } else if ready {
                "tool-validation-ready".to_string()
            } else {
                "ble-unavailable".to_string()
            },
            ready,
            native_ready,
            native_provider_id: "companion-type-windows-ble".to_string(),
            firmware_repo: self.firmware_repo.to_string_lossy().to_string(),
            helpers,
            message: message.to_string(),
        }
    }

    pub fn scan(&self) -> CompanionBleOperation {
        if let Some(operation) =
            env_native_operation("Companion device discovered from configured environment")
        {
            return operation;
        }
        if native_ble_available() {
            return match run_native_blocking(scan_native_device(None)) {
                Ok(device) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-scan".to_string(),
                    ready: true,
                    device_id: Some(device.device_id()),
                    recording_path: None,
                    message: format!(
                        "Companion device discovered via native BLE: name={} address={} rssi={:?}",
                        device.name, device.address, device.rssi
                    ),
                },
                Err(err) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-scan".to_string(),
                    ready: false,
                    device_id: None,
                    recording_path: None,
                    message: format!("Native BLE scan did not find Companion: {err}"),
                },
            };
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; scan requires Windows BLE or validation helper inventory.",
        )
    }

    pub fn connect(&self, requested_device_id: Option<&str>) -> CompanionBleOperation {
        if let Some(mut operation) =
            env_native_operation("Companion device connected from configured environment")
        {
            operation.device_id = Some(
                requested_device_id
                    .map(str::to_string)
                    .or_else(|| operation.device_id.clone())
                    .unwrap_or_else(|| "companion-nucleo-wb55rg".to_string()),
            );
            return operation;
        }
        if native_ble_available() {
            return match run_native_blocking(connect_native_probe(requested_device_id)) {
                Ok(probe) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-connect".to_string(),
                    ready: true,
                    device_id: Some(probe.device_id),
                    recording_path: None,
                    message: format!(
                        "Native BLE connect/discover passed: services={} characteristics={} recordings={}",
                        probe.service_count, probe.characteristic_count, probe.recordings_available
                    ),
                },
                Err(err) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-connect".to_string(),
                    ready: false,
                    device_id: requested_device_id.map(str::to_string),
                    recording_path: None,
                    message: format!("Native BLE connect failed: {err}"),
                },
            };
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; connect requires Windows BLE or validation helper inventory.",
        )
    }

    pub fn sync_recordings(&self) -> CompanionBleOperation {
        if let Ok(path) = std::env::var("COMPANION_TYPE_DEVICE_RECORDING_PATH") {
            let mut operation = self.connect(None);
            operation.recording_path = Some(path);
            operation.message = "Device recording path imported into Companion-Type".to_string();
            return operation;
        }
        if let Some(mut operation) =
            env_native_operation("Device sync completed from configured environment")
        {
            operation.message =
                "Device sync completed with no configured recording path in mock/native env mode"
                    .to_string();
            return operation;
        }
        if native_ble_available() {
            return match run_native_blocking(sync_first_native_recording(None)) {
                Ok(sync) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-recording-pull".to_string(),
                    ready: true,
                    device_id: Some(sync.device_id),
                    recording_path: sync.recording_path.clone(),
                    message: match &sync.recording_path {
                        Some(path) => format!(
                            "Native BLE pulled recording_id={} duration_ms={} bytes={} sha256={} -> {}",
                            sync.recording_id.unwrap_or_default(),
                            sync.duration_ms.unwrap_or_default(),
                            sync.total_length.unwrap_or_default(),
                            sync.sha256.clone().unwrap_or_default(),
                            path
                        ),
                        None => "Native BLE sync found no stored recordings on device".to_string(),
                    },
                },
                Err(err) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-recording-pull".to_string(),
                    ready: false,
                    device_id: None,
                    recording_path: None,
                    message: format!("Native BLE recording sync failed: {err}"),
                },
            };
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; recording sync requires Windows BLE or COMPANION_TYPE_DEVICE_RECORDING_PATH.",
        )
    }

    pub(crate) fn transfer_firmware_ota(
        &self,
        requested_device_id: Option<&str>,
        firmware: &[u8],
        chunk_bytes: u16,
    ) -> Result<CompanionOtaBleReport, String> {
        if !native_ble_available() {
            return Err("Companion OTA requires the native Windows BLE provider".to_string());
        }
        transfer_native_firmware_ota(requested_device_id, firmware, chunk_bytes)
    }
}

fn helper_operation(status: &CompanionBleBridgeStatus, message: &str) -> CompanionBleOperation {
    CompanionBleOperation {
        provider_id: status.native_provider_id.clone(),
        mode: status.mode.clone(),
        ready: false,
        device_id: None,
        recording_path: None,
        message: message.to_string(),
    }
}

fn env_native_operation(message: &str) -> Option<CompanionBleOperation> {
    let forced_ready = std::env::var("COMPANION_TYPE_BLE_NATIVE_READY")
        .map(|value| truthy(&value))
        .unwrap_or(false);
    let device_id = std::env::var("COMPANION_TYPE_BLE_DEVICE_ID").ok();
    if forced_ready || device_id.is_some() {
        return Some(CompanionBleOperation {
            provider_id: "companion-type-windows-ble".to_string(),
            mode: "windows-native-env".to_string(),
            ready: true,
            device_id: Some(device_id.unwrap_or_else(|| "companion-nucleo-wb55rg".to_string())),
            recording_path: None,
            message: message.to_string(),
        });
    }
    None
}

fn native_ble_available() -> bool {
    if std::env::var("COMPANION_TYPE_BLE_NATIVE_DISABLED")
        .map(|value| truthy(&value))
        .unwrap_or(false)
    {
        return false;
    }
    cfg!(windows)
        || std::env::var("COMPANION_TYPE_BLE_NATIVE_READY")
            .map(|value| truthy(&value))
            .unwrap_or(false)
}

fn truthy(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "1" | "true" | "yes" | "on"
    )
}

fn run_native_blocking<T>(
    future: impl std::future::Future<Output = Result<T, String>>,
) -> Result<T, String> {
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|err| format!("build native BLE runtime: {err}"))?
        .block_on(future)
}

fn env_timeout(name: &str, default_ms: u64) -> StdDuration {
    StdDuration::from_millis(
        std::env::var(name)
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(default_ms),
    )
}

struct CompanionOtaV1Transport {
    runtime: tokio::runtime::Runtime,
    peripheral: Peripheral,
    control: Characteristic,
    data: Characteristic,
    status: Characteristic,
    data_write_type: WriteType,
}

impl CompanionOtaV1Transport {
    fn write(
        &self,
        characteristic: Characteristic,
        bytes: Vec<u8>,
        write_type: WriteType,
        label: &str,
    ) -> Result<(), String> {
        let peripheral = self.peripheral.clone();
        let write_timeout = env_timeout("COMPANION_TYPE_OTA_WRITE_TIMEOUT_MS", 8_000);
        self.runtime.block_on(async move {
            timeout(
                write_timeout,
                peripheral.write(&characteristic, &bytes, write_type),
            )
            .await
            .map_err(|_| format!("{label} timed out after {}ms", write_timeout.as_millis()))?
            .map_err(|err| format!("{label}: {err}"))
        })
    }

    fn disconnected_after_finish(&self) -> bool {
        std::thread::sleep(StdDuration::from_millis(450));
        let peripheral = self.peripheral.clone();
        self.runtime
            .block_on(async move {
                timeout(StdDuration::from_secs(2), peripheral.is_connected())
                    .await
                    .ok()
                    .and_then(Result::ok)
            })
            .is_some_and(|connected| !connected)
    }
}

impl denzic_ota_core::OtaV1Transport for CompanionOtaV1Transport {
    fn write_control(
        &mut self,
        packet: &[u8; denzic_ota_core::CONTROL_BYTES],
    ) -> Result<(), String> {
        self.write(
            self.control.clone(),
            packet.to_vec(),
            WriteType::WithResponse,
            "Denzic OTA v1 control write",
        )
    }

    fn write_data(&mut self, packet: &[u8]) -> Result<(), String> {
        self.write(
            self.data.clone(),
            packet.to_vec(),
            self.data_write_type,
            "Denzic OTA v1 data write",
        )
    }

    fn read_status(&mut self) -> Result<Vec<u8>, String> {
        let peripheral = self.peripheral.clone();
        let status = self.status.clone();
        let read_timeout = env_timeout("COMPANION_TYPE_OTA_STATUS_TIMEOUT_MS", 8_000);
        self.runtime.block_on(async move {
            timeout(read_timeout, peripheral.read(&status))
                .await
                .map_err(|_| {
                    format!(
                        "Denzic OTA v1 status read timed out after {}ms",
                        read_timeout.as_millis()
                    )
                })?
                .map_err(|err| format!("Denzic OTA v1 status read: {err}"))
        })
    }

    fn status_retry_wait(&mut self, _attempt: u8) {
        std::thread::sleep(StdDuration::from_millis(150));
    }

    fn write_finish(
        &mut self,
        packet: &[u8; denzic_ota_core::CONTROL_BYTES],
    ) -> Result<(), String> {
        match self.write(
            self.control.clone(),
            packet.to_vec(),
            WriteType::WithResponse,
            "Denzic OTA v1 finish write",
        ) {
            Ok(()) => Ok(()),
            Err(_) if self.disconnected_after_finish() => Ok(()),
            Err(error) => Err(error),
        }
    }
}

fn transfer_native_firmware_ota(
    requested_device_id: Option<&str>,
    firmware: &[u8],
    chunk_bytes: u16,
) -> Result<CompanionOtaBleReport, String> {
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|err| format!("build Companion OTA BLE runtime: {err}"))?;
    let device = runtime.block_on(connect_native_device(requested_device_id))?;
    let device_id = device.device_id();
    let characteristics = device.peripheral.characteristics();
    let control = find_ota_characteristic(
        &characteristics,
        COMPANION_OTA_V1_CONTROL_UUID,
        CharPropFlags::WRITE,
    )?;
    let data = find_ota_data_characteristic(&characteristics)?;
    let status = find_ota_characteristic(
        &characteristics,
        COMPANION_OTA_V1_STATUS_UUID,
        CharPropFlags::READ,
    )?;
    let data_write_type = if data
        .properties
        .contains(CharPropFlags::WRITE_WITHOUT_RESPONSE)
    {
        WriteType::WithoutResponse
    } else {
        WriteType::WithResponse
    };
    let peripheral = device.peripheral.clone();
    let mut transport = CompanionOtaV1Transport {
        runtime,
        peripheral: device.peripheral,
        control,
        data,
        status,
        data_write_type,
    };
    let result = denzic_ota_core::transfer(
        &mut transport,
        firmware,
        denzic_ota_core::TransferOptions {
            chunk_payload_bytes: chunk_bytes,
            window_chunks: 8,
            status_read_attempts: 5,
            max_stalled_windows: 3,
            inactive_link_window_chunks: Some(4),
        },
        |_, _| {},
    );
    let disconnect_timeout = env_timeout("COMPANION_TYPE_BLE_DISCONNECT_TIMEOUT_MS", 3_000);
    let _ = transport
        .runtime
        .block_on(async move { timeout(disconnect_timeout, peripheral.disconnect()).await });
    result.map(|transfer| CompanionOtaBleReport {
        device_id,
        transfer,
    })
}

fn find_ota_characteristic(
    characteristics: &std::collections::BTreeSet<Characteristic>,
    uuid: Uuid,
    required_property: CharPropFlags,
) -> Result<Characteristic, String> {
    let characteristic = characteristics
        .iter()
        .find(|characteristic| {
            characteristic.uuid == uuid
                && characteristic.service_uuid == COMPANION_OTA_V1_SERVICE_UUID
        })
        .cloned()
        .ok_or_else(|| {
            format!(
                "missing Companion OTA characteristic {uuid} in service {COMPANION_OTA_V1_SERVICE_UUID}"
            )
        })?;
    if !characteristic.properties.contains(required_property) {
        return Err(format!(
            "Companion OTA characteristic {uuid} lacks required property {required_property:?}"
        ));
    }
    Ok(characteristic)
}

fn find_ota_data_characteristic(
    characteristics: &std::collections::BTreeSet<Characteristic>,
) -> Result<Characteristic, String> {
    let characteristic = characteristics
        .iter()
        .find(|characteristic| {
            characteristic.uuid == COMPANION_OTA_V1_DATA_UUID
                && characteristic.service_uuid == COMPANION_OTA_V1_SERVICE_UUID
        })
        .cloned()
        .ok_or_else(|| {
            format!("missing Companion OTA data characteristic {COMPANION_OTA_V1_DATA_UUID}")
        })?;
    if !characteristic.properties.contains(CharPropFlags::WRITE)
        && !characteristic
            .properties
            .contains(CharPropFlags::WRITE_WITHOUT_RESPONSE)
    {
        return Err("Companion OTA data characteristic is not writable".to_string());
    }
    Ok(characteristic)
}

#[derive(Clone)]
struct NativeDevice {
    peripheral: Peripheral,
    name: String,
    address: String,
    rssi: Option<i16>,
    service_uuids: Vec<Uuid>,
}

impl NativeDevice {
    fn device_id(&self) -> String {
        if !self.address.is_empty() {
            self.address.clone()
        } else {
            self.name.clone()
        }
    }
}

struct NativeConnectProbe {
    device_id: String,
    service_count: usize,
    characteristic_count: usize,
    recordings_available: usize,
}

struct NativeRecordingSync {
    device_id: String,
    recording_id: Option<u32>,
    duration_ms: Option<u32>,
    total_length: Option<u32>,
    sha256: Option<String>,
    recording_path: Option<String>,
}

#[derive(Clone, Debug)]
struct RecordingEntry {
    recording_id: u32,
    duration_ms: u32,
    codec: u8,
    source_mode: u8,
    total_length: u32,
    sha256_prefix: [u8; 8],
    content_crc32: u32,
}

#[derive(Clone, Debug)]
struct RecordingChunk {
    flags: u8,
    payload_length: u16,
    recording_id: u32,
    packet_sequence: u32,
    byte_offset: u32,
    total_length: u32,
    packet_crc32: u32,
    final_sha256: [u8; 32],
    payload: Vec<u8>,
}

async fn scan_native_device(requested_device_id: Option<&str>) -> Result<NativeDevice, String> {
    let timeout_ms = std::env::var("COMPANION_TYPE_BLE_SCAN_TIMEOUT_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(4_000);
    let manager = Manager::new()
        .await
        .map_err(|err| format!("open BLE manager: {err}"))?;
    let adapters = manager
        .adapters()
        .await
        .map_err(|err| format!("enumerate BLE adapters: {err}"))?;
    if adapters.is_empty() {
        return Err("no Bluetooth adapters reported by Windows".to_string());
    }

    for adapter in &adapters {
        adapter
            .start_scan(ScanFilter {
                services: Vec::new(),
            })
            .await
            .map_err(|err| format!("start BLE scan: {err}"))?;
    }
    sleep(StdDuration::from_millis(timeout_ms)).await;

    let mut best: Option<(i32, NativeDevice)> = None;
    for adapter in &adapters {
        let peripherals = adapter
            .peripherals()
            .await
            .map_err(|err| format!("read BLE peripherals: {err}"))?;
        for peripheral in peripherals {
            let Some(props) = peripheral
                .properties()
                .await
                .map_err(|err| format!("read peripheral properties: {err}"))?
            else {
                continue;
            };
            let name = props.local_name.unwrap_or_default();
            let address = props.address.to_string();
            let device = NativeDevice {
                peripheral: peripheral.clone(),
                name,
                address,
                rssi: props.rssi,
                service_uuids: props.services,
            };
            let Some(score) = companion_candidate_score(&device, requested_device_id) else {
                continue;
            };
            if best
                .as_ref()
                .map(|(current, _)| score > *current)
                .unwrap_or(true)
            {
                best = Some((score, device));
            }
        }
        let _ = adapter.stop_scan().await;
    }

    best.map(|(_, device)| device).ok_or_else(|| {
        format!(
            "no Companion candidate found with name containing '{COMPANION_DEVICE_NAME_FILTER}', recording service {RECORDING_SERVICE_UUID}, or OTA service {COMPANION_OTA_V1_SERVICE_UUID}"
        )
    })
}

fn companion_candidate_score(
    device: &NativeDevice,
    requested_device_id: Option<&str>,
) -> Option<i32> {
    let name = device.name.to_ascii_lowercase();
    let address = normalize_device_id(&device.address);
    let requested = requested_device_id
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_ascii_lowercase);
    let has_recording_service = device.service_uuids.contains(&RECORDING_SERVICE_UUID);
    let has_ota_service = device
        .service_uuids
        .contains(&COMPANION_OTA_V1_SERVICE_UUID);
    let name_match = name.contains(COMPANION_DEVICE_NAME_FILTER);
    let requested_match = requested.as_ref().map(|value| {
        normalize_device_id(value) == address
            || name.contains(value)
            || (value.contains(COMPANION_DEVICE_NAME_FILTER) && name_match)
    });

    if matches!(requested_match, Some(false)) {
        return None;
    }
    if requested_match == Some(true) || name_match || has_recording_service || has_ota_service {
        let rssi = i32::from(device.rssi.unwrap_or(-100));
        return Some(
            (if requested_match == Some(true) {
                100
            } else {
                0
            }) + (if has_recording_service { 40 } else { 0 })
                + (if has_ota_service { 40 } else { 0 })
                + (if name_match { 20 } else { 0 })
                + rssi,
        );
    }
    None
}

fn normalize_device_id(value: &str) -> String {
    value
        .chars()
        .filter(|ch| ch.is_ascii_hexdigit())
        .collect::<String>()
        .to_ascii_lowercase()
}

async fn connect_native_device(requested_device_id: Option<&str>) -> Result<NativeDevice, String> {
    let device = scan_native_device(requested_device_id).await?;
    let device_id = device.device_id();
    let connect_timeout = env_timeout("COMPANION_TYPE_BLE_CONNECT_TIMEOUT_MS", 12_000);
    let discover_timeout = env_timeout("COMPANION_TYPE_BLE_DISCOVER_TIMEOUT_MS", 8_000);
    let connected = timeout(connect_timeout, device.peripheral.is_connected())
        .await
        .map_err(|_| {
            format!(
                "read BLE connection state for {device_id} timed out after {}ms",
                connect_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("read BLE connection state: {err}"))?;
    if !connected {
        timeout(connect_timeout, device.peripheral.connect())
            .await
            .map_err(|_| {
                format!(
                    "connect BLE device {device_id} timed out after {}ms",
                    connect_timeout.as_millis()
                )
            })?
            .map_err(|err| format!("connect BLE device {device_id}: {err}"))?;
    }
    timeout(discover_timeout, device.peripheral.discover_services())
        .await
        .map_err(|_| {
            format!(
                "discover GATT services for {device_id} timed out after {}ms",
                discover_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("discover GATT services: {err}"))?;
    Ok(device)
}

async fn connect_native_probe(
    requested_device_id: Option<&str>,
) -> Result<NativeConnectProbe, String> {
    let device = connect_native_device(requested_device_id).await?;
    let characteristics = device.peripheral.characteristics();
    let recordings_available = match read_recording_list(&device.peripheral, &characteristics).await
    {
        Ok(entries) => entries.len(),
        Err(_) => 0,
    };
    let probe = NativeConnectProbe {
        device_id: device.device_id(),
        service_count: device.service_uuids.len(),
        characteristic_count: characteristics.len(),
        recordings_available,
    };
    let _ = timeout(
        env_timeout("COMPANION_TYPE_BLE_DISCONNECT_TIMEOUT_MS", 3_000),
        device.peripheral.disconnect(),
    )
    .await;
    Ok(probe)
}

async fn sync_first_native_recording(
    requested_device_id: Option<&str>,
) -> Result<NativeRecordingSync, String> {
    let device = connect_native_device(requested_device_id).await?;
    let result = sync_first_native_recording_inner(&device).await;
    let _ = timeout(
        env_timeout("COMPANION_TYPE_BLE_DISCONNECT_TIMEOUT_MS", 3_000),
        device.peripheral.disconnect(),
    )
    .await;
    result
}

async fn sync_first_native_recording_inner(
    device: &NativeDevice,
) -> Result<NativeRecordingSync, String> {
    let characteristics = device.peripheral.characteristics();
    let entries = read_recording_list(&device.peripheral, &characteristics).await?;
    let Some(entry) = entries.first().cloned() else {
        return Ok(NativeRecordingSync {
            device_id: device.device_id(),
            recording_id: None,
            duration_ms: None,
            total_length: None,
            sha256: None,
            recording_path: None,
        });
    };
    if entry.codec != RECORDING_CODEC_PCM16_MONO {
        return Err(format!("unsupported recording codec: {}", entry.codec));
    }
    if entry.source_mode != RECORDING_SOURCE_MIC_SAI {
        return Err(format!(
            "recording source_mode={} is not the SAI microphone path",
            entry.source_mode
        ));
    }

    let pcm_bytes = pull_recording_bytes(&device.peripheral, &characteristics, &entry).await?;
    let sha256 = Sha256::digest(&pcm_bytes);
    let sha256_hex = hex_lower(&sha256);
    if sha256[..8] != entry.sha256_prefix {
        return Err(format!(
            "recording SHA prefix mismatch: list={} host={}",
            hex_lower(&entry.sha256_prefix),
            &sha256_hex[..16]
        ));
    }
    let crc32 = crc32fast::hash(&pcm_bytes);
    if crc32 != entry.content_crc32 {
        return Err(format!(
            "recording CRC32 mismatch: list=0x{:08x} host=0x{crc32:08x}",
            entry.content_crc32
        ));
    }

    let path = native_recording_output_path(entry.recording_id)?;
    write_pcm16_wav(&path, &pcm_bytes)?;
    Ok(NativeRecordingSync {
        device_id: device.device_id(),
        recording_id: Some(entry.recording_id),
        duration_ms: Some(entry.duration_ms),
        total_length: Some(entry.total_length),
        sha256: Some(sha256_hex),
        recording_path: Some(path.to_string_lossy().to_string()),
    })
}

async fn read_recording_list(
    peripheral: &Peripheral,
    characteristics: &std::collections::BTreeSet<Characteristic>,
) -> Result<Vec<RecordingEntry>, String> {
    let char_recording_list = find_characteristic(characteristics, RECORDING_LIST_UUID)?;
    if !char_recording_list.properties.contains(CharPropFlags::READ) {
        return Err("recording_list characteristic is not readable".to_string());
    }
    let read_timeout = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let payload = timeout(read_timeout, peripheral.read(&char_recording_list))
        .await
        .map_err(|_| {
            format!(
                "read recording_list timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("read recording_list: {err}"))?;
    parse_recording_list(&payload)
}

async fn pull_recording_bytes(
    peripheral: &Peripheral,
    characteristics: &std::collections::BTreeSet<Characteristic>,
    entry: &RecordingEntry,
) -> Result<Vec<u8>, String> {
    let char_chunk_pull = find_characteristic(characteristics, RECORDING_CHUNK_PULL_UUID)?;
    if !char_chunk_pull.properties.contains(CharPropFlags::WRITE)
        && !char_chunk_pull
            .properties
            .contains(CharPropFlags::WRITE_WITHOUT_RESPONSE)
    {
        return Err("recording_chunk_pull characteristic is not writable".to_string());
    }
    if !char_chunk_pull.properties.contains(CharPropFlags::NOTIFY) {
        return Err("recording_chunk_pull characteristic is not notifiable".to_string());
    }

    let read_timeout = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let write_timeout = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);
    let mut notifications = timeout(read_timeout, peripheral.notifications())
        .await
        .map_err(|_| {
            format!(
                "open BLE notification stream timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("open BLE notification stream: {err}"))?;
    timeout(read_timeout, peripheral.subscribe(&char_chunk_pull))
        .await
        .map_err(|_| {
            format!(
                "subscribe recording_chunk_pull timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("subscribe recording_chunk_pull: {err}"))?;

    let chunk_bytes = std::env::var("COMPANION_TYPE_BLE_CHUNK_BYTES")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(180);
    let notify_timeout = StdDuration::from_millis(
        std::env::var("COMPANION_TYPE_BLE_NOTIFY_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(15_000),
    );
    let mut offset = 0_u32;
    let mut expected_sequence = 0_u32;
    let mut data = Vec::<u8>::with_capacity(entry.total_length as usize);
    let mut final_sha256: Option<[u8; 32]> = None;

    while offset < entry.total_length {
        let remaining = entry.total_length - offset;
        let requested = recording_chunk_requested_length(chunk_bytes, remaining);
        let request = recording_chunk_pull_request(entry.recording_id, offset, requested);
        timeout(
            write_timeout,
            peripheral.write(&char_chunk_pull, &request, WriteType::WithResponse),
        )
        .await
        .map_err(|_| {
            format!(
                "write recording_chunk_pull offset={offset} timed out after {}ms",
                write_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("write recording_chunk_pull offset={offset}: {err}"))?;

        let chunk = timeout(notify_timeout, async {
            loop {
                let notification = notifications
                    .next()
                    .await
                    .ok_or_else(|| "recording notification stream ended".to_string())?;
                if notification.uuid != RECORDING_CHUNK_PULL_UUID {
                    continue;
                }
                let parsed = parse_recording_chunk(&notification.value)?;
                if parsed.byte_offset == offset {
                    return Ok::<RecordingChunk, String>(parsed);
                }
            }
        })
        .await
        .map_err(|_| format!("recording chunk notify timeout at offset={offset}"))??;

        if chunk.flags & RECORDING_CHUNK_ERROR_FLAG != 0 {
            return Err(format!(
                "recording chunk returned error at offset={offset}: device_error_code=0x{:08x} device_total_length={} packet_sequence={} payload_length={} chunk_offset={}",
                chunk.packet_crc32,
                chunk.total_length,
                chunk.packet_sequence,
                chunk.payload_length,
                chunk.byte_offset
            ));
        }
        if chunk.recording_id != entry.recording_id {
            return Err("recording chunk id changed during transfer".to_string());
        }
        if chunk.packet_sequence != expected_sequence {
            return Err(format!(
                "recording packet sequence mismatch: got {}, expected {}",
                chunk.packet_sequence, expected_sequence
            ));
        }
        if chunk.total_length != entry.total_length {
            return Err("recording total_length changed during transfer".to_string());
        }
        if chunk.payload_length as usize != chunk.payload.len() {
            return Err("recording chunk payload_length mismatch".to_string());
        }
        let packet_crc = recording_packet_crc32(&chunk);
        if packet_crc != chunk.packet_crc32 {
            return Err(format!(
                "recording packet CRC mismatch at offset={offset}: got 0x{packet_crc:08x}, expected 0x{:08x}",
                chunk.packet_crc32
            ));
        }

        offset += u32::from(chunk.payload_length);
        expected_sequence += 1;
        data.extend_from_slice(&chunk.payload);
        if chunk.flags & RECORDING_CHUNK_FINAL_FLAG != 0 {
            final_sha256 = Some(chunk.final_sha256);
            break;
        }
    }

    let _ = peripheral.unsubscribe(&char_chunk_pull).await;
    if data.len() != entry.total_length as usize {
        return Err(format!(
            "recording byte count mismatch: got {}, expected {}",
            data.len(),
            entry.total_length
        ));
    }
    let sha256 = Sha256::digest(&data);
    let final_sha256 =
        final_sha256.ok_or_else(|| "final recording chunk did not include SHA-256".to_string())?;
    if sha256[..] != final_sha256 {
        return Err(format!(
            "final SHA mismatch: device={} host={}",
            hex_lower(&final_sha256),
            hex_lower(&sha256)
        ));
    }
    Ok(data)
}

fn find_characteristic(
    characteristics: &std::collections::BTreeSet<Characteristic>,
    uuid: Uuid,
) -> Result<Characteristic, String> {
    characteristics
        .iter()
        .find(|characteristic| characteristic.uuid == uuid)
        .cloned()
        .ok_or_else(|| format!("missing GATT characteristic {uuid}"))
}

fn parse_recording_list(payload: &[u8]) -> Result<Vec<RecordingEntry>, String> {
    if payload.len() < 4 {
        return Err(format!("recording_list too short: {}", payload.len()));
    }
    if payload[0] != 1 {
        return Err(format!(
            "unexpected recording_list schema_version={}",
            payload[0]
        ));
    }
    let count = payload[1] as usize;
    let entry_bytes = le_u16(payload, 2)? as usize;
    if count == 0 {
        return Ok(Vec::new());
    }
    if entry_bytes < RECORDING_LIST_ENTRY_BYTES {
        return Err(format!(
            "recording_list entry_bytes={entry_bytes}, expected at least {RECORDING_LIST_ENTRY_BYTES}"
        ));
    }
    let mut entries = Vec::with_capacity(count);
    for index in 0..count {
        let base = 4 + index * entry_bytes;
        if payload.len() < base + RECORDING_LIST_ENTRY_BYTES {
            return Err(format!("recording_list entry {index} truncated"));
        }
        let mut sha256_prefix = [0_u8; 8];
        sha256_prefix.copy_from_slice(&payload[base + 20..base + 28]);
        entries.push(RecordingEntry {
            recording_id: le_u32(payload, base)?,
            duration_ms: le_u32(payload, base + 8)?,
            codec: payload[base + 12],
            source_mode: payload[base + 14],
            total_length: le_u32(payload, base + 16)?,
            sha256_prefix,
            content_crc32: le_u32(payload, base + 28)?,
        });
    }
    Ok(entries)
}

fn parse_recording_chunk(payload: &[u8]) -> Result<RecordingChunk, String> {
    if payload.len() < RECORDING_CHUNK_HEADER_BYTES {
        return Err(format!("recording chunk too short: {}", payload.len()));
    }
    if payload[0] != 1 {
        return Err(format!(
            "unexpected recording chunk schema_version={}",
            payload[0]
        ));
    }
    let payload_length = le_u16(payload, 2)?;
    let payload_end = RECORDING_CHUNK_HEADER_BYTES + payload_length as usize;
    if payload.len() < payload_end {
        return Err("recording chunk payload truncated".to_string());
    }
    let mut final_sha256 = [0_u8; 32];
    final_sha256.copy_from_slice(&payload[24..56]);
    Ok(RecordingChunk {
        flags: payload[1],
        payload_length,
        recording_id: le_u32(payload, 4)?,
        packet_sequence: le_u32(payload, 8)?,
        byte_offset: le_u32(payload, 12)?,
        total_length: le_u32(payload, 16)?,
        packet_crc32: le_u32(payload, 20)?,
        final_sha256,
        payload: payload[RECORDING_CHUNK_HEADER_BYTES..payload_end].to_vec(),
    })
}

fn recording_chunk_pull_request(recording_id: u32, offset: u32, requested_length: u16) -> [u8; 16] {
    let mut payload = [0_u8; 16];
    payload[0] = 1;
    payload[1] = 0;
    payload[2..4].copy_from_slice(&requested_length.to_le_bytes());
    payload[4..8].copy_from_slice(&recording_id.to_le_bytes());
    payload[8..12].copy_from_slice(&offset.to_le_bytes());
    payload[12..16].copy_from_slice(&0_u32.to_le_bytes());
    payload
}

fn recording_chunk_requested_length(chunk_bytes: u16, remaining: u32) -> u16 {
    if remaining == 0 {
        return 0;
    }
    if remaining > u32::from(chunk_bytes) {
        return chunk_bytes;
    }
    remaining as u16
}

fn recording_packet_crc32(chunk: &RecordingChunk) -> u32 {
    let mut hasher = crc32fast::Hasher::new();
    hasher.update(&chunk.recording_id.to_le_bytes());
    hasher.update(&chunk.packet_sequence.to_le_bytes());
    hasher.update(&chunk.byte_offset.to_le_bytes());
    hasher.update(&chunk.total_length.to_le_bytes());
    hasher.update(&chunk.payload);
    hasher.finalize()
}

fn native_recording_output_path(recording_id: u32) -> Result<PathBuf, String> {
    let root = std::env::var("COMPANION_TYPE_RECORDING_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::temp_dir()
                .join("companion-type")
                .join("recordings")
        });
    create_dir_all(&root).map_err(|err| format!("create recording dir {root:?}: {err}"))?;
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|err| format!("clock before epoch: {err}"))?
        .as_secs();
    Ok(root.join(format!("{stamp}-device-recording-{recording_id}.wav")))
}

fn write_pcm16_wav(path: &Path, pcm_bytes: &[u8]) -> Result<(), String> {
    if pcm_bytes.len() % 2 != 0 {
        return Err("PCM16 payload has odd byte length".to_string());
    }
    if let Some(parent) = path.parent() {
        create_dir_all(parent).map_err(|err| format!("create wav parent {parent:?}: {err}"))?;
    }
    let mut file = File::create(path).map_err(|err| format!("create wav {path:?}: {err}"))?;
    write_wav_header(&mut file, pcm_bytes.len() as u32)?;
    file.write_all(pcm_bytes)
        .map_err(|err| format!("write wav payload: {err}"))?;
    Ok(())
}

fn write_wav_header(file: &mut File, data_bytes: u32) -> Result<(), String> {
    let byte_rate = PCM_SAMPLE_RATE_HZ * PCM_CHANNELS as u32 * PCM_BITS_PER_SAMPLE as u32 / 8;
    let block_align = PCM_CHANNELS * PCM_BITS_PER_SAMPLE / 8;
    let riff_size = 36u32.saturating_add(data_bytes);

    file.seek(SeekFrom::Start(0))
        .map_err(|err| format!("seek wav header: {err}"))?;
    file.write_all(b"RIFF")
        .map_err(|err| format!("write riff: {err}"))?;
    file.write_all(&riff_size.to_le_bytes())
        .map_err(|err| format!("write riff size: {err}"))?;
    file.write_all(b"WAVEfmt ")
        .map_err(|err| format!("write wave fmt: {err}"))?;
    file.write_all(&16u32.to_le_bytes())
        .map_err(|err| format!("write fmt size: {err}"))?;
    file.write_all(&1u16.to_le_bytes())
        .map_err(|err| format!("write pcm tag: {err}"))?;
    file.write_all(&PCM_CHANNELS.to_le_bytes())
        .map_err(|err| format!("write channels: {err}"))?;
    file.write_all(&PCM_SAMPLE_RATE_HZ.to_le_bytes())
        .map_err(|err| format!("write sample rate: {err}"))?;
    file.write_all(&byte_rate.to_le_bytes())
        .map_err(|err| format!("write byte rate: {err}"))?;
    file.write_all(&block_align.to_le_bytes())
        .map_err(|err| format!("write block align: {err}"))?;
    file.write_all(&PCM_BITS_PER_SAMPLE.to_le_bytes())
        .map_err(|err| format!("write bits per sample: {err}"))?;
    file.write_all(b"data")
        .map_err(|err| format!("write data tag: {err}"))?;
    file.write_all(&data_bytes.to_le_bytes())
        .map_err(|err| format!("write data size: {err}"))?;
    Ok(())
}

fn le_u16(payload: &[u8], offset: usize) -> Result<u16, String> {
    let bytes = payload
        .get(offset..offset + 2)
        .ok_or_else(|| format!("u16 at {offset} out of range"))?;
    Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
}

fn le_u32(payload: &[u8], offset: usize) -> Result<u32, String> {
    let bytes = payload
        .get(offset..offset + 4)
        .ok_or_else(|| format!("u32 at {offset} out of range"))?;
    Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
}

fn hex_lower(bytes: &[u8]) -> String {
    bytes
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<Vec<_>>()
        .join("")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bridge_reports_helper_inventory() {
        let bridge = CompanionBleBridge::detect_default();
        let status = bridge.status();
        assert_eq!(status.provider_id, "companion-type-ble-boundary");
        assert_eq!(status.helpers.len(), 3);
        assert!(status
            .helpers
            .iter()
            .any(|helper| helper.name == "ble-real-bench"));
    }

    #[test]
    fn bridge_exposes_native_device_operations() {
        std::env::set_var("COMPANION_TYPE_BLE_NATIVE_READY", "1");
        std::env::set_var("COMPANION_TYPE_BLE_DEVICE_ID", "companion-test-device");
        let bridge = CompanionBleBridge::detect_default();
        let scan = bridge.scan();
        assert!(scan.ready);
        assert_eq!(scan.provider_id, "companion-type-windows-ble");
        assert_eq!(scan.device_id.as_deref(), Some("companion-test-device"));
        let connect = bridge.connect(Some("manual-device"));
        assert_eq!(connect.device_id.as_deref(), Some("manual-device"));
        std::env::remove_var("COMPANION_TYPE_BLE_NATIVE_READY");
        std::env::remove_var("COMPANION_TYPE_BLE_DEVICE_ID");
    }

    #[test]
    fn recording_list_parser_decodes_firmware_entry() {
        let mut payload = vec![1, 1, RECORDING_LIST_ENTRY_BYTES as u8, 0];
        payload.extend_from_slice(&7_u32.to_le_bytes());
        payload.extend_from_slice(&0_u32.to_le_bytes());
        payload.extend_from_slice(&780_u32.to_le_bytes());
        payload.push(1);
        payload.push(0);
        payload.push(1);
        payload.push(0);
        payload.extend_from_slice(&24_960_u32.to_le_bytes());
        payload.extend_from_slice(&[0x47, 0x5b, 0x81, 0xf3, 0x12, 0x5d, 0x09, 0x86]);
        payload.extend_from_slice(&0xdb92_9709_u32.to_le_bytes());

        let entries = parse_recording_list(&payload).unwrap();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].recording_id, 7);
        assert_eq!(entries[0].duration_ms, 780);
        assert_eq!(entries[0].codec, 1);
        assert_eq!(entries[0].source_mode, 1);
        assert_eq!(entries[0].total_length, 24_960);
        assert_eq!(hex_lower(&entries[0].sha256_prefix), "475b81f3125d0986");
        assert_eq!(entries[0].content_crc32, 0xdb92_9709);
    }

    #[test]
    fn recording_chunk_parser_and_crc_match_firmware_contract() {
        let payload_bytes = b"hello companion".to_vec();
        let mut chunk = RecordingChunk {
            flags: RECORDING_CHUNK_FINAL_FLAG,
            payload_length: payload_bytes.len() as u16,
            recording_id: 7,
            packet_sequence: 0,
            byte_offset: 0,
            total_length: payload_bytes.len() as u32,
            packet_crc32: 0,
            final_sha256: Sha256::digest(&payload_bytes).into(),
            payload: payload_bytes,
        };
        chunk.packet_crc32 = recording_packet_crc32(&chunk);

        let mut wire = Vec::new();
        wire.push(1);
        wire.push(chunk.flags);
        wire.extend_from_slice(&chunk.payload_length.to_le_bytes());
        wire.extend_from_slice(&chunk.recording_id.to_le_bytes());
        wire.extend_from_slice(&chunk.packet_sequence.to_le_bytes());
        wire.extend_from_slice(&chunk.byte_offset.to_le_bytes());
        wire.extend_from_slice(&chunk.total_length.to_le_bytes());
        wire.extend_from_slice(&chunk.packet_crc32.to_le_bytes());
        wire.extend_from_slice(&chunk.final_sha256);
        wire.extend_from_slice(&chunk.payload);

        let parsed = parse_recording_chunk(&wire).unwrap();
        assert_eq!(parsed.flags, RECORDING_CHUNK_FINAL_FLAG);
        assert_eq!(parsed.payload, b"hello companion");
        assert_eq!(recording_packet_crc32(&parsed), parsed.packet_crc32);
        assert_eq!(
            hex_lower(&parsed.final_sha256),
            hex_lower(&Sha256::digest(b"hello companion"))
        );
    }

    #[test]
    fn recording_chunk_request_length_does_not_truncate_64k_remaining() {
        assert_eq!(recording_chunk_requested_length(180, 65_536), 180);
        assert_eq!(recording_chunk_requested_length(180, 179), 179);
        assert_eq!(recording_chunk_requested_length(180, 0), 0);
    }

    #[test]
    fn native_recording_wav_writer_uses_pcm16_16k_mono() {
        let root = std::env::temp_dir().join("companion-type-native-ble-wav-test");
        let path = root.join("recording.wav");
        let _ = std::fs::remove_file(&path);
        write_pcm16_wav(&path, &[0, 0, 1, 0, 255, 255]).unwrap();
        let bytes = std::fs::read(&path).unwrap();
        assert_eq!(&bytes[0..4], b"RIFF");
        assert_eq!(&bytes[8..12], b"WAVE");
        assert_eq!(&bytes[36..40], b"data");
        assert_eq!(u16::from_le_bytes([bytes[22], bytes[23]]), 1);
        assert_eq!(
            u32::from_le_bytes([bytes[24], bytes[25], bytes[26], bytes[27]]),
            16_000
        );
        assert_eq!(
            u32::from_le_bytes([bytes[40], bytes[41], bytes[42], bytes[43]]),
            6
        );
    }

    #[test]
    fn real_native_ble_scan_connect_smoke() {
        if std::env::var("COMPANION_TYPE_REAL_BLE_ACCEPTANCE")
            .ok()
            .as_deref()
            != Some("1")
        {
            return;
        }

        std::env::remove_var("COMPANION_TYPE_BLE_NATIVE_READY");
        std::env::remove_var("COMPANION_TYPE_BLE_DEVICE_ID");
        let bridge = CompanionBleBridge::detect_default();
        let scan = bridge.scan();
        assert!(scan.ready, "native scan failed: {}", scan.message);
        let connect = bridge.connect(scan.device_id.as_deref());
        assert!(connect.ready, "native connect failed: {}", connect.message);
        println!("native_ble_scan={}", scan.message);
        println!("native_ble_connect={}", connect.message);
    }

    #[test]
    fn real_native_ble_recording_sync_smoke() {
        if std::env::var("COMPANION_TYPE_REAL_BLE_SYNC_ACCEPTANCE")
            .ok()
            .as_deref()
            != Some("1")
        {
            return;
        }

        std::env::remove_var("COMPANION_TYPE_BLE_NATIVE_READY");
        std::env::remove_var("COMPANION_TYPE_BLE_DEVICE_ID");
        std::env::remove_var("COMPANION_TYPE_DEVICE_RECORDING_PATH");
        let bridge = CompanionBleBridge::detect_default();
        let sync = bridge.sync_recordings();
        assert!(sync.ready, "native sync failed: {}", sync.message);
        let path = sync
            .recording_path
            .as_ref()
            .expect("native sync did not return a WAV recording path");
        assert!(Path::new(path).exists(), "native sync WAV missing: {path}");
        println!("native_ble_recording_sync={}", sync.message);
    }
}
