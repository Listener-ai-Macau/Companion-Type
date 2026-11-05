//! Controlled native file operations only; no profile, service or board access.
#[cfg(windows)]
pub(crate) fn verify(output: &std::path::Path) -> Result<serde_json::Value, String> {
    use std::{fs, path::PathBuf, os::windows::{ffi::OsStrExt, fs::OpenOptionsExt}};
    use super::{export, device_connection};
    let output = if output.is_absolute() { output.to_path_buf() } else {
        std::env::current_dir().map_err(|_| "cannot resolve probe output")?.join(output)
    };
    fs::create_dir(&output).map_err(|_| "file storage probe requires a new empty output folder")?;
    let io = |error: std::io::Error| format!("controlled file storage operation failed: {error}");
    let directory = output.join("a".repeat(75)).join("b".repeat(75)).join("长目录".repeat(20));
    fs::create_dir_all(&directory).map_err(io)?;
    let mut checks = Vec::new();
    let mut check = |ok: bool, name: &str| -> Result<(), String> {
        if !ok { return Err(format!("controlled file storage check failed: {name}")); }
        checks.push(serde_json::json!({"name":name,"passed":true})); Ok(())
    };
    let plain = directory.join("会议 记录 🐾.json");
    let utf16_units = plain.as_os_str().encode_wide().count();
    check(utf16_units > 300, "unprefixedLongDestinationOver300Utf16Units")?;
    check(!plain.as_os_str().to_string_lossy().starts_with(r"\\?\"), "callerSuppliesOrdinaryWindowsPath")?;
    let old = b"original-complete-fixture"; let new = b"new-complete-fixture\0binary";
    export::write_atomic(&plain, old)?;
    check(fs::read(&plain).map_err(io)? == old, "longUnicodeCreateExactBytes")?;
    export::write_atomic(&plain, new)?;
    check(fs::read(&plain).map_err(io)? == new, "longUnicodeReplacementExactBytes")?;
    let occupied = fs::OpenOptions::new().read(true).share_mode(1 | 2).open(&plain).map_err(io)?;
    check(export::write_atomic(&plain, b"uncommitted").is_err(), "occupiedLongFileRejectsReplacement")?;
    check(fs::read(&plain).map_err(io)? == new, "occupiedFailureKeepsOldBytes")?;
    let temp_count = |root: &PathBuf| -> Result<usize, String> {
        Ok(fs::read_dir(root).map_err(io)?.filter_map(Result::ok)
            .filter(|entry| entry.file_name().to_string_lossy().ends_with(".tmp")).count())
    };
    check(temp_count(&directory)? == 0, "failedWriteRemovesOnlyOwnedStaging")?;
    drop(occupied); export::write_atomic(&plain, b"retried")?;
    check(fs::read(&plain).map_err(io)? == b"retried", "longFileRetryAfterRelease")?;
    let name = directory.join(format!("{}.json", "x".repeat(240)));
    export::write_atomic(&name, b"valid-long-component")?;
    check(fs::read(&name).map_err(io)? == b"valid-long-component", "valid245UnitFilenameUsesShortStagingName")?;
    let dot_path = directory.join("nested").join("..").join("dots.txt");
    export::write_atomic(&dot_path, b"resolved-once")?;
    check(fs::read(directory.join("dots.txt")).map_err(io)? == b"resolved-once", "dotParentResolvedBeforeVerbatimConversion")?;
    let source = directory.join("原始源.tmp"); let destination = directory.join("未创建目标.bin");
    fs::write(&source, b"direct-replace").map_err(io)?;
    export::replace_file(&source, &destination)?;
    check(!source.exists() && fs::read(&destination).map_err(io)? == b"direct-replace", "directReplaceAcceptsLongParentsAndMissingDestination")?;
    let canonical = directory.canonicalize().map_err(io)?.join("canonical.json");
    export::write_atomic(&canonical, b"canonical")?;
    check(fs::read(&canonical).map_err(io)? == b"canonical", "existingVerbatimPathRemainsSupported")?;
    let dir_target = directory.join("directory-target"); fs::create_dir(&dir_target).map_err(io)?;
    fs::write(dir_target.join("retained.txt"), b"retained").map_err(io)?;
    check(export::write_atomic(&dir_target, b"invalid").is_err()
        && fs::read(dir_target.join("retained.txt")).map_err(io)? == b"retained", "directoryDestinationRejectedWithoutDeletingItsContents")?;
    let preference_path = directory.join("device-preference.json");
    let mut preference = device_connection::DeviceConnectionPreference::default();
    preference.remember_native_success("AA:BB:CC:DD:EE:FF", "controlled-fixture".into());
    device_connection::save_to(&preference_path, &preference)?;
    check(device_connection::load_from(&preference_path).is_some_and(|value| value.can_automatically_reconnect()), "productionDevicePreferenceLongPathRoundTrip")?;
    let original = fs::read(&preference_path).map_err(io)?;
    let held = fs::OpenOptions::new().read(true).share_mode(1 | 2).open(&preference_path).map_err(io)?;
    preference.mark_manual_disconnect();
    check(device_connection::save_to(&preference_path, &preference).is_err()
        && fs::read(&preference_path).map_err(io)? == original, "preferenceSaveFailureKeepsOldPreference")?;
    drop(held); device_connection::save_to(&preference_path, &preference)?;
    check(device_connection::load_from(&preference_path).is_some_and(|value| !value.can_automatically_reconnect()), "preferenceSaveRetryAppliesNewPreference")?;
    check(temp_count(&directory)? == 0, "noUncommittedStagingRemains")?;
    Ok(serde_json::json!({"result":"PASS_LOCAL_WINDOWS_FILE_STORAGE_ONLY", "checks":checks,
        "destinationUtf16Units":utf16_units,"longFilenameUtf16Units":245,
        "realUserProfileAccess":false,"deviceAccess":false,"networkAccess":false,
        "nativeGui":"NOT_RUN","uncShareAcceptance":"NOT_RUN","powerLossAcceptance":"NOT_RUN",
        "hardwareAcceptance":"NOT_RUN","fullChainAcceptance":"NOT_RUN"}))
}

#[cfg(not(windows))]
pub(crate) fn verify(_: &std::path::Path) -> Result<serde_json::Value, String> {
    Err("Windows file storage probe unavailable on this platform".into())
}

#[cfg(all(test, windows))]
mod tests {
    #[test]
    fn long_windows_storage_preserves_complete_files_and_retries_occupied_destinations() {
        let parent = std::env::temp_dir();
        let output = parent.join(format!("companion-file-probe-{}", uuid::Uuid::new_v4()));
        let report = super::verify(&output).unwrap();
        assert_eq!(report["checks"].as_array().unwrap().len(), 17);
        assert!(report["destinationUtf16Units"].as_u64().unwrap() > 300);
        let before = std::fs::read_dir(&output).unwrap().count();
        assert!(super::verify(&output).is_err());
        assert_eq!(std::fs::read_dir(&output).unwrap().count(), before);
        let actual = output.canonicalize().unwrap();
        assert_eq!(actual.parent(), Some(parent.canonicalize().unwrap().as_path()));
        assert_eq!(actual.file_name(), output.file_name());
        std::fs::remove_dir_all(actual).unwrap();
    }
}
