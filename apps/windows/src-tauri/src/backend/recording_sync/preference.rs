//! Only the user's per-device sync choice is durable. Jobs, cursors, recorder
//! controls and temporary foreground handoff remain owned by their own paths.
use super::{key,Store};
use serde::{Deserialize,Serialize};
use std::path::{Path,PathBuf};

const READ_ERROR:&str="录音同步设置暂时不可读取，自动同步已暂停；可以手动同步当前设备，原录音保留。";
const WRITE_ERROR:&str="同步选择未能保存，自动同步已暂停；可以手动同步当前设备，原录音保留。";
const REPAIR_ERROR:&str="同步设置尚未修复，请检查本机文件权限或占用后重试；原录音和设置均保留。";

#[derive(Deserialize,Serialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
struct Preference { schema:u8, paused_devices:Vec<String>, last_paused_device:Option<String> }

fn path()->PathBuf {
    super::super::persistence::state_file_path().parent().unwrap_or_else(||Path::new(".")).join("recording-sync.json")
}

pub(super) fn load_product()->Store {
    // Unit tests without an explicit isolated profile never touch user data.
    if cfg!(test) && std::env::var_os("COMPANION_TYPE_STATE_PATH").is_none() {return Store::default();}
    load(path())
}

fn load(path:PathBuf)->Store {
    let mut store=Store {preference_path:Some(path.clone()),..Store::default()};
    let result=(|| {
        let bytes=match std::fs::read(&path) {
            Ok(bytes)=>bytes,
            Err(error) if error.kind()==std::io::ErrorKind::NotFound=>return Ok(()),
            Err(_)=>return Err(READ_ERROR.to_string()),
        };
        if bytes.len()>65536 {return Err(READ_ERROR.into());}
        let saved:Preference=serde_json::from_slice(&bytes).map_err(|_|READ_ERROR.to_string())?;
        if saved.schema!=1 || saved.paused_devices.len()>256
            || saved.paused_devices.iter().any(|id|!super::super::device_connection::stable_device_id(id))
            || saved.last_paused_device.as_deref().is_some_and(|id|!super::super::device_connection::stable_device_id(id)) {
            return Err(READ_ERROR.into());
        }
        store.paused_devices=saved.paused_devices.iter().map(|id|key(id)).collect();
        if store.paused_devices.len()!=saved.paused_devices.len()
            || saved.last_paused_device.as_deref().is_some_and(|id|!store.paused_devices.contains(&key(id)))
            || (!store.paused_devices.is_empty() && saved.last_paused_device.is_none()) {return Err(READ_ERROR.into());}
        store.last_paused_device=saved.last_paused_device;
        Ok(())
    })();
    store.storage_error=result.err();store
}

pub(super) fn save(store:&Store)->Result<(),String> {
    let Some(path)=store.preference_path.as_deref() else {return Ok(());};
    if store.storage_error.is_some() {return Err(READ_ERROR.into());}
    if store.paused_devices.len()>256 || store.paused_devices.iter().any(|id|!super::super::device_connection::stable_device_id(id)) {
        return Err(WRITE_ERROR.into());
    }
    let mut devices=store.paused_devices.iter().cloned().collect::<Vec<_>>();devices.sort();
    let bytes=serde_json::to_vec(&Preference {schema:1,paused_devices:devices,last_paused_device:store.last_paused_device.clone()})
        .map_err(|_|WRITE_ERROR.to_string())?;
    super::super::export::write_atomic(path,&bytes).map(|_|()).map_err(|_|WRITE_ERROR.into())
}

pub(super) fn resume(store:&mut Store,device:Option<&str>)->Result<(),String> {
    // Refresh the file for an explicit action. A repaired file can recover;
    // unreadable/corrupt settings cannot be silently replaced with defaults.
    let mut next=store.preference_path.as_ref().map(|p|load(p.clone())).unwrap_or_else(||Store {
        paused_devices:store.paused_devices.clone(),last_paused_device:store.last_paused_device.clone(),..Store::default()
    });
    if let Some(error)=next.storage_error {return permit_manual(store,device,error);}
    if let Some(device)=device {next.paused_devices.remove(&key(device));}
    else {next.paused_devices.clear();}
    if next.last_paused_device.as_deref().is_some_and(|id|!next.paused_devices.contains(&key(id))) {
        next.last_paused_device=next.paused_devices.iter().min().cloned();
    }
    match commit_resume(store,next) {
        Ok(()) => Ok(()),
        Err(error) => permit_manual(store,device,error),
    }
}

