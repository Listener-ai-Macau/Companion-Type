//! Experimental IMU-only desktop clutch, host side. Published design basis:
//! ST US7924267B2 and Logitech US20110288805A1: Z motion inhibits XY output.
//! Fusion supplies Earth acceleration; VQF supplies a rest observation.
//! This estimates return to a reference plane, never measures table contact.
//! Thresholds and short vertical integration are Companion platform policy,
//! not claimed upstream mouse code or a general position-tracking solution.
use serde::Serialize;

#[derive(Clone,Copy,Debug,Default,Serialize,PartialEq)]
#[serde(rename_all="camelCase")]
pub enum Phase {#[default] Ready,Lifted,Settling}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct Status {pub phase:Phase,pub height_m:f64,pub vertical_velocity_mps:f64}
#[derive(Default)]
pub struct Surface {
    reference:Option<[f64;3]>,last_ms:Option<u32>,lift_ms:Option<u32>,
    filtered_z:f64,peak:f64,returning:bool,braking:bool,tilt_only:bool,quiet:f64,
    contact_until:Option<u32>,pub status:Status,
}
fn unit(v:[f64;3])->[f64;3]{let n=v.iter().map(|x|x*x).sum::<f64>().sqrt().max(1e-9);v.map(|x|x/n)}
impl Surface {
    pub fn contact(&mut self,ms:u32){
        // A confirmed shell tap may initially look like vertical motion.
        // Cancel only a just-started, small excursion; a tap while already
        // held above the table cannot magically establish table contact.
        if self.status.phase==Phase::Ready||self.lift_ms.is_some_and(|t|ms.wrapping_sub(t)<150&&self.peak<0.03){
            self.reset_stroke();self.contact_until=Some(ms.wrapping_add(150));
        }
    }
    fn reset_stroke(&mut self){
        self.status=Status::default();self.lift_ms=None;self.filtered_z=0.;self.peak=0.;self.returning=false;self.braking=false;self.quiet=0.;self.tilt_only=false;
    }
    pub fn sample(&mut self,ms:u32,z:f64,up:[f64;3],stationary:bool)->bool{
        let elapsed=self.last_ms.map(|last|ms.wrapping_sub(last));self.last_ms=Some(ms);
        let up=unit(up);let reference=*self.reference.get_or_insert(up);
        let dot=reference.iter().zip(up).map(|(a,b)|a*b).sum::<f64>().clamp(-1.,1.);
        let dt=elapsed.map(|ms|ms as f64/1000.).unwrap_or(0.01);
        if dt<=0.||dt>0.05{
            // No unobserved displacement is integrated across a gap. Keep
            // a lifted estimate suspended instead of inventing a landing.
            self.status.vertical_velocity_mps=0.;self.quiet=0.;return false;
        }
        if self.contact_until.is_some_and(|until|(ms.wrapping_sub(until)as i32)<0){return false;}
        self.contact_until=None;
        if self.status.phase==Phase::Ready {
            if z.abs()<0.20&&dot>15_f64.to_radians().cos(){return true;}
            self.status.phase=Phase::Lifted;self.lift_ms=Some(ms);self.tilt_only=z.abs()<0.20;
            // Continue the filter from measured rest (zero residual), rather
            // than seeding it with the first acceleration peak. Peak seeding
            // adds a false impulse~a*tau and left16mm after a closed lift.
            self.filtered_z=0.;
        }
        self.filtered_z+=(z-self.filtered_z)*(dt/(0.02+dt));
        let old=self.status.vertical_velocity_mps;
        if old*self.filtered_z<0.&&self.filtered_z.abs()>0.10{self.braking=true;}
        let velocity=old+self.filtered_z*dt;
        self.status.height_m+=(old+velocity)*0.5*dt;
        self.status.vertical_velocity_mps=velocity;
        self.peak=self.peak.max(self.status.height_m);
        if self.status.height_m<self.peak-0.004&&velocity< -0.01{self.returning=true;}
        if stationary&&(self.braking||velocity.abs()<0.01){self.status.vertical_velocity_mps=0.;self.braking=false;}
        // A brief vertical desk impulse is not a completed lift. The actual
        //147 trace settled at0.64mm with zero vertical velocity, but could
        // never satisfy the4mm return-direction test and stayed suspended.
        // Reuse that same4mm excursion boundary to rearm an unconfirmed
        // impulse after observed rest. A confirmed lift retains its height
        // and still requires a return; quiet airborne input alone is not it.
        let transient=self.peak<0.004&&self.status.height_m.abs()<0.004&&!self.tilt_only;
        let near_plane=self.status.height_m.abs()<0.015&&(self.returning||self.tilt_only||transient);
        let aligned=dot>8_f64.to_radians().cos();
        let old_enough=self.lift_ms.is_some_and(|t|ms.wrapping_sub(t)>=if transient{120}else{600});
        if old_enough&&near_plane&&aligned&&stationary{
            self.status.phase=Phase::Settling;self.quiet+=dt;
            if self.quiet>=0.20{self.reset_stroke();return true;}
        }else{self.status.phase=Phase::Lifted;self.quiet=0.;}
        false
    }
}
#[cfg(test)]mod tests{
 use super::*;
 #[test]fn a_level_lift_hold_return_suppresses_xy_until_the_return_is_still(){
  let mut s=Surface::default();let up=[0.,0.,1.];let mut n=0u32;
  for _ in 0..100{assert!(s.sample(n*10,0.,up,true));n+=1;}
  // Coherent short lift: accelerate, coast, brake, hold flat in the air.
  for (count,z,rest) in [(15,1.,false),(20,0.,false),(15,-1.,false),(100,0.,true)]{
   for _ in 0..count{assert!(!s.sample(n*10,z,up,rest));n+=1;}
  }
  assert!(s.status.height_m>0.04,"holding flat in the air is not a table landing: {:?}",s.status);
  assert!((s.status.height_m-0.0525).abs()<0.002,"balanced short lift has a known endpoint, got {:?}",s.status);
  for (count,z)in[(15,-1.),(20,0.),(15,1.)]{for _ in 0..count{assert!(!s.sample(n*10,z,up,false));n+=1;}}
  let mut ready=false;for _ in 0..100{ready=s.sample(n*10,0.,up,true);n+=1;}
  assert!(ready,"return to the original plane must rearm: {:?}",s.status);
 }
 #[test]fn a_confirmed_contact_does_not_become_a_lift_or_change_the_plane(){
  let mut s=Surface::default();assert!(s.sample(0,0.,[0.,0.,1.],true));
  assert!(!s.sample(10,20.,[0.,0.,1.],false));s.contact(20);
  assert_eq!(s.status.phase,Phase::Ready);assert_eq!(s.status.height_m,0.);
  assert!(!s.sample(30,0.,[0.,0.,1.],true));assert!(s.sample(180,0.,[0.,0.,1.],true)==false); // gap does not integrate
  assert!(s.sample(190,0.,[0.,0.,1.],true));
 }
 #[test]fn horizontal_motion_keeps_the_plane_and_a_tilt_suspends_it(){
  let mut s=Surface::default();for n in 0..100{assert!(s.sample(n*10,0.,[0.,0.,1.],false));}
  let a=25_f64.to_radians();assert!(!s.sample(1000,0.,[a.sin(),0.,a.cos()],false));
  for n in 101..150{assert!(!s.sample(n*10,0.,[a.sin(),0.,a.cos()],true));}
  let mut ready=false;for n in 150..200{ready=s.sample(n*10,0.,[0.,0.,1.],true);}assert!(ready);
 }
 #[test]fn a_short_vertical_desk_impulse_rearms_without_a_hardware_tap(){
  let mut s=Surface::default();let up=[0.,0.,1.];assert!(s.sample(0,0.,up,true));
  assert!(!s.sample(10,-0.25,up,false));assert!(!s.sample(20,0.35,up,false));
  let mut ready=false;for n in 3..80{ready=s.sample(n*10,0.,up,true);}
  assert!(ready,"an unconfirmed impulse cannot wait forever for a4mm return: {:?}",s.status);
 }
 #[test]fn a_confirmed_small_lift_is_not_rearmed_by_holding_it_quietly_in_the_air(){
  let mut s=Surface::default();let up=[0.,0.,1.];assert!(s.sample(0,0.,up,true));let mut n=1;
  for (count,z,rest)in[(6,1.,false),(10,0.,false),(6,-1.,false),(100,0.,true)]{
   for _ in 0..count{assert!(!s.sample(n*10,z,up,rest));n+=1;}
  }
  assert!(s.status.height_m>0.007&&s.status.height_m<0.015,"known9.6mm lift {:?}",s.status);
 }
}
