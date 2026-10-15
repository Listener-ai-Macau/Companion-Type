//! Current WBA online capture uses the ordinary durable recorder, receiver and
//! service actions. Only the rolling ASR preview is specific to this screen.
use super::*;
use crate::backend::recording_wire::{SessionKey,receiver::{LiveCursor,Receiver}};
use crate::coordinator::CompanionDeviceOperationLease;
use std::{sync::mpsc,time::{Duration,Instant}};

/// Machine exercise of the installed GUI's exact start/stop/service path.
/// It emits stages and the saved row, never full-product acceptance claims.
pub(crate) fn run_cli(args:&[String])->Option<Result<(),String>> {
    if !args.iter().any(|a|a=="--segmented-online-live") {return None;}
    Some((|| {
        let value=|key:&str|args.iter().position(|a|a==key).and_then(|n|args.get(n+1))
            .filter(|v|!v.starts_with("--")).map(String::as_str).ok_or_else(||format!("{key} requires a value"));
        let seconds=value("--seconds")?.parse::<u16>().map_err(|_|"--seconds must be an integer")?;
        validate_board_online_duration(Some(seconds))?;
        let output=std::path::Path::new(value("--output")?);
        if !output.is_absolute() || output.exists() {return Err("输出必须是尚不存在的绝对路径，未启动录音。".into());}
        let device=value("--device-id")?.to_string();
        let _=crate::backend::product_settings::load_and_apply();
        let coordinator=Arc::new(CompanionCoordinator::new_fixture());
        let mut connect=crate::control_request(CompanionV1ControlAction::DeviceConnect,None);
        connect.device_id=Some(device.clone());let connected=coordinator.apply_control(connect)?;
        if !connected.device.connected || crate::backend::known_segmented_peer(&device).is_none() {
            return Err("当前设备未确认连续录音能力，未开录。".into());
        }
        let manager=Arc::new(CompanionBoardOnlineLiveManager::new());
        let started=start_board_online_live_owned(coordinator.clone(),manager.clone(),CompanionBoardOnlineLiveStartRequest {
            title:Some("Companion 在线会议实机检查".into()),device_id:Some(device),max_duration_seconds:Some(seconds),
            partial_interval_ms:Some(8000),disconnect_after_seconds:None })?;
        let session=started.session_id.clone().ok_or("未创建在线会议任务。")?;
        let until=Instant::now()+Duration::from_secs(u64::from(seconds)+1200);
        let mut last=String::new();
        loop {
            let status=manager.snapshot()?;
            let stage=format!("{}:{}",status.state,status.partial_count);
            if stage!=last {eprintln!("segmented_online_status={}",serde_json::to_string(&status).map_err(|e|e.to_string())?);last=stage;}
            if matches!(status.state.as_str(),"completed"|"pending"|"failed") {
                let snapshot=coordinator.snapshot()?;
                let row=snapshot.host.sessions.iter().find(|r|r.id==session);
                let payload=serde_json::json!({"schema":"companion.segmented-online-product-stage.v1",
                    "status":status,"session":row,"fullChainAcceptance":"NOT_QUALIFIED",
                    "hostMic":false,"seed":false,"captureSource":"board_device"});
                crate::backend::export::write_atomic(output,&serde_json::to_vec_pretty(&payload).map_err(|e|e.to_string())?)?;
                return if status.state=="completed" {Ok(())} else {Err(status.error.unwrap_or_else(||"在线会议未完成，原记录已保存。".into()))};
            }
            if Instant::now()>=until {
                // Do not exit while a capture might still own the board.
                manager.request_stop()?;
                return Err("在线会议处理超时，原控制和原音保留；进程退出后从会议列表恢复。".into());
            }
            std::thread::sleep(Duration::from_millis(200));
        }
    })())
}

