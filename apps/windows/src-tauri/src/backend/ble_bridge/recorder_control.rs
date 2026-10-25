//! Exact CMC3 intent and original index precede every write. STOP confirmation
//! precedes receipt on this same connection owner.
use super::*;
use std::collections::BTreeSet;
use crate::backend::{recorder_control::{Command, Journal, Observation, Store},
    recording_wire::{SessionKey, control::{PausePeer, PauseStatus}}};
use super::pull_session::{NativeSubscriptions, SubscriptionLease};

type Observed=(PauseStatus,u32,u32,u8);
const RECORDER_SERVICE_UUID:Uuid=Uuid::from_u128(0x8f7a00087b7d4f3d9d6f6c2d1b7c0000);

fn recorder_channel(chars:&BTreeSet<Characteristic>)->Option<(Characteristic,Characteristic)> {
    let control=chars.iter().find(|c|c.service_uuid==RECORDER_SERVICE_UUID && c.uuid==MEETING_CONTROL_UUID
        && c.properties.contains(CharPropFlags::WRITE))?;
    let status=chars.iter().find(|c|c.service_uuid==RECORDER_SERVICE_UUID && c.uuid==MEETING_STATUS_UUID
        && c.properties.contains(CharPropFlags::READ|CharPropFlags::NOTIFY))?;
    Some((control.clone(),status.clone()))
}

async fn require_recorder_channel(device:&NativeDevice)->Result<(BTreeSet<Characteristic>,Characteristic,Characteristic),String> {
    let mut chars=device.peripheral.characteristics();
    if recorder_channel(&chars).is_none() {
        let started=StdInstant::now();
        eprintln!("recorder_gatt incomplete=1 service={RECORDER_SERVICE_UUID} characteristic_count={} targeted_refresh_attempts=1 same_connection=1",chars.len());
        #[cfg(target_os="windows")]
        bounded_ble_result("refresh required CMC3 service",StdDuration::from_secs(12),
            device.peripheral.refresh_service_without_descriptors(RECORDER_SERVICE_UUID)).await?;
        #[cfg(not(target_os="windows"))]
        return Err("设备缺少完整录音控制通道；原录音保留，未发送命令。".into());
        chars=device.peripheral.characteristics();
        eprintln!("recorder_gatt refreshed=1 service={RECORDER_SERVICE_UUID} characteristic_count={} complete={} elapsed_ms={}",chars.len(),recorder_channel(&chars).is_some(),started.elapsed().as_millis());
    }
    let (control,status)=recorder_channel(&chars)
        .ok_or("设备仍缺少完整的受保护录音控制通道；原录音保留，未发送命令。")?;
    Ok((chars,control,status))
}

fn sealed_end_report(device:&NativeDevice,journal:&Journal)->Result<CompanionMeetingControlReport,String> {
    let end=journal.sealed_catalogue_end.as_ref().ok_or("原封口证据缺失。")?;
    journal.validate_sealed_end()?;
    // Functional finalized state, explicitly NOT a live CMC3/STOP reply.
    // Zero request ID prevents inventing an acknowledgement for the old intent.
    Ok(CompanionMeetingControlReport{device_id:device.device_id(),request_id:0,state:2,last_error:0,
        meeting_id:journal.anchor.ok_or("原锚点缺失。")?,duration_ms:end.duration_ms,sync_state:0,
        logical_key:journal.key.as_ref().map(SessionKey::from_public).transpose()?})
}
fn fields(wire:&[u8])->Result<Observed,String> {
    let status=PauseStatus::decode(wire)?;
    Ok((status,u32::from_le_bytes(wire[12..16].try_into().unwrap()),
        u32::from_le_bytes(wire[20..24].try_into().unwrap()),wire[24]))
}

