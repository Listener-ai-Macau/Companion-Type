//! Companion coordinator.
//!
//! Single owner of the Companion host workflow. The current backend is a
//! deterministic fixture, but the public methods are the same surface the real
//! BLE/audio/ASR backend will implement.

use std::sync::{
    atomic::{AtomicU8, Ordering},
    Arc,
};

use crate::backend::{
    BoardOnlineLiveReport, CompanionBackend, CompanionBackendCapabilities,
    CompanionBleBridgeStatus, CompanionFirmwareOtaReport, CompanionFirmwareOtaRequest,
    CompanionOtaPackageValidation, FixtureCompanionBackend,
};
use crate::companion_v1::{CompanionV1ControlRequest, CompanionV1Snapshot};
use crate::backend::diagnostics::{Operation, Span};

pub struct CompanionCoordinator {
    backend: Arc<dyn CompanionBackend>,
    device_operation: Arc<AtomicU8>,
}

pub struct CompanionDeviceOperationLease {
    gate: Arc<AtomicU8>,
    kind: u8,
}

impl Drop for CompanionDeviceOperationLease {
    fn drop(&mut self) {
        let _ = self
            .gate
            .compare_exchange(self.kind, 0, Ordering::AcqRel, Ordering::Acquire);
    }
}

fn operation_name(kind: u8) -> &'static str {
    match kind {
        1 => "device control",
        2 => "board recording/transfer",
        3 => "firmware OTA",
        4 => "automatic reconnect",
        5 => "device diagnostics",
        6 => "audio component preparation",
        7 => "service connection test",
        8 => "original audio export",
        9 => "confirmed device recording discard",
        10 => "service settings save",
        11 => "desktop software update",
        12 => "recording bookmark observation",
        _ => "unknown device operation",
    }
}

fn snapshot_has_active_recording(snapshot: &CompanionV1Snapshot) -> bool {
    snapshot.meeting.active
        || snapshot
            .host
            .sessions
            .iter()
            .any(|session| session.status == "recording")
}

/// Only an owned, ordinary board recording can change its desktop link while
/// the microphone keeps running. The operation lease still excludes transfers.
fn owned_offline_recording_link(snapshot: &CompanionV1Snapshot, request: &CompanionV1ControlRequest) -> bool {
    crate::backend::owned_offline_recording_link(snapshot, request).is_some()
}

fn device_recording_blocks_control(
    snapshot: &CompanionV1Snapshot,
    action: crate::companion_v1::CompanionV1ControlAction,
) -> bool {
    snapshot.device.recording
        && matches!(
            action,
            crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings
                | crate::companion_v1::CompanionV1ControlAction::OobeRunChecks
                | crate::companion_v1::CompanionV1ControlAction::SpeakerPrompt
                | crate::companion_v1::CompanionV1ControlAction::SpeakerStop
        )
}

impl CompanionCoordinator {
    pub fn begin_desktop_update_operation(&self) -> Result<CompanionDeviceOperationLease,String> {
        let lease=self.begin_device_operation_kind(11)?;
        let snapshot=self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording || snapshot.host.persistence.status!="ready" {
            return Err("请结束录音并安全保存会议，再更新软件。".into());
        }
        Ok(lease)
    }
    pub fn new_fixture() -> Self {
        Self {
            backend: Arc::new(FixtureCompanionBackend::new()),
            device_operation: Arc::new(AtomicU8::new(0)),
        }
    }

    fn begin_device_operation_kind(
        &self,
        kind: u8,
    ) -> Result<CompanionDeviceOperationLease, String> {
        self.device_operation
            .compare_exchange(0, kind, Ordering::AcqRel, Ordering::Acquire)
            .map_err(|active| {
                format!(
                    "device is busy with {}; {} cannot start",
                    operation_name(active),
                    operation_name(kind)
                )
            })?;
        Ok(CompanionDeviceOperationLease {
            gate: Arc::clone(&self.device_operation),
            kind,
        })
    }

    pub fn begin_board_recording_operation(
        &self,
    ) -> Result<CompanionDeviceOperationLease, String> {
        self.begin_device_operation_kind(2)
    }

    pub fn pull_device_diagnostics(&self) -> Result<crate::backend::diagnostics::DeviceLogPage, String> {
        let _operation = self.begin_device_operation_kind(5)?;
        let snapshot = self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording { return Err("请先结束录音，再读取设备日志".into()); }
        if !snapshot.device.connected { return Err("请先连接 Companion，再读取设备日志".into()); }
        crate::backend::pull_device_diagnostics(snapshot.device.device_id.as_deref().ok_or("没有真实设备标识")?)
    }

