//! Ports of AirCursor Pointer.swift and WatchPointer Receiver/WatchPointerApp.
//! See third_party/imu-pointer for the pinned originals and MIT notices.
//! Companion-specific parts: CIM1 decoding, upstream Fusion raw-sensor adapter,
//! stationary gyro bias, physical button/tap edges, and explicit pause/recenter.
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
pub mod native;
mod fusion;
mod rest;
mod relative;
pub mod desktop;
pub mod intent;
pub mod contact;
mod contact_dtw;
mod tap_motion;
pub mod surface;

#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize)]
pub struct Point { pub x: f64, pub y: f64 }
impl Point {
    fn distance(self, b: Self) -> f64 { (self.x-b.x).hypot(self.y-b.y) }
}
#[derive(Clone, Copy, Debug)]
pub struct Sample {
    pub sequence: u32, pub sensor_ms: u32, pub held: bool, pub tap_serial: u8, pub fused: bool, pub device_ready: Option<bool>,
    pub accel: [f64;3], pub gyro: [f64;3],
    /// CIM4: device heading, world-vertical yaw rate, device-X pitch rate.
    /// Heading is integrated BEFORE lossy delivery, as in WatchPointer.
    pub aim: Option<[f64;3]>,
}
impl Sample {
    pub fn parse(p: &[u8]) -> Result<Self, &'static str> {
        if p.len()<32 || &p[..4]!=b"CIM1" || !matches!(p[4],1|2|3|4|6) || p.len()!=if p[4]==6{40}else{32} || p[5]!=3 || p[6]&!(if p[4]>=3{3}else{1})!=0 || (p[4]==6&&p[34..36]!=[0,0]) {
            return Err("invalid CIM1 sample");
        }
        let mut crc=0xffff_ffffu32;
        let crc_at=p.len()-4;
        for byte in &p[..crc_at] { crc^=*byte as u32; for _ in 0..8 {crc=(crc>>1)^((0u32.wrapping_sub(crc&1))&0xedb8_8320);} }
        if !crc!=u32::from_le_bytes(p[crc_at..].try_into().unwrap()) {return Err("CIM1 CRC mismatch");}
        let mut s=Self {sequence:u32::from_le_bytes(p[8..12].try_into().unwrap()),
            sensor_ms:u32::from_le_bytes(p[12..16].try_into().unwrap()),held:p[6]&1!=0,tap_serial:p[7],fused:p[4]>=2,device_ready:if p[4]>=3{Some(p[6]&2!=0)}else{None},accel:[0.;3],gyro:[0.;3],aim:None};
        if p[4]==4 {
            let value=|at|i16::from_le_bytes(p[at..at+2].try_into().unwrap()) as f64/100.;
            s.aim=Some([value(16),value(24),value(26)]);
            for i in 0..3{s.accel[i]=i16::from_le_bytes(p[18+2*i..20+2*i].try_into().unwrap()) as f64*1000./16384.;}
            return Ok(s);
        }
        for i in 0..3 {s.accel[i]=i16::from_le_bytes(p[16+2*i..18+2*i].try_into().unwrap()) as f64;
            if p[4]==3||p[4]==6{s.accel[i]*=1000./16384.;}
            s.gyro[i]=i16::from_le_bytes(p[22+2*i..24+2*i].try_into().unwrap()) as f64/100.;}
        Ok(s)
    }
}
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq)]
#[serde(rename_all="camelCase")]
pub enum Mapping { #[default] Relative, Laser }
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq)]
#[serde(rename_all="camelCase")]
pub enum RelativeHorizontal { #[default] Turn, Tilt }
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq)]
#[serde(rename_all="camelCase")]
pub enum KeyRole { #[default] ClickDrag, Regrip }
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(default, rename_all="camelCase")]
pub struct Settings {
    pub mapping: Mapping, pub sensitivity: f64, pub smoothing: f64,
    pub deadzone: f64, pub acceleration: f64, pub invert_horizontal: bool, pub invert_vertical: bool,
    pub desktop_motion: bool,
    pub relative_direct:bool,pub tap_click:bool,
    pub relative_horizontal:RelativeHorizontal,
    pub key_role:KeyRole,
    pub contact_regions:bool,
    pub contact_profile:Option<contact::Profile>,
    pub contact_device:Option<String>,
}
impl Default for Settings {
    fn default()->Self {Self {mapping:Mapping::Laser,sensitivity:1.,smoothing:0.55,
            deadzone:3.,acceleration:0.6,invert_horizontal:false,invert_vertical:false,desktop_motion:false,relative_direct:false,tap_click:true,relative_horizontal:RelativeHorizontal::Turn,key_role:KeyRole::ClickDrag,contact_regions:false,contact_profile:None,contact_device:None}}
}
impl Settings {
    pub fn relative_remote()->Self{Self{mapping:Mapping::Relative,relative_direct:true,relative_horizontal:RelativeHorizontal::Tilt,tap_click:true,deadzone:0.,smoothing:0.,acceleration:0.,..Self::default()}}
    pub fn pointer_options(&self)->u8{if self.contact_regions{72}else if self.desktop_motion{24}else if self.relative_direct&&self.mapping==Mapping::Relative{40}else{8}}
    pub fn validate(&self)->Result<(), &'static str> {
        if self.desktop_motion&&self.mapping!=Mapping::Relative{return Err("desktop motion requires relative mapping");}
        if self.relative_direct&&self.mapping!=Mapping::Relative{return Err("direct relative input requires relative mapping");}
        if self.key_role==KeyRole::Regrip&&!self.relative_direct{return Err("按住换握姿需要相对遥控模式。");}
        if self.contact_regions&&!self.relative_direct{return Err("左右前角敲击需要相对鼠标模式。");}
        if let Some(profile)=&self.contact_profile{profile.validate()?;if !(self.desktop_motion||self.contact_regions){return Err("请启用左右前角敲击。");}}
        if !self.sensitivity.is_finite() || !(0.2..=3.).contains(&self.sensitivity) ||
           !self.smoothing.is_finite() || !(0.0..=0.97).contains(&self.smoothing) ||
           !self.deadzone.is_finite() || !(0.0..=5.).contains(&self.deadzone) ||
           !self.acceleration.is_finite() || !(0.0..=1.).contains(&self.acceleration) {return Err("invalid pointer settings");}
        Ok(())
    }
}

