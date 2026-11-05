//! Explicit WBA capacity contracts: legacy seven-entry CCP1 and segmented CCQ2.
//! CCQ2 keeps the same48-byte tail and reports allocation geometry, not a host estimate.
use crate::companion_v1::CompanionV1RecordingCapacity;

/// FW801+ commits the WBA segmented START=0 contract. Zero on earlier
/// firmware instead uses a saved device limit and must not be called unlimited.
pub(super) fn supports_unlimited(payload:&[u8])->bool {
    if payload.len()<84 || payload[0]!=1 || &payload[36..40]!=b"CCQ2" {return false;}
    let version=u32::from_le_bytes(payload[4..8].try_into().unwrap());
    version>=0x0001_0421 && parse(payload).is_some_and(|c|c.local_limit_seconds==0)
}

pub(super) fn parse(payload: &[u8]) -> Option<CompanionV1RecordingCapacity> {
    if payload.len()<84 || payload[0]!=1 || u32::from_le_bytes(payload[12..16].try_into().ok()?)!=0x5742_4155
        || !matches!(payload[40],1|3) || payload[41]&1==0 || payload[41]&!7!=0 {return None;}
    let segmented=match &payload[36..40] {b"CCP1"=>false,b"CCQ2"=>true,_=>return None};
    if segmented && payload[40]!=3 {return None;}
    let word=|offset|u32::from_le_bytes(payload[offset..offset+4].try_into().unwrap());
    let (frames,extent)=if segmented {
        let frames=word(68);let extent=word(72);
        if frames==0 || frames>6400 || extent<4096 || extent%4096!=0 || extent>word(48)
            || 12+528+(u64::from(frames)+5)*42 > (u64::from(extent)/256-1)*248 {return None;}
        (Some(frames),Some(extent))
    } else {(None,None)};
    let c=CompanionV1RecordingCapacity {
        layout_version:payload[40],busy:payload[41]&2!=0,confirmed_discard_supported:payload[41]&4!=0,
        used_entries:payload[42],max_entries:payload[43],catalog_generation:word(44),
        data_bytes:word(48),free_bytes:word(52),largest_free_extent:word(56),protected_bytes:word(60),consumed_bytes:word(64),
        bytes_per_second:if segmented{2100}else{word(68)},reserve_headroom:if segmented{4108}else{word(72)},
        segment_frames:frames,segment_extent_bytes:extent,local_limit_seconds:word(76),
        unsynced_entries:payload[80],writing_entries:payload[81],consumed_entries:payload[82],
    };
    if c.max_entries!=(if segmented{64}else{7}) || c.used_entries>c.max_entries
        || c.data_bytes==0 || c.data_bytes>16*1024*1024 || c.data_bytes%4096!=0
        || [c.free_bytes,c.largest_free_extent,c.protected_bytes,c.consumed_bytes].iter().any(|n|*n>c.data_bytes || *n%4096!=0)
        || c.free_bytes.checked_add(c.protected_bytes)?.checked_add(c.consumed_bytes)?!=c.data_bytes
        || c.largest_free_extent>c.free_bytes || c.bytes_per_second!=2100 || !matches!(c.reserve_headroom,4096|4108)
        || ![0,900,1800,3600].contains(&c.local_limit_seconds)
        || c.protected_bytes+c.consumed_bytes<u32::from(c.used_entries)*4096
        || (c.used_entries==0 && c.free_bytes!=c.data_bytes)
        || u16::from(c.unsynced_entries)+u16::from(c.writing_entries)+u16::from(c.consumed_entries)!=u16::from(c.used_entries)
        || c.protected_bytes<(u32::from(c.unsynced_entries)+u32::from(c.writing_entries))*4096
        || c.consumed_bytes<u32::from(c.consumed_entries)*4096 || payload[83]!=0 {return None;}
    Some(c)
}

pub(super) fn check(c:&CompanionV1RecordingCapacity,seconds:u16)->Result<(),String> {
    check_budget(c,seconds,false)
}

/// max_seconds remains the original board safety deadline. A connected owned
/// continuous sync needs only its bounded current+prepared-successor working
/// set at START, not space for its entire future duration. User-paused/blocked
/// sync and the legacy non-segmented contract retain the full offline budget.
pub(super) fn check_start(c:&CompanionV1RecordingCapacity,seconds:u16,
    owned_sync_allowed:bool)->Result<(),String> {
    check_budget(c,seconds,owned_sync_allowed)
}

