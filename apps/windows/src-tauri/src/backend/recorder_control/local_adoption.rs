//! A protected device-local capture can acquire a durable host controller.
//! This observes the real START; it never constructs/sends a START command.
use super::*;
use crate::companion_v1::{CompanionV1ControlRequest,
    CompanionV1HostSession,CompanionV1Snapshot};

fn rows(path:&Path)->Result<Vec<CompanionV1HostSession>,String> {
    let loaded=super::super::session_store::load(path);
    if loaded.state.status=="blocked" {return Err(failure("录音库不可读，未接管设备原录音"));}
    loaded.bytes.map(|b|serde_json::from_slice(&b).map_err(|_|failure("录音库格式无效")))
        .transpose().map(Option::unwrap_or_default)
}

impl Journal {
    fn from_local(peer:&PausePeer,host:&str,device:&str,status:&PauseStatus,
        anchor:u32,duration:u32)->Result<Self,String> {
        let start=status.local_start.ok_or_else(||failure("没有设备本地开始证据"))?;
        let key=status.key.as_ref().ok_or_else(||failure("设备原会话缺失"))?;
        if !same_device(device,device) || host.is_empty() || anchor==0 || start==0
            || peer.identity()!=(status.device_uid,status.format_epoch)
            || (key.device_uid,key.format_epoch)!=peer.identity() || key.session_id==0
            || !status.timeline || status.last_error!=0 || !matches!(status.state,1|3)
            || stable_state(status.command)!=Some(status.state) || status.request==0
            || (status.sequence==0)!=(status.command==1)
            || (status.command==1 && status.request!=start) {
            return Err(failure("设备本地录音尚无完整稳定身份"));
        }
        let journal=Self{schema:1,host_session:host.into(),device_id:device.into(),
            uid:status.device_uid,epoch:status.format_epoch,start_request:start,max_seconds:0,local_origin:true,
            key:Some(key.public_key()),anchor:Some(anchor),pending:None,superseded:None,sealed_catalogue_end:None,end_reason:None,
            confirmed:Some(Confirmed{command:status.command,request:status.request,sequence:status.sequence,
                state:status.state,duration_ms:duration,finished_locally:false,local_control:true})};
        journal.matches(peer,host,device)?;Ok(journal)
    }
}

pub(crate) fn adopt_local(path:&Path,peer:&PausePeer,device:&str,status:&PauseStatus,
    anchor:u32,duration:u32)->Result<String,String> {
    // Validate before opening or modifying an index/sidecar.
    let checked=Journal::from_local(peer,"local-validation",device,status,anchor,duration)?;
    let key=status.key.as_ref().ok_or_else(||failure("本地录音身份缺失"))?;
    let public=key.public_key();let existing=rows(path)?;
    let matches:Vec<_>=existing.iter().filter(|r|r.device_recording_key.as_ref()==Some(&public)).collect();
    if matches.len()>1 {return Err(failure("同一设备原录音有重复索引，未创建第三份"));}
    let host=matches.first().map(|r|r.id.clone()).unwrap_or_else(||
        format!("board-session-{:x}",Sha256::digest(serde_json::to_vec(key).expect("session key serialization"))));
    let mut store=Store::open(path,&host)?;
    let indexed=matches.first().and_then(|r|r.recorder_control.clone());
    let mut journal=store.journal.clone().or(indexed).unwrap_or_else(||Journal{host_session:host.clone(),..checked});
    journal.matches(peer,&host,device)?;
    if journal.key.as_ref()!=Some(&public) || journal.anchor!=Some(anchor) || journal.start_request!=status.local_start.unwrap() {
        return Err(failure("已保存控制属于另一原件，未替换"));
    }
    journal.observe_with_peer(peer,status,anchor,duration)?;
    super::super::session_store::update_checked(path,|all| {
        if all.iter().any(|r|r.status=="recording" && r.id!=host)
            || all.iter().filter(|r|r.device_recording_key.as_ref()==Some(&public)).count()>1 {
            return Err(failure("另一场录音仍未结束，未接管或重开"));
        }
        if let Some(row)=all.iter_mut().find(|r|r.id==host) {
            if row.audio_stored || row.source!="boardDevice" || row.device_recording_key.as_ref()!=Some(&public) {
                return Err(failure("索引不是这场仍在进行的设备原录音"));
            }
            journal.checkpoint_row(row)?;
        } else {
            if all.iter().any(|r|r.device_recording_key.as_ref()==Some(&public)) {return Err(failure("原录音已由另一行接收"));}
            let request:CompanionV1ControlRequest=serde_json::from_value(serde_json::json!({
                "action":"meetingStart","sessionId":host,"deviceId":device,"title":"设备录音",
                "meetingMode":"offlineStore","promptId":crate::companion_v1::CAPTURE_ONLY_PROMPT
            })).map_err(|_|failure("设备录音行无法建立"))?;
            let mut row=crate::companion_v1::create_host_session(&crate::companion_v1::fixture_snapshot(),&request,"");
            row.processing_policy=super::super::product_settings::new_card_processing_policy();
            row.source="boardDevice".into();row.source_device_id=Some(device.into());row.audio_path=None;
            row.audio_stored=false;row.audio_bytes=0;row.chunks.clear();row.started_at=None;row.stopped_at=None;
            row.retention.audio_cached=false;journal.checkpoint_row(&mut row)?;all.insert(0,row);
        }
        Ok(())
    })?;
    // An index write failure never authorizes control; a partial success is
    // recoverable by the same deterministic key, not a fresh local START.
    store.commit_bound(journal)?;Ok(host)
}

