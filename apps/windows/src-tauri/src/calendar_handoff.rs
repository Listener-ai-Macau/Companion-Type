//! Open only an exact calendar file saved by this process, after a user click.
//! A successful Shell handoff is not proof of import, synchronization or alarms.
use std::{collections::VecDeque, fs::File, io::Read, path::{Path, PathBuf}, sync::{Arc, Mutex}};
use sha2::{Digest, Sha256};
use crate::{companion_v1::CompanionV1HostSession, coordinator::CompanionCoordinator};

#[derive(Clone)]
struct Receipt { token:String, session_id:String, epoch:u64, mode:String, path:PathBuf, bytes:u64, hash:String, choices:Vec<(String,String)> }
#[derive(Default)]
pub(crate) struct CalendarHandoff { receipts:Mutex<VecDeque<Receipt>> }
#[derive(Debug,serde::Serialize)]
pub(crate) struct CalendarApplication { id:String, label:String }
#[derive(Debug,serde::Serialize)]
#[serde(tag="status",rename_all="snake_case")]
pub(crate) enum CalendarOpenOutcome { Requested, ChooseApplication { applications:Vec<CalendarApplication> } }
enum ShellOpenOutcome { Requested, Applications(Vec<(String,String)>) }

/// A remembered basename is only a dialog suggestion, never a remembered path
/// or permission to replace a file. Invalid historical names fall back to the
/// ordinary generated name.
pub(crate) fn saved_name_hint<'a>(session:&'a CompanionV1HostSession,mode:&str)->Option<&'a str> {
    let copy=session.calendar_copies.iter().find(|c|c.meeting_mode==mode && c.privacy_epoch==session.calendar_copy_epoch)?;
    let name=copy.file_name.as_str();
    let stem=name.split('.').next()?.to_ascii_uppercase();
    let reserved=matches!(stem.as_str(),"CON"|"PRN"|"AUX"|"NUL")
        || (stem.len()==4 && (stem.starts_with("COM")||stem.starts_with("LPT")) && matches!(stem.as_bytes()[3],b'1'..=b'9'));
    if name.is_empty() || name.trim()!=name || name.encode_utf16().count()>255
        || reserved
        || name.chars().any(|c|c.is_control()||matches!(c,'/'|'\\'|':'|'*'|'?'|'"'|'<'|'>'|'|'))
        || !Path::new(name).extension().is_some_and(|s|s.to_str().is_some_and(|s|s.eq_ignore_ascii_case("ics"))) {return None;}
    Some(name)
}

pub(crate) fn require_saved_name_unchanged(original:&CompanionV1HostSession,current:&CompanionV1HostSession,mode:&str,name:&str)->Result<(),String> {
    crate::backend::library_lifecycle::require_available(current)?;
    if current.id!=original.id || current.calendar_copy_epoch!=original.calendar_copy_epoch || saved_name_hint(current,mode)!=Some(name) {
        return Err("上次文件记录已改变，请重新核对保存位置；本次未写入文件。".into());
    }
    Ok(())
}

impl CalendarHandoff {
    pub(crate) fn remember(&self, session:&CompanionV1HostSession, mode:&str, path:&Path, bytes:u64, hash:String)->Result<String,String> {
        if !path.is_absolute() || !path.extension().is_some_and(|s|s.to_str().is_some_and(|s|s.eq_ignore_ascii_case("ics"))) {
            return Err("文件已保存；直接打开仅支持 .ics 日历文件，请在接收应用中手动导入。".into());
        }
        let path=path.canonicalize().map_err(|_|"文件已保存，但暂时无法确认保存位置；请在常用日历中手动导入。")?;
        // Canonicalization may resolve a link to a different file type.
        if !path.extension().is_some_and(|s|s.to_str().is_some_and(|s|s.eq_ignore_ascii_case("ics"))) {return Err("保存位置指向其它文件类型，请在常用日历中手动导入。".into());}
        let token=uuid::Uuid::new_v4().to_string();
        let mut receipts=self.receipts.lock().map_err(|_|"打开入口暂时不可用，已保存的文件仍保留。")?;
        while receipts.len()>=32 {receipts.pop_front();}
        receipts.push_back(Receipt{token:token.clone(),session_id:session.id.clone(),epoch:session.calendar_copy_epoch,mode:mode.into(),path,bytes,hash,choices:Vec::new()});
        Ok(token)
    }

