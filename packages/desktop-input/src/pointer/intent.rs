//! Planar-only relative control. No metric position-tracking claim.
//! Gyroscope samples serve gravity compensation, never cursor steering.
//! The causal Fusion desktop adapter remains experimental; AirCursor supplies
//! frame smoothing only, not a claimed upstream translation algorithm.
use super::{desktop::{Desktop,Raw},Mapping,Point,Settings,Smoother};
use serde::Serialize;
#[derive(Clone,Copy,Debug,Default,Serialize,PartialEq)]
pub enum Source {#[default] Rest,Translation}
pub struct Intent {
    pub desktop:Desktop,pub source:Source,pub settings:Settings,
    smoother:Smoother,at:Option<f64>,last:Option<(u32,u32,f64)>,
}
impl Default for Intent {
    fn default()->Self{Self{desktop:Desktop::coarse_gestures(),source:Source::Rest,settings:Settings{mapping:Mapping::Relative,..Settings::default()},
        smoother:Smoother::default(),at:None,last:None}}
}
impl Intent {
    pub fn surface_mouse()->Self{Self{desktop:Desktop::surface_mouse(),..Self::default()}}
    pub fn clear_motion(&mut self){
        self.desktop.pause_translation();self.smoother.reset();self.source=Source::Rest;self.at=None;
    }
    pub fn tap(&mut self){
        self.clear_motion();self.desktop.tap();
    }
    pub fn contact(&mut self,ms:u32){self.clear_motion();self.desktop.contact(ms);}
    pub fn sample(&mut self,s:Raw,now:f64){
        self.sample_blocked(s,now,false);
    }
    pub fn sample_blocked(&mut self,s:Raw,now:f64,blocked:bool){
        self.sample_blocked_gravity(s,now,blocked,None);
    }
    pub fn sample_blocked_gravity(&mut self,s:Raw,now:f64,blocked:bool,gravity:Option<[f64;3]>){
        if let Some((sequence,ms,arrival))=self.last{
            let n=s.sequence.wrapping_sub(sequence);
            if n==0||n>=0x8000_0000{return;}
            let dt=s.sensor_ms.wrapping_sub(ms)as f64/1000.;
            if n!=1||dt<=0.||dt>0.05||now-arrival>0.12{
                // A missing interval cannot justify continued displacement.
                self.smoother.reset();self.at=Some(now);
            }
        }
        self.last=Some((s.sequence,s.sensor_ms,now));
        self.desktop.sample_with_gravity(s,!blocked,gravity);
        let state=&self.desktop.state;
        if !state.calibrated{self.smoother.reset();self.source=Source::Rest;return;}
        let (mut goal,source)=if state.moving&&!state.clutched {
                // Gain controls feel, not a calibrated mm-to-pixel contract.
                (Point{x:(state.velocity_mps[0]*5000.*self.settings.sensitivity).clamp(-1000.,1000.),y:(-state.velocity_mps[1]*5000.*self.settings.sensitivity).clamp(-1000.,1000.)},Source::Translation)
            }else{(Point::default(),Source::Rest)};
        // A recognised rest/tap/lift must not leave an old interpolation tail
        // moving the cursor. No angular fallback is allowed in this mode.
        if source==Source::Rest{self.smoother.reset();}
        if self.settings.invert_horizontal{goal.x = -goal.x;}
        if self.settings.invert_vertical{goal.y = -goal.y;}
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
    fn ready()->Intent{let mut p=Intent::default();for n in 0..121{p.sample(raw(n),n as f64/100.);p.frame(n as f64/100.);}p}
    #[test]fn rotation_alone_cannot_steer_a_planar_session(){
        let mut p=ready();
        for n in 121..221{let mut s=raw(n);s.gyro_dps[2]=20.;p.sample(s,n as f64/100.);
            assert_eq!(p.source,Source::Rest);assert_eq!(p.frame(n as f64/100.),Point::default());}
    }
    #[test]fn incidental_rotation_cannot_replace_a_translation_with_angular_control(){
        let mut p=ready();let mut s=raw(121);s.accel_mg[0]=100.;s.gyro_dps[2]=4.;p.sample(s,1.21);
        assert_eq!(p.source,Source::Translation);assert!(p.desktop.state.velocity_mps[0]>0.);
        assert!(p.frame(1.22).x>0.);
    }
    #[test]fn gap_cancels_the_old_stroke_instead_of_falling_back_to_current_gyro(){
        let mut p=ready();let mut s=raw(121);s.accel_mg[0]=100.;p.sample(s,1.21);assert!(p.frame(1.22).x>0.);
        let mut s=raw(200);s.gyro_dps[2]=-20.;p.sample(s,2.);
        assert_eq!(p.frame(2.),Point::default());assert_eq!(p.frame(2.01),Point::default());
        assert!(p.desktop.state.clutched);assert_eq!(p.desktop.state.velocity_mps,[0.;2]);
    }
    #[test]fn duplicate_packets_cannot_keep_an_old_turn_alive(){
        let mut p=ready();let mut s=raw(121);s.accel_mg[0]=100.;p.sample(s,1.21);p.frame(1.22);
        for n in 123..250{let at=n as f64/100.;p.sample(s,at);p.frame(at);}
        assert_eq!(p.frame(2.5),Point::default());
    }
    #[test]fn tap_stops_translation_and_pending_smoothing(){
        let mut p=ready();let mut s=raw(121);s.accel_mg[0]=100.;p.sample(s,1.21);p.frame(1.22);p.tap();
        assert_eq!(p.source,Source::Rest);assert_eq!(p.frame(1.23),Point::default());
        assert!(p.desktop.state.clutched);assert_eq!(p.desktop.state.velocity_mps,[0.;2]);
    }
    #[test]fn planar_diagonal_acceleration_keeps_direction_across_different_amplitudes(){
        for strength in [30.,80.,150.]{
            let mut p=ready();let mut s=raw(121);s.accel_mg=[strength,-strength*0.7,1000.];p.sample(s,1.21);
            let delta=p.frame(1.22);assert!(delta.x>0.&&delta.y>0.);
        }
    }
}