pub(super) fn start(coordinator:Arc<CompanionCoordinator>,manager:Arc<CompanionBoardOnlineLiveManager>,
    lease:CompanionDeviceOperationLease,request:CompanionBoardOnlineLiveStartRequest,
    session:String,title:String,seconds:u16)->Result<CompanionBoardOnlineLiveStatus,String> {
    if request.disconnect_after_seconds.is_some() {
        return Err("在线会议入口不主动制造断连；请使用原会话恢复调试入口。".into());
    }
    let stop=Arc::new(AtomicBool::new(false));
    let queue=Arc::new(crate::backend::recording_bookmarks::live_queue::LiveQueue::new(&session));
    *manager.stop_requested.lock().map_err(|_|"在线会议停止状态不可用。")?=Some(stop.clone());
    *manager.bookmarks.lock().map_err(|_|"在线会议重点队列不可用。")?=Some(queue.clone());
    manager.set_status(CompanionBoardOnlineLiveStatus {state:"starting".into(),session_id:Some(session.clone()),
        device_id:request.device_id.clone(),max_duration_seconds:Some(seconds),..Default::default()});
    let worker_manager=manager.clone();let failed_queue=queue.clone();
    let spawned=std::thread::Builder::new().name("companion-segmented-online".into()).spawn(move|| {
        let result=run(&coordinator,&worker_manager,lease,&request,&session,&title,seconds,&stop,&queue);
        queue.close();
        let snapshot=coordinator.snapshot();
        let row=snapshot.as_ref().ok().and_then(|s|s.host.sessions.iter().find(|r|r.id==session));
        let complete=row.is_some_and(|r|r.audio_stored && !r.capture_incomplete && r.transcript_final
            && r.minutes_by_mode.offline_store.as_ref().is_some_and(|m|m.status=="minutesReady")
            && r.minutes_by_mode.online_live.as_ref().is_some_and(|m|m.status=="minutesReady"));
        let mut status=worker_manager.snapshot().unwrap_or_default();
        status.state=if complete {"completed"} else if row.is_some() {"pending"} else {"failed"}.into();
        if let Some(row)=row {status.duration_ms=row.duration_ms;
            status.final_recording_path=row.audio_stored.then(||row.audio_path.clone()).flatten();}
        status.error=result.err().or(status.error).or_else(||(!complete).then(||
            "原录音和控制记录已保留；请在会议列表继续同步或转写。".into()));
        worker_manager.set_status(status);
        if let Ok(mut s)=worker_manager.stop_requested.lock() {*s=None;}
        if let Ok(mut q)=worker_manager.bookmarks.lock() {*q=None;}
    });
    if let Err(e)=spawned {
        failed_queue.close();
        if let Ok(mut s)=manager.stop_requested.lock() {*s=None;}
        if let Ok(mut q)=manager.bookmarks.lock() {*q=None;}
        manager.set_status(CompanionBoardOnlineLiveStatus {state:"failed".into(),error:Some(e.to_string()),..Default::default()});
        return Err(format!("启动在线会议失败，尚未发送开录：{e}"));
    }
    manager.snapshot()
}

fn request(action:CompanionV1ControlAction,session:&str,device:Option<String>,title:&str,seconds:u16)
    ->CompanionV1ControlRequest {
    CompanionV1ControlRequest {action,session_id:Some(session.into()),device_id:device,title:Some(title.into()),
        meeting_mode:Some("onlineLive".into()),
        duration_ms:matches!(action,CompanionV1ControlAction::MeetingStart).then_some(u64::from(seconds)*1000),
        ble_name:None,prompt_id:None,transcript_text:None,audio_path:None,audio_bytes:None}
}

fn owned_row<'a>(snapshot:&'a CompanionV1Snapshot,session:&str,key:Option<&SessionKey>)
    ->Result<&'a crate::companion_v1::CompanionV1HostSession,String> {
    let row=snapshot.host.sessions.iter().find(|r|r.id==session).ok_or("在线会议原录音行不存在，未另开录音。")?;
    if row.source!="boardDevice" || row.recorder_control.as_ref().is_none_or(|j|j.host_session!=session)
        || key.is_some_and(|key|row.device_recording_key.as_ref()!=Some(&key.public_key())) {
        return Err("在线会议原录音身份变化，未控制其它录音。".into());
    }
    Ok(row)
}