/// The normal protected connect observes an already running local capture.
/// Wait only for its current transition, without any CMC3 command or clock
/// write. The durable index and sidecar bind the actual device START token.
pub(super) async fn observe_local_original(device:&NativeDevice,
    peer:&crate::backend::recording_wire::transport::Peer)->Result<(Option<String>,bool),String> {
    let pause=PausePeer::from_verified_peer(peer)?;
    let (_,_,status)=require_recorder_channel(device).await?;
    let deadline=StdInstant::now()+StdDuration::from_secs(15);
    loop {
        let wire=bounded_ble_result("observe device-local original",remaining_deadline_budget(deadline,StdDuration::from_secs(8)),
            device.peripheral.read(&status)).await?;
        if wire.len()!=80 {
            let old=parse_meeting_status(&wire)?;
            if wire.len()!=64 || wire[32..44]!=peer.uid || wire[44..52]!=peer.epoch.to_le_bytes() {
                return Err("本地录音状态与已验证设备不同，未接管。".into());
            }
            return Ok((None,!matches!(old.state,0|2)));
        }
        let (observed,anchor,duration,_)=fields(&wire)?;
        if (observed.device_uid,observed.format_epoch)!=(peer.uid,peer.epoch) || observed.last_error!=0 {
            return Err("本地录音状态与已验证设备不同或存在错误，未接管。".into());
        }
        if observed.local_start.is_none() {return Ok((None,!matches!(observed.state,0|2)));}
        if matches!(observed.state,1|3) {
            let host=crate::backend::recorder_control::adopt_local(&crate::backend::persistence::state_file_path(),
                &pause,&device.device_id(),&observed,anchor,duration)?;
            eprintln!("recorder_local adopted=1 original_start={} original_anchor={anchor} source_ms={duration} sequence={} host_session={host} command_writes=0 clock_write=0",
                observed.local_start.unwrap(),observed.sequence);
            return Ok((Some(host),true));
        }
        if matches!(observed.state,0|2) {return Ok((None,false));}
        if StdInstant::now()>=deadline {return Err("设备本地录音仍在切换状态；原录音保留，未重开。".into());}
        tokio::time::sleep(StdDuration::from_millis(100)).await;
    }
}

/// A reboot can replace live CMS3 with an idle CMS2 while its original audio
/// remains durable. This only admits a read-only catalogue query; its complete
/// exact-session descriptors, not the idle status, must prove the original end.
fn idle_original_catalogue_query(command:u8,journal:&Journal,wire:&[u8])->Result<bool,String> {
    let current=parse_meeting_status(wire)?;
    let key=journal.key.as_ref().map(SessionKey::from_public).transpose()?;
    Ok(command==0 && wire.len()==64 && current.last_error==0 && matches!(current.state,0|2)
        && journal.confirmed.is_some() && journal.key.is_some() && journal.anchor.is_some()
        && !journal.unconfirmed_start_retry()
        && key.as_ref().is_some_and(|key|wire[32..44]==key.device_uid && wire[44..52]==key.format_epoch.to_le_bytes()))
}

async fn archived_original_end(device:&NativeDevice,chars:&BTreeSet<Characteristic>,status:&Characteristic,
    wire:&[u8],peer:&PausePeer,store:&mut Store,journal:&mut Journal)
    ->Result<CompanionMeetingControlReport,String> {
    let catalog=read_recording_catalog(device,chars).await?;
    let catalog_peer=catalog.peer.as_ref().ok_or("原目录协议缺失。")?;
    if (catalog_peer.uid,catalog_peer.epoch)!=peer.identity() {
        return Err("原封口目录芯片或存储代次不同；原录音保留。".into());
    }
    let key=journal.key.as_ref().map(SessionKey::from_public).transpose()?.ok_or("原会话尚未确认。")?;
    let mut originals:Vec<_>=catalog.entries.iter().filter_map(|e|e.segment.as_ref())
        .filter(|d|d.key==key).cloned().collect();
    let device_count=originals.len();
    let local=crate::backend::recording_wire::receiver::Receiver::verified_received_catalogue(
        &native_recording_root()?,&key,&device.device_id())?;
    let local_count=local.len();
    for d in local {
        if let Some(current)=originals.iter().find(|current|current.segment_index==d.segment_index) {
            if !current.same_content(&d) {return Err("原会话本机与设备封口身份不同；未声明结束。".into());}
        } else {originals.push(d);}
    }
    originals.sort_by_key(|d|d.segment_index);
    eprintln!("recorder_control archived_catalogue_sources device_segments={device_count} verified_local_segments={local_count} combined_segments={} terminal_required=1 command_writes=0",originals.len());
    let after=bounded_ble_result("recheck sealed original catalogue status",StdDuration::from_secs(8),device.peripheral.read(status)).await?;
    // Equality also preserves the original format/CRC/identity validation;
    // a new capture, changing duration or status cannot close the old row.
    if after!=wire {return Err("设备录音状态在目录读取期间变化；原会话保留，未声明结束。".into());}
    journal.end_from_sealed_catalogue(&originals)?;
    store.commit_bound(journal.clone())?;
    if let Some(anchor)=journal.anchor {
        offline_connection_lock()?.forget(&device.device_id(),journal.start_request,anchor);
    }
    eprintln!("recorder_control archived_catalogue_end=1 host_session={} original_anchor={} status_bytes={} command_writes=0 stop_ack_fabricated=0",
        journal.host_session,journal.anchor.unwrap_or(0),wire.len());
    sealed_end_report(device,journal)
}

