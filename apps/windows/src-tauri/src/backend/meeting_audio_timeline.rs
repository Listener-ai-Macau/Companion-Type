//! Align separately captured PCM tracks to one sample timeline.
//!
//! Audio capture can stop producing callbacks while the system output is
//! silent. Callers supply the actual first sample position of each packet,
//! relative to the common recording start. Missing intervals are written as
//! silence and packets arriving twice or late are not duplicated. This is a
//! building block; it does not start capture, save audio, or expose a UI.

const SILENCE_BLOCK: [i16; 4096] = [0; 4096];

#[allow(dead_code)]
pub(super) struct Timeline {
    next: u64,
}

#[allow(dead_code)]
impl Timeline {
    pub(super) fn new() -> Self {
        Self { next: 0 }
    }

    pub(super) fn samples(&self) -> u64 { self.next }

    /// Write a packet whose first sample is at `first` on the shared timeline.
    /// Packets that begin before the current cursor are trimmed, not replayed.
    /// The writer must either accept a whole slice or return an error without
    /// accepting any of it. A partial disk write must stop and recover the
    /// recording instead of retrying with this cursor.
    pub(super) fn append<E>(
        &mut self,
        first: i64,
        samples: &[i16],
        mut write: impl FnMut(&[i16]) -> Result<(), E>,
    ) -> Result<(), E> {
        if samples.is_empty() {
            return Ok(());
        }
        if first >= 0 && first as u64 > self.next {
            self.pad_to(first as u64, &mut write)?;
        }
        // Signed arithmetic also trims packets that started before the chosen
        // common origin, without wrapping them to an enormous future offset.
        let already_written = (i128::from(self.next) - i128::from(first)).max(0);
        let skip = already_written.min(samples.len() as i128) as usize;
        let remaining = &samples[skip..];
        if !remaining.is_empty() {
            write(remaining)?;
            // A recording cannot practically contain u64::MAX samples, but
            // saturation still avoids wrapping the timeline on malformed data.
            self.next = self.next.saturating_add(remaining.len() as u64);
        }
        Ok(())
    }

    /// Preserve the silent tail up to the actual end of the session.
    pub(super) fn finish<E>(
        &mut self,
        end: u64,
        mut write: impl FnMut(&[i16]) -> Result<(), E>,
    ) -> Result<(), E> {
        self.pad_to(end, &mut write)
    }

    fn pad_to<E>(
        &mut self,
        end: u64,
        write: &mut impl FnMut(&[i16]) -> Result<(), E>,
    ) -> Result<(), E> {
        while self.next < end {
            let count = (end - self.next).min(SILENCE_BLOCK.len() as u64) as usize;
            write(&SILENCE_BLOCK[..count])?;
            self.next += count as u64;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn separate_tracks_keep_start_gaps_overlap_and_silent_tail() {
        let mut system = Timeline::new();
        let mut mic = Timeline::new();
        let mut system_pcm = Vec::new();
        let mut mic_pcm = Vec::new();
        system.append(2, &[1, 2, 3], |p| { system_pcm.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        system.append(4, &[3, 4], |p| { system_pcm.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        system.append(9, &[5], |p| { system_pcm.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        mic.append(0, &[7, 8], |p| { mic_pcm.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        mic.append(9, &[9], |p| { mic_pcm.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        system.finish(12, |p| { system_pcm.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        mic.finish(12, |p| { mic_pcm.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        assert_eq!(system_pcm, [0, 0, 1, 2, 3, 4, 0, 0, 0, 5, 0, 0]);
        assert_eq!(mic_pcm, [7, 8, 0, 0, 0, 0, 0, 0, 0, 9, 0, 0]);
    }

    #[test]
    fn long_silence_is_streamed_in_bounded_blocks() {
        let mut timeline = Timeline::new();
        let mut lengths = Vec::new();
        timeline.append(20_000, &[42], |p| { lengths.push(p.len()); Ok::<_, ()>(()) }).unwrap();
        assert_eq!(lengths, [4096, 4096, 4096, 4096, 3616, 1]);
    }

    #[test]
    fn packet_starting_before_origin_is_trimmed() {
        let mut timeline = Timeline::new();
        let mut output = Vec::new();
        timeline.append(-2, &[1, 2, 3, 4], |p| { output.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        timeline.append(-4, &[5, 6], |p| { output.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        assert_eq!(output, [3, 4]);
        assert_eq!(timeline.next, 2);
    }

    #[test]
    fn failed_atomic_write_does_not_advance_past_what_was_saved() {
        let mut timeline = Timeline::new();
        let mut calls = 0;
        let result = timeline.append(5000, &[7], |_| { calls += 1; if calls == 2 { Err("disk") } else { Ok(()) } });
        assert_eq!(result, Err("disk"));
        assert_eq!(timeline.next, 4096);
        let mut tail = Vec::new();
        timeline.append(5000, &[7], |p| { tail.extend_from_slice(p); Ok::<_, ()>(()) }).unwrap();
        assert_eq!(tail.len(), 905);
        assert_eq!(tail[904], 7);
        assert_eq!(timeline.next, 5001);
    }
}
