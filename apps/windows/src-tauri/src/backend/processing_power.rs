//! Request execution only while a meeting operation is running. The screen
//! may turn off; explicit sleep and the user's power policy still win.
#[cfg(windows)]
mod native {
    #[repr(C)]
    union Reason { simple:*const u16, _detailed:[usize;3] }
    #[repr(C)]
    struct Context { version:u32, flags:u32, reason:Reason }
    #[link(name="kernel32")]
    extern "system" {
        fn PowerCreateRequest(context:*const Context)->isize;
        fn PowerSetRequest(request:isize,kind:i32)->i32;
        fn PowerClearRequest(request:isize,kind:i32)->i32;
        fn CloseHandle(handle:isize)->i32;
    }
    pub(super) struct Lease { handle:isize, _reason:Vec<u16> }
    impl Lease {
        pub(super) fn new(reason:&str)->Option<Self>{
            let reason=reason.encode_utf16().chain(Some(0)).collect::<Vec<_>>();
            let context=Context{version:0,flags:1,reason:Reason{simple:reason.as_ptr()}};
            let handle=unsafe{PowerCreateRequest(&context)};
            if handle==0||handle==-1{return None;}
            if unsafe{PowerSetRequest(handle,1)}==0 {unsafe{CloseHandle(handle)};return None;}
            if unsafe{PowerSetRequest(handle,3)}==0 {
                unsafe{PowerClearRequest(handle,1);CloseHandle(handle)};return None;
            }
            Some(Self{handle,_reason:reason})
        }
    }
    impl Drop for Lease {
        fn drop(&mut self){unsafe{
            PowerClearRequest(self.handle,3);PowerClearRequest(self.handle,1);CloseHandle(self.handle);
        }}
    }
}

pub(super) struct ProcessingPower {
    #[cfg(windows)]
    _lease:Option<native::Lease>,
}

pub(super) fn hold()->ProcessingPower{
    #[cfg(windows)] {
        let lease=native::Lease::new("Companion 正在处理会议，完成后自动释放");
        if lease.is_none(){eprintln!("[meeting] task execution power request unavailable");}
        ProcessingPower{_lease:lease}
    }
    #[cfg(not(windows))] {ProcessingPower{}}
}

#[cfg(all(test,windows))]
mod tests {
    use super::*;
    use std::os::windows::process::CommandExt;
    #[test]
    fn owned_power_request_is_visible_and_released_without_a_global_setting(){
        let marker=format!("companion-meeting-power-test-{}",std::process::id());
        let requests=||String::from_utf8_lossy(&std::process::Command::new("powercfg.exe")
            .arg("/requests").creation_flags(0x08000000).output().unwrap().stdout).into_owned();
        {let _lease=native::Lease::new(&marker).expect("create owned system/execution request");
            assert!(requests().contains(&marker));}
        assert!(!requests().contains(&marker));
    }
}
