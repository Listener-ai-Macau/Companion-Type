//! Windows clipboard and system share sheet. No recipient is ever selected here.
use std::path::{Path,PathBuf};

#[derive(Clone,Copy,Debug,PartialEq,Eq)]
pub enum ShareDestination {SystemPanel,FileLocation}
impl ShareDestination {
    pub fn parse(value:Option<&str>)->Result<Self,String>{
        match value {None|Some("system")=>Ok(Self::SystemPanel),Some("folder")=>Ok(Self::FileLocation),_=>Err("不支持的分享方式，请重新选择。".into())}
    }
    pub fn status(self)->&'static str{match self{Self::SystemPanel=>"opened",Self::FileLocation=>"folderOpened"}}
}

pub fn write_clipboard(owner:usize,text:&str)->Result<(),String>{
    if text.contains('\0'){return Err("所选内容含无效空字符，请保存文件后核对。".into());}
    #[cfg(windows)] unsafe {
        use windows::Win32::{Foundation::{GlobalFree,HANDLE,HWND},System::{DataExchange::{OpenClipboard,CloseClipboard,EmptyClipboard,SetClipboardData},Memory::{GlobalAlloc,GlobalLock,GlobalUnlock,GMEM_MOVEABLE}}};
        let wide:Vec<u16>=text.encode_utf16().chain(std::iter::once(0)).collect();
        let memory=GlobalAlloc(GMEM_MOVEABLE,wide.len().checked_mul(2).ok_or("复制内容过长。")?).map_err(|_|"没有足够内存复制，请保存为文件。")?;
        let pointer=GlobalLock(memory) as *mut u16;
        if pointer.is_null(){let _=GlobalFree(memory);return Err("Windows暂时不能准备剪贴板，请重试。".into());}
        std::ptr::copy_nonoverlapping(wide.as_ptr(),pointer,wide.len());let _=GlobalUnlock(memory);
        if OpenClipboard(HWND(owner as *mut _)).is_err(){let _=GlobalFree(memory);return Err("剪贴板正被其他应用使用，请稍后重试或手动复制。".into());}
        struct Close;impl Drop for Close{fn drop(&mut self){unsafe{let _=CloseClipboard();}}}let _close=Close;
        if EmptyClipboard().is_err(){let _=GlobalFree(memory);return Err("Windows未能打开剪贴板，请重试。".into());}
        if SetClipboardData(13,HANDLE(memory.0)).is_err(){let _=GlobalFree(memory);return Err("复制未完成，请重试或保存文件。".into());}
        // Windows owns the memory only after successful SetClipboardData.
        return Ok(());
    }
    #[cfg(not(windows))]{let _=(owner,text);Err("当前系统不支持Windows剪贴板。".into())}
}

pub fn reserve_shared_file(directory:&Path,name:&str)->Result<PathBuf,String>{
    let file_name=Path::new(name);
    if file_name.components().count()!=1||file_name.file_name().and_then(|s|s.to_str())!=Some(name){return Err("分享文件名无效。".into());}
    std::fs::create_dir_all(directory).map_err(|_|"无法准备本机分享文件，请改用保存。")?;
    cleanup_expired(directory);
    let slot=directory.join(uuid::Uuid::new_v4().to_string());
    std::fs::create_dir(&slot).map_err(|_|"无法准备本机分享文件，请改用保存。")?;
    Ok(slot.join(name))
}

