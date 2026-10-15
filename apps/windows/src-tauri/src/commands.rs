//! Tauri command surface for Companion Type.

use std::path::PathBuf;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, State, Manager};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};

use crate::backend::{
    product_settings::{self, CompanionProductSettingsPatch, CompanionProductSettingsPublic},
    record_board_online_live_controlled, BoardPartialConsumer, BoardPartialObserver,
    BoardRecordingObserver, BoardBookmarkObserver, CompanionBackendCapabilities, CompanionBleBridgeStatus,
    CompanionFirmwareOtaReport, CompanionFirmwareOtaRequest, CompanionOtaPackageValidation,
    CompanionTranscriptionManager,
};
use crate::companion_v1::{
    CompanionV1ControlAction, CompanionV1ControlRequest, CompanionV1Snapshot,
};
use crate::coordinator::CompanionCoordinator;

type CompanionCoordinatorState<'a> = State<'a, Arc<CompanionCoordinator>>;
type BoardOnlineLiveManagerState<'a> = State<'a, Arc<CompanionBoardOnlineLiveManager>>;

#[tauri::command]
pub async fn save_companion_bookmark(coordinator: CompanionCoordinatorState<'_>, manager: BoardOnlineLiveManagerState<'_>,
    request:crate::backend::recording_bookmarks::Request) -> Result<CompanionV1Snapshot,String> {
    let coordinator=coordinator.inner().clone();
    let manager=manager.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let snapshot=coordinator.snapshot()?;
        let session=snapshot.host.sessions.iter().find(|s| s.id == request.session_id).ok_or("这场会议已不存在。")?;
        if snapshot.host.persistence.status != "ready" { return Err("请先重试保存会议库；重点输入仍保留。".into()); }
        if crate::backend::recording_bookmarks::duplicate(session,&request)? { return Ok(snapshot); }
        let status=manager.snapshot()?;
        if request.action == crate::backend::recording_bookmarks::Action::AddLive
            && status.session_id.as_deref() == Some(&request.session_id)
            && matches!(status.state.as_str(),"starting"|"recording") {
            let queue=manager.bookmarks.lock().map_err(|_| "重点队列暂时不可用。")?.clone()
                .ok_or("在线录音正在结束，未添加重点。")?;
            let receiver=queue.enqueue(request)?;
            receiver.recv_timeout(std::time::Duration::from_secs(26))
                .map_err(|_| "未及时取得设备时间，请刷新核对；输入仍保留，可以用同一请求重试。".to_string())?
        } else { coordinator.save_bookmark(request) }
    }).await.map_err(|_| "保存重点任务未完成，请刷新核对后重试。".to_string())?
}

#[tauri::command]
pub async fn save_companion_meeting_note(coordinator: CompanionCoordinatorState<'_>, request: crate::backend::meeting_notes::Request)
    -> Result<CompanionV1Snapshot, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || coordinator.save_meeting_note(request)).await
        .map_err(|_| "备注保存任务未完成；输入仍保留，请重试。".to_string())?
}

#[tauri::command]
pub async fn check_companion_service(coordinator: CompanionCoordinatorState<'_>, service: crate::backend::service_check::Service)
    -> Result<crate::backend::service_check::CheckResult, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || coordinator.check_service(service)).await
        .map_err(|_| "服务测试任务未完成，请重试。".to_string())?
}

#[tauri::command]
pub async fn prepare_companion_audio_components(coordinator: CompanionCoordinatorState<'_>)->Result<(),String> {
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move|| coordinator.prepare_audio_components()).await.map_err(|_|"准备音频组件任务失败".to_string())?
}

#[tauri::command]
pub async fn export_companion_diagnostics(
    app: AppHandle, coordinator: CompanionCoordinatorState<'_>, include_device: bool,
) -> Result<Option<CompanionMeetingExportResult>, String> {
    let destination = app.dialog().file().add_filter("Companion diagnostics", &["json"])
        .set_file_name("companion-diagnostics.json").blocking_save_file();
    let Some(destination) = destination else { return Ok(None); };
    let destination = destination.simplified().into_path().map_err(|_| "请选择本机文件位置")?;
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let (device, warning) = if include_device {
            match coordinator.pull_device_diagnostics() {
                Ok(page) => (Some(page), None),
                Err(_) => (None,Some("本机日志已保存；设备日志读取未成功，可能尚未连接、正在忙碌或固件不支持。请结束录音/升级并确认连接后重试。".to_string())),
            }
        } else { (None,None) };
        let snapshot = coordinator.snapshot()?;
        let report = crate::backend::diagnostics::report(&snapshot,device,include_device);
        let bytes=serde_json::to_vec_pretty(&report).map_err(|_| "无法生成诊断报告")?;
        let written=crate::backend::export::write_atomic(&destination,&bytes)?;
        Ok(Some(CompanionMeetingExportResult { path:destination.to_string_lossy().into_owned(),bytes:written,warning }))
    }).await.map_err(|_| "诊断导出任务失败".to_string())?
}

