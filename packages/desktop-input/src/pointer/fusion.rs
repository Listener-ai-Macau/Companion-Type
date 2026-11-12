//! Owned opaque desktop Fusion state; all algorithm code remains upstream C.
use std::{ffi::c_void,ptr::NonNull};
unsafe extern "C" {
    fn companion_fusion_create()->*mut c_void;
    fn companion_fusion_destroy(handle:*mut c_void);
    fn companion_fusion_configure(handle:*mut c_void,sample_rate:f32);
    fn companion_fusion_align(handle:*mut c_void,accel:*const f32);
    fn companion_fusion_step(handle:*mut c_void,gyro:*const f32,accel:*const f32,dt:f32,gravity:*mut f32,corrected:*mut f32);
}
pub struct Fusion {handle:NonNull<c_void>,configured:bool}
// Upstream state has no thread affinity/global mutable state. Access is owned
// through &mut, and the product shares Pointer through a Mutex.
unsafe impl Send for Fusion {}
impl Default for Fusion {fn default()->Self{Self{handle:NonNull::new(unsafe{companion_fusion_create()}).expect("Fusion state allocation"),configured:false}}}
impl Drop for Fusion {fn drop(&mut self){unsafe{companion_fusion_destroy(self.handle.as_ptr())}}}
impl Fusion {
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