    pub fn prepare_audio_components(&self)->Result<(),String> {
        let _operation=self.begin_device_operation_kind(6)?;
        let snapshot=self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording {return Err("请先结束录音，再准备音频组件".into());}
        crate::backend::prepare_speaker_runtime()
    }

    pub fn check_service(&self, service: crate::backend::service_check::Service) -> Result<crate::backend::service_check::CheckResult, String> {
        let _operation = self.begin_device_operation_kind(7)?;
        let snapshot = self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording {
            return Err("请先结束录音，再测试服务。".into());
        }
        Ok(crate::backend::service_check::check(service))
    }

    pub fn save_product_settings(&self, patch: crate::backend::product_settings::CompanionProductSettingsPatch)
        -> Result<crate::backend::product_settings::CompanionProductSettingsPublic, String> {
        let _operation = self.begin_device_operation_kind(10)?;
        let snapshot = self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording {
            return Err("请先结束录音，再修改服务设置。".into());
        }
        crate::backend::product_settings::merge_patch_and_save(patch)?;
        Ok(crate::backend::product_settings::public_report())
    }

    pub fn snapshot(&self) -> Result<CompanionV1Snapshot, String> {
        self.backend.snapshot()
    }

    pub fn begin_audio_export(&self) -> Result<CompanionDeviceOperationLease, String> {
        let lease = self.begin_device_operation_kind(8)?;
        let snapshot = self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording {
            return Err("请先结束并保存录音，再导出原音。".into());
        }
        Ok(lease)
    }

    pub fn discard_oldest_recording<F>(&self, seconds: u16, confirm: F)
        -> Result<crate::backend::recording_discard::RecordingDiscardReport, String>
    where F: FnOnce(&crate::backend::recording_discard::RecordingLossInfo) -> bool {
        let _lease = self.begin_device_operation_kind(9)?;
        let snapshot = self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording {
            return Err("请先结束录音，再查看可释放的设备录音。".into());
        }
        if !snapshot.device.connected || snapshot.device.mode != "windowsNative" {
            return Err("请先连接真实 Companion；演示和工具桥接不执行用户录音删除。".into());
        }
        let id = snapshot.device.device_id.as_deref().filter(|id| !id.is_empty())
            .ok_or("未取得当前设备身份，请重新连接。")?;
        crate::backend::discard_oldest_recording(id, seconds, confirm)
    }

    pub fn save_meeting_edit(&self, request: crate::backend::meeting_workspace::MeetingEditRequest) -> Result<CompanionV1Snapshot, String> {
        self.backend.save_meeting_edit(request)
    }

    pub fn save_meeting_note(&self, request: crate::backend::meeting_notes::Request) -> Result<CompanionV1Snapshot, String> {
        if self.device_operation.load(Ordering::Acquire) == 11 { return Err("软件正在更新，请稍后保存备注。".into()); }
        self.backend.save_meeting_note(request)
    }

    pub fn save_bookmark(&self, request:crate::backend::recording_bookmarks::Request)
        -> Result<CompanionV1Snapshot,String> {
        use crate::backend::recording_bookmarks::Action;
        if self.device_operation.load(Ordering::Acquire) == 11 { return Err("软件正在更新，请稍后保存重点。".into()); }
        let _lease=if request.action == Action::AddLive { Some(self.begin_device_operation_kind(12)?) } else { None };
        self.backend.save_bookmark(request,None)
    }

    pub(crate) fn save_live_bookmark(&self, request:crate::backend::recording_bookmarks::Request,
        stamp:crate::backend::recording_bookmarks::LiveStamp) -> Result<CompanionV1Snapshot,String> {
        if self.device_operation.load(Ordering::Acquire) != 2
            || request.action != crate::backend::recording_bookmarks::Action::AddLive {
            return Err("在线采集连接已结束，未添加重点。".into());
        }
        self.backend.save_bookmark(request,Some(stamp))
    }

