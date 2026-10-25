use std::sync::Arc;
use tauri::State;
use crate::{backend::pet_profile,coordinator::CompanionCoordinator};
#[tauri::command]
pub async fn get_companion_pet_profile(coordinator:State<'_,Arc<CompanionCoordinator>>)->Result<pet_profile::View,String>{
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move||pet_profile::get(&coordinator)).await.map_err(|_|"读取宠物档案的任务未完成。".to_string())?
}
#[tauri::command]
pub async fn save_companion_pet_profile(coordinator:State<'_,Arc<CompanionCoordinator>>,profile:pet_profile::Document)->Result<pet_profile::View,String>{
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move||pet_profile::save(&coordinator,profile)).await.map_err(|_|"保存尚未确认，请重新读取。".to_string())?
}
#[tauri::command]
pub async fn cleanup_companion_pet_profile(coordinator:State<'_,Arc<CompanionCoordinator>>)->Result<pet_profile::View,String>{
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move||pet_profile::cleanup(&coordinator)).await.map_err(|_|"旧副本清理尚未确认。".to_string())?
}
#[tauri::command]
pub async fn reset_companion_pet_profile(coordinator:State<'_,Arc<CompanionCoordinator>>,uid:String,generation:u32,confirmed:bool)->Result<pet_profile::View,String>{
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move||pet_profile::reset(&coordinator,uid,generation,confirmed)).await.map_err(|_|"重置尚未确认，请重新读取。".to_string())?
}
