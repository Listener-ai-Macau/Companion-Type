//! Platform click-stability adapter. Raw acceleration reaches this before the
//! fused gyro from the same packet. Quarantine a shock and its short rebound,
//! instead of interpreting that angular motion as an intentional mouse stroke.
//! Gyro-off during clicks is the established remote-control clutch pattern;
//! the shock/quiet thresholds here are Companion-specific, not GRT/Fusion.
use super::{desktop::Raw,Point};
use std::collections::VecDeque;
#[derive(Default)]
pub struct TapMotion {
    last:Option<Raw>,impact:Option<u32>,quiet:u32,
    rates:VecDeque<(u32,Point,f64)>,
    ready:Option<(Point,f64)>,
}
impl TapMotion {
    pub fn clear(&mut self){*self=Self::default();}
    pub fn clear_rates(&mut self){self.rates.clear();self.ready=None;}
    pub fn blocked(&self)->bool{self.impact.is_some()}
    pub fn observe(&mut self,s:Raw){
        if self.last.is_some_and(|p|{let n=s.sequence.wrapping_sub(p.sequence);n==0||n>=0x8000_0000}){return;}
        let previous=self.last.replace(s);let Some(p)=previous else{return;};
        let elapsed=s.sensor_ms.wrapping_sub(p.sensor_ms);
        if elapsed==0||elapsed>50{self.impact=None;self.clear_rates();self.quiet=0;return;}
        let step=s.accel_mg.iter().zip(p.accel_mg).map(|(a,b)|(a-b).powi(2)).sum::<f64>().sqrt();
        if self.impact.is_none()&&step>=500.{self.impact=Some(s.sensor_ms);self.quiet=0;self.clear_rates();}
        if let Some(start)=self.impact{
            // Resume on observed quiet, with a finite escape for a deliberate
            // new movement immediately after a tap. Never wait for old pose.
            let still=step<100.&&s.gyro_dps.iter().map(|v|v*v).sum::<f64>()<100.;
            self.quiet=if still{self.quiet+elapsed}else{0};
            if self.quiet>=30||s.sensor_ms.wrapping_sub(start)>=200{
                self.impact=None;self.quiet=0;self.clear_rates();
            }
        }
    }
    pub fn angular(&mut self,ms:u32,value:Point,dt:f64)->Option<(Point,f64)>{
        if self.blocked(){self.clear_rates();return None;}
        // Two100Hz samples of look-ahead prevent the first impulse reaching
        // the OS before the raw acceleration reveals the contact. This is
        // bounded20ms latency, not a long post-CLICK movement freeze.
        self.rates.push_back((ms,value,dt));
        let mut ready=None;
        while self.rates.front().is_some_and(|(at,_,_)|ms.wrapping_sub(*at)>=20){
            let (_,v,dt)=self.rates.pop_front().unwrap();ready=Some((v,dt));
        }
        while self.rates.len()>8{self.rates.pop_front();}
        if ready.is_some(){self.ready=ready;}
        self.ready
    }
}
#[cfg(test)]mod tests{
 use super::*;
 fn raw(n:u32,a:f64,g:f64)->Raw{Raw{sequence:n,sensor_ms:n*10,accel_mg:[a,0.,1000.],gyro_dps:[g,0.,0.]}}
 #[test]fn a_shock_discards_queued_motion_before_a_delayed_click_and_resumes_at_quiet(){
  let mut s=TapMotion::default();s.observe(raw(1,0.,0.));
  assert!(s.angular(10,Point{x:20.,y:0.},0.01).is_none());
  s.observe(raw(2,900.,100.));assert!(s.blocked());
  assert!(s.angular(20,Point{x:500.,y:500.},0.01).is_none());
  s.observe(raw(3,-900.,-100.));assert!(s.blocked());
  for n in 4..8{s.observe(raw(n,0.,0.));}
  assert!(!s.blocked());
  assert!(s.angular(70,Point{x:2.,y:0.},0.01).is_none());
  assert_eq!(s.angular(90,Point{x:2.,y:0.},0.01).unwrap().0,Point{x:2.,y:0.});
 }
 #[test]fn smooth_rotation_stays_available_and_a_tap_cannot_lock_out_a_new_stroke(){
  let mut s=TapMotion::default();
  for n in 1..50{s.observe(raw(n,0.,80.));let _=s.angular(n*10,Point{x:80.,y:0.},0.01);assert!(!s.blocked());}
  s.observe(raw(50,1000.,200.));assert!(s.blocked());
  for n in 51..71{s.observe(raw(n,1000.,80.));}
  assert!(!s.blocked());s.clear();assert!(!s.blocked());
 }
 #[test]fn uneven_packet_spacing_does_not_insert_zero_rates_after_the_lookahead(){
  let mut s=TapMotion::default();
  for ms in [0,14,22,37,44,52,67,74,82]{
   let result=s.angular(ms,Point{x:8.,y:0.},0.01);
   if ms>=22{assert_eq!(result.unwrap().0,Point{x:8.,y:0.});}
  }
  s.clear_rates();assert!(s.angular(100,Point::default(),0.01).is_none());
 }
}
