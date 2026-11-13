//! Receive the real desktop input stream, preserving errors and control order.
use super::{SETTINGS_UUID, ValueNotification};
use super::super::{recorder_input::InputStatus, recording_wire::transport::Peer};
use super::desktop_input::{trace_input, Update};
use futures::{FutureExt, StreamExt};
use std::{future::Future, pin::Pin, sync::atomic::{AtomicBool,Ordering}, time::Duration};

pub(super) type Notifications=Pin<Box<dyn futures::Stream<Item=Result<ValueNotification,String>>+Send>>;
pub(super) const MOTION_TIMEOUT:Duration=Duration::from_millis(750);

// Opt-in, process-bounded QA capture of motion packets only. Normal product
// sessions do not format or write these records; no microphone data is here.
fn trace_motion_wire(packet:&[u8]) {
    static ENABLED:std::sync::OnceLock<bool>=std::sync::OnceLock::new();
    static COUNT:std::sync::atomic::AtomicU32=std::sync::atomic::AtomicU32::new(0);
    if !*ENABLED.get_or_init(||std::env::var("COMPANION_POINTER_CAPTURE_WIRE").as_deref()==Ok("1")){return;}
    if COUNT.fetch_update(Ordering::Relaxed,Ordering::Relaxed,|n|(n<12000).then_some(n+1)).is_err(){return;}
    let host_us=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_micros();
    let hex=packet.iter().map(|b|format!("{b:02x}")).collect::<String>();
    eprintln!("desktop_input_motion_wire schema=1 host_unix_us={host_us} packet={hex}");
}

#[derive(Debug,PartialEq,Eq)]
pub(super) enum ReceiveError { MotionStopped, Channel(String) }
impl ReceiveError {
    pub(super) fn message(self)->String {match self {
        Self::MotionStopped=>"鼠标动作流停止，正在重新建立动作通道。".into(),
        Self::Channel(message)=>message,
    }}
}
impl From<String> for ReceiveError {fn from(value:String)->Self{Self::Channel(value)}}
impl From<&str> for ReceiveError {fn from(value:&str)->Self{Self::Channel(value.into())}}

