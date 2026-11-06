mod backend {pub mod export {pub fn write_atomic(path:&std::path::Path, bytes:&[u8])->Result<(),String>{std::fs::write(path,bytes).map_err(|e|e.to_string())}}}
mod content_handoff;
mod baseline_handoff;
use windows::{core::{Interface,w},ApplicationModel::DataTransfer::DataPackage,Win32::{Foundation::{HWND,LRESULT,WPARAM,LPARAM},System::WinRT::{RoInitialize,RO_INIT_SINGLETHREADED},UI::WindowsAndMessaging::*}};
fn public_path()->std::path::PathBuf {
 let path=std::path::PathBuf::from(std::env::args_os().nth(1).expect("exact public file"));
 assert!(path.file_name().unwrap().to_string_lossy().starts_with("Windows067-public-"));path
}
fn prepared_payload()->Result<DataPackage,String>{
 let path=public_path();let title="公开虚构Windows内容验收 · 非真实会议".to_string();
 if std::env::args().any(|a|a=="--baseline") {baseline_handoff::prepare_share(baseline_handoff::ShareFile{path,title})}
 else {let file=content_handoff::prepare_share(content_handoff::ShareFile{path,title})?;
  content_handoff::qa_package_for_probe(&file).map_err(|e|format!("Probe fill error {e:?}"))}
}
unsafe extern "system" fn wndproc(hwnd:HWND,msg:u32,wparam:WPARAM,lparam:LPARAM)->LRESULT{
 match msg{
  WM_COMMAND if wparam.0&0xffff==100 || wparam.0&0xffff==101=>{
   let path=public_path();let title="公开虚构Windows内容验收 · 非真实会议".to_string();
   let result=if wparam.0&0xffff==100 {
    baseline_handoff::prepare_share(baseline_handoff::ShareFile{path,title}).and_then(|p|baseline_handoff::open_share(hwnd.0 as usize,p))
   }else{
    content_handoff::prepare_share(content_handoff::ShareFile{path,title}).and_then(|p|content_handoff::open_share(hwnd.0 as usize,p))
   };
   println!("button={} result={:?}",wparam.0&0xffff,result);LRESULT(0)
  },
  WM_DESTROY=>{PostQuitMessage(0);LRESULT(0)},
  _=>DefWindowProcW(hwnd,msg,wparam,lparam)
 }
}
fn main(){
 if std::env::args().any(|a|a.starts_with("--ipc")) {
  if let Err(e)=main_ipc(){eprintln!("BACKGROUND_IPC_ERROR {e:?}");std::process::exit(1);}return;
 }
 if !std::env::args().any(|a|a=="--gui") {eprintln!("Explicit --ipc-send or --gui required");return;}
 unsafe{
  RoInitialize(RO_INIT_SINGLETHREADED).unwrap();
  let class=w!("CompanionShareDualProbe069");assert!(RegisterClassW(&WNDCLASSW{lpfnWndProc:Some(wndproc),lpszClassName:class,..Default::default()})!=0);
  let hwnd=CreateWindowExW(WINDOW_EX_STYLE(0),class,w!("Companion 本机分享对照 · 仅公开资料"),WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,650,230,None,None,None,None).unwrap();
  CreateWindowExW(WINDOW_EX_STYLE(0),w!("BUTTON"),w!("1. 原方式"),WS_CHILD|WS_VISIBLE,30,30,250,50,hwnd,HMENU(100 as *mut _),None,None).unwrap();
  CreateWindowExW(WINDOW_EX_STYLE(0),w!("BUTTON"),w!("2. 修复候选"),WS_CHILD|WS_VISIBLE,320,30,250,50,hwnd,HMENU(101 as *mut _),None,None).unwrap();
  let _=ShowWindow(hwnd,SW_SHOWMINNOACTIVE);
  let mut msg=MSG::default();while GetMessageW(&mut msg,None,0,0).as_bool(){let _=TranslateMessage(&msg);DispatchMessageW(&msg);}
 }
}

