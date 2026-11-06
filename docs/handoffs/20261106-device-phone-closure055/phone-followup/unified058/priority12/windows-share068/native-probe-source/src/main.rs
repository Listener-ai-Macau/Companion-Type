
mod backend {pub mod export {pub fn write_atomic(path:&std::path::Path, bytes:&[u8])->Result<(),String>{std::fs::write(path,bytes).map_err(|e|e.to_string())}}}
mod content_handoff;
use windows::{core::{Interface,IInspectable,HSTRING},Win32::System::WinRT::{RoInitialize,RoUninitialize,RO_INIT_SINGLETHREADED},ApplicationModel::DataTransfer::{DataPackage,StandardDataFormats}};
fn inspect(){
 unsafe{RoInitialize(RO_INIT_SINGLETHREADED).unwrap();}
 let path=std::path::PathBuf::from(std::env::args_os().nth(1).expect("exact public file"));
 assert!(path.file_name().unwrap().to_string_lossy().starts_with("Windows067-public-"));
 let result=content_handoff::prepare_share(content_handoff::ShareFile{path,title:"公开虚构Windows内容验收 · 非真实会议".into()});
 match result {
  Err(e)=>println!("prepare error {e}"),
  Ok(package)=>{
   let checked=(||->windows::core::Result<()>{
    let view=package.GetView()?;println!("title {:?}",view.Properties()?.Title()?);
    println!("storage-format {:?}",view.Contains(&StandardDataFormats::StorageItems()?)?);
    let files=view.GetStorageItemsAsync()?.get()?;println!("storage count {}",files.Size()?);
    println!("first file {:?}",files.GetAt(0)?.Path()?);Ok(())
   })();println!("post-worker STA package result {:?}",checked);
  }
 }
 unsafe{RoUninitialize();}
}
use windows::{core::w,Win32::{Foundation::{HWND,LRESULT,WPARAM,LPARAM,HINSTANCE},UI::WindowsAndMessaging::*}};
unsafe extern "system" fn wndproc(hwnd:HWND,msg:u32,wparam:WPARAM,lparam:LPARAM)->LRESULT{
 match msg {
  WM_COMMAND if wparam.0&0xffff==100=>{
   let path=std::path::PathBuf::from(std::env::args_os().nth(1).unwrap());
   let result=content_handoff::prepare_share(content_handoff::ShareFile{path,title:"公开虚构Windows内容验收 · 非真实会议".into()}).and_then(|data|content_handoff::open_share(hwnd.0 as usize,data));
   println!("ordinary probe button -> {:?}",result);LRESULT(0)
  },
  WM_DESTROY=>{PostQuitMessage(0);LRESULT(0)},
  _=>DefWindowProcW(hwnd,msg,wparam,lparam)
 }
}
fn main(){
 if !std::env::args().any(|a|a=="--gui"){inspect();return;}
 unsafe{
  RoInitialize(RO_INIT_SINGLETHREADED).unwrap();
  let class=w!("CompanionShareProbe068");
  let atom=RegisterClassW(&WNDCLASSW{lpfnWndProc:Some(wndproc),lpszClassName:class,..Default::default()});assert!(atom!=0);
  let hwnd=CreateWindowExW(WINDOW_EX_STYLE(0),class,w!("Companion 本机分享诊断 · 公开资料"),WS_OVERLAPPEDWINDOW,CW_USEDEFAULT,CW_USEDEFAULT,600,180,None,None,None,None).unwrap();
  CreateWindowExW(WINDOW_EX_STYLE(0),w!("BUTTON"),w!("分享公开测试文件"),WS_CHILD|WS_VISIBLE,30,35,300,45,hwnd,HMENU(100 as *mut _),None,None).unwrap();
  let _=ShowWindow(hwnd,SW_SHOW);
  let mut msg=MSG::default();while GetMessageW(&mut msg,None,0,0).as_bool(){let _=TranslateMessage(&msg);DispatchMessageW(&msg);}
  RoUninitialize();
 }
}
