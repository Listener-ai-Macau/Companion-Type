//! Protected WBA logical-recorder controls. Never infer a session from a
//! physical segment ID or enable this extension without CRV2 capability bit 8.
use super::{fail, u32le, u64le, SessionKey, transport::Peer};

pub(crate) fn status(payload: &[u8]) -> Result<Option<SessionKey>, String> {
    if payload.len() == 28 { return Ok(None); }
    if payload.len()==80 {return Ok(PauseStatus::decode(payload)?.key);}
    if payload.len() != 64 || &payload[28..32] != b"CMS2"
        || crc32fast::hash(&payload[..60]) != u32le(payload,60) {
        return Err(fail("invalid logical meeting status length/schema/CRC"));
    }
    let uid = payload[32..44].try_into().unwrap();
    let epoch = u64le(payload,44);
    let session = u64le(payload,52);
    if uid == [0;12] || uid == [255;12] || epoch == 0 {
        return Err(fail("empty logical meeting identity"));
    }
    Ok((session != 0).then_some(SessionKey {device_uid: uid, format_epoch: epoch, session_id: session}))
}

/// This type can only be constructed from a CRC-checked CRV2 status with the
/// explicit pause-control bit. No legacy peer is silently upgraded to CMC3.
pub(crate) struct PausePeer {peer:Peer}
impl PausePeer {
    pub(crate) fn identity(&self) -> ([u8;12], u64) { (self.peer.uid, self.peer.epoch) }
    pub(crate) fn from_verified_peer(peer:&Peer)->Result<Self,String> {
        if !peer.pause_control || !peer.logical_control || !peer.growing_tail {
            return Err(fail("verified recorder has no explicit pause capability"));
        }
        Ok(Self{peer:peer.clone()})
    }
    pub(crate) fn from_status(bytes:&[u8])->Result<Option<Self>,String> {
        let Some(peer)=Peer::from_status(bytes)? else{return Ok(None)};
        Ok((u32le(bytes,92)&64!=0).then_some(Self{peer}))
    }
    pub(crate) fn request(&self,key:Option<&SessionKey>,command:u8,request:u32,start:u32,
        max_seconds:u16,sequence:u32,timeline:bool)->Result<[u8;56],String> {
        if !(1..=5).contains(&command)||request==0||start==0||
            (command==1 && (key.is_some()||start!=request||sequence!=0))||
            (command!=1 && (timeline||max_seconds!=0||sequence==0||key.is_none_or(|key|
                key.device_uid!=self.peer.uid||key.format_epoch!=self.peer.epoch||key.session_id==0)))||
            (matches!(command,4|5)&&sequence==u32::MAX) {
            return Err(fail("pause command is not bound to the exact recorder/session/sequence"));
        }
        let mut p=[0;56];p[..4].copy_from_slice(b"CMC3");p[4]=3;p[5]=command;p[6]=2;p[7]=u8::from(timeline);
        p[8..20].copy_from_slice(&self.peer.uid);p[20..28].copy_from_slice(&self.peer.epoch.to_le_bytes());
        p[28..36].copy_from_slice(&key.map_or(0,|key|key.session_id).to_le_bytes());
        p[36..40].copy_from_slice(&request.to_le_bytes());p[40..44].copy_from_slice(&start.to_le_bytes());
        p[44..46].copy_from_slice(&max_seconds.to_le_bytes());p[48..52].copy_from_slice(&sequence.to_le_bytes());
        let crc=crc32fast::hash(&p[..52]);p[52..56].copy_from_slice(&crc.to_le_bytes());Ok(p)
    }
}

#[derive(Clone, Debug)]
pub(crate) struct PauseStatus {
    pub(crate) device_uid:[u8;12],pub(crate) format_epoch:u64,
    pub(crate) key:Option<SessionKey>,pub(crate) state:u8,pub(crate) last_error:u8,
    pub(crate) request:u32,pub(crate) sequence:u32,pub(crate) command:u8,pub(crate) timeline:bool,
    /// Present only for a device-local action. This is never a remote ACK.
    pub(crate) local_start:Option<u32>,
    pub(crate) end_reason:Option<crate::companion_v1::CompanionV1RecordingEndReason>,
}
impl PauseStatus {
    pub(crate) fn decode(p:&[u8])->Result<Self,String> {
        if p.len()!=80||p[0]!=1||p[1]>6||&p[28..32]!=b"CMS3"||p[64]>1||p[65]>5||
            p[66]>1 || p[71]>5 || p[72..76].iter().any(|b|*b!=0) ||
            (p[71]!=0 && (u64le(p,52)==0 || !matches!(p[1],2|6))) ||
            (p[66]==0 && p[67..71].iter().any(|b|*b!=0)) ||
            crc32fast::hash(&p[..76])!=u32le(p,76) {
            return Err(fail("invalid pause recorder status length/schema/CRC"));
        }
        let uid=p[32..44].try_into().unwrap();let epoch=u64le(p,44);let session=u64le(p,52);
        if uid==[0;12]||uid==[255;12]||epoch==0{return Err(fail("empty pause recorder identity"));}
        let local_start=(p[66]==1).then(||u32le(p,67));
        if local_start.is_some_and(|start|start==0 || session==0 || p[64]!=1 ||
            !matches!(p[65],1|4|5) || u32le(p,8)==0 ||
            ((u32le(p,60)==0)!=(p[65]==1)) ||
            (p[65]==1 && u32le(p,8)!=start)) {
            return Err(fail("invalid local recorder origin/start/sequence"));
        }
        Ok(Self{device_uid:uid,format_epoch:epoch,key:(session!=0).then_some(SessionKey{device_uid:uid,format_epoch:epoch,session_id:session}),
            state:p[1],last_error:p[2],request:u32le(p,8),sequence:u32le(p,60),command:p[65],timeline:p[64]==1,local_start,
            end_reason:crate::companion_v1::CompanionV1RecordingEndReason::from_code(p[71])?})
    }
    pub(crate) fn confirms(&self,key:&SessionKey,command:u8,request:u32,sequence:u32)->bool {
        let state=match command{1|5=>1,2|3=>2,4=>3,_=>return false};
        self.local_start.is_none()&&self.key.as_ref()==Some(key)&&self.last_error==0&&self.command==command&&self.request==request&&
            self.sequence==sequence&&self.state==state&&(!matches!(command,4|5)||self.timeline)
    }
}

