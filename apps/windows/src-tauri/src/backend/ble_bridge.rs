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
const COMPANION_OTA_V1_SERVICE_UUID: Uuid =
    Uuid::from_u128(denzic_ota_core::GATT_SERVICE_UUID_U128);
const COMPANION_OTA_V1_CONTROL_UUID: Uuid =
    Uuid::from_u128(denzic_ota_core::GATT_CONTROL_UUID_U128);
const COMPANION_OTA_V1_DATA_UUID: Uuid =
    Uuid::from_u128(denzic_ota_core::GATT_DATA_UUID_U128);
const COMPANION_OTA_V1_STATUS_UUID: Uuid =
    Uuid::from_u128(denzic_ota_core::GATT_STATUS_UUID_U128);
const RECORDING_LIST_UUID: Uuid = Uuid::from_u128(0x8f7a30027b7d4f3d9d6f6c2d1b7c0000);
const RECORDING_CHUNK_PULL_UUID: Uuid = Uuid::from_u128(0x8f7a30037b7d4f3d9d6f6c2d1b7c0000);
const DELETE_PRIVACY_UUID: Uuid = Uuid::from_u128(0x8f7a60017b7d4f3d9d6f6c2d1b7c0000);
const DELETE_PRIVACY_SCHEMA_VERSION: u8 = 1;
const DELETE_PRIVACY_OP_DELETE_RECORDING: u8 = 1;
const DELETE_PRIVACY_OP_DELETE_ALL: u8 = 2;
const DELETE_PRIVACY_OP_FACTORY_WIPE: u8 = 3;
const DELETE_PRIVACY_REFUSAL_FLAG: u16 = 0x0001;
const DELETE_PRIVACY_REQUEST_BYTES: usize = 48;
const RECORDING_CHUNK_FINAL_FLAG: u8 = 0x01;
const RECORDING_CHUNK_COMPRESSED_IMA_FLAG: u8 = 0x02;
const RECORDING_CHUNK_COMPACT_FLAG: u8 = 0x08;
const RECORDING_CHUNK_ERROR_FLAG: u8 = 0x80;
const RECORDING_REQ_COMPRESS_IMA: u8 = 0x02;
const RECORDING_REQ_STREAM_ALL: u8 = 0x04;
const RECORDING_LIST_ENTRY_BYTES: usize = 32;
/// Compact intermediate (no total_length on wire): schema..offset + crc = 20 B.
const RECORDING_CHUNK_HEADER_COMPACT_BYTES: usize = 20;
/// Legacy intermediate with total_length: 24 B.
const RECORDING_CHUNK_HEADER_LEGACY_BASE_BYTES: usize = 24;
const RECORDING_CHUNK_HEADER_FULL_BYTES: usize = 56;
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
                        Some(path) => {
                            let base = format!(
                                "Native BLE pulled recording_id={} duration_ms={} bytes={} sha256={} -> {}",
                                sync.recording_id.unwrap_or_default(),
                                sync.duration_ms.unwrap_or_default(),
                                sync.total_length.unwrap_or_default(),
                                sync.sha256.clone().unwrap_or_default(),
                                path
                            );
                            match &sync.device_erase_status {
                                Some(status) => format!("{base}; {status}"),
                                None => base,
                            }
                        }
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

    pub fn delete_all_privacy(&self, requested_device_id: Option<&str>) -> CompanionBleOperation {
        if let Some(operation) = env_native_operation(
            "Companion device privacy wipe acknowledged from configured environment",
        ) {
            return operation;
        }
        if native_ble_available() {
            return match run_native_blocking(delete_privacy_native(
                requested_device_id,
                DELETE_PRIVACY_OP_DELETE_ALL,
                0,
                0,
                [0u8; 32],
            )) {
                Ok(result) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-privacy-wipe".to_string(),
                    ready: !result.refused,
                    device_id: Some(result.device_id),
                    recording_path: None,
                    message: if result.refused {
                        "Device refused delete_all_recordings (privacy locked or busy).".to_string()
                    } else {
                        "Device acknowledged delete_all_recordings; on-device recordings erased."
                            .to_string()
                    },
                },
                Err(err) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-privacy-wipe".to_string(),
                    ready: false,
                    device_id: None,
                    recording_path: None,
                    message: format!("Native BLE privacy wipe failed: {err}"),
                },
            };
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; on-device privacy wipe requires the Windows BLE provider.",
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
    result
        .map(|transfer| CompanionOtaBleReport {
            device_id,
            transfer,
        })
        .map_err(String::from)
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
    device_erase_status: Option<String>,
}

