//! Replay scoped IMU/contact originals through the production Pointer. No OS,
//! microphone, BLE, model service or alternate classification implementation.
use companion_desktop_input::pointer::{Bounds,Control,Mapping,Pointer,Sample,Settings,desktop::Raw,contact::Side};
use std::io::{self,BufRead};
fn main(){
    let mut pointer=Pointer::new(Settings{mapping:Mapping::Relative,desktop_motion:true,..Settings::default()},Default::default());
    let bounds=Bounds{left:0.,top:0.,width:1920.,height:1080.,primary:None};let mut now=0.;
    for line in io::stdin().lock().lines(){
        let Ok(line)=line else{break;};let Ok(v)=serde_json::from_str::<serde_json::Value>(&line)else{continue;};
        if let Some(settings)=v.get("settings").and_then(|x|serde_json::from_value::<Settings>(x.clone()).ok()){
            settings.validate().expect("replay profile must be valid");pointer=Pointer::new(settings,Default::default());
        }
        if let Some(at)=v.get("now").and_then(|x|x.as_f64()){now=at;}
        let mut error=None;
        if let Some(action)=v.get("action").and_then(|x|x.as_str()){
            let result=match action{
                "left"=>pointer.learn_contact(Side::Left),"right"=>pointer.learn_contact(Side::Right),
                "save"=>pointer.finish_contacts(),"cancel"=>{pointer.cancel_contacts();Ok(())},
                _=>Err("unknown replay action"),
            };if let Err(e)=result{error=Some(e);}
        }
        if let Some(hex)=v.get("wire").and_then(|x|x.as_str()).filter(|x|x.len()==64){
            if let Ok(bytes)=(0..64).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16)).collect::<Result<Vec<_>,_>>(){
                if let Ok(sample)=Raw::parse(&bytes){pointer.sample_raw(sample,now);}
                else if let Ok(sample)=Sample::parse(&bytes){pointer.sample(sample,now,bounds);}
            }
        }
        if let Some(event)=v.get("control").and_then(|e|serde_json::from_value::<Control>(e.clone()).ok()){
            if let Err(e)=pointer.control(event){error=Some(e);}
        }
        let frame=pointer.frame(now,bounds);
        println!("{}",serde_json::json!({"now":now,"error":error,"contacts":pointer.contact_status(),"metrics":pointer.metrics,"buttons":format!("{:?}",frame.buttons),"position":frame.position,"settings":pointer.settings}));
    }
}