pub(crate) fn restore_connected_local(snapshot:&mut CompanionV1Snapshot,device:&str)->Result<(),String> {
    let hosts:Vec<_>=snapshot.host.sessions.iter().filter(|r|r.status=="recording"
        && r.source_device_id.as_deref().is_some_and(|d|same_device(d,device))
        && r.recorder_control.as_ref().is_some_and(|j|j.local_origin && !j.ended()))
        .map(|r|r.id.clone()).collect();
    if hosts.len()>1 {return Err(failure("存在多份进行中的设备原件，未猜选控制对象"));}
    if let Some(host)=hosts.first() {super::application::restore_snapshot(snapshot,host)?;}
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    const DEVICE:&str="C8:92:FF:DD:3B:CA";
    fn observed(i:usize)->(PausePeer,PauseStatus,u32,u32) {
        let bytes=include_bytes!("../cop1/tests/engine-local-controls.cms3");
        let raw=&bytes[8+i*80..8+(i+1)*80];let status=PauseStatus::decode(raw).unwrap();
        let peer=PausePeer::from_verified_peer(&crate::backend::recording_wire::transport::Peer{
            uid:status.device_uid,epoch:status.format_epoch,capacity:64,max_value_bytes:248,
            logical_control:true,growing_tail:true,pause_control:true,batch_interval:true}).unwrap();
        (peer,status,u32::from_le_bytes(raw[12..16].try_into().unwrap()),u32::from_le_bytes(raw[20..24].try_into().unwrap()))
    }
    struct Temp(PathBuf);
    impl Temp {fn new()->Self {let path=std::env::temp_dir().join(format!("companion-local-adopt-{}",uuid::Uuid::new_v4()));
        fs::create_dir_all(&path).unwrap();Self(path.join("sessions.json"))}}
    impl Drop for Temp {fn drop(&mut self){let _=fs::remove_dir_all(self.0.parent().unwrap());}}
    #[test]
    fn c_local_start_adopts_without_start_wire_then_remote_control_keeps_real_token() {
        let t=Temp::new();let (peer,status,anchor,ms)=observed(8);
        let host=adopt_local(&t.0,&peer,DEVICE,&status,anchor,ms).unwrap();
        let saved=rows(&t.0).unwrap();assert_eq!(saved.len(),1);
        let row=&saved[0];assert_eq!(row.id,host);assert!(row.started_at.is_none()&&row.audio_path.is_none()&&!row.audio_stored);
        assert_eq!(row.processing_policy,super::super::super::product_settings::new_card_processing_policy());
        assert_eq!(row.device_recording_key,Some(status.key.as_ref().unwrap().public_key()));
        let mut store=Store::open(&t.0,&host).unwrap();let mut journal=store.journal.clone().unwrap();
        assert!(journal.local_origin&&journal.max_seconds==0&&journal.pending.is_none());
        assert_eq!(journal.start_request,status.local_start.unwrap());
        assert!(journal.prepare(&peer,1).is_err(),"adoption never permits START retry");
        assert!(journal.prepare(&peer,4).unwrap());let pending=journal.pending.as_ref().unwrap();
        assert_eq!(pending.sequence,1);assert_eq!(&pending.wire[40..44],&status.local_start.unwrap().to_le_bytes());
        assert_ne!(journal.start_request,crate::backend::ble_bridge::meeting_idempotency_request_id(&host,1));
        store.commit_bound(journal).unwrap();drop(store);
        assert!(Store::open(&t.0,&host).unwrap().journal.unwrap().pending.is_some());
    }
    #[test]
    fn c_paused_original_reopens_idempotently_without_inventing_start_time_or_duration_limit() {
        let t=Temp::new();let (peer,first,anchor,ms)=observed(8);
        let host=adopt_local(&t.0,&peer,DEVICE,&first,anchor,ms).unwrap();
        let (_,paused,anchor,ms)=observed(10);
        assert_eq!(adopt_local(&t.0,&peer,DEVICE,&paused,anchor,ms).unwrap(),host);
        assert_eq!(adopt_local(&t.0,&peer,DEVICE,&paused,anchor,ms).unwrap(),host);
        let saved=rows(&t.0).unwrap();assert_eq!(saved.len(),1);
        let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.source="lastKnown";
        snapshot.host.sessions=saved;snapshot.host.active_session_id=None;snapshot.host.selected_session_id=None;
        snapshot.device.device_id=Some(DEVICE.into());
        assert!(super::super::restart_recovery_request(&snapshot,DEVICE).is_some());
        let mut journal=Store::open(&t.0,&host).unwrap().journal.unwrap();
        assert_eq!(journal.confirmed.as_ref().unwrap().state,3);assert!(journal.prepare(&peer,5).unwrap());
        assert_eq!(journal.pending.as_ref().unwrap().sequence,2);
        assert!(snapshot.host.sessions[0].started_at.is_none());
    }
    #[test]
    fn stale_foreign_transient_remote_or_finished_state_cannot_replace_local_original() {
        let t=Temp::new();let (peer,first,anchor,ms)=observed(8);
        let host=adopt_local(&t.0,&peer,DEVICE,&first,anchor,ms).unwrap();
        let (_,paused,anchor,ms)=observed(10);adopt_local(&t.0,&peer,DEVICE,&paused,anchor,ms).unwrap();
        let before=fs::read(&t.0).unwrap();let sidecar=Store::open(&t.0,&host).unwrap().path.clone();let control=fs::read(&sidecar).unwrap();
        for i in [0usize,8,9,11,13,15] {
            let (_,status,a,d)=observed(i);assert!(adopt_local(&t.0,&peer,DEVICE,&status,a,d).is_err(),"C state {i}");
            assert_eq!(fs::read(&t.0).unwrap(),before);assert_eq!(fs::read(&sidecar).unwrap(),control);
        }
        for which in 0..5 {
            let mut bad=paused.clone();let mut a=anchor;
            match which {0=>bad.device_uid[0]^=1,1=>bad.format_epoch+=1,2=>bad.local_start=Some(999),
                3=>a+=1,_=>bad.key.as_mut().unwrap().session_id+=1};
            assert!(adopt_local(&t.0,&peer,DEVICE,&bad,a,ms).is_err());
            assert_eq!(fs::read(&t.0).unwrap(),before);assert_eq!(fs::read(&sidecar).unwrap(),control);
        }
    }
}
