//! WBA segmented-session discard wire codec. A decoded offer is NOT consent.
use std::convert::TryInto;

pub const BYTES: usize = 96;
pub const PREVIEW: u8 = 1;
pub const CONFIRM: u8 = 2;
pub const CANCEL: u8 = 3;
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Offer { pub request_id:u32,pub generation:u32,pub uid:[u8;12],pub epoch:u64,pub session:u64,
    pub slots:u64,pub samples:u64,pub oldest_id:u32,pub max_id:u32,pub segments:u8,pub anchor_slot:u8,
    pub encoded_bytes:u32,pub reserved_bytes:u32,pub started_unix_s:u32,pub last_index:u32,pub token:[u32;2], wire:[u8;BYTES] }
fn u32le(p:&[u8],i:usize)->u32 { u32::from_le_bytes(p[i..i+4].try_into().unwrap()) }
fn u64le(p:&[u8],i:usize)->u64 { u64::from_le_bytes(p[i..i+8].try_into().unwrap()) }
fn crc(p:&[u8])->u32 {let mut c=u32::MAX;for b in p {c^=u32::from(*b);for _ in 0..8 {c=(c>>1)^((0u32.wrapping_sub(c&1))&0xedb88320);}} !c}
fn finish(p:&mut [u8;BYTES]) {let v=crc(&p[..92]);p[92..].copy_from_slice(&v.to_le_bytes());}
pub fn preview_request(request_id:u32)->Result<[u8;BYTES], &'static str> {
    if request_id==0{return Err("request id is zero")}
    let mut p=[0;BYTES];p[..4].copy_from_slice(b"CDS3");p[4]=PREVIEW;p[8..12].copy_from_slice(&request_id.to_le_bytes());finish(&mut p);Ok(p)
}
pub fn parse_offer(p:&[u8],expected_request:u32)->Result<Offer,&'static str> {
    if p.len()!=BYTES||&p[..4]!=b"CDS3"||p[4]!=PREVIEW||p[5]!=0||u32le(p,8)!=expected_request||expected_request==0||u32le(p,92)!=crc(&p[..92]) {return Err("invalid offer frame")}
    let a=p[6];let n=p[7];let generation=u32le(p,12);let uid:[u8;12]=p[16..28].try_into().unwrap();
    let epoch=u64le(p,28);let session=u64le(p,36);let slots=u64le(p,44);let samples=u64le(p,52);
    let oldest_id=u32le(p,60);let max_id=u32le(p,64);let encoded=u32le(p,68);let reserved=u32le(p,72);
    let started=u32le(p,76);let last=u32le(p,80);let token=[u32le(p,84),u32le(p,88)];
    if a>=64||n==0||n>64||slots&(1u64<<a)==0||slots.count_ones()!=u32::from(n)||generation==0||epoch==0||session==0||
        uid.iter().all(|x|*x==0)||uid.iter().all(|x|*x==255)||samples==0||samples%320!=0||oldest_id==0||max_id<oldest_id||
        encoded==0||reserved==0||reserved%4096!=0||last==u32::MAX||(token[0]==0&&token[1]==0) {return Err("invalid offer fields")}
    Ok(Offer{request_id:expected_request,generation,uid,epoch,session,slots,samples,oldest_id,max_id,segments:n,
        anchor_slot:a,encoded_bytes:encoded,reserved_bytes:reserved,started_unix_s:started,last_index:last,token,wire:p.try_into().unwrap()})
}
impl Offer {
    /// The caller must obtain explicit consent and stay on this encrypted connection.
    pub fn decision(&self,approved:bool,elapsed_ms:u64)->Result<[u8;BYTES],&'static str> {
        if approved&&elapsed_ms>=50_000{return Err("offer expired")}
        let mut p=self.wire;p[4]=if approved{CONFIRM}else{CANCEL};finish(&mut p);Ok(p)
    }
    pub fn validate_response(&self,p:&[u8],operation:u8,status:u8)->Result<(),&'static str> {
        if p.len()!=BYTES||p[4]!=operation||p[5]!=status||u32le(p,92)!=crc(&p[..92]) {return Err("invalid receipt")}
        let mut expected=self.wire;expected[4]=operation;expected[5]=status;finish(&mut expected);
        if p!=expected{return Err("different confirmed recording")};Ok(())
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    const C_FRAME:&str="434453330100000223000000090000000102030405060708090a0b0c070000000000000064000000000000000500000000000000800200000000000001000000030000006c0000000020000040e20100010000007b000000c80100001d569764";
    fn unhex(s:&str)->Vec<u8>{s.as_bytes().chunks_exact(2).map(|x|u8::from_str_radix(std::str::from_utf8(x).unwrap(),16).unwrap()).collect()}
    #[test] fn c_generated_offer_and_exact_confirmation() {
        let p=unhex(C_FRAME);let o=parse_offer(&p,35).unwrap();assert_eq!((o.session,o.slots,o.segments,o.samples),(100,5,2,640));
        let c=o.decision(true,49999).unwrap();assert_eq!(c[4],CONFIRM);o.validate_response(&c,CONFIRM,0).unwrap();
        assert!(o.decision(true,50000).is_err());assert_eq!(o.decision(false,50000).unwrap()[4],CANCEL);
        let mut forged=c;forged[44]^=1;finish(&mut forged);assert!(o.validate_response(&forged,CONFIRM,0).is_err());
    }
    #[test] fn reject_old_and_invalid() {
        let p=unhex(C_FRAME);assert!(parse_offer(&p[..84],35).is_err());assert!(parse_offer(&p,36).is_err());
        let mut p:[u8;BYTES]=p.try_into().unwrap();p[7]=3;finish(&mut p);assert!(parse_offer(&p,35).is_err());
        p[7]=2;p[44]^=1;assert!(parse_offer(&p,35).is_err());assert!(preview_request(0).is_err());
        assert_eq!(preview_request(35).unwrap().len(),96);
    }
}