fn cleanup_expired(directory:&Path){
    // Only bounded, UUID-named directories created by this cache; no recursive
    // delete, symlink traversal, recording/library scan or current-file removal.
    let Ok(entries)=std::fs::read_dir(directory)else{return};
    for entry in entries.take(512).flatten(){
        if uuid::Uuid::parse_str(&entry.file_name().to_string_lossy()).is_err()||!entry.file_type().is_ok_and(|t|t.is_dir()&&!t.is_symlink()){continue;}
        let Ok(files)=std::fs::read_dir(entry.path())else{continue};let files=files.take(5).collect::<Result<Vec<_>,_>>();
        let Ok(files)=files else{continue};if files.len()>4{continue;}
        if !files.iter().all(|file|file.file_type().is_ok_and(|t|t.is_file()&&!t.is_symlink())&&file.metadata().ok().and_then(|m|m.modified().ok()).and_then(|t|t.elapsed().ok()).is_some_and(|age|age.as_secs()>7*24*3600)){continue;}
        for file in files{let _=std::fs::remove_file(file.path());}let _=std::fs::remove_dir(entry.path());
    }
}
pub fn prepare_shared_file(directory:&Path,name:&str,bytes:&[u8])->Result<PathBuf,String>{
    let path=reserve_shared_file(directory,name)?;
    let slot=path.parent().ok_or("分享位置无效。")?;
    if let Err(error)=crate::backend::export::write_atomic(&path,bytes){let _=std::fs::remove_dir(&slot);return Err(error);}
    Ok(path)
}

#[cfg(windows)]
pub struct ShareFile {pub path:PathBuf,pub title:String}

#[cfg(windows)]
mod native {
    use super::*;
    use windows::{core::{Interface,HSTRING},ApplicationModel::DataTransfer::{DataPackage,DataPackageOperation,DataTransferManager,DataRequestedEventArgs},Foundation::{TypedEventHandler,EventRegistrationToken},Foundation::Collections::IIterable,Storage::{StorageFile,IStorageItem},Win32::{Foundation::HWND,UI::Shell::IDataTransferManagerInterop}};
    struct Registration {manager:DataTransferManager,token:EventRegistrationToken}
    impl Drop for Registration{fn drop(&mut self){let _=self.manager.RemoveDataRequested(self.token);}}
    thread_local! {static ACTIVE:std::cell::RefCell<Option<Registration>>=const{std::cell::RefCell::new(None)};}

