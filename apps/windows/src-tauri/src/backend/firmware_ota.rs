//! Companion product adapter for the shared Denzic OTA v1 host core.

use std::fs;
use std::path::Path;
use std::time::Instant;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use super::ble_bridge::{CompanionBleBridge, CompanionOtaBleReport};

const PACKAGE_TYPE_FIRMWARE: &str = "companion-firmware-ota";
const PACKAGE_TYPE_RESOURCE: &str = "companion-resource-ota";
const HARDWARE_REVISION: &str = "NUCLEO-WB55RG";
const WBA_HARDWARE_REVISION: &str = "COMPANION-WBA55-V1.1";
const WBA_CE_HARDWARE_REVISION: &str = "COMPANION-WBA55CE-V1.1";

fn wba_geometry(hardware: &str) -> Option<(u32, usize)> {
    match hardware {
        WBA_HARDWARE_REVISION => Some((0x31315643, 0xF4000)),
        WBA_CE_HARDWARE_REVISION => Some((0x45315643, 0x74000)),
        _ => None,
    }
}
pub(crate) const WBA_MANIFEST_UUID_U128: u128 = 0xe571544a7c414650b0d6ccebfe1db48a;
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
    pub package_type: String,
    pub already_installed: bool,
    pub firmware_bytes: usize,
    pub data_writes: u32,
    pub status_reads: u32,
    pub recovered_offsets: u32,
    pub active_link_confirmed: bool,
    pub elapsed_ms: u128,
    pub payload_metrics: super::ota_metrics::PayloadMetrics,
    pub system_bundle: Option<serde_json::Value>,
}

/// Host-side validation of a firmware or resource OTA package (no BLE).
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionOtaPackageValidation {
    pub ok: bool,
    pub package_type: String,
    pub version_note: String,
    pub payload_bytes: usize,
    pub chunk_bytes: u16,
    pub payload_sha256: String,
    pub message: String,
}

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u8,
    package_type: String,
    hardware_revision: String,
    file: ManifestFile,
    protocol: ManifestProtocol,
    #[serde(default)]
    wba_manifest_hex: Option<String>,
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
    #[serde(default)]
    firmware_capability: Option<String>,
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
    package_type: String,
    firmware: Vec<u8>,
    chunk_bytes: u16,
    payload_sha256: String,
    wba_manifest: Option<[u8; 144]>,
}

pub fn validate_ota_package(
    request: &CompanionFirmwareOtaRequest,
) -> Result<CompanionOtaPackageValidation, String> {
    if super::system_ota::is_bundle(Path::new(&request.manifest_path))? {
        let p=super::system_ota::load(Path::new(&request.manifest_path))?;
        return Ok(CompanionOtaPackageValidation{ok:true,package_type:"companion-system-ota".into(),
            version_note:"固件＋资源单文件，断开后重新下载".into(),payload_bytes:p.file.len(),chunk_bytes:505,
            payload_sha256:p.id,message:"单文件内容已核对；Boot 在覆盖前验证签名。新版本正常启动且临时空间释放后才显示升级成功。".into()});
    }
    let package = validate_package(
        Path::new(&request.manifest_path),
        Path::new(&request.firmware_path),
    )?;
    let is_resource = package.package_type == PACKAGE_TYPE_RESOURCE;
    let message = if package.wba_manifest.is_some() {
        "WBA package payload and signed envelope match. The device must verify its trusted signing key before transfer; installation and boot confirmation are separate device steps.".to_string()
    } else if is_resource {
        "Resource package is valid on host. Device app installer (ui_assets candidate + atomic activate) is not shipped yet — BLE transfer is blocked by default to avoid flashing CEMP into mcu_app.".to_string()
    } else {
        "Firmware package is valid on host and may be transferred over denzic_ota_v1.".to_string()
    };
    Ok(CompanionOtaPackageValidation {
        ok: true,
        package_type: package.package_type,
        version_note: if is_resource {
            "companion-resource-ota / ui_assets".to_string()
        } else {
            "companion-firmware-ota / mcu_app".to_string()
        },
        payload_bytes: package.firmware.len(),
        chunk_bytes: package.chunk_bytes,
        payload_sha256: package.payload_sha256,
        message,
    })
}

