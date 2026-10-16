//! One-way process shutdown. This is transient ownership, never a saved
//! Disconnect/sync-pause preference or a command to stop the board microphone.
use std::sync::{atomic::{AtomicBool,Ordering},Arc,LazyLock};

pub(crate) const CLOSING:&str="Companion Type 正在退出；设备原录音和接收断点保留。";
pub(crate) struct Shutdown {
    requested:AtomicBool,
    signal:tokio::sync::watch::Sender<bool>,
}
impl Shutdown {
    pub(crate) fn new()->Self {
        let(signal,_)=tokio::sync::watch::channel(false);
        Self{requested:AtomicBool::new(false),signal}
    }
    pub(crate) fn requested(&self)->bool {self.requested.load(Ordering::Acquire)}
    pub(crate) fn request(&self) {
        if !self.requested.swap(true,Ordering::AcqRel) {self.signal.send_replace(true);}
    }
    pub(crate) async fn run<T>(&self,work:impl std::future::Future<Output=Result<T,String>>)->Result<T,String> {
        let mut changed=self.signal.subscribe();
        if self.requested() {return Err(CLOSING.into());}
        tokio::select! {
            biased;
            _=changed.changed()=>Err(CLOSING.into()),
            result=work=>if self.requested(){Err(CLOSING.into())}else{result},
        }
    }
}
pub(crate) static PROCESS:LazyLock<Arc<Shutdown>>=LazyLock::new(||Arc::new(Shutdown::new()));

#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn r55_shutdown_interrupts_pending_link_and_rejects_late_or_new_work() {
        let stop=Arc::new(Shutdown::new());let work_stop=stop.clone();
        let(entered,ready)=tokio::sync::oneshot::channel();
        let worker=tokio::spawn(async move {work_stop.run(async {
            let _=entered.send(());std::future::pending::<()>().await;Ok::<_,String>(())
        }).await});
        ready.await.unwrap();stop.request();
        assert_eq!(tokio::time::timeout(std::time::Duration::from_secs(1),worker).await.unwrap().unwrap().unwrap_err(),CLOSING);
        let called=AtomicBool::new(false);
        assert_eq!(stop.run(async {called.store(true,Ordering::Relaxed);Ok(())}).await.unwrap_err(),CLOSING);
        assert!(!called.load(Ordering::Relaxed));
        let late=Shutdown::new();
        assert_eq!(late.run(async {late.request();Ok("late ready")}).await.unwrap_err(),CLOSING);
    }
}
