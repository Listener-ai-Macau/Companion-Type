use super::*;
use crate::backend::cop1::tests::{audio,event,fixture};

fn descriptor(payload:&[u8],index:u32,samples:u64,last:bool)->Descriptor {
    Descriptor{key:super::super::SessionKey{device_uid:[0x35;12],format_epoch:7,session_id:23},
        recording_id:901+index,segment_index:index,sample_offset:u64::from(index)*1280,
        sample_count:samples,encoded_length:payload.len() as u32,content_crc32:crc32fast::hash(payload),
        sha256:Sha256::digest(payload).into(),total_segments:if last {index+1} else {0},
        flags:if last {3} else {1},codec:3,source_mode:1,sync_state:0}
}
fn root()->PathBuf {
    let path=std::env::temp_dir().join(format!("companion-pause-receiver-{}",uuid::Uuid::new_v4()));
    fs::create_dir_all(&path).unwrap();path
}
fn rewrite_event(payload:&mut [u8],at:usize,kind:u8,seq:u32,ms:u64) {
    payload[at+6]=kind;payload[at+8..at+12].copy_from_slice(&seq.to_le_bytes());
    payload[at+20..at+28].copy_from_slice(&ms.to_le_bytes());
    let crc=crc32fast::hash(&payload[at..at+28]);payload[at+28..at+32].copy_from_slice(&crc.to_le_bytes());
}

