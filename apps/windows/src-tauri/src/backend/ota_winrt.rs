//! Companion OTA v1 host path: **WinRT dual-lane WWR** via platform
//! `denzic-ble-windows` — same shape as Listener 1.0.3, not btleplug threads.
//!
//! Copied from Listener-Type `windows_ble` dual-lane pipeline:
//! - `start_gatt_write_with_option_async` + dual pending queues
//! - joint drain of DATA + DATA_B
//! - `TransferOptions::dual_lane_bulk` window=400, inactive cold=64
//! - pipeline depth 32 (~16/lane)
//!
//! WBA signed and legacy WB updates use their actual MTU and distinct attribute
//! limits. Link readiness precedes manifest and bulk writes.

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
    GattSession, GattSessionStatus, GattWriteOption, GattOpenStatus, GattSharingMode,
};
use windows::Devices::Bluetooth::{
    BluetoothAddressType, BluetoothCacheMode, BluetoothLEDevice, BluetoothLEPreferredConnectionParameters,
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

/// Legacy WB budget. WBA uses its authenticated device-advertised window,
/// one data lane and Denzic's authoritative bytes_written recovery.
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
    // Rust drops fields in declaration order. Retire the temporary preference
    // and session ownership before closing our service/device. Characteristics
    // may still have COM references; explicit Close retires this owner anyway.
    _conn_pref_request: Option<denzic_ble_windows::ScopedBleResource<BluetoothLEPreferredConnectionParametersRequest>>,
    _session: Option<denzic_ble_windows::ScopedBleResource<GattSession>>,
    _service: denzic_ble_windows::ScopedBleResource<GattDeviceService>,
    _device: Option<denzic_ble_windows::ScopedBleResource<BluetoothLEDevice>>,
    device_id: String,
    control: GattCharacteristic,
    data: GattCharacteristic,
    data_b: Option<GattCharacteristic>,
    status: GattCharacteristic,
    data_write_option: GattWriteOption,
}

struct CompanionOtaWinrtTransport<'a> {
    target: &'a OpenOtaTarget,
    pending_wwr: Vec<IAsyncOperation<GattCommunicationStatus>>,
    pending_wwr_b: Vec<IAsyncOperation<GattCommunicationStatus>>,
    status_error_started: Option<Instant>,
    wba_signed: bool,
    pipeline_depth: usize,
    system_component: Option<u8>,
    simple_file_bytes: Option<u32>,
}

impl Drop for CompanionOtaWinrtTransport<'_> {
    fn drop(&mut self) {
        // Failure may leave asynchronous writes owned by either lane. Retire
        // them before the target's session/service close. On normal completion
        // both queues are already empty; this adds no transfer pacing/wait.
        self.cancel_pending_wwr();
    }
}