#[tauri::command]
pub async fn save_companion_meeting_edit(
    coordinator: CompanionCoordinatorState<'_>, request: crate::backend::meeting_workspace::MeetingEditRequest,
) -> Result<CompanionV1Snapshot, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || coordinator.save_meeting_edit(request))
        .await.map_err(|e| format!("保存会议任务失败：{e}"))?
}

#[tauri::command]
pub fn prepare_companion_audio(
    app: AppHandle, coordinator: CompanionCoordinatorState<'_>, session_id: String,
) -> Result<String, String> {
    // No renderer-supplied filesystem path, recursive scope, file upload or
    // full-file base64 allocation. Tauri serves bounded HTTP ranges locally.
    let path = crate::backend::meeting_workspace::local_audio_path(&coordinator.snapshot()?, &session_id)?;
    app.asset_protocol_scope().allow_file(&path).map_err(|e| format!("无法准备回听：{e}"))?;
    Ok(path.to_string_lossy().into_owned())
}

#[derive(Serialize)]
#[serde(rename_all="camelCase")]
pub struct PreparedAudioTimeline {
    path:String,
    pause_timeline:Option<crate::backend::recording_pause_view::PauseTimeline>,
}

#[tauri::command]
pub async fn prepare_companion_audio_with_timeline(
    app:AppHandle,coordinator:CompanionCoordinatorState<'_>,session_id:String,
)->Result<PreparedAudioTimeline,String> {
    let coordinator=coordinator.inner().clone();
    let prepared=tauri::async_runtime::spawn_blocking(move || {
        let _lease=coordinator.begin_audio_export()?;
        let snapshot=coordinator.snapshot()?;
        let path=crate::backend::meeting_workspace::local_audio_path(&snapshot,&session_id)?;
        let pause_timeline=crate::backend::recording_pause_view::prepare(&snapshot,&session_id)?;
        Ok::<_,String>(PreparedAudioTimeline{path:path.to_string_lossy().into_owned(),pause_timeline})
    }).await.map_err(|e|format!("准备原音任务失败：{e}"))??;
    app.asset_protocol_scope().allow_file(&prepared.path).map_err(|e|format!("无法准备回听：{e}"))?;
    Ok(prepared)
}

#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum CompanionMeetingExportFormat {
    Markdown,
    Txt,
    Json,
    Srt,
    Todo,
    Ics,
}