/// AirCursor's bounded angular-velocity mapping, with its original constants.
pub fn axis_speed(rate:f64,s:&Settings)->f64 {
    if rate.abs()<=s.deadzone {return 0.;}
    let effective=rate.abs()-s.deadzone;
    rate.signum()*effective*28.*s.sensitivity*(1.+s.acceleration*(effective/60.).min(3.))
}
#[derive(Default)]
pub struct Smoother { velocity:Point,target:Point,at:Option<f64> }
impl Smoother {
    pub fn target(&mut self,p:Point,at:f64) {self.target=p;self.at=Some(at);}
    pub fn reset(&mut self){*self=Self::default();}
    pub fn step(&mut self,now:f64,dt:f64,smoothing:f64)->Point {
        if dt<=0. {return Point::default();}
        let goal=if self.at.is_none_or(|at|now-at>0.12) {Point::default()}else{self.target};
        let alpha=1.-smoothing.clamp(0.,0.97).powf(dt*60.);
        self.velocity.x+=(goal.x-self.velocity.x)*alpha;self.velocity.y+=(goal.y-self.velocity.y)*alpha;
        if goal==Point::default() && self.velocity.x.hypot(self.velocity.y)<2. {self.velocity=Point::default();}
        Point{x:self.velocity.x*dt,y:self.velocity.y*dt}
    }
}
/// WatchPointer's adaptive 1-Euro filter, including its derivative convention.
#[derive(Default)]
pub struct OneEuro { value:Option<f64>, velocity:f64 }
impl OneEuro {
    pub fn update(&mut self,x:f64,dt:f64)->f64 {
        self.update_with(x,dt,0.8,0.01)
    }
    fn update_with(&mut self,x:f64,dt:f64,min_cutoff:f64,beta:f64)->f64 {
        let Some(previous)=self.value.filter(|_|dt>0.) else {self.value=Some(x);return x;};
        let alpha=|cutoff:f64|1./(1.+1./(2.*std::f64::consts::PI*cutoff*dt));
        self.velocity+=alpha(1.)*((x-previous)/dt-self.velocity);
        let smoothed=previous+alpha(min_cutoff+beta*self.velocity.abs())*(x-previous);
        self.value=Some(smoothed);smoothed
    }
}
pub fn laser(left:f64,up:f64,speed:f64,b:Bounds)->Point {
    let [left_edge,top,width,height]=b.primary.unwrap_or([b.left,b.top,b.width,b.height]);
    let h=(-left).clamp(-80.,80.).to_radians(); let v=up.clamp(-80.,80.).to_radians();
    let unit=width*0.5/(25./speed).to_radians().tan();
    Point{x:left_edge+width*0.5+h.tan()*unit,y:top+height*0.5-v.tan()/h.cos()*unit}
}
#[derive(Clone,Copy)]
pub struct Bounds {pub left:f64,pub top:f64,pub width:f64,pub height:f64,pub primary:Option<[f64;4]>}
impl Bounds {
    fn clamp(self,p:Point)->Point {Point{x:p.x.clamp(self.left,self.left+self.width-1.),y:p.y.clamp(self.top,self.top+self.height-1.)}}
}
#[derive(Clone,Copy,Debug,PartialEq)]
pub enum Button {Click(Point),RightClick(Point),Down(Point),Up}
#[derive(Clone,Copy,Debug,Deserialize)]
pub struct Control {pub sequence:u32,pub sensor_ms:u32,pub events:u16}
pub const CLICK:u16=512;pub const DOWN:u16=1024;pub const UP:u16=2048;pub const OVERFLOW:u16=4096;
#[derive(Default)]
pub struct Frame {pub position:Option<Point>,pub buttons:Vec<Button>}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Metrics {pub samples:u64,pub missing:u64,pub duplicates:u64,pub gaps:u64,pub tap_events:u64,pub sensor_hz:f64,pub receive_hz:f64,pub calibrated:bool,pub calibration_samples:u32,pub dragging:bool,pub paused:bool,pub regripping:bool,pub stream_stale:bool,pub surface_paused:bool}