    /// A location hint for an ordinary native Save As dialog, never authority
    /// to overwrite. The user still selects and confirms the destination.
    pub(crate) fn save_hint(&self, token:&str, session:&CompanionV1HostSession, mode:&str)->Result<PathBuf,String> {
        let receipts=self.receipts.lock().map_err(|_|"上次保存位置暂时无法读取，请重新选择保存位置。")?;
        let receipt=receipts.iter().find(|r|r.token==token).ok_or("上次保存入口已过期，请选择保存新的日历文件。")?;
        crate::backend::library_lifecycle::require_available(session)?;
        if receipt.session_id!=session.id || receipt.epoch!=session.calendar_copy_epoch || receipt.mode!=mode {
            return Err("上次保存位置不属于当前记录或整理方式，请重新选择。".into());
        }
        Ok(receipt.path.clone())
    }

    fn selected_application(&self, token:&str, choice:&str)->Result<String,String> {
        let rows=self.receipts.lock().map_err(|_|"应用选择暂时不可用，请重新打开文件。")?;
        rows.iter().find(|r|r.token==token).and_then(|r|r.choices.iter().find(|(id,_)|id==choice))
            .map(|(_,name)|name.clone()).ok_or_else(||"这个应用选择已过期，请重新打开文件并选择。".into())
    }

    fn response(&self, token:&str, result:ShellOpenOutcome)->Result<CalendarOpenOutcome,String> {
        match result {
            ShellOpenOutcome::Requested=>Ok(CalendarOpenOutcome::Requested),
            ShellOpenOutcome::Applications(handlers)=>{
                if handlers.is_empty() {return Err("Windows 尚未提供可接收 .ics 文件的应用。文件已保留；请在常用日历中导入，或安装支持日历文件的应用后重试。".into());}
                let mut rows=self.receipts.lock().map_err(|_|"应用选择暂时不可用，请重试。")?;
                let receipt=rows.iter_mut().find(|r|r.token==token).ok_or("这个打开入口已过期，请重新保存日历文件。")?;
                receipt.choices.clear();
                let applications=handlers.into_iter().map(|(name,label)|{
                    let id=uuid::Uuid::new_v4().to_string();receipt.choices.push((id.clone(),name));CalendarApplication{id,label}
                }).collect();
                Ok(CalendarOpenOutcome::ChooseApplication{applications})
            }
        }
    }

