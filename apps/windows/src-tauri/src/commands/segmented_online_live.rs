//! Current WBA online capture uses the ordinary durable recorder, receiver and
//! service actions. Only the rolling ASR preview is specific to this screen.
use super::*;
use crate::backend::recording_wire::{SessionKey,receiver::{LiveCursor,Receiver}};
use crate::coordinator::CompanionDeviceOperationLease;
use std::{sync::mpsc,time::{Duration,Instant}};

pub(super) fn start(coordinator:Arc<CompanionCoordinator>,manager:Arc<CompanionBoardOnlineLiveManager>,
    lease:CompanionDeviceOperationLease,request:CompanionBoardOnlineLiveStartRequest,
    session:String,title:String,seconds:u16)->Result<CompanionBoardOnlineLiveStatus,String> {
    recovery_schedule(&request,seconds)?;
    *manager.link_events.lock().map_err(|_|"在线会议连接记录不可用。")?=(Vec::new(),0);
    let stop=Arc::new(AtomicBool::new(false));
    let queue=Arc::new(crate::backend::recording_bookmarks::live_queue::LiveQueue::new(&session));
    *manager.stop_requested.lock().map_err(|_|"在线会议停止状态不可用。")?=Some(stop.clone());
    *manager.bookmarks.lock().map_err(|_|"在线会议重点队列不可用。")?=Some(queue.clone());
    manager.set_status(CompanionBoardOnlineLiveStatus {state:"starting".into(),session_id:Some(session.clone()),
        device_id:request.device_id.clone(),max_duration_seconds:(seconds != 0).then_some(seconds),..Default::default()});
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
        context_note_revision: None, ble_name:None,prompt_id:None,transcript_text:None,audio_path:None,audio_bytes:None}
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

pub(super) fn recovery_schedule(options:&CompanionBoardOnlineLiveStartRequest,seconds:u16)
    ->Result<Option<(u16,u16)>,String> {
    match (options.disconnect_after_seconds,options.reconnect_after_seconds) {
        (None,None)=>Ok(None),
        (Some(drop),reconnect)=>{
            let reconnect=reconnect.unwrap_or_else(||drop.saturating_add(4));
            if drop==0 || drop>=reconnect || (seconds != 0 && reconnect>=seconds) {
                return Err("断连恢复时点须满足 0 < 断开 < 接回 < 录音时长，未发送开录。".into());
            }
            Ok(Some((drop,reconnect)))
        }
        _=>Err("接回时点必须同时指定断开时点，未发送开录。".into()),
    }
}

fn original_reconfirmed(snapshot:&CompanionV1Snapshot,session:&str,key:&SessionKey,anchor:u32,start_request:u32)
    ->Result<bool,String> {
    let row=owned_row(snapshot,session,Some(key))?;
    let journal=row.recorder_control.as_ref().ok_or("原录音控制记录缺失。")?;
    if row.device_recording_id!=Some(anchor) || journal.start_request!=start_request || journal.pending.is_some()
        || row.recorder_control_uncertain || !snapshot.device.connected {
        return Err("重连尚未确认原录音与原开录指令，设备原件保留，没有重开。".into());
    }
    let confirmed=journal.confirmed.as_ref().ok_or("原录音状态尚未确认。")?;
    if !matches!(confirmed.state,1..=3) {return Err("原录音返回未知状态，没有重开。".into());}
    Ok(confirmed.state!=2)
}

fn reconnect_retry_delay(error:&str,attempts:u32)->Option<Duration> {
    if crate::backend::reconnect_requires_pairing(error) { return None; }
    Some(Duration::from_secs((1u64<<attempts.min(4)).min(15)))
}

fn board_start_seconds(seconds:u16)->u16 {
    if seconds == 0 { 0 } else { seconds.saturating_add(120) }
}

fn capture_continues(seconds:u16,elapsed:Duration,stopped:bool)->bool {
    !stopped && (seconds == 0 || elapsed < Duration::from_secs(u64::from(seconds)))
}

