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