pub(crate) fn request(peer: &Peer, key: Option<&SessionKey>, command: u8, request: u32,
    start: u32, max_seconds: u16) -> Result<[u8;52], String> {
    if !peer.logical_control || !(1..=3).contains(&command) || request == 0 || start == 0
        || (command == 1 && (key.is_some() || start != request))
        || (command != 1 && key.is_none_or(|k| k.device_uid != peer.uid ||
            k.format_epoch != peer.epoch || k.session_id == 0)) {
        return Err(fail("control is not bound to the negotiated logical recorder"));
    }
    let mut p = [0;52]; p[..4].copy_from_slice(b"CMC2");p[4]=2;p[5]=command;p[6]=2;
    p[8..20].copy_from_slice(&peer.uid);p[20..28].copy_from_slice(&peer.epoch.to_le_bytes());
    p[28..36].copy_from_slice(&key.map_or(0, |k| k.session_id).to_le_bytes());
    p[36..40].copy_from_slice(&request.to_le_bytes());p[40..44].copy_from_slice(&start.to_le_bytes());
    p[44..46].copy_from_slice(&max_seconds.to_le_bytes());
    let crc=crc32fast::hash(&p[..48]);p[48..52].copy_from_slice(&crc.to_le_bytes());Ok(p)
}

#[cfg(test)]
mod pause_tests;
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wba_logical_control_wire_matches_full_u64_key_and_rejects_wrong_scope() {
        let peer=Peer{uid:[0x35;12],epoch:0xc055aa0710123456,capacity:64,max_value_bytes:248,logical_control:true,growing_tail:false,pause_control:false,batch_interval:false};
        let key=SessionKey{device_uid:peer.uid,format_epoch:peer.epoch,session_id:0xf000000000000023};
        let wire=request(&peer,None,1,101,101,7200).unwrap();
        assert_eq!(&wire[..8],b"CMC2\x02\x01\x02\x00");
        assert_eq!(u64le(&wire,20),peer.epoch);assert_eq!(u64le(&wire,28),0);
        assert_eq!(u32le(&wire,36),101);assert_eq!(&wire[44..48],&[0x20,0x1c,0,0]);
        let wire=request(&peer,Some(&key),2,202,101,0).unwrap();
        assert_eq!(u64le(&wire,28),key.session_id);assert_eq!(u32le(&wire,40),101);
        assert_eq!(u32le(&wire,48),crc32fast::hash(&wire[..48]));
        assert!(request(&peer,None,2,202,101,0).is_err());
        assert!(request(&peer,Some(&key),1,101,101,0).is_err());
        let mut wrong=key.clone();wrong.format_epoch+=1;
        assert!(request(&peer,Some(&wrong),2,202,101,0).is_err());
        wrong=key.clone();wrong.device_uid[0]^=1;
        assert!(request(&peer,Some(&wrong),2,202,101,0).is_err());
        let public=key.public_key();let serialized=serde_json::to_vec(&public).unwrap();
        let restored:crate::companion_v1::CompanionV1RecordingKey=serde_json::from_slice(&serialized).unwrap();
        assert_eq!(SessionKey::from_public(&restored).unwrap(),key);
    }
    #[test]
    fn wba_logical_status_rejects_truncation_corrupt_key_and_crc() {
        assert!(status(&[0;28]).unwrap().is_none());
        let mut wire=[0;64];wire[28..32].copy_from_slice(b"CMS2");wire[32..44].fill(0x35);
        wire[44..52].copy_from_slice(&7u64.to_le_bytes());wire[52..60].copy_from_slice(&23u64.to_le_bytes());
        let crc=crc32fast::hash(&wire[..60]);wire[60..].copy_from_slice(&crc.to_le_bytes());
        let key=status(&wire).unwrap().unwrap();assert_eq!(key.session_id,23);
        assert!(status(&wire[..63]).is_err());wire[52]^=1;assert!(status(&wire).is_err());
        wire[32..44].fill(0);let crc=crc32fast::hash(&wire[..60]);wire[60..].copy_from_slice(&crc.to_le_bytes());
        assert!(status(&wire).is_err());
    }
}
