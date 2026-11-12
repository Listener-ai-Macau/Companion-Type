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
    fn ready()->Intent{let mut p=Intent::default();for n in 0..121{p.sample(raw(n),n as f64/100.);p.frame(n as f64/100.);}p}
    #[test]fn reversed_turn_after_radio_gap_uses_current_direction_without_a_catchup_jump(){
        let mut p=ready();let mut s=raw(121);s.gyro_dps[2]=40.;p.sample(s,1.21);assert!(p.frame(1.22).x<0.);
        let mut s=raw(200);s.gyro_dps[2]=-20.;p.sample(s,2.);
        assert_eq!(p.frame(2.),Point::default());assert!(p.frame(2.01).x>0.);
        assert!(p.desktop.state.clutched);assert_eq!(p.desktop.state.velocity_mps,[0.;2]);
    }
    #[test]fn duplicate_packets_cannot_keep_an_old_turn_alive(){
        let mut p=ready();let mut s=raw(121);s.gyro_dps[2]=20.;p.sample(s,1.21);p.frame(1.22);
        for n in 123..250{let at=n as f64/100.;p.sample(s,at);p.frame(at);}
        assert_eq!(p.frame(2.5),Point::default());
    }
    #[test]fn tap_stops_both_motion_paths_and_pending_smoothing(){
        let mut p=ready();let mut s=raw(121);s.gyro_dps[2]=20.;p.sample(s,1.21);p.frame(1.22);p.tap();
        assert_eq!(p.source,Source::Rest);assert_eq!(p.frame(1.23),Point::default());
        assert!(p.desktop.state.clutched);assert_eq!(p.desktop.state.velocity_mps,[0.;2]);
    }
    #[test]fn natural_diagonal_turns_keep_direction_across_different_amplitudes(){
        for strength in [8.,20.,55.]{
            let mut p=ready();let mut s=raw(121);s.gyro_dps=[-strength,0.,strength*0.7];p.sample(s,1.21);
            let delta=p.frame(1.22);assert!(delta.x<0.&&delta.y>0.);
        }
    }
}
