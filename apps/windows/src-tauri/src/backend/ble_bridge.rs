//! Companion BLE bridge boundary.
//!
//! The Windows app owns a native BLE path here. Firmware Python tools remain
//! validation inventory, but app scan/connect/sync can use the OS BLE stack
//! directly through btleplug's Windows backend.

use std::fs::{create_dir_all, File, OpenOptions};
use std::future::Future;
use std::io::{Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::{Duration as StdDuration, Instant as StdInstant, SystemTime, UNIX_EPOCH};

use btleplug::api::{
    AddressType, Central, CentralEvent, CharPropFlags, Characteristic, Manager as _, Peripheral as _, ScanFilter,
    ValueNotification, WriteType,
};
use btleplug::platform::{Manager, Peripheral};
use futures::{FutureExt, StreamExt};
use serde::Serialize;
use sha2::{Digest, Sha256};
use tokio::time::{sleep, timeout};
use uuid::Uuid;
use super::recording_sync::{self, Job as RecordingSyncJob};

mod offline_connection;
pub(crate) use offline_connection::original_follow_scope;
mod pull_session;
mod pull_progress;
mod pull_reorder;
mod pull_timing;
mod pull_receiver;
mod pull_recovery;
mod prepared_connection;
mod segmented;
mod batch_interval;
mod recorder_control;
pub(crate) mod pet_caption;
mod upload_benchmark;
pub(crate) use upload_benchmark::receive_fixture as benchmark_recording_upload;
use pull_session::PullSession;
pub(crate) use offline_connection::{owner_for_link as owned_offline_recording_link,
    owner_for_sync as owned_segmented_recording_sync, OwnedRecorder};

static OFFLINE_RECORDER_CONNECTION: std::sync::Mutex<offline_connection::Store<NativeDevice>> =
    std::sync::Mutex::new(offline_connection::Store::empty());
static PREPARED_DEVICE_CONNECTION: std::sync::Mutex<prepared_connection::Store<NativeDevice>> =
    std::sync::Mutex::new(prepared_connection::Store::empty());

const COMPANION_DEVICE_NAME_FILTER: &str = "companion";
const RECORDING_SERVICE_UUID: Uuid = Uuid::from_u128(0x8f7a00037b7d4f3d9d6f6c2d1b7c0000);
/// OTA service UUID kept for BLE scan/device match only. Product OTA transfer
/// is WinRT (`ota_winrt.rs`), not btleplug.
const COMPANION_OTA_V1_SERVICE_UUID: Uuid =
    Uuid::from_u128(denzic_ota_core::GATT_SERVICE_UUID_U128);
const RECORDING_LIST_UUID: Uuid = Uuid::from_u128(0x8f7a30027b7d4f3d9d6f6c2d1b7c0000);
const RECORDING_CONTROL_UUID: Uuid = Uuid::from_u128(0x8f7a30017b7d4f3d9d6f6c2d1b7c0000);
const SETTINGS_UUID: Uuid = Uuid::from_u128(0x8f7a40017b7d4f3d9d6f6c2d1b7c0000);
const BLE_NAME_CONFIG_UUID: Uuid = Uuid::from_u128(0x8f7a40027b7d4f3d9d6f6c2d1b7c0000);
const BLE_NAME_CONFIG_BYTES: usize = 41;
const BLE_NAME_MAX_BYTES: usize = 29;
const BLE_NAME_STAGE: u8 = 1;
const BLE_NAME_APPLY: u8 = 2;
const BLE_NAME_RESET: u8 = 3;
const DEVICE_STATUS_UUID: Uuid = Uuid::from_u128(0x8f7a10017b7d4f3d9d6f6c2d1b7c0000);
const MEETING_CONTROL_UUID: Uuid = Uuid::from_u128(0x8f7a80017b7d4f3d9d6f6c2d1b7c0000);
const MEETING_STATUS_UUID: Uuid = Uuid::from_u128(0x8f7a80027b7d4f3d9d6f6c2d1b7c0000);
const IMU_STATUS_UUID: Uuid = Uuid::from_u128(0x8f7a90017b7d4f3d9d6f6c2d1b7c0000);
const SPEAKER_CONTROL_UUID: Uuid = Uuid::from_u128(0x8f7aa0017b7d4f3d9d6f6c2d1b7c0000);
const SPEAKER_STATUS_UUID: Uuid = Uuid::from_u128(0x8f7aa0027b7d4f3d9d6f6c2d1b7c0000);
const RECORDING_CHUNK_PULL_UUID: Uuid = Uuid::from_u128(0x8f7a30037b7d4f3d9d6f6c2d1b7c0000);
/// Dual-lane bulk notify twin (COMP-REQ-667). Optional on older firmware.
const RECORDING_CHUNK_PULL_B_UUID: Uuid = Uuid::from_u128(0x8f7a30047b7d4f3d9d6f6c2d1b7c0000);
const DELETE_PRIVACY_UUID: Uuid = Uuid::from_u128(0x8f7a60017b7d4f3d9d6f6c2d1b7c0000);
const DELETE_PRIVACY_SCHEMA_VERSION: u8 = 1;
const DELETE_PRIVACY_OP_DELETE_RECORDING: u8 = 1;
const DELETE_PRIVACY_OP_DELETE_ALL: u8 = 2;
const DELETE_PRIVACY_OP_FACTORY_WIPE: u8 = 3;
const DELETE_PRIVACY_REFUSAL_FLAG: u16 = 0x0001;
const DELETE_PRIVACY_REQUEST_BYTES: usize = 48;
const RECORDING_CHUNK_FINAL_FLAG: u8 = 0x01;
const RECORDING_CHUNK_COMPRESSED_IMA_FLAG: u8 = 0x02;
/// Product compact transport:20B plus negotiated payload, maximum489B.
const RECORDING_CHUNK_COMPACT_FLAG: u8 = 0x08;
/// COMP-REQ-666: IMA payload is 8 kHz; host upsamples ×2 to 16 kHz PCM.
const RECORDING_CHUNK_HALF_RATE_8K_FLAG: u8 = 0x10;
/// Experimental slim 12B (not product default); still accepted if an old build sends it.
const RECORDING_CHUNK_SLIM_FLAG: u8 = 0x20;
const RECORDING_CHUNK_ERROR_FLAG: u8 = 0x80;
/// Firmware encodes SPI NOR failures as 0x1000 | (-driver_status & 0xff).
/// During a live codec=3 capture, the writer owns the same NOR briefly, so a
/// read-side storage error is recoverable by restarting from the unchanged
/// durable byte offset. Completed recordings still treat it as terminal.
const RECORDING_FLASH_READ_STORAGE_BASE: u32 = 0x0000_1000;
const RECORDING_FLASH_READ_STORAGE_MASK: u32 = 0xffff_ff00;
const RECORDING_LIVE_STORAGE_RETRY_MAX: u8 = 4;
const RECORDING_LIVE_STORAGE_RETRY_DELAY_MS: u64 = 250;
const RECORDING_FINAL_PULL_RECONNECT_MAX: u8 = 3;
const RECORDING_FINAL_PULL_RECONNECT_DELAY_MS: u64 = 750;
/// Capability reads are best-effort connect probes. An encrypted characteristic
/// may wait for pairing UI, so one missing response must not hang DeviceConnect.
const OPTIONAL_STATUS_READ_TIMEOUT: StdDuration = StdDuration::from_millis(2_500);
const RECORDING_REQ_COMPRESS_IMA: u8 = 0x02;
const RECORDING_REQ_STREAM_ALL: u8 = 0x04;
const RECORDING_LIST_ENTRY_BYTES: usize = 32;
/// Product intermediate: schema,flags,len,id,seq,offset,crc = 20 B (no total_length).
const RECORDING_CHUNK_HEADER_COMPACT_BYTES: usize = 20;
/// Compat only: slim schema,flags,len,seq,offset = 12 B.
const RECORDING_CHUNK_HEADER_SLIM_BYTES: usize = 12;
/// Legacy intermediate with total_length: 24 B.
const RECORDING_CHUNK_HEADER_LEGACY_BASE_BYTES: usize = 24;
const RECORDING_CHUNK_HEADER_FULL_BYTES: usize = 56;
/// Product ATT payload budget matches firmware SAFE_ATT 244 − compact 20.
const RECORDING_CHUNK_PRODUCT_PAYLOAD_MAX: usize = 489;
const RECORDING_CODEC_PCM16_MONO: u8 = 1;
/// Half-rate IMA ADPCM on flash (compress-at-record product path).
const RECORDING_CODEC_HALF_IMA: u8 = 2;
/// Opus 16 kbps mono frames on flash (board RT encode stretch).
const RECORDING_CODEC_OPUS16: u8 = 3;
fn recording_wire_ima_allowed(codec: u8, requested: bool) -> bool {
    // Only legacy PCM can request additional lossy wire IMA. Stored IMA/Opus
    // originals must transfer byte-for-byte and retain their full digest.
    codec == RECORDING_CODEC_PCM16_MONO && requested
}
fn recording_wire_ima_requested(codec: u8) -> bool {
    recording_wire_ima_allowed(codec, std::env::var("COMPANION_TYPE_BLE_COMPRESS")
        .map(|v| matches!(v.trim().to_ascii_lowercase().as_str(), "1" | "true" | "on" | "yes"))
        .unwrap_or(false))
}
const RECORDING_SOURCE_MIC_SAI: u8 = super::recording_wire::SOURCE_MIC_SAI;
const RECORDING_SYNC_UNSYNCED: u8 = 0;
const RECORDING_SYNC_TRANSFER_ACTIVE: u8 = 1;
const PCM_SAMPLE_RATE_HZ: u32 = 16_000;
const PCM_CHANNELS: u16 = 1;
const PCM_BITS_PER_SAMPLE: u16 = 16;
const RECORDING_CONTROL_START: u8 = 1;
const RECORDING_CONTROL_STOP: u8 = 2;
const RECORDING_CONTROL_PROFILE_BOARD_MIC: u8 = 2;
const RECORDING_CONTROL_ERROR_FLAG: u8 = 0x80;
const RECORDING_CONTROL_STORAGE_FULL_FLAG: u8 = 0x40;
const MEETING_ERROR_STORAGE_FULL: u8 = 3;
const STORAGE_FULL_MESSAGE: &str = "设备存储已满，请先同步录音，或确认清除不需要的设备录音后重试。未同步录音不会自动删除。";
const MEETING_STATE_RECORDING: u8 = 1;
const MEETING_STATE_FINALIZED: u8 = 2;
const MEETING_CONTROL_PROFILE_BOARD_MIC: u8 = 2;

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
    pub sync_paused: bool,
    pub device_id: Option<String>,
    pub recording_path: Option<String>,
    pub recordings: Vec<CompanionSyncedRecording>,
    pub(crate) device_identity: Option<CompanionDeviceIdentity>,
    pub message: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct CompanionDeviceIdentity {
    pub firmware_version: Option<u32>,
    pub build_id: Option<u32>,
    pub board_id: Option<u32>,
    pub mcu_uid: Option<String>,
    pub ui_generation: Option<u32>,
    pub recording_capacity: Option<crate::companion_v1::CompanionV1RecordingCapacity>,
    pub recording: Option<bool>,
    pub imu_supported: Option<bool>,
    pub imu_online: Option<bool>,
    pub imu_sample_hz: Option<u16>,
    pub speaker_supported: Option<bool>,
    pub speaker_online: Option<bool>,
    pub speaker_volume: Option<u8>,
}

#[derive(Clone, Debug)]
pub(crate) struct CompanionOobeProbeReport {
    pub device_id: String,
    pub service_count: usize,
    pub characteristic_count: usize,
    pub recordings_available: usize,
    pub identity: CompanionDeviceIdentity,
    pub device_status_read: bool,
    pub imu_status_read: bool,
    pub speaker_status_read: bool,
    pub missing_required_gatt: Vec<String>,
    pub recording_list_error: Option<String>,
    pub clock_sync_error: Option<String>,
    pub clock_sync_evidence: Option<String>,
}

#[derive(Clone, Debug)]
pub struct CompanionSyncedRecording {
    pub recording_id: u32,
    pub duration_ms: u32,
    pub total_length: u32,
    pub sha256: String,
    pub recording_path: String,
    pub device_reclaimed: bool,
    pub capture_incomplete: bool,
}

#[derive(Clone, Debug)]
pub(crate) struct CompanionMeetingControlReport {
    pub device_id: String,
    pub request_id: u32,
    pub state: u8,
    pub last_error: u8,
    pub meeting_id: u32,
    pub duration_ms: u32,
    pub sync_state: u8,
    pub logical_key: Option<super::recording_wire::SessionKey>,
}

#[derive(Clone, Debug)]
pub(crate) struct CompanionSpeakerControlReport {
    pub device_id: String,
    pub state: u8,
    pub volume_percent: u8,
}

#[derive(Clone, Debug)]
pub(crate) struct CompanionBleNameReport {
    pub device_id: String,
    pub active_name: String,
}

#[derive(Debug)]
pub(crate) struct CompanionOtaBleReport {
    pub device_id: String,
    pub transfer: denzic_ota_core::TransferReport,
    pub payload_metrics: super::ota_metrics::PayloadMetrics,
    pub system_bundle: Option<serde_json::Value>,
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
            return match run_native_blocking(scan_native_device_with_retry(None)) {
                Ok(device) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-scan".to_string(),
                    ready: true,
                    sync_paused: false,
                    device_id: Some(device.device_id()),
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: None,
                    message: format!(
                        "Companion device discovered via native BLE: name={} address={} rssi={:?}",
                        device.name, device.address, device.rssi
                    ),
                },
                Err(err) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-scan".to_string(),
                    ready: false,
                    sync_paused: false,
                    device_id: None,
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: None,
                    message: format!("Native BLE scan did not find Companion: {err}"),
                },
            };
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; scan requires Windows BLE or validation helper inventory.",
        )
    }

    /// Run the first-use board checks without starting a recording, pulling
    /// audio, or invoking ASR/minutes services. Environment-forced transports
    /// are deliberately rejected because they cannot prove physical hardware.
    pub(crate) fn oobe_probe(
        &self,
        requested_device_id: Option<&str>,
    ) -> Result<CompanionOobeProbeReport, String> {
        if std::env::var("COMPANION_TYPE_BLE_NATIVE_READY")
            .map(|value| truthy(&value))
            .unwrap_or(false)
            || std::env::var_os("COMPANION_TYPE_BLE_DEVICE_ID").is_some()
        {
            return Err(
                "simulated/configured BLE transport cannot prove a physical first-use check"
                    .to_string(),
            );
        }
        if !native_ble_available() {
            return Err("Windows native BLE is unavailable; hardware checks were not run".to_string());
        }
        run_native_blocking(oobe_native_probe(requested_device_id))
    }

    pub fn connect(
        &self,
        requested_device_id: Option<&str>,
        known_recording_ids: &[u32],
    ) -> CompanionBleOperation {
        self.connect_with_owned_recording(requested_device_id, known_recording_ids, None)
    }

    pub(crate) fn connect_with_owned_recording(
        &self,
        requested_device_id: Option<&str>,
        known_recording_ids: &[u32],
        owned_recording: Option<&OwnedRecorder>,
    ) -> CompanionBleOperation {
        if let Some(mut operation) =
            env_native_operation("Companion device connected from configured environment")
        {
            if owned_recording.is_some() {
                operation.ready = false;
                operation.message = "Configured BLE cannot resume an owned physical recording connection".into();
                return operation;
            }
            operation.device_id = Some(
                requested_device_id
                    .map(str::to_string)
                    .or_else(|| operation.device_id.clone())
                    .unwrap_or_else(|| "companion-nucleo-wb55rg".to_string()),
            );
            // Product path: connect auto-drains pending (pop queue + transfer + ACK), not enqueue-only.
            let drain = super::recording_ring::product_auto_drain_transfers_on_connect(None)
                .unwrap_or_else(|e| {
                    eprintln!("recording_ring auto_drain env-connect: {e}");
                    super::recording_ring::AutoDrainTransferReport {
                        enqueued: vec![],
                        transferred_ids: vec![],
                        host_paths: vec![],
                        auto_transfer_started: false,
                        connect_count: 0,
                        upload_ack_count: 0,
                    }
                });
            if let Some(p) = drain.host_paths.first() {
                operation.recording_path = Some(p.clone());
            }
            operation.message = format!(
                "{}; recording_ring auto_drain enqueued={:?} transferred={:?} paths={}",
                operation.message,
                drain.enqueued,
                drain.transferred_ids,
                drain.host_paths.len()
            );
            return operation;
        }
        if native_ble_available() {
            return match run_native_blocking(connect_native_probe(requested_device_id, owned_recording, None)) {
                Ok(probe) => {
                    let actual_device_id = probe.device_id.clone();
                    let device_recording = probe.identity.recording;
                    // 1) Host ring pending → pop_next_auto_upload + complete transfer (ACK/consume).
                    let drain =
                        super::recording_ring::product_auto_drain_transfers_on_connect(None)
                            .unwrap_or_else(|e| {
                                eprintln!("recording_ring auto_drain: {e}");
                                super::recording_ring::AutoDrainTransferReport {
                                    enqueued: vec![],
                                    transferred_ids: vec![],
                                    host_paths: vec![],
                                    auto_transfer_started: false,
                                    connect_count: 0,
                                    upload_ack_count: 0,
                                }
                            });
                    // Connection readiness belongs to the final transport,
                    // independently of any audio already committed to disk.
                    let mut operation = CompanionBleOperation {
                        provider_id: "companion-type-windows-ble".into(),
                        mode: if probe.segmented_recording { "windows-native-connect-auto-upload-segmented" }
                            else { "windows-native-connect-auto-upload" }.into(),
                        ready: true, sync_paused: false,
                        device_id: Some(actual_device_id.clone()),
                        recording_path: drain.host_paths.first().cloned(), recordings: Vec::new(),
                        device_identity: Some(probe.identity),
                        message: format!("Native BLE protected probe: services={} characteristics={} recordings={}; owned_recording_connection_retained={}; ring auto_drain enqueued={:?} transferred={:?}",
                            probe.service_count, probe.characteristic_count, probe.recordings_available,
                            probe.owned_recording_connection_retained, drain.enqueued, drain.transferred_ids),
                    };
                    if device_recording == Some(true) && !probe.segmented_recording {
                        operation.message.push_str("; board recording is active; automatic recording pull deferred");
                    } else if device_recording.is_none() {
                        operation.message.push_str("; board recording state is unavailable; automatic recording pull deferred");
                    } else if !recording_sync::automatic_allowed(&actual_device_id) {
                        operation.sync_paused = true;
                        operation.message.push_str("; 录音同步已暂停，点击同步录音可从断点继续");
                    } else if probe.segmented_recording || should_auto_pull_recordings(
                        device_recording, probe.recordings_available) {
                        complete_connect_sync(&mut operation, run_native_blocking(sync_native_recordings_excluding(
                            Some(&actual_device_id), known_recording_ids)));
                    }
                    operation
                }
                Err(err) => {
                    super::recording_ring::product_on_ble_disconnected();
                    CompanionBleOperation {
                        provider_id: "companion-type-windows-ble".to_string(),
                        mode: "windows-native-connect".to_string(),
                        ready: false,
                        sync_paused: false,
                        device_id: requested_device_id.map(str::to_string),
                        recording_path: None,
                        recordings: Vec::new(),
                        device_identity: None,
                        message: format!("Native BLE connect failed: {err}"),
                    }
                }
            };
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; connect requires Windows BLE or validation helper inventory.",
        )
    }

    /// Probe only the exact native address remembered after a previous real
    /// GATT success. This path never falls back to configured fixtures and
    /// never drains/pulls recordings.
    pub(crate) fn probe_remembered(&self, device_id: &str) -> CompanionBleOperation {
        if !super::device_connection::stable_device_id(device_id) {
            return helper_operation(
                &self.status(),
                "Remembered device identity is not a stable native Bluetooth address.",
            );
        }
        if !native_ble_available() {
            return helper_operation(
                &self.status(),
                "Windows native BLE is unavailable; remembered-device probe was not run.",
            );
        }
        match super::diagnostics::Span::start(super::diagnostics::Operation::Reconnect).result(run_native_blocking(connect_native_probe(Some(device_id), None, known_segmented_peer(device_id)))) {
            Ok(probe)
                if normalize_device_id(&probe.device_id) == normalize_device_id(device_id) =>
            {
                CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-remembered-probe".to_string(),
                    ready: true,
                    sync_paused: false,
                    device_id: Some(probe.device_id),
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: Some(probe.identity),
                    message: format!(
                        "Remembered Companion verified transactionally: services={} characteristics={}",
                        probe.service_count, probe.characteristic_count
                    ),
                }
            }
            Ok(probe) => CompanionBleOperation {
                provider_id: "companion-type-windows-ble".to_string(),
                mode: "windows-native-remembered-probe".to_string(),
                ready: false,
                sync_paused: false,
                device_id: Some(device_id.to_string()),
                recording_path: None,
                recordings: Vec::new(),
                device_identity: None,
                message: format!(
                    "Remembered-device probe returned a different address {}; refusing it",
                    probe.device_id
                ),
            },
            Err(error) => CompanionBleOperation {
                provider_id: "companion-type-windows-ble".to_string(),
                mode: "windows-native-remembered-probe".to_string(),
                ready: false,
                sync_paused: false,
                device_id: Some(device_id.to_string()),
                recording_path: None,
                recordings: Vec::new(),
                device_identity: None,
                message: format!("Remembered Companion is offline: {error}"),
            },
        }
    }

    pub(crate) fn apply_ble_name(
        &self,
        requested_device_id: Option<&str>,
        name: &str,
    ) -> Result<CompanionBleNameReport, String> {
        if !crate::companion_v1::companion_ble_name_is_valid(name) {
            return Err("BLE name must be printable ASCII, 1..29 bytes, without quotes, semicolon, equals or backslash".to_string());
        }
        if !native_ble_available() {
            return Err("Windows native BLE is unavailable; device name was not changed".to_string());
        }
        run_native_blocking(configure_native_ble_name(
            requested_device_id,
            Some(name),
            false,
        ))
    }

    pub(crate) fn reset_ble_name(
        &self,
        requested_device_id: Option<&str>,
    ) -> Result<CompanionBleNameReport, String> {
        if !native_ble_available() {
            return Err("Windows native BLE is unavailable; device name was not reset".to_string());
        }
        run_native_blocking(configure_native_ble_name(
            requested_device_id,
            None,
            true,
        ))
    }

    pub fn sync_recordings(
        &self,
        requested_device_id: Option<&str>,
        known_recording_ids: &[u32],
    ) -> CompanionBleOperation {
        if let Err(error)=recording_sync::resume_explicit(requested_device_id) {return native_recording_operation(Err(error));}
        if let Ok(path) = std::env::var("COMPANION_TYPE_DEVICE_RECORDING_PATH") {
            // Explicit file import/diagnostic path, using the in-memory queue.
            // This does not exercise the board NOR journal or V2 sealed segments.
            let staged = std::fs::read(&path).ok().and_then(|bytes| {
                super::recording_ring::product_append_pending_segment(bytes)
                    .map_err(|e| eprintln!("ring append import: {e}"))
                    .ok()
            });
            let mut operation = self.connect(requested_device_id, known_recording_ids);
            if operation.recording_path.is_none() {
                operation.recording_path = Some(path.clone());
            }
            operation.message = format!(
                "Device recording path staged as ring pending id={:?}; {}",
                staged, operation.message
            );
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
            return native_recording_operation(run_native_blocking(sync_native_recordings_excluding(
                requested_device_id,
                known_recording_ids,
            )));
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; recording sync requires Windows BLE or COMPANION_TYPE_DEVICE_RECORDING_PATH.",
        )
    }

    pub(crate) fn sync_original_recording(&self, original: &OwnedRecorder) -> CompanionBleOperation {
        if let Err(error)=recording_sync::resume_explicit(Some(&original.device_id)) {return native_recording_operation(Err(error));}
        if !native_ble_available() {
            return helper_operation(&self.status(), "原设备录音同步需要真实Windows蓝牙，未用导入或演示源替代。");
        }
        native_recording_operation(run_native_blocking(sync_native_recordings_original(original)))
    }

    /// The user's STOP/retry owns exactly this sealed recording. An older
    /// backlog stays available for normal automatic or explicit batch sync.
    pub(crate) fn sync_stopped_recording(
        &self,
        requested_device_id: Option<&str>,
        recording_id: u32,
        known_recording_ids: &[u32],
    ) -> CompanionBleOperation {
        if !native_ble_available() {
            return helper_operation(&self.status(), "Native BLE is unavailable; stopped recording sync requires Windows BLE.");
        }
        if let Err(error)=recording_sync::resume_explicit(requested_device_id) {return native_recording_operation(Err(error));}
        native_recording_operation(run_native_blocking(sync_native_recordings_selected(
            requested_device_id, known_recording_ids, Some(recording_id))))
    }

    pub(crate) fn meeting_control_idempotent(
        &self,
        requested_device_id: Option<&str>,
        command: u8,
        max_seconds: u16,
        session_key: &str,
        expected_recording_id: Option<u32>,
        expected_key: Option<&crate::companion_v1::CompanionV1RecordingKey>,
    ) -> Result<CompanionMeetingControlReport, String> {
        if !native_ble_available() {
            return Err(
                "V1 meeting control requires the native Windows BLE provider; fixture control is not accepted"
                    .to_string(),
            );
        }
        let request_id = meeting_idempotency_request_id(session_key, command);
        run_native_blocking(meeting_control_native(
            requested_device_id,
            command,
            request_id,
            max_seconds,
            meeting_idempotency_request_id(session_key, 1),
            expected_recording_id.map(|id| MeetingControlIdentity::for_session(session_key, id)
                .with_key(expected_key)).transpose()?,
        ))
    }

    /// CMC3 controls are explicitly opt-in until the application can present
    /// their durable pending/paused states. No CMC2 or fixture fallback.
    pub(crate) fn pausable_meeting_control(
        &self, requested_device_id: &str, command: u8, max_seconds: u16,
        session_id: &str, expected_recording_id: Option<u32>,
        expected_key: Option<&crate::companion_v1::CompanionV1RecordingKey>,
        fresh_start: bool,
        known_recording_ids: &[u32],
        automatic_recovery: bool,
    ) -> Result<(CompanionMeetingControlReport, super::recorder_control::Journal, Option<CompanionBleOperation>), String> {
        if !native_ble_available() {
            return Err("暂停录音控制需要正式 Windows 蓝牙，不能用模拟控制替代。".into());
        }
        run_native_blocking(async {
            let (report,journal,device)=recorder_control::execute_owned(
                requested_device_id, command, max_seconds, session_id,
                expected_recording_id, expected_key, fresh_start,
            ).await?;
            if report.state!=2 {return Ok((report,journal,None));}
            // The original row and STOP/natural-seal confirmation are already
            // durable. Receive on the same owner; no re-pair/clock/START here.
            if automatic_recovery && !recording_sync::automatic_allowed(&device.device_id()) {
                // A background original-state observation cannot undo the
                // independent user pause or receive/consume a sealed original.
                finish_native_device_operation(device,true).await?;
                return Ok((report,journal,None));
            }
            if !automatic_recovery {
                if let Err(error)=recording_sync::resume_explicit(Some(&device.device_id())) {
                    let cleanup=finish_native_device_operation(device,true).await;
                    return Err(match cleanup {Ok(())=>error,Err(cleanup)=>format!("{error}; connection cleanup: {cleanup}")});
                }
            }
            let pulled=sync_native_recordings_with_link_policy(&device,known_recording_ids,
                Some(report.meeting_id),&mut SealedLinkPolicy::default(),report.logical_key.as_ref()).await;
            let reusable=pulled.as_ref().is_ok_and(|batch|batch.connection_reusable);
            finish_native_device_operation(device,reusable).await?;
            Ok((report,journal,Some(native_recording_operation(pulled))))
        })
    }

    /// STOP and durable receive share one verified device/connection owner.
    /// The ACK timestamp is captured before transfer; a failed receive remains
    /// a recoverable sealed recording and never replays START or STOP.
    pub(crate) fn stop_and_sync_recordings<F>(
        &self,
        requested_device_id: Option<&str>,
        session_key: &str,
        expected_recording_id: u32,
        known_recording_ids: &[u32],
        expected_key: Option<&crate::companion_v1::CompanionV1RecordingKey>,
        on_stopped: F,
    ) -> Result<(CompanionMeetingControlReport, String, CompanionBleOperation), String>
    where F: FnOnce(&CompanionMeetingControlReport, &str) -> Result<(), String> {
        if !native_ble_available() {
            return Err("V1 meeting control requires the native Windows BLE provider; fixture control is not accepted".into());
        }
        run_native_blocking(async {
            let (report, device) = meeting_control_native_owned(
                requested_device_id, 2, meeting_idempotency_request_id(session_key, 2),
                0, meeting_idempotency_request_id(session_key, 1),
                Some(MeetingControlIdentity::for_session(session_key, expected_recording_id).with_key(expected_key)?),
            ).await?;
            let observed_at = super::observation_timestamp();
            if let Err(error) = on_stopped(&report, &observed_at) {
                // Capture has physically stopped even if its host index
                // cannot be saved. Release this owner without reading or
                // reclaiming the original device audio.
                let cleanup = finish_native_device_operation(device, false).await;
                return Err(match cleanup {
                    Ok(()) => error,
                    Err(cleanup) => format!("{error}; connection cleanup: {cleanup}"),
                });
            }
            if let Err(error)=recording_sync::resume_explicit(Some(&device.device_id())) {
                let cleanup=finish_native_device_operation(device,true).await;
                return Err(match cleanup {Ok(())=>error,Err(cleanup)=>format!("{error}; connection cleanup: {cleanup}")});
            }
            eprintln!("recording_sync_stage stage=connection elapsed_ms=0 stopped_connection_reused=1 id={}", report.meeting_id);
            let pulled = sync_native_recordings_with_link_policy(&device, known_recording_ids,
                Some(report.meeting_id), &mut SealedLinkPolicy::default(), report.logical_key.as_ref()).await;
            let reusable = pulled.as_ref().is_ok_and(|batch| batch.connection_reusable);
            finish_native_device_operation(device, reusable).await?;
            Ok((report, observed_at, native_recording_operation(pulled)))
        })
    }

    pub(crate) fn speaker_prompt(
        &self,
        requested_device_id: Option<&str>,
        volume_percent: u8,
        prompt_id: u8,
    ) -> Result<CompanionSpeakerControlReport, String> {
        if !native_ble_available() {
            return Err("speaker prompt requires the native Windows BLE provider".to_string());
        }
        run_native_blocking(speaker_prompt_native(
            requested_device_id,
            volume_percent,
            prompt_id,
        ))
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
                    sync_paused: false,
                    device_id: Some(result.device_id),
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: None,
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
                    sync_paused: false,
                    device_id: None,
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: None,
                    message: format!("Native BLE privacy wipe failed: {err}"),
                },
            };
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; on-device privacy wipe requires the Windows BLE provider.",
        )
    }

    pub fn delete_recording_exact(
        &self,
        requested_device_id: Option<&str>,
        recording_id: u32,
        total_length: u32,
        sha256_hex: &str,
    ) -> CompanionBleOperation {
        let validated_sha256 = match parse_sha256_hex(sha256_hex) {
            Ok(value) => value,
            Err(err) => {
                return CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-privacy-delete-exact".to_string(),
                    ready: false,
                    sync_paused: false,
                    device_id: requested_device_id.map(str::to_string),
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: None,
                    message: err,
                }
            }
        };
        if let Some(mut operation) = env_native_operation(
            "Companion exact recording delete acknowledged from configured environment",
        ) {
            operation.mode = "windows-native-privacy-delete-exact-env".to_string();
            return operation;
        }
        if native_ble_available() {
            return match run_native_blocking(delete_privacy_native(
                requested_device_id,
                DELETE_PRIVACY_OP_DELETE_RECORDING,
                recording_id,
                total_length,
                validated_sha256,
            )) {
                Ok(result) if result.refused => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-privacy-delete-exact".to_string(),
                    ready: false,
                    sync_paused: false,
                    device_id: Some(result.device_id),
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: None,
                    message: format!(
                        "Device rejected exact delete recording_id={recording_id} length={total_length}"
                    ),
                },
                Ok(result) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-privacy-delete-exact".to_string(),
                    ready: true,
                    sync_paused: false,
                    device_id: Some(result.device_id),
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: None,
                    message: format!(
                        "Device reclaimed exact recording_id={recording_id} length={total_length} after SHA-256 verification"
                    ),
                },
                Err(err) => CompanionBleOperation {
                    provider_id: "companion-type-windows-ble".to_string(),
                    mode: "windows-native-privacy-delete-exact".to_string(),
                    ready: false,
                    sync_paused: false,
                    device_id: requested_device_id.map(str::to_string),
                    recording_path: None,
                    recordings: Vec::new(),
                    device_identity: None,
                    message: format!("Exact on-device recording delete failed: {err}"),
                },
            };
        }
        helper_operation(
            &self.status(),
            "Native BLE is unavailable; exact on-device recording delete was not applied.",
        )
    }

    pub(crate) fn transfer_firmware_ota(
        &self,
        requested_device_id: Option<&str>,
        firmware: &[u8],
        chunk_bytes: u16,
        wba_manifest: Option<&[u8; 144]>,
    ) -> Result<CompanionOtaBleReport, String> {
        if !native_ble_available() {
            return Err("Companion OTA requires the native Windows BLE provider".to_string());
        }
        // Product path only: Listener-aligned WinRT dual-lane WWR (denzic-ble-windows).
        // btleplug OTA was removed — incompatible host path, do not reintroduce.
        #[cfg(windows)]
        {
            return crate::backend::ota_winrt::transfer_companion_ota_winrt(
                requested_device_id,
                firmware,
                chunk_bytes,
                wba_manifest,
            );
        }
        #[cfg(not(windows))]
        {
            let _ = (requested_device_id, firmware, chunk_bytes, wba_manifest);
            Err("Companion OTA WinRT path is only available on Windows".to_string())
        }
    }
}

