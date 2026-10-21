use std::sync::Arc;
use tauri::State;
use crate::{backend::pet_find,coordinator::CompanionCoordinator};

#[tauri::command]
pub async fn control_companion_pet_find(coordinator:State<'_,Arc<CompanionCoordinator>>,request:pet_find::Request)->Result<pet_find::Report,String> {
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move||pet_find::control(&coordinator,request)).await
        .map_err(|_|"寻找任务未返回结果；设备仍按自身时限结束，未确认实际声音。".to_string())?
}
