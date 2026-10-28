//! Same retained production-model Opus packets, re-containered with the C
//! synthetic provenance golden. This is file/receiver evidence, not new audio.
use super::*;
const PROFILE:&[u8;96]=include_bytes!("../../fixtures/audio-profile-v1.bin");
fn put_boundary(b:cop1::CodecBoundary)->[u8;32]{
    let mut w=[0;32];w[2..6].copy_from_slice(b"CDB1");w[6]=b.kind;w[8..12].copy_from_slice(&b.delay_samples.to_le_bytes());
    w[12..20].copy_from_slice(&b.encoded_samples.to_le_bytes());w[20..28].copy_from_slice(&b.valid_source_samples.to_le_bytes());
    let c=crc32fast::hash(&w[..28]);w[28..].copy_from_slice(&c.to_le_bytes());w
}
fn pad(b:&mut Vec<u8>){while b.len()%248!=0{b.push(255);}}
pub(super) fn fixture()->Vec<(Descriptor,Vec<u8>)>{
    source_boundary_tests::fixture().into_iter().map(|(mut d,old)|{
        let mut b=b"COP1\x05\x01\x14\x0f\x80\x3e\x00\x00".to_vec();
        let mut reader=cop1::Reader::new(old.as_slice(),d.sample_offset,false).unwrap();
        while let Some(r)=reader.next().unwrap(){match r {
            cop1::Record::Boundary(v)=>{if v.kind==2{pad(&mut b);}b.extend_from_slice(&put_boundary(v));if v.kind==1{b.extend_from_slice(PROFILE);}else{pad(&mut b);}},
            cop1::Record::Audio(p)=>{b.extend_from_slice(&(p.len()as u16).to_le_bytes());b.extend_from_slice(&p);},
            cop1::Record::Event(e)=>{
                pad(&mut b);let mut w=[0;32];w[2..6].copy_from_slice(b"CPG1");w[6]=e.kind;w[8..12].copy_from_slice(&e.sequence.to_le_bytes());
                w[12..20].copy_from_slice(&e.sample_offset.to_le_bytes());w[20..28].copy_from_slice(&e.elapsed_ms.to_le_bytes());let c=crc32fast::hash(&w[..28]);w[28..].copy_from_slice(&c.to_le_bytes());b.extend_from_slice(&w);pad(&mut b);
            }
        }}reader.finish(false).unwrap();
        d.encoded_length=b.len()as u32;d.content_crc32=crc32fast::hash(&b);d.sha256=Sha256::digest(&b).into();(d,b)
    }).collect()
}
pub(super) fn change_identity(d:&mut Descriptor,p:&mut [u8]){
    p[44+24]^=1;let crc=crc32fast::hash(&p[44..44+92]);p[44+92..44+96].copy_from_slice(&crc.to_le_bytes());
    d.content_crc32=crc32fast::hash(p);d.sha256=Sha256::digest(p).into();
}
fn root()->PathBuf{let p=std::env::temp_dir().join(format!("companion-audio-profile-{}",uuid::Uuid::new_v4()));fs::create_dir_all(&p).unwrap();p}
#[test]fn production_engine_profile5_reaches_real_receiver_without_recontainering(){
    let raw=include_bytes!("../../fixtures/production-model-audio-profile5.cmb4");assert_eq!(&raw[..4],b"CMB4");
    let count=u32::from_le_bytes(raw[4..8].try_into().unwrap())as usize;let mut at=8usize;let root=root();let index=root.join("sessions.json");
    let mut parts=Vec::new();
    for _ in 0..count {let n=u32::from_le_bytes(raw[at..at+4].try_into().unwrap())as usize;at+=4;let d=Descriptor::decode(&raw[at..at+112]).unwrap();at+=112;let p=raw[at..at+n].to_vec();at+=n;parts.push((d,p));}
    assert_eq!(at,raw.len());assert_eq!(count,3);assert_eq!(parts[0].0.key.device_uid,[1,2,3,4,5,6,7,8,9,10,11,12]);
    let mut r=Receiver::open(&root,&parts[0].0.encode().unwrap()).unwrap();for(d,p)in&parts{r.accept_segment(&d.encode().unwrap(),p).unwrap();}
    let output=r.assemble().unwrap();let before=fs::read(&output).unwrap();let audio=r.receipt.audio.as_ref().unwrap();assert_eq!(audio.samples,6400);
    let t=audio.timeline.as_ref().unwrap();assert_eq!(t.captured_samples,6400);assert_eq!(t.playback_samples(),6400);assert!(t.sample_boundary.unwrap().boundary_complete);
    assert_eq!(t.audio_profile.unwrap().calibration_sha256,[0x83;32]);r.publish(&index,"C8:ED:45:EB:95:B4").unwrap();assert_eq!(r.ack_candidates(&index).unwrap().len(),3);
    drop(r);let mut r=Receiver::open(&root,&parts[0].0.encode().unwrap()).unwrap();r.assemble().unwrap();assert_eq!(fs::read(&output).unwrap(),before);assert!(r.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap().audio_profile.is_some());
    drop(r);fs::remove_dir_all(root).unwrap();
}
#[test]fn audio_profile_survives_real_receiver_save_reopen_publish_and_origin_check(){
    let root=root();let index=root.join("sessions.json");let parts=fixture();let first=parts[0].0.encode().unwrap();
    let mut r=Receiver::open(&root,&first).unwrap();for(d,p)in&parts{r.accept_segment(&d.encode().unwrap(),p).unwrap();}
    let output=r.assemble().unwrap();let original=fs::read(&output).unwrap();let saved=r.receipt.audio.as_ref().unwrap();assert_eq!(saved.samples,6400);
    let profile=saved.timeline.as_ref().unwrap().audio_profile.unwrap();assert_eq!(profile.firmware_source,[0x5a;20]);assert_eq!(profile.delay_q8,128);
    r.publish(&index,"C8:ED:45:EB:95:B4").unwrap();assert_eq!(r.ack_candidates(&index).unwrap().len(),parts.len());assert!(r.receipt.segments.iter().all(|s|!s.acked));
    drop(r);let mut reopened=Receiver::open(&root,&first).unwrap();reopened.assemble().unwrap();assert_eq!(reopened.receipt.audio.as_ref().unwrap().timeline.as_ref().unwrap().audio_profile,Some(profile));
    reopened.receipt.audio.as_mut().unwrap().timeline.as_mut().unwrap().audio_profile.as_mut().unwrap().firmware_source[0]^=1;
    assert!(reopened.assemble().is_err(),"saved JSON cannot relabel immutable original processing");assert_eq!(fs::read(&output).unwrap(),original);
    drop(reopened);fs::remove_dir_all(root).unwrap();
}
#[test]fn audio_profile_change_across_valid_hashed_segments_retains_originals_without_publish(){
    let root=root();let mut parts=fixture();let(d,p)=&mut parts[1];change_identity(d,p);let first=parts[0].0.encode().unwrap();
    let mut r=Receiver::open(&root,&first).unwrap();for(d,p)in&parts{r.accept_segment(&d.encode().unwrap(),p).unwrap();}
    assert!(r.assemble().is_err());assert!(r.receipt.audio.is_none());for(d,p)in&parts{assert_eq!(fs::read(r.payload_path(d)).unwrap(),*p);}
    assert!(r.ack_candidates(&root.join("sessions.json")).is_err());assert!(r.receipt.segments.iter().all(|s|!s.acked));drop(r);fs::remove_dir_all(root).unwrap();
}