#[derive(Debug,PartialEq,Eq)]
enum SettlementAction { Complete, Wait, Write(Command) }

/// A physical transition has no pending host command. Keep observing it
/// without a write; a queued previous stable status cannot finish that wait.
/// Only an explicit fresh START may write an unaccepted initial intent.
fn settlement_action(journal:&Journal,disposition:Observation,initial:bool,
    fresh_start:bool,write_floor:&mut Option<u32>)->Result<SettlementAction,String> {
    if initial {*write_floor=journal.pending.as_ref().map(|p|p.sequence);}
    if let Some(pending)=journal.pending.as_ref() {
        if initial && pending.command==1 && disposition==Observation::Previous && !fresh_start {
            return Err("设备尚未确认上次开始；可能已重启，未自动重新开录。原命令与会议保留。".into());
        }
        if disposition==Observation::Previous
            && (initial || write_floor.is_none_or(|sequence|pending.sequence>sequence)) {
            *write_floor=Some(pending.sequence);
            return Ok(SettlementAction::Write(pending.clone()));
        }
        return Ok(SettlementAction::Wait);
    }
    Ok(if disposition==Observation::Confirmed || (initial && disposition==Observation::Previous) {
        SettlementAction::Complete
    } else {SettlementAction::Wait})
}

async fn settle(device:&NativeDevice,control:&Characteristic,status:&Characteristic,
    peer:&PausePeer,store:&mut Store,journal:&mut Journal,initial:Option<Observed>,fresh_start:bool,
    subscription:&mut Option<SubscriptionLease<NativeSubscriptions>>)->Result<Observed,String> {
    let disposition=if let Some((s,anchor,duration,_))=initial.as_ref() {
        journal.observe_with_peer(peer,s,*anchor,*duration)?
    } else {Observation::Previous};
    store.commit_bound(journal.clone())?;
    let waiting_for_start=journal.pending.as_ref().is_some_and(|p|p.command==1);
    let mut write_floor=None;
    let first=settlement_action(journal,disposition,true,fresh_start,&mut write_floor)?;
    if first==SettlementAction::Complete {return initial.ok_or("实际确认缺失。".into());}
    let deadline=StdInstant::now()+env_timeout("COMPANION_TYPE_MEETING_STATUS_TIMEOUT_MS",60_000);
    let mut notifications=bounded_ble_result("CMC3 notifications",StdDuration::from_secs(8),device.peripheral.notifications()).await?;
    // The outer link guard can cancel this wait on a real session loss. Keep
    // an owned CCCD lease so that cancellation also releases an in-flight
    // subscription, just as the audio receiver already does.
    *subscription=Some(SubscriptionLease::pending(NativeSubscriptions::new(
        device.peripheral.clone(),vec![status.clone()]),StdDuration::from_secs(8)));
    subscription.as_mut().expect("owned CMC3 subscription")
        .subscribe_lanes(1,StdDuration::from_secs(8)).await?;
    let result:Result<Observed,String>=async {
        if let SettlementAction::Write(pending)=first {
            bounded_ble_result("write durable CMC3 command",remaining_deadline_budget(deadline,StdDuration::from_secs(8)),
                device.peripheral.write(control,&pending.wire,WriteType::WithResponse)).await?;
        }
        loop {
            if StdInstant::now()>=deadline {return Err("设备控制确认超时；原命令和原会议已保存，下次核对同一命令。".into());}
            let notified=match timeout(remaining_deadline_budget(deadline,StdDuration::from_millis(700)),notifications.next()).await {
                Ok(Some(n)) if n.uuid==MEETING_STATUS_UUID=>Some(n.value),
                Ok(None)=>return Err("录音确认通道已断开；原命令和原音保留。".into()),_=>None,
            };
            let wire=match notified {Some(wire)=>wire,None=>bounded_ble_result("read durable CMC3 confirmation",
                remaining_deadline_budget(deadline,StdDuration::from_secs(8)),device.peripheral.read(status)).await?};
            // A queued pre-START CMS2 idle notification is not a CMC3 ACK.
            if waiting_for_start && wire.len()==64 {
                let old=parse_meeting_status(&wire)?;
                if old.last_error==0 && matches!(old.state,0|2) {continue;}
            }
            let observed=fields(&wire)?;
            let disposition=journal.observe_with_peer(peer,&observed.0,observed.1,observed.2)?;
            store.commit_bound(journal.clone())?;
            match settlement_action(journal,disposition,false,false,&mut write_floor)? {
                SettlementAction::Complete=>return Ok(observed),
                SettlementAction::Wait=>{},
                SettlementAction::Write(rebased)=>{
                    bounded_ble_result("write rebased original STOP after physical control",
                        remaining_deadline_budget(deadline,StdDuration::from_secs(8)),
                        device.peripheral.write(control,&rebased.wire,WriteType::WithResponse)).await?;
                }
            }
        }
    }.await;
    if let Some(mut lease)=subscription.take() {lease.close().await;}
    result
}

