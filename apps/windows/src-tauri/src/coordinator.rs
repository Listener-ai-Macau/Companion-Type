//! Companion coordinator.
//!
//! Single owner of the Companion host workflow over the selected native or
//! explicitly isolated fixture backend.

use std::sync::{
    atomic::{AtomicBool, AtomicU8, Ordering},
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
    pet_foreground: Arc<AtomicBool>,
    shutdown:Arc<crate::backend::lifecycle::Shutdown>,
}

const PET_CAPTION_OPERATION:u8=15;
const PET_CAPTURE_OPERATION:u8=16;
struct PetForegroundGuard(Arc<AtomicBool>);
impl Drop for PetForegroundGuard {
    fn drop(&mut self) {self.0.store(false,Ordering::Release);}
}

pub struct CompanionDeviceOperationLease {
    gate: Arc<AtomicU8>,
    kind: u8,
}
#[derive(serde::Serialize)]
#[serde(rename_all="camelCase")]
pub struct CompanionLibraryPurgeReport {
    pub snapshot:CompanionV1Snapshot,pub deleted:Vec<String>,pub failures:Vec<CompanionLibraryPurgeFailure>,
}
#[derive(serde::Serialize)]
#[serde(rename_all="camelCase")]
pub struct CompanionLibraryPurgeFailure{pub session_id:String,pub message:String}

impl Drop for CompanionDeviceOperationLease {
    fn drop(&mut self) {
        let _ = self
            .gate
            .compare_exchange(self.kind, 0, Ordering::AcqRel, Ordering::Acquire);
    }
}

