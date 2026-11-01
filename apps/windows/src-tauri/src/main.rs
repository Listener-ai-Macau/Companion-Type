#[cfg(windows)]
fn recording_cli_requested() -> bool {
    std::env::args_os().skip(1).any(|arg| {
        arg == "--sync-device-recording" || arg == "--v1-real-meeting"
    })
}

fn main() {
    // Recording's nested BLE futures need more space than the 1 MiB Windows
    // process-main stack in some release configurations. Keep the native GUI
    // on its original main thread; only the two affected headless commands run
    // on a bounded, larger worker. Do not alter any BLE, data or audio policy.
    #[cfg(windows)]
    if recording_cli_requested() {
        let worker = std::thread::Builder::new()
            .name("companion-recording-cli".into())
            .stack_size(8 * 1024 * 1024)
            .spawn(companion_type_lib::run)
            .unwrap_or_else(|error| {
                eprintln!("Cannot start recording worker: {error}");
                std::process::exit(1);
            });
        if worker.join().is_err() {
            eprintln!("Recording worker failed");
            std::process::exit(1);
        }
        return;
    }
    companion_type_lib::run()
}