    pub fn apply_control(
        &self,
        request: CompanionV1ControlRequest,
    ) -> Result<CompanionV1Snapshot, String> {
        let operation = if request.action == crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings { Operation::RecordingSync } else { Operation::DeviceControl };
        let span = Span::start(operation);
        let result = self.apply_control_inner(request);
        let error = match &result {
            Err(error) => Some(error.as_str()),
            Ok(snapshot) => snapshot.last_control.as_ref().filter(|echo| !echo.accepted).map(|echo| echo.message.as_str()),
        };
        span.finish(error);
        result
    }

    fn apply_control_inner(
        &self, request: CompanionV1ControlRequest,
    ) -> Result<CompanionV1Snapshot, String> {
        let needs_device = match request.action {
            crate::companion_v1::CompanionV1ControlAction::DeviceScan
            | crate::companion_v1::CompanionV1ControlAction::DeviceConnect
            | crate::companion_v1::CompanionV1ControlAction::DeviceDisconnect
            | crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings
            | crate::companion_v1::CompanionV1ControlAction::ApplyBleName
            | crate::companion_v1::CompanionV1ControlAction::ResetBleName
            | crate::companion_v1::CompanionV1ControlAction::OobeRunChecks
            | crate::companion_v1::CompanionV1ControlAction::PrivacyDeleteSession
            | crate::companion_v1::CompanionV1ControlAction::PrivacyEraseAudio
            | crate::companion_v1::CompanionV1ControlAction::PrivacyEraseAll
            | crate::companion_v1::CompanionV1ControlAction::SpeakerPrompt
            | crate::companion_v1::CompanionV1ControlAction::SpeakerStop
            | crate::companion_v1::CompanionV1ControlAction::WakeArm
            | crate::companion_v1::CompanionV1ControlAction::WakeDisable
            | crate::companion_v1::CompanionV1ControlAction::WakeTestDetect => true,
            crate::companion_v1::CompanionV1ControlAction::MeetingStart
            | crate::companion_v1::CompanionV1ControlAction::MeetingStop
            | crate::companion_v1::CompanionV1ControlAction::MeetingFinalize => {
                request.audio_path.as_deref().is_none_or(|path| !path.starts_with("board://"))
            }
            _ => false,
        };
        let snapshot = self.backend.snapshot()?;
        if device_recording_blocks_control(&snapshot, request.action) {
            return Err(
                "device operation cannot start while the Companion is recording; end the recording on the device, then read device status again"
                    .to_string(),
            );
        }
        if needs_device
            && !owned_offline_recording_link(&snapshot,&request)
            && !matches!(
                request.action,
                crate::companion_v1::CompanionV1ControlAction::MeetingStop
                    | crate::companion_v1::CompanionV1ControlAction::MeetingFinalize
            )
            && snapshot_has_active_recording(&snapshot)
        {
            return Err(
                "device operation cannot start while a recording or transfer is active"
                    .to_string(),
            );
        }
        let _operation = needs_device
            .then(|| self.begin_device_operation_kind(1))
            .transpose()?;
        self.backend.apply_control(request)
    }

    pub fn automatic_reconnect_once(&self) -> Result<CompanionV1Snapshot, String> {
        let _operation = self.begin_device_operation_kind(4)?;
        // No-op background probes must not grow the log every polling tick.
        self.backend.automatic_reconnect_once()
    }

    pub fn record_meeting_recovery_failure(
        &self,
        session_id: &str,
        retry_stage: &str,
        error: &str,
    ) -> Result<(), String> {
        self.backend
            .record_meeting_recovery_failure(session_id, retry_stage, error)
    }

    pub fn mark_meeting_exported(
        &self,
        session_id: &str,
        meeting_mode: &str,
    ) -> Result<(), String> {
        self.backend
            .mark_meeting_exported(session_id, meeting_mode)
    }

    pub fn backend_capabilities(&self) -> CompanionBackendCapabilities {
        self.backend.capabilities()
    }

    pub fn ble_bridge_status(&self) -> CompanionBleBridgeStatus {
        self.backend.ble_bridge_status()
    }