/// Decode only a correlated optional allocation snapshot. An unrelated
/// notification is ignored; a correlated but malformed response fails closed.
pub(super) fn parse_slots_reply(p:&[u8],uid:&[u8;12],token:u32,generation:u32)->Result<Option<u8>,String> {
    if p.len()<4||&p[..4]!=b"CSN1" {return Ok(None);}
    if p.len()!=32 {return Err("设备录音容量快照长度无效，未开始录音。".into());}
    if u32::from_le_bytes(p[4..8].try_into().unwrap())!=token {return Ok(None);}
    if p[13..16]!=[0,0,0]||p[16..28]!=*uid||
       crc32fast::hash(&p[..28])!=u32::from_le_bytes(p[28..32].try_into().unwrap()) {
        return Err("设备录音容量快照校验失败，未开始录音。".into());
    }
    if u32::from_le_bytes(p[8..12].try_into().unwrap())!=generation {
        return Err("设备录音目录已变化，请重试。".into());
    }
    Ok(Some(p[12]))
}

/// A fresh negotiated device snapshot counts whole independently allocatable
/// extents, not total free bytes. The caller must bind its generation and UID
/// to the protected START; legacy/unknown firmware keeps check_start unchanged.
pub(super) fn check_start_with_slots(c:&CompanionV1RecordingCapacity,seconds:u16,
    owned_sync_allowed:bool,segments:u8)->Result<(),String> {
    if c.busy {return Err("recording preflight: 设备正在录音、回收或升级，请等待结束后重试".into());}
    let (frames,extent)=match(c.segment_frames,c.segment_extent_bytes) {
        (Some(f),Some(e)) if f>0&&e>0=>(f,e),
        _=>return Err("recording preflight: 容量几何不可核对，未开始录音".into()),
    };
    let remaining=c.max_entries.checked_sub(c.used_entries).ok_or("录音目录无效")?;
    if remaining==0 {return Err("recording preflight: 设备录音目录已满，请先同步并回收录音".into());}
    let count=u32::from(segments);
    let lower=(c.largest_free_extent/extent).min(u32::from(remaining));
    let upper=(c.free_bytes/extent).min(u32::from(remaining));
    if count<lower||count>upper {return Err("设备的空闲段数与容量状态不一致，未开始录音。".into());}
    let needed=if seconds==0 {1} else {(u64::from(seconds)*50).div_ceil(u64::from(frames))};
    let needed=if owned_sync_allowed{needed.min(2)}else{needed};
    if needed>u64::from(segments) {return Err(format!("recording preflight: 可用录音段不足以录制完整的 {seconds} 秒，请先同步录音。未开始录音，也未覆盖旧录音。"));}
    Ok(())
}