#[test]
fn paused_cross_segment_original_decodes_once_and_recovers_durable_gap_index() {
    let root=root();let first=fixture(0);let mut second=fixture(1280);
    rewrite_event(&mut second,248,1,3,5120);rewrite_event(&mut second,496,2,4,8120);
    let ds=[descriptor(&first,0,1280,false),descriptor(&second,1,1280,true)];
    let output;
    {
        let mut r=Receiver::open(&root,&ds[1].encode().unwrap()).unwrap();
        r.accept_segment(&ds[0].encode().unwrap(),&first).unwrap();
        r.accept_segment(&ds[1].encode().unwrap(),&second).unwrap();
        output=r.assemble().unwrap();let saved=r.receipt.audio.as_ref().unwrap();
        let timeline=saved.timeline.as_ref().unwrap();
        assert_eq!(timeline.events.len(),4);assert_eq!(timeline.closed_pause_ms(),8000);
        assert_eq!(timeline.captured_samples,2560);assert_eq!(saved.samples,2240);
        assert_eq!(saved.bytes,44+2240*2);
        assert_eq!(timeline.events[2].sample_offset,1920);
        assert!(!timeline.pause_open_at_end);assert!(r.receipt.segments.iter().all(|s|s.received && !s.acked));
        assert_eq!(fs::read(r.payload_path(&ds[0])).unwrap(),first);
        assert_eq!(fs::read(r.payload_path(&ds[1])).unwrap(),second);
    }
    let wav=fs::read(&output).unwrap();
    let mut legacy=b"COP1\x01\x01\x14\x00\x80\x3e\x00\x00".to_vec();audio(&mut legacy,8);
    let input=root.join("continuous.cop1");let baseline=root.join("continuous.wav");fs::write(&input,legacy).unwrap();
    crate::backend::audio_decode::decode_recording(&input,&baseline,false).unwrap();
    assert_eq!(wav,fs::read(&baseline).unwrap(),"same audio, one pre-skip, no gap silence or segment reset");
    {
        let mut r=Receiver::open(&root,&ds[1].encode().unwrap()).unwrap();
        assert_eq!(r.assemble().unwrap(),output);assert_eq!(r.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap().closed_pause_ms(),8000);
        r.receipt.audio.as_mut().unwrap().timeline.as_mut().unwrap().events[1].elapsed_ms+=1;
        assert!(r.assemble().is_err(),"receipt times must agree with exact raw event proof");
        assert_eq!(fs::read(&output).unwrap(),wav);
    }
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn full_outer_crc_sha_does_not_accept_unpaired_or_cross_segment_replayed_events() {
    let root=root();let mut p=fixture(0);rewrite_event(&mut p,248,2,1,40);
    let d=descriptor(&p,0,1280,true);let mut r=Receiver::open(&root,&d.encode().unwrap()).unwrap();
    assert!(r.accept_segment(&d.encode().unwrap(),&p).is_err());
    assert!(!r.receipt.segments[0].received);assert!(!r.audio_path().exists());
    assert!(!r.payload_path(&d).exists(),"invalid events cannot be committed as verified original");
    drop(r);fs::remove_dir_all(&root).unwrap();
    let root=super::pause_tests::root();let first=fixture(0);let second=fixture(1280);
    let ds=[descriptor(&first,0,1280,false),descriptor(&second,1,1280,true)];
    let mut r=Receiver::open(&root,&ds[1].encode().unwrap()).unwrap();
    r.accept_segment(&ds[0].encode().unwrap(),&first).unwrap();
    r.accept_segment(&ds[1].encode().unwrap(),&second).unwrap();
    assert!(r.assemble().is_err(),"replayed sequence across otherwise valid segments is refused");
    assert!(!r.audio_path().exists());assert!(r.receipt.segments.iter().all(|s|!s.acked));
    let index=root.join("sessions.json");r.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
    assert!(r.ack_candidates(&index).is_err(),"invalid global timing cannot authorize consume even with valid raw hashes");
    drop(r);fs::remove_dir_all(root).unwrap();
}

#[test]
fn ended_pause_and_recovered_open_pause_keep_true_audio_and_unknown_end() {
    for ended in [false,true] {
        let root=root();let mut p=b"COP1\x02\x01\x14\x01\x80\x3e\x00\x00".to_vec();audio(&mut p,2);
        event(&mut p,1,7,640,40);if ended {event(&mut p,3,8,640,3040);}
        let mut d=descriptor(&p,0,640,true);if !ended {d.flags|=4;}
        let mut r=Receiver::open(&root,&d.encode().unwrap()).unwrap();r.accept_segment(&d.encode().unwrap(),&p).unwrap();
        let output=r.assemble().unwrap();let timeline=r.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap();
        assert_eq!(timeline.pause_open_at_end,!ended);assert_eq!(timeline.ended_paused,ended);
        assert_eq!(timeline.closed_pause_ms(),if ended {3000} else {0});
        assert_eq!(fs::metadata(output).unwrap().len(),44+320*2);
        drop(r);let r=Receiver::open(&root,&d.encode().unwrap()).unwrap();
        assert_eq!(r.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap().pause_open_at_end,!ended);
        drop(r);fs::remove_dir_all(root).unwrap();
    }
}

#[test]
fn c_engine_pause_container_cross_decoder_keeps_full_original_and_baseline_audio() {
    let golden=include_bytes!("../../cop1/tests/engine-pause.cpf2");
    fn take<'a>(data:&'a [u8],at:&mut usize,n:usize)->&'a [u8] {let out=&data[*at..*at+n];*at+=n;out}
    let mut at=0;assert_eq!(take(golden,&mut at,4),b"CPF2");
    let count=u32::from_le_bytes(take(golden,&mut at,4).try_into().unwrap());assert_eq!(count,4);
    let mut segments=Vec::new();
    for _ in 0..count {
        let length=u32::from_le_bytes(take(golden,&mut at,4).try_into().unwrap()) as usize;
        let wire=take(golden,&mut at,112).to_vec();let payload=take(golden,&mut at,length).to_vec();
        let d=Descriptor::decode(&wire).unwrap();d.verify_payload(&payload).unwrap();segments.push((wire,payload));
    }
    let n=u32::from_le_bytes(take(golden,&mut at,4).try_into().unwrap()) as usize;
    let baseline=take(golden,&mut at,n);assert_eq!(at,golden.len());
    let root=root();let mut r=Receiver::open(&root,&segments.last().unwrap().0).unwrap();
    for (wire,payload) in &segments {r.accept_segment(wire,payload).unwrap();}
    let output=r.assemble().unwrap();let timeline=r.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap();
    assert_eq!(timeline.closed_pause_ms(),2000);assert_eq!(timeline.captured_samples,40*320);
    assert_eq!(timeline.events.len(),2);assert_eq!(timeline.events[0].sample_offset,1280);
    assert_eq!(timeline.audio_packet_bytes,40*42);assert_eq!(timeline.event_bytes,64);
    let original=fs::read(&output).unwrap();assert_eq!(original.len(),44+39*320*2);
    let input=root.join("c-continuous-baseline.cop1");let expected=root.join("baseline.wav");fs::write(&input,baseline).unwrap();
    crate::backend::audio_decode::decode_recording(&input,&expected,false).unwrap();assert_eq!(fs::read(expected).unwrap(),original);
    for (wire,payload) in &segments {assert_eq!(fs::read(r.payload_path(&Descriptor::decode(wire).unwrap())).unwrap(),*payload);}
    let index=root.join("sessions.json");r.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
    assert_eq!(r.ack_candidates(&index).unwrap().len(),4,"full raw/timeline/library proof permits exact softwareACKs");
    drop(r);let r=Receiver::open(&root,&segments[3].0).unwrap();assert_eq!(fs::read(r.audio_path()).unwrap(),original);
    assert!(r.receipt.segments.iter().all(|segment|!segment.acked));drop(r);fs::remove_dir_all(root).unwrap();
}
