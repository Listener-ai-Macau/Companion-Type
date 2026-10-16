//! Finish Windows pairing before btleplug opens/discovers protected GATT.
//! A device's finite physical pairing window still decides whether to pair.
#![cfg(windows)]

use std::sync::{atomic::{AtomicBool, AtomicU32, Ordering}, Arc};
use std::time::Duration;

use btleplug::api::AddressType;
use denzic_ble_windows::{wait_async_operation_with_cancel, BleCancel};
use windows::Devices::Bluetooth::{BluetoothAddressType, BluetoothLEDevice};
use windows::Devices::Enumeration::{
    DeviceInformation, DeviceInformationCustomPairing, DevicePairingKinds,
    DevicePairingProtectionLevel, DevicePairingRequestedEventArgs, DevicePairingResultStatus,
};
use windows::Foundation::{EventRegistrationToken, TypedEventHandler};

const OPEN_TIMEOUT: Duration = Duration::from_secs(8);
const PAIR_TIMEOUT: Duration = Duration::from_secs(45);
const PAIR_ERROR: &str = "Windows BLE pairing required:";

struct CancelOnDrop(Arc<AtomicBool>);
impl Drop for CancelOnDrop {
    fn drop(&mut self) { self.0.store(true, Ordering::SeqCst); }
}

struct DeviceHandle(BluetoothLEDevice);
// This temporary pairing/metadata reference does not own the GATT link.
// As in Listener and TransferPreference, release its COM reference normally:
// Close() can invalidate another live owner's cached WinRT device object.

struct PairingHandler {
    custom: DeviceInformationCustomPairing,
    token: EventRegistrationToken,
}
impl Drop for PairingHandler {
    fn drop(&mut self) { let _ = self.custom.RemovePairingRequested(self.token); }
}

pub(super) fn is_pairing_error(error: &str) -> bool {
    // These two product boundaries retain the original native category inside
    // a context prefix. Do not misclassify them as a retryable offline peer.
    let native=error.strip_prefix("Native BLE connect failed: ")
        .or_else(||error.strip_prefix("Remembered Companion is offline: ")).unwrap_or(error);
    native.starts_with(PAIR_ERROR)
}

/* OTA's synchronous WinRT path must use the same normal pairing ceremony as
 * recorder connect, with the address type read from its actual device handle.
 * This never unpairs/deletes a bond or opens the device's physical window. */
pub(super) fn ensure_paired_for_ota(address:u64,kind:BluetoothAddressType)->Result<(),String> {
    let kind=if kind==BluetoothAddressType::Random {AddressType::Random}else{AddressType::Public};
    pair_before_services(address,Some(kind),&BleCancel::NONE).map_err(pair_error)
}

pub(super) async fn ensure_paired_before_gatt(
    address: &str, address_type: Option<AddressType>,
) -> Result<(), String> {
    let address = parse_address(address).map_err(pair_error)?;
    let cancel = Arc::new(AtomicBool::new(false));
    // Dropping a connect/reconnect future cancels the native operation too.
    // The worker removes its handler and releases its temporary COM reference.
    let _cancel_on_drop = CancelOnDrop(cancel.clone());
    tokio::task::spawn_blocking(move || {
        let cancel = BleCancel::new(cancel, "cancelled Companion connection");
        pair_before_services(address, address_type, &cancel).map_err(pair_error)
    }).await.map_err(|error| pair_error(format!("配对任务失败：{error}")))?
}

fn pair_error(error: String) -> String { format!("{PAIR_ERROR} {error}") }

fn parse_address(address: &str) -> Result<u64, String> {
    let compact: String = address.trim().chars().filter(|ch| *ch != ':' && *ch != '-').collect();
    if compact.len() != 12 || !compact.bytes().all(|ch| ch.is_ascii_hexdigit()) {
        return Err("设备蓝牙地址无效，未尝试配对。".into());
    }
    u64::from_str_radix(&compact, 16).map_err(|_| "设备蓝牙地址无效。".into())
}

