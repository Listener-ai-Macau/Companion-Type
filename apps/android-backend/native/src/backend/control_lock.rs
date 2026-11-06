//! Process-wide recording control lock on the app's private filesystem.
//!
//! Rust 1.95's standard file locks return Unsupported on Android. Use the
//! Android/Bionic flock implementation there, preserving nonblocking ownership
//! and close-to-release semantics without changing the recording protocol.
use std::fs::File;

const BUSY: &str = "该设备正在处理另一项录音操作。";

pub(crate) fn try_lock(file: &File) -> Result<(), String> {
    #[cfg(target_os = "android")]
    {
        use std::os::fd::AsRawFd;
        use std::os::raw::c_int;
        unsafe extern "C" {
            fn flock(fd: c_int, operation: c_int) -> c_int;
        }
        // Android's sys/file.h: LOCK_EX=2, LOCK_NB=4. The File owns a live fd
        // throughout this call; dropping that File releases the kernel lock.
        if unsafe { flock(file.as_raw_fd(), 2 | 4) } == 0 {
            return Ok(());
        }
        let error = std::io::Error::last_os_error();
        if error.kind() == std::io::ErrorKind::WouldBlock {
            return Err(BUSY.into());
        }
        Err(format!("无法锁定本机录音控制记录：{error}"))
    }
    #[cfg(not(target_os = "android"))]
    {
        match file.try_lock() {
            Ok(()) => Ok(()),
            Err(std::fs::TryLockError::WouldBlock) => Err(BUSY.into()),
            Err(std::fs::TryLockError::Error(error)) => {
                Err(format!("无法锁定本机录音控制记录：{error}"))
            }
        }
    }
}