pub(super) async fn execute_owned(
    device_id:&str,command:u8,max_seconds:u16,host_session:&str,
    expected_anchor:Option<u32>,expected_key:Option<&crate::companion_v1::CompanionV1RecordingKey>,
    fresh_start:bool,
) -> Result<(CompanionMeetingControlReport,Journal,NativeDevice),String> {
    if command>5 || (command!=1 && max_seconds!=0) {
        return Err("录音控制缺少原会话或有效命令；没有连接设备。".into());
    }
    let expected_key=expected_key.map(SessionKey::from_public).transpose()?;
    let mut store=Store::open(&crate::backend::persistence::state_file_path(),host_session)?;
    let mut journal=store.journal.clone().ok_or("原命令尚未耐久保存；未连接或新开录音。")?;
    let start_request=journal.start_request;
    if start_request==0 || normalize_device_id(&journal.device_id)!=normalize_device_id(device_id)
        || journal.anchor!=expected_anchor || journal.key.as_ref().map(SessionKey::from_public).transpose()?!=expected_key
        || (command==1 && journal.max_seconds!=max_seconds) {
        return Err("控制与耐久保存的原录音不同；未连接其它录音。".into());
    }
    let request=journal.pending.as_ref().map(|p|p.request)
        .or_else(||journal.confirmed.as_ref().map(|c|c.request)).ok_or("原命令缺失。")?;
    let retained=retained_offline_connection(Some(device_id),start_request,expected_anchor,request).await?;
    let reused=retained.is_some();
    let mut device=match retained {Some(lease)=>lease.device,
        // Retrying an original capture must not rewrite its clock.
        None=>connect_native_device_with_clock(Some(device_id),false).await?};
    // Own the subscription outside the cancellable work. On link loss both
    // an in-flight CCCD write and a confirmation wait are drained before the
    // connection closes, never left to unsubscribe a later fresh connection.
    let mut subscription=None;
    let link=NativeLinkGuard::capture(&device);
    let result=link.run(async {
        let (chars,control,status)=require_recorder_channel(&device).await?;
        let identity=read_recorder_control_identity(&device.peripheral,&chars).await?;
        let peer=PausePeer::from_status(&identity)?.ok_or("当前固件没有明确支持暂停；未停止重开。")?;
        journal.matches(&peer,host_session,&device.device_id())?;
        let actual_peer=crate::backend::recording_wire::transport::Peer::from_status(&identity)?.ok_or("逻辑录音能力缺失。")?;
        device.verified_uid=Some(hex_lower(&actual_peer.uid));device.recording_peer=Some(actual_peer.clone());device.user_connection=true;
        device.observed_identity=Some(parse_device_identity(Some(&identity),None,None));
        if journal.sealed_catalogue_end.is_some() {
            if !matches!(command,0|2|3) {return Err("原录音已封口，不能再暂停/继续或重开。".into());}
            store.commit_bound(journal.clone())?;
            if let Some(anchor)=journal.anchor {offline_connection_lock()?.forget(&device.device_id(),start_request,anchor);}
            return Ok((sealed_end_report(&device,&journal)?,journal.clone()));
        }
        let wire=bounded_ble_result("read original CMC3 recorder",StdDuration::from_secs(8),device.peripheral.read(&status)).await?;
        let mut observed=if wire.len()==80 {Some(fields(&wire)?)} else {
            // A new START switches CMS2 to CMS3. Before the switch require a
            // checked idle/sealed status; never manufacture an extended ACK.
            let old=parse_meeting_status(&wire)?;
            if idle_original_catalogue_query(command,&journal,&wire)? {
                let report=archived_original_end(&device,&chars,&status,&wire,&peer,&mut store,&mut journal).await?;
                return Ok((report,journal.clone()));
            }
            if journal.confirmed.is_some() || journal.pending.as_ref().is_none_or(|p|p.command!=1)
                || old.last_error!=0 || !matches!(old.state,0|2) {return Err("设备当前状态不能确认原开始请求；未重开。".into());}
            None
        };
        let mut disposition=Observation::Previous;
        if let Some((s,anchor,duration,_))=observed.as_ref() {
            match journal.observe_with_peer(&peer,s,*anchor,*duration) {
                Ok(value)=>{disposition=value;store.commit_bound(journal.clone())?;},
                Err(_) if command==0 && s.last_error==0 && matches!(s.state,0|2) => {
                    // The recorder only exposes the latest live CMS3. An old
                    // original may still have a complete immutable catalogue.
                    // Require one stable status around that protected snapshot;
                    // never infer completion merely because another ID is idle.
                    let report=archived_original_end(&device,&chars,&status,&wire,&peer,&mut store,&mut journal).await?;
                    return Ok((report,journal.clone()));
                },
                Err(error)=>return Err(error),
            }
        }
        if journal.confirmed.is_none() && journal.pending.as_ref().is_some_and(|p|p.command==1) {
            if let Some(capacity)=crate::backend::recording_capacity::parse(&identity) {
                if !capacity.busy {crate::backend::recording_capacity::check_start(&capacity,journal.max_seconds,
                    recording_sync::owned_follow_allowed(&device.device_id()))?;}
            }
        }
        // STOP settles the exact lost PAUSE/RESUME/START, then uses the next
        // sequence. Recovery only settles the original pending intent.
        if disposition==Observation::Accepted || (matches!(command,0|2|3) && journal.pending.is_some()) {
            observed=Some(settle(&device,&control,&status,&peer,&mut store,&mut journal,observed,false,&mut subscription).await?);
        }
        // Only an explicit START retry may resend an unaccepted initial
        // intent. Automatic QUERY/STOP recovery retains its no-restart guard.
        let allow_initial_start=fresh_start || (command==1 && journal.unconfirmed_start_retry());
        if command!=0 && journal.prepare(&peer,command)? {
            observed=Some(settle(&device,&control,&status,&peer,&mut store,&mut journal,observed,allow_initial_start,&mut subscription).await?);
        }
        let (observed,anchor,duration,sync_state)=observed.ok_or("设备尚未确认原控制。")?;
        if !matches!(observed.state,1|2|3) || observed.last_error!=0 || !observed.timeline {
            return Err("设备尚未到达稳定确认，未更新界面。".into());
        }
        // Repair an index write failure after the sidecar commit before any
        // receive/consume can proceed.
        store.commit_bound(journal.clone())?;
        let actual_peer=crate::backend::recording_wire::transport::Peer::from_status(&identity)?.ok_or("逻辑录音能力缺失。")?;
        device.verified_uid=Some(hex_lower(&actual_peer.uid));device.recording_peer=Some(actual_peer.clone());device.user_connection=true;
        device.observed_identity=Some(parse_device_identity(Some(&identity),None,None));
        if matches!(observed.state,1|3) {
            *VERIFIED_SEGMENTED_RECORDER.lock().map_err(|_|"连续录音身份锁不可用")?=Some((device.device_id(),actual_peer));
            let previous=offline_connection_lock()?.remember(offline_connection::Lease {
                device:device.clone(),device_id:device.device_id(),start_token:start_request,recording_id:anchor,logical_key:observed.key.clone(),
            })?;
            if let Some(previous)=previous {if normalize_device_id(&previous.device_id)!=normalize_device_id(&device.device_id()) {close_native_device(&previous.device).await;}}
        } else {offline_connection_lock()?.forget(&device.device_id(),start_request,anchor);}
        Ok((CompanionMeetingControlReport{device_id:device.device_id(),request_id:observed.request,state:observed.state,
            last_error:observed.last_error,meeting_id:anchor,duration_ms:duration,sync_state,logical_key:observed.key},journal.clone()))
    }).await;
    if let Some(mut lease)=subscription.take() {lease.close().await;}
    if result.is_err() {
        // A fresh START may have acquired its anchor immediately before the
        // loss callback. Retire that exact lease as well; the durable original
        // and its confirmed/pending command remain available for recovery.
        if let Some(anchor)=journal.anchor.or(expected_anchor) {offline_connection_lock()?.forget(device_id,start_request,anchor);}
        close_native_device(&device).await;
    }
    eprintln!("recorder_control scope=CMC3 original_session={host_session} command={command} connection_reused={reused} result_confirmed={}",result.is_ok());
    result.map(|(report,journal)|(report,journal,device))
}