impl From<CompanionMeetingExportFormat> for crate::backend::export::MeetingExportFormat {
    fn from(value: CompanionMeetingExportFormat) -> Self {
        match value {
            CompanionMeetingExportFormat::Markdown => Self::Markdown,
            CompanionMeetingExportFormat::Txt => Self::Txt,
            CompanionMeetingExportFormat::Json => Self::Json,
            CompanionMeetingExportFormat::Srt => Self::Srt,
            CompanionMeetingExportFormat::Todo => Self::Todo,
            CompanionMeetingExportFormat::Ics => Self::Ics,
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionMeetingExportRequest {
    pub session_id: String,
    pub meeting_mode: String,
    pub format: CompanionMeetingExportFormat,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionMeetingExportResult {
    pub path: String,
    pub bytes: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub warning: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionBoardOnlineLiveStartRequest {
    pub title: Option<String>,
    pub device_id: Option<String>,
    pub max_duration_seconds: Option<u16>,
    pub partial_interval_ms: Option<u64>,
    pub disconnect_after_seconds: Option<u16>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CompanionBoardOnlineLiveStatus {
    pub state: String,
    pub session_id: Option<String>,
    pub device_id: Option<String>,
    pub recording_id: Option<u32>,
    pub partial_count: u32,
    pub duration_ms: u64,
    pub max_duration_seconds: Option<u16>,
    pub disconnect_resume: bool,
    pub final_recording_path: Option<String>,
    pub error: Option<String>,
}

impl Default for CompanionBoardOnlineLiveStatus {
    fn default() -> Self {
        Self {
            state: "idle".to_string(),
            session_id: None,
            device_id: None,
            recording_id: None,
            partial_count: 0,
            duration_ms: 0,
            max_duration_seconds: None,
            disconnect_resume: false,
            final_recording_path: None,
            error: None,
        }
    }
}

pub struct CompanionBoardOnlineLiveManager {
    status: Mutex<CompanionBoardOnlineLiveStatus>,
    stop_requested: Mutex<Option<Arc<AtomicBool>>>,
    bookmarks: Mutex<Option<Arc<crate::backend::recording_bookmarks::live_queue::LiveQueue>>>,
}

impl CompanionBoardOnlineLiveManager {
    pub fn new() -> Self {
        Self {
            status: Mutex::new(CompanionBoardOnlineLiveStatus::default()),
            stop_requested: Mutex::new(None),
            bookmarks: Mutex::new(None),
        }
    }

    fn snapshot(&self) -> Result<CompanionBoardOnlineLiveStatus, String> {
        self.status
            .lock()
            .map(|status| status.clone())
            .map_err(|_| "board onlineLive status lock failed".to_string())
    }

    fn set_status(&self, next: CompanionBoardOnlineLiveStatus) {
        if let Ok(mut status) = self.status.lock() {
            *status = next;
        }
    }

    fn mark_recording_active(&self, recording_id: u32, duration_ms: u32) {
        if let Ok(mut status) = self.status.lock() {
            if status.state != "stopping" {
                status.state = "recording".to_string();
            }
            status.recording_id = Some(recording_id);
            status.duration_ms = u64::from(duration_ms);
        }
    }

    fn request_stop(&self) -> Result<CompanionBoardOnlineLiveStatus, String> {
        let stop = self
            .stop_requested
            .lock()
            .map_err(|_| "board onlineLive stop lock failed".to_string())?
            .clone()
            .ok_or_else(|| "板端在线会议当前没有运行".to_string())?;
        stop.store(true, Ordering::Release);
        let mut status = self
            .status
            .lock()
            .map_err(|_| "board onlineLive status lock failed".to_string())?;
        if matches!(status.state.as_str(), "starting" | "recording") {
            status.state = "stopping".to_string();
        }
        Ok(status.clone())
    }
}

fn ensure_board_online_live_start_is_idle(snapshot: &CompanionV1Snapshot) -> Result<(), String> {
    if snapshot.host.persistence.status != "ready" {
        return Err("会议库尚未保存或恢复，请先重试保存，再启动板端在线会议".into());
    }
    if snapshot.device.recording
        || snapshot.meeting.active
        || snapshot
            .host
            .sessions
            .iter()
            .any(|session| session.status == "recording")
    {
        return Err("已有录音正在进行；请先结束当前录音，再启动板端在线会议".to_string());
    }
    Ok(())
}

#[tauri::command]
pub async fn get_companion_v1_snapshot(
    coordinator: CompanionCoordinatorState<'_>,
) -> Result<CompanionV1Snapshot, String> {
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move||coordinator.snapshot()).await
        .map_err(|_|"读取 Companion 状态任务未完成，请重试。".to_string())?
}

#[tauri::command]
pub async fn apply_companion_v1_control(
    coordinator: CompanionCoordinatorState<'_>,
    request: CompanionV1ControlRequest,
) -> Result<CompanionV1Snapshot, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || apply_renderer_control(&coordinator, request))
        .await
        .map_err(|err| format!("Companion control task failed: {err}"))?
}

// These commands must remain independent of the coordinator workflow lock:
// the operation they pause can be awaiting a BLE notification under that lock.
#[tauri::command]
pub fn get_companion_recording_sync_status() -> Result<crate::backend::recording_sync::Status, String> {
    crate::backend::recording_sync::status()
}

#[tauri::command]
pub fn pause_companion_recording_sync(job_id: String) -> Result<bool, String> {
    crate::backend::recording_sync::pause(&job_id)
}

fn apply_renderer_control(
    coordinator: &CompanionCoordinator,
    request: CompanionV1ControlRequest,
) -> Result<CompanionV1Snapshot, String> {
    // Only native capture/import/sync code may establish a retained audio source.
    // Otherwise a renderer could seed an arbitrary path and later obtain an asset grant.
    if request.audio_path.is_some() || request.audio_bytes.is_some() {
        return Err("音频来源由录音和同步流程确定，不能从界面指定文件路径或大小。".to_string());
    }
    coordinator.apply_control(request)
}

fn recording_loss_message(info: &crate::backend::recording_discard::RecordingLossInfo) -> String {
    let started = if info.started_at_unix_seconds == 0 { "设备尚未校时".into() } else {
        chrono::DateTime::from_timestamp(i64::from(info.started_at_unix_seconds), 0)
            .map(|time| time.with_timezone(&chrono::Local).format("%Y-%m-%d %H:%M:%S %:z").to_string())
            .unwrap_or_else(|| "时间未知".into())
    };
    let seconds = u64::from(info.duration_ms).div_ceil(1000);
    format!("最旧尚未确认完整同步的设备录音 #{}\n录制时间：{}\n时长：{} 分 {} 秒\n原音：{:.1} KiB；可释放：{:.1} KiB\n当前请求：{} 分 {} 秒；释放后连续可录约 {} 分 {} 秒\n\n建议先同步录音。继续后，这一条设备原音将永久删除，不能撤销；其它录音保留，不会自动开始新录音。若仍不足，需要重新查看下一条并单独确认。\n\n确认仅在本次连接内短暂有效，过期后需重新查看具体录音。",
        info.recording_id, started, seconds / 60, seconds % 60,
        f64::from(info.encoded_bytes) / 1024.0, f64::from(info.releasable_bytes) / 1024.0,
        info.requested_seconds / 60, info.requested_seconds % 60,
        info.available_after_seconds / 60, info.available_after_seconds % 60)
}

#[tauri::command]
pub async fn discard_oldest_companion_recording(
    app: AppHandle, coordinator: CompanionCoordinatorState<'_>, required_seconds: u16,
) -> Result<crate::backend::recording_discard::RecordingDiscardReport, String> {
    if required_seconds == 0 { return Err("请填写有效录音时长后再查看可释放空间。".into()); }
    let coordinator = coordinator.inner().clone();
    // The renderer supplies only the desired budget. Identity, loss details,
    // capability and confirmation proof come from the real device/backend.
    tauri::async_runtime::spawn_blocking(move || {
        coordinator.discard_oldest_recording(required_seconds, |info| {
            app.dialog().message(recording_loss_message(info)).title("确认删除这一条设备录音")
                .kind(MessageDialogKind::Warning)
                .buttons(MessageDialogButtons::OkCancelCustom("删除这条录音".into(), "取消".into()))
                .blocking_show()
        })
    }).await.map_err(|error| format!("设备录音删除任务未完成，请核对设备当前状态：{error}"))?
}

#[tauri::command]
pub async fn export_companion_audio(
    app: AppHandle,
    coordinator: CompanionCoordinatorState<'_>,
    session_id: String,
) -> Result<Option<CompanionMeetingExportResult>, String> {
    let lease = coordinator.begin_audio_export()?;
    let (original, name) = crate::backend::audio_export::source(&coordinator.snapshot()?, &session_id)?;
    let destination = app.dialog().file().add_filter("原始录音 WAV", &["wav"])
        .set_file_name(&name).blocking_save_file();
    let Some(destination) = destination else { return Ok(None); };
    let destination = destination.simplified().into_path().map_err(|e| e.to_string())?;
    // Recheck the stable session identity after the user finishes the dialog.
    let snapshot = coordinator.snapshot()?;
    if crate::backend::audio_export::source(&snapshot, &session_id)?.0 != original {
        return Err("这场会议的原音已变化，请重新选择保存。".into());
    }
    let path = destination.clone();
    let bytes = tauri::async_runtime::spawn_blocking(move || {
        let _lease = lease;
        crate::backend::audio_export::export(&snapshot, &session_id, &path)
    }).await.map_err(|e| format!("原音保存任务未完成：{e}"))??;
    Ok(Some(CompanionMeetingExportResult { path: destination.to_string_lossy().into(), bytes, warning: None }))
}

#[tauri::command]
pub async fn export_companion_meeting(
    app: AppHandle,
    coordinator: CompanionCoordinatorState<'_>,
    request: CompanionMeetingExportRequest,
) -> Result<Option<CompanionMeetingExportResult>, String> {
    let snapshot = coordinator.snapshot()?;
    let session = snapshot
        .host
        .sessions
        .iter()
        .find(|session| session.id == request.session_id)
        .cloned()
        .ok_or_else(|| format!("meeting export target {} is missing", request.session_id))?;
    let format: crate::backend::export::MeetingExportFormat = request.format.into();
    let prepared = crate::backend::export::prepare_meeting_export(
        &session,
        &request.meeting_mode,
        format,
    )?;

    // The snapshot/session clone above deliberately releases backend state
    // before opening the native dialog or performing disk I/O.
    let destination = app
        .dialog()
        .file()
        .add_filter(prepared.format.dialog_label(), &[prepared.format.extension()])
        .set_file_name(&prepared.suggested_name)
        .blocking_save_file();
    let Some(destination) = destination else {
        return Ok(None);
    };
    let destination = destination
        .simplified()
        .into_path()
        .map_err(|error| format!("selected export destination is not a local file: {error}"))?;
    let bytes = prepared.bytes;
    let write_path = destination.clone();
    let written = tauri::async_runtime::spawn_blocking(move || {
        crate::backend::export::write_atomic(&write_path, &bytes)
    })
    .await
    .map_err(|error| format!("meeting export task failed: {error}"))??;

    let warning = coordinator
        .mark_meeting_exported(&request.session_id, &request.meeting_mode)
        .err()
        .map(|error| {
            format!(
                "文件已保存，但导出记录未能更新：{error}"
            )
        });

    Ok(Some(CompanionMeetingExportResult {
        path: destination.to_string_lossy().to_string(),
        bytes: written,
        warning,
    }))
}

#[tauri::command]
pub fn get_companion_board_online_live_status(
    manager: BoardOnlineLiveManagerState<'_>,
) -> Result<CompanionBoardOnlineLiveStatus, String> {
    manager.snapshot()
}

fn validate_board_online_duration(seconds: Option<u16>) -> Result<u16,String> {
    let seconds=seconds.unwrap_or(2580);
    if !(12..=2580).contains(&seconds) {
        return Err("在线转写时长须为 12 秒至 43 分钟；请修改时长，不会自动截短录音".into());
    }
    Ok(seconds)
}

#[tauri::command]
pub fn start_companion_board_online_live(
    coordinator: CompanionCoordinatorState<'_>,
    manager: BoardOnlineLiveManagerState<'_>,
    request: CompanionBoardOnlineLiveStartRequest,
) -> Result<CompanionBoardOnlineLiveStatus, String> {
    let current = manager.snapshot()?;
    if matches!(
        current.state.as_str(),
        "starting" | "recording" | "stopping" | "finalizing"
    ) {
        return Err("板端在线会议已经在运行".to_string());
    }
    let max_duration_seconds=validate_board_online_duration(request.max_duration_seconds)?;

    let coordinator = coordinator.inner().clone();
    // Hold the shared device gate for the whole board capture/pull/finalize
    // lifecycle. OTA, OOBE, reconnect, and manual device controls must wait.
    let device_operation = coordinator.begin_board_recording_operation()?;
    let manager = manager.inner().clone();
    let snapshot = coordinator.snapshot()?;
    // The operation lease is already held, so a concurrent device action cannot
    // invalidate this final state check before the session and worker are born.
    // Reject every recording source here to preserve its active session and
    // capture process unchanged.
    ensure_board_online_live_start_is_idle(&snapshot)?;
    let device_id = request
        .device_id
        .clone()
        .or(snapshot.device.device_id.clone())
        .filter(|value| !value.trim().is_empty());
    let now_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    let session_id = format!("board-online-{now_ms}");
    let title = request
        .title
        .clone()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "Companion 板端在线会议".to_string());
    let prepared = coordinator.apply_control(CompanionV1ControlRequest {
        action: CompanionV1ControlAction::MeetingStart,
        ble_name: None,
        session_id: Some(session_id.clone()),
        prompt_id: None,
        title: Some(title),
        transcript_text: None,
        meeting_mode: Some("onlineLive".to_string()),
        audio_path: Some(format!("board://online/{session_id}")),
        audio_bytes: Some(0),
        device_id: device_id.clone(),
        duration_ms: Some(0),
    })?;
    if prepared.host.persistence.status != "ready" {
        let reason = "未能保存会议启动记录，设备尚未开始录音；请重试保存后重新开始。";
        let _ = coordinator.fail_board_online_live(&session_id, reason);
        return Err(reason.into());
    }

    let stop_requested = Arc::new(AtomicBool::new(false));
    let bookmark_queue=Arc::new(crate::backend::recording_bookmarks::live_queue::LiveQueue::new(&session_id));
    *manager.bookmarks.lock().map_err(|_| "重点队列暂时不可用。")?=Some(Arc::clone(&bookmark_queue));
    *manager
        .stop_requested
        .lock()
        .map_err(|_| "board onlineLive stop lock failed".to_string())? =
        Some(Arc::clone(&stop_requested));
    manager.set_status(CompanionBoardOnlineLiveStatus {
        state: "starting".to_string(),
        session_id: Some(session_id.clone()),
        device_id: device_id.clone(),
        max_duration_seconds: Some(max_duration_seconds),
        ..CompanionBoardOnlineLiveStatus::default()
    });

    let partial_interval_ms = request.partial_interval_ms.unwrap_or(8_000).max(2_000);
    let disconnect_after_seconds = request.disconnect_after_seconds;
    let worker_manager = Arc::clone(&manager);
    let worker_bookmarks = Arc::clone(&bookmark_queue);
    std::thread::Builder::new()
        .name("companion-board-online-live".to_string())
        .spawn(move || {
            let _device_operation = device_operation;
            let partial_coordinator = Arc::clone(&coordinator);
            let partial_session_id = session_id.clone();
            let consumer: BoardPartialConsumer = Arc::new(move |wav_path: PathBuf| {
                if partial_coordinator.snapshot()?.host.persistence.status != "ready" {
                    return Err("本地会议内容尚未保存，已暂停在线转写；录音仍可停止，请重试保存。".into());
                }
                let transcript = CompanionTranscriptionManager::new()
                    .transcribe_audio_owned(&partial_session_id, &wav_path.to_string_lossy())?;
                if transcript.text.trim().is_empty() {
                    return Err(format!(
                        "ASR returned an empty board partial for {}",
                        wav_path.display()
                    ));
                }
                partial_coordinator
                    .set_board_online_live_partial(&partial_session_id, &transcript.text)?;
                Ok(transcript.text)
            });
            let observer_manager = Arc::clone(&worker_manager);
            let identity_coordinator = Arc::clone(&coordinator);
            let identity_session_id = session_id.clone();
            let recording_observer: BoardRecordingObserver =
                Arc::new(move |actual_device, recording_id, duration_ms, start_ack_at| {
                    identity_coordinator.bind_board_online_live_recording(&identity_session_id, actual_device, recording_id, start_ack_at)?;
                    observer_manager.mark_recording_active(recording_id, duration_ms);
                    Ok(())
                });
            let observer_manager = Arc::clone(&worker_manager);
            let observer: BoardPartialObserver = Arc::new(move |partial| {
                if let Ok(mut status) = observer_manager.status.lock() {
                    if status.state != "stopping" {
                        status.state = "recording".to_string();
                    }
                    status.recording_id = Some(partial.recording_id);
                    status.partial_count = status.partial_count.saturating_add(1);
                    status.duration_ms = u64::from(partial.duration_ms);
                }
            });
            let pending_queue=Arc::clone(&worker_bookmarks);
            let stamp_queue=Arc::clone(&worker_bookmarks);
            let close_queue=Arc::clone(&worker_bookmarks);
            let bookmark_coordinator=Arc::clone(&coordinator);
            let bookmarks=BoardBookmarkObserver {
                pending:Arc::new(move || pending_queue.has_pending()),
                stamp:Arc::new(move |device,id,time| stamp_queue.stamp(device,id,time,|request,stamp|
                    bookmark_coordinator.save_live_bookmark(request,stamp))),
                close:Arc::new(move || close_queue.close()),
            };
            let result = record_board_online_live_controlled(
                device_id.as_deref(),
                max_duration_seconds,
                partial_interval_ms,
                disconnect_after_seconds,
                consumer,
                stop_requested,
                Some(recording_observer),
                Some(observer),
                Some(bookmarks),
            );
            worker_bookmarks.close();
            match result {
                Ok(report) => {
                    if let Ok(mut status) = worker_manager.status.lock() {
                        status.state = "finalizing".to_string();
                        status.recording_id = Some(report.recording_id);
                        status.partial_count = report.partials.len() as u32;
                        status.disconnect_resume = report.disconnect_resume;
                        status.final_recording_path = (!report.final_recording_path.is_empty()).then(|| report.final_recording_path.clone());
                    }
                    match coordinator.complete_board_online_live(&session_id, &report) {
                        Ok(snapshot) => {
                            let completed_session = snapshot
                                .host
                                .sessions
                                .iter()
                                .find(|session| session.id == session_id);
                            let duration_ms = completed_session
                                .map(|session| session.duration_ms)
                                .unwrap_or(0);
                            let saved = snapshot.host.persistence.status == "ready";
                            let minutes_ready = saved && completed_session
                                .map(|session| session.status == "minutesReady")
                                .unwrap_or(false);
                            worker_manager.set_status(CompanionBoardOnlineLiveStatus {
                                state: if minutes_ready {
                                    "completed".to_string()
                                } else {
                                    "pending".to_string()
                                },
                                session_id: Some(session_id),
                                device_id: Some(report.device_id),
                                recording_id: Some(report.recording_id),
                                partial_count: report.partials.len() as u32,
                                duration_ms,
                                max_duration_seconds: Some(max_duration_seconds),
                                disconnect_resume: report.disconnect_resume,
                                final_recording_path: (!report.final_recording_path.is_empty()).then_some(report.final_recording_path),
                                error: if !saved {
                                    snapshot.host.persistence.message.clone()
                                } else if report.sync_paused {
                                    Some(crate::backend::recording_sync::PAUSED.into())
                                } else if minutes_ready {
                                    None
                                } else {
                                    Some(
                                        "录音已安全保存；当前无可用 ASR，联网后点“转写”继续消费"
                                            .to_string(),
                                    )
                                },
                            });
                        }
                        Err(err) => {
                            let _ = coordinator.fail_board_online_live(&session_id, &err);
                            worker_manager.set_status(CompanionBoardOnlineLiveStatus {
                                state: "failed".to_string(),
                                session_id: Some(session_id),
                                device_id: Some(report.device_id),
                                recording_id: Some(report.recording_id),
                                partial_count: report.partials.len() as u32,
                                duration_ms: 0,
                                max_duration_seconds: Some(max_duration_seconds),
                                disconnect_resume: report.disconnect_resume,
                                final_recording_path: Some(report.final_recording_path),
                                error: Some(err),
                            });
                        }
                    }
                }
                Err(err) => {
                    let _ = coordinator.fail_board_online_live(&session_id, &err);
                    let mut status = worker_manager.snapshot().unwrap_or_default();
                    status.state = "failed".to_string();
                    status.error = Some(err);
                    worker_manager.set_status(status);
                }
            }
            if let Ok(mut stop) = worker_manager.stop_requested.lock() {
                *stop = None;
            }
            if let Ok(mut bookmarks)=worker_manager.bookmarks.lock() { *bookmarks=None; }
        })
        .map_err(|err| { bookmark_queue.close(); format!("启动板端在线会议线程失败：{err}") })?;

    manager.snapshot()
}

#[tauri::command]
pub fn stop_companion_board_online_live(
    manager: BoardOnlineLiveManagerState<'_>,
) -> Result<CompanionBoardOnlineLiveStatus, String> {
    manager.request_stop()
}

#[tauri::command]
pub fn get_companion_backend_capabilities(
    coordinator: CompanionCoordinatorState<'_>,
) -> CompanionBackendCapabilities {
    coordinator.backend_capabilities()
}

#[tauri::command]
pub fn get_companion_ble_bridge_status(
    coordinator: CompanionCoordinatorState<'_>,
) -> CompanionBleBridgeStatus {
    coordinator.ble_bridge_status()
}

#[tauri::command]
pub async fn transfer_companion_firmware_ota(
    coordinator: CompanionCoordinatorState<'_>,
    request: CompanionFirmwareOtaRequest,
) -> Result<CompanionFirmwareOtaReport, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || coordinator.transfer_firmware_ota(request))
        .await
        .map_err(|err| format!("Companion OTA task failed: {err}"))?
}

