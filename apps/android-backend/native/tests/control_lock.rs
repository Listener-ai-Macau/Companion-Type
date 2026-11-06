#[path = "../src/backend/control_lock.rs"]
mod control_lock;

#[test]
fn control_lock_excludes_another_owner_and_releases_on_close() {
    use std::fs::{self, OpenOptions};
    let directory = std::env::temp_dir().join(format!("companion-control-lock-{}", std::process::id()));
    fs::create_dir(&directory).unwrap();
    let path = directory.join("control.lock");
    let open = || OpenOptions::new().read(true).write(true).create(true).truncate(false).open(&path).unwrap();
    let first = open();
    control_lock::try_lock(&first).expect("first owner must acquire the recording control lock");
    let second = open();
    assert_eq!(control_lock::try_lock(&second).unwrap_err(), "该设备正在处理另一项录音操作。");
    drop(first);
    control_lock::try_lock(&second).expect("closing the old owner must release its lock");
    drop(second);
    fs::remove_file(path).unwrap();
    fs::remove_dir(directory).unwrap();
}
