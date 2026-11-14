//! IMU desktop lift clutch, not absolute height/contact estimation.
//! Published basis: Logitech US20110288805A1 Fig5 inhibits XY on Z motion.
//! Owner permits a few-second lift pause. Companion uses a2s minimum pause
//! plus observed rest; it cannot prove physical table contact in mid-air.
//! The rejected147149150 height-gate implementation/evidence remains in Git.
use serde::Serialize;
pub const LIFT_PAUSE_MS:u32=2000;
#[derive(Clone,Copy,Debug,Default,Serialize,PartialEq)]
#[serde(rename_all="camelCase")]
pub enum Phase {#[default] Ready,Lifted,Settling}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Status {pub phase:Phase}
#[derive(Default)]
pub struct Surface {
    reference:Option<[f64;3]>,last_ms:Option<u32>,lift_ms:Option<u32>,
    filtered_z:f64,candidate:f64,quiet:f64,contact_until:Option<u32>,pub status:Status,
}
fn unit(v:[f64;3])->[f64;3]{let n=v.iter().map(|x|x*x).sum::<f64>().sqrt().max(1e-9);v.map(|x|x/n)}
impl Surface {
    pub fn contact(&mut self,ms:u32){
        // Keep the accepted143 tap isolation. A short tap can initially look
        // like lift onset; a much older pause is not silently cancelled.
        if self.status.phase==Phase::Ready||self.lift_ms.is_some_and(|t|ms.wrapping_sub(t)<150){
            self.reset_stroke();self.contact_until=Some(ms.wrapping_add(150));
        }
    }
    fn reset_stroke(&mut self){self.status=Status::default();self.lift_ms=None;self.filtered_z=0.;self.candidate=0.;self.quiet=0.;}
    pub fn reanchor_if_ready(&mut self,up:[f64;3]){if self.status.phase==Phase::Ready{self.reference=Some(unit(up));self.filtered_z=0.;self.candidate=0.;}}
    pub fn sample(&mut self,ms:u32,z:f64,up:[f64;3],stationary:bool)->bool{self.sample_with_planar(ms,z,0.,up,stationary)}
    pub fn sample_with_planar(&mut self,ms:u32,z:f64,planar:f64,up:[f64;3],stationary:bool)->bool{
        let elapsed=self.last_ms.map(|last|ms.wrapping_sub(last));self.last_ms=Some(ms);
        let up=unit(up);let reference=*self.reference.get_or_insert(up);
        let dot=reference.iter().zip(up).map(|(a,b)|a*b).sum::<f64>().clamp(-1.,1.);
        let dt=elapsed.map(|n|n as f64/1000.).unwrap_or(0.01);
        if dt<=0.||dt>0.05{self.filtered_z=0.;self.candidate=0.;self.quiet=0.;self.reanchor_if_ready(up);return false;}
        if self.contact_until.is_some_and(|until|(ms.wrapping_sub(until)as i32)<0){return false;}self.contact_until=None;
        self.filtered_z+=(z-self.filtered_z)*(dt/(0.02+dt));
        // Horizontal sliding often includes a small vertical component. A
        // brief non-dominant Z bump is not a measured lift. Confirm vertical
        // dominance for20ms; raw tap isolation independently holds the cursor.
        let vertical=self.filtered_z.abs()>0.20&&self.filtered_z.abs()>planar;
        let vertical_impulse=z.abs()>0.20&&z.abs()>planar;
        if self.status.phase==Phase::Ready {
            self.candidate=if vertical{self.candidate+dt}else{0.};
            if self.candidate<0.02&&dot>15_f64.to_radians().cos(){return !(vertical||vertical_impulse);}
            self.status.phase=Phase::Lifted;self.lift_ms=Some(ms);self.quiet=0.;
        }
        if stationary{self.quiet+=dt;self.status.phase=Phase::Settling;}else{self.quiet=0.;self.status.phase=Phase::Lifted;}
        if self.lift_ms.is_some_and(|t|ms.wrapping_sub(t)>=LIFT_PAUSE_MS)&&self.quiet>=0.20{
            self.reference=Some(up);self.reset_stroke();return true;
        }
        false
    }
}
#[cfg(test)]mod tests{
 use super::*;
 #[test]fn horizontal_strokes_with_vertical_cross_axis_motion_are_not_locked_out(){
  let mut s=Surface::default();for n in 0..150{assert!(s.sample_with_planar(n*10,0.25,0.6,[0.,0.,1.],false));}
  assert_eq!(s.status.phase,Phase::Ready);
 }
 #[test]fn a_single_vertical_impulse_does_not_create_an_endless_lift(){
  let mut s=Surface::default();s.sample(0,0.,[0.,0.,1.],true);
  assert!(!s.sample(10,0.7,[0.,0.,1.],false));
  let mut ready=false;for n in 2..80{ready=s.sample(n*10,0.,[0.,0.,1.],true);}assert!(ready);
 }
 #[test]fn a_lift_pauses_for_two_seconds_then_observed_rest_rearms(){
  let mut s=Surface::default();let up=[0.,0.,1.];s.sample(0,0.,up,true);
  for n in 1..30{assert!(!s.sample(n*10,1.,up,false));}
  for n in 30..200{assert!(!s.sample(n*10,0.,up,true));}
  let mut ready=false;for n in 200..250{ready=s.sample(n*10,0.,up,true);}assert!(ready);
 }
 #[test]fn changing_the_resting_pose_does_not_require_an_old_estimated_height(){
  let mut s=Surface::default();s.sample(0,0.,[0.,0.,1.],true);
  let a=25_f64.to_radians();let up=[a.sin(),0.,a.cos()];assert!(!s.sample(10,0.,up,false));
  let mut ready=false;for n in 2..250{ready=s.sample(n*10,0.06,up,true);}assert!(ready);
  for n in 250..300{assert!(s.sample(n*10,0.06,up,true));}
 }
 #[test]fn a_confirmed_contact_preserves_the_tap_and_double_tap_target(){
  let mut s=Surface::default();s.sample(0,0.,[0.,0.,1.],true);s.sample(10,20.,[0.,0.,1.],false);s.contact(20);
  assert_eq!(s.status.phase,Phase::Ready);assert!(!s.sample(30,0.,[0.,0.,1.],true));
  let mut ready=false;for n in 4..40{ready=s.sample(n*10,0.,[0.,0.,1.],true);}assert!(ready);
 }
}