/// Host-only validation of firmware or resource OTA packages (no BLE).
#[tauri::command]
pub fn validate_companion_ota_package(
    coordinator: CompanionCoordinatorState<'_>,
    request: CompanionFirmwareOtaRequest,
) -> Result<CompanionOtaPackageValidation, String> {
    coordinator.validate_ota_package(request)
}

#[tauri::command]
pub fn get_companion_product_settings() -> CompanionProductSettingsPublic {
    product_settings::public_report()
}

/// Save product settings. Empty secret fields keep previous on-disk values.
#[tauri::command]
pub fn save_companion_product_settings(
    coordinator: CompanionCoordinatorState<'_>,
    settings: CompanionProductSettingsPatch,
) -> Result<CompanionProductSettingsPublic, String> {
    coordinator.save_product_settings(settings)
}

#[cfg(test)]
mod board_online_live_tests {
    use super::*;
    #[test]
    fn loss_prompt_identifies_one_original_and_never_implies_it_was_synced() {
        let info = crate::backend::recording_discard::RecordingLossInfo {
            recording_id: 42, started_at_unix_seconds: 0, duration_ms: 61_000,
            encoded_bytes: 12_345, releasable_bytes: 16_384,
            available_after_seconds: 900, requested_seconds: 1800,
        };
        let text = recording_loss_message(&info);
        for required in ["#42", "设备尚未校时", "1 分 1 秒", "16.0 KiB", "30 分 0 秒",
                         "15 分 0 秒", "永久删除", "其它录音保留", "不会自动开始新录音"] {
            assert!(text.contains(required), "missing {required}");
        }
        assert!(!text.contains("已经同步"));
    }
    #[test]
    fn online_duration_is_rejected_instead_of_silently_clamped() {
        assert_eq!(validate_board_online_duration(Some(1800)).unwrap(),1800);
        assert_eq!(validate_board_online_duration(None).unwrap(),2580);
        assert!(validate_board_online_duration(Some(2700)).is_err());
        assert!(validate_board_online_duration(Some(0)).is_err());
    }

