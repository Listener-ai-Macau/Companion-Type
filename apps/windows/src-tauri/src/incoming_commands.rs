//! User-initiated OS delivery. No device, cloud or model operation occurs here.
use crate::{backend::incoming_files as incoming, coordinator::CompanionCoordinator};
use std::{
    path::{Path, PathBuf},
    sync::Arc,
};
#[tauri::command]
pub async fn companion_incoming_files(
    coordinator: tauri::State<'_, Arc<CompanionCoordinator>>,
    action: String,
    request: serde_json::Value,
) -> Result<serde_json::Value, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        #[derive(serde::Deserialize)]
        #[serde(rename_all = "camelCase", deny_unknown_fields)]
        struct Request {
            id: String,
            key: Option<String>,
            library_token: Option<String>,
        }
        match action.as_str() {
            "list" => incoming::list(),
            "remove" => {
                let r: Request = serde_json::from_value(request).map_err(|_| "接收项标识无效。")?;
                incoming::remove(&r.id)
            }
            "import" => {
                let r: Request = serde_json::from_value(request).map_err(|_| "接收目标不完整。")?;
                incoming::import(
                    coordinator,
                    &r.id,
                    r.key.as_deref(),
                    r.library_token.as_deref().ok_or("请重新确认资料库。")?,
                )
            }
            _ => Err("不支持此接收操作。".into()),
        }
    })
    .await
    .map_err(|_| "文件接收尚未确认，请重新读取清单；原资料保留。".to_owned())?
}
#[cfg(windows)]
pub(crate) struct Registration {
    handle: windows::Win32::Foundation::HANDLE,
    pub existing: bool,
}
#[cfg(windows)]
impl Registration {
    pub fn new() -> Result<Self, String> {
        use windows::{
            core::PCWSTR,
            Win32::{
                Foundation::{GetLastError, ERROR_ALREADY_EXISTS},
                System::Threading::CreateMutexW,
            },
        };
        // Isolated/portable libraries retain separate receivers. This does not own
        // or terminate another process, and never runs for a CLI/device command.
        let identity = crate::backend::audio_editing::context_token()?;
        let name = format!("Local\\CompanionIncoming-{identity}")
            .encode_utf16()
            .chain(Some(0))
            .collect::<Vec<_>>();
        let handle = unsafe { CreateMutexW(None, false, PCWSTR(name.as_ptr())) }
            .map_err(|_| "无法建立文件接收入口，请稍后重试。")?;
        let existing = unsafe { GetLastError() } == ERROR_ALREADY_EXISTS;
        Ok(Self { handle, existing })
    }
}
#[cfg(windows)]
impl Drop for Registration {
    fn drop(&mut self) {
        let _ = unsafe { windows::Win32::Foundation::CloseHandle(self.handle) };
    }
}
pub(crate) fn receive(paths: Vec<PathBuf>, cwd: &Path) -> Result<(), String> {
    incoming::receive(paths, cwd)
}
pub(crate) fn error(message: &str) {
    eprintln!("incoming_file_error={message}");
    #[cfg(windows)]
    if std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none()
        && std::env::var("COMPANION_TYPE_BACKGROUND_WINDOW").as_deref() != Ok("1")
    {
        use windows::{
            core::PCWSTR,
            Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK},
        };
        let message = message.encode_utf16().chain(Some(0)).collect::<Vec<_>>();
        let title = "Companion · 文件未接收"
            .encode_utf16()
            .chain(Some(0))
            .collect::<Vec<_>>();
        unsafe {
            MessageBoxW(
                None,
                PCWSTR(message.as_ptr()),
                PCWSTR(title.as_ptr()),
                MB_OK | MB_ICONERROR,
            );
        }
    }
}
