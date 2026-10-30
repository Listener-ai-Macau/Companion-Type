use super::{recorder_control::{Journal,Observation,SettlementAction,settlement_action},recording_wire::control::{PausePeer,PauseStatus}};

fn capability()->Vec<u8> {
    let mut s=vec![0;116];s[0]=1;s[12..16].copy_from_slice(&0x5742_4155u32.to_le_bytes());
    for(i,b)in s[20..32].iter_mut().enumerate(){*b=(i+1) as u8;}
    let p=&mut s[84..];p[..4].copy_from_slice(b"CRV2");p[4..6].copy_from_slice(&2u16.to_le_bytes());
    p[6..8].copy_from_slice(&32u16.to_le_bytes());p[8..12].copy_from_slice(&127u32.to_le_bytes());
    p[12..20].copy_from_slice(&7u64.to_le_bytes());p[20..22].copy_from_slice(&64u16.to_le_bytes());
    p[22..24].copy_from_slice(&1024u16.to_le_bytes());p[24..26].copy_from_slice(&248u16.to_le_bytes());
    let crc=crc32fast::hash(&p[..28]);p[28..32].copy_from_slice(&crc.to_le_bytes());s
}
fn vector(index:usize)->&'static [u8] {
    let golden=include_bytes!("../../../../windows/src-tauri/src/backend/cop1/tests/engine-pause-control.cpc3");
    &golden[8+index*137..8+(index+1)*137]
}
fn reply(index:usize,request:u32,sequence:u32)->(PauseStatus,u32,u32) {
    let mut raw=vector(index)[56..136].to_vec();raw[8..12].copy_from_slice(&request.to_le_bytes());
    raw[60..64].copy_from_slice(&sequence.to_le_bytes());let crc=crc32fast::hash(&raw[..76]);raw[76..80].copy_from_slice(&crc.to_le_bytes());
    let anchor=u32::from_le_bytes(raw[12..16].try_into().unwrap());let duration=u32::from_le_bytes(raw[20..24].try_into().unwrap());
    (PauseStatus::decode(&raw).unwrap(),anchor,duration)
}

#[test]
fn real_desktop_journal_keeps_start_pause_resume_and_stop_identity() {
    let peer=PausePeer::from_status(&capability()).unwrap().unwrap();let start=&vector(0)[..56];
    let request=u32::from_le_bytes(start[36..40].try_into().unwrap());let max=u16::from_le_bytes(start[44..46].try_into().unwrap());
    let mut journal=Journal::start(&peer,"synthetic-session","C8:92:FF:DD:3B:CA",request,max).unwrap();
    assert_eq!(journal.pending.as_ref().unwrap().wire,start);
    let(s,a,d)=reply(0,request,0);assert_eq!(journal.observe_with_peer(&peer,&s,a,d).unwrap(),Observation::Confirmed);
    for (command,transitional,stable) in [(4,1,2),(5,4,5),(2,7,8)] {
        assert!(journal.prepare(&peer,command).unwrap());let intent=journal.pending.as_ref().unwrap().clone();
        let saved=serde_json::to_vec(&journal).unwrap();let mut journal2:Journal=serde_json::from_slice(&saved).unwrap();
        journal2.matches(&peer,"synthetic-session","C8:92:FF:DD:3B:CA").unwrap();
        assert_eq!(journal2.pending.as_ref().unwrap().wire,intent.wire);
        assert!(journal2.prepare(&peer,if command==4{5}else{4}).is_err());
        let(s,a,d)=reply(transitional,intent.request,intent.sequence);
        assert_eq!(journal2.observe_with_peer(&peer,&s,a,d).unwrap(),Observation::Accepted);
        assert!(journal2.pending.is_some());
        let(s,a,d)=reply(stable,intent.request,intent.sequence);
        assert_eq!(journal2.observe_with_peer(&peer,&s,a,d).unwrap(),Observation::Confirmed);
        assert!(journal2.pending.is_none());journal=journal2;
    }
    assert!(journal.ended());assert!(journal.prepare(&peer,1).is_err());
}

#[test]
fn same_intent_survives_lost_confirmation_and_foreign_or_corrupt_reply_is_rejected() {
    let peer=PausePeer::from_status(&capability()).unwrap().unwrap();let start=&vector(0)[..56];
    let request=u32::from_le_bytes(start[36..40].try_into().unwrap());let max=u16::from_le_bytes(start[44..46].try_into().unwrap());
    let mut journal=Journal::start(&peer,"synthetic-session","C8:92:FF:DD:3B:CA",request,max).unwrap();
    let before=journal.pending.as_ref().unwrap().wire.clone();let saved=serde_json::to_vec(&journal).unwrap();
    journal=serde_json::from_slice(&saved).unwrap();assert!(journal.prepare(&peer,1).unwrap());
    assert_eq!(journal.pending.as_ref().unwrap().wire,before);
    let(s,a,d)=reply(0,request+1,0);assert!(journal.observe_with_peer(&peer,&s,a,d).is_err());
    let mut corrupted=vector(0)[56..136].to_vec();corrupted[40]^=1;assert!(PauseStatus::decode(&corrupted).is_err());
    assert_eq!(journal.pending.as_ref().unwrap().wire,before);
    assert!(journal.matches(&peer,"other-session","C8:92:FF:DD:3B:CA").is_err());
}

#[test]
fn lost_start_is_not_silently_resent_and_other_pending_commands_keep_bytes() {
    let peer=PausePeer::from_status(&capability()).unwrap().unwrap();let start=&vector(0)[..56];
    let request=u32::from_le_bytes(start[36..40].try_into().unwrap());let max=u16::from_le_bytes(start[44..46].try_into().unwrap());
    let mut journal=Journal::start(&peer,"synthetic-session","C8:92:FF:DD:3B:CA",request,max).unwrap();
    let mut floor=None;
    assert!(settlement_action(&journal,Observation::Previous,true,false,&mut floor).is_err());
    let action=settlement_action(&journal,Observation::Previous,true,true,&mut floor).unwrap();
    assert!(matches!(action,SettlementAction::Write(ref cmd) if cmd.wire==start));
    assert_eq!(settlement_action(&journal,Observation::Accepted,false,false,&mut floor).unwrap(),SettlementAction::Wait);
    let(s,a,d)=reply(0,request,0);journal.observe_with_peer(&peer,&s,a,d).unwrap();journal.prepare(&peer,4).unwrap();
    let pending=journal.pending.as_ref().unwrap().wire.clone();let mut floor=None;
    let action=settlement_action(&journal,Observation::Previous,true,false,&mut floor).unwrap();
    assert!(matches!(action,SettlementAction::Write(ref cmd) if cmd.wire==pending));
    assert_eq!(settlement_action(&journal,Observation::Previous,false,false,&mut floor).unwrap(),SettlementAction::Wait);
}
