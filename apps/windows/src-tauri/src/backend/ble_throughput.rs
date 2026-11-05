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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SealedBootstrapProfile { Balanced, ThroughputBootstrap, ThroughputHold }
impl SealedBootstrapProfile {
    fn parse(value: Option<&str>) -> Result<Self, String> {
        match value.map(str::trim).unwrap_or("") {
            "" | "balanced" => Ok(Self::Balanced),
            "throughput_bootstrap" => Ok(Self::ThroughputBootstrap),
            "throughput_hold" => Ok(Self::ThroughputHold),
            _ => Err("unknown sealed connection diagnostic profile; normal GATT retained".into()),
        }
    }
    fn release_at_peer_handoff(self) -> bool { self != Self::ThroughputHold }
    fn name(self) -> &'static str {
        match self { Self::Balanced=>"balanced",Self::ThroughputBootstrap=>"throughput_bootstrap",Self::ThroughputHold=>"throughput_hold" }
    }
}

struct CancelOnDrop(Arc<AtomicBool>);
impl Drop for CancelOnDrop {
    fn drop(&mut self) { self.0.store(true, Ordering::SeqCst); }
}

struct SessionHandles {
    device: BluetoothLEDevice,
    session: Option<GattSession>,
    status_token: Option<EventRegistrationToken>,
    maintain_requested: bool,
    observation: Arc<SessionObservation>,
}
impl Drop for SessionHandles {
    fn drop(&mut self) {
        self.observation.close_owner();
        if let Some(session) = self.session.take() {
            // Detach first so intentional owner cleanup is not a radio fault.
            if let Some(token) = self.status_token.take() {
                let _ = session.RemoveSessionStatusChanged(token);
            }
            if self.maintain_requested {
                let release_started = Instant::now();
                let released = session.SetMaintainConnection(false);
                self.maintain_requested=false;
                // A local owner retirement is distinct from Windows accepting
                // its property write, and neither proves radio disconnection.
                // Retain the native HRESULT instead of reporting false success.
                match released {
                    Ok(()) => eprintln!("BLE connection_session maintain_requested=0 release_attempted=1 release_confirmed=1 release_call_us={} physical_disconnect=unconfirmed", release_started.elapsed().as_micros()),
                    Err(error) => eprintln!("BLE connection_session maintain_requested=unknown release_attempted=1 release_confirmed=0 release_call_us={} release_error={error:?} physical_disconnect=unconfirmed", release_started.elapsed().as_micros()),
                }
            }
            // Release this wrapper's COM reference after detaching its event.
            // The peripheral owns a separate device/service reference.
            drop(session);
        }
    }
}

/// Keep the first loss even when Windows repeatedly retries a failed bond.
/// Observe WinRT events without extra ATT reads, retries or policy changes.
struct SessionObservation {
    started: Instant,
    active_seen: AtomicBool,
    owner_closed: AtomicBool,
    // Sticky for this actual session, even if Windows later reconnects its
    // device object. Old notification/ACK state cannot cross that boundary.
    terminal: tokio::sync::watch::Sender<Option<String>>,
}
impl SessionObservation {
    fn new() -> Self {
        let (terminal, _) = tokio::sync::watch::channel(None);
        Self { started: Instant::now(), active_seen: AtomicBool::new(false),
            owner_closed: AtomicBool::new(false), terminal }
    }

    fn error(&self) -> Option<String> { self.terminal.borrow().clone() }

    fn close_owner(&self) {
        self.owner_closed.store(true, Ordering::SeqCst);
        self.terminal.send_if_modified(|state| {
            if state.is_some() { return false; }
            *state=Some("BLE session disconnected: connection owner released; original recording retained".into());
            true
        });
    }

    fn observe(&self, address: u64, status: Option<GattSessionStatus>, error: Option<BluetoothError>) {
        if self.owner_closed.load(Ordering::SeqCst) { return; }
        let explicit_error = error.is_some_and(|value| value != BluetoothError::Success);
        if status == Some(GattSessionStatus::Active) && !explicit_error {
            if !self.active_seen.swap(true, Ordering::SeqCst) {
                eprintln!("BLE session_trace address={address:012X} elapsed_us={} stage=first_active status={status:?} error={error:?}", self.started.elapsed().as_micros());
            }
            return;
        }
        // Initial Closed is normal before the first successful connection;
        // unknown event fields alone do not prove a lost link.
        if !explicit_error && !(self.active_seen.load(Ordering::SeqCst)
            && status == Some(GattSessionStatus::Closed)) { return; }
        self.terminal.send_if_modified(|state| {
            if state.is_some() { return false; }
            let detail=format!("BLE session disconnected: address={address:012X} status={status:?} error={error:?}; original recording retained; reconnect with a fresh verified session");
            eprintln!("BLE session_trace address={address:012X} elapsed_us={} stage=first_loss was_active={} status={status:?} error={error:?} owner_cleanup=false", self.started.elapsed().as_micros(),self.active_seen.load(Ordering::SeqCst));
            *state=Some(detail);
            true
        });
    }

