//! Tauri command surface for Companion Type.

use std::sync::Arc;

use tauri::State;

use crate::backend::{
    CompanionBackendCapabilities, CompanionBleBridgeStatus, CompanionFirmwareOtaReport,
    CompanionFirmwareOtaRequest,
};
use crate::companion_v1::{CompanionV1ControlRequest, CompanionV1Snapshot};
use crate::coordinator::CompanionCoordinator;

type CompanionCoordinatorState<'a> = State<'a, Arc<CompanionCoordinator>>;

#[tauri::command]
pub fn get_companion_v1_snapshot(
    coordinator: CompanionCoordinatorState<'_>,
) -> Result<CompanionV1Snapshot, String> {
    coordinator.snapshot()
}

#[tauri::command]
pub async fn apply_companion_v1_control(
    coordinator: CompanionCoordinatorState<'_>,
    request: CompanionV1ControlRequest,
) -> Result<CompanionV1Snapshot, String> {
    let coordinator = coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move || coordinator.apply_control(request))
        .await
        .map_err(|err| format!("Companion control task failed: {err}"))?
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
