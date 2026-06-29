mod companion_v1;

#[tauri::command]
fn get_companion_v1_snapshot() -> companion_v1::CompanionV1Snapshot {
    companion_v1::fixture_snapshot()
}

#[tauri::command]
fn apply_companion_v1_control(
    request: companion_v1::CompanionV1ControlRequest,
) -> Result<companion_v1::CompanionV1Snapshot, String> {
    companion_v1::apply_fixture_control(request)
}

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_companion_v1_snapshot,
            apply_companion_v1_control
        ])
        .run(tauri::generate_context!())
        .expect("error while running Companion Type");
}