fn check_budget(c:&CompanionV1RecordingCapacity,seconds:u16,
    owned_sync_allowed:bool)->Result<(),String> {
    if c.busy {return Err("recording preflight: 设备正在录音、回收或升级，请等待结束后重试".into());}
    if c.used_entries>=c.max_entries {return Err("recording preflight: 设备录音目录已满，请先同步并回收录音".into());}
    let wanted=match(c.segment_frames,c.segment_extent_bytes) {
        (Some(frames),Some(extent)) if frames>0 && extent>0 => {
            // A zero-duration request on a verified new device means stop on
            // user request or actual capacity, not a zero-byte recording.
            let slots=if seconds==0 {1} else {(u64::from(seconds)*50).div_ceil(u64::from(frames))};
            let slots=if owned_sync_allowed{slots.min(2)}else{slots};
            if slots>u64::from(c.max_entries-c.used_entries) {
                return Err(format!("recording preflight: 目录剩余槽位不足以录制完整的 {seconds} 秒；约可录 {} 秒，请先同步录音。",available_seconds(c)));
            }
            slots*u64::from(extent)
        },
        (None,None) if seconds==0 =>return Err("设备暂不支持无预设时长录音，请先升级设备。".into()),
        (None,None)=>(u64::from(seconds)*u64::from(c.bytes_per_second)+u64::from(c.reserve_headroom)).div_ceil(4096)*4096,
        _=>return Err("recording preflight: 容量几何不可核对，未开始录音".into()),
    };
    if wanted>u64::from(c.largest_free_extent) {
        if owned_sync_allowed && c.segment_frames.is_some() && c.segment_extent_bytes.is_some() {
            return Err("recording preflight: 设备当前没有足够的连续空间准备录音段，请先同步已有录音；未开始，也未覆盖旧录音。".into());
        }
        return Err(format!("recording preflight: 设备连续可用空间不足以录制完整的 {seconds} 秒；约可录 {} 秒，请先同步录音或缩短时长。未开始录音，也未覆盖旧录音",available_seconds(c)));
    }
    Ok(())
}
pub(super) fn available_seconds(c:&CompanionV1RecordingCapacity)->u32 {
    if c.used_entries>=c.max_entries {return 0;}
    match(c.segment_frames,c.segment_extent_bytes) {
        (Some(frames),Some(extent))if frames>0 && extent>0=>{
            let slots=(c.largest_free_extent/extent).min(u32::from(c.max_entries-c.used_entries));
            ((u64::from(slots)*u64::from(frames))/50) as u32
        },
        (None,None)=>c.largest_free_extent.saturating_sub(c.reserve_headroom)/c.bytes_per_second,
        _=>0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn empty_wire() -> Vec<u8> {
        let mut p=vec![0;84];p[0]=1;p[12..16].copy_from_slice(&0x5742_4155u32.to_le_bytes());
        p[36..40].copy_from_slice(b"CCP1");p[40]=1;p[41]=1;p[43]=7;
        for (at,n) in [(48,8u32*1024*1024-8192),(52,8*1024*1024-8192),
            (56,8*1024*1024-8192),(68,2100),(72,4096),(76,1800)] {
            p[at..at+4].copy_from_slice(&n.to_le_bytes());
        } p
    }
    #[test]
    fn actual_geometry_legacy_and_malformed_are_distinct() {
        let p=empty_wire();let c=parse(&p).unwrap();
        assert_eq!(c.data_bytes,8*1024*1024-8192);assert_eq!(available_seconds(&c),3988);
        assert!(check(&c,3988).is_ok());assert!(check(&c,3989).is_err());
        assert!(parse(&p[..36]).is_none());assert!(parse(&p[..79]).is_none());
        for at in [0,12,36,40,41,43,48,52,56,68,72,76,80,81,82,83] {
            let mut broken=p.clone();broken[at]=255;assert!(parse(&broken).is_none(),"offset {at}");
        }
    }
    #[test]
    fn layout_three_exposes_shared_capacity_and_two_hour_budget() {
        let mut p=empty_wire();p[40]=3;
        for at in [48,52,56] {p[at..at+4].copy_from_slice(&0xEE0000u32.to_le_bytes());}
        let c=parse(&p).unwrap();assert_eq!(c.layout_version,3);
        assert!(check(&c,7200).is_ok());assert!(available_seconds(&c)>7200);
        // Current WBA also reserves the 12-byte COP1 header. Accept its real
        // capacity frame without dropping support for the older 4096 value.
        for at in [48,52,56] {p[at..at+4].copy_from_slice(&0xEFC000u32.to_le_bytes());}
        p[72..76].copy_from_slice(&4108u32.to_le_bytes());
        let current=parse(&p).unwrap();assert_eq!(current.reserve_headroom,4108);
        assert!(check(&current,7200).is_ok());
        p[72..76].copy_from_slice(&4109u32.to_le_bytes());assert!(parse(&p).is_none());
        p[72..76].copy_from_slice(&4108u32.to_le_bytes());
        p[40]=2;assert!(parse(&p).is_none());p[40]=4;assert!(parse(&p).is_none());
    }
    #[test]
    fn fragmentation_directory_and_reclaim_do_not_advertise_free_capacity() {
        let mut c=parse(&empty_wire()).unwrap();c.used_entries=3;c.protected_bytes=16384;
        c.consumed_bytes=8192;c.data_bytes=57344;c.free_bytes=32768;c.largest_free_extent=24576;
        assert!(check(&c,9).is_ok());assert!(check(&c,10).is_err());
        c.busy=true;assert!(check(&c,1).is_err());c.busy=false;c.used_entries=7;
        assert_eq!(available_seconds(&c),0);assert!(check(&c,1).is_err());
    }
    #[test]
    #[ignore = "requires current real C product fixture; host-only cross-language evidence"]
    fn firmware_wire_fixture() {
        let p=std::fs::read(std::env::var("COMPANION_CAPACITY_FIXTURE").unwrap()).unwrap();
        let c=parse(&p).unwrap();assert_eq!(p.len(),84);
        assert_eq!(c.data_bytes,8*1024*1024-8192);assert_eq!(c.used_entries,0);
        assert_eq!(c.free_bytes,c.data_bytes);assert_eq!(c.local_limit_seconds,1800);
        assert!(check(&c,1800).is_ok());assert!(check(&c,7200).is_err());
    }
}

#[cfg(test)]
mod segmented_capacity_tests {
    use super::*;
    fn real_c_status()->Vec<u8>{include_bytes!("recording_capacity/fixtures/ccq2-current-arena.bin").to_vec()}
    #[test]fn unlimited_requires_new_wba_contract_and_one_allocatable_segment(){
        let mut p=real_c_status();p[76..80].copy_from_slice(&0u32.to_le_bytes());
        p[4..8].copy_from_slice(&0x0001_0420u32.to_le_bytes());assert!(!supports_unlimited(&p),"old firmware can also report local limit zero");
        p[4..8].copy_from_slice(&0x0001_0421u32.to_le_bytes());assert!(supports_unlimited(&p));
        let c=parse(&p).unwrap();assert!(check_start(&c,0,false).is_ok());
        let mut insufficient=c.clone();insufficient.largest_free_extent=c.segment_extent_bytes.unwrap()-4096;
        assert!(check_start(&insufficient,0,false).is_err());
        insufficient=c.clone();insufficient.used_entries=insufficient.max_entries;
        assert!(check_start(&insufficient,0,false).is_err());
        insufficient=c.clone();insufficient.busy=true;assert!(check_start(&insufficient,0,false).is_err());
        p[12..16].copy_from_slice(&0x1234u32.to_le_bytes());assert!(!supports_unlimited(&p));
    }
    #[test]fn actual_c_geometry_and64_directory_allow_two_hours_without_raw_byte_estimate(){
        let c=parse(&real_c_status()).unwrap();assert_eq!(c.max_entries,64);
        assert_eq!((c.segment_frames,c.segment_extent_bytes),(Some(6211),Some(270336)));
        assert_eq!(available_seconds(&c),7204);assert!(check(&c,7200).is_ok());
        assert!(check(&c,7204).is_ok());assert!(check(&c,7205).is_err());
    }
    #[test]fn slot_and_fragment_limits_cannot_be_overridden_by_large_total_free_bytes(){
        let mut p=real_c_status();p[42]=63;p[80]=63;
        let data=15695872u32;let protected=63*4096u32;
        for(at,n)in[(52,data-protected),(56,data-protected),(60,protected)]{p[at..at+4].copy_from_slice(&n.to_le_bytes());}
        let c=parse(&p).unwrap();assert_eq!(available_seconds(&c),124);
        assert!(check(&c,124).is_ok());assert!(check(&c,125).is_err());
        p[56..60].copy_from_slice(&266240u32.to_le_bytes());let c=parse(&p).unwrap();
        assert_eq!(available_seconds(&c),0);assert!(check(&c,1).is_err());
    }
    #[test]fn unknown_or_corrupt_geometry_is_not_legacy_fallback(){
        for at in [68usize,72]{let mut p=real_c_status();p[at..at+4].copy_from_slice(&u32::MAX.to_le_bytes());assert!(parse(&p).is_none());}
        let mut p=real_c_status();p[43]=7;assert!(parse(&p).is_none());
        let mut p=real_c_status();p[40]=1;assert!(parse(&p).is_none());
        let mut p=real_c_status();p[36..40].copy_from_slice(b"CCP1");assert!(parse(&p).is_none(),"old64 report is not a seven-slot byte contract");
    }
}

