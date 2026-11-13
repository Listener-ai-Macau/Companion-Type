//! Relative remote profile: pinned GamepadMotionHelpers player-space mapping,
//! existing1-Euro filter, and JSM's zero-cutoff recovery (soft tightening).
//! No position estimation, new AHRS, or second gyro calibration.
use super::{OneEuro,Point};
unsafe extern "C" {fn companion_player_space(gyro:*const f32,up:*const f32,result:*mut f32);}
pub fn player_space(gyro:[f64;3],up:[f64;3])->Point{
    let gyro=gyro.map(|x|x as f32);let up=up.map(|x|x as f32);let mut result=[0f32;2];
    unsafe{companion_player_space(gyro.as_ptr(),up.as_ptr(),result.as_mut_ptr());}
    Point{x:result[0]as f64,y:result[1]as f64}
}
#[derive(Default)]
pub struct Response {yaw:OneEuro,pitch:OneEuro}
impl Response {
    pub fn reset(&mut self){*self=Self::default();}
    pub fn sample(&mut self,rates:Point,dt:f64)->Point{
        if rates==Point::default(){self.reset();return rates;}
        // Higher minimum cutoff than the absolute laser's0.8Hz: light fine
        // stabilization with a short response; derivative opens it on motion.
        let yaw=self.yaw.update_with(rates.x,dt,8.,0.05);
        let pitch=self.pitch.update_with(rates.y,dt,8.,0.05);
        // JSM gyroIgnoreFactor with cutoffSpeed=0, recovery=0.5deg/s.
        // Every nonzero input retains a response; there is no3deg/s deadzone.
        let factor=(yaw.hypot(pitch)/0.5).min(1.);
        Point{x:yaw*factor,y:pitch*factor}
    }
}
