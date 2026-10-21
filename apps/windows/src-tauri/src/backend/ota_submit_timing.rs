//! Bounded Windows-host metadata. Never grants credits or changes operation ownership.
use std::time::{Instant,SystemTime,UNIX_EPOCH};

#[derive(Clone,Copy,Default,Debug,serde::Serialize)]
pub(super) struct WriteCosts {
    pub status_calls:u64,pub status_ns:u64,
    pub result_calls:u64,pub result_ns:u64,
    pub close_calls:u64,pub close_ns:u64,
}
#[derive(Clone,Copy)]
pub(super) enum WriteCall {Status,Result,Close}
impl WriteCosts {
    pub fn measure<T>(&mut self,kind:WriteCall,call:impl FnOnce()->T)->T {
        let start=Instant::now();let result=call();
        let elapsed=start.elapsed().as_nanos().min(u64::MAX as u128) as u64;
        let (n,ns)=match kind {
            WriteCall::Status=>(&mut self.status_calls,&mut self.status_ns),
            WriteCall::Result=>(&mut self.result_calls,&mut self.result_ns),
            WriteCall::Close=>(&mut self.close_calls,&mut self.close_ns),
        };
        *n=n.saturating_add(1);*ns=ns.saturating_add(elapsed);result
    }
}
pub(super) fn observe<T>(costs:&mut Option<&mut WriteCosts>,kind:WriteCall,call:impl FnOnce()->T)->T {
    if let Some(costs)=costs.as_deref_mut(){costs.measure(kind,call)}else{call()}
}
fn stamp()->u64 {SystemTime::now().duration_since(UNIX_EPOCH)
    .map(|v|v.as_micros().min(u64::MAX as u128) as u64).unwrap_or(0)}
#[derive(Clone,Debug,serde::Serialize)]
pub(super) struct SubmitProbe {
    pub file_offset:u32,pub submitted_before:u32,pub generation:u32,pub accepted_prefix:u32,
    pub wait_enter_unix_us:u64,pub receipt_observed_unix_us:u64,pub admitted_unix_us:u64,
    pub enqueue_enter_unix_us:u64,pub write_api_enter_unix_us:u64,pub write_api_returned_unix_us:u64,
    pub enqueue_done_unix_us:u64,pub succeeded:bool,
    pub costs_before:WriteCosts,pub costs_at_grant:WriteCosts,pub costs_after:WriteCosts,
}
#[derive(Clone,serde::Serialize)]
pub(super) struct SubmitTrace {
    pub rows:Vec<SubmitProbe>,pub active:Option<SubmitProbe>,pub dropped:u32,
    pub costs:WriteCosts,
}
impl Default for SubmitTrace {
    fn default()->Self{Self{rows:Vec::with_capacity(512),active:None,dropped:0,costs:WriteCosts::default()}}
}
impl SubmitTrace {
    pub fn begin(&mut self,offset:u32,submitted:u32,generation:u32) {
        // Unexpected overlapping metadata is retained as incomplete; never
        // reject, replay or alter an actual write because tracing is full.
        if self.active.is_some(){self.finish(false);}
        self.active=Some(SubmitProbe{file_offset:offset,submitted_before:submitted,generation,accepted_prefix:0,
            wait_enter_unix_us:stamp(),receipt_observed_unix_us:0,admitted_unix_us:0,enqueue_enter_unix_us:0,
            write_api_enter_unix_us:0,write_api_returned_unix_us:0,enqueue_done_unix_us:0,succeeded:false,
            costs_before:self.costs,costs_at_grant:WriteCosts::default(),costs_after:WriteCosts::default()});
    }
    pub fn granted(&mut self,accepted:u32,generation:u32) {
        if let Some(p)=self.active.as_mut(){p.accepted_prefix=accepted;p.generation=generation;
            p.receipt_observed_unix_us=stamp();p.costs_at_grant=self.costs;}
    }
    pub fn admitted(&mut self){if let Some(p)=self.active.as_mut(){p.admitted_unix_us=stamp();}}
    pub fn enqueue(&mut self){if let Some(p)=self.active.as_mut(){p.enqueue_enter_unix_us=stamp();}}
    pub fn api_enter(&mut self){if let Some(p)=self.active.as_mut(){p.write_api_enter_unix_us=stamp();}}
    pub fn api_returned(&mut self){if let Some(p)=self.active.as_mut(){p.write_api_returned_unix_us=stamp();}}
    pub fn finish(&mut self,succeeded:bool) {
        if let Some(mut p)=self.active.take(){p.enqueue_done_unix_us=stamp();p.succeeded=succeeded;p.costs_after=self.costs;
            if self.rows.len()<512{self.rows.push(p)}else{self.dropped=self.dropped.saturating_add(1);}}
    }
}

#[cfg(test)] mod tests {
    use super::*;
    #[test] fn wrapped_result_and_invocation_are_preserved(){
        let mut costs=WriteCosts::default();let mut n=0;
        let result:Result<u8,&str>=costs.measure(WriteCall::Result,||{n+=1;Err("original failure")});
        assert_eq!(result,Err("original failure"));assert_eq!(n,1);assert_eq!(costs.result_calls,1);
        let mut off=None;assert_eq!(observe(&mut off,WriteCall::Close,||17),17);
    }
    #[test] fn incomplete_failure_and_capacity_are_honest(){
        let mut trace=SubmitTrace::default();trace.begin(466,466,7);trace.api_enter();trace.finish(false);
        assert!(!trace.rows[0].succeeded);assert_eq!(trace.rows[0].write_api_returned_unix_us,0);
        for n in 0..513{trace.begin(n,n,7);trace.granted(n,7);trace.admitted();trace.enqueue();trace.api_enter();trace.api_returned();trace.finish(true);}
        assert_eq!(trace.rows.len(),512);assert_eq!(trace.dropped,2);assert!(trace.active.is_none());
    }
    #[test] fn incomplete_active_survives_serialization(){
        let mut trace=SubmitTrace::default();trace.begin(32,32,9);
        let v=serde_json::to_value(&trace).unwrap();assert_eq!(v["active"]["file_offset"],32);
        assert_eq!(v["active"]["receipt_observed_unix_us"],0);assert_eq!(v["rows"].as_array().unwrap().len(),0);
    }
}
