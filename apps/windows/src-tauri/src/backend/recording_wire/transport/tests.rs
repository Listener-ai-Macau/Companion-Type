use super::*;
use super::super::{receiver::Receiver, SessionKey, SEALED, LAST};
use sha2::{Digest, Sha256};
use std::path::Path;

fn fixture() -> (Peer, Vec<Descriptor>, Vec<u8>) {
    // Actual libopus-compatible silence packets, SOFTWARE ONLY; no microphone,
    // board, BLE timing or cloud evidence is claimed by these tests.
    let mut raw = b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();
    for _ in 0..3 { raw.extend_from_slice(&[3, 0, 0xf8, 0xff, 0xfe]); }
    let peer = Peer { uid: [0x35; 12], epoch: 0xc055_aa07_1012_3456, capacity: 64, max_value_bytes: 248, logical_control: false, growing_tail: false, pause_control: false, batch_interval: false };
    let key = SessionKey { device_uid: peer.uid, format_epoch: peer.epoch, session_id: 23 };
    let ds = (0..3).map(|n| Descriptor { key: key.clone(), recording_id: n + 91,
        segment_index: n, sample_offset: u64::from(n) * 960, sample_count: 960,
        encoded_length: raw.len() as u32, content_crc32: crc32fast::hash(&raw),
        sha256: Sha256::digest(&raw).into(), total_segments: if n == 2 { 3 } else { 0 },
        flags: if n == 2 { SEALED | LAST } else { SEALED }, codec: 3, source_mode: 1, sync_state: 0,
    }).collect();
    (peer, ds, raw)
}
fn status(peer: &Peer) -> Vec<u8> {
    let mut s = vec![0; 116]; s[0] = 1;
    s[12..16].copy_from_slice(&0x5742_4155u32.to_le_bytes());
    s[20..32].copy_from_slice(&peer.uid);
    let p = &mut s[84..]; p[..4].copy_from_slice(b"CRV2");
    p[4..6].copy_from_slice(&2u16.to_le_bytes()); p[6..8].copy_from_slice(&32u16.to_le_bytes());
    p[8..12].copy_from_slice(&7u32.to_le_bytes()); p[12..20].copy_from_slice(&peer.epoch.to_le_bytes());
    p[20..22].copy_from_slice(&peer.capacity.to_le_bytes()); p[22..24].copy_from_slice(&1024u16.to_le_bytes());
    p[24..26].copy_from_slice(&248u16.to_le_bytes());
    let crc = crc32fast::hash(&p[..28]); p[28..].copy_from_slice(&crc.to_le_bytes()); s
}

