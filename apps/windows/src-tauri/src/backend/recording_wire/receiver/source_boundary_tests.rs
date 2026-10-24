//! Real Opus packets exported by the portable production C/NOR model, not a
//! fresh board recording. Its END is in segment1; the drain is in segment2.
use super::*;
pub(super) fn fixture()->Vec<(Descriptor,Vec<u8>)> {
    parse_fixture(include_bytes!("fixtures/source-boundary642.segments"))
}
fn parse_fixture(raw:&[u8])->Vec<(Descriptor,Vec<u8>)> {
    let mut at=0usize;let mut offset=0u64;let mut parts=Vec::new();
    while at<raw.len() {
        let n=u32::from_le_bytes(raw[at..at+4].try_into().unwrap())as usize;at+=4;
        let p=raw[at..at+n].to_vec();at+=n;
        let mut reader=cop1::Reader::new(p.as_slice(),offset,false).unwrap();
        while reader.next().unwrap().is_some(){}
        let summary=reader.finish(false).unwrap();let index=parts.len()as u32;
        let d=Descriptor{key:SessionKey{device_uid:[0x35;12],format_epoch:7,session_id:23},
            recording_id:901+index,segment_index:index,sample_offset:offset,sample_count:summary.frames*320,
            encoded_length:p.len()as u32,content_crc32:crc32fast::hash(&p),sha256:Sha256::digest(&p).into(),
            total_segments:0,flags:1,codec:3,source_mode:1,sync_state:0};
        offset+=d.sample_count;parts.push((d,p));
    }
    let count=parts.len()as u32;parts.last_mut().unwrap().0.flags=3;
    parts.last_mut().unwrap().0.total_segments=count;parts
}
#[test] fn exact_source_end_crosses_segment_without_early_completion_or_padding() {
    let root=std::env::temp_dir().join(format!("companion-boundary-{}",uuid::Uuid::new_v4()));
    fs::create_dir_all(&root).unwrap();let index=root.join("sessions.json");let parts=fixture();
    let mut r=Receiver::open(&root,&parts[0].0.encode().unwrap()).unwrap();
    for (d,p) in &parts[..2]{r.accept_segment(&d.encode().unwrap(),p).unwrap();}
    assert!(r.assemble().is_err(),"END without LAST/drain cannot complete a recording");
    assert!(r.receipt.audio.is_none());
    let (d,p)=parts.last().unwrap();r.accept_segment(&d.encode().unwrap(),p).unwrap();
    let output=r.assemble().unwrap();let saved=r.receipt.audio.as_ref().unwrap();
    assert_eq!(saved.samples,6400);assert_eq!(saved.bytes,44+6400*2);
    let timeline=saved.timeline.as_ref().unwrap();assert_eq!(timeline.captured_samples,6400);
    assert_eq!(timeline.source_origin_samples(),0);assert_eq!(timeline.playback_samples(),6400);
    assert!(timeline.sample_boundary.unwrap().boundary_complete);
    r.publish(&index,"C8:ED:45:EB:95:B4").unwrap();
    assert_eq!(r.ack_candidates(&index).unwrap().len(),3);
    assert!(r.receipt.segments.iter().all(|s|!s.acked));
    let wav=fs::read(&output).unwrap();drop(r);
    // Re-container the same production packets as one COP1 original. The
    // standalone import and segmented decoder must produce the same WAV.
    let mut flat=b"COP1\x04\x01\x14\x07\x80\x3e\x00\x00".to_vec();
    flat.extend_from_slice(&parts[0].1[12..44]);let mut end=None;
    for (d,p) in &parts {
        let mut reader=cop1::Reader::new(p.as_slice(),d.sample_offset,false).unwrap();
        while let Some(record)=reader.next().unwrap(){match record {
            cop1::Record::Boundary(b)if b.kind==2=>end=Some(b),
            cop1::Record::Audio(packet)=>{
                if let Some(e)=end.take(){
                    while flat.len()%248!=0{flat.push(255);}
                    let mut w=[0u8;32];w[2..6].copy_from_slice(b"CDB1");w[6]=2;
                    w[8..12].copy_from_slice(&e.delay_samples.to_le_bytes());w[12..20].copy_from_slice(&e.encoded_samples.to_le_bytes());
                    w[20..28].copy_from_slice(&e.valid_source_samples.to_le_bytes());let crc=crc32fast::hash(&w[..28]);w[28..].copy_from_slice(&crc.to_le_bytes());flat.extend_from_slice(&w);
                    while flat.len()%248!=0{flat.push(255);}
                }
                flat.extend_from_slice(&(packet.len()as u16).to_le_bytes());flat.extend_from_slice(&packet);
            }
            _=>(),
        }}
    }
    let input=root.join("continuous.opus");let imported=root.join("imported.wav");fs::write(&input,flat).unwrap();
    crate::backend::audio_decode::decode_recording(&input,&imported,false).unwrap();assert_eq!(fs::read(&imported).unwrap(),wav);
    let mut restored=Receiver::open(&root,&d.encode().unwrap()).unwrap();
    assert_eq!(restored.assemble().unwrap(),output);
    restored.receipt.audio.as_mut().unwrap().timeline.as_mut().unwrap().sample_boundary.as_mut().unwrap().source_origin_samples=320;
    assert!(restored.assemble().is_err(),"saved source mapping must agree with original metadata");
    assert_eq!(fs::read(&output).unwrap(),wav);drop(restored);fs::remove_dir_all(root).unwrap();
}
#[test] fn paused_stop_at_exact_rollover_has_one_declared_drain_and_preserves_gap() {
    let parts=parse_fixture(include_bytes!("fixtures/paused-stop642.segments"));assert_eq!(parts.len(),2);
    let root=std::env::temp_dir().join(format!("companion-boundary-pause-{}",uuid::Uuid::new_v4()));fs::create_dir_all(&root).unwrap();
    let mut r=Receiver::open(&root,&parts[0].0.encode().unwrap()).unwrap();
    for(d,p)in&parts{r.accept_segment(&d.encode().unwrap(),p).unwrap();}
    r.assemble().unwrap();let audio=r.receipt.audio.as_ref().unwrap();let t=audio.timeline.as_ref().unwrap();
    assert_eq!(audio.samples,3200);assert!(t.ended_paused);assert_eq!(t.events.len(),2);
    assert_eq!(t.playback_position(t.events[0].sample_offset),3200);drop(r);fs::remove_dir_all(root).unwrap();
}
#[test] fn production_marked_source4_rollover_keeps_exact_playback_positions_and_consume_gate() {
    let raw=include_bytes!("fixtures/engine-source-boundary-marks642.cmb4");assert_eq!(&raw[..4],b"CMB4");
    let count=u32::from_le_bytes(raw[4..8].try_into().unwrap())as usize;let mut at=8usize;let mut parts=Vec::new();
    for _ in 0..count {let len=u32::from_le_bytes(raw[at..at+4].try_into().unwrap())as usize;at+=4;
        let d=Descriptor::decode(&raw[at..at+112]).unwrap();at+=112;let p=raw[at..at+len].to_vec();at+=len;parts.push((d,p));}
    let root=std::env::temp_dir().join(format!("companion-boundary-marks-{}",uuid::Uuid::new_v4()));fs::create_dir_all(&root).unwrap();
    let index=root.join("sessions.json");let mut r=Receiver::open(&root,&parts[0].0.encode().unwrap()).unwrap();
    for(d,p)in&parts{r.accept_segment(&d.encode().unwrap(),p).unwrap();}
    r.assemble().unwrap();r.publish(&index,"C8:ED:45:EB:95:B4").unwrap();
    let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();let row=&rows[0];
    assert_eq!(row.bookmarks.len(),17);assert!(row.bookmarks.iter().all(|b|b.audio_position_ms==Some(b.position_ms)));
    let t=r.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap();assert_eq!(t.source_origin_samples(),0);
    assert_eq!(row.duration_ms,t.playback_samples()/16);assert_eq!(r.ack_candidates(&index).unwrap().len(),count);
    assert!(r.receipt.segments.iter().all(|s|!s.acked));drop(r);fs::remove_dir_all(root).unwrap();
}