pub fn transfer_companion_ota_winrt(
    requested_device_id: Option<&str>,
    firmware: &[u8],
    chunk_bytes: u16,
    wba_manifest: Option<&[u8; 144]>,
) -> Result<CompanionOtaBleReport, String> {
    // Connection-params request is held on `target` for the whole transfer.
    let mut target = open_ota_target(requested_device_id)?;
    let actual_mtu = wait_ota_mtu(&target, wba_manifest.is_some())?;
    let wba_flow=if wba_manifest.is_some() {
        // The public readiness value may still be the boot snapshot while a
        // lost bond is being replaced. Complete one protected read first: this
        // makes Windows establish encryption without sending an OTA command or
        // payload. MTU negotiation alone does not establish authentication.
        let capability=read_characteristic_bytes_with_timeout(&target.status,BluetoothCacheMode::Uncached,
            "WBA OTA packet capability",STATUS_READ_TIMEOUT,&BleCancel::NONE)?;
        check_wba_readiness(&target)?;
        let supports_wwr=target.data.CharacteristicProperties()
            .map_err(|e|format!("WBA OTA DATA properties: {e}"))?
            .contains(GattCharacteristicProperties::WriteWithoutResponse);
        let flow=super::ota_flow::WbaFlow::from_status(&capability,supports_wwr)?;
        target.data_write_option=if flow.pipelined {GattWriteOption::WriteWithoutResponse}
            else {GattWriteOption::WriteWithResponse};
        Some(flow)
    } else {None};
    let board_limit=wba_flow.map(|flow|flow.payload_bytes).unwrap_or(244);
    // Package validation emits240; the generic transport default is244.
    // Grow either only through the explicit, parsed WBA capacity. The actual
    // MTU and board limit below remain authoritative; WB stays unchanged.
    let requested=wba_flow.map(|flow|flow.preferred_payload(chunk_bytes)).unwrap_or(chunk_bytes);
    let chunk_bytes = ota_payload_for_mtu(requested, actual_mtu, wba_manifest.is_some(),board_limit)?;
    eprintln!("[companion-ota] actual_att_mtu={actual_mtu} selected_file_payload={chunk_bytes}");
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
                if Instant::now()>=deadline {
                    // A recording/power condition may have changed since the
                    // preflight. Read its current device reason once, never a
                    // cached snapshot or our own unverified manifest write.
                    if let Ok(current) = read_wba_readiness(&target) {
                        if let Some(reason) = current.blocker_message() { return Err(reason); }
                    }
                    return Err("设备未接受签名升级包，请核对签名、板型和版本；尚未发送固件内容。".into());
                }
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
    eprintln!("[companion-ota] host=WinRT/denzic-ble-windows target={} data_write={:?} dual_available={}",
        if wba_manifest.is_some() { "WBA_signed" } else { "WB_legacy" },
        target.data_write_option, target.data_b.is_some());

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
                target._conn_pref_request = Some(denzic_ble_windows::ScopedBleResource::new(req));
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

    let pipeline = wba_flow.map(|flow|flow.pipeline_depth()).unwrap_or(WWR_PIPELINE_DEPTH);
    eprintln!(
        "[companion-ota] data_write={:?} pipeline_depth={} per_lane={} dual={}",
        target.data_write_option,
        pipeline,
        if wba_manifest.is_some() { pipeline } else { (pipeline + 1) / 2 },
        target.data_b.is_some()
    );

    let mut options = denzic_ota_core::TransferOptions::dual_lane_bulk(chunk_bytes);
    options.chunk_payload_bytes = chunk_bytes;
    options.window_chunks = wba_flow.map(|flow|flow.window_chunks).unwrap_or(WINDOW_CHUNKS);
    options.inactive_link_window_chunks = Some(wba_flow.map(|flow|flow.window_chunks).unwrap_or(INACTIVE_LINK_WINDOW_CHUNKS));
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
        pipeline_depth: pipeline,
        system_component: None,
        simple_file_bytes: None,
    };

    let progress_started = Instant::now();
    let mut payload_window = super::ota_metrics::PayloadWindow::default();
    let report = denzic_ota_core::transfer(&mut transport, firmware, options, |accepted, total| {
        payload_window.observe(accepted, total, progress_started.elapsed());
    })
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
    let payload_metrics = payload_window.finish(&report,wba_manifest.is_some());
    let new_bytes = report.firmware_bytes.saturating_sub(report.resumed_bytes);
    let bulk_kb_s = payload_metrics.actual_payload_kib_s
        .map(|rate| format!("{rate:.2}")).unwrap_or_else(|| "not_measured".into());
    // Sum of API call durations is a diagnostic, never the speed gate.
    let transport_kb_s = (new_bytes as f64 / 1024.0) / transport_ms;
    eprintln!("firmware_ota_payload_metrics {}",serde_json::to_string(&payload_metrics).map_err(|e|e.to_string())?);
    eprintln!(
        "[companion-ota] bulk_kb_s={} transport_call_only_kib_s={:.1} bytes={} data_writes={} status_reads={} dual={} active_link={} recovered_offsets={} elapsed_ms={:.0} transport_ms={:.0}",
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
        "firmware_ota_report bulk_kb_s={} protocol_ms={:.0} wall_ms={:.0} bytes={} data_writes={} target={} actual_att_mtu={} file_payload={} data_write={:?} dual={}",
        bulk_kb_s,
        total_ms * 1000.0,
        total_ms * 1000.0,
        report.firmware_bytes,
        report.data_writes,
        if wba_manifest.is_some() { "WBA_signed" } else { "WB_legacy" },
        actual_mtu, chunk_bytes, target.data_write_option, options.prefer_dual_lane && target.data_b.is_some()
    );

    Ok(CompanionOtaBleReport {
        device_id: target.device_id.clone(),
        transfer: report,
        payload_metrics,
        system_bundle: None,
    })
}

/// Read-only native preflight for the existing single-file OTA path. Uses the
/// same protected status and readiness reads; never BEGIN/ABORT/DATA/FINISH.
pub(crate) fn inspect_system_ota_winrt(device_id:&str)->Result<serde_json::Value,String> {
    let address=parse_ble_address(device_id)?;
    let target=open_ota_target_for_address(address,&format_ble_address(address))?;
    let bytes=read_simple_protected_status(&target)?;
    let status=denzic_ota_core::parse_status(&bytes)?;
    let props=target.data.CharacteristicProperties().map_err(|e|e.to_string())?;
    let flow=super::ota_flow::WbaFlow::from_simple_status(&bytes,props.contains(GattCharacteristicProperties::WriteWithoutResponse))?;
    let readiness=read_wba_readiness(&target)?;
    let sharing=target._service.SharingMode().map_err(|e|e.to_string())?;
    Ok(serde_json::json!({"result":"OTA_PROTECTED_READ_ONLY_INSPECTION_COMPLETE","deviceId":target.device_id,
        "state":status.state,"lastError":status.last_error,"bytesWritten":status.bytes_written,"expectedBytes":status.expected_size,
        "readinessBlockers":readiness.blockers,"payloadCapacity":flow.payload_bytes,"windowChunks":flow.window_chunks,
        "sharingMode":sharing.0,"controlWrites":0,"firmwareBytesSent":0,"downloadStarted":false,"fullChainAcceptance":"NOT_QUALIFIED"}))
}

