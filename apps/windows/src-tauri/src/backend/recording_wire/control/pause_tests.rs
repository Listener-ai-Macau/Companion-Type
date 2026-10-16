use super::*;
use super::super::u16le;

fn capability(flags:u32)->Vec<u8> {
    let mut s=vec![0;116];s[0]=1;
    s[12..16].copy_from_slice(&0x5742_4155u32.to_le_bytes());
    for (i,b) in s[20..32].iter_mut().enumerate(){*b=(i+1) as u8;}
    let p=&mut s[84..];p[..4].copy_from_slice(b"CRV2");
    p[4..6].copy_from_slice(&2u16.to_le_bytes());p[6..8].copy_from_slice(&32u16.to_le_bytes());
    p[8..12].copy_from_slice(&flags.to_le_bytes());p[12..20].copy_from_slice(&7u64.to_le_bytes());
    p[20..22].copy_from_slice(&64u16.to_le_bytes());p[22..24].copy_from_slice(&1024u16.to_le_bytes());
    p[24..26].copy_from_slice(&248u16.to_le_bytes());
    let crc=crc32fast::hash(&p[..28]);p[28..].copy_from_slice(&crc.to_le_bytes());s
}
fn status_crc(p:&mut [u8]) {
    let crc=crc32fast::hash(&p[..76]);p[76..80].copy_from_slice(&crc.to_le_bytes());
}

#[test]
fn actual_c_controls_match_type_and_only_stable_exact_reply_confirms() {
    // Real C product/coordinator/Opus SOFTWARE model, exported at transition
    // boundaries. This is not physical microphone/radio/runtime/GUI evidence.
    let golden=include_bytes!("../../cop1/tests/engine-pause-control.cpc3");
    assert_eq!(&golden[..4],b"CPC3");let count=u32le(golden,4) as usize;
    assert_eq!(count,14);assert_eq!(golden.len(),8+count*137);
    let peer=PausePeer::from_status(&capability(127)).unwrap().unwrap();
    let mut transitions=[0;3];let mut stable_pauses=0;let mut finalized=0;
    for vector in golden[8..].chunks_exact(137) {
        let request=&vector[..56];let raw=&vector[56..136];
        let decoded=PauseStatus::decode(raw).unwrap();let key=decoded.key.as_ref().unwrap();
        let command=request[5];let id=u32le(request,36);let sequence=u32le(request,48);
        assert_eq!(peer.request(if command==1{None}else{Some(key)},command,id,
            u32le(request,40),u16le(request,44),sequence,request[7]==1).unwrap().as_slice(),request);
        assert_eq!(status(raw).unwrap().as_ref(),Some(key));
        assert_eq!(decoded.confirms(key,command,id,sequence),vector[136]==1);
        let mut wrong=key.clone();wrong.session_id+=1;
        assert!(!decoded.confirms(&wrong,command,id,sequence));
        assert!(!decoded.confirms(key,command,id+1,sequence));
        assert!(!decoded.confirms(key,command,id,sequence+1));
        if (4..=6).contains(&decoded.state){
            transitions[(decoded.state-4) as usize]+=1;assert_eq!(vector[136],0);
        }
        if decoded.state==3&&vector[136]==1{stable_pauses+=1;}
        if decoded.state==2&&vector[136]==1{finalized+=1;}
        let mut corrupt=raw.to_vec();corrupt[48]^=1;
        assert!(PauseStatus::decode(&corrupt).is_err());
        corrupt=raw.to_vec();corrupt[70]=1;status_crc(&mut corrupt);
        assert!(PauseStatus::decode(&corrupt).is_err());
        corrupt=raw.to_vec();corrupt[32..44].fill(0);status_crc(&mut corrupt);
        assert!(PauseStatus::decode(&corrupt).is_err());
    }
    assert!(transitions.iter().all(|count|*count>0));assert_eq!(stable_pauses,3);assert_eq!(finalized,2);
}

#[test]
fn pause_requires_explicit_coherent_capability_and_scoped_nonzero_sequence() {
    assert!(PausePeer::from_status(&[0;84]).unwrap().is_none());
    assert!(PausePeer::from_status(&capability(63)).unwrap().is_none());
    for flags in [71,79,87,255] {assert!(PausePeer::from_status(&capability(flags)).is_err());}
    let peer=PausePeer::from_status(&capability(127)).unwrap().unwrap();
    let key=SessionKey{device_uid:peer.peer.uid,format_epoch:7,session_id:0x100000003};
    assert!(peer.request(Some(&key),4,110,101,0,1,false).is_ok());
    assert!(peer.request(None,4,110,101,0,1,false).is_err());
    assert!(peer.request(Some(&key),4,110,101,0,0,false).is_err());
    assert!(peer.request(Some(&key),4,110,101,0,u32::MAX,false).is_err());
    assert!(peer.request(Some(&key),5,120,101,0,u32::MAX,false).is_err());
    assert!(peer.request(Some(&key),4,110,101,0,1,true).is_err());
    assert!(peer.request(Some(&key),4,110,101,600,1,false).is_err());
    assert!(peer.request(None,1,101,102,600,0,true).is_err());
    assert!(peer.request(None,1,101,101,600,1,true).is_err());
    for which in 0..3 {
        let mut wrong=key.clone();match which {0=>wrong.device_uid[0]^=1,1=>wrong.format_epoch+=1,_=>wrong.session_id=0};
        assert!(peer.request(Some(&wrong),4,110,101,0,1,false).is_err());
    }
}

#[test]
fn local_origin_extension_requires_exact_reserved_layout_and_is_never_remote_confirmation() {
    let mut raw=include_bytes!("../../cop1/tests/engine-pause-control.cpc3")[64..144].to_vec();
    let start=u32le(&raw,8);raw[66]=1;raw[67..71].copy_from_slice(&start.to_le_bytes());status_crc(&mut raw);
    let status=PauseStatus::decode(&raw).unwrap();assert_eq!(status.local_start,Some(start));
    assert!(!status.confirms(status.key.as_ref().unwrap(),1,start,0));
    for invalid in 0..7 {
        let mut bad=raw.clone();match invalid {0=>bad[66]=2,1=>bad[67..71].fill(0),
            2=>bad[71]=1,3=>bad[65]=2,4=>bad[64]=0,5=>bad[60]=1,_=>bad[66]=0};
        status_crc(&mut bad);assert!(PauseStatus::decode(&bad).is_err(),"bad local origin {invalid}");
    }
}