#[test] fn interrupted_drain_keeps_saved_audio_and_last_source_mark_publishable() {
 let raw=include_bytes!("fixtures/engine-source-boundary-marks642.cmb4");
 let count=u32::from_le_bytes(raw[4..8].try_into().unwrap())as usize;let mut at=8usize;let mut parts=Vec::new();
 for _ in 0..count {let n=u32::from_le_bytes(raw[at..at+4].try_into().unwrap())as usize;at+=4;
  let d=Descriptor::decode(&raw[at..at+112]).unwrap();at+=112;let p=raw[at..at+n].to_vec();at+=n;parts.push((d,p));}
 let (last,p)=parts.last_mut().unwrap();assert!(last.sample_count>320);assert_eq!(&p[p.len()-42..p.len()-40],&40u16.to_le_bytes());
 p.truncate(p.len()-42);last.sample_count-=320;last.encoded_length=p.len()as u32;last.flags|=4;
 last.content_crc32=crc32fast::hash(p);last.sha256=Sha256::digest(p).into();
 let root=std::env::temp_dir().join(format!("companion-interrupted-source-mark-{}",uuid::Uuid::new_v4()));fs::create_dir_all(&root).unwrap();
 let index=root.join("sessions.json");let mut r=Receiver::open(&root,&parts[0].0.encode().unwrap()).unwrap();
 for(d,p)in&parts{r.accept_segment(&d.encode().unwrap(),p).unwrap();}
 r.assemble().unwrap();let output=r.audio_path();let before=fs::read(&output).unwrap();
 r.publish(&index,"C8:ED:45:EB:95:B4").expect("a missing drain must not block saved audio behind a valid final source mark");
 let rows=crate::backend::persistence::load_sessions_from(&index).unwrap();let row=&rows[0];
 assert!(row.capture_incomplete&&row.audio_stored&&!row.device_reclaimed);assert_eq!(row.pending_reason.as_deref(),Some("capture_interrupted"));
 assert_eq!(row.bookmarks.len(),17);assert!(row.bookmarks.iter().all(|b|b.audio_position_ms.is_some_and(|p|p<=row.duration_ms)));
 let last_mark=row.bookmarks.last().unwrap();assert!(last_mark.position_ms>last_mark.audio_position_ms.unwrap());
 let timeline=r.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap();assert!(!timeline.sample_boundary.unwrap().boundary_complete);
 assert_eq!(timeline.captured_samples-timeline.playback_samples(),40);
 assert_eq!(r.ack_candidates(&index).unwrap().len(),count);assert_eq!(fs::read(&output).unwrap(),before);
 let saved_marks=row.bookmarks.clone();drop(r);
 let mut restored=Receiver::open(&root,&parts[0].0.encode().unwrap()).unwrap();restored.assemble().unwrap();
 restored.publish(&index,"C8:ED:45:EB:95:B4").unwrap();
 let reopened=crate::backend::persistence::load_sessions_from(&index).unwrap();
 assert_eq!(reopened[0].bookmarks,saved_marks);assert!(reopened[0].capture_incomplete);
 assert_eq!(reopened[0].pending_reason.as_deref(),Some("capture_interrupted"));
 assert_eq!(restored.ack_candidates(&index).unwrap().len(),count);assert_eq!(fs::read(&output).unwrap(),before);
 drop(restored);fs::remove_dir_all(root).unwrap();
}