fn run(coordinator:&Arc<CompanionCoordinator>,manager:&Arc<CompanionBoardOnlineLiveManager>,
    lease:CompanionDeviceOperationLease,options:&CompanionBoardOnlineLiveStartRequest,
    session:&str,title:&str,seconds:u16,stop:&AtomicBool,
    bookmarks:&crate::backend::recording_bookmarks::live_queue::LiveQueue)->Result<(),String> {
    use CompanionV1ControlAction as A;
    let started=coordinator.apply_online_capture_control(&lease,request(A::MeetingStart,session,
        options.device_id.clone(),title,board_start_seconds(seconds)))?;
    let row=owned_row(&started,session,None)?;
    let key=SessionKey::from_public(row.device_recording_key.as_ref().ok_or("开录尚未确认连续会话身份；原控制已保存。")?)?;
    let anchor=row.device_recording_id.ok_or("开录尚未确认原录音编号；原控制已保存。")?;
    let device=row.source_device_id.clone().ok_or("开录缺少原设备身份。")?;
    let start_request=row.recorder_control.as_ref().ok_or("原录音控制缺失。")?.start_request;
    // A late/ambiguous START is never a licence to create another recording.
    if row.recorder_control_uncertain || row.recorder_control.as_ref().and_then(|j|j.confirmed.as_ref())
        .is_none_or(|c|c.state!=1) {return Err("原开录尚待确认，请恢复这场录音。".into());}
    manager.mark_recording_active(anchor,0);
    manager.observe_link("startConfirmed",&started,session,0,0,None);
    eprintln!("segmented_online phase=recording host={} anchor={} logical={:016x}",session,anchor,key.session_id);
    let started_at=Instant::now();
    let capture_result=(|| ->Result<(),String> {
    let mut cursor=LiveCursor::new(key.clone())?;
    let mut next_follow=Instant::now();
    let interval=Duration::from_millis(options.partial_interval_ms.unwrap_or(8000).max(2000));
    let mut next_partial=started_at+interval;
    let mut pending:Option<mpsc::Receiver<Result<String,String>>>=None;
    let mut live_error:Option<String>=None;let mut link_error:Option<String>=None;
    let mut last_window_ms=0;
    let schedule=recovery_schedule(options,seconds)?;
    let mut planned_drop_done=false;let mut planned_offline=false;
    let mut reconnect_at:Option<Instant>=None;let mut reconnect_attempts=0u32;
    let mut awaiting_prefix:Option<u64>=None;
    while capture_continues(seconds,started_at.elapsed(),stop.load(Ordering::Acquire)) {
        let elapsed=||started_at.elapsed().as_millis().min(u128::from(u64::MAX)) as u64;
        if !planned_drop_done && schedule.is_some_and(|(drop,_)|started_at.elapsed().as_secs()>=u64::from(drop)) {
            planned_drop_done=true;
            let before=coordinator.snapshot()?;
            manager.observe_link("disconnectRequested",&before,session,elapsed(),cursor.captured_ms(),None);
            let offline=coordinator.apply_online_capture_control(&lease,request(A::DeviceDisconnect,session,Some(device.clone()),title,0))?;
            owned_row(&offline,session,Some(&key))?;
            if offline.device.connected || !offline.meeting.active {return Err("断开未保留原录音状态，未制造替代录音。".into());}
            manager.observe_link("offlineActionConfirmed",&offline,session,elapsed(),cursor.captured_ms(),None);
            // A product action acknowledgement is not proof of physical radio
            // loss. The CLI reports that gate as unknown until passive HCI.
            planned_offline=true;link_error=Some("蓝牙已断开，设备继续离线录音。".into());
            reconnect_at=Some(started_at+Duration::from_secs(u64::from(schedule.unwrap().1)));
            awaiting_prefix=Some(cursor.captured_ms());
        }
        if link_error.is_some() && reconnect_at.is_some_and(|at|Instant::now()>=at) {
            let current=coordinator.snapshot()?;
            if planned_offline || (current.device.auto_reconnect_enabled && !current.device.manual_disconnect) {
                reconnect_attempts+=1;
                manager.observe_link("reconnectRequested",&current,session,elapsed(),cursor.captured_ms(),None);
                let restored=coordinator.apply_online_capture_control(&lease,
                    request(A::DeviceConnect,session,Some(device.clone()),title,0))
                    .and_then(|snapshot|original_reconfirmed(&snapshot,session,&key,anchor,start_request).map(|active|(snapshot,active)));
                match restored {
                    Ok((snapshot,active))=>{
                        manager.observe_link("originalReconfirmed",&snapshot,session,elapsed(),cursor.captured_ms(),None);
                        link_error=None;planned_offline=false;reconnect_at=None;reconnect_attempts=0;next_follow=Instant::now();
                        if !active {break;}
                    }
                    Err(error)=>{
                        manager.observe_link("reconnectFailed",&coordinator.snapshot()?,session,elapsed(),cursor.captured_ms(),Some(&error));
                        reconnect_at=reconnect_retry_delay(&error,reconnect_attempts).map(|delay|Instant::now()+delay);
                        if reconnect_at.is_none() {
                            manager.observe_link("reconnectNeedsPairing",&coordinator.snapshot()?,session,elapsed(),cursor.captured_ms(),Some(&error));
                        }
                        link_error=Some(error);
                    }
                }
            } else {reconnect_at=None;}
        }
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
            match coordinator.follow_online_capture(&lease,session,&mut cursor) {
                Ok(_)=>{
                    if awaiting_prefix.is_some_and(|prior|cursor.captured_ms()>prior) {
                        manager.observe_link("prefixResumed",&coordinator.snapshot()?,session,elapsed(),cursor.captured_ms(),None);
                        awaiting_prefix=None;
                    }
                }
                Err(error)=>{
                    manager.observe_link("followFailed",&coordinator.snapshot()?,session,elapsed(),cursor.captured_ms(),Some(&error));
                    link_error=Some(error);awaiting_prefix=Some(cursor.captured_ms());reconnect_at=Some(Instant::now()+Duration::from_secs(1));
                }
            }
            next_follow=Instant::now()+Duration::from_millis(500);
            manager.mark_recording_active(anchor,cursor.duration_ms().min(u64::from(u32::MAX)) as u32);
            if bookmarks.has_pending() && cursor.captured_ms()>0 {
                bookmarks.stamp_logical(&device,anchor,cursor.captured_ms().min(u64::from(u32::MAX)) as u32,&key,
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
    manager.observe_link("stopConfirmedSourceSaved",&stopped,session,started_at.elapsed().as_millis() as u64,row.duration_ms,None);
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

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unlimited_online_capture_runs_until_explicit_stop() {
        assert_eq!(board_start_seconds(0),0);
        assert_eq!(board_start_seconds(1800),1920);
        assert!(capture_continues(0,Duration::from_secs(7200),false));
        assert!(!capture_continues(0,Duration::from_secs(7200),true));
        assert!(!capture_continues(1800,Duration::from_secs(1800),false));
        let r=request(CompanionV1ControlAction::MeetingStart,"test",None,"test",board_start_seconds(0));
        assert_eq!(r.duration_ms,Some(0));
    }
    #[test]
    fn ordinary_link_loss_keeps_paced_retry_without_overflow() {
        assert_eq!(reconnect_retry_delay("GATT peer unreachable",1),Some(Duration::from_secs(2)));
        assert_eq!(reconnect_retry_delay("GATT peer unreachable",u32::MAX),Some(Duration::from_secs(15)));
    }
    #[cfg(windows)]
    #[test]
    fn pairing_failure_waits_for_explicit_reconnect_instead_of_repeating_ceremony() {
        for attempt in [1,2,15,u32::MAX] {
            assert_eq!(reconnect_retry_delay("Windows BLE pairing required: Windows 状态 19",attempt),None);
        }
        assert!(reconnect_retry_delay("GATT peer unreachable",1).is_some());
    }
    #[test]
    fn reconnect_must_keep_exact_logical_key_anchor_and_original_start() {
        use crate::backend::recording_wire::{control::PausePeer,transport::Peer};
        use crate::backend::recorder_control::{Journal,Confirmed};
        let id="board-online-owned";let key=SessionKey{device_uid:[7;12],format_epoch:11,session_id:13};
        let peer=Peer{uid:[7;12],epoch:11,capacity:64,max_value_bytes:509,logical_control:true,growing_tail:true,batch_interval:true,pause_control:true};
        let pause=PausePeer::from_verified_peer(&peer).unwrap();
        let mut journal=Journal::start(&pause,id,"AA:BB:CC:DD:EE:19",17,60).unwrap();
        journal.key=Some(key.public_key());journal.anchor=Some(19);journal.pending=None;
        journal.confirmed=Some(Confirmed{command:1,request:17,sequence:0,state:1,duration_ms:1000,finished_locally:false,local_control:false});
        let mut s=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),request(
            CompanionV1ControlAction::MeetingStart,id,None,"unit",60)).unwrap();
        s.device.connected=true;
        let r=&mut s.host.sessions[0];r.source="boardDevice".into();r.device_recording_key=Some(key.public_key());
        r.device_recording_id=Some(19);r.recorder_control=Some(journal);
        assert!(original_reconfirmed(&s,id,&key,19,17).unwrap());
        for n in 0..4 {
            let mut bad=s.clone();let row=&mut bad.host.sessions[0];
            match n {0=>row.device_recording_id=Some(20),1=>row.recorder_control.as_mut().unwrap().start_request=18,
                2=>row.device_recording_key.as_mut().unwrap().session_id="000000000000000e".into(),_=>row.recorder_control_uncertain=true}
            assert!(original_reconfirmed(&bad,id,&key,19,17).is_err());
        }
    }
}
