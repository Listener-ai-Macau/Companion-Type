//! Software decoder/storage model. No microphone, BLE or device erase occurs.
use super::*;
use crate::backend::{cop1::tests::{audio,event},recording_bookmarks};
const DEVICE:&str="C8:92:FF:DD:3B:CA";
fn root()->PathBuf {
    let p=std::env::temp_dir().join(format!("companion-device-bookmarks-{}",uuid::Uuid::new_v4()));
    fs::create_dir_all(&p).unwrap();p
}
fn payload(index:u32)->Vec<u8> {
    let sample=u64::from(index)*1280+640;let time=u64::from(index)*1000;
    let mut p=b"COP1\x03\x01\x14\x03\x80\x3e\x00\x00".to_vec();audio(&mut p,2);
    event(&mut p,4,index*2+1,sample,time+40);
    event(&mut p,1,index*2+1,sample,time+50);
    event(&mut p,4,index*2+2,sample,time+100);
    event(&mut p,2,index*2+2,sample,time+200);audio(&mut p,2);p
}
fn descriptor(raw:&[u8],index:u32,last:bool)->Descriptor {
    Descriptor{key:SessionKey{device_uid:[0x35;12],format_epoch:7,session_id:23},recording_id:901+index,
        segment_index:index,sample_offset:u64::from(index)*1280,sample_count:1280,encoded_length:raw.len() as u32,
        content_crc32:crc32fast::hash(raw),sha256:Sha256::digest(raw).into(),total_segments:if last {index+1}else{0},
        flags:if last {3}else{1},codec:3,source_mode:1,sync_state:0}
}
fn rows(index:&Path)->Vec<crate::companion_v1::CompanionV1HostSession> {
    crate::backend::persistence::load_sessions_from(index).unwrap()
}

#[test]
fn offline_device_bookmarks_durable_before_consume_and_preserve_user_edits_after_restart() {
    let root=root();let index=root.join("sessions.json");let p0=payload(0);let p1=payload(1);
    let d0=descriptor(&p0,0,false);let d1=descriptor(&p1,1,true);
    let mut r=Receiver::open(&root,&d1.encode().unwrap()).unwrap();
    r.accept_segment(&d0.encode().unwrap(),&p0).unwrap();r.publish(&index,DEVICE).unwrap();
    let partial=rows(&index).remove(0);
    assert_eq!(partial.bookmarks.len(),2);assert_eq!(partial.device_bookmark_imports.len(),2);
    assert!(partial.bookmarks.iter().all(|p|p.audio_position_ms.is_none()));
    assert_eq!(r.ack_candidates(&index).unwrap().len(),1,"only the saved sealed segment, never the growth tail");
    r.accept_segment(&d1.encode().unwrap(),&p1).unwrap();let output=r.assemble().unwrap();
    r.publish(&index,DEVICE).unwrap();let mut library=rows(&index);let original=library[0].clone();
    let t=r.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap();
    assert_eq!(t.captured_samples,2560);assert_eq!(t.bookmarks.len(),4);assert_eq!(t.events.len(),4);
    assert_eq!(t.closed_pause_ms(),300);assert_eq!(fs::metadata(&output).unwrap().len(),44+7*320*2);
    assert_eq!(original.bookmarks.iter().map(|p|p.audio_position_ms.unwrap()).collect::<Vec<_>>(),vec![20,20,100,100]);
    assert!(original.bookmarks.iter().all(|p|p.source_recording_key==original.device_recording_key&&p.origin=="boardOffline"));
    let raw_before=fs::read(r.payload_path(&d0)).unwrap();let wav_before=fs::read(&output).unwrap();
    library[0].device_bookmark_imports.clear();
    crate::backend::session_store::save(&index,&library).unwrap();
    assert!(r.ack_candidates(&index).is_err(),"raw audio alone cannot authorize consumption of unsaved device marks");
    assert!(r.receipt.segments.iter().all(|s|!s.acked));
    library[0]=original.clone();
    let id=original.bookmarks[0].id.clone();
    let rename=recording_bookmarks::Request{session_id:original.id.clone(),bookmark_id:id.clone(),
        expected_revision:original.bookmark_revision,action:recording_bookmarks::Action::Rename,
        label:Some("预算决定".into()),position_ms:None};
    recording_bookmarks::apply(&mut library[0],&rename,None,None,"rename").unwrap();
    let deleted=original.bookmarks[1].id.clone();
    let delete=recording_bookmarks::Request{session_id:original.id.clone(),bookmark_id:deleted.clone(),
        expected_revision:library[0].bookmark_revision,action:recording_bookmarks::Action::Delete,label:None,position_ms:None};
    recording_bookmarks::apply(&mut library[0],&delete,None,None,"delete").unwrap();
    crate::backend::session_store::save(&index,&library).unwrap();let revision=library[0].bookmark_revision;drop(r);
    let mut reopened=Receiver::open(&root,&d1.encode().unwrap()).unwrap();
    reopened.publish(&index,DEVICE).unwrap();let saved=rows(&index).remove(0);
    assert_eq!(saved.bookmarks.len(),3);assert_eq!(saved.bookmark_revision,revision);
    assert_eq!(saved.bookmarks.iter().find(|p|p.id==id).unwrap().label,"预算决定");
    assert!(!saved.bookmarks.iter().any(|p|p.id==deleted),"deleted mark is not resurrected by source replay");
    assert_eq!(saved.device_bookmark_imports.len(),4);assert_eq!(reopened.ack_candidates(&index).unwrap().len(),2);
    assert_eq!(fs::read(reopened.payload_path(&d0)).unwrap(),raw_before);assert_eq!(fs::read(output).unwrap(),wav_before);
    drop(reopened);fs::remove_dir_all(root).unwrap();
}