fn confirmation_supported(kind: DevicePairingKinds) -> bool {
    // Do not accept a PIN/passkey or numeric comparison without the user.
    kind == DevicePairingKinds::ConfirmOnly
}

fn verify_pair_result(status: DevicePairingResultStatus) -> Result<(), String> {
    if status == DevicePairingResultStatus::Paired || status == DevicePairingResultStatus::AlreadyPaired {
        Ok(())
    } else {
        // Windows' Failed (19) explicitly means an unknown failure. Do not
        // diagnose every failure as a closed device pairing window or imply
        // that authentication/access denial can be bypassed by retrying GATT.
        let detail = if status == DevicePairingResultStatus::Failed {
            "Windows 返回未知配对失败，具体原因尚未确定；可重试连接，仍失败时通过 Companion 的正常配对窗口重新配对"
        } else if status == DevicePairingResultStatus::AuthenticationFailure {
            "蓝牙身份认证失败；请通过 Companion 的正常配对窗口重新配对"
        } else if status == DevicePairingResultStatus::AuthenticationTimeout {
            "蓝牙身份认证超时；请确认设备可连接后重试"
        } else if status == DevicePairingResultStatus::AccessDenied {
            "Windows 拒绝应用的配对访问，尚未打开受保护的设备服务"
        } else if status == DevicePairingResultStatus::ProtectionLevelCouldNotBeMet {
            "配对无法达到要求的加密保护，尚未打开受保护的设备服务"
        } else if status == DevicePairingResultStatus::OperationAlreadyInProgress {
            "Windows 已有配对或取消配对任务进行中；请等待该任务完成后重新连接"
        } else if status == DevicePairingResultStatus::PairingCanceled {
            "配对已取消；需要连接时可以重新发起"
        } else if status == DevicePairingResultStatus::NotReadyToPair || status == DevicePairingResultStatus::NotPaired {
            "设备尚未完成配对；请通过 Companion 的正常配对窗口重新连接"
        } else {
            "Windows 未完成配对，具体原因请结合此状态和设备反馈定位"
        };
        Err(format!("设备配对未完成（Windows 状态 {}）：{detail}；板端录音仍保留。", status.0))
    }
}

