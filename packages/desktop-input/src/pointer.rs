//! Ports of AirCursor Pointer.swift and WatchPointer Receiver/WatchPointerApp.
//! See third_party/imu-pointer for the pinned originals and MIT notices.
//! Companion-specific parts: CIM1 decoding, upstream Fusion raw-sensor adapter,
//! stationary gyro bias, physical button/tap edges, and explicit pause/recenter.
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
pub mod native;
mod fusion;
pub mod desktop;
pub mod intent;

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
        if p.len()!=32 || &p[..4]!=b"CIM1" || !matches!(p[4],1|2|3|4) || p[5]!=3 || p[6]&!(if p[4]>=3{3}else{1})!=0 {
            return Err("invalid CIM1 sample");
        }
        let mut crc=0xffff_ffffu32;
        for byte in &p[..28] { crc^=*byte as u32; for _ in 0..8 {crc=(crc>>1)^((0u32.wrapping_sub(crc&1))&0xedb8_8320);} }
        if !crc!=u32::from_le_bytes(p[28..32].try_into().unwrap()) {return Err("CIM1 CRC mismatch");}
        let mut s=Self {sequence:u32::from_le_bytes(p[8..12].try_into().unwrap()),
            sensor_ms:u32::from_le_bytes(p[12..16].try_into().unwrap()),held:p[6]&1!=0,tap_serial:p[7],fused:p[4]>=2,device_ready:if p[4]>=3{Some(p[6]&2!=0)}else{None},accel:[0.;3],gyro:[0.;3],aim:None};
        if p[4]==4 {
            let value=|at|i16::from_le_bytes(p[at..at+2].try_into().unwrap()) as f64/100.;
            s.aim=Some([value(16),value(24),value(26)]);
            for i in 0..3{s.accel[i]=i16::from_le_bytes(p[18+2*i..20+2*i].try_into().unwrap()) as f64*1000./16384.;}
            return Ok(s);
        }
        for i in 0..3 {s.accel[i]=i16::from_le_bytes(p[16+2*i..18+2*i].try_into().unwrap()) as f64;
            if p[4]==3{s.accel[i]*=1000./16384.;}
            s.gyro[i]=i16::from_le_bytes(p[22+2*i..24+2*i].try_into().unwrap()) as f64/100.;}
        Ok(s)
    }
}
#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq)]
#[serde(rename_all="camelCase")]
pub enum Mapping { #[default] Relative, Laser }
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(default, rename_all="camelCase")]
pub struct Settings {
    pub mapping: Mapping, pub sensitivity: f64, pub smoothing: f64,
    pub deadzone: f64, pub acceleration: f64, pub invert_horizontal: bool, pub invert_vertical: bool,
}
impl Default for Settings {
    fn default()->Self {Self {mapping:Mapping::Laser,sensitivity:1.,smoothing:0.55,
        deadzone:3.,acceleration:0.6,invert_horizontal:false,invert_vertical:false}}
}
impl Settings {
    pub fn validate(&self)->Result<(), &'static str> {
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
        let Some(previous)=self.value.filter(|_|dt>0.) else {self.value=Some(x);return x;};
        let alpha=|cutoff:f64|1./(1.+1./(2.*std::f64::consts::PI*cutoff*dt));
        self.velocity+=alpha(1.)*((x-previous)/dt-self.velocity);
        let smoothed=previous+alpha(0.8+0.01*self.velocity.abs())*(x-previous);
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
pub enum Button {Click(Point),Down(Point),Up}
#[derive(Clone,Copy,Debug,Deserialize)]
pub struct Control {pub sequence:u32,pub sensor_ms:u32,pub events:u16}
pub const CLICK:u16=512;pub const DOWN:u16=1024;pub const UP:u16=2048;pub const OVERFLOW:u16=4096;
#[derive(Default)]
pub struct Frame {pub position:Option<Point>,pub buttons:Vec<Button>}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Metrics {pub samples:u64,pub missing:u64,pub duplicates:u64,pub gaps:u64,pub sensor_hz:f64,pub calibrated:bool,pub calibration_samples:u32,pub dragging:bool,pub paused:bool,pub stream_stale:bool}

pub struct Pointer {
    pub settings:Settings,pub metrics:Metrics, smoother:Smoother, filter_x:OneEuro,filter_y:OneEuro,
    last:Option<(u32,u32)>, last_tap:Option<u8>, arrival:Option<f64>, frame_at:Option<f64>,sensor_clock:f64,clock_offset:Option<f64>,
    bias:[f64;3],bias_sum:[f64;3],accel_sum:[f64;3],calibration_start:Option<u32>,
    fusion:fusion::Fusion,
    heading:f64,heading_zero:Option<f64>,elevation_zero:Option<f64>,target:Option<Point>,shown:Point,
    laser_offset:Point,last_projected:Option<Point>,
    last_control:Option<u32>,
    pressed:Option<(f64,Point)>,wait_release:bool,queued:Vec<Button>,history:VecDeque<(f64,Point)>,
}
impl Pointer {
    pub fn new(settings:Settings,position:Point)->Self {
        Self {settings,metrics:Metrics::default(),smoother:Smoother::default(),filter_x:OneEuro::default(),filter_y:OneEuro::default(),
            last:None,last_tap:None,arrival:None,frame_at:None,sensor_clock:0.,clock_offset:None,bias:[0.;3],bias_sum:[0.;3],accel_sum:[0.;3],calibration_start:None,fusion:fusion::Fusion::default(),
            heading:0.,heading_zero:None,elevation_zero:None,target:None,shown:position,laser_offset:Point::default(),last_projected:None,last_control:None,pressed:None,wait_release:true,queued:vec![],history:VecDeque::with_capacity(360)}
    }
    fn release(&mut self) {if self.metrics.dragging {self.queued.push(Button::Up);}self.metrics.dragging=false;self.pressed=None;self.wait_release=true;}
    fn reset_motion(&mut self){self.smoother.reset();self.filter_x=OneEuro::default();self.filter_y=OneEuro::default();self.target=None;self.history.clear();}
    fn press_point(&self,at:f64)->Point {self.history.iter().rev().find(|(t,_)|*t<=at).or(self.history.front()).map(|(_,p)|*p).unwrap_or(self.shown)}
    pub fn pause(&mut self,paused:bool) {self.release();self.reset_motion();self.metrics.paused=paused;}
    pub fn calibrate(&mut self) {self.release();self.reset_motion();self.fusion=fusion::Fusion::default();self.metrics.calibrated=false;self.metrics.calibration_samples=0;self.calibration_start=None;self.bias_sum=[0.;3];self.accel_sum=[0.;3];self.heading=0.;self.heading_zero=None;self.elevation_zero=None;self.laser_offset=Point::default();self.last_projected=None;}
    pub fn recenter(&mut self,position:Point) {self.release();self.reset_motion();self.shown=position;self.heading=0.;self.heading_zero=None;self.elevation_zero=None;self.laser_offset=Point::default();self.last_projected=None;}
    /// An ordinary mouse moved the real cursor since our last OS output.
    /// Re-anchor to that position, canceling the old follow residual. The next
    /// unchanged card pose must stay here; subsequent card motion adds to it.
    pub fn external_position(&mut self,position:Point) {
        self.shown=position;
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
        if self.metrics.paused||!self.metrics.calibrated{if event.events&UP!=0{self.wait_release=false;}return Ok(true);}
        let measured_at=self.last.map(|(_,ms)|self.sensor_clock+(event.sensor_ms.wrapping_sub(ms) as i32 as f64)/1000.+self.clock_offset.unwrap_or(0.)).unwrap_or(0.);
        // A new reliable DOWN is an intentional edge, unlike an unknown held
        // level in a recovered motion packet. UP without a matching DOWN is
        // consumed without clicking after pause/calibration/stale release.
        if event.events&(DOWN|UP)!=0{self.wait_release=false;}
        if event.events&DOWN!=0 && self.pressed.is_none(){self.pressed=Some((measured_at,self.press_point(measured_at)));}
        if event.events&UP!=0 {
            if let Some((at,point))=self.pressed.take(){
                if self.metrics.dragging{self.queued.push(Button::Up);}
                else if measured_at-at>=0.35{self.queued.push(Button::Down(point));self.queued.push(Button::Up);}
                else {self.queued.push(Button::Click(point));}
            }
            self.metrics.dragging=false;self.wait_release=false;
        }
        if event.events&CLICK!=0 && self.pressed.is_none()&&!self.metrics.dragging {
            let point=self.press_point(measured_at-0.1);self.shown=point;self.queued.push(Button::Click(point));
        }
        Ok(true)
    }
    pub fn sample(&mut self,s:Sample,now:f64,bounds:Bounds) {
        let dt=if let Some((sequence,ms))=self.last {
            let advance=s.sequence.wrapping_sub(sequence);
            if advance==0 || advance>=0x8000_0000 {self.metrics.duplicates+=1;return;}
            self.metrics.missing+=(advance-1) as u64;
            s.sensor_ms.wrapping_sub(ms) as f64/1000.
        }else{0.};
        let gap=dt>0.2 || self.arrival.is_some_and(|at|now-at>0.3);
        if gap {self.metrics.gaps+=1;self.release();self.reset_motion();}
        // Same fastest-arriving clock alignment as WatchPointer. Button DOWN
        // uses its sensor sample time, rather than an invented60ms rewind.
        if gap||self.last.is_none(){self.sensor_clock=s.sensor_ms as f64/1000.;self.clock_offset=None;}else{self.sensor_clock+=dt;}
        self.clock_offset=Some(self.clock_offset.unwrap_or(f64::INFINITY).min(now-self.sensor_clock));
        let measured_at=self.sensor_clock+self.clock_offset.unwrap();
        // Consume the serial even while paused/calibrating. A lost packet may
        // carry the same event again; reconnect/baseline must never replay it.
        let tapped=self.last_tap.is_some_and(|previous|s.tap_serial.wrapping_sub(previous)==1);
        self.last_tap=Some(s.tap_serial);
        self.last=Some((s.sequence,s.sensor_ms));self.arrival=Some(now);self.metrics.samples+=1;
        if dt>0. && dt<0.2 {self.metrics.sensor_hz=if self.metrics.sensor_hz==0.{1./dt}else{self.metrics.sensor_hz*0.9+0.1/dt};}
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
                let dx=-axis_speed(yaw,&self.settings)*if self.settings.invert_horizontal{-1.}else{1.};
                let dy=-axis_speed(pitch,&self.settings)*if self.settings.invert_vertical{-1.}else{1.};
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
                let projected=laser(left,height,self.settings.sensitivity,bounds);self.last_projected=Some(projected);
                let point=Point{x:projected.x+self.laser_offset.x,y:projected.y+self.laser_offset.y};
                if self.target.is_none(){self.shown=point;}
                let filter_dt=if dt>0.&&dt<0.2{dt}else{0.};
                self.target=Some(Point{x:self.filter_x.update(point.x,filter_dt),y:self.filter_y.update(point.y,filter_dt)});
            }
        }
        if self.metrics.paused {return;}
        if s.aim.is_some(){if !s.held{self.wait_release=false;}return;} // CIN owns CIM4 physical controls.
        if self.wait_release {if !s.held {self.wait_release=false;}return;}
        if tapped && !gap && !s.held && self.pressed.is_none() && !self.metrics.dragging {
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
        let stale=self.arrival.is_none_or(|at|now-at>0.3);
        self.metrics.stream_stale=stale;
        if stale {self.release();self.reset_motion();}
        let mut f=Frame{position:None,buttons:std::mem::take(&mut self.queued)};
        if stale || self.metrics.paused || !self.metrics.calibrated {return f;}
        if let Some((at,point))=self.pressed {if !self.metrics.dragging && now-at>=0.35 {self.metrics.dragging=true;f.buttons.push(Button::Down(point));}}
        let next=match self.settings.mapping {
            Mapping::Relative=>{let delta=self.smoother.step(now,dt,self.settings.smoothing);Point{x:self.shown.x+delta.x,y:self.shown.y+delta.y}},
            Mapping::Laser=>{let p=self.target.unwrap_or(self.shown);let follow=1.-(-dt/0.005).exp();Point{x:self.shown.x+(p.x-self.shown.x)*follow,y:self.shown.y+(p.y-self.shown.y)*follow}}
        };
        let next=if self.settings.mapping==Mapping::Laser{next}else{bounds.clamp(next)};
        if (next.x-self.shown.x).abs()+(next.y-self.shown.y).abs()>0.05 {self.shown=next;f.position=Some(bounds.clamp(next));}
        if self.history.len()==360 {self.history.pop_front();}self.history.push_back((now,bounds.clamp(self.shown)));f
    }
}

#[cfg(test)]
mod tests;
