//! Minimal OTA has no download resume. Retire an incomplete transaction and
//! observe its release before BEGIN; never discard an already retained file.
use denzic_ota_core::{OtaV1Transport,Operation,control_packet,parse_status,STATE_IDLE,STATE_COMPLETE};
use std::time::{Duration,Instant};

/// Windows can report ERROR_CANCELLED as a numeric HRESULT without spelling
/// out "cancelled". This only permits a protected exact receipt read; it
/// never proves that the packet committed or that a retry is authorized.
pub(super) fn ambiguous_write_completion(error:&str)->bool {
    let lower=error.to_ascii_lowercase();
    lower.contains("timed out") || lower.contains("timeout") || lower.contains("canceled")
        || lower.contains("cancelled") || lower.contains("hresult(0x800704c7)")
}

/// A timed-out ATT write is ambiguous. Only this same admitted file's exact
/// device receipt may complete the packet or allow ONE identical retry.
pub(super) fn acknowledged_write_receipt(packet:&[u8],file_bytes:u32,bytes:&[u8])->Result<bool,String> {
    super::ota_flow::WbaFlow::from_simple_status(bytes,false)?;
    if packet.len()<=4 {return Err("升级数据包缺少有效载荷。".into());}
    let offset=u32::from_le_bytes(packet[..4].try_into().unwrap());
    let end=offset.checked_add(u32::try_from(packet.len()-4).map_err(|_|"升级包长度溢出")?)
        .filter(|n|*n<=file_bytes).ok_or("升级数据范围超出本次文件。")?;
    let status=parse_status(bytes)?;
    if status.state!=denzic_ota_core::STATE_RECEIVING || status.last_error!=0 || status.expected_size!=file_bytes {
        return Err("设备未确认本次文件仍可继续，保留原写入失败。".into());
    }
    if status.bytes_written==end {return Ok(true);}
    if status.bytes_written==offset {return Ok(false);}
    Err("设备接收位置不属于本次单包，未猜测写入完成。".into())
}

