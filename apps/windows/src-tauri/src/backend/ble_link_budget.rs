//! Shared device-perspective link feedback for recording and OTA.
//! Encryption/identity and durable receipts own authorization. This is only
//! measured controller metadata, not an applied speed or over-air proof.
#[derive(Clone,Copy,Debug,PartialEq,Eq,serde::Serialize)]
#[serde(rename_all="camelCase")]
pub(super) struct LinkBudget {
    pub connected:bool, pub encrypted:bool,
    pub tx_phy:Option<u8>, pub rx_phy:Option<u8>,
    pub tx_octets:Option<u16>, pub tx_time_us:Option<u16>,
    pub rx_octets:Option<u16>, pub rx_time_us:Option<u16>,
    pub interval_units:Option<u16>, pub att_mtu:Option<u16>,
}
impl LinkBudget {
    pub(super) fn from_ota_status(b:&[u8])->Result<Option<Self>,String> {
        if b.len()<28 || &b[24..28]!=b"WOC5" {return Ok(None);}
        let bad=||"Invalid current link-budget extension; no measured maxima inferred".to_string();
        if b.len()!=64 || &b[44..48]!=b"BLK1" || b[48]&!15!=0 || b[51]!=0 {return Err(bad());}
        let f=b[48];let connected=f&1!=0;let encrypted=f&2!=0;
        if !connected && (f!=0 || b[49..64].iter().any(|x|*x!=0)) {return Err(bad());}
        let phy=f&8!=0;let dle=f&4!=0;
        if (phy && (!(1..=3).contains(&b[49]) || !(1..=3).contains(&b[50]))) ||
            (!phy && (b[49]!=0 || b[50]!=0)) {return Err(bad());}
        let word=|i|u16::from_le_bytes([b[i],b[i+1]]);
        let (tx,tt,rx,rt)=(word(52),word(54),word(56),word(58));
        if dle {
            if !(27..=251).contains(&tx) || !(27..=251).contains(&rx) ||
                !(328..=17040).contains(&tt) || !(328..=17040).contains(&rt) {return Err(bad());}
        } else if tx!=0 || tt!=0 || rx!=0 || rt!=0 {return Err(bad());}
        let (ci,mtu)=(word(60),word(62));
        if (ci!=0 && !(6..=3200).contains(&ci)) || (mtu!=0 && !(23..=512).contains(&mtu)) {return Err(bad());}
        Ok(Some(Self{connected,encrypted,tx_phy:phy.then_some(b[49]),rx_phy:phy.then_some(b[50]),
            tx_octets:dle.then_some(tx),tx_time_us:dle.then_some(tt),rx_octets:dle.then_some(rx),rx_time_us:dle.then_some(rt),
            interval_units:(ci!=0).then_some(ci),att_mtu:(mtu!=0).then_some(mtu)}))
    }
}
/// Apply the same bounded WinRT buffer admission to old and new frames
/// before allocation; content and BEGIN ownership are still checked later.
pub(super) fn notification_extent(bytes:usize)->Result<(),String> {
    if matches!(bytes,44|64) {Ok(())} else {Err("Invalid durable notification extent".into())}
}
/// One format discriminator owns all durable-notification consumers.
/// Legacy WOC4 remains exact44B; WOC5 must validate its complete64B shape.
pub(super) fn generation_status(b:&[u8])->Result<bool,String> {
    if b.len()==44 && &b[24..28]==b"WOC4" {return Ok(true);}
    if b.len()>=28 && &b[24..28]==b"WOC5" {
        LinkBudget::from_ota_status(b)?;return Ok(true);
    }
    Ok(false)
}
#[cfg(test)] mod tests {
    use super::*;
    fn frame()->Vec<u8>{let mut b=vec![0u8;64];b[24..28].copy_from_slice(b"WOC5");b[44..48].copy_from_slice(b"BLK1");b}
    #[test] fn unknown_is_not_a_fabricated_controller_limit(){
        let b=frame();let s=LinkBudget::from_ota_status(&b).unwrap().unwrap();
        assert!(!s.connected);assert_eq!(s.tx_phy,None);assert_eq!(s.rx_time_us,None);assert_eq!(s.att_mtu,None);
        let mut old=vec![0u8;44];old[24..28].copy_from_slice(b"WOC4");assert_eq!(LinkBudget::from_ota_status(&old).unwrap(),None);assert!(generation_status(&old).unwrap());
    }
    #[test] fn asymmetric_real_events_and_short_time_are_retained(){
        let mut b=frame();b[48]=15;b[49]=2;b[50]=1;
        for (offset,value) in [(52,251u16),(54,340),(56,70),(58,965),(60,6),(62,512)] {b[offset..offset+2].copy_from_slice(&value.to_le_bytes());}
        let s=LinkBudget::from_ota_status(&b).unwrap().unwrap();assert_eq!(s.tx_time_us,Some(340));assert_eq!(s.rx_octets,Some(70));assert_eq!(s.rx_phy,Some(1));assert!(generation_status(&b).unwrap());
        for (i,value) in [(48,31),(49,0),(50,4),(51,1),(53,255),(55,255)] {let mut bad=b.clone();bad[i]=value;assert!(LinkBudget::from_ota_status(&bad).is_err());}
        for len in [44,63,65] {let mut bad=b.clone();bad.resize(len,0);assert!(generation_status(&bad).is_err());}
    }
}