fn permit_manual(store:&mut Store,device:Option<&str>,error:String)->Result<(),String> {
    let Some(device)=device.filter(|id|super::super::device_connection::stable_device_id(id)) else {return Err(error);};
    store.storage_error=Some(error);
    store.manual_recovery_devices.insert(key(device));
    Ok(())
}

fn commit_resume(store:&mut Store,next:Store)->Result<(),String> {
    save(&next)?;
    store.paused_devices=next.paused_devices;store.last_paused_device=next.last_paused_device;store.storage_error=None;
    store.manual_recovery_devices.clear();
    Ok(())
}

/// Explicitly reset only the sync-pause choice, after saving the prior file.
/// The UI tells the user that all per-device pause choices will be cleared.
pub(super) fn reset_choice(store:&mut Store)->Result<(),String> {
    if store.storage_error.is_none() {return Err("同步设置已恢复，无需再次修复。".into());}
    let path=store.preference_path.as_ref().ok_or(REPAIR_ERROR)?;
    match std::fs::File::open(path) {
        Ok(mut original)=>{
            let backup=path.with_file_name(format!("recording-sync-before-repair-{}.json",uuid::Uuid::new_v4()));
            let mut target=std::fs::OpenOptions::new().write(true).create_new(true).open(backup).map_err(|_|REPAIR_ERROR)?;
            std::io::copy(&mut original,&mut target).map_err(|_|REPAIR_ERROR)?;
            target.sync_all().map_err(|_|REPAIR_ERROR)?;
        }
        Err(e) if e.kind()==std::io::ErrorKind::NotFound=>(),
        Err(_)=>return Err(REPAIR_ERROR.into()),
    }
    let next=Store{preference_path:Some(path.clone()),..Store::default()};
    save(&next).map_err(|_|REPAIR_ERROR)?;
    store.paused_devices.clear();store.last_paused_device=None;
    store.storage_error=None;store.manual_recovery_devices.clear();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn explicit_reset_preserves_bad_file_and_restores_auto_sync() {
        let root=std::env::temp_dir().join(format!("companion-sync-repair-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let path=root.join("recording-sync.json");
        let bad=b"{incomplete sync choice";std::fs::write(&path,bad).unwrap();
        let mut store=load(path.clone());assert!(store.storage_error.is_some());
        reset_choice(&mut store).unwrap();assert!(store.storage_error.is_none());
        assert!(super::super::automatic_allowed_for(&store,"AA:BB:CC:DD:EE:01",false));
        assert!(super::super::automatic_allowed_for(&load(path.clone()),"AA:BB:CC:DD:EE:02",false));
        let backups:Vec<_>=std::fs::read_dir(&root).unwrap().map(|e|e.unwrap().path())
            .filter(|p|p.file_name().unwrap().to_string_lossy().starts_with("recording-sync-before-repair-")).collect();
        assert_eq!(backups.len(),1);assert_eq!(std::fs::read(&backups[0]).unwrap(),bad);
        assert!(reset_choice(&mut store).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn reset_failure_does_not_clear_pause_or_enable_sync() {
        let root=std::env::temp_dir().join(format!("companion-sync-repair-fail-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let path=root.join("recording-sync.json");
        std::fs::create_dir(&path).unwrap();
        let mut store=load(path);store.paused_devices.insert(key("AA:BB:CC:DD:EE:01"));
        assert!(reset_choice(&mut store).is_err());assert!(store.storage_error.is_some());
        assert!(store.paused_devices.contains(&key("AA:BB:CC:DD:EE:01")));
        assert!(!super::super::automatic_allowed_for(&store,"AA:BB:CC:DD:EE:01",false));
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn corrupt_choice_allows_one_explicit_device_without_automatic_receive_or_replacement() {
        let root=std::env::temp_dir().join(format!("companion-sync-corrupt-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let path=root.join("recording-sync.json");
        for bytes in [b"{".as_slice(),br#"{"schema":2,"pausedDevices":[],"lastPausedDevice":null}"#,
            br#"{"schema":1,"pausedDevices":["not-a-device"],"lastPausedDevice":"not-a-device"}"#] {
            std::fs::write(&path,bytes).unwrap();let mut store=load(path.clone());
            assert!(!super::super::owned_follow_allowed_for(&store,"AA:BB:CC:DD:EE:01"));
            assert!(resume(&mut store,None).is_err());
            assert!(resume(&mut store,Some("not-a-device")).is_err());
            assert!(resume(&mut store,Some("AA:BB:CC:DD:EE:01")).is_ok());
            assert!(!super::super::automatic_allowed_for(&store,"AA:BB:CC:DD:EE:01",false));
            assert!(super::super::admit_job(&mut store,"AA:BB:CC:DD:EE:01",true).is_err());
            assert!(super::super::admit_job(&mut store,"AA:BB:CC:DD:EE:02",false).is_err());
            assert!(super::super::admit_job(&mut store,"AA:BB:CC:DD:EE:01",false).is_ok());
            assert!(super::super::admit_job(&mut store,"AA:BB:CC:DD:EE:01",false).is_err());
            assert_eq!(std::fs::read(&path).unwrap(),bytes);
        }
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn failed_resume_write_keeps_pause_and_other_devices() {
        let root=std::env::temp_dir().join(format!("companion-sync-write-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let path=root.join("recording-sync.json");
        let mut store=load(path.clone());store.paused_devices.insert(key("AA:BB:CC:DD:EE:01"));
        store.paused_devices.insert(key("AA:BB:CC:DD:EE:02"));store.last_paused_device=Some("AA:BB:CC:DD:EE:01".into());
        save(&store).unwrap();resume(&mut store,Some("aabbccddee01")).unwrap();
        assert!(!store.paused_devices.contains("aabbccddee01"));assert!(store.paused_devices.contains("aabbccddee02"));
        // Fail the durable publication of a valid resumed choice, without
        // relying on platform-specific read-only attributes or permissions.
        let blocker=root.join("file");std::fs::write(&blocker,b"x").unwrap();
        let next=Store {preference_path:Some(blocker.join("recording-sync.json")),..Store::default()};
        assert!(commit_resume(&mut store,next).unwrap_err().contains("未能保存"));
        assert!(store.paused_devices.contains("aabbccddee02"));
        std::fs::remove_dir_all(root).unwrap();
    }

    #[cfg(windows)]
    #[test]
    fn occupied_choice_file_still_allows_the_selected_manual_job() {
        use std::os::windows::fs::OpenOptionsExt;
        let root=std::env::temp_dir().join(format!("companion-sync-occupied-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&root).unwrap();let path=root.join("recording-sync.json");
        let mut store=load(path.clone());store.paused_devices.insert(key("AA:BB:CC:DD:EE:01"));
        store.paused_devices.insert(key("AA:BB:CC:DD:EE:02"));store.last_paused_device=Some("AA:BB:CC:DD:EE:01".into());
        save(&store).unwrap();let before=std::fs::read(&path).unwrap();
        let held=std::fs::OpenOptions::new().read(true).share_mode(1|2).open(&path).unwrap();
        resume(&mut store,Some("AA:BB:CC:DD:EE:01")).unwrap();
        assert!(!super::super::automatic_allowed_for(&store,"AA:BB:CC:DD:EE:01",false));
        assert!(store.paused_devices.contains(&key("AA:BB:CC:DD:EE:02")));
        assert!(super::super::admit_job(&mut store,"AA:BB:CC:DD:EE:01",false).is_ok());
        assert!(super::super::admit_job(&mut store,"AA:BB:CC:DD:EE:02",false).is_err());
        assert_eq!(std::fs::read(&path).unwrap(),before);
        drop(held);std::fs::remove_dir_all(root).unwrap();
    }
}
