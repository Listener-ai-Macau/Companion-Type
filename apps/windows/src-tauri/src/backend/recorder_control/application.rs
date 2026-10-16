//! Bind CMC3 to the original durable product row, never a fixture/replacement.
use super::*;
use crate::companion_v1::{CompanionV1ControlAction as Action, CompanionV1ControlRequest,
    CompanionV1HostSession, CompanionV1Snapshot, CompanionV1ControlEcho, COMPANION_V1_GATT_BOUNDARY};

pub(crate) fn unconfirmed_start_retry_request(snapshot:&CompanionV1Snapshot,request:&CompanionV1ControlRequest)->bool {
    if request.action!=Action::MeetingStart || request.audio_path.is_some() || request.audio_bytes.is_some()
        || snapshot.host.persistence.status!="ready" || !matches!(snapshot.source,"lastKnown"|"firmware") {return false;}
    let Some(host)=request.session_id.as_deref() else{return false;};
    let Some(device)=request.device_id.as_deref() else{return false;};
    let mut active=snapshot.host.sessions.iter().filter(|row|row.status=="recording");
    let Some(row)=active.next() else{return false;};
    if active.next().is_some() || row.id!=host || row.source!="boardDevice"
        || row.device_recording_id.is_some() || row.device_recording_key.is_some()
        || row.source_device_id.as_deref().is_none_or(|id|!same_device(id,device))
        || snapshot.device.device_id.as_deref().is_some_and(|id|!same_device(id,device)) {return false;}
    row.recorder_control.as_ref().is_some_and(|journal|journal.schema==1 && journal.host_session==host
        && same_device(&journal.device_id,device) && journal.unconfirmed_start_retry()
        && request.duration_ms.is_none_or(|ms|ms==u64::from(journal.max_seconds)*1000))
}

/// A fresh host has no live GATT identity. A durable, already-confirmed
/// original authorizes its protected QUERY/recovery, not a generic probe or
/// a replacement START. The actual UID/epoch/journal are still checked on GATT.
pub(crate) fn restart_recovery_request(snapshot:&CompanionV1Snapshot,device:&str)->Option<CompanionV1ControlRequest> {
    if snapshot.host.persistence.status!="ready" || !matches!(snapshot.source,"lastKnown"|"firmware")
        || snapshot.device.device_id.as_deref().is_some_and(|id|!same_device(id,device)) {return None;}
    let mut active=snapshot.host.sessions.iter().filter(|row|row.status=="recording");
    let row=active.next()?;
    if active.next().is_some() || row.source!="boardDevice"
        || snapshot.host.active_session_id.as_deref().is_some_and(|id|id!=row.id)
        || row.source_device_id.as_deref().is_none_or(|id|!same_device(id,device)) {return None;}
    let journal=row.recorder_control.as_ref()?;
    let key=SessionKey::from_public(row.device_recording_key.as_ref()?).ok()?;
    if journal.schema!=1 || journal.host_session!=row.id || !same_device(&journal.device_id,device)
        || journal.uid!=key.device_uid || journal.epoch!=key.format_epoch
        || journal.start_request==0 || (journal.max_seconds==0 && !journal.local_origin)
        || journal.key.as_ref()!=row.device_recording_key.as_ref()
        || journal.anchor.is_none_or(|id|id==0) || journal.anchor!=row.device_recording_id
        || journal.confirmed.as_ref().is_none_or(|confirmed|!matches!(confirmed.state,1|3))
        || journal.pending.as_ref().is_some_and(|pending|!matches!(pending.command,2..=5))
        || journal.sealed_catalogue_end.is_some()
        || snapshot.device.mcu_uid.as_deref().is_some_and(|uid|!uid.eq_ignore_ascii_case(&key.public_key().device_uid)) {return None;}
    Some(CompanionV1ControlRequest {action:Action::MeetingRecoverControl,session_id:Some(row.id.clone()),
        device_id:Some(device.into()),ble_name:None,prompt_id:Some("__companion_original_auto_reconnect__".into()),title:None,transcript_text:None,
        meeting_mode:None,audio_path:None,audio_bytes:None,duration_ms:None})
}

