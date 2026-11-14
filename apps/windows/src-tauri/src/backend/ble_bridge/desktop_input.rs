//! Keep the enabled desktop mode on the same verified recorder across link loss.
use super::super::recorder_input::{self, InputStatus};
use super::*;
use super::desktop_input_stream::{self as input_stream, Notifications};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

pub(crate) enum Update {
    Ready(InputStatus),
    Motion(companion_desktop_input::pointer::Sample),
    RawMotion(companion_desktop_input::pointer::desktop::Raw),
    Physical(InputStatus),
    Reconcile(InputStatus),
    Reconnecting(String),
}

pub(super) fn trace_input(source: &str, status: &InputStatus) {
    use std::sync::{atomic::AtomicUsize, LazyLock};
    static ENABLED: LazyLock<bool> = LazyLock::new(|| std::env::var_os("COMPANION_DESKTOP_INPUT_DIAGNOSTICS").is_some());
    static COUNT: AtomicUsize = AtomicUsize::new(0);
    if !*ENABLED { return; }
    let count = COUNT.fetch_add(1, Ordering::Relaxed);
    if count < 512 {
        let host_ms = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_millis();
        // Only the already received physical protocol metadata, never audio,
        // transcript, editor content, extra polling or synthesized MIC commands.
        eprintln!("desktop_input_wire source={source} host_unix_ms={host_ms} request={} sequence={} event_ms={} mode={} flags={} feedback={} events={} token={} session={}",
            status.request,status.sequence,status.event_ms,status.mode,status.flags,status.feedback,status.events,status.token,status.session);
    } else if count == 512 {
        eprintln!("desktop_input_wire trace_limit=512 no_more_metadata=1");
    }
}

// Bounded diagnostics for this existing ACK, including cancellation when a
// stalled receiver is retired. No extra packet, polling or audio data.
struct AckTrace {sequence:u32,started:Option<StdInstant>,done:bool}
impl AckTrace {
    fn new(sequence:u32)->Self {
        static ENABLED:std::sync::LazyLock<bool>=std::sync::LazyLock::new(||std::env::var_os("COMPANION_DESKTOP_INPUT_DIAGNOSTICS").is_some());
        static COUNT:std::sync::atomic::AtomicUsize=std::sync::atomic::AtomicUsize::new(0);
        let started=(*ENABLED&&COUNT.fetch_add(1,Ordering::Relaxed)<128).then(StdInstant::now);
        let trace=Self{sequence,started,done:false};trace.log("start",false);trace
    }
    fn log(&self,phase:&str,ok:bool){if let Some(start)=self.started{
        let host=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().as_micros();
        eprintln!("desktop_input_ack phase={phase} sequence={} host_unix_us={host} elapsed_us={} ok={ok}",self.sequence,start.elapsed().as_micros());
    }}
    fn finish(mut self,ok:bool){self.log("complete",ok);self.done=true;}
}
impl Drop for AckTrace {fn drop(&mut self){if !self.done{self.log("cancelled",false);}}}

async fn exchange(
    device: &NativeDevice,
    characteristic: &Characteristic,
    values: &mut Notifications,
    peer: &super::super::recording_wire::transport::Peer,
    mode: Option<u8>,
    pointer_options:u8,
) -> Result<InputStatus, String> {
    let nonce = segmented::nonce();
    let message = match mode {
        Some(3) if pointer_options!=0 => recorder_input::pointer_request_options(peer,nonce,pointer_options)?,
        Some(mode) => recorder_input::request(peer, mode, nonce)?,
        None => recorder_input::query(peer, nonce)?,
    };
    tokio::time::timeout(StdDuration::from_secs(5), async {
        device
            .peripheral
            .write(characteristic, &message, WriteType::WithResponse)
            .await
            .map_err(|error| format!("录音卡模式读取/切换未完成：{error}"))?;
        while let Some(value) = values.next().await {
            let value=value?;
            if value.uuid == SETTINGS_UUID {
                if let Ok(status) = InputStatus::parse(&value.value, peer) {
                    if status.request == nonce {
                        trace_input("reply", &status);
                        return Ok(status);
                    }
                }
            }
        }
        Err("录音卡交互连接已断开。".into())
    })
    .await
    .map_err(|_| "录音卡模式读取/切换未确认。".to_string())?
}

