//! Keep the enabled desktop mode on the same verified recorder across link loss.
use super::super::recorder_input::{self, InputStatus};
use super::*;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

pub(crate) enum Update {
    Ready(InputStatus),
    Motion(companion_desktop_input::pointer::Sample),
    Physical(InputStatus),
    Reconcile(InputStatus),
    Reconnecting(String),
}

type Notifications =
    std::pin::Pin<Box<dyn futures::Stream<Item = btleplug::api::ValueNotification> + Send>>;

fn trace_input(source: &str, status: &InputStatus) {
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

async fn exchange(
    device: &NativeDevice,
    characteristic: &Characteristic,
    values: &mut Notifications,
    peer: &super::super::recording_wire::transport::Peer,
    mode: Option<u8>,
) -> Result<InputStatus, String> {
    let nonce = segmented::nonce();
    let message = match mode {
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
    listen_mode(device_id,peer,stop,connection,1,notify)
}

pub(crate) fn listen_mode(
    device_id:&str, peer:super::super::recording_wire::transport::Peer,
    stop:Arc<AtomicBool>,connection:Arc<tokio::sync::Mutex<()>>,mode:u8,
    notify:impl Fn(Update)+Send+Sync+'static,
)->Result<(),String> {
    run_native_blocking(async {
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
            let result = on_native_link(&device, async {
                let characteristic =
                    find_characteristic(&device.peripheral.characteristics(), SETTINGS_UUID)?;
                let mut values = device
                    .peripheral
                    .notifications()
                    .await
                    .map_err(|e| format!("交互通知未就绪：{e}"))?;
                device
                    .peripheral
                    .subscribe(&characteristic)
                    .await
                    .map_err(|e| format!("交互通知未就绪：{e}"))?;
                let run = async {
                    // Query carries the original UID/epoch and performs no MIC
                    // command. A new handle may only resume this same recorder.
                    let mut current =
                        exchange(&device, &characteristic, &mut values, &peer, None).await?;
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
                            exchange(&device, &characteristic, &mut values, &peer, None).await?;
                        notify(Update::Reconcile(current.clone()));
                    }
                    let initial = if current.mode == mode && current.options == 0 {
                        current
                    } else {
                        exchange(&device, &characteristic, &mut values, &peer, Some(mode)).await?
                    };
                    if mode==3 && initial.result==2 {return Err("此固件尚不支持空中鼠标，请先升级录音卡固件。".into());}
                    if initial.result != 0 || initial.mode != mode {
                        return Err("请先松开按键并结束当前录音，再启用电脑输入。".into());
                    }
                    notify(Update::Ready(initial));
                    drop(acquisition);
                    let mut tick = tokio::time::interval(StdDuration::from_millis(100));
                    loop {
                        tokio::select! {
                            _=tick.tick()=>if stop.load(Ordering::Acquire) {break;},
                            value=values.next()=>{
                                let value=value.ok_or("录音卡交互连接已断开。")?;
                                if value.uuid==SETTINGS_UUID {
                                    if mode==3 {if let Ok(sample)=companion_desktop_input::pointer::Sample::parse(&value.value) {notify(Update::Motion(sample));continue;}}
                                    if let Ok(status)=InputStatus::parse(&value.value,&peer) {
                                        if status.request==0 {trace_input("physical", &status);notify(Update::Physical(status));}
                                    }
                                }
                            }
                        }
                    }
                    Ok(())
                }
                .await;
                // Physical release owns STOP. Explicitly leaving the mode has
                // to receive a real mode0 ACK before reporting it restored.
                let restored = exchange(&device, &characteristic, &mut values, &peer, Some(0))
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
            if lost && !stop.load(Ordering::Acquire) {
                // Existing acquisition owns its bounded retries/retirement.
                // Do not replay START, change device or drop pending targets.
                notify(Update::Reconnecting(
                    "录音卡连接中断，正在重新连接同一设备；原音保留，先不用重录。".into(),
                ));
                continue;
            }
            return result;
        }
    })
}
