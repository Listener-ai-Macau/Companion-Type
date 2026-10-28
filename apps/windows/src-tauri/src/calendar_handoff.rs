//! Open only an exact calendar file saved by this process, after a user click.
//! A successful Shell handoff is not proof of import, synchronization or alarms.
use std::{collections::VecDeque, fs::File, io::Read, path::{Path, PathBuf}, sync::{Arc, Mutex}};
use sha2::{Digest, Sha256};
use crate::{companion_v1::CompanionV1HostSession, coordinator::CompanionCoordinator};

#[derive(Clone)]
struct Receipt { token:String, session_id:String, epoch:u64, path:PathBuf, bytes:u64, hash:String }
#[derive(Default)]
pub(crate) struct CalendarHandoff { receipts:Mutex<VecDeque<Receipt>> }
const NO_APPLICATION:&str="这台电脑还没有可用的默认日历文件应用。文件已保留；请在常用日历中导入下方保存位置的文件，或在 Windows 中为 .ics 文件选择默认应用后重试。";

impl CalendarHandoff {
    pub(crate) fn remember(&self, session:&CompanionV1HostSession, path:&Path, bytes:u64, hash:String)->Result<String,String> {
        if !path.is_absolute() || !path.extension().is_some_and(|s|s.to_str().is_some_and(|s|s.eq_ignore_ascii_case("ics"))) {
            return Err("文件已保存；直接打开仅支持 .ics 日历文件，请在接收应用中手动导入。".into());
        }
        let path=path.canonicalize().map_err(|_|"文件已保存，但暂时无法确认保存位置；请在常用日历中手动导入。")?;
        // Canonicalization may resolve a link to a different file type.
        if !path.extension().is_some_and(|s|s.to_str().is_some_and(|s|s.eq_ignore_ascii_case("ics"))) {return Err("保存位置指向其它文件类型，请在常用日历中手动导入。".into());}
        let token=uuid::Uuid::new_v4().to_string();
        let mut receipts=self.receipts.lock().map_err(|_|"打开入口暂时不可用，已保存的文件仍保留。")?;
        while receipts.len()>=32 {receipts.pop_front();}
        receipts.push_back(Receipt{token:token.clone(),session_id:session.id.clone(),epoch:session.calendar_copy_epoch,path,bytes,hash});
        Ok(token)
    }

    fn open_with(&self, token:&str, rows:&[CompanionV1HostSession], opener:impl FnOnce(&Path)->Result<(),String>)->Result<(),String> {
        let receipt=self.receipts.lock().map_err(|_|"打开入口暂时不可用。")?.iter().find(|r|r.token==token).cloned()
            .ok_or("这个打开入口已过期。已保存的文件仍保留；请手动导入或重新保存日历文件。")?;
        let session=rows.iter().find(|s|s.id==receipt.session_id).ok_or("原记录已移除，请自行核对已导出的日历文件。")?;
        crate::backend::library_lifecycle::require_available(session)?;
        if session.calendar_copy_epoch!=receipt.epoch {return Err("原记录的文字已清除，这个旧文件不会再从此入口打开。".into());}
        let mut options=std::fs::OpenOptions::new();options.read(true);
        #[cfg(windows)] {
            use std::os::windows::fs::OpenOptionsExt;
            // Keep the checked file from being replaced until the Shell accepts
            // it. The receiving application can read it normally.
            options.share_mode(1); // FILE_SHARE_READ
        }
        let file=options.open(&receipt.path).map_err(|_|"无法读取已保存的日历文件。它可能已移动、删除或正在被修改；请核对保存位置，或重新保存。")?;
        check_file(&file,&receipt)?;
        opener(&receipt.path)
    }
}