    pub fn transfer_firmware_ota(
        &self,
        request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionFirmwareOtaReport, String> {
        Span::start(Operation::OtaTransfer).result(self.transfer_firmware_ota_inner(request))
    }

    fn transfer_firmware_ota_inner(&self, request: CompanionFirmwareOtaRequest) -> Result<CompanionFirmwareOtaReport, String> {
        let _operation = self.begin_device_operation_kind(3)?;
        let snapshot = self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording {
            return Err("firmware OTA cannot start while a recording or transfer is active".to_string());
        }
        self.backend.transfer_firmware_ota(request)
    }

    pub fn validate_ota_package(
        &self,
        request: CompanionFirmwareOtaRequest,
    ) -> Result<CompanionOtaPackageValidation, String> {
        Span::start(Operation::OtaValidate).result(self.backend.validate_ota_package(request))
    }

    pub fn complete_board_online_live(
        &self,
        session_id: &str,
        report: &BoardOnlineLiveReport,
    ) -> Result<CompanionV1Snapshot, String> {
        self.backend.complete_board_online_live(session_id, report)
    }

    pub fn set_board_online_live_partial(
        &self,
        session_id: &str,
        transcript: &str,
    ) -> Result<CompanionV1Snapshot, String> {
        self.backend
            .set_board_online_live_partial(session_id, transcript)
    }
    pub fn bind_board_online_live_recording(&self, session_id: &str, device_id: &str, recording_id: u32, start_ack_at: &str)
        -> Result<(), String> {
        self.backend.bind_board_online_live_recording(session_id, device_id, recording_id, start_ack_at)
    }

    pub fn fail_board_online_live(
        &self,
        session_id: &str,
        reason: &str,
    ) -> Result<CompanionV1Snapshot, String> {
        self.backend.fail_board_online_live(session_id, reason)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn confirmed_discard_has_exclusive_lease_and_fixture_never_asks_to_destroy() {
        let coordinator = CompanionCoordinator::new_fixture();
        let lease = coordinator.begin_device_operation_kind(9).unwrap();
        for kind in [1, 2, 3, 4, 5, 9] {
            assert!(coordinator.begin_device_operation_kind(kind).is_err());
        }
        drop(lease);
        let asked = std::sync::atomic::AtomicBool::new(false);
        assert!(coordinator.discard_oldest_recording(1800, |_| {
            asked.store(true, std::sync::atomic::Ordering::Relaxed); true
        }).is_err());
        assert!(!asked.load(std::sync::atomic::Ordering::Relaxed));
        assert!(coordinator.begin_device_operation_kind(1).is_ok());
    }
    use crate::companion_v1::CompanionV1ControlAction;

    #[test]
    fn only_same_owned_offline_board_session_can_change_its_link_during_capture() {
        use crate::companion_v1::{apply_fixture_control,fixture_snapshot};
        let request:CompanionV1ControlRequest=serde_json::from_value(serde_json::json!({"action":"meetingStart","sessionId":"owned"})).unwrap();
        let mut snapshot=apply_fixture_control(fixture_snapshot(),request).unwrap();
        snapshot.source="firmware";snapshot.device.mode="windowsNative".into();
        snapshot.device.device_id=Some("C8:92:FF:DD:3B:CA".into());
        let row=&mut snapshot.host.sessions[0];row.source="boardDevice".into();row.meeting_mode="offlineStore".into();
        row.source_device_id=snapshot.device.device_id.clone();row.device_recording_id=Some(32);
        let connect:CompanionV1ControlRequest=serde_json::from_value(serde_json::json!({"action":"deviceConnect","deviceId":"c892ffdd3bca"})).unwrap();
        assert!(owned_offline_recording_link(&snapshot,&connect));
        let disconnect=serde_json::from_value(serde_json::json!({"action":"deviceDisconnect"})).unwrap();
        assert!(owned_offline_recording_link(&snapshot,&disconnect));
        for invalid in ["online","host","unknown","foreign","wrong_session","multiple","fixture"] {
            let mut s=snapshot.clone();let mut r=connect.clone();
            match invalid {
                "online"=>s.host.sessions[0].meeting_mode="onlineLive".into(),
                "host"=>s.host.sessions[0].source="hostMicrophone".into(),
                "unknown"=>s.host.sessions[0].device_recording_id=None,
                "foreign"=>r.device_id=Some("00:11:22:33:44:55".into()),
                "wrong_session"=>r.session_id=Some("other".into()),
                "multiple"=>s.host.sessions.push(s.host.sessions[0].clone()),
                "fixture"=>s.source="fixture",_=>{}
            }
            assert!(!owned_offline_recording_link(&s,&r),"{invalid}");
        }
        for action in ["deviceScan","deviceSyncRecordings","privacyEraseAll","speakerPrompt"] {
            let r=serde_json::from_value(serde_json::json!({"action":action})).unwrap();
            assert!(!owned_offline_recording_link(&snapshot,&r),"{action}");
        }
    }

    #[test]
    fn coordinator_owns_backend_state() {
        let coordinator = CompanionCoordinator::new_fixture();
        let initial = coordinator.snapshot().unwrap();
        assert_eq!(initial.host.sessions.len(), 0);

        coordinator
            .apply_control(CompanionV1ControlRequest {
                action: CompanionV1ControlAction::MeetingStart,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: Some("Coordinator chain".to_string()),
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            })
            .unwrap();

        let next = coordinator.snapshot().unwrap();
        assert_eq!(next.host.sessions.len(), 1);
        assert_eq!(next.host.sessions[0].title, "Coordinator chain");
    }

    #[test]
    fn one_device_operation_lease_blocks_recording_ota_oobe_and_reconnect() {
        let coordinator = CompanionCoordinator::new_fixture();
        let board = coordinator.begin_board_recording_operation().unwrap();
        assert!(coordinator.begin_device_operation_kind(1).is_err());
        assert!(coordinator.begin_device_operation_kind(3).is_err());
        assert!(coordinator.begin_device_operation_kind(4).is_err());
        drop(board);
        assert!(coordinator.begin_device_operation_kind(4).is_ok());
    }

    #[test]
    fn original_export_blocks_capture_and_privacy_deletion_until_released() {
        let coordinator = CompanionCoordinator::new_fixture();
        let export = coordinator.begin_audio_export().unwrap();
        for action in ["meetingStart", "privacyDeleteSession", "privacyEraseAudio", "privacyEraseAll"] {
            let request = serde_json::from_value(serde_json::json!({"action": action})).unwrap();
            let error = coordinator.apply_control(request).unwrap_err();
            assert!(error.contains("original audio export"), "{action}: {error}");
        }
        assert!(coordinator.begin_audio_export().is_err());
        drop(export);
        assert!(coordinator.begin_audio_export().is_ok());
    }

    #[test]
    fn active_recording_state_blocks_device_maintenance_planning() {
        let mut snapshot = crate::companion_v1::fixture_snapshot();
        assert!(!snapshot_has_active_recording(&snapshot));
        snapshot.meeting.active = true;
        assert!(snapshot_has_active_recording(&snapshot));
        snapshot.meeting.active = false;
        let mut session = crate::companion_v1::synced_device_session(
            &snapshot,
            &CompanionV1ControlRequest {
                action: CompanionV1ControlAction::DeviceSyncRecordings,
                ble_name: None,
                session_id: Some("recording".to_string()),
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: Some("board://recording".to_string()),
                audio_bytes: Some(0),
                device_id: None,
                duration_ms: Some(0),
            },
            "now",
        );
        session.status = "recording".to_string();
        snapshot.host.sessions = vec![session];
        assert!(snapshot_has_active_recording(&snapshot));
    }

    #[test]
    fn service_settings_cannot_change_during_recording_or_another_operation() {
        let coordinator = CompanionCoordinator::new_fixture();
        let patch = || crate::backend::product_settings::CompanionProductSettingsPatch {
            settings: crate::backend::product_settings::CompanionProductSettings::default(),
            clear_credentials: vec![crate::backend::product_settings::CredentialKind::DeepseekApiKey],
        };
        let lease = coordinator.begin_board_recording_operation().unwrap();
        assert!(coordinator.save_product_settings(patch()).unwrap_err().contains("board recording/transfer"));
        drop(lease);
        coordinator.apply_control(serde_json::from_value(serde_json::json!({"action": "meetingStart"})).unwrap()).unwrap();
        assert!(coordinator.save_product_settings(patch()).unwrap_err().contains("请先结束录音"));
    }

    #[test]
    fn board_recording_blocks_maintenance_but_allows_status_refresh() {
        let mut snapshot = crate::companion_v1::fixture_snapshot();
        snapshot.device.recording = true;
        for action in [
            CompanionV1ControlAction::DeviceSyncRecordings,
            CompanionV1ControlAction::OobeRunChecks,
            CompanionV1ControlAction::SpeakerPrompt,
            CompanionV1ControlAction::SpeakerStop,
        ] {
            assert!(device_recording_blocks_control(&snapshot, action));
        }
        assert!(!device_recording_blocks_control(
            &snapshot,
            CompanionV1ControlAction::DeviceConnect
        ));
        snapshot.device.recording = false;
        assert!(!device_recording_blocks_control(
            &snapshot,
            CompanionV1ControlAction::DeviceSyncRecordings
        ));
    }
}