    struct FileLocation(*mut windows::Win32::UI::Shell::Common::ITEMIDLIST);
    impl Drop for FileLocation{fn drop(&mut self){unsafe{windows::Win32::System::Com::CoTaskMemFree(Some(self.0.cast()));}}}
    impl FileLocation{
        fn prepare(path:&Path)->Result<Self,String>{
            use std::os::windows::ffi::OsStrExt;
            use windows::{core::PCWSTR,Win32::UI::Shell::SHParseDisplayName};
            if !path.is_absolute()||!path.is_file(){return Err("分享副本已不可用，请重新准备或保存文件。".into());}
            let mut wide:Vec<u16>=path.as_os_str().encode_wide().collect();
            if wide.contains(&0){return Err("分享文件位置无效，请改用保存。".into());}
            wide.push(0);
            let mut location=Self(std::ptr::null_mut());
            unsafe{SHParseDisplayName(PCWSTR(wide.as_ptr()),None,&mut location.0,0,None)}
                .map_err(|_|"Windows无法定位分享副本，请改用保存。")?;
            if location.0.is_null(){return Err("Windows无法定位分享副本，请改用保存。".into());}
            Ok(location)
        }
    }
    pub fn open_file_location(path:&Path)->Result<(),String>{
        // The explicit user action runs on Tauri's initialized UI thread. A PIDL
        // avoids shell command strings, quoting, executable/verb injection and
        // changes to network sharing permissions. Select exactly this one copy.
        let location=FileLocation::prepare(path)?;
        unsafe{windows::Win32::UI::Shell::SHOpenFolderAndSelectItems(location.0,None,0)}
            .map_err(|_|"Windows未能打开分享文件夹，请改用保存后分享。".into())
    }
    #[cfg(test)]
    pub fn inspect_file_location(path:&Path)->Result<PathBuf,String>{
        use windows::Win32::{System::Com::CoTaskMemFree,UI::Shell::{SHGetNameFromIDList,SIGDN_FILESYSPATH}};
        let location=FileLocation::prepare(path)?;
        let value=unsafe{SHGetNameFromIDList(location.0,SIGDN_FILESYSPATH)}.map_err(|e|e.to_string())?;
        let result=unsafe{value.to_string()}.map(PathBuf::from).map_err(|e|e.to_string());
        unsafe{CoTaskMemFree(Some(value.0.cast()));}result
    }
    pub fn package(file:&ShareFile)->windows::core::Result<DataPackage>{
        let storage=StorageFile::GetFileFromPathAsync(&HSTRING::from(file.path.to_string_lossy().as_ref()))?.get()?;
        let item:IStorageItem=storage.cast()?;
        let items:IIterable<IStorageItem>=vec![Some(item)].try_into()?;
        let data=DataPackage::new()?;data.Properties()?.SetTitle(&HSTRING::from(&file.title))?;
        data.SetRequestedOperation(DataPackageOperation::Copy)?;data.SetStorageItems(&items,true)?;
        Ok(data)
    }
    pub fn prepare(file:ShareFile)->Result<DataPackage,String>{
        std::thread::spawn(move||{
            use windows::Win32::System::WinRT::{RoInitialize,RoUninitialize,RO_INIT_MULTITHREADED};
            unsafe{RoInitialize(RO_INIT_MULTITHREADED).map_err(|_|"Windows分享服务暂不可用。")?;}
            let result=package(&file).map_err(|_|"无法读取本机分享文件，请保存后分享。".to_string());
            unsafe{RoUninitialize();}result
        }).join().map_err(|_|"分享文件准备未完成，请重试。".to_string())?
    }
    pub fn open(owner:usize,package:DataPackage)->Result<(),String>{
        let result=(||->windows::core::Result<()>{
            // Called on the application's UI thread, with a real owner HWND.
            let interop:IDataTransferManagerInterop=windows::core::factory::<DataTransferManager,IDataTransferManagerInterop>()?;
            let manager:DataTransferManager=unsafe{interop.GetForWindow(HWND(owner as *mut _))?};
            ACTIVE.with(|slot|{slot.borrow_mut().take();});
            let handler=TypedEventHandler::<DataTransferManager,DataRequestedEventArgs>::new(move|_,args|{
                let args=args.as_ref().ok_or_else(windows::core::Error::from_win32)?;
                args.Request()?.SetData(&package)
            });
            let token=manager.DataRequested(&handler)?;
            ACTIVE.with(|slot|*slot.borrow_mut()=Some(Registration{manager,token}));
            if let Err(error)=unsafe{interop.ShowShareUIForWindow(HWND(owner as *mut _))}{ACTIVE.with(|slot|{slot.borrow_mut().take();});return Err(error);}
            Ok(())
        })();
        result.map_err(|_|"Windows分享面板暂不可用。文件仍保留在本机，可使用保存后分享。".into())
    }
    #[cfg(test)]
    pub fn inspect_package(file:&ShareFile)->windows::core::Result<(String,bool,u32)>{
        let data=package(file)?;let view=data.GetView()?;let items=view.GetStorageItemsAsync()?.get()?;
        Ok((view.Properties()?.Title()?.to_string(),view.RequestedOperation()?==DataPackageOperation::Copy,items.Size()?))
    }
}
#[cfg(windows)]pub use native::open as open_share;
#[cfg(windows)]pub use native::prepare as prepare_share;
#[cfg(windows)]pub use native::open_file_location;