pub(super) async fn receive<A,F>(values:&mut Notifications,mode:u8,options:u8,
    peer:&Peer,stop:&AtomicBool,notify:&(impl Fn(Update)+Sync),acknowledge:A,
)->Result<(),ReceiveError>
where A:Fn(u32)->F,F:Future<Output=Result<(),String>> {
    let (ack_tx,mut ack_rx)=tokio::sync::watch::channel(None::<u32>);
    let acknowledgements=async {
        while ack_rx.changed().await.is_ok() {
            let sequence=(*ack_rx.borrow_and_update()).unwrap();
            acknowledge(sequence).await?;
        }
        Ok::<(),String>(())
    };
    tokio::pin!(acknowledgements);
    let mut tick=tokio::time::interval(Duration::from_millis(100));
    let mut motion_at=tokio::time::Instant::now();
    let mut motion_sequence=None;
    loop {
        tokio::select! {
            result=&mut acknowledgements=>{result?;return Err("动作确认通道已结束。".into());},
            _=tick.tick()=>{
                if stop.load(Ordering::Acquire){return Ok(());}
                // Pointer::frame already releases at300ms. This is recovery,
                // not a relaxed quality gate. Idle dictation has no CIM clock.
                if mode==3&&motion_at.elapsed()>=MOTION_TIMEOUT{return Err(ReceiveError::MotionStopped);}
            },
            value=values.next()=>{
                let mut value=value.ok_or("录音卡交互连接已断开。")??;
                let mut latest=None;let mut physical=Vec::new();let mut sequence=None;
                for index in 0..64 {
                    if value.uuid==SETTINGS_UUID {
                        if mode==3 {
                            if let Ok(sample)=companion_desktop_input::pointer::Sample::parse(&value.value){
                                trace_motion_wire(&value.value);
                                sequence=Some(sample.sequence);
                                if sample.aim.is_some(){latest=Some(sample);}else{notify(Update::Motion(sample));}
                            }
                            if options==24 {
                                if let Ok(sample)=companion_desktop_input::pointer::desktop::Raw::parse(&value.value){
                                    sequence=Some(sample.sequence);notify(Update::RawMotion(sample));
                                }
                            }
                        }
                        if let Ok(status)=InputStatus::parse(&value.value,peer){
                            if status.request==0 {trace_input("physical",&status);physical.push(status);}
                        }
                    }
                    if index==63{break;}
                    match values.next().now_or_never(){
                        Some(Some(next))=>value=next?,
                        Some(None)=>return Err("录音卡交互连接已断开。".into()),None=>break,
                    }
                }
                if let Some(sequence)=sequence {
                    // A duplicate/old callback cannot make a frozen sensor
                    // clock healthy, including at the u32 sequence wrap.
                    if motion_sequence.is_none_or(|previous:u32|{let d=sequence.wrapping_sub(previous);d!=0&&d<0x8000_0000}){
                        motion_sequence=Some(sequence);motion_at=tokio::time::Instant::now();
                    }
                }
                if let Some(sample)=latest{notify(Update::Motion(sample));}
                // Keep the existing motion-before-control ordering and latest
                // ACK slot. No microphone/recording command exists here.
                for status in physical {
                    let ack=mode==3&&status.options&8!=0&&status.events&0x1e00!=0;
                    let sequence=status.sequence;notify(Update::Physical(status));
                    if ack{ack_tx.send(Some(sequence)).map_err(|_|"动作确认通道已结束。")?;}
                }
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc,Mutex};
    fn peer()->Peer {Peer{uid:[7;12],epoch:9,capacity:64,max_value_bytes:509,
        logical_control:true,growing_tail:true,batch_interval:true,pause_control:true}}
    fn motion(sequence:u32)->ValueNotification {
        let mut p=vec![0u8;32];p[..4].copy_from_slice(b"CIM1");p[4]=4;p[5]=3;p[6]=2;
        p[8..12].copy_from_slice(&sequence.to_le_bytes());p[12..16].copy_from_slice(&sequence.wrapping_mul(10).to_le_bytes());
        p[22..24].copy_from_slice(&16384i16.to_le_bytes());let crc=crc32fast::hash(&p[..28]);p[28..].copy_from_slice(&crc.to_le_bytes());
        ValueNotification{uuid:SETTINGS_UUID,value:p}
    }
    fn click(sequence:u32)->ValueNotification {
        let peer=peer();let mut p=vec![0u8;64];p[..4].copy_from_slice(b"CIN1");p[4]=1;p[6]=3;
        p[12..16].copy_from_slice(&sequence.to_le_bytes());p[20..22].copy_from_slice(&512u16.to_le_bytes());p[22]=8;
        p[40..52].copy_from_slice(&peer.uid);p[52..60].copy_from_slice(&peer.epoch.to_le_bytes());
        let crc=crc32fast::hash(&p[..60]);p[60..].copy_from_slice(&crc.to_le_bytes());
        ValueNotification{uuid:SETTINGS_UUID,value:p}
    }
    #[tokio::test(start_paused=true)]
    async fn silent_pointer_with_live_native_connection_leaves_waiting_and_requests_recovery(){
        let mut values:Notifications=Box::pin(futures::stream::pending());let stop=AtomicBool::new(false);
        let result=tokio::time::timeout(Duration::from_secs(2),receive(&mut values,3,8,&peer(),&stop,&|_|{},|_|async{Ok(())})).await;
        assert_eq!(result.unwrap(),Err(ReceiveError::MotionStopped));
    }
    #[tokio::test(start_paused=true)]
    async fn control_order_and_ack_prefix_survive_until_missing_motion_ends_the_owner(){
        let mut values:Notifications=Box::pin(futures::stream::unfold(1u32,|sequence|async move{
            tokio::time::sleep(Duration::from_millis(40)).await;Some((Ok(click(sequence)),sequence+1))}));
        let delivered=Arc::new(Mutex::new(Vec::new()));let acked=Arc::new(Mutex::new(Vec::new()));
        let result=receive(&mut values,3,8,&peer(),&AtomicBool::new(false),&|event|{
            if let Update::Physical(s)=event{delivered.lock().unwrap().push(s.sequence);}
        },|s|{acked.lock().unwrap().push(s);async{Ok(())}}).await;
        assert_eq!(result,Err(ReceiveError::MotionStopped));
        let delivered=delivered.lock().unwrap();let acked=acked.lock().unwrap();
        assert!(delivered.len()>10);
        assert_eq!(*delivered,(1..=delivered.len()as u32).collect::<Vec<_>>());
        // Retirement may cancel the one current ACK after consumption. The
        // new owner must reconcile mode/edges; we do not claim that terminal
        // pending ACK reached the peripheral or replay its click later.
        assert!(acked.len()+1>=delivered.len());
        assert_eq!(acked.as_slice(),&delivered[..acked.len()]);
    }
    #[tokio::test(start_paused=true)]
    async fn fresh_motion_across_sequence_wrap_stays_active_until_explicit_stop(){
        let stop=Arc::new(AtomicBool::new(false));let signal=stop.clone();
        let ending=tokio::spawn(async move{tokio::time::sleep(Duration::from_secs(2)).await;signal.store(true,Ordering::Release);});
        let mut values:Notifications=Box::pin(futures::stream::unfold(u32::MAX-30,|s|async move{
            tokio::time::sleep(Duration::from_millis(10)).await;Some((Ok(motion(s)),s.wrapping_add(1)))}));
        let received=std::sync::atomic::AtomicUsize::new(0);
        assert_eq!(receive(&mut values,3,8,&peer(),&stop,&|e|{if matches!(e,Update::Motion(_)){received.fetch_add(1,Ordering::Relaxed);}},|_|async{Ok(())}).await,Ok(()));
        ending.await.unwrap();assert!(received.load(Ordering::Relaxed)>150);
    }
    #[tokio::test(start_paused=true)]
    async fn duplicate_motion_callbacks_do_not_keep_a_frozen_sensor_alive(){
        let mut values:Notifications=Box::pin(futures::stream::unfold((),|_|async{
            tokio::time::sleep(Duration::from_millis(10)).await;Some((Ok(motion(4)),()))}));
        assert_eq!(receive(&mut values,3,8,&peer(),&AtomicBool::new(false),&|_|{},|_|async{Ok(())}).await,Err(ReceiveError::MotionStopped));
    }
    #[tokio::test(start_paused=true)]
    async fn checked_receiver_lag_is_not_filtered_into_an_endless_silent_stream(){
        let mut values:Notifications=Box::pin(futures::stream::once(async{Err("receiver lagged16 notifications".into())}));
        assert_eq!(receive(&mut values,3,8,&peer(),&AtomicBool::new(false),&|_|{},|_|async{Ok(())}).await,
            Err(ReceiveError::Channel("receiver lagged16 notifications".into())));
    }
    #[tokio::test(start_paused=true)]
    async fn idle_dictation_does_not_require_a_constant_mouse_stream(){
        let stop=Arc::new(AtomicBool::new(false));let signal=stop.clone();
        let ending=tokio::spawn(async move{tokio::time::sleep(Duration::from_secs(2)).await;signal.store(true,Ordering::Release);});
        let mut values:Notifications=Box::pin(futures::stream::pending());
        assert_eq!(receive(&mut values,1,0,&peer(),&stop,&|_|{},|_|async{Ok(())}).await,Ok(()));ending.await.unwrap();
    }
}