pub(super) fn transfer_system_ota_winrt(requested_device_id:Option<&str>,package:&super::system_ota::Package)->Result<CompanionOtaBleReport,String> {
    let transport_profile=super::ota_flow::SimpleTransportProfile::from_env()?;
    let started=Instant::now();let mut target=open_ota_target(requested_device_id)?;
    // Protected capability read establishes encryption before public readiness.
    let bytes=read_simple_protected_status(&target)?;
    let preflight=denzic_ota_core::parse_status(&bytes)?;
    eprintln!("[companion-ota] preflight_receive state={} accepted={} expected={} error={}",preflight.state,preflight.bytes_written,preflight.expected_size,preflight.last_error);
    check_wba_readiness(&target)?;
    let props=target.data.CharacteristicProperties().map_err(|e|e.to_string())?;
    let flow=super::ota_flow::WbaFlow::from_simple_status(&bytes,props.contains(GattCharacteristicProperties::WriteWithoutResponse))?;
    let pipelined=transport_profile.pipelined(flow)?;
    let identity=open_read_char(&target._service,GUID::from_u128(super::firmware_ota::WBA_MANIFEST_UUID_U128),"当前升级版本")?;
    let current=read_characteristic_bytes_with_timeout(&identity,BluetoothCacheMode::Uncached,"当前升级版本",STATUS_READ_TIMEOUT,&BleCancel::NONE)?;
    package.admit(&current)?;drop(identity);
    let mtu=wait_ota_mtu(&target,false)?;
    // First CE release uses one acknowledged <=244-byte ATT value. The
    // observed509-byte burst did not advance offset0; throughput work remains
    // deferred, rather than making fragmented WWR a prerequisite for OTA.
    target.data_write_option=if pipelined {GattWriteOption::WriteWithoutResponse}
        else {GattWriteOption::WriteWithResponse};
    let connection_preference=if pipelined {"ThroughputOptimized"} else {"Balanced"};
    if let Some(device)=target._device.as_ref() {
        if pipelined {
            // R69's same-size WWR capture: Windows rejected the peripheral's
            // CI6 request and applied its Balanced CI48 for the whole239s
            // download. CI6 became effective only after that request was
            // released. Own a bulk preference for the actual payload phase;
            // the existing success/drop paths release it on every exit.
            target._conn_pref_request=Some(denzic_ble_windows::ScopedBleResource::new(
                apply_throughput_optimized(device)
                    .map_err(|e|format!("增强OTA连接参数请求失败；尚未下载升级包：{e}"))?));
        } else if let Ok(p)=BluetoothLEPreferredConnectionParameters::Balanced() {
            if let Ok(r)=device.RequestPreferredConnectionParameters(&p) {target._conn_pref_request=Some(denzic_ble_windows::ScopedBleResource::new(r));}
        }
    }
    let peer_handoff=transport_profile.releases_after_first_durable_window();
    let release_scope=if peer_handoff {"first_durable_window_or_owner_drop"}
        else {"payload_complete_or_owner_drop"};
    eprintln!("[companion-ota] simple_connection_preference requested={connection_preference} applied_not_guaranteed=1 release={release_scope}");
    // Signature travels inside the file. Only DATA geometry is relevant;
    // do not inherit WB's244 cap or the former separate-manifest147 minimum.
    let payload=transport_profile.file_payload(flow,mtu)?;
    let mut options=denzic_ota_core::TransferOptions::dual_lane_bulk(payload);
    // Logical durable checkpoints can span multiple bounded RAM-ring turns.
    // WinRT outstanding operations remain limited by the advertised queue;
    // neither local completion nor RAM admission is a NOR receipt.
    options.window_chunks=flow.window_chunks;options.inactive_link_window_chunks=Some(flow.window_chunks);options.prefer_dual_lane=false;
    let pipeline=if pipelined {flow.pipeline_depth()} else {1};
    eprintln!("[companion-ota] simple_file att_mtu={mtu} file_payload={payload} acknowledged_window={} download_resume=0 transport_profile={} pipeline_depth={pipeline} data_write={:?} diagnostic={}",
        flow.window_chunks,transport_profile.name(),target.data_write_option,u8::from(pipelined));
    eprintln!("[companion-ota] simple_window_barrier={} storage_receipt_required=1",
        if pipelined { "encrypted_status_after_bounded_queue_drains" } else { "sync_write_then_status" });
    // Move the selected diagnostic preference into this operation before any
    // later failure. Early errors still close it; the original profile keeps
    // its R71 lifetime. No replacement Windows preference is requested.
    let mut handoff_preference=if peer_handoff {target._conn_pref_request.take()} else {None};
    let mut handoff_release:Option<Result<(),String>>=None;
    let mut handoff_offset:Option<usize>=None;
    let first_window=usize::from(payload)*usize::from(flow.window_chunks);
    let mut transport=CompanionOtaWinrtTransport{target:&target,pending_wwr:Vec::with_capacity(pipeline),pending_wwr_b:Vec::new(),
        status_error_started:None,wba_signed:true,pipeline_depth:pipeline,system_component:None,
        simple_file_bytes:Some(u32::try_from(package.file.len()).map_err(|_|"完整升级文件过大")?)};
    super::simple_ota_restart::prepare_fresh_download(&mut transport,&bytes,
        ||read_wba_readiness(&target).map(|r|r.blockers))?;
    let mut window=super::ota_metrics::PayloadWindow::default();
    let mut progress_bucket=usize::MAX;
    let mut report=denzic_ota_core::transfer(&mut transport,&package.file,options,|accepted,total|{
        window.observe(accepted,total,started.elapsed());
        if transport_profile.handoff_ready(accepted,total,first_window) {
            if let Some(mut request)=handoff_preference.take() {
                let result=request.close();
                let interval=target._device.as_ref().and_then(|d|d.GetConnectionParameters().ok())
                    .and_then(|p|p.ConnectionInterval().ok());
                eprintln!("[companion-ota] preference_peer_handoff accepted={accepted} total={total} first_window={first_window} close_ok={} interval_units={interval:?} applied_fast_interval_not_assumed=1 replacement_preference=none at_epoch_us={} error={:?}",
                    u8::from(result.is_ok()),chrono::Utc::now().timestamp_micros(),result.as_ref().err());
                handoff_offset=Some(accepted);handoff_release=Some(result);
            }
        }
        let bucket=accepted/(64*1024);
        if bucket!=progress_bucket||accepted==total {
            eprintln!("[companion-ota] payload_progress accepted={accepted} total={total}");
            progress_bucket=bucket;
        }
    }).map_err(|e|format!("完整升级包传输未完成；断开后请从头重新下载：{e}"))?;
    if report.resumed_bytes!=0 {return Err("单文件升级意外返回了非零起点，不能当作本次完整传输".into());}
    let mut payload_metrics=window.finish(&report,true);
    payload_metrics.exclude_package_header(176);
    drop(transport);drop(handoff_preference);drop(target._conn_pref_request.take());
    let device_id=target.device_id.clone();let mut connection=Some(target);
    // FINISH only retained the file. Boot verifies the signature before erase,
    // installs both destinations, then normal App reports actual running IDs.
    let deadline=Instant::now()+Duration::from_secs(180);let mut last_error=String::new();
    loop {
        if Instant::now()>=deadline {return Err(format!("完整包已传入，但尚未看到新程序和资源正常启动；没有判升级成功。最后状态：{last_error}"));}
        if connection.is_none() {
            match open_ota_target(Some(&device_id)) {Ok(t)=>connection=Some(t),Err(e)=>{last_error=e;std::thread::sleep(Duration::from_millis(500));continue;}}
        }
        let t=connection.as_ref().unwrap();
        let result=open_read_char(&t._service,GUID::from_u128(super::firmware_ota::WBA_MANIFEST_UUID_U128),"升级后实际版本")
            .and_then(|c|read_characteristic_bytes_with_timeout(&c,BluetoothCacheMode::Uncached,"升级后实际版本",STATUS_READ_TIMEOUT,&BleCancel::NONE));
        match result {
            Ok(r) if package.installed(&r)=>break,
            Ok(_)=>std::thread::sleep(Duration::from_millis(200)),
            Err(e)=>{last_error=e;drop(connection.take());std::thread::sleep(Duration::from_millis(500));},
        }
    }
    report.timings.total=started.elapsed();
    let system_bundle=Some(serde_json::json!({"bundleId":package.id,"jointConfirmed":true,"temporarySpaceReleased":true,
        "receipt":"WSI3-running-version-and-signed-payload-sha","firmwareBytes":package.firmware_bytes,"resourceBytes":package.resource_bytes,
        "downloadResume":false,"installationElapsedMs":started.elapsed().as_millis(),
        "transportProfile":transport_profile.name(),"actualAttMtu":mtu,
        "filePayloadBytes":payload,"pipelineDepth":pipeline,"physicalQueueChunks":flow.queue_chunks,
        "durableWindowChunks":flow.window_chunks,"pipelined":pipelined,
        "windowBarrier":if pipelined {"encrypted_status_after_bounded_queue_drains"} else {"sync_write_then_status"},
        "connectionPreference":connection_preference,
        "connectionPreferenceRelease":release_scope,
        "connectionPreferenceHandoffOffset":handoff_offset,
        "connectionPreferenceHandoffCloseSucceeded":handoff_release.as_ref().map(|r|r.is_ok())}));
    Ok(CompanionOtaBleReport{device_id,transfer:report,payload_metrics,system_bundle})
}