#[cfg(test)]
mod gatt_tests {
    use super::*;

    fn local_fixture(index:usize,state:Option<u8>)->Observed {
        // Produced by the actual portable C recorder. Only explicit drain/
        // error cases below alter its bytes and recompute the protocol CRC.
        let bytes=include_bytes!("../cop1/tests/engine-local-controls.cms3");
        let mut wire=bytes[8+index*80..8+(index+1)*80].to_vec();
        if let Some(state)=state {wire[1]=state;let crc=crc32fast::hash(&wire[..76]);wire[76..].copy_from_slice(&crc.to_le_bytes());}
        fields(&wire).unwrap()
    }

    fn fixture_original(local:bool)->(PausePeer,Journal) {
        let (s,anchor,ms,_)=local_fixture(if local {8}else{0},None);
        let peer=PausePeer::from_verified_peer(&crate::backend::recording_wire::transport::Peer {
            uid:s.device_uid,epoch:s.format_epoch,capacity:64,max_value_bytes:248,
            logical_control:true,growing_tail:true,pause_control:true,batch_interval:true}).unwrap();
        let journal=if local {
            serde_json::from_value(serde_json::json!({
                "schema":1,"hostSession":"settlement-original","deviceId":"C8:92:FF:DD:3B:CA",
                "uid":s.device_uid,"epoch":s.format_epoch,"startRequest":s.local_start.unwrap(),
                "maxSeconds":0,"localOrigin":true,"key":s.key.as_ref().unwrap().public_key(),
                "anchor":anchor,"confirmed":{"command":s.command,"request":s.request,
                    "sequence":s.sequence,"state":s.state,"durationMs":ms,"localControl":true},"pending":null
            })).unwrap()
        } else {
            let mut j=Journal::start(&peer,"settlement-original","C8:92:FF:DD:3B:CA",s.request,600).unwrap();
            j.observe_with_peer(&peer,&s,anchor,ms).unwrap();j
        };
        journal.matches(&peer,&journal.host_session,&journal.device_id).unwrap();
        (peer,journal)
    }

