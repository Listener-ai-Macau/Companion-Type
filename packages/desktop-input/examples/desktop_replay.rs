//! Causal desktop core replay only. No native cursor, MIC, BLE or models.
use companion_desktop_input::pointer::desktop::{Desktop,Raw};
use companion_desktop_input::pointer::intent::Intent;
use std::io::{self,BufRead};
fn main(){
    let mut desktop=Desktop::default();
    let mut intent=Intent::default();let mut origin=None;
    for line in io::stdin().lock().lines(){
        let Ok(line)=line else{break;};let Ok(value)=serde_json::from_str::<serde_json::Value>(&line)else{continue;};
        if value.get("tap").and_then(|v|v.as_bool())==Some(true){desktop.tap();continue;}
        let Some(hex)=value.get("wire").and_then(|v|v.as_str()).filter(|h|h.len()==64)else{continue;};
        let wire=(0..64).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16)).collect::<Result<Vec<_>,_>>();
        if let Ok(wire)=wire{if let Ok(sample)=Raw::parse(&wire){let delta=desktop.sample(sample);
            let zero=*origin.get_or_insert(sample.sensor_ms);let now=sample.sensor_ms.wrapping_sub(zero)as f64/1000.;
            intent.sample(sample,now);let motion=intent.frame(now);
            println!("{}",serde_json::json!({"sensorMs":sample.sensor_ms,"deltaMeters":delta,"state":desktop.state,"coarseDeltaPixels":motion,"movementSource":intent.source}));
        }}
    }
}
