//! A rendered file clipboard payload; no Shell invocation or recipient selection.
use std::path::Path;

#[cfg(windows)]
fn file_clipboard_payload(path:&Path)->Result<Vec<u8>,String>{
    use std::os::windows::ffi::OsStrExt;
    let metadata=std::fs::symlink_metadata(path).map_err(|_|"文件副本已不可用，请重新准备或保存文件。")?;
    if !path.is_absolute()||!metadata.is_file()||metadata.file_type().is_symlink(){return Err("文件副本已不可用，请重新准备或保存文件。".into());}
    let wide:Vec<u16>=path.as_os_str().encode_wide().collect();
    if wide.is_empty()||wide.contains(&0){return Err("文件位置无效，请改用保存。".into());}
    // DROPFILES: pFiles, POINT(x/y), fNC, fWide; followed by exactly one
    // UTF-16 filename and two terminating NULs. No text/shell command fallback.
    let length=20usize.checked_add(wide.len().checked_add(2).and_then(|n|n.checked_mul(2)).ok_or("文件位置过长。")?).ok_or("文件位置过长。")?;
    let mut bytes=Vec::with_capacity(length);
    for value in [20u32,0,0,0,1]{bytes.extend_from_slice(&value.to_le_bytes());}
    for value in wide.into_iter().chain([0,0]){bytes.extend_from_slice(&value.to_le_bytes());}
    Ok(bytes)
}

pub fn copy_file_to_clipboard(owner:usize,path:&Path)->Result<(),String>{
    #[cfg(windows)] unsafe{
        use windows::{core::w,Win32::{Foundation::{GlobalFree,HANDLE,HGLOBAL,HWND},System::{DataExchange::{OpenClipboard,CloseClipboard,EmptyClipboard,RegisterClipboardFormatW,SetClipboardData},Memory::{GlobalAlloc,GlobalLock,GlobalUnlock,GMEM_MOVEABLE}}}};
        if owner==0{return Err("窗口已关闭，请重新打开记录。".into());}
        let payload=file_clipboard_payload(path)?;
        struct Memory(Option<HGLOBAL>);
        impl Drop for Memory{fn drop(&mut self){if let Some(value)=self.0.take(){unsafe{let _=GlobalFree(value);}}}}
        impl Memory{
            unsafe fn new(bytes:&[u8])->Result<Self,String>{
                let memory=Self(Some(GlobalAlloc(GMEM_MOVEABLE,bytes.len()).map_err(|_|"没有足够内存复制文件，请改用保存。")?));
                let pointer=GlobalLock(memory.0.unwrap());
                if pointer.is_null(){return Err("Windows暂时不能准备文件剪贴板，请重试。".into());}
                std::ptr::copy_nonoverlapping(bytes.as_ptr(),pointer.cast(),bytes.len());let _=GlobalUnlock(memory.0.unwrap());Ok(memory)
            }
            unsafe fn publish(&mut self,format:u32)->Result<(),String>{
                SetClipboardData(format,HANDLE(self.0.unwrap().0)).map_err(|_|"文件未能完整放入剪贴板，请重试或保存文件。")?;
                self.0.take();Ok(()) // Windows owns the allocation only after success.
            }
        }
        // Allocate everything before opening/clearing the user's clipboard.
        let mut files=Memory::new(&payload)?;let mut effect=Memory::new(&1u32.to_le_bytes())?;
        let effect_format=RegisterClipboardFormatW(w!("Preferred DropEffect"));
        if effect_format==0{return Err("Windows文件剪贴板暂不可用，请改用保存。".into());}
        if OpenClipboard(HWND(owner as *mut _)).is_err(){return Err("剪贴板正被其他应用使用，请稍后重试。".into());}
        struct Close;impl Drop for Close{fn drop(&mut self){unsafe{let _=CloseClipboard();}}}let _close=Close;
        EmptyClipboard().map_err(|_|"Windows未能准备文件剪贴板，请重试。")?;
        effect.publish(effect_format)?;files.publish(15)?;
        return Ok(());
    }
    #[cfg(not(windows))]{let _=(owner,path);Err("当前系统不支持Windows文件剪贴板。".into())}
}