pub(crate) fn listen(
    device_id: &str,
    peer: super::super::recording_wire::transport::Peer,
    stop: Arc<AtomicBool>,
    connection: Arc<tokio::sync::Mutex<()>>,
    notify: impl Fn(Update) + Send + Sync + 'static,
) -> Result<(), String> {
    listen_mode(device_id,peer,stop,connection,1,0,notify)
}

pub(crate) fn listen_mode(
    device_id:&str, peer:super::super::recording_wire::transport::Peer,
    stop:Arc<AtomicBool>,connection:Arc<tokio::sync::Mutex<()>>,mode:u8,pointer_options:u8,
    notify:impl Fn(Update)+Send+Sync+'static,
)->Result<(),String> {
    run_native_blocking(async {
        let mut stream_recoveries=0u8;
        loop {
            if stop.load(Ordering::Acquire) {
                return Err("已停止重连；请下次连接时核对录音卡模式，原音保留。".into());
            }
            // The receiver may itself reconnect while preserving an original.
            // Borrow its resulting handle instead of opening a competing one.
            let acquisition = connection.lock().await;
            let device = match take_prepared_device(Some(device_id)).await? {
                Some(device) => device,
                None => connect_recorder_device_with_clock(Some(device_id), false).await?,
            };
            let stream_failed=AtomicBool::new(false);
            let result = on_native_link(&device, async {
                let characteristic =
                    find_characteristic(&device.peripheral.characteristics(), SETTINGS_UUID)?;
                #[cfg(windows)]
                let mut values:Notifications=Box::pin(device.peripheral.checked_notifications().map(|value|
                    value.map(|(value,_)|value).map_err(|e|format!("交互通知接收失败：{e}"))));
                #[cfg(not(windows))]
                let mut values:Notifications=Box::pin(device.peripheral.notifications().await
                    .map_err(|e|format!("交互通知未就绪：{e}"))?.map(Ok));
                #[cfg(all(test,windows))]
                let mut values=hardware_test::motion_delivery_fault(values,mode);
                device
                    .peripheral
                    .subscribe(&characteristic)
                    .await
                    .map_err(|e| format!("交互通知未就绪：{e}"))?;
                let run = async {
                    // Query carries the original UID/epoch and performs no MIC
                    // command. A new handle may only resume this same recorder.
                    let mut current =
                        exchange(&device, &characteristic, &mut values, &peer, None,0).await?;
                    if current.result != 0 {
                        return Err("录音卡尚未确认当前输入状态。".into());
                    }
                    let mut shared = device.clone();
                    shared.user_connection = true;
                    shared.verified_uid =
                        Some(peer.uid.iter().map(|b| format!("{b:02x}")).collect());
                    shared.recording_peer = Some(peer.clone());
                    // The exact receiver must borrow this handle even when a
                    // previously observed capture sealed during the radio gap.
                    remember_prepared_device(shared).await?;
                    notify(Update::Reconcile(current.clone()));
                    let waiting = StdInstant::now();
                    while current.mode != mode && current.flags & 6 != 0 {
                        if stop.load(Ordering::Acquire) {
                            return Err("已取消电脑输入；原录音保留，请松开按键。".into());
                        }
                        if waiting.elapsed() > StdDuration::from_secs(10) {
                            return Err("上一段仍在录音或保存，请先松开按键；原音保留。".into());
                        }
                        notify(Update::Reconnecting(
                            "已接回同一录音卡，正在等待上一段保存；请先松开按键。".into(),
                        ));
                        tokio::time::sleep(StdDuration::from_millis(250)).await;
                        current =
                            exchange(&device, &characteristic, &mut values, &peer, None,0).await?;
                        notify(Update::Reconcile(current.clone()));
                    }
                    let wanted_options=if mode==3{pointer_options}else{0};
                    let mut initial = if current.mode == mode && current.options == wanted_options {
                        current
                    } else {
                        exchange(&device, &characteristic, &mut values, &peer, Some(mode),wanted_options).await?
                    };
                    // Old normal firmware remains usable with its original
                    // schema3 controls. New firmware negotiates CIM4 explicitly.
                    if mode==3&&initial.result==2&&wanted_options==8 {
                        initial=exchange(&device,&characteristic,&mut values,&peer,Some(mode),0).await?;
                    }
                    if mode==3 && initial.result==2 {return Err("此固件尚不支持空中鼠标，请先升级录音卡固件。".into());}
                    if initial.result != 0 || initial.mode != mode {
                        return Err("请先松开按键并结束当前录音，再启用电脑输入。".into());
                    }
                    notify(Update::Ready(initial));
                    drop(acquisition);
                    let input_characteristic=&characteristic;
                    let input_peer=&peer;
                    let input_device=&device;
                    let receive=input_stream::receive(&mut values,mode,wanted_options,&peer,&stop,&notify,
                        |sequence|async move {
                            let message=recorder_input::pointer_ack(input_peer,sequence)?;
                            let trace=AckTrace::new(sequence);
                            let result=tokio::time::timeout(StdDuration::from_secs(2),input_device.peripheral.write(input_characteristic,&message,WriteType::WithResponse))
                                .await.map_err(|_|"动作确认超时。".to_string())
                                .and_then(|r|r.map_err(|e|format!("动作确认未完成：{e}")));
                            trace.finish(result.is_ok());result
                        }).await;
                    if let Err(error)=receive {
                        if mode==3&&!stop.load(Ordering::Acquire) {
                            stream_failed.store(true,Ordering::Release);
                            notify(Update::Reconnecting("鼠标动作通道已停顿，光标已停止，正在恢复连接。".into()));
                        }
                        return Err(error.message());
                    }
                    Ok(())
                }
                .await;
                // A broken notification receiver cannot prove a mode0 ACK.
                // Retire this exact owner below, then verify the same peer on
                // its fresh connection. Explicit Stop still takes the normal
                // mode0 handshake and cannot report restoration prematurely.
                if stream_failed.load(Ordering::Acquire){return run;}
                // Physical release owns STOP. Explicitly leaving the mode has
                // to receive a real mode0 ACK before reporting it restored.
                let restored = exchange(&device, &characteristic, &mut values, &peer, Some(0),0)
                    .await
                    .and_then(|s| {
                        if s.result == 0 && s.mode == 0 {
                            Ok(())
                        } else {
                            Err("请先松开按键；普通录音模式尚未确认。".into())
                        }
                    });
                let _ = device.peripheral.unsubscribe(&characteristic).await;
                run.and(restored)
            })
            .await;
            if result.is_ok() {
                return result;
            }
            let retirement = connection.lock().await;
            #[cfg(windows)]
            let already_retired = device
                .connection_session
                .as_ref()
                .is_some_and(|s| s.released_after_observed_loss());
            #[cfg(not(windows))]
            let already_retired = false;
            // A receiver may already have retired this owner and established
            // its successor. Do not disconnect the shared peripheral again.
            if !already_retired {
                retire_native_device(&device, "desktop input link ended").await;
            }
            #[cfg(windows)]
            let lost = device
                .connection_session
                .as_ref()
                .is_some_and(|s| s.released_after_observed_loss());
            #[cfg(not(windows))]
            let lost = false;
            drop(retirement);
            let recover_stream=stream_failed.load(Ordering::Acquire)&&stream_recoveries<2;
            if recover_stream{stream_recoveries+=1;}
            if (lost||recover_stream) && !stop.load(Ordering::Acquire) {
                // Existing acquisition owns its bounded retries/retirement.
                // Do not replay START, change device or drop pending targets.
                eprintln!("desktop_input recovery mode={mode} observed_link_loss={lost} stream_failure={} stream_retry={stream_recoveries}",stream_failed.load(Ordering::Acquire));
                notify(Update::Reconnecting(if mode==3 {
                    "鼠标连接中断，光标已停止，正在重新连接同一卡片。"
                } else {"录音卡连接中断，正在重新连接同一设备；原音保留，先不用重录。"}.into()));
                continue;
            }
            if stream_failed.load(Ordering::Acquire)&&!stop.load(Ordering::Acquire){
                return Err(format!("鼠标动作通道未能恢复，控制已停止；可重新开启鼠标。{}",result.unwrap_err()));
            }
            return result;
        }
    })
}