    async fn guard<T>(&self, work: impl std::future::Future<Output=Result<T,String>>) -> Result<T,String> {
        let mut terminal=self.terminal.subscribe();
        // Subscribe before checking, covering a callback before the wait is
        // polled. Watch retains the first loss without a per-packet timer.
        if let Some(error)=terminal.borrow().clone() { return Err(error); }
        tokio::select! {
            biased;
            changed=terminal.changed()=> {
                let error=terminal.borrow().clone().unwrap_or_else(||
                    format!("BLE session disconnected: state observer ended ({changed:?}); original recording retained"));
                Err(error)
            }
            result=work=> {
                if let Some(error)=self.error() { Err(error) } else { result }
            }
        }
    }
}

/// Shared by the actual native connection clones. A BluetoothLEDevice handle
/// alone does not request a link during a long recording with no ATT traffic.
/// Explicit disconnect closes this guard for every clone; normal completion
/// drops it when no user/recorder owner remains. This requests no fast interval.
pub(super) struct ConnectionSession {
    handles: Mutex<Option<SessionHandles>>,
    observation: Arc<SessionObservation>,
}
impl ConnectionSession {
    /// Preserve the error that made this owner unusable before intentional
    /// cleanup signals its watchers. Otherwise the outer guard can cancel
    /// its own cleanup and replace the real failure with "owner released".
    pub(super) fn retire_with_cause(&self, cause: &str) {
        self.observation.terminal.send_if_modified(|state| {
            if state.is_some() {return false;}
            *state=Some(cause.to_owned());true
        });
        self.close();
    }

    pub(super) fn is_open(&self) -> bool {
        self.observation.error().is_none()
            && self.handles.lock().unwrap_or_else(|error| error.into_inner()).is_some()
    }

    pub(super) async fn guard<T>(&self, work: impl std::future::Future<Output=Result<T,String>>) -> Result<T,String> {
        self.observation.guard(work).await
    }

    pub(super) fn close(&self) {
        let handles = self.handles.lock().unwrap_or_else(|error| error.into_inner()).take();
        drop(handles);
    }

    /// Read the owned session; waiting creates no extra connection handle,
    /// connection preference, ATT operation or MTU request.
    pub(super) async fn wait_recording_mtu(&self, budget: Duration) -> Result<u16, String> {
        let wait = super::ble_mtu::MtuWait::new("V2 recording", super::ble_mtu::RECORDING_MIN_MTU, budget);
        let started = Instant::now();
        loop {
            let actual = {
                let handles = self.handles.lock().unwrap_or_else(|error| error.into_inner());
                let session = handles.as_ref().and_then(|handles| handles.session.as_ref())
                    .ok_or("Recording connection closed while waiting for MTU; no protocol write was sent")?;
                session.MaxPduSize().map_err(|error| format!("recording actual ATT MTU: {error}"))?
            };
            if let Some(mtu) = wait.observe(actual, started.elapsed())? {
                eprintln!("BLE recording_mtu actual_att_mtu={mtu} ready=1 elapsed_ms={}", started.elapsed().as_millis());
                return Ok(mtu);
            }
            tokio::time::sleep(Duration::from_millis(50).min(budget.saturating_sub(started.elapsed()))).await;
        }
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
        let observation = Arc::new(SessionObservation::new());
        let mut handles = SessionHandles { device, session: None, status_token: None,
            maintain_requested:false, observation: observation.clone() };
        let id = handles.device.BluetoothDeviceId().map_err(|e| format!("connection device identity: {e}"))?;
        let operation = GattSession::FromDeviceIdAsync(&id).map_err(|e| format!("create connection session: {e}"))?;
        handles.session = Some(wait_async_operation_with_cancel(
            operation, OPEN_TIMEOUT, "connection session open", &cancel)?);
        let session = handles.session.as_ref().ok_or("connection session missing")?;
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
        handles.maintain_requested=true;
        if cancel.requested() { return Err(cancel.cancelled_error("connection session")); }
        eprintln!("BLE connection_session maintain_requested=1 status={:?} owner=normal_user_or_recorder", session.SessionStatus().ok());
        Ok(Arc::new(ConnectionSession { handles: Mutex::new(Some(handles)), observation }))
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
    parameter_token: Option<EventRegistrationToken>,
    phy_token: Option<EventRegistrationToken>,
    parameter_observation: Arc<ParameterObservation>,
    sealed_bootstrap: bool,
    payload_release_attempted: bool,
}

impl TransferPreference {
    pub(super) fn handoff_to_sealed_sync(&mut self) {
        // Keep the existing WinRT request alive. Close/reopen can queue a
        // normal interval update that lands after the new upload request.
        eprintln!("recording_link_timeline scope={} stage=handoff_to_sealed_sync elapsed_us={} preference_not_released=1 host_unix_us={}",
            self.scope, self.parameter_observation.started.elapsed().as_micros(),
            chrono::Utc::now().timestamp_micros());
        self.scope = if self.sealed_bootstrap { "sealed_bootstrap_to_peer_interval" }
            else { "connection_setup_through_sealed_sync" };
    }