#[cfg(all(test,windows))]
mod tests{
    use super::*;
    use std::os::windows::ffi::OsStringExt;
    use windows::{core::w,Win32::{Foundation::{HANDLE,HWND},System::{DataExchange::{OpenClipboard,CloseClipboard,GetClipboardData,RegisterClipboardFormatW},Memory::{GlobalLock,GlobalUnlock}},UI::{Shell::{DragQueryFileW,HDROP},WindowsAndMessaging::{CreateWindowExW,DestroyWindow,WINDOW_EX_STYLE,WINDOW_STYLE}}}};
    #[link(name="user32")]
    extern "system"{
        fn GetProcessWindowStation()->*mut std::ffi::c_void;
        fn OpenWindowStationW(name:*const u16,inherit:i32,access:u32)->*mut std::ffi::c_void;
        fn SetProcessWindowStation(handle:*mut std::ffi::c_void)->i32;
        fn OpenDesktopW(name:*const u16,flags:u32,inherit:i32,access:u32)->*mut std::ffi::c_void;
        fn SetThreadDesktop(handle:*mut std::ffi::c_void)->i32;
        fn GetUserObjectInformationW(handle:*mut std::ffi::c_void,index:i32,info:*mut std::ffi::c_void,length:u32,needed:*mut u32)->i32;
    }
    fn station_name()->String{
        unsafe{let mut name=[0u16;256];let mut needed=0;
            assert_ne!(GetUserObjectInformationW(GetProcessWindowStation(),2,name.as_mut_ptr().cast(),(name.len()*2)as u32,&mut needed),0);
            String::from_utf16(&name[..name.iter().position(|n|*n==0).unwrap()]).unwrap()}
    }
    unsafe fn copied_file(owner:HWND)->(std::path::PathBuf,u32){
        OpenClipboard(owner).unwrap();
        struct Close;impl Drop for Close{fn drop(&mut self){unsafe{CloseClipboard().unwrap();}}}let _close=Close;
        let handle=GetClipboardData(15).unwrap();let drop=HDROP(handle.0);
        assert_eq!(DragQueryFileW(drop,u32::MAX,None),1);
        let length=DragQueryFileW(drop,0,None);let mut buffer=vec![0u16;length as usize+1];
        assert_eq!(DragQueryFileW(drop,0,Some(&mut buffer)),length);
        let path=std::path::PathBuf::from(std::ffi::OsString::from_wide(&buffer[..length as usize]));
        let effect=GetClipboardData(RegisterClipboardFormatW(w!("Preferred DropEffect"))).unwrap();
        let ptr=GlobalLock(windows::Win32::Foundation::HGLOBAL(effect.0));assert!(!ptr.is_null());
        let value=std::ptr::read_unaligned(ptr.cast::<u32>());let _=GlobalUnlock(windows::Win32::Foundation::HGLOBAL(effect.0));
        (path,value)
    }
    #[test]
    #[ignore="Requires a separate noninteractive window station; never use the owner's clipboard"]
    fn content078_real_file_clipboard_is_exact_unicode_copy_and_preserves_source(){
        let required=std::env::var("COMPANION_FILE_CLIPBOARD_TEST_STATION").expect("Isolated launcher required");
        assert!(required.starts_with("CompanionFileCopy078-")&&!required.eq_ignore_ascii_case("WinSta0"));
        // Explicitly bind this fresh non-GUI test process/thread. Python's
        // STARTUPINFO object does not expose native lpDesktop to CreateProcess.
        // No clipboard API or owner window exists before actual-station proof.
        unsafe{
            let name:Vec<u16>=required.encode_utf16().chain([0]).collect();
            let station=OpenWindowStationW(name.as_ptr(),0,0x37f);assert!(!station.is_null());
            assert_ne!(SetProcessWindowStation(station),0);
            let desktop=OpenDesktopW(w!("ClipboardTest").as_ptr(),0,0,0x1ff);assert!(!desktop.is_null());
            assert_ne!(SetThreadDesktop(desktop),0);
        }
        assert_eq!(station_name(),required,"No clipboard API runs on the interactive station");
        let root=std::path::PathBuf::from(std::env::var_os("COMPANION_FILE_CLIPBOARD_TEST_DIR").unwrap());
        std::fs::create_dir_all(&root).unwrap();
        let file=root.join("公开会议 # 20% & 中文 😀.pdf");let bytes=b"public exact export; budget NOT approved";
        std::fs::write(&file,bytes).unwrap();
        let owner=unsafe{CreateWindowExW(WINDOW_EX_STYLE::default(),w!("STATIC"),w!("Companion file-copy isolated test"),WINDOW_STYLE::default(),0,0,1,1,None,None,None,None)}.unwrap();
        struct Window(HWND);impl Drop for Window{fn drop(&mut self){unsafe{let _=DestroyWindow(self.0);}}}let _window=Window(owner);
        copy_file_to_clipboard(owner.0 as usize,&file).unwrap();
        let (actual,effect)=unsafe{copied_file(owner)};assert_eq!(actual,file);assert_eq!(effect,1);
        assert_eq!(std::fs::read(&actual).unwrap(),bytes);
        for rejected in [root.clone(),root.join("missing.pdf"),std::path::PathBuf::from("relative.pdf")]{
            assert!(copy_file_to_clipboard(owner.0 as usize,&rejected).is_err());
            assert_eq!(unsafe{copied_file(owner)}.0,file,"Rejected inputs must not clear the clipboard");
        }
        assert_eq!(std::fs::read(&file).unwrap(),bytes);
        println!("PASS real CF_HDROP: one exact Unicode file, Preferred DropEffect COPY, readable unchanged bytes; invalid inputs preserve prior clipboard. Private station={required}");
    }
}

