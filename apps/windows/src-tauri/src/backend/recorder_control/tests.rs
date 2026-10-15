use super::*;

#[test]
fn actual_fw212_start_preparation_waits_without_confirmation_or_replacement_start() {
    let hex=|s:&str|s.as_bytes().chunks_exact(2).map(|p|
        u8::from_str_radix(std::str::from_utf8(p).unwrap(),16).unwrap()).collect::<Vec<_>>();
    // Actual protected request/reply from the failed installed product HCI.
    let request=hex("434d433303010201180010000d50335754363720e13649cf7ab2591f00000000000000009a08162f9a08162f5e01000000000000a814f39c");
    let wire=hex("01000000000000009a08162f00000000000000000000000000000000434d5333180010000d50335754363720e13649cf7ab2591f0000000000000000000000000101000000000000000000007852675b");
    let s=PauseStatus::decode(&wire).unwrap();
    let peer=PausePeer::from_verified_peer(&crate::backend::recording_wire::transport::Peer {
        uid:s.device_uid,epoch:s.format_epoch,capacity:64,max_value_bytes:248,logical_control:true,
        growing_tail:true,pause_control:true,batch_interval:true}).unwrap();
    let mut j=Journal::start(&peer,HOST,DEVICE,s.request,350).unwrap();
    assert_eq!(j.pending.as_ref().unwrap().wire,request);
    let before=j.clone();
    assert_eq!(j.observe(&s,0,0).unwrap(),Observation::Accepted);assert_eq!(j,before);
    assert!(j.pending.is_some()&&j.confirmed.is_none()&&j.key.is_none()&&j.anchor.is_none());
    for which in 0..6 {
        let mut invalid=s.clone();let (anchor,duration)=match which {
            0=>{invalid.last_error=1;(0,0)},1=>{invalid.timeline=false;(0,0)},
            2=>{invalid.state=1;(0,0)},3=>{invalid.device_uid[0]^=1;(0,0)},
            4=>(1,0),_=>(0,10)};
        assert!(j.observe(&invalid,anchor,duration).is_err());assert_eq!(j,before);
    }
    let mut stable=s;stable.state=1;
    stable.key=Some(SessionKey{device_uid:stable.device_uid,format_epoch:stable.format_epoch,session_id:7});
    assert_eq!(j.observe(&stable,15,10).unwrap(),Observation::Confirmed);
    assert!(j.pending.is_none());assert_eq!(j.anchor,Some(15));
}

fn peer()->PausePeer {
    let mut s=vec![0;116];s[0]=1;s[12..16].copy_from_slice(&0x57424155u32.to_le_bytes());
    for (i,b) in s[20..32].iter_mut().enumerate(){*b=(i+1) as u8;}
    let p=&mut s[84..];p[..4].copy_from_slice(b"CRV2");p[4..6].copy_from_slice(&2u16.to_le_bytes());
    p[6..8].copy_from_slice(&32u16.to_le_bytes());p[8..12].copy_from_slice(&127u32.to_le_bytes());
    p[12..20].copy_from_slice(&7u64.to_le_bytes());p[20..22].copy_from_slice(&64u16.to_le_bytes());
    p[22..24].copy_from_slice(&1024u16.to_le_bytes());p[24..26].copy_from_slice(&248u16.to_le_bytes());
    let crc=crc32fast::hash(&p[..28]);p[28..32].copy_from_slice(&crc.to_le_bytes());
    PausePeer::from_status(&s).unwrap().unwrap()
}
const DEVICE:&str="C8:92:FF:DD:3B:CA";
const HOST:&str="pause-original";
fn golden()->&'static [u8] {include_bytes!("../cop1/tests/engine-pause-control.cpc3")}
fn vector(index:usize)->&'static [u8] {&golden()[8+index*137..8+(index+1)*137]}
fn c_status(index:usize)->(PauseStatus,u32,u32) {
    let wire=&vector(index)[56..136];(PauseStatus::decode(wire).unwrap(),
        u32::from_le_bytes(wire[12..16].try_into().unwrap()),u32::from_le_bytes(wire[20..24].try_into().unwrap()))
}
fn start()->Journal {
    let wire=&vector(0)[..56];let j=Journal::start(&peer(),HOST,DEVICE,
        u32::from_le_bytes(wire[36..40].try_into().unwrap()),u16::from_le_bytes(wire[44..46].try_into().unwrap())).unwrap();
    assert_eq!(j.pending.as_ref().unwrap().wire,wire);j
}
fn running()->Journal {
    let mut j=start();let (s,id,ms)=c_status(0);assert_eq!(j.observe(&s,id,ms).unwrap(),Observation::Confirmed);j
}

