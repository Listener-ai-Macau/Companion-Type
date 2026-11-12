//! Companion Type Tauri backend.
//!
//! The module split keeps IPC commands, workflow state, replaceable services,
//! and the shared Companion contract separate.

mod backend;
mod cli_fallback;
mod commands;
mod document_commands;
mod incoming_commands;
mod audio_edit_commands;
mod content_handoff;
mod file_clipboard;
mod calendar_handoff;
mod close_review;
mod cache_updates;
mod companion_v1;
mod coordinator;
mod pet_chat_commands;
mod pet_profile_commands;
mod pet_find_commands;
mod recorder_sync_exercise;

use std::fs;
use std::path::{Path, PathBuf};
use std::process;
use std::sync::Arc;

use backend::{
    CompanionFirmwareOtaRequest, CompanionOtaPackageValidation, CompanionTranscriptionManager,
};
use coordinator::CompanionCoordinator;
use sha2::{Digest, Sha256};

fn exit_after_device_cleanup(code:i32)->! {
    backend::lifecycle::PROCESS.request();
    backend::recording_sync::request_process_shutdown();
    let result=backend::release_process_device_links();
    match result {
        Ok(owners)=>{
            eprintln!("device_process_exit cleanup=complete released_owner_records={owners} board_stop_commands=0 saved_preferences_changed=0");
            process::exit(code)
        },
        Err(error)=>{
            eprintln!("device_process_exit cleanup=incomplete error={error} original_exit_code={code}");
            process::exit(if code==0 {1}else{code})
        },
    }
}

