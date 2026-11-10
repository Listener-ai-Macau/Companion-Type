//! The ordinary selected link also owns CIN1. Audio uses the existing exact receiver.
use super::super::recorder_input::{self, InputStatus};
use super::*;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

pub(crate) fn listen(
    device_id: &str,
    stop: Arc<AtomicBool>,
    notify: impl Fn(InputStatus) + Send + Sync + 'static,
) -> Result<(), String> {
    run_native_blocking(async {
        let device = match take_prepared_device(Some(device_id)).await? {
            Some(device) => device,
            None => connect_recorder_device_with_clock(Some(device_id), false).await?,
        };
        let result = on_native_link(&device, async {
            let peer = device
                .recording_peer
                .clone()
                .or_else(|| known_segmented_peer(device_id))
                .ok_or("请先用普通连接读取录音卡，再启用电脑输入。")?;
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
                let request_id = segmented::nonce();
                let message = recorder_input::request(&peer, 1, request_id)?;
                device
                    .peripheral
                    .write(&characteristic, &message, WriteType::WithResponse)
                    .await
                    .map_err(|e| format!("模式切换未完成：{e}"))?;
                let initial = tokio::time::timeout(StdDuration::from_secs(5), async {
                    while let Some(value) = values.next().await {
                        if value.uuid == SETTINGS_UUID {
                            if let Ok(status) = InputStatus::parse(&value.value, &peer) {
                                if status.request == request_id {
                                    return Ok(status);
                                }
                            }
                        }
                    }
                    Err("录音卡连接已断开。".to_string())
                })
                .await
                .map_err(|_| "模式切换未确认，请松开按键后重试。".to_string())??;
                if initial.result != 0 || initial.mode != 1 {
                    return Err("请先松开按键并结束当前录音，再启用电脑输入。".into());
                }
                // Keep the selected connection available to the existing receiver.
                remember_prepared_device(device.clone()).await?;
                notify(initial);
                let mut tick = tokio::time::interval(StdDuration::from_millis(100));
                loop {
                    tokio::select! {
                        _=tick.tick()=>if stop.load(Ordering::Acquire) {break;},
                        value=values.next()=>{
                            let value=value.ok_or("录音卡已断开，原音仍保留在录音卡。")?;
                            if value.uuid==SETTINGS_UUID {
                                if let Ok(status)=InputStatus::parse(&value.value,&peer) {
                                    if status.request==0 {notify(status);}
                                }
                            }
                        }
                    }
                }
                Ok(())
            }
            .await;
            // No STOP command here: physical release owns the recording end.
            let request_id = segmented::nonce();
            let mode = recorder_input::request(&peer, 0, request_id)?;
            let restored = async {
                device
                    .peripheral
                    .write(&characteristic, &mode, WriteType::WithResponse)
                    .await
                    .map_err(|e| e.to_string())?;
                while let Some(value) = values.next().await {
                    if value.uuid == SETTINGS_UUID {
                        if let Ok(status) = InputStatus::parse(&value.value, &peer) {
                            if status.request == request_id {
                                return if status.result == 0 && status.mode == 0 {
                                    Ok(())
                                } else {
                                    Err("请先松开按键；录音卡尚未确认回到普通录音模式。".into())
                                };
                            }
                        }
                    }
                }
                Err("录音模式恢复前连接已断开。".to_string())
            };
            let restored = tokio::time::timeout(StdDuration::from_secs(3), restored)
                .await
                .map_err(|_| "录音模式恢复尚未确认。".to_string())
                .and_then(|r| r);
            let _ = device.peripheral.unsubscribe(&characteristic).await;
            run.and(restored)
        })
        .await;
        if result.is_err() {
            retire_native_device(&device, "desktop input ended").await;
        }
        result
    })
}