fn sealed_catalogue(j:&Journal)->Vec<crate::backend::recording_wire::Descriptor> {
    use crate::backend::recording_wire::{Descriptor,SessionKey};
    let key=SessionKey::from_public(j.key.as_ref().unwrap()).unwrap();
    (0..2).map(|i|Descriptor{key:key.clone(),recording_id:j.anchor.unwrap()+i,
        segment_index:i,sample_offset:u64::from(i)*64000,sample_count:64000,
        encoded_length:2012,content_crc32:42,sha256:[42;32],total_segments:if i==1 {2}else{0},
        flags:if i==1 {7}else{1},codec:3,source_mode:1,sync_state:0}).collect()
}

#[test]
fn archived_original_end_keeps_actual_intent_and_persists_without_a_stop_ack_or_new_start() {
    let root=Temp::new();let path=root.0.join("sessions.json");let mut j=running();
    j.prepare(&peer(),4).unwrap();let confirmed=j.confirmed.clone();let pending=j.pending.clone();
    let mut row=original_row(&j);row.audio_stored=false;
    super::super::session_store::save(&path,&[row]).unwrap();
    j.end_from_sealed_catalogue(&sealed_catalogue(&j)).unwrap();j.matches(&peer(),HOST,DEVICE).unwrap();
    assert!(j.ended());assert_eq!(j.confirmed,confirmed);assert_eq!(j.pending,pending);
    assert!(j.prepare(&peer(),1).is_err());assert!(j.prepare(&peer(),2).is_err());
    let mut store=Store::open(&path,HOST).unwrap();store.commit_bound(j.clone()).unwrap();drop(store);
    let loaded=super::super::persistence::load_sessions_from(&path).unwrap();let row=&loaded[0];
    assert_eq!(row.id,HOST);assert_eq!(row.status,"captured");assert_eq!(row.duration_ms,8000);
    assert!(row.capture_incomplete);assert!(!row.audio_stored);assert!(!row.device_reclaimed);
    assert!(!row.recorder_control_uncertain);assert!(row.stopped_at.is_none());
    assert_eq!(row.pending_reason.as_deref(),Some("needs_device_sync"));
    assert_eq!(row.recorder_control.as_ref(),Some(&j));
    assert_eq!(Store::open(&path,HOST).unwrap().journal,Some(j));
}

#[test]
fn archived_original_rejects_wrong_scope_missing_terminal_holes_and_corruption_without_mutation() {
    for variant in 0..10 {
        let mut j=running();let before=j.clone();let mut items=sealed_catalogue(&j);
        match variant {
            0=>items[0].key.device_uid[0]^=1,1=>items[0].key.format_epoch+=1,
            2=>items[0].key.session_id+=1,3=>items[0].recording_id+=10,
            4=>{items[1].flags=1;items[1].total_segments=0;},
            5=>{items.remove(0);},6=>items[1].sample_offset+=320,
            7=>items[1].sha256=[0;32],8=>items[1].source_mode=2,_=>items[1].encoded_length=1,
        }
        assert!(j.end_from_sealed_catalogue(&items).is_err(),"variant {variant}");assert_eq!(j,before);
    }
    let mut j=running();j.end_from_sealed_catalogue(&sealed_catalogue(&j)).unwrap();
    let mut json=serde_json::to_value(&j).unwrap();json["sealedCatalogueEnd"]["anchor"]=123.into();
    let bad:Journal=serde_json::from_value(json).unwrap();assert!(bad.matches(&peer(),HOST,DEVICE).is_err());
}
struct Temp(PathBuf);
impl Temp {fn new()->Self {let p=std::env::temp_dir().join(format!("companion-recorder-journal-{}",uuid::Uuid::new_v4()));fs::create_dir(&p).unwrap();Self(p)}}
impl Drop for Temp {fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}

