//! One opt-in pointer session, sharing the recorder's encrypted native link.
use companion_desktop_input::pointer::{native::Cursor,Metrics,Pointer,Settings};
use crate::coordinator::CompanionCoordinator;
use serde::Serialize;
use std::sync::{Arc,Mutex,LazyLock,atomic::{AtomicBool,Ordering}};
use std::time::{Instant,Duration};

#[derive(Clone,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Status {pub enabled:bool,pub ready:bool,pub controls_cursor:bool,pub message:String,pub metrics:Metrics,pub settings:Settings,pub device_id:Option<String>,pub contacts:companion_desktop_input::pointer::contact::Status}
static STATUS:LazyLock<Mutex<Status>>=LazyLock::new(||Mutex::new(Status::default()));
struct Session {stop:Arc<AtomicBool>,pointer:Arc<Mutex<Pointer>>,recenter:Arc<AtomicBool>,user_paused:Arc<AtomicBool>}
static SESSION:LazyLock<Mutex<Option<Session>>>=LazyLock::new(||Mutex::new(None));
fn change(f:impl FnOnce(&mut Status)){f(&mut STATUS.lock().unwrap_or_else(|e|e.into_inner()));}
pub fn status()->Status{STATUS.lock().unwrap_or_else(|e|e.into_inner()).clone()}
pub fn request_stop(){if let Some(s)=SESSION.lock().unwrap_or_else(|e|e.into_inner()).as_ref(){s.stop.store(true,Ordering::Release);}}
pub fn start(coordinator:Arc<CompanionCoordinator>,mut settings:Settings,controls_cursor:bool)->Result<Status,String>{
    // Owner paused planar motion while the angular pointer is tuned. Old
    // persisted clients must not reactivate the mixed experimental mapper.
    if settings.desktop_motion {return Err("桌面平移已暂停，请使用转动／倾斜模式。".into());}
    settings.validate().map_err(str::to_string)?;
    let pointer_options=settings.pointer_options();
    let mut session=SESSION.lock().map_err(|_|"空中鼠标暂时不可用。")?;
    if session.is_some(){return Err("空中鼠标已经开启。".into());}
    let (device,peer,lease)=coordinator.begin_desktop_pointer()?;
    if settings.contact_device.as_deref()!=Some(device.as_str()){
        settings.contact_profile=None;settings.contact_device=None;
    }
    // Opening reads OS position only. No movement/click is emitted until the
    // explicit UI start and a completed stationary calibration.
    let cursor=Cursor::open()?;let position=cursor.position()?;drop(cursor);
    let pointer=Arc::new(Mutex::new(Pointer::new(settings.clone(),position)));
    let stop=Arc::new(AtomicBool::new(false));let recenter=Arc::new(AtomicBool::new(false));
    let user_paused=Arc::new(AtomicBool::new(false));
    *session=Some(Session{stop:stop.clone(),pointer:pointer.clone(),recenter:recenter.clone(),user_paused:user_paused.clone()});
    change(|s|{*s=Status{enabled:true,ready:false,controls_cursor,message:"正在连接动作通道…".into(),metrics:Metrics::default(),settings,device_id:Some(device.clone()),contacts:Default::default()};});
    let spawn=std::thread::Builder::new().name("companion-pointer".into()).spawn(move||{
        let _lease=lease;let origin=Instant::now();let frame_stop=stop.clone();let frame_pointer=pointer.clone();
        let frames=std::thread::Builder::new().name("companion-pointer-frames".into()).spawn(move||->Result<(),String>{
            struct StopOnExit(Arc<AtomicBool>);
            impl Drop for StopOnExit{fn drop(&mut self){self.0.store(true,Ordering::Release);}}
            let _stop_on_exit=StopOnExit(frame_stop.clone());
            let mut cursor=Cursor::open()?;let mut update=Instant::now();let mut next=Instant::now();
            while !frame_stop.load(Ordering::Acquire) {
                if controls_cursor && Cursor::escape(){frame_stop.store(true,Ordering::Release);break;}
                // Win32 cursor/monitor reads may wait on the input desktop.
                // Do them before taking the core lock so the BLE receiver can
                // still deliver samples and button edges during that wait.
                let external=if controls_cursor{cursor.external_position()?}else{None};
                let center=if recenter.swap(false,Ordering::AcqRel){Some(cursor.position()?)}else{None};
                let bounds=cursor.bounds();
                let (frame,metrics,contacts,period)={let mut p=frame_pointer.lock().unwrap_or_else(|e|e.into_inner());
                    if let Some(position)=external{p.external_position(position);}
                    if let Some(position)=center{p.recenter(position);}
                    let frame=p.frame(origin.elapsed().as_secs_f64(),bounds);
                    (frame,p.metrics.clone(),p.contact_status(),if p.settings.mapping==companion_desktop_input::pointer::Mapping::Laser{4_166_667}else{8_333_333})};
                if controls_cursor {if let Err(e)=cursor.apply(frame){frame_stop.store(true,Ordering::Release);return Err(e);}}
                if update.elapsed()>=Duration::from_millis(200){
                    change(|s|{s.metrics=metrics.clone();s.contacts=contacts.clone();if s.ready {s.message=if metrics.stream_stale{"正在等待动作数据，光标已停止。"}
                        else if metrics.paused{"已暂停；换好握姿后，从当前位置继续。"}
                        else if metrics.regripping{"光标已稳住，可以轻敲点选或换握姿；松开按键继续。"}
                        else if !metrics.calibrated{if metrics.tap_events>0{"已收到轻敲；先稳住卡片约1秒，等就绪后再点选。"}else{"请把卡片放稳约1秒，正在校准…"}}
                        else if contacts.learning.is_some(){if contacts.learning==Some(companion_desktop_input::pointer::contact::Side::Left){"请在左侧自然轻敲三次；校准时不控制光标。"}else{"请在右侧自然轻敲三次；校准时不控制光标。"}}
                        else if controls_cursor&&s.settings.desktop_motion&&contacts.calibrated{"平移或转动控制方向；左侧轻敲左击，右侧轻敲右击；连续轻敲两次即双击。按住按键拖拽，Esc退出。"}
                        else if controls_cursor&&s.settings.desktop_motion{"平移或转动控制方向；轻敲或短按左击，按住拖拽。可校准左右轻敲。Esc退出。"}
                        else if controls_cursor&&s.settings.relative_direct&&s.settings.key_role==companion_desktop_input::pointer::KeyRole::Regrip{"倾斜移动，轻敲外壳点击；按住实体键可稳住点选或换握姿，松开继续。Esc退出。"}
                        else if controls_cursor&&s.settings.relative_direct{"倾斜移动，轻敲或短按实体键点击，按住拖拽。暂停可换握姿，Esc退出。"}
                        else if controls_cursor{"左右转动移动光标；敲击机身或短按点击，按住拖拽。Esc退出。"}
                        else{"动作预览中，未控制光标。"}.into();}});update=Instant::now();
                }
                next+=Duration::from_nanos(period);
                if let Some(wait)=next.checked_duration_since(Instant::now()){std::thread::sleep(wait);}else{next=Instant::now();}
            }
            cursor.release()
        });
        let result=if frames.is_ok(){
            let p=pointer.clone();let event_stop=stop.clone();let failure=Arc::new(Mutex::new(None));let event_failure=failure.clone();
            let result=super::ble_bridge::listen_pointer_input(&device,peer,stop.clone(),Arc::new(tokio::sync::Mutex::new(())),3,pointer_options,move|event|{
                use super::ble_bridge::DesktopInputUpdate;
                match event {
                    DesktopInputUpdate::Motion(sample)=>{
                        // Mapping needs monitor geometry; Win32 read only.
                        let b=desktop_bounds();p.lock().unwrap_or_else(|e|e.into_inner()).sample(sample,origin.elapsed().as_secs_f64(),b);
                    },
                    DesktopInputUpdate::RawMotion(sample)=>{p.lock().unwrap_or_else(|e|e.into_inner()).sample_raw(sample,origin.elapsed().as_secs_f64());},
                    DesktopInputUpdate::Ready(_)=>{let mut p=p.lock().unwrap_or_else(|e|e.into_inner());p.begin_stream();p.pause(user_paused.load(Ordering::Acquire));change(|s|{s.ready=true;});},
                    DesktopInputUpdate::Physical(s) if s.mode==3&&s.options&8!=0=>{
                        if let Err(message)=p.lock().unwrap_or_else(|e|e.into_inner()).control(companion_desktop_input::pointer::Control{sequence:s.sequence,sensor_ms:s.event_ms,events:s.events}){
                            *event_failure.lock().unwrap_or_else(|e|e.into_inner())=Some(message.to_string());event_stop.store(true,Ordering::Release);
                        }
                    },
                    DesktopInputUpdate::Reconnecting(message)=>{p.lock().unwrap_or_else(|e|e.into_inner()).pause(true);change(|s|{s.ready=false;s.message=message;});},
                    _=>{},
                }
            });
            let message=failure.lock().unwrap_or_else(|e|e.into_inner()).take();
            match message{Some(message)=>Err(message),None=>result}
        }else {Err("光标任务未能启动。".into())};
        stop.store(true,Ordering::Release);
        let frame_result=frames.map_err(|_|"光标任务未能启动。".to_string()).and_then(|h|h.join().map_err(|_|"光标任务已中断。".to_string()).and_then(|r|r));
        change(|s|{s.enabled=false;s.ready=false;s.metrics.dragging=false;s.message=match result.and(frame_result){Ok(())=>"已退出空中鼠标，恢复录音模式。".into(),Err(e)=>e};});
        *SESSION.lock().unwrap_or_else(|e|e.into_inner())=None;
    });
    if let Err(e)=spawn {*session=None;change(|s|{s.enabled=false;s.message="空中鼠标未启动。".into();});return Err(e.to_string());}
    drop(session);Ok(status())
}
#[cfg(windows)]
fn desktop_bounds()->companion_desktop_input::pointer::Bounds {
    use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics,SM_XVIRTUALSCREEN,SM_YVIRTUALSCREEN,SM_CXVIRTUALSCREEN,SM_CYVIRTUALSCREEN};
    unsafe {companion_desktop_input::pointer::Bounds{left:GetSystemMetrics(SM_XVIRTUALSCREEN) as f64,top:GetSystemMetrics(SM_YVIRTUALSCREEN) as f64,width:GetSystemMetrics(SM_CXVIRTUALSCREEN).max(1) as f64,height:GetSystemMetrics(SM_CYVIRTUALSCREEN).max(1) as f64,primary:Some([0.,0.,GetSystemMetrics(windows::Win32::UI::WindowsAndMessaging::SM_CXSCREEN).max(1) as f64,GetSystemMetrics(windows::Win32::UI::WindowsAndMessaging::SM_CYSCREEN).max(1) as f64])}}
}
#[cfg(not(windows))]
fn desktop_bounds()->companion_desktop_input::pointer::Bounds {companion_desktop_input::pointer::Bounds{left:0.,top:0.,width:1.,height:1.,primary:None}}
pub fn control(action:&str)->Result<Status,String>{
    let session=SESSION.lock().map_err(|_|"空中鼠标暂时不可用。")?;
    let s=session.as_ref().ok_or("空中鼠标尚未开启。")?;
    match action {
        "stop"=>{s.stop.store(true,Ordering::Release);change(|s|s.message="正在恢复录音模式…".into());},
        "pause"=>{s.user_paused.store(true,Ordering::Release);s.pointer.lock().unwrap_or_else(|e|e.into_inner()).pause(true);},
        "resume"=>{s.user_paused.store(false,Ordering::Release);s.pointer.lock().unwrap_or_else(|e|e.into_inner()).pause(false);},
        "calibrate"=>s.pointer.lock().unwrap_or_else(|e|e.into_inner()).calibrate(),
        "recenter"=>{s.recenter.store(true,Ordering::Release);},
        "contact-left"=>{s.pointer.lock().unwrap_or_else(|e|e.into_inner()).learn_contact(companion_desktop_input::pointer::contact::Side::Left).map_err(str::to_string)?;},
        "contact-right"=>{s.pointer.lock().unwrap_or_else(|e|e.into_inner()).learn_contact(companion_desktop_input::pointer::contact::Side::Right).map_err(str::to_string)?;},
        "contact-save"=>{
            let mut p=s.pointer.lock().unwrap_or_else(|e|e.into_inner());p.finish_contacts().map_err(str::to_string)?;
            p.settings.contact_device=status().device_id;let settings=p.settings.clone();drop(p);change(|s|s.settings=settings);
        },
        "contact-cancel"=>{s.pointer.lock().unwrap_or_else(|e|e.into_inner()).cancel_contacts();},
        "contact-clear"=>{
            let mut p=s.pointer.lock().unwrap_or_else(|e|e.into_inner());p.clear_contacts();let settings=p.settings.clone();drop(p);change(|s|s.settings=settings);
        },
        _=>return Err("未知空中鼠标操作。".into())
    }
    let contacts=s.pointer.lock().unwrap_or_else(|e|e.into_inner()).contact_status();change(|s|s.contacts=contacts);
    Ok(status())
}
