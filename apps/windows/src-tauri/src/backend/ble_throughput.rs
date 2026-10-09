//! Bounded native preferences for GATT setup and sealed recording sync.
//! A preference request is not evidence that Windows applied its parameters.
#![cfg(windows)]

use std::sync::{atomic::{AtomicBool, Ordering}, Arc, Mutex};
use std::time::{Duration, Instant};

use btleplug::api::AddressType;
use denzic_ble_windows::{wait_async_operation_with_cancel, BleCancel};
use windows::Devices::Bluetooth::{
    BluetoothAddressType, BluetoothError, BluetoothLEDevice, BluetoothLEPreferredConnectionParameters,
    BluetoothLEPreferredConnectionParametersRequest,
};
use windows::Devices::Bluetooth::GenericAttributeProfile::{
    GattSession, GattSessionStatus, GattSessionStatusChangedEventArgs,
};
use windows::Foundation::{EventRegistrationToken, TypedEventHandler};

const OPEN_TIMEOUT: Duration = Duration::from_millis(1_000);
const WORKER_TIMEOUT: Duration = Duration::from_millis(1_250);

struct CancelOnDrop(Arc<AtomicBool>);
impl Drop for CancelOnDrop {
    fn drop(&mut self) { self.0.store(true, Ordering::SeqCst); }
}

struct SessionHandles {
    device: BluetoothLEDevice,
    session: Option<GattSession>,
    status_token: Option<EventRegistrationToken>,
}
impl Drop for SessionHandles {
    fn drop(&mut self) {
        if let Some(session) = self.session.take() {
            // Detach first so intentional owner cleanup is not a radio fault.
            if let Some(token) = self.status_token.take() {
                let _ = session.RemoveSessionStatusChanged(token);
            }
            let _ = session.SetMaintainConnection(false);
            let _ = session.Close();
            eprintln!("BLE connection_session maintain_requested=0 released=1");
        }
        let _ = self.device.Close();
    }
}

/// Keep the first loss even when Windows repeatedly retries a failed bond.
/// Observe WinRT events without extra ATT reads, retries or policy changes.
struct SessionObservation {
    started: Instant,
    active_seen: AtomicBool,
    first_loss: AtomicBool,
}
impl SessionObservation {
    fn observe(&self, address: u64, status: Option<GattSessionStatus>, error: Option<BluetoothError>) {
        if status == Some(GattSessionStatus::Active) {
            if !self.active_seen.swap(true, Ordering::Relaxed) {
                eprintln!("BLE session_trace address={address:012X} elapsed_us={} stage=first_active status={status:?} error={error:?}", self.started.elapsed().as_micros());
            }
            return;
        }
        let explicit_error = error.is_some_and(|value| value != BluetoothError::Success);
        if (self.active_seen.load(Ordering::Relaxed) || explicit_error)
            && !self.first_loss.swap(true, Ordering::Relaxed) {
            eprintln!("BLE session_trace address={address:012X} elapsed_us={} stage=first_loss was_active={} status={status:?} error={error:?} owner_cleanup=false",
                self.started.elapsed().as_micros(), self.active_seen.load(Ordering::Relaxed));
        }
    }
}

/// Shared by the actual native connection clones. A BluetoothLEDevice handle
/// alone does not request a link during a long recording with no ATT traffic.
/// Explicit disconnect closes this guard for every clone; normal completion
/// drops it when no user/recorder owner remains. This requests no fast interval.
pub(super) struct ConnectionSession {
    handles: Mutex<Option<SessionHandles>>,
}
impl ConnectionSession {
    pub(super) fn is_open(&self) -> bool {
        self.handles.lock().unwrap_or_else(|error| error.into_inner()).is_some()
    }

    pub(super) fn close(&self) {
        let handles = self.handles.lock().unwrap_or_else(|error| error.into_inner()).take();
        drop(handles);
    }
}

