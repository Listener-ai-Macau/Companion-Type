use std::sync::{Arc,atomic::{AtomicUsize,AtomicI32,Ordering}};
use windows::Foundation::{IAsyncOperation,IAsyncInfo,IAsyncInfo_Impl,IAsyncOperation_Impl,AsyncOperationCompletedHandler,AsyncStatus};
use windows::Devices::Bluetooth::GenericAttributeProfile::GattCommunicationStatus;
use windows_core::{implement,HRESULT};
use crate::{ota_pending,ota_flow::{DeviceQueueCredits,DurableStatusMailbox}};

#[implement(IAsyncOperation<GattCommunicationStatus>,IAsyncInfo)]
struct Pending {
    status:Arc<AtomicI32>,closes:Arc<AtomicUsize>,gets:Arc<AtomicUsize>,
    result:GattCommunicationStatus,
}
impl IAsyncInfo_Impl for Pending_Impl {
    fn Id(&self)->windows_core::Result<u32>{Ok(1)}
    fn Status(&self)->windows_core::Result<AsyncStatus>{Ok(AsyncStatus(self.status.load(Ordering::SeqCst)))}
    fn ErrorCode(&self)->windows_core::Result<HRESULT>{Ok(HRESULT(0x80004005u32 as i32))}
    fn Cancel(&self)->windows_core::Result<()>{self.status.store(AsyncStatus::Canceled.0,Ordering::SeqCst);Ok(())}
    fn Close(&self)->windows_core::Result<()>{self.closes.fetch_add(1,Ordering::SeqCst);Ok(())}
}
impl IAsyncOperation_Impl<GattCommunicationStatus> for Pending_Impl {
    fn SetCompleted(&self,_:Option<&AsyncOperationCompletedHandler<GattCommunicationStatus>>)->windows_core::Result<()>{Ok(())}
    fn Completed(&self)->windows_core::Result<AsyncOperationCompletedHandler<GattCommunicationStatus>>{Err(HRESULT(0x80004001u32 as i32).into())}
    fn GetResults(&self)->windows_core::Result<GattCommunicationStatus>{
        assert_eq!(self.status.load(Ordering::SeqCst),AsyncStatus::Completed.0,"Started must never be drained by this poll");
        self.gets.fetch_add(1,Ordering::SeqCst);Ok(self.result)
    }
}
fn operation(status:AsyncStatus,result:GattCommunicationStatus)->(IAsyncOperation<GattCommunicationStatus>,Arc<AtomicUsize>,Arc<AtomicUsize>){
    let closes=Arc::new(AtomicUsize::new(0));let gets=Arc::new(AtomicUsize::new(0));
    let op: IAsyncOperation<GattCommunicationStatus>=Pending{status:Arc::new(AtomicI32::new(status.0)),closes:closes.clone(),gets:gets.clone(),result}.into();
    (op,closes,gets)
}
fn packet(offset:u32)->Vec<u8>{let mut p=vec![0;219];p[..4].copy_from_slice(&offset.to_le_bytes());p}
fn notice(offset:u32)->Vec<u8>{
    let mut b=vec![0;44];b[..4].copy_from_slice(b"DOV1");b[4]=1;b[5]=denzic_ota_core::STATE_RECEIVING;
    b[8..12].copy_from_slice(&offset.to_le_bytes());b[12..16].copy_from_slice(&(64u32*215).to_le_bytes());
    b[24..28].copy_from_slice(b"WOC4");b[28..30].copy_from_slice(&505u16.to_le_bytes());b[30..32].copy_from_slice(&509u16.to_le_bytes());
    b[32]=64;b[34]=21;b[36]=16;b[40..44].copy_from_slice(&7u32.to_le_bytes());b
}
#[test]
fn pipeline_nonblocking_keeps_started_writes_owned_while_real_partial_credits_refill(){
    let mut pending=Vec::new();let mut still_owned=Vec::new();
    for _ in 0..14 {let(op,c,g)=operation(AsyncStatus::Started,GattCommunicationStatus::Success);pending.push(op);still_owned.push((c,g));}
    let(done,closed,got)=operation(AsyncStatus::Completed,GattCommunicationStatus::Success);pending.push(done);
    let mut credits=DeviceQueueCredits::new(64*215,215,16).unwrap();credits.begin();credits.observe(&notice(0)).unwrap();
    for i in 0..16 {credits.admit(&packet(i*215)).unwrap();}
    assert!(credits.needs_receipt(&packet(16*215)).unwrap());
    let mailbox=DurableStatusMailbox::default();let mut cursor=mailbox.bind(7,64*215).unwrap();mailbox.publish(Ok(notice(8*215)));
    assert!(ota_pending::retire_ready(&mut pending,"test").unwrap());
    assert_eq!(pending.len(),14);assert_eq!(closed.load(Ordering::SeqCst),1);assert_eq!(got.load(Ordering::SeqCst),1);
    let bytes=mailbox.next(&mut cursor,std::time::Instant::now()).unwrap().unwrap();credits.observe(&bytes).unwrap();
    // Only the eight durable boundaries return slots. Local completion of
    // one of the fifteen writes neither grants nor consumes device credit.
    for i in 16..24 {credits.admit(&packet(i*215)).unwrap();}
    assert!(credits.needs_receipt(&packet(24*215)).unwrap());
    assert!(!ota_pending::retire_ready(&mut pending,"test").unwrap());assert_eq!(pending.len(),14);
    for(c,g) in still_owned {assert_eq!(c.load(Ordering::SeqCst),0);assert_eq!(g.load(Ordering::SeqCst),0);}
}
#[test]
fn pipeline_nonblocking_keeps_write_errors_terminal_and_closes_retired_operations(){
    for (state,result,needle) in [(AsyncStatus::Error,GattCommunicationStatus::Success,"async error"),
        (AsyncStatus::Canceled,GattCommunicationStatus::Success,"async canceled"),
        (AsyncStatus::Completed,GattCommunicationStatus::Unreachable,"returned status")] {
        let(op,closes,_)=operation(state,result);let mut pending=vec![op];
        assert!(ota_pending::retire_ready(&mut pending,"test").unwrap_err().contains(needle));
        assert!(pending.is_empty());assert_eq!(closes.load(Ordering::SeqCst),1);
    }
}