#[test]
fn exact_c_transitions_cannot_confirm_pausing_or_resuming_and_repeat_is_previous() {
    let peer=peer();let mut j=start();
    for index in 0..6 {
        let v=vector(index);let (s,id,ms)=c_status(index);
        if j.pending.is_none() && index!=3 {
            // Preserve the actual C coordinator intent/CRC and unmodified
            // CMS3 reply. C's request IDs differ from our SHA-derived IDs.
            j.pending=Some(Command{command:v[5],request:u32::from_le_bytes(v[36..40].try_into().unwrap()),
                sequence:u32::from_le_bytes(v[48..52].try_into().unwrap()),wire:v[..56].to_vec()});
        }
        j.matches(&peer,HOST,DEVICE).unwrap();
        let expected=match index {1|4=>Observation::Accepted,3=>Observation::Previous,_=>Observation::Confirmed};
        assert_eq!(j.observe(&s,id,ms).unwrap(),expected);
        assert_eq!(j.pending.is_some(),matches!(index,1|4));
    }
    let (stale,id,ms)=c_status(6);let before=j.clone();assert!(j.observe(&stale,id,ms).is_err());assert_eq!(j,before);
}

#[test]
fn pending_pause_survives_process_reopen_with_same_wire_sequence_and_cross_process_lock() {
    let root=Temp::new();let path=root.0.join("sessions.json");let peer=peer();
    let mut j=running();assert!(j.prepare(&peer,4).unwrap());let original=j.pending.clone().unwrap();
    let mut store=Store::open(&path,HOST).unwrap();store.commit(j).unwrap();
    assert!(Store::open(&path,HOST).is_err(),"second controller cannot reserve the next sequence");drop(store);
    let mut reopened=Store::open(&path,HOST).unwrap();let mut j=reopened.journal.clone().unwrap();
    j.matches(&peer,HOST,DEVICE).unwrap();assert!(j.prepare(&peer,4).unwrap());assert_eq!(j.pending.as_ref(),Some(&original));
    assert!(j.prepare(&peer,5).is_err());assert!(j.prepare(&peer,2).is_err());
    assert_eq!(j.pending.as_ref(),Some(&original));reopened.commit(j).unwrap();drop(reopened);
    assert_eq!(Store::open(&path,HOST).unwrap().journal.unwrap().pending.unwrap(),original);
}

#[test]
fn lost_start_ack_can_confirm_original_and_retry_does_not_create_another_start() {
    let root=Temp::new();let path=root.0.join("sessions.json");let mut store=Store::open(&path,HOST).unwrap();
    store.commit(start()).unwrap();drop(store);
    let mut store=Store::open(&path,HOST).unwrap();let mut j=store.journal.clone().unwrap();
    let (s,id,ms)=c_status(0);assert_eq!(j.observe(&s,id,ms).unwrap(),Observation::Confirmed);
    assert!(!j.prepare(&peer(),1).unwrap());store.commit(j.clone()).unwrap();drop(store);
    assert_eq!(Store::open(&path,HOST).unwrap().journal,Some(j));
}

#[test]
fn wrong_confirmations_and_corrupt_journals_never_authorize_a_new_control() {
    let peer=peer();let mut j=start();let (s,id,ms)=c_status(0);
    for which in 0..8 {
        let mut wrong=s.clone();let mut anchor=id;
        match which {0=>wrong.device_uid[0]^=1,1=>wrong.format_epoch+=1,2=>wrong.request+=1,
            3=>wrong.sequence+=1,4=>wrong.command=4,5=>wrong.timeline=false,6=>wrong.last_error=1,_=>anchor=0};
        let before=j.clone();assert!(j.observe(&wrong,anchor,ms).is_err(),"{which}");assert_eq!(j,before);
    }
    j.observe(&s,id,ms).unwrap();assert!(j.prepare(&peer,4).unwrap());
    let mut corrupt=j.clone();corrupt.pending.as_mut().unwrap().wire[36]^=1;
    assert!(corrupt.matches(&peer,HOST,DEVICE).is_err());
    assert!(j.matches(&peer,"another",DEVICE).is_err());assert!(j.matches(&peer,HOST,"C8:92:FF:DD:3B:CB").is_err());
    let root=Temp::new();let path=root.0.join("sessions.json");let store=Store::open(&path,HOST).unwrap();
    fs::write(&store.path,b"broken").unwrap();drop(store);assert!(Store::open(&path,HOST).is_err());
    fs::remove_file(root.0.join("recorder-controls").join(format!("{:x}.json",Sha256::digest(HOST.as_bytes())))).unwrap();
    fs::write(root.0.join("recorder-controls-blocked"),b"not a directory").unwrap();
    assert!(Store::open(&root.0.join("recorder-controls-blocked/sessions.json"),HOST).is_err());
}

