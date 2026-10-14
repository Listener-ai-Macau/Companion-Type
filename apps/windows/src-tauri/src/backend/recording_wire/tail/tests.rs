use super::*;
use crate::backend::cop1::{Reader,Record,Timeline};
fn engine_fixture()->(Peer,Vec<(Tail,Vec<u8>)>,Descriptor,Vec<u8>) {
    let bytes=include_bytes!("../../cop1/tests/engine-pause-tail.cpt2");
    fn take<'a>(bytes:&'a [u8],at:&mut usize,n:usize)->&'a [u8]{let out=&bytes[*at..*at+n];*at+=n;out}
    let mut at=0;assert_eq!(take(bytes,&mut at,4),b"CPT2");
    assert_eq!(u32::from_le_bytes(take(bytes,&mut at,4).try_into().unwrap()),3);
    let peer=Peer{uid:[1,2,3,4,5,6,7,8,9,10,11,12],epoch:7,capacity:64,max_value_bytes:248,
        logical_control:true,growing_tail:true,pause_control:false,batch_interval:false};
    let key=SessionKey{device_uid:peer.uid,format_epoch:peer.epoch,session_id:56};let mut tails=Vec::new();
    for _ in 0..3 {
        let wire=take(bytes,&mut at,80);let n=u32::from_le_bytes(take(bytes,&mut at,4).try_into().unwrap()) as usize;
        let tail=Tail::decode(wire,&peer,&key,u32le(wire,68)).unwrap();let raw=take(bytes,&mut at,n).to_vec();
        validate_audio(&tail,&raw).unwrap();tails.push((tail,raw));
    }
    let d=Descriptor::decode(take(bytes,&mut at,112)).unwrap();
    let n=u32::from_le_bytes(take(bytes,&mut at,4).try_into().unwrap()) as usize;
    let raw=take(bytes,&mut at,n).to_vec();assert_eq!(at,bytes.len());d.verify_payload(&raw).unwrap();
    (peer,tails,d,raw)
}
fn root()->PathBuf {
    let root=std::env::temp_dir().join(format!("companion-pause-tail-{}",uuid::Uuid::new_v4()));
    fs::create_dir(&root).unwrap();root
}
fn rewrite_wire(tail:&Tail,samples:u64,bytes:u32,flags:u16)->Vec<u8> {
    let mut wire=tail.wire.clone();wire[52..60].copy_from_slice(&samples.to_le_bytes());
    wire[60..64].copy_from_slice(&bytes.to_le_bytes());wire[74..76].copy_from_slice(&flags.to_le_bytes());
    let crc=crc32fast::hash(&wire[..76]);wire[76..].copy_from_slice(&crc.to_le_bytes());wire
}
fn fixture(frames:u32)->(Peer,Tail,Vec<u8>) {
    let peer=Peer{uid:[0x35;12],epoch:0xc055aa0710123456,capacity:64,max_value_bytes:248,logical_control:true,growing_tail:true,pause_control:false,batch_interval:false};
    let key=SessionKey{device_uid:peer.uid,format_epoch:peer.epoch,session_id:0x100000002};
    let mut p=vec![0;80];p[..8].copy_from_slice(b"CLP2\x02\x00\x50\x00");p[8..20].copy_from_slice(&peer.uid);
    p[20..28].copy_from_slice(&peer.epoch.to_le_bytes());p[28..36].copy_from_slice(&key.session_id.to_le_bytes());
    p[36..40].copy_from_slice(&91u32.to_le_bytes());p[40..44].copy_from_slice(&0u32.to_le_bytes());
    p[52..60].copy_from_slice(&(u64::from(frames)*320).to_le_bytes());
    p[60..64].copy_from_slice(&(12+frames*42).to_le_bytes());p[68..72].copy_from_slice(&9u32.to_le_bytes());
    p[72]=3;p[73]=super::super::SOURCE_MIC_SAI;p[74]=1;let crc=crc32fast::hash(&p[..76]);p[76..80].copy_from_slice(&crc.to_le_bytes());
    let mut body=b"COP1\x01\x01\x14\x00\x80\x3e\0\0".to_vec();
    for _ in 0..frames {body.extend_from_slice(&[40,0]);body.extend_from_slice(&[0x35;40]);}
    (peer.clone(),Tail::decode(&p,&peer,&key,9).unwrap(),body)
}
#[test]
fn protected_tail_rejects_stale_scope_partial_frame_and_never_becomes_sealed() {
    let (peer,tail,_)=fixture(5);
    assert_eq!(Tail::request(&peer,&tail.key,9).unwrap()[1],0x23);
    assert_eq!(tail.pull(192,4).unwrap()[1],0x24);
    assert!(tail.pull(222,4).is_err());
    assert!(Tail::decode(&tail.wire,&peer,&tail.key,10).is_err());
    let mut wrong=tail.key.clone();wrong.session_id+=1;
    assert!(Tail::decode(&tail.wire,&peer,&wrong,9).is_err());
    let mut p=tail.wire.clone();p[60]+=1;let crc=crc32fast::hash(&p[..76]);p[76..].copy_from_slice(&crc.to_le_bytes());
    assert!(Tail::decode(&p,&peer,&tail.key,9).is_err());
    assert!(Descriptor::decode(&tail.wire).is_err());
}
#[test]
fn durable_prefix_recovers_grows_then_sealed_sha_still_governs_consume() {
    let root=std::env::temp_dir().join(format!("companion-tail-{}",uuid::Uuid::new_v4()));fs::create_dir(&root).unwrap();
    let (peer,first,bytes)=fixture(5);
    let (p,empty)=Prefix::load(&root,&first,&peer).unwrap();assert!(empty.is_empty());p.save(&first,&bytes,&peer).unwrap();drop(p);
    let (_,grown,more)=fixture(10);let (p,saved)=Prefix::load(&root,&grown,&peer).unwrap();assert_eq!(saved,bytes);
    let mut changed=more.clone();changed[60]^=1;assert!(p.save(&grown,&changed,&peer).is_err());
    p.save(&grown,&more,&peer).unwrap();drop(p);
    assert!(Prefix::load(&root,&first,&peer).is_err(),"board cannot shrink below a durable cursor");
    let d=Descriptor{key:grown.key.clone(),recording_id:91,segment_index:0,sample_offset:0,sample_count:3200,
        encoded_length:more.len() as u32,content_crc32:crc32fast::hash(&more),sha256:Sha256::digest(&more).into(),
        total_segments:1,flags:3,codec:3,source_mode:super::super::SOURCE_MIC_SAI,sync_state:0};
    assert_eq!(Prefix::sealed(&root,&d,&peer).unwrap().unwrap(),more);
    let mut bad=d.clone();bad.sha256[0]^=1;assert!(bad.verify_payload(&more).is_err());
    assert!(Prefix::release(&root,&bad,&peer).is_err());
    Prefix::release(&root,&d,&peer).unwrap();assert!(Prefix::sealed(&root,&d,&peer).unwrap().is_none());
    fs::remove_dir_all(root).unwrap();
}
#[test]
fn corrupt_durable_body_does_not_advance_cursor() {
    let root=std::env::temp_dir().join(format!("companion-tail-{}",uuid::Uuid::new_v4()));fs::create_dir(&root).unwrap();
    let (peer,tail,bytes)=fixture(5);let (p,_)=Prefix::load(&root,&tail,&peer).unwrap();p.save(&tail,&bytes,&peer).unwrap();drop(p);
    let body=fs::read_dir(&root).unwrap().map(|p|p.unwrap().path()).find(|p|p.extension().is_some_and(|e|e=="opus")).unwrap();
    let mut changed=bytes;changed[100]^=1;fs::write(body,changed).unwrap();assert!(Prefix::load(&root,&tail,&peer).is_err());
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn c_pipeline_paused_tail_survives_restart_grows_without_fake_samples_then_requires_full_seal() {
    let root=root();let (peer,tails,d,raw)=engine_fixture();
    assert_eq!(tails.iter().map(|(tail,_)|tail.sample_count).collect::<Vec<_>>(),vec![1600,2560,2560]);
    assert_eq!(tails.iter().map(|(tail,_)|tail.encoded_length).collect::<Vec<_>>(),vec![222,744,992]);
    let mut old=Vec::new();
    for (tail,body) in &tails {
        let (prefix,saved)=Prefix::load(&root,tail,&peer).unwrap();assert_eq!(saved,old);
        prefix.save(tail,body,&peer).unwrap();drop(prefix); // Each step reopens the actual durable cursor.
        let (prefix,saved)=Prefix::load(&root,tail,&peer).unwrap();assert_eq!(saved,*body);drop(prefix);
        assert!(Descriptor::decode(&tail.wire).is_err(),"live prefix is never a sealed/consume proof");old=body.clone();
    }
    let (prefix,saved)=Prefix::load(&root,&tails[2].0,&peer).unwrap();assert_eq!(saved.len(),992);drop(prefix);
    assert!(Prefix::load(&root,&tails[0].0,&peer).is_err(),"pause does not authorize cursor rollback");
    let saved=Prefix::sealed(&root,&d,&peer).unwrap().unwrap();assert!(raw.starts_with(&saved));d.verify_payload(&raw).unwrap();
    let mut receiver=super::super::receiver::Receiver::open(&root,&d.encode().unwrap()).unwrap();
    assert!(receiver.assemble().is_err(),"cached live bytes alone do not publish a complete recording");
    receiver.accept_segment(&d.encode().unwrap(),&raw).unwrap();let wav=receiver.assemble().unwrap();
    assert_eq!(fs::metadata(wav).unwrap().len(),44+11*320*2);
    let mut parser=Reader::new(raw.as_slice(),d.sample_offset,false).unwrap();let mut timeline=Timeline::default();
    while let Some(record)=parser.next().unwrap(){if let Record::Event(event)=record{timeline.push(event).unwrap();}}
    timeline.add_segment(&parser.finish(false).unwrap()).unwrap();
    assert_eq!(timeline.captured_samples,12*320);assert_eq!(timeline.events.len(),2);assert_eq!(timeline.event_bytes,64);
    assert!(timeline.closed_pause_ms()>=5000&&!timeline.pause_open_at_end);
    let index=root.join("sessions.json");receiver.publish(&index,"C8:92:FF:DD:3B:CA").unwrap();
    assert_eq!(receiver.ack_candidates(&index).unwrap().len(),1,"only full raw/timeline/library proof authorizes exact softwareACK");
    Prefix::release(&root,&d,&peer).unwrap();assert!(Prefix::sealed(&root,&d,&peer).unwrap().is_none());
    drop(receiver);fs::remove_dir_all(root).unwrap();
}

#[test]
fn paused_tail_rejects_count_spoof_crc_valid_unpaired_or_partial_event_without_advancing() {
    let root=root();let (peer,tails,_,_)=engine_fixture();let (tail,body)=&tails[1];
    let (prefix,_)=Prefix::load(&root,tail,&peer).unwrap();prefix.save(tail,body,&peer).unwrap();
    let wire=rewrite_wire(tail,tail.sample_count+320,tail.encoded_length,3);
    let spoof=Tail::decode(&wire,&peer,&tail.key,u32le(&wire,68)).unwrap();
    assert!(prefix.save(&spoof,body,&peer).is_err(),"CRC-valid count must agree with actual Opus records");
    let wire=rewrite_wire(tail,tail.sample_count,tail.encoded_length,5);
    assert!(Tail::decode(&wire,&peer,&tail.key,u32le(&wire,68)).is_err());
    let wire=rewrite_wire(tail,tail.sample_count,tail.encoded_length,1);
    assert!(Tail::decode(&wire,&peer,&tail.key,u32le(&wire,68)).is_err(),"no schema1 fallback for event bytes");
    let mut wrong=body.clone();wrong[496+6]=2;let crc=crc32fast::hash(&wrong[496..524]);wrong[524..528].copy_from_slice(&crc.to_le_bytes());
    assert!(prefix.save(tail,&wrong,&peer).is_err(),"outer receipt hashing does not excuse unpaired resume");
    let wire=rewrite_wire(tail,tail.sample_count,527,3);
    let partial=Tail::decode(&wire,&peer,&tail.key,u32le(&wire,68)).unwrap();
    assert!(validate_audio(&partial,&body[..527]).is_err(),"committed tail must contain complete event records");
    assert_eq!(prefix.read(&peer,&tail.key).unwrap().unwrap().1,*body,"failed candidates leave durable raw cursor unchanged");
    drop(prefix);fs::remove_dir_all(root).unwrap();
}