#[derive(Clone, Debug)]
struct NativeDeleteResult {
    device_id: String,
    operation: u8,
    request_id: u32,
    refused: bool,
    recording_id: u32,
    validated_total_length: u32,
}

#[derive(Clone, Debug)]
struct DeletePrivacyResponse {
    operation: u8,
    flags: u16,
    request_id: u32,
    recording_id: u32,
    validated_total_length: u32,
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
    // Best-effort Windows host CI preference (ThroughputOptimized ≈ 15 ms).
    // Device also asks for 7.5 ms; host preference reduces variance (COMP-REQ-663).
    request_windows_ble_throughput_params(&device.address);
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

/// Request WinRT `ThroughputOptimized` preferred connection parameters when possible.
/// Uses a short Python one-shot so we do not add a Windows WinRT crate dependency.
fn request_windows_ble_throughput_params(address: &str) {
    if std::env::var("COMPANION_TYPE_SKIP_WINRT_CONN_PARAMS")
        .map(|v| {
            let t = v.trim();
            t == "1" || t.eq_ignore_ascii_case("true")
        })
        .unwrap_or(false)
    {
        return;
    }
    let addr = address.trim();
    if addr.is_empty() {
        return;
    }
    // Prefer python launcher; ignore all failures (bench still works without this).
    let py = r#"
import asyncio, sys
async def main(addr):
    try:
        from winrt.windows.devices.bluetooth import (
            BluetoothLEDevice,
            BluetoothLEPreferredConnectionParameters,
        )
    except Exception as exc:
        print(f"winrt_import_skip={exc}", flush=True)
        return
    addr_int = int(addr.replace(":", "").replace("-", ""), 16)
    ble = await BluetoothLEDevice.from_bluetooth_address_async(addr_int)
    if ble is None:
        print("winrt_device_none", flush=True)
        return
    result = ble.request_preferred_connection_parameters(
        BluetoothLEPreferredConnectionParameters.throughput_optimized
    )
    params = ble.get_connection_parameters()
    print(f"winrt_pref_ok result={result} params={params}", flush=True)
asyncio.run(main(sys.argv[1]))
"#;
    let _ = std::process::Command::new("python")
        .args(["-c", py, addr])
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::null())
        .status();
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

async fn delete_privacy_native(
    requested_device_id: Option<&str>,
    operation: u8,
    recording_id: u32,
    total_length: u32,
    validated_sha256: [u8; 32],
) -> Result<NativeDeleteResult, String> {
    let device = connect_native_device(requested_device_id).await?;
    let result =
        delete_privacy_on_device(&device, operation, recording_id, total_length, validated_sha256)
            .await;
    let _ = timeout(
        env_timeout("COMPANION_TYPE_BLE_DISCONNECT_TIMEOUT_MS", 3_000),
        device.peripheral.disconnect(),
    )
    .await;
    result
}

async fn delete_privacy_on_device(
    device: &NativeDevice,
    operation: u8,
    recording_id: u32,
    total_length: u32,
    validated_sha256: [u8; 32],
) -> Result<NativeDeleteResult, String> {
    let characteristics = device.peripheral.characteristics();
    let char_delete = find_characteristic(&characteristics, DELETE_PRIVACY_UUID)?;
    if !char_delete.properties.contains(CharPropFlags::WRITE) {
        return Err("delete_privacy characteristic is not writable".to_string());
    }
    if !char_delete.properties.contains(CharPropFlags::NOTIFY) {
        return Err("delete_privacy characteristic is not notifiable".to_string());
    }

    let request_id = next_delete_request_id();
    let request = delete_privacy_request(
        operation,
        request_id,
        recording_id,
        total_length,
        validated_sha256,
    );

    let read_timeout = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let write_timeout = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);
    let mut notifications = timeout(read_timeout, device.peripheral.notifications())
        .await
        .map_err(|_| {
            format!(
                "open BLE notification stream timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("open BLE notification stream: {err}"))?;
    timeout(read_timeout, device.peripheral.subscribe(&char_delete))
        .await
        .map_err(|_| {
            format!(
                "subscribe delete_privacy timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("subscribe delete_privacy: {err}"))?;

    timeout(
        write_timeout,
        device.peripheral.write(&char_delete, &request, WriteType::WithResponse),
    )
    .await
    .map_err(|_| {
        format!(
            "write delete_privacy timed out after {}ms",
            write_timeout.as_millis()
        )
    })?
    .map_err(|err| format!("write delete_privacy: {err}"))?;

    let notify_timeout = StdDuration::from_millis(
        std::env::var("COMPANION_TYPE_BLE_NOTIFY_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(15_000),
    );
    let response = timeout(notify_timeout, async {
        loop {
            let notification = notifications
                .next()
                .await
                .ok_or_else(|| "delete_privacy notification stream ended".to_string())?;
            if notification.uuid != DELETE_PRIVACY_UUID {
                continue;
            }
            let parsed = parse_delete_privacy_response(&notification.value)?;
            if parsed.request_id == request_id {
                return Ok::<DeletePrivacyResponse, String>(parsed);
            }
        }
    })
    .await
    .map_err(|_| format!("delete_privacy notify timeout for request_id={request_id}"))??;

    let _ = device.peripheral.unsubscribe(&char_delete).await;
    Ok(NativeDeleteResult {
        device_id: device.device_id(),
        operation: response.operation,
        request_id: response.request_id,
        refused: (response.flags & DELETE_PRIVACY_REFUSAL_FLAG) != 0,
        recording_id: response.recording_id,
        validated_total_length: response.validated_total_length,
    })
}

fn delete_privacy_request(
    operation: u8,
    request_id: u32,
    recording_id: u32,
    total_length: u32,
    validated_sha256: [u8; 32],
) -> [u8; DELETE_PRIVACY_REQUEST_BYTES] {
    let mut payload = [0u8; DELETE_PRIVACY_REQUEST_BYTES];
    payload[0] = DELETE_PRIVACY_SCHEMA_VERSION;
    payload[1] = operation;
    payload[4..8].copy_from_slice(&request_id.to_le_bytes());
    payload[8..12].copy_from_slice(&recording_id.to_le_bytes());
    payload[12..16].copy_from_slice(&total_length.to_le_bytes());
    payload[16..48].copy_from_slice(&validated_sha256);
    payload
}

fn parse_delete_privacy_response(payload: &[u8]) -> Result<DeletePrivacyResponse, String> {
    if payload.len() < 16 {
        return Err(format!("delete_privacy response too short: {}", payload.len()));
    }
    if payload[0] != DELETE_PRIVACY_SCHEMA_VERSION {
        return Err(format!(
            "unexpected delete_privacy schema_version={}",
            payload[0]
        ));
    }
    Ok(DeletePrivacyResponse {
        operation: payload[1],
        flags: le_u16(payload, 2)?,
        request_id: le_u32(payload, 4)?,
        recording_id: le_u32(payload, 8)?,
        validated_total_length: le_u32(payload, 12)?,
    })
}

fn next_delete_request_id() -> u32 {
    static COUNTER: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(1);
    COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
}

fn delete_after_sync_enabled() -> bool {
    std::env::var("COMPANION_TYPE_DELETE_AFTER_SYNC")
        .map(|value| truthy(&value))
        .unwrap_or(false)
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
            device_erase_status: None,
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
    // IMA path is lossy: list SHA/CRC are of original device PCM, not decoded host PCM.
    // Packet CRC + length already enforced inside pull. Only raw path must match list digests.
    let compress = std::env::var("COMPANION_TYPE_BLE_COMPRESS")
        .map(|v| {
            let t = v.trim();
            t == "1"
                || t.eq_ignore_ascii_case("true")
                || t.eq_ignore_ascii_case("on")
                || t.eq_ignore_ascii_case("yes")
        })
        .unwrap_or(false);
    if !compress {
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
    }

    let path = native_recording_output_path(entry.recording_id)?;
    write_pcm16_wav(&path, &pcm_bytes)?;

    let mut verified_sha256 = [0u8; 32];
    verified_sha256.copy_from_slice(&sha256);
    let device_erase_status = if delete_after_sync_enabled() {
        match delete_privacy_on_device(
            device,
            DELETE_PRIVACY_OP_DELETE_RECORDING,
            entry.recording_id,
            entry.total_length,
            verified_sha256,
        )
        .await
        {
            Ok(result) if result.refused => Some(format!(
                "device refused delete-after-sync for recording_id={} (privacy locked or busy)",
                entry.recording_id
            )),
            Ok(_) => Some(format!(
                "device deleted recording_id={} after verified sync",
                entry.recording_id
            )),
            Err(err) => Some(format!(
                "delete-after-sync failed (audio already synced to host): {err}"
            )),
        }
    } else {
        None
    };

    Ok(NativeRecordingSync {
        device_id: device.device_id(),
        recording_id: Some(entry.recording_id),
        duration_ms: Some(entry.duration_ms),
        total_length: Some(entry.total_length),
        sha256: Some(sha256_hex),
        recording_path: Some(path.to_string_lossy().to_string()),
        device_erase_status,
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

    // Default product path: **非压缩** raw STREAM_ALL (COMP-REQ-662 wire ≥50 KB/s).
    // Opt-in IMA: set COMPANION_TYPE_BLE_COMPRESS=1 (COMP-REQ-661 effective path).
    // Device intermediate payload max is 220 B (ATT 244 − 24 B base header); firmware
    // sizes STREAM_ALL packets itself — host only starts/resumes the stream.
    // Note: full ATT 248 regressed Windows multi-notify (COMP-REQ-663 experiment).
    let compress = std::env::var("COMPANION_TYPE_BLE_COMPRESS")
        .map(|v| {
            let t = v.trim();
            t == "1"
                || t.eq_ignore_ascii_case("true")
                || t.eq_ignore_ascii_case("on")
                || t.eq_ignore_ascii_case("yes")
        })
        .unwrap_or(false);
    let req_flags = if compress {
        RECORDING_REQ_COMPRESS_IMA | RECORDING_REQ_STREAM_ALL
    } else {
        RECORDING_REQ_STREAM_ALL
    };

    // Large raw pulls (~2 MB @ ~50–60 KB/s) need a long first-packet budget and
    // enough idle before re-START; 400 ms raw idle was flaky under Windows CE.
    let notify_timeout = StdDuration::from_millis(
        std::env::var("COMPANION_TYPE_BLE_NOTIFY_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(if compress { 20_000 } else { 45_000 }),
    );
    // Compress encodes on-device between packets; raw still needs margin after TX stalls.
    let inter_default = if compress { 1_200 } else { 800 };
    let inter_packet_timeout = StdDuration::from_millis(
        std::env::var("COMPANION_TYPE_BLE_INTER_PACKET_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(inter_default),
    );
    let link_settle_ms = std::env::var("COMPANION_TYPE_BLE_LINK_SETTLE_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(if compress { 800 } else { 2_500 });
    if link_settle_ms > 0 {
        tokio::time::sleep(StdDuration::from_millis(link_settle_ms)).await;
    }

    let mut offset = 0_u32;
    let mut expected_sequence = 0_u32;
    let mut data = Vec::<u8>::with_capacity(entry.total_length as usize);
    let mut wire_bytes: u64 = 0;
    let mut final_sha256: Option<[u8; 32]> = None;
    let mut pending: std::collections::BTreeMap<u32, RecordingChunk> =
        std::collections::BTreeMap::new();
    let transfer_started = std::time::Instant::now();
    let write_type = if char_chunk_pull
        .properties
        .contains(CharPropFlags::WRITE_WITHOUT_RESPONSE)
    {
        WriteType::WithoutResponse
    } else {
        WriteType::WithResponse
    };

    let write_label = match write_type {
        WriteType::WithoutResponse => "without_response",
        WriteType::WithResponse => "with_response",
    };
    eprintln!(
        "recording pull start pcm_total={} compress={} flags=0x{:02x} write={} (wire_rate=实际空中; effective_rate=等效PCM)",
        entry.total_length, compress, req_flags, write_label
    );

    // One START with STREAM_ALL: device streams remaining PCM (raw or IMA).
    let request = recording_chunk_pull_request_flags(
        entry.recording_id,
        0,
        u16::MAX.min(entry.total_length.min(u32::from(u16::MAX)) as u16),
        req_flags,
    );
    timeout(
        write_timeout,
        peripheral.write(&char_chunk_pull, &request, write_type),
    )
    .await
    .map_err(|_| {
        format!(
            "write recording_chunk_pull start timed out after {}ms",
            write_timeout.as_millis()
        )
    })?
    .map_err(|err| format!("write recording_chunk_pull start: {err}"))?;

    let first_deadline = std::time::Instant::now() + notify_timeout;
    let mut last_rx = std::time::Instant::now();
    let mut packets: u32 = 0;

    while offset < entry.total_length {
        if let Some(mut chunk) = pending.remove(&offset) {
            if chunk.flags & RECORDING_CHUNK_ERROR_FLAG != 0 {
                return Err(format!(
                    "recording chunk error at offset={offset}: code=0x{:08x}",
                    chunk.packet_crc32
                ));
            }
            if chunk.recording_id != entry.recording_id {
                return Err("recording chunk id changed during transfer".to_string());
            }
            if chunk.packet_sequence != expected_sequence {
                // re-START / prep discard can burn sequence without moving PCM offset.
                // Offset is the stream cursor; accept a jump when byte_offset matches.
                if packets == 0 || chunk.byte_offset == offset {
                    expected_sequence = chunk.packet_sequence;
                } else {
                    return Err(format!(
                        "recording packet sequence mismatch: got {}, expected {} offset={} pkt_off={}",
                        chunk.packet_sequence,
                        expected_sequence,
                        offset,
                        chunk.byte_offset
                    ));
                }
            }
            // Compact intermediate omits total_length on wire (0); CRC still uses list total.
            if chunk.total_length == 0 {
                chunk.total_length = entry.total_length;
            } else if chunk.total_length != entry.total_length {
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

            wire_bytes += chunk.payload.len() as u64;
            let pcm_piece = if chunk.flags & RECORDING_CHUNK_COMPRESSED_IMA_FLAG != 0 {
                decode_ima_adpcm_frame(&chunk.payload)?
            } else {
                chunk.payload.clone()
            };
            if offset != chunk.byte_offset {
                return Err(format!(
                    "recording offset mismatch: host={offset} device={}",
                    chunk.byte_offset
                ));
            }
            data.extend_from_slice(&pcm_piece);
            offset = offset.saturating_add(pcm_piece.len() as u32);
            expected_sequence += 1;
            packets += 1;
            last_rx = std::time::Instant::now();

            if packets % 50 == 0 || offset >= entry.total_length {
                let elapsed = transfer_started.elapsed().as_secs_f64().max(0.001);
                let wire_rate = (wire_bytes as f64 / 1024.0) / elapsed;
                let effective_rate = (data.len() as f64 / 1024.0) / elapsed;
                eprintln!(
                    "recording pull progress pcm={}/{} wire={} packets={} wire_rate={:.1} KB/s effective_rate={:.1} KB/s compress={}",
                    data.len(),
                    entry.total_length,
                    wire_bytes,
                    packets,
                    wire_rate,
                    effective_rate,
                    compress
                );
            }
            if chunk.flags & RECORDING_CHUNK_FINAL_FLAG != 0 {
                final_sha256 = Some(chunk.final_sha256);
                break;
            }
            continue;
        }

        let wait = if packets > 0 {
            let idle = last_rx.elapsed();
            if idle >= inter_packet_timeout {
                // Stream stalled — re-START from current PCM offset.
                let resume = recording_chunk_pull_request_flags(
                    entry.recording_id,
                    offset,
                    u16::MAX,
                    req_flags,
                );
                timeout(
                    write_timeout,
                    peripheral.write(&char_chunk_pull, &resume, write_type),
                )
                .await
                .map_err(|_| "resume write timed out".to_string())?
                .map_err(|err| format!("resume write: {err}"))?;
                last_rx = std::time::Instant::now();
                continue;
            }
            inter_packet_timeout.saturating_sub(idle).min(StdDuration::from_millis(50))
        } else if std::time::Instant::now() >= first_deadline {
            return Err(format!(
                "recording chunk notify timeout at offset={offset}"
            ));
        } else {
            first_deadline
                .saturating_duration_since(std::time::Instant::now())
                .min(StdDuration::from_millis(50))
        };

        let chunk_result = timeout(wait, async {
            loop {
                let notification = notifications
                    .next()
                    .await
                    .ok_or_else(|| "recording notification stream ended".to_string())?;
                if notification.uuid != RECORDING_CHUNK_PULL_UUID {
                    continue;
                }
                return parse_recording_chunk(&notification.value);
            }
        })
        .await;

        match chunk_result {
            Ok(Ok(parsed)) => {
                last_rx = std::time::Instant::now();
                if parsed.recording_id == entry.recording_id && parsed.byte_offset >= offset {
                    pending.insert(parsed.byte_offset, parsed);
                }
            }
            Ok(Err(err)) => return Err(err),
            Err(_) => continue,
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
    // Lossy IMA: length + packet CRC already enforced; raw path requires full SHA match.
    if !compress && sha256[..] != final_sha256 {
        return Err(format!(
            "final SHA mismatch: device={} host={}",
            hex_lower(&final_sha256),
            hex_lower(&sha256)
        ));
    }
    let elapsed = transfer_started.elapsed().as_secs_f64().max(0.001);
    let wire_rate = (wire_bytes as f64 / 1024.0) / elapsed;
    let effective_rate = (data.len() as f64 / 1024.0) / elapsed;
    let ratio = if wire_bytes > 0 {
        data.len() as f64 / wire_bytes as f64
    } else {
        0.0
    };
    let p1_wire_50 = wire_rate >= 50.0 && wire_bytes >= 102_400 && !compress;
    let p1_product_50 = effective_rate >= 50.0 && data.len() as u64 >= 102_400;
    eprintln!(
        "recording pull done pcm={} wire={} packets={} 实际wire_rate={:.1} KB/s 等效effective_rate={:.1} KB/s ratio={:.2}x elapsed={:.3}s compress={} p1_wire_50={} p1_product_50={}",
        data.len(),
        wire_bytes,
        packets,
        wire_rate,
        effective_rate,
        ratio,
        elapsed,
        compress,
        p1_wire_50,
        p1_product_50
    );
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
    if payload.len() < RECORDING_CHUNK_HEADER_COMPACT_BYTES {
        return Err(format!("recording chunk too short: {}", payload.len()));
    }
    if payload[0] != 1 {
        return Err(format!(
            "unexpected recording chunk schema_version={}",
            payload[0]
        ));
    }
    let flags = payload[1];
    let payload_length = le_u16(payload, 2)?;
    // FINAL/ERROR: 56B with SHA. Compact intermediate: 20B. Legacy intermediate: 24B.
    let header_bytes = if flags & RECORDING_CHUNK_FINAL_FLAG != 0
        || flags & RECORDING_CHUNK_ERROR_FLAG != 0
    {
        RECORDING_CHUNK_HEADER_FULL_BYTES
    } else if flags & RECORDING_CHUNK_COMPACT_FLAG != 0 {
        RECORDING_CHUNK_HEADER_COMPACT_BYTES
    } else {
        RECORDING_CHUNK_HEADER_LEGACY_BASE_BYTES
    };
    let payload_end = header_bytes + payload_length as usize;
    if payload.len() < payload_end {
        return Err("recording chunk payload truncated".to_string());
    }
    let mut final_sha256 = [0_u8; 32];
    let (total_length, packet_crc32) = if header_bytes == RECORDING_CHUNK_HEADER_COMPACT_BYTES {
        // total_length omitted; CRC still covers real total (filled by caller context).
        (0_u32, le_u32(payload, 16)?)
    } else {
        if header_bytes == RECORDING_CHUNK_HEADER_FULL_BYTES {
            final_sha256.copy_from_slice(&payload[24..56]);
        }
        (le_u32(payload, 16)?, le_u32(payload, 20)?)
    };
    Ok(RecordingChunk {
        flags,
        payload_length,
        recording_id: le_u32(payload, 4)?,
        packet_sequence: le_u32(payload, 8)?,
        byte_offset: le_u32(payload, 12)?,
        total_length,
        packet_crc32,
        final_sha256,
        payload: payload[header_bytes..payload_end].to_vec(),
    })
}

fn recording_chunk_pull_request(recording_id: u32, offset: u32, requested_length: u16) -> [u8; 16] {
    recording_chunk_pull_request_flags(recording_id, offset, requested_length, 0)
}

fn recording_chunk_pull_request_flags(
    recording_id: u32,
    offset: u32,
    requested_length: u16,
    flags: u8,
) -> [u8; 16] {
    let mut payload = [0_u8; 16];
    payload[0] = 1;
    payload[1] = flags;
    payload[2..4].copy_from_slice(&requested_length.to_le_bytes());
    payload[4..8].copy_from_slice(&recording_id.to_le_bytes());
    payload[8..12].copy_from_slice(&offset.to_le_bytes());
    payload[12..16].copy_from_slice(&0_u32.to_le_bytes());
    payload
}

/// Decode one companion IMA-ADPCM frame (6B header + nibbles) to LE i16 PCM bytes.
fn decode_ima_adpcm_frame(frame: &[u8]) -> Result<Vec<u8>, String> {
    const STEP: [i32; 89] = [
        7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60,
        66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371,
        408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707,
        1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132,
        7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623,
        27086, 29794, 32767,
    ];
    const INDEX: [i32; 16] = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8];
    if frame.len() < 6 {
        return Err("IMA-ADPCM frame too short".to_string());
    }
    let mut predictor = i16::from_le_bytes([frame[0], frame[1]]) as i32;
    let mut step_index = frame[2] as i32;
    if !(0..=88).contains(&step_index) {
        return Err(format!("IMA-ADPCM bad step_index={step_index}"));
    }
    let sample_count = u16::from_le_bytes([frame[4], frame[5]]) as usize;
    let nibble_bytes = sample_count.div_ceil(2);
    if frame.len() < 6 + nibble_bytes {
        return Err("IMA-ADPCM frame truncated".to_string());
    }
    let mut samples = Vec::with_capacity(sample_count);
    let mut decode_nibble = |nibble: u8| {
        let step = STEP[step_index as usize];
        let mut delta = step >> 3;
        if nibble & 4 != 0 {
            delta += step;
        }
        if nibble & 2 != 0 {
            delta += step >> 1;
        }
        if nibble & 1 != 0 {
            delta += step >> 2;
        }
        if nibble & 8 != 0 {
            delta = -delta;
        }
        predictor = (predictor + delta).clamp(-32768, 32767);
        step_index = (step_index + INDEX[(nibble & 0x0f) as usize]).clamp(0, 88);
        predictor as i16
    };
    for &packed in &frame[6..6 + nibble_bytes] {
        if samples.len() >= sample_count {
            break;
        }
        samples.push(decode_nibble(packed & 0x0f));
        if samples.len() >= sample_count {
            break;
        }
        samples.push(decode_nibble((packed >> 4) & 0x0f));
    }
    if samples.len() != sample_count {
        return Err(format!(
            "IMA-ADPCM sample count mismatch: got {} expected {sample_count}",
            samples.len()
        ));
    }
    let mut out = Vec::with_capacity(sample_count * 2);
    for s in samples {
        out.extend_from_slice(&s.to_le_bytes());
    }
    Ok(out)
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

/// Window request size (may exceed single ATT notify payload). Firmware may
/// burst multiple notifies; current intermediate payload max is 224 B.
fn recording_window_requested_length(window_bytes: u32, remaining: u32) -> u16 {
    if remaining == 0 {
        return 0;
    }
    let want = remaining.min(window_bytes).min(u32::from(u16::MAX));
    want as u16
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
    fn recording_chunk_parser_accepts_intermediate_224_payload_compact_header() {
        // COMP-REQ-663 compact intermediate: 20B header + up to 224B payload (no SHA).
        let payload_bytes = vec![0xA5_u8; 224];
        let mut chunk = RecordingChunk {
            flags: RECORDING_CHUNK_COMPACT_FLAG,
            payload_length: 224,
            recording_id: 1,
            packet_sequence: 42,
            byte_offset: 9240,
            total_length: 1_920_000,
            packet_crc32: 0,
            final_sha256: [0_u8; 32],
            payload: payload_bytes.clone(),
        };
        chunk.packet_crc32 = recording_packet_crc32(&chunk);

        let mut wire = Vec::new();
        wire.push(1);
        wire.push(chunk.flags);
        wire.extend_from_slice(&chunk.payload_length.to_le_bytes());
        wire.extend_from_slice(&chunk.recording_id.to_le_bytes());
        wire.extend_from_slice(&chunk.packet_sequence.to_le_bytes());
        wire.extend_from_slice(&chunk.byte_offset.to_le_bytes());
        // Compact: no total_length on wire; CRC follows offset.
        wire.extend_from_slice(&chunk.packet_crc32.to_le_bytes());
        wire.extend_from_slice(&chunk.payload);
        assert_eq!(wire.len(), RECORDING_CHUNK_HEADER_COMPACT_BYTES + 224);

        let mut parsed = parse_recording_chunk(&wire).unwrap();
        assert_eq!(parsed.flags & RECORDING_CHUNK_COMPACT_FLAG, RECORDING_CHUNK_COMPACT_FLAG);
        assert_eq!(parsed.payload_length, 224);
        assert_eq!(parsed.payload, payload_bytes);
        assert_eq!(parsed.total_length, 0); // filled from list at pull time
        parsed.total_length = 1_920_000;
        assert_eq!(recording_packet_crc32(&parsed), parsed.packet_crc32);
        assert_eq!(parsed.final_sha256, [0_u8; 32]);
    }

    #[test]
    fn recording_chunk_request_length_does_not_truncate_64k_remaining() {
        assert_eq!(recording_chunk_requested_length(180, 65_536), 180);
        assert_eq!(recording_chunk_requested_length(180, 179), 179);
        assert_eq!(recording_chunk_requested_length(180, 0), 0);
        assert_eq!(recording_window_requested_length(1536, 65_536), 1536);
        assert_eq!(recording_window_requested_length(1536, 200), 200);
        assert_eq!(recording_window_requested_length(1536, 0), 0);
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

    #[test]
    fn delete_privacy_request_encodes_firmware_contract_layout() {
        let digest = Sha256::digest(b"companion privacy proof");
        let sha: [u8; 32] = digest.into();
        let request = delete_privacy_request(
            DELETE_PRIVACY_OP_DELETE_ALL,
            0x11223344,
            0x55667788,
            0x99aabbcc,
            sha,
        );
        assert_eq!(request.len(), DELETE_PRIVACY_REQUEST_BYTES);
        assert_eq!(request[0], DELETE_PRIVACY_SCHEMA_VERSION);
        assert_eq!(request[1], DELETE_PRIVACY_OP_DELETE_ALL);
        assert_eq!(&request[2..4], &[0u8, 0]);
        assert_eq!(le_u32(&request, 4).unwrap(), 0x11223344);
        assert_eq!(le_u32(&request, 8).unwrap(), 0x55667788);
        assert_eq!(le_u32(&request, 12).unwrap(), 0x99aabbcc);
        assert_eq!(&request[16..48], &sha[..]);

        // synthetic device response echoes the same layout; flags bit0 is the refusal bit
        let mut response = request;
        response[2..4].copy_from_slice(&0u16.to_le_bytes());
        let accepted = parse_delete_privacy_response(&response).unwrap();
        assert_eq!(accepted.request_id, 0x11223344);
        assert_eq!(accepted.flags & DELETE_PRIVACY_REFUSAL_FLAG, 0);

        response[2..4].copy_from_slice(&DELETE_PRIVACY_REFUSAL_FLAG.to_le_bytes());
        let refused = parse_delete_privacy_response(&response).unwrap();
        assert_ne!(refused.flags & DELETE_PRIVACY_REFUSAL_FLAG, 0);
    }
}
