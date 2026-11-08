//! Publish only a completed, synced WAV; never replace an existing output.
use std::{io,path::Path};

#[cfg(target_os="android")]
pub(crate) fn without_replacement(ready:&Path,output:&Path)->io::Result<()> {
    use std::{ffi::CString,os::unix::ffi::OsStrExt};
    let path=|p:&Path|CString::new(p.as_os_str().as_bytes())
        .map_err(|_|io::Error::new(io::ErrorKind::InvalidInput,"audio path contains NUL"));
    let from=path(ready)?;let to=path(output)?;
    // Android file policy can reject hard links even in app-private storage.
    // The kernel move keeps publication atomic and rejects an existing target
    // in the same operation. Do not fall back to check-then-rename or overwrite.
    let result=unsafe {libc::syscall(libc::SYS_renameat2,libc::AT_FDCWD,from.as_ptr(),
        libc::AT_FDCWD,to.as_ptr(),libc::RENAME_NOREPLACE)};
    if result==0 {Ok(())} else {Err(io::Error::last_os_error())}
}

#[cfg(not(target_os="android"))]
pub(crate) fn without_replacement(ready:&Path,output:&Path)->io::Result<()> {
    std::fs::hard_link(ready,output)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{fs,sync::{Arc,Barrier},thread};
    #[test]
    fn concurrent_publication_keeps_exactly_one_original_and_all_losing_sources() {
        let dir=std::env::temp_dir().join(format!("companion-audio-publish-{}",uuid::Uuid::new_v4()));
        fs::create_dir(&dir).unwrap();let target=dir.join("complete.wav");
        let gate=Arc::new(Barrier::new(8));let mut jobs=Vec::new();
        for id in 0u8..8 {
            let source=dir.join(format!("ready-{id}"));fs::write(&source,[id;64]).unwrap();
            let target=target.clone();let gate=gate.clone();
            jobs.push(thread::spawn(move||{gate.wait();(id,source.clone(),without_replacement(&source,&target))}));
        }
        let rows=jobs.into_iter().map(|job|job.join().unwrap()).collect::<Vec<_>>();
        assert_eq!(rows.iter().filter(|row|row.2.is_ok()).count(),1);
        let winner=rows.iter().find(|row|row.2.is_ok()).unwrap().0;
        assert_eq!(fs::read(&target).unwrap(),vec![winner;64]);
        for(id,source,result)in rows {
            if id!=winner {assert_eq!(result.unwrap_err().kind(),io::ErrorKind::AlreadyExists);assert_eq!(fs::read(source).unwrap(),vec![id;64]);}
        }
        let canonical=dir.canonicalize().unwrap();
        assert_eq!(canonical.parent(),Some(std::env::temp_dir().canonicalize().unwrap().as_path()));
        assert!(canonical.file_name().unwrap().to_string_lossy().starts_with("companion-audio-publish-"));
        fs::remove_dir_all(canonical).unwrap();
    }
}