#[cfg(test)]
mod rolling_start_tests {
    use super::*;
    fn segmented()->CompanionV1RecordingCapacity {
        parse(include_bytes!("recording_capacity/fixtures/ccq2-current-arena.bin")).unwrap()
    }
    #[test]
    fn three_hour_start_uses_bounded_working_set_only_when_owned_sync_allowed() {
        let c=segmented();assert_eq!(available_seconds(&c),7204);
        assert!(check(&c,10800).is_err(),"full offline duration remains impossible");
        assert!(check_start(&c,10800,false).is_err(),"paused/blocked sync retains offline budget");
        assert!(check_start(&c,10800,true).is_ok(),"a rolling recording may outlive its local arena");
        assert!(check_start(&c,u16::MAX,true).is_ok());
    }
    #[test]
    fn long_start_requires_current_and_prepared_successor_not_just_one_slot() {
        let mut c=segmented();let extent=c.segment_extent_bytes.unwrap();
        c.used_entries=62;c.largest_free_extent=2*extent;
        assert!(check_start(&c,10800,true).is_ok());
        c.used_entries=63;assert!(check_start(&c,10800,true).is_err());
        assert!(check_start(&c,60,true).is_ok(),"short recording needs one reserved segment");
        c.used_entries=62;c.largest_free_extent=extent;assert!(check_start(&c,10800,true).is_err());
        c.largest_free_extent=2*extent;c.busy=true;assert!(check_start(&c,10800,true).is_err());
    }
    #[test]
    fn legacy_and_malformed_geometry_never_gain_a_rolling_budget() {
        let mut c=segmented();c.segment_frames=None;c.segment_extent_bytes=None;
        assert!(check_start(&c,10800,true).is_err());
        c.segment_frames=Some(6211);assert!(check_start(&c,60,true).is_err());
    }
}

