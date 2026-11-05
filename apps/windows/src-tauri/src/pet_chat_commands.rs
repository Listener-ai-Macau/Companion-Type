use std::sync::Arc;
use tauri::State;
use crate::{backend::pet_chat,coordinator::CompanionCoordinator};
#[tauri::command]
pub fn get_companion_pet_chat()->Result<pet_chat::Status,String>{pet_chat::status()}
#[tauri::command]
pub fn clear_companion_pet_chat()->Result<pet_chat::Status,String>{pet_chat::clear()}
#[tauri::command]
pub fn start_companion_pet_chat(coordinator:State<'_,Arc<CompanionCoordinator>>)->Result<pet_chat::Status,String>{
    pet_chat::begin(coordinator.inner().clone())
}
#[tauri::command]
pub fn finish_companion_pet_chat(request_id:u32,cancel:bool)->Result<pet_chat::Status,String>{
    pet_chat::finish(request_id,cancel)
}
#[tauri::command]
pub async fn display_companion_pet_chat(coordinator:State<'_,Arc<CompanionCoordinator>>,request_id:u32,pixels:Vec<u8>)->Result<pet_chat::Status,String>{
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move||pet_chat::display(&coordinator,request_id,pixels)).await
        .map_err(|_|"字幕显示任务未完成，回复已保留。".to_string())?
}