    /// The first validated, uncached payload proves the bulk path is open.
    /// Release the initial request once and let the peripheral's policy own
    /// the payload interval. No replacement Windows preference is issued.
    pub(super) fn release_after_verified_payload(&mut self) {
        self.release_bootstrap("first_verified_payload");
    }

    /// The authenticated batch ACK proves that the peripheral admitted the
    /// scoped batch owner. It does not prove peer acceptance of a parameter
    /// request or an applied fast interval; only observed parameters do that.
    pub(super) fn release_after_verified_batch_owner(&mut self) {
        self.release_bootstrap("verified_peripheral_batch_owner");
    }

    fn release_bootstrap(&mut self,stage:&'static str) {
        if !self.sealed_bootstrap || self.payload_release_attempted { return; }
        self.payload_release_attempted = true;
        let Some(request) = self.request.take() else { return; };
        trace_native_link(&self.device,self.scope,"before_peer_handoff",Some(&request));
        let result = request.Close();
        let (interval, latency, supervision) = observed_parameters(&self.device);
        eprintln!("recording_link_timeline scope={} stage={stage} bootstrap_released={} interval_units={interval:?} latency={latency:?} supervision_units={supervision:?} elapsed_us={} host_unix_us={} release_error={:?} replacement_preference=none",
            self.scope, u8::from(result.is_ok()), self.parameter_observation.started.elapsed().as_micros(),
            chrono::Utc::now().timestamp_micros(), result.as_ref().err());
        if result.is_err() { self.request = Some(request); }
    }
}

struct ParameterObservation {
    started: Instant,
    changes: std::sync::atomic::AtomicU64,
    phy_changes: std::sync::atomic::AtomicU64,
}

fn observed_parameters(device: &BluetoothLEDevice) -> (Option<u16>, Option<u16>, Option<u16>) {
    let parameters = device.GetConnectionParameters().ok();
    (
        parameters.as_ref().and_then(|p| p.ConnectionInterval().ok()),
        parameters.as_ref().and_then(|p| p.ConnectionLatency().ok()),
        parameters.as_ref().and_then(|p| p.LinkTimeout().ok()),
    )
}

// Read-only WinRT state at the same phase boundary for recording and OTA.
// Success means the OS accepted the preference, not that its values were applied.
// These getters do not perform ATT reads and cannot set controller DLE/PHY.
pub(super) fn trace_native_link(
    device: &BluetoothLEDevice, scope: &str, stage: &str,
    request: Option<&BluetoothLEPreferredConnectionParametersRequest>,
) {
    let connected = device.ConnectionStatus().ok().map(|s|
        s == windows::Devices::Bluetooth::BluetoothConnectionStatus::Connected);
    let accepted = request.and_then(|r| r.Status().ok()).map(|s|
        s == windows::Devices::Bluetooth::BluetoothLEPreferredConnectionParametersRequestStatus::Success);
    let (interval, latency, supervision) = if connected == Some(true) {
        observed_parameters(device)
    } else { (None, None, None) };
    let phy = if connected == Some(true) { device.GetConnectionPhy().ok() } else { None };
    let decode = |info: windows::Devices::Bluetooth::BluetoothLEConnectionPhyInfo| {
        if info.IsUncoded2MPhy().ok() == Some(true) { Some(2u8) }
        else if info.IsUncoded1MPhy().ok() == Some(true) { Some(1u8) }
        else if info.IsCodedPhy().ok() == Some(true) { Some(3u8) } else { None }
    };
    let tx_phy = phy.as_ref().and_then(|p| p.TransmitInfo().ok()).and_then(decode);
    let rx_phy = phy.as_ref().and_then(|p| p.ReceiveInfo().ok()).and_then(decode);
    eprintln!("ble_link_observed schema=1 scope={scope} stage={stage} connected={connected:?} preference_accepted={accepted:?} applied_not_guaranteed=1 actual_interval_units={interval:?} actual_latency={latency:?} actual_supervision_units={supervision:?} actual_tx_phy={tx_phy:?} actual_rx_phy={rx_phy:?} no_extra_att_reads=1 host_unix_us={}",
        chrono::Utc::now().timestamp_micros());
}

impl Drop for TransferPreference {
    fn drop(&mut self) {
        let observer_registered = self.parameter_token.is_some();
        if let Some(token) = self.phy_token.take() {
            let _ = self.device.RemoveConnectionPhyChanged(token);
        }
        trace_native_link(&self.device,self.scope,"owner_end",self.request.as_ref());
        if let Some(token) = self.parameter_token.take() {
            let _ = self.device.RemoveConnectionParametersChanged(token);
        }
        // Read the actual interval after the scoped operation, before releasing the
        // preference. Request acceptance alone does not prove negotiation.
        let interval = self.device.GetConnectionParameters().ok()
            .and_then(|p| p.ConnectionInterval().ok());
        eprintln!("recording native throughput preference scope={} end_interval_units={interval:?}", self.scope);
        eprintln!("recording_link_timeline scope={} stage=end elapsed_us={} parameter_changes={} event_log_limit=32 observer_registered={} no_extra_att_reads=1 host_unix_us={}",
            self.scope, self.parameter_observation.started.elapsed().as_micros(),
            self.parameter_observation.changes.load(Ordering::Relaxed), observer_registered,
            chrono::Utc::now().timestamp_micros());
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
/// Existing/protected connections use the same Balanced bootstrap as a fresh
/// sealed sync; the operation releases it after its first verified payload.
/// A cached retry still needs its control exchange; live capture never calls it.
pub(super) async fn request_for_sealed_sync(
    address: &str, address_type: Option<AddressType>,
) -> Option<TransferPreference> {
    request_scoped(address, address_type, "sealed_receive_and_reclaim", true).await
}

/// Pairing must finish before this is called. Hold the request through the
/// uncached service/descriptor enumeration and clock sync, then drop it before
/// returning the normal idle/user connection. Errors and cancelled futures
/// release it through the same guard as recording receive.
pub(super) async fn request_for_connection_setup(
    address: &str, address_type: Option<AddressType>,
) -> Option<TransferPreference> {
    request_scoped(address, address_type, "connection_setup", false).await
}

/// A sealed-file connection uses this bootstrap, before the
/// maintained session starts. Normal/live connections retain their policy.
/// Same-file HCI measurements showed Balanced preserving a larger packet
/// time budget, and its release allowing the peripheral's faster interval.
pub(super) async fn request_for_sealed_connection_setup(
    address: &str, address_type: Option<AddressType>,
) -> Option<TransferPreference> {
    request_scoped(address, address_type, "sealed_connection_bootstrap", true).await
}

async fn request_scoped(
    address: &str, address_type: Option<AddressType>, scope: &'static str, sealed_bootstrap: bool,
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
        open_preference(address, address_type, scope, sealed_bootstrap, &cancel)
    });
    match tokio::time::timeout(WORKER_TIMEOUT, worker).await {
        Ok(Ok(Ok(preference))) => Some(preference),
        Ok(Ok(Err(error))) => { eprintln!("recording native throughput preference unavailable: {error}"); None },
        Ok(Err(error)) => { eprintln!("recording native throughput preference worker: {error}"); None },
        Err(_) => { eprintln!("recording native throughput preference timeout; normal GATT retained"); None },
    }
}

fn open_preference(address: u64, address_type: Option<AddressType>, scope: &'static str, sealed_bootstrap: bool, cancel: &BleCancel)
    -> Result<TransferPreference, String>
{
    if cancel.requested() { return Err(cancel.cancelled_error("throughput preference")); }
    // Separate initial-controller scheduling from the previously failed held
    // profile. Bootstrap releases at the existing verified peer ownership
    // exchange (or first verified payload), before sustained receive. Normal
    // products still default to Balanced; all guards/cancellation stay intact.
    let profile = if sealed_bootstrap {
        let value=match std::env::var("COMPANION_TYPE_BLE_SEALED_BOOTSTRAP_PROFILE") {
            Ok(v)=>Some(v), Err(std::env::VarError::NotPresent)=>None,
            Err(_)=>return Err("invalid sealed connection diagnostic profile".into()),
        };
        SealedBootstrapProfile::parse(value.as_deref())?
    } else { SealedBootstrapProfile::ThroughputHold };
    let diagnostic=sealed_bootstrap && profile!=SealedBootstrapProfile::Balanced;
    let held=sealed_bootstrap && !profile.release_at_peer_handoff();
    let parameters = if sealed_bootstrap && profile==SealedBootstrapProfile::Balanced { BluetoothLEPreferredConnectionParameters::Balanced() }
        else { BluetoothLEPreferredConnectionParameters::ThroughputOptimized() }
        .map_err(|e| format!("connection preference: {e}"))?;
    eprintln!("recording connection_policy profile={} diagnostic={} held_through_payload={} release_at_peer_handoff={}",
        if sealed_bootstrap { profile.name() } else { "throughput" }, u8::from(diagnostic),u8::from(held),
        u8::from(sealed_bootstrap && profile.release_at_peer_handoff()));
    let sealed_bootstrap=sealed_bootstrap && profile.release_at_peer_handoff();
    let device = open_device(address, address_type, cancel)?;
    let observation = Arc::new(ParameterObservation {
        started: Instant::now(), changes: std::sync::atomic::AtomicU64::new(0),
        phy_changes: std::sync::atomic::AtomicU64::new(0),
    });
    let mut preference = TransferPreference {
        device, request: None, scope, parameter_token: None, phy_token: None, parameter_observation: observation.clone(),
        sealed_bootstrap, payload_release_attempted: false,
    };
    let handler = TypedEventHandler::<BluetoothLEDevice, windows::core::IInspectable>::new(move |sender, _| {
        let change = observation.changes.fetch_add(1, Ordering::Relaxed) + 1;
        if change <= 32 {
            if let Some(device) = sender {
                trace_native_link(device,scope,"parameters_changed",None);
                let (interval, latency, supervision) = observed_parameters(device);
                eprintln!("recording_link_timeline scope={scope} stage=parameters_changed elapsed_us={} event={} interval_units={interval:?} latency={latency:?} supervision_units={supervision:?} no_extra_att_reads=1 host_unix_us={}",
                    observation.started.elapsed().as_micros(), change, chrono::Utc::now().timestamp_micros());
            }
        }
        Ok(())
    });
    match preference.device.ConnectionParametersChanged(&handler) {
        Ok(token) => preference.parameter_token = Some(token),
        Err(error) => eprintln!("recording_link_timeline scope={scope} stage=observer_unavailable cause={error}; normal_preference_retained=1"),
    }
    let phy_observation = preference.parameter_observation.clone();
    let phy_handler = TypedEventHandler::<BluetoothLEDevice,windows::core::IInspectable>::new(move |sender,_| {
        let change=phy_observation.phy_changes.fetch_add(1,Ordering::Relaxed)+1;
        if change<=32 {
            if let Some(device)=sender { trace_native_link(device,scope,"phy_changed",None); }
        }
        Ok(())
    });
    match preference.device.ConnectionPhyChanged(&phy_handler) {
        Ok(token)=>preference.phy_token=Some(token),
        Err(error)=>eprintln!("ble_link_observed scope={scope} stage=phy_observer_unavailable cause={error}; normal_connection_retained=1"),
    }
    let (interval, latency, supervision) = observed_parameters(&preference.device);
    eprintln!("recording_link_timeline scope={scope} stage=start elapsed_us={} interval_units={interval:?} latency={latency:?} supervision_units={supervision:?} no_extra_att_reads=1 host_unix_us={}",
        preference.parameter_observation.started.elapsed().as_micros(), chrono::Utc::now().timestamp_micros());
    if cancel.requested() { return Err(cancel.cancelled_error("throughput preference")); }
    preference.request = Some(preference.device.RequestPreferredConnectionParameters(&parameters)
        .map_err(|e| format!("request throughput preference: {e}"))?);
    if cancel.requested() { return Err(cancel.cancelled_error("throughput preference")); }
    trace_native_link(&preference.device,scope,"preference_requested",preference.request.as_ref());
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

#[cfg(test)]
mod session_loss_tests {
    use super::*;
    use std::sync::atomic::AtomicUsize;
    use crate::backend::recording_transfer::{Cursor, ReceiveCursor, Source};
    use sha2::{Digest, Sha256};

    const ADDRESS:u64=0xc892ffdd3bca;

    #[tokio::test]
    async fn r53_session_loss_interrupts_control_wait_and_preserves_exact_durable_command() {
        use crate::backend::recorder_control::{Journal,Store};
        use crate::backend::recording_wire::control::{PausePeer,PauseStatus};
        let root=std::env::temp_dir().join(format!("companion-control-loss-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let path=root.join("library.json");
        let bytes=include_bytes!("cop1/tests/engine-local-controls.cms3");
        let wire=&bytes[8..88];let status=PauseStatus::decode(wire).unwrap();
        let peer=PausePeer::from_verified_peer(&crate::backend::recording_wire::transport::Peer {
            uid:status.device_uid,epoch:status.format_epoch,capacity:64,max_value_bytes:248,
            logical_control:true,growing_tail:true,pause_control:true,batch_interval:true,
        }).unwrap();
        let mut journal=Journal::start(&peer,"r53-original","C8:92:FF:DD:3B:CA",status.request,600).unwrap();
        journal.observe_with_peer(&peer,&status,u32::from_le_bytes(wire[12..16].try_into().unwrap()),
            u32::from_le_bytes(wire[20..24].try_into().unwrap())).unwrap();
        journal.prepare(&peer,4).unwrap();let original=journal.clone();
        let mut store=Store::open(&path,&journal.host_session).unwrap();store.commit(journal).unwrap();
        let state=Arc::new(SessionObservation::new());state.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        let worker=state.clone();let (entered,ready)=tokio::sync::oneshot::channel();
        let task=tokio::spawn(async move {
            // This is the same sticky guard now used by setup/probe/CMC3,
            // with an actual persisted intent held through the cancelled wait.
            worker.guard(async {
                let _store=store;let _=entered.send(());
                tokio::time::sleep(Duration::from_secs(60)).await;
                Ok::<_,String>("incorrectly confirmed by a late control wait")
            }).await
        });
        ready.await.unwrap();state.observe(ADDRESS,Some(GattSessionStatus::Closed),Some(BluetoothError::Success));
        let error=tokio::time::timeout(Duration::from_secs(1),task).await.unwrap().unwrap().unwrap_err();
        assert!(error.starts_with("BLE session disconnected:"));
        let restored=Store::open(&path,"r53-original").unwrap();
        assert_eq!(restored.journal.as_ref(),Some(&original),"loss is neither a PAUSE acknowledgement nor a replacement START");
        drop(restored);std::fs::remove_dir_all(root).unwrap();
    }

    #[tokio::test]
    async fn r53_session_loss_cannot_publish_late_setup_success() {
        let state=SessionObservation::new();state.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        let result=state.guard(async {
            // WinRT may complete an already queued read at the same time as
            // the terminal callback; that read cannot qualify this old link.
            state.observe(ADDRESS,Some(GattSessionStatus::Closed),Some(BluetoothError::Success));
            Ok("ready")
        }).await;
        assert!(result.unwrap_err().starts_with("BLE session disconnected:"));
    }

    #[tokio::test]
    async fn session_loss_initial_closed_is_not_failure_but_active_loss_is_sticky() {
        let state=SessionObservation::new();
        state.observe(ADDRESS,Some(GattSessionStatus::Closed),None);
        state.observe(ADDRESS,None,Some(BluetoothError::Success));
        assert_eq!(state.guard(async {Ok(7)}).await.unwrap(),7);
        state.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        state.observe(ADDRESS,None,None);
        assert!(state.error().is_none(),"unknown fields are not proof of a disconnect");
        state.observe(ADDRESS,Some(GattSessionStatus::Closed),Some(BluetoothError::Success));
        let first=state.error().unwrap();
        // Windows can reconnect its device object; the old CCCD/receive state
        // must still be retired and a fresh protected session established.
        state.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        let calls=AtomicUsize::new(0);
        assert_eq!(state.guard(async {calls.fetch_add(1,Ordering::SeqCst);Ok(8)}).await.unwrap_err(),first);
        assert_eq!(calls.load(Ordering::SeqCst),0,"do not send another START/resume on a lost session");
    }

    #[tokio::test]
    async fn session_loss_interrupts_pending_receive_and_preserves_actual_durable_prefix() {
        let root=std::env::temp_dir().join(format!("companion-session-loss-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();
        let body:Vec<u8>=(0..16_384).map(|n|(n%239)as u8).collect();
        let digest=Sha256::digest(&body);
        let source=Source{device:"same-sealed-session-loss".into(),recording_id:18,codec:3,
            source_mode:1,duration_ms:120_000,total_length:body.len()as u32,
            sha256_prefix:digest[..8].try_into().unwrap(),content_crc32:crc32fast::hash(&body)};
        let state=Arc::new(SessionObservation::new());
        state.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        let worker_state=state.clone();let worker_root=root.clone();let worker_source=source.clone();
        let prefix=body[..8_192].to_vec();
        let (ready,received)=tokio::sync::oneshot::channel();
        let task=tokio::spawn(async move {
            worker_state.guard(async {
                let(mut cursor,old)=ReceiveCursor::open(&worker_root,worker_source).await?;
                assert!(old.is_empty());
                cursor.append(&prefix).await?;
                cursor.checkpoint().await?;
                let _=ready.send(());
                // The actual receive cursor lives in this cancelled future;
                // its normal drop drains accepted data and releases its lock.
                std::future::pending::<()>().await;
                Ok::<_,String>(())
            }).await
        });
        received.await.unwrap();
        state.observe(ADDRESS,Some(GattSessionStatus::Closed),Some(BluetoothError::Success));
        let error=tokio::time::timeout(Duration::from_secs(2),task).await.unwrap().unwrap().unwrap_err();
        assert!(error.starts_with("BLE session disconnected:"));
        let(cursor,persisted)=Cursor::open(&root,source).unwrap();
        assert_eq!(persisted,body[..8_192]);
        assert!(persisted.len()<body.len(),"failure must not promote an incomplete original to saved/consumed");
        drop(cursor);std::fs::remove_dir_all(root).unwrap();
    }

    #[tokio::test]
    async fn retiring_failed_owner_keeps_primary_cleanup_cause_and_first_native_loss() {
        let observed=Arc::new(SessionObservation::new());
        observed.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        let owner=Arc::new(ConnectionSession{handles:Mutex::new(None),observation:observed.clone()});
        let work_owner=owner.clone();
        let cause="sealed stream release failed before reclaim: cannot unsubscribe lane B";
        let result=observed.guard(async move {
            work_owner.retire_with_cause(cause);
            std::future::pending::<()>().await;Ok::<_,String>(())
        }).await.unwrap_err();
        assert_eq!(result,cause);observed.close_owner();assert_eq!(observed.error().as_deref(),Some(cause));
        let radio=Arc::new(SessionObservation::new());
        radio.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        radio.observe(ADDRESS,Some(GattSessionStatus::Closed),Some(BluetoothError::Success));
        let first=radio.error().unwrap();
        ConnectionSession{handles:Mutex::new(None),observation:radio.clone()}.retire_with_cause("later cleanup failure");
        assert_eq!(radio.error().as_deref(),Some(first.as_str()));
    }
    #[tokio::test]
    async fn session_loss_owner_release_and_old_callbacks_cannot_poison_new_session() {
        let old=SessionObservation::new();
        let fresh=SessionObservation::new();
        old.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        old.close_owner();
        let released=old.error().unwrap();
        old.observe(ADDRESS,Some(GattSessionStatus::Closed),Some(BluetoothError::Success));
        assert_eq!(old.error().as_deref(),Some(released.as_str()));
        fresh.observe(ADDRESS,Some(GattSessionStatus::Active),None);
        assert_eq!(fresh.guard(async {Ok(9)}).await.unwrap(),9);
        let failed=SessionObservation::new();
        failed.observe(ADDRESS,None,Some(BluetoothError::OtherError));
        assert!(failed.guard(async {Ok(0)}).await.is_err(),"explicit native errors also terminate an unready session");
    }
}