pub(super) fn reconfirm_if_current_version(
    request:&CompanionFirmwareOtaRequest,current_version:Option<u32>,
)->Result<Option<CompanionFirmwareOtaReport>,String> {
    let package=super::system_ota::load(Path::new(&request.manifest_path))?;
    // Leave ordinary higher-version updates on the existing connection path.
    if current_version!=Some(package.app_version) {return Ok(None);}
    #[cfg(windows)] {
        let started=Instant::now();
        return super::ota_winrt::reconfirm_system_ota_winrt(request.device_id.as_deref(),&package)
            .map(|result|result.map(|r|report(r,"companion-system-ota".into(),started.elapsed().as_millis())));
    }
    #[cfg(not(windows))] {Ok(None)}
}

pub fn transfer(
    bridge: &CompanionBleBridge,
    request: CompanionFirmwareOtaRequest,
) -> Result<CompanionFirmwareOtaReport, String> {
    if super::system_ota::is_bundle(Path::new(&request.manifest_path))? {
        let p=super::system_ota::load(Path::new(&request.manifest_path))?;
        #[cfg(windows)] {
            let started=Instant::now();
            let r=super::ota_winrt::transfer_system_ota_winrt(request.device_id.as_deref(),&p)?;
            return Ok(report(r,"companion-system-ota".into(),started.elapsed().as_millis()));
        }
        #[cfg(not(windows))] {let _=p;return Err("整套升级需要原生Windows蓝牙入口".into());}
    }
    let package = validate_package(
        Path::new(&request.manifest_path),
        Path::new(&request.firmware_path),
    )?;
    if package.package_type == PACKAGE_TYPE_RESOURCE && package.wba_manifest.is_none() && !resource_ble_transfer_allowed() {
        return Err(
            "companion-resource-ota BLE transfer is blocked until the device app resource installer \
             (ui_assets_candidate + atomic_boot_meta) ships. Host validation passed — re-run with \
             COMPANION_TYPE_RESOURCE_OTA_BLE=1 only for lab experiments (unsafe on current loader)."
                .to_string(),
        );
    }
    let started = Instant::now();
    let result = bridge.transfer_firmware_ota(
        request.device_id.as_deref(),
        &package.firmware,
        package.chunk_bytes,
        package.wba_manifest.as_ref(),
    )?;
    Ok(report(
        result,
        package.package_type,
        started.elapsed().as_millis(),
    ))
}

fn resource_ble_transfer_allowed() -> bool {
    std::env::var("COMPANION_TYPE_RESOURCE_OTA_BLE")
        .map(|v| {
            let t = v.trim();
            t == "1" || t.eq_ignore_ascii_case("true")
        })
        .unwrap_or(false)
}

