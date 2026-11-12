//! Ports of AirCursor Pointer.swift and WatchPointer Receiver/WatchPointerApp.
//! See third_party/imu-pointer for the pinned originals and MIT notices.
//! Companion-specific parts: CIM1 decoding, raw-acceleration gravity adapter,
//! stationary gyro bias, physical button edges, and explicit pause/recenter.
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
pub mod native;

#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize)]
pub struct Point { pub x: f64, pub y: f64 }
impl Point {
    fn distance(self, b: Self) -> f64 { (self.x-b.x).hypot(self.y-b.y) }
}
#[derive(Clone, Copy, Debug)]
pub struct Sample {
    pub sequence: u32, pub sensor_ms: u32, pub held: bool,
    pub accel: [f64;3], pub gyro: [f64;3],
}
impl Sample {
    pub fn parse(p: &[u8]) -> Result<Self, &'static str> {
        if p.len()!=32 || &p[..4]!=b"CIM1" || p[4]!=1 || p[5]!=3 || p[6]&!1!=0 || p[7]!=0 {
            return Err("invalid CIM1 sample");
        }
        let mut crc=0xffff_ffffu32;
        for byte in &p[..28] { crc^=*byte as u32; for _ in 0..8 {crc=(crc>>1)^((0u32.wrapping_sub(crc&1))&0xedb8_8320);} }
        if !crc!=u32::from_le_bytes(p[28..32].try_into().unwrap()) {return Err("CIM1 CRC mismatch");}
        let mut s=Self {sequence:u32::from_le_bytes(p[8..12].try_into().unwrap()),
            sensor_ms:u32::from_le_bytes(p[12..16].try_into().unwrap()),held:p[6]&1!=0,accel:[0.;3],gyro:[0.;3]};
        for i in 0..3 {s.accel[i]=i16::from_le_bytes(p[16+2*i..18+2*i].try_into().unwrap()) as f64;
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
    fn default()->Self {Self {mapping:Mapping::Relative,sensitivity:1.,smoothing:0.55,
        deadzone:0.6,acceleration:0.35,invert_horizontal:false,invert_vertical:false}}
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
    let h=(-left).clamp(-80.,80.).to_radians(); let v=up.clamp(-80.,80.).to_radians();
    let unit=b.width*0.5/(25./speed).to_radians().tan();
    Point{x:b.left+b.width*0.5+h.tan()*unit,y:b.top+b.height*0.5-v.tan()/h.cos()*unit}
}
#[derive(Clone,Copy)]
pub struct Bounds {pub left:f64,pub top:f64,pub width:f64,pub height:f64}
impl Bounds {
    fn clamp(self,p:Point)->Point {Point{x:p.x.clamp(self.left,self.left+self.width-1.),y:p.y.clamp(self.top,self.top+self.height-1.)}}
}
#[derive(Clone,Copy,Debug,PartialEq)]
pub enum Button {Click(Point),Down(Point),Up}
#[derive(Default)]
pub struct Frame {pub position:Option<Point>,pub buttons:Vec<Button>}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Metrics {pub samples:u64,pub missing:u64,pub duplicates:u64,pub gaps:u64,pub sensor_hz:f64,pub calibrated:bool,pub calibration_samples:u32,pub dragging:bool,pub paused:bool,pub stream_stale:bool}

pub struct Pointer {
    pub settings:Settings,pub metrics:Metrics, smoother:Smoother, filter_x:OneEuro,filter_y:OneEuro,
    last:Option<(u32,u32)>, arrival:Option<f64>, frame_at:Option<f64>,
    bias:[f64;3],bias_sum:[f64;3],calibration_start:Option<u32>,gravity:[f64;3],
    heading:f64,elevation_zero:Option<f64>,target:Option<Point>,shown:Point,
    pressed:Option<(f64,Point)>,wait_release:bool,queued:Vec<Button>,history:VecDeque<(f64,Point)>,
}
impl Pointer {
    pub fn new(settings:Settings,position:Point)->Self {
        Self {settings,metrics:Metrics::default(),smoother:Smoother::default(),filter_x:OneEuro::default(),filter_y:OneEuro::default(),
            last:None,arrival:None,frame_at:None,bias:[0.;3],bias_sum:[0.;3],calibration_start:None,gravity:[0.;3],
            heading:0.,elevation_zero:None,target:None,shown:position,pressed:None,wait_release:true,queued:vec![],history:VecDeque::with_capacity(360)}
    }
    fn release(&mut self) {if self.metrics.dragging {self.queued.push(Button::Up);}self.metrics.dragging=false;self.pressed=None;self.wait_release=true;}
    fn reset_motion(&mut self){self.smoother.reset();self.filter_x=OneEuro::default();self.filter_y=OneEuro::default();self.target=None;self.history.clear();}
    pub fn pause(&mut self,paused:bool) {self.release();self.reset_motion();self.metrics.paused=paused;}
    pub fn calibrate(&mut self) {self.release();self.reset_motion();self.metrics.calibrated=false;self.metrics.calibration_samples=0;self.calibration_start=None;self.bias_sum=[0.;3];self.heading=0.;self.elevation_zero=None;}
    pub fn recenter(&mut self,position:Point) {self.release();self.reset_motion();self.shown=position;self.heading=0.;self.elevation_zero=None;}
    pub fn sample(&mut self,s:Sample,now:f64,bounds:Bounds) {
        let dt=if let Some((sequence,ms))=self.last {
            let advance=s.sequence.wrapping_sub(sequence);
            if advance==0 || advance>=0x8000_0000 {self.metrics.duplicates+=1;return;}
            self.metrics.missing+=(advance-1) as u64;
            s.sensor_ms.wrapping_sub(ms) as f64/1000.
        }else{0.};
        if dt>0.2 || self.arrival.is_some_and(|at|now-at>0.3) {self.metrics.gaps+=1;self.release();self.reset_motion();}
        self.last=Some((s.sequence,s.sensor_ms));self.arrival=Some(now);self.metrics.samples+=1;
        if dt>0. && dt<0.2 {self.metrics.sensor_hz=if self.metrics.sensor_hz==0.{1./dt}else{self.metrics.sensor_hz*0.9+0.1/dt};}
        let norm=s.accel.iter().map(|x|x*x).sum::<f64>().sqrt();
        if !self.metrics.calibrated {
            // Raw LSM6DSO has no Apple's fused gravity/bias. Learn bias only
            // from a continuous stationary second, never while the card moves.
            let still=(850.0..=1150.0).contains(&norm) && s.gyro.iter().all(|x|x.abs()<3.) && !s.held;
            if !still || dt>0.2 {self.calibration_start=None;self.bias_sum=[0.;3];self.metrics.calibration_samples=0;return;}
            let start=*self.calibration_start.get_or_insert(s.sensor_ms);
            self.metrics.calibration_samples+=1;
            for i in 0..3 {self.bias_sum[i]+=s.gyro[i];}
            if s.sensor_ms.wrapping_sub(start)>=1000 && self.metrics.calibration_samples>=20 {
                for i in 0..3 {self.bias[i]=self.bias_sum[i]/self.metrics.calibration_samples as f64;self.gravity[i]=s.accel[i];}
                self.metrics.calibrated=true;
            }
            return;
        }
        if self.metrics.paused {return;}
        // Adapt the input only: accelerometer proper acceleration points UP,
        // whereas CoreMotion's gravity points DOWN. Filter non-gravity motion.
        let a=if dt>0. {1.-(-dt/0.15).exp()}else{0.};
        if (750.0..=1250.0).contains(&norm) {for i in 0..3 {self.gravity[i]+=a*(s.accel[i]-self.gravity[i]);}}
        let gn=self.gravity.iter().map(|x|x*x).sum::<f64>().sqrt().max(1.);
        let up=self.gravity.map(|x|x/gn);let rate=std::array::from_fn::<_,3,_>(|i|s.gyro[i]-self.bias[i]);
        let yaw=(0..3).map(|i|rate[i]*up[i]).sum::<f64>();
        let pitch=rate[0];
        match self.settings.mapping {
            Mapping::Relative=>{
                let dx=-axis_speed(yaw,&self.settings)*if self.settings.invert_horizontal{-1.}else{1.};
                let dy=-axis_speed(pitch,&self.settings)*if self.settings.invert_vertical{-1.}else{1.};
                self.smoother.target(Point{x:dx,y:dy},now);
            },
            Mapping::Laser=>{
                self.heading+=yaw*dt.min(0.05);
                let elevation=up[1].clamp(-1.,1.).asin().to_degrees();
                let zero=*self.elevation_zero.get_or_insert(elevation);
                let left=((self.heading+180.).rem_euclid(360.)-180.)*if self.settings.invert_horizontal{-1.}else{1.};
                let height=(elevation-zero)*if self.settings.invert_vertical{-1.}else{1.};
                let point=laser(left,height,self.settings.sensitivity,bounds);
                if dt>0. && dt<0.2 {self.target=Some(Point{x:self.filter_x.update(point.x,dt),y:self.filter_y.update(point.y,dt)});}
            }
        }
        if self.wait_release {if !s.held {self.wait_release=false;}return;}
        if s.held && self.pressed.is_none() {
            // WatchPointer's pre-press position prevents button-pressure jitter.
            let point=self.history.iter().rev().find(|(at,_)|*at<=now-0.06).map(|(_,p)|*p).unwrap_or(self.shown);
            self.pressed=Some((now,point));
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
        let next=bounds.clamp(next);
        if next.distance(self.shown)>0.05 {self.shown=next;f.position=Some(next);}
        if self.history.len()==360 {self.history.pop_front();}self.history.push_back((now,self.shown));f
    }
}

#[cfg(test)]
mod tests;