fn read_simple_protected_status(target:&OpenOtaTarget)->Result<Vec<u8>,String> {
    let deadline=Instant::now()+Duration::from_secs(15);
    loop {
        let op=target.status.ReadValueWithCacheModeAsync(BluetoothCacheMode::Uncached)
            .map_err(|e|format!("升级加密状态读取失败：{e}"))?;
        let read=wait_async_operation_with_cancel(op,STATUS_READ_TIMEOUT,"升级加密状态",&BleCancel::NONE)?;
        let status=read.Status().map_err(|e|e.to_string())?;
        if status==GattCommunicationStatus::Success {
            return denzic_ble_windows::buffer_to_vec(&read.Value().map_err(|e|e.to_string())?).map_err(|e|e.to_string());
        }
        let protocol=read.ProtocolError().ok().and_then(|v|v.Value().ok());
        // Only SMP's transient insufficient authentication/encryption may
        // wait on this SAME connection. Access denial/other errors fail closed.
        if status!=GattCommunicationStatus::ProtocolError||!matches!(protocol,Some(0x05|0x0f))||Instant::now()>=deadline {
            return Err(format!("升级加密未完成：status={status:?} ATT={protocol:?}；未发送升级内容"));
        }
        std::thread::sleep(Duration::from_millis(200));
    }
}