impl Journal {
    pub(crate) fn checkpoint_row(&self,row:&mut CompanionV1HostSession)->Result<(),String> {
        if row.id!=self.host_session || row.source!="boardDevice"
            || row.source_device_id.as_deref().is_none_or(|d|!same_device(d,&self.device_id))
            || row.device_recording_key.as_ref().is_some_and(|k|self.key.as_ref()!=Some(k))
            || row.device_recording_id.is_some_and(|id|self.anchor!=Some(id)) {
            return Err(failure("会议库与原控制的设备／会话身份不同"));
        }
        if let Some(old)=row.recorder_control.as_ref() {
            if old.host_session!=self.host_session || old.start_request!=self.start_request
                || old.max_seconds!=self.max_seconds || old.local_origin!=self.local_origin || (old.uid,old.epoch)!=(self.uid,self.epoch)
                || old.confirmed.as_ref().is_some_and(|c|self.confirmed.as_ref().is_none_or(|next|next.sequence<c.sequence)) {
                return Err(failure("拒绝用另一命令或旧确认覆盖原录音"));
            }
            if old.sealed_catalogue_end.is_some() && old.sealed_catalogue_end!=self.sealed_catalogue_end {
                return Err(failure("拒绝撤回或替换原封口目录证据"));
            }
        }
        self.validate_sealed_end()?;
        if let Some(reason)=self.end_reason {
            if row.device_recording_end_reason.is_some_and(|old|old!=reason) {return Err(failure("原音库的停止原因冲突"));}
            row.device_recording_end_reason=Some(reason);
        }
        row.recorder_control=Some(self.clone());
        if let Some(end)=self.sealed_catalogue_end.as_ref() {
            row.device_recording_id=self.anchor;row.device_recording_key=self.key.clone();
            row.recorder_control_uncertain=false;
            if !row.audio_stored {row.duration_ms=u64::from(end.duration_ms);row.status="captured".into();}
            else if row.status=="recording" {row.status="captured".into();}
            // A sealed original proves capture ended, not why or exactly when.
            // Preserve the warning and keep automatic cloud work paused after
            // receiving; source audio is still verified independently.
            row.capture_incomplete|=end.capture_incomplete;
            row.pending_reason=(!row.audio_stored).then(||"needs_device_sync".into());
            if row.audio_stored {super::super::interrupted_capture::hold(row);}
            return Ok(());
        }
        row.recorder_control_uncertain=self.pending.is_some();
        if let Some(c)=self.confirmed.as_ref() {
            row.device_recording_id=self.anchor;row.device_recording_key=self.key.clone();
            // Source samples exclude every pause. Never derive this from host
            // wall time, and never overwrite a received WAV with an estimate.
            if !row.audio_stored {row.duration_ms=u64::from(c.duration_ms);}
            if !self.local_origin && matches!(c.state,1|3) && row.started_at.is_none() {
                row.started_at=Some(super::super::observation_timestamp());
            }
            if c.state==2 {
                row.status="captured".into();
                // Reconnecting after a local limit/button stop observes an
                // already sealed original, not its actual stop time. Keep an
                // unknown time unknown; source duration remains device-derived.
                if row.stopped_at.is_none() && !c.finished_locally {
                    row.stopped_at=Some(super::super::observation_timestamp());
                }
                row.pending_reason=(!row.audio_stored).then(||"needs_device_sync".into());
            } else {row.status="recording".into();row.stopped_at=None;}
        } else {row.status="recording".into();}
        if self.pending.is_some() {row.pending_reason=Some("device_control_pending".into());}
        else if self.confirmed.as_ref().is_some_and(|c|matches!(c.state,1|3)) {row.pending_reason=None;}
        Ok(())
    }
}

