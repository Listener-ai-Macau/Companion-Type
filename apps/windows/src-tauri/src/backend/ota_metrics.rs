//! New OTA payload accepted by the device over one monotonic bulk window.
//! Resumed bytes, retries and WinRT-call-only timing never inflate the rate.
use std::time::Duration;
use serde::Serialize;
use super::recording_metrics::targets;

#[derive(Default)]
pub(super) struct PayloadWindow {
    total: usize,
    initial: Option<usize>,
    started: Duration,
    completed: Option<Duration>,
    last_time: Duration,
    last_accepted: usize,
    invalid: bool,
}
impl PayloadWindow {
    // The shared OTA engine calls this before the first data window and after
    // each authoritative bytes_written status. Its final repeated callback
    // follows FINISH and must not move the already captured bulk endpoint.
    pub fn observe(&mut self, accepted: usize, total: usize, at: Duration) {
        if total == 0 || accepted > total || at < self.last_time { self.invalid = true; }
        if self.initial.is_none() {
            self.initial = Some(accepted); self.total = total; self.started = at;
        } else if total != self.total || accepted < self.last_accepted { self.invalid = true; }
        self.last_accepted = accepted;
        self.last_time = at;
        if accepted == total && self.completed.is_none() { self.completed = Some(at); }
    }
    pub fn finish(&self, report: &denzic_ota_core::TransferReport, signed_wba: bool) -> PayloadMetrics {
        let initial = self.initial.unwrap_or(report.firmware_bytes);
        let valid = !self.invalid && self.initial.is_some()
            && self.total == report.firmware_bytes && initial == report.resumed_bytes
            && initial <= report.firmware_bytes && report.finish_confirmed;
        let elapsed = self.completed.and_then(|end| end.checked_sub(self.started));
        let new_bytes = if valid { report.firmware_bytes - initial } else { 0 };
        let seconds = elapsed.map(|d| d.as_secs_f64()).unwrap_or(0.0);
        let rate = if valid && new_bytes > 0 && seconds > 0.0 {
            Some(new_bytes as f64 / 1024.0 / seconds)
        } else { None };
        let qualified = signed_wba && valid && new_bytes >= targets::OTA_MINIMUM_NEW_PAYLOAD_BYTES
            && rate.is_some();
        let floor_met = qualified && rate.is_some_and(|r| if targets::OTA_PAYLOAD_DELIVERY_STRICT {
            r > targets::OTA_PAYLOAD_DELIVERY_KIB_S
        } else { r >= targets::OTA_PAYLOAD_DELIVERY_KIB_S });
        PayloadMetrics {
            new_payload_bytes: new_bytes, resumed_bytes: report.resumed_bytes,
            payload_elapsed_us: if valid { elapsed.map(|d| d.as_micros()) } else { None },
            actual_payload_kib_s: rate, rate_basis: "new_device_accepted_payload_bytes",
            timing_basis: "host_first_data_window_to_last_device_bytes_written",
            floor_kib_s: targets::OTA_PAYLOAD_DELIVERY_KIB_S,
            comparison: if targets::OTA_PAYLOAD_DELIVERY_STRICT { "gt" } else { "ge" },
            target_version: targets::VERSION,
            payload_gate: if !qualified { "not_evaluated" } else if floor_met { "met" } else { "not_met" },
            scope: "payload_rate_only", full_chain_acceptance: false,
        }
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PayloadMetrics {
    pub new_payload_bytes: usize,
    pub resumed_bytes: usize,
    pub payload_elapsed_us: Option<u128>,
    pub actual_payload_kib_s: Option<f64>,
    pub rate_basis: &'static str,
    pub timing_basis: &'static str,
    pub floor_kib_s: f64,
    pub comparison: &'static str,
    pub target_version: &'static str,
    pub payload_gate: &'static str,
    pub scope: &'static str,
    pub full_chain_acceptance: bool,
}
impl PayloadMetrics {
    pub(super) fn paired(new_bytes:usize,resumed:usize,elapsed:Option<Duration>)->Self {
        let seconds=elapsed.map(|d|d.as_secs_f64()).unwrap_or(0.0);
        let rate=(new_bytes>0&&seconds>0.0).then(||new_bytes as f64/1024.0/seconds);
        let qualified=new_bytes>=targets::OTA_MINIMUM_NEW_PAYLOAD_BYTES&&rate.is_some();
        let met=qualified&&rate.is_some_and(|r|if targets::OTA_PAYLOAD_DELIVERY_STRICT {r>targets::OTA_PAYLOAD_DELIVERY_KIB_S}else{r>=targets::OTA_PAYLOAD_DELIVERY_KIB_S});
        Self{new_payload_bytes:new_bytes,resumed_bytes:resumed,payload_elapsed_us:elapsed.map(|d|d.as_micros()),
            actual_payload_kib_s:rate,rate_basis:"new_device_accepted_payload_bytes",timing_basis:"first_component_data_window_to_last_component_device_bytes_written",
            floor_kib_s:targets::OTA_PAYLOAD_DELIVERY_KIB_S,comparison:if targets::OTA_PAYLOAD_DELIVERY_STRICT {"gt"}else{"ge"},
            target_version:targets::VERSION,payload_gate:if !qualified {"not_evaluated"}else if met {"met"}else{"not_met"},
            scope:"payload_rate_only",full_chain_acceptance:false}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn report(total: usize, resumed: usize) -> denzic_ota_core::TransferReport {
        denzic_ota_core::TransferReport { firmware_bytes: total, resumed_bytes: resumed,
            data_writes: 3000, status_reads: 100, recovered_offsets: 2, active_link_confirmed: true,
            finish_confirmed: true, timings: denzic_ota_core::TransferTimings::default() }
    }
    #[test]
    fn ota_resume_and_retries_cannot_claim_full_image_rate() {
        let mut w = PayloadWindow::default();
        w.observe(307_200,614_400,Duration::from_secs(3));
        w.observe(409_600,614_400,Duration::from_secs(5));
        w.observe(409_600,614_400,Duration::from_secs(6)); // resend adds no confirmed bytes
        w.observe(614_400,614_400,Duration::from_secs(13));
        w.observe(614_400,614_400,Duration::from_secs(40)); // FINISH latency
        let m = w.finish(&report(614_400,307_200),true);
        assert_eq!(m.new_payload_bytes,307_200);
        assert_eq!(m.payload_elapsed_us,Some(10_000_000));
        assert_eq!(m.actual_payload_kib_s,Some(30.0));
        assert_eq!(m.payload_gate,"not_met");
        assert!(!m.full_chain_acceptance);
    }
    #[test]
    fn ota_floor_inclusive_100_and_full_cache_or_small_tail_is_not_a_speed_sample() {
        let mut w = PayloadWindow::default();
        w.observe(0,614_400,Duration::ZERO);w.observe(614_400,614_400,Duration::from_secs(10));
        assert_eq!(w.finish(&report(614_400,0),true).payload_gate,"not_met");
        let mut w = PayloadWindow::default();
        w.observe(0,614_400,Duration::ZERO);w.observe(614_400,614_400,Duration::from_secs(6));
        assert_eq!(w.finish(&report(614_400,0),true).payload_gate,"met");
        assert_eq!(w.finish(&report(614_400,0),true).comparison,"ge");
        assert_eq!(w.finish(&report(614_400,0),false).payload_gate,"not_evaluated");
        for initial in [614_400,614_399] {
            let mut w = PayloadWindow::default();
            w.observe(initial,614_400,Duration::ZERO);w.observe(614_400,614_400,Duration::from_millis(1));
            let m=w.finish(&report(614_400,initial),true);
            assert_eq!(m.payload_gate,"not_evaluated");
            if initial==614_400 { assert_eq!(m.actual_payload_kib_s,None); }
        }
    }
    #[test]
    fn ota_rounding_cannot_promote_below_100_to_pass() {
        let mut w=PayloadWindow::default();
        w.observe(0,614_400,Duration::ZERO);
        w.observe(614_400,614_400,Duration::from_micros(6_000_010));
        let m=w.finish(&report(614_400,0),true);
        assert_eq!(format!("{:.2}",m.actual_payload_kib_s.unwrap()),"100.00");
        assert_eq!(m.payload_gate,"not_met");
        assert_eq!(m.floor_kib_s,100.0);
    }
    #[test]
    fn ota_wrong_identity_or_bad_time_has_no_numeric_speed_claim() {
        for bad in [0,1,2] {
            let mut w = PayloadWindow::default();w.observe(0,614_400,Duration::from_secs(5));
            w.observe(614_400,614_400,Duration::from_secs(if bad==0 {4} else {10}));
            let mut r=report(614_400,if bad==1 {10} else {0});
            if bad==2 { r.finish_confirmed=false; }
            let m=w.finish(&r,true);
            assert_eq!(m.actual_payload_kib_s,None);assert_eq!(m.payload_gate,"not_evaluated");
        }
    }
    #[test]
    fn a_regressing_receipt_cannot_enter_the_fixed_speed_gate() {
        for after_completion in [false,true] {
            let mut w=PayloadWindow::default();
            w.observe(0,614_400,Duration::from_secs(5));
            w.observe(if after_completion {614_400} else {100_000},614_400,Duration::from_secs(6));
            w.observe(50_000,614_400,Duration::from_secs(7));
            w.observe(614_400,614_400,Duration::from_secs(10));
            let m=w.finish(&report(614_400,0),true);
            assert_eq!(m.actual_payload_kib_s,None);
            assert_eq!(m.payload_gate,"not_evaluated");
            assert_eq!(m.new_payload_bytes,0);
        }
    }
}