fn check_wba_readiness(target:&OpenOtaTarget)->Result<(),String> {
    let readiness=read_wba_readiness(target)?;
    eprintln!("[companion-ota] device_preflight blockers={} battery_percent={:?} minimum_required_mv={} authenticated_status_read_complete=1 signed_manifest_still_required=1",
        readiness.blockers,readiness.battery_percent,readiness.minimum_required_mv);
    readiness.check_preflight()
}
fn read_wba_readiness(target: &OpenOtaTarget) -> Result<super::ota_readiness::Readiness, String> {
    let device = target._device.as_ref().ok_or("无法确认设备升级条件：缺少本次设备连接，尚未发送固件。")?;
    let cancel = BleCancel::NONE;
    let op = device.GetGattServicesForUuidWithCacheModeAsync(
        GUID::from_u128(super::ota_readiness::SERVICE_UUID), BluetoothCacheMode::Uncached)
        .map_err(|e| format!("读取设备升级条件失败，尚未发送固件：{e}"))?;
    let result = wait_async_operation_with_cancel(op, DISCOVERY_TIMEOUT, "WBA upgrade readiness service", &cancel)?;
    if result.Status().map_err(|e| e.to_string())? != GattCommunicationStatus::Success {
        return Err("无法读取设备升级条件，尚未发送固件。".into());
    }
    let services = result.Services().map_err(|e| e.to_string())?;
    // These services belong only to this read. Close them on every exit; the
    // device/session and the OTA service continue to belong to target.
    let mut owned = Vec::new();
    for i in 0..services.Size().map_err(|e| e.to_string())? {
        owned.push(denzic_ble_windows::ScopedBleResource::new(services.GetAt(i).map_err(|e| e.to_string())?));
    }
    if owned.len() != 1 { return Err("无法确认唯一的设备升级状态服务，尚未发送固件。".into()); }
    let characteristic = open_read_char(&owned[0],
        GUID::from_u128(super::ota_readiness::CHARACTERISTIC_UUID), "WBA upgrade readiness")?;
    let bytes = read_characteristic_bytes_with_timeout(&characteristic, BluetoothCacheMode::Uncached,
        "WBA upgrade readiness", STATUS_READ_TIMEOUT, &cancel)?;
    super::ota_readiness::Readiness::parse(&bytes)
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
    // Pairing owns/closes a temporary WinRT device. Complete that lifetime
    // before opening the device/session that will own OTA discovery and I/O.
    let address_type = {
        let probe = denzic_ble_windows::ScopedBleResource::new(
            open_ble_device_with_timeout(address, DISCOVERY_TIMEOUT, false, &cancel)?);
        probe.BluetoothAddressType().map_err(|e| format!("OTA address type: {e}"))?
    };
    super::ble_pairing::ensure_paired_for_ota(address,address_type)?;
    let device = denzic_ble_windows::ScopedBleResource::new(
        open_ble_device_with_timeout(address, DISCOVERY_TIMEOUT,
            address_type==BluetoothAddressType::Random, &cancel)?);
    if device.BluetoothAddress().map_err(|e|e.to_string())?!=address
        || device.BluetoothAddressType().map_err(|e|e.to_string())?!=address_type {
        return Err("OTA reopened device identity changed; no firmware sent".into());
    }
    let id=device.BluetoothDeviceId().map_err(|e|format!("OTA session identity: {e}"))?;
    let operation=GattSession::FromDeviceIdAsync(&id).map_err(|e|format!("OTA session open: {e}"))?;
    let session=denzic_ble_windows::ScopedBleResource::new(
        wait_async_operation_with_cancel(operation,DISCOVERY_TIMEOUT,"OTA connection session",&cancel)?);
    activate_gatt_session(&session)?;
    // Always label with the radio address from the open handle (not service-id UUID crumbs).
    let label = device
        .BluetoothAddress()
        .ok()
        .map(format_ble_address)
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| device_id_label.to_string());
    let discovery_started=Instant::now();
    let mut discovery_attempt=0u8;
    let services_result=loop {
        let remaining=DISCOVERY_TIMEOUT.saturating_sub(discovery_started.elapsed());
        if remaining.is_zero() {return Err("OTA initial service discovery exceeded12seconds; no firmware sent".into());}
        let services_op=device.GetGattServicesForUuidWithCacheModeAsync(OTA_SERVICE_UUID,BluetoothCacheMode::Uncached)
            .map_err(|e|format!("OTA GetGattServices failed: {e}"))?;
        let result=wait_async_operation_with_cancel(services_op,remaining,"OTA services",&cancel)?;
        let status=result.Status().map_err(|e|format!("OTA services status: {e}"))?;
        eprintln!("[companion-ota] initial_services attempt={} status={status:?} connection={:?} elapsed_ms={} same_device_session=1 package_writes=0 at_epoch_us={}",
            discovery_attempt+1,device.ConnectionStatus().ok(),discovery_started.elapsed().as_millis(),chrono::Utc::now().timestamp_micros());
        if status==GattCommunicationStatus::Success {break result;}
        let remaining=DISCOVERY_TIMEOUT.saturating_sub(discovery_started.elapsed());
        if !super::ota_flow::retry_initial_services(discovery_attempt,status.0,remaining.as_millis()) {
            return Err(format!("OTA services status={status:?}; attempts={} no firmware sent",discovery_attempt+1));
        }
        // Keep this maintained owner, release only the failed read result.
        // No second pairing, device close/reopen, BEGIN or adapter reset.
        drop(result);discovery_attempt+=1;
        std::thread::sleep(Duration::from_millis(500));
    };
    let services = services_result
        .Services()
        .map_err(|e| format!("OTA services list: {e}"))?;
    if services.Size().unwrap_or(0) == 0 {
        return Err("OTA service not present on device".to_string());
    }
    let service = services.GetAt(0).map_err(|e| format!("OTA service: {e}"))?;
    open_chars_from_service(service, Some(device), &label, Some(session))
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
    open_chars_from_service(service, None, device_id_label, None)
}