#[test]
fn sequence_exhaustion_leaves_a_last_stop_and_duplicate_pause_has_no_new_intent() {
    let peer=peer();let mut j=running();assert!(j.prepare(&peer,4).unwrap());
    let command=j.pending.clone().unwrap();let (mut s,id,ms)=c_status(2);
    s.request=command.request;assert_eq!(j.observe(&s,id,ms).unwrap(),Observation::Confirmed);
    assert!(!j.prepare(&peer,4).unwrap());assert!(j.pending.is_none());
    j.confirmed.as_mut().unwrap().sequence=u32::MAX-1;
    assert!(j.prepare(&peer,5).is_err());assert!(j.pending.is_none());
    assert!(j.prepare(&peer,2).unwrap());assert_eq!(j.pending.as_ref().unwrap().sequence,u32::MAX);
    j.matches(&peer,HOST,DEVICE).unwrap();
}

fn original_row(j:&Journal)->crate::companion_v1::CompanionV1HostSession {
    use crate::companion_v1::*;
    let snapshot=fixture_snapshot();
    let request=CompanionV1ControlRequest{action:CompanionV1ControlAction::MeetingStart,
        ble_name:None,session_id:Some(HOST.into()),prompt_id:None,title:Some("保留原会议标题".into()),
        transcript_text:None,meeting_mode:Some("offlineStore".into()),audio_path:None,
        audio_bytes:Some(0),device_id:Some(DEVICE.into()),duration_ms:Some(0)};
    let mut row=create_host_session(&snapshot,&request,"");row.source="boardDevice".into();
    row.started_at=None;row.stopped_at=None;row.audio_path=None;row.chunks.clear();
    j.checkpoint_row(&mut row).unwrap();row
}

#[test]
fn bound_pending_pause_survives_index_restart_and_confirmation_stays_in_original_row() {
    let root=Temp::new();let path=root.0.join("sessions.json");let mut j=running();
    let row=original_row(&j);super::super::session_store::save(&path,&[row]).unwrap();
    j.prepare(&peer(),4).unwrap();let pending=j.pending.clone().unwrap();
    let mut store=Store::open(&path,HOST).unwrap();store.commit_bound(j.clone()).unwrap();drop(store);
    let loaded=super::super::persistence::load_sessions_from(&path).unwrap();
    assert_eq!(loaded.len(),1);assert_eq!(loaded[0].id,HOST);
    assert_eq!(loaded[0].status,"recording");assert!(loaded[0].recorder_control_uncertain);
    assert_eq!(loaded[0].recorder_control.as_ref().unwrap().pending.as_ref(),Some(&pending));
    assert!(loaded[0].stopped_at.is_none());assert!(!loaded[0].audio_stored);
    let (mut s,id,ms)=c_status(2);s.request=pending.request;
    assert_eq!(j.observe(&s,id,ms).unwrap(),Observation::Confirmed);
    let mut store=Store::open(&path,HOST).unwrap();store.commit_bound(j.clone()).unwrap();
    let raw=super::super::session_store::load(&path).bytes.unwrap();
    let loaded:Vec<crate::companion_v1::CompanionV1HostSession>=serde_json::from_slice(&raw).unwrap();
    assert_eq!(loaded[0].title,"保留原会议标题");assert_eq!(loaded[0].recorder_control,Some(j));
    assert!(!loaded[0].recorder_control_uncertain);assert_eq!(loaded[0].status,"recording");
    assert!(loaded[0].stopped_at.is_none());assert_eq!(loaded[0].duration_ms,u64::from(ms));
}

