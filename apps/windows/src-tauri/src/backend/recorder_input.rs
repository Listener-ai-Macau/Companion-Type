//! CIN1 shared with normal firmware788 and the Mac RecorderWire implementation.
//! These events describe physical input; this host never synthesizes START.
use super::recording_wire::transport::Peer;
use serde::Serialize;

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct InputStatus {
    pub result: u8,
    pub mode: u8,
    pub flags: u8,
    pub options: u8,
    pub feedback: u8,
    pub request: u32,
    pub sequence: u32,
    pub event_ms: u32,
    pub events: u16,
    pub token: u32,
    pub session: u64,
    pub bookmark: u32,
}
impl InputStatus {
    pub fn parse(p: &[u8], peer: &Peer) -> Result<Self, String> {
        if p.len() != 64
            || &p[..4] != b"CIN1"
            || p[4] != 1
            || p[6] > 3
            || p[40..52] != peer.uid
            || u64::from_le_bytes(p[52..60].try_into().unwrap()) != peer.epoch
            || crc32fast::hash(&p[..60]) != u32::from_le_bytes(p[60..64].try_into().unwrap())
        {
            return Err("设备交互消息来源或校验不匹配。".into());
        }
        Ok(Self {
            result: p[5],
            mode: p[6],
            flags: p[7],
            options: p[22],
            feedback: p[23],
            request: u32::from_le_bytes(p[8..12].try_into().unwrap()),
            sequence: u32::from_le_bytes(p[12..16].try_into().unwrap()),
            event_ms: u32::from_le_bytes(p[16..20].try_into().unwrap()),
            events: u16::from_le_bytes(p[20..22].try_into().unwrap()),
            token: u32::from_le_bytes(p[24..28].try_into().unwrap()),
            session: u64::from_le_bytes(p[28..36].try_into().unwrap()),
            bookmark: u32::from_le_bytes(p[36..40].try_into().unwrap()),
        })
    }
}
pub(crate) fn request(peer: &Peer, mode: u8, nonce: u32) -> Result<[u8; 36], String> {
    encode_request(peer, 1, mode, 0, nonce)
}
pub(crate) fn pointer_request(peer:&Peer,nonce:u32)->Result<[u8;36],String>{encode_request(peer,1,3,8,nonce)}
pub(crate) fn pointer_request_options(peer:&Peer,nonce:u32,options:u8)->Result<[u8;36],String>{
    if !matches!(options,8|24|40|72|200){return Err("鼠标模式参数无效。".into());}
    encode_request(peer,1,3,options,nonce)
}
pub(crate) fn pointer_ack(peer:&Peer,sequence:u32)->Result<[u8;36],String>{encode_request(peer,2,0,0,sequence)}

pub(crate) fn query(peer: &Peer, nonce: u32) -> Result<[u8; 36], String> {
    encode_request(peer, 0, 0, 0, nonce)
}

fn encode_request(peer: &Peer, operation: u8, mode: u8, options:u8, nonce: u32) -> Result<[u8; 36], String> {
    if (mode > 1 && mode != 3) || nonce == 0 {
        return Err("电脑输入模式请求无效。".into());
    }
    let mut p = [0u8; 36];
    p[..4].copy_from_slice(b"CIN1");
    p[4] = 1;
    p[5] = operation;
    p[6] = mode;
    p[7] = options;
    p[8..12].copy_from_slice(&nonce.to_le_bytes());
    p[12..24].copy_from_slice(&peer.uid);
    p[24..32].copy_from_slice(&peer.epoch.to_le_bytes());
    let crc = crc32fast::hash(&p[..32]);
    p[32..].copy_from_slice(&crc.to_le_bytes());
    Ok(p)
}
