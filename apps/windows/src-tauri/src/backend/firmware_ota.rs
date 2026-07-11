//! Companion product adapter for the shared Denzic OTA v1 host core.

use std::fs;
use std::path::Path;
use std::time::Instant;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use super::ble_bridge::{CompanionBleBridge, CompanionOtaBleReport};

const PACKAGE_TYPE: &str = "companion-firmware-ota";
const HARDWARE_REVISION: &str = "NUCLEO-WB55RG";
const FIRMWARE_CAPABILITY: &str = denzic_ota_core::PROTOCOL_NAME;
const SERVICE_UUID: &str = denzic_ota_core::GATT_SERVICE_UUID;
const CONTROL_UUID: &str = denzic_ota_core::GATT_CONTROL_UUID;
const DATA_UUID: &str = denzic_ota_core::GATT_DATA_UUID;
const STATUS_UUID: &str = denzic_ota_core::GATT_STATUS_UUID;
const MAX_CHUNK_BYTES: u16 = 244;

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionFirmwareOtaRequest {
    pub manifest_path: String,
    pub firmware_path: String,
    pub device_id: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionFirmwareOtaReport {
    pub protocol: String,
    pub device_id: String,
    pub firmware_bytes: usize,
    pub data_writes: u32,
    pub status_reads: u32,
    pub recovered_offsets: u32,
    pub active_link_confirmed: bool,
    pub elapsed_ms: u128,
}

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u8,
    package_type: String,
    hardware_revision: String,
    file: ManifestFile,
    protocol: ManifestProtocol,
}

#[derive(Debug, Deserialize)]
struct ManifestFile {
    name: String,
    size_bytes: usize,
    sha256: String,
}

#[derive(Debug, Deserialize)]
struct ManifestProtocol {
    name: String,
    version: u8,
    firmware_capability: String,
    gatt: ManifestGatt,
}

#[derive(Debug, Deserialize)]
struct ManifestGatt {
    service_uuid: String,
    control_uuid: String,
    data_uuid: String,
    status_uuid: String,
    chunk_bytes: u16,
}

#[derive(Debug)]
struct ValidatedPackage {
    firmware: Vec<u8>,
    chunk_bytes: u16,
}

pub fn transfer(
    bridge: &CompanionBleBridge,
    request: CompanionFirmwareOtaRequest,
) -> Result<CompanionFirmwareOtaReport, String> {
    let package = validate_package(
        Path::new(&request.manifest_path),
        Path::new(&request.firmware_path),
    )?;
    let started = Instant::now();
    let result = bridge.transfer_firmware_ota(
        request.device_id.as_deref(),
        &package.firmware,
        package.chunk_bytes,
    )?;
    Ok(report(result, started.elapsed().as_millis()))
}

fn report(result: CompanionOtaBleReport, elapsed_ms: u128) -> CompanionFirmwareOtaReport {
    CompanionFirmwareOtaReport {
        protocol: denzic_ota_core::PROTOCOL_NAME.to_string(),
        device_id: result.device_id,
        firmware_bytes: result.transfer.firmware_bytes,
        data_writes: result.transfer.data_writes,
        status_reads: result.transfer.status_reads,
        recovered_offsets: result.transfer.recovered_offsets,
        active_link_confirmed: result.transfer.active_link_confirmed,
        elapsed_ms,
    }
}

fn validate_package(
    manifest_path: &Path,
    firmware_path: &Path,
) -> Result<ValidatedPackage, String> {
    let manifest_text = fs::read_to_string(manifest_path)
        .map_err(|err| format!("read OTA manifest {}: {err}", manifest_path.display()))?;
    let manifest: Manifest = serde_json::from_str(&manifest_text)
        .map_err(|err| format!("parse OTA manifest {}: {err}", manifest_path.display()))?;
    let firmware = fs::read(firmware_path)
        .map_err(|err| format!("read OTA firmware {}: {err}", firmware_path.display()))?;

    require_equal(manifest.schema_version, 1, "schema_version")?;
    require_text_equal(&manifest.package_type, PACKAGE_TYPE, "package_type")?;
    require_text_equal(
        &manifest.hardware_revision,
        HARDWARE_REVISION,
        "hardware_revision",
    )?;
    require_text_equal(
        &manifest.protocol.name,
        denzic_ota_core::PROTOCOL_NAME,
        "protocol.name",
    )?;
    require_equal(
        manifest.protocol.version,
        denzic_ota_core::PROTOCOL_VERSION,
        "protocol.version",
    )?;
    require_text_equal(
        &manifest.protocol.firmware_capability,
        FIRMWARE_CAPABILITY,
        "protocol.firmware_capability",
    )?;
    require_text_equal(
        &manifest.protocol.gatt.service_uuid.to_ascii_lowercase(),
        SERVICE_UUID,
        "protocol.gatt.service_uuid",
    )?;
    require_text_equal(
        &manifest.protocol.gatt.control_uuid.to_ascii_lowercase(),
        CONTROL_UUID,
        "protocol.gatt.control_uuid",
    )?;
    require_text_equal(
        &manifest.protocol.gatt.data_uuid.to_ascii_lowercase(),
        DATA_UUID,
        "protocol.gatt.data_uuid",
    )?;
    require_text_equal(
        &manifest.protocol.gatt.status_uuid.to_ascii_lowercase(),
        STATUS_UUID,
        "protocol.gatt.status_uuid",
    )?;
    if manifest.protocol.gatt.chunk_bytes == 0
        || manifest.protocol.gatt.chunk_bytes > MAX_CHUNK_BYTES
    {
        return Err(format!(
            "protocol.gatt.chunk_bytes must be in 1..={MAX_CHUNK_BYTES}, got {}",
            manifest.protocol.gatt.chunk_bytes
        ));
    }
    require_equal(manifest.file.size_bytes, firmware.len(), "file.size_bytes")?;
    if firmware.is_empty() {
        return Err("OTA firmware is empty".to_string());
    }
    let firmware_name = firmware_path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| "OTA firmware path has no UTF-8 file name".to_string())?;
    require_text_equal(&manifest.file.name, firmware_name, "file.name")?;
    let actual_sha256 = format!("{:x}", Sha256::digest(&firmware));
    require_text_equal(
        &manifest.file.sha256.to_ascii_lowercase(),
        &actual_sha256,
        "file.sha256",
    )?;

    Ok(ValidatedPackage {
        firmware,
        chunk_bytes: manifest.protocol.gatt.chunk_bytes,
    })
}