#[test]
fn missing_or_different_library_owner_blocks_bound_commit_without_losing_pending_intent() {
    let root=Temp::new();let path=root.0.join("sessions.json");let mut j=running();j.prepare(&peer(),4).unwrap();
    let mut store=Store::open(&path,HOST).unwrap();assert!(store.commit_bound(j.clone()).is_err());
    assert_eq!(store.journal,Some(j.clone()));
    let mut row=original_row(&running());row.source_device_id=Some("C8:92:FF:DD:3B:CB".into());
    super::super::session_store::save(&path,&[row]).unwrap();
    assert!(store.commit_bound(j.clone()).is_err());assert_eq!(store.journal,Some(j));
    let rows=super::super::persistence::load_sessions_from(&path).unwrap();
    assert_eq!(rows[0].source_device_id.as_deref(),Some("C8:92:FF:DD:3B:CB"));
}

#[test]
fn exact_local_seal_resolves_pending_control_without_fabricating_stop_or_starting_again() {
    let mut j=running();j.prepare(&peer(),4).unwrap();
    let (mut sealed,id,ms)=c_status(0);sealed.state=2;
    assert_eq!(j.observe(&sealed,id,ms).unwrap(),Observation::Confirmed);
    let c=j.confirmed.as_ref().unwrap();assert_eq!(c.command,1);assert_eq!(c.sequence,0);
    assert_eq!(c.state,2);assert!(c.finished_locally);assert!(j.pending.is_none());
    j.matches(&peer(),HOST,DEVICE).unwrap();assert!(!j.prepare(&peer(),2).unwrap());
    assert!(j.prepare(&peer(),1).is_err());assert!(j.prepare(&peer(),5).is_err());
    let mut wrong=sealed;wrong.key.as_mut().unwrap().session_id+=1;
    let before=j.clone();assert!(j.observe(&wrong,id,ms).is_err());assert_eq!(j,before);
}

#[test]
fn natural_end_recovery_keeps_unknown_stop_time_and_preserves_real_stop_observation() {
    let mut j=running();let mut row=original_row(&j);let actual_start=row.started_at.clone();
    let (mut sealed,id,_)=c_status(0);sealed.state=2;
    assert_eq!(j.observe(&sealed,id,350000).unwrap(),Observation::Confirmed);
    j.checkpoint_row(&mut row).unwrap();
    assert_eq!(row.status,"captured");assert_eq!(row.started_at,actual_start);
    assert!(row.stopped_at.is_none());assert_eq!(row.duration_ms,350000);
    assert!(row.recorder_control.as_ref().unwrap().confirmed.as_ref().unwrap().finished_locally);
    row.stopped_at=Some("actual-previous-stop-observation".into());
    j.checkpoint_row(&mut row).unwrap();
    assert_eq!(row.stopped_at.as_deref(),Some("actual-previous-stop-observation"));
    let mut explicit=running();let mut owned=original_row(&explicit);
    explicit.prepare(&peer(),2).unwrap();let command=explicit.pending.as_ref().unwrap().clone();
    sealed.command=2;sealed.request=command.request;sealed.sequence=command.sequence;
    assert_eq!(explicit.observe(&sealed,id,350000).unwrap(),Observation::Confirmed);
    explicit.checkpoint_row(&mut owned).unwrap();
    assert!(owned.stopped_at.is_some());assert!(!explicit.confirmed.as_ref().unwrap().finished_locally);
}

#[test]
fn actual_fw402_start_stopping_waits_for_exact_local_end_without_replacement_start() {
    let (mut status,anchor,_)=c_status(0);
    let mut journal=Journal::start(&peer(),HOST,DEVICE,status.request,1830).unwrap();
    status.state=6;
    let before=journal.clone();
    assert_eq!(journal.observe(&status,anchor,0).unwrap(),Observation::Accepted);
    assert_eq!(journal,before); // no live recording or fabricated STOP ACK
    for which in 0..4 {
        let mut rejected=status.clone();
        let observed_anchor=match which {0=>{rejected.last_error=1;anchor},
            1=>{rejected.timeline=false;anchor},2=>{rejected.device_uid[0]^=1;anchor},_=>0};
        assert!(journal.observe(&rejected,observed_anchor,0).is_err());
        assert_eq!(journal,before);
    }
    status.state=2;
    assert_eq!(journal.observe(&status,anchor,0).unwrap(),Observation::Confirmed);
    assert!(journal.pending.is_none());
    let ended=journal.confirmed.as_ref().unwrap();
    assert_eq!((ended.command,ended.sequence,ended.state,ended.duration_ms),(1,0,2,0));
    assert!(ended.finished_locally);
    assert!(journal.prepare(&peer(),1).is_err());
}