#[cfg(test)]mod tests{
    use super::*;
    #[test]fn content070_share_destination_is_explicit_and_never_accepts_a_shell_verb(){
        assert_eq!(ShareDestination::parse(None).unwrap(),ShareDestination::SystemPanel);
        assert_eq!(ShareDestination::parse(Some("folder")).unwrap().status(),"folderOpened");
        for input in ["Windows.Share","delete","../escape","folder & calc.exe",""]{assert!(ShareDestination::parse(Some(input)).is_err());}
    }
    #[cfg(windows)]#[test]fn content070_file_location_resolves_only_existing_exact_file_without_opening_explorer(){
        use windows::Win32::System::Com::{CoInitializeEx,CoUninitialize,COINIT_APARTMENTTHREADED};
        unsafe{CoInitializeEx(None,COINIT_APARTMENTTHREADED).ok().unwrap();}
        struct Com;impl Drop for Com{fn drop(&mut self){unsafe{CoUninitialize();}}}let _com=Com;
        let root=std::env::temp_dir().join(format!("content-location-test-{}",uuid::Uuid::new_v4()));
        let name="公开会议 # 20% & 中文 😀.txt";
        let file=prepare_shared_file(&root,name,"尚未确认采购".as_bytes()).unwrap();
        let before=std::fs::read(&file).unwrap();
        let actual=native::inspect_file_location(&file).unwrap();
        assert_eq!(std::fs::canonicalize(actual).unwrap(),std::fs::canonicalize(&file).unwrap());
        assert_eq!(std::fs::read(&file).unwrap(),before);
        assert!(native::inspect_file_location(Path::new(name)).is_err());
        assert!(native::inspect_file_location(&root).is_err());
        std::fs::remove_file(&file).unwrap();assert!(native::inspect_file_location(&file).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]fn content051_share_file_is_exact_immutable_and_cannot_escape_its_cache(){
        let root=std::env::temp_dir().join(format!("content-share-test-{}",uuid::Uuid::new_v4()));
        let file=prepare_shared_file(&root,"会议-所选内容.txt","尚未确认采购".as_bytes()).unwrap();
        assert_eq!(std::fs::read(&file).unwrap(),"尚未确认采购".as_bytes());
        assert!(prepare_shared_file(&root,"../escape.txt",b"no").is_err());
        let next=prepare_shared_file(&root,"会议-所选内容.txt",b"another").unwrap();assert_ne!(file,next);
        assert_eq!(std::fs::read(&file).unwrap(),"尚未确认采购".as_bytes());
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]fn content051_expired_share_cleanup_keeps_recent_and_non_owned_files(){
        let root=std::env::temp_dir().join(format!("content-cache-test-{}",uuid::Uuid::new_v4()));
        let old=prepare_shared_file(&root,"old.txt",b"old").unwrap();
        let recent=prepare_shared_file(&root,"recent.txt",b"recent").unwrap();
        let foreign=root.join("not-a-share-uuid");std::fs::create_dir(&foreign).unwrap();let foreign=foreign.join("keep.txt");std::fs::write(&foreign,b"keep").unwrap();
        let time=std::time::SystemTime::now()-std::time::Duration::from_secs(8*24*3600);
        std::fs::OpenOptions::new().write(true).open(&old).unwrap().set_modified(time).unwrap();
        std::fs::OpenOptions::new().write(true).open(&foreign).unwrap().set_modified(time).unwrap();
        cleanup_expired(&root);assert!(!old.exists());assert!(recent.exists());assert!(foreign.exists());
        std::fs::remove_dir_all(root).unwrap();
    }
    #[cfg(windows)]#[test]fn content051_real_share_package_has_one_read_only_file_and_copy_operation(){
        use windows::Win32::System::WinRT::{RoInitialize,RoUninitialize,RO_INIT_MULTITHREADED};
        unsafe{RoInitialize(RO_INIT_MULTITHREADED).unwrap();}
        let root=std::env::temp_dir().join(format!("content-share-package-{}",uuid::Uuid::new_v4()));
        let path=prepare_shared_file(&root,"公开测试.txt",b"public fixture").unwrap();
        let (title,copy,count)=native::inspect_package(&ShareFile{path,title:"公开测试，不发送".into()}).unwrap();
        assert_eq!(title,"公开测试，不发送");assert!(copy);assert_eq!(count,1);
        std::fs::remove_dir_all(root).unwrap();unsafe{RoUninitialize();}
    }
}
