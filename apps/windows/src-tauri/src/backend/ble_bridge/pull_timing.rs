//! Bounded timing of verified original payloads, using native callback times.
//! No packet logging, ATT reads, cached bytes, or changes to transfer behavior.
use std::time::Instant;

const REORDER_TIMESTAMPS: usize = 32;

#[derive(Clone, Copy, Default)]
struct Window {
    first: Option<Instant>,
    last: Option<Instant>,
    bytes: u64,
    packets: u64,
}

#[derive(Clone, Copy)]
struct Gap {
    at: Instant,
    offset: u32,
    us: u64,
}

pub(super) struct PullTiming {
    recording_id: u32,
    initial_offset: u32,
    total_length: u32,
    clock_anchor: Instant,
    unix_anchor_us: i64,
    first: Option<Instant>,
    arrivals: Vec<(Instant, u32)>,
    last_ordered: Option<Instant>,
    late_timestamps: u64,
    gaps: [u64; 8],
    long_gap_us: u64,
    worst: [Option<Gap>; 3],
    windows: [Window; 10],
    completed: bool,
}

impl PullTiming {
    pub fn new(recording_id: u32, initial_offset: u32, total_length: u32) -> Self {
        Self {
            recording_id, initial_offset, total_length,
            clock_anchor: Instant::now(), unix_anchor_us: chrono::Utc::now().timestamp_micros(), first: None,
            arrivals: Vec::with_capacity(REORDER_TIMESTAMPS + 1), last_ordered: None,
            late_timestamps: 0, gaps: [0; 8], long_gap_us: 0, worst: [None; 3],
            windows: [Window::default(); 10], completed: false,
        }
    }

    /// Called once per identity/offset/CRC-checked packet before its disk append.
    /// Validation can occur after reordering; its wall time is never used here.
    pub fn validated(&mut self, offset: u32, bytes: usize, arrived_at: Instant) {
        if bytes == 0 || offset < self.initial_offset || offset >= self.total_length { return; }
        self.first = Some(self.first.map_or(arrived_at, |first| first.min(arrived_at)));
        let remaining = u64::from(self.total_length.saturating_sub(self.initial_offset)).max(1);
        let index = ((u64::from(offset - self.initial_offset) * 10 / remaining) as usize).min(9);
        let window = &mut self.windows[index];
        window.first = Some(window.first.map_or(arrived_at, |first| first.min(arrived_at)));
        window.last = Some(window.last.map_or(arrived_at, |last| last.max(arrived_at)));
        window.bytes += bytes as u64;
        window.packets += 1;
        // Dual lanes can be validated out of timestamp order. Sort a small
        // fixed window; timestamps arriving beyond it are counted explicitly,
        // so their gaps cannot silently be treated as exact radio timing.
        let index = self.arrivals.partition_point(|&(at, _)| at <= arrived_at);
        self.arrivals.insert(index, (arrived_at, offset));
        if self.arrivals.len() > REORDER_TIMESTAMPS { self.flush_oldest(); }
    }

    fn flush_oldest(&mut self) {
        let (at, offset) = self.arrivals.remove(0);
        if let Some(last) = self.last_ordered {
            let Some(gap) = at.checked_duration_since(last) else {
                self.late_timestamps += 1;
                return;
            };
            let us = gap.as_micros().min(u128::from(u64::MAX)) as u64;
            let bucket = [1_000, 5_000, 10_000, 20_000, 50_000, 100_000, 500_000]
                .partition_point(|&bound| us >= bound);
            self.gaps[bucket] += 1;
            if us >= 50_000 { self.long_gap_us += us; }
            let mut candidate = Some(Gap { at, offset, us });
            for slot in &mut self.worst {
                if candidate.is_some_and(|gap| slot.is_none_or(|old| gap.us > old.us)) {
                    std::mem::swap(slot, &mut candidate);
                }
            }
        }
        self.last_ordered = Some(at);
    }

    pub fn completed(&mut self) { self.completed = true; }

    fn unix_us(&self, at: Instant) -> i64 {
        if let Some(after) = at.checked_duration_since(self.clock_anchor) {
            self.unix_anchor_us.saturating_add(after.as_micros().min(i64::MAX as u128) as i64)
        } else {
            self.unix_anchor_us.saturating_sub(self.clock_anchor.duration_since(at)
                .as_micros().min(i64::MAX as u128) as i64)
        }
    }

