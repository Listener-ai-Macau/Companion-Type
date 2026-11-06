//! Non-blocking private-file exclusion for recorder control. Android's Rust
//! 1.95 std::File::try_lock is unsupported; an actual flock is still required,
//! never a successful no-op or an in-process-only replacement.
use std::fs::File;

const BUSY:&str="该设备正在处理另一项录音操作。";
fn unavailable(error:std::io::Error)->String {format!("无法锁定录音控制记录：{error}。未发送新命令，请重新操作。")}

#[cfg(target_os="android")]
pub(crate) fn try_lock(file:&File)->Result<(),String> {
    use std::{ffi::c_int,os::fd::AsRawFd};
    unsafe extern "C" {fn flock(fd:c_int,operation:c_int)->c_int;}
    // Android NDK sys/file.h: LOCK_EX=2, LOCK_NB=4. The borrowed File owns the
    // descriptor throughout this non-blocking call and releases on Drop.
    loop {
        if unsafe {flock(file.as_raw_fd(),2|4)}==0 {return Ok(());}
        let error=std::io::Error::last_os_error();
        match error.kind(){std::io::ErrorKind::Interrupted=>continue,
            std::io::ErrorKind::WouldBlock=>return Err(BUSY.into()),_=>return Err(unavailable(error))}
    }
}

#[cfg(not(target_os="android"))]
pub(crate) fn try_lock(file:&File)->Result<(),String> {
    file.try_lock().map_err(|error|match error {
        std::fs::TryLockError::WouldBlock=>BUSY.into(),std::fs::TryLockError::Error(error)=>unavailable(error)})
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{fs::{self,OpenOptions},time::{SystemTime,UNIX_EPOCH}};
    #[test]
    fn exclusive_across_independent_handles_and_released_on_drop(){
        let path=std::env::temp_dir().join(format!("companion-control-lock-{}-{}",std::process::id(),SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
        let first=OpenOptions::new().read(true).write(true).create_new(true).open(&path).unwrap();
        let second=OpenOptions::new().read(true).write(true).open(&path).unwrap();
        try_lock(&first).unwrap();assert_eq!(try_lock(&second).unwrap_err(),BUSY);drop(first);
        try_lock(&second).unwrap();drop(second);fs::remove_file(path).unwrap();
    }
}