pub(crate) fn reserve_start(snapshot:&mut CompanionV1Snapshot,request:&CompanionV1ControlRequest,
    peer:&crate::backend::recording_wire::transport::Peer,device:&str,host:&str,max_seconds:u16)->Result<(),String> {
    if snapshot.host.sessions.iter().any(|r|r.status=="recording" && r.id!=host) {
        return Err("另一场录音尚未结束或核对，未开始新录音。".into());
    }
    let pause_peer=PausePeer::from_verified_peer(peer)?;
    let journal=if let Some(row)=snapshot.host.sessions.iter().find(|row|row.id==host) {
        let journal=row.recorder_control.clone().ok_or("原录音没有暂停协议，未覆盖或重开。")?;
        journal.matches(&pause_peer,host,device)?;
        if journal.max_seconds!=max_seconds {return Err("原录音时长已固定，未重开。".into());}
        journal
    } else {
        let journal=Journal::start(&pause_peer,host,device,
            super::super::ble_bridge::meeting_idempotency_request_id(host,1),max_seconds)?;
        let mut request=request.clone();request.session_id=Some(host.into());request.duration_ms=Some(0);
        request.audio_path=None;request.audio_bytes=Some(0);request.device_id=Some(device.into());
        let mut row=crate::companion_v1::create_host_session(snapshot,&request,"");
        row.source="boardDevice".into();row.started_at=None;row.stopped_at=None;
        row.audio_path=None;row.audio_bytes=0;row.duration_ms=0;row.audio_stored=false;row.chunks.clear();
        if request.prompt_id.as_deref()==Some(super::super::pet_chat::CAPTURE_PROMPT)
            && host.starts_with("pet-chat-") {
            row.recovery.intent=super::super::pet_chat::CAPTURE_INTENT.into();
        }
        journal.checkpoint_row(&mut row)?;snapshot.host.sessions.insert(0,row);journal
    };
    snapshot.host.active_session_id=Some(host.into());snapshot.host.selected_session_id=Some(host.into());
    snapshot.meeting.active=true;snapshot.meeting.status="controlPending".into();
    super::super::persistence::save_snapshot(snapshot)?;
    let mut store=Store::open(&super::super::persistence::state_file_path(),host)?;
    if let Some(saved)=store.journal.as_ref() {
        // A newer sidecar can survive an index write failure. It must be
        // recovered; never replace it with the older renderer/library copy.
        if saved!=&journal {return Err(failure("上次命令尚待恢复，未替换原命令"));}
    }
    store.commit_bound(journal)
}

pub(crate) fn restore_snapshot(snapshot:&mut CompanionV1Snapshot,host:&str)->Result<(),String> {
    let loaded=super::super::session_store::load(&super::super::persistence::state_file_path());
    if loaded.state.status=="blocked" {snapshot.host.persistence=loaded.state;return Err("原录音库暂时不可读，控制记录保留。".into());}
    let rows:Vec<CompanionV1HostSession>=serde_json::from_slice(&loaded.bytes.ok_or("原录音库缺失。")?)
        .map_err(|e|format!("读取原录音库：{e}"))?;
    let row=rows.into_iter().find(|row|row.id==host).ok_or("原录音行缺失，未创建替代录音。")?;
    let j=row.recorder_control.as_ref().ok_or("原录音控制缺失。")?;
    j.validate_sealed_end()?;
    let ended=j.ended();
    let state=if ended {"captured"} else if j.pending.is_some() || row.recorder_control_uncertain {"controlPending"}
        else if j.confirmed.as_ref().is_some_and(|c|c.state==3) {"paused"} else {"recording"};
    snapshot.meeting.active=!ended;snapshot.meeting.status=state.into();
    snapshot.meeting.duration_ms=row.duration_ms;snapshot.meeting.started_at=row.started_at.clone();
    snapshot.device.recording=state=="recording";
    snapshot.host.active_session_id=(!ended).then(||host.into());snapshot.host.selected_session_id=Some(host.into());
    if let Some(old)=snapshot.host.sessions.iter_mut().find(|r|r.id==host) {*old=row;}
    else {snapshot.host.sessions.insert(0,row);}
    Ok(())
}