pub(super) async fn maintain_connection(
    address: &str, address_type: Option<AddressType>,
) -> Result<Arc<ConnectionSession>, String> {
    let compact: String = address.trim().chars().filter(|ch| *ch != ':' && *ch != '-').collect();
    if compact.len() != 12 || !compact.bytes().all(|ch| ch.is_ascii_hexdigit()) {
        return Err("无法为无效设备地址维持蓝牙会话。".into());
    }
    let address = u64::from_str_radix(&compact, 16).map_err(|_| "设备蓝牙地址无效。")?;
    let cancel = Arc::new(AtomicBool::new(false));
    let _cancel_on_drop = CancelOnDrop(cancel.clone());
    let worker = tokio::task::spawn_blocking(move || {
        let cancel = BleCancel::new(cancel, "cancelled Companion connection session");
        let device = open_device(address, address_type, &cancel)?;
        let mut handles = SessionHandles { device, session: None, status_token: None };
        let id = handles.device.BluetoothDeviceId().map_err(|e| format!("connection device identity: {e}"))?;
        let operation = GattSession::FromDeviceIdAsync(&id).map_err(|e| format!("create connection session: {e}"))?;
        handles.session = Some(wait_async_operation_with_cancel(
            operation, OPEN_TIMEOUT, "connection session open", &cancel)?);
        let session = handles.session.as_ref().ok_or("connection session missing")?;
        let observation = Arc::new(SessionObservation {
            started: Instant::now(), active_seen: AtomicBool::new(false), first_loss: AtomicBool::new(false),
        });
        let event_observation = observation.clone();
        let handler = TypedEventHandler::<GattSession, GattSessionStatusChangedEventArgs>::new(move |_, args| {
            if let Some(args) = args {
                event_observation.observe(address, args.Status().ok(), args.Error().ok());
            }
            Ok(())
        });
        match session.SessionStatusChanged(&handler) {
            Ok(token) => handles.status_token = Some(token),
            Err(error) => eprintln!("BLE session_trace address={address:012X} stage=observer_unavailable cause={error}; normal_connection_retained=1"),
        }
        observation.observe(address, session.SessionStatus().ok(), None);
        if !session.CanMaintainConnection().map_err(|e| format!("connection session capability: {e}"))? {
            return Err("Windows 当前不能为此设备维持蓝牙会话；未发送开录命令。".into());
        }
        session.SetMaintainConnection(true).map_err(|e| format!("maintain Companion connection: {e}"))?;
        if cancel.requested() { return Err(cancel.cancelled_error("connection session")); }
        eprintln!("BLE connection_session maintain_requested=1 status={:?} owner=normal_user_or_recorder", session.SessionStatus().ok());
        Ok(Arc::new(ConnectionSession { handles: Mutex::new(Some(handles)) }))
    });
    match tokio::time::timeout(Duration::from_millis(2_500), worker).await {
        Ok(Ok(result)) => result,
        Ok(Err(error)) => Err(format!("connection session worker: {error}")),
        Err(_) => Err("connection session creation timed out; no recording START issued".into()),
    }
}

pub(super) struct TransferPreference {
    device: BluetoothLEDevice,
    request: Option<BluetoothLEPreferredConnectionParametersRequest>,
    scope: &'static str,
}
impl Drop for TransferPreference {
    fn drop(&mut self) {
        // Read the actual interval after the scoped operation, before releasing the
        // preference. Request acceptance alone does not prove negotiation.
        let interval = self.device.GetConnectionParameters().ok()
            .and_then(|p| p.ConnectionInterval().ok());
        eprintln!("recording native throughput preference scope={} end_interval_units={interval:?}", self.scope);
        if let Some(request) = self.request.take() { let _ = request.Close(); }
        // This is a temporary reference to a device already owned by the
        // native connection, not the owner of that connection. WinRT can
        // share its device object across opens: Close would invalidate the
        // retained GATT objects after setup or between backlog entries.
        // Release this COM reference normally. Only the connection owner
        // closes the device/session on disconnect, failure or final release.
    }
}

/// Unsupported Windows versions/adapters keep the normal protected GATT path.
/// No external process, persistent parameter override, or connection retry.
/// Hold through receive, durable host commit and exact device consume receipt.
/// A cached retry still needs its control exchange; live capture never calls it.
pub(super) async fn request_for_sealed_sync(
    address: &str, address_type: Option<AddressType>,
) -> Option<TransferPreference> {
    request_scoped(address, address_type, "sealed_receive_and_reclaim").await
}

