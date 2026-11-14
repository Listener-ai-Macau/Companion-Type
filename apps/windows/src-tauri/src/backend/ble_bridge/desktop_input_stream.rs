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
            // Only this receiver sends to the watch slot. Duplicates already
            // buffered DURING that write need no second identical write.
            // A new device retry AFTER completion still wakes changed(), and
            // a newer pending head must remain pending for its own ACK.
            let pending=*ack_rx.borrow();
            if pending==Some(sequence){ack_rx.borrow_and_update();}
        }
        Ok::<(),String>(())
    };
    tokio::pin!(acknowledgements);
    let mut tick=tokio::time::interval(Duration::from_millis(100));
    let mut motion_at=tokio::time::Instant::now();
    let mut motion_sequence=None;
    let mut ack_sequence=None;
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
                            let fused=companion_desktop_input::pointer::Sample::parse(&value.value).ok();
                            if options==24||options==72 {
                                if let Ok(sample)=companion_desktop_input::pointer::desktop::Raw::parse(&value.value){
                                    sequence=Some(sample.sequence);notify(Update::RawMotion(sample,fused.as_ref().map(|s|s.accel)));
                                }
                            }
                            if let Some(sample)=fused{
                                trace_motion_wire(&value.value);
                                sequence=Some(sample.sequence);
                                if sample.aim.is_some(){latest=Some(sample);}else{notify(Update::Motion(sample));}
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
                    if ack&&ack_sequence.is_none_or(|previous:u32|{
                        sequence==previous||sequence.wrapping_sub(previous)<0x8000_0000
                    }){
                        // Seeing a newer real head proves the previous head
                        // was removed. A delayed older callback cannot replace
                        // that newer pending ACK. Same-head retries stay valid.
                        ack_sequence=Some(sequence);
                        ack_tx.send(Some(sequence)).map_err(|_|"动作确认通道已结束。")?;
                    }
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
    async fn contact_packet_delivers_raw_then_exact_fused_motion_before_control(){
        let hex="43494d310603030209000000000000000000000000400000000028230100feffe8030000adc11945";
        let packet=(0..hex.len()).step_by(2).map(|i|u8::from_str_radix(&hex[i..i+2],16).unwrap()).collect();
        let stop=Arc::new(AtomicBool::new(false));let signal=stop.clone();
        let mut values:Notifications=Box::pin(futures::stream::iter(vec![Ok(ValueNotification{uuid:SETTINGS_UUID,value:packet}),Ok(click(1))]).chain(futures::stream::pending()));
        let events=Mutex::new(vec![]);
        assert_eq!(receive(&mut values,3,72,&peer(),&stop,&|e|match e{
            Update::RawMotion(s,gravity)=>{assert_eq!(s.accel_mg,[1.,-2.,1000.]);assert_eq!(gravity,Some([0.,0.,1000.]));events.lock().unwrap().push("raw");},
            Update::Motion(s)=>{assert_eq!(s.accel,[0.,0.,1000.]);events.lock().unwrap().push("motion");},
            Update::Physical(_)=>{events.lock().unwrap().push("control");signal.store(true,Ordering::Release);},_=>{},
        },|_|async{Ok(())}).await,Ok(()));
        assert_eq!(*events.lock().unwrap(),vec!["raw","motion","control"]);
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
    async fn ack_replay(controls:Vec<(u64,u32)>)->Vec<u32>{
        use std::sync::{Arc,Mutex};
        let stop=Arc::new(AtomicBool::new(false));let ending=stop.clone();
        let task=tokio::spawn(async move{tokio::time::sleep(Duration::from_millis(1000)).await;ending.store(true,Ordering::Release);});
        let origin=tokio::time::Instant::now();
        let motion_stream=futures::stream::unfold(1u32,|s|async move{tokio::time::sleep(Duration::from_millis(10)).await;Some((Ok(motion(s)),s+1))});
        let control_stream=futures::stream::iter(controls).then(move|(at,sequence)|async move{tokio::time::sleep_until(origin+Duration::from_millis(at)).await;Ok(click(sequence))});
        let mut values:Notifications=Box::pin(futures::stream::select(motion_stream,control_stream));
        let writes=Arc::new(Mutex::new(Vec::new()));let sent=writes.clone();
        receive(&mut values,3,8,&peer(),&stop,&|_|{},move|s|{let sent=sent.clone();async move{
            sent.lock().unwrap().push(s);tokio::time::sleep(Duration::from_millis(200)).await;Ok(())
        }}).await.unwrap();task.await.unwrap();
        Arc::try_unwrap(writes).unwrap().into_inner().unwrap()
    }
    #[tokio::test(start_paused=true)]
    async fn duplicate_controls_buffered_during_ack_do_not_queue_redundant_writes(){
        // The actual137 trace received the same12/13/14/15 heads4/8/10/7times.
        // Coalesce only duplicates already seen while their own ACK is pending.
        assert_eq!(ack_replay(vec![(100,12),(110,12),(120,12),(130,12)]).await,vec![12]);
    }
    #[tokio::test(start_paused=true)]
    async fn device_retry_after_completed_ack_is_still_acknowledged(){
        // ATT success alone cannot prove the firmware applied the ACK.
        assert_eq!(ack_replay(vec![(100,12),(110,12),(600,12)]).await,vec![12,12]);
    }
    #[tokio::test(start_paused=true)]
    async fn newer_head_is_not_lost_to_an_older_callback_or_ack_completion(){
        assert_eq!(ack_replay(vec![(100,12),(110,12),(180,13),(190,12)]).await,vec![12,13]);
        assert_eq!(ack_replay(vec![(100,u32::MAX),(180,1),(190,u32::MAX)]).await,vec![u32::MAX,1]);
    }

}
