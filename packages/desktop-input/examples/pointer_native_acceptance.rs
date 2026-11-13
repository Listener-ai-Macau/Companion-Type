//! Actual OS-input acceptance on an owned disposable GitHub Windows runner.
//! Never move the Owner desktop. No BLE, microphone or application data.
#[cfg(not(windows))]
fn main(){panic!("Windows only");}
#[cfg(windows)]
fn main(){
    let allowed=std::env::var("GITHUB_ACTIONS").as_deref()==Ok("true")
        &&std::env::var("RUNNER_ENVIRONMENT").as_deref()==Ok("github-hosted");
    if !allowed{eprintln!("OS-input test runs only on a disposable GitHub-hosted runner");std::process::exit(2);}
    let result=run();
    let value=match &result{Ok(v)=>v.clone(),Err(e)=>serde_json::json!({"state":"NATIVE_POINTER_OS_FAILED","error":e,"boardAccessed":false})};
    let out=std::env::args().nth(1).unwrap_or_else(||"pointer-native-result.json".into());
    std::fs::write(out,serde_json::to_string_pretty(&value).unwrap()).unwrap();
    println!("{value}");if result.is_err(){std::process::exit(1);}
}
#[cfg(windows)]
fn run()->Result<serde_json::Value,String>{
    use companion_desktop_input::pointer::{native::Cursor,Button,Frame,Point};
    use windows::{core::w,Win32::{Foundation::HWND,UI::WindowsAndMessaging::*}};
    use std::time::{Duration,Instant};
    struct Window(HWND);impl Drop for Window{fn drop(&mut self){unsafe{let _=DestroyWindow(self.0);}}}
    #[derive(Default)]struct Events{left_down:u32,left_up:u32,right_down:u32,right_up:u32}
    fn pump(e:&mut Events){unsafe{
        let mut m=MSG::default();
        while PeekMessageW(&mut m,None,0,0,PM_REMOVE).as_bool(){
            match m.message{WM_LBUTTONDOWN|WM_LBUTTONDBLCLK=>e.left_down+=1,WM_LBUTTONUP=>e.left_up+=1,
                WM_RBUTTONDOWN|WM_RBUTTONDBLCLK=>e.right_down+=1,WM_RBUTTONUP=>e.right_up+=1,_=>{}}
            let _=TranslateMessage(&m);DispatchMessageW(&m);
        }
    }}
    fn settle(cursor:&Cursor,p:Point,e:&mut Events)->Result<f64,String>{
        let start=Instant::now();loop{
            pump(e);let actual=cursor.position()?;if (actual.x-p.x).hypot(actual.y-p.y)<=1.5{return Ok(start.elapsed().as_secs_f64()*1000.);}
            if start.elapsed()>Duration::from_secs(1){return Err(format!("OS cursor did not reach {p:?}: {:?}",cursor.position()?));}
            std::thread::sleep(Duration::from_millis(1));
        }
    }
    let window=Window(unsafe{CreateWindowExW(Default::default(),w!("STATIC"),w!("Companion native pointer acceptance"),WS_OVERLAPPEDWINDOW|WS_VISIBLE,
        50,50,700,550,None,None,None,None)}.map_err(|e|e.to_string())?);
    unsafe{let _=ShowWindow(window.0,SW_SHOW);if !SetForegroundWindow(window.0).as_bool(){return Err("Owned native fixture did not get foreground".into());}}
    let mut cursor=Cursor::open()?;let mut events=Events::default();let initial=cursor.position()?;
    cursor.external_position()?;let mut latencies=vec![];
    for i in 0..40{
        let point=Point{x:200.+(i%5)as f64*70.,y:200.+(i%3)as f64*60.};
        cursor.apply(Frame{position:Some(point),..Frame::default()})?;
        latencies.push(settle(&cursor,point,&mut events)?);
        if cursor.external_position()?.is_some(){return Err("Own native move was mistaken for the ordinary mouse after OS settled".into());}
    }
    let mut false_external=0;
    for i in 0..40{
        let point=Point{x:if i%2==0{250.}else{500.},y:300.};
        cursor.apply(Frame{position:Some(point),..Frame::default()})?;
        std::thread::sleep(Duration::from_nanos(4_166_667));
        if cursor.external_position()?.is_some(){false_external+=1;}
        settle(&cursor,point,&mut events)?;
    }
    if false_external!=0{return Err(format!("Own 240Hz output mistaken for external mouse {false_external}/40 times"));}
    let outside=Point{x:420.,y:380.};unsafe{SetCursorPos(outside.x as i32,outside.y as i32).map_err(|e|e.to_string())?;}
    if cursor.external_position()?.is_none(){return Err("Genuine OS cursor change was not detected".into());}
    if cursor.external_position()?.is_some(){return Err("Same ordinary-mouse position was detected repeatedly".into());}
    let click=Point{x:350.,y:280.};cursor.apply(Frame{buttons:vec![Button::Click(click)],..Frame::default()})?;
    settle(&cursor,click,&mut events)?;std::thread::sleep(Duration::from_millis(50));pump(&mut events);
    if events.left_down!=1||events.left_up!=1{return Err(format!("Single click not delivered exactly once: {}/{}",events.left_down,events.left_up));}
    cursor.apply(Frame{buttons:vec![Button::Click(click),Button::Click(click)],..Frame::default()})?;
    std::thread::sleep(Duration::from_millis(50));pump(&mut events);
    if events.left_down!=3||events.left_up!=3{return Err("Two click requests did not become two clicks".into());}
    cursor.apply(Frame{buttons:vec![Button::Down(click)],..Frame::default()})?;
    std::thread::sleep(Duration::from_millis(30));pump(&mut events);
    if unsafe{windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState(1)}>=0{return Err("Drag press not held".into());}
    cursor.apply(Frame{position:Some(Point{x:450.,y:330.}),..Frame::default()})?;
    cursor.apply(Frame{buttons:vec![Button::Up],..Frame::default()})?;
    std::thread::sleep(Duration::from_millis(40));pump(&mut events);
    if unsafe{windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState(1)}<0{return Err("Drag release left button held".into());}
    cursor.apply(Frame{buttons:vec![Button::RightClick(click)],..Frame::default()})?;
    std::thread::sleep(Duration::from_millis(50));pump(&mut events);
    if events.right_down!=1||events.right_up!=1{return Err("Right-click OS delivery failed".into());}
    cursor.apply(Frame{buttons:vec![Button::Down(click)],..Frame::default()})?;drop(cursor);
    std::thread::sleep(Duration::from_millis(50));pump(&mut events);
    if unsafe{windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState(1)}<0{return Err("Cursor shutdown left button held".into());}
    unsafe{SetCursorPos(initial.x as i32,initial.y as i32).map_err(|e|e.to_string())?;}
    latencies.sort_by(f64::total_cmp);
    Ok(serde_json::json!({"state":"ACTUAL_WINDOWS_POINTER_MOVE_CLICKS_DRAG_COEXISTENCE_AND_RELEASE_PASSED",
        "ordinaryOsMovementDetectedOnce":true,"ownOutputFalseExternal":false_external,
        "leftDown":events.left_down,"leftUp":events.left_up,"rightDown":events.right_down,"rightUp":events.right_up,
        "osSubmissionToObservedPositionP95Ms":latencies[latencies.len()*95/100],"osSubmissionToObservedPositionMaxMs":latencies.last(),
        "timingScope":"OS submission to GetCursorPos observation only; not device/BLE or human latency",
        "physicalMultipleMonitorLayoutsTested":false,"physicalMouseOrBoardTested":false,
        "actualWindowsInput":true,"boardAccessed":false,"microphone":false,"ownerDesktopTouched":false}))
}