fn require_equal<T>(actual: T, expected: T, label: &str) -> Result<(), String>
where
    T: PartialEq + std::fmt::Debug,
{
    if actual != expected {
        return Err(format!(
            "{label} mismatch: expected {expected:?}, got {actual:?}"
        ));
    }
    Ok(())
}

fn require_text_equal(actual: &str, expected: &str, label: &str) -> Result<(), String> {
    if actual != expected {
        return Err(format!(
            "{label} mismatch: expected {expected:?}, got {actual:?}"
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn package_paths(label: &str) -> (std::path::PathBuf, std::path::PathBuf) {
        let root =
            std::env::temp_dir().join(format!("companion-type-ota-{label}-{}", std::process::id()));
        let _ = fs::create_dir_all(&root);
        (
            root.join("ota_manifest.json"),
            root.join("firmware_ota.bin"),
        )
    }

    fn write_package(
        label: &str,
        protocol_name: &str,
        sha256: Option<&str>,
    ) -> (std::path::PathBuf, std::path::PathBuf) {
        let (manifest_path, firmware_path) = package_paths(label);
        let firmware = b"companion-ota-v1-test";
        fs::write(&firmware_path, firmware).unwrap();
        let actual_sha256 = format!("{:x}", Sha256::digest(firmware));
        let manifest = serde_json::json!({
            "schema_version": 1,
            "package_type": PACKAGE_TYPE,
            "hardware_revision": HARDWARE_REVISION,
            "file": {
                "name": "firmware_ota.bin",
                "size_bytes": firmware.len(),
                "sha256": sha256.unwrap_or(&actual_sha256),
            },
            "protocol": {
                "name": protocol_name,
                "version": denzic_ota_core::PROTOCOL_VERSION,
                "firmware_capability": FIRMWARE_CAPABILITY,
                "gatt": {
                    "service_uuid": SERVICE_UUID,
                    "control_uuid": CONTROL_UUID,
                    "data_uuid": DATA_UUID,
                    "status_uuid": STATUS_UUID,
                    "chunk_bytes": 240,
                }
            }
        });
        fs::write(
            &manifest_path,
            serde_json::to_vec_pretty(&manifest).unwrap(),
        )
        .unwrap();
        (manifest_path, firmware_path)
    }

    #[test]
    fn accepts_companion_product_manifest_and_firmware() {
        let (manifest, firmware) = write_package("valid", denzic_ota_core::PROTOCOL_NAME, None);
        let package = validate_package(&manifest, &firmware).unwrap();
        assert_eq!(package.chunk_bytes, 240);
        assert_eq!(package.firmware, b"companion-ota-v1-test");
    }

    #[test]
    fn rejects_protocol_drift() {
        let (manifest, firmware) = write_package("protocol", "obsolete", None);
        let error = validate_package(&manifest, &firmware).unwrap_err();
        assert!(error.contains("protocol.name mismatch"));
    }

    #[test]
    fn rejects_firmware_hash_drift() {
        let (manifest, firmware) =
            write_package("hash", denzic_ota_core::PROTOCOL_NAME, Some("00"));
        let error = validate_package(&manifest, &firmware).unwrap_err();
        assert!(error.contains("file.sha256 mismatch"));
    }

    #[test]
    fn validates_external_package_when_requested() {
        let Ok(manifest) = std::env::var("COMPANION_TYPE_OTA_TEST_MANIFEST") else {
            return;
        };
        let firmware = std::env::var("COMPANION_TYPE_OTA_TEST_FIRMWARE")
            .expect("COMPANION_TYPE_OTA_TEST_FIRMWARE must accompany the manifest");
        validate_package(Path::new(&manifest), Path::new(&firmware))
            .expect("generated Companion package must pass the real host validator");
    }
}
