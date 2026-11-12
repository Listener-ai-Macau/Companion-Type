//! Owner hardware trial adapter for the SAME core/native glue as the app.
//! stdin: {wire:hex CIM1} / {action:pause|resume|calibrate|recenter|relative|laser|stop}.
//! No BLE, MIC, ASR, app focus or algorithm implementation lives here.
use companion_desktop_input::pointer::{native::Cursor,Button,Control,Mapping,Pointer,Sample,Settings};
use std::{io::{self,BufRead,Write},sync::{mpsc,Arc,atomic::{AtomicBool,Ordering}},time::{Instant,Duration}};
fn main(){if let Err(e)=run(){eprintln!("{e}");std::process::exit(1);}}
fn run()->Result<(),String>{
    let controls=std::env::args().any(|a|a=="--control");
    let mut cursor=Cursor::open()?;let mut p=Pointer::new(Settings::default(),cursor.position()?);
    let mut preview_position=cursor.position()?;
    let stop=Arc::new(AtomicBool::new(false));let input_stop=stop.clone();let(tx,rx)=mpsc::sync_channel::<serde_json::Value>(8);
    std::thread::spawn(move||{for line in io::stdin().lock().lines(){
        let Ok(line)=line else{break;};let Ok(value)=serde_json::from_str(&line)else{continue;};
        if tx.send(value).is_err(){break;}
    }input_stop.store(true,Ordering::Release);});
    let origin=Instant::now();let mut next=Instant::now();let mut report=Instant::now();let(mut clicks,mut drags)=(0u64,0u64);
    while !stop.load(Ordering::Acquire){
        if controls && Cursor::escape(){break;}
        while let Ok(value)=rx.try_recv(){
            if let Some(action)=value.get("action").and_then(|v|v.as_str()){
                match action {
                    "pause"=>p.pause(true),"resume"=>p.pause(false),"calibrate"=>p.calibrate(),
                    "recenter"=>p.recenter(cursor.position()?),
                    "relative"|"laser"=>{p.settings.mapping=if action=="laser"{Mapping::Laser}else{Mapping::Relative};p.recenter(cursor.position()?);},
                    "stop"=>{stop.store(true,Ordering::Release);},_=>{}
                }
            }
            if let Some(event)=value.get("control") {
                if let Ok(event)=serde_json::from_value::<Control>(event.clone()) {p.control(event).map_err(str::to_string)?;}
            }
            if let Some(hex)=value.get("wire").and_then(|v|v.as_str()).filter(|h|h.len()==64){
                let wire=(0..64).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16)).collect::<Result<Vec<_>,_>>();
                if let Ok(wire)=wire {if let Ok(s)=Sample::parse(&wire){p.sample(s,origin.elapsed().as_secs_f64(),cursor.bounds());}}
            }
        }
        if stop.load(Ordering::Acquire){break;}
        let f=p.frame(origin.elapsed().as_secs_f64(),cursor.bounds());
        if let Some(position)=f.position{preview_position=position;}
        if controls{let c=f.buttons.iter().filter(|e|matches!(e,Button::Click(_))).count() as u64;
            let d=f.buttons.iter().filter(|e|matches!(e,Button::Down(_))).count() as u64;
            cursor.apply(f)?;clicks+=c;drags+=d;}
        if report.elapsed()>Duration::from_millis(250){
            println!("{}",serde_json::json!({"stage":"running","controlsCursor":controls,"mapping":p.settings.mapping,"metrics":p.metrics,"position":preview_position,"clickRequests":clicks,"dragRequests":drags}));
            io::stdout().flush().map_err(|e|e.to_string())?;report=Instant::now();
        }
        next+=Duration::from_nanos(if p.settings.mapping==Mapping::Laser{4_166_667}else{8_333_333});
        if let Some(wait)=next.checked_duration_since(Instant::now()){std::thread::sleep(wait);}else{next=Instant::now();}
    }
    cursor.release()?;
    println!("{}",serde_json::json!({"stage":"stopped","metrics":p.metrics,"position":preview_position,"clickRequests":clicks,"dragRequests":drags}));Ok(())
}
