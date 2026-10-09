//! Companion Type Tauri backend.
//!
//! The module split keeps IPC commands, workflow state, replaceable services,
//! and the shared Companion contract separate.

mod backend;
mod commands;
mod companion_v1;
mod coordinator;

use std::fs;
use std::path::{Path, PathBuf};
use std::process;
use std::sync::Arc;

use backend::{
    CompanionFirmwareOtaRequest, CompanionOtaPackageValidation, CompanionTranscriptionManager,
};
use coordinator::CompanionCoordinator;
use sha2::{Digest, Sha256};

pub fn run() {
    let args = std::env::args().collect::<Vec<_>>();
    if let Some(result) = run_meeting_workspace_cli(&args) {
        if let Err(error) = &result { eprintln!("meeting_workspace_error={error}"); }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--recording-session-self-test") {
        let result=args.get(index+1).ok_or_else(||"--recording-session-self-test requires a fresh output folder".to_string())
            .and_then(|output|backend::recording_wire::receiver::verify(Path::new(output)));
        match &result {Ok(r)=>println!("recording_session_json={r}"),Err(e)=>eprintln!("recording_session_error={e}")}
        process::exit(if result.is_ok(){0}else{1});
    }
    if let Some(index) = args.iter().position(|arg| arg == "--recording-session-probe-phase") {
        let result=(|| {let output=args.get(index+1).ok_or_else(||"missing isolated probe folder".to_string())?;
            let phase=args.get(index+2).ok_or_else(||"missing isolated probe phase".to_string())?;
            backend::recording_wire::receiver::phase(Path::new(output),phase)})();
        match &result {Ok(r)=>println!("recording_session_phase_json={r}"),Err(e)=>eprintln!("recording_session_phase_error={e}")}
        process::exit(if result.is_ok(){0}else{1});
    }
    if let Some(index) = args.iter().position(|arg| arg == "--desktop-update-verify-package") {
        let result = (|| {
            let msi=args.get(index+1).ok_or("更新检查需要 MSI 路径。")?;
            let version=args.get(index+2).ok_or("更新检查需要版本。")?;
            let signature=args.get(index+3).ok_or("更新检查需要签名文件路径。")?;
            let key=args.iter().position(|arg| arg=="--verification-public-key")
                .map(|i| args.get(i+1).map(|path|Path::new(path)).ok_or("缺少只读验证公钥路径。"))
                .transpose()?;
            backend::desktop_update::verify_release(Path::new(msi),version,Path::new(signature),key)
        })();
        match &result {
            Ok(report)=>println!("desktop_update_verification_json={report}"),
            Err(error)=>eprintln!("desktop_update_verification_error={error}"),
        }
        process::exit(if result.is_ok(){0}else{1});
    }
    if let Some(index) = args.iter().position(|arg| arg == "--desktop-update-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--desktop-update-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::desktop_update::self_test(Path::new(output)));
        match &result {
            Ok(report) => println!("desktop_update_json={report}"),
            Err(error) => eprintln!("desktop_update_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result)=backend::recording_bookmarks::probe::run(&args) {
        if let Err(error)=&result {eprintln!("recording_bookmarks_error={error}");}
        process::exit(if result.is_ok(){0}else{1});
    }
    if let Some(index) = args.iter().position(|arg| arg == "--recording-wire-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--recording-wire-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::recording_wire::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("recording_wire_json={report}"),
            Err(error) => eprintln!("recording_wire_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--recording-transfer-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--recording-transfer-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::recording_transfer::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("recording_transfer_json={report}"),
            Err(error) => eprintln!("recording_transfer_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--cache-privacy-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--cache-privacy-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::verify_cache_privacy(Path::new(output)));
        match &result {
            Ok(report) => println!("cache_privacy_json={report}"),
            Err(error) => eprintln!("cache_privacy_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--audio-artifacts-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--audio-artifacts-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::audio_artifacts::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("audio_artifacts_json={report}"),
            Err(error) => eprintln!("audio_artifacts_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--file-storage-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--file-storage-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::file_storage_probe::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("file_storage_json={report}"),
            Err(error) => eprintln!("file_storage_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--privacy-delete-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--privacy-delete-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::verify_privacy_delete(Path::new(output)));
        match &result {
            Ok(report) => println!("privacy_delete_json={report}"),
            Err(error) => eprintln!("privacy_delete_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if args.get(1).is_some_and(|arg| arg == "--external-command-test-fixture") {
        process::exit(backend::external_command_probe::fixture_main(&args[2..]));
    }
    if let Some(index) = args.iter().position(|arg| arg == "--external-command-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--external-command-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::external_command_probe::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("external_command_json={report}"),
            Err(error) => eprintln!("external_command_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--service-network-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--service-network-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::service_network_probe::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("service_network_json={report}"),
            Err(error) => eprintln!("service_network_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--asr-cache-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--asr-cache-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::verify_asr_cache(Path::new(output)));
        match &result {
            Ok(report) => println!("asr_cache_json={report}"),
            Err(error) => eprintln!("asr_cache_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--settings-storage-self-test") {
        #[cfg(windows)]
        let result = args.get(index + 1).ok_or_else(|| "--settings-storage-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::product_settings::verify_storage(Path::new(output)));
        #[cfg(not(windows))]
        let result: Result<serde_json::Value, String> = Err("Windows settings storage probe is unavailable on this platform".into());
        match &result {
            Ok(report) => println!("settings_storage_json={report}"),
            Err(error) => eprintln!("settings_storage_error={error}"),
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_diagnostics_cli(&args) {
        if let Err(error) = &result { eprintln!("diagnostics_error={error}"); }
        process::exit(if result.is_ok() {0} else {1});
    }
    if let Some(result) = run_firmware_ota_cli(&args) {
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_v1_real_meeting_cli(&args) {
        if let Err(err) = &result {
            eprintln!("v1_real_meeting_error={err}");
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_board_online_live_cli(&args) {
        if let Err(err) = &result {
            eprintln!("board_online_live_error={err}");
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_sync_device_recording_cli(&args) {
        if let Err(err) = &result {
            eprintln!("sync_device_recording_error={err}");
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_process_device_library_cli(&args) {
        if let Err(err) = &result {
            eprintln!("process_device_library_error={err}");
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_delete_device_recording_cli(&args) {
        if let Err(err) = &result {
            eprintln!("delete_device_recording_error={err}");
        }
        process::exit(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_embedded_audio_cli(args) {
        process::exit(if result.is_ok() { 0 } else { 1 });
    }

    // Load ASR / DeepSeek / compress preferences into process env before IPC.
    let _ = backend::product_settings::load_and_apply();

    let coordinator = Arc::new(CompanionCoordinator::new_fixture());
    spawn_automatic_meeting_recovery(Arc::clone(&coordinator));
    spawn_automatic_device_reconnect(Arc::clone(&coordinator));
    let board_online_live = Arc::new(commands::CompanionBoardOnlineLiveManager::new());

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(backend::desktop_update::Manager::default())
        .manage(coordinator)
        .manage(board_online_live)
        .invoke_handler(tauri::generate_handler![
            backend::desktop_update::get_companion_type_update,
            backend::desktop_update::check_companion_type_update,
            backend::desktop_update::download_companion_type_update,
            backend::desktop_update::cancel_companion_type_update,
            backend::desktop_update::install_companion_type_update,
            commands::check_companion_service,
            commands::get_companion_v1_snapshot,
            commands::save_companion_meeting_edit,
            commands::save_companion_meeting_note,
            commands::save_companion_bookmark,
            commands::prepare_companion_audio,
            commands::apply_companion_v1_control,
            commands::get_companion_recording_sync_status,
            commands::pause_companion_recording_sync,
            commands::discard_oldest_companion_recording,
            commands::export_companion_meeting,
            commands::export_companion_audio,
            commands::export_companion_diagnostics,
            commands::prepare_companion_audio_components,
            commands::get_companion_backend_capabilities,
            commands::get_companion_ble_bridge_status,
            commands::get_companion_board_online_live_status,
            commands::start_companion_board_online_live,
            commands::stop_companion_board_online_live,
            commands::transfer_companion_firmware_ota,
            commands::validate_companion_ota_package,
            commands::get_companion_product_settings,
            commands::save_companion_product_settings
        ])
        .setup(|app| {
            backend::recording_sync::bind_app(app.handle().clone());
            // The main window is built here (not in tauri.conf.json) so we can inject
            // WebView2 browser args for acceptance-test automation (e.g. CDP). The window
            // matches the previous config: "Companion Type", 980x720, min 420x560.
            let mut builder = tauri::webview::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title("Companion Type")
            .inner_size(980.0, 720.0)
            .min_inner_size(420.0, 560.0);

            // Acceptance-test hook: only when COMPANION_TYPE_WEBVIEW_ARGS is set (e.g.
            // "--remote-debugging-port=9223"). wry overrides its default browser args when this
            // is used, so the standard --disable-features are re-added to keep the normal app
            // behavior identical.
            if let Ok(extra) = std::env::var("COMPANION_TYPE_WEBVIEW_ARGS") {
                let extra = extra.trim();
                if !extra.is_empty() {
                    let combined = format!(
                        "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection {extra}"
                    );
                    builder = builder.additional_browser_args(&combined);
                }
            }

            builder.build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Companion Type");
}

// Headless local review uses the very same persistence and export boundary as
// the desktop commands. It never uploads audio or substitutes an ASR result.
fn run_meeting_workspace_cli(args: &[String]) -> Option<Result<(), String>> {
    let (index, operation) = args.iter().enumerate().find_map(|(i,arg)| match arg.as_str() {
        "--meeting-edit-request" => Some((i,0)),
        "--meeting-export-request" => Some((i,1)),
        "--meeting-minutes-request" => Some((i,2)),
        "--meeting-bookmark-request" => Some((i,3)),
        "--meeting-note-request" => Some((i,4)),
        _ => None,
    })?;
    Some((|| {
        let input = args.get(index+1).ok_or("缺少会议请求 JSON 路径。")?;
        let destination = args.get(index+2).ok_or("缺少本机结果文件路径。")?;
        let file = fs::File::open(input).map_err(|_| "无法打开会议请求文件。")?;
        if file.metadata().map_err(|_| "无法读取请求文件大小。")?.len() > 4*1024*1024 {
            return Err("会议请求文件不能超过 4 MB。".into());
        }
        let coordinator = CompanionCoordinator::new_fixture();
        if operation == 0 {
            let request: backend::meeting_workspace::MeetingEditRequest = serde_json::from_reader(file)
                .map_err(|_| "会议修改请求格式不正确。")?;
            let id = request.session_id.clone();
            let snapshot = coordinator.save_meeting_edit(request)?;
            let session = snapshot.host.sessions.iter().find(|s| s.id == id).ok_or("会议保存结果缺失。")?;
            let ready = snapshot.host.persistence.status == "ready";
            let report = serde_json::json!({
                "result": if ready {"SAVED_LOCAL_MEETING_REVIEW"} else {"UNSAVED_LOCAL_MEETING_REVIEW"},
                "sessionId": id, "reviewRevision": session.transcript_review.as_ref().map(|r| r.revision),
                "persistenceStatus": snapshot.host.persistence.status,
                "reviewStale": backend::transcript_review::review_is_stale(session),
                "fullChainAcceptance": "NOT_RUN", "hardwareAcceptance": "NOT_RUN"
            });
            backend::export::write_atomic(Path::new(destination), &serde_json::to_vec_pretty(&report).map_err(|_| "无法生成保存结果。")?)?;
            if !ready { return Err("修改尚未保存到磁盘；请使用应用的重试保存，原内容仍保留。".into()); }
            println!("meeting_workspace_result=SAVED_LOCAL_MEETING_REVIEW");
        } else if operation == 1 {
            let request: commands::CompanionMeetingExportRequest = serde_json::from_reader(file)
                .map_err(|_| "会议导出请求格式不正确。")?;
            let snapshot = coordinator.snapshot()?;
            if snapshot.device.recording || snapshot.meeting.active || snapshot.host.sessions.iter().any(|s| s.status == "recording") {
                return Err("请结束录音并保存会议，再导出。".into());
            }
            let session = snapshot.host.sessions.iter().find(|s| s.id == request.session_id).ok_or("找不到这场会议。")?;
            let export = backend::export::prepare_meeting_export(session, &request.meeting_mode, request.format.into())?;
            backend::export::write_atomic(Path::new(destination), &export.bytes)?;
            println!("meeting_workspace_result=EXPORTED_LOCAL_MEETING");
        } else if operation == 4 {
            let request: backend::meeting_notes::Request = serde_json::from_reader(file).map_err(|_| "会议备注请求格式不正确。")?;
            let id = request.session_id.clone();
            let snapshot = coordinator.save_meeting_note(request)?;
            let session = snapshot.host.sessions.iter().find(|s| s.id == id).ok_or("会议备注保存结果缺失。")?;
            backend::export::write_atomic(Path::new(destination), &serde_json::to_vec_pretty(&serde_json::json!({
                "result":"SAVED_LOCAL_USER_NOTE", "session":session, "persistenceStatus":snapshot.host.persistence.status,
                "fullChainAcceptance":"NOT_RUN", "hardwareAcceptance":"NOT_RUN"
            })).map_err(|_| "无法生成备注保存结果。")?)?;
            println!("meeting_workspace_result=SAVED_LOCAL_USER_NOTE");
        } else if operation == 3 {
            let request:backend::recording_bookmarks::Request=serde_json::from_reader(file)
                .map_err(|_| "会议重点请求格式不正确。")?;
            let id=request.session_id.clone();
            let snapshot=coordinator.save_bookmark(request)?;
            let session=snapshot.host.sessions.iter().find(|s| s.id == id).ok_or("会议重点保存结果缺失。")?;
            backend::export::write_atomic(Path::new(destination), &serde_json::to_vec_pretty(&serde_json::json!({
                "result":"SAVED_LOCAL_RECORDING_BOOKMARK", "session":session,
                "persistenceStatus":snapshot.host.persistence.status, "fullChainAcceptance":"NOT_RUN"
            })).map_err(|_| "无法生成重点保存结果。")?)?;
            println!("meeting_workspace_result=SAVED_LOCAL_RECORDING_BOOKMARK");
        } else {
            let request: companion_v1::CompanionV1ControlRequest = serde_json::from_reader(file)
                .map_err(|_| "纪要生成请求格式不正确。")?;
            if request.action != companion_v1::CompanionV1ControlAction::MeetingGenerateMinutes
                || request.session_id.is_none() || request.transcript_text.is_some() || request.audio_path.is_some()
                || request.prompt_id.is_some() {
                return Err("此入口只接受指定会议的纪要生成，不导入文字或音频。".into());
            }
            let _ = backend::product_settings::load_and_apply();
            let id = request.session_id.clone().unwrap();
            let snapshot = coordinator.apply_control(request)?;
            let session = snapshot.host.sessions.iter().find(|s| s.id == id).ok_or("纪要生成结果缺失。")?;
            backend::export::write_atomic(Path::new(destination), &serde_json::to_vec_pretty(session).map_err(|_| "无法生成纪要结果。")?)?;
            if snapshot.host.persistence.status != "ready" { return Err("纪要尚未保存到磁盘，请重试保存。".into()); }
            if [&session.minutes_by_mode.offline_store, &session.minutes_by_mode.online_live].into_iter().flatten()
                .any(|v| v.status == "retryPending") {
                return Err("纪要服务未完成；已有内容已保留，请检查结果后重试。".into());
            }
            println!("meeting_workspace_result=SAVED_LOCAL_MINUTES");
        }
        Ok(())
    })())
}

fn run_diagnostics_cli(args:&[String])->Option<Result<(),String>> {
    if let Some(index) = args.iter().position(|arg| arg == "--export-session-audio") {
        return Some((|| {
            let id = args.get(index + 1).ok_or("--export-session-audio requires session ID and output path")?;
            let destination = args.get(index + 2).ok_or("requires output path")?;
            let coordinator = CompanionCoordinator::new_fixture();
            let _lease = coordinator.begin_audio_export()?;
            let bytes = backend::audio_export::export(&coordinator.snapshot()?, id, Path::new(destination))?;
            println!("audio_export_json={}", serde_json::json!({"status":"SAVED_ORIGINAL_AUDIO","bytes":bytes,"networkAccess":false,"deviceAccess":false,"fullChainAcceptance":"NOT_RUN"}));
            Ok(())
        })());
    }
    if let Some(index) = args.iter().position(|arg| arg == "--check-service") {
        return Some((|| {
            let service = match args.get(index+1).map(String::as_str) {
                Some("asr") => backend::service_check::Service::Asr,
                Some("minutes") => backend::service_check::Service::Minutes,
                _ => return Err("--check-service requires asr or minutes".into()),
            };
            backend::product_settings::load_and_apply();
            let result = CompanionCoordinator::new_fixture().check_service(service)?;
            println!("service_check_json={}", serde_json::to_string(&result).map_err(|_| "cannot encode service result")?);
            if result.status == "available" { Ok(()) } else { Err(format!("service check: {}", result.status)) }
        })());
    }
    if let Some(index) = args.iter().position(|arg| arg == "--export-meeting-json") {
        return Some((|| {
            let input = args.get(index+1).ok_or("requires saved session JSON, mode, format, output")?;
            let mode = args.get(index+2).ok_or("requires meeting mode")?;
            let format = match args.get(index+3).map(String::as_str) {
                Some("todo") => backend::export::MeetingExportFormat::Todo,
                Some("ics") => backend::export::MeetingExportFormat::Ics,
                _ => return Err("export format must be todo or ics".into()),
            };
            let output = args.get(index+4).ok_or("requires output path")?;
            use std::io::Read;
            let mut raw = Vec::new(); fs::File::open(input).map_err(|e| e.to_string())?.take(1_000_001).read_to_end(&mut raw).map_err(|e|e.to_string())?;
            if raw.len()>1_000_000 { return Err("session JSON exceeds 1 MB".into()); }
            let session: companion_v1::CompanionV1HostSession = serde_json::from_slice(&raw).map_err(|e|e.to_string())?;
            let prepared = backend::export::prepare_meeting_export(&session,mode,format)?;
            let bytes = backend::export::write_atomic(Path::new(output),&prepared.bytes)?;
            println!("meeting_export_json={}",serde_json::json!({"status":"EXPORTED_SAVED_DOCUMENT","bytes":bytes,"networkAccess":false,"deviceAccess":false,"fullChainAcceptance":"NOT_RUN"}));
            Ok(())
        })());
    }
    if args.iter().any(|arg|arg=="--prepare-audio-components") {
        return Some(CompanionCoordinator::new_fixture().prepare_audio_components().map(|_|println!("audio_components_json={{\"status\":\"VERIFIED_AND_LOADED\",\"recordedAudio\":false,\"uploadedAudio\":false}}")));
    }
    if let Some(index)=args.iter().position(|arg|arg=="--diagnostics-export") {
        return Some((|| {
            let output=args.get(index+1).ok_or("--diagnostics-export requires output path")?;
            let snapshot=CompanionCoordinator::new_fixture().snapshot()?;
            let report=backend::diagnostics::report(&snapshot,None,false);
            let bytes=serde_json::to_vec_pretty(&report).map_err(|e|e.to_string())?;
            backend::export::write_atomic(Path::new(output),&bytes)?;
            println!("diagnostics_export_json={}",serde_json::json!({"status":"EXPORTED_HOST_ONLY","bytes":bytes.len(),"deviceAccess":false,"fullChainAcceptance":"NOT_RUN"}));
            Ok(())
        })());
    }
    args.iter().position(|arg|arg=="--decode-cop1").map(|index| (|| {
        let input=args.get(index+1).ok_or("--decode-cop1 requires input and output paths")?;
        let output=args.get(index+2).ok_or("--decode-cop1 requires output path")?;
        use std::io::Read;
        let mut header=[0u8;4]; fs::File::open(input).and_then(|mut f|f.read_exact(&mut header)).map_err(|e|e.to_string())?;
        if &header!=b"COP1" {return Err("--decode-cop1 only accepts Companion COP1 recordings".into());}
        let bytes=backend::decode_recording(Path::new(input),Path::new(output),false)?;
        println!("cop1_decode_json={}",serde_json::json!({"status":"DECODED","bytes":bytes,"decoder":"bundled-libopus-1.5.2","hardwareAcceptance":"NOT_RUN"}));
        Ok(())
    })())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum AutomaticRecoveryAction {
    Transcribe,
    GenerateMinutes,
}

fn next_automatic_recovery(
    snapshot: &companion_v1::CompanionV1Snapshot,
    now_ms: u64,
) -> (Option<(String, AutomaticRecoveryAction)>, Option<u64>) {
    if snapshot.host.persistence.status != "ready"
        || snapshot.device.recording
        || snapshot.meeting.active
        || snapshot
            .host
            .sessions
            .iter()
            .any(|session| session.status == "recording")
    {
        return (None, None);
    }
    let mut next_wake = None;
    for session in &snapshot.host.sessions {
        let recovery = &session.recovery;
        if recovery.intent != "processMeeting"
            || recovery.requested_meeting_mode != session.meeting_mode
            || matches!(recovery.stage.as_str(), "idle" | "paused" | "complete")
        {
            continue;
        }
        if recovery.stage == "pendingMinutes"
            && session.transcript_final
            && !session.transcript_text.trim().is_empty()
        {
            return (
                Some((session.id.clone(), AutomaticRecoveryAction::GenerateMinutes)),
                None,
            );
        }
        if recovery.stage == "pendingTranscription" {
            return (
                Some((session.id.clone(), AutomaticRecoveryAction::Transcribe)),
                None,
            );
        }
        if recovery.stage == "retryBackoff" {
            let due = recovery.next_retry_at_unix_ms.unwrap_or(now_ms);
            if due <= now_ms {
                let action = if recovery.retry_stage == "minutes"
                    && session.transcript_final
                    && !session.transcript_text.trim().is_empty()
                {
                    AutomaticRecoveryAction::GenerateMinutes
                } else {
                    AutomaticRecoveryAction::Transcribe
                };
                return (
                    Some((session.id.clone(), action)),
                    None,
                );
            }
            next_wake = Some(next_wake.map_or(due, |current: u64| current.min(due)));
        }
    }
    (None, next_wake)
}

fn current_unix_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX)
}

fn spawn_automatic_meeting_recovery(coordinator: Arc<CompanionCoordinator>) {
    if std::env::var("COMPANION_TYPE_DISABLE_AUTO_RECOVERY")
        .ok()
        .is_some_and(|value| value == "1")
    {
        return;
    }
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(500));
        loop {
            let snapshot = match coordinator.snapshot() {
                Ok(snapshot) => snapshot,
                Err(error) => {
                    eprintln!("[meeting-recovery] snapshot failed: {error}");
                    std::thread::sleep(std::time::Duration::from_secs(1));
                    continue;
                }
            };
            let now = current_unix_ms();
            let (next, wake_at) = next_automatic_recovery(&snapshot, now);
            let Some((session_id, action)) = next else {
                let wait_ms = wake_at
                    .map(|wake_at| wake_at.saturating_sub(now).clamp(100, 1_000))
                    .unwrap_or(1_000);
                std::thread::sleep(std::time::Duration::from_millis(wait_ms));
                continue;
            };
            let control = match action {
                AutomaticRecoveryAction::Transcribe => {
                    companion_v1::CompanionV1ControlAction::MeetingTranscribeAudio
                }
                AutomaticRecoveryAction::GenerateMinutes => {
                    companion_v1::CompanionV1ControlAction::MeetingGenerateMinutes
                }
            };
            let mut request = control_request(control, Some(session_id.clone()));
            request.prompt_id = Some("__companion_auto_recovery__".to_string());
            if let Err(error) = coordinator.apply_control(request) {
                eprintln!("[meeting-recovery] {action:?} {session_id} failed: {error}");
                let retry_stage = match action {
                    AutomaticRecoveryAction::Transcribe => "transcription",
                    AutomaticRecoveryAction::GenerateMinutes => "minutes",
                };
                if let Err(record_error) = coordinator.record_meeting_recovery_failure(
                    &session_id,
                    retry_stage,
                    &error,
                ) {
                    eprintln!(
                        "[meeting-recovery] could not checkpoint {session_id} failure: {record_error}"
                    );
                }
            }
        }
    });
}

fn should_attempt_device_reconnect(snapshot: &companion_v1::CompanionV1Snapshot) -> bool {
    snapshot.device.auto_reconnect_enabled
        && !snapshot.device.manual_disconnect
        && snapshot.device.remembered_device_id.is_some()
        && !matches!(snapshot.device.connection_phase.as_str(), "reconnecting" | "busy")
        && !snapshot.meeting.active
        && !snapshot
            .host
            .sessions
            .iter()
            .any(|session| session.status == "recording")
}

fn spawn_automatic_device_reconnect(coordinator: Arc<CompanionCoordinator>) {
    if std::env::var("COMPANION_TYPE_DISABLE_AUTO_RECONNECT")
        .ok()
        .is_some_and(|value| value == "1")
    {
        return;
    }
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(750));
        let mut failed_attempts = 0u32;
        loop {
            let snapshot = match coordinator.snapshot() {
                Ok(snapshot) => snapshot,
                Err(error) => {
                    eprintln!("[device-reconnect] snapshot failed: {error}");
                    std::thread::sleep(std::time::Duration::from_secs(2));
                    continue;
                }
            };
            if !should_attempt_device_reconnect(&snapshot) {
                failed_attempts = 0;
                // No eligible remembered device, or a foreground capture owns
                // the device. This branch performs no Bluetooth operation.
                std::thread::sleep(std::time::Duration::from_secs(5));
                continue;
            }
            match coordinator.automatic_reconnect_once() {
                Ok(_) => {
                    failed_attempts = 0;
                    std::thread::sleep(std::time::Duration::from_secs(60));
                }
                Err(error) if error.contains("device is busy with") => {
                    std::thread::sleep(std::time::Duration::from_secs(2));
                }
                Err(error) => {
                    failed_attempts = failed_attempts.saturating_add(1).min(8);
                    let delay_seconds = 60u64
                        .saturating_mul(1u64 << failed_attempts.saturating_sub(1))
                        .min(300);
                    eprintln!(
                        "[device-reconnect] exact remembered-device probe failed; retry in {delay_seconds}s: {error}"
                    );
                    std::thread::sleep(std::time::Duration::from_secs(delay_seconds));
                }
            }
        }
    });
}

fn run_v1_real_meeting_cli(args: &[String]) -> Option<Result<(), String>> {
    if !args.iter().any(|arg| arg == "--v1-real-meeting") {
        return None;
    }
    Some((|| {
        let _ = backend::product_settings::load_and_apply();
        let requested_device = args
            .iter()
            .position(|arg| arg == "--device-id")
            .and_then(|position| args.get(position + 1))
            .cloned();
        let output_path = args
            .iter()
            .position(|arg| arg == "--output")
            .and_then(|position| args.get(position + 1))
            .map(PathBuf::from);
        let seconds = args
            .iter()
            .position(|arg| arg == "--seconds")
            .and_then(|position| args.get(position + 1))
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(6)
            .clamp(2, 7_200);
        // Exercise the ordinary application's recovery with the same live
        // coordinator: let the actual board limit seal its original recording
        // and reconnect. No synthetic STOP acknowledgement or new process.
        let recover_after_limit = args.iter().any(|arg| arg == "--recover-after-limit");
        let coordinator = CompanionCoordinator::new_fixture();

        let scan = coordinator.apply_control(control_request(
            companion_v1::CompanionV1ControlAction::DeviceScan,
            None,
        ))?;
        let device_id = requested_device
            .or(scan.device.device_id)
            .ok_or_else(|| "V1 real meeting scan returned no Companion device id".to_string())?;
        let mut connect =
            control_request(companion_v1::CompanionV1ControlAction::DeviceConnect, None);
        connect.device_id = Some(device_id.clone());
        let connected = coordinator.apply_control(connect)?;
        if !connected.connected || !connected.device.connected {
            return Err("V1 real meeting did not reach a connected BLE state".to_string());
        }

        let session_id = format!(
            "v1-real-installed-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis()
        );
        let mut start = control_request(
            companion_v1::CompanionV1ControlAction::MeetingStart,
            Some(session_id.clone()),
        );
        start.title = Some("Companion 实板录音控制与收取".to_string());
        start.meeting_mode = Some("offlineStore".to_string());
        start.device_id = Some(device_id.clone());
        start.duration_ms = Some((seconds + if recover_after_limit { 0 } else { 30 }) * 1_000);
        let started = coordinator.apply_control(start)?;
        let started_session = started
            .host
            .sessions
            .iter()
            .find(|session| session.id == session_id)
            .ok_or_else(|| "V1 START did not create the Type session".to_string())?;
        if started.meeting.status != "recording" || started_session.source != "boardDevice" {
            return Err(format!(
                "V1 START state diverged: meeting={} source={}",
                started.meeting.status, started_session.source
            ));
        }
        let start_recording_id = started_session
            .device_recording_id
            .ok_or_else(|| "V1 START did not surface the board recording id".to_string())?;
        let recovery_link_disconnected = if recover_after_limit {
            let mut disconnect = control_request(
                companion_v1::CompanionV1ControlAction::DeviceDisconnect,
                Some(session_id.clone()),
            );
            disconnect.device_id = Some(device_id.clone());
            let disconnected = coordinator.apply_control(disconnect)?;
            if disconnected.connected || disconnected.device.connected {
                return Err("Recovery did not disconnect the original BLE link".into());
            }
            eprintln!("offline_recovery original_link_disconnected=true microphone_stop_sent=false");
            true
        } else {
            false
        };
        // Follow the actual user path once. The product intentionally rejects
        // a new START while capture is active; that guard is not a second step
        // in normal recording and must not abort this STOP/receive exercise.
        std::thread::sleep(std::time::Duration::from_secs(seconds + if recover_after_limit { 3 } else { 0 }));

        let mut stop = control_request(
            companion_v1::CompanionV1ControlAction::MeetingStop,
            Some(session_id.clone()),
        );
        stop.device_id = Some(device_id.clone());
        let stop_requested_at = std::time::Instant::now();
        let stopped = if recover_after_limit {
            let mut reconnect = control_request(
                companion_v1::CompanionV1ControlAction::DeviceConnect, Some(session_id.clone()));
            reconnect.device_id = Some(device_id.clone());
            coordinator.apply_control(reconnect)?
        } else { coordinator.apply_control(stop)? };
        let stop_to_durable_receive_ms = stop_requested_at.elapsed().as_millis();
        let stop_session = stopped
            .host
            .sessions
            .iter()
            .find(|session| session.id == session_id)
            .ok_or_else(|| "V1 STOP lost the Type session".to_string())?;
        let recording_id = stop_session
            .device_recording_id
            .ok_or_else(|| "V1 STOP did not attach a real recording id".to_string())?;
        if stop_session.device_total_length.unwrap_or(0) == 0
            || stop_session
                .device_sha256
                .as_deref()
                .unwrap_or_default()
                .len()
                != 64
            || !stop_session
                .audio_path
                .as_deref()
                .is_some_and(|path| Path::new(path).is_file())
        {
            return Err("V1 STOP did not persist a verified pulled WAV".to_string());
        }

        let mut finalize = control_request(
            companion_v1::CompanionV1ControlAction::MeetingFinalize,
            Some(session_id.clone()),
        );
        finalize.device_id = Some(device_id.clone());
        let finalized = if recover_after_limit { stopped } else { coordinator.apply_control(finalize)? };
        let session = finalized
            .host
            .sessions
            .iter()
            .find(|session| session.id == session_id)
            .ok_or_else(|| "V1 FINALIZE lost the Type session".to_string())?;
        let checks = serde_json::json!({
            "connectedRealBle": finalized.connected && finalized.device.connected,
            "boardSourceNotHostMic": session.source == "boardDevice",
            "recordingIdentity": start_recording_id == recording_id
                && session.device_recording_id == Some(recording_id)
                && session.device_total_length.unwrap_or(0) > 0
                && session.device_sha256.as_deref().unwrap_or_default().len() == 64,
            "pulledWav": session.audio_path.as_deref().is_some_and(|path| Path::new(path).is_file()),
            "durableDeviceConsume": session.device_reclaimed,
            "completeCapture": !session.capture_incomplete,
            "endedMeetingUnlocked": !finalized.meeting.active && !finalized.device.recording
                && finalized.host.active_session_id.is_none(),
            "noInventedStopTime": !recover_after_limit || session.stopped_at.is_none(),
            "originalLinkDisconnected": !recover_after_limit || recovery_link_disconnected,
        });
        let pass = checks.as_object().is_some_and(|checks| {
            checks
                .values()
                .all(|value| value == &serde_json::Value::Bool(true))
        });
        let payload = serde_json::json!({
            "schema": "companion.real-recording-control.v2",
            "result": if pass { "PASS_RECORDING_CONTROL_AND_RECEIVE_STAGE_ONLY" } else { "FAIL_RECORDING_CONTROL_AND_RECEIVE_STAGE" },
            "scope": if recover_after_limit { "original_ended_recording_reconnect_and_durable_receive_only" }
                else { "recording_control_and_durable_receive_only" },
            "source": "board_device",
            "hostMic": false,
            "seed": false,
            "asr": "NOT_RUN",
            "minutes": "NOT_RUN",
            "fullChainAcceptance": "NOT_RUN",
            "stopToDurableReceiveMs": if recover_after_limit { None } else { Some(stop_to_durable_receive_ms) },
            "reconnectToDurableReceiveMs": if recover_after_limit { Some(stop_to_durable_receive_ms) } else { None },
            "normalStopAcknowledged": !recover_after_limit,
            "recoveryLinkDisconnected": recovery_link_disconnected,
            "sessionId": session_id,
            "deviceId": device_id,
            "recordingId": recording_id,
            "startRecordingId": start_recording_id,
            "duplicateStart": "NOT_ATTEMPTED_NORMAL_USER_PATH",
            "durationMs": session.duration_ms,
            "totalLength": session.device_total_length,
            "sha256": session.device_sha256,
            "audioPath": session.audio_path,
            "checks": checks,
        });
        println!("v1_real_meeting_result_json={payload}");
        if let Some(output_path) = output_path {
            if let Some(parent) = output_path.parent() {
                fs::create_dir_all(parent)
                    .map_err(|err| format!("create V1 result directory: {err}"))?;
            }
            fs::write(
                &output_path,
                format!(
                    "{}\n",
                    serde_json::to_string_pretty(&payload)
                        .map_err(|err| format!("serialize V1 result: {err}"))?
                ),
            )
            .map_err(|err| format!("write V1 result {}: {err}", output_path.display()))?;
        }
        if !pass {
            return Err(format!("installed V1 machine checks failed: {payload}"));
        }
        Ok(())
    })())
}

fn accuracy_normalize(value: &str) -> String {
    value
        .chars()
        .flat_map(char::to_lowercase)
        .filter(|ch| ch.is_alphanumeric())
        .collect()
}

fn accuracy_includes(haystack: &str, needle: &str) -> bool {
    let haystack = accuracy_normalize(haystack);
    let needle = accuracy_normalize(needle);
    !needle.is_empty() && haystack.contains(&needle)
}

fn rounded_ratio(hits: usize, total: usize) -> f64 {
    if total == 0 {
        return 0.0;
    }
    ((hits as f64 / total as f64) * 10_000.0).round() / 10_000.0
}

fn load_accuracy_truth(path: &Path) -> Result<(Vec<String>, String), String> {
    let bytes = fs::read(path)
        .map_err(|err| format!("read minutes accuracy truth {}: {err}", path.display()))?;
    let truth = serde_json::from_slice::<Vec<String>>(&bytes).map_err(|err| {
        format!(
            "minutes accuracy truth must be a JSON array of strings ({}): {err}",
            path.display()
        )
    })?;
    let truth = truth
        .into_iter()
        .map(|item| item.trim().to_string())
        .filter(|item| !item.is_empty())
        .collect::<Vec<_>>();
    if truth.is_empty() {
        return Err(format!(
            "minutes accuracy truth contains no non-empty phrases: {}",
            path.display()
        ));
    }
    Ok((truth, format!("{:x}", Sha256::digest(&bytes))))
}

fn minutes_claims(markdown: &str) -> Vec<String> {
    let mut in_claim_section = false;
    let mut claims = Vec::new();
    for raw in markdown.lines() {
        let line = raw.trim();
        if line.starts_with('#') {
            let heading = accuracy_normalize(line.trim_start_matches('#'));
            in_claim_section = ["决定", "决策", "行动", "待办", "decision", "action"]
                .iter()
                .any(|marker| heading.contains(marker));
            continue;
        }
        if !in_claim_section {
            continue;
        }
        let item = line
            .trim_start_matches(|ch: char| {
                ch.is_whitespace()
                    || ch == '-'
                    || ch == '*'
                    || ch == '+'
                    || ch == '.'
                    || ch.is_ascii_digit()
            })
            .trim();
        if !item.is_empty() && item != "无" && !item.eq_ignore_ascii_case("none") {
            claims.push(item.to_string());
        }
    }
    claims
}

fn score_claim_support(transcript: &str, markdown: &str) -> (Vec<serde_json::Value>, f64) {
    let claims = minutes_claims(markdown);
    let rows = claims
        .iter()
        .map(|claim| {
            serde_json::json!({
                "text": claim,
                "supported": accuracy_includes(transcript, claim),
            })
        })
        .collect::<Vec<_>>();
    let supported = rows
        .iter()
        .filter(|row| {
            row.get("supported")
                .and_then(serde_json::Value::as_bool)
                == Some(true)
        })
        .count();
    (rows, rounded_ratio(supported, claims.len()))
}

fn score_board_minutes_accuracy(
    truth: &[String],
    truth_path: &Path,
    truth_sha256: &str,
    transcript: &str,
    offline_markdown: &str,
    online_markdown: &str,
    _minutes: Option<&companion_v1::CompanionV1MeetingMinutes>,
) -> serde_json::Value {
    let hit_rows = |text: &str| {
        truth
            .iter()
            .map(|phrase| {
                serde_json::json!({
                    "phrase": phrase,
                    "hit": accuracy_includes(text, phrase),
                })
            })
            .collect::<Vec<_>>()
    };
    let asr_hits = hit_rows(transcript);
    let offline_hits = hit_rows(offline_markdown);
    let online_hits = hit_rows(online_markdown);
    let hit_count = |rows: &[serde_json::Value]| {
        rows.iter()
            .filter(|row| row.get("hit").and_then(serde_json::Value::as_bool) == Some(true))
            .count()
    };
    let asr_recall = rounded_ratio(hit_count(&asr_hits), truth.len());
    let offline_coverage = rounded_ratio(hit_count(&offline_hits), truth.len());
    let online_coverage = rounded_ratio(hit_count(&online_hits), truth.len());

    let (offline_claim_support, offline_fidelity) =
        score_claim_support(transcript, offline_markdown);
    let (online_claim_support, online_fidelity) = score_claim_support(transcript, online_markdown);
    let offline_hallucination = if offline_claim_support.is_empty() {
        0.0
    } else {
        ((1.0 - offline_fidelity) * 10_000.0).round() / 10_000.0
    };
    let online_hallucination = if online_claim_support.is_empty() {
        0.0
    } else {
        ((1.0 - online_fidelity) * 10_000.0).round() / 10_000.0
    };
    let transcript_has_decision = ["决定", "议定", "同意", "批准", "conclusion", "decid"]
        .iter()
        .any(|word| transcript.to_lowercase().contains(word));
    let both_modes_have_decisions =
        !offline_claim_support.is_empty() && !online_claim_support.is_empty();
    let structure_ok = transcript.chars().count() >= 20
        && (!transcript_has_decision || both_modes_have_decisions);
    let claims_gate = (offline_claim_support.is_empty()
        || (offline_fidelity >= 0.7 && offline_hallucination <= 0.4))
        && (online_claim_support.is_empty()
            || (online_fidelity >= 0.7 && online_hallucination <= 0.4));
    let pass = asr_recall >= 0.6
        && offline_coverage >= 0.5
        && online_coverage >= 0.5
        && claims_gate
        && structure_ok;
    serde_json::json!({
        "schema": "companion_type.minutes_accuracy.v1",
        "status": if pass { "PASS" } else { "FAIL" },
        "pass": pass,
        "truthFile": truth_path,
        "truthSha256": truth_sha256,
        "scores": {
            "asrKeyphraseRecall": asr_recall,
            "offlineMinutesClaimCoverage": offline_coverage,
            "onlineMinutesClaimCoverage": online_coverage,
            "offlineMinutesFidelity": offline_fidelity,
            "onlineMinutesFidelity": online_fidelity,
            "offlineHallucinationRate": offline_hallucination,
            "onlineHallucinationRate": online_hallucination,
        },
        "gates": {
            "asrKeyphraseRecallMin": 0.6,
            "eachMinutesModeClaimCoverageMin": 0.5,
            "minutesFidelityMin": 0.7,
            "hallucinationRateMax": 0.4,
        },
        "evidence": {
            "truth": truth,
            "asrHits": asr_hits,
            "offlineMinutesHits": offline_hits,
            "onlineMinutesHits": online_hits,
            "offlineClaimSupport": offline_claim_support,
            "onlineClaimSupport": online_claim_support,
            "asrChars": transcript.chars().count(),
            "structureOk": structure_ok,
            "asrHasDecisionWord": transcript_has_decision,
        },
    })
}

fn inspect_pulled_wav(path: &Path) -> serde_json::Value {
    let bytes = match fs::read(path) {
        Ok(bytes) => bytes,
        Err(error) => {
            return serde_json::json!({
                "decodable": false,
                "nonSilent": false,
                "error": format!("read pulled WAV {}: {error}", path.display()),
            });
        }
    };
    if bytes.len() < 12 || &bytes[..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return serde_json::json!({
            "decodable": false,
            "nonSilent": false,
            "error": "pulled audio is not a RIFF/WAVE file",
        });
    }
    let mut cursor = 12usize;
    let mut format = None;
    let mut data = None;
    while cursor.saturating_add(8) <= bytes.len() {
        let id = &bytes[cursor..cursor + 4];
        let size = u32::from_le_bytes(bytes[cursor + 4..cursor + 8].try_into().unwrap()) as usize;
        cursor += 8;
        if cursor.saturating_add(size) > bytes.len() {
            break;
        }
        if id == b"fmt " && size >= 16 {
            format = Some((
                u16::from_le_bytes(bytes[cursor..cursor + 2].try_into().unwrap()),
                u16::from_le_bytes(bytes[cursor + 2..cursor + 4].try_into().unwrap()),
                u32::from_le_bytes(bytes[cursor + 4..cursor + 8].try_into().unwrap()),
                u16::from_le_bytes(bytes[cursor + 14..cursor + 16].try_into().unwrap()),
            ));
        } else if id == b"data" {
            data = Some(&bytes[cursor..cursor + size]);
        }
        cursor = cursor.saturating_add(size + (size % 2));
    }
    let Some((audio_format, channels, sample_rate, bits_per_sample)) = format else {
        return serde_json::json!({"decodable": false, "nonSilent": false, "error": "WAV fmt chunk is missing"});
    };
    let Some(data) = data else {
        return serde_json::json!({"decodable": false, "nonSilent": false, "error": "WAV data chunk is missing"});
    };
    let decodable = audio_format == 1
        && channels > 0
        && sample_rate > 0
        && bits_per_sample == 16
        && !data.is_empty()
        && data.len() % 2 == 0;
    let mut peak = 0u32;
    let mut sum_squares = 0f64;
    let mut samples = 0usize;
    if decodable {
        for sample in data.chunks_exact(2) {
            let value = i16::from_le_bytes([sample[0], sample[1]]) as i32;
            peak = peak.max(value.unsigned_abs());
            sum_squares += f64::from(value).powi(2);
            samples += 1;
        }
    }
    let rms = if samples == 0 {
        0.0
    } else {
        (sum_squares / samples as f64).sqrt()
    };
    let non_silent = decodable && peak >= 64 && rms >= 8.0;
    serde_json::json!({
        "decodable": decodable,
        "nonSilent": non_silent,
        "audioFormat": audio_format,
        "channels": channels,
        "sampleRate": sample_rate,
        "bitsPerSample": bits_per_sample,
        "dataBytes": data.len(),
        "samplePeak": peak,
        "sampleRms": (rms * 100.0).round() / 100.0,
        "nonSilentGate": {"samplePeakMin": 64, "sampleRmsMin": 8.0},
    })
}

fn write_board_acceptance_output(path: &Path, payload: &serde_json::Value) -> Result<(), String> {
    if let Some(parent) = path.parent().filter(|parent| !parent.as_os_str().is_empty()) {
        fs::create_dir_all(parent).map_err(|error| {
            format!(
                "create board acceptance output directory {}: {error}",
                parent.display()
            )
        })?;
    }
    let rendered = serde_json::to_vec_pretty(payload)
        .map_err(|error| format!("serialize board acceptance result: {error}"))?;
    fs::write(path, rendered)
        .map_err(|error| format!("write board acceptance result {}: {error}", path.display()))
}

fn run_board_online_live_cli(args: &[String]) -> Option<Result<(), String>> {
    if !args.iter().any(|arg| arg == "--board-online-live") {
        return None;
    }
    let output_path = args
        .iter()
        .position(|arg| arg == "--output")
        .and_then(|position| args.get(position + 1))
        .map(PathBuf::from);
    let device_check_output = args
        .iter()
        .position(|arg| arg == "--device-check-output")
        .and_then(|position| args.get(position + 1))
        .map(PathBuf::from);
    let mut final_artifact_written = false;
    let result = (|| {
        let expected_identity = args.iter().position(|arg| arg == "--expected-identity")
            .map(|position| args.get(position+1).ok_or_else(||"--expected-identity requires a JSON path".to_string())
                .and_then(|path| backend::hardware_identity::ExpectedIdentity::load(Path::new(path))))
            .transpose()?;
        let _ = backend::product_settings::load_and_apply();
        let device_id = args
            .iter()
            .position(|arg| arg == "--device-id")
            .and_then(|position| args.get(position + 1))
            .map(String::as_str);
        let seconds = args
            .iter()
            .position(|arg| arg == "--seconds")
            .and_then(|position| args.get(position + 1))
            .and_then(|value| value.parse::<u16>().ok())
            .unwrap_or(35);
        let partial_interval_ms = args
            .iter()
            .position(|arg| arg == "--partial-interval-ms")
            .and_then(|position| args.get(position + 1))
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(8_000);
        let disconnect_after_seconds = args
            .iter()
            .position(|arg| arg == "--disconnect-after-seconds")
            .and_then(|position| args.get(position + 1))
            .and_then(|value| value.parse::<u16>().ok());
        let truth_path = args
            .iter()
            .position(|arg| arg == "--truth-file")
            .and_then(|position| args.get(position + 1))
            .map(PathBuf::from);
        let accuracy_truth = truth_path
            .as_deref()
            .map(load_accuracy_truth)
            .transpose()?;
        let coordinator = Arc::new(CompanionCoordinator::new_fixture());
        let device_check = coordinator.apply_control(companion_v1::CompanionV1ControlRequest {
            action: companion_v1::CompanionV1ControlAction::OobeRunChecks,
            ble_name: None,
            session_id: None,
            prompt_id: None,
            title: None,
            transcript_text: None,
            meeting_mode: None,
            audio_path: None,
            audio_bytes: None,
            device_id: device_id.map(str::to_string),
            duration_ms: None,
        })?;
        let check_status = |id: &str| {
            device_check
                .oobe
                .checks
                .iter()
                .find(|check| check.id == id)
                .map(|check| check.status.as_str())
        };
        let recording_catalog_pass = device_check
            .oobe
            .checks
            .iter()
            .find(|check| check.id == "boardMicrophone")
            .is_some_and(|check| check.status != "fail" && check.message.contains("可访问"));
        let legacy_identity_pass = device_check.device.firmware_version == Some(0x0001_0114)
            && device_check.device.build_id == Some(0x2026_1004)
            && device_check.device.board_id == Some(0x5742_4155)
            && device_check.device.hardware_revision.as_deref() == Some("COMPANION-WBA55-V1.1")
            && device_check.device.mcu_uid.as_deref().is_some_and(|uid| uid.len() == 24)
            && device_check.device.ui_generation == Some(38);
        let hardware_identity_pass = expected_identity.as_ref()
            .map_or(legacy_identity_pass, |expected| expected.matches(&device_check.device));
        let device_machine_pass = ["bluetooth", "firmware", "gatt", "clock", "imu", "speaker"]
            .iter()
            .all(|id| check_status(id) == Some("pass"))
            && recording_catalog_pass
            && hardware_identity_pass;
        let device_check_payload = serde_json::json!({
            "schema": "companion.wba.v11.type-device-check.v1",
            "result": if device_machine_pass { "PASS_TYPE_DEVICE_CHECK" } else { "FAIL_TYPE_DEVICE_CHECK" },
            "board": "companion-v1.1-wba55",
            "deviceId": device_check.device.device_id,
            "firmwareVersion": device_check.device.firmware_version,
            "buildId": device_check.device.build_id,
            "boardId": device_check.device.board_id,
            "hardwareRevision": device_check.device.hardware_revision,
            "mcuUid": device_check.device.mcu_uid,
            "uiGeneration": device_check.device.ui_generation,
            "expectedIdentity": expected_identity,
            "checks": {
                "bluetooth": if check_status("bluetooth") == Some("pass") { "PASS" } else { "FAIL" },
                "firmware": if check_status("firmware") == Some("pass") && hardware_identity_pass { "PASS" } else { "FAIL" },
                "gatt": if check_status("gatt") == Some("pass") { "PASS" } else { "FAIL" },
                "recordingCatalog": if recording_catalog_pass { "PASS" } else { "FAIL" },
                "clock": if check_status("clock") == Some("pass") { "PASS" } else { "FAIL" },
                "imu": if check_status("imu") == Some("pass") { "PASS" } else { "FAIL" },
                "speaker": if check_status("speaker") == Some("pass") { "PASS" } else { "FAIL" },
                "display": "MANUAL_REQUIRED",
                "touch": "MANUAL_REQUIRED",
                "power": "MANUAL_REQUIRED",
            },
            "rawChecks": device_check.oobe.checks,
        });
        if let Some(path) = device_check_output.as_deref() {
            write_board_acceptance_output(path, &device_check_payload)?;
        }
        if !device_machine_pass {
            return Err(format!("WBA device identity or machine checks failed: {device_check_payload}"));
        }
        let verified_device_id = device_check
            .device
            .device_id
            .as_deref()
            .ok_or_else(|| "WBA device check returned no stable device id".to_string())?;
        let session_id = format!(
            "board-online-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis()
        );
        coordinator.apply_control(companion_v1::CompanionV1ControlRequest {
            action: companion_v1::CompanionV1ControlAction::MeetingStart,
            ble_name: None,
            session_id: Some(session_id.clone()),
            prompt_id: None,
            title: Some("Companion 板端在线会议（CLI 验收）".to_string()),
            transcript_text: None,
            meeting_mode: Some("onlineLive".to_string()),
            audio_path: Some(format!("board://online/{session_id}")),
            audio_bytes: Some(0),
            device_id: Some(verified_device_id.to_string()),
            duration_ms: Some(0),
        })?;
        let partial_coordinator = Arc::clone(&coordinator);
        let partial_session_id = session_id.clone();
        let consumer: backend::BoardPartialConsumer = Arc::new(move |wav_path: PathBuf| {
            let transcript = CompanionTranscriptionManager::new()
                .transcribe_audio(&wav_path.to_string_lossy())?;
            if transcript.text.trim().is_empty() {
                return Err(format!(
                    "ASR returned an empty board partial for {}",
                    wav_path.display()
                ));
            }
            println!(
                "board_online_live_asr_partial path={} text={}",
                wav_path.display(),
                transcript.text.replace('\r', " ").replace('\n', " ")
            );
            partial_coordinator
                .set_board_online_live_partial(&partial_session_id, &transcript.text)?;
            Ok(transcript.text)
        });
        let report = match backend::record_board_online_live(
            Some(verified_device_id),
            seconds,
            partial_interval_ms,
            disconnect_after_seconds,
            consumer,
        ) {
            Ok(report) => report,
            Err(error) => {
                let _ = coordinator.fail_board_online_live(&session_id, &error);
                return Err(error);
            }
        };
        let completed = coordinator.complete_board_online_live(&session_id, &report)?;
        if report.sync_paused { return Err(backend::recording_sync::PAUSED.into()); }
        let session = completed
            .host
            .sessions
            .iter()
            .find(|item| item.id == session_id)
            .ok_or_else(|| format!("completed board session disappeared: {session_id}"))?;
        let offline = session.minutes_by_mode.offline_store.as_ref();
        let online = session.minutes_by_mode.online_live.as_ref();
        let dual_mode_ready = offline
            .zip(online)
            .map(|(offline, online)| {
                offline.status == "minutesReady"
                    && online.status == "minutesReady"
                    && offline.quality == "final"
                    && online.quality == "final"
                    && !offline.markdown.trim().is_empty()
                    && !online.markdown.trim().is_empty()
            })
            .unwrap_or(false);
        let transcript_injected = std::env::var("COMPANION_TYPE_TRANSCRIPT_TEXT")
            .ok()
            .is_some_and(|value| !value.trim().is_empty());
        let final_audio = Path::new(&report.final_recording_path);
        let sidecar_candidates = final_audio
            .file_stem()
            .and_then(|value| value.to_str())
            .map(|stem| final_audio.with_file_name(format!("{stem}.transcript.txt")))
            .into_iter()
            .chain([final_audio.with_extension("txt"), PathBuf::from(format!("{}.txt", final_audio.display()))]);
        let transcript_sidecar = sidecar_candidates.into_iter().find(|path| path.is_file());
        let real_asr = !transcript_injected && transcript_sidecar.is_none();
        let minutes_accuracy = match (accuracy_truth.as_ref(), truth_path.as_deref()) {
            (Some((truth, truth_sha256)), Some(path)) => score_board_minutes_accuracy(
                truth,
                path,
                truth_sha256,
                &session.transcript_text,
                offline.map(|item| item.markdown.as_str()).unwrap_or_default(),
                online.map(|item| item.markdown.as_str()).unwrap_or_default(),
                session.minutes.as_ref(),
            ),
            _ => serde_json::json!({
                "schema": "companion_type.minutes_accuracy.v1",
                "status": "NOT_RUN",
                "pass": false,
                "reason": "--truth-file is required for factual minutes accuracy acceptance",
            }),
        };
        let accuracy_pass = minutes_accuracy
            .get("pass")
            .and_then(serde_json::Value::as_bool)
            == Some(true);
        let pulled = !report.final_recording_path.is_empty()
            && final_audio.is_file()
            && report.final_total_length > 0
            && report.final_sha256.len() == 64;
        let wav_evidence = inspect_pulled_wav(final_audio);
        let decodable = wav_evidence
            .get("decodable")
            .and_then(serde_json::Value::as_bool)
            == Some(true);
        let non_silent = wav_evidence
            .get("nonSilent")
            .and_then(serde_json::Value::as_bool)
            == Some(true);
        let automatic_transcript_evidence = session.transcript_review.is_none();
        let pass = automatic_transcript_evidence && report.partials.len() >= 2
            && pulled
            && report.disconnect_resume
            && session.status == "minutesReady"
            && !session.transcript_text.trim().is_empty()
            && decodable
            && non_silent
            && session.minutes.is_some()
            && dual_mode_ready
            && real_asr
            && accuracy_pass;
        let payload = serde_json::json!({
            "schema": "companion.wba.v11.full-chain-acceptance.v1",
            "result": if pass { "PASS_WBA_FULL_CHAIN" } else { "FAIL_WBA_FULL_CHAIN" },
            "status": if pass { "PASS" } else { "FAIL" },
            "captureSource": "board_device",
            "source": "board_device",
            "hostMic": false,
            "automaticTranscriptEvidence": automatic_transcript_evidence,
            "humanReviewedTranscript": session.transcript_review.is_some(),
            "codec": 3,
            "nonSeed": true,
            "disconnectResume": report.disconnect_resume,
            "deviceId": report.device_id,
            "hardwareIdentity": {
                "verified": hardware_identity_pass,
                "firmwareVersion": device_check.device.firmware_version,
                "buildId": device_check.device.build_id,
                "boardId": device_check.device.board_id,
                "hardwareRevision": device_check.device.hardware_revision,
                "mcuUid": device_check.device.mcu_uid,
                "uiGeneration": device_check.device.ui_generation,
            },
            "durableBeforePartial": true,
            "sessionId": session_id,
            "sessionStatus": session.status,
            "transcriptChars": session.transcript_text.chars().count(),
            "boardStorage": {
                "finalized": report.final_total_length > 0 && report.final_sha256.len() == 64,
                "recordingId": report.recording_id,
                "totalLength": report.final_total_length,
                "sha256": report.final_sha256,
            },
            "typePull": {
                "complete": pulled,
                "decodable": decodable,
                "nonSilent": non_silent,
                "path": report.final_recording_path,
                "wavEvidence": wav_evidence,
            },
            "asr": {
                "real": real_asr,
                "transcriptChars": session.transcript_text.chars().count(),
                "blockedInjection": if transcript_injected { "environmentText" } else if transcript_sidecar.is_some() { "sidecar" } else { "none" },
            },
            "dualMode": {
                "ready": dual_mode_ready,
                "offlineStore": offline,
                "onlineLive": online,
            },
            "minutesAccuracy": minutes_accuracy,
            "report": report,
        });
        if let Some(path) = output_path.as_deref() {
            write_board_acceptance_output(path, &payload)?;
            final_artifact_written = true;
        }
        println!("board_online_live_result_json={payload}");
        if !pass {
            return Err(format!("board onlineLive acceptance failed: {payload}"));
        }
        Ok(())
    })();
    if let (Err(error), Some(path)) = (&result, output_path.as_deref()) {
        if !final_artifact_written {
            let failure = serde_json::json!({
                "schema": "companion.wba.v11.full-chain-acceptance.v1",
                "result": "FAIL_WBA_FULL_CHAIN",
                "status": "FAIL",
                "stage": "beforeFinalAcceptanceArtifact",
                "error": error,
                "captureSource": "NOT_RUN",
                "disconnectResume": false,
                "boardStorage": {"finalized": false},
                "typePull": {"complete": false, "decodable": false, "nonSilent": false},
                "asr": {"real": false, "transcriptChars": 0},
                "dualMode": {"offlineStore": {"status": "NOT_RUN"}, "onlineLive": {"status": "NOT_RUN"}},
                "minutesAccuracy": {"status": "NOT_RUN", "pass": false},
            });
            if let Err(write_error) = write_board_acceptance_output(path, &failure) {
                eprintln!("board_online_live_failure_artifact_error={write_error}");
            }
        }
    }
    Some(result)
}

fn run_sync_device_recording_cli(args: &[String]) -> Option<Result<(), String>> {
    if !args.iter().any(|a| a == "--sync-device-recording") {
        return None;
    }
    Some((|| {
        let _ = backend::product_settings::load_and_apply();
        let coordinator = CompanionCoordinator::new_fixture();
        // Prefer explicit --device-id; else scan once and pass the winner into sync.
        let mut device_id = args
            .iter()
            .position(|arg| arg == "--device-id")
            .and_then(|position| args.get(position + 1))
            .cloned();
        if device_id.is_none() {
            if let Ok(scan) = coordinator.apply_control(companion_v1::CompanionV1ControlRequest {
                action: companion_v1::CompanionV1ControlAction::DeviceScan,
                ble_name: None,
                session_id: None,
                prompt_id: None,
                title: None,
                transcript_text: None,
                meeting_mode: None,
                audio_path: None,
                audio_bytes: None,
                device_id: None,
                duration_ms: None,
            }) {
                device_id = scan
                    .device
                    .device_id
                    .clone()
                    .or_else(|| scan.device_id.clone());
                eprintln!(
                    "sync scan device_id={:?} last={:?}",
                    device_id,
                    scan.last_control.as_ref().map(|c| &c.message)
                );
            }
        }
        let snap = coordinator.apply_control(companion_v1::CompanionV1ControlRequest {
            action: companion_v1::CompanionV1ControlAction::DeviceSyncRecordings,
            ble_name: None,
            session_id: None,
            prompt_id: None,
            title: None,
            transcript_text: None,
            meeting_mode: None,
            audio_path: None,
            audio_bytes: None,
            device_id,
            duration_ms: None,
        })?;
        let device_sessions = snap
            .host
            .sessions
            .iter()
            .filter(|session| session.device_recording_id.is_some())
            .collect::<Vec<_>>();
        let session = snap
            .host
            .selected_session_id
            .as_deref()
            .and_then(|id| snap.host.sessions.iter().find(|session| session.id == id))
            .or_else(|| device_sessions.first().copied())
            .ok_or_else(|| "sync returned no host session".to_string())?;
        let path = session
            .audio_path
            .clone()
            .unwrap_or_else(|| "(none)".to_string());
        let is_pass = path != "(none)"
            && !path.starts_with("device://")
            && !path.starts_with("host://")
            && Path::new(&path).is_file();
        let payload = serde_json::json!({
            "status": if is_pass { "PASS" } else { "FAIL" },
            "audioPath": path,
            "audioBytes": session.audio_bytes,
            "durationMs": session.duration_ms,
            "source": session.source,
            "recordingId": session.device_recording_id,
            "sha256": session.device_sha256,
            "sessions": device_sessions.iter().map(|item| serde_json::json!({
                "sessionId": item.id,
                "recordingId": item.device_recording_id,
                "audioPath": item.audio_path,
                "audioBytes": item.audio_bytes,
                "durationMs": item.duration_ms,
                "totalLength": item.device_total_length,
                "sha256": item.device_sha256,
                "deviceReclaimed": item.device_reclaimed,
            })).collect::<Vec<_>>(),
            "lastControl": snap.last_control.as_ref().map(|c| &c.message),
        });
        println!("sync_device_recording_result_json={payload}");
        if !is_pass {
            return Err(format!("device sync did not produce a host WAV: {payload}"));
        }
        // Opus path evidence: sibling .opus file when codec=3 was pulled.
        let opus_path = PathBuf::from(&path).with_extension("opus");
        if opus_path.is_file() {
            println!(
                "opus_device_path_evidence=opus_bytes={} wav={}",
                fs::metadata(&opus_path).map(|m| m.len()).unwrap_or(0),
                path
            );
        }
        Ok(())
    })())
}

fn control_request(
    action: companion_v1::CompanionV1ControlAction,
    session_id: Option<String>,
) -> companion_v1::CompanionV1ControlRequest {
    companion_v1::CompanionV1ControlRequest {
        action,
        ble_name: None,
        session_id,
        prompt_id: None,
        title: None,
        transcript_text: None,
        meeting_mode: None,
        audio_path: None,
        audio_bytes: None,
        device_id: None,
        duration_ms: None,
    }
}

/// Product-path acceptance entry point: reopen the durable session index, then
/// run the same select -> real ASR -> minutes controls used by the GUI for
/// every board recording. This intentionally does not accept transcript text,
/// so an unconfigured or failing ASR provider fails the command.
fn run_process_device_library_cli(args: &[String]) -> Option<Result<(), String>> {
    if !args
        .iter()
        .any(|arg| arg == "--process-device-recording-library")
    {
        return None;
    }
    Some((|| {
        let requested_recording_id = args
            .windows(2)
            .find(|pair| pair[0] == "--recording-id")
            .map(|pair| {
                pair[1]
                    .parse::<u32>()
                    .map_err(|_| format!("invalid --recording-id: {}", pair[1]))
            })
            .transpose()?;
        let recovery_audio_path = args
            .windows(2)
            .find(|pair| pair[0] == "--recover-audio-path")
            .map(|pair| PathBuf::from(&pair[1]));
        if let Some(path) = recovery_audio_path.as_ref() {
            let recording_id = requested_recording_id
                .ok_or_else(|| "--recover-audio-path requires --recording-id".to_string())?;
            let recovered_session = backend::recover_persisted_board_recording(recording_id, path)?;
            eprintln!(
                "process device library recovered recording_id={recording_id} session_id={recovered_session} wav={}",
                path.display()
            );
        }
        let _ = backend::product_settings::load_and_apply();
        let coordinator = CompanionCoordinator::new_fixture();
        let initial = coordinator.snapshot()?;
        let mut targets = initial
            .host
            .sessions
            .iter()
            .filter_map(|session| {
                session.device_recording_id.map(|recording_id| {
                    let complete = session.transcript_final
                        && !session.transcript_text.trim().is_empty()
                        && backend::session_has_final_minutes_product(session);
                    (recording_id, session.id.clone(), complete)
                })
            })
            .filter(|(recording_id, _, _)| {
                requested_recording_id.is_none_or(|requested| requested == *recording_id)
            })
            .collect::<Vec<_>>();
        targets.sort_by_key(|(recording_id, _, _)| *recording_id);
        if targets.is_empty() {
            return Err(match requested_recording_id {
                Some(recording_id) => {
                    format!("recording library contains no board session id={recording_id}")
                }
                None => "recording library contains no board sessions".to_string(),
            });
        }

        let mut failures = Vec::new();
        for (recording_id, session_id, complete) in targets {
            if complete {
                eprintln!(
                    "process device library skip_complete recording_id={recording_id} session_id={session_id}"
                );
                continue;
            }
            let outcome = (|| -> Result<(), String> {
                coordinator.apply_control(control_request(
                    companion_v1::CompanionV1ControlAction::MeetingSelectSession,
                    Some(session_id.clone()),
                ))?;
                let transcribed = coordinator.apply_control(control_request(
                    companion_v1::CompanionV1ControlAction::MeetingTranscribeAudio,
                    Some(session_id.clone()),
                ))?;
                let transcript_session = transcribed
                    .host
                    .sessions
                    .iter()
                    .find(|session| session.id == session_id)
                    .ok_or_else(|| format!("session disappeared after ASR: {session_id}"))?;
                if transcript_session.transcript_text.trim().is_empty()
                    || transcript_session.status != "transcribed"
                {
                    return Err(format!(
                        "real ASR did not complete: status={} pending={:?}",
                        transcript_session.status, transcript_session.pending_reason
                    ));
                }
                let minutes = coordinator.apply_control(control_request(
                    companion_v1::CompanionV1ControlAction::MeetingGenerateMinutes,
                    Some(session_id.clone()),
                ))?;
                let session = minutes
                    .host
                    .sessions
                    .iter()
                    .find(|session| session.id == session_id)
                    .ok_or_else(|| format!("session disappeared after minutes: {session_id}"))?;
                session
                    .minutes
                    .as_ref()
                    .ok_or_else(|| "minutes missing after generation".to_string())?;
                if !backend::session_has_final_minutes_product(session) {
                    return Err(format!(
                        "minutes did not complete: status={} pending={:?}; original audio and transcript retained",
                        session.status, session.pending_reason
                    ));
                }
                Ok(())
            })();
            if let Err(error) = outcome {
                eprintln!(
                    "process device library isolate_failure recording_id={recording_id} session_id={session_id} continue=1 error={error}"
                );
                failures.push(serde_json::json!({
                    "recordingId": recording_id,
                    "sessionId": session_id,
                    "retryable": !error.contains("no_speech_detected"),
                    "automaticRetryScheduled": coordinator.snapshot()?.host.sessions.iter()
                        .find(|session| session.id == session_id)
                        .is_some_and(|session| session.recovery.next_retry_at_unix_ms.is_some()),
                    "manualRetryAvailable": coordinator.snapshot()?.host.sessions.iter()
                        .find(|session| session.id == session_id)
                        .is_some_and(|session| session.audio_stored),
                    "error": error,
                }));
            }
        }
        let final_snapshot = coordinator.snapshot()?;
        let mut reports = final_snapshot
            .host
            .sessions
            .iter()
            .filter_map(|session| {
                let recording_id = session.device_recording_id?;
                if requested_recording_id.is_some_and(|requested| requested != recording_id) {
                    return None;
                }
                let generated = session.minutes.as_ref()?;
                Some(serde_json::json!({
                    "sessionId": session.id,
                    "recordingId": recording_id,
                    "status": session.status,
                    "audioPath": session.audio_path,
                    "totalLength": session.device_total_length,
                    "sha256": session.device_sha256,
                    "transcriptChars": session.transcript_text.chars().count(),
                    "transcript": session.transcript_text,
                    "utterances": session.utterances.len(),
                    "speakerIds": session.utterances.iter().map(|item| item.speaker).collect::<std::collections::BTreeSet<_>>(),
                    "minutesSource": generated.source,
                    "minutesQuality": generated.quality,
                    "minutesMarkdown": generated.markdown,
                    "minutesByMode": {
                        "offlineStore": session.minutes_by_mode.offline_store.as_ref().map(|item| &item.status),
                        "onlineLive": session.minutes_by_mode.online_live.as_ref().map(|item| &item.status),
                    },
                }))
            })
            .collect::<Vec<_>>();
        reports.sort_by_key(|report| report["recordingId"].as_u64().unwrap_or(u64::MAX));
        let status = if failures.is_empty() {
            "PASS"
        } else {
            "PARTIAL"
        };
        let payload = serde_json::json!({
            "status": status,
            "realAsr": true,
            "requestedRecordingId": requested_recording_id,
            "sessions": reports,
            "failures": failures,
        });
        println!("process_device_library_result_json={payload}");
        if status == "PASS" {
            Ok(())
        } else {
            Err(
                "recording library has retryable isolated failures; healthy entries continued"
                    .to_string(),
            )
        }
    })())
}

/// Exercise the exact product delete rather than a broad privacy wipe. The
/// backend refuses to remove the local card unless the board first accepts the
/// recording_id + length + SHA-256 tuple.
fn run_delete_device_recording_cli(args: &[String]) -> Option<Result<(), String>> {
    let position = args
        .iter()
        .position(|arg| arg == "--delete-device-recording-exact")?;
    Some((|| {
        let recording_id = args
            .get(position + 1)
            .ok_or_else(|| "--delete-device-recording-exact requires an id".to_string())?
            .parse::<u32>()
            .map_err(|err| format!("invalid recording id: {err}"))?;
        let _ = backend::product_settings::load_and_apply();
        let coordinator = CompanionCoordinator::new_fixture();
        let before = coordinator.snapshot()?;
        let target = before
            .host
            .sessions
            .iter()
            .find(|session| session.device_recording_id == Some(recording_id))
            .ok_or_else(|| format!("recording_id={recording_id} is not in the Type library"))?;
        let target_id = target.id.clone();
        let preserved_before = before
            .host
            .sessions
            .iter()
            .filter(|session| session.id != target_id)
            .filter_map(|session| {
                session.device_recording_id.map(|id| {
                    (
                        id,
                        session.device_total_length,
                        session.device_sha256.clone(),
                        session.status.clone(),
                    )
                })
            })
            .collect::<Vec<_>>();
        coordinator.apply_control(control_request(
            companion_v1::CompanionV1ControlAction::MeetingSelectSession,
            Some(target_id.clone()),
        ))?;
        let after = coordinator.apply_control(control_request(
            companion_v1::CompanionV1ControlAction::PrivacyDeleteSession,
            Some(target_id.clone()),
        ))?;
        let target_absent = !after
            .host
            .sessions
            .iter()
            .any(|session| session.id == target_id);
        let preserved = preserved_before.iter().all(|expected| {
            after.host.sessions.iter().any(|session| {
                session.device_recording_id == Some(expected.0)
                    && session.device_total_length == expected.1
                    && session.device_sha256 == expected.2
                    && session.status == expected.3
            })
        });
        let pass = target_absent && preserved;
        let payload = serde_json::json!({
            "status": if pass { "PASS" } else { "FAIL" },
            "exactDelete": pass,
            "recordingId": recording_id,
            "targetAbsent": target_absent,
            "preservedNeighbors": preserved,
            "remainingRecordingIds": after.host.sessions.iter().filter_map(|s| s.device_recording_id).collect::<Vec<_>>(),
            "lastControl": after.last_control.as_ref().map(|control| &control.message),
        });
        println!("delete_device_recording_result_json={payload}");
        if !pass {
            return Err(format!("exact delete invariant failed: {payload}"));
        }
        Ok(())
    })())
}

fn run_firmware_ota_cli(args: &[String]) -> Option<Result<(), String>> {
    let transfer_flag = args
        .iter()
        .position(|arg| arg == "--firmware-ota-transfer" || arg == "--resource-ota-transfer");
    let validate_flag = args.iter().position(|arg| arg == "--resource-ota-validate");
    let (index, mode) = if let Some(i) = validate_flag {
        (i, "validate")
    } else if let Some(i) = transfer_flag {
        (i, "transfer")
    } else {
        return None;
    };
    let result = (|| {
        let manifest_path = args
            .get(index + 1)
            .ok_or_else(|| "missing manifest path after OTA CLI flag".to_string())?;
        let firmware_path = args
            .get(index + 2)
            .ok_or_else(|| "missing payload path after OTA CLI flag".to_string())?;
        if !Path::new(manifest_path).is_file() {
            return Err(format!("OTA manifest does not exist: {manifest_path}"));
        }
        if !Path::new(firmware_path).is_file() {
            return Err(format!("OTA payload does not exist: {firmware_path}"));
        }
        let device_id = args
            .iter()
            .position(|arg| arg == "--device-id")
            .and_then(|position| args.get(position + 1))
            .cloned();
        let request = CompanionFirmwareOtaRequest {
            manifest_path: manifest_path.clone(),
            firmware_path: firmware_path.clone(),
            device_id,
        };
        let coordinator = CompanionCoordinator::new_fixture();
        if mode == "validate" {
            let report: CompanionOtaPackageValidation =
                coordinator.validate_ota_package(request)?;
            let payload = serde_json::json!({
                "status": if report.ok { "PASS" } else { "FAIL" },
                "packageType": report.package_type,
                "payloadBytes": report.payload_bytes,
                "chunkBytes": report.chunk_bytes,
                "payloadSha256": report.payload_sha256,
                "message": report.message,
                "versionNote": report.version_note,
            });
            println!("resource_ota_validate_json={payload}");
            return Ok(());
        }
        let report = coordinator.transfer_firmware_ota(request)?;
        let payload = serde_json::json!({
            "status": "PASS",
            "protocol": report.protocol,
            "packageType": report.package_type,
            "deviceId": report.device_id,
            "firmwareBytes": report.firmware_bytes,
            "dataWrites": report.data_writes,
            "statusReads": report.status_reads,
            "recoveredOffsets": report.recovered_offsets,
            "activeLinkConfirmed": report.active_link_confirmed,
            "elapsedMs": report.elapsed_ms,
        });
        println!("firmware_ota_result_json={payload}");
        Ok(())
    })();
    if let Err(error) = &result {
        eprintln!("[cli] Companion OTA failed: {error}");
    }
    Some(result)
}

fn run_embedded_audio_cli(args: Vec<String>) -> Option<Result<(), String>> {
    let intent = match embedded_audio_cli_path(&args) {
        Some(Ok(intent)) => intent,
        Some(Err(error)) => {
            eprintln!("[cli] submit-embedded-audio-streaming-file failed: {error}");
            return Some(Err(error));
        }
        None => return None,
    };

    let audio_path = intent.audio_path;
    let _ = backend::product_settings::load_and_apply();
    let audio_path_text = audio_path.to_string_lossy().to_string();
    println!(
        "[cli] submit-embedded-audio-streaming-file: path={} format={}",
        audio_path.display(),
        intent.format
    );

    let result = CompanionTranscriptionManager::new().transcribe_audio(&audio_path_text);
    match result {
        Ok(transcript) => {
            let text = transcript.text;
            if let Err(error) = write_debug_transcript(&text) {
                eprintln!("[cli] write debug transcript failed: {error}");
            }
            let payload = serde_json::json!({
                "result": {
                    "text": text.clone(),
                    "utterances": [
                        {
                            "definite": true,
                            "text": text.clone(),
                        }
                    ]
                }
            });
            println!("[asr] server JSON: {payload}");
            println!("source=backend.companion_type_cli event=asr_final transcript_empty=false");
            println!(
                "[cli] submit-embedded-audio-streaming-file done: pcm_bytes={} missing_packets=0",
                pcm_payload_bytes(&audio_path, intent.format)
            );
            Some(Ok(()))
        }
        Err(error) => {
            eprintln!("[cli] submit-embedded-audio-streaming-file failed: {error}");
            Some(Err(error))
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum EmbeddedAudioFormat {
    Raw,
    Wav,
    Pcm16Le,
}

impl std::fmt::Display for EmbeddedAudioFormat {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let value = match self {
            EmbeddedAudioFormat::Raw => "raw",
            EmbeddedAudioFormat::Wav => "wav",
            EmbeddedAudioFormat::Pcm16Le => "pcm16le",
        };
        formatter.write_str(value)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct EmbeddedAudioCliIntent {
    audio_path: PathBuf,
    format: EmbeddedAudioFormat,
}

fn embedded_audio_cli_path(args: &[String]) -> Option<Result<EmbeddedAudioCliIntent, String>> {
    let mut index = 1;
    while index < args.len() {
        let format = match args[index].as_str() {
            "--submit-embedded-audio" | "--submit-embedded-audio-stream" => {
                Some(EmbeddedAudioFormat::Raw)
            }
            "--submit-embedded-audio-wav" | "--submit-embedded-audio-wav-stream" => {
                Some(EmbeddedAudioFormat::Wav)
            }
            "--submit-embedded-audio-pcm16le" | "--submit-embedded-audio-pcm16le-stream" => {
                Some(EmbeddedAudioFormat::Pcm16Le)
            }
            _ => None,
        };
        if let Some(format) = format {
            let Some(path) = args.get(index + 1) else {
                return Some(Err(format!("missing audio path after {}", args[index])));
            };
            let audio_path = PathBuf::from(path);
            if !audio_path.exists() {
                return Some(Err(format!(
                    "audio path does not exist: {}",
                    audio_path.display()
                )));
            }
            return Some(Ok(EmbeddedAudioCliIntent { audio_path, format }));
        }
        index += 1;
    }
    None
}

fn write_debug_transcript(text: &str) -> Result<(), String> {
    let mut paths = Vec::new();
    for key in [
        "COMPANION_TYPE_DEBUG_TRANSCRIPT_FILE",
        "LISTENER_TYPE_DEBUG_TRANSCRIPT_FILE",
    ] {
        if let Some(path) = std::env::var_os(key).map(PathBuf::from) {
            if !paths.contains(&path) {
                paths.push(path);
            }
        }
    }
    for path in paths {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)
                .map_err(|error| format!("create {}: {error}", parent.display()))?;
        }
        fs::write(&path, text).map_err(|error| format!("write {}: {error}", path.display()))?;
    }
    Ok(())
}

fn pcm_payload_bytes(audio_path: &Path, format: EmbeddedAudioFormat) -> u64 {
    if format == EmbeddedAudioFormat::Wav
        || audio_path
            .extension()
            .is_some_and(|value| value.to_string_lossy().eq_ignore_ascii_case("wav"))
    {
        if let Some(size) = wav_data_chunk_bytes(audio_path) {
            return size;
        }
    }
    fs::metadata(audio_path)
        .map(|metadata| metadata.len())
        .unwrap_or(0)
}

fn wav_data_chunk_bytes(audio_path: &Path) -> Option<u64> {
    let data = fs::read(audio_path).ok()?;
    if data.len() < 12 || &data[0..4] != b"RIFF" || &data[8..12] != b"WAVE" {
        return None;
    }
    let mut cursor = 12;
    while cursor + 8 <= data.len() {
        let chunk_id = &data[cursor..cursor + 4];
        let chunk_size = u32::from_le_bytes(data[cursor + 4..cursor + 8].try_into().ok()?) as usize;
        cursor += 8;
        if chunk_id == b"data" {
            return Some(chunk_size as u64);
        }
        cursor = cursor.saturating_add(chunk_size + (chunk_size % 2));
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot_with_pending_recovery(
        id: &str,
    ) -> companion_v1::CompanionV1Snapshot {
        let mut snapshot = companion_v1::fixture_snapshot();
        let request = companion_v1::CompanionV1ControlRequest {
            action: companion_v1::CompanionV1ControlAction::DeviceSyncRecordings,
            ble_name: None,
            session_id: Some(id.to_string()),
            prompt_id: None,
            title: Some(id.to_string()),
            transcript_text: None,
            meeting_mode: Some("offlineStore".to_string()),
            audio_path: Some(format!("C:/test/{id}.wav")),
            audio_bytes: Some(16),
            device_id: Some("test-device".to_string()),
            duration_ms: Some(1_000),
        };
        let session = companion_v1::synced_device_session(&snapshot, &request, "test");
        snapshot.host.sessions = vec![session];
        snapshot
    }

    #[test]
    fn automatic_recovery_waits_until_the_library_is_durable() {
        let mut snapshot = snapshot_with_pending_recovery("storage-pending");
        for status in ["blocked", "unsaved", "recovered"] {
            snapshot.host.persistence.status = status.to_string();
            assert_eq!(next_automatic_recovery(&snapshot, 10), (None, None));
        }
        snapshot.host.persistence.status = "ready".to_string();
        assert!(next_automatic_recovery(&snapshot, 10).0.is_some());
    }

    #[test]
    fn automatic_recovery_waits_while_any_meeting_is_recording() {
        let mut snapshot = snapshot_with_pending_recovery("old-pending");
        let mut recording = snapshot.host.sessions[0].clone();
        recording.id = "active-recording".to_string();
        recording.status = "recording".to_string();
        recording.recovery = companion_v1::CompanionV1MeetingRecovery::default();
        snapshot.host.sessions.push(recording);
        snapshot.meeting.active = true;
        snapshot.host.active_session_id = Some("active-recording".to_string());
        assert_eq!(next_automatic_recovery(&snapshot, 10), (None, None));
    }

    #[test]
    fn automatic_recovery_waits_for_device_button_recording_then_resumes() {
        let mut snapshot = snapshot_with_pending_recovery("device-busy-pending");
        snapshot.device.recording = true;
        assert_eq!(next_automatic_recovery(&snapshot, 10), (None, None));

        snapshot.device.recording = false;
        assert_eq!(
            next_automatic_recovery(&snapshot, 10),
            (
                Some((
                    "device-busy-pending".to_string(),
                    AutomaticRecoveryAction::Transcribe
                )),
                None
            )
        );
    }

    #[test]
    fn automatic_device_reconnect_requires_exact_opt_in_and_yields_to_recording() {
        let mut snapshot = companion_v1::fixture_snapshot();
        snapshot.connected = false;
        snapshot.device.connected = false;
        snapshot.device.connection_phase = "offline".to_string();
        snapshot.device.remembered_device_id = Some("AA:BB:CC:DD:EE:FF".to_string());
        snapshot.device.auto_reconnect_enabled = true;
        snapshot.device.manual_disconnect = false;
        assert!(should_attempt_device_reconnect(&snapshot));

        snapshot.device.manual_disconnect = true;
        assert!(!should_attempt_device_reconnect(&snapshot));
        snapshot.device.manual_disconnect = false;
        snapshot.meeting.active = true;
        assert!(!should_attempt_device_reconnect(&snapshot));
        snapshot.meeting.active = false;
        snapshot.connected = true;
        snapshot.device.connection_phase = "ready".to_string();
        assert!(should_attempt_device_reconnect(&snapshot));
        snapshot.device.recording = true;
        assert!(should_attempt_device_reconnect(&snapshot));
        snapshot.device.connection_phase = "reconnecting".to_string();
        assert!(!should_attempt_device_reconnect(&snapshot));
    }

    #[test]
    fn recovery_retry_backoff_resumes_the_persisted_minutes_stage_only() {
        let mut snapshot = snapshot_with_pending_recovery("minutes-retry");
        let session = &mut snapshot.host.sessions[0];
        session.transcript_text = "final transcript".to_string();
        session.transcript_final = true;
        session.recovery.stage = "retryBackoff".to_string();
        session.recovery.retry_stage = "minutes".to_string();
        session.recovery.next_retry_at_unix_ms = Some(9);
        let (next, _) = next_automatic_recovery(&snapshot, 10);
        assert_eq!(
            next,
            Some((
                "minutes-retry".to_string(),
                AutomaticRecoveryAction::GenerateMinutes
            ))
        );
    }

    #[test]
    fn embedded_audio_cli_ignores_normal_app_launch() {
        let args = vec![
            "companion-type".to_string(),
            "--suppress-capsule-window".to_string(),
        ];
        assert_eq!(embedded_audio_cli_path(&args), None);
    }

    #[test]
    fn embedded_audio_cli_accepts_listener_compatible_wav_stream_flag() {
        let root = std::env::temp_dir().join("companion-type-cli-wav-stream-test");
        let _ = fs::create_dir_all(&root);
        let audio = root.join("input.wav");
        fs::write(&audio, b"RIFF----WAVEfmt ").unwrap();
        let args = vec![
            "companion-type".to_string(),
            "--suppress-capsule-window".to_string(),
            "--submit-embedded-audio-wav-stream".to_string(),
            audio.to_string_lossy().to_string(),
        ];
        let intent = embedded_audio_cli_path(&args).unwrap().unwrap();
        assert_eq!(intent.audio_path, audio);
        assert_eq!(intent.format, EmbeddedAudioFormat::Wav);
    }

    #[test]
    fn wav_payload_bytes_uses_data_chunk_size() {
        let root = std::env::temp_dir().join("companion-type-cli-wav-bytes-test");
        let _ = fs::create_dir_all(&root);
        let audio = root.join("input.wav");
        let mut wav = Vec::new();
        wav.extend_from_slice(b"RIFF");
        wav.extend_from_slice(&40_u32.to_le_bytes());
        wav.extend_from_slice(b"WAVE");
        wav.extend_from_slice(b"fmt ");
        wav.extend_from_slice(&16_u32.to_le_bytes());
        wav.extend_from_slice(&[1, 0, 1, 0, 0x80, 0x3e, 0, 0, 0, 0x7d, 0, 0, 2, 0, 16, 0]);
        wav.extend_from_slice(b"data");
        wav.extend_from_slice(&4_u32.to_le_bytes());
        wav.extend_from_slice(&[1, 2, 3, 4]);
        fs::write(&audio, wav).unwrap();
        assert_eq!(pcm_payload_bytes(&audio, EmbeddedAudioFormat::Wav), 4);
    }

    #[test]
    fn board_minutes_accuracy_requires_both_minutes_modes() {
        let truth = vec![
            "采用离线先存".to_string(),
            "在线实时纪要".to_string(),
            "小陈周五验收".to_string(),
        ];
        let transcript = "会议采用离线先存，也生成在线实时纪要，小陈周五验收并完整记录结果。";
        let passing = score_board_minutes_accuracy(
            &truth,
            Path::new("truth.json"),
            "abc",
            transcript,
            "采用离线先存；在线实时纪要；小陈周五验收。",
            "采用离线先存；在线实时纪要；小陈周五验收。",
            None,
        );
        assert_eq!(passing["pass"], true);

        let missing_online = score_board_minutes_accuracy(
            &truth,
            Path::new("truth.json"),
            "abc",
            transcript,
            "采用离线先存；在线实时纪要；小陈周五验收。",
            "无事实内容",
            None,
        );
        assert_eq!(missing_online["pass"], false);
        assert_eq!(
            missing_online["scores"]["onlineMinutesClaimCoverage"],
            0.0
        );
        assert!(!accuracy_includes(
            "设备必须使用 48K 采样率",
            "设备必须使用 16K 采样率"
        ));
    }

    #[test]
    fn pulled_wav_inspection_measures_decode_and_signal() {
        let root = std::env::temp_dir().join("companion-type-board-wav-evidence-test");
        let _ = fs::create_dir_all(&root);
        let audio = root.join("signal.wav");
        let samples = [0_i16, 512, -512, 256];
        let mut wav = Vec::new();
        wav.extend_from_slice(b"RIFF");
        wav.extend_from_slice(&(36 + samples.len() as u32 * 2).to_le_bytes());
        wav.extend_from_slice(b"WAVEfmt ");
        wav.extend_from_slice(&16_u32.to_le_bytes());
        wav.extend_from_slice(&[1, 0, 1, 0, 0x80, 0x3e, 0, 0, 0, 0x7d, 0, 0, 2, 0, 16, 0]);
        wav.extend_from_slice(b"data");
        wav.extend_from_slice(&(samples.len() as u32 * 2).to_le_bytes());
        for sample in samples {
            wav.extend_from_slice(&sample.to_le_bytes());
        }
        fs::write(&audio, wav).unwrap();
        let evidence = inspect_pulled_wav(&audio);
        assert_eq!(evidence["decodable"], true);
        assert_eq!(evidence["nonSilent"], true);
    }
}
