//! Retries follow validated byte progress, never arbitrary GATT activity.
use std::time::{Duration, Instant};

const MAX_RETRIES_WITHOUT_PROGRESS: u8 = 3;

#[derive(Debug, PartialEq, Eq)]
pub(super) enum Next {
    Wait(Duration),
    Retry(u8),
    FirstPacketTimeout,
    Stalled,
}

pub(super) struct PullProgress {
    offset: u32,
    started: Instant,
    first_timeout: Duration,
    retry_interval: Duration,
    last_request_or_progress: Instant,
    retries: u8,
    progressed: bool,
    full_gap: bool,
}

impl PullProgress {
    pub fn new(now: Instant, offset: u32, first_timeout: Duration, retry_interval: Duration) -> Self {
        Self {
            offset,
            started: now,
            first_timeout,
            // A diagnostic setting of zero must not produce a busy retry loop.
            retry_interval: retry_interval.max(Duration::from_millis(50)),
            last_request_or_progress: now,
            retries: 0,
            progressed: false,
            full_gap: false,
        }
    }

    // Called only after the packet passed identity/offset/CRC validation and
    // its original bytes were accepted by the durable receive cursor.
    pub fn advanced(&mut self, offset: u32, now: Instant) {
        if offset > self.offset {
            self.offset = offset;
            self.last_request_or_progress = now;
            self.retries = 0;
            self.progressed = true;
            self.full_gap = false;
        }
    }

    // A full reorder window is evidence of a missing earlier packet. Allow
    // one paced early request, then retain the normal retry spacing and bound.
    // Ordinary two-lane reordering never supplies this hint.
    pub fn missing_offset(&mut self) { self.full_gap = true; }

    pub fn write_budget(&self, now: Instant, normal: Duration) -> Duration {
        if self.progressed { normal } else {
            normal.min(self.first_timeout.saturating_sub(now.saturating_duration_since(self.started)))
        }
    }

    pub fn next(&mut self, now: Instant) -> Next {
        let first_remaining = self.first_timeout
            .saturating_sub(now.saturating_duration_since(self.started));
        if !self.progressed && first_remaining.is_zero() {
            return Next::FirstPacketTimeout;
        }
        let interval = if self.full_gap && self.retries == 0 {
            self.retry_interval.min(Duration::from_millis(100))
        } else { self.retry_interval };
        let until_retry = interval.saturating_sub(
            now.saturating_duration_since(self.last_request_or_progress));
        if !until_retry.is_zero() {
            return Next::Wait(if self.progressed { until_retry } else { until_retry.min(first_remaining) });
        }
        if self.retries >= MAX_RETRIES_WITHOUT_PROGRESS {
            // Keep the existing first-notification allowance, with at most
            // three paced re-arms. An established transfer has a finite exit.
            return if self.progressed { Next::Stalled } else { Next::Wait(first_remaining) };
        }
        self.retries += 1;
        self.full_gap = false;
        self.last_request_or_progress = now;
        Next::Retry(self.retries)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn guard(start: Instant, offset: u32) -> PullProgress {
        PullProgress::new(start, offset, Duration::from_secs(45), Duration::from_millis(800))
    }
    #[test]
    fn missing_first_packet_is_paced_bounded_and_keeps_original_deadline() {
        let start = Instant::now();
        let mut progress = guard(start, 0);
        let mut retries = Vec::new();
        // The production receiver wakes every 50ms even while no data arrives.
        for ms in (50..45_000).step_by(50) {
            match progress.next(start + Duration::from_millis(ms)) {
                Next::Retry(n) => retries.push((ms, n)),
                Next::Wait(_) => {},
                other => panic!("unexpected early exit {other:?}"),
            }
        }
        assert_eq!(retries, [(800, 1), (1_600, 2), (2_400, 3)]);
        assert_eq!(progress.next(start + Duration::from_secs(45)), Next::FirstPacketTimeout);
        assert_eq!(progress.write_budget(start + Duration::from_millis(44_900), Duration::from_secs(8)), Duration::from_millis(100));
    }
    #[test]
    fn duplicate_or_earlier_offsets_cannot_keep_a_stalled_transfer_alive() {
        let start = Instant::now();
        let mut progress = guard(start, 65_632);
        progress.advanced(65_856, start);
        // Continuous duplicate traffic must not renew the retry budget or time.
        for (ms, attempt) in [(800, 1), (1_600, 2), (2_400, 3)] {
            let now = start + Duration::from_millis(ms);
            progress.advanced(65_856, now);
            progress.advanced(0, now);
            assert_eq!(progress.next(now), Next::Retry(attempt));
        }
        assert_eq!(progress.next(start + Duration::from_millis(3_200)), Next::Stalled);
    }
    #[test]
    fn new_validated_bytes_restore_retry_budget_without_a_whole_file_deadline() {
        let start = Instant::now();
        let mut progress = guard(start, 0);
        progress.advanced(224, start);
        for ms in [800, 1_600, 2_400] {
            assert!(matches!(progress.next(start + Duration::from_millis(ms)), Next::Retry(_)));
        }
        let recovered = start + Duration::from_millis(3_199);
        progress.advanced(448, recovered);
        assert_eq!(progress.next(recovered + Duration::from_millis(800)), Next::Retry(1));
        // A progressing two-hour file is not timed out by the first-packet limit.
        let later = start + Duration::from_secs(7_200);
        progress.advanced(672, later);
        assert_eq!(progress.next(later), Next::Wait(Duration::from_millis(800)));
    }
    #[test]
    fn zero_retry_interval_cannot_flood_start_commands() {
        let start = Instant::now();
        let mut progress = PullProgress::new(start, 0, Duration::from_secs(1), Duration::ZERO);
        assert_eq!(progress.next(start), Next::Wait(Duration::from_millis(50)));
        assert_eq!(progress.next(start + Duration::from_millis(50)), Next::Retry(1));
        assert_eq!(progress.next(start + Duration::from_millis(50)), Next::Wait(Duration::from_millis(50)));
    }

    #[test]
    fn full_future_window_recovers_early_once_without_flooding_or_extending_deadlines() {
        let start = Instant::now();
        let mut progress = guard(start, 224);
        progress.advanced(448, start);
        progress.missing_offset();
        assert_eq!(progress.next(start + Duration::from_millis(99)), Next::Wait(Duration::from_millis(1)));
        assert_eq!(progress.next(start + Duration::from_millis(100)), Next::Retry(1));
        // Endless future traffic cannot accelerate the other requests.
        progress.missing_offset();
        assert_eq!(progress.next(start + Duration::from_millis(200)), Next::Wait(Duration::from_millis(700)));
        assert_eq!(progress.next(start + Duration::from_millis(900)), Next::Retry(2));
        progress.missing_offset();
        assert_eq!(progress.next(start + Duration::from_millis(1_700)), Next::Retry(3));
        assert_eq!(progress.next(start + Duration::from_millis(2_500)), Next::Stalled);
        let mut first = guard(start, 0);
        first.missing_offset();
        assert_eq!(first.next(start + Duration::from_millis(100)), Next::Retry(1));
        first.missing_offset();
        assert_eq!(first.next(start + Duration::from_secs(45)), Next::FirstPacketTimeout);
    }
}
