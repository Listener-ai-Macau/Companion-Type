use crate::backend::document_context as docs;
use crate::coordinator::CompanionCoordinator;
use std::sync::Arc;
use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;
type CompanionCoordinatorState<'a> = tauri::State<'a, Arc<CompanionCoordinator>>;

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Request {
    session_id: String,
    #[serde(default)]
    revision: u64,
    document_id: Option<String>,
    offset: Option<u64>,
    extraction: Option<docs::Extraction>,
}
#[tauri::command]
pub async fn read_companion_document_context(
    coordinator: CompanionCoordinatorState<'_>,
    action: String,
    request: Request,
) -> Result<serde_json::Value, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        if action == "commit" || action == "remove" {
            let change = if action == "remove" {
                docs::Change::Remove
            } else {
                docs::Change::Commit(request.extraction.ok_or("提取文字尚未准备好。")?)
            };
            let value = coordinator.change_document_context(docs::Request {
                session_id: request.session_id,
                document_id: request.document_id.ok_or("材料标识缺失。")?,
                expected_revision: request.revision,
                change,
            })?;
            return serde_json::to_value(value).map_err(|_| "材料保存结果无法读取。".into());
        }
        let snapshot = coordinator.snapshot()?;
        let row = snapshot
            .host
            .sessions
            .iter()
            .find(|r| r.id == request.session_id)
            .ok_or("这场会议已不存在。")?;
        match action.as_str() {
            "list" => {
                serde_json::to_value(docs::describe(row)?).map_err(|_| "材料目录暂不可读。".into())
            }
            "chunk" => docs::chunk(
                row,
                request.document_id.as_deref().ok_or("材料标识缺失。")?,
                request.revision,
                request.offset.ok_or("材料读取位置缺失。")?,
            ),
            "read" => serde_json::to_value(docs::extraction(
                row,
                request.document_id.as_deref().ok_or("材料标识缺失。")?,
                request.revision,
            )?)
            .map_err(|_| "材料文字暂不可读。".into()),
            _ => Err("不支持的材料操作。".into()),
        }
    })
    .await
    .map_err(|_| "材料处理未完成，原件仍保留。".to_owned())?
}
#[tauri::command]
pub async fn import_companion_document(
    app: AppHandle,
    coordinator: CompanionCoordinatorState<'_>,
    session_id: String,
    document_id: String,
    revision: u64,
) -> Result<Option<docs::View>, String> {
    {
        let snapshot = coordinator.snapshot()?;
        let row = snapshot
            .host
            .sessions
            .iter()
            .find(|r| r.id == session_id)
            .ok_or("这场会议已不存在。")?;
        docs::can_import(row)?;
    }
    let chosen = app
        .dialog()
        .file()
        .add_filter(
            "文档材料（每份最多20MB）",
            &["pdf", "docx", "xlsx", "pptx", "txt", "md", "csv"],
        )
        .blocking_pick_file();
    let Some(chosen) = chosen else {
        return Ok(None);
    };
    let path = chosen.into_path().map_err(|_| "请选择保存在本机的文档。")?;
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        coordinator.change_document_context(docs::Request {
            session_id,
            document_id,
            expected_revision: revision,
            change: docs::Change::Import(path),
        })
    })
    .await
    .map_err(|_| "原件保存未完成，请重新读取材料核对。".to_owned())?
    .map(Some)
}
#[tauri::command]
pub async fn save_companion_document_original(
    app: AppHandle,
    coordinator: CompanionCoordinatorState<'_>,
    session_id: String,
    document_id: String,
    revision: u64,
) -> Result<bool, String> {
    let name = {
        let snapshot = coordinator.snapshot()?;
        let row = snapshot
            .host
            .sessions
            .iter()
            .find(|r| r.id == session_id)
            .ok_or("这场会议已不存在。")?;
        let value = docs::describe(row)?;
        if value.revision != revision {
            return Err("材料已更新，请重新读取。".into());
        }
        value
            .rows
            .iter()
            .find(|r| r.id == document_id)
            .ok_or("这份材料已移除。")?
            .name
            .clone()
    };
    let chosen = app.dialog().file().set_file_name(name).blocking_save_file();
    let Some(chosen) = chosen else {
        return Ok(false);
    };
    let path = chosen
        .simplified()
        .into_path()
        .map_err(|_| "请选择本机保存位置。")?;
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let snapshot = coordinator.snapshot()?;
        let row = snapshot
            .host
            .sessions
            .iter()
            .find(|r| r.id == session_id)
            .ok_or("这场会议已不存在。")?;
        docs::save_original(row, &document_id, revision, &path)?;
        Ok(true)
    })
    .await
    .map_err(|_| "原件另存未完成，请检查保存位置。".to_owned())?
}