    #[test]
    fn renderer_cannot_seed_a_retained_audio_path_for_later_playback() {
        let coordinator = CompanionCoordinator::new_fixture();
        let before = coordinator.snapshot().expect("snapshot");
        for action in ["meetingStart", "meetingStop", "deviceSyncRecordings",
            "meetingImportTranscript", "meetingTranscribeAudio"] {
            for field in ["audioPath", "audioBytes"] {
                let mut payload = serde_json::json!({
                    "action": action,
                    "sessionId": "renderer-injected-audio",
                    "title": "Untrusted audio source"
                });
                payload[field] = if field == "audioPath" {
                    serde_json::json!("C:/private/unrelated.wav")
                } else {
                    serde_json::json!(44)
                };
                let request = serde_json::from_value(payload).expect("renderer request");
                let error = apply_renderer_control(&coordinator, request).expect_err("reject source");
                assert!(error.contains("音频来源"));
                let after = coordinator.snapshot().expect("unchanged snapshot");
                assert_eq!(after.host.sessions.len(), before.host.sessions.len());
                assert_eq!(after.host.active_session_id, before.host.active_session_id);
                assert_eq!(after.device.recording, before.device.recording);
                assert_eq!(after.meeting.active, before.meeting.active);
                assert!(crate::backend::meeting_workspace::local_audio_path(
                    &after, "renderer-injected-audio"
                ).is_err());
            }
        }
    }

