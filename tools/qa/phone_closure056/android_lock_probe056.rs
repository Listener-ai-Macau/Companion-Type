use std::{fs::OpenOptions,os::fd::AsRawFd};
unsafe extern "C" {fn flock(fd:i32,operation:i32)->i32;}
fn main(){
 let path=std::env::args().nth(1).expect("owned test path");
 let first=OpenOptions::new().read(true).write(true).create(true).truncate(false).open(&path).unwrap();
 let original=first.try_lock();println!("STD_TRY_LOCK={original:?}");if original.is_ok(){first.unlock().unwrap();}
 let fd=first.as_raw_fd();let raw=unsafe{flock(fd,2|4)};println!("RAW_FIRST={raw} ERR={:?}",std::io::Error::last_os_error());assert_eq!(raw,0);
 let second=OpenOptions::new().read(true).write(true).open(&path).unwrap();let conflict=unsafe{flock(second.as_raw_fd(),2|4)};let error=std::io::Error::last_os_error();println!("RAW_CONFLICT={conflict} ERR={error:?}");assert_eq!(conflict,-1);assert_eq!(error.kind(),std::io::ErrorKind::WouldBlock);
 drop(first);let reopened=unsafe{flock(second.as_raw_fd(),2|4)};println!("RAW_AFTER_DROP={reopened}");assert_eq!(reopened,0);drop(second);println!("PASS_ANDROID_REAL_FILE_LOCK_EXCLUSION_AND_DROP_RELEASE");
}
