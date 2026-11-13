//! OS glue only. Mapping/filtering live in the portable upstream ports.
use super::{Bounds,Button,Frame,Point};
#[cfg(windows)]
use enigo::{Enigo,Settings,Mouse,Direction};
#[cfg(windows)]
fn absolute_move(p:Point,b:Bounds)->(Point,windows::Win32::UI::Input::KeyboardAndMouse::INPUT){
    use windows::Win32::UI::Input::KeyboardAndMouse::{INPUT,INPUT_0,INPUT_MOUSE,MOUSEINPUT,MOUSEEVENTF_MOVE,MOUSEEVENTF_ABSOLUTE,MOUSEEVENTF_VIRTUALDESK};
    let p=b.clamp(Point{x:p.x.round(),y:p.y.round()});
    // Win32 absolute input without VIRTUALDESK addresses the primary monitor.
    // The pointer/history use the virtual desktop, including negative origins.
    // Normalize that SAME rectangle for movement, clicks and drag starts.
    let axis=|value:f64,origin:f64,extent:f64|((value-origin)*65535./(extent-1.).max(1.)).round().clamp(0.,65535.)as i32;
    (p,INPUT{r#type:INPUT_MOUSE,Anonymous:INPUT_0{mi:MOUSEINPUT{
        dx:axis(p.x,b.left,b.width),dy:axis(p.y,b.top,b.height),mouseData:0,
        dwFlags:MOUSEEVENTF_MOVE|MOUSEEVENTF_ABSOLUTE|MOUSEEVENTF_VIRTUALDESK,
        time:0,dwExtraInfo:enigo::EVENT_MARKER as usize,
    }}})
}
#[cfg(windows)]
pub struct Cursor {input:Enigo,down:bool,expected:Option<Point>}
#[cfg(windows)]
impl Cursor {
    pub fn open()->Result<Self,String> {Ok(Self{input:Enigo::new(&Settings::default()).map_err(|e|e.to_string())?,down:false,expected:None})}
    pub fn position(&self)->Result<Point,String>{let(x,y)=self.input.location().map_err(|e|e.to_string())?;Ok(Point{x:x as f64,y:y as f64})}
    pub fn bounds(&self)->Bounds {
        use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics,SM_XVIRTUALSCREEN,SM_YVIRTUALSCREEN,SM_CXVIRTUALSCREEN,SM_CYVIRTUALSCREEN};
        unsafe {Bounds{left:GetSystemMetrics(SM_XVIRTUALSCREEN) as f64,top:GetSystemMetrics(SM_YVIRTUALSCREEN) as f64,
            width:GetSystemMetrics(SM_CXVIRTUALSCREEN).max(1) as f64,height:GetSystemMetrics(SM_CYVIRTUALSCREEN).max(1) as f64,primary:Some([0.,0.,GetSystemMetrics(windows::Win32::UI::WindowsAndMessaging::SM_CXSCREEN).max(1) as f64,GetSystemMetrics(windows::Win32::UI::WindowsAndMessaging::SM_CYSCREEN).max(1) as f64])}}
    }
    pub fn escape()->bool {unsafe {windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState(0x1b)<0}}
    pub fn external_position(&mut self)->Result<Option<Point>,String>{
        let p=self.position()?;
        if let Some(expected)=self.expected {
            // SendInput's normalized coordinates may round one pixel. Keep
            // the same expected position until a real accumulated move.
            if p.distance(expected)>1.5{self.expected=Some(p);return Ok(Some(p));}
        }else{self.expected=Some(p);}
        Ok(None)
    }
    fn move_to(&mut self,p:Point)->Result<(),String>{
        use windows::Win32::UI::Input::KeyboardAndMouse::{SendInput,INPUT};
        let(p,event)=absolute_move(p,self.bounds());
        if unsafe{SendInput(&[event],std::mem::size_of::<INPUT>()as i32)}!=1{
            return Err(format!("系统未接收鼠标移动：{}",windows::core::Error::from_win32()));
        }
        self.expected=Some(p);Ok(())
    }
    pub fn apply(&mut self,f:Frame)->Result<(),String> {
        // Rewind to pre-press point for click/down, then continue dragging.
        for event in f.buttons {
            match event {
                Button::Click(p)=>{self.move_to(p)?;self.input.button(enigo::Button::Left,Direction::Press).map_err(|e|e.to_string())?;self.down=true;self.release()?;},
                Button::RightClick(p)=>{self.move_to(p)?;self.input.button(enigo::Button::Right,Direction::Click).map_err(|e|e.to_string())?;},
                Button::Down(p)=>{self.move_to(p)?;self.input.button(enigo::Button::Left,Direction::Press).map_err(|e|e.to_string())?;self.down=true;},
                Button::Up=>self.release()?,
            }
        }
        if let Some(p)=f.position {self.move_to(p)?;}Ok(())
    }
    pub fn release(&mut self)->Result<(),String> {if self.down {self.input.button(enigo::Button::Left,Direction::Release).map_err(|e|e.to_string())?;self.down=false;}Ok(())}
}