    fn open_with<T>(&self, token:&str, rows:&[CompanionV1HostSession], opener:impl FnOnce(&Path)->Result<T,String>)->Result<T,String> {
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
pub(crate) async fn open_companion_saved_calendar(app:tauri::AppHandle, coordinator:tauri::State<'_,Arc<CompanionCoordinator>>, token:String,choice_id:Option<String>,choose_application:Option<bool>)->Result<CalendarOpenOutcome,String> {
    let coordinator=coordinator.inner().clone();
    tauri::async_runtime::spawn_blocking(move|| {
        use tauri::Manager;
        // A dedicated STA avoids the Tokio worker's existing COM apartment.
        std::thread::spawn(move||{
            let snapshot=coordinator.snapshot()?;
            if snapshot.host.persistence.status!="ready" {return Err("请先恢复本机资料库，再打开日历文件；原文件仍保留。".into());}
            let manager=app.state::<CalendarHandoff>();
            let selected=choice_id.as_deref().map(|id|manager.selected_application(&token,id)).transpose()?;
            manager.open_with(&token,&snapshot.host.sessions,|path|manager.response(&token,open_default(path,selected.as_deref(),choose_application.unwrap_or(false))?))
        }).join().map_err(|_|"打开日历文件的任务未完成；原文件仍保留。".to_string())?
    }).await.map_err(|_|"打开日历文件的任务未完成；原文件仍保留。".to_string())?
}

#[cfg(windows)]
fn open_default(path:&Path,selected:Option<&str>,list_only:bool)->Result<ShellOpenOutcome,String> {open_shell(path,None,selected,list_only)}

#[cfg(windows)]
fn shell_file_name(path:&Path)->Vec<u16> {
    use std::os::windows::ffi::OsStrExt;
    let original:Vec<u16>=path.as_os_str().encode_wide().collect();
    let mut normal=if original.starts_with(&[92,92,63,92,85,78,67,92]) {
        let mut unc=vec![92,92];unc.extend_from_slice(&original[8..]);unc
    }else if original.starts_with(&[92,92,63,92]) {original[4..].to_vec()}else{original};
    normal.push(0);normal
}

#[cfg(windows)]
fn open_shell(path:&Path, explicit_class:Option<&str>,selected:Option<&str>,list_only:bool)->Result<ShellOpenOutcome,String> {
    use windows::{core::{w,PCWSTR,PWSTR},Win32::{System::Com::{CoInitializeEx,CoUninitialize,COINIT_APARTMENTTHREADED,COINIT_DISABLE_OLE1DDE},UI::{Shell::*,WindowsAndMessaging::SW_SHOWNORMAL}}};
    struct Apartment; impl Drop for Apartment {fn drop(&mut self){unsafe{CoUninitialize();}}}
    unsafe{CoInitializeEx(None,COINIT_APARTMENTTHREADED|COINIT_DISABLE_OLE1DDE).ok()}.map_err(|_|"Windows 暂时不能打开日历文件，请重试或手动导入。")?;
    let _apartment=Apartment;
    if list_only && selected.is_none() {return Ok(ShellOpenOutcome::Applications(registered_handlers()?.into_iter().map(|(name,label,_)|(name,label)).collect()));}
    if let Some(name)=selected {
        let handlers=registered_handlers()?;
        let (_,_,handler)=handlers.into_iter().find(|(candidate,_,_)|candidate==name)
            .ok_or("所选应用已不可用，请重新打开文件并选择其它应用。")?;
        let file=shell_file_name(path);
        let item:IShellItem=unsafe{SHCreateItemFromParsingName(PCWSTR(file.as_ptr()),None)}
            .map_err(|_|"暂时无法准备已保存文件，请重试。")?;
        let data:windows::Win32::System::Com::IDataObject=unsafe{item.BindToHandler(None,&BHID_DataObject)}
            .map_err(|_|"暂时无法交接已保存文件，请重试。")?;
        unsafe{handler.Invoke(&data)}.map_err(|error|format!("所选应用未能打开日历文件（{}）。文件仍保留，可重试或手动导入。",error.code()))?;
        return Ok(ShellOpenOutcome::Requested);
    }
    let query=|kind| {let mut output=vec![0u16;32768];let mut length=output.len()as u32;
        let result=unsafe{AssocQueryStringW(ASSOCF_NONE,kind,w!(".ics"),w!("open"),PWSTR(output.as_mut_ptr()),&mut length)};
        if result.is_err()||length<2||length as usize>output.len(){None}else{Some(String::from_utf16_lossy(&output[..length as usize-1]))}};
    // Use the default when present; otherwise let the user choose for this file.
    // No association-registration flags or settings writes are used. The explicit
    // class remains confined to the ignored isolated receiver test.
    if explicit_class.is_none() {
        let prog_id=query(ASSOCSTR_PROGID);let executable=query(ASSOCSTR_EXECUTABLE);
        if prog_id.as_deref().is_none_or(|p|p.eq_ignore_ascii_case("Unknown"))
            ||executable.as_deref().is_some_and(|p|Path::new(p).file_name().is_some_and(|n|n.to_str().is_some_and(|s|s.eq_ignore_ascii_case("OpenWith.exe")))) {
            return Ok(ShellOpenOutcome::Applications(registered_handlers()?.into_iter().map(|(name,label,_)|(name,label)).collect()));
        }
    }
    // Shell document opening uses a path, never a command string or frontend URL.
    let file=shell_file_name(path);
    let class:Vec<u16>=explicit_class.unwrap_or("").encode_utf16().chain(Some(0)).collect();
    let mut info=SHELLEXECUTEINFOW{cbSize:std::mem::size_of::<SHELLEXECUTEINFOW>()as u32,
        fMask:SEE_MASK_NOASYNC|SEE_MASK_FLAG_NO_UI,lpVerb:w!("open"),lpFile:PCWSTR(file.as_ptr()),nShow:SW_SHOWNORMAL.0,..Default::default()};
    if explicit_class.is_some() {info.fMask|=SEE_MASK_CLASSNAME;info.lpClass=PCWSTR(class.as_ptr());}
    unsafe{ShellExecuteExW(&mut info)}.map(|_|ShellOpenOutcome::Requested).map_err(|error|format!("Windows 未能打开日历文件（{}）。文件仍保留，请在常用日历中手动导入。",error.code()))
}

#[cfg(windows)]
fn registered_handlers()->Result<Vec<(String,String,windows::Win32::UI::Shell::IAssocHandler)>,String> {
    use windows::{core::{w,PWSTR},Win32::{System::Com::CoTaskMemFree,UI::Shell::*}};
    fn owned_text(value:PWSTR)->Option<String> {
        if value.is_null(){return None;}
        let text=unsafe{value.to_string()}.ok();unsafe{CoTaskMemFree(Some(value.0 as *const _));}text
    }
    let enumerator=unsafe{SHAssocEnumHandlers(w!(".ics"),ASSOC_FILTER_RECOMMENDED)}
        .map_err(|_|"Windows 暂时无法列出日历文件应用，请重试或手动导入。")?;
    let mut result=Vec::new();
    for _ in 0..64 {
        let mut item=[None];let mut count=0;
        unsafe{enumerator.Next(&mut item,Some(&mut count))}.map_err(|_|"Windows 应用列表未读取完成，请重试。")?;
        if count==0{break;}
        if let Some(handler)=item[0].take() {
            let name=unsafe{handler.GetName()}.ok().and_then(owned_text);
            let label=unsafe{handler.GetUIName()}.ok().and_then(owned_text);
            if let (Some(name),Some(label))=(name,label) {
                if name.is_empty()||label.trim().is_empty()||name.to_lowercase().ends_with("openwith.exe")||result.iter().any(|(n,_,_)|n==&name){continue;}
                result.push((name,label,handler));
            }
        }
    }
    Ok(result)
}

#[cfg(not(windows))]
fn open_default(_path:&Path,_selected:Option<&str>,_list_only:bool)->Result<ShellOpenOutcome,String>{Err("请在 Windows Companion Type 中打开已保存的日历文件。".into())}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]fn remembered_basename_is_scoped_and_never_a_path() {
        let (path,mut session,_,_)=fixture();
        let make=|name:&str,mode:&str,epoch:u64| crate::backend::calendar_copy::Copy {
            schema:1,privacy_epoch:epoch,meeting_mode:mode.into(),saved_at:"2026-10-29".into(),file_name:name.into(),file_sha256:"a".repeat(64),content_hash:"b".repeat(64),source_title:"例".into(),source_markdown:"示例".into(),entries:vec![],transient_slots:vec![]
        };
        session.calendar_copies=vec![make("交接提醒.ics","offlineStore",0)];
        assert_eq!(saved_name_hint(&session,"offlineStore"),Some("交接提醒.ics"));
        assert!(require_saved_name_unchanged(&session,&session,"offlineStore","交接提醒.ics").is_ok());
        let mut later=session.clone();later.calendar_copy_epoch+=1;
        assert!(require_saved_name_unchanged(&session,&later,"offlineStore","交接提醒.ics").is_err());
        later=session.clone();later.calendar_copies[0].file_name="别的文件.ics".into();
        assert!(require_saved_name_unchanged(&session,&later,"offlineStore","交接提醒.ics").is_err());
        later=session.clone();later.organization.trashed_at=Some("now".into());
        assert!(require_saved_name_unchanged(&session,&later,"offlineStore","交接提醒.ics").is_err());
        assert_eq!(saved_name_hint(&session,"onlineLive"),None);
        session.calendar_copy_epoch=1;assert_eq!(saved_name_hint(&session,"offlineStore"),None);session.calendar_copy_epoch=0;
        for name in ["../other.ics",r"C:\other.ics","other.txt"," ","bad:name.ics","a\n.ics","CON.ics","Lpt9.ics"] {
            session.calendar_copies[0].file_name=name.into();assert_eq!(saved_name_hint(&session,"offlineStore"),None,"{name}");
        }
        std::fs::remove_file(path).unwrap();
    }
    fn fixture()->(PathBuf,CompanionV1HostSession,CalendarHandoff,String){
        let path=std::env::temp_dir().join(format!("companion-calendar-{}.ics",uuid::Uuid::new_v4()));
        std::fs::write(&path,b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n").unwrap();
        let mut session=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap().host.sessions.remove(0);session.id="fictional-handoff".into();
        let manager=CalendarHandoff::default();let bytes=std::fs::read(&path).unwrap();
        let token=manager.remember(&session,&session.meeting_mode,&path,bytes.len()as u64,format!("{:x}",Sha256::digest(&bytes))).unwrap();
        (path,session,manager,token)
    }
    #[test]fn calendar_save_hint_is_scoped_but_never_opens_or_writes() {
        let(path,mut session,manager,token)=fixture();
        let before=std::fs::read(&path).unwrap();
        assert_eq!(manager.save_hint(&token,&session,&session.meeting_mode).unwrap(),path.canonicalize().unwrap());
        assert!(manager.save_hint(&token,&session,"onlineLive").is_err());
        assert!(manager.save_hint("arbitrary path",&session,&session.meeting_mode).is_err());
        let original_id=session.id.clone();session.id="other-record".into();
        assert!(manager.save_hint(&token,&session,&session.meeting_mode).is_err());session.id=original_id;
        session.calendar_copy_epoch+=1;
        assert!(manager.save_hint(&token,&session,&session.meeting_mode).is_err());session.calendar_copy_epoch-=1;
        session.organization.trashed_at=Some("2026-10-29T00:00:00Z".into());
        assert!(manager.save_hint(&token,&session,&session.meeting_mode).is_err());
        assert_eq!(std::fs::read(&path).unwrap(),before);std::fs::remove_file(path).unwrap();
    }
    #[test]fn calendar_save_hint_keeps_explicit_native_overwrite_choice() {
        let(path,session,manager,token)=fixture();
        // A hint is deliberately independent of old file contents. External
        // edits are not silently replaced: the command still opens Save As.
        std::fs::write(&path,b"external change").unwrap();
        assert_eq!(manager.save_hint(&token,&session,&session.meeting_mode).unwrap(),path.canonicalize().unwrap());
        assert_eq!(std::fs::read(&path).unwrap(),b"external change");
        std::fs::remove_file(path).unwrap();
        assert!(manager.save_hint(&token,&session,&session.meeting_mode).is_ok());
    }
    #[test]fn calendar_handoff_exact_file_and_retry(){
        let(path,session,manager,token)=fixture();
        assert_eq!(manager.open_with::<()>(&token,&[session.clone()],|_|Err::<(),String>("no receiver".into())).unwrap_err(),"no receiver");
        manager.open_with::<()>(&token,&[session],|p|{assert_eq!(p,path.canonicalize().unwrap());assert!(std::fs::read(p).is_ok());Ok(())}).unwrap();std::fs::remove_file(path).unwrap();
    }
    #[test]fn calendar_handoff_changed_missing_unknown_never_launch(){
        let(path,session,manager,token)=fixture();let rows=[session];
        assert!(manager.open_with::<()>("untrusted-path-or-token",&rows,|_|panic!("unknown launched")).is_err());
        let mut bytes=std::fs::read(&path).unwrap();bytes[0]=b'X';std::fs::write(&path,bytes).unwrap();
        assert!(manager.open_with::<()>(&token,&rows,|_|panic!("changed launched")).unwrap_err().contains("已变化"));
        std::fs::remove_file(path).unwrap();assert!(manager.open_with::<()>(&token,&rows,|_|panic!("missing launched")).is_err());
    }
    #[test]fn calendar_handoff_removed_or_cleared_source_never_launch(){
        let(path,mut session,manager,token)=fixture();
        assert!(manager.open_with::<()>(&token,&[],|_|panic!("removed launched")).is_err());
        session.organization.trashed_at=Some("2026-10-28T15:00:00Z".into());
        assert!(manager.open_with::<()>(&token,&[session.clone()],|_|panic!("trashed launched")).is_err());
        session.organization.trashed_at=None;
        session.calendar_copy_epoch+=1;assert!(manager.open_with::<()>(&token,&[session],|_|panic!("cleared launched")).is_err());std::fs::remove_file(path).unwrap();
    }
    #[test]fn calendar_handoff_application_choices_are_bound_to_saved_file(){
        let(path,session,manager,token)=fixture();
        let result=manager.response(&token,ShellOpenOutcome::Applications(vec![("trusted-receiver".into(),"Calendar".into())])).unwrap();
        let CalendarOpenOutcome::ChooseApplication{applications}=result else{panic!("missing choice")};
        let choice=&applications[0].id;
        assert_eq!(manager.selected_application(&token,choice).unwrap(),"trusted-receiver");
        assert!(manager.selected_application(&token,"C:\\untrusted.exe").is_err());
        assert!(manager.selected_application("another-file",choice).is_err());
        manager.response(&token,ShellOpenOutcome::Applications(vec![("new-receiver".into(),"New Calendar".into())])).unwrap();
        assert!(manager.selected_application(&token,choice).is_err());
        manager.open_with(&token,&[session],|_|Ok(())).unwrap();std::fs::remove_file(path).unwrap();
    }
    #[cfg(windows)]
    #[test]fn calendar_handoff_preserves_windows_path_units(){
        use std::os::windows::ffi::OsStringExt;
        let units:Vec<u16>=r"\\?\C:\日程\".encode_utf16().chain([0xd800]).chain(".ics".encode_utf16()).collect();
        let path=PathBuf::from(std::ffi::OsString::from_wide(&units));
        assert_eq!(shell_file_name(&path),units[4..].iter().copied().chain([0]).collect::<Vec<_>>());
        assert_eq!(shell_file_name(Path::new(r"\\?\UNC\server\share\日程.ics")),r"\\server\share\日程.ics".encode_utf16().chain([0]).collect::<Vec<_>>());
    }
    #[cfg(windows)]
    #[test]
    #[ignore="Requires a prepared isolated desktop, private receiver profile and temporary explicit Shell class; never changes default apps"]
    fn calendar_handoff_windows_receiver_contract(){
        let path=PathBuf::from(std::env::var_os("P700_TEST_ICS").expect("prepared isolated file"));
        let class=std::env::var("P700_TEST_CLASS").expect("temporary test association");assert!(class.starts_with("Companion.Calendar.Handoff.Test."));
        let result=PathBuf::from(std::env::var_os("P700_TEST_RESULT").expect("isolated evidence destination"));
        let mut session=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),serde_json::from_value(serde_json::json!({"action":"meetingLoadDemo"})).unwrap()).unwrap().host.sessions.remove(0);session.id="fictional-windows-shell-handoff".into();
        let bytes=std::fs::read(&path).unwrap();let hash=format!("{:x}",Sha256::digest(&bytes));let manager=CalendarHandoff::default();
        let token=manager.remember(&session,&session.meeting_mode,&path,bytes.len()as u64,hash.clone()).unwrap();
        let opened=manager.open_with(&token,&[session],|p|open_shell(p,Some(&class),None,false));
        std::fs::write(result,serde_json::to_vec_pretty(&serde_json::json!({"shellAccepted":opened.is_ok(),"error":opened.as_ref().err(),"fileSha256":hash,"explicitTestClass":class,"defaultAssociationExercised":false,"importConfirmed":false})).unwrap()).unwrap();
        opened.unwrap();
    }
    #[cfg(windows)]
    #[test]fn calendar_handoff_keeps_checked_file_locked_during_open(){
        let(path,session,manager,token)=fixture();
        manager.open_with::<()>(&token,&[session],|p|{
            assert!(std::fs::OpenOptions::new().write(true).open(p).is_err());
            assert!(std::fs::remove_file(p).is_err());
            Ok(())
        }).unwrap();
        std::fs::remove_file(path).unwrap();
    }
    #[test]fn calendar_handoff_refuses_other_extensions_and_bounds_receipts(){
        let(path,session,manager,token)=fixture();
        assert!(manager.remember(&session,&session.meeting_mode,&path.with_extension("exe"),0,String::new()).is_err());
        let bytes=std::fs::read(&path).unwrap();
        for _ in 0..32 {manager.remember(&session,&session.meeting_mode,&path,bytes.len()as u64,format!("{:x}",Sha256::digest(&bytes))).unwrap();}
        assert_eq!(manager.receipts.lock().unwrap().len(),32);
        assert!(manager.open_with::<()>(&token,&[session],|_|panic!("evicted launched")).is_err());std::fs::remove_file(path).unwrap();
    }
}
