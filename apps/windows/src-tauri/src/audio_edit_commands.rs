//! Desktop edit IPC: only library IDs and sample plans cross the boundary.
use crate::{
    backend::{audio_edit_job as jobs, audio_editing as edit},
    coordinator::CompanionCoordinator,
};
use std::sync::Arc;
pub(crate) fn dispatch(
    coordinator: Arc<CompanionCoordinator>,
    action: &str,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    if serde_json::to_vec(&request)
        .map_err(|e| e.to_string())?
        .len()
        > 256 * 1024
    {
        return Err("编辑请求过大，请分批处理。".into());
    }
    #[derive(serde::Deserialize)]
    #[serde(rename_all = "camelCase", deny_unknown_fields)]
    struct Id {
        id: String,
    }
    #[derive(serde::Deserialize)]
    #[serde(rename_all = "camelCase", deny_unknown_fields)]
    struct Keys {
        keys: Vec<String>,
    }
    #[derive(serde::Deserialize)]
    #[serde(rename_all = "camelCase", deny_unknown_fields)]
    struct Source {
        session_id: String,
        index: Option<usize>,
    }
    match action {
        "context" => Ok(serde_json::json!({"libraryToken":edit::context_token()?})),
        "status" => jobs::status(),
        "dismiss" => {
            let r: Id = serde_json::from_value(request).map_err(|_| "任务标识缺失。")?;
            jobs::dismiss(&r.id)?;
            Ok(serde_json::json!({"dismissed":true}))
        }
        "cancel" => {
            let r: Id = serde_json::from_value(request).map_err(|_| "取消任务标识缺失。")?;
            Ok(serde_json::json!({"cancelled":jobs::cancel(&r.id)?}))
        }
        "start" => jobs::start(
            coordinator,
            serde_json::from_value(request).map_err(|_| "编辑请求格式无效。")?,
        ),
        "retry" => {
            let r: Id = serde_json::from_value(request).map_err(|_| "重试任务标识缺失。")?;
            jobs::retry(coordinator, &r.id)
        }
        "sources" => {
            let r: Keys = serde_json::from_value(request).map_err(|_| "原录音标识无效。")?;
            let _lease = coordinator.begin_audio_edit()?;
            serde_json::to_value(edit::sources(&coordinator.snapshot()?, &r.keys)?)
                .map_err(|e| e.to_string())
        }
        "provenance" | "sourceTarget" => {
            let r: Source = serde_json::from_value(request).map_err(|_| "录音来源请求无效。")?;
            let _lease = coordinator.begin_audio_edit()?;
            let snapshot = coordinator.snapshot()?;
            if action == "sourceTarget" {
                return edit::source_target(
                    &snapshot,
                    &r.session_id,
                    r.index.ok_or("来源序号缺失。")?,
                );
            }
            let row = snapshot
                .host
                .sessions
                .iter()
                .find(|s| s.id == r.session_id)
                .ok_or("这条录音已不存在。")?;
            crate::backend::library_lifecycle::require_available(row)?;
            let provenance = edit::provenance(row)?;
            Ok(serde_json::json!({"available":provenance.is_some(),"provenance":provenance}))
        }
        _ => Err("不支持的录音编辑操作。".into()),
    }
}
#[tauri::command]
pub async fn control_companion_audio_edit(
    coordinator: tauri::State<'_, Arc<CompanionCoordinator>>,
    action: String,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || dispatch(coordinator, &action, request))
        .await
        .map_err(|_| "编辑操作尚未完成，原音保留。")?
}