fn report(
    result: CompanionOtaBleReport,
    package_type: String,
    elapsed_ms: u128,
) -> CompanionFirmwareOtaReport {
    let protocol_ms = result.transfer.timings.total.as_secs_f64();
    // Use the same authoritative new-byte wall-clock window as QM16. The
    // total engine/API timings cannot substitute for an unknown payload rate.
    let bulk_kb_s = result.payload_metrics.actual_payload_kib_s
        .map(|rate| format!("{rate:.2}")).unwrap_or_else(|| "not_measured".into());
    // Keep stderr machine-parseable for acceptance scripts.
    eprintln!(
        "firmware_ota_report package_type={package_type} bulk_kb_s={bulk_kb_s} protocol_ms={:.0} wall_ms={elapsed_ms} bytes={} data_writes={} new_payload_bytes={} payload_window_us={:?} rate_basis={}",
        protocol_ms * 1000.0,
        result.transfer.firmware_bytes,
        result.transfer.data_writes,
        result.payload_metrics.new_payload_bytes,
        result.payload_metrics.payload_elapsed_us,
        result.payload_metrics.rate_basis
    );
    CompanionFirmwareOtaReport {
        protocol: denzic_ota_core::PROTOCOL_NAME.to_string(),
        device_id: result.device_id,
        package_type,
        already_installed: result.system_bundle.as_ref().is_some_and(|b|b["alreadyInstalled"]==true),
        firmware_bytes: result.transfer.firmware_bytes,
        data_writes: result.transfer.data_writes,
        status_reads: result.transfer.status_reads,
        recovered_offsets: result.transfer.recovered_offsets,
        active_link_confirmed: result.transfer.active_link_confirmed,
        elapsed_ms,
        payload_metrics: result.payload_metrics,
        system_bundle: result.system_bundle,
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
    if manifest.package_type != PACKAGE_TYPE_FIRMWARE
        && manifest.package_type != PACKAGE_TYPE_RESOURCE
    {
        return Err(format!(
            "package_type mismatch: expected {PACKAGE_TYPE_FIRMWARE:?} or {PACKAGE_TYPE_RESOURCE:?}, got {:?}",
            manifest.package_type
        ));
    }
    if manifest.hardware_revision != HARDWARE_REVISION && wba_geometry(&manifest.hardware_revision).is_none() {
        return Err(format!("unsupported hardware_revision: {}", manifest.hardware_revision));
    }
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
    if let Some(cap) = manifest.protocol.firmware_capability.as_deref() {
        require_text_equal(cap, FIRMWARE_CAPABILITY, "protocol.firmware_capability")?;
    }
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
    if wba_geometry(&manifest.hardware_revision).is_some() && manifest.protocol.gatt.chunk_bytes>240 {
        return Err("WBA incoming event geometry requires chunk_bytes <= 240".into());
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

    let wba_manifest = if wba_geometry(&manifest.hardware_revision).is_some() {
        Some(validate_wba_envelope(manifest.wba_manifest_hex.as_deref().ok_or(
            "WBA package requires wba_manifest_hex; unsigned development-board payloads are incompatible")?,
            &firmware, manifest.package_type == PACKAGE_TYPE_RESOURCE, &manifest.hardware_revision)?)
    } else {
        if manifest.wba_manifest_hex.is_some() {return Err("WBA envelope cannot target WB55 hardware".into());}
        None
    };
    Ok(ValidatedPackage {
        package_type: manifest.package_type,
        firmware,
        chunk_bytes: manifest.protocol.gatt.chunk_bytes,
        payload_sha256: actual_sha256,
        wba_manifest,
    })
}

fn validate_wba_envelope(hex: &str, payload: &[u8], resource: bool, hardware: &str) -> Result<[u8; 144], String> {
    let (board_target, app_capacity) = wba_geometry(hardware).ok_or("unsupported WBA geometry")?;
    if hex.len()!=288 || !hex.is_ascii() {return Err("WUM1 envelope must be exactly 288 hex characters".into());}
    let mut wire=[0u8;144];
    for (i, value) in wire.iter_mut().enumerate() {
        *value=u8::from_str_radix(&hex[i*2..i*2+2],16).map_err(|_|"invalid WUM1 hex")?;
    }
    let word=|offset: usize| u32::from_le_bytes(wire[offset..offset+4].try_into().unwrap());
    let format=u16::from_le_bytes([wire[6],wire[7]]);
    if &wire[..4]!=b"WUM1" || wire[4]!=1 || wire[5]!=(if resource {2} else {1}) ||
       word(8)!=0x41425743 || word(12)!=board_target ||
       (!resource && format!=1) || (resource && format!=2) ||
       (word(24)!=0 && word(20)>word(24)) || payload.is_empty() || (!resource && payload.len()>app_capacity) || (resource && payload.len()>0x1000000-0x20000-0x1000) ||
       wire[68]!=1 || wire[69..72]!=[0,0,0] || word(72)==0 || word(16)==0 ||
       word(28) as usize!=payload.len() || word(32)!=crc32fast::hash(payload) ||
       wire[36..68]!=Sha256::digest(payload)[..] || word(140)!=crc32fast::hash(&wire[..140]) ||
       wire[76..108].iter().all(|b|*b==0) || wire[108..140].iter().all(|b|*b==0) {
        return Err("WUM1 identity, payload digest, signature encoding or CRC mismatch".into());
    }
    /* Authenticity is checked against the device's provisioned public key.
     * Host consistency checks must never be described as signature verification. */
    Ok(wire)
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

    fn encoded_wba_fixture(payload: &[u8], hardware: &str, resource: bool) -> String {
        let (board, _) = wba_geometry(hardware).unwrap();
        let mut wire = [0u8; 144];
        wire[..4].copy_from_slice(b"WUM1");
        wire[4] = 1;
        wire[5] = if resource { 2 } else { 1 };
        wire[6] = if resource { 2 } else { 1 };
        for (offset, value) in [(8, 0x41425743), (12, board), (16, 2),
            (28, payload.len() as u32), (32, crc32fast::hash(payload)), (72, 1)] {
            wire[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
        }
        wire[36..68].copy_from_slice(&Sha256::digest(payload));
        wire[68] = 1;
        // Encoding fixture only; the device still verifies real P-256 signatures.
        wire[107] = 1;
        wire[139] = 1;
        let checksum = crc32fast::hash(&wire[..140]);
        wire[140..].copy_from_slice(&checksum.to_le_bytes());
        wire.iter().map(|b| format!("{b:02x}")).collect()
    }

    #[test]
    fn ce_and_cg_envelopes_are_not_interchangeable_even_when_payload_fits_both() {
        let payload = b"same app bytes cannot substitute for the signed MCU identity";
        for (hardware, opposite) in [(WBA_HARDWARE_REVISION, WBA_CE_HARDWARE_REVISION),
                                    (WBA_CE_HARDWARE_REVISION, WBA_HARDWARE_REVISION)] {
            let wire = encoded_wba_fixture(payload, hardware, false);
            assert!(validate_wba_envelope(&wire, payload, false, hardware).is_ok());
            assert!(validate_wba_envelope(&wire, payload, false, opposite).is_err());
            let resource = encoded_wba_fixture(payload, hardware, true);
            assert!(validate_wba_envelope(&resource, payload, true, hardware).is_ok());
            assert!(validate_wba_envelope(&resource, payload, true, opposite).is_err());
        }
    }

    #[test]
    fn each_mcu_application_limit_is_enforced_and_resources_retain_their_own_limit() {
        for hardware in [WBA_HARDWARE_REVISION, WBA_CE_HARDWARE_REVISION] {
            let (_, capacity) = wba_geometry(hardware).unwrap();
            let payload = vec![0x5a; capacity];
            let wire = encoded_wba_fixture(&payload, hardware, false);
            assert!(validate_wba_envelope(&wire, &payload, false, hardware).is_ok());
            let too_large = vec![0x5a; capacity + 1];
            let wire = encoded_wba_fixture(&too_large, hardware, false);
            assert!(validate_wba_envelope(&wire, &too_large, false, hardware).is_err());
            for size in [0xe4000, 0x200000, 0x400000] {
                let ui = vec![0xff; size];
                let wire = encoded_wba_fixture(&ui, hardware, true);
                assert!(validate_wba_envelope(&wire, &ui, true, hardware).is_ok());
            }
            let too_large_ui = vec![0xff; 0x1000000];
            let wire = encoded_wba_fixture(&too_large_ui, hardware, true);
            assert!(validate_wba_envelope(&wire, &too_large_ui, true, hardware).is_err());
        }
    }

    #[test]
    fn ce_package_uses_the_product_validator_and_cannot_be_relabelled_cg() {
        let (manifest, payload) = write_package("ce-package", denzic_ota_core::PROTOCOL_NAME, None);
        let mut value: serde_json::Value = serde_json::from_slice(&fs::read(&manifest).unwrap()).unwrap();
        let bytes = fs::read(&payload).unwrap();
        value["hardware_revision"] = WBA_CE_HARDWARE_REVISION.into();
        value["protocol"]["gatt"]["chunk_bytes"] = 240.into();
        value["wba_manifest_hex"] = encoded_wba_fixture(&bytes, WBA_CE_HARDWARE_REVISION, false).into();
        fs::write(&manifest, serde_json::to_vec(&value).unwrap()).unwrap();
        assert!(validate_package(&manifest, &payload).unwrap().wba_manifest.is_some());
        value["hardware_revision"] = WBA_HARDWARE_REVISION.into();
        fs::write(&manifest, serde_json::to_vec(&value).unwrap()).unwrap();
        assert!(validate_package(&manifest, &payload).is_err());
    }

    #[test]
    fn wba_envelope_checks_payload_target_and_corruption_without_claiming_signature_verification() {
        let payload=b"relocated WBA test payload";
        let mut wire=[0u8;144];wire[..4].copy_from_slice(b"WUM1");wire[4]=1;wire[5]=1;wire[6]=1;
        for (offset,value) in [(8,0x41425743u32),(12,0x31315643),(16,2),(24,u32::MAX),
            (28,payload.len() as u32),(32,crc32fast::hash(payload)),(72,1)] {
            wire[offset..offset+4].copy_from_slice(&value.to_le_bytes());
        }
        wire[36..68].copy_from_slice(&Sha256::digest(payload));wire[68]=1;
        // Nonzero fixture scalars exercise encoding only. Device P-256 tests
        // separately reject this deliberately unauthenticated signature.
        wire[107]=1;wire[139]=1;
        let checksum=crc32fast::hash(&wire[..140]);wire[140..].copy_from_slice(&checksum.to_le_bytes());
        let hex=wire.iter().map(|b|format!("{b:02x}")).collect::<String>();
        assert!(validate_wba_envelope(&hex,payload,false,WBA_HARDWARE_REVISION).is_ok());
        assert!(validate_wba_envelope(&hex,payload,true,WBA_HARDWARE_REVISION).is_err());
        assert!(validate_wba_envelope(&hex,b"other payload",false,WBA_HARDWARE_REVISION).is_err());
        assert!(validate_wba_envelope(&hex[..286],payload,false,WBA_HARDWARE_REVISION).is_err());
        wire[20..24].copy_from_slice(&1u32.to_le_bytes());wire[24..28].fill(0);
        let checksum=crc32fast::hash(&wire[..140]);wire[140..].copy_from_slice(&checksum.to_le_bytes());
        let unbounded=wire.iter().map(|b|format!("{b:02x}")).collect::<String>();
        assert!(validate_wba_envelope(&unbounded,payload,false,WBA_HARDWARE_REVISION).is_ok());
        wire[12]^=1;let checksum=crc32fast::hash(&wire[..140]);wire[140..].copy_from_slice(&checksum.to_le_bytes());
        let wrong_board=wire.iter().map(|b|format!("{b:02x}")).collect::<String>();
        assert!(validate_wba_envelope(&wrong_board,payload,false,WBA_HARDWARE_REVISION).is_err());
    }

    #[test]
    fn wba_cannot_use_unsigned_wb_package() {
        let (manifest,payload)=write_package("wba-unsigned",denzic_ota_core::PROTOCOL_NAME,None);
        let mut value:serde_json::Value=serde_json::from_slice(&fs::read(&manifest).unwrap()).unwrap();
        value["hardware_revision"]=WBA_HARDWARE_REVISION.into();
        fs::write(&manifest,serde_json::to_vec(&value).unwrap()).unwrap();
        assert!(validate_package(&manifest,&payload).unwrap_err().contains("wba_manifest_hex"));
    }

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
            "package_type": PACKAGE_TYPE_FIRMWARE,
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
        assert_eq!(package.package_type, PACKAGE_TYPE_FIRMWARE);
    }

    #[test]
    fn accepts_companion_resource_package() {
        let (manifest_path, payload_path) = package_paths("resource");
        let payload = b"cemp-resource-slice";
        fs::write(&payload_path, payload).unwrap();
        let sha = format!("{:x}", Sha256::digest(payload));
        let manifest = serde_json::json!({
            "schema_version": 1,
            "package_type": PACKAGE_TYPE_RESOURCE,
            "hardware_revision": HARDWARE_REVISION,
            "file": {
                "name": payload_path.file_name().unwrap().to_string_lossy(),
                "size_bytes": payload.len(),
                "sha256": sha,
            },
            "protocol": {
                "name": denzic_ota_core::PROTOCOL_NAME,
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
        let package = validate_package(&manifest_path, &payload_path).unwrap();
        assert_eq!(package.package_type, PACKAGE_TYPE_RESOURCE);
        let report = validate_ota_package(&CompanionFirmwareOtaRequest {
            manifest_path: manifest_path.to_string_lossy().into(),
            firmware_path: payload_path.to_string_lossy().into(),
            device_id: None,
        })
        .unwrap();
        assert!(report.ok);
        assert_eq!(report.package_type, PACKAGE_TYPE_RESOURCE);
        assert!(report.message.contains("Resource package is valid"));
    }

    #[test]
    fn resource_ble_transfer_blocked_without_escape() {
        std::env::remove_var("COMPANION_TYPE_RESOURCE_OTA_BLE");
        let (manifest_path, payload_path) = package_paths("resource-ble-block");
        let payload = b"cemp-block";
        fs::write(&payload_path, payload).unwrap();
        let sha = format!("{:x}", Sha256::digest(payload));
        let manifest = serde_json::json!({
            "schema_version": 1,
            "package_type": PACKAGE_TYPE_RESOURCE,
            "hardware_revision": HARDWARE_REVISION,
            "file": {
                "name": payload_path.file_name().unwrap().to_string_lossy(),
                "size_bytes": payload.len(),
                "sha256": sha,
            },
            "protocol": {
                "name": denzic_ota_core::PROTOCOL_NAME,
                "version": denzic_ota_core::PROTOCOL_VERSION,
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
        let bridge = CompanionBleBridge::detect_default();
        let err = transfer(
            &bridge,
            CompanionFirmwareOtaRequest {
                manifest_path: manifest_path.to_string_lossy().into(),
                firmware_path: payload_path.to_string_lossy().into(),
                device_id: None,
            },
        )
        .unwrap_err();
        assert!(
            err.contains("RESOURCE_OTA")
                || err.contains("resource installer")
                || err.contains("blocked"),
            "unexpected err: {err}"
        );
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