/// Returns false only for the established non-CMC3 path. Missing/corrupt
/// capability or commands never turn PAUSE into STOP/new START.
pub(crate) fn apply(snapshot:&mut CompanionV1Snapshot,request:&CompanionV1ControlRequest,
    bridge:&super::super::ble_bridge::CompanionBleBridge)->Result<bool,String> {
    let command=match request.action {Action::MeetingStart=>1,Action::MeetingStop=>2,
        Action::MeetingFinalize=>3,Action::MeetingPause=>4,Action::MeetingResume=>5,
        Action::MeetingRecoverControl|Action::DeviceConnect=>0,_=>return Ok(false)};
    let explicit_audio=request.audio_path.as_deref().is_some_and(|p|!p.trim().is_empty());
    let owner=request.session_id.as_deref().or(snapshot.host.active_session_id.as_deref())
        .or(snapshot.host.selected_session_id.as_deref()).and_then(|id|snapshot.host.sessions.iter().find(|r|r.id==id))
        .or_else(||snapshot.host.sessions.iter().find(|r|r.recorder_control.is_some() && r.status=="recording"));
    let saved=owner.and_then(|r|r.recorder_control.clone());
    if saved.as_ref().is_some_and(|j|request.session_id.as_deref().is_some_and(|id|id!=j.host_session)) {
        return Err("指定会议与原录音控制不同，未修改另一场录音。".into());
    }
    if request.action==Action::DeviceConnect && owner.is_none_or(|r|r.status!="recording") {return Ok(false);}
    let device=saved.as_ref().map(|j|j.device_id.clone()).or_else(||request.device_id.clone())
        .or_else(||snapshot.device.device_id.clone());
    let peer=device.as_deref().and_then(super::super::ble_bridge::known_segmented_peer);
    let new_start=command==1 && saved.is_none() && !explicit_audio && snapshot.connected
        && snapshot.device.mode=="windowsNative" && peer.as_ref().is_some_and(|p|p.pause_control);
    if !new_start && saved.is_none() {
        if matches!(request.action,Action::MeetingPause|Action::MeetingResume|Action::MeetingRecoverControl) {
            return Err("这场录音尚未启用设备暂停控制；未停止重开。".into());
        }
        return Ok(false);
    }
    if explicit_audio {return Err("设备原录音不能换成本机音频。".into());}
    let device=device.ok_or("原录音设备身份缺失。")?;
    if request.device_id.as_deref().is_some_and(|d|!same_device(d,&device))
        || snapshot.device.device_id.as_deref().is_some_and(|d|!same_device(d,&device)) {
        return Err("请连接原来的 Companion，未控制其它设备。".into());
    }
    let host=saved.as_ref().map(|j|j.host_session.clone()).or_else(||request.session_id.clone())
        .unwrap_or_else(||format!("meeting-{}-{}",std::process::id(),uuid::Uuid::new_v4()));
    if snapshot.host.sessions.iter().any(|r|r.status=="recording" && r.id!=host) {
        return Err("另一场录音正在进行，未控制或新开录音。".into());
    }
    let max_seconds=if command==1 {
        saved.as_ref().map(|j|j.max_seconds).unwrap_or(super::super::recording_duration_seconds(request.duration_ms)?)
    } else {0};
    if new_start {reserve_start(snapshot,request,peer.as_ref().unwrap(),&device,&host,max_seconds)?;}
    let owned=snapshot.host.sessions.iter().find(|r|r.id==host).ok_or("原录音尚未保存。")?;
    let anchor=owned.device_recording_id;let key=owned.device_recording_key.clone();
    let known=super::super::verified_device_recording_ids(snapshot,Some(&device));
    let automatic_recovery=request.prompt_id.as_deref()==Some("__companion_original_auto_reconnect__");
    let result=bridge.pausable_meeting_control(&device,command,max_seconds,&host,anchor,key.as_ref(),new_start,&known,automatic_recovery);
    // Reload even on timeout/pull failure: START intent or the real STOP ACK
    // was saved before any BLE write/receive, so neither can disappear.
    let restored=restore_snapshot(snapshot,&host);
    let (report,_journal,operation)=match result {
        Ok(value)=>{restored?;value},
        Err(error)=>{
            if restored.is_ok() {
                if let Some(row)=snapshot.host.sessions.iter_mut().find(|r|r.id==host && r.status=="recording") {
                    row.recorder_control_uncertain=true;snapshot.meeting.status="controlPending".into();
                }
                snapshot.device.recording=false;snapshot.device.connected=false;snapshot.connected=false;
            }
            return Err(error);
        }
    };
    snapshot.source="firmware";snapshot.device.device_id=Some(report.device_id.clone());
    snapshot.device.mode="windowsNative".into();
    snapshot.device.mcu_uid=Some(_journal.uid.iter().map(|b|format!("{b:02x}")).collect());
    if let Some(row)=snapshot.host.sessions.iter_mut().find(|r|r.id==host) {row.recorder_control_uncertain=false;}
    let message=if _journal.sealed_catalogue_end.is_some() {"原录音的封口目录已核对，原音按同一场恢复；结束原因未确认，没有重开或伪造停止确认。"} else {match report.state {1=>"设备已确认录音中。",3=>"设备已暂停，继续后仍是同一场录音。",
        2=>"设备已结束录音，原音按同一场会议收取。",_=>"设备控制结果已核对。"}};
    finish_original_connection(snapshot,request.action,message,operation.as_ref())?;
    Ok(true)
}