#[cfg(all(test,windows))]
mod hardware_test {
    use super::*;
    use std::sync::Mutex;
    static STALL_ONE_RECEIVER:AtomicBool=AtomicBool::new(false);
    pub(super) fn motion_delivery_fault(values:Notifications,mode:u8)->Notifications {
        if mode!=3||!STALL_ONE_RECEIVER.load(Ordering::Acquire){return values;}
        let mut count=0usize;let mut drop_motion=false;
        Box::pin(values.filter_map(move|value|{
            let motion=value.as_ref().is_ok_and(|v|v.uuid==SETTINGS_UUID&&
                companion_desktop_input::pointer::Sample::parse(&v.value).is_ok());
            if motion {
                count+=1;
                if count==100&&STALL_ONE_RECEIVER.swap(false,Ordering::AcqRel){drop_motion=true;}
            }
            futures::future::ready(if motion&&drop_motion{None}else{Some(value)})
        }))
    }

    #[test]
    #[ignore="Leased fixed UID only: real stale-ACK traffic probe, no MIC, no OS cursor, no physical-click acceptance"]
    fn real_fixed_board_pointer_ack_traffic_probe(){
        const DEVICE:&str="C8:ED:45:EB:95:B4";
        assert_eq!(std::env::var("COMPANION_IMU_HARDWARE_LEASE").as_deref(),Ok("fixed-uid-ack-probe-no-mic-no-cursor"));
        let expected: u32=std::env::var("COMPANION_IMU_EXPECT_FIRMWARE").expect("explicit actual firmware").parse().unwrap();
        let result=run_native_blocking(async {
            let device=connect_recorder_device_with_clock(Some(DEVICE),false).await?;
            let run=on_native_link(&device,async {
                let wire=read_optional_status(&device.peripheral,&device.peripheral.characteristics(),DEVICE_STATUS_UUID,116).await.ok_or("No protected identity reply")?;
                let peer=super::super::super::recording_wire::transport::Peer::from_status(&wire)?.ok_or("No actual V2 peer")?;
                let uid=peer.uid.iter().map(|b|format!("{b:02x}")).collect::<String>();
                let firmware=u32::from_le_bytes(wire[4..8].try_into().unwrap());
                if uid!="120011000d50335754363720"||firmware!=expected{return Err("Wrong fixed UID/firmware".into());}
                let characteristic=find_characteristic(&device.peripheral.characteristics(),SETTINGS_UUID)?;
                let echoes=Arc::new(std::sync::atomic::AtomicUsize::new(0));let observed=echoes.clone();let checked_peer=peer.clone();
                let mut values:Notifications=Box::pin(device.peripheral.checked_notifications().map(|v|v.map(|(v,_)|v).map_err(|e|e.to_string()))
                    .inspect(move|v|{if v.as_ref().ok().filter(|v|v.uuid==SETTINGS_UUID).and_then(|v|InputStatus::parse(&v.value,&checked_peer).ok()).is_some_and(|s|s.request==0xffff_ff00){observed.fetch_add(1,Ordering::Relaxed);}}));
                device.peripheral.subscribe(&characteristic).await.map_err(|e|e.to_string())?;
                let current=exchange(&device,&characteristic,&mut values,&peer,None,0).await?;
                if current.result!=0||current.flags&6!=0||current.events&0x1e00!=0||current.sequence==0xffff_ff00 {
                    return Err("Probe requires idle audio and no queued physical input; no mode changed".into());
                }
                let initial=exchange(&device,&characteristic,&mut values,&peer,Some(3),8).await;
                if !initial.as_ref().is_ok_and(|s|s.result==0&&s.mode==3){
                    let restore=exchange(&device,&characteristic,&mut values,&peer,Some(0),0).await;
                    return Err(format!("Pointer mode not confirmed: {initial:?}; cleanup={restore:?}"));
                }
                let stop=AtomicBool::new(false);let phase=std::sync::atomic::AtomicUsize::new(0);
                let rows=Mutex::new(Vec::<(usize,u32,u128)>::new());let started=StdInstant::now();
                let writer=async {
                    tokio::time::sleep(StdDuration::from_secs(2)).await;phase.store(1,Ordering::Release);
                    let packet=recorder_input::pointer_ack(&peer,0xffff_ff00)?;
                    let mut times=Vec::new();let mut error=None;
                    for _ in 0..10 {
                        let t=StdInstant::now();
                        let write=tokio::time::timeout(StdDuration::from_secs(2),device.peripheral.write(&characteristic,&packet,WriteType::WithResponse)).await;
                        times.push(t.elapsed().as_micros());
                        match write {Ok(Ok(()))=>{},other=>{error=Some(format!("stale ACK write failed: {other:?}"));break;}}
                        tokio::time::sleep(StdDuration::from_millis(50)).await;
                    }
                    phase.store(2,Ordering::Release);tokio::time::sleep(StdDuration::from_secs(2)).await;stop.store(true,Ordering::Release);
                    error.map_or(Ok(times),Err)
                };
                let observe=|u|{
                    if let Update::Motion(s)=u{rows.lock().unwrap().push((phase.load(Ordering::Acquire),s.sequence,started.elapsed().as_micros()));}
                };
                let input_peer=&peer;let input_device=&device;let input_characteristic=&characteristic;
                let receiver=input_stream::receive(&mut values,3,8,&peer,&stop,&observe,|sequence|async move {
                    let packet=recorder_input::pointer_ack(input_peer,sequence)?;
                    input_device.peripheral.write(input_characteristic,&packet,WriteType::WithResponse).await.map_err(|e|e.to_string())
                });
                let (writes,received)=tokio::join!(writer,receiver);
                let restored=exchange(&device,&characteristic,&mut values,&peer,Some(0),0).await;
                let _=device.peripheral.unsubscribe(&characteristic).await;
                let rows=rows.into_inner().unwrap();let mut samples=[0u32;3];let mut missing=[0u32;3];let mut max_gap=[0u128;3];
                for (i,(p,seq,t)) in rows.iter().enumerate(){samples[*p]+=1;if i>0{let (_,previous,at)=rows[i-1];let delta=seq.wrapping_sub(previous);if delta>1&&delta<0x8000_0000{missing[*p]+=delta-1;}max_gap[*p]=max_gap[*p].max(t-at);}}
                eprintln!("ACK_TRAFFIC_PROBE firmware={firmware} samples={samples:?} missing={missing:?} max_host_gap_us={max_gap:?} write_us={writes:?} echoes={} receive={received:?} mode0={restored:?} microphone_commands=0 cursor_output=false synthetic_physical_events=0",echoes.load(Ordering::Relaxed));
                received.map_err(|e|e.message())?;writes?;
                let restored=restored?;if restored.result!=0||restored.mode!=0{return Err("Actual mode0 not confirmed".into());}
                if samples.iter().any(|n|*n<100){return Err("Insufficient real motion during a probe phase".into());}
                Ok(())
            }).await;
            close_native_device(&device).await;run
        });
        result.expect("actual same-owner control traffic and mode0 restoration; not shell-tap qualification");
    }