#[test]
fn offline_device_bookmarks_reject_replayed_sequence_and_unknown_schema_without_consumption() {
    let first=payload(0);let mut replay=payload(1);
    for at in [248,744] { // Four records occupy separate media pages.
        let seq=if at==248 {1u32}else{2u32};
        replay[at+8..at+12].copy_from_slice(&seq.to_le_bytes());
        let crc=crc32fast::hash(&replay[at..at+28]);replay[at+28..at+32].copy_from_slice(&crc.to_le_bytes());
    }
    let root=root();let ds=[descriptor(&first,0,false),descriptor(&replay,1,true)];
    let mut r=Receiver::open(&root,&ds[1].encode().unwrap()).unwrap();
    r.accept_segment(&ds[0].encode().unwrap(),&first).unwrap();r.accept_segment(&ds[1].encode().unwrap(),&replay).unwrap();
    assert!(r.assemble().is_err());assert!(r.publish(&root.join("sessions.json"),DEVICE).is_err());
    assert!(r.receipt.segments.iter().all(|s|!s.acked));drop(r);fs::remove_dir_all(root).unwrap();
    let mut old=first;old[4]=2;old[7]=1;
    let mut reader=crate::backend::cop1::Reader::new(old.as_slice(),0,false).unwrap();
    assert!(reader.next().unwrap().is_some());assert!(reader.next().unwrap().is_some());
    assert!(reader.next().is_err(),"schema2 cannot silently acquire a new event kind");
}

#[test]
fn offline_device_bookmarks_failed_publication_keeps_raw_and_allows_later_retry() {
    let root=root();let p=payload(0);let d=descriptor(&p,0,true);
    let mut r=Receiver::open(&root,&d.encode().unwrap()).unwrap();r.accept_segment(&d.encode().unwrap(),&p).unwrap();r.assemble().unwrap();
    let index=root.join("blocked-index");fs::create_dir(&index).unwrap();
    assert!(r.publish(&index,DEVICE).is_err());assert!(r.ack_candidates(&index).is_err());
    assert!(!r.receipt.segments[0].acked);assert_eq!(fs::read(r.payload_path(&d)).unwrap(),p);
    let good=root.join("sessions.json");r.publish(&good,DEVICE).unwrap();assert_eq!(r.ack_candidates(&good).unwrap().len(),1);
    drop(r);fs::remove_dir_all(root).unwrap();
}