fn finish_original_connection(snapshot:&mut CompanionV1Snapshot,action:Action,message:&str,
    operation:Option<&super::super::ble_bridge::CompanionBleOperation>)->Result<(),String> {
    let error=operation.filter(|op|!op.ready&&!op.sync_paused).map(|op|
        format!("设备已结束录音，原会议已保存；收取尚未完成：{}",op.message));
    let connected=error.is_none();let message=error.as_deref().unwrap_or(message);
    snapshot.connected=connected;snapshot.device.connected=connected;
    snapshot.device.connection_phase=if connected {"ready"}else{"offline"}.into();
    snapshot.device.message=message.into();
    snapshot.last_control=Some(CompanionV1ControlEcho{action,
        characteristic_uuid:COMPANION_V1_GATT_BOUNDARY.meeting_control_uuid,
        payload_hex:String::new(),accepted:connected,message:message.into()});
    if let Some(error)=error {Err(error)}else{Ok(())}
}

#[cfg(test)]
mod connection_outcome_tests {
    use super::*;
    #[test]
    fn r52_original_connection_replaces_stale_message_and_failed_sync_cannot_claim_connected() {
        let mut s=crate::companion_v1::fixture_snapshot();
        let request=crate::control_request(Action::MeetingStart,Some("original".into()));
        let mut row=crate::companion_v1::create_host_session(&s,&request,"");
        row.source="boardDevice".into();row.status="captured".into();row.audio_stored=true;
        s.host.sessions=vec![row];s.device.message="Not scanned".into();
        let saved=serde_json::to_vec(&s.host.sessions).unwrap();
        finish_original_connection(&mut s,Action::DeviceConnect,"原件已暂停",None).unwrap();
        assert!(s.connected&&s.device.connected);assert_eq!(s.device.message,"原件已暂停");
        let op=super::super::super::ble_bridge::CompanionBleOperation {provider_id:"windows-ble".into(),
            mode:"windows-native-sync-segmented".into(),ready:false,sync_paused:false,device_id:None,
            recording_path:None,recordings:vec![],device_identity:None,message:"native GATT session lost".into()};
        let error=finish_original_connection(&mut s,Action::MeetingStop,"已停止",Some(&op)).unwrap_err();
        assert!(!s.connected&&!s.device.connected);assert_eq!(s.device.connection_phase,"offline");
        assert_eq!(s.device.message,error);assert!(!s.last_control.as_ref().unwrap().accepted);
        assert_eq!(serde_json::to_vec(&s.host.sessions).unwrap(),saved,"a transport failure must retain the confirmed original and saved data");
    }
}
