//! A live mark travels through the existing capture connection, never a second
//! BLE client. Expired requests cannot turn into surprise marks later.
use std::collections::VecDeque;
use std::sync::{mpsc, Mutex};
use std::time::{Duration, Instant};
use crate::companion_v1::CompanionV1Snapshot;
use super::{Request, LiveStamp};

type Reply = Result<CompanionV1Snapshot, String>;
struct Pending { request: Request, deadline: Instant, reply: mpsc::Sender<Reply> }
struct State { closed: bool, pending: VecDeque<Pending> }
pub(crate) struct LiveQueue { session_id: String, state: Mutex<State> }

impl LiveQueue {
    pub fn new(session_id: &str) -> Self {
        Self { session_id: session_id.into(), state: Mutex::new(State { closed:false, pending:VecDeque::new() }) }
    }
    pub fn enqueue(&self, request: Request) -> Result<mpsc::Receiver<Reply>, String> {
        if request.session_id != self.session_id || request.action != super::Action::AddLive {
            return Err("这个重点不属于当前在线录音。".into());
        }
        let mut state = self.state.lock().map_err(|_| "重点队列暂时不可用。")?;
        if state.closed { return Err("在线录音已结束；请收录后在原音中添加重点。".into()); }
        if state.pending.len() >= 16 { return Err("重点正在保存，请稍后再试。".into()); }
        let (reply, receiver) = mpsc::channel();
        state.pending.push_back(Pending { request, deadline:Instant::now()+Duration::from_secs(25), reply });
        Ok(receiver)
    }
    pub fn has_pending(&self) -> bool {
        self.state.lock().map(|s| !s.closed && !s.pending.is_empty()).unwrap_or(false)
    }
    pub fn stamp<F>(&self, device_id: &str, recording_id:u32, position_ms:u32, mut save:F)
    where F:FnMut(Request,LiveStamp)->Reply {
        self.stamp_key(device_id,recording_id,position_ms,None,&mut save);
    }
    pub fn stamp_logical<F>(&self,device_id:&str,recording_id:u32,position_ms:u32,
        key:&crate::backend::recording_wire::SessionKey,mut save:F)
    where F:FnMut(Request,LiveStamp)->Reply {
        self.stamp_key(device_id,recording_id,position_ms,Some(key.public_key()),&mut save);
    }
    fn stamp_key<F>(&self,device_id:&str,recording_id:u32,position_ms:u32,
        key:Option<crate::companion_v1::CompanionV1RecordingKey>,mut save:F)
    where F:FnMut(Request,LiveStamp)->Reply {
        // Release the queue lock before the coordinator's durable file commit.
        let pending = self.state.lock().map(|mut s| std::mem::take(&mut s.pending)).unwrap_or_default();
        for item in pending {
            let result = if Instant::now() >= item.deadline {
                Err("未及时取得设备录音时间；这次没有添加重点，请重试。".into())
            } else {
                save(item.request, LiveStamp { session_id:self.session_id.clone(), device_id:device_id.into(),
                    recording_id, position_ms:u64::from(position_ms),recording_key:key.clone() })
            };
            let _ = item.reply.send(result);
        }
    }
    pub fn close(&self) {
        if let Ok(mut state) = self.state.lock() {
            state.closed = true;
            for item in state.pending.drain(..) {
                let _ = item.reply.send(Err("录音已结束或连接未恢复；未添加这个重点，可收录后回听标记。".into()));
            }
        }
    }
}

impl Drop for LiveQueue { fn drop(&mut self) { self.close(); } }

#[cfg(test)]
mod tests {
    use super::*;
    fn request(id: &str) -> Request { Request { session_id:id.into(), bookmark_id:uuid::Uuid::new_v4().to_string(),
        expected_revision:0, action:super::super::Action::AddLive, label:None, position_ms:None } }
    #[test]
    fn closed_foreign_and_expired_requests_never_call_save() {
        let q = LiveQueue::new("s");
        assert!(q.enqueue(request("other")).is_err());
        let receiver=q.enqueue(request("s")).unwrap();
        q.state.lock().unwrap().pending[0].deadline=Instant::now()-Duration::from_secs(1);
        q.stamp("dev",1,400,|_,_| panic!("expired mark must not persist"));
        assert!(receiver.recv().unwrap().is_err());
        let receiver=q.enqueue(request("s")).unwrap(); q.close();
        assert!(receiver.recv().unwrap().is_err()); assert!(q.enqueue(request("s")).is_err());
    }
    #[test]
    fn worker_stamp_preserves_actual_identity_and_time() {
        let q=LiveQueue::new("s"); let receiver=q.enqueue(request("s")).unwrap();
        q.stamp("dev",17,2460,|r,s| {
            assert_eq!(r.session_id,s.session_id); assert_eq!(s.device_id,"dev");
            assert_eq!(s.recording_id,17); assert_eq!(s.position_ms,2460);
            assert!(s.recording_key.is_none());
            Ok(crate::companion_v1::fixture_snapshot())
        });
        assert!(receiver.recv().unwrap().is_ok()); assert!(!q.has_pending());
    }
    #[test]
    fn r66_logical_worker_stamp_retains_verified_session_identity() {
        let q=LiveQueue::new("s");let receiver=q.enqueue(request("s")).unwrap();
        let key=crate::backend::recording_wire::SessionKey{device_uid:[0x35;12],format_epoch:7,session_id:23};
        q.stamp_logical("dev",17,2460,&key,|_,stamp| {
            assert_eq!(stamp.recording_key,Some(key.public_key()));
            assert_eq!(stamp.position_ms,2460);
            Ok(crate::companion_v1::fixture_snapshot())
        });
        assert!(receiver.recv().unwrap().is_ok());assert!(!q.has_pending());
    }
}
