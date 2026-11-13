// Exact former mixed-source mapping retained only for causal regression comparison.
// Baseline source and digest recorded in planar review receipt.
//! Coarse direction/velocity control. No metric position-tracking claim.
//! Angular speed/filtering reuse the pinned AirCursor port. Planar velocity
//! comes from the causal Fusion desktop adapter; never add both for one sample.
use companion_desktop_input::pointer::{axis_speed,desktop::{Desktop,Raw},Mapping,Point,Settings,Smoother};
use serde::Serialize;
#[derive(Clone,Copy,Debug,Default,Serialize,PartialEq)]
pub enum Source {#[default] Rest,Translation,Angular}
pub struct Intent {
    pub desktop:Desktop,pub source:Source,pub settings:Settings,
    pub angular_horizontal:[f64;3],pub angular_vertical:[f64;3],
    smoother:Smoother,at:Option<f64>,last:Option<(u32,u32,f64)>,
}
impl Default for Intent {
    fn default()->Self{Self{desktop:Desktop::default(),source:Source::Rest,settings:Settings{mapping:Mapping::Relative,..Settings::default()},
        angular_horizontal:[0.,0.,1.],angular_vertical:[1.,0.,0.],smoother:Smoother::default(),at:None,last:None}}
}
impl Intent {
    pub fn clear_motion(&mut self){
        self.desktop.pause_translation();self.smoother.reset();self.source=Source::Rest;self.at=None;
    }
    pub fn tap(&mut self){
        self.clear_motion();self.desktop.tap();
    }
    pub fn sample(&mut self,s:Raw,now:f64){
        if let Some((sequence,ms,arrival))=self.last{
            let n=s.sequence.wrapping_sub(sequence);
            if n==0||n>=0x8000_0000{return;}
            let dt=s.sensor_ms.wrapping_sub(ms)as f64/1000.;
            if n!=1||dt<=0.||dt>0.05||now-arrival>0.12{
                // Keep AirCursor's latest-rate semantics: never integrate a
                // missing interval or blend a reversed turn with an old one.
                self.smoother.reset();self.at=Some(now);
            }
        }
        self.last=Some((s.sequence,s.sensor_ms,now));
        self.desktop.sample(s);
        let state=&self.desktop.state;
        if !state.calibrated{self.smoother.reset();self.source=Source::Rest;return;}
        let project=|axis:[f64;3]|(0..3).map(|i|axis[i]*state.gyro_dps[i]).sum::<f64>();
        let angular=Point{x:-axis_speed(project(self.angular_horizontal),&self.settings),y:-axis_speed(project(self.angular_vertical),&self.settings)};
        let (mut goal,source)=if angular.x!=0.||angular.y!=0.{(angular,Source::Angular)}
            else if state.moving&&!state.clutched {
                // Gain controls feel, not a calibrated mm-to-pixel contract.
                (Point{x:(state.velocity_mps[0]*5000.*self.settings.sensitivity).clamp(-1000.,1000.),y:(-state.velocity_mps[1]*5000.*self.settings.sensitivity).clamp(-1000.,1000.)},Source::Translation)
            }else{(Point::default(),Source::Rest)};
        if source==Source::Angular{self.desktop.pause_translation();}
        if self.settings.invert_horizontal{goal.x = -goal.x;}
        if self.settings.invert_vertical{goal.y = -goal.y;}
        self.source=source;self.smoother.target(goal,now);
    }
    pub fn frame(&mut self,now:f64)->Point{
        let dt=self.at.map(|at|(now-at).clamp(0.,0.05)).unwrap_or(0.);self.at=Some(now);
        self.smoother.step(now,dt,self.settings.smoothing)
    }
}