#[cfg(test)] mod extent_tests {
    #[test] fn actual_native_callback_admits_only_exact_old_and_new_bounds(){
        for size in [44,64] {super::notification_extent(size).unwrap();}
        for size in [0,1,43,45,63,65,512,usize::MAX] {assert!(super::notification_extent(size).is_err());}
    }
}


/// Observed receipt metadata, not the instant at which a radio change applied.
/// Existing WOC5 frames only: no ATT reads, preference requests or wire changes.
#[derive(Clone,Debug,serde::Serialize)]
#[serde(rename_all="camelCase")]
pub(super) struct BudgetObservation {
    stage:&'static str, host_unix_us:u64, elapsed_us:u64,
    generation:u32, accepted:u32, expected:u32, state:u8, budget:LinkBudget,
}
#[derive(Clone,Debug,serde::Serialize)]
#[serde(rename_all="camelCase")]
pub(super) struct BudgetHistory {
    frames:u64, known:u64, unknown:u64, invalid:u64, changes:u64, dropped_changes:u64,
    last_frame_kind:&'static str, last_frame_elapsed_us:u64,
    first_known:Option<BudgetObservation>, last_known:Option<BudgetObservation>,
    change_rows:Vec<BudgetObservation>,
}
impl Default for BudgetHistory {
    fn default()->Self {Self{frames:0,known:0,unknown:0,invalid:0,changes:0,dropped_changes:0,
        last_frame_kind:"none",last_frame_elapsed_us:0,first_known:None,last_known:None,
        change_rows:Vec::with_capacity(32)}}
}
impl BudgetHistory {
    pub(super) fn observe(&mut self,stage:&'static str,host_unix_us:u64,elapsed_us:u64,bytes:Option<&[u8]>) {
        let Some(bytes)=bytes else{return;};
        self.frames=self.frames.saturating_add(1);self.last_frame_elapsed_us=elapsed_us;
        // Recording a frame never validates its durable receipt/owner. Keep
        // malformed and old unknown frames visible without changing transport.
        let decoded=if bytes.len()<24 || &bytes[..4]!=b"DOV1" || bytes[4]!=1 {
            Err("invalid status header".to_string())
        } else {LinkBudget::from_ota_status(bytes)};
        let budget=match decoded {
            Ok(Some(value))=>value,
            Ok(None)=>{self.unknown=self.unknown.saturating_add(1);self.last_frame_kind="unknown";return;},
            Err(_)=>{self.invalid=self.invalid.saturating_add(1);self.last_frame_kind="invalid";return;},
        };
        self.known=self.known.saturating_add(1);self.last_frame_kind="known";
        let word=|at|u32::from_le_bytes(bytes[at..at+4].try_into().unwrap());
        let row=BudgetObservation{stage,host_unix_us,elapsed_us,generation:word(40),accepted:word(8),
            expected:word(12),state:bytes[5],budget};
        if self.last_known.as_ref().map(|previous|previous.budget)!=Some(budget) {
            self.changes=self.changes.saturating_add(1);
            if self.change_rows.len()<32 {self.change_rows.push(row.clone());}
            else {self.dropped_changes=self.dropped_changes.saturating_add(1);}
        }
        if self.first_known.is_none(){self.first_known=Some(row.clone());}
        // Still update the last observed value after either bounded log fills.
        // It is a LAST KNOWN observation, never assumed current across a gap.
        self.last_known=Some(row);
    }
}