    #[test]
    fn physical_transitions_wait_without_host_intent_and_ignore_previous_stable_notification() {
        let (peer,mut journal)=fixture_original(true);let start=journal.start_request;
        for (transient,stable,old) in [(9,10,8),(11,12,10)] {
            let mut floor=None;
            let (s,anchor,ms,_)=local_fixture(transient,None);
            let disposition=journal.observe_with_peer(&peer,&s,anchor,ms).unwrap();
            assert_eq!(disposition,Observation::Accepted);assert!(journal.pending.is_none());
            assert_eq!(settlement_action(&journal,disposition,true,false,&mut floor).unwrap(),SettlementAction::Wait);
            let (s,anchor,ms,_)=local_fixture(old,None);
            let disposition=journal.observe_with_peer(&peer,&s,anchor,ms).unwrap();
            assert_eq!(disposition,Observation::Previous);
            assert_eq!(settlement_action(&journal,disposition,false,false,&mut floor).unwrap(),SettlementAction::Wait,
                "an old queued stable notification is not completion of a newer physical transition");
            let (s,anchor,ms,_)=local_fixture(stable,None);
            let disposition=journal.observe_with_peer(&peer,&s,anchor,ms).unwrap();
            assert_eq!(settlement_action(&journal,disposition,false,false,&mut floor).unwrap(),SettlementAction::Complete);
            assert_eq!(floor,None,"QUERY/physical pause/resume must never send a CMC3 command");
            assert_eq!(journal.start_request,start);assert!(journal.pending.is_none());
        }
    }

