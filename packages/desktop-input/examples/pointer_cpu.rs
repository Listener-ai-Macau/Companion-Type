//! CPU cost of the shipped portable mapping, no OS cursor or BLE operations.
//! Synthetic timing workload: never evidence of real-board CPU or user feel.
use companion_desktop_input::pointer::{Bounds,Pointer,Point,Sample,Settings,Mapping};
use std::{hint::black_box,time::Instant};
fn main(){
    let b=Bounds{left:0.,top:0.,width:1920.,height:1080.,primary:None};
    for mapping in [Mapping::Relative,Mapping::Laser] {
        let mut p=Pointer::new(Settings{mapping,..Settings::default()},Point{x:960.,y:540.});
        let start=Instant::now();let samples=250_000u32;let mut frames=0u64;
        for n in 0..samples {
            let t=n as f64*0.04;let rate=if n<50 {0.}else{(t*0.8).sin()*25.};
            p.sample(black_box(Sample{sequence:n+1,sensor_ms:n*40,held:false,tap_serial:0,fused:false,device_ready:None,accel:[0.,100.,995.],gyro:[rate*0.3,0.,rate]}),t,b);
            for f in 0..5 {black_box(p.frame(t+f as f64*0.008,b));frames+=1;}
        }
        let seconds=start.elapsed().as_secs_f64();let simulated_seconds=samples as f64*0.04;
        println!("mapping={mapping:?} samples={samples} frames={frames} processing_seconds={seconds:.6} us_per_sample_plus_five_frames={:.3} one_core_duty_at_25hz_percent={:.6} scope=SYNTHETIC_PORTABLE_MAPPING_ONLY_NO_BLE_OR_OS",seconds*1e6/samples as f64,100.*seconds/simulated_seconds);
    }
}
