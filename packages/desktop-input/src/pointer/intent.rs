//! Coarse direction/velocity control. No metric position-tracking claim.
//! Angular speed/filtering reuse the pinned AirCursor port. Planar velocity
//! comes from the causal Fusion desktop adapter; never add both for one sample.
use super::{axis_speed,desktop::{Desktop,Raw},Mapping,Point,Settings,Smoother};
use serde::Serialize;
#[derive(Clone,Copy,Debug,Default,Serialize,PartialEq)]
pub enum Source {#[default] Rest,Translation,Angular}
pub struct Intent {
    pub desktop:Desktop,pub source:Source,pub settings:Settings,
    pub angular_horizontal:[f64;3],pub angular_vertical:[f64;3],
    smoother:Smoother,at:Option<f64>,
}
impl Default for Intent {
    fn default()->Self{Self{desktop:Desktop::default(),source:Source::Rest,settings:Settings{mapping:Mapping::Relative,..Settings::default()},
        angular_horizontal:[0.,0.,1.],angular_vertical:[1.,0.,0.],smoother:Smoother::default(),at:None}}
}
impl Intent {
    pub fn sample(&mut self,s:Raw,now:f64){
        self.desktop.sample(s);
        let state=&self.desktop.state;
        if !state.calibrated{self.smoother.reset();self.source=Source::Rest;return;}
        let project=|axis:[f64;3]|(0..3).map(|i|axis[i]*state.gyro_dps[i]).sum::<f64>();
        let angular=Point{x:-axis_speed(project(self.angular_horizontal),&self.settings),y:-axis_speed(project(self.angular_vertical),&self.settings)};
        let (goal,source)=if angular.x!=0.||angular.y!=0.{(angular,Source::Angular)}
            else if state.moving&&!state.clutched {
                // Gain controls feel, not a calibrated mm-to-pixel contract.
                (Point{x:(state.velocity_mps[0]*5000.).clamp(-1000.,1000.),y:(-state.velocity_mps[1]*5000.).clamp(-1000.,1000.)},Source::Translation)
            }else{(Point::default(),Source::Rest)};
        if source==Source::Angular{self.desktop.pause_translation();}
        self.source=source;self.smoother.target(goal,now);
    }
    pub fn frame(&mut self,now:f64)->Point{
        let dt=self.at.map(|at|(now-at).clamp(0.,0.05)).unwrap_or(0.);self.at=Some(now);
        self.smoother.step(now,dt,self.settings.smoothing)
    }
}
#[cfg(test)]mod tests{
    use super::*;
    fn raw(n:u32)->Raw{Raw{sequence:n+1,sensor_ms:n*10,accel_mg:[0.,0.,1000.],gyro_dps:[0.;3]}}
    #[test]fn natural_angular_motion_controls_direction_and_expires_when_samples_stop(){
        let mut p=Intent::default();for n in 0..121{p.sample(raw(n),n as f64/100.);p.frame(n as f64/100.);}
        let mut s=raw(121);s.gyro_dps=[0.,0.,20.];p.sample(s,1.21);assert_eq!(p.source,Source::Angular);assert!(p.frame(1.22).x<0.);
        for n in 123..250{p.frame(n as f64/100.);}assert_eq!(p.frame(2.5),Point::default());
    }
    #[test]fn frame_uses_one_movement_source_instead_of_double_counting_a_tilt(){
        let mut p=Intent::default();for n in 0..121{p.sample(raw(n),n as f64/100.);}
        let mut s=raw(121);s.accel_mg[0]=100.;s.gyro_dps[2]=20.;p.sample(s,1.21);
        assert_eq!(p.source,Source::Angular);assert_eq!(p.desktop.state.velocity_mps,[0.;2]);
    }
}