fn require_shared_open(status:GattOpenStatus,mode:GattSharingMode)->Result<(),String> {
    if matches!(status,GattOpenStatus::Success|GattOpenStatus::AlreadyOpened) && mode==GattSharingMode::SharedReadAndWrite {return Ok(());}
    Err(format!("OTA shared service open failed: status={status:?} sharing={mode:?}; no exclusive fallback or upgrade bytes sent"))
}

fn ensure_shared_service(service:&GattDeviceService,cancel:&BleCancel)->Result<(),String> {
    let before=service.SharingMode().map_err(|e|format!("OTA service sharing state: {e}"))?;
    if before==GattSharingMode::SharedReadAndWrite {return Ok(());}
    let op=service.RequestAccessAsync().map_err(|e|format!("OTA service access request: {e}"))?;
    let access=wait_async_operation_with_cancel(op,DISCOVERY_TIMEOUT,"OTA service access",cancel)?;
    if access!=DeviceAccessStatus::Allowed {return Err(format!("OTA service access not granted: {access:?}; no upgrade bytes sent"));}
    let op=service.OpenAsync(GattSharingMode::SharedReadAndWrite).map_err(|e|format!("OTA shared service open: {e}"))?;
    let opened=wait_async_operation_with_cancel(op,DISCOVERY_TIMEOUT,"OTA shared service open",cancel)?;
    let after=service.SharingMode().map_err(|e|format!("OTA opened service sharing state: {e}"))?;
    eprintln!("[companion-ota] shared_service_open access={access:?} before={before:?} opened={opened:?} after={after:?}");
    require_shared_open(opened,after)
}

