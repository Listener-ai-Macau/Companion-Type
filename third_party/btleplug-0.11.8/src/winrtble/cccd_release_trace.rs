//! Opt-in release diagnostics for an observed one-second CCCD timeout.
//! Store bounded timestamps while the operation runs; emit once on Drop, after
//! normal return or cancellation. No ATT request, payload, deadline or retry change.
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicU8, Ordering};
use std::time::{Instant, SystemTime, UNIX_EPOCH};
use uuid::Uuid;

static NEXT: AtomicU64 = AtomicU64::new(1);
pub(crate) struct ReleaseTrace {
    id: u64, generation: u64, uuid: Uuid, started: Instant,
    unix_us: Option<u128>, events: [AtomicU64; 13], last: AtomicU8,
    finished: AtomicBool, success: AtomicBool,
}
impl ReleaseTrace {
    pub(crate) fn begin(generation: u64, uuid: Uuid) -> Option<Self> {
        if std::env::var_os("COMPANION_TYPE_TRACE_CCCD_RELEASE").as_deref()
            != Some(std::ffi::OsStr::new("1")) { return None; }
        let trace = Self { id: NEXT.fetch_add(1, Ordering::Relaxed), generation, uuid,
            started: Instant::now(), unix_us: SystemTime::now().duration_since(UNIX_EPOCH).ok().map(|d|d.as_micros()),
            events: std::array::from_fn(|_|AtomicU64::new(0)), last: AtomicU8::new(0),
            finished: AtomicBool::new(false), success: AtomicBool::new(false) };
        trace.event(1); Some(trace)
    }
    pub(crate) fn event(&self, stage: usize) {
        if stage == 0 || stage >= self.events.len() { return; }
        let us = self.started.elapsed().as_micros().min(u128::from(u64::MAX-1)) as u64;
        self.events[stage].store(us+1, Ordering::Relaxed);
        self.last.store(stage as u8, Ordering::Relaxed);
    }
    pub(crate) fn finish(&self, success: bool) {
        self.event(if success {11} else {12});
        self.success.store(success,Ordering::Relaxed);
        self.finished.store(true,Ordering::Relaxed);
    }
}
impl Drop for ReleaseTrace {
    fn drop(&mut self) {
        let names=["unset","mutex_wait_begin","mutex_acquired","ownership_accepted",
            "characteristic_ready","handler_detach_begin","handler_detach_done",
            "cccd_request_begin","cccd_request_created","cccd_wait_begin","cccd_wait_done",
            "return_ok","return_error"];
        let events=(1..self.events.len()).filter_map(|n|{
            let value=self.events[n].load(Ordering::Relaxed);
            (value!=0).then(||format!("{}:{}",names[n],value-1))
        }).collect::<Vec<_>>().join(",");
        let outcome=if !self.finished.load(Ordering::Relaxed) {"future_dropped_before_return"}
            else if self.success.load(Ordering::Relaxed) {"completed_ok"} else {"completed_error"};
        eprintln!("ble_cccd_release_trace schema=1 op={} generation={} uuid={} outcome={} last_stage={} total_us={} anchor_unix_us={} clock_known={} events={} timing=monotonic emit_after_operation=1 physical_cancel_confirmed=0",
            self.id,self.generation,self.uuid,outcome,self.last.load(Ordering::Relaxed),
            self.started.elapsed().as_micros(),self.unix_us.unwrap_or(0),u8::from(self.unix_us.is_some()),events);
    }
}
