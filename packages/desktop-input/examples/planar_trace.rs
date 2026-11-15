//! Replay recorded RAW/CIM input through the existing pointer core only.
//! No OS cursor or BLE. Frame calls occur at sample arrival, so this is a
//! diagnostic of core decisions, not a physical latency/trajectory measure.
use companion_desktop_input::pointer::{Bounds,Control,Point,Pointer,Sample,Settings,desktop::Raw};
use std::io::{self,BufRead};
fn main(){
    let settings_path=std::env::args().nth(1).expect("explicit settings JSON");
    let settings:Settings=serde_json::from_slice(&std::fs::read(settings_path).unwrap()).unwrap();
    settings.validate().unwrap();
    let mut p=Pointer::new(settings,Point::default());
    let bounds=Bounds{left:-1e6,top:-1e6,width:2e6,height:2e6,primary:None};
    let mut origin=None;let mut shown=Point::default();
    for line in io::stdin().lock().lines(){
        let value:serde_json::Value=serde_json::from_str(&line.unwrap()).unwrap();
        let host=value["hostUnixUs"].as_u64().unwrap();
        let zero=*origin.get_or_insert(host);let now=(host-zero)as f64/1e6;
        if let Some(control)=value.get("control"){
            p.control(serde_json::from_value::<Control>(control.clone()).unwrap()).unwrap();
            continue;
        }
        let hex=value["wire"].as_str().unwrap();
        let wire=(0..hex.len()).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16).unwrap()).collect::<Vec<_>>();
        let raw=Raw::parse(&wire).unwrap();
        let fused=Sample::parse(&wire).ok();
        p.sample_raw_gravity(raw,fused.as_ref().map(|s|s.accel),now);
        if let Some(s)=fused{p.observe_device_readiness(s.device_ready);}
        let frame=p.frame(now,bounds);let mut delta=Point::default();
        if let Some(position)=frame.position{delta=Point{x:position.x-shown.x,y:position.y-shown.y};shown=position;}
        println!("{}",serde_json::json!({"hostUnixUs":host,"sensorMs":raw.sensor_ms,"sequence":raw.sequence,
            "deltaPixels":delta,"position":shown,"metrics":p.metrics,"state":p.planar_state()}));
    }
}