#[cfg(test)]
mod fragmented_slots_tests {
    use super::*;
    #[test]
    fn actual_device_model_response_is_generation_and_identity_bound() {
        let p=include_bytes!("recording_capacity/fixtures/csn1-fragmented.bin");
        let uid:[u8;12]=p[16..28].try_into().unwrap();
        let generation=u32::from_le_bytes(p[8..12].try_into().unwrap());
        assert_eq!(parse_slots_reply(p,&uid,901,generation).unwrap(),Some(2));
        assert_eq!(parse_slots_reply(p,&uid,902,generation).unwrap(),None);
        assert!(parse_slots_reply(p,&uid,901,generation.wrapping_add(1)).is_err());
        let mut bad=*p;bad[16]^=1;assert!(parse_slots_reply(&bad,&uid,901,generation).is_err());
        let mut bad=*p;bad[12]^=1;assert!(parse_slots_reply(&bad,&uid,901,generation).is_err());
        let mut bad=*p;bad[13]=1;let crc=crc32fast::hash(&bad[..28]);bad[28..].copy_from_slice(&crc.to_le_bytes());
        assert!(parse_slots_reply(&bad,&uid,901,generation).is_err());
        assert!(parse_slots_reply(&p[..7],&uid,901,generation).is_err());
    }
    #[test]
    fn whole_gaps_can_admit_but_total_bytes_and_false_counts_cannot() {
        let c=CompanionV1RecordingCapacity{layout_version:3,busy:false,confirmed_discard_supported:false,
            used_entries:1,max_entries:64,catalog_generation:1,data_bytes:811008,free_bytes:540672,
            largest_free_extent:270336,protected_bytes:270336,consumed_bytes:0,bytes_per_second:2100,
            reserve_headroom:4108,segment_frames:Some(6209),segment_extent_bytes:Some(270336),
            local_limit_seconds:1800,unsynced_entries:1,writing_entries:0,consumed_entries:0};
        assert!(check_start(&c,200,false).is_err());assert!(check_start(&c,200,true).is_err());
        assert!(check_start_with_slots(&c,200,false,2).is_ok());
        assert!(check_start_with_slots(&c,200,true,2).is_ok());
        for count in [0,1,3,64] {assert!(check_start_with_slots(&c,200,false,count).is_err());}
        let mut busy=c.clone();busy.busy=true;assert!(check_start_with_slots(&busy,200,false,2).is_err());
        let mut full=c.clone();full.used_entries=64;assert!(check_start_with_slots(&full,0,false,0).is_err());
    }
}