fn pair_before_services(address: u64, address_type: Option<AddressType>, cancel: &BleCancel)
    -> Result<(), String>
{
    if cancel.requested() { return Err(cancel.cancelled_error("pairing")); }
    // Keep the address type obtained from the actual advertisement. WBA uses
    // a static-random identity; an older WB with a public address stays public.
    let operation = match address_type {
        Some(kind) => BluetoothLEDevice::FromBluetoothAddressWithBluetoothAddressTypeAsync(
            address, match kind {
                AddressType::Random => BluetoothAddressType::Random,
                AddressType::Public => BluetoothAddressType::Public,
            }),
        None => BluetoothLEDevice::FromBluetoothAddressAsync(address),
    }.map_err(|error| format!("打开配对设备失败：{error}"))?;
    let device = DeviceHandle(wait_async_operation_with_cancel(
        operation, OPEN_TIMEOUT, "pairing device open", cancel)?);
    let initial_information = device.0.DeviceInformation()
        .map_err(|error| format!("读取配对设备身份失败：{error}"))?;
    let id = initial_information.Id()
        .map_err(|error| format!("读取配对设备身份失败：{error}"))?;
    eprintln!("BLE pairing_trace stage=opened_native_device address={address:012X} native_id={id:?} information_kind={:?} native_connection={:?} initial_paired={:?}",
        initial_information.Kind().ok(), device.0.ConnectionStatus().ok(),
        initial_information.Pairing().and_then(|p|p.IsPaired()).ok());
    // Refresh pairing information instead of trusting the BluetoothLEDevice's
    // initial cached DeviceInformation object.
    let operation = DeviceInformation::CreateFromIdAsync(&id)
        .map_err(|error| format!("读取 Windows 配对信息失败：{error}"))?;
    let information = wait_async_operation_with_cancel(
        operation, OPEN_TIMEOUT, "pairing information refresh", cancel)?;
    let pairing = information.Pairing().map_err(|error| format!("读取配对状态失败：{error}"))?;
    let is_paired = pairing.IsPaired().map_err(|error| format!("读取配对状态失败：{error}"))?;
    eprintln!("BLE pairing_trace stage=refreshed_windows_state address={address:012X} address_type={address_type:?} paired={is_paired} information_kind={:?} id_matches={}",
        information.Kind().ok(),information.Id().ok().as_ref()==Some(&id));
    // As in Listener, release the temporary BluetoothLEDevice before PairAsync.
    // DeviceInformation owns the pairing metadata; no explicit Close or GATT.
    drop(initial_information);
    drop(device);
    eprintln!("BLE pairing_trace stage=temporary_device_released address={address:012X} before_ceremony=1 explicit_close=0");
    if is_paired {
        eprintln!("BLE Windows pairing already_paired before GATT address={address:012X}");
        return Ok(());
    }
    let can_pair = pairing.CanPair().map_err(|error| format!("读取配对可用状态失败：{error}"))?;
    eprintln!("BLE pairing_trace stage=can_pair address={address:012X} can_pair={can_pair}");
    if !can_pair {
        return Err("Windows 暂不能配对此设备，请打开 Companion 配对窗口后重新连接；未更改已存录音。".into());
    }
    if cancel.requested() { return Err(cancel.cancelled_error("pairing")); }
    let custom = pairing.Custom().map_err(|error| format!("打开原生配对流程失败：{error}"))?;
    let callback_cancel = cancel.clone();
    let requested_events=Arc::new(AtomicU32::new(0));
    let accepted_events=Arc::new(AtomicU32::new(0));
    let requested=requested_events.clone();let accepted=accepted_events.clone();
    let pair_started = std::time::Instant::now();
    let handler = TypedEventHandler::<DeviceInformationCustomPairing, DevicePairingRequestedEventArgs>::new(
        move |_, args| {
            let count=requested.fetch_add(1,Ordering::Relaxed)+1;
            if let Some(args)=args {
                let kind=args.PairingKind()?;
                let allow=!callback_cancel.requested() && confirmation_supported(kind);
                eprintln!("BLE pairing_trace stage=ceremony_requested address={address:012X} elapsed_us={} event={count} kind={} confirm_only_allowed={allow}",
                    pair_started.elapsed().as_micros(),kind.0);
                if allow {
                    let result=args.Accept();
                    if result.is_ok(){accepted.fetch_add(1,Ordering::Relaxed);}
                    eprintln!("BLE pairing_trace stage=ceremony_accept address={address:012X} elapsed_us={} accepted={} error_hresult={:?}",
                        pair_started.elapsed().as_micros(),result.is_ok(),result.as_ref().err().map(|e|e.code().0));
                    result?;
                }
            }
            Ok(())
        });
    let token = custom.PairingRequested(&handler)
        .map_err(|error| format!("注册配对确认失败：{error}"))?;
    let _handler = PairingHandler { custom: custom.clone(), token };
    eprintln!("BLE pairing_trace stage=encrypted_pair_begin address={address:012X}");
    let operation = custom.PairWithProtectionLevelAsync(
        DevicePairingKinds::ConfirmOnly, DevicePairingProtectionLevel::Encryption)
        .map_err(|error| format!("开始加密配对失败：{error}"))?;
    let paired = match wait_async_operation_with_cancel(operation, PAIR_TIMEOUT, "encrypted pairing", cancel) {
        Ok(result)=>result,
        Err(error)=>{
            eprintln!("BLE pairing_trace stage=encrypted_pair_operation_error address={address:012X} elapsed_us={} requested_events={} accepted_events={} temporary_device_reference_held=0 error={error}",
                pair_started.elapsed().as_micros(),requested_events.load(Ordering::Relaxed),accepted_events.load(Ordering::Relaxed));
            return Err(error);
        }
    };
    let status = paired.Status().map_err(|error| format!("读取配对结果失败：{error}"))?;
    eprintln!("BLE pairing_trace stage=encrypted_pair_result address={address:012X} elapsed_us={} status={} requested_protection=Encryption reported_protection={:?} requested_events={} accepted_events={} temporary_device_reference_held=0",
        pair_started.elapsed().as_micros(), status.0, paired.ProtectionLevelUsed().ok(),requested_events.load(Ordering::Relaxed),accepted_events.load(Ordering::Relaxed));
    verify_pair_result(status)?;
    eprintln!("BLE Windows pairing completed before GATT address={address:012X} status={} requested_protection=Encryption reported_protection={:?}",
        status.0, paired.ProtectionLevelUsed().ok());
    // A Windows pairing receipt is not a substitute for the firmware's actual
    // encrypted GATT gate; normal protected reads/writes must still succeed.
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_pairing_category_survives_only_known_product_contexts() {
        for context in ["","Native BLE connect failed: ","Remembered Companion is offline: "] {
            assert!(is_pairing_error(&format!("{context}Windows BLE pairing required: Windows 状态 19")));
        }
        assert!(!is_pairing_error("Remembered Companion is offline: GATT device unreachable"));
        assert!(!is_pairing_error("A payload happened to contain Windows BLE pairing required: text"));
    }

    #[test]
    fn only_confirm_only_can_be_accepted_without_user_pin_or_comparison() {
        assert!(confirmation_supported(DevicePairingKinds::ConfirmOnly));
        for kind in [DevicePairingKinds::None, DevicePairingKinds::DisplayPin,
            DevicePairingKinds::ProvidePin, DevicePairingKinds::ConfirmPinMatch,
            DevicePairingKinds::ConfirmOnly | DevicePairingKinds::ConfirmPinMatch] {
            assert!(!confirmation_supported(kind));
        }
    }

    #[test]
    fn only_completed_pairing_is_accepted_and_failures_are_identifiable() {
        for status in [DevicePairingResultStatus::Paired, DevicePairingResultStatus::AlreadyPaired] {
            verify_pair_result(status).unwrap();
        }
        for status in [DevicePairingResultStatus::NotPaired, DevicePairingResultStatus::AuthenticationFailure,
            DevicePairingResultStatus::OperationAlreadyInProgress, DevicePairingResultStatus::Failed] {
            let error = pair_error(verify_pair_result(status).unwrap_err());
            assert!(is_pairing_error(&error));
            assert!(error.contains("板端录音仍保留"));
        }
    }

    #[test]
    fn unknown_pairing_failure_is_not_misreported_as_authentication_or_permission() {
        let unknown = verify_pair_result(DevicePairingResultStatus::Failed).unwrap_err();
        assert!(unknown.contains("未知配对失败") && unknown.contains("状态 19"));
        assert!(!unknown.contains("身份认证失败") && !unknown.contains("拒绝应用"));
        let denied = verify_pair_result(DevicePairingResultStatus::AccessDenied).unwrap_err();
        assert!(denied.contains("拒绝应用") && denied.contains("状态 12"));
        assert!(!denied.contains("打开配对窗口"));
        for value in 0..=20 {
            assert_eq!(verify_pair_result(DevicePairingResultStatus(value)).is_ok(), value == 0 || value == 3);
        }
    }

    #[test]
    fn address_must_be_a_complete_bluetooth_identity() {
        assert_eq!(parse_address("C8:92:FF:DD:3B:CA").unwrap(), 0xc892ffdd3bca);
        assert_eq!(parse_address("c8-92-ff-dd-3b-ca").unwrap(), 0xc892ffdd3bca);
        for value in ["Companion", "C8:92:FF:DD:3B", "C8:92:FF:DD:3B:CZ", "C892FFDD3BCA00"] {
            assert!(parse_address(value).is_err());
        }
    }
}