    #[test]
    fn board_online_live_status_defaults_to_idle() {
        let manager = CompanionBoardOnlineLiveManager::new();
        let status = manager.snapshot().expect("status");
        assert_eq!(status.state, "idle");
        assert_eq!(status.partial_count, 0);
        assert!(status.session_id.is_none());
    }

    #[test]
    fn board_online_live_stop_is_explicit_and_idempotent_at_the_signal() {
        let manager = CompanionBoardOnlineLiveManager::new();
        let signal = Arc::new(AtomicBool::new(false));
        *manager.stop_requested.lock().expect("stop lock") = Some(Arc::clone(&signal));
        manager.set_status(CompanionBoardOnlineLiveStatus {
            state: "recording".to_string(),
            session_id: Some("board-online-test".to_string()),
            ..CompanionBoardOnlineLiveStatus::default()
        });

        let stopped = manager.request_stop().expect("stop request");
        assert_eq!(stopped.state, "stopping");
        assert!(signal.load(Ordering::Acquire));
        let stopped_again = manager.request_stop().expect("second stop request");
        assert_eq!(stopped_again.state, "stopping");
    }

    #[test]
    fn board_online_live_stop_without_a_worker_is_rejected() {
        let manager = CompanionBoardOnlineLiveManager::new();
        assert!(manager.request_stop().is_err());
    }

