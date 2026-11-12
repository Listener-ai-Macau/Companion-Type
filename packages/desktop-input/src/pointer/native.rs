//! OS glue only. Mapping/filtering live in the portable upstream ports.
use super::{Bounds,Button,Frame,Point};
#[cfg(windows)]
use enigo::{Enigo,Settings,Mouse,Coordinate,Direction};
#[cfg(windows)]
pub struct Cursor {input:Enigo,down:bool}
#[cfg(windows)]
impl Cursor {
    pub fn open()->Result<Self,String> {Ok(Self{input:Enigo::new(&Settings::default()).map_err(|e|e.to_string())?,down:false})}
    pub fn position(&self)->Result<Point,String>{let(x,y)=self.input.location().map_err(|e|e.to_string())?;Ok(Point{x:x as f64,y:y as f64})}
    pub fn bounds(&self)->Bounds {
        use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics,SM_XVIRTUALSCREEN,SM_YVIRTUALSCREEN,SM_CXVIRTUALSCREEN,SM_CYVIRTUALSCREEN};
        unsafe {Bounds{left:GetSystemMetrics(SM_XVIRTUALSCREEN) as f64,top:GetSystemMetrics(SM_YVIRTUALSCREEN) as f64,
            width:GetSystemMetrics(SM_CXVIRTUALSCREEN).max(1) as f64,height:GetSystemMetrics(SM_CYVIRTUALSCREEN).max(1) as f64,primary:Some([0.,0.,GetSystemMetrics(windows::Win32::UI::WindowsAndMessaging::SM_CXSCREEN).max(1) as f64,GetSystemMetrics(windows::Win32::UI::WindowsAndMessaging::SM_CYSCREEN).max(1) as f64])}}
    }
    pub fn escape()->bool {unsafe {windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState(0x1b)<0}}
    fn move_to(&mut self,p:Point)->Result<(),String>{self.input.move_mouse(p.x.round() as i32,p.y.round() as i32,Coordinate::Abs).map_err(|e|e.to_string())}
    pub fn apply(&mut self,f:Frame)->Result<(),String> {
        // Rewind to pre-press point for click/down, then continue dragging.
        for event in f.buttons {
            match event {
                Button::Click(p)=>{self.move_to(p)?;self.input.button(enigo::Button::Left,Direction::Press).map_err(|e|e.to_string())?;self.down=true;self.release()?;},
                Button::Down(p)=>{self.move_to(p)?;self.input.button(enigo::Button::Left,Direction::Press).map_err(|e|e.to_string())?;self.down=true;},
                Button::Up=>self.release()?,
            }
        }
        if let Some(p)=f.position {self.move_to(p)?;}Ok(())
    }
    pub fn release(&mut self)->Result<(),String> {if self.down {self.input.button(enigo::Button::Left,Direction::Release).map_err(|e|e.to_string())?;self.down=false;}Ok(())}
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
    pub fn apply(&mut self,_:Frame)->Result<(),String>{Err("Unsupported platform".into())}
    pub fn release(&mut self)->Result<(),String>{Ok(())}
}