fn run(coordinator:&Arc<CompanionCoordinator>,manager:&Arc<CompanionBoardOnlineLiveManager>,
    lease:CompanionDeviceOperationLease,options:&CompanionBoardOnlineLiveStartRequest,
    session:&str,title:&str,seconds:u16,stop:&AtomicBool,
    bookmarks:&crate::backend::recording_bookmarks::live_queue::LiveQueue)->Result<(),String> {
    use CompanionV1ControlAction as A;
    let started=coordinator.apply_online_capture_control(&lease,request(A::MeetingStart,session,
        options.device_id.clone(),title,seconds.saturating_add(120)))?;
    let row=owned_row(&started,session,None)?;
    let key=SessionKey::from_public(row.device_recording_key.as_ref().ok_or("开录尚未确认连续会话身份；原控制已保存。")?)?;
    let anchor=row.device_recording_id.ok_or("开录尚未确认原录音编号；原控制已保存。")?;
    let device=row.source_device_id.clone().ok_or("开录缺少原设备身份。")?;
    // A late/ambiguous START is never a licence to create another recording.
    if row.recorder_control_uncertain || row.recorder_control.as_ref().and_then(|j|j.confirmed.as_ref())
        .is_none_or(|c|c.state!=1) {return Err("原开录尚待确认，请恢复这场录音。".into());}
    manager.mark_recording_active(anchor,0);
    eprintln!("segmented_online phase=recording host={} anchor={} logical={:016x}",session,anchor,key.session_id);
    let capture_result=(|| ->Result<(),String> {
    let mut cursor=LiveCursor::new(key.clone())?;
    let started_at=Instant::now();let mut next_follow=Instant::now();
    let interval=Duration::from_millis(options.partial_interval_ms.unwrap_or(8000).max(2000));
    let mut next_partial=started_at+interval;
    let mut pending:Option<mpsc::Receiver<Result<String,String>>>=None;
    let mut live_error:Option<String>=None;let mut link_error:Option<String>=None;
    let mut last_window_ms=0;
    while started_at.elapsed()<Duration::from_secs(u64::from(seconds)) && !stop.load(Ordering::Acquire) {
        if let Some(job)=pending.as_ref() {
            match job.try_recv() {
                Ok(Ok(text))=>{
                    pending=None;
                    if !text.trim().is_empty() {
                        let s=coordinator.snapshot()?;let row=owned_row(&s,session,Some(&key))?;
                        if row.status=="recording" {
                            coordinator.set_board_online_live_partial(session,&text)?;
                            if let Ok(mut s)=manager.status.lock() {s.partial_count+=1;}
                            eprintln!("segmented_online phase=partial_saved host={} source_end_ms={}",session,last_window_ms);
                        }
                    }
                }
                Ok(Err(e))=>{live_error=Some(e);pending=None;}
                Err(mpsc::TryRecvError::Disconnected)=>{live_error=Some("录中转写工作已退出，原音继续保存。".into());pending=None;}
                Err(mpsc::TryRecvError::Empty)=>(),
            }
        }
        if link_error.is_none() && Instant::now()>=next_follow {
            // One bounded receive borrows the existing original connection.
            // A link failure suspends this consumer, never the microphone.
            if let Err(e)=coordinator.follow_online_capture(&lease,session,&mut cursor) {link_error=Some(e);}
            next_follow=Instant::now()+Duration::from_millis(500);
            manager.mark_recording_active(anchor,cursor.duration_ms().min(u64::from(u32::MAX)) as u32);
            if bookmarks.has_pending() && cursor.captured_ms()>0 {
                bookmarks.stamp(&device,anchor,cursor.captured_ms().min(u64::from(u32::MAX)) as u32,
                    |r,s|coordinator.save_live_bookmark(r,s));
            }
        }
        if cursor.error().is_some() && live_error.is_none() {live_error=cursor.error().map(str::to_string);}
        if Instant::now()>=next_partial && pending.is_none() && live_error.is_none()
            && cursor.duration_ms()>last_window_ms && link_error.is_none() {
            next_partial=Instant::now()+interval;
            let current=coordinator.snapshot()?;let row=owned_row(&current,session,Some(&key))?;
            if row.status=="recording" {
                match cursor.window() {
                    Ok(Some(path))=>{
                        last_window_ms=cursor.duration_ms();let (tx,rx)=mpsc::channel();let owner=session.to_string();
                        match std::thread::Builder::new().name("companion-online-preview".into()).spawn(move|| {
                            let result=CompanionTranscriptionManager::new().transcribe_audio_owned(&owner,&path.to_string_lossy())
                                .map(|t|t.text);
                            let _=crate::backend::audio_artifacts::remove_temporary(&path);
                            let _=tx.send(result);
                        }) {Ok(_)=>pending=Some(rx),Err(e)=>live_error=Some(format!("启动录中转写失败：{e}"))}
                    }
                    Ok(None)=>(),Err(e)=>live_error=Some(e),
                }
            }
        }
        if let Ok(mut s)=manager.status.lock() {s.error=link_error.clone().or(live_error.clone());}
        std::thread::sleep(Duration::from_millis(80));
    }
    Ok(())
    })();
    bookmarks.close();
    if let Ok(mut s)=manager.status.lock() {s.state="stopping".into();}
    // Do not wait for cloud partials. STOP, sealed receive, source validation
    // and exact physical consumption are the ordinary recorder implementation.
    let stopped=coordinator.apply_online_capture_control(&lease,request(A::MeetingStop,session,
        Some(device),title,0))?;
    let row=owned_row(&stopped,session,Some(&key))?;
    if row.status=="recording" || row.recorder_control_uncertain || !row.audio_stored || row.capture_incomplete {
        return Err("录音结束／原音收齐尚未确认，请在原会议继续恢复。".into());
    }
    Receiver::verify_saved_row(row)?;
    eprintln!("segmented_online phase=original_saved host={} duration_ms={} reclaimed={}",session,row.duration_ms,row.device_reclaimed);
    drop(lease);
    if let Ok(mut s)=manager.status.lock() {s.state="finalizing".into();s.duration_ms=row.duration_ms;s.final_recording_path=row.audio_path.clone();}
    capture_result?;
    // These are the existing serialized, stale-result-safe service actions.
    // A rolling 30s preview is never promoted to the final whole transcript.
    let transcribed=coordinator.apply_control(request(A::MeetingTranscribeAudio,session,None,title,0))?;
    if !owned_row(&transcribed,session,Some(&key))?.transcript_final {
        return Err("原音已保存；完整转写尚未完成，联网后可继续处理。".into());
    }
    for mode in ["offlineStore","onlineLive"] {
        let mut r=request(A::MeetingGenerateMinutes,session,None,title,0);r.meeting_mode=Some(mode.into());
        coordinator.apply_control(r)?;
    }
    Ok(())
}