/// Pairing must finish before this is called. Hold the request through the
/// uncached service/descriptor enumeration and clock sync, then drop it before
/// returning the normal idle/user connection. Errors and cancelled futures
/// release it through the same guard as recording receive.
pub(super) async fn request_for_connection_setup(
    address: &str, address_type: Option<AddressType>,
) -> Option<TransferPreference> {
    request_scoped(address, address_type, "connection_setup").await
}

async fn request_scoped(
    address: &str, address_type: Option<AddressType>, scope: &'static str,
) -> Option<TransferPreference> {
    if std::env::var("COMPANION_TYPE_SKIP_WINRT_CONN_PARAMS")
        .map(|v| matches!(v.trim().to_ascii_lowercase().as_str(), "1" | "true" | "on"))
        .unwrap_or(false) { return None; }
    let compact: String = address.trim().chars().filter(|ch| *ch != ':' && *ch != '-').collect();
    if compact.len() != 12 || !compact.bytes().all(|ch| ch.is_ascii_hexdigit()) { return None; }
    let address = u64::from_str_radix(&compact, 16).ok()?;
    let cancel = Arc::new(AtomicBool::new(false));
    let _cancel_on_drop = CancelOnDrop(cancel.clone());
    let worker = tokio::task::spawn_blocking(move || {
        let cancel = BleCancel::new(cancel, "cancelled recording throughput preference");
        open_preference(address, address_type, scope, &cancel)
    });
    match tokio::time::timeout(WORKER_TIMEOUT, worker).await {
        Ok(Ok(Ok(preference))) => Some(preference),
        Ok(Ok(Err(error))) => { eprintln!("recording native throughput preference unavailable: {error}"); None },
        Ok(Err(error)) => { eprintln!("recording native throughput preference worker: {error}"); None },
        Err(_) => { eprintln!("recording native throughput preference timeout; normal GATT retained"); None },
    }
}

fn open_preference(address: u64, address_type: Option<AddressType>, scope: &'static str, cancel: &BleCancel)
    -> Result<TransferPreference, String>
{
    if cancel.requested() { return Err(cancel.cancelled_error("throughput preference")); }
    let parameters = BluetoothLEPreferredConnectionParameters::ThroughputOptimized()
        .map_err(|e| format!("ThroughputOptimized: {e}"))?;
    let device = open_device(address, address_type, cancel)?;
    let mut preference = TransferPreference { device, request: None, scope };
    if cancel.requested() { return Err(cancel.cancelled_error("throughput preference")); }
    preference.request = Some(preference.device.RequestPreferredConnectionParameters(&parameters)
        .map_err(|e| format!("request throughput preference: {e}"))?);
    if cancel.requested() { return Err(cancel.cancelled_error("throughput preference")); }
    let status = preference.request.as_ref().and_then(|r| r.Status().ok());
    let interval = preference.device.GetConnectionParameters().ok()
        .and_then(|p| p.ConnectionInterval().ok());
    eprintln!("recording native throughput preference scope={scope} request_status={status:?} current_interval_units={interval:?} held_until_sync_end={} held_until_setup_end={}",
        u8::from(scope == "sealed_receive_and_reclaim"), u8::from(scope == "connection_setup"));
    Ok(preference)
}

fn open_device(address: u64, address_type: Option<AddressType>, cancel: &BleCancel)
    -> Result<BluetoothLEDevice, String>
{
    if cancel.requested() { return Err(cancel.cancelled_error("connection device open")); }
    let operation = match address_type {
        Some(kind) => BluetoothLEDevice::FromBluetoothAddressWithBluetoothAddressTypeAsync(
            address, match kind { AddressType::Random => BluetoothAddressType::Random,
                AddressType::Public => BluetoothAddressType::Public }),
        None => BluetoothLEDevice::FromBluetoothAddressAsync(address),
    }.map_err(|e| format!("open throughput device: {e}"))?;
    wait_async_operation_with_cancel(operation, OPEN_TIMEOUT, "connection device open", cancel)
}