pub(super) fn prepare_fresh_download<T:OtaV1Transport>(transport:&mut T,initial:&[u8],
    mut readiness:impl FnMut()->Result<u16,String>)->Result<(),String> {
    let status=parse_status(initial)?;
    if status.state==STATE_IDLE && status.last_error==0 && status.bytes_written==0 && status.expected_size==0 {return Ok(());}
    if status.state==STATE_COMPLETE {
        return Err("设备已保留完整升级包，正在等待安装；未丢弃完整包或另开下载。".into());
    }
    transport.write_control(&control_packet(Operation::Abort,0,0,0,0))?;
    let deadline=Instant::now()+Duration::from_secs(15);
    loop {
        let bytes=transport.read_status()?;let status=parse_status(&bytes)?;
        if bytes[24..]!=initial[24..] {return Err("设备升级能力在重新开始时改变，未发送新文件。".into());}
        if status.state==STATE_COMPLETE {
            return Err("设备已经保留完整升级包，未继续重新下载。".into());
        }
        if status.state==STATE_IDLE && status.last_error==0 && status.bytes_written==0 && status.expected_size==0 {
            let blockers=readiness()?;
            if blockers==0 {
                eprintln!("[companion-ota] fresh_download previous_aborted=1 accepted=0 expected=0 readiness=0");
                return Ok(());
            }
            // The released dynamic-pool capacity view may need foreground
            // work. Power/storage faults never become a busy retry or bypass.
            if blockers&!2!=0 {return Err(format!("旧升级已结束，但设备升级条件未满足（阻塞{blockers}），尚未发送新文件。"));}
        }
        if Instant::now()>=deadline {return Err("尚未确认旧下载及动态空间已释放；没有发送新文件，请查看设备状态。".into());}
        std::thread::sleep(Duration::from_millis(50));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::VecDeque;
    #[test]
    fn actual_windows_cancel_hresult_requires_receipt_instead_of_immediate_abort() {
        assert!(ambiguous_write_completion("BLE Companion OTA data write async error: Some(HRESULT(0x800704C7))"));
        assert!(ambiguous_write_completion("OTA data write timed out"));
        for fatal in ["ATT access denied", "HRESULT(0x80070005)", "CRC mismatch", "device rejected manifest", "HRESULT(0x800704C8)"] {
            assert!(!ambiguous_write_completion(fatal),"{fatal}");
        }
    }
    fn status(state:u8,accepted:u32,total:u32)->Vec<u8> {
        let mut p=vec![0u8;24];p[..4].copy_from_slice(b"DOV1");p[4]=1;p[5]=state;
        p[8..12].copy_from_slice(&accepted.to_le_bytes());p[12..16].copy_from_slice(&total.to_le_bytes());p
    }
    struct Peer {reads:VecDeque<Vec<u8>>,controls:Vec<[u8;20]>}
    impl OtaV1Transport for Peer {
        fn write_control(&mut self,p:&[u8;20])->Result<(),String>{self.controls.push(*p);Ok(())}
        fn write_data(&mut self,_:&[u8])->Result<(),String>{panic!("fresh admission must not send file data")}
        fn read_status(&mut self)->Result<Vec<u8>,String>{self.reads.pop_front().ok_or("no scripted status".into())}
    }
    #[test]
    fn interrupted_file_requires_zero_receipt_and_released_capacity_before_new_data() {
        let partial=status(denzic_ota_core::STATE_RECEIVING,69360,1338004);
        let mut peer=Peer{reads:VecDeque::from([partial.clone(),status(STATE_IDLE,0,0),status(STATE_IDLE,0,0)]),controls:vec![]};
        let mut views=VecDeque::from([2,0]);
        prepare_fresh_download(&mut peer,&partial,||Ok(views.pop_front().unwrap())).unwrap();
        assert_eq!(peer.controls,[control_packet(Operation::Abort,0,0,0,0)]);
        assert!(peer.reads.is_empty()&&views.is_empty());
    }
    #[test]
    fn complete_package_is_retained_and_power_or_transport_failure_cannot_authorize_begin() {
        let mut peer=Peer{reads:VecDeque::new(),controls:vec![]};
        assert!(prepare_fresh_download(&mut peer,&status(STATE_COMPLETE,100,100),||Ok(0)).is_err());
        assert!(peer.controls.is_empty());
        for blockers in [1,4,8,16] {
            let mut peer=Peer{reads:VecDeque::from([status(STATE_IDLE,0,0)]),controls:vec![]};
            assert!(prepare_fresh_download(&mut peer,&status(denzic_ota_core::STATE_RECEIVING,10,100),||Ok(blockers)).is_err());
        }
        let mut peer=Peer{reads:VecDeque::new(),controls:vec![]};
        assert!(prepare_fresh_download(&mut peer,&status(denzic_ota_core::STATE_RECEIVING,10,100),||Ok(0)).is_err());
        let mut error=status(STATE_IDLE,0,0);error[6]=6;
        let mut peer=Peer{reads:VecDeque::from([error.clone()]),controls:vec![]};
        assert!(prepare_fresh_download(&mut peer,&error,||panic!("a stale idle error cannot authorize a fresh file")).is_err());
    }
    #[test]
    fn ambiguous_ack_only_accepts_exact_same_file_commit_or_identical_retry_offset() {
        let packet=[10,0,0,0,1,2,3,4];
        let receipt=|accepted,total,state,error| {
            let mut p=status(state,accepted,total);p[6]=error;
            p.extend_from_slice(b"WOC2");p.extend_from_slice(&240u16.to_le_bytes());
            p.extend_from_slice(&244u16.to_le_bytes());p.extend_from_slice(&16u16.to_le_bytes());p.extend_from_slice(&5u16.to_le_bytes());p
        };
        assert!(acknowledged_write_receipt(&packet,100,&receipt(14,100,denzic_ota_core::STATE_RECEIVING,0)).unwrap());
        assert!(!acknowledged_write_receipt(&packet,100,&receipt(10,100,denzic_ota_core::STATE_RECEIVING,0)).unwrap());
        for p in [receipt(14,101,2,0),receipt(13,100,2,0),receipt(15,100,2,0),
            receipt(14,100,denzic_ota_core::STATE_COMPLETE,0),receipt(14,100,2,5),receipt(14,100,0,0)] {
            assert!(acknowledged_write_receipt(&packet,100,&p).is_err());
        }
        assert!(acknowledged_write_receipt(&packet,13,&receipt(14,100,2,0)).is_err());
    }
}