fn check_file(file:&File, receipt:&Receipt)->Result<(),String> {
    let meta=file.metadata().map_err(|_|"无法核对日历文件，请重新保存。")?;
    if !meta.is_file() || meta.len()!=receipt.bytes {return Err("日历文件在保存后已变化，未打开；请重新保存所需内容。".into());}
    let mut hash=Sha256::new();let mut reader=file.take(receipt.bytes.saturating_add(1));let mut buffer=[0u8;16384];
    loop {let count=reader.read(&mut buffer).map_err(|_|"日历文件读取未完成，未打开；请重试。")?;if count==0{break;}hash.update(&buffer[..count]);}
    if format!("{:x}",hash.finalize())!=receipt.hash {return Err("日历文件在保存后已变化，未打开；请重新保存所需内容。".into());}
    Ok(())
}

#[tauri::command]
pub(crate) async fn open_companion_saved_calendar(app:tauri::AppHandle, coordinator:tauri::State<'_,Arc<CompanionCoordinator>>, token:String)->Result<(),String> {
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move|| {
        use tauri::Manager;
        // A dedicated STA avoids the Tokio worker's existing COM apartment.
        std::thread::spawn(move||{
            let snapshot=coordinator.snapshot()?;
            if snapshot.host.persistence.status!="ready" {return Err("请先恢复本机资料库，再打开日历文件；原文件仍保留。".into());}
            app.state::<CalendarHandoff>().open_with(&token,&snapshot.host.sessions,open_default)
        }).join().map_err(|_|"打开日历文件的任务未完成；原文件仍保留。".to_string())?
    }).await.map_err(|_|"打开日历文件的任务未完成；原文件仍保留。".to_string())?
}