    #[test]
    #[ignore="Requires explicitly leased fixed Companion830; real protected BLE, no MIC or cursor"]
    fn real_830_live_session_recovers_a_stalled_motion_receiver_and_restores_mode0(){
        const DEVICE:&str="C8:ED:45:EB:95:B4";
        assert_eq!(std::env::var("COMPANION_IMU_HARDWARE_LEASE").as_deref(),Ok("830-fixed-uid-no-mic-no-cursor"));
        let peer=run_native_blocking(async {
            let mut device=connect_recorder_device_with_clock(Some(DEVICE),false).await?;
            let status=read_optional_status(&device.peripheral,&device.peripheral.characteristics(),DEVICE_STATUS_UUID,116).await
                .ok_or("No protected identity/capability reply")?;
            let peer=super::super::super::recording_wire::transport::Peer::from_status(&status)?
                .ok_or("No actual V2 peer")?;
            let uid=peer.uid.iter().map(|b|format!("{b:02x}")).collect::<String>();
            if uid!="120011000d50335754363720"{close_native_device(&device).await;return Err("Wrong fixed MCU UID".into());}
            device.user_connection=true;device.verified_uid=Some(uid);device.recording_peer=Some(peer.clone());
            remember_prepared_device(device).await?;Ok(peer)
        }).expect("protected same-board preparation");
        let stop=Arc::new(AtomicBool::new(false));let timeout_stop=stop.clone();
        let ending=std::thread::spawn(move||{for _ in 0..400{
            if timeout_stop.load(Ordering::Acquire){return;}
            std::thread::sleep(StdDuration::from_millis(100));
        }timeout_stop.store(true,Ordering::Release);});
        let started=StdInstant::now();let ready=Arc::new(std::sync::atomic::AtomicUsize::new(0));
        let samples=Arc::new(std::sync::atomic::AtomicUsize::new(0));let rows=Arc::new(Mutex::new(Vec::<String>::new()));
        let ready_count=ready.clone();let sample_count=samples.clone();let report=rows.clone();let complete=stop.clone();
        let external_acl=std::env::var("COMPANION_IMU_HARDWARE_FAULT").as_deref()==Ok("external-acl");
        STALL_ONE_RECEIVER.store(!external_acl,Ordering::Release);
        let result=listen_mode(DEVICE,peer,stop.clone(),Arc::new(tokio::sync::Mutex::new(())),3,8,move|event|{
            match event {
                Update::Ready(_)=>{let n=ready_count.fetch_add(1,Ordering::AcqRel)+1;
                    eprintln!("IMU_HARDWARE_READY index={n} elapsed_ms={}",started.elapsed().as_millis());
                    report.lock().unwrap().push(format!("ready={n} elapsed_ms={}",started.elapsed().as_millis()));},
                Update::Reconnecting(message)=>report.lock().unwrap().push(format!("reconnecting elapsed_ms={} {message}",started.elapsed().as_millis())),
                Update::Motion(_)=>{let n=sample_count.fetch_add(1,Ordering::AcqRel)+1;
                    if ready_count.load(Ordering::Acquire)>=2&&n>=300{complete.store(true,Ordering::Release);}},
                _=>{},
            }
        });
        STALL_ONE_RECEIVER.store(false,Ordering::Release);stop.store(true,Ordering::Release);ending.join().unwrap();
        let cleanup=run_native_blocking(async{
            let old=PREPARED_DEVICE_CONNECTION.lock().unwrap().disconnect(Some(DEVICE));
            if let Some(old)=old{disconnect_native_device(&old.device).await?;}Ok(())
        });
        eprintln!("IMU_REAL_RECOVERY rows={:?} samples={} result={result:?} cleanup={cleanup:?} mode0_ack_required=true microphone_commands=0 cursor_output=false",rows.lock().unwrap(),samples.load(Ordering::Acquire));
        cleanup.expect("owned native handles closed");result.expect("same-peer recovery and actual mode0 restoration ACK");
        assert!(ready.load(Ordering::Acquire)>=2,"fresh owner was not made ready");
        assert!(samples.load(Ordering::Acquire)>=300,"new owner did not deliver real motion");
    }
}
