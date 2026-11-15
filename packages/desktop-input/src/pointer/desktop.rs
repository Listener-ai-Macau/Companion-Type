//! Existing-hardware desktop feasibility core. No OS input, disk or BLE.
//! Ready CIM6 can reuse upstream x-io Fusion for gyro pose propagation within
//! a stroke. Board pose seeds gaps; accelerometer correction is gated during
//! translation. Older callers retain the gravity-only/CIM5 adapters.
//! Causal stroke integration/zero-velocity decisions are Companion adapters;
//! the upstream Gait-Tracking end-of-stroke interpolation is NONCAUSAL and is
//! deliberately not represented as a real-time mouse implementation.
use super::{fusion,rest,surface,Point};
use serde::Serialize;
// Existing rest/braking tolerance, also used when deciding whether there is
// an established stroke worth preserving through an unconfirmed Z bump.
const NEGLIGIBLE_SPEED_MPS:f64=0.005;

#[derive(Clone,Copy,Debug)]
pub struct Raw {pub sequence:u32,pub sensor_ms:u32,pub accel_mg:[f64;3],pub gyro_dps:[f64;3]}
impl Raw {
    pub fn parse(p:&[u8])->Result<Self,&'static str>{
        if p.len()<32||&p[..4]!=b"CIM1"||!matches!(p[4],5|6)||p.len()!=if p[4]==6{40}else{32}||p[5]!=3||p[6]&!3!=0||(p[4]==6&&p[34..36]!=[0,0]){return Err("invalid raw CIM5/6");}
        let mut crc=0xffff_ffffu32;
        let crc_at=p.len()-4;
        for byte in &p[..crc_at]{crc^=*byte as u32;for _ in 0..8{crc=(crc>>1)^((0u32.wrapping_sub(crc&1))&0xedb8_8320);}}
        if !crc!=u32::from_le_bytes(p[crc_at..].try_into().unwrap()){return Err("raw CRC mismatch");}
        let value=|i|i16::from_le_bytes(p[i..i+2].try_into().unwrap())as f64;
        Ok(Self{sequence:u32::from_le_bytes(p[8..12].try_into().unwrap()),sensor_ms:u32::from_le_bytes(p[12..16].try_into().unwrap()),
            accel_mg:std::array::from_fn(|i|value((if p[4]==6{28}else{16})+2*i)),gyro_dps:std::array::from_fn(|i|value(22+2*i)/100.)})
    }
}
#[derive(Clone,Debug,Default,Serialize)]
#[serde(rename_all="camelCase")]
pub struct State {pub calibrated:bool,pub moving:bool,pub clutched:bool,pub stationary:bool,pub board_gravity:bool,pub pose_prediction:bool,pub translation_inhibited:bool,pub gaps:u64,pub samples:u64,pub velocity_mps:[f64;2],pub position_m:[f64;2],pub linear_mps2:[f64;3],pub gyro_dps:[f64;3],pub surface:Option<surface::Status>}
pub struct Desktop {
    fusion:fusion::Fusion,rest:Option<rest::Rest>,last:Option<(u32,u32)>,count:u32,start_ms:Option<u32>,
    accel_sum:[f64;3],gyro_sum:[f64;3],gyro_bias:[f64;3],earth_bias:[f64;3],
    filtered:[f64;2],quiet:f64,stroke:f64,braking:bool,
    surface:Option<surface::Surface>,reacquire_plane:bool,
    predict_board_pose:bool,reanchor_after_contact:bool,
    pub state:State,
}
impl Default for Desktop {
    fn default()->Self{Self{fusion:fusion::Fusion::default(),rest:None,last:None,count:0,start_ms:None,accel_sum:[0.;3],gyro_sum:[0.;3],gyro_bias:[0.;3],earth_bias:[0.;3],filtered:[0.;2],quiet:0.,stroke:0.,braking:false,surface:None,reacquire_plane:false,predict_board_pose:false,reanchor_after_contact:false,state:State::default()}}
}
fn board_acceleration(accel:[f64;3],gravity:[f64;3])->Option<([f64;3],[f64;3])>{
    let dot=|a:[f64;3],b:[f64;3]|a.iter().zip(b).map(|(x,y)|x*y).sum::<f64>();
    let norm=dot(gravity,gravity).sqrt();if !norm.is_finite()||norm<500.||norm>1500.{return None;}
    let up=gravity.map(|x|x/norm);
    // Project the card's X direction onto the horizontal plane. Type-C is
    // the fixed forward direction; no unobserved gyro/yaw is integrated on
    // the host. The board has already performed the actual AHRS calculation.
    let x=[1.-up[0]*up[0],-up[0]*up[1],-up[0]*up[2]];let n=dot(x,x).sqrt();if n<0.1{return None;}
    let x=x.map(|v|v/n);let y=[up[1]*x[2]-up[2]*x[1],up[2]*x[0]-up[0]*x[2],up[0]*x[1]-up[1]*x[0]];
    Some(([dot(accel,x)*0.00980665,dot(accel,y)*0.00980665,dot(accel,up)*0.00980665-9.80665],up))
}
impl Desktop {
    /// Coarse short-stroke mouse candidate, rather than metric dead reckoning.
    /// Rest confirmation deliberately discards sustained quiet coasting. Keep
    /// Default's reference integrator for explicit constant-velocity analysis.
    pub fn coarse_gestures()->Self{Self{rest:Some(rest::Rest::default()),..Self::default()}}
    pub fn surface_mouse()->Self{Self{surface:Some(surface::Surface::default()),..Self::coarse_gestures()}}
    /// Native CIM6 opts in only after its explicit device-ready flag. Do not
    /// propagate uncalibrated rates merely because a gravity vector exists.
    pub fn enable_board_pose_prediction(&mut self){self.predict_board_pose=true;}
    pub fn has_surface(&self)->bool{self.surface.is_some()}
    pub fn contact(&mut self,ms:u32){if let Some(surface)=self.surface.as_mut(){
        surface.contact(ms);
        if self.state.pose_prediction{
            // The accepted tap guard already freezes the target for a bounded
            // interval. Requiring another stationary interval here latched
            // Owner158 out while trying to move immediately after a click.
            self.stop();self.state.clutched=false;self.reanchor_after_contact=true;
        }else{self.clutch();}
    }else{self.tap();}}
    fn stop(&mut self){self.state.moving=false;self.state.velocity_mps=[0.;2];self.filtered=[0.;2];self.quiet=0.;self.stroke=0.;self.braking=false;}
    fn clutch(&mut self){self.stop();self.state.clutched=true;self.count=0;self.accel_sum=[0.;3];self.gyro_sum=[0.;3];}
    pub fn tap(&mut self){self.clutch();}
    pub fn pause_translation(&mut self){self.stop();}
    pub fn sample(&mut self,s:Raw)->Point {self.sample_with_translation(s,true)}
    pub fn sample_with_translation(&mut self,s:Raw,allow_translation:bool)->Point {
        self.sample_with_gravity(s,allow_translation,None)
    }
    pub fn sample_with_gravity(&mut self,s:Raw,allow_translation:bool,gravity:Option<[f64;3]>)->Point {
        self.state.translation_inhibited=true;
        let board=gravity.and_then(|g|board_acceleration(s.accel_mg,g));
        self.state.board_gravity=board.is_some();
        self.state.pose_prediction=self.predict_board_pose&&board.is_some();
        if gravity.is_some()&&board.is_none(){self.clutch();return Point::default();}
        let dt=if let Some((sequence,ms))=self.last{
            let n=s.sequence.wrapping_sub(sequence);
            if n==0||n>=0x8000_0000{return Point::default();}
            let dt=s.sensor_ms.wrapping_sub(ms)as f64/1000.;
            if n!=1||dt>0.05||dt<=0.{
                if let Some(rest)=self.rest.as_mut(){*rest=rest::Rest::default();}self.state.stationary=false;
                self.state.gaps+=1;self.stop();self.last=Some((s.sequence,s.sensor_ms));
                if let Some((_,up))=board.filter(|_|self.state.calibrated){
                    // The board's current absolute gravity remains usable
                    // despite a missing BLE interval. Drop old XY velocity;
                    // do not demand a new stationary calibration each time.
                    self.state.clutched=false;self.reacquire_plane=false;
                    if self.predict_board_pose{self.fusion.align(up.map(|v|v*1000.));}
                    if let Some(surface)=self.surface.as_mut(){surface.reanchor_if_ready(up);}
                }else{self.clutch();if self.surface.is_some(){self.reacquire_plane=true;}}
                // A gap invalidates displacement integration, not the CURRENT
                // rate observation. The coarse angular path must never reuse
                // the rate from before the gap as this sample's direction.
                self.state.gyro_dps=std::array::from_fn(|i|s.gyro_dps[i]-self.gyro_bias[i]);
                if !self.state.calibrated{self.start_ms=None;}
                return Point::default();
            }
            dt
        }else{0.01};
        self.last=Some((s.sequence,s.sensor_ms));self.state.samples+=1;
        // CIM6 supplies gravity independently of this receive stream. Its
        // gyro offset can still be adapting at entry; do not make an
        // accelerometer-only mouse wait for another gyro calibration.
        let rest_gyro=if board.is_some(){[0.;3]}else{s.gyro_dps};
        self.state.stationary=self.rest.as_mut().is_some_and(|rest|rest.sample(rest_gyro,s.accel_mg));
        let norm=s.accel_mg.iter().map(|x|x*x).sum::<f64>().sqrt();
        if !self.state.calibrated {
            if !(850. ..=1150.).contains(&norm)||(if board.is_some(){!self.state.stationary}else{s.gyro_dps.iter().any(|x|x.abs()>3.)}){
                self.start_ms=None;self.count=0;self.accel_sum=[0.;3];self.gyro_sum=[0.;3];return Point::default();
            }
            let start=*self.start_ms.get_or_insert(s.sensor_ms);self.count+=1;
            for i in 0..3{self.accel_sum[i]+=s.accel_mg[i];self.gyro_sum[i]+=s.gyro_dps[i];}
            let ready=if board.is_some(){s.sensor_ms.wrapping_sub(start)>=200&&self.count>=20}else{s.sensor_ms.wrapping_sub(start)>=1000&&self.count>=80};
            if !ready{return Point::default();}
            let accel=self.accel_sum.map(|x|x/self.count as f64);
            if let Some(g)=gravity{
                if self.predict_board_pose{
                    // Ready CIM6 already carries the board's corrected rates.
                    // Its offset keeps adapting; a second fixed host offset
                    // turns that correction into a fictitious rotation.
                    self.gyro_bias=[0.;3];self.fusion.align(accel);
                    self.earth_bias=self.fusion.desktop_step([0.;3],accel,dt,true).0;
                }else{self.gyro_bias=[0.;3];self.earth_bias=board_acceleration(accel,g).unwrap().0;}
            }else{
                self.gyro_bias=self.gyro_sum.map(|x|x/self.count as f64);self.fusion.align(accel);
                self.earth_bias=self.fusion.desktop_step([0.;3],accel,dt,true).0;
            }
            self.state.calibrated=true;self.stop();return Point::default();
        }
        let rates=std::array::from_fn(|i|s.gyro_dps[i]-self.gyro_bias[i]);
        self.state.gyro_dps=rates;
        let on_plane=self.surface.as_ref().is_none_or(|s|s.status.phase==surface::Phase::Ready);
        // Constant linear acceleration can pass a variance-only rest test.
        // Never learn that force as gravity during a lifted reposition.
        let small_force=self.state.linear_mps2.iter().map(|v|v*v).sum::<f64>()<0.055f64.powi(2);
        let correction=if self.surface.is_some(){small_force&&(self.state.stationary||(!self.state.moving&&on_plane))}else{self.state.stationary||!self.state.moving};
        // A body-fixed plane (rejected Owner158) turns a natural grip rotation
        // into apparent XY/Z acceleration. Reuse the existing upstream gyro
        // propagation instead; its accelerometer correction is off while a
        // translational force is present. No invented position/height fusion.
        let (earth,up)=if self.state.pose_prediction{self.fusion.desktop_step(rates,s.accel_mg,dt,correction)}
            else{board.unwrap_or_else(||self.fusion.desktop_step(rates,s.accel_mg,dt,correction))};
        let linear=std::array::from_fn(|i|earth[i]-self.earth_bias[i]);self.state.linear_mps2=linear;
        let surface_ready=if self.state.clutched{false}else if let Some(surface)=self.surface.as_mut(){
            let allowed=surface.sample_with_planar(s.sensor_ms,linear[2],linear[0].hypot(linear[1]),up,self.state.stationary);
            self.state.surface=Some(surface.status.clone());allowed
        }else{true};
        self.state.translation_inhibited=!allow_translation||!surface_ready;
        if self.state.clutched {
            // Natural use can put the card back at a different angle. Waiting
            // for the OLD gravity plane/residual to become quiet locks it out.
            // Re-arm from stable raw observations at the NEW resting pose.
            let stable=(850. ..=1150.).contains(&norm)&&(board.is_some()||rates.iter().all(|x|x.abs()<2.))&&
                (self.count==0||(0..3).all(|i|(s.accel_mg[i]-self.accel_sum[i]/self.count as f64).abs()<15.));
            if !stable{self.count=0;self.accel_sum=[0.;3];self.gyro_sum=[0.;3];self.quiet=0.;return Point::default();}
            self.count+=1;self.quiet+=dt;
            for i in 0..3{self.accel_sum[i]+=s.accel_mg[i];self.gyro_sum[i]+=s.gyro_dps[i];}
            let settled=if self.surface.is_some(){self.quiet>=0.12&&self.count>=8}else{self.quiet>=0.3&&self.count>=20};
            if settled{
                let accel=self.accel_sum.map(|x|x/self.count as f64);
                if let Some(g)=gravity{
                    if self.predict_board_pose{self.gyro_bias=[0.;3];self.fusion.align(accel);self.earth_bias=self.fusion.desktop_step([0.;3],accel,dt,true).0;}
                    else{self.gyro_bias=[0.;3];self.earth_bias=board_acceleration(accel,g).unwrap().0;}
                }
                else{self.gyro_bias=self.gyro_sum.map(|x|x/self.count as f64);self.fusion.align(accel);self.earth_bias=self.fusion.desktop_step([0.;3],accel,dt,true).0;}
                if self.reacquire_plane{
                    // A missing interval invalidates height, not the board's
                    // current fused gravity. Reacquire from actual observed
                    // rest instead of demanding a return to an invented1.4m.
                    self.surface=self.surface.as_ref().map(|_|surface::Surface::default());
                    self.state.surface=self.surface.as_ref().map(|s|s.status.clone());self.reacquire_plane=false;
                }
                self.state.clutched=false;self.stop();
            }
            return Point::default();
        }
        if !allow_translation{self.stop();return Point::default();}
        if !surface_ready{
            // Actual159:109/124 moving-to-stop edges were unconfirmed Z
            // shocks while the lift phase was still Ready. Suppress that
            // sample's output, but retain the stroke velocity so ordinary
            // table vibration cannot force a slow restart every other tick.
            // Confirmed lift, contact and gaps still discard old motion.
            if self.state.surface.as_ref().is_none_or(|s|s.phase!=surface::Phase::Ready)||
                self.state.velocity_mps[0].hypot(self.state.velocity_mps[1])<NEGLIGIBLE_SPEED_MPS{self.stop();}
            return Point::default();
        }
        if self.reanchor_after_contact&&self.state.pose_prediction{
            // Use the fresh board pose AFTER the shock/target-freeze window,
            // not the impact acceleration. No extra user rest or gyro offset
            // calibration; discard this one transition sample's displacement.
            if let Some((_,up))=board{
                self.fusion.align(up.map(|v|v*1000.));self.reanchor_after_contact=false;
                self.stop();self.state.linear_mps2=[0.;3];return Point::default();
            }
        }
        if self.state.stationary&&(self.surface.is_none()||!self.state.moving||self.braking||self.state.velocity_mps[0].hypot(self.state.velocity_mps[1])<NEGLIGIBLE_SPEED_MPS){
            // Residual gravity/offset is not evidence of continued motion.
            // Confirm rest from raw six-axis deviations independently of the
            // integrated velocity, then discard that residual and old tail.
            let reanchor=self.state.pose_prediction&&(self.state.moving||!on_plane);
            self.stop();
            self.earth_bias=if reanchor{self.fusion.align(s.accel_mg);self.fusion.desktop_step([0.;3],s.accel_mg,dt,true).0}else{earth};
            self.state.linear_mps2=[0.;3];return Point::default();
        }
        // Fusion already rotates acceleration into the Earth frame. Comparing
        // the current tilt to the old resting tilt imposed an unrelated12deg
        // lock and disabled genuine translation during a natural grip change.
        // Earth Z is not used for2D movement. A moderate vertical desk bump
        // must not lock out XY until a fresh resting calibration: raw822 had
        // exactly that failure at9.714s. Retain the existing gross-impact
        // boundary; neither norm nor orientation proves physical table contact.
        if norm<650.||norm>1350. {
            self.clutch();return Point::default();
        }
        let planar=linear[0].hypot(linear[1]);let quiet=planar<0.055&&rates.iter().all(|x|x.abs()<2.);
        if !self.state.moving {
            // Adapt residual bias only while classified at rest, never from
            // the middle of a constant-velocity stroke.
            if quiet{for i in 0..3{self.earth_bias[i]+=(earth[i]-self.earth_bias[i])*(dt/2.).min(1.);}}
            if planar<0.10{return Point::default();}
            self.state.moving=true;self.stroke=0.;self.braking=false;
        }
        // A table user may keep moving for more than two seconds. The old
        // total-stroke deadline then demanded fresh rest/calibration (466
        // clutched frames on the repaired159 replay). Bound only a completely
        // unobserved quiet coast; never latch an active stroke out by duration.
        self.stroke=if self.surface.is_some(){if quiet{self.stroke+dt}else{0.}}else{self.stroke+dt};
        if self.stroke>2.0{if self.surface.is_some(){self.stop();}else{self.clutch();}return Point::default();}
        let old=self.state.velocity_mps;
        for i in 0..2 {
            // Retain20ms noise filtering: removing it made the retained real
            // stationary147/149 trace drift5.08px. Sensor-time output below
            // avoids a second HOST-clock integration without that regression.
            self.filtered[i]+=(linear[i]-self.filtered[i])*(dt/(0.02+dt));
            if old[i]*self.filtered[i]<0.&&self.filtered[i].abs()>0.10{self.braking=true;}
            self.state.velocity_mps[i]=(old[i]+self.filtered[i]*dt).clamp(-0.6,0.6);
        }
        self.quiet=if quiet{self.quiet+dt}else{0.};
        // Rest must follow braking, or have a negligible residual velocity.
        // Quiet acceleration alone cannot distinguish constant speed from rest.
        if self.quiet>=0.12&&(self.braking||self.state.velocity_mps[0].hypot(self.state.velocity_mps[1])<NEGLIGIBLE_SPEED_MPS){
            self.stop();return Point::default();
        }
        let delta=Point{x:(old[0]+self.state.velocity_mps[0])*0.5*dt,y:(old[1]+self.state.velocity_mps[1])*0.5*dt};
        self.state.position_m[0]+=delta.x;self.state.position_m[1]+=delta.y;delta
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn raw(n:u32,x:f64,y:f64)->Raw{Raw{sequence:n+1,sensor_ms:n*10,accel_mg:[x,y,1000.],gyro_dps:[0.;3]}}
    fn ready()->Desktop{let mut d=Desktop::default();for n in 0..=120{d.sample(raw(n,0.,0.));}assert!(d.state.calibrated);d}
    #[test]fn board_corrected_rates_do_not_gain_a_second_offset_at_entry_or_regrip(){
        for regrip in [false,true]{
            let mut d=Desktop::surface_mouse();d.enable_board_pose_prediction();
            let up=Some([0.,0.,1000.]);
            let mut next=0;
            while !d.state.calibrated&&next<150{let mut s=raw(next,0.,0.);s.gyro_dps=[0.4,0.,0.];d.sample_with_gravity(s,true,up);next+=1;}
            assert!(d.state.calibrated);
            if regrip{
                d.tap();let end=next+60;
                while d.state.clutched&&next<end{let mut s=raw(next,0.,0.);s.gyro_dps=[0.3,0.,0.];d.sample_with_gravity(s,true,up);next+=1;}
                assert!(!d.state.clutched);
            }
            // Firmware correction has converged to zero while the user now
            // moves on X. No observed roll can justify cross-axis Y travel.
            for n in next..next+70{d.sample_with_gravity(raw(n,80.,0.),true,up);}
            assert!(d.state.position_m[0]>0.005,"real X stroke must remain available");
            assert!(d.state.position_m[1].abs()<1e-6,"a host-only gyro offset created cross-axis motion: {:?}",d.state.position_m);
        }
    }
    #[test]fn board_gravity_is_used_directly_without_reintegrating_the_received_gyro(){
        let mut d=Desktop::surface_mouse();let up=Some([0.,0.,1000.]);
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        assert!(d.state.calibrated&&d.state.board_gravity);
        for n in 150..200{let mut s=raw(n,0.,0.);s.gyro_dps=[20.,10.,5.];assert_eq!(d.sample_with_gravity(s,true,up),Point::default());}
        assert_eq!(d.state.position_m,[0.;2]);assert!(!d.state.moving);
    }
    #[test]fn table_motion_does_not_turn_fused_gravity_correction_into_cross_axis_translation(){
        let mut d=Desktop::surface_mouse();
        d.enable_board_pose_prediction();
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,Some([0.,0.,1000.]));}
        // A planar acceleration can leak into the AHRS accelerometer
        // correction. The card's fixed supported plane did not tilt. This
        // is a filter-disturbance regression, not labelled Owner direction.
        for n in 150..195{
            let x=if n<165{100.}else if n<180{0.}else{-100.};
            d.sample_with_gravity(raw(n,x,0.),true,Some([0.,(n-150)as f64*2.,1000.]));
        }
        assert!(d.state.position_m[0]>0.02);
        assert!(d.state.position_m[1].abs()<0.001,"gravity correction invented a transverse stroke: {:?}",d.state.position_m);
    }
    #[test]fn ready_board_grip_rotation_is_not_a_translation_or_lift(){
        let mut d=Desktop::surface_mouse();d.enable_board_pose_prediction();
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,Some([0.,0.,1000.]));}
        for n in 150..250{
            let angle=((n-149)as f64*0.2).to_radians();let g=[0.,angle.sin()*1000.,angle.cos()*1000.];
            let mut s=raw(n,0.,0.);s.accel_mg=g;s.gyro_dps=[20.,0.,0.];d.sample_with_gravity(s,true,Some(g));
            assert_eq!(d.state.surface.as_ref().unwrap().phase,surface::Phase::Ready);
        }
        assert!(d.state.pose_prediction);
        assert!(d.state.position_m[0].hypot(d.state.position_m[1])<0.001,"rotation created a fake desk stroke: {:?}",d.state);
    }
    #[test]fn ready_board_contact_does_not_require_the_user_to_stop_moving_again(){
        let mut d=Desktop::surface_mouse();d.enable_board_pose_prediction();let up=Some([0.,0.,1000.]);
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        d.contact(1500);let origin=d.state.position_m;
        for n in 150..165{d.sample_with_gravity(raw(n,80.,0.),true,up);assert_eq!(d.state.position_m,origin);}
        for n in 165..200{d.sample_with_gravity(raw(n,80.,0.),true,up);}
        assert!(!d.state.clutched);assert!(d.state.position_m[0]>origin[0]+0.001,"click left an unbounded rest clutch: {:?}",d.state);
    }
    #[test]fn an_unconfirmed_table_z_bump_holds_output_without_erasing_the_stroke_velocity(){
        let mut d=Desktop::surface_mouse();d.enable_board_pose_prediction();let up=Some([0.,0.,1000.]);
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        for n in 150..170{d.sample_with_gravity(raw(n,80.,0.),true,up);}
        let velocity=d.state.velocity_mps;assert!(velocity[0]>0.01);
        let mut shock=raw(170,0.,0.);shock.accel_mg[2]+=40.;
        assert_eq!(d.sample_with_gravity(shock,true,up),Point::default());
        assert!(d.state.translation_inhibited);assert_eq!(d.state.surface.as_ref().unwrap().phase,surface::Phase::Ready);
        assert_eq!(d.state.velocity_mps,velocity,"an unconfirmed desk bump erased the ongoing stroke");
        let delta=d.sample_with_gravity(raw(171,0.,0.),true,up);
        assert!(delta.x>0.,"coasting after the bump must not require another acceleration onset");
    }
    #[test]fn an_active_table_stroke_does_not_force_recalibration_after_two_seconds(){
        let mut d=Desktop::surface_mouse();d.enable_board_pose_prediction();let up=Some([0.,0.,1000.]);
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        for n in 150..500{
            let x=if (n-150)%40<20{80.}else{-80.};d.sample_with_gravity(raw(n,x,0.),true,up);
            assert!(!d.state.clutched,"an active table stroke was latched out at{n}");
        }
    }
    #[test]fn an_unobservable_long_table_coast_can_end_without_latching_the_next_stroke(){
        let mut d=Desktop::surface_mouse();d.enable_board_pose_prediction();let up=Some([0.,0.,1000.]);
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        for n in 150..170{d.sample_with_gravity(raw(n,80.,0.),true,up);}
        for n in 170..400{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        assert!(!d.state.moving&&!d.state.clutched);
        assert!(d.sample_with_gravity(raw(400,80.,0.),true,up).x>0.);
    }
    #[test]fn board_gravity_entry_learns_rest_without_waiting_for_a_second_gyro_bias(){
        let mut d=Desktop::surface_mouse();
        for n in 0..60{let mut s=raw(n,0.,0.);s.gyro_dps=[4.,-4.,2.];d.sample_with_gravity(s,true,Some([0.,0.,1000.]));}
        assert!(d.state.calibrated&&d.state.board_gravity);assert_eq!(d.state.position_m,[0.;2]);
    }
    #[test]fn fresh_fused_acceleration_after_a_gap_resumes_without_a_new_stationary_second(){
        let mut d=Desktop::surface_mouse();let up=Some([0.,0.,1000.]);
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        for n in 150..160{d.sample_with_gravity(raw(n,80.,0.),true,up);}
        let position=d.state.position_m;assert_eq!(d.sample_with_gravity(raw(300,80.,0.),true,up),Point::default());
        assert!(d.state.calibrated&&!d.state.clutched);assert_eq!(d.state.velocity_mps,[0.;2]);
        d.sample_with_gravity(raw(301,80.,0.),true,up);d.sample_with_gravity(raw(302,80.,0.),true,up);
        assert!(d.state.position_m[0]>position[0]);
    }
    #[test]fn a_fused_planar_stroke_uses_acceleration_and_keeps_a_constant_velocity_section(){
        let mut d=Desktop::surface_mouse();let up=Some([0.,0.,1000.]);
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        let(mut a,mut b)=(0.,0.);
        for n in 150..195{let x=if n<165{100.}else if n<180{0.}else{-100.};d.sample_with_gravity(raw(n,x,0.),true,up);if n==165{a=d.state.position_m[0];}if n==179{b=d.state.position_m[0];}}
        assert!(b-a>0.01);assert!(d.state.position_m[0]>0.02&&d.state.position_m[1].abs()<0.001);
    }
    #[test]fn a_gap_drops_old_velocity_but_keeps_current_board_pose_usable(){
        let mut d=Desktop::surface_mouse();let up=Some([0.,0.,1000.]);
        for n in 0..150{d.sample_with_gravity(raw(n,0.,0.),true,up);}
        for n in 150..165{d.sample_with_gravity(raw(n,100.,0.),true,up);}
        assert!(d.state.moving);
        let mut s=raw(250,0.,0.);s.accel_mg=[260.,0.,965.];d.sample_with_gravity(s,true,Some([260.,0.,965.]));
        assert!(!d.state.clutched);assert_eq!(d.state.velocity_mps,[0.;2]);let position=d.state.position_m;
        for n in 251..351{let mut s=raw(n,0.,0.);s.accel_mg=[260.,0.,965.];d.sample_with_gravity(s,true,Some([260.,0.,965.]));}
        assert!(!d.state.clutched);assert_eq!(d.state.surface.as_ref().unwrap().phase,surface::Phase::Ready);
        assert_eq!(d.state.position_m,position);
    }
    #[test]fn c_raw_fixture_and_crc(){let h="43494d310503020108000000f0ffffff0100feffe8036b03589eff7f252106ed";let p=(0..h.len()).step_by(2).map(|i|u8::from_str_radix(&h[i..i+2],16).unwrap()).collect::<Vec<_>>();let s=Raw::parse(&p).unwrap();assert_eq!(s.accel_mg,[1.,-2.,1000.]);assert_eq!(s.gyro_dps,[8.75,-250.,327.67]);}
    #[test]fn stationary_noise_does_not_accumulate_displacement(){let mut d=ready();for n in 121..6121{let noise=((n*7919)%5)as f64-2.;d.sample(raw(n,noise,-noise));}assert!(d.state.position_m[0].hypot(d.state.position_m[1])<0.0001);}
    #[test]fn physical_stroke_direction_and_constant_velocity_are_not_discarded(){
        let mut d=ready();let mut cruise_start=0.;let mut cruise_end=0.;
        for n in 121..231{let a=if n<141{100.}else if n<211{0.}else{-100.};d.sample(raw(n,a,0.));if n==141{cruise_start=d.state.position_m[0];}if n==210{cruise_end=d.state.position_m[0];}}
        assert!(cruise_end-cruise_start>0.09,"constant-speed displacement {:?}",d.state);
        assert!(d.state.position_m[0]>0.10&&d.state.position_m[1].abs()<0.005);
        for n in 231..281{d.sample(raw(n,0.,0.));}assert!(!d.state.moving);
    }
    #[test]fn missing_sample_and_vertical_lift_cannot_be_integrated_as_a_desk_jump(){
        let mut d=ready();d.sample(raw(121,100.,0.));let before=d.state.position_m;
        d.sample(raw(200,0.,0.));assert_eq!(d.state.position_m,before);assert!(d.state.clutched);
        let mut d=ready();let mut s=raw(121,0.,0.);s.accel_mg[2]=1500.;assert_eq!(d.sample(s),Point::default());assert!(d.state.clutched);
    }
    #[test]fn putting_down_at_a_different_angle_rearms_without_returning_to_old_pose(){
        let mut d=ready();let mut s=raw(121,0.,0.);s.accel_mg=[0.,200.,980.];s.gyro_dps=[40.,0.,0.];d.sample(s);d.tap();
        for n in 122..222{let mut s=raw(n,0.,0.);s.accel_mg=[0.,200.,980.];d.sample(s);}
        assert!(!d.state.clutched);let before=d.state.position_m;
        for n in 222..322{let mut s=raw(n,0.,0.);s.accel_mg=[0.,200.,980.];d.sample(s);}
        assert!((d.state.position_m[0]-before[0]).hypot(d.state.position_m[1]-before[1])<0.001);
    }
    #[test]fn compensated_translation_keeps_working_during_a_natural_orientation_change(){
        let mut d=ready();let mut distance=0.;
        // Rotate about X at15deg/s while translating along world X. The raw
        // gravity vector rotates with the body; this is a coherent6axis trace,
        // not a changed expected cursor direction or a loosened angle gate.
        for n in 121..271{
            let t=(n-120)as f64*0.01;let angle=(15.*t).to_radians();
            let a=if t<=0.2{100.}else if t>=1.3{-100.}else{0.};
            let mut s=raw(n,0.,0.);s.accel_mg=[a,angle.sin()*1000.,angle.cos()*1000.];s.gyro_dps=[15.,0.,0.];
            distance+=d.sample(s).x;
            assert!(!d.state.clutched,"tilt must not suppress compensated translation at{t}s");
        }
        assert!(distance>0.12,"expected continuous translation, got{distance}");
    }
    #[test]fn moderate_vertical_surface_bump_does_not_lock_out_horizontal_translation(){
        let mut d=ready();
        for n in 121..141{d.sample(raw(n,100.,0.));}
        let before=d.state.position_m[0];
        let mut s=raw(141,0.,0.);s.accel_mg[2]=1170.;d.sample(s);
        assert!(!d.state.clutched);
        for n in 142..172{d.sample(raw(n,0.,0.));}
        assert!(d.state.position_m[0]>before+0.04);
    }
    fn coarse_ready()->Desktop{
        let mut d=Desktop::coarse_gestures();for n in 0..121{d.sample(raw(n,0.,0.));}assert!(d.state.calibrated);d
    }
    #[test]fn quiet_sensor_bias_change_cannot_start_and_sustain_coarse_cursor_motion(){
        let mut d=coarse_ready();
        // Slow residual changes can pass an absolute acceleration start limit
        // after AHRS correction freezes. Raw deviations still identify quiet
        // input; this exercises the reported self-moving cursor mechanism.
        let before=d.state.position_m;
        for n in 121..1121{let offset=((n-121)as f64*0.2).min(25.);d.sample(raw(n,offset,0.));}
        assert!(d.state.stationary);assert!(!d.state.moving);
        assert_eq!(d.state.velocity_mps,[0.;2]);assert_eq!(d.state.position_m,before);
    }
    #[test]fn coarse_short_strokes_retain_all_four_directions_then_stop(){
        for (axis,sign)in [(0,1.),(0,-1.),(1,1.),(1,-1.)]{
            let mut d=coarse_ready();
            for n in 121..211{
                let a=if n<131{150.*sign}else if (146..156).contains(&n){-150.*sign}else{0.};
                d.sample(raw(n,if axis==0{a}else{0.},if axis==1{a}else{0.}));
            }
            assert!(d.state.position_m[axis]*sign>0.01,"direction {axis}/{sign}: {:?}",d.state);
            assert!(d.state.position_m[1-axis].abs()<0.002);
            assert!(d.state.stationary);assert_eq!(d.state.velocity_mps,[0.;2]);
            let stopped=d.state.position_m;
            for n in 211..311{d.sample(raw(n,0.,0.));}
            assert_eq!(d.state.position_m,stopped);
        }
    }
    #[test]fn coarse_rest_tradeoff_is_explicit_and_does_not_claim_sustained_constant_speed(){
        let mut d=coarse_ready();for n in 121..141{d.sample(raw(n,100.,0.));}
        assert!(d.state.moving);
        for n in 141..231{d.sample(raw(n,0.,0.));}
        assert!(d.state.stationary);assert!(!d.state.moving);assert_eq!(d.state.velocity_mps,[0.;2]);
        // The reference integrator's separate constant-velocity test remains
        // unchanged. A coarse rest classifier cannot claim that same contract.
    }
}