    #[test]
    fn physical_stop_drain_waits_for_same_original_and_does_not_fabricate_stop_ack() {
        for local in [false,true] {
            let (peer,mut journal)=fixture_original(local);let original=journal.clone();let mut floor=None;
            let (s,anchor,ms,_)=local_fixture(if local {8}else{0},Some(6));
            let disposition=journal.observe_with_peer(&peer,&s,anchor,ms).unwrap();
            assert_eq!(disposition,Observation::Accepted);assert_eq!(journal,original);
            assert_eq!(settlement_action(&journal,disposition,true,false,&mut floor).unwrap(),SettlementAction::Wait);
            for field in 0..4 {
                let mut bad=s.clone();let mut id=anchor;
                match field {0=>bad.device_uid[0]^=1,1=>bad.last_error=1,2=>id+=1,_=>bad.key.as_mut().unwrap().session_id+=1}
                assert!(journal.observe_with_peer(&peer,&bad,id,ms).is_err());assert_eq!(journal,original);
            }
            let (ended,anchor,ms,_)=local_fixture(if local {8}else{0},Some(2));
            let disposition=journal.observe_with_peer(&peer,&ended,anchor,ms).unwrap();
            assert_eq!(settlement_action(&journal,disposition,false,false,&mut floor).unwrap(),SettlementAction::Complete);
            let c=journal.confirmed.as_ref().unwrap();assert!(c.finished_locally);assert_eq!(c.command,1);
            assert_eq!(c.request,original.start_request);assert_eq!(floor,None);assert!(journal.pending.is_none());
            let sealed=journal.clone();
            assert!(journal.observe_with_peer(&peer,&s,anchor,ms).is_err(),"a delayed draining status cannot revive an ended original");
            assert_eq!(journal,sealed);
        }
    }

    #[test]
    fn pending_stop_survives_physical_transition_and_writes_only_the_rebased_sequence() {
        let (peer,mut journal)=fixture_original(true);journal.prepare(&peer,2).unwrap();
        let original_stop=journal.pending.clone().unwrap();let mut floor=None;
        let (s,anchor,ms,_)=local_fixture(9,None);
        let disposition=journal.observe_with_peer(&peer,&s,anchor,ms).unwrap();
        assert_eq!(settlement_action(&journal,disposition,true,false,&mut floor).unwrap(),SettlementAction::Wait);
        assert_eq!(journal.pending.as_ref(),Some(&original_stop));
        let (s,anchor,ms,_)=local_fixture(10,None);
        let disposition=journal.observe_with_peer(&peer,&s,anchor,ms).unwrap();
        let rebased=match settlement_action(&journal,disposition,false,false,&mut floor).unwrap() {
            SettlementAction::Write(command)=>command,other=>panic!("STOP must follow physical PAUSE: {other:?}"),
        };
        assert_eq!(rebased.command,2);assert_eq!(rebased.sequence,2);assert_eq!(journal.superseded.as_ref(),Some(&original_stop));
        assert_eq!(settlement_action(&journal,Observation::Previous,false,false,&mut floor).unwrap(),SettlementAction::Wait,
            "repeated notifications must not resend rebased STOP");
        // Model the exact remote STOP response after its one allowed write.
        let mut final_status=s;final_status.local_start=None;final_status.state=2;final_status.command=2;
        final_status.sequence=rebased.sequence;final_status.request=rebased.request;
        let disposition=journal.observe_with_peer(&peer,&final_status,anchor,ms).unwrap();
        assert_eq!(settlement_action(&journal,disposition,false,false,&mut floor).unwrap(),SettlementAction::Complete);
        assert!(!journal.confirmed.as_ref().unwrap().finished_locally);assert!(journal.pending.is_none());
    }

    #[test]
    fn automatic_settlement_never_writes_an_unaccepted_replacement_start() {
        let (peer,original)=fixture_original(false);
        let journal=Journal::start(&peer,&original.host_session,&original.device_id,original.start_request,600).unwrap();
        let mut floor=None;
        assert!(settlement_action(&journal,Observation::Previous,true,false,&mut floor).is_err());
        let write=settlement_action(&journal,Observation::Previous,true,true,&mut floor).unwrap();
        assert_eq!(write,SettlementAction::Write(journal.pending.clone().unwrap()));
        assert_eq!(settlement_action(&journal,Observation::Accepted,false,false,&mut floor).unwrap(),SettlementAction::Wait);
        assert_eq!(journal.pending.as_ref().unwrap().sequence,0);
    }

