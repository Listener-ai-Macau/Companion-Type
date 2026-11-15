//! Owned opaque desktop Fusion state; all algorithm code remains upstream C.
use std::{ffi::c_void,ptr::NonNull};
unsafe extern "C" {
    fn companion_fusion_create()->*mut c_void;
    fn companion_fusion_destroy(handle:*mut c_void);
    fn companion_fusion_configure(handle:*mut c_void,sample_rate:f32);
    fn companion_fusion_align(handle:*mut c_void,accel:*const f32);
    fn companion_fusion_step(handle:*mut c_void,gyro:*const f32,accel:*const f32,dt:f32,gravity:*mut f32,corrected:*mut f32);
    fn companion_fusion_desktop_step(handle:*mut c_void,gyro:*const f32,accel:*const f32,dt:f32,correct_gravity:bool,gyro_corrected:bool,earth:*mut f32,gravity:*mut f32);
}
pub struct Fusion {handle:NonNull<c_void>,configured:bool}
// Upstream state has no thread affinity/global mutable state. Access is owned
// through &mut, and the product shares Pointer through a Mutex.
unsafe impl Send for Fusion {}
impl Default for Fusion {fn default()->Self{Self{handle:NonNull::new(unsafe{companion_fusion_create()}).expect("Fusion state allocation"),configured:false}}}
impl Drop for Fusion {fn drop(&mut self){unsafe{companion_fusion_destroy(self.handle.as_ptr())}}}
impl Fusion {
    pub fn desktop_step(&mut self,gyro:[f64;3],accel:[f64;3],dt:f64,correct_gravity:bool)->([f64;3],[f64;3]){
        self.desktop_step_rates(gyro,accel,dt,correct_gravity,false)
    }
    /// Ready CIM6 rates have already passed the board's FusionBias. Keep
    /// this explicit through the C boundary instead of estimating them twice.
    pub fn desktop_step_corrected(&mut self,gyro:[f64;3],accel:[f64;3],dt:f64,correct_gravity:bool)->([f64;3],[f64;3]){
        self.desktop_step_rates(gyro,accel,dt,correct_gravity,true)
    }
    fn desktop_step_rates(&mut self,gyro:[f64;3],accel:[f64;3],dt:f64,correct_gravity:bool,gyro_corrected:bool)->([f64;3],[f64;3]){
        let gyro=gyro.map(|v|v as f32);let accel=accel.map(|v|v as f32);let(mut earth,mut up)=([0f32;3],[0f32;3]);
        unsafe{companion_fusion_desktop_step(self.handle.as_ptr(),gyro.as_ptr(),accel.as_ptr(),dt as f32,correct_gravity,gyro_corrected,earth.as_mut_ptr(),up.as_mut_ptr())};
        (earth.map(f64::from),up.map(f64::from))
    }
    pub fn align(&mut self,accel:[f64;3]){let a=accel.map(|v|v as f32);unsafe{companion_fusion_align(self.handle.as_ptr(),a.as_ptr())};}
    pub fn step(&mut self,gyro:[f64;3],accel:[f64;3],dt:f64)->([f64;3],[f64;3]) {
        if !self.configured && dt>0. && dt<0.2 {
            unsafe{companion_fusion_configure(self.handle.as_ptr(),(1./dt).clamp(12.,208.) as f32)};self.configured=true;
        }
        let gyro=gyro.map(|v|v as f32);let accel=accel.map(|v|v as f32);let(mut up,mut corrected)=([0f32;3],[0f32;3]);
        unsafe{companion_fusion_step(self.handle.as_ptr(),gyro.as_ptr(),accel.as_ptr(),dt.clamp(0.001,0.1) as f32,up.as_mut_ptr(),corrected.as_mut_ptr())};
        (up.map(f64::from),corrected.map(f64::from))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn already_corrected_slow_rotation_is_not_learned_as_a_second_gyro_bias(){
        let mut corrected=Fusion::default();let mut raw_reference=Fusion::default();
        corrected.align([0.,0.,1000.]);raw_reference.align([0.,0.,1000.]);
        // Warm up a stationary estimator, then provide an independently
        // corrected, genuine0.25dps roll with matching measured gravity.
        // Without the contract flag the host learns that real angular rate
        // as bias and fails to rotate gravity out of a stationary location.
        for _ in 0..500{
            corrected.desktop_step_corrected([0.;3],[0.,0.,1000.],0.01,true);
            raw_reference.desktop_step([0.;3],[0.,0.,1000.],0.01,true);
        }
        let(mut worst_corrected,mut worst_double)=(0_f64,0_f64);
        for n in 1..=1000{
            let angle=(n as f64*0.01*0.25).to_radians();
            let accel=[0.,angle.sin()*1000.,angle.cos()*1000.];
            let good=corrected.desktop_step_corrected([0.25,0.,0.],accel,0.01,false).0;
            let double=raw_reference.desktop_step([0.25,0.,0.],accel,0.01,false).0;
            worst_corrected=worst_corrected.max(good[0].hypot(good[1]));
            worst_double=worst_double.max(double[0].hypot(double[1]));
        }
        eprintln!("Independent corrected-rate roll: single offset max{worst_corrected:.6}m/s2; duplicate-offset reference{worst_double:.6}m/s2");
        assert!(worst_double>0.04,"regression stimulus did not expose duplicate correction");
        assert!(worst_corrected<0.003,"already-corrected slow rotation created fake XY acceleration{worst_corrected}");
    }
    #[test]
    fn measured_gyro_rebias_does_not_keep_a_previous_runtime_bias_after_alignment(){
        let mut f=Fusion::default();let accel=[90.,100.,970.];
        f.align(accel);
        // Runtime correction has learned a small residual. The caller then
        // measures a NEW resting bias and supplies already-rebiased zero gyro.
        // Reusing the old residual would manufacture rotation while at rest.
        for _ in 0..2000{f.desktop_step([0.4,0.25,0.3],accel,0.01,true);}
        f.align(accel);
        let baseline=f.desktop_step([0.;3],accel,0.01,true).0;
        let mut max_horizontal=0f64;
        for _ in 0..300{
            let earth=f.desktop_step([0.;3],accel,0.01,false).0;
            max_horizontal=max_horizontal.max((earth[0]-baseline[0]).hypot(earth[1]-baseline[1]));
        }
        assert!(max_horizontal<0.02,"a static rebased gyro created{max_horizontal}m/s2 horizontal acceleration");
    }
}