#[cfg(all(test,windows))]
mod tests {
    use super::*;
    use windows::Win32::UI::Input::KeyboardAndMouse::{INPUT_MOUSE,MOUSEEVENTF_ABSOLUTE,MOUSEEVENTF_MOVE,MOUSEEVENTF_VIRTUALDESK};
    fn event(p:Point,b:Bounds)->windows::Win32::UI::Input::KeyboardAndMouse::MOUSEINPUT{
        let(_,v)=absolute_move(p,b);assert_eq!(v.r#type,INPUT_MOUSE);
        let m=unsafe{v.Anonymous.mi};
        assert_eq!(m.dwFlags,MOUSEEVENTF_MOVE|MOUSEEVENTF_ABSOLUTE|MOUSEEVENTF_VIRTUALDESK);m
    }
    #[test]fn native_absolute_input_reaches_a_secondary_display_instead_of_the_primary_edge(){
        let b=Bounds{left:0.,top:0.,width:3840.,height:1080.,primary:Some([0.,0.,1920.,1080.])};
        let m=event(Point{x:2880.,y:540.},b);
        assert!((49000..49400).contains(&m.dx));assert!((32700..32900).contains(&m.dy));
    }
    #[test]fn native_absolute_input_handles_monitors_left_of_and_above_the_primary(){
        let b=Bounds{left:-1920.,top:-1080.,width:3840.,height:2160.,primary:Some([0.,0.,1920.,1080.])};
        let m=event(Point{x:-960.,y:-540.},b);
        assert!((16300..16500).contains(&m.dx));assert!((16300..16500).contains(&m.dy));
        let first=event(Point{x:-1920.,y:-1080.},b);assert_eq!((first.dx,first.dy),(0,0));
        let last=event(Point{x:1919.,y:1079.},b);assert_eq!((last.dx,last.dy),(65535,65535));
    }
    #[test]fn native_absolute_input_clamps_and_supports_single_pixel_extents(){
        let b=Bounds{left:-100.,top:300.,width:1.,height:1.,primary:None};
        let(p,_)=absolute_move(Point{x:9000.,y:-4000.},b);assert_eq!(p,Point{x:-100.,y:300.});
        let m=event(p,b);assert_eq!((m.dx,m.dy),(0,0));
    }
}
#[cfg(windows)]
impl Drop for Cursor {fn drop(&mut self){let _=self.release();}}

#[cfg(not(windows))]
pub struct Cursor;
#[cfg(not(windows))]
impl Cursor {
    pub fn open()->Result<Self,String>{Err("空中鼠标当前支持Windows客户端。".into())}
    pub fn position(&self)->Result<Point,String>{Err("Unsupported platform".into())}
    pub fn bounds(&self)->Bounds{Bounds{left:0.,top:0.,width:1.,height:1.,primary:None}}
    pub fn escape()->bool{false}
    pub fn external_position(&mut self)->Result<Option<Point>,String>{Ok(None)}
    pub fn apply(&mut self,_:Frame)->Result<(),String>{Err("Unsupported platform".into())}
    pub fn release(&mut self)->Result<(),String>{Ok(())}
}