pub fn run() {
    let args = std::env::args().collect::<Vec<_>>();
    // Handle help before any command or application startup: the latter can
    // reconnect to a device and resume recordings automatically.
    if cli_fallback::help_requested(&args) {
        println!("Companion Type: launch without arguments to open the app.\n\
                  --system-ota-validate <manifest> checks a package offline.\n\
                  Other command-line operations require an explicit supported command.");
        process::exit(0);
    }
    if args.iter().any(|arg|arg=="--recording-sync-status") {
        if args.len()!=2 {eprintln!("recording_sync_status_error=此只读入口不能与其它操作组合。");exit_after_device_cleanup(1);}
        match backend::recording_sync::status() {
            Ok(status)=>println!("recording_sync_status_json={}",serde_json::to_string(&status).unwrap()),
            Err(error)=>{eprintln!("recording_sync_status_error={error}");exit_after_device_cleanup(1);}
        }
        exit_after_device_cleanup(0);
    }
    if args.iter().any(|arg|arg=="--restore-local-recordings") {
        let result=backend::recording_wire::receiver::restore_local_product();
        let good=result.as_ref().is_ok_and(|report|report.failures.is_empty());
        match result {
            Ok(report)=>println!("local_recording_restore_json={}",serde_json::to_string(&report).unwrap()),
            Err(error)=>eprintln!("local_recording_restore_error={error}"),
        }
        exit_after_device_cleanup(if good {0} else {1});
    }
    if let Some(result) = run_meeting_workspace_cli(&args) {
        if let Err(error) = &result { eprintln!("meeting_workspace_error={error}"); }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--recording-session-self-test") {
        let result=args.get(index+1).ok_or_else(||"--recording-session-self-test requires a fresh output folder".to_string())
            .and_then(|output|backend::recording_wire::receiver::verify(Path::new(output)));
        match &result {Ok(r)=>println!("recording_session_json={r}"),Err(e)=>eprintln!("recording_session_error={e}")}
        exit_after_device_cleanup(if result.is_ok(){0}else{1});
    }
    if let Some(index) = args.iter().position(|arg| arg == "--recording-session-probe-phase") {
        let result=(|| {let output=args.get(index+1).ok_or_else(||"missing isolated probe folder".to_string())?;
            let phase=args.get(index+2).ok_or_else(||"missing isolated probe phase".to_string())?;
            backend::recording_wire::receiver::phase(Path::new(output),phase)})();
        match &result {Ok(r)=>println!("recording_session_phase_json={r}"),Err(e)=>eprintln!("recording_session_phase_error={e}")}
        exit_after_device_cleanup(if result.is_ok(){0}else{1});
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
        exit_after_device_cleanup(if result.is_ok(){0}else{1});
    }
    if let Some(index) = args.iter().position(|arg| arg == "--desktop-update-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--desktop-update-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::desktop_update::self_test(Path::new(output)));
        match &result {
            Ok(report) => println!("desktop_update_json={report}"),
            Err(error) => eprintln!("desktop_update_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result)=backend::recording_bookmarks::probe::run(&args) {
        if let Err(error)=&result {eprintln!("recording_bookmarks_error={error}");}
        exit_after_device_cleanup(if result.is_ok(){0}else{1});
    }
    if let Some(index) = args.iter().position(|arg| arg == "--recording-wire-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--recording-wire-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::recording_wire::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("recording_wire_json={report}"),
            Err(error) => eprintln!("recording_wire_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--recording-transfer-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--recording-transfer-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::recording_transfer::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("recording_transfer_json={report}"),
            Err(error) => eprintln!("recording_transfer_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--cache-privacy-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--cache-privacy-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::verify_cache_privacy(Path::new(output)));
        match &result {
            Ok(report) => println!("cache_privacy_json={report}"),
            Err(error) => eprintln!("cache_privacy_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--audio-artifacts-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--audio-artifacts-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::audio_artifacts::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("audio_artifacts_json={report}"),
            Err(error) => eprintln!("audio_artifacts_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--file-storage-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--file-storage-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::file_storage_probe::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("file_storage_json={report}"),
            Err(error) => eprintln!("file_storage_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--privacy-delete-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--privacy-delete-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::verify_privacy_delete(Path::new(output)));
        match &result {
            Ok(report) => println!("privacy_delete_json={report}"),
            Err(error) => eprintln!("privacy_delete_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if args.get(1).is_some_and(|arg| arg == "--external-command-test-fixture") {
        exit_after_device_cleanup(backend::external_command_probe::fixture_main(&args[2..]));
    }
    if let Some(index) = args.iter().position(|arg| arg == "--external-command-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--external-command-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::external_command_probe::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("external_command_json={report}"),
            Err(error) => eprintln!("external_command_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--service-network-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--service-network-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::service_network_probe::verify(Path::new(output)));
        match &result {
            Ok(report) => println!("service_network_json={report}"),
            Err(error) => eprintln!("service_network_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(index) = args.iter().position(|arg| arg == "--asr-cache-self-test") {
        let result = args.get(index + 1).ok_or_else(|| "--asr-cache-self-test requires a fresh output folder".to_string())
            .and_then(|output| backend::verify_asr_cache(Path::new(output)));
        match &result {
            Ok(report) => println!("asr_cache_json={report}"),
            Err(error) => eprintln!("asr_cache_error={error}"),
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
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
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_diagnostics_cli(&args) {
        if let Err(error) = &result { eprintln!("diagnostics_error={error}"); }
        exit_after_device_cleanup(if result.is_ok() {0} else {1});
    }
    if let Some(result) = run_firmware_ota_cli(&args) {
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_recorder_control_cli(&args) {
        if let Err(error) = &result { eprintln!("recorder_control_error={error}"); }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_v1_real_meeting_cli(&args) {
        if let Err(err) = &result {
            eprintln!("v1_real_meeting_error={err}");
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = commands::run_segmented_online_cli(&args) {
        if let Err(err)=result {eprintln!("segmented_online_error={err}");exit_after_device_cleanup(1);}
        return;
    }
    if let Some(result) = run_recording_upload_benchmark_cli(&args) {
        if let Err(error) = &result { eprintln!("recording_upload_benchmark_error={error}"); }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_release_one_saved_segment_cli(&args) {
        if let Err(err)=&result {eprintln!("release_one_saved_segment_error={err}");}
        exit_after_device_cleanup(if result.is_ok(){0}else{1});
    }
    if let Some(result) = run_sync_device_recording_cli(&args) {
        if let Err(err) = &result {
            eprintln!("sync_device_recording_error={err}");
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_process_device_library_cli(&args) {
        if let Err(err) = &result {
            eprintln!("process_device_library_error={err}");
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    if let Some(result) = run_delete_device_recording_cli(&args) {
        if let Err(err) = &result {
            eprintln!("delete_device_recording_error={err}");
        }
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }
    let incoming_paths=if args.len()>1&&!args[1].starts_with('-'){args.iter().skip(1).map(std::path::PathBuf::from).collect::<Vec<_>>()}else{Vec::new()};
    let unhandled_option = cli_fallback::unhandled_option(&args);
    if let Some(result) = run_embedded_audio_cli(args) {
        exit_after_device_cleanup(if result.is_ok() { 0 } else { 1 });
    }

    if unhandled_option {
        eprintln!("Unsupported command-line option; no application or device operation was started.");
        process::exit(2);
    }

    // Register before any automatic device reconnect. OpenWith deliveries
    // reach the matching existing library process through its atomic pending
    // receipt, then this extra launch exits without opening a second device owner.
    #[cfg(windows)]
    let _incoming_registration=match incoming_commands::Registration::new(){Ok(value)=>value,Err(error)=>{incoming_commands::error(&error);process::exit(2)}};
    if !incoming_paths.is_empty(){
        let cwd=std::env::current_dir().unwrap_or_else(|_|std::path::PathBuf::from("."));
        if let Err(error)=incoming_commands::receive(incoming_paths,&cwd){incoming_commands::error(&error);process::exit(2);}
        #[cfg(windows)]if _incoming_registration.existing{process::exit(0);}
    }

    // Load ASR / DeepSeek / compress preferences into process env before IPC.
    let _ = backend::product_settings::load_and_apply();

    let coordinator = Arc::new(CompanionCoordinator::new_fixture());
    let local_recovery=Arc::clone(&coordinator);
    std::thread::spawn(move || {
        // One startup recovery, not a periodic scan. File decode stays off the
        // window thread; the operation/receiver leases serialize mutation.
        match cache_updates::after(|| local_recovery.restore_local_recordings()) {
            Ok(report) if !report.restored.is_empty() || !report.failures.is_empty()=>
                eprintln!("local_recording_restore_json={}",serde_json::to_string(&report).unwrap()),
            Err(error)=>eprintln!("local_recording_restore_error={error}"),
            _=>(),
        }
        spawn_automatic_meeting_recovery(Arc::clone(&local_recovery));
        spawn_automatic_device_reconnect(Arc::clone(&local_recovery));
        spawn_continuous_recording_sync(local_recovery);
    });
    let board_online_live = Arc::new(commands::CompanionBoardOnlineLiveManager::new());
    let close_review=Arc::new(close_review::CloseReview::default());

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(backend::desktop_update::Manager::default())
        .manage(Arc::clone(&coordinator))
        .manage(calendar_handoff::CalendarHandoff::default())
        .manage(board_online_live)
        .manage(Arc::clone(&close_review))
        .invoke_handler(tauri::generate_handler![
            close_review::register_companion_close_review,
            close_review::unregister_companion_close_review,
            close_review::respond_companion_close_review,
            pet_find_commands::control_companion_pet_find,
            pet_chat_commands::get_companion_pet_chat,
            pet_chat_commands::clear_companion_pet_chat,
            pet_chat_commands::start_companion_pet_chat,
            pet_chat_commands::finish_companion_pet_chat,
            pet_chat_commands::display_companion_pet_chat,
            pet_profile_commands::get_companion_pet_profile,
            pet_profile_commands::save_companion_pet_profile,
            pet_profile_commands::cleanup_companion_pet_profile,
            pet_profile_commands::reset_companion_pet_profile,
            backend::desktop_update::get_companion_type_update,
            backend::desktop_update::check_companion_type_update,
            backend::desktop_update::download_companion_type_update,
            backend::desktop_update::cancel_companion_type_update,
            backend::desktop_update::install_companion_type_update,
            commands::check_companion_service,
            commands::get_companion_v1_snapshot,
            commands::get_companion_pointer,
            commands::start_companion_pointer,
            commands::control_companion_pointer,
            commands::get_companion_desktop_input,
            commands::start_companion_desktop_input,
            commands::stop_companion_desktop_input,
            commands::copy_companion_desktop_input,
            commands::save_companion_meeting_edit,
            commands::refine_companion_meeting_speakers,
            commands::preview_companion_meeting_transcription,
            commands::preview_companion_meeting_gap,
            commands::save_companion_meeting_note,
            commands::check_companion_note_evidence,
            commands::add_companion_image_note,
            commands::preview_companion_note_image,
            audio_edit_commands::control_companion_audio_edit,
            document_commands::read_companion_document_context,
            document_commands::import_companion_document,
            incoming_commands::companion_incoming_files,
            document_commands::save_companion_document_original,
            commands::save_companion_bookmark,
            commands::import_companion_audio,
            commands::cancel_companion_audio_import,
            commands::ask_companion_meetings,
            commands::cancel_companion_meeting_question,
            commands::prepare_companion_audio,
            commands::prepare_companion_audio_with_timeline,
            commands::prepare_companion_meeting_audio_tracks,
            commands::save_companion_library_organization,
            commands::apply_companion_v1_control,
            commands::cancel_companion_meeting_processing,
            commands::get_companion_recording_sync_status,
            commands::pause_companion_recording_sync,
            commands::repair_companion_recording_sync_settings,
            commands::discard_oldest_companion_recording,
            commands::list_companion_device_recordings,
            commands::sync_companion_device_recording,
            commands::delete_companion_device_recording,
            commands::export_companion_meeting,
            commands::copy_companion_meeting_content,
            commands::share_companion_meeting_content,
            commands::share_companion_audio,
            calendar_handoff::open_companion_saved_calendar,
            commands::preview_companion_meeting_export,
            commands::export_companion_audio,
            commands::export_companion_library,
            commands::backup_companion_library,
            commands::restore_companion_library_backup,
            commands::backup_companion_library_with_templates,
            commands::restore_companion_library_backup_with_templates,
            commands::save_companion_library_lifecycle,
            commands::purge_companion_library,
            commands::export_companion_diagnostics,
            commands::preview_companion_diagnostics,
            commands::prepare_companion_audio_components,
            commands::prepare_companion_local_asr,
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
            cache_updates::bind_app(app.handle().clone());
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

            // Background integration checks must use an explicitly isolated
            // library; ordinary launches retain the normal visible window.
            if std::env::var("COMPANION_TYPE_BACKGROUND_WINDOW").as_deref()==Ok("1") {
                if std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none(){return Err("后台验证需要明确的独立资料库。".into());}
                builder=builder.visible(false).focused(false);
            }

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

            let window=builder.build()?;
            window.on_webview_event(|event|{
                if let tauri::WebviewEvent::DragDrop(tauri::DragDropEvent::Drop{paths,..})=event{
                    let paths=paths.clone();std::thread::spawn(move||{let cwd=std::env::current_dir().unwrap_or_else(|_|std::path::PathBuf::from("."));if let Err(error)=incoming_commands::receive(paths,&cwd){incoming_commands::error(&error);}});
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Companion Type")
        .run({
            let worker=Arc::new(std::sync::atomic::AtomicBool::new(false));
            let completed=Arc::new(std::sync::atomic::AtomicBool::new(false));
            move |app,event| {
                use std::sync::atomic::Ordering;
                use tauri::Manager;
                match event {
                    tauri::RunEvent::WindowEvent{label,event:tauri::WindowEvent::CloseRequested{api,..},..}
                        if label=="main" && !completed.load(Ordering::Acquire)=>{
                        // Keep the last window until cleanup succeeds; an
                        // incomplete cleanup must leave a way to retry Close.
                        api.prevent_close();close_review::request(app,&close_review,None);
                    },
                    tauri::RunEvent::ExitRequested{code,api,..} if !completed.load(Ordering::Acquire)=>{
                        api.prevent_exit();
                        if !close_review.approved(){close_review::request(app,&close_review,code);return;}
                        if worker.compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire).is_ok() {
                            if let Some(window)=app.get_webview_window("main") {let _=window.set_title("Companion Type · 正在退出，请稍候");}
                            coordinator.request_shutdown();
                            let coordinator=Arc::clone(&coordinator);let app=app.clone();
                            let worker=Arc::clone(&worker);let completed=Arc::clone(&completed);
                            std::thread::spawn(move || {
                                match coordinator.finish_shutdown(std::time::Duration::from_secs(30)) {
                                    Ok(owners)=>{
                                        eprintln!("device_process_exit cleanup=complete released_owner_records={owners} board_stop_commands=0 saved_preferences_changed=0 path=desktop");
                                        completed.store(true,Ordering::Release);
                                        app.exit(code.unwrap_or(0));
                                    },
                                    Err(error)=>{
                                        // Keep the app alive rather than kill an operation that
                                        // has not finished cleanup. A later Close can retry.
                                        eprintln!("device_process_exit cleanup=pending path=desktop error={error}");
                                        if let Some(window)=app.get_webview_window("main") {let _=window.set_title("Companion Type · 当前操作尚未结束，可稍后再关闭");}
                                        worker.store(false,Ordering::Release);
                                    },
                                }
                            });
                        }
                    },
                    tauri::RunEvent::Exit=>coordinator.request_shutdown(),
                    _=>{},
                }
            }
        });
}

fn prepare_headless_meeting_export(
    session:&companion_v1::CompanionV1HostSession,
    request:&commands::CompanionMeetingExportRequest,
)->Result<backend::export::PreparedMeetingExport,String> {
    // A CLI destination is caller-selected; it has neither the native Save As
    // confirmation nor an in-process handoff receipt required by GUI hints.
    if request.calendar_save_token.is_some() || request.calendar_saved_name {
        return Err("上次日历文件的保存选择需要在 Type 窗口确认；本次未写入文件。".into());
    }
    if (request.calendar_reminders.is_some() || request.calendar_slots.is_some()) && request.expected_content_hash.is_none() {
        return Err("请先核对本次逐项提醒和执行时段，再保存日历文件。".into());
    }
    let prepared=commands::prepare_requested_export(session,request)?;
    backend::export::require_unchanged(&prepared,request.expected_content_hash.as_deref())?;
    Ok(prepared)
}

#[cfg(test)]
mod headless_calendar_request_tests {
    use super::*;
    #[test]
    fn selected_alarm_slot_hash_and_gui_hint_are_not_silently_discarded() {
        let sessions:Vec<companion_v1::CompanionV1HostSession>=serde_json::from_str(include_str!("calendar_test_fixtures/p738-sessions.json")).unwrap();
        let row=&sessions[0];
        let base=backend::export::prepare_meeting_export(row,"offlineStore",backend::export::MeetingExportFormat::Calendar).unwrap();
        let uid=&base.calendar_items.as_ref().unwrap()[1].uid;
        let mut value=serde_json::json!({"sessionId":row.id,"meetingMode":"offlineStore","format":"calendar",
            "expectedContentHash":"0".repeat(64),"calendarReminders":[{"uid":uid,"reminder":{"kind":"at","at":"2026-11-07T08:00:00+08:00"}}],
            "calendarSlots":[{"uid":uid,"slot":{"start":"2026-11-07T09:00:00+08:00","end":"2026-11-07T10:00:00+08:00"}}]});
        let request=|v:serde_json::Value|serde_json::from_value::<commands::CompanionMeetingExportRequest>(v).unwrap();
        let stale=request(value.clone());assert!(prepare_headless_meeting_export(row,&stale).is_err());
        let prepared=backend::export::prepare_meeting_export_with_calendar_choices(row,"offlineStore",backend::export::MeetingExportFormat::Calendar,stale.calendar_reminders.as_deref(),stale.calendar_slots.as_deref()).unwrap();
        let hash=backend::export::content_hash(&prepared);value["expectedContentHash"]=hash.clone().into();
        let checked=prepare_headless_meeting_export(row,&request(value.clone())).unwrap();let file=String::from_utf8(checked.bytes).unwrap();
        assert!(file.contains("TRIGGER;VALUE=DATE-TIME:20261107T000000Z\r\n"));
        assert!(file.contains("DTSTART:20261107T010000Z\r\nDTEND:20261107T020000Z\r\n"));
        println!("P738_VALID_PREVIEW_HASH={hash}");
        let mut no_hash=value.clone();no_hash.as_object_mut().unwrap().remove("expectedContentHash");assert!(prepare_headless_meeting_export(row,&request(no_hash)).is_err());
        let mut hinted=value.clone();hinted["calendarSaveToken"]="stale-token".into();assert!(prepare_headless_meeting_export(row,&request(hinted)).is_err());
        let mut named=value.clone();named["calendarSavedName"]=true.into();assert!(prepare_headless_meeting_export(row,&request(named)).is_err());
        let mut wrong=value.clone();wrong["format"]="markdown".into();assert!(prepare_headless_meeting_export(row,&request(wrong)).is_err());
        let mut bad_uid=value.clone();bad_uid["calendarReminders"][0]["uid"]="different-item".into();assert!(prepare_headless_meeting_export(row,&request(bad_uid)).is_err());
        let legacy=request(serde_json::json!({"sessionId":row.id,"meetingMode":"offlineStore","format":"calendar"}));
        assert_eq!(backend::export::content_hash(&prepare_headless_meeting_export(row,&legacy).unwrap()),backend::export::content_hash(&base));
    }
}

fn local_recording_outcome_error(
    operation: u8,
    outcome_error: Option<String>,
    persistence: &companion_v1::CompanionV1PersistenceState,
) -> Option<String> {
    outcome_error.or_else(|| {
        if operation == 12 && persistence.status != "ready" {
            Some(persistence.message.clone().filter(|s| !s.trim().is_empty())
                .unwrap_or_else(|| "转写尚未保存到磁盘，请重试保存。".into()))
        } else { None }
    })
}

#[cfg(test)]
mod local_recording_cli_result_tests {
    use super::*;

    #[test]
    fn transcription_reports_unsaved_without_hiding_original_failure() {
        let mut persistence = companion_v1::CompanionV1PersistenceState::default();
        assert!(local_recording_outcome_error(12, None, &persistence).is_none());
        persistence.status = "unsaved".into();
        persistence.message = Some("写入失败，原录音保留".into());
        assert_eq!(local_recording_outcome_error(12, None, &persistence).as_deref(),
            Some("写入失败，原录音保留"));
        assert_eq!(local_recording_outcome_error(12, Some("转写中断".into()), &persistence).as_deref(),
            Some("转写中断"));
        assert!(local_recording_outcome_error(13, None, &persistence).is_none(),
            "a read-only snapshot must still be available for recovery");
        persistence.message = None;
        assert!(local_recording_outcome_error(12, None, &persistence).is_some());
    }
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
        "--meeting-image-note-request" => Some((i,17)),
        "--meeting-note-image-preview" => Some((i,18)),
        "--meeting-document-request" => Some((i,19)),
        "--audio-edit-request" => Some((i,20)),
        "--meeting-speakers-request" => Some((i,5)),
        "--device-connect-request" => Some((i,6)),
        "--library-organize-request" => Some((i,7)),
        "--library-export-request" => Some((i,8)),
        "--library-state-request" => Some((i,9)),
        "--library-purge-request" => Some((i,10)),
        "--library-control-request" => Some((i,11)),
        "--meeting-transcribe-request" => Some((i,12)),
        "--local-recording-snapshot" => Some((i,13)),
        "--local-recording-select" => Some((i,14)),
        "--library-backup-request" => Some((i,15)),
        "--library-restore-request" => Some((i,16)),
        _ => None,
    })?;
    Some((|| {
        let input = args.get(index+1).ok_or("缺少会议请求 JSON 路径。")?;
        let destination = args.get(index+2).ok_or("缺少本机结果文件路径。")?;
        let file = fs::File::open(input).map_err(|_| "无法打开会议请求文件。")?;
        if file.metadata().map_err(|_| "无法读取请求文件大小。")?.len() > 4*1024*1024 {
            return Err("会议请求文件不能超过 4 MB。".into());
        }
        if matches!(operation,6|12|13|14) {let _=backend::product_settings::load_and_apply();}
        let coordinator = CompanionCoordinator::new_fixture();
        if matches!(operation,15|16) {
            #[derive(serde::Deserialize)] #[serde(rename_all="camelCase",deny_unknown_fields)]
            struct BackupRequest { directory:std::path::PathBuf,#[serde(default)] include_templates:bool }
            let request:BackupRequest=serde_json::from_reader(file).map_err(|_|"备份请求格式不正确。")?;
            if operation==15 {
                let _lease=coordinator.begin_audio_export()?;
                let report=backend::library_backup::save_product(&coordinator.snapshot()?,&request.directory)?;
                backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&report).map_err(|e|e.to_string())?)?;
            } else if request.include_templates {
                let result=commands::restore_library_with_templates(&coordinator,&request.directory)?;
                backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&result).map_err(|e|e.to_string())?)?;
            } else {
                let result=coordinator.restore_library_backup(&request.directory)?;
                backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&result).map_err(|e|e.to_string())?)?;
            }
            println!("library_backup_result=LOCAL_OPERATION_COMPLETED");
        } else if matches!(operation,12|13|14) {
            #[derive(serde::Deserialize)] #[serde(rename_all="camelCase",deny_unknown_fields)]
            struct LocalRecordingRequest { session_id: Option<String> }
            let request:LocalRecordingRequest=serde_json::from_reader(file)
                .map_err(|_|"本机录音请求只接受已有录音身份。")?;
            let outcome=if operation==13 {
                if request.session_id.is_some(){return Err("读取本机录音库不接受修改请求。".into());}
                Ok(coordinator.snapshot()?)
            } else {
                let id=request.session_id.filter(|id|!id.is_empty()).ok_or("缺少已有录音身份。")?;
                let snapshot=coordinator.snapshot()?;
                let row=snapshot.host.sessions.iter().find(|row|row.id==id).ok_or("找不到这条本机录音。")?;
                if operation==12 && (!row.audio_stored || !row.retention.audio_cached
                    || row.status=="recording" || row.recorder_control_uncertain
                    || matches!(row.pending_reason.as_deref(),Some("needs_device_sync"|"needs_segments"|"needs_pull"))
                    || if row.source == "hostMeeting" {
                        backend::meeting_workspace::local_meeting_audio_tracks(&snapshot, &id).is_err()
                    } else { !row.audio_path.as_deref().is_some_and(|path|Path::new(path).is_file()) }) {
                    return Err("本机原音尚未就绪；这次没有连接设备或提交转写。".into());
                }
                let action=if operation==12 {companion_v1::CompanionV1ControlAction::MeetingTranscribeAudio}
                    else {companion_v1::CompanionV1ControlAction::MeetingSelectSession};
                coordinator.apply_control(control_request(action,Some(id)))
            };
            let outcome_error=outcome.as_ref().err().cloned();
            let snapshot=match outcome {Ok(snapshot)=>snapshot,Err(_)=>coordinator.snapshot()?};
            let error=local_recording_outcome_error(operation, outcome_error, &snapshot.host.persistence);
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&serde_json::json!({
                "snapshot":snapshot,"settings":backend::product_settings::public_report(),"operationError":error,
                "deviceAccess":false,"transcriptionRequested":operation==12
            })).map_err(|_|"无法生成本机录音结果。")?)?;
            if let Some(error)=error {return Err(error);}
            println!("local_recording_result=SAVED_NATIVE_RESULT");
        } else if operation == 11 {
            let mut request:companion_v1::CompanionV1ControlRequest=serde_json::from_reader(file).map_err(|_|"本机资料控制请求格式不正确。")?;
            use companion_v1::CompanionV1ControlAction as A;
            if !matches!(request.action,A::PrivacyEraseAudio|A::PrivacyEraseTranscript|A::PrivacyDeleteSession|A::PrivacyEraseAll|A::MeetingResetSession|A::MeetingRestoreAudio){return Err("此后台入口只接受明确的本机录音恢复、隐私清理或新工作区操作。".into());}
            request.prompt_id=if request.action==A::PrivacyDeleteSession{Some(backend::library_lifecycle::LOCAL_TRASH_PERMANENT.into())}else{None};
            if let Some(id)=request.session_id.as_deref().filter(|_|request.action!=A::MeetingRestoreAudio){
                let select=serde_json::from_value(serde_json::json!({"action":"meetingSelectSession","sessionId":id})).map_err(|e|e.to_string())?;
                coordinator.apply_control(select)?;
            }
            let snapshot=coordinator.apply_control(request)?;
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&snapshot).map_err(|e|e.to_string())?)?;
            println!("library_control_result=LOCAL_CONTROL_COMPLETED");
        } else if operation == 9 {
            let request:backend::library_lifecycle::Request=serde_json::from_reader(file).map_err(|_|"录音保护/回收站请求格式不正确。")?;
            let snapshot=coordinator.save_library_lifecycle(request)?;
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&snapshot).map_err(|e|e.to_string())?)?;
            println!("library_state_result=SAVED_LOCAL_PROTECTION_OR_TRASH");
        } else if operation == 10 {
            let request:backend::library_lifecycle::PurgeRequest=serde_json::from_reader(file).map_err(|_|"永久清除请求格式不正确。")?;
            let result=coordinator.purge_library(request)?;
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&result).map_err(|e|e.to_string())?)?;
            if !result.failures.is_empty(){return Err("部分回收站录音未永久清除；逐条结果已保存，请核对后重试。".into());}
            println!("library_purge_result=PERMANENTLY_ERASED_LOCAL_TRASH_ONLY");
        } else if operation == 7 {
            let request:backend::library_organization::Request=serde_json::from_reader(file).map_err(|_|"录音分类请求格式不正确。")?;
            let snapshot=coordinator.save_library_organization(request)?;
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&serde_json::json!({
                "result":"SAVED_LOCAL_LIBRARY_ORGANIZATION","sessions":snapshot.host.sessions,
                "persistenceStatus":snapshot.host.persistence.status,"deviceAccess":false,"networkAccess":false
            })).map_err(|e|e.to_string())?)?;
            println!("library_organization_result=SAVED_LOCAL_LIBRARY_ORGANIZATION");
        } else if operation == 8 {
            let request:backend::library_export::Request=serde_json::from_reader(file).map_err(|_|"批量导出请求格式不正确。")?;
            let _lease=coordinator.begin_audio_export()?;
            let report=backend::library_export::save(&coordinator.snapshot()?,&request,Path::new(destination))?;
            println!("library_export_json={}",serde_json::to_string(&report).map_err(|e|e.to_string())?);
        } else if operation == 0 {
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
            let export = prepare_headless_meeting_export(session,&request)?;
            let data=backend::content_export::materialize(&session.title,export)?;
            backend::export::write_atomic(Path::new(destination), &data)?;
            println!("meeting_workspace_result=EXPORTED_LOCAL_MEETING");
        } else if operation==20 {
            #[derive(serde::Deserialize)] #[serde(rename_all="camelCase",deny_unknown_fields)]
            struct AudioEditCli{action:String,#[serde(default)]request:serde_json::Value,cancel_after_outputs:Option<u64>,cancel_after_ms:Option<u64>}
            let input:AudioEditCli=serde_json::from_reader(file).map_err(|_|"录音编辑请求格式无效。")?;
            let coordinator=Arc::new(coordinator);
            let result=audio_edit_commands::dispatch(coordinator.clone(),&input.action,input.request)?;
            if matches!(input.action.as_str(),"start"|"retry"){
                let id=result["id"].as_str().ok_or("编辑启动结果缺失。")?.to_owned();let started=std::time::Instant::now();let mut cancelled=false;
                loop{
                    let status=backend::audio_edit_job::status()?;
                    backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&status).map_err(|e|e.to_string())?)?;
                    if !status["running"].as_bool().unwrap_or(false){break;}
                    if !cancelled&&(input.cancel_after_ms.is_some_and(|ms|started.elapsed().as_millis()>=u128::from(ms))
                        ||input.cancel_after_outputs.is_some_and(|n|status["completed"].as_u64().unwrap_or(0)>=n)){
                        backend::audio_edit_job::cancel(&id)?;cancelled=true;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(20));
                }
                let result=serde_json::json!({"status":backend::audio_edit_job::status()?,"snapshot":coordinator.snapshot()?});
                backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&result).map_err(|e|e.to_string())?)?;
            }else{backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&result).map_err(|e|e.to_string())?)?;}
            println!("meeting_workspace_result=LOCAL_AUDIO_EDIT_OPERATION_COMPLETED");
        } else if operation==19 {
            #[derive(serde::Deserialize)] #[serde(rename_all="camelCase",deny_unknown_fields)]
            struct DocumentRequest{action:String,session_id:String,#[serde(default)]revision:u64,document_id:Option<String>,source_path:Option<PathBuf>,offset:Option<u64>,extraction:Option<backend::document_context::Extraction>}
            let request:DocumentRequest=serde_json::from_reader(file).map_err(|_|"文档材料请求格式不正确。")?;
            let result=if matches!(request.action.as_str(),"import"|"commit"|"remove"){
                let change=match request.action.as_str(){"import"=>backend::document_context::Change::Import(request.source_path.ok_or("所选原件路径缺失。")?),"commit"=>backend::document_context::Change::Commit(request.extraction.ok_or("提取文字缺失。")?),_=>backend::document_context::Change::Remove};
                serde_json::to_value(coordinator.change_document_context(backend::document_context::Request{session_id:request.session_id,document_id:request.document_id.ok_or("材料标识缺失。")?,expected_revision:request.revision,change})?).map_err(|_|"材料保存结果无法读取。")?
            }else{
                let snapshot=coordinator.snapshot()?;let row=snapshot.host.sessions.iter().find(|r|r.id==request.session_id).ok_or("这场会议已不存在。")?;
                match request.action.as_str(){
                    "list"=>serde_json::to_value(backend::document_context::describe(row)?).map_err(|_|"材料目录无法读取。")?,
                    "chunk"=>backend::document_context::chunk(row,request.document_id.as_deref().ok_or("材料标识缺失。")?,request.revision,request.offset.ok_or("读取位置缺失。")?)?,
                    "read"=>serde_json::to_value(backend::document_context::extraction(row,request.document_id.as_deref().ok_or("材料标识缺失。")?,request.revision)?).map_err(|_|"材料文字无法读取。")?,
                    "original"=>{backend::document_context::save_original(row,request.document_id.as_deref().ok_or("材料标识缺失。")?,request.revision,Path::new(destination))?;println!("meeting_workspace_result=EXPORTED_LOCAL_DOCUMENT_ORIGINAL");return Ok(());},
                    _=>return Err("不支持的文档材料操作。".into()),
                }
            };
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&result).map_err(|_|"材料结果无法保存。")?)?;println!("meeting_workspace_result=LOCAL_DOCUMENT_OPERATION_COMPLETED");
        } else if operation==17 {
            let request:backend::meeting_note_images::Request=serde_json::from_reader(file).map_err(|_|"图片备注请求格式不正确。")?;let id=request.session_id.clone();let snapshot=coordinator.save_meeting_image_note(request)?;let session=snapshot.host.sessions.iter().find(|s|s.id==id).ok_or("图片备注保存结果缺失。")?;
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&serde_json::json!({"result":"SAVED_LOCAL_IMAGE_NOTE","session":session,"persistenceStatus":snapshot.host.persistence.status,"nativePickerAcceptance":"NOT_RUN"})).map_err(|_|"图片备注结果无法保存。")?)?;println!("meeting_workspace_result=SAVED_LOCAL_IMAGE_NOTE");
        } else if operation==18 {
            #[derive(serde::Deserialize)] #[serde(rename_all="camelCase",deny_unknown_fields)] struct Preview {session_id:String,note_id:String}
            let request:Preview=serde_json::from_reader(file).map_err(|_|"图片预览请求无效。")?;let snapshot=coordinator.snapshot()?;let session=snapshot.host.sessions.iter().find(|s|s.id==request.session_id).ok_or("会议不存在。")?;let data=backend::meeting_note_images::preview(session,&request.note_id)?;backend::export::write_atomic(Path::new(destination),&serde_json::to_vec(&serde_json::json!({"dataUri":data})).map_err(|_|"预览结果无法保存。")?)?;println!("meeting_workspace_result=READ_LOCAL_IMAGE_PREVIEW");
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
        } else if operation == 6 {
            #[derive(serde::Deserialize)] #[serde(rename_all="camelCase",deny_unknown_fields)]
            struct ConnectRequest {device_id:String}
            let request:ConnectRequest=serde_json::from_reader(file).map_err(|_|"连接请求只接受明确设备地址。")?;
            if !backend::same_device_id(&request.device_id,&request.device_id) {return Err("设备地址无效，未扫描或连接。".into());}
            let mut control=control_request(companion_v1::CompanionV1ControlAction::DeviceConnect,None);control.device_id=Some(request.device_id);
            let result=coordinator.apply_control(control);let snapshot=coordinator.snapshot()?;
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(&serde_json::json!({
                "result":if result.is_ok(){"NORMAL_DEVICE_CONNECT_CONFIRMED"}else{"NORMAL_DEVICE_CONNECT_NOT_CONFIRMED"},
                "source":snapshot.source,"connected":snapshot.connected,"device":snapshot.device,"error":result.as_ref().err(),
                "moduleChecks":"NOT_RUN","newRecording":false,"asrRequests":0,"fullChainAcceptance":"NOT_QUALIFIED"
                ,"connectionLifetime":"commandScoped","postExitPairingVerified":false
            })).map_err(|_|"无法保存连接结果。")?)?;
            result?;println!("device_connection_result=NORMAL_DEVICE_CONNECT_CONFIRMED");
        } else if operation == 5 {
            let request:backend::speaker_refinement::Request=serde_json::from_reader(file).map_err(|_|"本地分组请求格式不正确。")?;
            let snapshot=coordinator.refine_meeting_speakers(&request.session_id)?;
            let row=snapshot.host.sessions.iter().find(|r|r.id==request.session_id).ok_or("原会议不存在。")?;
            backend::export::write_atomic(Path::new(destination),&serde_json::to_vec_pretty(row).map_err(|_|"无法保存本地分组结果。")?)?;
            println!("meeting_workspace_result=SAVED_LOCAL_SPEAKER_REFINEMENT cloud_calls=0");
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
    if args.get(1).is_some_and(|a|a=="--recording-pause-timeline") {
        return Some((|| {
            if args.len()!=4 {return Err("--recording-pause-timeline requires original session ID and output path".into());}
            let coordinator=CompanionCoordinator::new_fixture();
            let _lease=coordinator.begin_audio_export()?;
            let timeline=backend::recording_pause_view::prepare(&coordinator.snapshot()?,&args[2])?;
            backend::export::write_atomic(Path::new(&args[3]),&serde_json::to_vec_pretty(&timeline).map_err(|e|e.to_string())?)?;
            println!("recording_timeline_result=VERIFIED_LOCAL_SOURCE_ONLY");
            Ok(())
        })());
    }
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
                Some("pdf") => backend::export::MeetingExportFormat::Pdf,
                Some("docx") => backend::export::MeetingExportFormat::Docx,
                Some("pptx") => backend::export::MeetingExportFormat::Pptx,
                Some("png") => backend::export::MeetingExportFormat::Png,
                Some("bundle") => backend::export::MeetingExportFormat::Bundle,
                Some("mindmap") => backend::export::MeetingExportFormat::Mindmap,
                Some("todo") => backend::export::MeetingExportFormat::Todo,
                Some("ics") => backend::export::MeetingExportFormat::Ics,
                Some("calendar") => backend::export::MeetingExportFormat::Calendar,
                Some("calendarreminder") => backend::export::MeetingExportFormat::CalendarReminder,
                Some("calendarreminder30") => backend::export::MeetingExportFormat::CalendarReminder30,
                Some("calendarreminder60") => backend::export::MeetingExportFormat::CalendarReminder60,
                _ => return Err("unsupported export format".into()),
            };
            let output = args.get(index+4).ok_or("requires output path")?;
            use std::io::Read;
            let mut raw = Vec::new(); fs::File::open(input).map_err(|e| e.to_string())?.take(1_000_001).read_to_end(&mut raw).map_err(|e|e.to_string())?;
            if raw.len()>1_000_000 { return Err("session JSON exceeds 1 MB".into()); }
            let session: companion_v1::CompanionV1HostSession = serde_json::from_slice(&raw).map_err(|e|e.to_string())?;
            let slots=if matches!(format,backend::export::MeetingExportFormat::Calendar|backend::export::MeetingExportFormat::CalendarReminder|backend::export::MeetingExportFormat::CalendarReminder30|backend::export::MeetingExportFormat::CalendarReminder60){
                backend::calendar_copy::latest_saved_slots(&session,mode)?
            } else {None};
            let sections=if format==backend::export::MeetingExportFormat::Pdf {
                args.get(index+5).map(|value|serde_json::from_str::<backend::export::PdfSections>(value).map_err(|e|e.to_string())).transpose()?
            } else {None};
            let prepared = backend::export::prepare_meeting_export_selected(&session,mode,format,None,slots,sections.as_ref())?;
            let data=backend::content_export::materialize_bytes(&session.title,format,prepared.bytes)?;
            let bytes = backend::export::write_atomic(Path::new(output),&data)?;
            println!("meeting_export_json={}",serde_json::json!({"status":"EXPORTED_SAVED_DOCUMENT","bytes":bytes,"warning":prepared.warning,"networkAccess":false,"deviceAccess":false,"fullChainAcceptance":"NOT_RUN"}));
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
    next_automatic_recovery_with_local(snapshot,now_ms,
        backend::product_settings::auto_local_card_transcription_enabled()
            && backend::transcription::local_asr_assets_present())
}

fn next_automatic_recovery_with_local(
    snapshot: &companion_v1::CompanionV1Snapshot, now_ms:u64, local_ready:bool,
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
        let local_card=session.processing_policy==companion_v1::CompanionV1ProcessingPolicy::LocalTranscription;
        if local_card && (!local_ready || session.transcript_final) {continue;}
        if session.processing_policy == companion_v1::CompanionV1ProcessingPolicy::Manual
            || session.pending_reason.as_deref()==Some("needs_local_audio")
            || recovery.intent != "processMeeting"
            || recovery.requested_meeting_mode != session.meeting_mode
            || matches!(recovery.stage.as_str(), "idle" | "paused" | "complete")
        {
            continue;
        }
        if !local_card && recovery.stage == "pendingMinutes"
            && session.transcript_final
            && !session.transcript_text.trim().is_empty()
        {
            return (
                Some((session.id.clone(), AutomaticRecoveryAction::GenerateMinutes)),
                None,
            );
        }
        if recovery.stage == "pendingTranscription"
            && !(session.transcript_final && !session.transcript_text.trim().is_empty()) {
            return (
                Some((session.id.clone(), AutomaticRecoveryAction::Transcribe)),
                None,
            );
        }
        if recovery.stage == "retryBackoff" {
            // Match the exact stage the backend can claim. An inconsistent
            // checkpoint must not spin forever and starve later meetings.
            let action = match recovery.retry_stage.as_str() {
                "transcription" if !(session.transcript_final && !session.transcript_text.trim().is_empty())
                    => AutomaticRecoveryAction::Transcribe,
                "minutes" if !local_card && session.transcript_final && !session.transcript_text.trim().is_empty()
                    => AutomaticRecoveryAction::GenerateMinutes,
                _ => continue,
            };
            let due = recovery.next_retry_at_unix_ms.unwrap_or(now_ms);
            if due <= now_ms {
                return (Some((session.id.clone(), action)), None);
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
            if coordinator.is_shutting_down(){break;}
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
            cache_updates::after(|| {
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
            });
        }
    });
}

fn should_attempt_device_reconnect(snapshot: &companion_v1::CompanionV1Snapshot) -> bool {
    snapshot.device.auto_reconnect_enabled
        && !snapshot.device.manual_disconnect
        && (!backend::segmented_link_change_allowed(snapshot) || !snapshot.device.connected)
        && snapshot.device.remembered_device_id.is_some()
        && !matches!(snapshot.device.connection_phase.as_str(), "reconnecting" | "busy" | "pairingRequired")
        && (backend::segmented_link_change_allowed(snapshot) || backend::automatic_original_reconnect_pending(snapshot) || (!snapshot.meeting.active
        && !snapshot
            .host
            .sessions
            .iter()
            .any(|session| session.status == "recording")))
}

fn spawn_continuous_recording_sync(coordinator: Arc<CompanionCoordinator>) {
    if std::env::var("COMPANION_TYPE_DISABLE_AUTO_RECOVERY").as_deref() == Ok("1") { return; }
    std::thread::spawn(move || {
        let mut failures = 0u32;
        loop {
            if coordinator.is_shutting_down(){break;}
            let work = coordinator.snapshot().and_then(|snapshot| {
                if !snapshot.device.connected && (backend::segmented_link_change_allowed(&snapshot)
                    || backend::automatic_original_reconnect_pending(&snapshot))
                    && should_attempt_device_reconnect(&snapshot) {
                    coordinator.automatic_reconnect_once().map(|_| true)
                } else { coordinator.follow_recording_once() }
            });
            // A no-op or occupied lease has not published a new library.
            if matches!(&work, Ok(true)) || work.as_ref().is_err_and(|e| !e.contains("device is busy with")) {
                cache_updates::changed();
            }
            let wait = match work {
                Ok(active) => { failures = 0; if active { 2 } else { 10 } },
                Err(error) if error.contains("device is busy with") => 2,
                Err(error) => {
                    failures = failures.saturating_add(1).min(5);
                    eprintln!("[recording-follow] local audio/cursors kept; {error}");
                    (1u64 << failures).min(60)
                }
            };
            std::thread::sleep(std::time::Duration::from_secs(wait));
        }
    });
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
            if coordinator.is_shutting_down(){break;}
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
            match cache_updates::after(|| coordinator.automatic_reconnect_once()) {
                Ok(_) => {
                    failed_attempts = 0;
                    std::thread::sleep(std::time::Duration::from_secs(60));
                }
                Err(error) if error.contains("device is busy with") => {
                    std::thread::sleep(std::time::Duration::from_secs(2));
                }
                Err(error) if backend::reconnect_requires_pairing(&error) => {
                    failed_attempts=0;
                    eprintln!("[device-reconnect] pairing needs explicit action; original recording kept; automatic pairing paused: {error}");
                    std::thread::sleep(std::time::Duration::from_secs(5));
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

/// Recover/control a durable original through the same coordinator as the GUI.
/// No scan, replacement START, supplied audio, or fallback to another row.
/// An explicit retry-start can only replay that row's unconfirmed START.
fn original_recorder_request(args: &[String]) -> Result<(companion_v1::CompanionV1ControlRequest, Option<PathBuf>), String> {
    use companion_v1::CompanionV1ControlAction as Action;
    let mut values = std::collections::BTreeMap::new();
    let mut i = 1;
    while i < args.len() {
        let flag = &args[i];
        if !matches!(flag.as_str(), "--recorder-control" | "--session-id" | "--device-id" | "--output") {
            return Err(format!("原录音控制不接受参数 {flag}，未连接设备。"));
        }
        let value = args.get(i + 1).filter(|value| !value.trim().is_empty() && !value.starts_with("--"))
            .ok_or_else(|| format!("{flag} 需要明确的值，未连接设备。"))?;
        if values.insert(flag.as_str(), value.clone()).is_some() {
            return Err(format!("{flag} 重复，未连接设备。"));
        }
        i += 2;
    }
    let action = match values.get("--recorder-control").map(String::as_str) {
        Some("recover") => Action::MeetingRecoverControl,
        Some("pause") => Action::MeetingPause,
        Some("resume") => Action::MeetingResume,
        Some("stop") => Action::MeetingStop,
        Some("finalize") => Action::MeetingFinalize,
        Some("retry-start") => Action::MeetingStart,
        _ => return Err("原录音控制仅接受 recover/pause/resume/stop/finalize/retry-start；不会创建替代录音。".into()),
    };
    let host = values.get("--session-id").ok_or("必须指定原录音 --session-id，未选择其它会议。")?;
    let mut request = control_request(action, Some(host.clone()));
    request.device_id = values.get("--device-id").cloned();
    Ok((request, values.get("--output").map(PathBuf::from)))
}

fn bind_original_recorder_request(snapshot: &companion_v1::CompanionV1Snapshot,
    request: &mut companion_v1::CompanionV1ControlRequest) -> Result<(), String> {
    if snapshot.host.persistence.status != "ready" { return Err("原录音库暂时不可读，未连接设备。".into()); }
    let host = request.session_id.as_deref().ok_or("原录音行缺失。")?;
    let row = snapshot.host.sessions.iter().find(|row| row.id == host).ok_or("指定原录音不存在，未创建替代会议。")?;
    let journal = row.recorder_control.as_ref().ok_or("原录音没有耐久控制记录，未发送命令。")?;
    let same = |a: &str, b: &str| a.eq_ignore_ascii_case(b);
    if row.source != "boardDevice" || journal.host_session != host
        || row.source_device_id.as_deref().is_none_or(|d| !same(d, &journal.device_id))
        || request.device_id.as_deref().is_some_and(|d| !same(d, &journal.device_id)) {
        return Err("指定行、设备与原控制身份不一致，未控制其它录音。".into());
    }
    request.device_id = Some(journal.device_id.clone());
    if request.action==companion_v1::CompanionV1ControlAction::MeetingStart {
        request.duration_ms=Some(u64::from(journal.max_seconds)*1000);
        if !backend::recorder_control::unconfirmed_start_retry_request(snapshot,request) {
            return Err("只有原始开始请求尚未确认时才能明确重试；未重开已确认录音。".into());
        }
    }
    Ok(())
}

fn run_recorder_control_cli(args: &[String]) -> Option<Result<(), String>> {
    if !args.iter().any(|arg| arg == "--recorder-control") { return None; }
    Some((|| {
        let (mut request, output) = original_recorder_request(args)?;
        let _ = backend::product_settings::load_and_apply();
        let coordinator = CompanionCoordinator::new_fixture();
        bind_original_recorder_request(&coordinator.snapshot()?, &mut request)?;
        let host = request.session_id.clone().unwrap();
        let result = coordinator.apply_control(request);
        // Preserve the actual original after errors too: the product may have
        // durably confirmed a command before receipt/another step failed.
        let snapshot = coordinator.snapshot()?;
        let row = snapshot.host.sessions.iter().find(|row| row.id == host).ok_or("控制后原录音行缺失。")?;
        let catalogue_ended=row.recorder_control.as_ref().is_some_and(|j|j.sealed_catalogue_end.is_some());
        let payload = serde_json::json!({"result": if result.is_ok() && catalogue_ended {"ORIGINAL_SEALED_RECORDING_RECOVERED_FROM_CATALOGUE"}
            else if result.is_ok() {"ORIGINAL_CONTROL_CONFIRMED"} else {"ORIGINAL_CONTROL_FAILED_OR_UNCONFIRMED"},
            "sessionId": host, "error": result.as_ref().err(), "meetingStatus": snapshot.meeting.status,
            "connected": snapshot.device.connected, "recording": snapshot.device.recording,
            "session": row, "lastControl": snapshot.last_control});
        if let Some(path) = output { fs::write(&path, serde_json::to_vec_pretty(&payload).map_err(|e|e.to_string())?)
            .map_err(|e| format!("保存原控制结果：{e}"))?; }
        println!("recorder_control_result_json={payload}");
        result.map(|_| ())
    })())
}

fn capture_pause_schedule(args: &[String], seconds: u64, incompatible: bool) -> Result<Option<(u64,u64)>,String> {
    let time = |flag: &str| -> Result<Option<u64>,String> {
        let positions: Vec<usize> = args.iter().enumerate().filter_map(|(i,a)|(a==flag).then_some(i)).collect();
        if positions.len()>1 {return Err(format!("{flag} is repeated; no device command was sent"));}
        positions.first().map(|i|args.get(i+1).ok_or_else(||format!("{flag} requires seconds"))?
            .parse::<u64>().map_err(|_|format!("{flag} requires integer seconds"))).transpose()
    };
    match (time("--capture-pause-at")?,time("--capture-resume-at")?) {
        (None,None)=>Ok(None),
        (Some(pause),Some(resume)) if !incompatible && 0<pause && pause<resume && resume<seconds =>Ok(Some((pause,resume))),
        _=>Err("Pause requires 0 < pause < resume < recording seconds; isolate it from disconnect/limit recovery before connecting".into()),
    }
}

fn capture_start_duration(args: &[String], seconds: u64, follow: bool, recover_after_limit: bool) -> Result<u64, String> {
    if args.iter().any(|arg| arg == "--no-recording-limit") {
        if !follow || recover_after_limit {
            return Err("No-limit capture requires following the original segments and cannot exercise limit recovery".into());
        }
        // Zero takes the ordinary product path, including firmware identity and
        // capacity checks. The test still explicitly stops after `seconds`.
        Ok(0)
    } else {
        Ok((seconds + if recover_after_limit { 0 } else { 30 }) * 1_000)
    }
}

// Observe the coordinator's existing in-memory snapshot. Acceptance consumers
// must not repeatedly open the mutable session index while it is being saved.
fn emit_capture_progress(row: &companion_v1::CompanionV1HostSession, elapsed_ms: u128) {
    println!("v1_real_meeting_progress_json={}", serde_json::json!({
        "id": row.id,
        "status": row.status,
        "deviceRecordingId": row.device_recording_id,
        "deviceRecordingKey": row.device_recording_key,
        "sealedChunks": row.chunks.iter().filter(|chunk| chunk.status == "sealed").count(),
        "captureElapsedMs": elapsed_ms,
    }));
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
            .clamp(2, 86_400);
        // Exercise the ordinary application's recovery with the same live
        // coordinator: let the actual board limit seal its original recording
        // and reconnect. No synthetic STOP acknowledgement or new process.
        let recover_after_limit = args.iter().any(|arg| arg == "--recover-after-limit");
        let follow_original = args.iter().any(|arg| arg == "--follow-original-segments");
        if follow_original && recover_after_limit {
            return Err("An offline limit exercise cannot follow a disconnected original".into());
        }
        let start_duration_ms = capture_start_duration(args, seconds, follow_original, recover_after_limit)?;
        // These exercise the normal product's disconnect/connect actions while
        // its original capture is still open. Actual radio loss is established
        // separately by HCI/UART, never inferred from a reducer acknowledgement.
        let capture_time = |flag: &str| -> Result<Option<u64>, String> {
            args.iter().position(|arg| arg == flag).map(|i| {
                args.get(i + 1).ok_or_else(|| format!("{flag} requires seconds"))?
                    .parse::<u64>().map_err(|_| format!("{flag} requires integer seconds"))
            }).transpose()
        };
        let capture_disconnect_at = capture_time("--capture-disconnect-at")?;
        let capture_reconnect_at = capture_time("--capture-reconnect-at")?;
        let capture_recovery = match (capture_disconnect_at, capture_reconnect_at) {
            (None, None) => None,
            (Some(disconnect), Some(reconnect))
                if !recover_after_limit && 0 < disconnect && disconnect < reconnect && reconnect < seconds =>
                    Some((disconnect, reconnect)),
            _ => return Err("Capture recovery requires 0 < disconnect < reconnect < recording seconds and cannot combine with limit recovery".into()),
        };
        let capture_pause = capture_pause_schedule(args,seconds,recover_after_limit||capture_recovery.is_some()||follow_original)?;
        let sync_schedule=recorder_sync_exercise::schedule(args,seconds,
            follow_original && !recover_after_limit && capture_recovery.is_none() && capture_pause.is_none())?;
        let coordinator = CompanionCoordinator::new_fixture();

        let device_id = if let Some(id)=requested_device {id} else {
            coordinator.apply_control(control_request(companion_v1::CompanionV1ControlAction::DeviceScan,None))?
                .device.device_id.ok_or("Recording scan returned no Companion device id")?
        };
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
        start.title = Some("设备录音".to_string());
        start.prompt_id = Some(companion_v1::CAPTURE_ONLY_PROMPT.into());
        start.meeting_mode = Some("offlineStore".to_string());
        start.device_id = Some(device_id.clone());
        start.duration_ms = Some(start_duration_ms);
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
        let started_logical_key = started_session.device_recording_key.clone();
        eprintln!("recording_capture_stage stage=started physical_anchor={} logical={}",start_recording_id,started_logical_key.is_some());
        emit_capture_progress(started_session, 0);
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
        let capture_started=std::time::Instant::now();
        let sync_pause=sync_schedule.map(|(pause,_)|recorder_sync_exercise::Pause::start(device_id.clone(),capture_started,pause));
        let mut sync_pause_observed:Option<serde_json::Value>=None;
        let mut sync_resume_observed:Option<serde_json::Value>=None;
        let capture_deadline=capture_started+std::time::Duration::from_secs(seconds + if recover_after_limit {3} else {0});
        let mut followed_during_capture=false;
        let mut sealed_segments_during_capture=0usize;
        let mut capture_disconnect_requested=false;
        let mut capture_reconnect_original_confirmed=false;
        let mut pause_confirmed:Option<serde_json::Value>=None;
        let mut resume_confirmed:Option<serde_json::Value>=None;
        while std::time::Instant::now()<capture_deadline {
            let poll = if capture_pause.is_some() {std::time::Duration::from_millis(100)}
                else {std::time::Duration::from_secs(5)};
            std::thread::sleep(capture_deadline.saturating_duration_since(std::time::Instant::now()).min(poll));
            if let (Some((_,resume_at)),Some(exercise))=(sync_schedule,sync_pause.as_ref()) {
                if sync_pause_observed.is_none() {
                    if let Some(observation)=exercise.observation()? {
                        let snapshot=coordinator.snapshot()?;
                        let row=snapshot.host.sessions.iter().find(|r|r.id==session_id).ok_or("Sync pause lost original row")?;
                        if row.status!="recording" || !snapshot.device.recording || row.device_recording_key!=started_logical_key
                            || row.recorder_control.as_ref().map(|j|j.start_request)!=started_session.recorder_control.as_ref().map(|j|j.start_request)
                            || backend::recording_sync::owned_follow_allowed(&device_id) {
                            return Err("Sync pause did not retain the same active original".into());
                        }
                        sync_pause_observed=Some(serde_json::json!({"pause":observation,"chunksAtPause":row.chunks.len(),
                            "recordingStillActive":true,"originalStartUnchanged":true,"logicalKey":row.device_recording_key}));
                    }
                }
                if sync_resume_observed.is_none() && capture_started.elapsed().as_secs()>=resume_at {
                    let paused=sync_pause_observed.as_ref().ok_or("Sync pause was not confirmed before resume")?;
                    let before=coordinator.snapshot()?;
                    let row=before.host.sessions.iter().find(|r|r.id==session_id).ok_or("Original row missing before resume")?;
                    if row.chunks.len() as u64!=paused["chunksAtPause"].as_u64().ok_or("Pause chunk count missing")?
                        || backend::recording_sync::owned_follow_allowed(&device_id) {
                        return Err("A paused original received new segments before explicit resume".into());
                    }
                    let mut request=control_request(companion_v1::CompanionV1ControlAction::DeviceSyncRecordings,Some(session_id.clone()));
                    request.device_id=Some(device_id.clone());
                    let resumed=coordinator.apply_control(request)?;
                    let row=resumed.host.sessions.iter().find(|r|r.id==session_id).ok_or("Resume lost original row")?;
                    if row.status!="recording" || !resumed.device.recording || row.device_recording_key!=started_logical_key
                        || row.device_recording_id!=Some(start_recording_id) || row.device_reclaimed
                        || row.recorder_control.as_ref().map(|j|j.start_request)!=started_session.recorder_control.as_ref().map(|j|j.start_request)
                        || !backend::recording_sync::owned_follow_allowed(&device_id) || row.chunks.is_empty() {
                        return Err("Resume did not receive the same active original; no replacement START sent".into());
                    }
                    sync_resume_observed=Some(serde_json::json!({"elapsedMs":capture_started.elapsed().as_millis(),
                        "chunksAfterResume":row.chunks,"recordingStillActive":true,"originalStartUnchanged":true,
                        "logicalKey":row.device_recording_key,"wholeDeviceReclaimed":row.device_reclaimed}));
                    eprintln!("capture_sync_pause stage=resumed_same_original elapsed_ms={} received_segments={} microphone_command=false",capture_started.elapsed().as_millis(),row.chunks.len());
                }
            }
            if let Some((pause_at,resume_at))=capture_pause {
                let requested = if pause_confirmed.is_none() && capture_started.elapsed().as_secs()>=pause_at {
                    Some((companion_v1::CompanionV1ControlAction::MeetingPause,4u8,3u8))
                } else if pause_confirmed.is_some() && resume_confirmed.is_none() && capture_started.elapsed().as_secs()>=resume_at {
                    Some((companion_v1::CompanionV1ControlAction::MeetingResume,5u8,1u8))
                } else {None};
                if let Some((action,command,state))=requested {
                    let mut request=control_request(action,Some(session_id.clone()));
                    request.device_id=Some(device_id.clone());
                    let snapshot=coordinator.apply_control(request)?;
                    let row=snapshot.host.sessions.iter().find(|row|row.id==session_id).ok_or("Pause control lost original row")?;
                    let journal=row.recorder_control.as_ref().ok_or("Pause control lost original durable command")?;
                    let confirmed=journal.confirmed.as_ref().ok_or("Pause control has no stable device reply")?;
                    if journal.pending.is_some() || row.recorder_control_uncertain || confirmed.command!=command || confirmed.state!=state
                        || row.device_recording_id!=Some(start_recording_id) || row.device_recording_key!=started_logical_key
                        || journal.start_request!=started_session.recorder_control.as_ref().ok_or("Original START missing")?.start_request
                        || !snapshot.meeting.active || row.status!="recording"
                        || snapshot.device.recording!=(state==1) || snapshot.meeting.status!=if state==3 {"paused"} else {"recording"} {
                        return Err("Pause/resume did not confirm the same stable original; no replacement START".into());
                    }
                    let observation=serde_json::json!({"elapsedMs":capture_started.elapsed().as_millis(),
                        "journal":journal,"deviceRecording":snapshot.device.recording,"meetingStatus":snapshot.meeting.status,
                        "durationMs":row.duration_ms,"physicalAnchor":start_recording_id,"logicalKey":row.device_recording_key});
                    eprintln!("capture_pause stage={} elapsed_ms={} source_duration_ms={} sequence={} physical_anchor={} new_start_sent=false",
                        if state==3 {"paused"} else {"resumed"},capture_started.elapsed().as_millis(),row.duration_ms,confirmed.sequence,start_recording_id);
                    if state==3 {pause_confirmed=Some(observation);} else {resume_confirmed=Some(observation);}
                }
            }
            if let Some((disconnect, reconnect))=capture_recovery {
                if !capture_disconnect_requested && capture_started.elapsed().as_secs() >= disconnect {
                    let mut request=control_request(companion_v1::CompanionV1ControlAction::DeviceDisconnect,
                        Some(session_id.clone()));
                    request.device_id=Some(device_id.clone());
                    let snapshot=coordinator.apply_control(request)?;
                    if snapshot.connected || snapshot.device.connected {
                        return Err("Capture disconnect action did not release the product connection".into());
                    }
                    capture_disconnect_requested=true;
                    eprintln!("capture_recovery stage=disconnect_requested elapsed_ms={} physical_anchor={} microphone_stop_sent=false radio_disconnect=await_hci",
                        capture_started.elapsed().as_millis(), start_recording_id);
                }
                if capture_disconnect_requested && !capture_reconnect_original_confirmed
                    && capture_started.elapsed().as_secs() >= reconnect {
                    let mut request=control_request(companion_v1::CompanionV1ControlAction::DeviceConnect,
                        Some(session_id.clone()));
                    request.device_id=Some(device_id.clone());
                    let snapshot=coordinator.apply_control(request)?;
                    let row=snapshot.host.sessions.iter().find(|row|row.id==session_id)
                        .ok_or("Capture reconnect lost the original library row")?;
                    if !snapshot.connected || !snapshot.device.connected || !snapshot.device.recording
                        || row.status!="recording" || row.device_recording_id!=Some(start_recording_id)
                        || row.device_recording_key!=started_logical_key
                        || row.recorder_control.as_ref().map(|j|j.start_request)
                            != started_session.recorder_control.as_ref().map(|j|j.start_request) {
                        return Err("Capture reconnect did not confirm the same still-recording original; no replacement START".into());
                    }
                    capture_reconnect_original_confirmed=true;
                    eprintln!("capture_recovery stage=original_capture_reconnected elapsed_ms={} physical_anchor={} new_start_sent=false",
                        capture_started.elapsed().as_millis(), start_recording_id);
                }
            }
            if started_logical_key.is_some() && !recover_after_limit && capture_pause.is_none()
                && (!capture_disconnect_requested || capture_reconnect_original_confirmed) {
                let _ = if follow_original { coordinator.follow_original_recording_once(&session_id)? }
                    else { coordinator.follow_recording_once()? };
                let snapshot = coordinator.snapshot()?;
                let row = snapshot.host.sessions.iter().find(|r| r.id == session_id)
                    .ok_or("The original recording row disappeared during live receive")?;
                if row.device_recording_key != started_logical_key || row.device_recording_id != Some(start_recording_id) {
                    return Err("Live receive changed the original recording identity".into());
                }
                sealed_segments_during_capture = sealed_segments_during_capture.max(
                    row.chunks.iter().filter(|c| c.status == "sealed").count());
                followed_during_capture = sealed_segments_during_capture > 0;
                emit_capture_progress(row, capture_started.elapsed().as_millis());
            }
        }

        let mut stop = control_request(
            companion_v1::CompanionV1ControlAction::MeetingStop,
            Some(session_id.clone()),
        );
        stop.device_id = Some(device_id.clone());
        let stop_requested_at = std::time::Instant::now();
        let mut stopped = if recover_after_limit {
            let mut reconnect = control_request(
                companion_v1::CompanionV1ControlAction::DeviceConnect, Some(session_id.clone()));
            reconnect.device_id = Some(device_id.clone());
            coordinator.apply_control(reconnect)?
        } else { coordinator.apply_control(stop)? };
        if recover_after_limit && stopped.host.sessions.iter().any(|row|
            row.id == session_id && row.source == "boardDevice" && row.status == "captured"
                && row.device_recording_id == Some(start_recording_id)
                && row.device_recording_key == started_logical_key && !row.audio_stored)
        {
            // Isolated capture intentionally disables automatic backlog pulls.
            // After the protected probe closes this original meeting, explicitly
            // use the product sync action; never send STOP or create another START.
            eprintln!("offline_recovery stage=explicit_original_receive microphone_stop_sent=false");
            let mut sync = control_request(
                companion_v1::CompanionV1ControlAction::DeviceSyncRecordings, Some(session_id.clone()));
            sync.device_id = Some(device_id.clone());
            stopped = coordinator.apply_control(sync)?;
        }
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
        let legacy_identity_complete=stop_session.device_total_length.unwrap_or(0)>0
            && stop_session
                .device_sha256
                .as_deref()
                .unwrap_or_default()
                .len()
                ==64;
        let logical_identity_complete=started_logical_key.as_ref().is_some_and(|key|
            stop_session.device_recording_key.as_ref()==Some(key)) && stop_session.audio_stored
            && backend::recording_wire::receiver::Receiver::verify_saved_row(stop_session).is_ok();
        if !(legacy_identity_complete || logical_identity_complete) || !stop_session
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
                && (legacy_identity_complete || logical_identity_complete),
            "pulledWav": session.audio_path.as_deref().is_some_and(|path| Path::new(path).is_file()),
            "durableDeviceConsume": session.device_reclaimed,
            "completeCapture": !session.capture_incomplete,
            "endedMeetingUnlocked": !finalized.meeting.active && !finalized.device.recording
                && finalized.host.active_session_id.is_none(),
            "noInventedStopTime": !recover_after_limit || session.stopped_at.is_none(),
            "originalLinkDisconnected": !recover_after_limit || recovery_link_disconnected,
            "captureRecoveryActions": capture_recovery.is_none()
                || (capture_disconnect_requested && capture_reconnect_original_confirmed),
            "originalLiveSegmentsReceived": !follow_original || followed_during_capture,
            "originalPauseResumeConfirmed": capture_pause.is_none() || (pause_confirmed.is_some() && resume_confirmed.is_some()),
            "syncPauseAndResumeSameRecording": sync_schedule.is_none() || (sync_pause_observed.is_some() && sync_resume_observed.is_some()),
        });
        let pass = checks.as_object().is_some_and(|checks| {
            checks
                .values()
                .all(|value| value == &serde_json::Value::Bool(true))
        });
        let payload = serde_json::json!({
            "schema": "companion.real-recording-control.v2",
            "sealedSegmentsReceivedDuringCapture": sealed_segments_during_capture,
            "syncPause":sync_pause_observed,"syncResume":sync_resume_observed,
            "result": if pass { "PASS_RECORDING_CONTROL_AND_RECEIVE_STAGE_ONLY" } else { "FAIL_RECORDING_CONTROL_AND_RECEIVE_STAGE" },
            "scope": if recover_after_limit { "original_ended_recording_reconnect_and_durable_receive_only" }
                else { "recording_control_and_durable_receive_only" },
            "source": "board_device",
            "hostMic": false,
            "seed": false,
            "asr": "NOT_RUN",
            "minutes": "NOT_RUN",
            "processingPolicy": session.processing_policy,
            "fullChainAcceptance": "NOT_RUN",
            "stopToDurableReceiveMs": if recover_after_limit { None } else { Some(stop_to_durable_receive_ms) },
            "reconnectToDurableReceiveMs": if recover_after_limit { Some(stop_to_durable_receive_ms) } else { None },
            "normalStopAcknowledged": !recover_after_limit,
            "recoveryLinkDisconnected": recovery_link_disconnected,
            "sessionId": session_id,
            "deviceId": device_id,
            "recordingId": recording_id,
            "startRecordingId": start_recording_id,
            "logicalRecordingKey": session.device_recording_key,
            "sealedSegmentFollowDuringCapture": followed_during_capture,
            "captureRecoveryRequested": capture_recovery.is_some(),
            "captureDisconnectRequested": capture_disconnect_requested,
            "captureOriginalReconfirmed": capture_reconnect_original_confirmed,
            "captureRadioDisconnect": if capture_recovery.is_some() { "VERIFY_WITH_ACTUAL_HCI_UART" } else { "NOT_REQUESTED" },
            "pauseObservation":pause_confirmed,"resumeObservation":resume_confirmed,
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

fn verified_synced_audio(session: &companion_v1::CompanionV1HostSession) -> bool {
    if !session.audio_stored || session.status=="recording" || !session.retention.audio_cached
        || !matches!(session.source.as_str(),"boardDevice"|"deviceFlash") {return false;}
    if session.device_recording_key.is_some() {
        return backend::recording_wire::receiver::Receiver::verify_saved_row(session).is_ok();
    }
    let Some(path)=session.audio_path.as_deref().map(Path::new).filter(|p|p.is_absolute()) else {return false;};
    session.device_recording_id.is_some()
        && fs::symlink_metadata(path).is_ok_and(|m|m.is_file() && !m.file_type().is_symlink() && m.len()==session.audio_bytes)
        && backend::meeting_workspace::wav_duration_ms(path).is_ok_and(|duration|duration==session.duration_ms)
}

/// A selected growing/partial meeting cannot hide originals saved by this
/// batch. Receipt verification, rather than file existence, admits each result.
fn synced_device_audio(snap:&companion_v1::CompanionV1Snapshot) -> Result<&companion_v1::CompanionV1HostSession,String> {
    snap.host.selected_session_id.as_deref().and_then(|id|snap.host.sessions.iter().find(|s|s.id==id))
        .filter(|s|verified_synced_audio(s))
        .or_else(||snap.host.sessions.iter().find(|s|verified_synced_audio(s)))
        .ok_or_else(||"设备片段已保存在录音库，但还没有收齐并校验的本机原音；未把部分录音当作完成。".into())
}

fn run_recording_upload_benchmark_cli(args: &[String]) -> Option<Result<(), String>> {
    if !args.iter().any(|a|a=="--benchmark-recording-upload") { return None; }
    Some((|| {
        let required = |name: &str| -> Result<&str, String> {
            let positions: Vec<_> = args.iter().enumerate().filter(|(_,a)|a.as_str()==name).map(|(i,_)|i).collect();
            if positions.len()!=1 {return Err(format!("exactly one {name} is required"));}
            args.get(positions[0]+1).filter(|v|!v.starts_with("--")).map(String::as_str)
                .ok_or_else(||format!("missing {name} value"))
        };
        let profiles = if args.iter().any(|a|a=="--benchmark-value-profiles") {
            Some(required("--benchmark-value-profiles")?.split(',').map(|s|
                s.parse::<u16>().map_err(|_|"benchmark profiles must be comma-separated integers".to_string()))
                .collect::<Result<Vec<_>,_>>()?)
        } else { None };
        let report = backend::benchmark_recording_upload(required("--device-id")?,
            Path::new(required("--benchmark-sample")?), Path::new(required("--benchmark-output")?),
            profiles.as_deref(), args.iter().any(|a|a=="--benchmark-capture-setup"))?;
        println!("recording_upload_benchmark_json={report}");
        Ok(())
    })())
}

// Explicit diagnostic operation: release one already verified single-segment
// recording. It cannot select other device sessions or erase local audio.
fn run_release_one_saved_segment_cli(args:&[String])->Option<Result<(),String>> {
    let position=args.iter().position(|s|s=="--release-one-saved-segment")?;
    Some((|| {
        let value=|flag:&str| -> Result<&str,String> {
            let indexes=args.iter().enumerate().filter(|(_,s)|s.as_str()==flag).map(|(i,_)|i).collect::<Vec<_>>();
            if indexes.len()!=1 {return Err(format!("需要明确且唯一的{flag}。"));}
            args.get(indexes[0]+1).filter(|v|!v.starts_with("--")).map(String::as_str).ok_or_else(||format!("{flag}缺少值。"))
        };
        if args.iter().filter(|s|s.as_str()=="--release-one-saved-segment").count()!=1 {return Err("释放请求不唯一。".into());}
        let receipt=Path::new(args.get(position+1).filter(|v|!v.starts_with("--")).ok_or("缺少本机原录音回执。")?);
        let encoded=Path::new(value("--encoded-path")?);
        let device=value("--device-id")?;
        let id=value("--recording-id")?.parse::<u32>().map_err(|_|"录音编号无效。")?;
        let expected_sha=value("--expected-sha256")?.to_ascii_lowercase();
        let root=PathBuf::from(std::env::var_os("COMPANION_TYPE_RECORDING_DIR").ok_or("必须指定隔离本机录音目录。")?);
        let root=fs::canonicalize(root).map_err(|_|"本机录音目录不存在。")?;
        for path in [receipt,encoded] {
            let meta=fs::symlink_metadata(path).map_err(|_|"本机备份文件不可读。")?;
            if !meta.is_file() || meta.file_type().is_symlink() || !fs::canonicalize(path).map_err(|_|"备份路径不可核对。")?.starts_with(&root) {
                return Err("回执和原始数据必须是指定本机录音目录中的普通文件。".into());
            }
        }
        let receipt_bytes=fs::read(receipt).map_err(|_|"无法读取本机原录音回执。")?;
        if receipt_bytes.len()>1024*1024 {return Err("本机回执过大。".into());}
        let saved:serde_json::Value=serde_json::from_slice(&receipt_bytes).map_err(|_|"本机回执格式无效。")?;
        let segments=saved.get("segments").and_then(|v|v.as_array()).ok_or("本机回执缺少录音段。")?;
        if segments.len()!=1 || segments[0].get("received").and_then(|v|v.as_bool())!=Some(true)
            || segments[0].get("acked").and_then(|v|v.as_bool())!=Some(false) {return Err("本机回执不是一段已保存未释放的原录音。".into());}
        let wire:Vec<u8>=serde_json::from_value(segments[0].get("wire").cloned().ok_or("缺少原录音描述。")?).map_err(|_|"原录音描述无效。")?;
        let descriptor=backend::recording_wire::Descriptor::decode(&wire)?;
        let payload=fs::read(encoded).map_err(|_|"无法读取本机原始压缩数据。")?;
        descriptor.verify_payload(&payload)?;
        if descriptor.recording_id!=id || format!("{:x}",Sha256::digest(&payload))!=expected_sha {
            return Err("指定编号或摘要与已备份原录音不一致，未释放。".into());
        }
        let snapshot=CompanionCoordinator::new_fixture().snapshot()?;
        let rows=snapshot.host.sessions.iter().filter(|row|row.device_recording_key.as_ref()
            .and_then(|key|backend::recording_wire::SessionKey::from_public(key).ok()).as_ref()==Some(&descriptor.key)).collect::<Vec<_>>();
        if rows.len()!=1 || !verified_synced_audio(rows[0]) || rows[0].device_reclaimed || rows[0].capture_incomplete
            || !rows[0].source_device_id.as_deref().is_some_and(|saved|backend::same_device_id(saved,device)) {
            return Err("本机完整备份或原设备身份未核对，未释放。".into());
        }
        backend::release_one_saved_segment(device,&descriptor)?;
        descriptor.verify_payload(&fs::read(encoded).map_err(|_|"释放后本机原始文件不可读。")?)?;
        println!("release_one_saved_segment_result=EXACT_ORIGINAL_RELEASED_LOCAL_RAW_REVERIFIED recording_id={id}");
        Ok(())
    })())
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
        if let Some(index)=args.iter().position(|arg|arg=="--recording-key") {
            let path=args.get(index+1).filter(|value|!value.starts_with("--"))
                .ok_or("--recording-key requires an exact saved logical key JSON file")?;
            let device=device_id.as_deref().ok_or("Exact-session sync requires --device-id; no scan was started")?;
            let file=fs::File::open(path).map_err(|e|e.to_string())?;
            if file.metadata().map_err(|e|e.to_string())?.len()>1024 {return Err("Recording key file is too large".into());}
            let mut key:companion_v1::CompanionV1RecordingKey=serde_json::from_reader(file).map_err(|e|e.to_string())?;
            key.device_uid.make_ascii_lowercase();key.format_epoch.make_ascii_lowercase();key.session_id.make_ascii_lowercase();
            backend::sync_selected_recording_key(device,&key)?;
            let snap=CompanionCoordinator::new_fixture().snapshot()?;
            let row=snap.host.sessions.iter().find(|row|row.device_recording_key.as_ref()==Some(&key))
                .ok_or("The selected recording did not publish a durable library row")?;
            if !verified_synced_audio(row) {return Err("The selected recording is still partial; saved progress was retained".into());}
            let payload=serde_json::json!({"result":"EXACT_SESSION_RECEIVE_COMPLETED","session":row,
                "deviceId":device,"logicalKey":key,"microphoneCommands":0});
            println!("sync_device_recording_result_json={payload}");
            return Ok(());
        }
        if device_id.is_none() {
            if let Ok(scan) = coordinator.apply_control(companion_v1::CompanionV1ControlRequest { minutes_template: None, recording_source: None,
                action: companion_v1::CompanionV1ControlAction::DeviceScan,
                context_note_revision: None, ble_name: None,
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
        let snap = coordinator.apply_control(companion_v1::CompanionV1ControlRequest { minutes_template: None, recording_source: None,
            action: companion_v1::CompanionV1ControlAction::DeviceSyncRecordings,
            context_note_revision: None, ble_name: None,
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
            .filter(|session| session.device_recording_id.is_some() || session.device_recording_key.is_some())
            .collect::<Vec<_>>();
        let session = synced_device_audio(&snap)?;
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
            "scope": "verified_local_original_audio_only_not_capture_or_meeting_acceptance",
            "pendingAudioSessions": device_sessions.iter().filter(|item|!item.audio_stored).count(),
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
                "audioStored": item.audio_stored,
                "captureIncomplete": item.capture_incomplete,
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
    companion_v1::CompanionV1ControlRequest { minutes_template: None, recording_source: None,
        action,
        context_note_revision: None, ble_name: None,
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
fn recording_library_targets(mut candidates: Vec<(u32,String,bool)>, recording: Option<u32>, host: Option<&str>)
    -> Result<Vec<(u32,String,bool)>,String> {
    if host.is_some_and(|id| id.is_empty() || id.starts_with("--")) {
        return Err("--session-id requires the exact saved meeting identity; no recording was processed".into());
    }
    candidates.retain(|(id,session,_)| recording.is_none_or(|wanted|wanted==*id)
        && host.is_none_or(|wanted|wanted==session));
    if recording.is_some() && host.is_none() && candidates.len()>1 {
        return Err("The device recording number belongs to multiple saved meetings. Specify --session-id; no recording was processed".into());
    }
    if candidates.is_empty() || (host.is_some() && candidates.len()!=1) {
        return Err("No unique saved board meeting matches this recording/session identity; no recording was processed".into());
    }
    candidates.sort_by(|a,b|a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    Ok(candidates)
}

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
        let requested_session_id=if let Some(index)=args.iter().position(|arg|arg=="--session-id") {
            if args.iter().filter(|arg|arg.as_str()=="--session-id").count()!=1 {
                return Err("--session-id must occur once; no recording was processed".into());
            }
            Some(args.get(index+1).filter(|id|!id.is_empty()&&!id.starts_with("--"))
                .ok_or("--session-id requires the exact saved meeting identity")?.clone())
        } else {None};
        let recovery_audio_path = args
            .windows(2)
            .find(|pair| pair[0] == "--recover-audio-path")
            .map(|pair| PathBuf::from(&pair[1]));
        if let Some(path) = recovery_audio_path.as_ref() {
            if requested_session_id.is_some() {
                return Err("Legacy --recover-audio-path cannot be combined with a segmented meeting identity; use normal original-recording recovery".into());
            }
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
        let candidates = initial
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
            .collect::<Vec<_>>();
        let targets=recording_library_targets(candidates,requested_recording_id,requested_session_id.as_deref())?;
        let selected_hosts=targets.iter().map(|(_,host,_)|host.clone()).collect::<std::collections::BTreeSet<_>>();

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
                if !selected_hosts.contains(&session.id) {
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
            "requestedSessionId": requested_session_id,
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
    if args.iter().any(|arg|arg=="--engineering-ota-preserve-inspect") {
        let result=(|| {
            if args.len()!=4 || !args.iter().any(|arg|arg=="--device-id") {
                return Err("Read-only preservation inspection requires only an exact --device-id".into());
            }
            let index=args.iter().position(|arg|arg=="--device-id").ok_or("Missing device ID")?;
            let device=args.get(index+1).ok_or("Missing device ID")?;
            backend::inspect_engineering_ota_preservation(device)?;
            println!("engineering_ota_preserve_inspection=PASS no_recording_sync=1 no_ota_transfer=1");
            Ok(())
        })();
        if let Err(error)=&result {eprintln!("engineering_ota_preserve_inspection=FAIL {error}");}
        return Some(result);
    }
    if args.iter().any(|arg|arg=="--engineering-ota-preserve-capability") {
        if args.len()!=2 { return Some(Err("Capability inspection cannot be combined with other operations".into())); }
        println!("engineering_ota_preserve_capability=1");
        return Some(Ok(()));
    }
    if args.iter().any(|arg|arg=="--system-ota-inspect") {
        let result=(|| {
            if args.iter().any(|arg|matches!(arg.as_str(),"--system-ota-transfer"|"--firmware-ota-transfer"|"--resource-ota-transfer"|"--system-ota-validate"|"--resource-ota-validate")) {
                return Err("Read-only OTA inspection cannot be combined with a transfer or validation request".to_string());
            }
            let device=args.iter().position(|arg|arg=="--device-id").and_then(|i|args.get(i+1))
                .ok_or("Read-only OTA inspection requires the exact device address")?;
            #[cfg(windows)] {
                let report=backend::ota_winrt::inspect_system_ota_winrt(device)?;
                println!("system_ota_inspect_json={report}");Ok(())
            }
            #[cfg(not(windows))] {let _=device;Err("Native OTA inspection currently requires Windows".to_string())}
        })();
        if let Err(error)=&result {eprintln!("[cli] Companion OTA inspection failed: {error}");}
        return Some(result);
    }
    let transfer_flag = args
        .iter()
        .position(|arg| arg == "--firmware-ota-transfer" || arg == "--resource-ota-transfer" || arg=="--system-ota-transfer");
    let validate_flag = args.iter().position(|arg| arg == "--resource-ota-validate" || arg=="--system-ota-validate");
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
        let system=args[index].starts_with("--system-ota-");
        let firmware_path = if system {manifest_path} else {args.get(index+2).ok_or("missing payload path after OTA CLI flag")?};
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
            "systemBundle":report.system_bundle,
            "payloadMetrics":report.payload_metrics,
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
    #[test]
    fn r65_local_audio_wait_never_schedules_cloud_work_or_consumes_retry_budget() {
        use super::*;
        let mut snapshot=companion_v1::apply_fixture_control(companion_v1::fixture_snapshot(),
            control_request(companion_v1::CompanionV1ControlAction::MeetingStart,Some("local-only-wait".into()))).unwrap();
        snapshot.meeting.active=false;snapshot.device.recording=false;snapshot.host.active_session_id=None;
        let row=&mut snapshot.host.sessions[0];row.status="captured".into();row.audio_stored=false;
        row.processing_policy=companion_v1::CompanionV1ProcessingPolicy::Automatic;
        row.recovery=companion_v1::CompanionV1MeetingRecovery::armed("offlineStore");row.pending_reason=Some("needs_local_audio".into());
        let before=serde_json::to_value(&snapshot.host.sessions[0].recovery).unwrap();
        assert_eq!(next_automatic_recovery(&snapshot,10),(None,None));
        assert_eq!(serde_json::to_value(&snapshot.host.sessions[0].recovery).unwrap(),before);
        snapshot.host.sessions[0].pending_reason=Some("needs_transcription".into());snapshot.host.sessions[0].audio_stored=true;
        assert_eq!(next_automatic_recovery(&snapshot,10).0,Some(("local-only-wait".into(),AutomaticRecoveryAction::Transcribe)));
    }
    #[test]
    fn local_card_processing_schedules_text_only_and_waits_for_local_readiness() {
        use super::*;
        let mut snapshot=companion_v1::apply_fixture_control(companion_v1::fixture_snapshot(),
            control_request(companion_v1::CompanionV1ControlAction::MeetingStart,Some("local-card".into()))).unwrap();
        snapshot.meeting.active=false;snapshot.device.recording=false;snapshot.host.active_session_id=None;
        let row=&mut snapshot.host.sessions[0];row.status="captured".into();row.audio_stored=true;
        row.processing_policy=companion_v1::CompanionV1ProcessingPolicy::LocalTranscription;
        row.recovery=companion_v1::CompanionV1MeetingRecovery::armed("offlineStore");
        assert!(next_automatic_recovery_with_local(&snapshot,10,false).0.is_none());
        assert_eq!(next_automatic_recovery_with_local(&snapshot,10,true).0,
            Some(("local-card".into(),AutomaticRecoveryAction::Transcribe)));
        let row=&mut snapshot.host.sessions[0];row.transcript_final=true;row.transcript_text="真实文字".into();
        row.recovery.stage="pendingMinutes".into();
        assert!(next_automatic_recovery_with_local(&snapshot,10,true).0.is_none(),"local card never silently submits a cloud summary");
    }
    use super::*;

    #[test]
    fn manual_processing_policy_survives_restart_and_does_not_enter_automatic_queue() {
        use companion_v1::{CompanionV1ProcessingPolicy as Policy,CompanionV1ControlAction as A};
        let mut req=control_request(A::MeetingStart,Some("manual-policy".into()));
        req.prompt_id=Some(companion_v1::CAPTURE_ONLY_PROMPT.into());
        let mut state=companion_v1::apply_fixture_control(companion_v1::fixture_snapshot(),req).unwrap();
        state.meeting.active=false;state.host.active_session_id=None;state.device.recording=false;
        let row=&mut state.host.sessions[0];row.status="captured".into();row.audio_stored=true;
        row.recovery=companion_v1::CompanionV1MeetingRecovery::armed("offlineStore");
        let mut restored=state.clone();
        restored.host.sessions=serde_json::from_slice(&serde_json::to_vec(&state.host.sessions).unwrap()).unwrap();
        assert_eq!(restored.host.sessions[0].processing_policy,Policy::Manual);
        assert!(next_automatic_recovery(&restored,0).0.is_none());
        let mut old=serde_json::to_value(&state.host.sessions).unwrap();
        old[0].as_object_mut().unwrap().remove("processingPolicy");
        let mut legacy=state.clone();legacy.host.sessions=serde_json::from_value(old).unwrap();
        assert_eq!(legacy.host.sessions[0].processing_policy,Policy::Automatic);
        assert!(next_automatic_recovery(&legacy,0).0.is_some());
        let erased=companion_v1::apply_fixture_control(restored,
            control_request(A::PrivacyEraseTranscript,Some("manual-policy".into()))).unwrap();
        assert_eq!(erased.host.sessions[0].processing_policy,Policy::Manual);
    }

    #[test]
    fn recording_library_scope_reused_device_id_requires_exact_host() {
        let rows=vec![(3,"legacy-recording-3".to_string(),false),(3,"current-original".to_string(),false),(4,"another".to_string(),false)];
        assert!(recording_library_targets(rows.clone(),Some(3),None).unwrap_err().contains("multiple saved meetings"));
        assert_eq!(recording_library_targets(rows.clone(),Some(3),Some("current-original")).unwrap(),vec![(3,"current-original".into(),false)]);
        assert!(recording_library_targets(rows.clone(),Some(4),Some("current-original")).is_err());
        assert!(recording_library_targets(rows.clone(),None,Some("missing")).is_err());
        assert_eq!(recording_library_targets(rows,None,None).unwrap().len(),3,"explicit whole-library operation remains available");
    }

    #[test]
    fn sync_result_keeps_verified_original_when_another_selected_capture_is_partial() {
        let mut snap=companion_v1::apply_fixture_control(companion_v1::fixture_snapshot(),
            control_request(companion_v1::CompanionV1ControlAction::MeetingStart,Some("saved-original".into()))).unwrap();
        let root=std::env::temp_dir().join(format!("companion-sync-result-{}",uuid::Uuid::new_v4()));fs::create_dir(&root).unwrap();
        let path=root.join("original.wav");
        let frames=800u32;let data_bytes=frames*2;
        let mut wav=b"RIFF".to_vec();wav.extend((36+data_bytes).to_le_bytes());wav.extend(b"WAVEfmt ");
        wav.extend(16u32.to_le_bytes());wav.extend(1u16.to_le_bytes());wav.extend(1u16.to_le_bytes());
        wav.extend(16000u32.to_le_bytes());wav.extend(32000u32.to_le_bytes());wav.extend(2u16.to_le_bytes());wav.extend(16u16.to_le_bytes());
        wav.extend(b"data");wav.extend(data_bytes.to_le_bytes());wav.resize(44+data_bytes as usize,0);fs::write(&path,&wav).unwrap();
        let row=&mut snap.host.sessions[0];row.source="boardDevice".into();row.status="captured".into();
        row.device_recording_id=Some(7);row.audio_path=Some(path.to_string_lossy().into());
        row.audio_stored=true;row.retention.audio_cached=true;row.audio_bytes=wav.len() as u64;row.duration_ms=50;
        let mut partial=row.clone();partial.id="selected-partial".into();partial.audio_stored=false;
        partial.audio_path=Some(root.join("not-complete.wav").to_string_lossy().into());partial.status="recording".into();
        snap.host.sessions.insert(0,partial);snap.host.selected_session_id=Some("selected-partial".into());
        assert_eq!(synced_device_audio(&snap).unwrap().id,"saved-original");
        // An arbitrary existing WAV cannot stand in for a V2 original receipt.
        let mut forged=snap.host.sessions[1].clone();forged.device_recording_key=Some(companion_v1::CompanionV1RecordingKey{
            device_uid:"180010000d50335754363720".into(),format_epoch:"1f59b27acf4936e1".into(),session_id:"0000000000000005".into()});
        assert!(!verified_synced_audio(&forged));
        snap.host.sessions[1].audio_bytes+=1;assert!(synced_device_audio(&snap).is_err());
        fs::remove_file(path).unwrap();fs::remove_dir(root).unwrap();
    }

    #[test]
    fn no_limit_capture_requires_follow_and_preserves_existing_test_modes() {
        let plain=vec!["app".to_string()];
        let unlimited=vec!["app".to_string(),"--no-recording-limit".to_string()];
        assert_eq!(capture_start_duration(&plain,7200,true,false).unwrap(),7_230_000);
        assert_eq!(capture_start_duration(&plain,45,false,true).unwrap(),45_000);
        assert_eq!(capture_start_duration(&unlimited,7200,true,false).unwrap(),0);
        assert!(capture_start_duration(&unlimited,7200,false,false).is_err());
        assert!(capture_start_duration(&unlimited,7200,true,true).is_err());
    }

    #[test]
    fn scheduled_original_pause_rejects_ambiguous_or_conflicting_controls_before_connect() {
        let args=|values:&[&str]|values.iter().map(|s|s.to_string()).collect::<Vec<_>>();
        assert_eq!(capture_pause_schedule(&args(&["app","--capture-pause-at","8","--capture-resume-at","13"]),25,false).unwrap(),Some((8,13)));
        for flags in [vec!["--capture-pause-at","8"],vec!["--capture-pause-at","8","--capture-resume-at","8"],
            vec!["--capture-pause-at","8","--capture-resume-at","25"],vec!["--capture-pause-at","8","--capture-pause-at","9","--capture-resume-at","13"],
            vec!["--capture-pause-at","zero","--capture-resume-at","13"]] {
            let mut all=vec!["app"];all.extend(flags);assert!(capture_pause_schedule(&args(&all),25,false).is_err());
        }
        assert!(capture_pause_schedule(&args(&["app","--capture-pause-at","8","--capture-resume-at","13"]),25,true).is_err());
        assert_eq!(capture_pause_schedule(&args(&["app"]),25,true).unwrap(),None);
    }

    #[test]
    fn original_recorder_cli_requires_exact_durable_owner_and_cannot_start() {
        let args = |tail: &[&str]| std::iter::once("companion-type").chain(tail.iter().copied()).map(str::to_string).collect::<Vec<_>>();
        let original = "v1-real-installed-1791751615096";
        let (mut request, _) = original_recorder_request(&args(&["--recorder-control", "recover", "--session-id", original])).unwrap();
        assert_eq!(request.action, companion_v1::CompanionV1ControlAction::MeetingRecoverControl);
        for tail in [vec!["--recorder-control", "start", "--session-id", original],
            vec!["--recorder-control", "recover"],
            vec!["--recorder-control", "recover", "--session-id", original, "--v1-real-meeting"],
            vec!["--recorder-control", "recover", "--session-id", original, "--session-id", "another"],
            vec!["--recorder-control", "stop", "--session-id", "--device-id", "other"]] {
            assert!(original_recorder_request(&args(&tail)).is_err());
        }
        let mut snapshot = companion_v1::fixture_snapshot();
        snapshot.host.persistence.status = "ready".into();
        let mut row = companion_v1::create_host_session(&snapshot, &request, "");
        row.id = original.into(); row.source = "boardDevice".into();
        row.source_device_id = Some("C8:92:FF:DD:3B:CA".into());
        row.recorder_control = Some(serde_json::from_str(r#"{"schema":1,"hostSession":"v1-real-installed-1791751615096","deviceId":"C8:92:FF:DD:3B:CA","uid":[24,0,16,0,13,80,51,87,84,54,55,32],"epoch":2259032928636450529,"startRequest":789973146,"maxSeconds":350,"key":null,"anchor":null,"confirmed":null,"pending":{"command":1,"request":789973146,"sequence":0,"wire":[67,77,67,51,3,1,2,1,24,0,16,0,13,80,51,87,84,54,55,32,225,54,73,207,122,178,89,31,0,0,0,0,0,0,0,0,154,8,22,47,154,8,22,47,94,1,0,0,0,0,0,0,168,20,243,156]}}"#).unwrap());
        snapshot.host.sessions = vec![row];
        let original_journal = snapshot.host.sessions[0].recorder_control.clone();
        bind_original_recorder_request(&snapshot, &mut request).unwrap();
        assert_eq!(request.device_id.as_deref(), Some("C8:92:FF:DD:3B:CA"));
        assert_eq!(snapshot.host.sessions[0].recorder_control, original_journal);
        request.session_id = Some("another".into());
        assert!(bind_original_recorder_request(&snapshot, &mut request).is_err());
        request.session_id = Some(original.into()); request.device_id = Some("other-device".into());
        assert!(bind_original_recorder_request(&snapshot, &mut request).is_err());
        request.device_id = None; snapshot.host.persistence.status = "blocked".into();
        assert!(bind_original_recorder_request(&snapshot, &mut request).is_err());
        snapshot.host.persistence.status = "ready".into(); snapshot.host.sessions[0].source = "hostMic".into();
        assert!(bind_original_recorder_request(&snapshot, &mut request).is_err());
    }

    fn snapshot_with_pending_recovery(
        id: &str,
    ) -> companion_v1::CompanionV1Snapshot {
        let mut snapshot = companion_v1::fixture_snapshot();
        let request = companion_v1::CompanionV1ControlRequest { minutes_template: None, recording_source: None,
            action: companion_v1::CompanionV1ControlAction::DeviceSyncRecordings,
            context_note_revision: None, ble_name: None,
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
        snapshot.device.connection_phase="pairingRequired".into();
        assert!(!should_attempt_device_reconnect(&snapshot));
    }

    #[test]
    fn recovery_does_not_starve_other_meetings_on_inconsistent_retry_stage() {
        let mut snapshot=snapshot_with_pending_recovery("invalid-minutes");
        let original=snapshot.host.sessions[0].clone();
        let bad=&mut snapshot.host.sessions[0];
        bad.transcript_text="partial".into(); bad.transcript_final=false;
        bad.recovery.stage="retryBackoff".into(); bad.recovery.retry_stage="minutes".into();
        bad.recovery.next_retry_at_unix_ms=Some(0);
        let mut healthy=original;healthy.id="healthy-pending".into();
        healthy.recovery.stage="pendingTranscription".into();
        snapshot.host.sessions.push(healthy);
        assert_eq!(next_automatic_recovery(&snapshot,10).0,
            Some(("healthy-pending".into(),AutomaticRecoveryAction::Transcribe)));
        snapshot.host.sessions.remove(1);
        assert_eq!(next_automatic_recovery(&snapshot,10),(None,None));
        snapshot.host.sessions[0].recovery.retry_stage.clear();
        assert_eq!(next_automatic_recovery(&snapshot,10),(None,None));
        let row=&mut snapshot.host.sessions[0];
        row.transcript_final=true; row.transcript_text="saved final".into();
        row.recovery.stage="pendingTranscription".into();
        assert_eq!(next_automatic_recovery(&snapshot,10),(None,None));
        snapshot.host.sessions[0].recovery.stage="retryBackoff".into();
        snapshot.host.sessions[0].recovery.retry_stage="transcription".into();
        assert_eq!(next_automatic_recovery(&snapshot,10),(None,None));
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