    fn diagnostics(&mut self) -> Vec<String> {
        while !self.arrivals.is_empty() { self.flush_oldest(); }
        let packets: u64 = self.windows.iter().map(|window| window.packets).sum();
        if packets == 0 { return Vec::new(); }
        let mut lines = vec![format!(
            "recording_pull_arrivals id={} completed={} verified_packets={} cached_prefix_bytes={} timestamp_reorder_capacity={} late_timestamps={} gap_lt1ms={} gap_1to5ms={} gap_5to10ms={} gap_10to20ms={} gap_20to50ms={} gap_50to100ms={} gap_100to500ms={} gap_ge500ms={} gaps_ge50ms_total_ms={:.3} timing_basis=native_callback gaps_scope=verified_payload_observations radio_cause_proven=false native_first_unix_us={} unix_projection=monotonic_anchor",
            self.recording_id, self.completed, packets, self.initial_offset,
            REORDER_TIMESTAMPS, self.late_timestamps, self.gaps[0], self.gaps[1], self.gaps[2],
            self.gaps[3], self.gaps[4], self.gaps[5], self.gaps[6], self.gaps[7],
            self.long_gap_us as f64 / 1000.0, self.unix_us(self.first.unwrap()),
        )];
        for (index, window) in self.windows.iter().enumerate() {
            let (Some(first), Some(last)) = (window.first, window.last) else { continue; };
            let span = last.saturating_duration_since(first).as_secs_f64();
            lines.push(format!(
                "recording_pull_window id={} part={}of10 new_bytes={} packets={} first_ms={:.3} last_ms={:.3} span_ms={:.3} observed_kib_s={:.2} rate_qualified={} timing_basis=native_callback scope=file_progress_window",
                self.recording_id, index + 1, window.bytes, window.packets,
                first.saturating_duration_since(self.first.unwrap()).as_secs_f64() * 1000.0,
                last.saturating_duration_since(self.first.unwrap()).as_secs_f64() * 1000.0,
                span * 1000.0, if span > 0.0 { window.bytes as f64 / 1024.0 / span } else { 0.0 },
                window.packets > 1 && span > 0.0,
            ));
        }
        for (index, gap) in self.worst.iter().flatten().enumerate() {
            lines.push(format!(
                "recording_pull_gap id={} rank={} offset={} at_ms={:.3} gap_ms={:.3} timing_basis=native_callback at_unix_us={} unix_projection=monotonic_anchor",
                self.recording_id, index + 1, gap.offset,
                gap.at.saturating_duration_since(self.first.unwrap()).as_secs_f64() * 1000.0,
                gap.us as f64 / 1000.0, self.unix_us(gap.at),
            ));
        }
        lines
    }
}

impl Drop for PullTiming {
    fn drop(&mut self) {
        // A failed transfer retains its partial timing, without logging in the
        // receive loop or discarding the existing failure/CRC/SHA conclusion.
        for line in self.diagnostics() { eprintln!("{line}"); }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[test]
    fn reordered_validation_keeps_native_gaps_and_resumed_bytes_separate() {
        let start = Instant::now();
        let mut trace = PullTiming::new(20, 500, 1500);
        trace.validated(0, 500, start); // Cached prefix is not reception.
        trace.validated(500, 224, start + Duration::from_millis(4));
        trace.validated(724, 224, start + Duration::from_millis(2));
        trace.validated(948, 224, start + Duration::from_millis(200));
        trace.validated(1172, 224, start + Duration::from_millis(201));
        trace.completed();
        let lines = trace.diagnostics();
        assert!(lines[0].contains("completed=true verified_packets=4 cached_prefix_bytes=500"));
        assert!(lines[0].contains("late_timestamps=0"));
        assert!(lines[0].contains("gap_1to5ms=2"));
        assert!(lines[0].contains("gap_100to500ms=1"));
        assert!(lines[0].contains("gaps_ge50ms_total_ms=196.000"));
        assert!(lines.iter().any(|line| line.contains("rank=1 offset=948 at_ms=198.000 gap_ms=196.000")));
        assert_eq!(trace.windows.iter().map(|window| window.bytes).sum::<u64>(), 896);
    }

    #[test]
    fn timestamp_window_is_bounded_and_exposes_late_callbacks_on_failure() {
        let start = Instant::now();
        let mut trace = PullTiming::new(21, 0, 30_000);
        for index in 0..100 {
            trace.validated(index * 224, 224, start + Duration::from_millis(u64::from(index) + 100));
            assert!(trace.arrivals.len() <= REORDER_TIMESTAMPS);
        }
        trace.validated(22_400, 224, start);
        let lines = trace.diagnostics();
        assert!(lines[0].contains("completed=false verified_packets=101"));
        assert!(lines[0].contains("late_timestamps=1"));
        assert_eq!(trace.gaps.iter().sum::<u64>(), 99);
    }
}