use windows::{core::IUnknown,ApplicationModel::DataTransfer::DataPackageView,Storage::{StorageFile,FileIO,Streams::DataReader},Win32::System::Com::{Marshal::{CoMarshalInterface,CoUnmarshalInterface},StructuredStorage::CreateStreamOnHGlobal,STATSTG,STATFLAG_NONAME,STREAM_SEEK_SET}};
pub fn main_ipc() -> Result<(),Box<dyn std::error::Error>> {
    let args:Vec<String>=std::env::args().collect();
    if args.iter().any(|a|a=="--ipc-receive") {
        unsafe { RoInitialize(windows::Win32::System::WinRT::RO_INIT_MULTITHREADED)?; }
        let blob=std::path::PathBuf::from(&args[1]);
        assert!(blob.file_name().unwrap().to_string_lossy().starts_with("ipc-public-"));
        let bytes=std::fs::read(&blob)?;
        unsafe {
            let stream=CreateStreamOnHGlobal(None,true)?;
            stream.Write(bytes.as_ptr().cast(),bytes.len() as u32,None).ok()?;
            stream.Seek(0,STREAM_SEEK_SET,None)?;
            let view:DataPackageView=CoUnmarshalInterface(&stream)?;
            assert_eq!(view.Properties()?.Title()?.to_string(),"公开虚构Windows内容验收 · 非真实会议");
            if args.iter().any(|a|a=="--expect-source-context") {
                assert_eq!(view.Properties()?.ApplicationName()?.to_string(),"Windows source context");
            }
            let files=view.GetStorageItemsAsync()?.get()?;assert_eq!(files.Size()?,1);
            let file=files.GetAt(0)?.cast::<StorageFile>()?;
            assert!(std::path::Path::new(&file.Path()?.to_string()).file_name().unwrap().to_string_lossy().starts_with("Windows067-public-"));
            let data=FileIO::ReadBufferAsync(&file)?.get()?;
            let mut actual=vec![0u8;data.Length()? as usize];assert!(actual.len()<1024*1024);
            DataReader::FromBuffer(&data)?.ReadBytes(&mut actual)?;
            let expected=std::fs::read(file.Path()?.to_string())?;assert_eq!(actual,expected);
            println!("INDEPENDENT_RECEIVER_EXACT_BYTES_MATCHED bytes={}",actual.len());
        }
        return Ok(());
    }
    unsafe { RoInitialize(RO_INIT_SINGLETHREADED)?; }
    let public=std::path::PathBuf::from(&args[1]);
    assert!(public.file_name().unwrap().to_string_lossy().starts_with("Windows067-public-"));
    let prepared=prepared_payload()?;
    let view=prepared.GetView()?;
    unsafe {
        let stream=CreateStreamOnHGlobal(None,true)?;
        CoMarshalInterface(&stream,&DataPackageView::IID,&view.cast::<IUnknown>()?,0,None,0)?;
        let mut stat=STATSTG::default();stream.Stat(&mut stat,STATFLAG_NONAME)?;
        assert!(stat.cbSize<1024*1024);
        stream.Seek(0,STREAM_SEEK_SET,None)?;
        let mut bytes=vec![0u8;stat.cbSize as usize];let mut read=0;
        stream.Read(bytes.as_mut_ptr().cast(),bytes.len() as u32,Some(&mut read)).ok()?;assert_eq!(read as usize,bytes.len());
        let blob=std::path::Path::new("E:/CodexData/Companion/.build-cache/windows-share068").join(format!("ipc-public-{}.bin",uuid::Uuid::new_v4()));
        std::fs::write(&blob,bytes)?;
        let mut command=std::process::Command::new(std::env::current_exe()?);
        command.arg(&blob).arg("--ipc-receive");
        if args.iter().any(|a|a=="--expect-source-context"){command.arg("--expect-source-context");}
        let mut child=command.stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::piped()).spawn()?;
        let deadline=std::time::Instant::now()+std::time::Duration::from_secs(20);
        while child.try_wait()?.is_none() {
            let mut msg=MSG::default();while PeekMessageW(&mut msg,None,0,0,PM_REMOVE).as_bool(){let _=TranslateMessage(&msg);DispatchMessageW(&msg);}
            if std::time::Instant::now()>deadline { child.kill()?;return Err("Own IPC receiver timed out".into()); }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        let output=child.wait_with_output()?;println!("receiver stdout: {}",String::from_utf8_lossy(&output.stdout));println!("receiver stderr: {}",String::from_utf8_lossy(&output.stderr));
        assert!(output.status.success(),"Independent receiver failed: {:?}",output.status);
        println!("BACKGROUND_PRODUCT_SHARE_PACKAGE_IPC_PASSED");
    }
    Ok(())
}