#[test]
fn c_engine_offline_marks_cross_decoder_preserves_audio_and_durable_positions() {
    // Produced by the production C recorder/NOR/Opus software model, not a
    // physical capture. Mark padding, shortened roll and both descriptors
    // must agree with this receiver without re-encoding or invented samples.
    let golden=include_bytes!("../../cop1/tests/engine-bookmarks.cmb3");
    fn take<'a>(data:&'a [u8],at:&mut usize,n:usize)->&'a [u8] {let out=&data[*at..*at+n];*at+=n;out}
    let mut at=0;assert_eq!(take(golden,&mut at,4),b"CMB3");
    let count=u32::from_le_bytes(take(golden,&mut at,4).try_into().unwrap());assert_eq!(count,2);
    let mut segments=Vec::new();let mut samples=0;
    for _ in 0..count {
        let length=u32::from_le_bytes(take(golden,&mut at,4).try_into().unwrap()) as usize;
        let wire=take(golden,&mut at,112).to_vec();let payload=take(golden,&mut at,length).to_vec();
        let d=Descriptor::decode(&wire).unwrap();d.verify_payload(&payload).unwrap();
        assert_eq!(d.sample_offset,samples);samples+=d.sample_count;
        segments.push((wire,payload));
    }
    let n=u32::from_le_bytes(take(golden,&mut at,4).try_into().unwrap()) as usize;
    let baseline=take(golden,&mut at,n);assert_eq!(at,golden.len());
    let root=root();let index=root.join("sessions.json");
    let mut receiver=Receiver::open(&root,&segments[1].0).unwrap();
    for (wire,payload) in &segments {receiver.accept_segment(wire,payload).unwrap();}
    let output=receiver.assemble().unwrap();let timeline=receiver.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap();
    assert_eq!(timeline.captured_samples,samples);assert_eq!(timeline.bookmarks.len(),17);
    assert!(timeline.events.is_empty());assert_eq!(timeline.closed_pause_ms(),0);
    assert_eq!(timeline.bookmarks[0].sample_offset,960,"queued half-packet rounds down on the original sample axis");
    let positions=timeline.bookmarks.iter().map(|p|p.sample_offset.saturating_sub(320)/16).collect::<Vec<_>>();
    let original=fs::read(output).unwrap();assert_eq!(original.len() as u64,44+(samples-320)*2);
    let input=root.join("unmarked-baseline.cop1");let expected=root.join("baseline.wav");fs::write(&input,baseline).unwrap();
    crate::backend::audio_decode::decode_recording(&input,&expected,false).unwrap();
    assert_eq!(fs::read(expected).unwrap(),original,"one decoder and one preskip across mark pages and segment roll");
    assert!(receiver.ack_candidates(&index).is_err(),"source bytes alone cannot authorize consumption");
    receiver.publish(&index,DEVICE).unwrap();let saved=rows(&index).remove(0);
    assert_eq!(saved.device_bookmark_imports.len(),17);assert_eq!(saved.bookmarks.len(),17);
    assert_eq!(saved.bookmarks.iter().map(|p|p.audio_position_ms.unwrap()).collect::<Vec<_>>(),positions);
    assert!(saved.bookmarks.iter().all(|p|p.source_recording_key==saved.device_recording_key&&p.origin=="boardOffline"));
    assert_eq!(receiver.ack_candidates(&index).unwrap().len(),2);
    drop(receiver);let mut reopened=Receiver::open(&root,&segments[1].0).unwrap();reopened.publish(&index,DEVICE).unwrap();
    assert_eq!(rows(&index)[0].bookmarks,saved.bookmarks);assert_eq!(fs::read(reopened.audio_path()).unwrap(),original);
    assert!(reopened.receipt.segments.iter().all(|s|!s.acked));drop(reopened);fs::remove_dir_all(root).unwrap();
}
