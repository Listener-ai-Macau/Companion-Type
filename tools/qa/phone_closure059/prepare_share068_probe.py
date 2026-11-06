from pathlib import Path
import json,subprocess,tomllib,time,os,shutil,psutil
R=Path('C:/Users/Billy/Desktop/Denzic/Companion');S=R/'companion-device-closure055';W=Path(__file__).parent
C=Path('E:/CodexData/Companion/.build-cache/windows-share068/native-probe');C.mkdir(exist_ok=True);(C/'src').mkdir(exist_ok=True)
product=tomllib.loads((S/'apps/windows/src-tauri/Cargo.toml').read_text(encoding='utf8'));dep=product['target']['cfg(windows)']['dependencies']['windows'];features=dep['features']+['Win32_Graphics_Gdi','Win32_System_Com_Marshal','Win32_System_Com_StructuredStorage']
(C/'Cargo.toml').write_text('[package]\nname="companion-share068-probe"\nversion="0.1.0"\nedition="2021"\n[dependencies]\nwindows={version="0.58",features='+json.dumps(features)+'}\nuuid={version="1",features=["v4"]}\n',encoding='utf8')
source=(S/'apps/windows/src-tauri/src/content_handoff.rs').read_text(encoding='utf8')
needle='args.Request()?.SetData(&package)'
assert source.count(needle)==1
source=source.replace(needle,'''if std::env::var_os("COMPANION_QA_POPULATE_REQUEST").is_some(){
                    let target=args.Request()?.Data()?;let view=package.GetView()?;
                    target.Properties()?.SetTitle(&view.Properties()?.Title()?)?;
                    target.SetRequestedOperation(view.RequestedOperation()?)?;
                    let items:IIterable<IStorageItem>=view.GetStorageItemsAsync()?.get()?.cast()?;
                    target.SetStorageItems(&items,true)
                }else{args.Request()?.SetData(&package)}''')
(C/'src/content_handoff.rs').write_text(source,encoding='utf8')
main=r'''
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
    println!("advertised file types {}",view.Properties()?.FileTypes()?.Size()?);
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
 if std::env::args().any(|a|a.starts_with("--ipc")){match main_ipc(){Ok(())=>{},Err(e)=>{eprintln!("BACKGROUND_IPC_ERROR {e:?}");std::process::exit(1);}}return;}
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
'''
main+='\n'+(W/'windows_shareqa068/ipc_probe.rs').read_text(encoding='utf8')
(C/'src/main.rs').write_text(main,encoding='utf8')
env={**os.environ,'CARGO_TARGET_DIR':str(Path('E:/CodexData/Companion/.build-cache/windows051/target')),'CARGO_BUILD_JOBS':'1','RAYON_NUM_THREADS':'2'}
args=[str(Path('C:/Users/Billy/.cargo/bin/cargo.exe')),'build','--offline','--manifest-path',str(C/'Cargo.toml')]
psutil.Process().cpu_affinity([12,13,14,15])
run=subprocess.run(args,env=env,cwd=C,capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
O=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows-share068'
if (O/'probe-build.log').exists():shutil.copy2(O/'probe-build.log',O/('probe-build-prior-'+str(time.time_ns())+'.log'))
(O/'probe-build.log').write_text(run.stdout+run.stderr,encoding='utf8');assert run.returncode==0,(run.stdout+run.stderr)[-5000:]
exe=Path(env['CARGO_TARGET_DIR'])/'debug/companion-share068-probe.exe'
public=R/'docs/handoffs/20261106-device-phone-closure055/phone-followup/unified058/priority12/windows067-literal-and-rendering/system-handoff/saved/Windows067-public-transcript.pdf'
run=subprocess.run([str(exe),str(public)],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
(O/'probe-result.log').write_text(run.stdout+run.stderr,encoding='utf8');print(run.stdout+run.stderr);assert run.returncode==0,run.returncode
run=subprocess.run([str(exe),str(public),'--ipc-send'],capture_output=True,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS,timeout=30)
(O/('ipc-result-'+str(time.time_ns())+'.log')).write_text(run.stdout+run.stderr,encoding='utf8');print(run.stdout+run.stderr);assert run.returncode==0,run.returncode
