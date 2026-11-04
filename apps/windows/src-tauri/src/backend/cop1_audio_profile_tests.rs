use super::*;
const PROFILE:&[u8;96]=include_bytes!("fixtures/audio-profile-v1.bin");
fn crc(w:&mut [u8;96]){let c=crc32fast::hash(&w[..92]);w[92..].copy_from_slice(&c.to_le_bytes());}
fn boundary(kind:u8,encoded:u64,valid:u64)->[u8;32]{
    let mut w=[0u8;32];w[2..6].copy_from_slice(b"CDB1");w[6]=kind;w[8..12].copy_from_slice(&40u32.to_le_bytes());
    w[12..20].copy_from_slice(&encoded.to_le_bytes());w[20..28].copy_from_slice(&valid.to_le_bytes());
    let c=crc32fast::hash(&w[..28]);w[28..].copy_from_slice(&c.to_le_bytes());w
}
fn source()->Vec<u8>{
    let mut b=b"COP1\x05\x01\x14\x0f\x80\x3e\x00\x00".to_vec();b.extend_from_slice(&boundary(1,0,u64::MAX));b.extend_from_slice(PROFILE);
    for _ in 0..2 {b.extend_from_slice(&40u16.to_le_bytes());b.extend_from_slice(&tests::PACKET);}
    while b.len()%248!=0 {b.push(255);}b.extend_from_slice(&boundary(2,960,640));while b.len()%248!=0{b.push(255);}
    b.extend_from_slice(&40u16.to_le_bytes());b.extend_from_slice(&tests::PACKET);b
}
fn read(bytes:&[u8],live:bool)->Result<Summary,String>{let mut r=Reader::new(bytes,0,live)?;while r.next()?.is_some(){}r.finish(true)}
#[test]fn c_golden_parameters_and_saved_timeline_roundtrip(){
    let p=AudioProfile::decode(PROFILE).unwrap();assert_eq!(p.output,3);assert_eq!(p.delay_q8,128);assert_eq!(p.firmware_source,[0x5a;20]);assert_eq!(p.calibration_sha256,[0x83;32]);
    let original=source();let mut reader=Reader::new(original.as_slice(),0,false).unwrap();let mut window=SampleWindow::new(reader.schema,320).unwrap();
    while let Some(record)=reader.next().unwrap(){match record {Record::Audio(_)=>{window.packet(320).unwrap();},Record::Boundary(b)=>window.observe(b).unwrap(),Record::Event(_)=>panic!()}}
    let summary=reader.finish(false).unwrap();assert_eq!(summary.frames,3);assert_eq!(summary.audio_profile,Some(p));assert_eq!(window.finish(false).unwrap().written_samples,640);
    let mut t=Timeline::default();t.add_segment(&summary).unwrap();t.apply_boundary(window.finish(false).unwrap());
    let saved=serde_json::to_vec(&t).unwrap();let reloaded:Timeline=serde_json::from_slice(&saved).unwrap();assert_eq!(t,reloaded);assert_eq!(reloaded.audio_profile,Some(p));
    let old:Timeline=serde_json::from_str(r#"{"events":[],"capturedSamples":0,"audioPacketBytes":0,"eventBytes":0,"paddingBytes":0,"pauseOpenAtEnd":false,"endedPaused":false}"#).unwrap();assert_eq!(old.audio_profile,None);
}
#[test]fn corrupt_unknown_and_noncanonical_profile_refuse(){
    for i in 0..96 {for bit in 0..8{let mut w=*PROFILE;w[i]^=1<<bit;assert!(AudioProfile::decode(&w).is_err());}}
    for (at,value) in [(7,4),(8,1),(9,1),(10,8),(11,1),(80,65),(82,2),(83,2),(84,2),(86,1)]{let mut w=*PROFILE;w[at]=value;crc(&mut w);assert!(AudioProfile::decode(&w).is_err());}
}
#[test]fn required_prelude_is_not_inferred_from_current_settings(){
    let source=source();let mut missing=source.clone();missing.drain(44..140);assert!(read(&missing,false).is_err());
    let mut duplicate=source.clone();duplicate.splice(140..140,PROFILE.iter().copied());assert!(read(&duplicate,false).is_err());
    let mut late=source.clone();late.drain(44..140);late.splice(86..86,PROFILE.iter().copied());assert!(read(&late,false).is_err());
    let mut wrong=source.clone();wrong[4]=4;wrong[7]=7;assert!(read(&wrong,false).is_err());
    for n in 12..140 {assert!(read(&source[..n],false).is_err(),"finalized prelude length {n}");let p=read(&source[..n],true).unwrap();assert!(p.audio_profile.is_none());assert_eq!(p.frames,0);}
}
#[test]fn changed_or_missing_profile_cannot_relabel_one_logical_recording(){
    let s=read(&source(),false).unwrap();let mut t=Timeline::default();t.add_segment(&s).unwrap();let before=t.clone();
    let mut other=s;other.audio_profile.as_mut().unwrap().firmware_source[0]^=1;assert!(t.add_segment(&other).is_err());assert_eq!(t,before);
    other=s;other.audio_profile=None;assert!(t.add_segment(&other).is_err());assert_eq!(t,before);
    let mut old=Timeline::default();let mut legacy=s;legacy.audio_profile=None;old.add_segment(&legacy).unwrap();let before=old.clone();assert!(old.add_segment(&s).is_err());assert_eq!(old,before);
}