    #[test]
    fn reboot_idle_cms2_can_only_query_the_same_confirmed_original_catalogue() {
        // The R36 paused original: CMS3 command4 was durable, but the next
        // native connection found base CMS2 after uptime returned to~25s.
        let mut journal:Journal=serde_json::from_value(serde_json::json!({
            "schema":1,"hostSession":"r36-paused-original","deviceId":"C8:92:FF:DD:3B:CA",
            "uid":[24,0,16,0,13,80,51,87,84,54,55,32],"epoch":13310445085575704248u64,
            "startRequest":452280907,"maxSeconds":150,
            "key":{"deviceUid":"180010000d50335754363720","formatEpoch":"b8b8334898156eb8","sessionId":"0000000000000007"},
            "anchor":12,"confirmed":{"command":4,"request":1943436034,"sequence":1,"state":3,"durationMs":8300,"finishedLocally":false},
            "pending":null
        })).unwrap();
        let key=SessionKey::from_public(journal.key.as_ref().unwrap()).unwrap();
        let mut wire=vec![0;64];wire[0]=1;wire[28..32].copy_from_slice(b"CMS2");
        wire[32..44].copy_from_slice(&key.device_uid);wire[44..52].copy_from_slice(&key.format_epoch.to_le_bytes());
        let seal=|wire:&mut Vec<u8>|{let crc=crc32fast::hash(&wire[..60]);wire[60..64].copy_from_slice(&crc.to_le_bytes());};
        seal(&mut wire);
        assert!(idle_original_catalogue_query(0,&journal,&wire).unwrap());
        let original=journal.clone();
        for command in 1..=5 {assert!(!idle_original_catalogue_query(command,&journal,&wire).unwrap());}
        assert_eq!(journal,original,"a status can never end or rewrite the original by itself");
        for variant in 0..5 {
            let mut bad=wire.clone();
            match variant {0=>bad[1]=1,1=>bad[1]=3,2=>bad[2]=1,3=>bad[32]^=1,_=>bad[44]^=1};
            seal(&mut bad);assert!(!idle_original_catalogue_query(0,&journal,&bad).unwrap());
        }
        let mut corrupt=wire.clone();corrupt[60]^=1;
        assert!(idle_original_catalogue_query(0,&journal,&corrupt).is_err());
        journal.confirmed=None;
        assert!(!idle_original_catalogue_query(0,&journal,&wire).unwrap());
    }

    #[test]
    fn recorder_channel_requires_both_characteristics_properties_and_exact_service() {
        let characteristic=|uuid,properties| Characteristic {
            uuid,service_uuid:RECORDER_SERVICE_UUID,properties,descriptors:BTreeSet::new(),
        };
        let control=characteristic(MEETING_CONTROL_UUID,CharPropFlags::WRITE);
        let status=characteristic(MEETING_STATUS_UUID,CharPropFlags::READ|CharPropFlags::NOTIFY);
        let complete=BTreeSet::from([control.clone(),status.clone()]);
        assert!(recorder_channel(&complete).is_some());
        assert_eq!(RECORDER_SERVICE_UUID.to_string(),crate::companion_v1::COMPANION_V1_GATT_BOUNDARY.meeting_service_uuid);
        for incomplete in [BTreeSet::new(),BTreeSet::from([control.clone()]),BTreeSet::from([status.clone()])] {
            assert!(recorder_channel(&incomplete).is_none());
        }
        let mut wrong=control.clone();wrong.properties=CharPropFlags::WRITE_WITHOUT_RESPONSE;
        assert!(recorder_channel(&BTreeSet::from([wrong,status.clone()])).is_none());
        let mut wrong=status.clone();wrong.properties=CharPropFlags::READ|CharPropFlags::INDICATE;
        assert!(recorder_channel(&BTreeSet::from([control.clone(),wrong])).is_none());
        for change_control in [false,true] {
            let (mut c,mut s)=(control.clone(),status.clone());
            if change_control { c.service_uuid=Uuid::nil(); } else { s.service_uuid=Uuid::nil(); }
            assert!(recorder_channel(&BTreeSet::from([c,s])).is_none());
        }
    }
}