fn open_chars_from_service(
    service: GattDeviceService,
    device: Option<denzic_ble_windows::ScopedBleResource<BluetoothLEDevice>>,
    device_id_label: &str,
    owned_session: Option<denzic_ble_windows::ScopedBleResource<GattSession>>,
) -> Result<OpenOtaTarget, String> {
    // Acquire ownership before access/characteristic checks can return early.
    // Device first, then service/session: early local exits also close in the
    // reverse order, while final target fields define their explicit order.
    let device = device.or_else(|| reopen_device_from_service(&service)
        .map(denzic_ble_windows::ScopedBleResource::new));
    let service = denzic_ble_windows::ScopedBleResource::new(service);
    let cancel = BleCancel::NONE;
    ensure_shared_service(&service,&cancel)?;
    // Prefer an explicit device handle; otherwise reopen from the service DeviceId
    // so ThroughputOptimized can be held for the transfer lifetime.
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
    let session = match owned_session {Some(session)=>Some(session),None=>prepare_gatt_session(&service)?};
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

fn prepare_gatt_session(service: &GattDeviceService) -> Result<Option<denzic_ble_windows::ScopedBleResource<GattSession>>, String> {
    let session = match service.Session() {
        Ok(s) => denzic_ble_windows::ScopedBleResource::new(s),
        Err(_) => return Ok(None),
    };
    activate_gatt_session(&session)?;
    Ok(Some(session))
}

fn activate_gatt_session(session: &GattSession) -> Result<(), String> {
    if !session.CanMaintainConnection().map_err(|e|format!("OTA maintain capability: {e}"))? {
        return Err("Windows cannot maintain this OTA connection; no firmware sent".into());
    }
    // Request before waiting. An idle Windows session need not become Active
    // while nobody owns a connection request; the old code waited first.
    session.SetMaintainConnection(true).map_err(|e|format!("OTA maintain connection: {e}"))?;
    let started=Instant::now();
    eprintln!("OTA connection_session maintain_requested=1 requested_before_wait=1 owner=ota");
    let deadline = started + GATT_READY_TIMEOUT;
    while Instant::now() < deadline {
        if let Ok(status) = session.SessionStatus() {
            if status == GattSessionStatus::Active {
                eprintln!("OTA connection_session active=1 elapsed_ms={}",started.elapsed().as_millis());
                return Ok(());
            }
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    Err("OTA connection session did not become active within its bounded wait; no firmware sent".into())
}

fn wb_sync_settle(wba_signed: bool, option: GattWriteOption, is_sync: bool) -> bool {
    !wba_signed && option == GattWriteOption::WriteWithoutResponse && is_sync
}

fn wait_ota_mtu(target: &OpenOtaTarget, wba_signed: bool) -> Result<u16, String> {
    let session = target._session.as_ref()
        .ok_or("Cannot obtain this connection's ATT MTU; OTA has not started")?;
    let started = Instant::now();
    let minimum = if wba_signed { super::ble_mtu::SIGNED_OTA_MIN_MTU } else { 24 };
    let wait = super::ble_mtu::MtuWait::new("OTA", minimum, GATT_READY_TIMEOUT);
    loop {
        let mtu = session.MaxPduSize().map_err(|e| format!("OTA actual ATT MTU: {e}"))?;
        if let Some(mtu) = wait.observe(mtu, started.elapsed())? { return Ok(mtu); }
        std::thread::sleep(Duration::from_millis(50).min(GATT_READY_TIMEOUT.saturating_sub(started.elapsed())));
    }
}

#[cfg(test)]
fn wba_payload_capability(status:&[u8])->Result<u16,String> {
    super::ota_flow::WbaFlow::from_status(status,false).map(|flow|flow.payload_bytes)
}
fn ota_payload_for_mtu(requested: u16, mtu: u16, wba_signed: bool, board_limit:u16) -> Result<u16, String> {
    // Bound real writes by peer capability and actual ATT MTU. WBA assembles
    // SDK HCI fragments before durable DOV1 acknowledgement; no prepared write
    // is needed because a value never exceeds the negotiated MTU minus3.
    if requested == 0 || mtu <= 23 || (wba_signed && mtu < 147) {
        return Err(format!("ATT MTU {mtu} cannot carry this OTA protocol; no manifest or payload was sent"));
    }
    let board_limit=if wba_signed {board_limit.min(505)} else {244};
    Ok(requested.min(mtu.saturating_sub(7)).min(board_limit))
}

#[cfg(test)]
mod mtu_tests {
    use super::{ota_payload_for_mtu, wba_payload_capability, wb_sync_settle, GattWriteOption};

    #[test]
    fn large_ota_requires_peer_capability_and_actual_mtu() {
        let mut s=vec![0u8;24];s[..4].copy_from_slice(b"DOV1");s[4]=1;
        assert_eq!(wba_payload_capability(&s).unwrap(),240);
        s.extend_from_slice(b"WOC1");s.extend_from_slice(&505u16.to_le_bytes());s.extend_from_slice(&509u16.to_le_bytes());
        assert_eq!(wba_payload_capability(&s).unwrap(),505);
        assert_eq!(ota_payload_for_mtu(505,512,true,505).unwrap(),505);
        assert_eq!(ota_payload_for_mtu(505,251,true,505).unwrap(),244);
        assert_eq!(ota_payload_for_mtu(505,512,true,240).unwrap(),240);
        s[31]=0;assert!(wba_payload_capability(&s).is_err());
    }
    #[test]
    fn wba_window_does_not_inherit_the_wb_wwr_delay() {
        assert!(!wb_sync_settle(true, GattWriteOption::WriteWithResponse, true));
        assert!(!wb_sync_settle(true, GattWriteOption::WriteWithoutResponse, true));
        assert!(!wb_sync_settle(false, GattWriteOption::WriteWithResponse, true));
        assert!(!wb_sync_settle(false, GattWriteOption::WriteWithoutResponse, false));
        assert!(wb_sync_settle(false, GattWriteOption::WriteWithoutResponse, true));
    }

    #[test]
    fn uses_actual_mtu_and_wba_attribute_limit() {
        assert_eq!(ota_payload_for_mtu(244, 517, true, 240).unwrap(), 240);
        assert_eq!(ota_payload_for_mtu(244, 251, true, 240).unwrap(), 240);
        assert_eq!(ota_payload_for_mtu(244, 185, true, 240).unwrap(), 178);
        assert_eq!(ota_payload_for_mtu(100, 185, true, 240).unwrap(), 100);
        assert_eq!(ota_payload_for_mtu(244, 247, false, 244).unwrap(), 240);
        assert_eq!(ota_payload_for_mtu(244, 251, false, 244).unwrap(), 244);
    }

    #[test]
    fn refuses_unnegotiated_or_unrepresentable_manifest_before_writes() {
        assert!(ota_payload_for_mtu(244, 23, true, 240).is_err());
        assert!(ota_payload_for_mtu(244, 146, true, 240).is_err());
        assert!(ota_payload_for_mtu(0, 251, true, 240).is_err());
        assert_eq!(ota_payload_for_mtu(244, 147, true, 240).unwrap(), 140);
    }
}

fn open_write_char(
    service: &GattDeviceService,
    uuid: GUID,
    label: &str,
) -> Result<GattCharacteristic, String> {
    let cancel = BleCancel::NONE;
    ensure_shared_service(service,&cancel)?;
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
    ensure_shared_service(service,&cancel)?;
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
                            let result = operation.GetResults();
                            let _ = operation.Close();
                            let status = result
                                .map_err(|err| format!("BLE {label} write result failed: {err}"))?;
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
        let dual = !self.wba_signed && self.target.data_b.is_some();
        let depth_per_lane = if dual {
            (self.pipeline_depth + 1) / 2
        } else {
            self.pipeline_depth
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
            || total >= self.pipeline_depth
        {
            self.drain_pending_wwr_until(max_a, max_b)?;
        }
        Ok(())
    }
}

impl CompanionOtaWinrtTransport<'_> {
    fn write_simple_acknowledged_data(&mut self,packet:&[u8],file_bytes:u32)->Result<(),String> {
        for attempt in 0..2 {
            let error=match write_gatt_value_with_timeout(&self.target.data,packet,
                GattWriteOption::WriteWithResponse,OTA_WRITE_TIMEOUT,"Companion OTA data") {
                Ok(_)=>return Ok(()),Err(error)=>error,
            };
            if !super::simple_ota_restart::ambiguous_write_completion(&error) {return Err(error);}
            // No reconnect and no new BEGIN here. The one same-file packet
            // may have committed even though Windows lost its completion.
            let bytes=read_characteristic_bytes_with_timeout(&self.target.status,BluetoothCacheMode::Uncached,
                "升级写入超时后的设备收据",STATUS_READ_TIMEOUT,&BleCancel::NONE)
                .map_err(|e|format!("{error}；设备收据无法核对，未猜测完成或重连：{e}"))?;
            let receipt=denzic_ota_core::parse_status(&bytes)?;
            let offset=packet.get(..4).map(|b|u32::from_le_bytes(b.try_into().unwrap()));
            eprintln!("[companion-ota] data_completion_fault attempt={} packet_offset={offset:?} payload_bytes={} api_timeout=1 receipt_state={} receipt_error={} accepted={} expected={} no_reconnect=1",
                attempt+1,packet.len().saturating_sub(4),receipt.state,receipt.last_error,receipt.bytes_written,receipt.expected_size);
            match super::simple_ota_restart::acknowledged_write_receipt(packet,file_bytes,&bytes) {
                Ok(true)=>{
                    eprintln!("[companion-ota] data_completion_resolved exact_device_commit=1 stop_or_finish_fabricated=0");
                    return Ok(());
                },
                Ok(false) if attempt==0=>{
                    eprintln!("[companion-ota] data_completion_retry same_packet_same_offset=1 limit=1");
                },
                Ok(false)=>return Err(format!("{error}；相同数据仅重试一次后仍未写入，原文件状态保留。")),
                Err(e)=>return Err(format!("{error}；{e}")),
            }
        }
        unreachable!("bounded acknowledged data attempts return")
    }
}

impl denzic_ota_core::OtaV1Transport for CompanionOtaWinrtTransport<'_> {
    fn write_control(
        &mut self,
        packet: &[u8; denzic_ota_core::CONTROL_BYTES],
    ) -> Result<(), String> {
        let mut selected=*packet;
        if let Some(c)=self.system_component {selected[6]=c;selected[7]=0xB2;}
        let packet=&selected;
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
        if is_sync && self.wba_signed && self.simple_file_bytes.is_some()
            && self.target.data_write_option == GattWriteOption::WriteWithoutResponse {
            // Only the authenticated WOC2/simple-file window reaches here.
            // Its DATA callback writes NOR synchronously; DOV1 advances the
            // cursor only after that write succeeds. The GATT adapter publishes
            // that cursor only after its whole command queue drains. OP_SYNC
            // itself merely checks RECEIVING and performs no flush/checkpoint.
            // Keep the engine's exact status/catch-up/offset validation barrier,
            // but omit the extra ATT write/response before every status READ.
            // Local WWR completion above remains no storage acknowledgement.
            return Ok(());
        }
        // The old WB WWR path needed settling after draining the host queue.
        // WBA signed/acknowledged writes must use their device status instead
        // of inheriting this per-window fixed delay.
        if wb_sync_settle(self.wba_signed, self.target.data_write_option, is_sync) {
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
                    if self.wba_signed {
                        self.cancel_pending_wwr();
                        return Err(e);
                    }
                    if e.contains("stalled") {
                        return Err(e);
                    }
                    let _ = self.flush_pending_wwr();
                }
            }
        } else {
            self.flush_pending_wwr()?;
            if let Some(file_bytes)=self.simple_file_bytes {
                return self.write_simple_acknowledged_data(packet,file_bytes);
            }
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
                if let Some(component)=self.system_component {super::ota_flow::WbaFlow::check_component(&bytes,component)?;}
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

    fn window_drain_timeout(&self) -> Option<Duration> {
        (self.wba_signed && self.simple_file_bytes.is_some() &&
         self.target.data_write_option==GattWriteOption::WriteWithoutResponse)
            .then_some(Duration::from_secs(2))
    }

    fn write_finish(
        &mut self,
        packet: &[u8; denzic_ota_core::CONTROL_BYTES],
    ) -> Result<(), String> {
        let mut selected=*packet;
        if let Some(c)=self.system_component {selected[6]=c;selected[7]=0xB2;}
        let packet=&selected;
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

#[cfg(test)]
mod shared_open_tests {
    use super::*;
    #[test]
    fn ota_service_open_preserves_denial_and_requires_actual_shared_mode() {
        for status in [GattOpenStatus::Success,GattOpenStatus::AlreadyOpened] {
            assert!(require_shared_open(status,GattSharingMode::SharedReadAndWrite).is_ok());
            for mode in [GattSharingMode::Exclusive,GattSharingMode::SharedReadOnly,GattSharingMode::Unspecified] {
                assert!(require_shared_open(status,mode).is_err());
            }
        }
        for status in [GattOpenStatus::SharingViolation,GattOpenStatus::AccessDenied,GattOpenStatus::NotFound,GattOpenStatus::Unspecified,GattOpenStatus(77)] {
            assert!(require_shared_open(status,GattSharingMode::SharedReadAndWrite).unwrap_err().contains("no exclusive fallback or upgrade bytes sent"));
        }
    }
}