#[cfg(windows)]
fn open_default(path:&Path)->Result<(),String> {
    use std::os::windows::ffi::OsStrExt;
    use windows::{core::{w,PCWSTR,PWSTR},Win32::{System::Com::{CoInitializeEx,CoUninitialize,COINIT_APARTMENTTHREADED,COINIT_DISABLE_OLE1DDE},UI::{Shell::*,WindowsAndMessaging::SW_SHOWNORMAL}}};
    struct Apartment; impl Drop for Apartment {fn drop(&mut self){unsafe{CoUninitialize();}}}
    unsafe{CoInitializeEx(None,COINIT_APARTMENTTHREADED|COINIT_DISABLE_OLE1DDE).ok()}.map_err(|_|"Windows 暂时不能打开日历文件，请重试或手动导入。")?;
    let _apartment=Apartment;
    let query=|kind| {let mut output=vec![0u16;32768];let mut length=output.len()as u32;
        let result=unsafe{AssocQueryStringW(ASSOCF_NONE,kind,w!(".ics"),w!("open"),PWSTR(output.as_mut_ptr()),&mut length)};
        if result.is_err()||length<2||length as usize>output.len(){None}else{Some(String::from_utf16_lossy(&output[..length as usize-1]))}};
    let prog_id=query(ASSOCSTR_PROGID);let executable=query(ASSOCSTR_EXECUTABLE);
    if prog_id.as_deref().is_none_or(|p|p.eq_ignore_ascii_case("Unknown"))
        ||executable.as_deref().is_some_and(|p|Path::new(p).file_name().is_some_and(|n|n.to_str().is_some_and(|s|s.eq_ignore_ascii_case("OpenWith.exe")))) {return Err(NO_APPLICATION.into());}
    // Shell document opening uses a path, never a command string or frontend URL.
    let normal=path.to_string_lossy();
    let normal=normal.strip_prefix(r"\\?\UNC\").map(|p|format!(r"\\{p}"))
        .unwrap_or_else(||normal.strip_prefix(r"\\?\").unwrap_or(&normal).to_string());
    let file:Vec<u16>=std::ffi::OsStr::new(&normal).encode_wide().chain(Some(0)).collect();
    let mut info=SHELLEXECUTEINFOW{cbSize:std::mem::size_of::<SHELLEXECUTEINFOW>()as u32,
        fMask:SEE_MASK_NOASYNC|SEE_MASK_FLAG_NO_UI,lpVerb:w!("open"),lpFile:PCWSTR(file.as_ptr()),nShow:SW_SHOWNORMAL.0,..Default::default()};
    unsafe{ShellExecuteExW(&mut info)}.map_err(|error|format!("Windows 未能打开日历文件（{}）。文件仍保留，请在常用日历中手动导入。",error.code()))
}

#[cfg(not(windows))]
fn open_default(_path:&Path)->Result<(),String>{Err("请在 Windows Companion Type 中打开已保存的日历文件。".into())}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture()->(PathBuf,CompanionV1HostSession,CalendarHandoff,String){
        let path=std::env::temp_dir().join(format!("companion-calendar-{}.ics",uuid::Uuid::new_v4()));
        std::fs::write(&path,b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n").unwrap();
        let mut session=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap().host.sessions.remove(0);session.id="fictional-handoff".into();
        let manager=CalendarHandoff::default();let bytes=std::fs::read(&path).unwrap();
        let token=manager.remember(&session,&path,bytes.len()as u64,format!("{:x}",Sha256::digest(&bytes))).unwrap();
        (path,session,manager,token)
    }
    #[test]fn calendar_handoff_exact_file_and_retry(){
        let(path,session,manager,token)=fixture();
        assert_eq!(manager.open_with(&token,&[session.clone()],|_|Err("no receiver".into())).unwrap_err(),"no receiver");
        manager.open_with(&token,&[session],|p|{assert_eq!(p,path.canonicalize().unwrap());assert!(std::fs::read(p).is_ok());Ok(())}).unwrap();std::fs::remove_file(path).unwrap();
    }
    #[test]fn calendar_handoff_changed_missing_unknown_never_launch(){
        let(path,session,manager,token)=fixture();let rows=[session];
        assert!(manager.open_with("untrusted-path-or-token",&rows,|_|panic!("unknown launched")).is_err());
        let mut bytes=std::fs::read(&path).unwrap();bytes[0]=b'X';std::fs::write(&path,bytes).unwrap();
        assert!(manager.open_with(&token,&rows,|_|panic!("changed launched")).unwrap_err().contains("已变化"));
        std::fs::remove_file(path).unwrap();assert!(manager.open_with(&token,&rows,|_|panic!("missing launched")).is_err());
    }
    #[test]fn calendar_handoff_removed_or_cleared_source_never_launch(){
        let(path,mut session,manager,token)=fixture();
        assert!(manager.open_with(&token,&[],|_|panic!("removed launched")).is_err());
        session.organization.trashed_at=Some("2026-10-28T15:00:00Z".into());
        assert!(manager.open_with(&token,&[session.clone()],|_|panic!("trashed launched")).is_err());
        session.organization.trashed_at=None;
        session.calendar_copy_epoch+=1;assert!(manager.open_with(&token,&[session],|_|panic!("cleared launched")).is_err());std::fs::remove_file(path).unwrap();
    }
    #[cfg(windows)]
    #[test]fn calendar_handoff_keeps_checked_file_locked_during_open(){
        let(path,session,manager,token)=fixture();
        manager.open_with(&token,&[session],|p|{
            assert!(std::fs::OpenOptions::new().write(true).open(p).is_err());
            assert!(std::fs::remove_file(p).is_err());
            Ok(())
        }).unwrap();
        std::fs::remove_file(path).unwrap();
    }
    #[test]fn calendar_handoff_refuses_other_extensions_and_bounds_receipts(){
        let(path,session,manager,token)=fixture();
        assert!(manager.remember(&session,&path.with_extension("exe"),0,String::new()).is_err());
        let bytes=std::fs::read(&path).unwrap();
        for _ in 0..32 {manager.remember(&session,&path,bytes.len()as u64,format!("{:x}",Sha256::digest(&bytes))).unwrap();}
        assert_eq!(manager.receipts.lock().unwrap().len(),32);
        assert!(manager.open_with(&token,&[session],|_|panic!("evicted launched")).is_err());std::fs::remove_file(path).unwrap();
    }
}