#[test]
fn product_transcription_paths_use_verified_v2_wav_and_refuse_bad_raw_original() {
    let (_, ds, raw) = fixture();
    let root = std::env::temp_dir().join(format!("companion-v2-asr-input-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap(); let index=root.join("sessions.json");
    let mut receiver=Receiver::open(&root,&ds[0].encode().unwrap()).unwrap();
    for d in &ds {receiver.accept_segment(&d.encode().unwrap(),&raw).unwrap();}
    receiver.assemble().unwrap();receiver.publish(&index,"A1:B2:C3:D4:E5:F6").unwrap();drop(receiver);
    let rows:Vec<crate::companion_v1::CompanionV1HostSession>=serde_json::from_slice(&std::fs::read(&index).unwrap()).unwrap();
    let row=&rows[0];let before=serde_json::to_value(row).unwrap();
    assert_eq!(crate::backend::transcription_chunk_paths(row).unwrap(),vec![row.audio_path.clone().unwrap()]);
    assert_eq!(serde_json::to_value(row).unwrap(),before,"do not rewrite raw provenance as WAV chunks");
    assert!(!row.device_reclaimed,"ASR can use verified audio before consume");
    let path=Path::new(row.chunks[1].path.as_deref().unwrap());
    std::fs::write(path,b"corrupt encoded original").unwrap();
    assert!(crate::backend::transcription_chunk_paths(row).is_err(),"do not hide missing/corrupt original behind a WAV or provider cache");
    assert_eq!(serde_json::to_value(row).unwrap(),before);
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn sealed_batch_reclaim_keeps_open_missing_and_background_segments_immediate() {
    let (_, ds, _) = fixture();
    let empty=std::collections::BTreeSet::new();
    let plan=super::super::plan_group(&ds,&empty).unwrap();
    assert!(plan.may_batch_reclaim(None), "complete closed metadata may retain data stream until exact ACK phase");
    assert!(!plan.payloads_complete, "batch policy does not invent received audio or authorize ACK");
    assert!(!plan.may_batch_reclaim(Some(1)), "recording follow slices consume their saved segment promptly");
    assert!(!super::super::plan_group(&ds[..2],&empty).unwrap().may_batch_reclaim(None), "no terminal descriptor means growing recording");
    assert!(!super::super::plan_group(&ds[1..],&empty).unwrap().may_batch_reclaim(None), "missing original segment cannot qualify closed batch");
}

#[test]
fn batch_interval_is_optional_and_bound_to_nonce_uid_epoch_and_crc() {
    let (mut peer,_,_)=fixture();
    assert!(peer.interval_request(41,true).is_err());
    let mut s=status(&peer);
    s[92..96].copy_from_slice(&39u32.to_le_bytes());
    let crc=crc32fast::hash(&s[84..112]);s[112..116].copy_from_slice(&crc.to_le_bytes());
    peer.batch_interval=true;
    assert_eq!(Peer::from_status(&s).unwrap(),Some(peer.clone()));
    assert!(peer.interval_request(0,true).is_err());
    for begin in [true,false] {
        let p=peer.interval_request(41,begin).unwrap();
        assert_eq!(&p[..4],&[2,0x25,u8::from(begin),0]);
        assert_eq!(u32le(&p,4),41);assert_eq!(&p[8..20],&peer.uid);
        assert_eq!(u64le(&p,20),peer.epoch);
        assert_eq!(u32le(&p,28),crc32fast::hash(&p[..28]));
    }
}

#[test]
fn capability_identity_and_pull_are_bound_to_real_epoch() {
    let (peer, ds, _) = fixture();
    assert_eq!(Peer::from_status(&status(&peer)).unwrap(), Some(peer.clone()));
    assert!(Peer::from_status(&status(&peer)[..84]).unwrap().is_none());
    let mut s = status(&peer); s[96] ^= 1;
    assert!(Peer::from_status(&s).is_err(), "corrupt capability must not fall back to V1");
    let n = peer.negotiate(9).unwrap();
    assert_eq!(&n[..8], &[2, 0x22, 0, 0, 9, 0, 0, 0]);
    assert_eq!(&n[8..20], &peer.uid); assert_eq!(u64le(&n, 20), peer.epoch);
    assert_eq!(crc32fast::hash(&n[..28]), u32le(&n, 28));
    let p = peer.pull(&ds[1], 17, 4).unwrap();
    assert_eq!(&p[..4], &[2, 0x21, 4, 0]);
    assert_eq!(u32le(&p, 4), 92); assert_eq!(u64le(&p, 8), peer.epoch);
    assert_eq!(u64le(&p, 16), 23); assert_eq!(u32le(&p, 24), 1); assert_eq!(u32le(&p, 28), 17);
    assert!(peer.pull(&ds[1], ds[1].encoded_length, 4).is_err());
    let mut foreign = ds[1].clone(); foreign.key.format_epoch += 1;
    assert!(peer.pull(&foreign, 0, 4).is_err());
}

#[test]
fn paged_directory_rejects_mixed_snapshots_and_ignores_old_callbacks() {
    let (peer, ds, _) = fixture();
    let mut d = Directory::new(&peer, 91).unwrap();
    let first = Page { snapshot: 7, nonce: 91, start: 0, total: 3, entries: ds[..2].to_vec() };
    let mut old = first.clone(); old.nonce = 90;
    assert!(!d.accept(&old.encode().unwrap()).unwrap());
    assert_eq!(u32le(&d.request(), 12), 0);
    assert!(d.accept(&first.encode().unwrap()).unwrap());
    assert!(!d.accept(&first.encode().unwrap()).unwrap(), "replay must not advance cursor");
    assert_eq!(u32le(&d.request(), 4), 7); assert_eq!(u32le(&d.request(), 12), 2);
    let mut next = Page { snapshot: 8, nonce: 91, start: 2, total: 3, entries: vec![ds[2].clone()] };
    assert!(d.accept(&next.encode().unwrap()).is_err());
    next.snapshot = 7; assert!(d.accept(&next.encode().unwrap()).unwrap());
    assert!(d.finished()); assert_eq!(d.entries(), ds);
    let mut empty = Directory::new(&peer, 92).unwrap();
    assert!(empty.accept(&Page { snapshot: 9, nonce: 92, start: 0, total: 0,
        entries: vec![] }.encode().unwrap()).unwrap()); assert!(empty.finished());
}

#[test]
fn exact_receipt_and_pending_host_recovery_survive_empty_device_directory() {
    let (peer, ds, raw) = fixture();
    let root = std::env::temp_dir().join(format!("companion-v2-native-receiver-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    let index = root.join("sessions.json");
    let device = "A1:B2:C3:D4:E5:F6";
    // Simulate local raw+index commit, then device removal with a lost reply.
    // No hardware deletion occurs here. Reopen must retry exact durable ACKs.
    let mut r = Receiver::open(&root, &ds[0].encode().unwrap()).unwrap();
    r.accept_segment(&ds[0].encode().unwrap(), &raw).unwrap();
    r.publish(&index, device).unwrap();
    let mut snapshot = crate::companion_v1::fixture_snapshot();
    snapshot.meeting.active = true;
    snapshot.host.active_session_id = Some("user-active-capture".into());
    let operation = crate::backend::ble_bridge::CompanionBleOperation {
        provider_id: "companion-type-windows-ble".into(), mode: "windows-native-segmented-recording-pull".into(),
        ready: true, sync_paused: false, device_id: Some(device.into()), recording_path: None,
        recordings: vec![], device_identity: None, message: "sealed raw and library durable".into(),
    };
    crate::backend::observe_segmented_library(&mut snapshot, &operation, &index,
        crate::companion_v1::CompanionV1ControlAction::DeviceSyncRecordings).unwrap();
    assert!(snapshot.meeting.active, "syncing a sealed segment must not present a STOP");
    assert_eq!(snapshot.host.active_session_id.as_deref(), Some("user-active-capture"));
    assert_eq!(snapshot.host.sessions.len(), 1);
    assert!(snapshot.host.sessions[0].device_recording_id.is_none());
    assert!(!snapshot.host.sessions[0].audio_stored, "open tail is not a playable completed meeting");
    let ack = r.ack_candidates(&index).unwrap().remove(0);
    assert!(receipt_matches(&ack, &ack, &peer).unwrap());
    let mut wrong = ack.clone(); wrong[48] ^= 1;
    let crc = crc32fast::hash(&wrong[..80]); wrong[80..].copy_from_slice(&crc.to_le_bytes());
    assert!(!receipt_matches(&ack, &wrong, &peer).unwrap());
    drop(r);
    let pending = Receiver::pending_initials(&root, &peer, device).unwrap();
    assert_eq!(pending.len(), 1);
    let mut r = Receiver::open(&root, &pending[0]).unwrap();
    assert!(r.has_segment(&ds[0].encode().unwrap()).unwrap(), "durable raw must avoid a second radio pull");
    r.publish(&index, device).unwrap();
    assert_eq!(r.ack_candidates(&index).unwrap(), vec![ack.clone()]);
    r.confirm_acked(&ack).unwrap();
    for d in &ds[1..] { r.accept_segment(&d.encode().unwrap(), &raw).unwrap(); }
    r.publish(&index, device).unwrap();
    for ack in r.ack_candidates(&index).unwrap() { r.confirm_acked(&ack).unwrap(); }
    r.assemble().unwrap(); r.publish(&index, device).unwrap(); drop(r);
    assert!(Receiver::pending_initials(&root, &peer, device).unwrap().is_empty());
    assert!(Receiver::pending_initials(&root, &peer, "11:22:33:44:55:66").unwrap().is_empty());
    // Leave the isolated artifacts available on failure. Delete only this
    // exact, newly created test directory after all affected paths passed.
    assert!(root.parent() == Some(Path::new(&std::env::temp_dir())));
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn interrupted_capture_review_verifies_original_and_survives_republish() {
    let (_, mut ds, raw) = fixture();
    ds.last_mut().unwrap().flags |= super::super::RECOVERED;
    let root = std::env::temp_dir().join(format!("companion-interrupted-receipt-{}", uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();
    let index = root.join("sessions.json");
    let device = "A1:B2:C3:D4:E5:F6";
    let load = || {
        let saved = crate::backend::session_store::load(&index);
        serde_json::from_slice::<Vec<crate::companion_v1::CompanionV1HostSession>>(&saved.bytes.unwrap()).unwrap()
    };
    let mut r = Receiver::open(&root, &ds[0].encode().unwrap()).unwrap();
    for d in &ds { r.accept_segment(&d.encode().unwrap(), &raw).unwrap(); }
    r.assemble().unwrap(); r.publish(&index, device).unwrap(); drop(r);
    let mut original = load().remove(0);
    assert!(original.capture_incomplete && original.audio_stored && !original.device_reclaimed);
    assert_eq!(original.pending_reason.as_deref(), Some("capture_interrupted"));
    assert_eq!(original.recovery.stage, "paused");
    let mut corrupt = original.clone(); corrupt.chunks[0].bytes += 1;
    assert!(crate::backend::interrupted_capture::confirm(&mut corrupt).is_err());
    assert!(!corrupt.recovery.capture_review_confirmed);
    crate::backend::interrupted_capture::confirm(&mut original).unwrap();
    assert!(original.recovery.capture_review_confirmed && original.capture_incomplete);
    assert!(!original.device_reclaimed, "reviewing fragments must not claim physical consumption");
    crate::backend::session_store::update_checked(&index, |rows| { *rows = vec![original.clone()]; Ok(()) }).unwrap();
    let mut r = Receiver::open(&root, &ds[0].encode().unwrap()).unwrap();
    r.publish(&index, device).unwrap(); drop(r);
    let reopened = load().remove(0);
    assert!(reopened.recovery.capture_review_confirmed && reopened.capture_incomplete);
    Receiver::verify_saved_row(&reopened).unwrap();
    assert!(!reopened.device_reclaimed);
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn wba_logical_recording_keeps_owned_row_through_partial_receive_stop_and_reclaim() {
    let (_peer,ds,raw)=fixture();let device="A1:B2:C3:D4:E5:F6";
    let root=std::env::temp_dir().join(format!("companion-logical-owned-{}",uuid::Uuid::new_v4()));
    std::fs::create_dir(&root).unwrap();let index=root.join("sessions.json");
    let mut request=crate::control_request(crate::companion_v1::CompanionV1ControlAction::MeetingStart,Some("owned-user-meeting".into()));
    request.meeting_mode=Some("offlineStore".into());
    let mut snapshot=crate::companion_v1::apply_fixture_control(crate::companion_v1::fixture_snapshot(),request).unwrap();
    let mut row=snapshot.host.sessions[0].clone();row.id="owned-user-meeting".into();row.source="boardDevice".into();
    row.status="recording".into();row.title="保留用户标题与备注".into();row.chunks.clear();row.audio_path=None;
    row.audio_stored=false;row.source_device_id=Some(device.into());row.device_recording_id=Some(91);
    row.device_recording_key=Some(ds[0].key.public_key());
    crate::backend::session_store::update_checked(&index,|rows|{*rows=vec![row.clone()];Ok(())}).unwrap();
    let load=|| {let saved=crate::backend::session_store::load(&index);
        serde_json::from_slice::<Vec<crate::companion_v1::CompanionV1HostSession>>(&saved.bytes.unwrap()).unwrap()};
    let mut r=Receiver::open(&root,&ds[0].encode().unwrap()).unwrap();
    r.accept_segment(&ds[0].encode().unwrap(),&raw).unwrap();
    assert_eq!(r.publish(&index,device).unwrap(),"owned-user-meeting");
    let rows=load();assert_eq!(rows.len(),1);assert_eq!(rows[0].status,"recording");
    assert_eq!(rows[0].title,row.title);assert_eq!(rows[0].device_recording_id,Some(91));
    assert_eq!(r.ack_candidates(&index).unwrap().len(),1);
    snapshot.host.sessions=rows.clone();snapshot.host.active_session_id=Some(row.id.clone());
    snapshot.device.device_id=Some(device.into());snapshot.device.recording=true;snapshot.meeting.active=true;
    let report=crate::backend::ble_bridge::CompanionMeetingControlReport {device_id:device.into(),
        request_id:202,state:2,last_error:0,meeting_id:91,duration_ms:180,sync_state:0,logical_key:Some(ds[0].key.clone())};
    crate::backend::board_stop::observe(&mut snapshot,&row.id,&report,"2026-10-11T10:00:00Z").unwrap();
    assert!(!snapshot.meeting.active);assert_eq!(snapshot.host.sessions[0].chunks.len(),1);
    assert_eq!(snapshot.host.sessions[0].title,row.title);
    crate::backend::session_store::update_checked(&index,|rows|{*rows=snapshot.host.sessions.clone();Ok(())}).unwrap();
    // A copied logical identity is ambiguous; neither publish nor physical ACK may choose one arbitrarily.
    crate::backend::session_store::update_checked(&index,|rows| {let mut duplicate=rows[0].clone();
        duplicate.id="different-host-row".into();rows.push(duplicate);Ok(())}).unwrap();
    assert!(r.publish(&index,device).is_err());assert!(r.ack_candidates(&index).is_err());
    crate::backend::session_store::update_checked(&index,|rows|{rows.retain(|s|s.id=="owned-user-meeting");Ok(())}).unwrap();
    drop(r);let mut r=Receiver::open(&root,&ds[0].encode().unwrap()).unwrap();
    for d in &ds[1..] {r.accept_segment(&d.encode().unwrap(),&raw).unwrap();}
    r.assemble().unwrap();assert_eq!(r.publish(&index,device).unwrap(),"owned-user-meeting");
    // Complete original audio is independent of physical consumption. A
    // retained development sample must still produce a verified saved result;
    // a user STOP retry cannot claim the device has reclaimed it.
    let saved=load();assert!(saved[0].audio_stored&&!saved[0].device_reclaimed);
    drop(r);Receiver::verify_saved_row(&saved[0]).unwrap();
    assert!(Receiver::verify_completed_row(&saved[0]).is_err());
    snapshot.host.sessions=saved.clone();
    assert!(!crate::backend::board_stop::completed_retry(&mut snapshot,&row.id).unwrap());
    let mut changed=saved[0].clone();changed.chunks[0].bytes+=1;
    assert!(Receiver::verify_saved_row(&changed).is_err());
    let mut r=Receiver::open(&root,&ds[0].encode().unwrap()).unwrap();
    for ack in r.ack_candidates(&index).unwrap(){r.confirm_acked(&ack).unwrap();}
    assert_eq!(r.publish(&index,device).unwrap(),"owned-user-meeting");
    let rows=load();assert_eq!(rows.len(),1);assert_eq!(rows[0].title,row.title);
    assert!(rows[0].audio_stored&&rows[0].device_reclaimed);assert_eq!(rows[0].status,"captured");
    assert_eq!(rows[0].chunks.len(),4);assert_eq!(rows[0].device_recording_id,Some(91));
    drop(r);Receiver::verify_completed_row(&rows[0]).unwrap();
    snapshot.host.sessions=rows.clone();
    assert!(crate::backend::board_stop::completed_retry(&mut snapshot,&row.id).unwrap());
    let mut changed=rows[0].clone();changed.chunks[0].bytes+=1;
    assert!(Receiver::verify_completed_row(&changed).is_err());
    assert_eq!(root.parent(),Some(std::env::temp_dir().as_path()));std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn recording_large_packet_profiles_negotiate_actual_mtu_and_keep_old_peer() {
    let (mut peer,_,_)=fixture();
    assert_eq!(u16le(&peer.negotiate_capacity(9,512,509).unwrap(),2),0);
    peer.max_value_bytes=509;
    for (mtu,preferred,expected) in [(512,509,509),(512,495,495),(251,509,248),(139,509,136),(512,244,244),
        (512,219,219),(202,219,199)] {
        let request=peer.negotiate_capacity(9,mtu,preferred).unwrap();
        assert_eq!(u16le(&request,2),expected);assert_eq!(u32le(&request,28),crc32fast::hash(&request[..28]));
    }
    assert!(peer.negotiate_capacity(9,512,500).is_err());
    assert!(peer.negotiate_capacity(9,23,509).is_err());
    let mut s=status(&peer);s[108..110].copy_from_slice(&509u16.to_le_bytes());
    let crc=crc32fast::hash(&s[84..112]);s[112..116].copy_from_slice(&crc.to_le_bytes());
    assert_eq!(Peer::from_status(&s).unwrap(),Some(peer));
}