    #[test]
    fn board_recording_becomes_active_before_asr_partial_finishes() {
        let manager = CompanionBoardOnlineLiveManager::new();
        manager.set_status(CompanionBoardOnlineLiveStatus {
            state: "starting".to_string(),
            ..CompanionBoardOnlineLiveStatus::default()
        });

        manager.mark_recording_active(37, 480);

        let status = manager.snapshot().expect("status");
        assert_eq!(status.state, "recording");
        assert_eq!(status.recording_id, Some(37));
        assert_eq!(status.duration_ms, 480);
        assert_eq!(status.partial_count, 0);
    }

    #[test]
    fn board_online_live_start_boundary_rejects_every_recording_source_and_allows_idle() {
        let idle = crate::companion_v1::fixture_snapshot();
        assert!(ensure_board_online_live_start_is_idle(&idle).is_ok());
        for status in ["blocked", "recovered", "unsaved"] {
            let mut uncommitted = idle.clone();
            uncommitted.host.persistence.status = status.into();
            assert!(ensure_board_online_live_start_is_idle(&uncommitted).is_err());
        }

        let mut device_recording = idle.clone();
        device_recording.device.recording = true;
        assert!(ensure_board_online_live_start_is_idle(&device_recording).is_err());

        let mut active_meeting = idle.clone();
        active_meeting.meeting.active = true;
        active_meeting.host.active_session_id = Some("existing-active".to_string());
        let active_id = active_meeting.host.active_session_id.clone();
        assert!(ensure_board_online_live_start_is_idle(&active_meeting).is_err());
        assert_eq!(active_meeting.host.active_session_id, active_id);

        let mut recording_session = idle;
        let request = CompanionV1ControlRequest {
            action: CompanionV1ControlAction::DeviceSyncRecordings,
            ble_name: None,
            session_id: Some("existing-row".to_string()),
            prompt_id: None,
            title: None,
            transcript_text: None,
            meeting_mode: Some("offlineStore".to_string()),
            audio_path: Some("C:/test/existing.wav".to_string()),
            audio_bytes: Some(16),
            device_id: Some("test-device".to_string()),
            duration_ms: Some(1_000),
        };
        let mut session =
            crate::companion_v1::synced_device_session(&recording_session, &request, "test");
        session.status = "recording".to_string();
        recording_session.host.sessions.push(session);
        let session_count = recording_session.host.sessions.len();
        assert!(ensure_board_online_live_start_is_idle(&recording_session).is_err());
        assert_eq!(recording_session.host.sessions.len(), session_count);
        assert_eq!(recording_session.host.sessions[0].status, "recording");
    }
}