fn ended_journal()->Journal {
    let mut j=running();let (mut s,id,ms)=c_status(0);s.state=2;
    assert_eq!(j.observe(&s,id,ms).unwrap(),Observation::Confirmed);j
}
fn privacy_request(action:&str)->crate::companion_v1::CompanionV1ControlRequest {
    serde_json::from_value(serde_json::json!({"action":action,"sessionId":HOST})).unwrap()
}
#[test]
fn completed_control_privacy_retires_only_original_and_keeps_lock_until_index_checkpoint() {
    let root=Temp::new();let path=root.0.join("sessions.json");let j=ended_journal();
    let row=original_row(&j);let mut snapshot=crate::companion_v1::fixture_snapshot();
    snapshot.host.sessions=vec![row.clone()];snapshot.host.selected_session_id=Some(HOST.into());
    super::super::session_store::save(&path,&[row]).unwrap();
    let mut store=Store::open(&path,HOST).unwrap();store.commit(j.clone()).unwrap();let original=store.path.clone();drop(store);
    let mut other=j.clone();other.host_session="other-completed".into();
    let mut store=Store::open(&path,&other.host_session).unwrap();store.commit(other.clone()).unwrap();let retained=store.path.clone();drop(store);
    assert!(prepare_privacy_retirement(&snapshot,&privacy_request("privacyEraseAudio"),&path).unwrap().is_none());
    let mut guard=prepare_privacy_retirement(&snapshot,&privacy_request("privacyDeleteSession"),&path).unwrap().unwrap();
    assert!(Store::open(&path,HOST).is_err());assert!(original.exists());
    assert_eq!(guard.erase().unwrap(),1);assert!(!original.exists());assert!(retained.exists());
    assert!(Store::open(&path,HOST).is_err(),"lock still guards erased sidecar until sanitized index checkpoint");
    super::super::session_store::save(&path,&[]).unwrap();drop(guard);
    assert!(Store::open(&path,HOST).unwrap().journal.is_none());
    let mut all=prepare_privacy_retirement(&snapshot,&privacy_request("privacyEraseAll"),&path).unwrap().unwrap();
    assert_eq!(all.erase().unwrap(),1);assert!(!retained.exists(),"explicit all clears proven ended orphan too");
}

#[test]
fn control_privacy_pending_corrupt_or_mismatched_identity_preflight_preserves_every_file() {
    let root=Temp::new();let path=root.0.join("sessions.json");let j=ended_journal();
    let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.host.sessions=vec![original_row(&j)];
    for which in 0..4 {
        let mut store=Store::open(&path,HOST).unwrap();
        let mut current=j.clone();
        match which {
            0=>{current=running();current.prepare(&peer(),4).unwrap();},
            1=>current.start_request+=1,
            2=>{},
            _=>current.confirmed.as_mut().unwrap().state=3,
        }
        store.commit(current).unwrap();let file=store.path.clone();drop(store);
        if which==2 {fs::write(&file,b"broken privacy record").unwrap();}
        let bytes=fs::read(&file).unwrap();
        assert!(prepare_privacy_retirement(&snapshot,&privacy_request("privacyDeleteSession"),&path).is_err(),"{which}");
        assert_eq!(fs::read(&file).unwrap(),bytes,"failed preflight never deletes original control");
        fs::remove_file(file).unwrap(); // each injected failure has its own original fixture
    }
}