fn helper_operation(status: &CompanionBleBridgeStatus, message: &str) -> CompanionBleOperation {
    CompanionBleOperation {
        provider_id: status.native_provider_id.clone(),
        mode: status.mode.clone(),
        ready: false,
        sync_paused: false,
        device_id: None,
        recording_path: None,
        recordings: Vec::new(),
        device_identity: None,
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
            sync_paused: false,
            device_id: Some(device_id.unwrap_or_else(|| "companion-nucleo-wb55rg".to_string())),
            recording_path: None,
            recordings: Vec::new(),
            device_identity: None,
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

fn parse_sha256_hex(value: &str) -> Result<[u8; 32], String> {
    let value = value.trim();
    if value.len() != 64 {
        return Err(format!(
            "validated SHA-256 must contain 64 hex characters, got {}",
            value.len()
        ));
    }
    let mut out = [0u8; 32];
    for (index, slot) in out.iter_mut().enumerate() {
        let pair = &value[index * 2..index * 2 + 2];
        *slot = u8::from_str_radix(pair, 16)
            .map_err(|_| format!("validated SHA-256 contains non-hex data at byte {index}"))?;
    }
    Ok(out)
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

pub(crate) fn discard_oldest_recording<F>(device_id: &str, seconds: u16, confirm: F)
    -> Result<super::recording_discard::RecordingDiscardReport, String>
where F: FnOnce(&super::recording_discard::RecordingLossInfo) -> bool {
    use super::recording_discard as loss;
    if !native_ble_available() || device_id.trim().is_empty() || seconds == 0 {
        return Err("请在 Windows Companion Type 中连接真实设备，并填写有效录音时长。".into());
    }
    run_native_blocking(async {
        let device = connect_native_device(Some(device_id)).await?;
        let characteristics = device.peripheral.characteristics();
        let result = async {
            let payload = read_optional_status(&device.peripheral, &characteristics, DEVICE_STATUS_UUID, 84)
                .await.ok_or("未读到设备容量，请重新连接或更新配套固件。")?;
            let capacity = super::recording_capacity::parse(&payload)
                .ok_or("设备容量格式未知，请更新配套固件。")?;
            if !capacity.confirmed_discard_supported || capacity.busy {
                return Err("当前设备不支持单条删除，或正在录音、回收、升级；请先同步录音。".into());
            }
            let characteristic = find_characteristic(&characteristics, DELETE_PRIVACY_UUID)?;
            if !characteristic.properties.contains(CharPropFlags::WRITE)
                || !characteristic.properties.contains(CharPropFlags::NOTIFY)
                || !characteristic.properties.contains(CharPropFlags::READ) {
                return Err("设备未提供可确认的单条删除通道。".into());
            }
            let budget = StdDuration::from_secs(8);
            let mut notifications = bounded_ble_result("open recording-loss notifications", budget,
                device.peripheral.notifications()).await?;
            bounded_ble_result("subscribe recording-loss notifications", budget,
                device.peripheral.subscribe(&characteristic)).await?;
            let mut id = next_delete_request_id();
            if id == 0 { id = next_delete_request_id(); }
            let preview = loss::preview_request(id, seconds);
            // Keep the very same connection and subscription across the human
            // decision. Reconnect must invalidate this capability in firmware.
            let issued = StdInstant::now();
            let packet = discard_exchange(&device, &characteristic, &mut notifications, &preview, false).await?;
            if loss::flags(&packet, &preview)? == loss::NO_CANDIDATE {
                return Ok(loss::RecordingDiscardReport { status: "noCandidate".into(), recording: None,
                    message: "没有可确认删除的候选：空间可能已经足够，或设备还在保护/回收录音。请重新读取容量或先同步。".into() });
            }
            let offer = loss::parse_offer(&packet, &preview, &capacity)?;
            let confirmed = confirm(&offer.info);
            let decision = offer.decision(confirmed, issued.elapsed())?;
            if !confirmed {
                // Cancellation sends no destructive instruction. Even if the
                // cancel notification is lost, disconnect retires the offer.
                let _ = discard_exchange(&device, &characteristic, &mut notifications, &decision, false).await;
                return Ok(loss::RecordingDiscardReport { status: "cancelled".into(), recording: Some(offer.info),
                    message: "已取消，未发送删除确认。".into() });
            }
            let completed = discard_exchange(&device, &characteristic, &mut notifications, &decision, true)
                .await.map_err(|error| format!("录音 #{} 的删除完成状态尚未确认，请重新读取设备目录核对；{error}", offer.info.recording_id))?;
            if loss::flags(&completed, &decision)? != loss::COMPLETE {
                return Err("未取得完整删除回执，请重新读取设备状态。".into());
            }
            Ok(loss::RecordingDiscardReport { status: "deleted".into(),
                message: format!("设备录音 #{} 已完成删除与空间回收；新录音尚未开始，请重新读取容量。", offer.info.recording_id),
                recording: Some(offer.info) })
        }.await;
        // All exits, including expired, refused and cancelled proposals, retire
        // the temporary connection. Never reconnect to replay a destructive proof.
        if let Ok(characteristic) = find_characteristic(&characteristics, DELETE_PRIVACY_UUID) {
            let _ = timeout(StdDuration::from_secs(3), device.peripheral.unsubscribe(&characteristic)).await;
        }
        close_native_device(&device).await;
        result
    })
}

async fn discard_exchange<S>(device: &NativeDevice, characteristic: &Characteristic,
    notifications: &mut S, request: &[u8; super::recording_discard::BYTES], complete: bool)
    -> Result<Vec<u8>, String>
where S: futures::Stream<Item = ValueNotification> + Unpin {
    use super::recording_discard as loss;
    let deadline = StdInstant::now() + StdDuration::from_secs(if complete { 600 } else { 8 });
    bounded_ble_result("write recording-loss instruction", StdDuration::from_secs(8),
        device.peripheral.write(characteristic, request, WriteType::WithResponse)).await?;
    let mut retry_at = StdInstant::now() + StdDuration::from_secs(1);
    loop {
        if StdInstant::now() >= deadline { return Err("设备删除回执超时。".into()); }
        let notification = timeout(remaining_deadline_budget(deadline, StdDuration::from_millis(700)),
            notifications.next()).await;
        let packet = match notification {
            Ok(None) => return Err("设备连接已断开，删除回执未确认。".into()),
            Ok(Some(n)) if n.uuid == DELETE_PRIVACY_UUID && n.value.len() == loss::BYTES => Some(n.value),
            _ => None,
        };
        let packet = match packet {
            Some(p) => Some(p),
            None => bounded_ble_result("read exact recording-loss receipt", remaining_deadline_budget(deadline, StdDuration::from_secs(8)),
                device.peripheral.read(characteristic)).await.ok(),
        };
        if let Some(packet) = packet {
            if packet.len() == loss::BYTES && packet[0] == 2 && packet[1] == request[1]
                && packet[4..8] == request[4..8] && packet.as_slice() != request {
                // Some GATT stacks retain the just-written request while the
                // foreground task has not processed it. It is not a receipt.
                let flags = loss::flags(&packet, request)?;
                if flags == loss::REFUSED {
                    return Err("设备拒绝这次删除：确认可能已过期、连接/录音目录已变化，或设备正忙。请重新读取状态后查看候选。".into());
                }
                if complete {
                    if flags == loss::COMPLETE { return Ok(packet); }
                    if flags != loss::PENDING { return Err("设备删除状态未知，请重新读取。".into()); }
                } else {
                    let allowed = if request[1] == loss::PREVIEW { [0, loss::NO_CANDIDATE] }
                                  else { [loss::CANCELLED, loss::CANCELLED] };
                    if !allowed.contains(&flags) { return Err("设备未返回有效删除候选或取消回执。".into()); }
                    return Ok(packet);
                }
            }
        }
        if complete && StdInstant::now() >= retry_at {
            // The same proof is idempotent before/after completion. A missing
            // notify can be recovered without a new offer or a different ID.
            bounded_ble_result("retry exact recording-loss receipt", remaining_deadline_budget(deadline, StdDuration::from_secs(8)),
                device.peripheral.write(characteristic, request, WriteType::WithResponse)).await?;
            retry_at = StdInstant::now() + StdDuration::from_secs(1);
        }
    }
}

/// Companion's own diagnostic wire format: one encrypted WRITE+NOTIFY
/// characteristic, never the platform's different 24-byte event protocol.
pub(crate) fn pull_device_diagnostics(device_id: &str) -> Result<super::diagnostics::DeviceLogPage, String> {
    if !super::device_connection::stable_device_id(device_id) { return Err("请先连接一个真实 Companion，再读取设备日志".into()); }
    if !native_ble_available() { return Err("Windows native Bluetooth is unavailable".into()); }
    let span = super::diagnostics::Span::start(super::diagnostics::Operation::DeviceLogPull);
    span.result(run_native_blocking(async {
        let device = timeout(StdDuration::from_secs(30), connect_native_device(Some(device_id))).await.map_err(|_| "Bluetooth diagnostic connection timeout".to_string())??;
        let result = timeout(StdDuration::from_secs(12), async {
            if normalize_device_id(&device.device_id()) != normalize_device_id(device_id) { return Err("Bluetooth diagnostic device identity mismatch".into()); }
            let uuid = Uuid::from_u128(0x8f7a50017b7d4f3d9d6f6c2d1b7c0000);
            let characteristic = find_characteristic(&device.peripheral.characteristics(), uuid)?;
            let mut notifications = device.peripheral.notifications().await.map_err(|e| format!("GATT diagnostic notifications: {e}"))?;
            device.peripheral.subscribe(&characteristic).await.map_err(|e| format!("GATT diagnostic subscribe: {e}"))?;
            let mut request = [0u8;12]; request[0]=1; request[8..10].copy_from_slice(&8u16.to_le_bytes()); request[10..12].copy_from_slice(&244u16.to_le_bytes());
            device.peripheral.write(&characteristic,&request,WriteType::WithResponse).await.map_err(|e| format!("GATT diagnostic request: {e}"))?;
            while let Some(notification)=notifications.next().await {
                if notification.uuid==uuid { return super::diagnostics::decode_device_page(&notification.value,0); }
            }
            Err("GATT diagnostic notification stream disconnected".into())
        }).await.map_err(|_| "GATT diagnostic response timeout".to_string()).and_then(|value|value);
        close_native_device(&device).await;
        result
    }))
}

pub(crate) fn record_board_online_live_controlled(
    requested_device_id: Option<&str>,
    capture_seconds: u16,
    partial_interval_ms: u64,
    disconnect_after_seconds: Option<u16>,
    consumer: BoardPartialConsumer,
    stop_requested: Arc<AtomicBool>,
    recording_observer: Option<BoardRecordingObserver>,
    observer: Option<BoardPartialObserver>,
    bookmarks: Option<BoardBookmarkObserver>,
) -> Result<BoardOnlineLiveReport, String> {
    if !(12..=2580).contains(&capture_seconds) {
        return Err("在线转写时长须为 12 秒至 43 分钟；不会自动截短录音".into());
    }
    let partial_interval_ms = partial_interval_ms.max(2_000);
    super::diagnostics::Span::start(super::diagnostics::Operation::BoardRecording).result(run_native_blocking(record_board_online_live_inner(
        requested_device_id,
        capture_seconds,
        partial_interval_ms,
        disconnect_after_seconds,
        consumer,
        stop_requested,
        recording_observer,
        observer,
        bookmarks,
    )))
}

fn env_timeout(name: &str, default_ms: u64) -> StdDuration {
    StdDuration::from_millis(
        std::env::var(name)
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(default_ms),
    )
}

// Setup preferences have one owner and never enter the cloned idle/recorder
// device stores. A sealed sync can move this guard into its operation; normal
// Connect/START extracts only the device and immediately releases it.
struct NativeConnectionSetup {
    device: NativeDevice,
    #[cfg(windows)]
    preference: Option<super::ble_throughput::TransferPreference>,
}

#[derive(Clone, Copy, Debug, PartialEq)]
enum ConnectionIntent { Normal, SealedSync }

// This policy belongs to one sync operation, never to cloned idle devices.
// Keep the bootstrap identity after releasing its request so later backlog
// entries cannot install a 15ms Windows override over the WBA's 7.5ms request.
#[derive(Default)]
struct SealedLinkPolicy {
    #[cfg(windows)]
    preference: Option<super::ble_throughput::TransferPreference>,
    #[cfg(windows)]
    initialized: bool,
}
impl SealedLinkPolicy {
    async fn initialize(&mut self, device: &NativeDevice) {
        #[cfg(windows)]
        if !self.initialized {
            self.initialized = true;
            self.preference = super::ble_throughput::request_for_sealed_sync(
                &device.address, device.address_type,
            ).await;
        }
        #[cfg(not(windows))]
        let _ = device;
    }

    fn verified_payload(&mut self) {
        #[cfg(windows)]
        if let Some(preference) = self.preference.as_mut() {
            preference.release_after_verified_payload();
        }
    }

    fn verified_batch_interval(&mut self) {
        #[cfg(windows)]
        if let Some(preference)=self.preference.as_mut() {
            preference.release_after_verified_batch_owner();
        }
    }
}

#[derive(Clone)]
struct NativeDevice {
    peripheral: Peripheral,
    name: String,
    address: String,
    address_type: Option<AddressType>,
    rssi: Option<i16>,
    service_uuids: Vec<Uuid>,
    user_connection: bool,
    verified_uid: Option<String>,
    // Learned only from the protected V2 catalogue on this verified link.
    recording_peer: Option<super::recording_wire::transport::Peer>,
    follow_generation: Option<u32>,
    observed_identity: Option<CompanionDeviceIdentity>,
    #[cfg(windows)]
    connection_session: Option<Arc<super::ble_throughput::ConnectionSession>>,
}

async fn on_native_link<T>(device: &NativeDevice,
    work: impl std::future::Future<Output=Result<T,String>>) -> Result<T,String> {
    #[cfg(windows)]
    if let Some(session)=device.connection_session.as_ref() { return session.guard(work).await; }
    work.await
}

async fn disconnect_native_device(device: &NativeDevice) -> Result<(), String> {
    #[cfg(windows)]
    if let Some(session) = &device.connection_session { session.close(); }
    bounded_ble_result("disconnect native device",
        env_timeout("COMPANION_TYPE_BLE_DISCONNECT_TIMEOUT_MS", 3_000),
        device.peripheral.disconnect()).await
}

async fn close_native_device(device: &NativeDevice) {
    let _ = disconnect_native_device(device).await;
}

async fn remember_prepared_device(device: NativeDevice) -> Result<(), String> {
    let saved = PREPARED_DEVICE_CONNECTION.lock()
        .map_err(|_| "已连接设备状态锁不可用".to_string())
        .map(|mut store| store
        .replace(prepared_connection::Peer { device_id: device.device_id(),
            mcu_uid: device.verified_uid.clone(), device: device.clone() }));
    let old = match saved {
        Ok(old) => old,
        Err(error) => { close_native_device(&device).await; return Err(error); }
    };
    if let Some(old) = old { close_native_device(&old.device).await; }
    Ok(())
}

async fn finish_native_device_operation(device: NativeDevice, succeeded: bool) -> Result<(), String> {
    if succeeded && device.user_connection {
        remember_prepared_device(device).await
    } else {
        close_native_device(&device).await;
        Ok(())
    }
}

async fn take_prepared_device(requested: Option<&str>) -> Result<Option<NativeDevice>, String> {
    let peer = PREPARED_DEVICE_CONNECTION.lock()
        .map_err(|_| "已连接设备状态锁不可用".to_string())?.take_exact(requested);
    let Some(mut peer) = peer else { return Ok(None) };
    #[cfg(windows)]
    if peer.device.connection_session.as_ref().is_some_and(|session| !session.is_open()) {
        close_native_device(&peer.device).await;
        return Ok(None);
    }
    let connected = bounded_ble_result("check prepared device connection", StdDuration::from_secs(3),
        peer.device.peripheral.is_connected()).await.unwrap_or(false);
    if !connected { close_native_device(&peer.device).await; return Ok(None); }
    let identity_checked = peer.mcu_uid.is_some();
    if let Some(expected) = peer.mcu_uid {
        let chars = peer.device.peripheral.characteristics();
        let status = read_optional_status(&peer.device.peripheral, &chars, DEVICE_STATUS_UUID, 36).await;
        let identity = parse_device_identity(status.as_deref(), None, None);
        if identity.mcu_uid.as_deref() != Some(expected.as_str()) {
            close_native_device(&peer.device).await;
            return Err("已连接设备的芯片身份不可核对或发生变化，未发送开停/收取命令。".into());
        }
        peer.device.observed_identity = Some(identity);
    }
    eprintln!("BLE prepared_connection reused=1 exact_address=1 identity_checked={}", u8::from(identity_checked));
    Ok(Some(peer.device))
}

static VERIFIED_SEGMENTED_RECORDER: std::sync::LazyLock<std::sync::Mutex<Option<(String, super::recording_wire::transport::Peer)>>> =
    std::sync::LazyLock::new(|| std::sync::Mutex::new(None));

pub(crate) fn known_segmented_peer(device_id: &str) -> Option<super::recording_wire::transport::Peer> {
    VERIFIED_SEGMENTED_RECORDER.lock().ok().and_then(|known| known.as_ref()
        .filter(|(id, _)| scan_exact_address_match(Some(device_id), id)).map(|(_, peer)| peer.clone()))
}

pub(crate) fn known_segmented_recording(device_id: &str) -> bool { known_segmented_peer(device_id).is_some() }

fn require_same_recorder(expected: Option<&super::recording_wire::transport::Peer>,
    actual: Option<&super::recording_wire::transport::Peer>) -> Result<(), String> {
    if expected.is_some_and(|expected| actual.is_none_or(|actual|
        expected.uid != actual.uid || expected.epoch != actual.epoch)) {
        return Err("重连设备的UID或录音格式代次改变；未收取、开停或消费原会话。".into());
    }
    Ok(())
}

pub(crate) fn prepared_segmented_recording(device_id: &str) -> bool {
    OFFLINE_RECORDER_CONNECTION.lock().ok().is_some_and(|store|
        store.peek_device(device_id).is_some_and(|lease| lease.logical_key.is_some()
            && lease.device.recording_peer.is_some())) ||
    PREPARED_DEVICE_CONNECTION.lock().ok().is_some_and(|store|
        store.peek_exact(device_id).is_some_and(|peer|
            peer.mcu_uid.is_some() && peer.device.user_connection && peer.device.recording_peer.is_some()))
}

// A bounded follower borrows only the already verified user connection. It
// never scans, pairs, starts/stops MIC or resumes a user-paused synchronization.
pub(crate) struct FollowObservation {
    pub(super) identity: CompanionDeviceIdentity,
    pub(super) operation: Option<CompanionBleOperation>,
}

pub(crate) fn follow_prepared_recording_once(device_id: &str,
    original_scope: Option<&super::recording_wire::SessionKey>,
    mut live: Option<&mut super::recording_wire::receiver::LiveCursor>) -> Result<Option<FollowObservation>, String> {
    if live.as_ref().is_some_and(|c|original_scope!=Some(c.key())) {
        return Err("在线转写游标不属于原录音，未读取其它会话。".into());
    }
    let allowed = if original_scope.is_some() { recording_sync::owned_follow_allowed(device_id) }
        else { recording_sync::automatic_allowed(device_id) };
    if !allowed || !prepared_segmented_recording(device_id) {
        return Ok(None);
    }
    run_native_blocking(async {
        // Backend's snapshot lock serializes this borrow with START/STOP and
        // bookmarks. Remove the actual lease while this bounded job owns it.
        let mut owned = {
            let mut store = offline_connection_lock()?;
            if original_scope.is_some_and(|scope| store.peek_device(device_id)
                .is_none_or(|lease| lease.logical_key.as_ref() != Some(scope))) {
                return Err("连续录音连接与指定原会话不同，未借用其它连接。".into());
            }
            store.take_device(Some(device_id))
        };
        let mut device = if let Some(lease) = owned.as_ref() { lease.device.clone() } else {
            take_prepared_device(Some(device_id)).await?
                .ok_or("连续录音连接已断开；设备继续离线录音，接收断点保留。")?
        };
        let mut identity = device.observed_identity.clone();
        let result = async {
            let peer = device.recording_peer.clone().ok_or("连续录音连接身份不可用。")?;
            let chars = device.peripheral.characteristics();
            if let Some(lease) = owned.as_ref() {
                let wire = read_optional_status(&device.peripheral,&chars,DEVICE_STATUS_UUID,36).await
                    .ok_or("录中同步未读到当前芯片状态；设备继续离线采音。")?;
                let current = parse_device_identity(Some(&wire),None,None);
                let status = find_characteristic(&chars,MEETING_STATUS_UUID)?;
                let status = bounded_ble_result("read logical recorder for follower",StdDuration::from_secs(3),
                    device.peripheral.read(&status)).await?;
                let status = parse_meeting_status(&status)?;
                lease.verify_observation(device.verified_uid.as_deref(),&device.device_id(),&current,&status,lease.start_token)?;
                identity = Some(current);
            }
            let job = RecordingSyncJob::begin_background(device_id)?;
            // Finish the bounded control exchange/CCCD cleanup before handoff;
            // do not drop a subscription-owning future midway through an ACK.
            let catalog = on_native_link(&device, segmented::read_catalog(&device, &chars, peer.clone())).await?;
            let tail_scope=owned.as_ref().and_then(|lease| lease.logical_key.as_ref());
            if catalog.generation.is_some() && device.follow_generation == catalog.generation
                && !(peer.growing_tail&&tail_scope.is_some()) {
                return Ok(None);
            }
            let mut policy = SealedLinkPolicy::default();
            let (mut batch, deferred) = segmented::sync_catalog_limited(&device, &chars, peer.clone(), catalog.entries,
                &job, &mut policy, Some(1), owned.as_ref().and_then(|lease| lease.logical_key.as_ref())).await?;
            if let Some(live)=live.as_deref_mut() {live.sealed(&native_recording_root()?,device_id);}
            if !deferred&&!batch.paused&&batch.failures.is_empty()&&peer.growing_tail {
                if let Some(scope)=tail_scope {
                    match segmented::follow_tail(&device,&chars,&peer,scope,&job,live.as_deref_mut()).await {
                        Ok(())=>(),Err(e) if e==recording_sync::PAUSED=>batch.paused=true,
                        Err(e)=>{batch.failures.push(e);batch.connection_reusable=false;}
                    }
                }
            }
            if !deferred && batch.failures.is_empty() && !batch.paused {
                device.follow_generation = catalog.generation;
            }
            if job.yielded() && batch.paused {
                batch.paused = false;
                // Cancelled payload awaits retain their durable cursor; retire
                // this handle before a user command establishes its own lane.
                batch.connection_reusable = false;
            }
            Ok::<_, String>(Some(batch))
        }.await;
        let reusable = result.as_ref().is_ok_and(|batch| batch.as_ref().is_none_or(|batch| batch.connection_reusable));
        if reusable {
            if let Some(lease) = owned.as_mut() {
                lease.device = device;offline_connection_lock()?.remember(lease.clone())?;
            } else { finish_native_device_operation(device,true).await?; }
        } else { close_native_device(&device).await; }
        let identity = identity.ok_or("连续录音状态没有当前身份读回。")?;
        result.map(|batch| Some(FollowObservation { identity, operation: batch.and_then(|batch| {
            if batch.failures.is_empty() && !batch.paused
                && batch.segmented.as_ref().is_none_or(|ids| ids.is_empty()) { None }
            else {
                let failed = !batch.failures.is_empty();
                let mut operation = native_recording_operation(Ok(batch));
                if failed { operation.ready = false; }
                Some(operation)
            }
        }) }))
    })
}

pub(crate) fn disconnect_prepared_device(device_id: Option<&str>) -> Result<(), String> {
    let peer = PREPARED_DEVICE_CONNECTION.lock()
        .map_err(|_| "已连接设备状态锁不可用".to_string())?.disconnect(device_id);
    if let Some(peer) = peer { run_native_blocking(async { close_native_device(&peer.device).await; Ok(()) })?; }
    Ok(())
}

fn offline_connection_lock() -> Result<std::sync::MutexGuard<'static, offline_connection::Store<NativeDevice>>, String> {
    OFFLINE_RECORDER_CONNECTION.lock().map_err(|_| "录音连接状态锁不可用；板端原录音仍保留。".into())
}

async fn retained_offline_connection(device_id: Option<&str>, start_token: u32, recording_id: Option<u32>, current_request: u32)
    -> Result<Option<offline_connection::Lease<NativeDevice>>,String> {
    let lease=offline_connection_lock()?.session(device_id,start_token,recording_id)?;
    let Some(lease)=lease else {return Ok(None)};
    let linked=bounded_ble_result("check retained offline recording connection",StdDuration::from_secs(3),
        lease.device.peripheral.is_connected()).await.unwrap_or(false);
    #[cfg(windows)]
    let linked=linked && lease.device.connection_session.as_ref().is_none_or(|session|session.is_open());
    if linked {
        return Ok(Some(lease));
    }
    // btleplug's Windows flag is maintained by ConnectionStatusChanged. Do
    // not tear down an owned GattSession on that flag alone: it may already
    // have recovered. Only a bounded, fresh protected identity read can keep
    // it. A failed read follows normal reconnect; an identity mismatch stops.
    #[cfg(windows)]
    if lease.device.connection_session.as_ref().is_some_and(|session| session.is_open()) {
        match recheck_retained_offline_connection(&lease, current_request).await {
            Ok(true) => {
                eprintln!("offline_retained_connection callback_linked=false protected_recheck=verified original_id={} new_pairing=false", lease.recording_id);
                return Ok(Some(lease));
            }
            Ok(false) => {}
            Err(error) => {
                offline_connection_lock()?.forget(&lease.device_id,lease.start_token,lease.recording_id);
                close_native_device(&lease.device).await;
                return Err(error);
            }
        }
    }
    offline_connection_lock()?.forget(&lease.device_id,lease.start_token,lease.recording_id);
    // The previous handle may still own stale WinRT services. Release it before
    // the ordinary fresh connection, preserving the on-board recording.
    close_native_device(&lease.device).await;
    Ok(None)
}

#[cfg(windows)]
async fn recheck_retained_offline_connection(
    lease: &offline_connection::Lease<NativeDevice>, current_request: u32,
) -> Result<bool, String> {
    if lease.device.verified_uid.as_deref().is_none_or(str::is_empty) { return Ok(false); }
    let characteristics = lease.device.peripheral.characteristics();
    let (Ok(device_status), Ok(meeting_status)) = (
        find_characteristic(&characteristics, DEVICE_STATUS_UUID),
        find_characteristic(&characteristics, MEETING_STATUS_UUID),
    ) else { return Ok(false) };
    let deadline = StdInstant::now() + StdDuration::from_secs(3);
    let read = async {
        let identity = bounded_ble_result("recheck original recorder chip",
            remaining_deadline_budget(deadline, StdDuration::from_secs(3)),
            lease.device.peripheral.read(&device_status)).await?;
        let status = bounded_ble_result("recheck original recorder control",
            remaining_deadline_budget(deadline, StdDuration::from_secs(3)),
            lease.device.peripheral.read(&meeting_status)).await?;
        Ok::<_, String>((identity, status))
    }.await;
    let (identity, status) = match read {
        Ok(values) => values,
        Err(error) => {
            eprintln!("offline_retained_connection callback_linked=false protected_recheck=unavailable original_id={} cause={error}", lease.recording_id);
            return Ok(false);
        }
    };
    lease.verify_observation(lease.device.verified_uid.as_deref(), &lease.device.device_id(),
        &parse_device_identity(Some(&identity), None, None), &parse_meeting_status(&status)?, current_request)?;
    Ok(true)
}

pub(crate) fn disconnect_retained_recording(device_id: Option<&str>) -> Result<(),String> {
    disconnect_prepared_device(device_id)?;
    let lease=offline_connection_lock()?.take_device(device_id);
    if let Some(lease)=lease {
        run_native_blocking(async { disconnect_native_device(&lease.device).await })?;
    }
    Ok(())
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
    identity: CompanionDeviceIdentity,
    owned_recording_connection_retained: bool,
    segmented_recording: bool,
}

#[derive(Clone, Debug)]
struct NativeRecordingSync {
    capture_incomplete: bool,
    device_id: String,
    recording_id: Option<u32>,
    duration_ms: Option<u32>,
    total_length: Option<u32>,
    sha256: Option<String>,
    recording_path: Option<String>,
    device_reclaimed: bool,
    reclaim_transport_failed: bool,
}

struct NativeRecordingBatch {
    device_id: String,
    recordings: Vec<CompanionSyncedRecording>,
    failures: Vec<String>,
    paused: bool,
    connection_reusable: bool,
    // V2 rows are already durably published with UID/epoch/session keys. They
    // must never pass through the V1 physical-ID import reducer.
    segmented: Option<Vec<String>>,
}

// A successful initial probe cannot outlive a failed automatic sync. A
// partial durable receipt is still a successful SAVE, not a live connection.
fn complete_connect_sync(operation: &mut CompanionBleOperation, result: Result<NativeRecordingBatch, String>) {
    match result {
        Ok(batch) => {
            if operation.device_id.as_deref().is_none_or(|id|
                !super::device_connection::same_device_id(id, &batch.device_id)) {
                operation.ready=false;
                operation.message="Native BLE connect failed: 自动收取返回了另一设备；未合并到当前设备。".into();
                super::recording_ring::product_on_ble_disconnected();
                return;
            }
            operation.sync_paused=batch.paused;
            if let Some(last)=batch.recordings.last(){operation.recording_path=Some(last.recording_path.clone());}
            operation.message.push_str(&format!("; auto_device_pull count={} continuous_sessions_saved={} isolated_failures={:?}",
                batch.recordings.len(),batch.segmented.as_ref().map_or(0,Vec::len),batch.failures));
            operation.recordings=batch.recordings;
            if batch.paused {operation.message.push_str(&format!("; {}",recording_sync::PAUSED));}
            if !batch.connection_reusable {
                operation.ready=false;
                operation.message=format!("蓝牙连接/自动收取未完成；已耐久保存的内容保留，未确认的录音仍在设备，需重连核对。{}",operation.message);
                super::recording_ring::product_on_ble_disconnected();
            }
        }
        Err(error) => {
            operation.ready=false;
            // Keep the native category at the known prefix so a genuine
            // pairing failure pauses automatic pairing attempts as before.
            operation.message=format!("Native BLE connect failed: {error}；自动收取未完成，已保存内容保留，未确认录音没有消费。");
            super::recording_ring::product_on_ble_disconnected();
        }
    }
}

fn native_recording_operation(result: Result<NativeRecordingBatch, String>) -> CompanionBleOperation {
    match result {
        Ok(batch) => CompanionBleOperation {
            provider_id: "companion-type-windows-ble".into(),
            mode: if batch.segmented.is_some() { "windows-native-segmented-recording-pull" }
                else { "windows-native-recording-pull" }.into(),
            // A durable receipt remains importable after its control transport
            // is retired. Physical consumption is tracked by each exact ACK,
            // separately from this host-save result and connection ownership.
            ready: batch.failures.is_empty() || !batch.recordings.is_empty()
                || batch.segmented.as_ref().is_some_and(|s| !s.is_empty()),
            sync_paused: batch.paused,
            device_id: Some(batch.device_id.clone()),
            recording_path: batch.recordings.last().map(|item| item.recording_path.clone()),
            recordings: batch.recordings.clone(),
            device_identity: None,
            message: if let Some(sessions) = batch.segmented.as_ref() {
                format!("设备连续录音已保存到录音库：{}场；{}。{:?}", sessions.len(),
                    if batch.paused { "同步已暂停，设备录音继续" }
                    else if !batch.connection_reusable { "回收确认未完成，原音已保存并保留精确重试记录" }
                    else { "未封口尾段仍留在设备，确认后才回收已保存段" }, batch.failures)
            } else if batch.paused {
                format!("{} 本次已完整保存{}条录音；未收齐的录音没有消费。", recording_sync::PAUSED, batch.recordings.len())
            } else if batch.recordings.is_empty() && batch.failures.is_empty() {
                "Native BLE sync found no stored recordings on device".into()
            } else if batch.recordings.is_empty() {
                format!("Native BLE sync isolated {} failed recording(s) and found no healthy new recording: {:?}",
                    batch.failures.len(), batch.failures)
            } else {
                format!("Native BLE durably saved {} recording(s), ids={:?}; physical_consume_confirmed={} pending_device_consume={}; connection_reusable={}; isolated_failures={:?}",
                    batch.recordings.len(), batch.recordings.iter().map(|item| item.recording_id).collect::<Vec<_>>(),
                    batch.recordings.iter().filter(|item| item.device_reclaimed).count(),
                    batch.recordings.iter().filter(|item| !item.device_reclaimed).count(),
                    batch.connection_reusable, batch.failures)
            },
        },
        Err(error) => CompanionBleOperation {
            provider_id: "companion-type-windows-ble".into(),
            mode: "windows-native-recording-pull".into(),
            ready: false,
            sync_paused: false,
            device_id: None,
            recording_path: None,
            recordings: Vec::new(),
            device_identity: None,
            message: format!("Native BLE recording sync failed: {error}"),
        },
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct BoardLivePartial {
    pub ordinal: u32,
    pub recording_id: u32,
    pub durable_codec_bytes: u32,
    pub duration_ms: u32,
    pub transcript: String,
    pub wav_path: String,
}

struct PendingBoardLivePartial {
    partial: BoardLivePartial,
    consumer: tokio::task::JoinHandle<Result<String, String>>,
}

pub(super) fn board_live_consumer_window(wav_path: &Path, duration_ms: u32) -> Result<PathBuf, String> {
    const WINDOW_SECONDS: u32 = 30;
    if duration_ms <= (WINDOW_SECONDS + 5) * 1_000 {
        return Ok(wav_path.to_path_buf());
    }
    let window_path = wav_path.with_file_name(format!(
        "{}-last{}s.wav",
        wav_path
            .file_stem()
            .and_then(|name| name.to_str())
            .unwrap_or("board-live"),
        WINDOW_SECONDS
    ));
    super::audio_artifacts::generated(wav_path, &window_path, super::audio_artifacts::Purpose::LiveWindow, || {
    // COP1 decoding already produces this exact format. Keep the last 30s
    // of PCM with the native writer; no executable lookup or shell involved.
    let pcm = super::diarization::read_pcm16k_mono_wav(wav_path)?;
    let start = pcm.len().saturating_sub(WINDOW_SECONDS as usize * 32_000);
    write_pcm16_wav(&window_path, &pcm[start..])?;
    Ok(window_path.clone())
    })
}

async fn collect_board_live_partials(
    pending: &mut Vec<PendingBoardLivePartial>,
    partials: &mut Vec<BoardLivePartial>,
    errors: &mut Vec<String>,
    drain_all: bool,
    observer: Option<&BoardPartialObserver>,
) {
    let mut index = 0usize;
    while index < pending.len() {
        if !drain_all && !pending[index].consumer.is_finished() {
            index += 1;
            continue;
        }
        let mut item = pending.swap_remove(index);
        match item.consumer.await {
            Ok(Ok(transcript)) => {
                eprintln!(
                    "board onlineLive partial={} id={} durable_codec_bytes={} duration_ms={} text={}",
                    item.partial.ordinal,
                    item.partial.recording_id,
                    item.partial.durable_codec_bytes,
                    item.partial.duration_ms,
                    transcript.replace(['\r', '\n'], " ")
                );
                item.partial.transcript = transcript;
                if let Some(observer) = observer {
                    observer(&item.partial);
                }
                partials.push(item.partial);
            }
            Ok(Err(err)) => {
                eprintln!(
                    "board onlineLive partial_error id={} durable_codec_bytes={} error={}",
                    item.partial.recording_id,
                    item.partial.durable_codec_bytes,
                    err.replace(['\r', '\n'], " ")
                );
                errors.push(err);
            }
            Err(err) => {
                let message = format!("board partial consumer join: {err}");
                eprintln!(
                    "board onlineLive partial_error id={} durable_codec_bytes={} error={}",
                    item.partial.recording_id, item.partial.durable_codec_bytes, message
                );
                errors.push(message);
            }
        }
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct BoardOnlineLiveReport {
    pub capture_incomplete: bool,
    pub sync_paused: bool,
    pub sealed_duration_ms: u32,
    pub device_id: String,
    pub recording_id: u32,
    /// Host observations of successful control acknowledgements, distinct
    /// from the board's sample clock and subsequent transfer/ASR completion.
    pub start_ack_at: String,
    pub stop_ack_at: String,
    pub partials: Vec<BoardLivePartial>,
    pub partial_errors: Vec<String>,
    pub disconnect_resume: bool,
    pub disconnect_offset: u32,
    pub final_recording_path: String,
    pub final_total_length: u32,
    pub final_sha256: String,
    pub device_reclaimed: bool,
}

pub(crate) type BoardPartialConsumer = Arc<dyn Fn(PathBuf) -> Result<String, String> + Send + Sync>;
pub(crate) type BoardRecordingObserver = Arc<dyn Fn(&str, u32, u32, &str) -> Result<(), String> + Send + Sync>;
pub(crate) type BoardPartialObserver = Arc<dyn Fn(&BoardLivePartial) + Send + Sync>;
pub(crate) struct BoardBookmarkObserver {
    pub pending: Arc<dyn Fn() -> bool + Send + Sync>,
    pub stamp: Arc<dyn Fn(&str,u32,u32) + Send + Sync>,
    pub close: Arc<dyn Fn() + Send + Sync>,
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
    capture_incomplete: bool,
    recording_id: u32,
    started_unix_s: u32,
    duration_ms: u32,
    codec: u8,
    sync_state: u8,
    source_mode: u8,
    total_length: u32,
    sha256_prefix: [u8; 8],
    content_crc32: u32,
    segment: Option<super::recording_wire::Descriptor>,
    tail: Option<super::recording_wire::tail::Tail>,
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

#[derive(Clone, Debug)]
struct MeetingStatus {
    state: u8,
    last_error: u8,
    request_id: u32,
    meeting_id: u32,
    duration_ms: u32,
    sync_state: u8,
    logical_key: Option<super::recording_wire::SessionKey>,
    pause_status: Option<super::recording_wire::control::PauseStatus>,
}

#[derive(Clone)]
struct MeetingControlIdentity {
    recording_id: u32,
    request_ids: [u32; 3],
    logical_key: Option<super::recording_wire::SessionKey>,
}

impl MeetingControlIdentity {
    fn for_session(session_key: &str, recording_id: u32) -> Self {
        Self { recording_id, logical_key: None, request_ids: [1, 2, 3].map(|command|
            meeting_idempotency_request_id(session_key, command)) }
    }
    fn with_key(mut self, key: Option<&crate::companion_v1::CompanionV1RecordingKey>) -> Result<Self, String> {
        self.logical_key = key.map(super::recording_wire::SessionKey::from_public).transpose()?;
        Ok(self)
    }
}

async fn scan_native_device(requested_device_id: Option<&str>) -> Result<NativeDevice, String> {
    #[cfg(windows)]
    if let Some(device) = connected_windows_device(requested_device_id).await {
        return Ok(device);
    }
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

    let started = StdInstant::now();
    let deadline = started + StdDuration::from_millis(timeout_ms);
    let mut events = futures::stream::SelectAll::new();
    // Register before scanning so the first advertisement cannot be missed.
    // A backend without events retains the bounded enumeration fallback.
    for (index, adapter) in adapters.iter().enumerate() {
        if let Ok(stream) = adapter.events().await {
            events.push(stream.map(move |event| (index, event)));
        }
    }
    let result = async {
        for adapter in &adapters {
            adapter.start_scan(ScanFilter { services: Vec::new() }).await
                .map_err(|err| format!("start BLE scan: {err}"))?;
        }
        let mut best: Option<(i32, NativeDevice)> = None;
        while StdInstant::now() < deadline && !events.is_empty() {
            let (index, event) = match timeout(deadline.saturating_duration_since(StdInstant::now()), events.next()).await {
                Ok(Some(value)) => value,
                Ok(None) | Err(_) => break,
            };
            let id = match event {
                // WinRT emits service metadata while constructing/updating
                // the peripheral, before registering a newly found device.
                // Use the completed advertisement events to avoid reading a
                // half-registered device or its missing address type.
                CentralEvent::DeviceDiscovered(id) | CentralEvent::DeviceUpdated(id) => id,
                _ => continue,
            };
            let peripheral = adapters[index].peripheral(&id).await
                .map_err(|err| format!("read advertised BLE peripheral: {err}"))?;
            if let Some(device) = scan_candidate(peripheral).await? {
                if let Some(score) = companion_candidate_score(&device, requested_device_id) {
                    // Only the exact, syntactically valid requested MAC can
                    // end discovery early. Names still use the whole window
                    // to select between multiple nearby Companion devices.
                    if device.address_type.is_some() && scan_exact_address_match(requested_device_id, &device.address) {
                        eprintln!("BLE scan exact_device elapsed_ms={} fixed_wait=0", started.elapsed().as_millis());
                        return Ok(device);
                    }
                    if best.as_ref().is_none_or(|(current, _)| score > *current) {
                        best = Some((score, device));
                    }
                }
            }
        }
        // Enumerate once for backends without event support and for events
        // whose property update was not complete when their callback ran.
        if events.is_empty() && StdInstant::now() < deadline {
            sleep(deadline.saturating_duration_since(StdInstant::now())).await;
        }
        for adapter in &adapters {
            for peripheral in adapter.peripherals().await
                .map_err(|err| format!("read BLE peripherals: {err}"))? {
                if let Some(device) = scan_candidate(peripheral).await? {
                    if let Some(score) = companion_candidate_score(&device, requested_device_id) {
                        if best.as_ref().is_none_or(|(current, _)| score > *current) {
                            best = Some((score, device));
                        }
                    }
                }
            }
        }
        eprintln!("BLE scan window elapsed_ms={} exact_device=0", started.elapsed().as_millis());
        best.map(|(_, device)| device).ok_or_else(|| format!(
            "no Companion candidate found with name containing '{COMPANION_DEVICE_NAME_FILTER}', recording service {RECORDING_SERVICE_UUID}, or OTA service {COMPANION_OTA_V1_SERVICE_UUID}"
        ))
    }.await;
    // Early success, partial start failure and discovery errors all stop every
    // watcher. Retries must not accumulate active advertisement scans.
    for adapter in &adapters {
        let _ = timeout(StdDuration::from_secs(1), adapter.stop_scan()).await;
    }
    result
}

#[cfg(windows)]
async fn connected_windows_device(requested_device_id: Option<&str>) -> Option<NativeDevice> {
    let requested = requested_device_id?;
    // Only an explicit exact MAC may use the Windows paired-device lookup.
    // Name/default selection still scans and chooses among advertised devices.
    if !scan_exact_address_match(Some(requested), requested) { return None; }
    let compact = requested.trim().replace([':', '-'], "");
    let address: btleplug::api::BDAddr = u64::from_str_radix(&compact, 16).ok()?.try_into().ok()?;
    let started = StdInstant::now();
    let peripheral = match timeout(StdDuration::from_secs(2),
        Peripheral::from_connected_paired_address(address)).await {
        Ok(Ok(peripheral)) => peripheral,
        result => {
            eprintln!("BLE known_device lookup_unavailable elapsed_ms={} cause={result:?} advertisement_fallback=1", started.elapsed().as_millis());
            return None;
        }
    };
    let device = scan_candidate(peripheral).await.ok()??;
    if !scan_exact_address_match(Some(requested), &device.address) { return None; }
    eprintln!("BLE known_device exact_paired_connected=1 elapsed_ms={} advertisement_wait=0 protected_setup_required=1", started.elapsed().as_millis());
    Some(device)
}

async fn scan_candidate(peripheral: Peripheral) -> Result<Option<NativeDevice>, String> {
    let Some(props) = peripheral.properties().await
        .map_err(|err| format!("read peripheral properties: {err}"))? else { return Ok(None) };
    Ok(Some(NativeDevice {
        peripheral,
        name: props.local_name.unwrap_or_default(),
        address: props.address.to_string(),
        address_type: props.address_type,
        rssi: props.rssi,
        service_uuids: props.services,
        user_connection: false,
        verified_uid: None,
        recording_peer: None,
        follow_generation: None,
        observed_identity: None,
        #[cfg(windows)]
        connection_session: None,
    }))
}

fn scan_exact_address_match(requested: Option<&str>, observed: &str) -> bool {
    let compact = |value: &str| {
        let value = value.trim().replace([':', '-'], "").to_ascii_lowercase();
        (value.len() == 12 && value.bytes().all(|byte| byte.is_ascii_hexdigit())).then_some(value)
    };
    requested.and_then(compact).is_some_and(|address| compact(observed).as_ref() == Some(&address))
}

async fn scan_native_device_with_retry(
    requested_device_id: Option<&str>,
) -> Result<NativeDevice, String> {
    let attempts = std::env::var("COMPANION_TYPE_BLE_SCAN_ATTEMPTS")
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(3)
        .max(1);
    let retry_delay = env_timeout("COMPANION_TYPE_BLE_SCAN_RETRY_DELAY_MS", 1_000);
    let mut failures = Vec::new();
    for attempt in 1..=attempts {
        if attempt > 1 {
            sleep(retry_delay).await;
        }
        match scan_native_device(requested_device_id).await {
            Ok(device) => {
                eprintln!("BLE scan success attempt={attempt}/{attempts}");
                return Ok(device);
            }
            Err(error) => failures.push(format!("attempt {attempt}: {error}")),
        }
    }
    Err(format!(
        "BLE scan exhausted {attempts} attempts: {}",
        failures.join(" | ")
    ))
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

async fn connect_native_device_once(
    requested_device_id: Option<&str>,
    sync_clock: bool,
    intent: ConnectionIntent,
) -> Result<NativeConnectionSetup, String> {
    let device = scan_native_device(requested_device_id).await?;
    connect_known_native_device_setup(device,sync_clock,intent).await
}

async fn connect_native_device(requested_device_id: Option<&str>) -> Result<NativeDevice, String> {
    connect_native_device_with_clock(requested_device_id,true).await
}

async fn connect_native_device_with_clock(requested_device_id: Option<&str>,sync_clock:bool) -> Result<NativeDevice,String> {
    connect_native_device_setup(requested_device_id, sync_clock).await.map(|setup| setup.device)
}

async fn connect_native_device_setup(requested_device_id: Option<&str>,sync_clock:bool) -> Result<NativeConnectionSetup,String> {
    connect_native_device_setup_with_intent(requested_device_id, sync_clock, ConnectionIntent::Normal).await
}

async fn connect_native_device_setup_with_intent(requested_device_id: Option<&str>,sync_clock:bool,intent:ConnectionIntent) -> Result<NativeConnectionSetup,String> {
    if let Some(device) = take_prepared_device(requested_device_id).await? {
        if sync_clock { let _ = sync_device_utc_clock(&device.peripheral).await; }
        #[cfg(windows)]
        let preference = if intent == ConnectionIntent::SealedSync {
            super::ble_throughput::request_for_sealed_sync(&device.address, device.address_type).await
        } else { None };
        return Ok(NativeConnectionSetup { device, #[cfg(windows)] preference });
    }
    /* Windows may retain a stale GATT object for a few seconds after the
     * transactional probe disconnects.  A one-shot connect made the UI look
     * ready while START could immediately fail with `Not connected`.  Treat
     * initial acquisition exactly like reconnect: bounded retries, a fresh
     * scan on every attempt, and one diagnostic containing every failure. */
    let attempts = std::env::var("COMPANION_TYPE_BLE_CONNECT_ATTEMPTS")
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(4)
        .max(1);
    let retry_delay = env_timeout("COMPANION_TYPE_BLE_CONNECT_RETRY_DELAY_MS", 2_000);
    let mut failures = Vec::new();
    for attempt in 1..=attempts {
        if attempt > 1 {
            sleep(retry_delay).await;
        }
        match connect_native_device_once(requested_device_id,sync_clock,intent).await {
            Ok(device) => {
                eprintln!("BLE initial connect success attempt={attempt}/{attempts}");
                return Ok(device);
            }
            Err(error) => {
                #[cfg(windows)]
                if super::ble_pairing::is_pairing_error(&error) { return Err(error); }
                eprintln!("BLE initial connect failed attempt={attempt}/{attempts} cause={error}");
                failures.push(format!("attempt {attempt}: {error}"));
            }
        }
    }
    Err(format!(
        "BLE initial connect exhausted {attempts} attempts: {}",
        failures.join(" | ")
    ))
}

async fn connect_known_native_device(device: NativeDevice) -> Result<NativeDevice, String> {
    connect_known_native_device_with_clock(device,true).await
}

async fn connect_known_native_device_with_clock(device: NativeDevice,sync_clock:bool) -> Result<NativeDevice,String> {
    connect_known_native_device_setup(device, sync_clock, ConnectionIntent::Normal).await.map(|setup| setup.device)
}

async fn connect_known_native_device_setup(device: NativeDevice,sync_clock:bool,intent:ConnectionIntent) -> Result<NativeConnectionSetup,String> {
    connect_known_native_device_setup_guarded(device,sync_clock,intent,false).await
}

async fn connect_known_native_device_setup_guarded(mut device: NativeDevice,sync_clock:bool,intent:ConnectionIntent,
    require_existing_connection:bool) -> Result<NativeConnectionSetup,String> {
    let device_id = device.device_id();
    let connect_timeout = env_timeout("COMPANION_TYPE_BLE_CONNECT_TIMEOUT_MS", 12_000);
    let discover_timeout = env_timeout("COMPANION_TYPE_BLE_DISCOVER_TIMEOUT_MS", 8_000);
    let started = StdInstant::now();
    #[cfg(windows)]
    let mut setup_preference = None;
    let result = async {
    let connected = timeout(connect_timeout, device.peripheral.is_connected())
        .await
        .map_err(|_| {
            format!(
                "read BLE connection state for {device_id} timed out after {}ms",
                connect_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("read BLE connection state: {err}"))?;
    if require_existing_connection && !connected {
        return Err("Diagnostic warm connection was lost; no reconnect or payload was attempted".into());
    }
    if !connected {
        // WBA may begin its security request immediately on connection.
        // Pair before btleplug opens/enumerates protected GATT services.
        #[cfg(windows)]
        super::ble_pairing::ensure_paired_before_gatt(&device.address, device.address_type).await?;
    }
    // A sealed sync uses the same peer-interval policy for cold and already
    // connected devices. Keep pairing first and request before maintaining
    // the session; warm connections must not acquire the 15ms setup override.
    #[cfg(windows)]
    if intent == ConnectionIntent::SealedSync {
        setup_preference = super::ble_throughput::request_for_sealed_connection_setup(
            &device.address, device.address_type,
        ).await;
    }
    #[cfg(windows)]
    if !device.connection_session.as_ref().is_some_and(|session| session.is_open()) {
        device.connection_session = Some(super::ble_throughput::maintain_connection(
            &device.address, device.address_type,
        ).await?);
    }
    // WinRT's uncached connect/service/descriptor enumeration contains many
    // ATT round trips. Scope the central preference to setup as well as bulk
    // receive. Return its single-owner guard separately: normal user/recorder
    // connections drop it, while a sealed upload can keep the same request.
    #[cfg(windows)]
    if intent == ConnectionIntent::Normal { setup_preference = super::ble_throughput::request_for_connection_setup(
        &device.address, device.address_type,
    ).await; }
    if !connected {
        let connect_begun = StdInstant::now();
        timeout(connect_timeout, device.peripheral.connect())
            .await
            .map_err(|_| {
                format!(
                    "connect BLE device {device_id} timed out after {}ms",
                    connect_timeout.as_millis()
                )
            })?
            .map_err(|err| format!("connect BLE device {device_id}: {err}"))?;
        eprintln!("BLE connection_setup phase=connect elapsed_ms={}", connect_begun.elapsed().as_millis());
    }
    let discovery_begun = StdInstant::now();
    let discovery = async {
        // Sealed receive uses characteristics and WinRT's CCCD subscription API,
        // never raw descriptors. Keep fresh service/characteristic discovery and
        // all normal encryption/identity checks, without enumerating every unused
        // descriptor over ATT before the first original byte can arrive.
        #[cfg(windows)]
        if intent == ConnectionIntent::SealedSync {
            return device.peripheral.discover_services_without_descriptors().await;
        }
        device.peripheral.discover_services().await
    };
    timeout(discover_timeout, discovery)
        .await
        .map_err(|_| {
            format!(
                "discover GATT services for {device_id} timed out after {}ms",
                discover_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("discover GATT services: {err}"))?;
    eprintln!("BLE connection_setup phase=gatt_discovery elapsed_ms={} scope={:?} raw_descriptors={}",
        discovery_begun.elapsed().as_millis(), intent,
        if cfg!(windows) && intent == ConnectionIntent::SealedSync { "not_used_not_enumerated" } else { "ordinary" });
    /* Best-effort clock sync is a backwards-compatible Settings extension.
     * The first 10 bytes are read back unchanged; UTC H/M/S are appended so
     * the board never has to invent a status-bar time. */
    if sync_clock {
        let clock_begun = StdInstant::now();
        let clock_result = sync_device_utc_clock(&device.peripheral).await;
        eprintln!("BLE connection_setup phase=clock_sync elapsed_ms={} success={}",
            clock_begun.elapsed().as_millis(), clock_result.is_ok());
    }
    Ok(())
    }.await;
    if result.is_err() {
        #[cfg(windows)]
        drop(setup_preference.take());
        // A failed connect/discovery can still own WinRT GATT handles. Close
        // them before the next fresh scan instead of leaving a stale attempt
        // in parallel with the retry. This never removes the pairing bond.
        close_native_device(&device).await;
    }
    eprintln!("BLE protected_connection elapsed_ms={} success={} clock_sync={sync_clock}",
        started.elapsed().as_millis(), result.is_ok());
    result.map(|()| NativeConnectionSetup { device, #[cfg(windows)] preference: setup_preference })
}

async fn sync_device_utc_clock(peripheral: &Peripheral) -> Result<(), String> {
    write_device_utc_clock(peripheral).await.map(|_| ())
}

async fn sync_device_utc_clock_verified(peripheral: &Peripheral) -> Result<String, String> {
    let expected = write_device_utc_clock(peripheral).await?;
    let characteristics = peripheral.characteristics();
    let settings = find_characteristic(&characteristics, SETTINGS_UUID)?;
    let read_timeout = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let payload = timeout(read_timeout, peripheral.read(&settings))
        .await
        .map_err(|_| {
            format!(
                "read settings clock readback timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("read settings clock readback: {err}"))?;
    verify_clock_readback(expected, &payload)
}

async fn write_device_utc_clock(peripheral: &Peripheral) -> Result<[u8; 3], String> {
    let characteristics = peripheral.characteristics();
    let settings = find_characteristic(&characteristics, SETTINGS_UUID)?;
    if !settings.properties.contains(CharPropFlags::READ)
        || !settings.properties.contains(CharPropFlags::WRITE)
    {
        return Err("settings must support READ+WRITE for clock sync".to_string());
    }
    let read_timeout = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let mut payload = timeout(read_timeout, peripheral.read(&settings))
        .await
        .map_err(|_| {
            format!(
                "read settings for clock sync timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("read settings for clock sync: {err}"))?;
    if payload.len() < 10 {
        return Err("settings payload too short for clock sync".to_string());
    }
    payload.truncate(10);
    let utc_seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|err| format!("system clock before unix epoch: {err}"))?
        .as_secs()
        % 86_400;
    let expected = [
        (utc_seconds / 3_600) as u8,
        ((utc_seconds / 60) % 60) as u8,
        (utc_seconds % 60) as u8,
    ];
    payload.extend_from_slice(&expected);
    let write_timeout = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);
    timeout(
        write_timeout,
        peripheral.write(&settings, &payload, WriteType::WithResponse),
    )
        .await
        .map_err(|_| {
            format!(
                "write settings clock sync timed out after {}ms",
                write_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("write settings clock sync: {err}"))?;
    Ok(expected)
}

fn verify_clock_readback(expected: [u8; 3], payload: &[u8]) -> Result<String, String> {
    if payload.len() < 13 {
        return Err(format!(
            "settings clock readback is {} bytes; expected at least 13",
            payload.len()
        ));
    }
    let actual = [payload[10], payload[11], payload[12]];
    if actual[0] > 23 || actual[1] > 59 || actual[2] > 59 {
        return Err(format!(
            "settings clock readback is invalid {:02}:{:02}:{:02}",
            actual[0], actual[1], actual[2]
        ));
    }
    let expected_seconds = u32::from(expected[0]) * 3_600
        + u32::from(expected[1]) * 60
        + u32::from(expected[2]);
    let actual_seconds =
        u32::from(actual[0]) * 3_600 + u32::from(actual[1]) * 60 + u32::from(actual[2]);
    let direct = expected_seconds.abs_diff(actual_seconds);
    let circular = direct.min(86_400 - direct);
    if circular > 2 {
        return Err(format!(
            "settings clock readback mismatch wrote={:02}:{:02}:{:02} read={:02}:{:02}:{:02}",
            expected[0], expected[1], expected[2], actual[0], actual[1], actual[2]
        ));
    }
    Ok(format!(
        "UTC write/readback verified {:02}:{:02}:{:02}",
        actual[0], actual[1], actual[2]
    ))
}

async fn reconnect_native_device(
    cached: &NativeDevice,
    requested_device_id: Option<&str>,
) -> Result<NativeDevice, String> {
    let attempts = std::env::var("COMPANION_TYPE_BLE_RECONNECT_ATTEMPTS")
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(4)
        .max(1);
    let mut failures = Vec::new();
    for attempt in 1..=attempts {
        if attempt > 1 {
            sleep(StdDuration::from_secs(3)).await;
        }
        match connect_known_native_device(cached.clone()).await {
            Ok(device) => {
                eprintln!("BLE reconnect cached_success attempt={attempt}/{attempts}");
                return Ok(device);
            }
            Err(error) => {
                #[cfg(windows)]
                if super::ble_pairing::is_pairing_error(&error) { return Err(error); }
                failures.push(format!("attempt {attempt} cached: {error}"));
            }
        }
        match connect_native_device_once(requested_device_id, true, ConnectionIntent::Normal).await {
            Ok(device) => {
                eprintln!("BLE reconnect scan_success attempt={attempt}/{attempts}");
                return Ok(device.device);
            }
            Err(error) => {
                #[cfg(windows)]
                if super::ble_pairing::is_pairing_error(&error) { return Err(error); }
                failures.push(format!("attempt {attempt} scan: {error}"));
            }
        }
    }
    Err(format!(
        "BLE reconnect exhausted {attempts} attempts: {}",
        failures.join(" | ")
    ))
}

async fn connect_native_probe(
    requested_device_id: Option<&str>,
    owner: Option<&OwnedRecorder>,
    expected_peer: Option<super::recording_wire::transport::Peer>,
) -> Result<NativeConnectProbe, String> {
    let begun = StdInstant::now();
    let retained = match owner {
        Some(owner) => {
            retained_offline_connection(
                Some(&owner.device_id),
                owner.start_token(),
                Some(owner.recording_id),
                owner.start_token(),
            )
            .await?
        }
        None => None,
    };
    let mut device = match retained {
        Some(lease) => lease.device,
        None => connect_native_device_with_clock(requested_device_id, false).await?,
    };
    let mut retain_active_recording = false;
    let result = async {
    let characteristics = device.peripheral.characteristics();
    let device_status = Some(read_optional_status(
        &device.peripheral, &characteristics, DEVICE_STATUS_UUID, 20,
    ).await.ok_or_else(|| "未读到设备身份，未把设备标为已连接。".to_string())?);
    let imu_status =
        read_optional_status(&device.peripheral, &characteristics, IMU_STATUS_UUID, 26).await;
    let speaker_status = read_optional_status(
        &device.peripheral,
        &characteristics,
        SPEAKER_STATUS_UUID,
        16,
    )
    .await;
    let identity = parse_device_identity(
        device_status.as_deref(),
        imu_status.as_deref(),
        speaker_status.as_deref(),
    );
    let actual_peer = super::recording_wire::transport::Peer::from_status(
        device_status.as_deref().expect("required device status"))?;
    require_same_recorder(expected_peer.as_ref(), actual_peer.as_ref())?;
    let recorder_active=if owner.is_none() && actual_peer.as_ref().is_some_and(|p|p.pause_control) {
        recorder_control::observe_local_original(&device,actual_peer.as_ref().unwrap()).await?.1
    } else {identity.recording!=Some(false)};
    // Preserve ordinary idle clock sync after ruling out a device-local
    // RUNNING/PAUSED capture. Connecting must not rewrite its original axis.
    if owner.is_none() && expected_peer.is_none() && !recorder_active {
        let _=sync_device_utc_clock(&device.peripheral).await;
    }
    if let Some(key) = owner.and_then(|owner| owner.logical_key.as_ref()) {
        if actual_peer.as_ref().is_none_or(|peer| !peer.logical_control ||
            peer.uid != key.device_uid || peer.epoch != key.format_epoch) {
            return Err("重新连接的录音协议／芯片／格式代次与原会议不同，未接管或消费。".into());
        }
        device.recording_peer = actual_peer.clone();device.user_connection = true;
        device.verified_uid = identity.mcu_uid.clone();device.observed_identity = Some(identity.clone());
    }
    let segmented_recording = actual_peer.is_some();
    let recordings_available = if let Some(owner) = owner {
        if identity.recording == Some(false) {
            owner.verify_closed_device(&device.device_id(), &identity)?;
            let entries = read_owned_closed_catalogue(&device, owner).await?;
            offline_connection_lock()?.forget(&device.device_id(), owner.start_token(), owner.recording_id);
            eprintln!("offline_reconnect_verified recording_id={} original_recorder_finalized=true clock_write=false", owner.recording_id);
            entries.len()
        } else {
            owner.verify_device(&device.device_id(), &identity)?;
            // A live bookmark still requires the original START status.
            let (entries, _) = read_owned_recording_position(&device, owner).await?;
            let previous = offline_connection_lock()?.remember(offline_connection::Lease {
                device: device.clone(), device_id: device.device_id(),
                start_token: owner.start_token(), recording_id: owner.recording_id,
                logical_key: owner.logical_key.clone(),
            })?;
            if let Some(previous) = previous {
                if normalize_device_id(&previous.device_id) != normalize_device_id(&device.device_id()) {
                    close_native_device(&previous.device).await;
                }
            }
            retain_active_recording = true;
            eprintln!("offline_reconnect_verified recording_id={} original_start_token={} connection_retained=true clock_write=false",
                owner.recording_id, owner.start_token());
            entries.len()
        }
    } else {
        // A public status read alone cannot establish that this paired device
        // is ready for recording. Require the protected catalogue as well.
        let catalog = read_recording_catalog(&device, &characteristics).await?;
        if segmented_recording != catalog.peer.is_some()
            || catalog.peer.as_ref().is_some_and(|p| identity.mcu_uid.as_deref() != Some(hex_lower(&p.uid).as_str())) {
            return Err("录音目录与刚读取的实际设备身份/协议不一致，未把设备标为可同步。".into());
        }
        device.recording_peer = catalog.peer;
        catalog.entries.len()
    };
    let probe = NativeConnectProbe {
        device_id: device.device_id(),
        service_count: device.service_uuids.len(),
        characteristic_count: characteristics.len(),
        recordings_available,
        identity,
        owned_recording_connection_retained: retain_active_recording,
        segmented_recording,
    };
    Ok(probe)
    }.await;
    if result.is_err() {
        if let Some(owner) = owner {
            offline_connection_lock()?.forget(
                &device.device_id(),
                owner.start_token(),
                owner.recording_id,
            );
        }
        close_native_device(&device).await;
    } else if !retain_active_recording {
        device.user_connection = true;
        device.verified_uid = result.as_ref().ok().and_then(|probe| probe.identity.mcu_uid.clone());
        if let Some(peer) = device.recording_peer.as_ref() {
            *VERIFIED_SEGMENTED_RECORDER.lock().map_err(|_| "连续录音身份状态锁不可用")? =
                Some((device.device_id(), peer.clone()));
        }
        remember_prepared_device(device).await?;
    }
    if owner.is_some() {
        eprintln!(
            "offline_reconnect_native_elapsed_ms={} verified={}",
            begun.elapsed().as_millis(),
            result.is_ok()
        );
    }
    result
}

fn ble_name_request(command: u8, request_id: u32, name: Option<&str>) -> Result<[u8; BLE_NAME_CONFIG_BYTES], String> {
    let mut request = [0u8; BLE_NAME_CONFIG_BYTES];
    request[0] = 1;
    request[1] = command;
    request[4..8].copy_from_slice(&request_id.to_le_bytes());
    request[9] = BLE_NAME_MAX_BYTES as u8;
    if let Some(name) = name {
        if !crate::companion_v1::companion_ble_name_is_valid(name) {
            return Err("invalid Companion BLE name".to_string());
        }
        request[8] = name.len() as u8;
        request[12..12 + name.len()].copy_from_slice(name.as_bytes());
    }
    Ok(request)
}

fn parse_ble_name_receipt(
    payload: &[u8],
    expected_command: u8,
    expected_request_id: u32,
) -> Result<String, String> {
    if payload.len() != BLE_NAME_CONFIG_BYTES {
        return Err(format!(
            "BLE name receipt is {} bytes; expected {BLE_NAME_CONFIG_BYTES}",
            payload.len()
        ));
    }
    let request_id = u32::from_le_bytes(payload[4..8].try_into().unwrap());
    if payload[0] != 1 || payload[1] != expected_command || request_id != expected_request_id {
        return Err(format!(
            "BLE name receipt identity mismatch schema={} command={} request_id={request_id}",
            payload[0], payload[1]
        ));
    }
    if payload[9] != BLE_NAME_MAX_BYTES as u8 {
        return Err(format!("BLE name receipt max_len={} is invalid", payload[9]));
    }
    if payload[10] != 0 {
        return Err(format!("device rejected BLE name command with status={}", payload[10]));
    }
    let name_len = payload[8] as usize;
    if name_len == 0 || name_len > BLE_NAME_MAX_BYTES {
        return Err(format!("BLE name receipt name_len={name_len} is invalid"));
    }
    let name = std::str::from_utf8(&payload[12..12 + name_len])
        .map_err(|_| "BLE name receipt is not UTF-8".to_string())?;
    if !crate::companion_v1::companion_ble_name_is_valid(name) {
        return Err("BLE name receipt violates the product name policy".to_string());
    }
    Ok(name.to_string())
}

async fn write_ble_name_command(
    peripheral: &Peripheral,
    characteristic: &Characteristic,
    command: u8,
    request_id: u32,
    name: Option<&str>,
) -> Result<String, String> {
    let payload = ble_name_request(command, request_id, name)?;
    let write_timeout = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);
    timeout(
        write_timeout,
        peripheral.write(characteristic, &payload, WriteType::WithResponse),
    )
    .await
    .map_err(|_| format!("BLE name command {command} write timed out"))?
    .map_err(|error| format!("BLE name command {command} write failed: {error}"))?;

    let deadline = StdInstant::now() + env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let mut last_error = "device did not publish a receipt".to_string();
    loop {
        let remaining = deadline.saturating_duration_since(StdInstant::now());
        if remaining.is_zero() {
            return Err(format!("BLE name command {command} readback failed: {last_error}"));
        }
        let read = timeout(remaining.min(StdDuration::from_secs(2)), peripheral.read(characteristic))
            .await;
        match read {
            Ok(Ok(bytes)) => match parse_ble_name_receipt(&bytes, command, request_id) {
                Ok(active_name) => return Ok(active_name),
                Err(error) => last_error = error,
            },
            Ok(Err(error)) => last_error = format!("read failed: {error}"),
            Err(_) => last_error = "read timed out".to_string(),
        }
        sleep(StdDuration::from_millis(50)).await;
    }
}

async fn configure_native_ble_name(
    requested_device_id: Option<&str>,
    requested_name: Option<&str>,
    reset: bool,
) -> Result<CompanionBleNameReport, String> {
    let device = connect_native_device(requested_device_id).await?;
    let device_id = device.device_id();
    let result = async {
        let characteristics = device.peripheral.characteristics();
        let characteristic = find_characteristic(&characteristics, BLE_NAME_CONFIG_UUID)?;
        if !characteristic.properties.contains(CharPropFlags::READ)
            || !characteristic.properties.contains(CharPropFlags::WRITE)
        {
            return Err("BLE name config must support READ+WRITE".to_string());
        }
        let seed = u32::from_le_bytes(
            Uuid::new_v4().as_bytes()[..4]
                .try_into()
                .expect("UUID prefix is four bytes"),
        )
        .max(1);
        let active_name = if reset {
            write_ble_name_command(
                &device.peripheral,
                &characteristic,
                BLE_NAME_RESET,
                seed,
                None,
            )
            .await?
        } else {
            let requested_name = requested_name.ok_or_else(|| "BLE name is missing".to_string())?;
            write_ble_name_command(
                &device.peripheral,
                &characteristic,
                BLE_NAME_STAGE,
                seed,
                Some(requested_name),
            )
            .await?;
            let active_name = write_ble_name_command(
                &device.peripheral,
                &characteristic,
                BLE_NAME_APPLY,
                seed.wrapping_add(1).max(1),
                None,
            )
            .await?;
            if active_name != requested_name {
                return Err(format!(
                    "BLE name readback mismatch requested={requested_name:?} active={active_name:?}"
                ));
            }
            active_name
        };
        if reset && active_name != crate::companion_v1::COMPANION_V1_DEFAULT_BLE_NAME {
            return Err(format!(
                "BLE name reset readback mismatch active={active_name:?}"
            ));
        }
        Ok(CompanionBleNameReport {
            device_id: device_id.clone(),
            active_name,
        })
    }
    .await;
    finish_native_device_operation(device, result.is_ok()).await?;
    result
}

async fn oobe_native_probe(
    requested_device_id: Option<&str>,
) -> Result<CompanionOobeProbeReport, String> {
    let device = connect_native_device(requested_device_id).await?;
    let characteristics = device.peripheral.characteristics();
    let services = device.peripheral.services();
    let missing_required_gatt = required_oobe_gatt_missing(&characteristics);

    let device_status =
        read_optional_status(&device.peripheral, &characteristics, DEVICE_STATUS_UUID, 20).await;
    let imu_status =
        read_optional_status(&device.peripheral, &characteristics, IMU_STATUS_UUID, 26).await;
    let speaker_status = read_optional_status(
        &device.peripheral,
        &characteristics,
        SPEAKER_STATUS_UUID,
        16,
    )
    .await;
    let identity = parse_device_identity(
        device_status.as_deref(),
        imu_status.as_deref(),
        speaker_status.as_deref(),
    );
    let (recordings_available, recording_list_error) =
        match read_recording_list(&device, &characteristics).await {
            Ok(entries) => (entries.len(), None),
            Err(error) => (0, Some(error)),
        };
    let (clock_sync_evidence, clock_sync_error) =
        match sync_device_utc_clock_verified(&device.peripheral).await {
            Ok(evidence) => (Some(evidence), None),
            Err(error) => (None, Some(error)),
        };
    let report = CompanionOobeProbeReport {
        device_id: device.device_id(),
        service_count: services.len(),
        characteristic_count: characteristics.len(),
        recordings_available,
        identity,
        device_status_read: device_status.is_some(),
        imu_status_read: imu_status.is_some(),
        speaker_status_read: speaker_status.is_some(),
        missing_required_gatt,
        recording_list_error,
        clock_sync_error,
        clock_sync_evidence,
    };
    let ready = report.device_status_read && report.recording_list_error.is_none()
        && report.missing_required_gatt.is_empty();
    finish_native_device_operation(device, ready).await?;
    Ok(report)
}

fn required_oobe_gatt_missing(
    characteristics: &std::collections::BTreeSet<Characteristic>,
) -> Vec<String> {
    [
        ("device_status", DEVICE_STATUS_UUID),
        ("settings", SETTINGS_UUID),
        ("ble_name_config", BLE_NAME_CONFIG_UUID),
        ("meeting_control", MEETING_CONTROL_UUID),
        ("meeting_status", MEETING_STATUS_UUID),
        ("recording_control", RECORDING_CONTROL_UUID),
        ("recording_list", RECORDING_LIST_UUID),
        ("recording_chunk_pull", RECORDING_CHUNK_PULL_UUID),
        ("delete_privacy", DELETE_PRIVACY_UUID),
    ]
    .into_iter()
    .filter(|(_, uuid)| {
        !characteristics
            .iter()
            .any(|characteristic| characteristic.uuid == *uuid)
    })
    .map(|(name, uuid)| format!("{name}({uuid})"))
    .collect()
}

async fn read_optional_status(
    peripheral: &Peripheral,
    characteristics: &std::collections::BTreeSet<Characteristic>,
    uuid: Uuid,
    minimum_length: usize,
) -> Option<Vec<u8>> {
    let characteristic = find_characteristic(characteristics, uuid).ok()?;
    if !characteristic.properties.contains(CharPropFlags::READ) {
        return None;
    }
    timeout(OPTIONAL_STATUS_READ_TIMEOUT, async {
        let first = peripheral.read(&characteristic).await.ok()?;
        if !status_needs_publish_retry(&first, minimum_length) {
            return Some(first);
        }
        // The encrypted event is delivered before comp_link_poll publishes
        // its first status snapshot on WBA. Give that task one short turn,
        // while keeping both reads inside the single 2.5 s probe budget.
        sleep(StdDuration::from_millis(120)).await;
        peripheral.read(&characteristic).await.ok()
    })
    .await
    .ok()?
}

fn status_needs_publish_retry(payload: &[u8], minimum_length: usize) -> bool {
    payload.len() < minimum_length || payload.first().copied().unwrap_or(0) == 0
}

fn parse_device_identity(
    device_status: Option<&[u8]>,
    imu_status: Option<&[u8]>,
    speaker_status: Option<&[u8]>,
) -> CompanionDeviceIdentity {
    let device = device_status.filter(|value| value.len() >= 20 && value[0] == 1);
    let imu = imu_status.filter(|value| value.len() >= 26 && value[0] == 1);
    let speaker = speaker_status.filter(|value| value.len() >= 16 && value[0] == 1);
    let imu_state = imu
        .map(|value| value[1])
        .filter(|state| (1..=3).contains(state));
    let speaker_state = speaker
        .map(|value| value[1])
        .filter(|state| (1..=5).contains(state));
    let wba_tail = device.filter(|value| value.len() >= 36);
    let mcu_uid = wba_tail.and_then(|value| {
        let uid = &value[20..32];
        if uid.iter().all(|byte| *byte == 0) || uid.iter().all(|byte| *byte == 0xff) {
            None
        } else {
            Some(uid.iter().map(|byte| format!("{byte:02x}")).collect())
        }
    });
    CompanionDeviceIdentity {
        firmware_version: device.map(|value| u32::from_le_bytes(value[4..8].try_into().unwrap())),
        build_id: device.map(|value| u32::from_le_bytes(value[8..12].try_into().unwrap())),
        board_id: device.map(|value| u32::from_le_bytes(value[12..16].try_into().unwrap())),
        mcu_uid,
        ui_generation: wba_tail
            .map(|value| u32::from_le_bytes(value[32..36].try_into().unwrap()))
            .filter(|generation| *generation != 0),
        recording_capacity: device.and_then(super::recording_capacity::parse),
        recording: device.and_then(|value| match value[1] {
            0 => Some(false),
            1 => Some(true),
            _ => None,
        }),
        imu_supported: imu_state.map(|state| state != 1),
        imu_online: imu_state.map(|state| state == 2),
        imu_sample_hz: imu_state
            .and_then(|_| imu.map(|value| u16::from_le_bytes(value[4..6].try_into().unwrap()))),
        speaker_supported: speaker_state.map(|state| state != 1),
        speaker_online: speaker_state.map(|state| matches!(state, 2..=4)),
        speaker_volume: speaker_state.and_then(|_| speaker.map(|value| value[3])),
    }
}

fn should_auto_pull_recordings(
    recording: Option<bool>,
    recordings_available: usize,
) -> bool {
    recording == Some(false) && recordings_available > 0
}

fn meeting_control_request(command: u8, request_id: u32, max_seconds: u16) -> [u8; 12] {
    let mut payload = [0u8; 12];
    payload[0] = 1;
    payload[1] = command;
    payload[4..8].copy_from_slice(&request_id.to_le_bytes());
    payload[8..10].copy_from_slice(&max_seconds.to_le_bytes());
    payload[10] = MEETING_CONTROL_PROFILE_BOARD_MIC;
    payload
}

fn speaker_control_request(request_id: u32, volume_percent: u8, prompt_id: u8) -> [u8; 12] {
    let mut payload = [0u8; 12];
    payload[0] = 1;
    payload[1] = 1;
    payload[2] = volume_percent;
    payload[3] = prompt_id;
    payload[4..8].copy_from_slice(&request_id.to_le_bytes());
    payload
}

fn parse_speaker_status(payload: &[u8]) -> Result<(u8, u8, u8, u32), String> {
    if payload.len() < 16 || payload[0] != 1 {
        return Err(format!(
            "speaker_status wire mismatch: length={} schema={}",
            payload.len(),
            payload.first().copied().unwrap_or(0)
        ));
    }
    Ok((
        payload[1],
        payload[2],
        payload[3],
        u32::from_le_bytes(payload[4..8].try_into().unwrap()),
    ))
}

async fn speaker_prompt_native(
    requested_device_id: Option<&str>,
    volume_percent: u8,
    prompt_id: u8,
) -> Result<CompanionSpeakerControlReport, String> {
    if volume_percent > 100 || prompt_id > 3 {
        return Err("speaker prompt requires volume<=100 and prompt_id<=3".to_string());
    }
    let device = connect_native_device(requested_device_id).await?;
    let characteristics = device.peripheral.characteristics();
    let control = find_characteristic(&characteristics, SPEAKER_CONTROL_UUID)?;
    let status = find_characteristic(&characteristics, SPEAKER_STATUS_UUID)?;
    if !control.properties.contains(CharPropFlags::WRITE)
        || !status.properties.contains(CharPropFlags::READ)
    {
        return Err("speaker control requires WRITE control and READ status".to_string());
    }
    let mut request_id = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    if request_id == 0 {
        request_id = 1;
    }
    device
        .peripheral
        .write(
            &control,
            &speaker_control_request(request_id, volume_percent, prompt_id),
            WriteType::WithResponse,
        )
        .await
        .map_err(|err| format!("write speaker prompt: {err}"))?;
    let deadline = StdInstant::now() + StdDuration::from_secs(5);
    let accepted = loop {
        let payload = device
            .peripheral
            .read(&status)
            .await
            .map_err(|err| format!("read speaker status: {err}"))?;
        let parsed = parse_speaker_status(&payload)?;
        if parsed.3 == request_id {
            break parsed;
        }
        if StdInstant::now() >= deadline {
            return Err(format!("speaker status timeout request_id={request_id}"));
        }
        sleep(StdDuration::from_millis(40)).await;
    };
    close_native_device(&device).await;
    if accepted.1 != 0 || !(2..=4).contains(&accepted.0) {
        return Err(format!(
            "board rejected speaker prompt request_id={request_id} state={} error={}",
            accepted.0, accepted.1
        ));
    }
    Ok(CompanionSpeakerControlReport {
        device_id: device.device_id(),
        state: accepted.0,
        volume_percent: accepted.2,
    })
}

pub(crate) fn meeting_idempotency_request_id(session_key: &str, command: u8) -> u32 {
    /* Stable FNV-1a over the product session identity and command.  A retry of
     * the same UI action therefore reaches firmware with the same request id,
     * while START/STOP/FINALIZE remain distinct state transitions. */
    let mut hash = 0x811c_9dc5_u32;
    for byte in session_key
        .as_bytes()
        .iter()
        .copied()
        .chain(std::iter::once(command))
    {
        hash ^= u32::from(byte);
        hash = hash.wrapping_mul(0x0100_0193);
    }
    if hash == 0 {
        1
    } else {
        hash
    }
}

async fn read_owned_recording_position(
    device: &NativeDevice,
    owner: &OwnedRecorder,
) -> Result<(Vec<RecordingEntry>, u64), String> {
    if normalize_device_id(&device.device_id()) != normalize_device_id(&owner.device_id) {
        return Err("重点的设备身份不匹配。".into());
    }
    let chars = device.peripheral.characteristics();
    let status = find_characteristic(&chars, MEETING_STATUS_UUID)?;
    let payload = bounded_ble_result(
        "read owned meeting status",
        StdDuration::from_secs(8),
        device.peripheral.read(&status),
    )
    .await?;
    let observed = parse_meeting_status(&payload)?;
    owner.verify_status(&observed)?;
    if owner.logical_key.is_some() { return Ok((Vec::new(),u64::from(observed.duration_ms))); }
    let mut notifications = device
        .peripheral
        .notifications()
        .await
        .map_err(|e| format!("recording notifications: {e}"))?;
    let entries = refresh_recording_list(&device, &chars, &mut notifications).await?;
    let entry = entries
        .iter()
        .find(|e| {
            e.recording_id == owner.recording_id
                && e.sync_state == RECORDING_SYNC_TRANSFER_ACTIVE
                && e.codec == RECORDING_CODEC_OPUS16
                && e.source_mode == RECORDING_SOURCE_MIC_SAI
                && e.total_length > 12
                && e.duration_ms > 0
        })
        .ok_or("设备尚无这场录音的已保存时间点，请稍后重试。")?;
    let position_ms = u64::from(entry.duration_ms);
    let payload = bounded_ble_result(
        "recheck owned meeting status",
        StdDuration::from_secs(8),
        device.peripheral.read(&status),
    )
    .await?;
    owner.verify_status(&parse_meeting_status(&payload)?)?;
    Ok((entries, position_ms))
}

async fn read_owned_closed_catalogue(
    device: &NativeDevice, owner: &OwnedRecorder,
) -> Result<Vec<RecordingEntry>, String> {
    let chars = device.peripheral.characteristics();
    let status = find_characteristic(&chars, MEETING_STATUS_UUID)?;
    let before = bounded_ble_result("read finalized original meeting", StdDuration::from_secs(8),
        device.peripheral.read(&status)).await?;
    let before = parse_meeting_status(&before)?;
    if let Some(key) = owner.logical_key.as_ref() {
        let identity = MeetingControlIdentity::for_session(&owner.session_id,owner.recording_id);
        let mut identity = identity;identity.logical_key = Some(key.clone());
        verify_meeting_control_target(&before,&identity)?;
        if before.state != MEETING_STATE_FINALIZED {return Err("原逻辑录音仍在采音，未声明停止。".into());}
        let mut catalog = read_recording_catalog(device,&chars).await?;
        let peer = catalog.peer.as_ref().ok_or("原逻辑录音目录协议不可用。")?;
        if peer.uid != key.device_uid || peer.epoch != key.format_epoch {return Err("原逻辑录音目录身份改变。".into());}
        let after = bounded_ble_result("recheck finalized logical meeting",StdDuration::from_secs(3),device.peripheral.read(&status)).await?;
        let after = parse_meeting_status(&after)?;verify_meeting_control_target(&after,&identity)?;
        if after.state != before.state || after.duration_ms != before.duration_ms || after.request_id != before.request_id {
            return Err("原逻辑录音结束状态仍在变化，未接管其它会议。".into());
        }
        catalog.entries.retain(|e| e.segment.as_ref().is_some_and(|d| &d.key == key));
        return Ok(catalog.entries);
    }
    let mut notifications = device.peripheral.notifications().await
        .map_err(|error| format!("recording notifications: {error}"))?;
    let entries = refresh_recording_list(&device, &chars, &mut notifications).await?;
    let entry = entries.iter().find(|entry| entry.recording_id == owner.recording_id)
        .ok_or("设备没有原录音的封存目录，未声明结束或消费。")?;
    let after = bounded_ble_result("recheck finalized original meeting", StdDuration::from_secs(8),
        device.peripheral.read(&status)).await?;
    let after = parse_meeting_status(&after)?;
    owner.verify_closed_catalogue(&before, entry, &after).map_err(|error| {
        eprintln!(concat!(
            "offline_reconnect_catalogue rejected=true original_id={} original_start_token={} ",
            "before_state={} before_error={} before_token={} before_id={} before_ms={} before_sync={} ",
            "after_state={} after_error={} after_token={} after_id={} after_ms={} after_sync={} ",
            "entry_id={} entry_ms={} entry_sync={} entry_codec={} entry_source={} entry_bytes={} entry_hash_present={}"),
            owner.recording_id, owner.start_token(),
            before.state, before.last_error, before.request_id, before.meeting_id, before.duration_ms, before.sync_state,
            after.state, after.last_error, after.request_id, after.meeting_id, after.duration_ms, after.sync_state,
            entry.recording_id, entry.duration_ms, entry.sync_state, entry.codec, entry.source_mode,
            entry.total_length, entry.sha256_prefix.iter().any(|byte| *byte != 0));
        error
    })?;
    Ok(entries)
}

/// Native read-only observation for the ordinary offlineStore START route.
/// Both status reads must still name this session's original START token.
pub(crate) fn live_recording_stamp(device_id: &str, session_id: &str, recording_id:u32,
    key: Option<&crate::companion_v1::CompanionV1RecordingKey>, journal:Option<&super::recorder_control::Journal>)
    -> Result<super::recording_bookmarks::LiveStamp,String> {
    let begun=StdInstant::now();
    let position_ms = run_native_blocking(async {
        // A bookmark observes a running recorder. Rewriting Settings here was
        // unnecessary and could wait eight seconds for its busy clock service.
        let token=meeting_idempotency_request_id(session_id,1);
        let current=journal.and_then(|j|j.pending.as_ref().map(|p|p.request)
            .or_else(||j.confirmed.as_ref().map(|c|c.request))).unwrap_or(token);
        let retained=retained_offline_connection(Some(device_id),token,Some(recording_id),current).await?;
        let reused=retained.is_some();
        let device=match retained {
            Some(lease)=>lease.device,
            None=>connect_native_device_with_clock(Some(device_id),false).await?,
        };
        let logical_key = key.map(super::recording_wire::SessionKey::from_public).transpose()?;
        let owner = OwnedRecorder { journal:journal.cloned(), device_id: device_id.into(), session_id: session_id.into(), recording_id, mcu_uid: None, logical_key: logical_key.clone() };
        let result = read_owned_recording_position(&device, &owner).await.map(|(_, position)| position);
        if result.is_ok() && !reused {
            offline_connection_lock()?.remember(offline_connection::Lease {
                device:device.clone(),device_id:device_id.into(),start_token:token,recording_id,
                logical_key,
            })?;
        } else if result.is_err() {
            offline_connection_lock()?.forget(device_id,token,recording_id);
            close_native_device(&device).await;
        }
        eprintln!("bookmark_connection_reused={reused}");
        result
    })?;
    eprintln!("bookmark_native_read_elapsed_ms={} recording_id={} board_position_ms={} clock_write=false",
        begun.elapsed().as_millis(),recording_id,position_ms);
    Ok(super::recording_bookmarks::LiveStamp { session_id:session_id.into(), device_id:device_id.into(),
        recording_id, position_ms })
}

pub(crate) fn bookmarks_probe_preflight(device_id:&str, expected_uid:&str)->Result<(),String> {
    run_native_blocking(async {
        let device=connect_native_device_with_clock(Some(device_id),false).await?;
        let result=async {
            let chars=device.peripheral.characteristics();
            let payload=read_optional_status(&device.peripheral,&chars,DEVICE_STATUS_UUID,84).await;
            let identity=parse_device_identity(payload.as_deref(),None,None);
            if normalize_device_id(&device.device_id()) != normalize_device_id(device_id)
                || identity.mcu_uid.as_deref() != Some(expected_uid) || identity.recording != Some(false) {
                return Err("实板身份或空闲状态未确认，未开始测试录音。".into());
            }
            let mut notifications=device.peripheral.notifications().await.map_err(|e|e.to_string())?;
            let entries=refresh_recording_list(&device,&chars,&mut notifications).await?;
            if !entries.is_empty() { return Err("设备仍有录音，未自动收录或覆盖这些录音。".into()); }
            Ok(())
        }.await;
        close_native_device(&device).await;
        result
    })
}

async fn bounded_ble_result<F, T, E>(
    operation: &str,
    budget: StdDuration,
    future: F,
) -> Result<T, String>
where
    F: Future<Output = Result<T, E>>,
    E: std::fmt::Display,
{
    if budget.is_zero() {
        return Err(format!("{operation} has no remaining deadline"));
    }
    timeout(budget, future)
        .await
        .map_err(|_| format!("{operation} timed out after {}ms", budget.as_millis()))?
        .map_err(|error| format!("{operation}: {error}"))
}

fn remaining_deadline_budget(deadline: StdInstant, maximum: StdDuration) -> StdDuration {
    deadline
        .saturating_duration_since(StdInstant::now())
        .min(maximum)
}

fn combine_operation_and_cleanup<T>(
    operation: Result<T, String>,
    cleanup: Result<(), String>,
) -> Result<T, String> {
    match (operation, cleanup) {
        (Ok(value), Ok(())) => Ok(value),
        (Err(error), _) => Err(error),
        (Ok(_), Err(error)) => Err(error),
    }
}

fn parse_meeting_status(payload: &[u8]) -> Result<MeetingStatus, String> {
    if payload.len() < 28 {
        return Err(format!(
            "meeting_status payload too short: {} < 28",
            payload.len()
        ));
    }
    if payload[0] != 1 {
        return Err(format!("meeting_status schema mismatch: {}", payload[0]));
    }
    Ok(MeetingStatus {
        pause_status: if payload.len()==80 {Some(super::recording_wire::control::PauseStatus::decode(payload)?)} else {None},
        state: payload[1],
        last_error: payload[2],
        request_id: u32::from_le_bytes(payload[8..12].try_into().unwrap()),
        meeting_id: u32::from_le_bytes(payload[12..16].try_into().unwrap()),
        duration_ms: u32::from_le_bytes(payload[20..24].try_into().unwrap()),
        sync_state: payload[24],
        logical_key: super::recording_wire::control::status(payload)?,
    })
}

async fn meeting_control_native(
    requested_device_id: Option<&str>,
    command: u8,
    request_id: u32,
    max_seconds: u16,
    start_token: u32,
    expected_identity: Option<MeetingControlIdentity>,
) -> Result<CompanionMeetingControlReport, String> {
    let (report, device) = meeting_control_native_owned(
        requested_device_id, command, request_id, max_seconds, start_token, expected_identity,
    ).await?;
    if command != 1 {
        finish_native_device_operation(device, true).await?;
    }
    Ok(report)
}

async fn meeting_control_native_owned(
    requested_device_id: Option<&str>,
    command: u8,
    request_id: u32,
    max_seconds: u16,
    start_token: u32,
    expected_identity: Option<MeetingControlIdentity>,
) -> Result<(CompanionMeetingControlReport, NativeDevice), String> {
    if !(1..=3).contains(&command) {
        return Err(format!("unsupported V1 meeting command={command}"));
    }
    if command != 1 && expected_identity.as_ref().is_none_or(|identity| identity.recording_id == 0) {
        return Err("原录音缺少设备录音编号，未连接设备或发送停止命令。".into());
    }
    // STOP/FINALIZE must not write unrelated settings while the mic is active.
    // Ordinary connection and START keep their existing clock synchronisation.
    let retained=retained_offline_connection(requested_device_id,start_token,
        expected_identity.as_ref().map(|identity| identity.recording_id),request_id).await?;
    let expected_identity = expected_identity.or_else(|| retained.as_ref().map(|lease|
        MeetingControlIdentity { recording_id: lease.recording_id, request_ids: [start_token; 3], logical_key: lease.logical_key.clone() }));
    let mut device=match retained {
        Some(lease)=>lease.device,
        None=>connect_native_device_with_clock(requested_device_id,command==1).await?,
    };
    let result = async {
    let characteristics = device.peripheral.characteristics();
    let control = find_characteristic(&characteristics, MEETING_CONTROL_UUID)?;
    let status = find_characteristic(&characteristics, MEETING_STATUS_UUID)?;
    let identity_wire = read_optional_status(&device.peripheral,&characteristics,DEVICE_STATUS_UUID,36).await;
    let peer = identity_wire.as_deref().map(super::recording_wire::transport::Peer::from_status).transpose()?.flatten();
    if expected_identity.as_ref().is_some_and(|id| id.logical_key.is_some())
        && peer.as_ref().is_none_or(|p| !p.logical_control) {
        return Err("原会议使用逻辑录音协议，当前连接未确认同一协议；未发送控制命令。".into());
    }
    let control_wire = if let Some(p) = peer.as_ref().filter(|p| p.logical_control) {
        super::recording_wire::control::request(p,
            expected_identity.as_ref().and_then(|id| id.logical_key.as_ref()),
            command,request_id,start_token,max_seconds)?.to_vec()
    } else { meeting_control_request(command,request_id,max_seconds).to_vec() };
    // A fresh connection after restart has no retained Lease. It still belongs
    // to the original meeting: read protected status before any control write.
    if let Some(identity) = expected_identity.as_ref() {
        let observed=bounded_ble_result("verify original recorder identity",StdDuration::from_secs(8),
            device.peripheral.read(&status)).await?;
        let observed=parse_meeting_status(&observed)?;
        verify_meeting_control_target(&observed, identity)?;
    }
    if command == 1 {
        let payload=read_optional_status(&device.peripheral,&characteristics,DEVICE_STATUS_UUID,20).await;
        if let Some(capacity)=payload.as_deref().and_then(super::recording_capacity::parse) {
            // Busy may be an already accepted START retried with the exact
            // request ID. Let firmware resolve that idempotently; never turn
            // a lost notification into a new, conflicting start request.
            if !capacity.busy {super::recording_capacity::check(&capacity,max_seconds)?;}
        }
    }
    if !control.properties.contains(CharPropFlags::WRITE) {
        return Err("meeting_control must support WRITE".to_string());
    }
    if !status.properties.contains(CharPropFlags::NOTIFY) {
        return Err("meeting_status must support NOTIFY".to_string());
    }
    let status_timeout = env_timeout("COMPANION_TYPE_MEETING_STATUS_TIMEOUT_MS", 60_000);
    let deadline = StdInstant::now() + status_timeout;
    let read_timeout = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let write_timeout = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);
    let mut notifications = bounded_ble_result(
        "open meeting_status notifications",
        remaining_deadline_budget(deadline, read_timeout),
        device.peripheral.notifications(),
    )
    .await?;
    bounded_ble_result(
        "subscribe meeting_status",
        remaining_deadline_budget(deadline, read_timeout),
        device.peripheral.subscribe(&status),
    )
    .await?;
    bounded_ble_result(
        &format!("write V1 meeting_control command={command}"),
        remaining_deadline_budget(deadline, write_timeout),
        device.peripheral.write(
            &control,
            &control_wire,
            WriteType::WithResponse,
        ),
    )
    .await?;

    let expected_state = if command == 1 {
        MEETING_STATE_RECORDING
    } else {
        MEETING_STATE_FINALIZED
    };
    let observed = loop {
        if StdInstant::now() >= deadline {
            return Err(format!(
                "meeting_status timeout command={command} request_id={request_id} expected_state={expected_state}"
            ));
        }

        /* WinRT occasionally drops a notify while the single-BUSY display or
         * NOR task is active.  MeetingStatus is READ+NOTIFY, so poll the same
         * authoritative value as a loss-recovery path instead of resending the
         * control command and risking a second recording. */
        let notified = match timeout(
            remaining_deadline_budget(deadline, StdDuration::from_millis(700)),
            notifications.next(),
        )
        .await
        {
            Ok(Some(notification)) if notification.uuid == MEETING_STATUS_UUID => {
                Some(notification.value)
            }
            Ok(Some(_)) | Err(_) => None,
            Ok(None) => {
                return Err("meeting_status notification stream ended".to_string());
            }
        };
        let payload = match notified {
            Some(payload) => payload,
            None => {
                let read_budget = remaining_deadline_budget(
                    deadline,
                    env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000),
                );
                bounded_ble_result(
                    "read meeting_status fallback",
                    read_budget,
                    device.peripheral.read(&status),
                )
                .await?
            }
        };
        let parsed = parse_meeting_status(&payload)?;
        if parsed.request_id != request_id {
            continue;
        }
        if parsed.last_error != 0 {
            return Err(meeting_control_failure(parsed.last_error, command, request_id));
        }
        if let Some(peer) = peer.as_ref().filter(|peer| peer.logical_control) {
            if parsed.state == expected_state && parsed.logical_key.as_ref().is_none_or(|key|
                key.device_uid != peer.uid || key.format_epoch != peer.epoch) {
                return Err("录音确认缺少当前芯片／格式代次的逻辑会话身份。".into());
            }
        }
        if let Some(identity) = expected_identity.as_ref() {
            verify_meeting_control_target(&parsed, identity)?;
        }
        /* STOP is acknowledged before the rec-task commits the journal.
         * Ignore that honest intermediate recording state and wait for the
         * later status emitted by the real recording-list boundary. */
        if parsed.state == expected_state && parsed.meeting_id != 0 {
            break parsed;
        }
    };

    let _ = bounded_ble_result(
        "unsubscribe meeting_status",
        StdDuration::from_secs(1),
        device.peripheral.unsubscribe(&status),
    )
    .await;
    if command==1 {
        if let Some(peer) = peer.filter(|p| p.logical_control) {
            device.verified_uid = Some(hex_lower(&peer.uid));device.recording_peer = Some(peer.clone());
            device.user_connection = true;
            device.observed_identity = Some(parse_device_identity(identity_wire.as_deref(),None,None));
            *VERIFIED_SEGMENTED_RECORDER.lock().map_err(|_| "连续录音身份锁不可用")? = Some((device.device_id(),peer));
        }
        let previous=offline_connection_lock()?.remember(offline_connection::Lease {
            device:device.clone(),device_id:device.device_id(),start_token,recording_id:observed.meeting_id,
            logical_key: observed.logical_key.clone(),
        })?;
        if let Some(previous)=previous {
            if normalize_device_id(&previous.device_id)!=normalize_device_id(&device.device_id()) {
                close_native_device(&previous.device).await;
            }
        }
    } else {
        // Transfer the stopped connection to the caller. Ownership of the
        // active recorder ends only after the matching finalized status.
        offline_connection_lock()?.forget(&device.device_id(),start_token,observed.meeting_id);
    }
    Ok(CompanionMeetingControlReport {
        device_id: device.device_id(),
        request_id,
        state: observed.state,
        last_error: observed.last_error,
        meeting_id: observed.meeting_id,
        duration_ms: observed.duration_ms,
        sync_state: observed.sync_state,
        logical_key: observed.logical_key,
    })
    }.await;
    if result.is_err() {
        // A failed command/status verification can still own a live WinRT
        // object. Close it; a normal retry rechecks the same START identity.
        close_native_device(&device).await;
    }
    result.map(|report| (report, device))
}

fn verify_meeting_control_target(
    status: &MeetingStatus,
    identity: &MeetingControlIdentity,
) -> Result<(), String> {
    if identity.recording_id == 0 || status.meeting_id != identity.recording_id
        || identity.logical_key.as_ref().is_some_and(|key| status.logical_key.as_ref() != Some(key))
        || status.request_id == 0 || !identity.request_ids.contains(&status.request_id)
        || !matches!(status.state, MEETING_STATE_RECORDING | MEETING_STATE_FINALIZED)
        || status.last_error != 0
    {
        return Err("设备当前录音与原会议不同或状态未确认，未把其他录音当成这场会议。".into());
    }
    Ok(())
}

fn recording_control_request(command: u8, request_id: u32, max_seconds: u16) -> [u8; 10] {
    let mut payload = [0u8; 10];
    payload[0] = 1;
    payload[1] = command;
    payload[2] = RECORDING_CONTROL_PROFILE_BOARD_MIC;
    payload[4..8].copy_from_slice(&request_id.to_le_bytes());
    payload[8..10].copy_from_slice(&max_seconds.to_le_bytes());
    payload
}

fn meeting_control_failure(error: u8, command: u8, request_id: u32) -> String {
    if error == MEETING_ERROR_STORAGE_FULL { STORAGE_FULL_MESSAGE.to_string() }
    else { format!("board rejected V1 meeting command={command} request_id={request_id} error={error}") }
}

fn recording_control_echo_matches(value: &[u8], request_id: u32, command: u8) -> Result<bool, String> {
    if value.len() != 10 || value[0] != 1 {
        return Err("recording control echo wire mismatch".into());
    }
    let echo_id = u32::from_le_bytes(value[4..8].try_into().unwrap());
    if echo_id != request_id || value[1] != command { return Ok(false); }
    if value[3] & RECORDING_CONTROL_ERROR_FLAG != 0 {
        if value[3] & RECORDING_CONTROL_STORAGE_FULL_FLAG != 0 {
            return Err(STORAGE_FULL_MESSAGE.to_string());
        }
        return Err(format!("board rejected recording control command={command} request_id={request_id}"));
    }
    if value[3] & RECORDING_CONTROL_STORAGE_FULL_FLAG != 0 {
        return Err("recording control echo has inconsistent error flags".into());
    }
    Ok(true)
}

async fn wait_recording_control_echo<S>(
    notifications: &mut S,
    request_id: u32,
    command: u8,
) -> Result<Vec<u8>, String>
where
    S: futures::Stream<Item = ValueNotification> + Unpin,
{
    timeout(StdDuration::from_secs(30), async {
        loop {
            let notification = notifications
                .next()
                .await
                .ok_or_else(|| "recording control notification stream ended".to_string())?;
            if notification.uuid != RECORDING_CONTROL_UUID {
                continue;
            }
            if !recording_control_echo_matches(&notification.value, request_id, command)? {
                continue;
            }
            return Ok(notification.value);
        }
    })
    .await
    .map_err(|_| format!("recording control echo timeout command={command}"))?
}

fn should_retry_live_storage_error(is_live_prefix: bool, error_code: u32, attempts: u8) -> bool {
    is_live_prefix
        && (error_code & RECORDING_FLASH_READ_STORAGE_MASK) == RECORDING_FLASH_READ_STORAGE_BASE
        && attempts < RECORDING_LIVE_STORAGE_RETRY_MAX
}

fn should_reconnect_final_pull(error: &str, attempts: u8) -> bool {
    attempts < RECORDING_FINAL_PULL_RECONNECT_MAX && pull_recovery::transport_lost(error)
}

async fn best_effort_stop_board_recording(
    peripheral: &Peripheral,
    char_control: &Characteristic,
    request_id: u32,
    reason: &str,
) {
    let stop = recording_control_request(RECORDING_CONTROL_STOP, request_id, 0);
    let write_timeout = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);
    match timeout(
        write_timeout,
        peripheral.write(char_control, &stop, WriteType::WithResponse),
    )
    .await
    {
        Ok(Ok(())) => eprintln!(
            "board onlineLive fail_safe_stop requested request_id={} reason={}",
            request_id, reason
        ),
        Ok(Err(error)) => eprintln!(
            "board onlineLive fail_safe_stop write_failed request_id={} reason={} error={}",
            request_id, reason, error
        ),
        Err(_) => eprintln!(
            "board onlineLive fail_safe_stop timed_out request_id={} reason={} timeout_ms={}",
            request_id,
            reason,
            write_timeout.as_millis()
        ),
    }
}

async fn record_board_online_live_inner(
    requested_device_id: Option<&str>,
    capture_seconds: u16,
    partial_interval_ms: u64,
    disconnect_after_seconds: Option<u16>,
    consumer: BoardPartialConsumer,
    stop_requested: Arc<AtomicBool>,
    recording_observer: Option<BoardRecordingObserver>,
    observer: Option<BoardPartialObserver>,
    bookmarks: Option<BoardBookmarkObserver>,
) -> Result<BoardOnlineLiveReport, String> {
    let mut device = connect_native_device(requested_device_id).await?;
    if device.recording_peer.is_some() {
        close_native_device(&device).await;
        return Err("当前WBA连续录音必须使用原会话CMC3入口；未发送旧10字节开录指令。".into());
    }
    let device_id = device.device_id();
    let mut characteristics = device.peripheral.characteristics();
    let mut char_control = find_characteristic(&characteristics, RECORDING_CONTROL_UUID)?;
    if !char_control.properties.contains(CharPropFlags::WRITE)
        || !char_control.properties.contains(CharPropFlags::NOTIFY)
    {
        return Err("recording_control must support WRITE+NOTIFY".to_string());
    }
    let mut notifications = device
        .peripheral
        .notifications()
        .await
        .map_err(|err| format!("open recording control notifications: {err}"))?;
    device
        .peripheral
        .subscribe(&char_control)
        .await
        .map_err(|err| format!("subscribe recording_control: {err}"))?;

    let request_id = (SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u32)
        .max(1);
    /* The host sends an explicit STOP when its monotonic capture clock expires.
     * max_seconds remains a crash/disconnect safety ceiling, not the normal
     * finalization mechanism: activation and prefix pulls must not race the
     * board's automatic timeout. */
    let board_max_seconds = capture_seconds + 120; // capture_seconds was validated as 12..=2580.
    let payload=read_optional_status(&device.peripheral,&characteristics,DEVICE_STATUS_UUID,20).await;
    if let Some(capacity)=payload.as_deref().and_then(super::recording_capacity::parse) {
        super::recording_capacity::check(&capacity,board_max_seconds)?;
    }
    let start = recording_control_request(RECORDING_CONTROL_START, request_id, board_max_seconds);
    device
        .peripheral
        .write(&char_control, &start, WriteType::WithResponse)
        .await
        .map_err(|err| format!("write board recording START: {err}"))?;
    let _ = wait_recording_control_echo(&mut notifications, request_id, RECORDING_CONTROL_START)
        .await?;
    let start_ack_at = super::observation_timestamp();
    eprintln!(
        "board onlineLive START accepted request_id={} profile=2 capture_s={} board_max_s={}",
        request_id, capture_seconds, board_max_seconds
    );

    /* Storage reservation/erase is asynchronous. The online clock starts only
     * when a TRANSFER_ACTIVE directory entry has at least one durable NOR page. */
    let activation_deadline = std::time::Instant::now() + StdDuration::from_secs(180);
    let active_entry = loop {
        let entries =
            match refresh_recording_list(&device, &characteristics, &mut notifications)
                .await
            {
                Ok(entries) => entries,
                Err(error) => {
                    best_effort_stop_board_recording(
                        &device.peripheral,
                        &char_control,
                        request_id.wrapping_add(1).max(1),
                        "activation_list_error",
                    )
                    .await;
                    return Err(error);
                }
            };
        if let Some(entry) = entries
            .into_iter()
            .filter(|entry| {
                entry.sync_state == RECORDING_SYNC_TRANSFER_ACTIVE
                    && entry.codec == RECORDING_CODEC_OPUS16
                    && entry.source_mode == RECORDING_SOURCE_MIC_SAI
                    && entry.total_length > 0
            })
            .max_by_key(|entry| entry.recording_id)
        {
            break entry;
        }
        if std::time::Instant::now() >= activation_deadline
            || stop_requested.load(Ordering::Acquire)
        {
            // START was already acknowledged. Do not leave the board recording
            // until its long safety ceiling when activation cannot be observed
            // (or the user stops during allocation/erase).
            let stop_request_id = request_id.wrapping_add(1).max(1);
            let stop = recording_control_request(RECORDING_CONTROL_STOP, stop_request_id, 0);
            let _ = device
                .peripheral
                .write(&char_control, &stop, WriteType::WithResponse)
                .await;
            let _ = wait_recording_control_echo(
                &mut notifications,
                stop_request_id,
                RECORDING_CONTROL_STOP,
            )
            .await;
            return Err(if stop_requested.load(Ordering::Acquire) {
                "board onlineLive stopped before its first durable prefix".to_string()
            } else {
                "board recording did not expose a durable codec=3 prefix".to_string()
            });
        }
        sleep(StdDuration::from_millis(500)).await;
    };
    let recording_id = active_entry.recording_id;
    if let Some(recording_observer) = recording_observer.as_ref() {
        if let Err(error) = recording_observer(&device.device_id(), recording_id, active_entry.duration_ms, &start_ack_at) {
            best_effort_stop_board_recording(&device.peripheral, &char_control,
                request_id.wrapping_add(1).max(1), "recording_identity_checkpoint_error").await;
            return Err(error);
        }
    }
    let active_at = std::time::Instant::now();
    let capture_duration = StdDuration::from_secs(u64::from(capture_seconds));
    let mut last_partial_bytes = 0u32;
    let mut partials = Vec::new();
    let mut partial_errors = Vec::new();
    let mut pending_partials = Vec::new();
    let mut generated_prefixes = Vec::new();
    let mut durable_codec = Vec::new();
    let mut live_pull_session = None;
    let mut next_partial_ordinal = 1u32;
    let mut disconnect_resume = false;
    let mut disconnect_offset = 0u32;
    let mut next_partial_at = active_at + StdDuration::from_millis(partial_interval_ms);

    loop {
        let remaining = capture_duration.saturating_sub(active_at.elapsed());
        if remaining.is_zero() || stop_requested.load(Ordering::Acquire) {
            break;
        }
        let until_partial = next_partial_at.saturating_duration_since(std::time::Instant::now());
        sleep(
            StdDuration::from_millis(250)
                .min(remaining)
                .min(until_partial),
        )
        .await;
        collect_board_live_partials(
            &mut pending_partials,
            &mut partials,
            &mut partial_errors,
            false,
            observer.as_ref(),
        )
        .await;
        if active_at.elapsed() >= capture_duration || stop_requested.load(Ordering::Acquire) {
            break;
        }
        let partial_due = std::time::Instant::now() >= next_partial_at;
        if !partial_due && !bookmarks.as_ref().is_some_and(|b| (b.pending)()) {
            continue;
        }
        if partial_due { next_partial_at = std::time::Instant::now() + StdDuration::from_millis(partial_interval_ms); }
        let entries =
            match refresh_recording_list(&device, &characteristics, &mut notifications)
                .await
            {
                Ok(entries) => entries,
                Err(error) => {
                    best_effort_stop_board_recording(
                        &device.peripheral,
                        &char_control,
                        request_id.wrapping_add(1).max(1),
                        "active_list_error",
                    )
                    .await;
                    return Err(error);
                }
            };
        let Some(entry) = entries.into_iter().find(|entry| {
            entry.recording_id == recording_id && entry.sync_state == RECORDING_SYNC_TRANSFER_ACTIVE
                && entry.codec == RECORDING_CODEC_OPUS16 && entry.source_mode == RECORDING_SOURCE_MIC_SAI
        }) else {
            break;
        };
        if let Some(bookmarks) = bookmarks.as_ref() {
            if entry.duration_ms > 0 { (bookmarks.stamp)(&device.device_id(), recording_id, entry.duration_ms); }
        }
        if !partial_due { continue; }
        let enough_new_codec = entry.total_length >= last_partial_bytes.saturating_add(1_024);
        /* ASR is a consumer of durable prefixes, not part of the recording
         * clock. Keep at most two provider requests in flight so a slow or
         * unavailable network can never delay STOP or exhaust host memory. */
        if enough_new_codec && pending_partials.len() < 2 {
            durable_codec = match pull_recording_bytes(
                &device,
                &characteristics,
                &mut live_pull_session,
                &entry,
                &device.address,
                device.address_type,
                Some(durable_codec),
                None,
                None,
            )
            .await
            {
                Ok(bytes) => bytes,
                Err(error) => {
                    best_effort_stop_board_recording(
                        &device.peripheral,
                        &char_control,
                        request_id.wrapping_add(1).max(1),
                        "live_prefix_pull_error",
                    )
                    .await;
                    return Err(format!("{error}; board_stop_requested=1"));
                }
            };
            let prepared = (|| -> Result<(PathBuf, PathBuf), String> {
                let base = native_recording_output_path(recording_id)?;
                let prefix_path = base.with_file_name(format!(
                    "board-live-{recording_id}-{:010}-{}.cop1",
                    entry.total_length, uuid::Uuid::new_v4().simple()
                ));
                let wav_path = prefix_path.with_extension("wav");
                // Persist provenance before generating this prefix. A failed
                // local write must not leave the microphone running silently.
                super::recording_transfer::groups::remember(&native_recording_root()?, &device.device_id(),
                    recording_id, &wav_path, &durable_codec)?;
                super::audio_artifacts::generated(&wav_path, &prefix_path, super::audio_artifacts::Purpose::LivePrefix,
                    || super::export::write_atomic(&prefix_path, &durable_codec).map(|_| ()))?;
                super::audio_decode::decode_recording(&prefix_path, &wav_path, true)
                    .map_err(|err| format!("decode board live COP1 prefix: {err}"))?;
                let consumer_path = board_live_consumer_window(&wav_path, entry.duration_ms)?;
                Ok((wav_path, consumer_path))
            })();
            let (wav_path, consumer_path) = match prepared {
                Ok(paths) => paths,
                Err(error) => {
                    best_effort_stop_board_recording(&device.peripheral, &char_control,
                        request_id.wrapping_add(1).max(1), "live_prefix_storage_error").await;
                    return Err(format!("{error}; board_stop_requested=1"));
                }
            };
            generated_prefixes.push(wav_path.clone());
            let consumer_fn = Arc::clone(&consumer);
            pending_partials.push(PendingBoardLivePartial {
                partial: BoardLivePartial {
                    ordinal: next_partial_ordinal,
                    recording_id,
                    durable_codec_bytes: entry.total_length,
                    duration_ms: entry.duration_ms,
                    transcript: String::new(),
                    wav_path: wav_path.to_string_lossy().to_string(),
                },
                consumer: tokio::task::spawn_blocking(move || consumer_fn(consumer_path)),
            });
            next_partial_ordinal = next_partial_ordinal.saturating_add(1);
            last_partial_bytes = entry.total_length;
        }
        if !disconnect_resume
            && disconnect_after_seconds
                .map(|seconds| active_at.elapsed() >= StdDuration::from_secs(u64::from(seconds)))
                .unwrap_or(false)
        {
            disconnect_offset = last_partial_bytes;
            PullSession::close(&mut live_pull_session).await;
            let _ = device.peripheral.unsubscribe(&char_control).await;
            device
                .peripheral
                .disconnect()
                .await
                .map_err(|err| format!("onlineLive intentional disconnect: {err}"))?;
            eprintln!(
                "board onlineLive intentional_disconnect id={} durable_offset={} elapsed_ms={}",
                recording_id,
                disconnect_offset,
                active_at.elapsed().as_millis()
            );
            sleep(StdDuration::from_secs(5)).await;
            device = match reconnect_native_device(&device, Some(&device_id)).await {
                Ok(device) => device,
                Err(error) => {
                    collect_board_live_partials(
                        &mut pending_partials,
                        &mut partials,
                        &mut partial_errors,
                        true,
                        observer.as_ref(),
                    )
                    .await;
                    return Err(error);
                }
            };
            characteristics = device.peripheral.characteristics();
            char_control = find_characteristic(&characteristics, RECORDING_CONTROL_UUID)?;
            notifications = device
                .peripheral
                .notifications()
                .await
                .map_err(|err| format!("reopen recording notifications: {err}"))?;
            device
                .peripheral
                .subscribe(&char_control)
                .await
                .map_err(|err| format!("resubscribe recording_control: {err}"))?;
            let resumed =
                refresh_recording_list(&device, &characteristics, &mut notifications)
                    .await?;
            let resume_entry = resumed
                .iter()
                .find(|entry| entry.recording_id == recording_id)
                .ok_or_else(|| {
                    format!("recording {recording_id} missing after intentional reconnect")
                })?;
            if resume_entry.total_length < disconnect_offset {
                return Err(format!(
                    "recording {recording_id} regressed across reconnect: {} < {}",
                    resume_entry.total_length, disconnect_offset
                ));
            }
            disconnect_resume = true;
            eprintln!(
                "board onlineLive reconnect_resume id={} from_offset={} durable_length={} sync_state={}",
                recording_id,
                disconnect_offset,
                resume_entry.total_length,
                resume_entry.sync_state
            );
        }
    }

    if let Some(bookmarks) = bookmarks.as_ref() { (bookmarks.close)(); }
    /* Normal completion is explicit and acknowledged. This closes the race in
     * which the host waited for UNSYNCED while the board was still active (or
     * had abandoned a write-failed journal at its safety timeout). */
    let stop_request_id = request_id.wrapping_add(1).max(1);
    let stop = recording_control_request(RECORDING_CONTROL_STOP, stop_request_id, 0);
    device
        .peripheral
        .write(&char_control, &stop, WriteType::WithResponse)
        .await
        .map_err(|err| format!("write board recording STOP: {err}"))?;
    let _ =
        wait_recording_control_echo(&mut notifications, stop_request_id, RECORDING_CONTROL_STOP)
            .await?;
    let stop_ack_at = super::observation_timestamp();
    eprintln!(
        "board onlineLive STOP accepted request_id={} id={} elapsed_ms={}",
        stop_request_id,
        recording_id,
        active_at.elapsed().as_millis()
    );

    let finalize_deadline = std::time::Instant::now() + StdDuration::from_secs(120);
    let final_entry = loop {
        let entries =
            refresh_recording_list(&device, &characteristics, &mut notifications)
                .await?;
        if let Some(entry) = entries.into_iter().find(|entry| {
            entry.recording_id == recording_id
                && entry.sync_state == RECORDING_SYNC_UNSYNCED
                && entry.total_length > 0
        }) {
            break entry;
        }
        if std::time::Instant::now() >= finalize_deadline {
            return Err(format!("board recording {recording_id} did not finalize"));
        }
        sleep(StdDuration::from_millis(500)).await;
    };
    /* Windows may close the WinRT GATT object after a long dual-lane stream
     * even though STOP was acknowledged and the board recording is already
     * immutable.  The non-live pull persists its verified prefix to the
     * durable cursor, so reconnecting and calling the same sync resumes at
     * that exact offset.  Keep this bounded and final-pull-only: START/STOP is
     * never replayed, and non-transport integrity failures still fail closed. */
    eprintln!(
        "board onlineLive final_pull_fresh_session id={} old_session_ms={} durable_cursor=1",
        recording_id,
        active_at.elapsed().as_millis()
    );
    PullSession::close(&mut live_pull_session).await;
    let _ = device.peripheral.unsubscribe(&char_control).await;
    close_native_device(&device).await;
    sleep(StdDuration::from_millis(
        RECORDING_FINAL_PULL_RECONNECT_DELAY_MS,
    ))
    .await;
    /* Do not accept the cached btleplug Peripheral here. Windows can report
     * it connected while its notification/write channel remains unreachable
     * (GattCommunicationStatus::Unreachable == 1). A rescan gives the final
     * transfer a genuinely new WinRT Peripheral/GATT object graph. */
    recording_sync::resume_explicit(Some(&device_id))?;
    device = connect_native_device(Some(&device_id))
        .await
        .map_err(|error| format!("open fresh final-pull GATT session: {error}"))?;
    characteristics = device.peripheral.characteristics();
    char_control = find_characteristic(&characteristics, RECORDING_CONTROL_UUID)?;

    let mut final_pull_reconnects = 0u8;
    let mut final_pull_session = None;
    let mut final_link_policy = SealedLinkPolicy::default();
    let final_sync_job = RecordingSyncJob::begin(&device_id)?;
    let final_sync = loop {
        match sync_native_recording_entry(&device, &characteristics, &mut final_pull_session, final_entry.clone(), Some(&final_sync_job), &mut final_link_policy).await {
            Ok(sync) => break Some(sync),
            Err(error) if error == recording_sync::PAUSED => break None,
            Err(error) if should_reconnect_final_pull(&error, final_pull_reconnects) => {
                final_pull_reconnects = final_pull_reconnects.saturating_add(1);
                eprintln!(
                    "board onlineLive final_pull_reconnect id={} attempt={}/{} delay_ms={} durable_cursor=1 cause={}",
                    recording_id,
                    final_pull_reconnects,
                    RECORDING_FINAL_PULL_RECONNECT_MAX,
                    RECORDING_FINAL_PULL_RECONNECT_DELAY_MS,
                    error
                );
                PullSession::close(&mut final_pull_session).await;
                let _ = device.peripheral.unsubscribe(&char_control).await;
                close_native_device(&device).await;
                sleep(StdDuration::from_millis(
                    RECORDING_FINAL_PULL_RECONNECT_DELAY_MS,
                ))
                .await;
                device =
                    connect_native_device(Some(&device_id))
                        .await
                        .map_err(|reconnect_error| {
                            format!("final pull reconnect after {error}: {reconnect_error}")
                        })?;
                characteristics = device.peripheral.characteristics();
                char_control = find_characteristic(&characteristics, RECORDING_CONTROL_UUID)?;
            }
            Err(error) => {
                PullSession::close(&mut final_pull_session).await;
                let _ = timeout(StdDuration::from_secs(1), device.peripheral.unsubscribe(&char_control)).await;
                close_native_device(&device).await;
                return Err(error);
            },
        }
    };
    PullSession::close(&mut final_pull_session).await;
    let _ = timeout(StdDuration::from_secs(1), device.peripheral.unsubscribe(&char_control)).await;
    close_native_device(&device).await;
    drop(final_sync_job);
    // A paused final pull releases the BLE handles before returning the real
    // STOP metadata. It does not await or start any additional cloud work.
    let sync_paused = final_sync.is_none();
    if let Some(final_path) = final_sync.as_ref().and_then(|sync| sync.recording_path.as_deref()) {
        for prefix in &generated_prefixes { super::audio_artifacts::attach_group(prefix, Path::new(final_path))?; }
    }
    collect_board_live_partials(
        &mut pending_partials,
        &mut partials,
        &mut partial_errors,
        !sync_paused,
        observer.as_ref(),
    )
    .await;
    partials.sort_by_key(|partial| partial.ordinal);
    Ok(BoardOnlineLiveReport {
        capture_incomplete: final_sync.as_ref().map(|sync| sync.capture_incomplete).unwrap_or(false),
        sync_paused,
        sealed_duration_ms: final_entry.duration_ms,
        device_id: device.device_id(),
        recording_id,
        start_ack_at,
        stop_ack_at,
        partials,
        partial_errors,
        disconnect_resume,
        disconnect_offset,
        final_recording_path: final_sync.as_ref().and_then(|sync| sync.recording_path.clone()).unwrap_or_default(),
        final_total_length: final_sync.as_ref().and_then(|sync| sync.total_length).unwrap_or_default(),
        final_sha256: final_sync.as_ref().and_then(|sync| sync.sha256.clone()).unwrap_or_default(),
        device_reclaimed: final_sync.as_ref().is_some_and(|sync| sync.device_reclaimed),
    })
}

async fn sync_first_native_recording(
    requested_device_id: Option<&str>,
) -> Result<NativeRecordingBatch, String> {
    sync_native_recordings_excluding(requested_device_id, &[]).await
}

async fn sync_native_recordings_excluding(
    requested_device_id: Option<&str>,
    known_recording_ids: &[u32],
) -> Result<NativeRecordingBatch, String> {
    sync_native_recordings_selected(requested_device_id, known_recording_ids, None).await
}

async fn sync_native_recordings_selected(
    requested_device_id: Option<&str>,
    known_recording_ids: &[u32],
    recording_id: Option<u32>,
) -> Result<NativeRecordingBatch, String> {
    sync_native_recordings_scoped(requested_device_id,known_recording_ids,recording_id,None).await
}

async fn sync_native_recordings_original(original: &OwnedRecorder) -> Result<NativeRecordingBatch,String> {
    let key=original.logical_key.as_ref().ok_or("原录音缺少逻辑身份，未收取其它录音。")?;
    sync_native_recordings_scoped(Some(&original.device_id),&[],Some(original.recording_id),Some(key)).await
}

async fn sync_native_recordings_scoped(requested_device_id: Option<&str>,known_recording_ids: &[u32],
    recording_id: Option<u32>,logical_key: Option<&super::recording_wire::SessionKey>) -> Result<NativeRecordingBatch,String> {
    // Downloading sealed recordings cannot change their capture timestamps.
    // Acquire the protected connection without a best-effort settings-clock
    // read/write in front of the download. Normal connect/START still sync UTC.
    let started = StdInstant::now();
    let setup = connect_native_device_setup_with_intent(requested_device_id, false, ConnectionIntent::SealedSync).await?;
    let device = setup.device;
    #[cfg(windows)]
    let mut setup_preference = setup.preference;
    #[cfg(windows)]
    if let Some(preference) = setup_preference.as_mut() { preference.handoff_to_sealed_sync(); }
    let mut link_policy = SealedLinkPolicy {
        #[cfg(windows)] preference: setup_preference,
        #[cfg(windows)] initialized: true,
    };
    eprintln!("recording_sync_stage stage=connection elapsed_ms={}", started.elapsed().as_millis());
    let result = sync_native_recordings_with_link_policy(&device, known_recording_ids, recording_id, &mut link_policy, logical_key).await;
    // Release before returning a reusable idle connection or closing its
    // owner. Errors/cancel also drop this local guard, never retain fast idle.
    drop(link_policy);
    let reusable = result.as_ref().is_ok_and(|batch| batch.connection_reusable);
    finish_native_device_operation(device, reusable).await?;
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
    let result = delete_privacy_on_device(
        &device,
        operation,
        recording_id,
        total_length,
        validated_sha256,
    )
    .await;
    // A single consumed recording does not revoke the user's connection;
    // delete-all/factory-wipe do, and must retire the current private session.
    finish_native_device_operation(device,
        result.is_ok() && operation == DELETE_PRIVACY_OP_DELETE_RECORDING).await?;
    result
}

fn device_reclaim_timeout_ms(operation: u8, total_length: u32) -> u64 {
    // Consumption is acknowledged only after the existing physical reclaim.
    // FW88's five-minute file needed 5.7s; a fixed 15s wait cannot cover a
    // nearly full 16MiB arena. Allow 50ms per 4KiB sector plus catalog/tail
    // margin, with a finite four-minute cap. This is a waiting budget, not a
    // throughput promise or evidence of successful erasure.
    let bytes = match operation {
        DELETE_PRIVACY_OP_DELETE_RECORDING => u64::from(total_length),
        DELETE_PRIVACY_OP_DELETE_ALL | DELETE_PRIVACY_OP_FACTORY_WIPE => 16 * 1024 * 1024,
        _ => return 15_000,
    };
    let sectors = (bytes + 4095) / 4096 + 2;
    (5_000 + sectors * 50).clamp(15_000, 240_000)
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
    let control_started = StdInstant::now();
    let trace = |stage: &str| eprintln!(
        "BLE control_trace request_id={request_id} recording_id={recording_id} operation={operation} bytes={total_length} elapsed_us={} stage={stage}",
        control_started.elapsed().as_micros());

    let read_timeout = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let write_timeout = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);
    trace("notification_stream_begin");
    let mut notifications = timeout(read_timeout, device.peripheral.notifications())
        .await
        .map_err(|_| {
            format!(
                "open BLE notification stream timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("open BLE notification stream: {err}"))?;
    trace("notification_stream_ready");
    trace("subscribe_begin");
    timeout(read_timeout, device.peripheral.subscribe(&char_delete))
        .await
        .map_err(|_| {
            format!(
                "subscribe delete_privacy timed out after {}ms",
                read_timeout.as_millis()
            )
        })?
        .map_err(|err| format!("subscribe delete_privacy: {err}"))?;
    trace("subscribe_ready");

    trace("att_write_begin");
    timeout(
        write_timeout,
        device
            .peripheral
            .write(&char_delete, &request, WriteType::WithResponse),
    )
    .await
    .map_err(|_| {
        format!(
            "write delete_privacy timed out after {}ms",
            write_timeout.as_millis()
        )
    })?
    .map_err(|err| format!("write delete_privacy: {err}"))?;
    trace("att_write_response");

    let notify_timeout = StdDuration::from_millis(
        std::env::var("COMPANION_TYPE_BLE_NOTIFY_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or_else(|| device_reclaim_timeout_ms(operation, total_length)),
    );
    eprintln!("recording reclaim wait operation={operation} bytes={total_length} timeout_ms={} physical_receipt_required=1",
        notify_timeout.as_millis());
    trace("physical_receipt_wait");
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
                validate_delete_privacy_echo(&notification.value, &request)?;
                return Ok::<DeletePrivacyResponse, String>(parsed);
            }
        }
    })
    .await
    .map_err(|_| format!("delete_privacy notify timeout for request_id={request_id}"))??;

    trace(if (response.flags & DELETE_PRIVACY_REFUSAL_FLAG) != 0 {
        "exact_refusal_received"
    } else { "exact_physical_receipt_received" });
    trace("unsubscribe_begin");
    let _ = device.peripheral.unsubscribe(&char_delete).await;
    trace("unsubscribe_returned");
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
        return Err(format!(
            "delete_privacy response too short: {}",
            payload.len()
        ));
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

fn validate_delete_privacy_echo(payload: &[u8], request: &[u8; DELETE_PRIVACY_REQUEST_BYTES]) -> Result<(), String> {
    let response = parse_delete_privacy_response(payload)?;
    if response.operation != request[1] || payload[4..16] != request[4..16] {
        return Err("device reclaim receipt does not match operation, request, recording or length".into());
    }
    if response.flags & DELETE_PRIVACY_REFUSAL_FLAG == 0
        && (payload.len() != DELETE_PRIVACY_REQUEST_BYTES || payload[16..] != request[16..]) {
        return Err("device reclaim success lacks the exact validated SHA-256 receipt".into());
    }
    Ok(())
}

fn next_delete_request_id() -> u32 {
    static COUNTER: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(1);
    COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
}

fn decode_stored_half_ima_to_pcm16_bytes(blob: &[u8]) -> Result<Vec<u8>, String> {
    let samples = denzic_host_audio_v1_core::decompress_half_ima_to_pcm16k(blob)?;
    let mut pcm = Vec::with_capacity(samples.len() * 2);
    for sample in samples {
        pcm.extend_from_slice(&sample.to_le_bytes());
    }
    Ok(pcm)
}

pub(super) fn delete_after_sync_enabled() -> bool {
    std::env::var("COMPANION_TYPE_DELETE_AFTER_SYNC")
        .map(|value| truthy(&value))
        /* Product ring semantics: only a fully pulled, locally persisted,
         * length/SHA-verified recording reaches the exact device ACK/reclaim.
         * Setting the variable to 0 remains a diagnostic hold switch. */
        .unwrap_or(true)
}

async fn sync_first_native_recording_inner(
    device: &NativeDevice,
) -> Result<NativeRecordingBatch, String> {
    sync_native_recordings_inner(device, &[]).await
}

async fn sync_native_recordings_inner(
    device: &NativeDevice,
    known_recording_ids: &[u32],
) -> Result<NativeRecordingBatch, String> {
    sync_native_recordings_with_link_policy(device, known_recording_ids, None, &mut SealedLinkPolicy::default(), None).await
}

fn pending_recordings(mut entries: Vec<RecordingEntry>, known_recording_ids: &[u32], recording_id: Option<u32>)
    -> Vec<RecordingEntry>
{
    // A growing live prefix never enters the final SHA/ACK/reclaim path.
    // STOP selects only its own sealed file; ordinary backlog sync selects all.
    entries.retain(|entry| entry.sync_state == RECORDING_SYNC_UNSYNCED
        && !known_recording_ids.contains(&entry.recording_id)
        && recording_id.is_none_or(|id| entry.recording_id == id));
    entries.sort_by_key(|entry| entry.recording_id);
    entries
}

async fn sync_native_recordings_with_link_policy(
    device: &NativeDevice,
    known_recording_ids: &[u32],
    recording_id: Option<u32>,
    link_policy: &mut SealedLinkPolicy,
    logical_key: Option<&super::recording_wire::SessionKey>,
) -> Result<NativeRecordingBatch, String> {
    let job = RecordingSyncJob::begin(&device.device_id())?;
    let characteristics = device.peripheral.characteristics();
    let started = StdInstant::now();
    let catalog = match job.receive(on_native_link(device, read_recording_catalog(&device, &characteristics))).await {
        Ok(catalog) => catalog,
        Err(error) if error == recording_sync::PAUSED => return Ok(NativeRecordingBatch {
            device_id: device.device_id(), recordings: Vec::new(), failures: Vec::new(), paused: true,
            connection_reusable: false,
            segmented: None,
        }),
        Err(error) => return Err(error),
    };
    eprintln!("recording_sync_stage stage=catalog elapsed_ms={}", started.elapsed().as_millis());
    if let Some(peer) = catalog.peer {
        // Physical V1 IDs and host V1 known-ID caches cannot filter a session.
        // The durable V2 receiver itself selects missing immutable segments.
        if recording_id.is_some() && logical_key.is_none() {
            return Err("分段录音收取缺少原逻辑会话，未用物理段ID消费其它录音。".into());
        }
        return segmented::sync_catalog(device, &characteristics, peer, catalog.entries,
            &job, link_policy, logical_key).await;
    }
    if logical_key.is_some() {
        return Err("原分段录音的芯片与格式协议未核对，未退回旧物理ID收取其它录音。".into());
    }
    let entries = catalog.entries;
    let entries = pending_recordings(entries, known_recording_ids, recording_id);
    if entries.is_empty() {
        return Ok(NativeRecordingBatch {
            device_id: device.device_id(),
            recordings: Vec::new(),
            failures: Vec::new(),
            paused: false,
            connection_reusable: true,
            segmented: None,
        });
    }

    /* COMP-REQ-778: a connection drains the durable device backlog oldest
     * first.  Returning only after every directory entry has passed the full
     * length/SHA gate prevents the old one-recording-per-connect behaviour. */
    let backlog_count = entries.len();
    let mut recordings = Vec::with_capacity(backlog_count);
    let mut failures = Vec::new();
    let mut pull_session = None;
    let mut paused = false;
    let mut connection_reusable = true;
    for (index, entry) in entries.into_iter().enumerate() {
        if job.is_paused() { paused = true; break; }
        let recording_id = entry.recording_id;
        let synced = match sync_native_recording_entry(device, &characteristics, &mut pull_session, entry, Some(&job), link_policy).await {
            Ok(synced) => synced,
            Err(error) if error == recording_sync::PAUSED => { paused = true; break; },
            Err(err) => {
                let retire = pull_recovery::retire_connection(&err);
                let failure = format!("recording_id={recording_id}: {err}");
                eprintln!(
                    "recording backlog isolate failure={} progress={}/{} continue={}",
                    failure,
                    index + 1,
                    backlog_count,
                    u8::from(!retire)
                );
                failures.push(failure);
                if retire {
                    // Preserve this recording's cursor and the remaining
                    // backlog. A failed transport cannot become a prepared
                    // user connection or cost another timeout per recording.
                    connection_reusable = false;
                    break;
                }
                continue;
            }
        };
        eprintln!(
            "recording backlog consume id={} progress={}/{} sha={} path={:?}",
            synced.recording_id.unwrap_or_default(),
            index + 1,
            backlog_count,
            synced.sha256.as_deref().unwrap_or(""),
            synced.recording_path
        );
        recordings.push(CompanionSyncedRecording {
            capture_incomplete: synced.capture_incomplete,
            recording_id: synced.recording_id.unwrap_or_default(),
            duration_ms: synced.duration_ms.unwrap_or_default(),
            total_length: synced.total_length.unwrap_or_default(),
            sha256: synced.sha256.unwrap_or_default(),
            recording_path: synced.recording_path.unwrap_or_default(),
            device_reclaimed: synced.device_reclaimed,
        });
        if synced.reclaim_transport_failed {
            // Audio/index/cursor are already durable. This transport failed a
            // protected control operation: do not hand it to the next entry or
            // FINALIZE. The ordinary finite STOP retry can reopen a protected
            // connection and retry this exact cursor without retransmission.
            connection_reusable = false;
            eprintln!("recording backlog control_transport_failed id={recording_id} durable_audio_kept=1 retry_requires_new_protected_connection=1");
            break;
        }
    }
    PullSession::close(&mut pull_session).await;
    Ok(NativeRecordingBatch {
        device_id: device.device_id(),
        recordings,
        failures,
        paused,
        connection_reusable,
        segmented: None,
    })
}

async fn sync_native_recording_entry(
    device: &NativeDevice,
    characteristics: &std::collections::BTreeSet<Characteristic>,
    pull_session: &mut Option<PullSession>,
    entry: RecordingEntry,
    job: Option<&RecordingSyncJob>,
    link_policy: &mut SealedLinkPolicy,
) -> Result<NativeRecordingSync, String> {
    if let Some(job) = job { job.recording(entry.recording_id, entry.total_length); }
    if entry.codec != RECORDING_CODEC_PCM16_MONO
        && entry.codec != RECORDING_CODEC_HALF_IMA
        && entry.codec != RECORDING_CODEC_OPUS16
    {
        return Err(format!("unsupported recording codec: {}", entry.codec));
    }
    if entry.source_mode != RECORDING_SOURCE_MIC_SAI {
        return Err(format!(
            "recording source_mode={} is not the SAI microphone path",
            entry.source_mode
        ));
    }

    // Codec3 includes WBA COP1 and legacy Ogg Opus. Keep its compressed original.
    let is_opus16 = entry.codec == RECORDING_CODEC_OPUS16;

    // Cold, prepared and STOP/final backlog share one scoped bootstrap. Release
    // once at the first verified payload and retain that policy across entries;
    // neither later entries nor cached control recovery replace it with 15ms.
    // Live prefixes do not enter this sealed-file path.
    link_policy.initialize(device).await;

    let started = StdInstant::now();
    let payload_bytes = pull_recording_bytes(
        device,
        characteristics,
        pull_session,
        &entry,
        &device.address,
        device.address_type,
        None,
        job,
        Some(link_policy),
    )
    .await?;
    eprintln!("recording_sync_stage stage=receive id={} elapsed_ms={}", entry.recording_id, started.elapsed().as_millis());
    if let Some(job) = job { job.saving(); }
    let durable_started = StdInstant::now();
    let sha256 = Sha256::digest(&payload_bytes);
    let sha256_hex = hex_lower(&sha256);
    // IMA path is lossy: list SHA/CRC are of original device PCM, not decoded host PCM.
    // Packet CRC + length already enforced inside pull. Only raw path must match list digests.
    let compress = recording_wire_ima_requested(entry.codec);
    let skip_list_digest = std::env::var("COMPANION_TYPE_BLE_SKIP_FINAL_SHA")
        .map(|v| {
            let t = v.trim();
            t == "1" || t.eq_ignore_ascii_case("true") || t.eq_ignore_ascii_case("on")
        })
        .unwrap_or(false);
    if !compress && !skip_list_digest {
        if sha256[..8] != entry.sha256_prefix {
            return Err(format!(
                "recording SHA prefix mismatch: list={} host={}",
                hex_lower(&entry.sha256_prefix),
                &sha256_hex[..16]
            ));
        }
        let crc32 = crc32fast::hash(&payload_bytes);
        if crc32 != entry.content_crc32 {
            return Err(format!(
                "recording CRC32 mismatch: list=0x{:08x} host=0x{crc32:08x}",
                entry.content_crc32
            ));
        }
    }

    let path = native_recording_output_path(entry.recording_id)?;
    if is_opus16 {
        // Persist raw Opus then decode to product 16 kHz mono WAV for ASR/minutes.
        let opus_path = path.with_extension("opus");
        super::audio_artifacts::generated(&path, &opus_path, super::audio_artifacts::Purpose::CompressedOriginal,
            || super::export::write_atomic(&opus_path, &payload_bytes).map(|_| ()))?;
        super::audio_decode::decode_recording(&opus_path, &path, false).map_err(|e| {
            format!(
                "decode Opus16 recording_id={} opus={} -> wav={}: {e}",
                entry.recording_id,
                opus_path.display(),
                path.display()
            )
        })?;
        eprintln!(
            "recording pull codec=opus16 bytes={} opus={} wav={}",
            payload_bytes.len(),
            opus_path.display(),
            path.display()
        );
    } else {
        // Meeting half-rate PCM (codec=1): device stores 8 kHz mono. Detect by
        // byte budget vs duration (16 kB/s half vs 32 kB/s full) and upsample ×2.
        let pcm_for_wav = if entry.codec == RECORDING_CODEC_HALF_IMA {
            let decoded = decode_stored_half_ima_to_pcm16_bytes(&payload_bytes)?;
            eprintln!(
                "recording pull stored_half_ima decode 8k→16k bytes={} pcm_bytes={} duration_ms={}",
                payload_bytes.len(),
                decoded.len(),
                entry.duration_ms
            );
            decoded
        } else if entry.codec == RECORDING_CODEC_PCM16_MONO && entry.duration_ms > 0 {
            let full_budget = (entry.duration_ms as u64).saturating_mul(32);
            let half_budget = (entry.duration_ms as u64).saturating_mul(16);
            let n = payload_bytes.len() as u64;
            let dist_half = n.abs_diff(half_budget);
            let dist_full = n.abs_diff(full_budget);
            if dist_half + (n / 8) < dist_full {
                eprintln!(
                    "recording pull half_rate_pcm upsample 8k→16k bytes={} duration_ms={}",
                    payload_bytes.len(),
                    entry.duration_ms
                );
                upsample_pcm16_x2(&payload_bytes)?
            } else {
                payload_bytes.clone()
            }
        } else {
            payload_bytes.clone()
        };
        super::audio_artifacts::generated(&path, &path, super::audio_artifacts::Purpose::Recording,
            || write_pcm16_wav(&path, &pcm_for_wav))?;
    }

    let mut verified_sha256 = [0u8; 32];
    verified_sha256.copy_from_slice(&sha256);
    if !compress {
        super::audio_artifacts::verified_cursor(&path, &native_recording_partial_path(&device.address, &entry)?, payload_bytes.len() as u64, &sha256_hex)?;
    }
    super::recording_transfer::groups::attach(&native_recording_root()?, &device.device_id(),
        entry.recording_id, &payload_bytes, &path)?;

    // Decoder success is insufficient: flush the final audio and commit its
    // discoverable library entry before any exact device ACK/reclaim.
    OpenOptions::new().write(true).open(&path)
        .and_then(|file| file.sync_all()).map_err(|e| format!("flush received WAV before device ACK: {e}"))?;
    super::checkpoint_received_recording(&super::persistence::state_file_path(), &device.device_id(),
        &CompanionSyncedRecording {
            recording_id: entry.recording_id, duration_ms: entry.duration_ms,
            total_length: entry.total_length, sha256: sha256_hex.clone(),
            recording_path: path.to_string_lossy().into_owned(), device_reclaimed: false, capture_incomplete: entry.capture_incomplete,
        })?;

    eprintln!("recording_sync_stage stage=durable_audio_index id={} elapsed_ms={}", entry.recording_id, durable_started.elapsed().as_millis());

    // The durable WAV/library checkpoint is the host receipt. Device space is
    // released only by the exact firmware ACK/reclaim below, never by a second
    // host-only 14 MiB ring estimate with unrelated IDs and geometry.

    let delete_after_sync = delete_after_sync_enabled();
    let mut device_reclaimed = false;
    let mut reclaim_transport_failed = false;
    let reclaim_started = StdInstant::now();
    if let Some(job) = job { job.reclaiming(); }
    let device_erase_status = if delete_after_sync {
        // Finish both audio CCCD writes before opening the control stream.
        // This is outside the payload timer, after durable originals/index.
        // If release fails, preserve the cursor and retire this connection;
        // never send the irreversible exact consume on an uncertain stream.
        let quiesce_started = StdInstant::now();
        PullSession::quiesce_for_control(pull_session).await?;
        eprintln!("recording_sync_stage stage=sealed_stream_quiesce id={} elapsed_ms={} completed=true", entry.recording_id, quiesce_started.elapsed().as_millis());
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
            Ok(_) => {
                device_reclaimed = true;
                Some(format!(
                    "device deleted recording_id={} after verified sync",
                    entry.recording_id
                ))
            }
            Err(err) => {
                reclaim_transport_failed = true;
                Some(format!("delete-after-sync failed (audio already synced to host): {err}"))
            },
        }
    } else {
        None
    };

    eprintln!("recording_sync_stage stage=exact_reclaim id={} elapsed_ms={} acknowledged={device_reclaimed}",
        entry.recording_id, reclaim_started.elapsed().as_millis());
    if let Some(status) = device_erase_status { eprintln!("recording pull {status}"); }
    if device_reclaimed {
        // Persist only the actual exact-ID/length/hash device ACK. Both batch
        // and onlineLive need this checkpoint even when later ASR fails.
        super::checkpoint_received_recording(&super::persistence::state_file_path(), &device.device_id(),
            &CompanionSyncedRecording {
                recording_id: entry.recording_id, duration_ms: entry.duration_ms,
                total_length: entry.total_length, sha256: sha256_hex.clone(),
                recording_path: path.to_string_lossy().into_owned(), device_reclaimed: true,
                capture_incomplete: entry.capture_incomplete,
            })?;
    }

    /* Keep the complete .part through host decode and device ACK. If the app
     * dies anywhere before the durable queue advances, reconnect resumes from
     * total_length and can retry verification/ACK without retransmitting. */
    if !compress && (!delete_after_sync || device_reclaimed) {
        super::recording_transfer::release(&native_recording_root()?, recording_transfer_source(&device.address, &entry))?;
    }

    Ok(NativeRecordingSync {
        capture_incomplete: entry.capture_incomplete,
        device_id: device.device_id(),
        recording_id: Some(entry.recording_id),
        duration_ms: Some(entry.duration_ms),
        total_length: Some(entry.total_length),
        sha256: Some(sha256_hex),
        recording_path: Some(path.to_string_lossy().to_string()),
        device_reclaimed,
        reclaim_transport_failed,
    })
}

async fn read_recording_list(
    device: &NativeDevice,
    characteristics: &std::collections::BTreeSet<Characteristic>,
) -> Result<Vec<RecordingEntry>, String> {
    Ok(read_recording_catalog(device, characteristics).await?.entries)
}

struct RecordingCatalog {
    entries: Vec<RecordingEntry>,
    peer: Option<super::recording_wire::transport::Peer>,
    generation: Option<u32>,
}

async fn read_recording_catalog(
    device: &NativeDevice,
    characteristics: &std::collections::BTreeSet<Characteristic>,
) -> Result<RecordingCatalog, String> {
    let peripheral = &device.peripheral;
    // Decide protocol from the actual status capability before touching a
    // cached directory. An advertised V2 peer can never enter ID-only V1 just
    // because a stale ATT value happens to start with 1.
    if let Some(status) = read_optional_status(peripheral, characteristics, DEVICE_STATUS_UUID, 20).await {
        if let Some(peer) = super::recording_wire::transport::Peer::from_status(&status)? {
            return segmented::read_catalog(device, characteristics, peer).await;
        }
    }
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
    if payload.first() == Some(&2) {
        Err("设备目录为V2，但没有读到受支持的连续录音身份/能力；没有降级消费。".into())
    } else {
        Ok(RecordingCatalog { entries: parse_recording_list(&payload)?, peer: None, generation: None })
    }
}

/// The firmware publishes the recording directory when the list CCC is
/// enabled.  A plain ATT read can legitimately return the previous cached
/// value while an active capture is extending its durable NOR prefix, so the
/// online consumer uses a short subscribe/publish/unsubscribe handshake for
/// every sparse poll.  This keeps the encode hot path free of BLE work and
/// makes the value observed here a service-task snapshot of bytes that have
/// already reached flash.
async fn refresh_recording_list<S>(
    device: &NativeDevice,
    characteristics: &std::collections::BTreeSet<Characteristic>,
    notifications: &mut S,
) -> Result<Vec<RecordingEntry>, String>
where
    S: futures::Stream<Item = ValueNotification> + Unpin,
{
    let peripheral = &device.peripheral;
    let char_recording_list = find_characteristic(characteristics, RECORDING_LIST_UUID)?;
    if !char_recording_list
        .properties
        .contains(CharPropFlags::NOTIFY)
    {
        return Err("recording_list characteristic is not notifiable".to_string());
    }

    let refresh_timeout = env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000);
    let refresh_deadline = StdInstant::now() + refresh_timeout;
    bounded_ble_result(
        "subscribe recording_list refresh",
        remaining_deadline_budget(refresh_deadline, refresh_timeout),
        peripheral.subscribe(&char_recording_list),
    )
    .await?;
    let mut version2 = false;
    let result = match timeout(
        remaining_deadline_budget(refresh_deadline, refresh_timeout),
        async {
            loop {
                let notification = notifications
                    .next()
                    .await
                    .ok_or_else(|| "recording_list notification stream ended".to_string())?;
                if notification.uuid == RECORDING_LIST_UUID {
                    if notification.value.first() == Some(&2) {
                        version2 = true;
                        return Ok(Vec::new());
                    }
                    return parse_recording_list(&notification.value);
                }
            }
        },
    )
    .await
    {
        Ok(result) => result,
        Err(_) => Err(format!(
            "recording_list refresh timed out after {}ms",
            refresh_timeout.as_millis()
        )),
    };
    let unsubscribe_result = bounded_ble_result(
        "unsubscribe recording_list refresh",
        refresh_timeout.min(StdDuration::from_secs(1)),
        peripheral.unsubscribe(&char_recording_list),
    )
    .await;
    let entries = combine_operation_and_cleanup(result, unsubscribe_result)?;
    if version2 { Ok(read_recording_catalog(device, characteristics).await?.entries) }
    else { Ok(entries) }
}

/// Product recording pull; measured rates are reported per codec and device:
/// - dual-lane notify 3003+3004 when present
/// - compact intermediate 20B / payload ≤224 (firmware ATT 244)
/// - raw STREAM_ALL default; WithoutResponse START/resume
/// - scoped native WinRT throughput preference; final length/CRC/SHA required
const RECORDING_READY_BURST: usize = 32;

fn drain_ready_recording_chunks<S>(
    notifications: &mut S,
    pending: &mut pull_reorder::PendingChunks,
    entry_id: u32,
    offset: u32,
    dual_lane: bool,
) -> Result<usize, String>
where S: futures::Stream<Item = Result<pull_receiver::ReceivedNotification, String>> + Unpin {
    let mut count = 0;
    for _ in 0..RECORDING_READY_BURST {
        // Poll only buffered notifications: sleeping here delays processing
        // and checkpointing a complete burst while waiting for another one.
        let notification = match notifications.next().now_or_never() {
            Some(Some(value)) => value?,
            Some(None) => return Err("recording notification stream ended".into()),
            None => break,
        };
        count += 1;
        let arrived_at = notification.received_at;
        let notification = notification.notification;
        if notification.uuid != RECORDING_CHUNK_PULL_UUID
            && !(dual_lane && notification.uuid == RECORDING_CHUNK_PULL_B_UUID) { continue; }
        let chunk = parse_recording_chunk(&notification.value)?;
        if (chunk.recording_id == 0 || chunk.recording_id == entry_id) && chunk.byte_offset >= offset {
            pending.insert_at(chunk, offset, arrived_at);
        }
    }
    Ok(count)
}

async fn pull_recording_bytes(
    device: &NativeDevice,
    characteristics: &std::collections::BTreeSet<Characteristic>,
    session: &mut Option<PullSession>,
    entry: &RecordingEntry,
    device_address: &str,
    device_address_type: Option<AddressType>,
    initial_data: Option<Vec<u8>>,
    job: Option<&RecordingSyncJob>,
    link_policy: Option<&mut SealedLinkPolicy>,
) -> Result<Vec<u8>, String> {
    let sealed_original = entry.sync_state == RECORDING_SYNC_UNSYNCED
        && initial_data.is_none() && !recording_wire_ima_requested(entry.codec);
    let mut port = RecordingPull { device, characteristics, session, entry,
        device_address, device_address_type, initial_data, job, link_policy };
    pull_recovery::receive(&mut port, sealed_original, entry.recording_id).await
}

struct RecordingPull<'a> {
    device: &'a NativeDevice,
    characteristics: &'a std::collections::BTreeSet<Characteristic>,
    session: &'a mut Option<PullSession>,
    entry: &'a RecordingEntry,
    device_address: &'a str,
    device_address_type: Option<AddressType>,
    initial_data: Option<Vec<u8>>,
    job: Option<&'a RecordingSyncJob>,
    link_policy: Option<&'a mut SealedLinkPolicy>,
}
impl pull_recovery::Attempt for RecordingPull<'_> {
    fn receive(&mut self) -> futures::future::BoxFuture<'_, Result<Vec<u8>, String>> {
        Box::pin(async move {
            let result=on_native_link(self.device, pull_recording_bytes_once(&self.device.peripheral, self.characteristics,
                self.session, self.entry, self.device_address, self.device_address_type,
                self.initial_data.take(), self.job, self.link_policy.as_deref_mut())).await;
            // A session loss can cancel an in-flight receive. Join/drain its
            // durable cursor first, then retire both owned notification lanes.
            if result.is_err() { PullSession::close(self.session).await; }
            result
        })
    }
}

async fn pull_recording_bytes_once(
    peripheral: &Peripheral,
    characteristics: &std::collections::BTreeSet<Characteristic>,
    session: &mut Option<PullSession>,
    entry: &RecordingEntry,
    device_address: &str,
    device_address_type: Option<AddressType>,
    initial_data: Option<Vec<u8>>,
    job: Option<&RecordingSyncJob>,
    link_policy: Option<&mut SealedLinkPolicy>,
) -> Result<Vec<u8>, String> {
    if session.is_none() {
        let opening = PullSession::open(peripheral, characteristics,
            env_timeout("COMPANION_TYPE_BLE_READ_TIMEOUT_MS", 8_000));
        *session = Some(if let Some(job) = job { job.receive(opening).await? } else { opening.await? });
    }
    let work = pull_recording_bytes_in_session(peripheral,
        session.as_mut().expect("opened recording pull session"), entry,
        device_address, device_address_type, initial_data, job, link_policy);
    let result = if let Some(job) = job { job.receive(work).await } else { work.await };
    if result.is_err() {
        // Failed entry/window retries re-open both lanes. Successful prefixes
        // and backlog entries keep the same receiver until connection close.
        PullSession::close(session).await;
    }
    result
}

async fn pull_recording_bytes_in_session(
    peripheral: &Peripheral,
    session: &mut PullSession,
    entry: &RecordingEntry,
    device_address: &str,
    _device_address_type: Option<AddressType>,
    initial_data: Option<Vec<u8>>,
    job: Option<&RecordingSyncJob>,
    mut link_policy: Option<&mut SealedLinkPolicy>,
) -> Result<Vec<u8>, String> {
    let is_live_prefix = entry.sync_state == RECORDING_SYNC_TRANSFER_ACTIVE;
    let char_chunk_pull = session.chunk.clone();
    let dual_lane = session.dual_lane;
    let mut notifications = &mut session.notifications;
    let write_timeout = env_timeout("COMPANION_TYPE_BLE_WRITE_TIMEOUT_MS", 8_000);

    // Transfer stored compressed originals directly. Legacy PCM alone supports
    // opt-in additional wire IMA; never mutate a process-wide flag per recording.
    // Firmware sizes ATT packets (compact 20 + ≤224). Host only START/resume/drain.
    let compress = recording_wire_ima_requested(entry.codec);
    let req_flags = if compress {
        RECORDING_REQ_COMPRESS_IMA | RECORDING_REQ_STREAM_ALL
    } else {
        RECORDING_REQ_STREAM_ALL
    };

    let notify_timeout = StdDuration::from_millis(
        std::env::var("COMPANION_TYPE_BLE_NOTIFY_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(if compress { 20_000 } else { 45_000 }),
    );
    let inter_default = if compress { 1_200 } else { 800 };
    let inter_packet_timeout = StdDuration::from_millis(
        std::env::var("COMPANION_TYPE_BLE_INTER_PACKET_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(inter_default),
    );
    let mut resume_cursor = None;
    let mut data = if !compress && !is_live_prefix {
        let (mut cursor, mut bytes) = super::recording_transfer::ReceiveCursor::open(
            &native_recording_root()?, recording_transfer_source(device_address, entry)).await?;
        if let Some(prefix) = initial_data {
            if entry.segment.is_none() || prefix.len()>entry.total_length as usize {
                return Err("sealed prefix is not bound to a V2 descriptor".into());
            }
            let common=bytes.len().min(prefix.len());
            if bytes[..common]!=prefix[..common] { return Err("durable tail and sealed receive cursor disagree".into()); }
            if prefix.len()>bytes.len() {
                cursor.append(&prefix[bytes.len()..]).await?;cursor.checkpoint().await?;bytes=prefix;
            }
        }
        eprintln!("recording pull durable_resume id={} offset={}", entry.recording_id, bytes.len());
        resume_cursor = Some(cursor);
        bytes
    } else if let Some(bytes) = initial_data {
        if compress || bytes.len()>entry.total_length as usize {
            return Err("incremental recording cursor exceeds durable raw prefix".into());
        }
        bytes
    } else {
        Vec::with_capacity(entry.total_length as usize)
    };
    let mut offset = if compress { 0 } else { data.len() as u32 };
    let initial_offset = offset;
    if let Some(job) = job { job.received(offset); }
    if !compress && offset == entry.total_length {
        // Cursor::open checked the durable receipt and bytes. The caller still
        // checks the current catalog CRC/SHA, commits the host index, and waits
        // for the exact physical consume ACK. No zero-length radio START is
        // needed; the caller retains its preference through the consume receipt.
        eprintln!("recording pull verified_cached id={} bytes={} received_payload=0 physical_receipt_required=1",
            entry.recording_id, offset);
        return Ok(data);
    }
    // Sealed receive preferences belong to sync_native_recording_entry so they
    // also cover durable saving and consume. Live prefixes retain normal power
    // parameters and do not create a temporary throughput request here.
    let link_settle_ms = std::env::var("COMPANION_TYPE_BLE_LINK_SETTLE_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(0);
    if link_settle_ms > 0 {
        tokio::time::sleep(StdDuration::from_millis(link_settle_ms)).await;
    }
    eprintln!(
        "recording pull host=Type/btleplug product=negotiated_compact settle_ms={link_settle_ms} dual={dual_lane}"
    );
    let mut expected_sequence = 0_u32;
    let mut wire_bytes: u64 = 0;
    let mut final_sha256: Option<[u8; 32]> = if offset == entry.total_length {
        let digest = Sha256::digest(&data);
        let mut full = [0u8; 32];
        full.copy_from_slice(&digest);
        Some(full)
    } else {
        None
    };
    let mut pending = pull_reorder::PendingChunks::default();
    let mut arrival_timing = (!compress && !is_live_prefix).then(||
        pull_timing::PullTiming::new(entry.recording_id, initial_offset, entry.total_length));
    let transfer_started = std::time::Instant::now();
    // Product bulk: Write Without Response for START/resume (no ATT response RTT).
    let write_type = WriteType::WithoutResponse;
    let write_label = "without_response";
    eprintln!(
        "recording pull start source_total={} transport_ima={} flags=0x{:02x} write={} payload_max={} (stored codec={} stays original)",
        entry.total_length,
        compress,
        req_flags,
        write_label,
        RECORDING_CHUNK_PRODUCT_PAYLOAD_MAX,
        entry.codec
    );

    // One START with STREAM_ALL: stream the original stored bytes; optional
    // wire IMA applies only to legacy PCM, never a stored Opus/IMA original.
    let request = recording_entry_pull_request(entry, offset, req_flags)?;
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

    let mut progress = pull_progress::PullProgress::new(
        StdInstant::now(), offset, notify_timeout, inter_packet_timeout);
    let mut packets: u32 = 0;
    let test_hold_after_bytes = std::env::var("COMPANION_TYPE_TEST_HOLD_AFTER_BYTES")
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .unwrap_or(0);
    let test_hold_ms = std::env::var("COMPANION_TYPE_TEST_HOLD_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(0);
    let mut test_hold_done = false;
    let mut live_storage_error_retries = 0u8;
    let mut receive_store_us = 0u64;
    let mut receive_store_peak_us = 0u64;
    let mut receive_store_queue_wait_us = 0u64;
    let mut receive_store_drain_us = 0u64;
    // Read this diagnostic preference once, outside the notification loop.
    // Normal transfers check each packet as well as the final source hash.
    let skip_mid_crc = entry.segment.is_none() && entry.tail.is_none() && std::env::var("COMPANION_TYPE_BLE_SKIP_MID_CRC")
        .map(|v| {
            let t = v.trim();
            t == "1" || t.eq_ignore_ascii_case("true") || t.eq_ignore_ascii_case("on")
        })
        .unwrap_or(false);

    while offset < entry.total_length {
        if let Some((mut chunk, arrived_at)) = pending.take(offset) {
            if chunk.flags & RECORDING_CHUNK_ERROR_FLAG != 0 {
                let error_code = chunk.packet_crc32;
                if should_retry_live_storage_error(
                    is_live_prefix,
                    error_code,
                    live_storage_error_retries,
                ) {
                    live_storage_error_retries = live_storage_error_retries.saturating_add(1);
                    pending.clear();
                    eprintln!(
                        "recording pull live_storage_retry id={} offset={} code=0x{:08x} attempt={}/{} delay_ms={}",
                        entry.recording_id,
                        offset,
                        error_code,
                        live_storage_error_retries,
                        RECORDING_LIVE_STORAGE_RETRY_MAX,
                        RECORDING_LIVE_STORAGE_RETRY_DELAY_MS
                    );
                    sleep(StdDuration::from_millis(
                        RECORDING_LIVE_STORAGE_RETRY_DELAY_MS,
                    ))
                    .await;
                    let retry = recording_entry_pull_request(entry, offset, req_flags)?;
                    timeout(
                        write_timeout,
                        peripheral.write(&char_chunk_pull, &retry, write_type),
                    )
                    .await
                    .map_err(|_| "live storage retry write timed out".to_string())?
                    .map_err(|err| format!("live storage retry write: {err}"))?;
                    continue;
                }
                return Err(format!(
                    "recording chunk error at offset={offset}: code=0x{error_code:08x} live_storage_retries={live_storage_error_retries}"
                ));
            }
            live_storage_error_retries = 0;
            // Product compact carries recording_id; slim (compat) may omit (0).
            if chunk.recording_id == 0 {
                chunk.recording_id = entry.recording_id;
            } else if chunk.recording_id != entry.recording_id {
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
            } else if !is_live_prefix && chunk.total_length != entry.total_length {
                return Err("recording total_length changed during transfer".to_string());
            }
            if chunk.payload_length as usize != chunk.payload.len() {
                return Err("recording chunk payload_length mismatch".to_string());
            }
            if !skip_mid_crc {
                let packet_crc = recording_packet_crc32(&chunk);
                if packet_crc != chunk.packet_crc32 {
                    return Err(format!(
                        "recording packet CRC mismatch at offset={offset}: got 0x{packet_crc:08x}, expected 0x{:08x}",
                        chunk.packet_crc32
                    ));
                }
            }

            wire_bytes += chunk.payload.len() as u64;
            if offset != chunk.byte_offset {
                return Err(format!(
                    "recording offset mismatch: host={offset} device={}",
                    chunk.byte_offset
                ));
            }
            // Compress: defer IMA decode until after last notify so wall-clock wire
            // is not inflated by host CPU (measure air throughput honestly).
            let pcm_advance = if chunk.flags & RECORDING_CHUNK_COMPRESSED_IMA_FLAG != 0 {
                if chunk.payload.len() < 6 {
                    return Err("IMA frame too short for sample count".to_string());
                }
                let samples = u16::from_le_bytes([chunk.payload[4], chunk.payload[5]]) as u32;
                // HALF_RATE_8K: frame samples are 8 kHz; 16 kHz domain advances ×4 bytes/sample.
                if chunk.flags & RECORDING_CHUNK_HALF_RATE_8K_FLAG != 0 {
                    samples.saturating_mul(4)
                } else {
                    samples.saturating_mul(2)
                }
            } else {
                chunk.payload.len() as u32
            };
            if !is_live_prefix && !chunk.payload.is_empty() {
                if let Some(policy) = link_policy.as_deref_mut() { policy.verified_payload(); }
            }
            if let Some(timing) = arrival_timing.as_mut() {
                timing.validated(chunk.byte_offset, chunk.payload.len(), arrived_at);
            }
            if chunk.flags & RECORDING_CHUNK_COMPRESSED_IMA_FLAG != 0 {
                // stash: pcm_adv, plen, flags, payload
                data.extend_from_slice(&(pcm_advance as u32).to_le_bytes());
                data.extend_from_slice(&(chunk.payload.len() as u32).to_le_bytes());
                data.extend_from_slice(&(u32::from(chunk.flags)).to_le_bytes());
                data.extend_from_slice(&chunk.payload);
            } else {
                data.extend_from_slice(&chunk.payload);
                if let Some(cursor) = resume_cursor.as_mut() {
                    // A bounded worker batches file IO/checkpoints while this
                    // task continues draining notifications and validating CRC.
                    cursor.append(&chunk.payload).await?;
                    (receive_store_us, receive_store_peak_us, receive_store_queue_wait_us) = cursor.timing();
                    if !test_hold_done
                        && test_hold_after_bytes > 0
                        && test_hold_ms > 0
                        && offset.saturating_add(pcm_advance) >= test_hold_after_bytes
                    {
                        test_hold_done = true;
                        cursor.checkpoint().await?;
                        eprintln!(
                            "recording pull test_hold durable_offset={} hold_ms={}",
                            offset.saturating_add(pcm_advance),
                            test_hold_ms
                        );
                        tokio::time::sleep(StdDuration::from_millis(test_hold_ms)).await;
                    }
                }
            }
            offset = offset.saturating_add(pcm_advance);
            progress.advanced(offset, StdInstant::now());
            if let Some(job) = job { job.received(offset); }
            expected_sequence += 1;
            packets += 1;
            pending.validated(arrived_at);

            // Log every 250 packets (was 50) — eprint under multi-notify flood costs host CPU.
            if packets % 250 == 0 || offset >= entry.total_length {
                let elapsed = transfer_started.elapsed().as_secs_f64().max(0.001);
                let wire_rate = (wire_bytes as f64 / 1024.0) / elapsed;
                let cruise = pending.elapsed_seconds()
                    .map(|e| (wire_bytes as f64 / 1024.0) / e)
                    .unwrap_or(wire_rate);
                let effective_rate = (offset.saturating_sub(initial_offset) as f64 / 1024.0) / elapsed;
                eprintln!(
                    "recording pull progress payload={}/{} wire={} packets={} wire_rate={:.1} KiB/s cruise_rate={:.1} KiB/s effective_rate={:.1} KiB/s transport_ima={} receive_store_ms={:.3} receive_store_peak_ms={:.3} receive_store_queue_wait_ms={:.3}",
                    offset,
                    entry.total_length,
                    wire_bytes,
                    packets,
                    wire_rate,
                    cruise,
                    effective_rate,
                    compress,
                    receive_store_us as f64 / 1000.0,
                    receive_store_peak_us as f64 / 1000.0,
                    receive_store_queue_wait_us as f64 / 1000.0
                );
            }
            if chunk.flags & RECORDING_CHUNK_FINAL_FLAG != 0 {
                final_sha256 = Some(chunk.final_sha256);
                break;
            }
            continue;
        }

        if !is_live_prefix && pending.full_gap(offset) {
            progress.missing_offset();
        }
        let wait = match progress.next(StdInstant::now()) {
            pull_progress::Next::Wait(remaining) => remaining.min(StdDuration::from_millis(50)),
            pull_progress::Next::Retry(attempt) => {
                // A missing offset, not raw notification traffic, controls
                // retries. This also paces first-packet re-arms and bounds an
                // established stall so connection/power cleanup can run.
                let resume = recording_entry_pull_request(entry, offset, req_flags)?;
                eprintln!("recording pull resume id={} offset={} attempt={} validated_progress_only=1",
                    entry.recording_id, offset, attempt);
                timeout(
                    progress.write_budget(StdInstant::now(), write_timeout),
                    peripheral.write(&char_chunk_pull, &resume, write_type),
                )
                .await
                .map_err(|_| "resume write timed out".to_string())?
                .map_err(|err| format!("resume write: {err}"))?;
                continue;
            },
            pull_progress::Next::FirstPacketTimeout => {
                return Err(format!("recording chunk notify timeout at offset={offset}; original recording not consumed"));
            },
            pull_progress::Next::Stalled => {
                return Err(format!("recording transfer stalled after 3 resume requests at offset={offset}; original recording not consumed"));
            },
        };

        let is_chunk_uuid = |u: Uuid| {
            u == RECORDING_CHUNK_PULL_UUID || (dual_lane && u == RECORDING_CHUNK_PULL_B_UUID)
        };
        let chunk_result = timeout(wait, async {
            loop {
                let notification = notifications
                    .next()
                    .await
                    .ok_or_else(|| "recording notification stream ended".to_string())??;
                let arrived_at = notification.received_at;
                let notification = notification.notification;
                if !is_chunk_uuid(notification.uuid) {
                    continue;
                }
                return parse_recording_chunk(&notification.value).map(|parsed| (parsed, arrived_at));
            }
        })
        .await;

        match chunk_result {
            Ok(Ok((parsed, arrived_at))) => {
                // Accept product compact id match, or slim-compat id omitted (0).
                if (parsed.recording_id == 0 || parsed.recording_id == entry.recording_id)
                    && parsed.byte_offset >= offset
                {
                    pending.insert_at(parsed, offset, arrived_at);
                }
                // Bound the burst before returning to ordered CRC validation,
                // the durable cursor and the transfer deadline. Both notify
                // lanes still feed the same absolute-offset reorder map.
                drain_ready_recording_chunks(&mut notifications, &mut pending,
                    entry.recording_id, offset, dual_lane)?;
            }
            Ok(Err(err)) => return Err(err),
            Err(_) => continue,
        }
    }

    // Stop wall-clock for wire before optional host-side IMA decode.
    let elapsed_air = transfer_started.elapsed().as_secs_f64().max(0.001);

    if compress {
        // stash: [pcm_adv u32][plen u32][flags u32][payload...]
        let mut decoded = Vec::with_capacity(entry.total_length as usize);
        let mut i = 0usize;
        while i + 12 <= data.len() {
            let pcm_adv = u32::from_le_bytes(data[i..i + 4].try_into().unwrap()) as usize;
            let plen = u32::from_le_bytes(data[i + 4..i + 8].try_into().unwrap()) as usize;
            let flags = u32::from_le_bytes(data[i + 8..i + 12].try_into().unwrap()) as u8;
            i += 12;
            if i + plen > data.len() {
                return Err("compressed frame stash truncated".to_string());
            }
            let frame = &data[i..i + plen];
            i += plen;
            let mut piece = decode_ima_adpcm_frame(frame)?;
            if flags & RECORDING_CHUNK_HALF_RATE_8K_FLAG != 0 {
                piece = upsample_pcm16_x2(&piece)?;
            }
            if piece.len() != pcm_adv {
                return Err(format!(
                    "IMA pcm length mismatch: frame {} vs header {pcm_adv} half={}",
                    piece.len(),
                    flags & RECORDING_CHUNK_HALF_RATE_8K_FLAG != 0
                ));
            }
            decoded.extend_from_slice(&piece);
        }
        data = decoded;
    }

    /* Capture can commit another NOR page while a live-prefix pull is in
     * flight. The online consumer owns the list snapshot it requested; bytes
     * beyond that snapshot remain durable on the board and are consumed by the
     * next absolute-offset snapshot. A trailing partial COP1 packet is safe:
     * the platform decoder deliberately stops at the last complete packet. */
    if is_live_prefix && data.len() > entry.total_length as usize {
        data.truncate(entry.total_length as usize);
    }

    if data.len() != entry.total_length as usize {
        return Err(format!(
            "recording byte count mismatch: got {}, expected {}",
            data.len(),
            entry.total_length
        ));
    }
    let sha256 = Sha256::digest(&data);
    let final_sha256 = if is_live_prefix {
        final_sha256.unwrap_or([0u8; 32])
    } else {
        final_sha256.ok_or_else(|| "final recording chunk did not include SHA-256".to_string())?
    };
    // Lossy IMA: length + packet CRC already enforced; raw path requires full SHA match
    // unless COMPANION_TYPE_BLE_SKIP_FINAL_SHA=1 (virtual 10min wire package).
    let skip_final_sha = is_live_prefix
        || (entry.segment.is_none() && std::env::var("COMPANION_TYPE_BLE_SKIP_FINAL_SHA")
            .map(|v| {
                let t = v.trim();
                t == "1" || t.eq_ignore_ascii_case("true") || t.eq_ignore_ascii_case("on")
            })
            .unwrap_or(false));
    if !compress && !skip_final_sha && sha256[..] != final_sha256 {
        return Err(format!(
            "final SHA mismatch: device={} host={}",
            hex_lower(&final_sha256),
            hex_lower(&sha256)
        ));
    }
    if let Some(cursor) = resume_cursor.as_mut() {
        let started = StdInstant::now();
        let digest: [u8; 32] = sha256.into();
        cursor.finish(data.len(), digest, crc32fast::hash(&data)).await?;
        receive_store_drain_us = started.elapsed().as_micros().min(u128::from(u64::MAX)) as u64;
        (receive_store_us, receive_store_peak_us, _) = cursor.timing();
    }
    drop(resume_cursor);
    if skip_final_sha {
        eprintln!(
            "recording pull skip_final_sha=1 (wire timing; host_sha={} device_sha={})",
            hex_lower(&sha256),
            hex_lower(&final_sha256)
        );
    }
    // Notification payload rate from first packet to last, excluding arming.
    // This includes waits between packets, not BLE protocol/radio overhead.
    let elapsed = pending.elapsed_seconds().unwrap_or(elapsed_air);
    if let Some(timing) = arrival_timing.as_mut() { timing.completed(); }
    for line in super::recording_metrics::diagnostics(super::recording_metrics::CompletedPull {
        codec: entry.codec, directory_duration_ms: entry.duration_ms,
        payload_bytes: data.len(), received_payload_bytes: offset.saturating_sub(initial_offset),
        wire_bytes, packets: packets as u64, elapsed_s: elapsed,
        transport_ima: compress, dual_lane, settle_ms: link_settle_ms, live_prefix: is_live_prefix,
        receive_store_us, receive_store_peak_us, receive_store_queue_wait_us, receive_store_drain_us,
    }) {
        eprintln!("{line}");
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
    super::recording_wire::decode_v1(payload).map(|entries| entries.into_iter().map(|entry| RecordingEntry {
        capture_incomplete: entry.capture_incomplete, recording_id: entry.recording_id,
        started_unix_s: entry.started_unix_s, duration_ms: entry.duration_ms,
        codec: entry.codec, sync_state: entry.sync_state, source_mode: entry.source_mode,
        total_length: entry.total_length, sha256_prefix: entry.sha256_prefix, content_crc32: entry.content_crc32,
        segment: None, tail: None,
    }).collect())
}

fn parse_recording_chunk(payload: &[u8]) -> Result<RecordingChunk, String> {
    if payload.len()>509 {return Err("recording chunk exceeds supported ATT value ceiling".into());}
    // Need at least schema+flags+len before deciding header layout.
    if payload.len() < 4 {
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
    // Product: compact 20B intermediate. Compat: slim 12B. FINAL/ERROR: 56B. Legacy: 24B.
    let header_bytes =
        if flags & RECORDING_CHUNK_FINAL_FLAG != 0 || flags & RECORDING_CHUNK_ERROR_FLAG != 0 {
            RECORDING_CHUNK_HEADER_FULL_BYTES
        } else if flags & RECORDING_CHUNK_SLIM_FLAG != 0 {
            RECORDING_CHUNK_HEADER_SLIM_BYTES
        } else if flags & RECORDING_CHUNK_COMPACT_FLAG != 0 {
            RECORDING_CHUNK_HEADER_COMPACT_BYTES
        } else {
            RECORDING_CHUNK_HEADER_LEGACY_BASE_BYTES
        };
    if payload.len() < header_bytes {
        return Err(format!(
            "recording chunk header truncated: len={} flags=0x{:02x} need_hdr={}",
            payload.len(),
            flags,
            header_bytes
        ));
    }
    let payload_end = header_bytes + payload_length as usize;
    if payload.len() != payload_end {
        return Err(format!(
            "recording chunk payload truncated: len={} flags=0x{:02x} hdr={} claim_pl={} need={}",
            payload.len(),
            flags,
            header_bytes,
            payload_length,
            payload_end
        ));
    }
    let mut final_sha256 = [0_u8; 32];
    let (recording_id, packet_sequence, byte_offset, total_length, packet_crc32) =
        if header_bytes == RECORDING_CHUNK_HEADER_SLIM_BYTES {
            // id omitted (use list); no mid-stream CRC.
            (
                0_u32,
                le_u32(payload, 4)?,
                le_u32(payload, 8)?,
                0_u32,
                0_u32,
            )
        } else if header_bytes == RECORDING_CHUNK_HEADER_COMPACT_BYTES {
            (
                le_u32(payload, 4)?,
                le_u32(payload, 8)?,
                le_u32(payload, 12)?,
                0_u32,
                le_u32(payload, 16)?,
            )
        } else {
            if header_bytes == RECORDING_CHUNK_HEADER_FULL_BYTES {
                final_sha256.copy_from_slice(&payload[24..56]);
            }
            (
                le_u32(payload, 4)?,
                le_u32(payload, 8)?,
                le_u32(payload, 12)?,
                le_u32(payload, 16)?,
                le_u32(payload, 20)?,
            )
        };
    Ok(RecordingChunk {
        flags,
        payload_length,
        recording_id,
        packet_sequence,
        byte_offset,
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

fn recording_entry_pull_request(entry: &RecordingEntry, offset: u32, flags: u8) -> Result<Vec<u8>, String> {
    if let Some(tail)=entry.tail.as_ref() { return tail.pull(offset,flags); }
    if let Some(d) = entry.segment.as_ref() {
        let peer = super::recording_wire::transport::Peer {
            uid: d.key.device_uid, epoch: d.key.format_epoch, capacity: 64, max_value_bytes: 248, logical_control: false, growing_tail: false, pause_control: false, batch_interval: false,
        };
        peer.pull(d, offset, flags)
    } else {
        Ok(recording_chunk_pull_request_flags(entry.recording_id, offset,
            entry.total_length.saturating_sub(offset).min(u32::from(u16::MAX)) as u16, flags).to_vec())
    }
}

/// Decode one companion IMA-ADPCM frame (6B header + nibbles) to LE i16 PCM bytes.
fn decode_ima_adpcm_frame(frame: &[u8]) -> Result<Vec<u8>, String> {
    const STEP: [i32; 89] = [
        7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60,
        66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371,
        408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878,
        2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845,
        8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086,
        29794, 32767,
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

/// Linear upsample 8 kHz mono PCM16 → 16 kHz (COMP-REQ-666 Track A).
fn upsample_pcm16_x2(pcm8: &[u8]) -> Result<Vec<u8>, String> {
    if pcm8.len() % 2 != 0 {
        return Err("upsample input not even".to_string());
    }
    let n = pcm8.len() / 2;
    let mut out = Vec::with_capacity(pcm8.len() * 2);
    for i in 0..n {
        let s0 = i16::from_le_bytes([pcm8[i * 2], pcm8[i * 2 + 1]]) as i32;
        let s1 = if i + 1 < n {
            i16::from_le_bytes([pcm8[(i + 1) * 2], pcm8[(i + 1) * 2 + 1]]) as i32
        } else {
            s0
        };
        let mid = ((s0 + s1) / 2) as i16;
        out.extend_from_slice(&(s0 as i16).to_le_bytes());
        out.extend_from_slice(&mid.to_le_bytes());
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

/// Window request size (may exceed single ATT notify). Product payload max = 224 B.
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

fn native_recording_root() -> Result<PathBuf, String> {
    super::audio_storage::recording_root()
}

fn recording_transfer_source(device: &str, entry: &RecordingEntry) -> super::recording_transfer::Source {
    super::recording_transfer::Source {
        device: if let Some(d) = entry.segment.as_ref() {
            // Epoch/session/full digest isolate a reused physical ID from old
            // receive cursors without changing the legacy Source receipt schema.
            format!("{}#crv2:{}:{:016x}:{:016x}:{}:{}", device.trim().to_ascii_lowercase(),
                hex_lower(&d.key.device_uid), d.key.format_epoch, d.key.session_id,
                d.segment_index, hex_lower(&d.sha256))
        } else { device.trim().to_ascii_lowercase() }, recording_id: entry.recording_id,
        codec: entry.codec, source_mode: entry.source_mode, duration_ms: entry.duration_ms,
        total_length: entry.total_length, sha256_prefix: entry.sha256_prefix,
        content_crc32: entry.content_crc32,
    }
}
fn native_recording_partial_path(device: &str, entry: &RecordingEntry) -> Result<PathBuf, String> {
    super::recording_transfer::path(&native_recording_root()?, &recording_transfer_source(device, entry))
}

fn native_recording_output_path(recording_id: u32) -> Result<PathBuf, String> {
    let root = native_recording_root()?;
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|err| format!("clock before epoch: {err}"))?
        .as_secs();
    Ok(root.join(format!("{stamp}-device-recording-{recording_id}-{}.wav", uuid::Uuid::new_v4().simple())))
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
    file.sync_all().map_err(|err| format!("flush wav payload: {err}"))?;
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
    fn connect_transport_operation()->CompanionBleOperation {
        CompanionBleOperation{provider_id:"companion-type-windows-ble".into(),mode:"windows-native-connect-auto-upload-segmented".into(),
            ready:true,sync_paused:false,device_id:Some("C8:92:FF:DD:3B:CA".into()),recording_path:None,recordings:Vec::new(),
            device_identity:None,message:"protected GATT probe succeeded".into()}
    }
    #[test]
    fn connect_transport_failure_keeps_saved_rows_but_cannot_claim_connection_ready() {
        let mut operation=connect_transport_operation();
        complete_connect_sync(&mut operation,Ok(NativeRecordingBatch{
            device_id:"C8:92:FF:DD:3B:CA".into(),recordings:Vec::new(),
            failures:vec!["id18 offset2081: native GATT session lost".into()],paused:false,
            connection_reusable:false,segmented:Some(vec!["durable-partial-original".into()]),
        }));
        assert!(!operation.ready,"saved partials cannot prove the failed link is ready");
        assert_eq!(operation.mode,"windows-native-connect-auto-upload-segmented");
        assert!(operation.message.contains("id18 offset2081")&&operation.message.contains("continuous_sessions_saved=1"));
        assert_eq!(operation.device_id.as_deref(),Some("C8:92:FF:DD:3B:CA"));
        let mut wrong=connect_transport_operation();
        complete_connect_sync(&mut wrong,Ok(NativeRecordingBatch{device_id:"AA:BB:CC:DD:EE:FF".into(),recordings:Vec::new(),
            failures:Vec::new(),paused:false,connection_reusable:true,segmented:Some(vec!["foreign".into()])}));
        assert!(!wrong.ready&&wrong.message.contains("另一设备"));
    }
    #[test]
    fn connect_transport_success_pause_and_pairing_failure_have_distinct_outcomes() {
        for paused in [false,true] {
            let mut operation=connect_transport_operation();
            complete_connect_sync(&mut operation,Ok(NativeRecordingBatch{device_id:"C8:92:FF:DD:3B:CA".into(),recordings:Vec::new(),
                failures:Vec::new(),paused,connection_reusable:true,segmented:Some(Vec::new())}));
            assert!(operation.ready);assert_eq!(operation.sync_paused,paused);
        }
        let mut failed=connect_transport_operation();
        complete_connect_sync(&mut failed,Err("Windows BLE pairing required: Windows 状态19".into()));
        assert!(!failed.ready&&super::super::reconnect_requires_pairing(&failed.message));
    }

    use super::*;

    #[test]
    fn follower_reconnect_rejects_changed_uid_epoch_or_missing_v2() {
        use super::super::recording_wire::transport::Peer;
        let saved = Peer { uid: [3;12], epoch: 17, capacity: 64, max_value_bytes: 248, logical_control: false, growing_tail: false, pause_control: false, batch_interval: false };
        assert!(require_same_recorder(Some(&saved), Some(&saved)).is_ok());
        let mut changed = saved.clone(); changed.epoch += 1;
        assert!(require_same_recorder(Some(&saved), Some(&changed)).is_err());
        changed = saved.clone(); changed.uid[11] ^= 1;
        assert!(require_same_recorder(Some(&saved), Some(&changed)).is_err());
        assert!(require_same_recorder(Some(&saved), None).is_err());
        assert!(require_same_recorder(None, Some(&changed)).is_ok(), "explicit fresh Connect can negotiate a new recorder");
    }

    #[test]
    fn stop_saves_its_sealed_file_without_consuming_backlog_or_a_live_tail() {
        let entry = |id, state| RecordingEntry { segment: None, tail: None, capture_incomplete: false,
            recording_id: id, started_unix_s: 0, duration_ms: 10_000,
            codec: 3, sync_state: state, source_mode: 1, total_length: 21_000,
            sha256_prefix: [1; 8], content_crc32: 1 };
        let catalog = vec![entry(22, RECORDING_SYNC_TRANSFER_ACTIVE),
            entry(21, RECORDING_SYNC_UNSYNCED), entry(19, RECORDING_SYNC_UNSYNCED),
            entry(20, RECORDING_SYNC_UNSYNCED)];
        // The new production dispatcher must preserve the installed V1
        // START/resume wire and durable source key byte-for-byte.
        for offset in [0u32, 8_192u32] {
            assert_eq!(recording_entry_pull_request(&catalog[1], offset, 4).unwrap(),
                recording_chunk_pull_request_flags(21, offset, (21_000u32 - offset) as u16, 4));
        }
        assert_eq!(recording_transfer_source("C8:92:FF:DD:3B:CA", &catalog[1]).device,
            "c8:92:ff:dd:3b:ca");
        let ids = |items: Vec<RecordingEntry>| items.into_iter().map(|e| e.recording_id).collect::<Vec<_>>();
        assert_eq!(ids(pending_recordings(catalog.clone(), &[], Some(21))), [21]);
        assert_eq!(ids(pending_recordings(catalog.clone(), &[20], None)), [19, 21]);
        assert!(pending_recordings(catalog.clone(), &[], Some(22)).is_empty());
        assert!(pending_recordings(catalog, &[21], Some(21)).is_empty());
    }

    #[test]
    fn scan_exact_address_never_shortcuts_for_a_name_or_different_board() {
        let address = "C8:92:FF:DD:3B:CA";
        assert!(scan_exact_address_match(Some(" c8-92-ff-dd-3b-ca "), address));
        assert!(scan_exact_address_match(Some("C892FFDD3BCA"), address));
        for requested in [None, Some("Companion"), Some(""), Some("C8:92:FF:DD:3B:CB"),
            Some("C8:92:FF:DD:3B:C"), Some("target C892FFDD3BCA"), Some("C8:92:FF:DD:3B:CZ")] {
            assert!(!scan_exact_address_match(requested, address), "{requested:?}");
        }
        assert!(!scan_exact_address_match(Some(address), "prefix C892FFDD3BCA"));
    }

    #[test]
    fn ready_recording_burst_keeps_both_lanes_ordered_and_never_waits_for_future_packets() {
        let notification = |offset: u32, lane: Uuid| {
            let mut wire = vec![1, RECORDING_CHUNK_COMPACT_FLAG, 4, 0];
            for word in [17u32, offset / 4, offset, 0] { wire.extend_from_slice(&word.to_le_bytes()); }
            wire.extend_from_slice(&offset.to_le_bytes());
            Ok::<_, String>(pull_receiver::ReceivedNotification {
                notification: ValueNotification { uuid: lane, value: wire },
                received_at: StdInstant::now(),
            })
        };
        // Pairwise reversed delivery from the two channels must still produce
        // one ordered stream. A continuously ready producer cannot starve the
        // cursor forever, and a pending producer adds no timer wait.
        let queued = (0..40u32).map(|index| {
            let offset = (index ^ 1) * 4;
            notification(offset, if index % 2 == 0 { RECORDING_CHUNK_PULL_B_UUID } else { RECORDING_CHUNK_PULL_UUID })
        }).collect::<Vec<_>>();
        let mut stream = futures::stream::iter(queued).chain(futures::stream::pending());
        let mut pending = pull_reorder::PendingChunks::default();
        assert_eq!(drain_ready_recording_chunks(&mut stream, &mut pending, 17, 0, true).unwrap(), 32);
        assert_eq!(pending.offsets(), (0..32).map(|n| n * 4).collect::<Vec<_>>());
        assert_eq!(drain_ready_recording_chunks(&mut stream, &mut pending, 17, 0, true).unwrap(), 8);
        assert_eq!(pending.len(), 40);
        assert_eq!(drain_ready_recording_chunks(&mut stream, &mut pending, 17, 0, true).unwrap(), 0);
        let mut malformed = futures::stream::iter([Ok::<_, String>(pull_receiver::ReceivedNotification {
            notification: ValueNotification { uuid: RECORDING_CHUNK_PULL_B_UUID, value: vec![1] },
            received_at: StdInstant::now(),
        })])
            .chain(futures::stream::pending());
        assert!(drain_ready_recording_chunks(&mut malformed, &mut pending, 17, 0, true).is_err());
    }
    #[test]
    fn compressed_originals_ignore_legacy_wire_ima_request() {
        assert!(recording_wire_ima_allowed(RECORDING_CODEC_PCM16_MONO, true));
        assert!(!recording_wire_ima_allowed(RECORDING_CODEC_PCM16_MONO, false));
        for codec in [RECORDING_CODEC_HALF_IMA, RECORDING_CODEC_OPUS16, 0, 255] {
            assert!(!recording_wire_ima_allowed(codec, true));
            assert!(!recording_wire_ima_allowed(codec, false));
        }
    }

    #[test]
    fn storage_full_receipts_are_specific_and_never_accept_stale_or_malformed_echoes() {
        let mut echo = recording_control_request(RECORDING_CONTROL_START, 17, 60);
        assert!(recording_control_echo_matches(&echo, 17, RECORDING_CONTROL_START).unwrap());
        echo[3] = RECORDING_CONTROL_ERROR_FLAG | RECORDING_CONTROL_STORAGE_FULL_FLAG;
        assert!(recording_control_echo_matches(&echo, 18, RECORDING_CONTROL_START).is_ok_and(|v| !v));
        assert_eq!(recording_control_echo_matches(&echo, 17, RECORDING_CONTROL_START).unwrap_err(), STORAGE_FULL_MESSAGE);
        echo[3] = RECORDING_CONTROL_ERROR_FLAG;
        assert!(!recording_control_echo_matches(&echo, 17, RECORDING_CONTROL_START).unwrap_err().contains("存储已满"));
        echo[3] = RECORDING_CONTROL_STORAGE_FULL_FLAG;
        assert!(recording_control_echo_matches(&echo, 17, RECORDING_CONTROL_START).is_err());
        for length in 0..10 { assert!(recording_control_echo_matches(&echo[..length], 17, 1).is_err()); }
        echo[0] = 2;
        assert!(recording_control_echo_matches(&echo, 17, 1).is_err());
        assert_eq!(meeting_control_failure(3, 1, 17), STORAGE_FULL_MESSAGE);
        assert!(!meeting_control_failure(2, 1, 17).contains("存储已满"));
    }

    #[test]
    fn ble_name_wire_request_and_receipt_are_exact_and_fail_closed() {
        let request = ble_name_request(BLE_NAME_STAGE, 17, Some("Companion One")).unwrap();
        assert_eq!(request.len(), BLE_NAME_CONFIG_BYTES);
        assert_eq!(&request[..2], &[1, BLE_NAME_STAGE]);
        assert_eq!(u32::from_le_bytes(request[4..8].try_into().unwrap()), 17);
        assert_eq!(request[8], 13);
        assert_eq!(&request[12..25], b"Companion One");

        let mut receipt = ble_name_request(BLE_NAME_APPLY, 18, Some("Companion One")).unwrap();
        receipt[10] = 0;
        assert_eq!(
            parse_ble_name_receipt(&receipt, BLE_NAME_APPLY, 18).unwrap(),
            "Companion One"
        );
        receipt[10] = 4;
        assert!(parse_ble_name_receipt(&receipt, BLE_NAME_APPLY, 18)
            .unwrap_err()
            .contains("status=4"));
        receipt[10] = 0;
        assert!(parse_ble_name_receipt(&receipt, BLE_NAME_APPLY, 19).is_err());
        assert!(ble_name_request(BLE_NAME_STAGE, 1, Some("bad=name")).is_err());
    }

    #[tokio::test]
    async fn bounded_ble_result_covers_success_error_and_pending_timeout() {
        let success = bounded_ble_result(
            "success",
            StdDuration::from_millis(50),
            std::future::ready(Ok::<u8, &'static str>(7)),
        )
        .await;
        assert_eq!(success.unwrap(), 7);

        let failure = bounded_ble_result(
            "failure",
            StdDuration::from_millis(50),
            std::future::ready(Err::<u8, &'static str>("transport")),
        )
        .await;
        assert!(failure.is_err());

        let pending = bounded_ble_result(
            "pending",
            StdDuration::from_millis(1),
            std::future::pending::<Result<u8, &'static str>>(),
        )
        .await;
        assert!(pending.is_err());

        let expired = remaining_deadline_budget(
            StdInstant::now() - StdDuration::from_millis(1),
            StdDuration::from_secs(1),
        );
        assert!(expired.is_zero());

        let polled = Arc::new(AtomicBool::new(false));
        let observed = Arc::clone(&polled);
        let zero_budget = bounded_ble_result(
            "expired",
            StdDuration::ZERO,
            std::future::poll_fn(move |_| {
                observed.store(true, Ordering::SeqCst);
                std::task::Poll::Ready(Ok::<u8, &'static str>(9))
            }),
        )
        .await;
        assert!(zero_budget.is_err());
        assert!(!polled.load(Ordering::SeqCst));

        let primary = combine_operation_and_cleanup::<u8>(
            Err("notification failed".to_string()),
            Err("cleanup timed out".to_string()),
        );
        assert_eq!(primary.unwrap_err(), "notification failed");
        let cleanup = combine_operation_and_cleanup(Ok(7u8), Err("cleanup timed out".to_string()));
        assert_eq!(cleanup.unwrap_err(), "cleanup timed out");
    }

    #[test]
    fn wba_identity_and_capabilities_decode_only_from_valid_wire_status() {
        let mut device = [0u8; 36];
        device[0] = 1;
        device[1] = 1;
        device[4..8].copy_from_slice(&0x0001_0101u32.to_le_bytes());
        device[8..12].copy_from_slice(&0x2026_1003u32.to_le_bytes());
        device[12..16].copy_from_slice(&0x5742_4155u32.to_le_bytes());
        device[20..32].copy_from_slice(&[
            0x10, 0x32, 0x54, 0x76, 0x98, 0xba, 0xdc, 0xfe, 0x01, 0x23, 0x45, 0x67,
        ]);
        device[32..36].copy_from_slice(&33u32.to_le_bytes());
        let mut imu = [0u8; 26];
        imu[0] = 1;
        imu[1] = 2;
        imu[4..6].copy_from_slice(&52u16.to_le_bytes());
        let mut speaker = [0u8; 16];
        speaker[0] = 1;
        speaker[1] = 4;
        speaker[3] = 65;
        let identity = parse_device_identity(Some(&device), Some(&imu), Some(&speaker));
        assert_eq!(identity.firmware_version, Some(0x0001_0101));
        assert_eq!(identity.build_id, Some(0x2026_1003));
        assert_eq!(identity.board_id, Some(0x5742_4155));
        assert_eq!(
            identity.mcu_uid.as_deref(),
            Some("1032547698badcfe01234567")
        );
        assert_eq!(identity.ui_generation, Some(33));
        assert_eq!(identity.recording, Some(true));
        assert_eq!(identity.imu_supported, Some(true));
        assert_eq!(identity.imu_online, Some(true));
        assert_eq!(identity.imu_sample_hz, Some(52));
        assert_eq!(identity.speaker_supported, Some(true));
        assert_eq!(identity.speaker_online, Some(true));
        assert_eq!(identity.speaker_volume, Some(65));

        let legacy = parse_device_identity(Some(&device[..20]), None, None);
        assert_eq!(legacy.firmware_version, Some(0x0001_0101));
        assert_eq!(legacy.mcu_uid, None);
        assert_eq!(legacy.ui_generation, None);

        let unknown = parse_device_identity(Some(&device[..19]), None, Some(&[2, 4, 0, 65]));
        assert_eq!(unknown.firmware_version, None);
        assert_eq!(unknown.recording, None);
        assert_eq!(unknown.imu_supported, None);
        assert_eq!(unknown.speaker_supported, None);

        device[1] = 0;
        assert_eq!(parse_device_identity(Some(&device), None, None).recording, Some(false));
        device[1] = 2;
        assert_eq!(parse_device_identity(Some(&device), None, None).recording, None);
        assert!(!should_auto_pull_recordings(Some(true), 3));
        assert!(!should_auto_pull_recordings(None, 3));
        assert!(should_auto_pull_recordings(Some(false), 3));
        assert!(!should_auto_pull_recordings(Some(false), 0));
    }

    #[test]
    fn wb_not_populated_status_stays_explicitly_unsupported() {
        let mut imu = [0u8; 26];
        imu[0] = 1;
        imu[1] = 1;
        let mut speaker = [0u8; 16];
        speaker[0] = 1;
        speaker[1] = 1;
        let identity = parse_device_identity(None, Some(&imu), Some(&speaker));
        assert_eq!(identity.imu_supported, Some(false));
        assert_eq!(identity.speaker_supported, Some(false));
        assert_eq!(identity.firmware_version, None);
    }

    #[test]
    fn speaker_prompt_wire_and_status_match_firmware_layout() {
        assert_eq!(
            speaker_control_request(0x1122_3344, 65, 0),
            [1, 1, 65, 0, 0x44, 0x33, 0x22, 0x11, 0, 0, 0, 0]
        );
        let status = [1, 2, 0, 65, 0x44, 0x33, 0x22, 0x11, 0, 0, 0, 0, 3, 0, 0, 0];
        assert_eq!(
            parse_speaker_status(&status).unwrap(),
            (2, 0, 65, 0x1122_3344)
        );
        assert!(parse_speaker_status(&status[..15]).is_err());
    }

    #[test]
    fn capability_probe_timeout_is_bounded_below_connect_timeout() {
        assert_eq!(
            OPTIONAL_STATUS_READ_TIMEOUT,
            StdDuration::from_millis(2_500)
        );
        assert!(OPTIONAL_STATUS_READ_TIMEOUT < StdDuration::from_secs(3));
        assert!(status_needs_publish_retry(&[], 16));
        assert!(status_needs_publish_retry(&[0; 16], 16));
        assert!(status_needs_publish_retry(&[1; 15], 16));
        assert!(!status_needs_publish_retry(&[1; 16], 16));
        // A future nonzero schema is not retried into accidental support; the
        // strict parser below still maps it to unknown.
        assert!(!status_needs_publish_retry(&[2; 16], 16));
    }

    #[test]
    fn oobe_clock_readback_requires_valid_matching_device_evidence() {
        let mut exact = vec![0u8; 10];
        exact.extend_from_slice(&[23, 59, 59]);
        assert!(verify_clock_readback([23, 59, 59], &exact).is_ok());

        let mut midnight = vec![0u8; 10];
        midnight.extend_from_slice(&[0, 0, 0]);
        assert!(verify_clock_readback([23, 59, 59], &midnight).is_ok());
        assert!(verify_clock_readback([12, 0, 0], &[0u8; 10]).is_err());

        let mut invalid = vec![0u8; 10];
        invalid.extend_from_slice(&[24, 0, 0]);
        assert!(verify_clock_readback([0, 0, 0], &invalid).is_err());

        let mut stale = vec![0u8; 10];
        stale.extend_from_slice(&[10, 0, 10]);
        assert!(verify_clock_readback([10, 0, 0], &stale).is_err());
    }

    #[test]
    fn live_storage_errors_are_bounded_recoverable_only_during_active_capture() {
        assert!(should_retry_live_storage_error(true, 0x0000_1001, 0));
        assert!(should_retry_live_storage_error(true, 0x0000_1002, 3));
        assert!(!should_retry_live_storage_error(
            true,
            0x0000_1001,
            RECORDING_LIVE_STORAGE_RETRY_MAX
        ));
        assert!(!should_retry_live_storage_error(false, 0x0000_1001, 0));
        assert!(!should_retry_live_storage_error(true, 0x0000_0005, 0));
    }

    #[test]
    fn final_pull_reconnect_is_bounded_and_transport_only() {
        assert!(should_reconnect_final_pull(
            "resume write: Error { code: HRESULT(0x80000013), message: \"object closed\" }",
            0,
        ));
        assert!(should_reconnect_final_pull(
            "resume write: Error { code: HRESULT(0x80000013), message: \"该对象已关闭。\" }",
            0,
        ));
        assert!(should_reconnect_final_pull(
            "recording notification stream ended",
            2,
        ));
        assert!(should_reconnect_final_pull(
            "recording chunk notify timeout at offset=0",
            0,
        ));
        assert!(should_reconnect_final_pull(
            "resume write: Windows UWP threw error on write: GattCommunicationStatus(1)",
            0,
        ));
        assert!(should_reconnect_final_pull(
            "recording transfer stalled after 3 resume requests at offset=224; original recording not consumed",
            0,
        ));
        // Queue-only recovery already exhausted its own finite subscription
        // restart budget; do not multiply it into a reconnect loop here.
        assert!(!should_reconnect_final_pull(
            "recording receive queue overflow; original recording not consumed",
            0,
        ));
        assert!(!should_reconnect_final_pull(
            "recording SHA prefix mismatch",
            0,
        ));
        assert!(!should_reconnect_final_pull(
            "resume write timed out",
            RECORDING_FINAL_PULL_RECONNECT_MAX,
        ));
    }

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
        let connect = bridge.connect(Some("manual-device"), &[]);
        assert_eq!(connect.device_id.as_deref(), Some("manual-device"));
        std::env::remove_var("COMPANION_TYPE_BLE_NATIVE_READY");
        std::env::remove_var("COMPANION_TYPE_BLE_DEVICE_ID");
    }

    #[test]
    fn meeting_control_wire_contract_selects_real_board_microphone() {
        assert_eq!(
            meeting_control_request(1, 0x7856_3412, 600),
            [1, 1, 0, 0, 0x12, 0x34, 0x56, 0x78, 0x58, 0x02, 2, 0]
        );
    }

    #[test]
    fn meeting_idempotency_key_is_stable_per_session_action() {
        let first = meeting_idempotency_request_id("meeting-owner-42", 1);
        assert_ne!(first, 0);
        assert_eq!(first, meeting_idempotency_request_id("meeting-owner-42", 1));
        assert_ne!(first, meeting_idempotency_request_id("meeting-owner-42", 2));
        assert_ne!(first, meeting_idempotency_request_id("meeting-owner-43", 1));
    }

    #[test]
    fn meeting_status_parser_uses_real_recording_identity() {
        let mut payload = [0_u8; 28];
        payload[0] = 1;
        payload[1] = MEETING_STATE_RECORDING;
        payload[8..12].copy_from_slice(&0x1122_3344_u32.to_le_bytes());
        payload[12..16].copy_from_slice(&37_u32.to_le_bytes());
        payload[20..24].copy_from_slice(&1_920_u32.to_le_bytes());
        payload[24] = 3;

        let parsed = parse_meeting_status(&payload).unwrap();
        assert_eq!(parsed.request_id, 0x1122_3344);
        assert_eq!(parsed.meeting_id, 37);
        assert_eq!(parsed.duration_ms, 1_920);
        assert_eq!(parsed.sync_state, 3);
        assert_eq!(parsed.last_error, 0);
    }

    #[test]
    fn control_route_native_reconnect_accepts_only_original_recording_and_request() {
        let start = meeting_idempotency_request_id("original-reconnected", 1);
        let identity = MeetingControlIdentity::for_session("original-reconnected", 18);
        for command in [2, 3] {
            let request = meeting_idempotency_request_id("original-reconnected", command);
            for state in [MEETING_STATE_RECORDING, MEETING_STATE_FINALIZED] {
                for observed_request in [start, request] {
                    let mut wire = [0u8; 28];
                    wire[0] = 1;
                    wire[1] = state;
                    wire[8..12].copy_from_slice(&observed_request.to_le_bytes());
                    wire[12..16].copy_from_slice(&18u32.to_le_bytes());
                    let status = parse_meeting_status(&wire).unwrap();
                    verify_meeting_control_target(&status, &identity).unwrap();
                }
            }
        }
    }

    #[test]
    fn control_route_native_finalize_accepts_the_original_stop_before_its_write() {
        // Firmware keeps request_id=STOP in its protected status until the
        // subsequent FINALIZE write. That is still the same owned meeting.
        let stop = meeting_idempotency_request_id("original-reconnected", 2);
        let mut wire = [0u8; 28];
        wire[0] = 1;
        wire[1] = MEETING_STATE_FINALIZED;
        wire[8..12].copy_from_slice(&stop.to_le_bytes());
        wire[12..16].copy_from_slice(&18u32.to_le_bytes());
        let status = parse_meeting_status(&wire).unwrap();
        let identity = MeetingControlIdentity::for_session("original-reconnected", 18);
        verify_meeting_control_target(&status, &identity)
            .expect("normal FINALIZE after this meeting's STOP must remain available");
    }

    #[test]
    fn control_route_native_reconnect_rejects_replaced_recording_and_invalid_ack() {
        let start = meeting_idempotency_request_id("original-reconnected", 1);
        let stop = meeting_idempotency_request_id("original-reconnected", 2);
        for failure in ["another_recording", "zero_recording", "unknown_original",
            "other_start", "other_stop", "idle", "unknown_state", "board_error"] {
            let mut wire = [0u8; 28];
            wire[0] = 1;
            wire[1] = MEETING_STATE_RECORDING;
            wire[8..12].copy_from_slice(&start.to_le_bytes());
            wire[12..16].copy_from_slice(&18u32.to_le_bytes());
            let mut expected = 18;
            match failure {
                "another_recording" => wire[12..16].copy_from_slice(&19u32.to_le_bytes()),
                "zero_recording" => wire[12..16].fill(0),
                "unknown_original" => expected = 0,
                "other_start" => wire[8..12].copy_from_slice(
                    &meeting_idempotency_request_id("different-meeting", 1).to_le_bytes()),
                "other_stop" => wire[8..12].copy_from_slice(
                    &meeting_idempotency_request_id("different-meeting", 2).to_le_bytes()),
                "idle" => wire[1] = 0,
                "unknown_state" => wire[1] = 3,
                "board_error" => wire[2] = 1,
                _ => unreachable!(),
            }
            let status = parse_meeting_status(&wire).unwrap();
            let identity = MeetingControlIdentity::for_session("original-reconnected", expected);
            assert!(verify_meeting_control_target(&status, &identity).is_err(), "{failure}");
            // Apply the same validation to a matching STOP ACK: the request ID
            // alone cannot authorize a different recording or error state.
            if !matches!(failure, "other_start" | "other_stop") {
                wire[8..12].copy_from_slice(&stop.to_le_bytes());
                let status = parse_meeting_status(&wire).unwrap();
                assert!(verify_meeting_control_target(&status, &identity).is_err(), "ACK/{failure}");
            }
        }
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
        assert!(!entries[0].capture_incomplete);
        payload[4 + 15] = 1;
        assert!(parse_recording_list(&payload).unwrap()[0].capture_incomplete);
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
    fn recording_chunk_parser_accepts_intermediate_max509_value_compact_header() {
        // Negotiated product compact intermediate: 20B header plus489B payload.
        let payload_bytes = vec![0xA5_u8; RECORDING_CHUNK_PRODUCT_PAYLOAD_MAX];
        let mut chunk = RecordingChunk {
            flags: RECORDING_CHUNK_COMPACT_FLAG,
            payload_length: RECORDING_CHUNK_PRODUCT_PAYLOAD_MAX as u16,
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
        assert_eq!(
            wire.len(),
            RECORDING_CHUNK_HEADER_COMPACT_BYTES + RECORDING_CHUNK_PRODUCT_PAYLOAD_MAX
        );

        let mut parsed = parse_recording_chunk(&wire).unwrap();
        assert_eq!(
            parsed.flags & RECORDING_CHUNK_COMPACT_FLAG,
            RECORDING_CHUNK_COMPACT_FLAG
        );
        assert_eq!(
            parsed.payload_length,
            RECORDING_CHUNK_PRODUCT_PAYLOAD_MAX as u16
        );
        assert_eq!(parsed.payload, payload_bytes);
        assert_eq!(parsed.total_length, 0); // filled from list at pull time
        parsed.total_length = 1_920_000;
        assert_eq!(recording_packet_crc32(&parsed), parsed.packet_crc32);
        assert_eq!(parsed.final_sha256, [0_u8; 32]);
        let mut oversized=wire.clone();oversized.push(0);
        assert!(parse_recording_chunk(&oversized).is_err());
        assert!(parse_recording_chunk(&wire[..wire.len()-1]).is_err());
    }

    #[test]
    fn recording_chunk_parser_accepts_slim_12b_header_232_payload() {
        // COMP-REQ-667 slim intermediate: 12B header + 232B payload (ATT 244).
        // flags = COMPACT|SLIM (device ORs both on intermediate).
        let payload_bytes = vec![0x5A_u8; 232];
        let flags = RECORDING_CHUNK_COMPACT_FLAG | RECORDING_CHUNK_SLIM_FLAG;
        let mut wire = Vec::new();
        wire.push(1);
        wire.push(flags);
        wire.extend_from_slice(&232_u16.to_le_bytes());
        wire.extend_from_slice(&42_u32.to_le_bytes()); // seq
        wire.extend_from_slice(&9240_u32.to_le_bytes()); // offset
        wire.extend_from_slice(&payload_bytes);
        assert_eq!(wire.len(), RECORDING_CHUNK_HEADER_SLIM_BYTES + 232);
        assert_eq!(wire.len(), 244);

        let parsed = parse_recording_chunk(&wire).unwrap();
        assert_eq!(
            parsed.flags & RECORDING_CHUNK_SLIM_FLAG,
            RECORDING_CHUNK_SLIM_FLAG
        );
        assert_eq!(parsed.payload_length, 232);
        assert_eq!(parsed.packet_sequence, 42);
        assert_eq!(parsed.byte_offset, 9240);
        assert_eq!(parsed.recording_id, 0); // omitted on wire
        assert_eq!(parsed.packet_crc32, 0); // omitted mid-stream
        assert_eq!(parsed.payload, payload_bytes);
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
    fn stored_half_ima_is_decoded_before_wav_write() {
        let source: Vec<i16> = (0..640)
            .map(|i| (((i % 80) as i32 - 40) * 400) as i16)
            .collect();
        let (blob, original_samples) =
            denzic_host_audio_v1_core::compress_pcm16k_half_ima(&source, 80);
        let pcm = decode_stored_half_ima_to_pcm16_bytes(&blob).unwrap();
        assert_eq!(original_samples, source.len());
        assert_eq!(pcm.len(), source.len() * 2);
        assert_ne!(pcm, blob);
    }

    #[test]
    fn opus16_ogg_fixture_decodes_to_pcm_wav() {
        // Device path post-pull: opaque Ogg Opus (codec=3) → product 16 kHz WAV.
        let fixture = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(
            "../../../docs/validation/companion-type-opus16-full-path/stimulus_16k_opus16.opus",
        );
        if !fixture.is_file() {
            // Workspace layout alternate.
            let alt = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("../../../../Companion-Type/docs/validation/companion-type-opus16-full-path/stimulus_16k_opus16.opus");
            if !alt.is_file() {
                eprintln!("skip: opus fixture missing at {:?}", fixture);
                return;
            }
        }
        let fixture = if fixture.is_file() {
            fixture
        } else {
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(
                "../../../../Companion-Type/docs/validation/companion-type-opus16-full-path/stimulus_16k_opus16.opus",
            )
        };
        let dir = std::env::temp_dir().join("companion-opus16-decode-test");
        let _ = std::fs::create_dir_all(&dir);
        let wav = dir.join("out.wav");
        denzic_host_audio_v1_core::decode_opus_to_wav(&fixture, &wav).expect("decode_opus_to_wav");
        let meta = std::fs::metadata(&wav).expect("wav meta");
        assert!(
            meta.len() > 44 + 16_000,
            "decoded wav too small: {}",
            meta.len()
        );
        // 3 s * 16000 * 2 + 44 ≈ 96078
        assert!(
            (meta.len() as i64 - 96078).abs() < 5000,
            "unexpected decoded size {}",
            meta.len()
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
        let connect = bridge.connect(scan.device_id.as_deref(), &[]);
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
        let sync = bridge.sync_recordings(None, &[]);
        assert!(sync.ready, "native sync failed: {}", sync.message);
        let path = sync
            .recording_path
            .as_ref()
            .expect("native sync did not return a WAV recording path");
        assert!(Path::new(path).exists(), "native sync WAV missing: {path}");
        println!("native_ble_recording_sync={}", sync.message);
    }

    #[test]
    fn durable_reclaim_failure_retires_transport_without_losing_host_receipts() {
        let recording = |recording_id, device_reclaimed| CompanionSyncedRecording {
            recording_id, duration_ms: 300_420, total_length: 630_894,
            sha256: "59".repeat(32), recording_path: format!("recording-{recording_id}.wav"),
            device_reclaimed, capture_incomplete: false,
        };
        let operation = native_recording_operation(Ok(NativeRecordingBatch {
            device_id: "C8:92:FF:DD:3B:CA".into(),
            recordings: vec![recording(15, true), recording(16, false)],
            failures: vec![], paused: false, connection_reusable: false, segmented: None,
        }));
        assert!(operation.ready, "durable audio must still reach the library");
        assert_eq!(operation.recordings.len(), 2);
        assert!(operation.recordings[0].device_reclaimed);
        assert!(!operation.recordings[1].device_reclaimed);
        assert!(operation.message.contains("physical_consume_confirmed=1 pending_device_consume=1"));
        assert!(operation.message.contains("connection_reusable=false"));
        let failed = native_recording_operation(Ok(NativeRecordingBatch {
            device_id: "C8:92:FF:DD:3B:CA".into(), recordings: vec![],
            failures: vec!["no durable audio".into()], paused: false, connection_reusable: false, segmented: None,
        }));
        assert!(!failed.ready);
        assert!(failed.recordings.is_empty());
    }

    #[test]
    fn exact_reclaim_requires_all_identity_fields_and_sha_before_marking_consumed() {
        let request = delete_privacy_request(DELETE_PRIVACY_OP_DELETE_RECORDING, 7, 42, 1000, [0x5a; 32]);
        assert!(validate_delete_privacy_echo(&request, &request).is_ok());
        for offset in [1, 4, 8, 12, 16, 47] {
            let mut wrong = request; wrong[offset] ^= 1;
            assert!(validate_delete_privacy_echo(&wrong, &request).is_err(), "offset {offset}");
        }
        for length in 0..48 { assert!(validate_delete_privacy_echo(&request[..length], &request).is_err()); }
        let mut refusal = request;
        refusal[2] = DELETE_PRIVACY_REFUSAL_FLAG as u8;
        assert!(validate_delete_privacy_echo(&refusal[..16], &request).is_ok(), "short refusal can never mean consumed");
    }

    #[test]
    fn reclaim_wait_covers_long_recordings_and_full_arena_without_unbounded_timeout() {
        assert_eq!(device_reclaim_timeout_ms(DELETE_PRIVACY_OP_DELETE_RECORDING, 633_666), 15_000);
        let two_hours = device_reclaim_timeout_ms(DELETE_PRIVACY_OP_DELETE_RECORDING, 15_120_012);
        assert!((180_000..=240_000).contains(&two_hours), "long recording needs its own physical erase budget");
        let full_arena = device_reclaim_timeout_ms(DELETE_PRIVACY_OP_DELETE_ALL, 0);
        assert!(full_arena >= two_hours && full_arena <= 240_000,
            "delete-all has a full-arena budget even though the command carries no file length");
        assert_eq!(device_reclaim_timeout_ms(DELETE_PRIVACY_OP_DELETE_RECORDING, u32::MAX), 240_000);
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

    /// Completed GATT subscriptions need no artificial transfer delay.
    #[test]
    fn product_link_settle_default_is_at_most_800ms() {
        let src = include_str!("ble_bridge.rs");
        // Product settle line only (other 1500s may exist elsewhere in file).
        let settle_block = src
            .split("COMPANION_TYPE_BLE_LINK_SETTLE_MS")
            .nth(1)
            .expect("settle env");
        let settle_block = settle_block.split("if link_settle_ms").next().unwrap();
        assert!(
            settle_block.contains("unwrap_or(0)"),
            "ready subscriptions must not add a fixed transfer delay"
        );
        assert!(
            !settle_block.contains("3_500") && !settle_block.contains("1_500"),
            "must not regress product settle to 1500/3500"
        );
        assert!(
            include_str!("recording_metrics.rs").contains("recording_pull_metrics wire_kb_s="),
            "must emit machine-parseable wire_kb_s metrics"
        );
        assert!(
            src.contains("dual-lane required"),
            "when 3004 present, dual-lane subscribe failure must hard-error"
        );
    }

    /// Throughput Goal: product OTA is Listener-aligned WinRT dual-lane WWR only.
    #[test]
    fn ota_path_requests_throughput_and_dual_lane_bulk() {
        let bridge_full = include_str!("ble_bridge.rs");
        // Only production code — tests below mention deleted symbols by name.
        let bridge = bridge_full
            .rsplit_once("mod tests")
            .map(|(prod, _)| prod)
            .unwrap_or(bridge_full);
        assert!(
            bridge.contains("ota_winrt::transfer_companion_ota_winrt"),
            "product OTA must call WinRT dual-lane path"
        );
        // Incompatible btleplug OTA path must stay deleted.
        assert!(
            !bridge.contains("CompanionOtaV1Transport"),
            "btleplug OTA transport must be removed"
        );
        assert!(
            !bridge.contains("transfer_native_firmware_ota"),
            "btleplug OTA transfer function must be removed"
        );
        assert!(
            !bridge.contains("COMPANION_TYPE_OTA_BTLEPLUG"),
            "btleplug OTA escape hatch must be removed"
        );

        let winrt = include_str!("ota_winrt.rs");
        assert!(
            winrt.contains("start_gatt_write_with_option_async"),
            "WinRT OTA must use platform async WWR start (Listener pipeline)"
        );
        assert!(
            winrt.contains("RequestPreferredConnectionParameters")
                && winrt.contains("_conn_pref_request"),
            "preferred CI must be requested on the open device and held for transfer"
        );
        assert!(
            !winrt.contains("asyncio.run(main"),
            "must not use short-lived python subprocess for OTA connection params"
        );
        assert!(
            winrt.contains("pending_wwr_b"),
            "WinRT OTA must keep dual-lane pending queues"
        );
        assert!(
            winrt.contains("impl denzic_ota_core::OtaV1Transport for CompanionOtaWinrtTransport"),
            "WinRT OTA must implement OtaV1Transport"
        );
        assert!(
            winrt.contains("TransferOptions::dual_lane_bulk") || winrt.contains("dual_lane_bulk"),
            "WinRT OTA must use dual_lane_bulk options"
        );
        assert!(
            winrt.contains("WINDOW_CHUNKS: u16 = 400")
                || winrt.contains("window_chunks = 400")
                || winrt.contains("WINDOW_CHUNKS"),
            "product window must be 400"
        );
        assert!(
            winrt.contains("WWR_PIPELINE_DEPTH: usize = 16")
                || winrt.contains("WWR_PIPELINE_DEPTH: usize = 32"),
            "product pipeline must be dual-lane WWR (16=WB reorder-aligned or 32=Listener)"
        );
        assert!(
            winrt.contains("bulk_kb_s="),
            "OTA must log bulk_kb_s for acceptance"
        );
        assert!(
            !winrt.contains("window_chunks = 50") && !winrt.contains("WINDOW_CHUNKS: u16 = 50"),
            "must not shrink product window below 400"
        );
        let bulk = denzic_ota_core::TransferOptions::dual_lane_bulk(244);
        assert!(bulk.window_chunks >= 400);
        assert!(bulk.prefer_dual_lane);
        assert_eq!(bulk.chunk_payload_bytes, 244);
    }
}
