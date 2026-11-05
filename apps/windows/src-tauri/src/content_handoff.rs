//! Windows clipboard and system share sheet. No recipient is ever selected here.
use std::path::{Path,PathBuf};

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

pub fn prepare_shared_file(directory:&Path,name:&str,bytes:&[u8])->Result<PathBuf,String>{
    let file_name=Path::new(name);
    if file_name.components().count()!=1||file_name.file_name().and_then(|s|s.to_str())!=Some(name){return Err("分享文件名无效。".into());}
    std::fs::create_dir_all(directory).map_err(|_|"无法准备本机分享文件，请改用保存。")?;
    let slot=directory.join(uuid::Uuid::new_v4().to_string());
    std::fs::create_dir(&slot).map_err(|_|"无法准备本机分享文件，请改用保存。")?;
    let path=slot.join(name);
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

#[cfg(test)]mod tests{
    use super::*;
    #[test]fn content051_share_file_is_exact_immutable_and_cannot_escape_its_cache(){
        let root=std::env::temp_dir().join(format!("content-share-test-{}",uuid::Uuid::new_v4()));
        let file=prepare_shared_file(&root,"会议-所选内容.txt","尚未确认采购".as_bytes()).unwrap();
        assert_eq!(std::fs::read(&file).unwrap(),"尚未确认采购".as_bytes());
        assert!(prepare_shared_file(&root,"../escape.txt",b"no").is_err());
        let next=prepare_shared_file(&root,"会议-所选内容.txt",b"another").unwrap();assert_ne!(file,next);
        assert_eq!(std::fs::read(&file).unwrap(),"尚未确认采购".as_bytes());
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