fn claim_device_operation(gate:&Arc<AtomicU8>,shutdown:&crate::backend::lifecycle::Shutdown,kind:u8)
    ->Result<CompanionDeviceOperationLease,String> {
    if shutdown.requested(){return Err(crate::backend::lifecycle::CLOSING.into());}
    gate.compare_exchange(0,kind,Ordering::AcqRel,Ordering::Acquire)
        .map_err(|active|format!("device is busy with {}; {} cannot start",operation_name(active),operation_name(kind)))?;
    let lease=CompanionDeviceOperationLease{gate:Arc::clone(gate),kind};
    if shutdown.requested(){return Err(crate::backend::lifecycle::CLOSING.into());}
    Ok(lease)
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
        13 => "continuous recording synchronization",
        14 => "local original recording recovery",
        PET_CAPTION_OPERATION => "pet caption",
        PET_CAPTURE_OPERATION => "pet utterance capture",
        18 => "library organization",
        19 => "library protection/trash",
        20 => "pet finding",
        21 => "pet personality and memory",
        22 => "desktop dictation",
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

fn original_restart_connect(snapshot:&CompanionV1Snapshot, request:&CompanionV1ControlRequest)->bool {
    use crate::companion_v1::CompanionV1ControlAction as Action;
    if request.action!=Action::DeviceConnect || request.audio_path.is_some() || request.audio_bytes.is_some() {
        return false;
    }
    let Some(device)=request.device_id.as_deref().or(snapshot.device.device_id.as_deref()) else {return false;};
    // The same exact durable journal already authorizes automatic original
    // recovery. Explicit Connect after process exit must reach that protected
    // QUERY too, even before this process has learned the peer's capabilities.
    crate::backend::recorder_control::restart_recovery_request(snapshot,device)
        .is_some_and(|recovery|request.session_id.as_deref().is_none_or(|id|recovery.session_id.as_deref()==Some(id)))
}

fn device_recording_blocks_control(
    snapshot: &CompanionV1Snapshot,
    action: crate::companion_v1::CompanionV1ControlAction,
) -> bool {
    if action == crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings
        && crate::backend::segmented_link_change_allowed(snapshot) {
        return false;
    }
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
    pub(crate) fn is_shutting_down(&self)->bool {self.shutdown.requested()}
    pub(crate) fn request_shutdown(&self) {
        crate::backend::desktop_dictation::request_stop();
        self.shutdown.request();
        crate::backend::recording_sync::request_process_shutdown();
        crate::backend::meeting_processing_job::cancel_for_shutdown();
    }
    pub(crate) fn finish_shutdown(&self,budget:std::time::Duration)->Result<usize,String> {
        self.request_shutdown();
        let until=std::time::Instant::now()+budget;
        while self.device_operation.load(Ordering::Acquire)!=0 {
            if std::time::Instant::now()>=until {
                return Err(format!("仍在安全结束{}，未强行退出",operation_name(self.device_operation.load(Ordering::Acquire))));
            }
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        self.backend.finish_host_recording_on_exit()?;
        // Wait through backend persistence, not just the external model call.
        // Any caller already queued on the gate rejects work after shutdown.
        self.backend.finish_meeting_processing_on_exit(until.saturating_duration_since(std::time::Instant::now()))?;
        crate::backend::release_process_device_links()
    }
    pub fn begin_desktop_update_operation(&self) -> Result<CompanionDeviceOperationLease,String> {
        let lease=self.begin_foreground_operation_kind(11)?;
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
            pet_foreground: Arc::new(AtomicBool::new(false)),
            shutdown:Arc::clone(&crate::backend::lifecycle::PROCESS),
        }
    }

    fn begin_device_operation_kind(
        &self,
        kind: u8,
    ) -> Result<CompanionDeviceOperationLease, String> {
        if self.is_shutting_down(){return Err(crate::backend::lifecycle::CLOSING.into());}
        if kind == 13 && self.device_operation.load(Ordering::Acquire) == 0 {
            crate::backend::recording_sync::prepare_background();
        } else if kind != 13 && self.device_operation.load(Ordering::Acquire) == 13 {
            crate::backend::recording_sync::yield_background();
            let until = std::time::Instant::now() + std::time::Duration::from_secs(30);
            while self.device_operation.load(Ordering::Acquire) == 13 && std::time::Instant::now() < until {
                std::thread::sleep(std::time::Duration::from_millis(5));
            }
        }
        claim_device_operation(&self.device_operation,&self.shutdown,kind)
    }

    pub fn begin_board_recording_operation(
        &self,
    ) -> Result<CompanionDeviceOperationLease, String> {
        self.begin_foreground_operation_kind(2)
    }

    fn begin_foreground_operation_kind(&self,kind:u8)->Result<CompanionDeviceOperationLease,String> {
        self.begin_foreground_operation(kind,false,None)
    }

    fn begin_foreground_operation(&self,kind:u8,manual_disconnect:bool,target:Option<&str>)
        ->Result<CompanionDeviceOperationLease,String> {
        // Block new pet owners while the old owner performs its real cleanup.
        // Never exchange an in-use radio/recording lease for an idle marker.
        self.pet_foreground.compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire)
            .map_err(|_|"正在交接当前操作，请稍后再试。".to_string())?;
        let _guard=PetForegroundGuard(Arc::clone(&self.pet_foreground));
        // Save the exact user's intent without waiting for snapshot/native
        // probe locks. The existing background owner retains its real lease
        // and performs its own late-result cleanup. OTA/capture owners remain
        // non-preemptible and do not get a new preference as a side effect.
        if manual_disconnect && self.device_operation.load(Ordering::Acquire)==4 {
            self.backend.request_manual_disconnect(target)?;
        }
        let request=crate::backend::pet_chat::yield_for_foreground()?;
        let started=std::time::Instant::now();
        let until=started+std::time::Duration::from_secs(15);
        loop {
            if self.is_shutting_down(){return Err(crate::backend::lifecycle::CLOSING.into());}
            let active=self.device_operation.load(Ordering::Acquire);
            if matches!(active,PET_CAPTION_OPERATION|PET_CAPTURE_OPERATION) || (manual_disconnect && active==4) {
                if std::time::Instant::now()>=until {
                    return Err(if active==4 {"已保存断开请求，当前连接仍在安全收尾；尚未确认断开。"}
                        else {"宠物聊天还在安全收尾，这次操作尚未开始，请稍后重试。"}.into());
                }
                std::thread::sleep(std::time::Duration::from_millis(5));continue;
            }
            match self.begin_device_operation_kind(kind) {
                Ok(lease)=>{
                    if let Some(request)=request {
                        eprintln!("pet_chat_foreground_handoff request={} operation={} wait_ms={}",
                            request,kind,started.elapsed().as_millis());
                    }
                    return Ok(lease);
                },
                Err(_) if std::time::Instant::now()<until &&
                    matches!(self.device_operation.load(Ordering::Acquire),0|PET_CAPTION_OPERATION|PET_CAPTURE_OPERATION)=>continue,
                Err(error)=>return Err(error),
            }
        }
    }

    fn begin_pet_operation_kind(&self,kind:u8)->Result<CompanionDeviceOperationLease,String> {
        if self.pet_foreground.load(Ordering::Acquire) {return Err("设备正在切换操作，聊天已让路。".into());}
        let lease=self.begin_device_operation_kind(kind)?;
        // Close the race with a foreground request between the first check
        // and lease acquisition; dropping here has not opened a device handle.
        if self.pet_foreground.load(Ordering::Acquire) {return Err("设备正在切换操作，聊天已让路。".into());}
        Ok(lease)
    }
    pub(crate) fn begin_pet_capture_operation(&self)->Result<CompanionDeviceOperationLease,String> {
        self.begin_pet_operation_kind(PET_CAPTURE_OPERATION)
    }
    pub(crate) fn begin_pet_caption_operation(&self)->Result<CompanionDeviceOperationLease,String> {
        self.begin_pet_operation_kind(PET_CAPTION_OPERATION)
    }
    pub(crate) fn begin_pet_profile_operation(&self)->Result<CompanionDeviceOperationLease,String> {
        self.begin_foreground_operation_kind(21)
    }

    /// Pet capture already owns the recorder lease across START, the short
    /// utterance and durable STOP/receive. Re-enter the same product backend
    /// without trying to acquire a second, conflicting device-control lease.
    pub(crate) fn apply_pet_capture_control(&self, lease: &CompanionDeviceOperationLease,
        request: CompanionV1ControlRequest) -> Result<CompanionV1Snapshot,String> {
        use crate::companion_v1::CompanionV1ControlAction as Action;
        if lease.kind != PET_CAPTURE_OPERATION || !Arc::ptr_eq(&lease.gate,&self.device_operation)
            || self.device_operation.load(Ordering::Acquire) != PET_CAPTURE_OPERATION
            || !matches!(request.action,Action::MeetingStart|Action::MeetingStop)
            || request.prompt_id.as_deref()!=Some(crate::backend::pet_chat::CAPTURE_PROMPT)
            || request.session_id.as_deref().is_none_or(|id| !id.starts_with("pet-chat-"))
            || request.audio_path.is_some() || request.audio_bytes.is_some() {
            return Err("宠物聊天没有取得原录音操作，未发送控制。".into());
        }
        self.backend.apply_control(request)
    }

    fn owns_recording_lease(&self,lease:&CompanionDeviceOperationLease)->bool {
        lease.kind==2 && Arc::ptr_eq(&lease.gate,&self.device_operation)
            && self.device_operation.load(Ordering::Acquire)==2
    }

    pub(crate) fn apply_online_capture_control(&self,lease:&CompanionDeviceOperationLease,
        request:CompanionV1ControlRequest)->Result<CompanionV1Snapshot,String> {
        use crate::companion_v1::CompanionV1ControlAction as Action;
        if !self.owns_recording_lease(lease)
            || !matches!(request.action,Action::MeetingStart|Action::MeetingStop|Action::DeviceConnect|Action::DeviceDisconnect)
            || request.session_id.as_deref().is_none_or(|id|!id.starts_with("board-online-"))
            || request.meeting_mode.as_deref()!=Some("onlineLive")
            || request.audio_path.is_some() || request.audio_bytes.is_some() {
            return Err("在线会议没有取得原录音操作，未发送控制。".into());
        }
        if matches!(request.action,Action::DeviceConnect|Action::DeviceDisconnect)
            && !owned_offline_recording_link(&self.backend.snapshot()?,&request) {
            return Err("在线会议重连没有唯一的原录音身份，未建立替代连接。".into());
        }
        self.backend.apply_control(request)
    }

    pub(crate) fn follow_online_capture(&self,lease:&CompanionDeviceOperationLease,session:&str,
        live:&mut crate::backend::recording_wire::receiver::LiveCursor)->Result<bool,String> {
        if !self.owns_recording_lease(lease) {return Err("在线会议原录音操作已结束。".into());}
        // Acquiring the foreground recorder lease may have yielded a follower.
        // This scoped follower now borrows that same lease and must reopen its
        // background budget, just like the ordinary kind-13 follower does.
        crate::backend::recording_sync::prepare_background();
        self.backend.follow_recording_once(Some(session),Some(live))
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

    pub(crate) fn begin_pet_find_operation(&self)->Result<CompanionDeviceOperationLease,String> {
        // Finding is optional: never yield capture, captions or synchronization.
        if self.pet_foreground.load(Ordering::Acquire) {return Err("设备正在交接当前操作，寻找尚未开始。".into());}
        let lease=claim_device_operation(&self.device_operation,&self.shutdown,20)?;
        if self.pet_foreground.load(Ordering::Acquire) {return Err("设备正在交接当前操作，寻找尚未开始。".into());}
        Ok(lease)
    }

    pub fn snapshot(&self) -> Result<CompanionV1Snapshot, String> {
        self.backend.snapshot()
    }

    pub(crate) fn restore_local_recordings(&self) -> Result<crate::backend::recording_wire::receiver::LocalRestoreReport,String> {
        let _lease=self.begin_device_operation_kind(14)?;
        self.backend.restore_local_recordings()
    }

    pub fn begin_audio_export(&self) -> Result<CompanionDeviceOperationLease, String> {
        let lease = self.begin_device_operation_kind(8)?;
        let snapshot = self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot) || snapshot.device.recording {
            return Err("请先结束并保存录音，再导出原音。".into());
        }
        Ok(lease)
    }

    pub(crate) fn begin_audio_edit(&self)->Result<CompanionDeviceOperationLease,String>{
        let lease=self.begin_device_operation_kind(19)?;
        crate::backend::audio_editing::available(&self.backend.snapshot()?)?;Ok(lease)
    }
    pub(crate) fn commit_audio_edit(&self,row:crate::companion_v1::CompanionV1HostSession,
        sources:&[crate::backend::audio_derivation::SourceIdentity],token:&str)->Result<(),String>{
        if self.is_shutting_down(){return Err(crate::backend::lifecycle::CLOSING.into());}
        self.backend.commit_audio_edit(row,sources,token)
    }
    pub fn import_audio_file(&self,path:&std::path::Path)->Result<CompanionV1Snapshot,String>{
        if self.is_shutting_down() {return Err(crate::backend::lifecycle::CLOSING.into());}
        self.backend.import_audio_file(path)
    }

    pub fn restore_library_backup(&self,path:&std::path::Path)->Result<CompanionV1Snapshot,String>{
        let _lease=self.begin_device_operation_kind(19)?;
        self.backend.restore_library_backup(path)
    }

    fn management_device(&self)->Result<String,String> {
        let s=self.backend.snapshot()?;
        if snapshot_has_active_recording(&s)||s.device.recording {return Err("请先停止并保存录音。".into());}
        if !s.device.connected||s.device.mode!="windowsNative" {return Err("请先连接录音卡。".into());}
        s.device.device_id.filter(|id|!id.is_empty()).ok_or("未取得设备身份，请重新连接。".into())
    }
    pub(crate) fn list_device_recordings(&self)->Result<Vec<crate::backend::DeviceRecording>,String> {
        let _lease=self.begin_device_operation_kind(9)?;
        crate::backend::list_device_recordings(&self.management_device()?)
    }
    pub(crate) fn delete_device_recording<F>(&self,key:&crate::companion_v1::CompanionV1RecordingKey,confirm:F)
      ->Result<crate::backend::recording_discard::RecordingDiscardReport,String>
    where F:FnOnce(&crate::backend::recording_discard::RecordingLossInfo)->bool {
        let _lease=self.begin_device_operation_kind(9)?;
        crate::backend::delete_device_recording(&self.management_device()?,key,confirm)
    }
    pub(crate) fn sync_device_recording(&self,key:&crate::companion_v1::CompanionV1RecordingKey)->Result<CompanionV1Snapshot,String> {
        let _lease=self.begin_board_recording_operation()?;
        crate::backend::sync_selected_recording_key(&self.management_device()?,key)?;
        self.backend.refresh_device_recording_library()
    }

    pub(crate) fn begin_desktop_dictation(&self)->Result<(String,crate::backend::recording_wire::transport::Peer,CompanionDeviceOperationLease),String>{
        if !cfg!(windows){return Err("电脑输入当前支持Windows客户端。".into());}
        let lease=self.begin_foreground_operation_kind(22)?;
        let snapshot=self.backend.snapshot()?;
        if snapshot_has_active_recording(&snapshot)||snapshot.device.recording{return Err("请先结束并保存当前录音，再切换按住说话。".into());}
        let device=self.management_device()?;
        let peer=crate::backend::known_segmented_peer(&device).ok_or("请先正常连接录音卡并读取目录。")?;
        Ok((device,peer,lease))
    }
    pub(crate) fn complete_desktop_dictation(&self,device:&str,key:&crate::companion_v1::CompanionV1RecordingKey,
        cancelled:&AtomicBool,stage:impl Fn(&str))->Result<(String,String),String>{
        // The desktop-mode operation lease already owns these existing services.
        crate::backend::sync_selected_recording_key(device,key)?;
        let snapshot=self.backend.refresh_device_recording_library()?;
        let row=snapshot.host.sessions.iter().find(|s|s.device_recording_key.as_ref()==Some(key))
            .ok_or("本次原音已接收，请在录音库查看；尚未找到对应输入会话。")?;
        let id=row.id.clone();
        if cancelled.load(Ordering::Acquire){return Ok((id,String::new()));}
        stage("transcribing");
        let request=CompanionV1ControlRequest {action:crate::companion_v1::CompanionV1ControlAction::MeetingTranscribeAudio,
            session_id:Some(id.clone()),minutes_template:None,recording_source:None,context_note_revision:None,
            ble_name:None,prompt_id:Some(format!("__meeting_job__desktop-{}",uuid::Uuid::new_v4())),title:None,transcript_text:None,meeting_mode:None,audio_path:None,
            audio_bytes:None,device_id:None,duration_ms:None};
        let snapshot=self.backend.apply_control(request)?;
        let result=snapshot.host.sessions.iter().find(|s|s.id==id).ok_or("原文结果保存在录音库，请重新打开查看。")?;
        if !result.transcript_final||result.transcript_text.trim().is_empty(){return Err("本次没有得到可交付的完整文字。".into());}
        Ok((id,result.transcript_text.clone()))
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
    pub fn save_library_organization(&self,request:crate::backend::library_organization::Request)->Result<CompanionV1Snapshot,String>{
        let _lease=self.begin_device_operation_kind(18)?;
        self.backend.save_library_organization(request)
    }
    pub fn save_library_lifecycle(&self,request:crate::backend::library_lifecycle::Request)->Result<CompanionV1Snapshot,String>{
        let _lease=self.begin_device_operation_kind(19)?;self.backend.save_library_lifecycle(request)
    }
    pub fn purge_library(&self,request:crate::backend::library_lifecycle::PurgeRequest)->Result<CompanionLibraryPurgeReport,String>{
        use crate::backend::library_lifecycle;
        let _lease=self.begin_device_operation_kind(19)?;let before=self.backend.snapshot()?;
        library_lifecycle::validate_purge(&before,&request)?;
        let selected=before.host.selected_session_id;let mut deleted=Vec::new();let mut failures=Vec::new();
        for target in &request.targets{
            let result=(||{
                // Recheck each target immediately before destructive work; an
                // intervening failure/change is reported, never silently skipped.
                library_lifecycle::validate_purge(&self.backend.snapshot()?,&library_lifecycle::PurgeRequest{targets:vec![target.clone()]})?;
                let select=serde_json::from_value(serde_json::json!({"action":"meetingSelectSession","sessionId":target.session_id})).map_err(|e|e.to_string())?;
                self.backend.apply_control(select)?;
                let erase=serde_json::from_value(serde_json::json!({"action":"privacyDeleteSession","sessionId":target.session_id,"promptId":library_lifecycle::LOCAL_TRASH_PERMANENT})).map_err(|e|e.to_string())?;
                self.backend.apply_control(erase)?;Ok::<(),String>(())
            })();
            match result{Ok(())=>deleted.push(target.session_id.clone()),Err(message)=>failures.push(CompanionLibraryPurgeFailure{session_id:target.session_id.clone(),message})}
        }
        if let Some(id)=selected.filter(|id|self.backend.snapshot().is_ok_and(|s|s.host.sessions.iter().any(|r|&r.id==id))){
            if let Ok(select)=serde_json::from_value(serde_json::json!({"action":"meetingSelectSession","sessionId":id})){let _=self.backend.apply_control(select);}
        }
        Ok(CompanionLibraryPurgeReport{snapshot:self.backend.snapshot()?,deleted,failures})
    }
    pub fn refine_meeting_speakers(&self,id:&str)->Result<CompanionV1Snapshot,String> {self.backend.refine_meeting_speakers(id)}
    pub fn preview_meeting_transcription(&self,id:&str,job_id:&str)->Result<crate::backend::transcription::TranscriptionPreview,String> {self.backend.preview_meeting_transcription(id,job_id)}
    pub fn preview_meeting_gap(&self,id:&str,job_id:&str,range:crate::backend::transcription::TranscriptionRange)->Result<crate::backend::transcription::TranscriptionPreview,String> {self.backend.preview_meeting_gap(id,job_id,range)}

    pub fn change_document_context(&self,request:crate::backend::document_context::Request)->Result<crate::backend::document_context::View,String>{
        if self.device_operation.load(Ordering::Acquire)==11{return Err("软件正在更新，请稍后保存文档。".into());}self.backend.change_document_context(request)
    }
    pub fn save_meeting_image_note(&self,request:crate::backend::meeting_note_images::Request)->Result<CompanionV1Snapshot,String>{
        if self.device_operation.load(Ordering::Acquire)==11{return Err("软件正在更新，请稍后保存图片。".into());}self.backend.save_meeting_image_note(request)
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
        if self.is_shutting_down(){return Err(crate::backend::lifecycle::CLOSING.into());}
        // Request handoff before snapshot() can wait behind the follower's
        // state/library lock. This signal is not the user's Pause Sync choice.
        if self.device_operation.load(Ordering::Acquire) == 13 {
            crate::backend::recording_sync::yield_background();
        }
        let operation = if request.action == crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings { Operation::RecordingSync } else { Operation::DeviceControl };
        let _diagnostic_scope=crate::backend::diagnostics::RecordingScope::enter_optional(request.session_id.as_deref());
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
        use crate::companion_v1::CompanionV1ControlAction as Action;
        let _local_audio=if request.action==Action::MeetingRestoreAudio {
            Some(self.begin_device_operation_kind(14)?)
        }else{None};
        // Only explicit user controls preempt a pet reply. Background probes,
        // diagnostics and ordinary sync do not cancel a conversation.
        let priority_action=matches!(request.action,Action::MeetingStart|Action::MeetingStop|
            Action::MeetingFinalize|Action::DeviceConnect|Action::DeviceDisconnect);
        if request.action==crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings {
            // Finish durable host data before radio setup. A later connection
            // failure cannot strand a complete original behind a virtual URI.
            self.restore_local_recordings()?;
        }
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
        let priority_operation=if needs_device && priority_action {
            Some(if request.action==Action::DeviceDisconnect {
                self.begin_foreground_operation(1,true,request.device_id.as_deref())?
            } else {self.begin_foreground_operation_kind(1)?})
        } else {None};
        let snapshot = self.backend.snapshot()?;
        let original_sync=crate::backend::owned_segmented_recording_sync(&snapshot,&request).is_some();
        let original_start_retry=crate::backend::recorder_control::unconfirmed_start_retry_request(&snapshot,&request);
        let original_reconnect=original_restart_connect(&snapshot,&request);
        if !original_sync && !original_start_retry && !original_reconnect && device_recording_blocks_control(&snapshot, request.action) {
            return Err(
                "device operation cannot start while the Companion is recording; end the recording on the device, then read device status again"
                    .to_string(),
            );
        }
        if needs_device
            && !original_sync
            && !original_start_retry
            && !original_reconnect
            && !owned_offline_recording_link(&snapshot,&request)
            && !(matches!(request.action,
                crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings
                    | crate::companion_v1::CompanionV1ControlAction::DeviceConnect
                    | crate::companion_v1::CompanionV1ControlAction::DeviceDisconnect)
                && crate::backend::segmented_link_change_allowed(&snapshot)
                && request.device_id.as_deref().is_none_or(|target| snapshot.device.device_id.as_deref()
                    .is_some_and(|current| crate::backend::same_device_id(target, current))))
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
        let _operation = (needs_device && priority_operation.is_none())
            .then(|| self.begin_device_operation_kind(1))
            .transpose()?;
        self.backend.apply_control(request)
    }

    pub fn automatic_reconnect_once(&self) -> Result<CompanionV1Snapshot, String> {
        if self.pet_foreground.load(Ordering::Acquire) {return Err("device is busy with foreground control; automatic reconnect deferred".into());}
        let _operation = self.begin_device_operation_kind(4)?;
        if self.pet_foreground.load(Ordering::Acquire) {return Err("device is busy with foreground control; automatic reconnect deferred".into());}
        // No-op background probes must not grow the log every polling tick.
        self.backend.automatic_reconnect_once()
    }

    pub fn follow_recording_once(&self) -> Result<bool, String> {
        let _operation = self.begin_device_operation_kind(13)?;
        self.backend.follow_recording_once(None,None)
    }

    pub fn follow_original_recording_once(&self, session_id: &str) -> Result<bool, String> {
        let _operation = self.begin_device_operation_kind(13)?;
        self.backend.follow_recording_once(Some(session_id),None)
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
        calendar_copy: Option<crate::backend::calendar_copy::Copy>,
    ) -> Result<(), String> {
        self.backend
            .mark_meeting_exported(session_id, meeting_mode, calendar_copy)
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
        let _operation = self.begin_foreground_operation_kind(3)?;
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
    fn r55_shutdown_does_not_steal_active_operation_and_rejects_new_owners() {
        let shutdown=crate::backend::lifecycle::Shutdown::new();
        let gate=Arc::new(AtomicU8::new(0));
        let old=claim_device_operation(&gate,&shutdown,3).unwrap();
        shutdown.request();
        for kind in [1,2,3,4,13,14,15,16] {
            assert!(claim_device_operation(&gate,&shutdown,kind).is_err());
            assert_eq!(gate.load(Ordering::Acquire),3);
        }
        drop(old);assert_eq!(gate.load(Ordering::Acquire),0);
        assert!(claim_device_operation(&gate,&shutdown,4).is_err());
    }
    #[test]
    fn explicit_original_restart_connect_requires_one_exact_durable_original() {
        use crate::companion_v1::{fixture_snapshot,create_host_session,CompanionV1ControlAction as A};
        let device="C8:92:FF:DD:3B:CA";
        let mut snapshot=fixture_snapshot();
        let mut start=crate::control_request(A::MeetingStart,Some("local-original".into()));
        start.device_id=Some(device.into());
        let mut row=create_host_session(&snapshot,&start,"");
        row.source="boardDevice".into();row.source_device_id=Some(device.into());row.status="recording".into();
        row.device_recording_id=Some(28);
        row.device_recording_key=Some(serde_json::from_value(serde_json::json!({
            "deviceUid":"010101010101010101010101","formatEpoch":"0000000000000005","sessionId":"0000000000000009"})).unwrap());
        row.recorder_control=Some(serde_json::from_value(serde_json::json!({
            "schema":1,"hostSession":"local-original","deviceId":device,"uid":vec![1u8;12],"epoch":5,
            "startRequest":1,"maxSeconds":0,"localOrigin":true,"key":row.device_recording_key,
            "anchor":28,"confirmed":{"command":4,"request":2,"sequence":1,"state":3,"durationMs":15820},"pending":null
        })).unwrap());
        snapshot.source="lastKnown";snapshot.connected=false;snapshot.device.connected=false;
        snapshot.device.mode="windowsNative".into();snapshot.device.device_id=Some(device.into());snapshot.device.mcu_uid=None;
        snapshot.device.recording=false;snapshot.meeting.active=false;snapshot.host.active_session_id=None;
        snapshot.host.persistence.status="ready".into();snapshot.host.sessions=vec![row];
        let mut connect=crate::control_request(A::DeviceConnect,None);connect.device_id=Some(device.into());
        assert!(snapshot_has_active_recording(&snapshot));
        assert!(!owned_offline_recording_link(&snapshot,&connect),"a new process lacks current firmware/peer proof");
        assert!(original_restart_connect(&snapshot,&connect),"exact durable intent may reach protected QUERY without a new START");
        snapshot.host.sessions[0].recorder_control.as_mut().unwrap().confirmed.as_mut().unwrap().state=1;
        assert!(original_restart_connect(&snapshot,&connect));
        for invalid in ["foreign_device","foreign_session","two_originals","missing_journal","wrong_key","ended","host_audio","blocked_index","fixture","different_control","external_audio"] {
            let mut s=snapshot.clone();let mut r=connect.clone();
            match invalid {
                "foreign_device"=>r.device_id=Some("AA:BB:CC:DD:EE:FF".into()),
                "foreign_session"=>r.session_id=Some("other".into()),
                "two_originals"=>s.host.sessions.push(s.host.sessions[0].clone()),
                "missing_journal"=>s.host.sessions[0].recorder_control=None,
                "wrong_key"=>s.host.sessions[0].device_recording_key.as_mut().unwrap().session_id="0000000000000010".into(),
                "ended"=>s.host.sessions[0].recorder_control.as_mut().unwrap().confirmed.as_mut().unwrap().state=2,
                "host_audio"=>s.host.sessions[0].source="hostMicrophone".into(),
                "blocked_index"=>s.host.persistence.status="blocked".into(),
                "fixture"=>s.source="fixture",
                "different_control"=>r.action=A::DeviceSyncRecordings,
                "external_audio"=>r.audio_path=Some("test.wav".into()),_=>unreachable!(),
            }
            assert!(!original_restart_connect(&s,&r),"{invalid}");
        }
    }
    #[test]
    fn online_capture_rejects_foreign_lease_before_any_backend_control() {
        let owner=CompanionCoordinator::new_fixture();let other=CompanionCoordinator::new_fixture();
        let lease=owner.begin_board_recording_operation().unwrap();
        let mut request=crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingStart,
            Some("board-online-owned".into()));request.meeting_mode=Some("onlineLive".into());
        assert!(other.apply_online_capture_control(&lease,request.clone()).is_err());
        request.audio_path=Some("board://online/old-placeholder".into());
        assert!(owner.apply_online_capture_control(&lease,request).is_err());
        for action in [crate::companion_v1::CompanionV1ControlAction::DeviceConnect,
            crate::companion_v1::CompanionV1ControlAction::DeviceDisconnect] {
            let mut request=crate::control_request(action,Some("board-online-unowned".into()));request.meeting_mode=Some("onlineLive".into());
            assert!(owner.apply_online_capture_control(&lease,request).is_err());
        }
        let mut cursor=crate::backend::recording_wire::receiver::LiveCursor::new(
            crate::backend::recording_wire::SessionKey {device_uid:[7;12],format_epoch:11,session_id:13}).unwrap();
        assert!(other.follow_online_capture(&lease,"board-online-owned",&mut cursor).is_err());
    }
    #[test]
    fn online_capture_follower_reopens_the_budget_yielded_by_its_start_lease() {
        let owner=CompanionCoordinator::new_fixture();
        let lease=owner.begin_board_recording_operation().unwrap();
        // Simulate the flag retained after handing an active kind-13 follower
        // to this foreground owner; an already-idle gate does not set it.
        crate::backend::recording_sync::yield_background();
        let prior=crate::backend::recording_sync::Job::begin_background("AA:BB:CC:DD:EE:19").unwrap();
        assert!(prior.yielded());drop(prior);
        let mut cursor=crate::backend::recording_wire::receiver::LiveCursor::new(
            crate::backend::recording_wire::SessionKey {device_uid:[7;12],format_epoch:11,session_id:13}).unwrap();
        // Fixture has no radio. The check concerns the shared scheduler budget,
        // not a fabricated successful recording or data receipt.
        assert!(!owner.follow_online_capture(&lease,"board-online-owned",&mut cursor).unwrap());
        let next=crate::backend::recording_sync::Job::begin_background("AA:BB:CC:DD:EE:19").unwrap();
        assert!(!next.yielded());
    }
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
    fn follower_handoff_keeps_durable_cursor_without_pausing_future_sync() {
        use crate::backend::{recording_sync, recording_transfer::{Cursor, Source}};
        use sha2::{Digest, Sha256};
        let coordinator = Arc::new(CompanionCoordinator::new_fixture());
        let folder = std::env::temp_dir().join(format!("companion-follow-handoff-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&folder).unwrap();
        let body: Vec<u8> = (0..100_000).map(|n| (n % 239) as u8).collect();
        let source = Source { device: "AA:BB:CC:DD:EE:19".into(), recording_id: 77,
            codec: 3, source_mode: 1, duration_ms: 50_000, total_length: body.len() as u32,
            sha256_prefix: Sha256::digest(&body)[..8].try_into().unwrap(), content_crc32: crc32fast::hash(&body) };
        let (ready_tx, ready_rx) = std::sync::mpsc::channel();
        let worker_coordinator = coordinator.clone();
        let worker_folder = folder.clone(); let worker_source = source.clone(); let worker_body = body.clone();
        let worker = std::thread::spawn(move || {
            let lease = worker_coordinator.begin_device_operation_kind(13).unwrap();
            let job = recording_sync::Job::begin_background(&worker_source.device).unwrap();
            let (mut cursor, _) = Cursor::open(&worker_folder, worker_source).unwrap();
            for bytes in worker_body[..80_000].chunks(224) { cursor.append(bytes).unwrap(); }
            ready_tx.send(()).unwrap();
            let runtime = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
            let result = runtime.block_on(job.receive(std::future::pending::<Result<(), String>>()));
            assert_eq!(result.unwrap_err(), recording_sync::PAUSED);
            assert!(job.yielded());
            assert!(!recording_sync::status().unwrap().pause_requested);
            drop(cursor); drop(job); drop(lease);
        });
        ready_rx.recv_timeout(std::time::Duration::from_secs(5)).unwrap();
        let control = coordinator.begin_device_operation_kind(1).unwrap();
        worker.join().unwrap();
        let (cursor, received) = Cursor::open(&folder, source.clone()).unwrap();
        assert_eq!(received, body[..80_000], "user control leaves the physical download's real durable prefix");
        drop(cursor); drop(control);
        assert!(recording_sync::automatic_allowed(&source.device), "handoff is not a persisted user Pause Sync");
        let next = recording_sync::Job::begin(&source.device).unwrap();
        assert!(!next.is_paused());
        drop(next);
    }

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
    fn manual_disconnect_waits_for_background_reconnect_without_stealing_its_lease() {
        let coordinator=std::sync::Arc::new(CompanionCoordinator::new_fixture());
        let reconnect=coordinator.begin_device_operation_kind(4).unwrap();
        let worker=std::sync::Arc::clone(&coordinator);
        let (tx,rx)=std::sync::mpsc::channel();
        let thread=std::thread::spawn(move|| {
            let request=serde_json::from_value(serde_json::json!({"action":"deviceDisconnect"})).unwrap();
            tx.send(worker.apply_control(request)).unwrap();
        });
        let early=rx.recv_timeout(std::time::Duration::from_millis(100));
        let still_owned=coordinator.device_operation.load(Ordering::Acquire);
        drop(reconnect);
        thread.join().unwrap();
        assert!(early.is_err(),"manual disconnect was rejected before background cleanup: {early:?}");
        assert_eq!(still_owned,4,"foreground must not fake release of the background owner");
        let result=rx.recv_timeout(std::time::Duration::from_secs(2)).unwrap().unwrap();
        assert!(!result.device.connected);
        assert_eq!(coordinator.device_operation.load(Ordering::Acquire),0);
    }

    #[test]
    fn coordinator_owns_backend_state() {
        let coordinator = CompanionCoordinator::new_fixture();
        let initial = coordinator.snapshot().unwrap();
        assert_eq!(initial.host.sessions.len(), 0);

        coordinator
            .apply_control(CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::MeetingStart,
                context_note_revision: None, ble_name: None,
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
            &CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: CompanionV1ControlAction::DeviceSyncRecordings,
                context_note_revision: None, ble_name: None,
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