fn recovered_closed_original(root:&Path,j:&Journal)->crate::companion_v1::CompanionV1HostSession {
    use crate::backend::recording_wire::{Descriptor,SessionKey,receiver::Receiver};
    // Software libopus silence only. This models a sealed, interrupted original
    // whose durable START remains genuine; it is not a new board recording.
    let mut raw=b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();
    for _ in 0..3 {raw.extend_from_slice(&[3,0,0xf8,0xff,0xfe]);}
    let d=Descriptor {key:SessionKey::from_public(j.key.as_ref().unwrap()).unwrap(),
        recording_id:j.anchor.unwrap(),segment_index:0,sample_offset:0,sample_count:960,
        encoded_length:raw.len() as u32,content_crc32:crc32fast::hash(&raw),
        sha256:Sha256::digest(&raw).into(),total_segments:1,flags:7,
        codec:3,source_mode:1,sync_state:0};
    let index=root.join("sessions.json");
    super::super::session_store::save(&index,&[original_row(j)]).unwrap();
    let wire=d.encode().unwrap();let mut receiver=Receiver::open(root,&wire).unwrap();
    receiver.accept_segment(&wire,&raw).unwrap();receiver.assemble().unwrap();
    assert_eq!(receiver.publish(&index,DEVICE).unwrap(),HOST);drop(receiver);
    let row=super::super::persistence::load_sessions_from(&index).unwrap().remove(0);
    assert_eq!(row.status,"captured");assert!(row.audio_stored&&row.capture_incomplete);
    assert_eq!(row.recorder_control.as_ref().unwrap().confirmed.as_ref().unwrap().state,1);
    row
}

#[test]
fn control_privacy_recovered_closed_original_retires_without_inventing_stop() {
    let root=Temp::new();let path=root.0.join("sessions.json");let j=running();
    let row=recovered_closed_original(&root.0,&j);
    let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.host.sessions=vec![row.clone()];
    let mut store=Store::open(&path,HOST).unwrap();store.commit(j.clone()).unwrap();
    let file=store.path.clone();drop(store);let original=fs::read(&file).unwrap();
    let mut guard=prepare_privacy_retirement(&snapshot,&privacy_request("privacyDeleteSession"),&path)
        .expect("an exact LAST original and verified WAV can retire local recovery even without a fabricated STOP")
        .unwrap();
    assert_eq!(fs::read(&file).unwrap(),original,"preflight must not rewrite START as STOP");
    assert!(Store::open(&path,HOST).is_err());assert_eq!(guard.erase().unwrap(),1);
    assert!(!file.exists());assert!(Store::open(&path,HOST).is_err());
    super::super::session_store::save(&path,&[]).unwrap();drop(guard);
    assert!(Store::open(&path,HOST).unwrap().journal.is_none());
}

#[test]
fn control_privacy_closed_receipt_never_retires_pending_foreign_or_unverified_original() {
    let root=Temp::new();let path=root.0.join("sessions.json");let j=running();
    let row=recovered_closed_original(&root.0,&j);let raw=PathBuf::from(row.chunks[0].path.as_ref().unwrap());
    let original_raw=fs::read(&raw).unwrap();
    for which in 0..8 {
        let mut current=j.clone();let mut changed=row.clone();
        match which {
            0=>{current.prepare(&peer(),4).unwrap();},
            1=>current.start_request+=1,
            2=>changed.device_recording_id=Some(j.anchor.unwrap()+1),
            3=>changed.status="recording".into(),
            4=>changed.source_device_id=Some("A1:B2:C3:D4:E5:F6".into()),
            5=>{fs::write(&raw,b"not the sealed original").unwrap();},
            6=>changed.device_recording_key.as_mut().unwrap().session_id="0000000000000000".into(),
            _=>{
                // Even mutually matching row/journal fields cannot substitute
                // another physical anchor for the first immutable descriptor.
                current.anchor=Some(j.anchor.unwrap()+1);changed.device_recording_id=current.anchor;
                changed.recorder_control=Some(current.clone());
            },
        }
        let mut store=Store::open(&path,HOST).unwrap();store.commit(current).unwrap();
        let file=store.path.clone();drop(store);let before=fs::read(&file).unwrap();
        let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.host.sessions=vec![changed];
        assert!(prepare_privacy_retirement(&snapshot,&privacy_request("privacyDeleteSession"),&path).is_err(),"{which}");
        assert_eq!(fs::read(&file).unwrap(),before,"failed preflight keeps genuine command");
        fs::remove_file(file).unwrap();fs::write(&raw,&original_raw).unwrap();
    }
    let mut store=Store::open(&path,HOST).unwrap();store.commit(j).unwrap();let file=store.path.clone();drop(store);
    let mut snapshot=crate::companion_v1::fixture_snapshot();snapshot.host.sessions.clear();
    assert!(prepare_privacy_retirement(&snapshot,&privacy_request("privacyEraseAll"),&path).is_err(),
        "a non-ended orphan has no row/closed-original proof");assert!(file.exists());
}
