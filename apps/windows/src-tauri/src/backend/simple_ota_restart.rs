//! Minimal OTA has no download resume. Retire an incomplete transaction and
//! observe its release before BEGIN; never discard an already retained file.
use denzic_ota_core::{OtaV1Transport,Operation,control_packet,parse_status,STATE_IDLE,STATE_COMPLETE};
use std::time::{Duration,Instant};

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
}