pub struct Pointer {
    pub settings:Settings,pub metrics:Metrics, smoother:Smoother, filter_x:OneEuro,filter_y:OneEuro,
    relative:relative::Response,last_emitted:Point,
    last:Option<(u32,u32)>, last_tap:Option<u8>, arrival:Option<f64>, frame_at:Option<f64>,sensor_clock:f64,clock_offset:Option<f64>,
    bias:[f64;3],bias_sum:[f64;3],accel_sum:[f64;3],calibration_start:Option<u32>,
    fusion:fusion::Fusion,
    coarse:Option<intent::Intent>,
    desktop_device_ready:Option<bool>,first_arrival:Option<f64>,
    contacts:contact::Contact,
    tap_motion:tap_motion::TapMotion,
    heading:f64,heading_zero:Option<f64>,elevation_zero:Option<f64>,target:Option<Point>,shown:Point,
    laser_offset:Point,last_projected:Option<Point>,
    last_control:Option<u32>,
    pressed:Option<(f64,Point)>,wait_release:bool,queued:Vec<Button>,history:VecDeque<(f64,Point)>,
}
impl Pointer {
    pub fn new(settings:Settings,position:Point)->Self {
        let contacts=contact::Contact::new(settings.contact_profile.clone());
        Self {settings,metrics:Metrics::default(),smoother:Smoother::default(),filter_x:OneEuro::default(),filter_y:OneEuro::default(),
            relative:relative::Response::default(),last_emitted:position,
            last:None,last_tap:None,arrival:None,frame_at:None,sensor_clock:0.,clock_offset:None,bias:[0.;3],bias_sum:[0.;3],accel_sum:[0.;3],calibration_start:None,fusion:fusion::Fusion::default(),coarse:None,desktop_device_ready:None,first_arrival:None,contacts,tap_motion:tap_motion::TapMotion::default(),
            heading:0.,heading_zero:None,elevation_zero:None,target:None,shown:position,laser_offset:Point::default(),last_projected:None,last_control:None,pressed:None,wait_release:true,queued:vec![],history:VecDeque::with_capacity(360)}
    }
    fn release_button(&mut self) {if self.metrics.dragging {self.queued.push(Button::Up);}self.metrics.dragging=false;self.metrics.regripping=false;self.pressed=None;self.wait_release=true;}
    fn release(&mut self) {self.release_button();self.contacts.clear_stream();self.tap_motion.clear();}
    fn reset_motion(&mut self){self.smoother.reset();self.relative.reset();self.tap_motion.clear_rates();if let Some(c)=self.coarse.as_mut(){c.clear_motion();}self.filter_x=OneEuro::default();self.filter_y=OneEuro::default();self.target=None;self.history.clear();}
    fn drag_delay(&self)->f64{if self.settings.relative_direct{0.18}else{0.35}}
    fn press_point(&self,at:f64)->Point {self.history.iter().rev().find(|(t,_)|*t<=at).or(self.history.front()).map(|(_,p)|*p).unwrap_or(self.shown)}
    pub fn pause(&mut self,paused:bool) {self.release();self.reset_motion();self.contacts.cancel();self.metrics.paused=paused;}
    pub fn calibrate(&mut self) {self.release();self.reset_motion();self.contacts.cancel();self.coarse=None;self.desktop_device_ready=None;self.fusion=fusion::Fusion::default();self.metrics.calibrated=false;self.metrics.calibration_samples=0;self.calibration_start=None;self.bias_sum=[0.;3];self.accel_sum=[0.;3];self.heading=0.;self.heading_zero=None;self.elevation_zero=None;self.laser_offset=Point::default();self.last_projected=None;}
    /// A newly verified link may start a new device sequence/time domain.
    /// Keep its first levels as a baseline; fresh control edges still own input.
    pub fn begin_stream(&mut self){
        self.calibrate();self.last=None;self.last_tap=None;self.last_control=None;
        self.arrival=None;self.frame_at=None;self.clock_offset=None;self.sensor_clock=0.;
    }
    pub fn recenter(&mut self,position:Point) {self.release();self.reset_motion();self.shown=position;self.last_emitted=position;self.heading=0.;self.heading_zero=None;self.elevation_zero=None;self.laser_offset=Point::default();self.last_projected=None;}
    /// An ordinary mouse moved the real cursor since our last OS output.
    /// Re-anchor to that position, canceling the old follow residual. The next
    /// unchanged card pose must stay here; subsequent card motion adds to it.
    pub fn external_position(&mut self,position:Point) {
        self.shown=position;
        self.last_emitted=position;
        self.relative.reset();self.smoother.reset();
        self.tap_motion.clear_rates();
        self.contacts.reanchor(position);
        if self.settings.relative_direct{
            // A reliable click can be queued between two native frames. If
            // the ordinary mouse took over meanwhile, that click belongs at
            // the visible cursor, not at the old card-only position.
            for button in &mut self.queued{match button{
                Button::Click(point)|Button::RightClick(point)|Button::Down(point)=>*point=position,
                Button::Up=>{},
            }}
            if let Some((_,point))=self.pressed.as_mut(){*point=position;}
        }
        // A contact after using the ordinary mouse must not rewind into the
        // old card-only cursor history, even during the upstream tap rewind.
        self.history.clear();
        if let Some(c)=self.coarse.as_mut(){c.clear_motion();}
        if self.settings.mapping==Mapping::Laser {
            if let Some(projected)=self.last_projected {
                self.laser_offset=Point{x:position.x-projected.x,y:position.y-projected.y};
            }
            self.target=Some(position);
            self.filter_x=OneEuro{value:Some(position.x),velocity:0.};
            self.filter_y=OneEuro{value:Some(position.y),velocity:0.};
        }
    }
    /// Reliable control is independent of motion loss. Retries are consumed
    /// exactly once, including while paused/calibrating; stale input is not
    /// replayed later. The caller ACKs only after this function has consumed it.
    pub fn control(&mut self,event:Control)->Result<bool,&'static str> {
        if self.last_control.is_some_and(|last|{let n=event.sequence.wrapping_sub(last);n==0||n>=0x8000_0000}){return Ok(false);}
        self.last_control=Some(event.sequence);
        if event.events&OVERFLOW!=0{self.release();return Err("动作连接停顿过久，请重新开启空中鼠标。");}
        if event.events&CLICK!=0{self.metrics.tap_events+=1;}
        // Established gyro clutch semantics (JSM GYRO_OFF): hold to disengage
        // motion, return to a comfortable grip, release at the same cursor.
        // This is explicit intent, not a guessed reverse-motion classifier.
        if self.settings.key_role==KeyRole::Regrip&&event.events&(DOWN|UP)!=0{
            if event.events&DOWN!=0{self.release_button();self.metrics.regripping=true;}
            if event.events&UP!=0{
                self.metrics.regripping=false;
                if self.settings.desktop_motion{self.coarse=None;self.metrics.calibrated=false;self.metrics.surface_paused=false;}
            }
            self.reset_motion();self.history.clear();return Ok(true);
        }
        // GYRO_OFF disengages motion only. A shell tap while the user holds
        // the cursor steady remains a click, independently of the clutch key.
        if event.events==CLICK&&!self.settings.tap_click{return Ok(true);}
        if self.metrics.paused||!self.metrics.calibrated{if event.events&UP!=0{self.wait_release=false;}return Ok(true);}
        let measured_at=self.last.map(|(_,ms)|self.sensor_clock+(event.sensor_ms.wrapping_sub(ms) as i32 as f64)/1000.+self.clock_offset.unwrap_or(0.)).unwrap_or(0.);
        if self.contacts.status.learning.is_some(){
            if event.events&CLICK!=0{self.contacts.contact(event.sensor_ms,self.arrival.unwrap_or(measured_at),self.shown);}
            return Ok(true);
        }
        // A regional mode without a calibrated model must never pretend every
        // front corner is the left button. The UI offers calibration explicitly.
        if self.settings.contact_regions&&event.events&CLICK!=0&&!self.contacts.is_active(){return Ok(true);}
        // A new reliable DOWN is an intentional edge, unlike an unknown held
        // level in a recovered motion packet. UP without a matching DOWN is
        // consumed without clicking after pause/calibration/stale release.
        if event.events&(DOWN|UP)!=0{self.wait_release=false;}
        if event.events&DOWN!=0{self.contacts.discard_pending();}
        if event.events&DOWN!=0 && self.pressed.is_none(){self.pressed=Some((measured_at,self.press_point(measured_at)));}
        if event.events&UP!=0 {
            if let Some((at,point))=self.pressed.take(){
                if self.metrics.dragging{self.queued.push(Button::Up);}
                else if measured_at-at>=self.drag_delay(){self.queued.push(Button::Down(point));self.queued.push(Button::Up);}
                else {self.queued.push(Button::Click(point));}
            }
            self.metrics.dragging=false;self.wait_release=false;
            if self.settings.relative_direct{self.smoother.reset();self.relative.reset();}
        }
        if event.events&CLICK!=0 && self.pressed.is_none()&&!self.metrics.dragging {
            // A relative mouse clicks where its visible cursor is now. The
            // laser's historical tap compensation must not teleport it back
            // through100ms of relative movement (hundreds of pixels in131).
            let point=if self.settings.relative_direct{self.shown}else{self.press_point(measured_at-0.1)};
            if self.contacts.is_active(){
                if let Some(c)=self.coarse.as_mut(){c.contact_candidate(event.sensor_ms);}
                self.contacts.contact(event.sensor_ms,self.arrival.unwrap_or(measured_at),point);
            }
            else{
                if let Some(c)=self.coarse.as_mut(){c.contact(event.sensor_ms);}
                self.shown=point;self.queued.push(Button::Click(point));
                // The tap has already supplied its historical click position.
                // Do not replay the impact's last angular target afterwards.
                if self.settings.relative_direct{self.smoother.reset();self.relative.reset();}
            }
        }
        Ok(true)
    }
    fn observe_clock(&mut self,sequence:u32,sensor_ms:u32,now:f64)->Option<(f64,bool,f64)> {
        let dt=if let Some((previous,ms))=self.last {
            let advance=sequence.wrapping_sub(previous);
            if advance==0 || advance>=0x8000_0000 {self.metrics.duplicates+=1;return None;}
            self.metrics.missing+=(advance-1) as u64;
            sensor_ms.wrapping_sub(ms) as f64/1000.
        }else{0.};
        let gap=dt>0.2 || self.arrival.is_some_and(|at|now-at>0.3);
        if gap {self.metrics.gaps+=1;self.release();self.reset_motion();}
        // Same fastest-arriving clock alignment as WatchPointer. Button DOWN
        // uses its sensor sample time, rather than an invented60ms rewind.
        if gap||self.last.is_none(){self.sensor_clock=sensor_ms as f64/1000.;self.clock_offset=None;}else{self.sensor_clock+=dt;}
        self.clock_offset=Some(self.clock_offset.unwrap_or(f64::INFINITY).min(now-self.sensor_clock));
        let measured_at=self.sensor_clock+self.clock_offset.unwrap();
        self.last=Some((sequence,sensor_ms));self.arrival=Some(now);self.metrics.samples+=1;
        let first=*self.first_arrival.get_or_insert(now);
        if now>first{self.metrics.receive_hz=(self.metrics.samples-1)as f64/(now-first);}
        if dt>0. && dt<0.2 {self.metrics.sensor_hz=if self.metrics.sensor_hz==0.{1./dt}else{self.metrics.sensor_hz*0.9+0.1/dt};}
        Some((dt,gap,measured_at))
    }
    /// CIM5 remains raw sensor data. Reuse the same physical control clock,
    /// history, pause, drag and native output instead of inventing a CIM4 pose.
    pub fn sample_raw(&mut self,s:desktop::Raw,now:f64){
        self.sample_raw_gravity(s,None,now);
    }
    /// CIM6 supplies an explicit board calibration flag separately from its
    /// gravity vector. Do not report host-ready or integrate startup gyro
    /// offsets while the sensor's own fusion is still uncalibrated.
    pub fn observe_device_readiness(&mut self,ready:Option<bool>){
        if !self.settings.desktop_motion{return;}
        if let Some(ready)=ready{
            if !ready||self.desktop_device_ready==Some(false){
                self.coarse=None;self.metrics.calibrated=false;self.metrics.surface_paused=false;
            }
            self.desktop_device_ready=Some(ready);
        }
    }
    pub fn sample_raw_gravity(&mut self,s:desktop::Raw,gravity:Option<[f64;3]>,now:f64){
        if self.settings.desktop_motion{
            if self.observe_clock(s.sequence,s.sensor_ms,now).is_none(){return;}
            self.contacts.sample(s);
            let surface=self.settings.relative_direct;
            if surface||self.settings.contact_regions{self.tap_motion.observe(s);}
            if self.desktop_device_ready==Some(false){self.metrics.calibrated=false;return;}
            let c=self.coarse.get_or_insert_with(||if surface{intent::Intent::surface_mouse()}else{intent::Intent::default()});c.settings=self.settings.clone();
            if self.desktop_device_ready==Some(true){c.desktop.enable_board_pose_prediction();}
            c.sample_blocked_gravity(s,now,surface&&self.tap_motion.blocked(),gravity);
            self.metrics.calibrated=c.desktop.state.calibrated;
            self.metrics.surface_paused=c.desktop.state.surface.as_ref().is_some_and(|s|s.phase!=surface::Phase::Ready)||c.desktop.state.clutched;
            if self.metrics.paused||self.metrics.regripping{c.clear_motion();}
            return;
        }
        // CIM6 shares the fused motion clock. Raw contact acceleration must
        // not run a second fusion, count a second sample, or enable planar.
        if self.settings.contact_regions{
            self.contacts.sample(s);self.tap_motion.observe(s);
            if self.tap_motion.blocked(){self.smoother.reset();self.relative.reset();}
            return;
        }
    }
    pub fn contact_status(&self)->contact::Status{self.contacts.status.clone()}
    /// Experimental planar readiness differs from sensor calibration: after an
    /// impact/gap the user may need to rest before displacement can resume.
    pub fn planar_state(&self)->Option<&desktop::State>{self.coarse.as_ref().map(|c|&c.desktop.state)}
    pub fn learn_contact(&mut self,side:contact::Side)->Result<(),&'static str>{
        if !(self.settings.desktop_motion||self.settings.contact_regions){return Err("先启用左右前角敲击，再校准。");}
        if !self.metrics.calibrated||self.metrics.paused{return Err("先放稳卡片完成动作校准，再校准左右轻敲。");}
        self.release_button();self.reset_motion();self.contacts.learn(side);Ok(())
    }
    pub fn finish_contacts(&mut self)->Result<(),&'static str>{
        self.settings.contact_profile=Some(self.contacts.finish()?);self.reset_motion();Ok(())
    }
    pub fn cancel_contacts(&mut self){self.contacts.cancel();self.reset_motion();}
    pub fn clear_contacts(&mut self){self.contacts=contact::Contact::new(None);self.settings.contact_profile=None;self.settings.contact_device=None;}
    pub fn sample(&mut self,s:Sample,now:f64,bounds:Bounds) {
        if self.settings.desktop_motion{self.observe_device_readiness(s.device_ready);return;}
        let Some((dt,gap,measured_at))=self.observe_clock(s.sequence,s.sensor_ms,now)else{return;};
        // Consume the serial even while paused/calibrating. A lost packet may
        // carry the same event again; reconnect/baseline must never replay it.
        let tapped=self.last_tap.is_some_and(|previous|s.tap_serial.wrapping_sub(previous)==1);
        self.last_tap=Some(s.tap_serial);
        let norm=s.accel.iter().map(|x|x*x).sum::<f64>().sqrt();
        if let Some(ready)=s.device_ready {
            if !ready {
                if self.metrics.calibrated{self.release();self.reset_motion();}
                self.metrics.calibrated=false;return;
            }
            if !self.metrics.calibrated {
                // Firmware has measured its own stationary bias. Subtracting
                // another fixed host bias while device bias keeps adapting
                // would manufacture a drifting zero rate.
                self.bias=[0.;3];self.metrics.calibrated=true;self.heading=0.;
                self.heading_zero=s.aim.map(|aim|aim[0]);
                self.elevation_zero=Some((s.accel[1]/norm.max(1.)).clamp(-1.,1.).asin().to_degrees());
                return;
            }
        }
        let rates=std::array::from_fn(|i|s.gyro[i]-self.bias[i]);
        let (up,rate)=if s.fused {
            (s.accel.map(|v|v/norm.max(1.)),rates)
        }else{self.fusion.step(rates,s.accel,if dt>0.&&dt<0.2{dt}else{0.})};
        if !self.metrics.calibrated {
            // Raw LSM6DSO has no Apple's fused gravity/bias. Learn bias only
            // from a continuous stationary second, never while the card moves.
            let still=(850.0..=1150.0).contains(&norm) && s.gyro.iter().all(|x|x.abs()<3.) && !s.held;
            if !still || dt>0.2 {self.calibration_start=None;self.bias_sum=[0.;3];self.accel_sum=[0.;3];self.metrics.calibration_samples=0;return;}
            let start=*self.calibration_start.get_or_insert(s.sensor_ms);
            self.metrics.calibration_samples+=1;
            for i in 0..3 {self.bias_sum[i]+=s.gyro[i];self.accel_sum[i]+=s.accel[i];}
            if s.sensor_ms.wrapping_sub(start)>=1000 && self.metrics.calibration_samples>=20 {
                for i in 0..3 {self.bias[i]=self.bias_sum[i]/self.metrics.calibration_samples as f64;}
                if !s.fused {self.fusion.align(self.accel_sum.map(|v|v/self.metrics.calibration_samples as f64));}
                self.metrics.calibrated=true;
            }
            return;
        }
        // CoreMotion already supplies fused gravity. Raw LSM6DSO does not:
        // reuse x-io Fusion's no-magnetometer AHRS/bias instead of an added
        // low-pass delay. Its NWU gravity matches proper-acceleration UP.
        let yaw=s.aim.map(|aim|aim[1]).unwrap_or_else(||(0..3).map(|i|rate[i]*up[i]).sum::<f64>());
        let pitch=s.aim.map(|aim|aim[2]).unwrap_or(rate[0]);
        match self.settings.mapping {
            Mapping::Relative=>{
                let r=if self.settings.relative_direct{
                    // CIM3 carries the complete device-calibrated gyro. Older
                    // CIM4 can only provide its already projected two rates.
                    let raw=if self.settings.relative_horizontal==RelativeHorizontal::Tilt{
                        // JSM LOCAL axis selection, adapted to board X-right,
                        // Y-Type-C, Z-up. Right edge down (+gyroY) moves right;
                        // pitch is unchanged from the Owner-accepted path.
                        // CIM4 lacks roll: never substitute its yaw silently.
                        Point{x:-rate[1],y:pitch}
                    }else if s.aim.is_some(){Point{x:yaw,y:pitch}}else{relative::player_space(rate,up)};
                    if self.settings.contact_regions{
                        let value=self.tap_motion.angular(s.sensor_ms,raw,dt);
                        if let Some((raw,dt))=value{self.relative.sample(raw,dt)}
                        else{self.relative.reset();self.smoother.reset();Point::default()}
                    }else{self.relative.sample(raw,dt)}
                }else{Point{x:yaw,y:pitch}};
                let dx=-axis_speed(r.x,&self.settings)*if self.settings.invert_horizontal{-1.}else{1.};
                // Physical Type-C-front fixture binds lift to negative gyroX.
                let dy=axis_speed(r.y,&self.settings)*if self.settings.relative_direct{1.}else{-1.}*if self.settings.invert_vertical{-1.}else{1.};
                if !self.metrics.paused {self.smoother.target(Point{x:dx,y:dy},now);}
            },
            Mapping::Laser=>{
                if let Some(aim)=s.aim {self.heading=(aim[0]-*self.heading_zero.get_or_insert(aim[0])+180.).rem_euclid(360.)-180.;}
                else {self.heading+=yaw*dt.min(0.05);}
                let elevation=up[1].clamp(-1.,1.).asin().to_degrees();
                let zero=*self.elevation_zero.get_or_insert(elevation);
                let left=((self.heading+180.).rem_euclid(360.)-180.)*if self.settings.invert_horizontal{-1.}else{1.};
                let height=(elevation-zero)*if self.settings.invert_vertical{-1.}else{1.};
                if self.metrics.paused {return;} // Aim still tracks while paused, as upstream.
                let projected=laser(left,height,self.settings.sensitivity,bounds);
                // Anchor the upstream projection at the real cursor on the
                // first pose after start/recenter. Seeding `shown` from
                // screen centre made the first click jump even without an OS
                // move frame. Subsequent pose deltas keep the same projection.
                if self.last_projected.is_none(){self.laser_offset=Point{x:self.shown.x-projected.x,y:self.shown.y-projected.y};}
                self.last_projected=Some(projected);
                let point=Point{x:projected.x+self.laser_offset.x,y:projected.y+self.laser_offset.y};
                let filter_dt=if dt>0.&&dt<0.2{dt}else{0.};
                self.target=Some(Point{x:self.filter_x.update(point.x,filter_dt),y:self.filter_y.update(point.y,filter_dt)});
            }
        }
        if self.metrics.paused {return;}
        if s.aim.is_some()||self.settings.relative_direct{if !s.held{self.wait_release=false;}return;} // Reliable CIN owns current physical controls.
        if self.wait_release {if !s.held {self.wait_release=false;}return;}
        if self.settings.tap_click&&tapped && !gap && !s.held && self.pressed.is_none() && !self.metrics.dragging {
            // Hardware double-tap is one intentional click. Reuse the same
            // pre-press history to avoid clicking at the tap-induced wobble.
            let point=self.press_point(measured_at-0.1); // Upstream fallback when no touch-down timestamp exists.
            self.shown=point;
            self.queued.push(Button::Click(point));
        }
        if s.held && self.pressed.is_none() {
            // WatchPointer's pre-press position prevents button-pressure jitter.
            let point=self.press_point(measured_at);
            self.pressed=Some((measured_at,point));
        } else if !s.held {
            if let Some((_,point))=self.pressed.take() {
                self.queued.push(if self.metrics.dragging {Button::Up}else{Button::Click(point)});
                self.metrics.dragging=false;
            }
        }
    }
    pub fn frame(&mut self,now:f64,bounds:Bounds)->Frame {
        let dt=self.frame_at.map(|t|(now-t).clamp(0.,0.05)).unwrap_or(0.);self.frame_at=Some(now);
        if let Some(first)=self.first_arrival{if now>first{self.metrics.receive_hz=self.metrics.samples.saturating_sub(1)as f64/(now-first);}}
        let stale=self.arrival.is_none_or(|at|now-at>0.3);
        self.metrics.stream_stale=stale;
        if stale {self.release();self.reset_motion();}
        if !stale&&!self.metrics.paused&&self.metrics.calibrated{
            let clicks=self.contacts.poll(now);
            // A missing raw window or a rebound is not an accepted contact.
            // Candidate arrival/completion must not erase a planar stroke.
            for(side,point,ms)in clicks{
                if let Some(c)=self.coarse.as_mut(){c.contact(ms);}
                let point=if self.settings.relative_direct{self.shown}else{point};
                self.queued.push(match side{contact::Side::Left=>Button::Click(point),contact::Side::Right=>Button::RightClick(point)});
            }
        }
        let mut f=Frame{position:None,buttons:std::mem::take(&mut self.queued)};
        if stale || self.metrics.paused || self.metrics.regripping || !self.metrics.calibrated {return f;}
        if self.settings.contact_regions&&(self.tap_motion.blocked()||f.buttons.iter().any(|x|matches!(x,Button::Click(_)|Button::RightClick(_)))){return f;}
        if self.contacts.status.learning.is_some(){return f;}
        if let Some((at,point))=self.pressed {if !self.metrics.dragging && now-at>=self.drag_delay() {self.metrics.dragging=true;f.buttons.push(Button::Down(point));}}
        if self.settings.relative_direct&&self.pressed.is_some()&&!self.metrics.dragging{return f;}
        let next=match self.settings.mapping {
            Mapping::Relative=>{let delta=if let Some(c)=self.coarse.as_mut(){c.frame(now)}else{self.smoother.step(now,dt,self.settings.smoothing)};Point{x:self.shown.x+delta.x,y:self.shown.y+delta.y}},
            Mapping::Laser=>{let p=self.target.unwrap_or(self.shown);let follow=1.-(-dt/0.005).exp();Point{x:self.shown.x+(p.x-self.shown.x)*follow,y:self.shown.y+(p.y-self.shown.y)*follow}}
        };
        let next=if self.settings.mapping==Mapping::Laser{next}else{bounds.clamp(next)};
        if self.settings.relative_direct{
            // Preserve fractions between frames. Discarding <0.05px EVERY
            // frame made slow motion impossible even with a zero deadzone.
            self.shown=next;
            if next.x.round()!=self.last_emitted.x.round()||next.y.round()!=self.last_emitted.y.round(){
                self.last_emitted=Point{x:next.x.round(),y:next.y.round()};f.position=Some(bounds.clamp(next));
            }
        }else if (next.x-self.shown.x).abs()+(next.y-self.shown.y).abs()>0.05 {self.shown=next;f.position=Some(bounds.clamp(next));}
        if self.history.len()==360 {self.history.pop_front();}self.history.push_back((now,bounds.clamp(self.shown)));f
    }
}

#[cfg(test)]
mod tests;
#[cfg(test)]
mod remote_tests;
